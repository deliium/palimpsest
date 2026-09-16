"""Injectable FastAPI dependencies. Do not mutate domain state."""

from __future__ import annotations

from typing import cast

from fastapi import Request

from infrastructure.database import DatabaseResources
from infrastructure.settings import Settings
from persistence import (
    create_experiment_repository,
    create_run_repository,
    create_snapshot_repository,
    create_tick_journal_repository,
)
from simulation.persistence import (
    ExperimentRepository,
    SimulationRunRepository,
    SnapshotRepository,
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


def get_replay_service(request: Request) -> ReplayService:
    return ReplayService(
        get_run_repository(request),
        get_tick_journal_repository(request),
        get_snapshot_repository(request),
    )
