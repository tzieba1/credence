"""The committed evaluation set under eval/cases matches the specifications it came from."""

import json
from pathlib import Path

import pytest

from credence.synth import CASES, CaseSpec
from credence.synth.__main__ import meta
from credence.synth.pdfio import page_count

ROOT = Path(__file__).resolve().parents[1]
CASES_DIR = ROOT / "eval" / "cases"
EVAL_README = ROOT / "eval" / "README.md"


def test_every_committed_case_has_a_spec_and_vice_versa() -> None:
    on_disk = {p.name for p in CASES_DIR.iterdir() if p.is_dir()}
    assert on_disk == {c.id for c in CASES}


@pytest.mark.parametrize("spec", CASES, ids=[c.id for c in CASES])
def test_committed_files_match_spec(spec: CaseSpec) -> None:
    case_dir = CASES_DIR / spec.id
    assert json.loads((case_dir / "gold.json").read_text()) == spec.fields.to_gold()
    assert json.loads((case_dir / "meta.json").read_text()) == meta(spec)
    assert page_count((case_dir / "document.pdf").read_bytes()) == spec.page_count


def test_eval_readme_lists_every_case() -> None:
    readme = EVAL_README.read_text()
    missing = [c.id for c in CASES if f"`{c.id}`" not in readme]
    assert not missing, f"cases not listed in eval/README.md: {missing}"
