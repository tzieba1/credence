"""Shared fixtures: a real SDK client wired to a fake HTTP transport."""

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import anthropic
import httpx2 as httpx
import pytest


def message_body(
    *,
    text: str | None,
    stop_reason: str = "end_turn",
    model: str = "claude-opus-5-5",
    input_tokens: int = 1000,
    output_tokens: int = 100,
    cache_read: int = 0,
    cache_write: int = 0,
    stop_details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """A Messages API response body, as JSON, with an optional text block."""
    content: list[dict[str, Any]] = [{"type": "thinking", "thinking": "", "signature": "sig"}]
    if text is not None:
        content.append({"type": "text", "text": text})
    return {
        "id": "msg_test",
        "type": "message",
        "role": "assistant",
        "model": model,
        "content": content,
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "stop_details": stop_details,
        "usage": {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cache_read_input_tokens": cache_read,
            "cache_creation_input_tokens": cache_write,
        },
    }


def record_text(**overrides: Any) -> str:
    """The JSON text of a complete, valid Certificate, with any field overridden."""
    record: dict[str, Any] = {
        "issuer": "Northgate Certification Services Ltd",
        "holder": "Harwell Precision Engineering plc",
        "certificate_number": "NCS-QMS-2024-0417",
        "issue_date": "2024-03-14",
        "expiry_date": "2027-03-13",
        "scope": "Design and manufacture of machined aluminium housings for medical devices",
        "signatory": "Margaret Okonkwo",
        "notes": None,
    }
    record.update(overrides)
    return json.dumps(record)


@dataclass
class FakeApi:
    """Answers every request with `responses` in order and keeps what was sent."""

    responses: list[httpx.Response]
    requests: list[dict[str, Any]] = field(default_factory=list)

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(json.loads(request.content))
        if not self.responses:
            raise AssertionError("more requests than canned responses")
        return self.responses.pop(0)

    @property
    def client(self) -> anthropic.Anthropic:
        return anthropic.Anthropic(
            api_key="test-key",
            max_retries=0,
            http_client=anthropic.DefaultHttpxClient(transport=httpx.MockTransport(self.handler)),
        )


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("eval", "the evaluation set (pytest -m eval)")
    group.addoption(
        "--live",
        action="store_true",
        default=False,
        help="call the API, rewrite the fixtures and write a results file (costs money)",
    )
    group.addoption(
        "--model",
        action="append",
        default=None,
        metavar="MODEL",
        help="model(s) to evaluate; default: every model with recorded fixtures, "
        "or the configured model when --live",
    )
    group.addoption(
        "--prompt", default=None, metavar="VERSION", help="prompt version; default: configured"
    )


@pytest.fixture
def fake_api() -> Callable[..., FakeApi]:
    def make(*bodies: dict[str, Any], status: int = 200) -> FakeApi:
        responses = [
            httpx.Response(status, json=body, headers={"request-id": f"req_{i}"})
            for i, body in enumerate(bodies)
        ]
        return FakeApi(responses=responses)

    return make
