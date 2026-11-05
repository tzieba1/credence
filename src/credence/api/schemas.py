"""What the API sends and accepts. The database rows stay inside the service."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from credence.schema import Certificate


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sha256: str
    filename: str
    bytes_size: int
    page_count: int
    created_at: datetime


class ExtractionRequest(BaseModel):
    model: str | None = Field(default=None, description="Defaults to the configured model.")
    prompt_version: str | None = Field(
        default=None, description="Defaults to the configured prompt version."
    )


class UsageOut(BaseModel):
    input_tokens: int
    output_tokens: int
    cache_read_input_tokens: int
    cache_creation_input_tokens: int


class ExtractionOut(BaseModel):
    id: int
    document_id: int
    model: str
    prompt_version: str
    implementation: str
    record: Certificate | None
    """The validated record, or null when `failure` says why there is none."""
    failure: str | None
    stop_reason: str | None
    usage: UsageOut
    cost_usd: Decimal
    latency_ms: int
    request_id: str | None
    created_at: datetime


class ExtractionList(BaseModel):
    items: list[ExtractionOut]
    total: int
    limit: int
    offset: int


class Health(BaseModel):
    status: str
    database: str
    model_api_key: str
    """Whether ANTHROPIC_API_KEY is set, not whether it works; that costs a call."""
    model: str
    prompt_version: str
