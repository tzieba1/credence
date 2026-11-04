"""The runner, end to end, offline: record fixtures from a fake API, replay them, score them."""

import json
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from credence.evaluation.cases import load_cases
from credence.evaluation.compare import normalise, predicted_fields
from credence.evaluation.fixtures import MissingFixture, fixture_dir, read_fixtures
from credence.evaluation.metrics import results_table_row, summarise
from credence.evaluation.runner import (
    RunSpec,
    execute,
    load_thresholds,
    run_live,
    run_recorded,
    write_results,
)
from credence.extraction import Extractor
from credence.schema import Certificate
from credence.synth import CASES
from credence.synth.__main__ import write_case
from tests.conftest import FakeApi, message_body

SUBSET = ["g01-classic-en-iso", "g05-letter-en-no-expiry", "n01-invoice-en"]


@pytest.fixture
def eval_dir(tmp_path: Path) -> Path:
    """A small eval directory with three real cases rendered into it."""
    for spec in CASES:
        if spec.id in SUBSET:
            write_case(spec, tmp_path / "cases")
    (tmp_path / "thresholds.json").write_text(
        json.dumps({"claude-opus-5-5": {"field_accuracy": 0.5, "document_accuracy": 0.5}})
    )
    return tmp_path


def _answers(eval_dir: Path) -> list[dict[str, object]]:
    """One canned API response per case, in case order: perfect, one wrong field, perfect."""
    cases = load_cases(eval_dir)
    bodies = []
    for case in cases:
        gold = dict(case.gold)
        if case.id == "g05-letter-en-no-expiry":
            gold["expiry_date"] = "2025-05-26"  # a guessed expiry where the gold is null
        bodies.append(message_body(text=json.dumps({**gold, "notes": None}), input_tokens=2000))
    return bodies


@pytest.mark.parametrize(
    ("a", "b"),
    [
        ("Northgate  Certification\nServices Ltd", "northgate certification services ltd"),
        ("Étienne Rousseau", "Étienne rousseau"),
        (None, None),
    ],
)
def test_normalise_equates(a: str | None, b: str | None) -> None:
    assert normalise(a) == normalise(b)


def test_normalise_keeps_real_differences() -> None:
    assert normalise("NCS-QMS-2024-0417") != normalise("NCS-QMS-2024-0471")
    assert normalise("2024-03-14") != normalise(None)


def test_predicted_fields_drop_notes_and_render_dates() -> None:
    record = Certificate.model_validate(
        {
            "issuer": "A", "holder": None, "certificate_number": "1", "issue_date": "2024-03-14",
            "expiry_date": None, "scope": None, "signatory": None, "notes": "n",
        }
    )  # fmt: skip
    fields = predicted_fields(record)
    assert "notes" not in fields
    assert fields["issue_date"] == "2024-03-14"
    assert predicted_fields(None) == dict.fromkeys(fields)


def test_live_run_records_fixtures_and_recorded_run_replays_them(
    eval_dir: Path, fake_api: Callable[..., FakeApi]
) -> None:
    cases = load_cases(eval_dir)
    api = fake_api(*_answers(eval_dir))
    extractor = Extractor(api.client, model="claude-opus-5-5", prompt_version="v1")
    fixtures_path = fixture_dir(eval_dir, "v1", "claude-opus-5-5")
    started = datetime(2026, 11, 3, 12, 0, tzinfo=UTC)

    live = run_live(cases, extractor, fixtures_path, started)
    assert [r.all_correct for r in live] == [True, False, True]
    assert live[1].wrong_fields == ["expiry_date"]

    fixtures = read_fixtures(fixtures_path)
    assert set(fixtures) == set(SUBSET)
    assert fixtures["g01-classic-en-iso"].document_sha256 == cases[0].sha256
    assert fixtures["g01-classic-en-iso"].response["stop_reason"] == "end_turn"

    recorded = run_recorded(cases, fixtures, model="claude-opus-5-5", prompt_version="v1")
    assert [r.correct for r in recorded] == [r.correct for r in live]
    assert [r.cost_usd for r in recorded] == [r.cost_usd for r in live]
    assert [r.request_id for r in recorded] == [r.request_id for r in live]
    assert [r.latency_ms for r in recorded] == [r.latency_ms for r in live]


def test_recorded_run_fails_loudly_when_a_fixture_is_missing(eval_dir: Path) -> None:
    cases = load_cases(eval_dir)
    with pytest.raises(MissingFixture, match="3 case\\(s\\) have no fixture"):
        run_recorded(cases, {}, model="claude-opus-5-5", prompt_version="v1")


def test_summary_metrics(eval_dir: Path, fake_api: Callable[..., FakeApi]) -> None:
    cases = load_cases(eval_dir)
    api = fake_api(*_answers(eval_dir))
    extractor = Extractor(api.client, model="claude-opus-5-5", prompt_version="v1")
    results = run_live(cases, extractor, eval_dir / "scratch", datetime.now(UTC))
    summary = summarise(results)

    assert summary.cases == 3
    assert summary.documents_correct == 2
    assert summary.document_accuracy == pytest.approx(2 / 3)
    assert summary.failures == 0
    expiry = summary.fields["expiry_date"]
    assert expiry.accuracy == pytest.approx(2 / 3)
    assert expiry.wrong_cases == ("g05-letter-en-no-expiry",)
    # Gold has an expiry only for g01; the model filled it for g01 and g05.
    assert expiry.present_precision == pytest.approx(1 / 2)
    assert expiry.present_recall == pytest.approx(1.0)
    # The invoice: gold all null, predicted all null, so present precision is undefined.
    assert summary.fields["issuer"].present_precision == pytest.approx(1.0)
    assert summary.total_cost_usd == Decimal("0.03")  # 3 * (2000 * $4 + 100 * $20) / 1e6
    assert summary.cost_per_document_usd == Decimal("0.01")
    row = results_table_row(summary, model="m", prompt_version="v1", implementation="direct")
    assert row.startswith(
        "| m | v1 | direct | 1.00 | 1.00 | 1.00 | 1.00 | 0.67 | 1.00 | 1.00 | 0.67 |"
    )


def test_execute_recorded_and_write_results(
    eval_dir: Path, fake_api: Callable[..., FakeApi], monkeypatch: pytest.MonkeyPatch
) -> None:
    # Record through a patched live extractor, then replay through execute().
    api = fake_api(*_answers(eval_dir))
    monkeypatch.setattr(
        Extractor,
        "from_settings",
        lambda settings, *, model, prompt_version: Extractor(
            api.client, model=model, prompt_version=prompt_version
        ),
    )
    live = execute(RunSpec("claude-opus-5-5", "v1", live=True), eval_dir=eval_dir)
    recorded = execute(RunSpec("claude-opus-5-5", "v1", live=False), eval_dir=eval_dir)
    assert recorded.summary.document_accuracy == live.summary.document_accuracy

    json_path, md_path = write_results(recorded, eval_dir)
    data = json.loads(json_path.read_text())
    assert data["summary"]["documents_correct"] == 2
    assert data["cases"][1]["correct"]["expiry_date"] is False
    md = md_path.read_text()
    assert "| g05-letter-en-no-expiry | expiry_date | '2025-05-26' | None |" in md
    assert "claude-opus-5-5-v1-direct" in json_path.name


def test_thresholds_default_to_zero_for_unknown_model(eval_dir: Path) -> None:
    assert load_thresholds(eval_dir, "claude-opus-5-5").field_accuracy == 0.5
    assert load_thresholds(eval_dir, "claude-other").field_accuracy == 0.0
