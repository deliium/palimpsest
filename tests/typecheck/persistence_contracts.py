"""Mypy fixtures for persistence repository protocol contracts."""

from __future__ import annotations

from simulation.clock import Tick
from simulation.models import DERIVATION_VERSION, RunId, SimulationRunConfig
from simulation.persistence import (
    EVENT_SCHEMA_VERSION,
    PERSISTENCE_CODEC_VERSION,
    PROJECTOR_VERSION,
    CommitHash,
    ExperimentId,
    ExperimentMetadata,
    ExperimentRepository,
    ExperimentRunAssignment,
    PayloadHash,
    ReplayFallbackPolicy,
    ReplayMode,
    ReplayRequest,
    ReplayResult,
    ReplayStatus,
    RunCreateRequest,
    RunManifest,
    SimulationRunRepository,
    SnapshotId,
    SnapshotRepository,
    TickAppendRequest,
    TickCommit,
    TickJournalRepository,
    WorldSnapshot,
)
from world.events import WorldEvent
from world.identifiers import WorldId, WorldRevision


class _MemoryRunRepository:
    async def create_run(self, request: RunCreateRequest) -> RunManifest:
        return RunManifest(
            run_id=request.run_id,
            world_id=request.world_id,
            seed=request.seed,
            config=request.config,
            derivation_version=request.derivation_version,
            event_schema_version=request.event_schema_version,
            projector_version=request.projector_version,
            persistence_codec_version=request.persistence_codec_version,
        )

    async def get_run(self, run_id: RunId) -> RunManifest | None:
        _ = run_id
        return None


class _MemoryTickJournal:
    async def append_tick(self, request: TickAppendRequest) -> TickCommit:
        return TickCommit(
            run_id=request.run_id,
            tick=request.tick,
            resulting_tick=Tick(request.tick.value + 1),
            base_revision=request.expected_base_revision,
            resulting_revision=request.expected_base_revision,
            predecessor_commit_hash=request.expected_predecessor_commit_hash,
            commit_hash=CommitHash("a" * 64),
            idempotency_key=request.idempotency_key,
            event_count=len(request.events),
            payload_hash=PayloadHash("b" * 64),
        )

    async def get_tick_commit(
        self, run_id: RunId, tick: Tick
    ) -> TickCommit | None:
        _ = (run_id, tick)
        return None

    async def list_events(
        self,
        run_id: RunId,
        *,
        from_tick: Tick,
        to_tick: Tick | None,
        limit: int,
        offset: int,
    ) -> tuple[WorldEvent, ...]:
        _ = (run_id, from_tick, to_tick, limit, offset)
        return ()


class _MemorySnapshots:
    async def get_latest_at_or_before(
        self, run_id: RunId, tick: Tick
    ) -> WorldSnapshot | None:
        _ = (run_id, tick)
        return None

    async def get_snapshot(self, snapshot_id: SnapshotId) -> WorldSnapshot | None:
        _ = snapshot_id
        return None


class _MemoryExperiments:
    async def create_experiment(
        self, metadata: ExperimentMetadata
    ) -> ExperimentMetadata:
        return metadata

    async def assign_run(
        self, assignment: ExperimentRunAssignment
    ) -> ExperimentRunAssignment:
        return assignment

    async def get_experiment(
        self, experiment_id: ExperimentId
    ) -> ExperimentMetadata | None:
        _ = experiment_id
        return None


def _ports() -> tuple[
    SimulationRunRepository,
    TickJournalRepository,
    SnapshotRepository,
    ExperimentRepository,
]:
    runs: SimulationRunRepository = _MemoryRunRepository()
    ticks: TickJournalRepository = _MemoryTickJournal()
    snapshots: SnapshotRepository = _MemorySnapshots()
    experiments: ExperimentRepository = _MemoryExperiments()
    return runs, ticks, snapshots, experiments


def _replay_round_trip() -> ReplayResult:
    request = ReplayRequest(
        run_id=RunId("run-1"),
        target_tick=Tick(0),
        fallback_policy=ReplayFallbackPolicy.LATEST_AT_OR_BEFORE,
    )
    return ReplayResult(
        run_id=request.run_id,
        status=ReplayStatus.OK,
        mode=ReplayMode.CONTINUATION,
        snapshot_id=SnapshotId("snap-1"),
        snapshot_next_tick=Tick(0),
        target_tick=request.target_tick,
        events_applied=0,
        event_schema_version=EVENT_SCHEMA_VERSION,
        projector_version=PROJECTOR_VERSION,
        persistence_codec_version=PERSISTENCE_CODEC_VERSION,
    )


def _manifest_uses_public_config() -> RunManifest:
    return RunManifest(
        run_id=RunId("run-1"),
        world_id=WorldId("world-1"),
        seed=1,
        config=SimulationRunConfig(seed=1),
        derivation_version=DERIVATION_VERSION,
        event_schema_version=EVENT_SCHEMA_VERSION,
        projector_version=PROJECTOR_VERSION,
        persistence_codec_version=PERSISTENCE_CODEC_VERSION,
    )


_ = (_ports(), _replay_round_trip(), _manifest_uses_public_config(), WorldRevision(0))
