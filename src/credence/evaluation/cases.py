"""The labelled set on disk: eval/cases/<id>/{document.pdf,gold.json,meta.json}."""

import hashlib
import json
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import Any

from credence.synth.fields import GOLD_KEYS

DEFAULT_EVAL_DIR = Path("eval")


@dataclass(frozen=True)
class EvalCase:
    id: str
    directory: Path
    gold: dict[str, str | None]
    meta: dict[str, Any]

    @cached_property
    def pdf(self) -> bytes:
        return (self.directory / "document.pdf").read_bytes()

    @cached_property
    def sha256(self) -> str:
        return hashlib.sha256(self.pdf).hexdigest()


def load_cases(eval_dir: Path = DEFAULT_EVAL_DIR) -> list[EvalCase]:
    cases: list[EvalCase] = []
    for directory in sorted(p for p in (eval_dir / "cases").iterdir() if p.is_dir()):
        gold = json.loads((directory / "gold.json").read_text())
        if set(gold) != set(GOLD_KEYS):
            raise ValueError(f"{directory / 'gold.json'} does not have exactly the gold keys")
        meta = json.loads((directory / "meta.json").read_text())
        cases.append(EvalCase(id=directory.name, directory=directory, gold=gold, meta=meta))
    if not cases:
        raise ValueError(f"no cases under {eval_dir / 'cases'}")
    return cases
