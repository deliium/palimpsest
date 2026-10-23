"""Process-local repositories for deterministic prefix reconstruction.

These adapters implement existing public simulation ports. They are isolated
from production durability and are never a substitute for original history.
"""

from __future__ import annotations

import hashlib
import json

from simulation.clock import Tick
from simulation.models import RunId
from simulation.persistence import (
    CommitHash,
    PayloadHash,
    RunCreateRequest,
    RunManifest,
    SnapshotId,
    TickAppendRequest,
    TickCommit,
    WorldEvent,
    WorldRevision,
    WorldSnapshot,
)


class IsolatedReconstructionError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _digest(payload: object) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class IsolatedReconstructionRepositories:
    """In-memory run, journal and snapshot ports with real commit checks."""

    __slots__ = ("_commits", "_runs", "_snapshots")

    def __init__(self) -> None:
        self._runs: dict[RunId, RunManifest] = {}
        self._commits: dict[
            RunId, dict[Tick, tuple[TickCommit, tuple[WorldEvent, ...]]]
        ] = {}
        self._snapshots: dict[SnapshotId, WorldSnapshot] = {}

    @property
    def runs(self) -> IsolatedReconstructionRepositories:
        return self

    @property
    def journal(self) -> IsolatedReconstructionRepositories:
        return self

    @property
    def snapshots(self) -> IsolatedReconstructionRepositories:
        return self

    async def create_run(self, request: RunCreateRequest) -> RunManifest:
        if type(request) is not RunCreateRequest:
            raise TypeError("request must be RunCreateRequest")
        if request.run_id in self._runs:
            raise IsolatedReconstructionError("run_exists")
        manifest = RunManifest(
            run_id=request.run_id,
            world_id=request.world_id,
            seed=request.seed,
            config=request.config,
            derivation_version=request.derivation_version,
            event_schema_version=request.event_schema_version,
            projector_version=request.projector_version,
            persistence_codec_version=request.persistence_codec_version,
        )
        self._runs[request.run_id] = manifest
        self._commits[request.run_id] = {}
        self._snapshots[request.bootstrap.snapshot_id] = request.bootstrap
        return manifest

    async def get_run(self, run_id: RunId) -> RunManifest | None:
        return self._runs.get(run_id)

    async def append_tick(self, request: TickAppendRequest) -> TickCommit:
        if type(request) is not TickAppendRequest:
            raise TypeError("request must be TickAppendRequest")
        if request.run_id not in self._runs:
            raise IsolatedReconstructionError("run_missing")
        commits = self._commits[request.run_id]
        existing = commits.get(request.tick)
        if existing is not None:
            commit = existing[0]
            if commit.idempotency_key == request.idempotency_key:
                return commit
            raise IsolatedReconstructionError("tick_conflict")
        previous_tick = request.tick.value - 1
        predecessor = None
        if previous_tick >= 0:
            previous = commits.get(Tick(previous_tick))
            predecessor = None if previous is None else previous[0].commit_hash
        if predecessor != request.expected_predecessor_commit_hash:
            raise IsolatedReconstructionError("predecessor_mismatch")
        if request.tick.value > 0:
            latest_revision = max(
                (commit.resulting_revision.value for commit, _ in commits.values()),
                default=0,
            )
            if request.expected_base_revision.value != latest_revision:
                raise IsolatedReconstructionError("revision_mismatch")
        payload_ids = [
            [event.event_id.value, event.sequence, str(event.details.kind)]
            for event in request.events
        ]
        snapshot_hash = (
            None
            if request.snapshot is None
            else request.snapshot.integrity_hash.value
        )
        resulting_revision = WorldRevision(
            request.expected_base_revision.value
            + (1 if request.events else 0)
        )
        payload_digest = _digest(
            {
                "events": payload_ids,
                "snapshot": snapshot_hash,
                "tick": request.tick.value,
            }
        )
        commit_digest = _digest(
            {
                "predecessor": (
                    None
                    if request.expected_predecessor_commit_hash is None
                    else request.expected_predecessor_commit_hash.value
                ),
                "payload": payload_digest,
                "run_id": request.run_id.value,
                "tick": request.tick.value,
            }
        )
        snapshot_id = None
        if request.snapshot is not None:
            snapshot_id = request.snapshot.snapshot_id
            self._snapshots[snapshot_id] = request.snapshot
        commit = TickCommit(
            run_id=request.run_id,
            tick=request.tick,
            resulting_tick=Tick(request.tick.value + 1),
            base_revision=request.expected_base_revision,
            resulting_revision=resulting_revision,
            predecessor_commit_hash=request.expected_predecessor_commit_hash,
            commit_hash=CommitHash(commit_digest),
            idempotency_key=request.idempotency_key,
            event_count=len(request.events),
            payload_hash=PayloadHash(payload_digest),
            snapshot_id=snapshot_id,
        )
        commits[request.tick] = (commit, tuple(request.events))
        return commit

    async def get_tick_commit(
        self, run_id: RunId, tick: Tick
    ) -> TickCommit | None:
        entry = self._commits.get(run_id, {}).get(tick)
        return None if entry is None else entry[0]

    async def list_events(
        self,
        run_id: RunId,
        *,
        from_tick: Tick,
        to_tick: Tick | None,
        limit: int,
        offset: int,
    ) -> tuple[WorldEvent, ...]:
        events: list[WorldEvent] = []
        for tick, (_commit, tick_events) in sorted(
            self._commits.get(run_id, {}).items()
        ):
            if tick.value < from_tick.value:
                continue
            if to_tick is not None and tick.value > to_tick.value:
                continue
            events.extend(tick_events)
        return tuple(events[offset : offset + limit])

    async def list_tick_commits(
        self,
        run_id: RunId,
        *,
        from_tick: Tick,
        to_tick: Tick | None,
    ) -> tuple[TickCommit, ...]:
        return tuple(
            commit
            for tick, (commit, _events) in sorted(
                self._commits.get(run_id, {}).items()
            )
            if tick.value >= from_tick.value
            and (to_tick is None or tick.value <= to_tick.value)
        )

    async def get_latest_at_or_before(
        self, run_id: RunId, tick: Tick
    ) -> WorldSnapshot | None:
        candidates = [
            snapshot
            for snapshot_id, snapshot in self._snapshots.items()
            if snapshot.run_id == run_id and snapshot.next_tick.value <= tick.value
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda item: item.next_tick.value)

    async def get_snapshot(self, snapshot_id: SnapshotId) -> WorldSnapshot | None:
        return self._snapshots.get(snapshot_id)


__all__ = [
    "IsolatedReconstructionError",
    "IsolatedReconstructionRepositories",
]
