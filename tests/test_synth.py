"""The generator: every case renders, says what its gold says, and is reproducible."""

import json
import re
from datetime import date
from pathlib import Path

import pytest

from credence.pdfio import extract_text, page_count
from credence.synth import CASES, GOLD_KEYS, CaseSpec, CertificateFields
from credence.synth.__main__ import build, main
from credence.synth.dates import DateStyle, Language, format_date
from credence.synth.render import WORDS

BY_ID = {c.id: c for c in CASES}


def _squash(text: str) -> str:
    return re.sub(r"\s+", " ", text)


def test_gold_keys_are_the_seven_fields() -> None:
    assert CertificateFields().to_gold() == dict.fromkeys(GOLD_KEYS)


def test_gold_dates_are_iso() -> None:
    gold = CertificateFields(issue_date=date(2024, 3, 14)).to_gold()
    assert gold["issue_date"] == "2024-03-14"


@pytest.mark.parametrize(
    ("style", "language", "expected"),
    [
        (DateStyle.ISO, Language.EN, "2024-03-14"),
        (DateStyle.LONG, Language.EN, "14 March 2024"),
        (DateStyle.LONG, Language.ES, "14 de marzo de 2024"),
        (DateStyle.LONG, Language.FR, "14 mars 2024"),
        (DateStyle.LONG_US, Language.EN, "March 14, 2024"),
        (DateStyle.NUMERIC_DMY, Language.EN, "14/03/2024"),
        (DateStyle.NUMERIC_MDY, Language.EN, "03/14/2024"),
        (DateStyle.DOTTED, Language.EN, "14.03.2024"),
    ],
)
def test_format_date(style: DateStyle, language: Language, expected: str) -> None:
    assert format_date(date(2024, 3, 14), style, language) == expected


def test_case_set_shape() -> None:
    assert 15 <= len(CASES) <= 20
    assert sum(not c.is_certificate for c in CASES) == 2
    assert sum(c.scanned for c in CASES) >= 4
    assert {c.language for c in CASES} == set(Language)
    assert any(c.fields.expiry_date is None and c.is_certificate for c in CASES)
    assert any(c.fields.signatory is None and c.is_certificate for c in CASES)
    assert any(c.page_count > 1 for c in CASES)


@pytest.mark.parametrize("spec", CASES, ids=[c.id for c in CASES])
def test_case_builds_and_says_what_gold_says(spec: CaseSpec) -> None:
    pdf = build(spec)
    assert pdf.startswith(b"%PDF-")
    assert page_count(pdf) == spec.page_count
    text = _squash(extract_text(pdf))
    if spec.scanned:
        # Image-only: the model gets pixels, not a text layer.
        assert text.strip() == ""
        return
    f = spec.fields
    words = WORDS[spec.language]
    for key in ("issuer", "holder", "certificate_number", "scope", "signatory"):
        value = getattr(f, key)
        if value is not None:
            assert value in text, f"{key} not printed"
    if f.issue_date is not None:
        assert format_date(f.issue_date, spec.date_style, spec.language) in text
    if f.expiry_date is not None:
        style = spec.expiry_date_style or spec.date_style
        assert format_date(f.expiry_date, style, spec.language) in text
    elif spec.is_certificate:
        assert words.no_expiry in text
    if spec.is_certificate and f.signatory is None:
        assert words.unsigned in text


@pytest.mark.parametrize("case_id", ["g04-table-en-mixed-dates", "g12-scan-table-es"])
def test_build_is_deterministic(case_id: str) -> None:
    spec = BY_ID[case_id]
    assert build(spec) == build(spec)


def test_cli_writes_one_case(tmp_path: Path) -> None:
    spec = BY_ID["g01-classic-en-iso"]
    assert main(["--out", str(tmp_path), "--only", spec.id]) == 0
    case_dir = tmp_path / spec.id
    assert sorted(p.name for p in case_dir.iterdir()) == ["document.pdf", "gold.json", "meta.json"]
    assert json.loads((case_dir / "gold.json").read_text()) == spec.fields.to_gold()
    meta = json.loads((case_dir / "meta.json").read_text())
    assert meta["id"] == spec.id
    assert meta["pages"] == spec.page_count
    assert meta["source"] == "generated"


def test_cli_rejects_unknown_case_id(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["--out", str(tmp_path), "--only", "no-such-case"])
    assert excinfo.value.code == 2
