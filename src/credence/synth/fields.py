"""The seven fields the evaluation compares, and their JSON form."""

from dataclasses import dataclass, fields
from datetime import date

GOLD_KEYS: tuple[str, ...] = (
    "issuer",
    "holder",
    "certificate_number",
    "issue_date",
    "expiry_date",
    "scope",
    "signatory",
)


@dataclass(frozen=True)
class CertificateFields:
    """What a certificate says, with None for anything it does not say.

    `notes`, the model's free-text field, is deliberately absent: it is never
    compared, so it has no gold value.
    """

    issuer: str | None = None
    holder: str | None = None
    certificate_number: str | None = None
    issue_date: date | None = None
    expiry_date: date | None = None
    scope: str | None = None
    signatory: str | None = None

    def to_gold(self) -> dict[str, str | None]:
        """JSON-ready mapping with dates as ISO 8601 strings."""
        out: dict[str, str | None] = {}
        for f in fields(self):
            value = getattr(self, f.name)
            out[f.name] = value.isoformat() if isinstance(value, date) else value
        return out


assert tuple(f.name for f in fields(CertificateFields)) == GOLD_KEYS
