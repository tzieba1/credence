"""Turn a text-based PDF into something that looks like it came off a scanner.

Rasterise each page, tilt it, add grain and a touch of blur, and write the
pages back as an image-only PDF. The result has no text layer.
"""

import random
import time
from io import BytesIO

from PIL import Image, ImageFilter

from credence.pdfio import open_pdf

_EPOCH = time.gmtime(0)


def rasterise(pdf: bytes, dpi: int) -> list[Image.Image]:
    """Each page as a greyscale PIL image."""
    with open_pdf(pdf) as doc:
        images: list[Image.Image] = []
        for page in doc:
            bitmap = page.render(scale=dpi / 72)
            pil = bitmap.to_pil()
            assert isinstance(pil, Image.Image)
            images.append(pil.convert("L"))
            bitmap.close()
            page.close()
        return images


def scan(pdf: bytes, *, skew_degrees: float, seed: int, dpi: int = 150) -> bytes:
    """Deterministic for a given (pdf, skew_degrees, seed, dpi)."""
    rng = random.Random(seed)
    pages: list[Image.Image] = []
    for img in rasterise(pdf, dpi):
        tilted = img.rotate(skew_degrees, resample=Image.Resampling.BICUBIC, fillcolor=255)
        grain = Image.frombytes("L", tilted.size, rng.randbytes(tilted.width * tilted.height))
        noisy = Image.blend(tilted, grain, 0.06)
        pages.append(noisy.filter(ImageFilter.GaussianBlur(0.5)))
    out = BytesIO()
    pages[0].save(
        out,
        format="PDF",
        save_all=True,
        append_images=pages[1:],
        resolution=dpi,
        creationDate=_EPOCH,
        modDate=_EPOCH,
    )
    return out.getvalue()
