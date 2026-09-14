"""FastAPI composition root. Importing this module does not connect to PostgreSQL."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Protocol

from fastapi import FastAPI

from api.middleware import RequestIdMiddleware
from api.routes import health_router
from infrastructure.database import create_database_resources, dispose_engine
from infrastructure.logging import (
    configure_logging,
    log_bootstrap,
    log_lifecycle,
    log_setup_failure,
)
from infrastructure.settings import Settings, load_runtime_settings


class DisposableEngine(Protocol):
    async def dispose(self) -> None: ...


class DatabaseResourcesLike(Protocol):
    engine: DisposableEngine


DatabaseFactory = Callable[[Settings], DatabaseResourcesLike]


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    factory: DatabaseFactory = app.state.database_factory
    try:
        resources = factory(settings)
    except Exception:
        log_setup_failure("database_factory_failed")
        raise
    app.state.database = resources
    log_lifecycle("app_started")
    try:
        yield
        log_lifecycle("app_stopping")
    finally:
        await dispose_engine(resources.engine)
        log_lifecycle("app_stopped")


def create_app(
    settings: Settings | None = None,
    database_factory: DatabaseFactory | None = None,
) -> FastAPI:
    """Build the API. Logging is configured before application lifespan events."""
    resolved = settings if settings is not None else load_runtime_settings()
    configure_logging(resolved)
    log_bootstrap(resolved)
    app = FastAPI(
        title="Palimpsest",
        lifespan=_lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.settings = resolved
    app.state.database_factory = database_factory or create_database_resources
    app.add_middleware(RequestIdMiddleware)
    app.include_router(health_router)
    return app
