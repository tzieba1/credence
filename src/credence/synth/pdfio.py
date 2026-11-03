"""The few things we need from pypdfium2, behind typed functions.

pypdfium2 has no type information, so this is the one module allowed to
import it; everything else sees plain Python types.
"""

import pypdfium2 as pdfium
from PIL import Image


def page_count(pdf: bytes) -> int:
    doc = pdfium.PdfDocument(pdf)
    try:
        return len(doc)
    finally:
        doc.close()


def extract_text(pdf: bytes) -> str:
    """All text in the PDF's text layer, pages joined by form feeds. Empty for images."""
    doc = pdfium.PdfDocument(pdf)
    try:
        parts: list[str] = []
        for page in doc:
            textpage = page.get_textpage()
            parts.append(str(textpage.get_text_range()))
            textpage.close()
            page.close()
        return "\f".join(parts)
    finally:
        doc.close()


def rasterise(pdf: bytes, dpi: int) -> list[Image.Image]:
    """Each page as a greyscale PIL image."""
    doc = pdfium.PdfDocument(pdf)
    try:
        images: list[Image.Image] = []
        for page in doc:
            bitmap = page.render(scale=dpi / 72)
            pil = bitmap.to_pil()
            assert isinstance(pil, Image.Image)
            images.append(pil.convert("L"))
            bitmap.close()
            page.close()
        return images
    finally:
        doc.close()
