"""Aggregate case results into the numbers the README reports."""

import statistics
from dataclasses import dataclass
from decimal import Decimal

from credence.evaluation.compare import CaseResult
from credence.synth.fields import GOLD_KEYS


@dataclass(frozen=True)
class FieldMetrics:
    accuracy: float
    """Share of cases where the field matched the gold after normalisation."""
    present_precision: float | None
    """Of the cases where the model filled the field, the share where the gold has it too."""
    present_recall: float | None
    """Of the cases where the gold has the field, the share where the model filled it."""
    wrong_cases: tuple[str, ...]


@dataclass(frozen=True)
class Summary:
    cases: int
    fields: dict[str, FieldMetrics]
    document_accuracy: float
    documents_correct: int
    failures: int
    total_cost_usd: Decimal
    cost_per_document_usd: Decimal
    latency_p50_ms: int
    latency_max_ms: int


def _ratio(numerator: int, denominator: int) -> float | None:
    return None if denominator == 0 else numerator / denominator


def summarise(results: list[CaseResult]) -> Summary:
    if not results:
        raise ValueError("no results to summarise")
    fields: dict[str, FieldMetrics] = {}
    for key in GOLD_KEYS:
        correct = sum(r.correct[key] for r in results)
        predicted_present = [r for r in results if r.predicted[key] is not None]
        gold_present = [r for r in results if r.gold[key] is not None]
        both = sum(1 for r in predicted_present if r.gold[key] is not None)
        fields[key] = FieldMetrics(
            accuracy=correct / len(results),
            present_precision=_ratio(both, len(predicted_present)),
            present_recall=_ratio(both, len(gold_present)),
            wrong_cases=tuple(r.case_id for r in results if not r.correct[key]),
        )
    documents_correct = sum(r.all_correct for r in results)
    total_cost = sum((r.cost_usd for r in results), Decimal(0))
    latencies = sorted(r.latency_ms for r in results)
    return Summary(
        cases=len(results),
        fields=fields,
        document_accuracy=documents_correct / len(results),
        documents_correct=documents_correct,
        failures=sum(r.failure is not None for r in results),
        total_cost_usd=total_cost,
        cost_per_document_usd=total_cost / len(results),
        latency_p50_ms=round(statistics.median(latencies)),
        latency_max_ms=latencies[-1],
    )


_SHORT = {
    "issuer": "issuer",
    "holder": "holder",
    "certificate_number": "number",
    "issue_date": "issue",
    "expiry_date": "expiry",
    "scope": "scope",
    "signatory": "signatory",
}


def results_table_header() -> str:
    cols = ["model", "prompt", "impl", *(_SHORT[k] for k in GOLD_KEYS), "doc", "$/doc", "p50 ms"]
    return "| " + " | ".join(cols) + " |\n|" + "---|" * len(cols)


def results_table_row(
    summary: Summary, *, model: str, prompt_version: str, implementation: str
) -> str:
    cells = [
        model,
        prompt_version,
        implementation,
        *(f"{summary.fields[k].accuracy:.2f}" for k in GOLD_KEYS),
        f"{summary.document_accuracy:.2f}",
        f"{summary.cost_per_document_usd:.4f}",
        str(summary.latency_p50_ms),
    ]
    return "| " + " | ".join(cells) + " |"


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2f}"


def markdown_report(
    summary: Summary,
    results: list[CaseResult],
    *,
    model: str,
    prompt_version: str,
    implementation: str,
) -> str:
    lines = [
        f"## {model}, prompt {prompt_version}, {implementation}",
        "",
        f"{summary.cases} cases, {summary.documents_correct} fully correct "
        f"({summary.document_accuracy:.2f}), {summary.failures} failed calls. "
        f"Total ${summary.total_cost_usd:.4f}, ${summary.cost_per_document_usd:.4f} per document, "
        f"latency p50 {summary.latency_p50_ms} ms, max {summary.latency_max_ms} ms.",
        "",
        results_table_header(),
        results_table_row(
            summary, model=model, prompt_version=prompt_version, implementation=implementation
        ),
        "",
        "| field | accuracy | present precision | present recall | wrong cases |",
        "|---|---|---|---|---|",
    ]
    for key in GOLD_KEYS:
        f = summary.fields[key]
        lines.append(
            f"| {key} | {f.accuracy:.2f} | {_pct(f.present_precision)} | {_pct(f.present_recall)} "
            f"| {', '.join(f.wrong_cases) or '-'} |"
        )
    wrong = [r for r in results if not r.all_correct]
    if wrong:
        lines += [
            "",
            "| case | wrong fields | predicted | gold | failure |",
            "|---|---|---|---|---|",
        ]
        for r in wrong:
            for key in r.wrong_fields:
                lines.append(
                    f"| {r.case_id} | {key} | {r.predicted[key]!r} | {r.gold[key]!r} "
                    f"| {r.failure or '-'} |"
                )
    return "\n".join(lines) + "\n"
