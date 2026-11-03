"""Date wordings a certificate might use. The gold is always ISO 8601."""

from datetime import date
from enum import StrEnum


class Language(StrEnum):
    EN = "en"
    ES = "es"
    FR = "fr"


class DateStyle(StrEnum):
    ISO = "iso"  # 2024-03-14
    LONG = "long"  # 14 March 2024 / 14 de marzo de 2024 / 14 mars 2024
    LONG_US = "long_us"  # March 14, 2024
    NUMERIC_DMY = "dmy"  # 14/03/2024
    NUMERIC_MDY = "mdy"  # 03/14/2024
    DOTTED = "dotted"  # 14.03.2024


_MONTHS: dict[Language, tuple[str, ...]] = {
    Language.EN: (
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December",
    ),
    Language.ES: (
        "enero", "febrero", "marzo", "abril", "mayo", "junio",
        "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
    ),
    Language.FR: (
        "janvier", "février", "mars", "avril", "mai", "juin",
        "juillet", "août", "septembre", "octobre", "novembre", "décembre",
    ),
}  # fmt: skip


def format_date(d: date, style: DateStyle, language: Language) -> str:
    """Render `d` the way a document in `language` would print it in `style`."""
    month = _MONTHS[language][d.month - 1]
    match style:
        case DateStyle.ISO:
            return d.isoformat()
        case DateStyle.LONG:
            if language is Language.ES:
                return f"{d.day} de {month} de {d.year}"
            return f"{d.day} {month} {d.year}"
        case DateStyle.LONG_US:
            return f"{month} {d.day}, {d.year}"
        case DateStyle.NUMERIC_DMY:
            return f"{d.day:02d}/{d.month:02d}/{d.year}"
        case DateStyle.NUMERIC_MDY:
            return f"{d.month:02d}/{d.day:02d}/{d.year}"
        case DateStyle.DOTTED:
            return f"{d.day:02d}.{d.month:02d}.{d.year}"
