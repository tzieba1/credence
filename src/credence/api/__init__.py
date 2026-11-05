"""The HTTP service: FastAPI in front of the extraction service and Postgres.

    uv run credence serve                      # reads settings from the environment
    uv run uvicorn --factory credence.api:create_app --reload

`create_app` takes the settings explicitly so a test can point it at another
database and directory, and swaps the extractor factory for one that never
reaches the network.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from sqlalchemy import text

from credence.api.routes import router
from credence.api.schemas import Health
from credence.config import Settings
from credence.db import make_engine, session_factory
from credence.extraction import Extractor, api_key_present
from credence.storage import DocumentStore


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.engine = make_engine(settings.database_url)
        app.state.sessions = session_factory(app.state.engine)
        yield
        app.state.engine.dispose()

    app = FastAPI(
        title="credence",
        summary="Typed field extraction from PDF certificates, with the cost of every call.",
        version="0.0.1",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.store = DocumentStore(settings.storage_dir)

    def make_extractor(model: str | None, prompt_version: str | None) -> Extractor:
        return Extractor.from_settings(settings, model=model, prompt_version=prompt_version)

    app.state.make_extractor = make_extractor

    @app.get("/health", response_model=Health, responses={503: {"model": Health}})
    def health(request: Request, response: Response) -> Health:
        """Open, so a load balancer can call it. Says whether Postgres answers and a key is set."""
        try:
            with request.app.state.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            database = "ok"
        except Exception:  # any driver error means the same thing here
            database = "unreachable"
        key = "set" if api_key_present() else "missing"
        healthy = database == "ok" and key == "set"
        if not healthy:
            response.status_code = 503
        return Health(
            status="ok" if healthy else "degraded",
            database=database,
            model_api_key=key,
            model=settings.extraction_model,
            prompt_version=settings.prompt_version,
        )

    app.include_router(router)
    return app


__all__ = ["create_app"]
