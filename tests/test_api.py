"""The HTTP API against a real Postgres and a fake model API.

The extractor the app builds is the real one; only its HTTP transport is a
fake that answers with canned Messages API bodies. So these tests cover the
request the service sends, the row it stores and the JSON it returns.
"""

import json
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from credence.api import create_app
from credence.config import Settings
from credence.db import Document, Extraction
from credence.extraction import Extractor
from tests.conftest import ROOT, FakeApi, message_body, record_text

CERTIFICATE = (ROOT / "eval/cases/g01-classic-en-iso/document.pdf").read_bytes()
THREE_PAGES = (ROOT / "eval/cases/g10-classic-en-multipage/document.pdf").read_bytes()


def settings_for(database_url: str, tmp_path: Path, **overrides: Any) -> Settings:
    return Settings(
        _env_file=None,  # type: ignore[call-arg]  # pydantic-settings' init-only switch
        database_url=database_url,
        storage_dir=tmp_path / "documents",
        **overrides,
    )


@pytest.fixture
def make_client(
    clean_tables: Engine, database_url: str, tmp_path: Path
) -> Iterator[Callable[..., tuple[TestClient, FakeApi]]]:
    clients: list[TestClient] = []

    def make(
        *bodies: dict[str, Any], status: int = 200, **overrides: Any
    ) -> tuple[TestClient, FakeApi]:
        app = create_app(settings_for(database_url, tmp_path, **overrides))
        api = FakeApi(responses=[])
        from httpx2 import Response

        api.responses = [
            Response(status, json=b, headers={"request-id": f"req_{i}"})
            for i, b in enumerate(bodies)
        ]

        def make_extractor(model: str | None, prompt_version: str | None) -> Extractor:
            return Extractor(
                api.client, model=model or "claude-opus-5-5", prompt_version=prompt_version or "v1"
            )

        app.state.make_extractor = make_extractor
        client = TestClient(app)
        client.__enter__()  # runs the lifespan: engine and session factory
        clients.append(client)
        return client, api

    yield make
    for client in clients:
        client.__exit__(None, None, None)


def upload(client: TestClient, pdf: bytes, name: str = "cert.pdf") -> Any:
    return client.post("/documents", files={"file": (name, pdf, "application/pdf")})


# --- documents ----------------------------------------------------------------


def test_upload_stores_the_document_and_its_metadata(
    make_client: Callable[..., tuple[TestClient, FakeApi]], tmp_path: Path, clean_tables: Engine
) -> None:
    client, _ = make_client()
    response = upload(client, THREE_PAGES, "multi.pdf")
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["filename"] == "multi.pdf"
    assert body["page_count"] == 3
    assert body["bytes_size"] == len(THREE_PAGES)
    assert len(body["sha256"]) == 64

    stored = list((tmp_path / "documents").rglob("*.pdf"))
    assert [p.read_bytes() for p in stored] == [THREE_PAGES]
    with Session(clean_tables) as session:
        row = session.scalar(select(Document))
        assert row is not None and row.stored_path == str(stored[0])

    assert client.get(f"/documents/{body['id']}").json() == body


def test_same_bytes_twice_is_one_document(
    make_client: Callable[..., tuple[TestClient, FakeApi]], clean_tables: Engine
) -> None:
    client, _ = make_client()
    first = upload(client, CERTIFICATE, "a.pdf")
    second = upload(client, CERTIFICATE, "b.pdf")
    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]
    assert second.json()["filename"] == "a.pdf"
    with Session(clean_tables) as session:
        assert len(session.scalars(select(Document)).all()) == 1


@pytest.mark.parametrize(
    ("pdf", "status", "detail"),
    [
        (b"hello, not a pdf", 415, "only PDF documents are accepted"),
        (b"%PDF-1.7 but nothing follows", 422, "could not be read as a PDF"),
    ],
)
def test_upload_rejects_what_is_not_a_pdf(
    make_client: Callable[..., tuple[TestClient, FakeApi]], pdf: bytes, status: int, detail: str
) -> None:
    client, _ = make_client()
    response = upload(client, pdf)
    assert response.status_code == status
    assert detail in response.json()["detail"]


def test_upload_enforces_size_and_page_limits(
    make_client: Callable[..., tuple[TestClient, FakeApi]],
) -> None:
    client, _ = make_client(max_document_bytes=1000)
    assert upload(client, CERTIFICATE).status_code == 413
    client, _ = make_client(max_document_pages=2)
    response = upload(client, THREE_PAGES)
    assert response.status_code == 422
    assert "3 pages" in response.json()["detail"]


def test_missing_document_is_404(make_client: Callable[..., tuple[TestClient, FakeApi]]) -> None:
    client, _ = make_client()
    assert client.get("/documents/42").status_code == 404
    assert client.post("/documents/42/extractions", json={}).status_code == 404
    assert client.get("/extractions/42").status_code == 404


# --- extractions --------------------------------------------------------------


def test_extraction_is_run_stored_and_returned(
    make_client: Callable[..., tuple[TestClient, FakeApi]], clean_tables: Engine
) -> None:
    client, api = make_client(
        message_body(text=record_text(), input_tokens=12_000, output_tokens=150)
    )
    document_id = upload(client, CERTIFICATE).json()["id"]

    response = client.post(f"/documents/{document_id}/extractions", json={})
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["document_id"] == document_id
    assert body["model"] == "claude-opus-5-5"
    assert body["prompt_version"] == "v1"
    assert body["implementation"] == "direct"
    assert body["failure"] is None
    assert body["stop_reason"] == "end_turn"
    assert body["record"]["issuer"] == "Northgate Certification Services Ltd"
    assert body["record"]["issue_date"] == "2024-03-14"
    assert body["record"]["notes"] is None
    assert body["usage"] == {
        "input_tokens": 12_000,
        "output_tokens": 150,
        "cache_read_input_tokens": 0,
        "cache_creation_input_tokens": 0,
    }
    assert body["cost_usd"] == "0.051000"  # a string with the column's six decimals, never a float
    assert body["request_id"] == "req_0"

    # The model was sent this document, as a document block, with the v1 prompt.
    sent = api.requests[0]
    assert sent["model"] == "claude-opus-5-5"
    assert sent["messages"][0]["content"][0]["type"] == "document"
    assert "certificate" in sent["system"].lower()

    # Read back: the same JSON, from the row.
    assert client.get(f"/extractions/{body['id']}").json() == body
    with Session(clean_tables) as session:
        row = session.scalar(select(Extraction))
        assert row is not None
        assert row.fields is not None and "notes" not in row.fields
        assert row.fields["expiry_date"] == "2027-03-13"
        assert str(row.cost_usd) == "0.051000"


def test_a_refusal_is_a_stored_failure_not_an_error(
    make_client: Callable[..., tuple[TestClient, FakeApi]],
) -> None:
    client, _ = make_client(
        message_body(
            text=None, stop_reason="refusal", stop_details={"type": "refusal", "category": "safety"}
        )
    )
    document_id = upload(client, CERTIFICATE).json()["id"]
    response = client.post(f"/documents/{document_id}/extractions", json={})
    assert response.status_code == 201
    body = response.json()
    assert body["record"] is None
    assert body["failure"] == "refusal:safety"
    assert body["stop_reason"] == "refusal"
    assert client.get("/extractions").json()["total"] == 1


def test_unreachable_model_api_is_503_and_stores_nothing(
    make_client: Callable[..., tuple[TestClient, FakeApi]],
) -> None:
    client, _ = make_client({"type": "error", "error": {"type": "api_error"}}, status=500)
    document_id = upload(client, CERTIFICATE).json()["id"]
    response = client.post(f"/documents/{document_id}/extractions", json={})
    assert response.status_code == 503
    assert response.json()["detail"] == "the model API answered 500"
    assert client.get("/extractions").json()["total"] == 0


def test_unknown_model_or_prompt_is_rejected_before_any_call(
    make_client: Callable[..., tuple[TestClient, FakeApi]],
) -> None:
    client, api = make_client()
    document_id = upload(client, CERTIFICATE).json()["id"]
    url = f"/documents/{document_id}/extractions"
    assert client.post(url, json={"model": "claude-3-haiku"}).status_code == 422
    assert client.post(url, json={"prompt_version": "v9"}).status_code == 422
    assert api.requests == []


def test_list_filters_and_orders_newest_first(
    make_client: Callable[..., tuple[TestClient, FakeApi]],
) -> None:
    client, _ = make_client(
        message_body(text=record_text(), model="claude-opus-5-5"),
        message_body(text=record_text(holder="Someone Else"), model="claude-haiku-5-5"),
        message_body(text=record_text(), model="claude-opus-5-5"),
    )
    doc_a = upload(client, CERTIFICATE).json()["id"]
    doc_b = upload(client, THREE_PAGES).json()["id"]
    ids = [
        client.post(f"/documents/{doc_a}/extractions", json={}).json()["id"],
        client.post(f"/documents/{doc_a}/extractions", json={"model": "claude-haiku-5-5"}).json()[
            "id"
        ],
        client.post(f"/documents/{doc_b}/extractions", json={}).json()["id"],
    ]

    everything = client.get("/extractions").json()
    assert everything["total"] == 3
    assert [e["id"] for e in everything["items"]] == ids[::-1]

    by_document = client.get("/extractions", params={"document_id": doc_a}).json()
    assert [e["id"] for e in by_document["items"]] == ids[1::-1]

    haiku = client.get("/extractions", params={"model": "claude-haiku-5-5"}).json()
    assert haiku["total"] == 1
    assert haiku["items"][0]["record"]["holder"] == "Someone Else"

    page = client.get("/extractions", params={"limit": 1, "offset": 1}).json()
    assert page["total"] == 3 and [e["id"] for e in page["items"]] == [ids[1]]
    assert client.get("/extractions", params={"limit": 0}).status_code == 422


# --- health and the API key ---------------------------------------------------


@pytest.fixture(autouse=True)
def model_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """A key is configured, as it is wherever the service runs; one test takes it away."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")


def test_health_reports_the_database_the_key_and_the_configuration(
    make_client: Callable[..., tuple[TestClient, FakeApi]],
) -> None:
    client, _ = make_client(extraction_model="claude-haiku-5-5", prompt_version="v1")
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "database": "ok",
        "model_api_key": "set",
        "model": "claude-haiku-5-5",
        "prompt_version": "v1",
    }


def test_health_is_503_when_postgres_is_unreachable(tmp_path: Path) -> None:
    app = create_app(settings_for("postgresql+psycopg://nobody:nothing@127.0.0.1:1/none", tmp_path))
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 503
    assert response.json()["database"] == "unreachable"
    assert response.json()["status"] == "degraded"


def test_missing_model_api_key_is_degraded_health_and_a_503_extraction(
    clean_tables: Engine, database_url: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    # The real extractor factory this time, so the missing key is noticed where it would be.
    with TestClient(create_app(settings_for(database_url, tmp_path))) as client:
        health = client.get("/health")
        assert health.status_code == 503
        assert health.json()["model_api_key"] == "missing"
        document_id = upload(client, CERTIFICATE).json()["id"]
        response = client.post(f"/documents/{document_id}/extractions", json={})
        assert response.status_code == 503
        assert response.json()["detail"] == "ANTHROPIC_API_KEY is not set"
        assert client.get("/extractions").json()["total"] == 0


def test_api_key_guards_everything_but_health(
    make_client: Callable[..., tuple[TestClient, FakeApi]],
) -> None:
    client, _ = make_client(api_key="s3cret")
    assert client.get("/health").status_code == 200
    assert client.get("/extractions").status_code == 401
    assert client.get("/extractions", headers={"X-API-Key": "wrong"}).status_code == 401
    assert client.get("/extractions", headers={"X-API-Key": "s3cret"}).status_code == 200
    assert upload(client, CERTIFICATE).status_code == 401


def test_the_openapi_document_lists_every_route(
    make_client: Callable[..., tuple[TestClient, FakeApi]],
) -> None:
    client, _ = make_client()
    paths = client.get("/openapi.json").json()["paths"]
    assert set(paths) == {
        "/health",
        "/documents",
        "/documents/{document_id}",
        "/documents/{document_id}/extractions",
        "/extractions",
        "/extractions/{extraction_id}",
    }
    assert json.dumps(paths)  # serialisable, so the docs page renders
