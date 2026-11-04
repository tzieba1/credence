"""The evaluation suite: pytest -m eval [--live] [--model M ...] [--prompt V].

Recorded mode (the default, and what CI runs) replays the fixtures under
eval/fixtures/<prompt>/<model>/ and fails if accuracy drops below the floors
in eval/thresholds.json. With no fixtures recorded it skips. Live mode calls
the API, rewrites the fixtures and writes eval/results/<timestamp>-....
"""

import os
from pathlib import Path

import pytest

from credence.config import Settings
from credence.evaluation.cases import DEFAULT_EVAL_DIR
from credence.evaluation.runner import Report, RunSpec, execute, load_thresholds, write_results
from credence.synth.fields import GOLD_KEYS

EVAL_DIR = Path(__file__).resolve().parents[1] / DEFAULT_EVAL_DIR


def _planned_runs(config: pytest.Config) -> list[RunSpec]:
    settings = Settings()
    live = bool(config.getoption("--live"))
    prompt = config.getoption("--prompt") or settings.prompt_version
    models = config.getoption("--model")
    if models is None:
        if live:
            models = [settings.extraction_model]
        else:
            recorded = EVAL_DIR / "fixtures" / prompt
            models = sorted(p.name for p in recorded.iterdir()) if recorded.is_dir() else []
    return [RunSpec(model=m, prompt_version=prompt, live=live) for m in models]


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    if "run_spec" in metafunc.fixturenames:
        runs = _planned_runs(metafunc.config)
        metafunc.parametrize("run_spec", runs, ids=[r.label for r in runs], scope="session")


@pytest.fixture(scope="session")
def report(run_spec: RunSpec) -> Report:
    if run_spec.live and not os.environ.get("ANTHROPIC_API_KEY"):
        pytest.fail("--live needs ANTHROPIC_API_KEY in the environment")
    result = execute(run_spec, eval_dir=EVAL_DIR)
    if run_spec.live:
        json_path, md_path = write_results(result, EVAL_DIR)
        print(f"\nresults written to {json_path} and {md_path}\n")
        print(result.markdown())
    return result


@pytest.mark.eval
def test_nothing_recorded_is_a_skip_not_a_pass(request: pytest.FixtureRequest) -> None:
    if not _planned_runs(request.config):
        pytest.skip("no fixtures recorded yet: run pytest -m eval --live to record them")


@pytest.mark.eval
@pytest.mark.parametrize("field", GOLD_KEYS)
def test_field_accuracy_holds(report: Report, field: str) -> None:
    floor = load_thresholds(EVAL_DIR, report.spec.model).field_accuracy
    metrics = report.summary.fields[field]
    assert metrics.accuracy >= floor, (
        f"{field} accuracy {metrics.accuracy:.2f} is below the floor {floor:.2f} "
        f"for {report.spec.label}; wrong on {', '.join(metrics.wrong_cases)}"
    )


@pytest.mark.eval
def test_document_accuracy_holds(report: Report) -> None:
    floor = load_thresholds(EVAL_DIR, report.spec.model).document_accuracy
    wrong = [r.case_id for r in report.results if not r.all_correct]
    assert report.summary.document_accuracy >= floor, (
        f"document accuracy {report.summary.document_accuracy:.2f} is below the floor "
        f"{floor:.2f} for {report.spec.label}; wrong: {', '.join(wrong)}"
    )
