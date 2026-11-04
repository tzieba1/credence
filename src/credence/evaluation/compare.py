"""Score one extraction against one gold record."""

import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal

from credence.evaluation.cases import EvalCase
from credence.extraction import Extraction
from credence.pricing import Usage
from credence.schema import Certificate
from credence.synth.fields import GOLD_KEYS

_SPACES = re.compile(r"\s+")


def normalise(value: str | None) -> str | None:
    """What two values must agree on to count as the same.

    Unicode is composed, whitespace is collapsed, case is ignored. Dates are
    already ISO strings on both sides, so they compare exactly.
    """
    if value is None:
        return None
    return _SPACES.sub(" ", unicodedata.normalize("NFC", value)).strip().casefold()


def predicted_fields(record: Certificate | None) -> dict[str, str | None]:
    """The seven compared fields of a record as JSON values; all None if there is no record."""
    if record is None:
        return dict.fromkeys(GOLD_KEYS)
    dumped = record.model_dump(mode="json")
    return {key: dumped[key] for key in GOLD_KEYS}


@dataclass(frozen=True)
class CaseResult:
    case_id: str
    gold: dict[str, str | None]
    predicted: dict[str, str | None]
    correct: dict[str, bool]
    notes: str | None
    failure: str | None
    stop_reason: str | None
    usage: Usage
    cost_usd: Decimal
    latency_ms: int
    request_id: str | None

    @property
    def all_correct(self) -> bool:
        return all(self.correct.values())

    @property
    def wrong_fields(self) -> list[str]:
        return [key for key, ok in self.correct.items() if not ok]


def score(case: EvalCase, extraction: Extraction, *, latency_ms: int | None = None) -> CaseResult:
    predicted = predicted_fields(extraction.record)
    correct = {key: normalise(predicted[key]) == normalise(case.gold[key]) for key in GOLD_KEYS}
    return CaseResult(
        case_id=case.id,
        gold=case.gold,
        predicted=predicted,
        correct=correct,
        notes=extraction.record.notes if extraction.record else None,
        failure=extraction.failure,
        stop_reason=extraction.stop_reason,
        usage=extraction.usage,
        cost_usd=extraction.cost_usd,
        latency_ms=extraction.latency_ms if latency_ms is None else latency_ms,
        request_id=extraction.request_id,
    )
