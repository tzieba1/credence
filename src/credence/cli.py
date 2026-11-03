"""credence: extract one document from the command line.

    credence extract path/to/document.pdf [--model MODEL] [--prompt VERSION] [--json]

Prints the record and what the call cost. Needs ANTHROPIC_API_KEY in the
environment; every run is a live call and spends money.
"""

import argparse
import json
import logging
import sys
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path

from credence.config import Settings
from credence.extraction import Extraction, Extractor, ModelUnavailable
from credence.schema import Certificate


def render(extraction: Extraction) -> str:
    lines: list[str] = []
    if extraction.record is None:
        lines.append(f"no record: {extraction.failure}")
    else:
        width = max(len(name) for name in Certificate.model_fields)
        for name in Certificate.model_fields:
            value = getattr(extraction.record, name)
            lines.append(f"{name:<{width}}  {'-' if value is None else value}")
    lines.append("")
    u = extraction.usage
    lines.append(
        f"model {extraction.model}  prompt {extraction.prompt_version}  "
        f"stop {extraction.stop_reason}  tokens {u.input_tokens} in / {u.output_tokens} out  "
        f"cost ${extraction.cost_usd:.4f}  latency {extraction.latency_ms} ms"
    )
    return "\n".join(lines)


def to_json(extraction: Extraction) -> str:
    data = asdict(extraction)
    data["record"] = extraction.record.model_dump(mode="json") if extraction.record else None
    data["cost_usd"] = str(extraction.cost_usd)
    return json.dumps(data, indent=2, ensure_ascii=False)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="credence", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    ex = sub.add_parser("extract", help="extract one PDF and print the record")
    ex.add_argument("pdf", type=Path)
    ex.add_argument("--model", help="override the configured model")
    ex.add_argument("--prompt", help="override the configured prompt version")
    ex.add_argument("--json", action="store_true", help="print the full extraction as JSON")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    settings = Settings()
    pdf = args.pdf.read_bytes()
    if len(pdf) > settings.max_document_bytes:
        parser.error(f"{args.pdf} is larger than {settings.max_document_bytes} bytes")
    extractor = Extractor.from_settings(settings, model=args.model, prompt_version=args.prompt)
    try:
        extraction = extractor.extract(pdf)
    except ModelUnavailable as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(to_json(extraction) if args.json else render(extraction))
    return 0 if extraction.ok else 1


if __name__ == "__main__":
    sys.exit(main())
