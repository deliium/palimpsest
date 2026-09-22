"""FastAPI composition root. Importing this module does not connect to PostgreSQL."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Protocol

from fastapi import FastAPI

from api.errors import ApiError, api_error_handler
from api.middleware import RequestIdMiddleware
from api.routes import (
    health_router,
    inspection_router,
    replay_router,
    simulations_router,
    streams_router,
)
from api.simulation_manager import SimulationManager
from infrastructure.database import create_database_resources, dispose_engine
from infrastructure.logging import (
    configure_logging,
    log_bootstrap,
    log_lifecycle,
    log_setup_failure,
)
from infrastructure.settings import Settings, load_runtime_settings
from persistence import create_run_control_repository, create_stream_repository


class DisposableEngine(Protocol):
    async def dispose(self) -> None: ...


class DatabaseResourcesLike(Protocol):
    engine: DisposableEngine
    session_factory: object


DatabaseFactory = Callable[[Settings], DatabaseResourcesLike]


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    factory: DatabaseFactory = app.state.database_factory
    manager: SimulationManager | None = getattr(app.state, "simulation_manager", None)
    try:
        resources = factory(settings)
    except Exception:
        log_setup_failure("database_factory_failed")
        raise
    app.state.database = resources
    if (
        manager is None
        and getattr(app.state, "attach_default_manager", True)
        and hasattr(resources, "session_factory")
    ):
        run_control = create_run_control_repository(resources.session_factory)  # type: ignore[arg-type]
        app.state.run_control_repository = run_control
        app.state.stream_repository = create_stream_repository(
            resources.session_factory  # type: ignore[arg-type]
        )
        app.state.simulation_manager = SimulationManager(
            settings=settings,
            run_control=run_control,
        )
    log_lifecycle("app_started")
    try:
        yield
        log_lifecycle("app_stopping")
    finally:
        active = getattr(app.state, "simulation_manager", None)
        if isinstance(active, SimulationManager):
            await active.drain()
        fanout = getattr(app.state, "stream_fanout", None)
        if fanout is not None and hasattr(fanout, "close"):
            fanout.close()
        await dispose_engine(resources.engine)
        log_lifecycle("app_stopped")


def create_app(
    settings: Settings | None = None,
    database_factory: DatabaseFactory | None = None,
    *,
    simulation_manager: SimulationManager | None = None,
    attach_default_manager: bool = True,
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
    app.state.attach_default_manager = attach_default_manager
    if simulation_manager is not None:
        app.state.simulation_manager = simulation_manager
    app.add_exception_handler(ApiError, api_error_handler)
    app.add_middleware(RequestIdMiddleware)
    app.include_router(health_router)
    app.include_router(simulations_router)
    app.include_router(inspection_router)
    app.include_router(replay_router)
    app.include_router(streams_router)
    return app
