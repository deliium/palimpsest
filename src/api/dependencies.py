"""Injectable FastAPI dependencies. Do not mutate domain state."""

from __future__ import annotations

from typing import cast

from fastapi import Request

from api.branch_api import BranchApiService
from api.observer_service import ObserverReadService
from api.services import (
    CausalDebuggerApiService,
    InspectionService,
    MetricReadService,
    ReplayApiService,
)
from api.simulation_manager import SimulationManager
from infrastructure.database import DatabaseResources
from infrastructure.settings import Settings
from persistence import (
    create_branch_lineage_repository,
    create_experiment_repository,
    create_run_control_repository,
    create_run_repository,
    create_snapshot_repository,
    create_stream_repository,
    create_tick_journal_repository,
)
from simulation.branch_compare import JournalBranchCompare
from simulation.branch_service import BranchService
from simulation.persistence import (
    ExperimentRepository,
    RunControlRepository,
    SimulationRunRepository,
    SnapshotRepository,
    StreamRepository,
    TickJournalRepository,
)
from simulation.replay import ReplayService


def get_settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


def get_database_resources(request: Request) -> DatabaseResources:
    return cast(DatabaseResources, request.app.state.database)


def get_run_repository(request: Request) -> SimulationRunRepository:
    resources = get_database_resources(request)
    return create_run_repository(resources.session_factory)


def get_tick_journal_repository(request: Request) -> TickJournalRepository:
    resources = get_database_resources(request)
    return create_tick_journal_repository(resources.session_factory)


def get_snapshot_repository(request: Request) -> SnapshotRepository:
    resources = get_database_resources(request)
    return create_snapshot_repository(resources.session_factory)


def get_experiment_repository(request: Request) -> ExperimentRepository:
    resources = get_database_resources(request)
    return create_experiment_repository(resources.session_factory)


def get_run_control_repository(request: Request) -> RunControlRepository:
    existing = getattr(request.app.state, "run_control_repository", None)
    if existing is not None:
        return cast(RunControlRepository, existing)
    resources = get_database_resources(request)
    return cast(
        RunControlRepository,
        create_run_control_repository(resources.session_factory),
    )


def get_stream_repository(request: Request) -> StreamRepository:
    existing = getattr(request.app.state, "stream_repository", None)
    if existing is not None:
        return cast(StreamRepository, existing)
    resources = get_database_resources(request)
    return cast(
        StreamRepository,
        create_stream_repository(resources.session_factory),
    )


def get_replay_service(request: Request) -> ReplayService:
    return ReplayService(
        get_run_repository(request),
        get_tick_journal_repository(request),
        get_snapshot_repository(request),
    )


def get_simulation_manager(request: Request) -> SimulationManager:
    manager = getattr(request.app.state, "simulation_manager", None)
    if manager is None:
        from api.errors import service_unavailable

        raise service_unavailable(code="manager_unavailable")
    return cast(SimulationManager, manager)


def get_inspection_service(request: Request) -> InspectionService:
    service = getattr(request.app.state, "inspection_service", None)
    if service is None:
        return InspectionService()
    return cast(InspectionService, service)


def get_metric_read_service(request: Request) -> MetricReadService:
    service = getattr(request.app.state, "metric_read_service", None)
    if service is None:
        return MetricReadService()
    return cast(MetricReadService, service)


def get_observer_service(request: Request) -> ObserverReadService:
    service = getattr(request.app.state, "observer_service", None)
    if service is None:
        return ObserverReadService(replay=get_replay_service(request))
    return cast(ObserverReadService, service)


def get_replay_api_service(request: Request) -> ReplayApiService:
    service = getattr(request.app.state, "replay_api_service", None)
    if service is None:
        return ReplayApiService()
    return cast(ReplayApiService, service)


def get_debugger_service(request: Request) -> CausalDebuggerApiService:
    service = getattr(request.app.state, "debugger_service", None)
    if service is None:
        return CausalDebuggerApiService()
    return cast(CausalDebuggerApiService, service)


def get_branch_api_service(request: Request) -> BranchApiService:
    existing = getattr(request.app.state, "branch_api_service", None)
    if existing is not None:
        return cast(BranchApiService, existing)
    resources = get_database_resources(request)
    lineage = create_branch_lineage_repository(resources.session_factory)
    runs = create_run_repository(resources.session_factory)
    journal = create_tick_journal_repository(resources.session_factory)
    snapshots = create_snapshot_repository(resources.session_factory)
    run_control = get_run_control_repository(request)
    branch = BranchService(
        runs=runs,
        journal=journal,
        snapshots=snapshots,
        lineage=lineage,
        run_control=run_control,
    )
    compare = JournalBranchCompare(journal=journal, lineage=lineage)
    return BranchApiService(
        lineage=lineage,
        branch=branch,
        run_control=run_control,
        compare=compare,
    )
