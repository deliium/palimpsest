"""FastAPI composition root. Importing this module does not connect to PostgreSQL."""

from __future__ import annotations

import secrets
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Protocol, cast

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from api.civilization_cursor import CivilizationCursorCodec
from api.durable_runner import make_durable_runner_factory
from api.errors import ApiError, api_error_handler
from api.middleware import RequestIdMiddleware
from api.observer_replay_context import PersistenceObserverReplayContextSource
from api.observer_service import ObserverReadService
from api.persistence_services import (
    PersistenceCausalDebuggerService,
    PersistenceInspectionService,
    PersistenceMetricReadService,
    PersistenceReplayApiService,
)
from api.presentation_static import mount_presentation
from api.research_cultural_cursor import CulturalCursorCodec
from api.research_static import mount_research_ui
from api.routes import (
    branches_router,
    civilization_router,
    debugger_router,
    delegation_representation_router,
    dispute_router,
    evidence_testimony_router,
    formal_rule_router,
    health_router,
    inspection_router,
    lineage_router,
    macro_society_router,
    observer_router,
    observer_stream_router,
    organization_router,
    replay_router,
    research_matrix_router,
    research_router,
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
    @property
    def engine(self) -> DisposableEngine: ...

    @property
    def session_factory(self) -> object: ...


DatabaseFactory = Callable[[Settings], DatabaseResourcesLike]


def _attach_persistence_services(app: FastAPI, session_factory: object) -> None:
    """Wire default persistence-backed facades unless tests already overrode them."""
    runs = create_run_repository(session_factory)  # type: ignore[arg-type]
    settings: Settings | None = getattr(app.state, "settings", None)
    if settings is None:
        _LOGGER.debug(
            "civilization_service_attach_skipped",
            reason_code="settings_unavailable",
        )
    elif (
        settings.civilization_root is not None
        and getattr(app.state, "civilization_service", None) is None
    ):
        try:
            from api.civilization_service import ArtifactCivilizationApiService
            from persistence.civilization_filesystem import create_civilization_reader

            app.state.civilization_service = ArtifactCivilizationApiService(
                create_civilization_reader(settings.civilization_root),
                cast(CivilizationCursorCodec, app.state.civilization_cursor_codec),
                runs,
            )
            _LOGGER.info(
                "civilization_service_attached",
                service="ArtifactCivilizationApiService",
            )
        except Exception:
            app.state.civilization_service = None
            _LOGGER.warning(
                "civilization_service_attach_failed",
                reason_code="civilization_storage_unavailable",
            )
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
            replay_context=PersistenceObserverReplayContextSource(
                run_control=create_run_control_repository(session_factory)  # type: ignore[arg-type]
            ),
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
            return cast(object, manager.owner_runtime_checkpoint(run_id, owner_id))

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
                    resources.session_factory,  # type: ignore[arg-type]
                    settings=settings,
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


def _attach_macro_society_reader(app: FastAPI) -> None:
    from api.macro_society_cursor import MacroSocietyCursorCodec
    from persistence.macro_society_filesystem import create_macro_society_reader

    settings: Settings = app.state.settings
    secret = (
        settings.macro_society_cursor_key.get_secret_value().encode("utf-8")
        if settings.macro_society_cursor_key is not None
        else None
    )
    app.state.macro_society_cursor_codec = MacroSocietyCursorCodec.from_secret(secret)
    app.state.macro_society_reader = create_macro_society_reader(
        settings.macro_society_root
    )


def _attach_organization_reader(app: FastAPI) -> None:
    from api.organization_cursor import OrganizationCursorCodec
    from persistence.organization_filesystem import create_organization_reader

    settings: Settings = app.state.settings
    secret = (
        settings.organization_cursor_key.get_secret_value().encode("utf-8")
        if settings.organization_cursor_key is not None
        else None
    )
    if settings.organization_root is None or secret is None:
        app.state.organization_cursor_codec = None
        app.state.organization_reader = None
        return
    app.state.organization_cursor_codec = OrganizationCursorCodec.from_secret(secret)
    app.state.organization_reader = create_organization_reader(
        settings.organization_root
    )


def _attach_formal_rule_reader(app: FastAPI) -> None:
    from api.formal_rule_cursor import FormalRuleCursorCodec
    from persistence.formal_rule_filesystem import create_formal_rule_reader

    settings: Settings = app.state.settings
    secret = (
        settings.formal_rule_cursor_key.get_secret_value().encode("utf-8")
        if settings.formal_rule_cursor_key is not None
        else None
    )
    if settings.formal_rule_root is None or secret is None:
        app.state.formal_rule_cursor_codec = None
        app.state.formal_rule_reader = None
        return
    app.state.formal_rule_cursor_codec = FormalRuleCursorCodec.from_secret(secret)
    app.state.formal_rule_reader = create_formal_rule_reader(settings.formal_rule_root)


def _attach_dispute_reader(app: FastAPI) -> None:
    from api.dispute_cursor import DisputeCursorCodec
    from persistence.dispute_filesystem import create_dispute_reader

    settings = getattr(app.state, "settings", None)
    if not isinstance(settings, Settings):
        app.state.dispute_cursor_codec = None
        app.state.dispute_reader = None
        _LOGGER.debug("dispute_reader_skipped", reason_code="settings_unavailable")
        return
    secret = (
        settings.dispute_cursor_key.get_secret_value().encode("utf-8")
        if settings.dispute_cursor_key is not None
        else None
    )
    if settings.dispute_root is None or secret is None:
        app.state.dispute_cursor_codec = None
        app.state.dispute_reader = None
        return
    app.state.dispute_cursor_codec = DisputeCursorCodec.from_secret(secret)
    app.state.dispute_reader = create_dispute_reader(settings.dispute_root)


def _attach_evidence_testimony_reader(app: FastAPI) -> None:
    from api.evidence_testimony_cursor import EvidenceTestimonyCursorCodec
    from persistence.evidence_testimony_filesystem import (
        create_evidence_testimony_reader,
    )

    settings = getattr(app.state, "settings", None)
    if not isinstance(settings, Settings):
        app.state.evidence_testimony_cursor_codec = None
        app.state.evidence_testimony_reader = None
        return
    secret = (
        settings.evidence_cursor_key.get_secret_value().encode("utf-8")
        if settings.evidence_cursor_key is not None
        else None
    )
    if settings.evidence_root is None or secret is None:
        app.state.evidence_testimony_cursor_codec = None
        app.state.evidence_testimony_reader = None
        return
    app.state.evidence_testimony_cursor_codec = (
        EvidenceTestimonyCursorCodec.from_secret(secret)
    )
    app.state.evidence_testimony_reader = create_evidence_testimony_reader(
        settings.evidence_root
    )


def _attach_delegation_representation_reader(app: FastAPI) -> None:
    from api.delegation_representation_cursor import (
        DelegationRepresentationCursorCodec,
    )
    from persistence.delegation_representation_filesystem import (
        create_delegation_representation_reader,
    )

    settings = getattr(app.state, "settings", None)
    if not isinstance(settings, Settings):
        app.state.representation_cursor_codec = None
        app.state.representation_reader = None
        return
    secret = (
        settings.representation_cursor_key.get_secret_value().encode("utf-8")
        if settings.representation_cursor_key is not None
        else None
    )
    if settings.representation_root is None or secret is None:
        app.state.representation_cursor_codec = None
        app.state.representation_reader = None
        return
    app.state.representation_cursor_codec = (
        DelegationRepresentationCursorCodec.from_secret(secret)
    )
    app.state.representation_reader = create_delegation_representation_reader(
        settings.representation_root
    )


def _attach_lineage_service(app: FastAPI) -> None:
    from api.lineage_cursor import LineageCursorCodec

    settings: Settings = app.state.settings
    secret = (
        settings.lineage_cursor_key.get_secret_value().encode("utf-8")
        if settings.lineage_cursor_key is not None
        else None
    )
    try:
        codec = getattr(app.state, "lineage_cursor_codec", None)
        if codec is None:
            codec = LineageCursorCodec.from_secret(secret)
            app.state.lineage_cursor_codec = codec
        if getattr(app.state, "lineage_service", None) is not None:
            return
        if settings.lineage_root is None:
            return
        from api.lineage_service import ArtifactLineageApiService

        app.state.lineage_service = ArtifactLineageApiService(
            root=settings.lineage_root, codec=codec
        )
    except Exception:
        app.state.lineage_service = None


def _attach_research_cultural_service(app: FastAPI) -> None:
    settings: Settings = app.state.settings
    if settings.research_matrix_root is None:
        return
    if getattr(app.state, "research_cultural_service", None) is not None:
        return
    from api.research_cultural_service import ResearchCulturalService

    app.state.research_cultural_service = ResearchCulturalService(
        settings.research_matrix_root
    )


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
    _attach_lineage_service(app)
    _attach_macro_society_reader(app)
    _attach_organization_reader(app)
    _attach_formal_rule_reader(app)
    _attach_dispute_reader(app)
    _attach_evidence_testimony_reader(app)
    _attach_delegation_representation_reader(app)
    _attach_research_cultural_service(app)
    if getattr(app.state, "research_cultural_cursor_codec", None) is None:
        app.state.research_cultural_cursor_codec = CulturalCursorCodec.from_secret(
            secrets.token_bytes(32)
        )
    app.state.civilization_cursor_codec = CivilizationCursorCodec(
        None
        if resolved.civilization_cursor_key is None
        else resolved.civilization_cursor_key.get_secret_value().encode("utf-8")
    )
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
    app.include_router(research_router)
    app.include_router(research_matrix_router)
    app.include_router(debugger_router)
    app.include_router(lineage_router)
    app.include_router(macro_society_router)
    app.include_router(organization_router)
    app.include_router(formal_rule_router)
    app.include_router(dispute_router)
    app.include_router(evidence_testimony_router)
    app.include_router(delegation_representation_router)
    app.include_router(replay_router)
    app.include_router(streams_router)
    app.include_router(observer_router)
    app.include_router(civilization_router)
    app.include_router(observer_stream_router)
    app.include_router(version_router)
    # Research UI precedes the presentation catch-all at `/`.
    mount_research_ui(app, resolved)
    mount_presentation(app, resolved)
    return app
