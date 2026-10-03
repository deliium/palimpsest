"""FastAPI composition root. Importing this module does not connect to PostgreSQL."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Protocol

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from api.durable_runner import make_durable_runner_factory
from api.errors import ApiError, api_error_handler
from api.middleware import RequestIdMiddleware
from api.observer_service import ObserverReadService
from api.persistence_services import (
    PersistenceCausalDebuggerService,
    PersistenceInspectionService,
    PersistenceMetricReadService,
    PersistenceReplayApiService,
)
from api.presentation_static import mount_presentation
from api.routes import (
    branches_router,
    debugger_router,
    health_router,
    inspection_router,
    observer_router,
    observer_stream_router,
    replay_router,
    simulations_router,
    streams_router,
    version_router,
)
from api.simulation_manager import SimulationManager
from infrastructure.database import create_database_resources, dispose_engine
from infrastructure.logging import (
    configure_logging,
    get_logger,
    log_bootstrap,
    log_lifecycle,
    log_setup_failure,
)
from infrastructure.settings import Settings, load_runtime_settings
from persistence import (
    create_branch_lineage_repository,
    create_cognition_trace_repository,
    create_debugger_event_lookup,
    create_debugger_lineage_ports,
    create_inspection_evidence_loader,
    create_metric_document_repository,
    create_metric_set_repository,
    create_run_control_repository,
    create_run_repository,
    create_snapshot_repository,
    create_stream_repository,
    create_tick_journal_repository,
)
from persistence.subjective_sqlalchemy import RelationshipDimensionReader
from simulation.replay import ReplayService

_LOGGER = get_logger("api.app")


class DisposableEngine(Protocol):
    async def dispose(self) -> None: ...


class DatabaseResourcesLike(Protocol):
    engine: DisposableEngine
    session_factory: object


DatabaseFactory = Callable[[Settings], DatabaseResourcesLike]


def _attach_persistence_services(app: FastAPI, session_factory: object) -> None:
    """Wire default persistence-backed facades unless tests already overrode them."""
    runs = create_run_repository(session_factory)  # type: ignore[arg-type]
    journal = create_tick_journal_repository(session_factory)  # type: ignore[arg-type]
    snapshots = create_snapshot_repository(session_factory)  # type: ignore[arg-type]
    replay = ReplayService(runs, journal, snapshots)

    if getattr(app.state, "inspection_service", None) is None:
        evidence = create_inspection_evidence_loader(session_factory)  # type: ignore[arg-type]
        app.state.inspection_service = PersistenceInspectionService(
            evidence=evidence,
            runs=runs,
            replay=replay,
        )
        _LOGGER.info(
            "[FIX] inspection_service_attached",
            service="PersistenceInspectionService",
        )
    if getattr(app.state, "metric_read_service", None) is None:
        app.state.metric_read_service = PersistenceMetricReadService(
            documents=create_metric_document_repository(session_factory),  # type: ignore[arg-type]
            metric_sets=create_metric_set_repository(session_factory),  # type: ignore[arg-type]
            runs=runs,
        )
        _LOGGER.info(
            "[FIX] metric_read_service_attached",
            service="PersistenceMetricReadService",
        )
    if getattr(app.state, "replay_api_service", None) is None:
        app.state.replay_api_service = PersistenceReplayApiService(replay=replay)
        _LOGGER.info(
            "[FIX] replay_api_service_attached",
            service="PersistenceReplayApiService",
        )
    if getattr(app.state, "observer_service", None) is None:
        app.state.observer_service = ObserverReadService(
            replay=replay,
            relationships=RelationshipDimensionReader(session_factory),  # type: ignore[arg-type]
            lineage=create_branch_lineage_repository(session_factory),  # type: ignore[arg-type]
        )
        _LOGGER.info(
            "observer_service_attached",
            service="ObserverReadService",
        )
    if getattr(app.state, "debugger_service", None) is None:
        def _checkpoint_lookup(run_id: str, owner_id: str) -> object | None:
            manager = getattr(app.state, "simulation_manager", None)
            if manager is None or not hasattr(manager, "owner_runtime_checkpoint"):
                return None
            return manager.owner_runtime_checkpoint(run_id, owner_id)

        app.state.debugger_service = PersistenceCausalDebuggerService(
            traces=create_cognition_trace_repository(session_factory),  # type: ignore[arg-type]
            events=create_debugger_event_lookup(session_factory),  # type: ignore[arg-type]
            lineage_ports=create_debugger_lineage_ports(
                session_factory,  # type: ignore[arg-type]
                checkpoint_lookup=_checkpoint_lookup,
            ),
            runs=runs,
        )
        _LOGGER.info(
            "debugger_service_attached",
            service="PersistenceCausalDebuggerService",
        )


async def _api_error_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    """Starlette-compatible wrapper (handler signature uses Exception)."""
    if not isinstance(exc, ApiError):
        raise exc
    return await api_error_handler(request, exc)


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
    if hasattr(resources, "session_factory"):
        if manager is None and getattr(app.state, "attach_default_manager", True):
            run_control = create_run_control_repository(
                resources.session_factory  # type: ignore[arg-type]
            )
            app.state.run_control_repository = run_control
            app.state.stream_repository = create_stream_repository(
                resources.session_factory  # type: ignore[arg-type]
            )
            app.state.simulation_manager = SimulationManager(
                settings=settings,
                run_control=run_control,
                runner_factory=make_durable_runner_factory(
                    resources.session_factory  # type: ignore[arg-type]
                ),
            )
        _attach_persistence_services(app, resources.session_factory)
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
    app.add_exception_handler(ApiError, _api_error_exception_handler)
    app.add_middleware(RequestIdMiddleware)
    app.include_router(health_router)
    app.include_router(simulations_router)
    app.include_router(branches_router)
    app.include_router(inspection_router)
    app.include_router(debugger_router)
    app.include_router(replay_router)
    app.include_router(streams_router)
    app.include_router(observer_router)
    app.include_router(observer_stream_router)
    app.include_router(version_router)
    mount_presentation(app, resolved)
    return app
