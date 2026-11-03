"""The record the model is asked to produce. Its JSON schema is what the API enforces."""

from datetime import date

from pydantic import BaseModel, Field

# No field has a default. Pydantic then marks every key as required in the JSON
# schema, so the model must state each field explicitly, with null for absent.


class Certificate(BaseModel):
    issuer: str | None = Field(
        description="The organisation that issued the certificate, exactly as printed."
    )
    holder: str | None = Field(
        description="The organisation or person the certificate was issued to, exactly as printed."
    )
    certificate_number: str | None = Field(
        description="The certificate's own identifier, exactly as printed."
    )
    issue_date: date | None = Field(description="The date the certificate was issued, ISO 8601.")
    expiry_date: date | None = Field(
        description=(
            "The date the certificate stops being valid, ISO 8601. Null if it does not expire."
        )
    )
    scope: str | None = Field(
        description=(
            "What the certificate covers: the activity, product or site, exactly as printed."
        )
    )
    signatory: str | None = Field(
        description="The name of the person who signed the certificate, without title or honorific."
    )
    notes: str | None = Field(
        description=(
            "Anything that could not be placed in a field, and why a field was left null "
            "when that is not obvious. Null if there is nothing to say."
        )
    )
