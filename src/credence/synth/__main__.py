"""Write the synthetic cases to disk.

    uv run python -m credence.synth [--out eval/cases] [--only ID ...]

Each case becomes a directory with document.pdf, gold.json and meta.json.
"""

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from credence.synth.cases import CASES, CaseSpec
from credence.synth.render import render
from credence.synth.scan import scan


def build(spec: CaseSpec) -> bytes:
    pdf = render(spec)
    if spec.scanned:
        pdf = scan(pdf, skew_degrees=spec.skew_degrees, seed=spec.seed)
    return pdf


def meta(spec: CaseSpec) -> dict[str, object]:
    return {
        "id": spec.id,
        "source": "generated",
        "generator": "credence.synth",
        "layout": spec.layout.value,
        "language": spec.language.value,
        "font": spec.font,
        "date_style": spec.date_style.value,
        "expiry_date_style": spec.expiry_date_style.value if spec.expiry_date_style else None,
        "scanned": spec.scanned,
        "pages": spec.page_count,
        "is_certificate": spec.is_certificate,
        "hard": spec.hard,
    }


def write_case(spec: CaseSpec, out: Path) -> Path:
    case_dir = out / spec.id
    case_dir.mkdir(parents=True, exist_ok=True)
    (case_dir / "document.pdf").write_bytes(build(spec))
    (case_dir / "gold.json").write_text(json.dumps(spec.fields.to_gold(), indent=2) + "\n")
    (case_dir / "meta.json").write_text(json.dumps(meta(spec), indent=2, ensure_ascii=False) + "\n")
    return case_dir


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="credence.synth", description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("eval/cases"))
    parser.add_argument("--only", nargs="*", default=None, metavar="ID")
    args = parser.parse_args(argv)
    wanted = set(args.only) if args.only else None
    unknown = (wanted or set()) - {c.id for c in CASES}
    if unknown:
        parser.error(f"unknown case id(s): {', '.join(sorted(unknown))}")
    for spec in CASES:
        if wanted is None or spec.id in wanted:
            case_dir = write_case(spec, args.out)
            size = (case_dir / "document.pdf").stat().st_size
            print(f"{spec.id:40s} {spec.page_count} page(s) {size:>8,d} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
