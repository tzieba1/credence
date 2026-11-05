"""Shared fixtures: a real SDK client wired to a fake HTTP transport."""

import json
import os
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import anthropic
import httpx2 as httpx
import pytest
import sqlalchemy
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, text
from sqlalchemy.engine import make_url


def message_body(
    *,
    text: str | None,
    stop_reason: str = "end_turn",
    model: str = "claude-opus-5-5",
    input_tokens: int = 1000,
    output_tokens: int = 100,
    cache_read: int = 0,
    cache_write: int = 0,
    stop_details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """A Messages API response body, as JSON, with an optional text block."""
    content: list[dict[str, Any]] = [{"type": "thinking", "thinking": "", "signature": "sig"}]
    if text is not None:
        content.append({"type": "text", "text": text})
    return {
        "id": "msg_test",
        "type": "message",
        "role": "assistant",
        "model": model,
        "content": content,
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "stop_details": stop_details,
        "usage": {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cache_read_input_tokens": cache_read,
            "cache_creation_input_tokens": cache_write,
        },
    }


def record_text(**overrides: Any) -> str:
    """The JSON text of a complete, valid Certificate, with any field overridden."""
    record: dict[str, Any] = {
        "issuer": "Northgate Certification Services Ltd",
        "holder": "Harwell Precision Engineering plc",
        "certificate_number": "NCS-QMS-2024-0417",
        "issue_date": "2024-03-14",
        "expiry_date": "2027-03-13",
        "scope": "Design and manufacture of machined aluminium housings for medical devices",
        "signatory": "Margaret Okonkwo",
        "notes": None,
    }
    record.update(overrides)
    return json.dumps(record)


@dataclass
class FakeApi:
    """Answers every request with `responses` in order and keeps what was sent."""

    responses: list[httpx.Response]
    requests: list[dict[str, Any]] = field(default_factory=list)

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(json.loads(request.content))
        if not self.responses:
            raise AssertionError("more requests than canned responses")
        return self.responses.pop(0)

    @property
    def client(self) -> anthropic.Anthropic:
        return anthropic.Anthropic(
            api_key="test-key",
            max_retries=0,
            http_client=anthropic.DefaultHttpxClient(transport=httpx.MockTransport(self.handler)),
        )


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("eval", "the evaluation set (pytest -m eval)")
    group.addoption(
        "--live",
        action="store_true",
        default=False,
        help="call the API, rewrite the fixtures and write a results file (costs money)",
    )
    group.addoption(
        "--model",
        action="append",
        default=None,
        metavar="MODEL",
        help="model(s) to evaluate; default: every model with recorded fixtures, "
        "or the configured model when --live",
    )
    group.addoption(
        "--prompt", default=None, metavar="VERSION", help="prompt version; default: configured"
    )


@pytest.fixture
def fake_api() -> Callable[..., FakeApi]:
    def make(*bodies: dict[str, Any], status: int = 200) -> FakeApi:
        responses = [
            httpx.Response(status, json=body, headers={"request-id": f"req_{i}"})
            for i, body in enumerate(bodies)
        ]
        return FakeApi(responses=responses)

    return make


# --- Postgres -----------------------------------------------------------------
#
# The API tests need a real Postgres: JSONB, the unique index, the migrations.
# They look for CREDENCE_TEST_DATABASE_URL and fall back to a credence_test
# database on the Compose instance. If that is not running they skip, with the
# reason in the summary; when the variable is set explicitly (CI does) they fail
# instead, so a missing database can never turn the suite green by accident.

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TEST_DATABASE_URL = "postgresql+psycopg://credence:credence@localhost:5432/credence_test"


def alembic_config(url: str) -> Config:
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "migrations"))
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


def _ensure_database(url: str) -> None:
    """Create the test database if the server is there but the database is not."""
    target = make_url(url)
    maintenance = sqlalchemy.create_engine(
        target.set(database="credence"), isolation_level="AUTOCOMMIT"
    )
    with maintenance.connect() as conn:
        exists = conn.scalar(
            text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": target.database}
        )
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{target.database}"'))
    maintenance.dispose()


@pytest.fixture(scope="session")
def database_url() -> str:
    explicit = os.environ.get("CREDENCE_TEST_DATABASE_URL")
    url = explicit or DEFAULT_TEST_DATABASE_URL
    try:
        _ensure_database(url)
    except sqlalchemy.exc.OperationalError as exc:
        if explicit:
            raise
        pytest.skip(f"no Postgres for the API tests (docker compose up -d): {exc.orig}")
    return url


@pytest.fixture(scope="session")
def migrated_engine(database_url: str) -> Iterator[Engine]:
    """A clean database at the head migration, built by downgrading and upgrading."""
    cfg = alembic_config(database_url)
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    engine = sqlalchemy.create_engine(database_url)
    yield engine
    engine.dispose()


@pytest.fixture
def clean_tables(migrated_engine: Engine) -> Engine:
    with migrated_engine.begin() as conn:
        conn.execute(text("TRUNCATE extractions, documents RESTART IDENTITY CASCADE"))
    return migrated_engine
