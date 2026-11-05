"""The few things we need from pypdfium2, behind typed functions.

pypdfium2 has no type information, so this is the one module allowed to
import it; everything else sees plain Python types.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import pypdfium2 as pdfium


class NotAPdf(ValueError):
    """pdfium could not open the bytes as a PDF."""


@contextmanager
def open_pdf(pdf: bytes) -> Iterator[Any]:
    try:
        doc = pdfium.PdfDocument(pdf)
    except pdfium.PdfiumError as exc:
        raise NotAPdf(str(exc)) from exc
    try:
        yield doc
    finally:
        doc.close()


def page_count(pdf: bytes) -> int:
    with open_pdf(pdf) as doc:
        return len(doc)


def extract_text(pdf: bytes) -> str:
    """All text in the PDF's text layer, pages joined by form feeds. Empty for images."""
    with open_pdf(pdf) as doc:
        parts: list[str] = []
        for page in doc:
            textpage = page.get_textpage()
            parts.append(str(textpage.get_text_range()))
            textpage.close()
            page.close()
        return "\f".join(parts)
