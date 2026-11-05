"""Settings, read from the environment with a CREDENCE_ prefix, or from a .env file."""

from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

Effort = Literal["low", "medium", "high", "xhigh", "max"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CREDENCE_", env_file=".env", extra="ignore")

    extraction_model: str = "claude-opus-5-5"
    prompt_version: str = "v1"
    effort: Effort = "medium"
    max_output_tokens: int = 16000
    request_timeout_s: float = 120.0
    max_document_bytes: int = 20 * 1024 * 1024
    max_document_pages: int = 20

    database_url: str = "postgresql+psycopg://credence:credence@localhost:5432/credence"
    """The one in compose.yaml. Alembic reads it too."""
    storage_dir: Path = Path("data/documents")
    """Where uploaded PDFs live, named by their sha256. The database holds the path only."""
    api_key: SecretStr | None = None
    """When set, every request but /health must carry it in X-API-Key. Unset means open,
    which is only acceptable on a laptop."""
