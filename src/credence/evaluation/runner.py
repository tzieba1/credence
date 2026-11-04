"""Run the set, live or recorded, and write what came out."""

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from credence.config import Settings
from credence.evaluation.cases import DEFAULT_EVAL_DIR, EvalCase, load_cases
from credence.evaluation.compare import CaseResult, score
from credence.evaluation.fixtures import (
    Fixture,
    MissingFixture,
    fixture_dir,
    read_fixtures,
    replay_client,
    write_fixture,
)
from credence.evaluation.metrics import Summary, markdown_report, summarise
from credence.extraction import Extractor

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class RunSpec:
    model: str
    prompt_version: str
    live: bool
    implementation: str = "direct"

    @property
    def label(self) -> str:
        return f"{self.model}-{self.prompt_version}-{self.implementation}"


@dataclass(frozen=True)
class Report:
    spec: RunSpec
    started_at: datetime
    results: list[CaseResult]
    summary: Summary

    def markdown(self) -> str:
        return markdown_report(
            self.summary,
            self.results,
            model=self.spec.model,
            prompt_version=self.spec.prompt_version,
            implementation=self.spec.implementation,
        )

    def to_json(self) -> dict[str, Any]:
        return {
            "model": self.spec.model,
            "prompt_version": self.spec.prompt_version,
            "implementation": self.spec.implementation,
            "live": self.spec.live,
            "started_at": self.started_at.isoformat(),
            "summary": {
                "cases": self.summary.cases,
                "document_accuracy": self.summary.document_accuracy,
                "documents_correct": self.summary.documents_correct,
                "failures": self.summary.failures,
                "total_cost_usd": str(self.summary.total_cost_usd),
                "cost_per_document_usd": str(self.summary.cost_per_document_usd),
                "latency_p50_ms": self.summary.latency_p50_ms,
                "latency_max_ms": self.summary.latency_max_ms,
                "fields": {
                    key: {
                        "accuracy": f.accuracy,
                        "present_precision": f.present_precision,
                        "present_recall": f.present_recall,
                        "wrong_cases": list(f.wrong_cases),
                    }
                    for key, f in self.summary.fields.items()
                },
            },
            "cases": [
                {
                    "case_id": r.case_id,
                    "correct": r.correct,
                    "predicted": r.predicted,
                    "gold": r.gold,
                    "notes": r.notes,
                    "failure": r.failure,
                    "stop_reason": r.stop_reason,
                    "input_tokens": r.usage.input_tokens,
                    "output_tokens": r.usage.output_tokens,
                    "cost_usd": str(r.cost_usd),
                    "latency_ms": r.latency_ms,
                    "request_id": r.request_id,
                }
                for r in self.results
            ],
        }


def run_live(
    cases: list[EvalCase], extractor: Extractor, fixtures: Path, started_at: datetime
) -> list[CaseResult]:
    """Call the API for every case and overwrite its fixture."""
    results: list[CaseResult] = []
    for case in cases:
        extraction = extractor.extract(case.pdf)
        if extraction.api_response is not None:
            write_fixture(
                fixtures,
                Fixture(
                    case_id=case.id,
                    document_sha256=case.sha256,
                    model=extractor.model,
                    prompt_version=extractor.prompt_version,
                    recorded_at=started_at.isoformat(),
                    latency_ms=extraction.latency_ms,
                    request_id=extraction.request_id,
                    response=extraction.api_response,
                ),
            )
        else:
            log.warning("eval: no response to record for %s (%s)", case.id, extraction.failure)
        results.append(score(case, extraction))
        log.info(
            "eval: %s %s", case.id, "ok" if results[-1].all_correct else results[-1].wrong_fields
        )
    return results


def run_recorded(
    cases: list[EvalCase], fixtures: dict[str, Fixture], *, model: str, prompt_version: str
) -> list[CaseResult]:
    """Replay the fixtures through the real extraction code."""
    missing = [c.id for c in cases if c.id not in fixtures]
    if missing:
        raise MissingFixture(
            f"{len(missing)} case(s) have no fixture for {prompt_version}/{model}: "
            f"{', '.join(missing)}. Record them with: pytest -m eval --live --model {model}"
        )
    extractor = Extractor(replay_client(fixtures), model=model, prompt_version=prompt_version)
    return [
        score(case, extractor.extract(case.pdf), latency_ms=fixtures[case.id].latency_ms)
        for case in cases
    ]


def execute(
    spec: RunSpec, *, eval_dir: Path = DEFAULT_EVAL_DIR, settings: Settings | None = None
) -> Report:
    started_at = datetime.now(UTC).replace(microsecond=0)
    cases = load_cases(eval_dir)
    fixtures_path = fixture_dir(eval_dir, spec.prompt_version, spec.model)
    if spec.live:
        extractor = Extractor.from_settings(
            settings or Settings(), model=spec.model, prompt_version=spec.prompt_version
        )
        results = run_live(cases, extractor, fixtures_path, started_at)
    else:
        results = run_recorded(
            cases,
            read_fixtures(fixtures_path),
            model=spec.model,
            prompt_version=spec.prompt_version,
        )
    return Report(spec=spec, started_at=started_at, results=results, summary=summarise(results))


def write_results(report: Report, eval_dir: Path = DEFAULT_EVAL_DIR) -> tuple[Path, Path]:
    """eval/results/<timestamp>-<model>-<prompt>-<implementation>.{json,md}"""
    directory = eval_dir / "results"
    directory.mkdir(parents=True, exist_ok=True)
    stem = f"{report.started_at:%Y%m%d-%H%M%S}-{report.spec.label}"
    json_path = directory / f"{stem}.json"
    md_path = directory / f"{stem}.md"
    json_path.write_text(json.dumps(report.to_json(), indent=2, ensure_ascii=False) + "\n")
    md_path.write_text(report.markdown())
    return json_path, md_path


@dataclass(frozen=True)
class Thresholds:
    field_accuracy: float
    document_accuracy: float


def load_thresholds(eval_dir: Path, model: str) -> Thresholds:
    """Per-model floors from eval/thresholds.json. A model without an entry has no floor."""
    path = eval_dir / "thresholds.json"
    table: dict[str, dict[str, float]] = json.loads(path.read_text()) if path.is_file() else {}
    entry = table.get(model, {})
    return Thresholds(
        field_accuracy=entry.get("field_accuracy", 0.0),
        document_accuracy=entry.get("document_accuracy", 0.0),
    )
