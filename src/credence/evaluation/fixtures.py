"""Recorded API responses, one file per case, under eval/fixtures/<prompt>/<model>/.

A fixture is the whole response the API gave for a document, with the
latency and request id of that call. Recorded mode feeds the response back
through the real SDK client by way of a fake HTTP transport, so the code
under test is the same code that runs live; only the network is replaced.
"""

import base64
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import anthropic
import httpx2 as httpx

FIXTURE_FORMAT = 1


@dataclass(frozen=True)
class Fixture:
    case_id: str
    document_sha256: str
    model: str
    prompt_version: str
    recorded_at: str
    latency_ms: int
    request_id: str | None
    response: dict[str, Any]

    def to_json(self) -> dict[str, Any]:
        return {"format": FIXTURE_FORMAT, **self.__dict__}

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "Fixture":
        if data.get("format") != FIXTURE_FORMAT:
            raise ValueError(f"fixture format {data.get('format')!r}, expected {FIXTURE_FORMAT}")
        return cls(**{k: v for k, v in data.items() if k != "format"})


def fixture_dir(eval_dir: Path, prompt_version: str, model: str) -> Path:
    return eval_dir / "fixtures" / prompt_version / model


def write_fixture(directory: Path, fixture: Fixture) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{fixture.case_id}.json"
    path.write_text(json.dumps(fixture.to_json(), indent=2, ensure_ascii=False) + "\n")
    return path


def read_fixtures(directory: Path) -> dict[str, Fixture]:
    """Fixtures by case id. Empty if the directory does not exist."""
    if not directory.is_dir():
        return {}
    return {
        p.stem: Fixture.from_json(json.loads(p.read_text()))
        for p in sorted(directory.glob("*.json"))
    }


class MissingFixture(Exception):
    pass


def replay_client(fixtures: dict[str, Fixture]) -> anthropic.Anthropic:
    """A real SDK client whose transport answers each request from the fixture for its document."""
    by_hash = {f.document_sha256: f for f in fixtures.values()}

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        document = next(
            block["source"]["data"]
            for block in body["messages"][0]["content"]
            if block["type"] == "document"
        )
        digest = hashlib.sha256(base64.standard_b64decode(document)).hexdigest()
        fixture = by_hash.get(digest)
        if fixture is None:
            raise MissingFixture(f"no fixture recorded for document {digest[:12]}")
        headers = {"request-id": fixture.request_id} if fixture.request_id else {}
        return httpx.Response(200, json=fixture.response, headers=headers)

    return anthropic.Anthropic(
        api_key="recorded",
        max_retries=0,
        http_client=anthropic.DefaultHttpxClient(transport=httpx.MockTransport(handler)),
    )
