"""PostgreSQL execution and read-only path-dependence resume (no HTTP)."""

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
from simulation.branch_service import BranchService, rematerialize_snapshot
from simulation.clock import Tick
from simulation.engine import WorldEngine
from simulation.fork_checkpoint import RunnerForkCheckpoint
from simulation.models import RunId
from simulation.persistence import (
    SimulationRunRepository,
    SnapshotId,
    SnapshotRepository,
    TickJournalRepository,
)
from simulation.runner import RunnerDependencyFactories

_LOG: Final[logging.Logger] = logging.getLogger(
    "research_runner.path_dependence_composition"
)


@dataclass(frozen=True, slots=True)
class PostgresObjectivePresence:
    """Read-only objective presence used by resume classification."""

    runs: SimulationRunRepository
    journal: TickJournalRepository
    snapshots: SnapshotRepository

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

    async def materialize_engine(
        self, checkpoint: RunnerForkCheckpoint, child_run: RunId
    ) -> WorldEngine:
        """Persist the ordinary objective prefix before binding a fork child."""
        result = await BranchService(
            runs=self.presence.runs,
            journal=self.presence.journal,
            snapshots=self.presence.snapshots,
        ).materialize_objective_fork(
            parent_run_id=checkpoint.run_id,
            child_run_id=child_run,
            fork_tick=checkpoint.boundary_tick.value,
        )
        predecessor = (
            result.child_commits[-1].commit_hash if result.child_commits else None
        )
        snapshot = rematerialize_snapshot(
            checkpoint.snapshot,
            child_run_id=child_run,
            snapshot_id=SnapshotId(f"child-{child_run.value}"),
            predecessor_commit_hash=predecessor,
            next_tick=checkpoint.boundary_tick,
        )
        config = checkpoint.config
        return WorldEngine.restore_from_snapshot(
            snapshot,
            population_lifecycle=config.population_lifecycle,
            new_agent_initialization=config.new_agent_initialization,
            kinship_spec=config.kinship,
            environmental_dynamics=config.environmental_dynamics,
            artifacts_enabled=config.artifacts_enabled,
        )

    async def close(self) -> None:
        await self.resources.engine.dispose()

    @property
    def forks(self) -> object:
        return self.presence


def build_path_dependence_postgres_composition(
    settings: Settings,
) -> PathDependencePostgresComposition:
    """Compose execution and inspection from existing validated adapters."""
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
