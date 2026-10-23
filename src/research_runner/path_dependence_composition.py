"""Production repository composition for path-dependence resume (no HTTP)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Final

from infrastructure.database import DatabaseResources, create_database_resources
from infrastructure.settings import Settings
from persistence import (
    create_pending_finalization_repository,
    create_run_repository,
    create_scientific_evidence_repository,
    create_snapshot_repository,
    create_tick_journal_repository,
)
from simulation.clock import Tick
from simulation.models import RunId
from simulation.runner import RunnerDependencyFactories

_LOG: Final[logging.Logger] = logging.getLogger(
    "research_runner.path_dependence_composition"
)


@dataclass(frozen=True, slots=True)
class PostgresObjectivePresence:
    """Read-only objective presence used by resume classification."""

    runs: object
    journal: object
    snapshots: object

    async def exists(self, run_id: str) -> bool:
        get_run = getattr(self.runs, "get_run", None)
        if not callable(get_run):
            return False
        manifest = await get_run(RunId(run_id))
        return manifest is not None

    async def terminal(self, run_id: str) -> dict[str, object] | None:
        get_run = getattr(self.runs, "get_run", None)
        list_commits = getattr(self.journal, "list_tick_commits", None)
        get_snapshot = getattr(self.snapshots, "get_latest_at_or_before", None)
        if not callable(get_run) or not callable(list_commits):
            return None
        target = RunId(run_id)
        manifest = await get_run(target)
        if manifest is None:
            return None
        commits = await list_commits(target, from_tick=Tick(0), to_tick=None)
        if not commits:
            return None
        last = commits[-1]
        head_hash = None
        if callable(get_snapshot):
            snapshot = await get_snapshot(target, last.resulting_tick)
            if snapshot is not None:
                head_hash = snapshot.integrity_hash.value
        return {
            "terminal_tick": last.resulting_tick.value,
            "terminal_revision": last.resulting_revision.value,
            "head_hash": head_hash,
        }


@dataclass(slots=True)
class PathDependencePostgresComposition:
    resources: DatabaseResources
    presence: PostgresObjectivePresence
    factories: RunnerDependencyFactories

    async def close(self) -> None:
        await self.resources.engine.dispose()

    @property
    def forks(self) -> object:
        return self.presence


def build_path_dependence_postgres_composition(
    settings: Settings,
) -> PathDependencePostgresComposition:
    """Build read-only repositories from existing validated infrastructure."""
    resources = create_database_resources(settings)
    runs = create_run_repository(resources.session_factory)
    journal = create_tick_journal_repository(resources.session_factory)
    snapshots = create_snapshot_repository(resources.session_factory)
    pending = create_pending_finalization_repository(resources.session_factory)
    evidence = create_scientific_evidence_repository(resources.session_factory)
    _LOG.info("path_dependence_postgres_composition_built")
    return PathDependencePostgresComposition(
        resources=resources,
        presence=PostgresObjectivePresence(
            runs=runs, journal=journal, snapshots=snapshots
        ),
        factories=RunnerDependencyFactories(
            run_repository=runs,
            journal=journal,
            pending_finalizations=pending,
            scientific_evidence=evidence,
        ),
    )


__all__ = [
    "PathDependencePostgresComposition",
    "PostgresObjectivePresence",
    "build_path_dependence_postgres_composition",
]
