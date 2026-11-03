"""Settings, read from the environment with a CREDENCE_ prefix, or from a .env file."""

from typing import Literal

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
