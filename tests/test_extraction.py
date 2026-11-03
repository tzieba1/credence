"""The extractor, driven through the real SDK against a fake API."""

import base64
import json
import logging
from collections.abc import Callable
from datetime import date
from decimal import Decimal

import anthropic
import httpx2 as httpx
import pytest

from credence.extraction import USER_INSTRUCTION, Extractor, ModelUnavailable
from tests.conftest import FakeApi, message_body, record_text

PDF = b"%PDF-1.4\n% not really a certificate, but the bytes are opaque to this test\n"


def extractor(api: FakeApi, **kwargs: object) -> Extractor:
    return Extractor(api.client, model="claude-opus-5-5", prompt_version="v1", **kwargs)  # type: ignore[arg-type]


def test_successful_extraction(fake_api: Callable[..., FakeApi]) -> None:
    api = fake_api(message_body(text=record_text(), input_tokens=12_000, output_tokens=150))
    result = extractor(api).extract(PDF)

    assert result.ok and result.failure is None
    assert result.record is not None
    assert result.record.issuer == "Northgate Certification Services Ltd"
    assert result.record.issue_date == date(2024, 3, 14)
    assert result.record.expiry_date == date(2027, 3, 13)
    assert result.record.notes is None
    assert result.stop_reason == "end_turn"
    assert result.model == "claude-opus-5-5"
    assert result.prompt_version == "v1"
    assert result.implementation == "direct"
    assert result.usage.input_tokens == 12_000
    assert result.usage.output_tokens == 150
    # 12,000 * $4 + 150 * $20, per million tokens.
    assert result.cost_usd == Decimal("0.051")
    assert result.latency_ms >= 0
    assert result.request_id == "req_0"
    assert result.raw_output == record_text()


def test_request_shape_matches_the_plan(fake_api: Callable[..., FakeApi]) -> None:
    api = fake_api(message_body(text=record_text()))
    extractor(api, effort="high", max_output_tokens=4096).extract(PDF)

    [request] = api.requests
    assert request["model"] == "claude-opus-5-5"
    assert request["max_tokens"] == 4096
    assert request["system"].startswith("You extract the fields of a certificate")
    assert request["output_config"]["effort"] == "high"
    schema = request["output_config"]["format"]
    assert schema["type"] == "json_schema"
    assert set(schema["schema"]["required"]) == {
        "issuer", "holder", "certificate_number", "issue_date", "expiry_date",
        "scope", "signatory", "notes",
    }  # fmt: skip
    assert schema["schema"]["additionalProperties"] is False
    assert "{default" not in json.dumps(schema)

    [message] = request["messages"]
    document, text = message["content"]
    assert document["type"] == "document"
    assert document["source"]["media_type"] == "application/pdf"
    assert "\n" not in document["source"]["data"]
    assert base64.standard_b64decode(document["source"]["data"]) == PDF
    assert text == {"type": "text", "text": USER_INSTRUCTION}
    assert "fallbacks" not in request


def test_refusal_is_recorded_not_raised(fake_api: Callable[..., FakeApi]) -> None:
    api = fake_api(
        message_body(
            text=None,
            stop_reason="refusal",
            stop_details={"type": "refusal", "category": "cyber", "explanation": "declined"},
            input_tokens=5000,
            output_tokens=0,
        )
    )
    result = extractor(api).extract(PDF)
    assert result.record is None
    assert result.failure == "refusal:cyber"
    assert result.stop_reason == "refusal"
    assert result.cost_usd == Decimal("0.02")  # the input tokens were still billed


def test_max_tokens_with_complete_json_is_still_a_failure(
    fake_api: Callable[..., FakeApi],
) -> None:
    api = fake_api(message_body(text=record_text(), stop_reason="max_tokens"))
    result = extractor(api).extract(PDF)
    assert result.record is None
    assert result.failure == "max_tokens"
    assert result.usage.input_tokens == 1000


def test_truncated_output_is_recorded_without_usage(fake_api: Callable[..., FakeApi]) -> None:
    api = fake_api(message_body(text='{"issuer": "North', stop_reason="max_tokens"))
    result = extractor(api).extract(PDF)
    assert result.record is None
    assert result.failure == "invalid_output"
    assert result.stop_reason is None
    assert result.usage.input_tokens == 0
    assert result.cost_usd == Decimal(0)


def test_cache_tokens_are_priced(fake_api: Callable[..., FakeApi]) -> None:
    api = fake_api(
        message_body(
            text=record_text(), input_tokens=100, output_tokens=0, cache_read=10_000, cache_write=0
        )
    )
    result = extractor(api).extract(PDF)
    assert result.usage.cache_read_input_tokens == 10_000
    assert result.cost_usd == Decimal("0.0024")  # 100 * $4 + 10,000 * $0.20


@pytest.mark.parametrize("status", [500, 502, 529])
def test_server_errors_become_model_unavailable(
    fake_api: Callable[..., FakeApi], status: int
) -> None:
    api = fake_api({"type": "error", "error": {"type": "api_error", "message": "x"}}, status=status)
    with pytest.raises(ModelUnavailable):
        extractor(api).extract(PDF)


def test_rate_limit_becomes_model_unavailable(fake_api: Callable[..., FakeApi]) -> None:
    api = fake_api(
        {"type": "error", "error": {"type": "rate_limit_error", "message": "x"}}, status=429
    )
    with pytest.raises(ModelUnavailable):
        extractor(api).extract(PDF)


def test_bad_request_is_our_bug_and_surfaces(fake_api: Callable[..., FakeApi]) -> None:
    api = fake_api(
        {"type": "error", "error": {"type": "invalid_request_error", "message": "x"}}, status=400
    )
    with pytest.raises(anthropic.BadRequestError):
        extractor(api).extract(PDF)


def test_connection_failure_becomes_model_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    client = anthropic.Anthropic(
        api_key="test-key",
        max_retries=0,
        http_client=anthropic.DefaultHttpxClient(transport=httpx.MockTransport(handler)),
    )
    with pytest.raises(ModelUnavailable):
        Extractor(client, model="claude-opus-5-5", prompt_version="v1").extract(PDF)


def test_logs_carry_no_document_content_or_output(
    fake_api: Callable[..., FakeApi], caplog: pytest.LogCaptureFixture
) -> None:
    api = fake_api(message_body(text=record_text()))
    with caplog.at_level(logging.DEBUG, logger="credence"):
        extractor(api).extract(PDF)
    logged = "\n".join(r.getMessage() for r in caplog.records)
    assert logged, "the call should be logged"
    assert "Northgate" not in logged
    assert "Okonkwo" not in logged
    assert "not really a certificate" not in logged
    assert "claude-opus-5-5" in logged and "end_turn" in logged
