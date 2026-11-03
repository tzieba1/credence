"""One document in, one typed record out, with everything the call cost.

The call shape is fixed here: the PDF goes in as a document block ahead of a
short instruction, the system prompt is a versioned file, and the SDK
validates the model's JSON against `Certificate`. What the service adds is
the bookkeeping around the call: stop reason checked before the record is
trusted, usage priced, latency measured, failures recorded rather than raised.

Nothing in this module logs document content or model output.
"""

import base64
import hashlib
import logging
import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

import anthropic
import pydantic

from credence import prompts
from credence.config import Effort, Settings
from credence.pricing import Usage, cost_usd
from credence.schema import Certificate

log = logging.getLogger(__name__)

Implementation = Literal["direct", "langgraph"]

USER_INSTRUCTION = "Extract the certificate's fields."


class ModelUnavailable(Exception):
    """The API could not be reached or did not answer. The caller should say 503."""


@dataclass(frozen=True)
class Extraction:
    record: Certificate | None
    """The validated record, or None when `failure` says why there is none."""
    failure: str | None
    """None on success. Otherwise a short reason: refusal, max_tokens, invalid_output."""
    model: str
    prompt_version: str
    implementation: Implementation
    usage: Usage
    cost_usd: Decimal
    latency_ms: int
    stop_reason: str | None
    """As the API reported it; None when the SDK raised before exposing the response."""
    request_id: str | None
    raw_output: str | None
    """The model's text output, verbatim, for fixtures. Never logged."""

    @property
    def ok(self) -> bool:
        return self.failure is None


class Extractor:
    def __init__(
        self,
        client: anthropic.Anthropic,
        *,
        model: str,
        prompt_version: str,
        effort: Effort = "medium",
        max_output_tokens: int = 16000,
    ) -> None:
        self._client = client
        self.model = model
        self.prompt_version = prompt_version
        self._system_prompt = prompts.load(prompt_version)
        self._effort: Effort = effort
        self._max_output_tokens = max_output_tokens

    @classmethod
    def from_settings(
        cls, settings: Settings, *, model: str | None = None, prompt_version: str | None = None
    ) -> "Extractor":
        # The SDK reads ANTHROPIC_API_KEY itself and retries 429 and 5xx twice.
        client = anthropic.Anthropic(timeout=settings.request_timeout_s)
        return cls(
            client,
            model=model or settings.extraction_model,
            prompt_version=prompt_version or settings.prompt_version,
            effort=settings.effort,
            max_output_tokens=settings.max_output_tokens,
        )

    def extract(self, pdf: bytes) -> Extraction:
        digest = hashlib.sha256(pdf).hexdigest()[:12]
        pdf_b64 = base64.standard_b64encode(pdf).decode("ascii")
        started = time.perf_counter()
        try:
            response = self._client.messages.parse(
                model=self.model,
                max_tokens=self._max_output_tokens,
                system=self._system_prompt,
                output_config={"effort": self._effort},
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "document",
                                "source": {
                                    "type": "base64",
                                    "media_type": "application/pdf",
                                    "data": pdf_b64,
                                },
                            },
                            {"type": "text", "text": USER_INSTRUCTION},
                        ],
                    }
                ],
                output_format=Certificate,
            )
        except pydantic.ValidationError:
            # The SDK validates the output before we can look at stop_reason, so a
            # response cut off by max_tokens surfaces here, and its usage with it.
            latency_ms = _elapsed_ms(started)
            log.warning(
                "extraction %s: output did not match the schema (%d ms)", digest, latency_ms
            )
            return self._failed("invalid_output", latency_ms)
        except anthropic.APITimeoutError as exc:
            raise ModelUnavailable("the model API did not answer in time") from exc
        except anthropic.APIConnectionError as exc:
            raise ModelUnavailable("the model API could not be reached") from exc
        except anthropic.RateLimitError as exc:
            raise ModelUnavailable("the model API is rate limiting requests") from exc
        except anthropic.APIStatusError as exc:
            if exc.status_code >= 500:
                raise ModelUnavailable(f"the model API answered {exc.status_code}") from exc
            raise  # 4xx other than 429 is our mistake, not the API's: let it surface.

        latency_ms = _elapsed_ms(started)
        usage = Usage.from_api(response.usage)
        cost = cost_usd(self.model, usage)
        raw_output = next((b.text for b in response.content if b.type == "text"), None)

        failure: str | None = None
        record: Certificate | None = None
        if response.stop_reason == "end_turn":
            record = response.parsed_output
            if record is None:
                failure = "no_output"
        elif response.stop_reason == "refusal":
            category = response.stop_details.category if response.stop_details else None
            failure = f"refusal:{category}" if category else "refusal"
        else:
            failure = response.stop_reason or "unknown_stop"

        log.info(
            "extraction %s: bytes=%d model=%s prompt=%s stop=%s in=%d out=%d cost=%.5f "
            "latency=%dms%s",
            digest,
            len(pdf),
            response.model,
            self.prompt_version,
            response.stop_reason,
            usage.input_tokens,
            usage.output_tokens,
            cost,
            latency_ms,
            f" failure={failure}" if failure else "",
        )
        return Extraction(
            record=record,
            failure=failure,
            model=response.model,
            prompt_version=self.prompt_version,
            implementation="direct",
            usage=usage,
            cost_usd=cost,
            latency_ms=latency_ms,
            stop_reason=response.stop_reason,
            request_id=response._request_id,
            raw_output=raw_output,
        )

    def _failed(self, failure: str, latency_ms: int) -> Extraction:
        return Extraction(
            record=None,
            failure=failure,
            model=self.model,
            prompt_version=self.prompt_version,
            implementation="direct",
            usage=Usage.none(),
            cost_usd=Decimal(0),
            latency_ms=latency_ms,
            stop_reason=None,
            request_id=None,
            raw_output=None,
        )


def _elapsed_ms(started: float) -> int:
    return round((time.perf_counter() - started) * 1000)
