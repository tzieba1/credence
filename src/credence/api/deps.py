"""Request-scoped dependencies: a database session, the extractor, the API key check."""

import secrets
from collections.abc import Callable, Iterator
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from credence.config import Settings
from credence.extraction import Extractor
from credence.storage import DocumentStore

MakeExtractor = Callable[[str | None, str | None], Extractor]
"""(model, prompt_version) -> Extractor. Replaced in tests by one on a fake transport."""


def get_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def get_session(request: Request) -> Iterator[Session]:
    with request.app.state.sessions() as session:
        yield session


def get_store(request: Request) -> DocumentStore:
    store: DocumentStore = request.app.state.store
    return store


def get_make_extractor(request: Request) -> MakeExtractor:
    make: MakeExtractor = request.app.state.make_extractor
    return make


def require_api_key(
    settings: Annotated[Settings, Depends(get_settings)],
    x_api_key: Annotated[str | None, Header()] = None,
) -> None:
    if settings.api_key is None:
        return
    expected = settings.api_key.get_secret_value()
    if x_api_key is None or not secrets.compare_digest(x_api_key, expected):
        raise HTTPException(status_code=401, detail="missing or wrong X-API-Key")


SettingsDep = Annotated[Settings, Depends(get_settings)]
SessionDep = Annotated[Session, Depends(get_session)]
StoreDep = Annotated[DocumentStore, Depends(get_store)]
MakeExtractorDep = Annotated[MakeExtractor, Depends(get_make_extractor)]
