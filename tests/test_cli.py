import json
from collections.abc import Callable
from pathlib import Path

import pytest

from credence import cli
from credence.config import Settings
from credence.extraction import Extractor
from tests.conftest import FakeApi, message_body, record_text


def _install(monkeypatch: pytest.MonkeyPatch, api: FakeApi) -> None:
    def from_settings(
        settings: Settings, *, model: str | None = None, prompt_version: str | None = None
    ) -> Extractor:
        return Extractor(
            api.client, model=model or "claude-opus-5-5", prompt_version=prompt_version or "v1"
        )

    monkeypatch.setattr(Extractor, "from_settings", from_settings)


def test_extract_prints_record_and_cost(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    fake_api: Callable[..., FakeApi],
) -> None:
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"%PDF-1.4 test")
    _install(monkeypatch, fake_api(message_body(text=record_text(), input_tokens=10_000)))

    assert cli.main(["extract", str(pdf)]) == 0
    out = capsys.readouterr().out
    assert "issuer              Northgate Certification Services Ltd" in out
    assert "notes               -" in out
    assert "cost $0.0420" in out
    assert "stop end_turn" in out


def test_extract_json_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    fake_api: Callable[..., FakeApi],
) -> None:
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"%PDF-1.4 test")
    _install(monkeypatch, fake_api(message_body(text=record_text())))

    assert cli.main(["extract", str(pdf), "--json", "--prompt", "v1"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["record"]["issue_date"] == "2024-03-14"
    assert data["usage"]["input_tokens"] == 1000
    assert data["prompt_version"] == "v1"


def test_failed_extraction_exits_nonzero(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    fake_api: Callable[..., FakeApi],
) -> None:
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"%PDF-1.4 test")
    _install(
        monkeypatch,
        fake_api(
            message_body(
                text=None,
                stop_reason="refusal",
                stop_details={"type": "refusal", "category": None, "explanation": None},
            )
        ),
    )
    assert cli.main(["extract", str(pdf)]) == 1
    assert "no record: refusal" in capsys.readouterr().out
