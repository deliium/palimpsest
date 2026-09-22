"""In-memory scientific evidence and stream repositories for unit tests."""

from __future__ import annotations

from collections.abc import Sequence

from simulation.evidence import (
    ActionResolutionRecord,
    EvidenceManifest,
    GoalRevisionRecord,
)
from simulation.models import RunId
from simulation.persistence import FinalizedBoundaryBatch
from simulation.run_control import StreamRecord, StreamRecordDraft


class InMemoryScientificEvidenceRepository:
    """Copy-on-write scientific evidence with identical-retry semantics."""

    __slots__ = (
        "_goals",
        "_manifests",
        "_resolutions",
        "_stream",
        "_stream_high_water",
    )

    def __init__(self) -> None:
        self._goals: dict[tuple[str, str, int], GoalRevisionRecord] = {}
        self._resolutions: dict[tuple[str, int, int], ActionResolutionRecord] = {}
        self._manifests: dict[tuple[str, str], EvidenceManifest] = {}
        self._stream: dict[str, list[StreamRecord]] = {}
        self._stream_high_water: dict[str, int] = {}

    async def append_goal_revision(self, record: GoalRevisionRecord) -> None:
        key = (record.run_id, record.goal_id, record.revision)
        existing = self._goals.get(key)
        if existing is not None:
            if existing == record:
                return
            raise ValueError("goal_revision_conflict")
        self._goals[key] = record

    async def append_action_resolution(self, record: ActionResolutionRecord) -> None:
        key = (record.run_id, record.tick, record.ordinal)
        existing = self._resolutions.get(key)
        if existing is not None:
            if existing == record:
                return
            raise ValueError("action_resolution_conflict")
        self._resolutions[key] = record

    async def append_manifest(self, manifest: EvidenceManifest) -> None:
        key = (manifest.run_id, manifest.manifest_hash)
        existing = self._manifests.get(key)
        if existing is not None:
            if existing == manifest:
                return
            raise ValueError("manifest_conflict")
        self._manifests[key] = manifest

    async def get_manifest(
        self, *, run_id: str, manifest_hash: str | None = None
    ) -> EvidenceManifest | None:
        if manifest_hash is not None:
            return self._manifests.get((run_id, manifest_hash))
        matches = [
            item for (rid, _), item in self._manifests.items() if rid == run_id
        ]
        if not matches:
            return None
        return matches[-1]

    async def list_goal_revisions(
        self, *, run_id: str
    ) -> tuple[GoalRevisionRecord, ...]:
        items = [item for item in self._goals.values() if item.run_id == run_id]
        items.sort(key=lambda item: (item.goal_id, item.revision))
        return tuple(items)

    async def list_action_resolutions(
        self, *, run_id: str, tick: int | None = None
    ) -> tuple[ActionResolutionRecord, ...]:
        items = [
            item
            for item in self._resolutions.values()
            if item.run_id == run_id and (tick is None or item.tick == tick)
        ]
        items.sort(key=lambda item: (item.tick, item.ordinal))
        return tuple(items)

    async def publish_finalized_boundary(
        self, batch: FinalizedBoundaryBatch
    ) -> tuple[StreamRecord, ...]:
        for resolution in batch.resolutions:
            await self.append_action_resolution(resolution)
        for goal in batch.goal_revisions:
            await self.append_goal_revision(goal)
        if batch.manifest is not None:
            await self.append_manifest(batch.manifest)
        return await self._publish_stream(batch.run_id, batch.stream_drafts)

    async def _publish_stream(
        self, run_id: RunId, drafts: Sequence[StreamRecordDraft]
    ) -> tuple[StreamRecord, ...]:
        if not drafts:
            return ()
        cursor = self._stream_high_water.get(run_id.value, 0)
        bucket = self._stream.setdefault(run_id.value, [])
        published: list[StreamRecord] = []
        for draft in drafts:
            cursor += 1
            record = StreamRecord(
                run_id=run_id,
                cursor=cursor,
                kind=draft.kind,
                envelope=draft.envelope,
                related_tick=draft.related_tick,
            )
            bucket.append(record)
            published.append(record)
        self._stream_high_water[run_id.value] = cursor
        return tuple(published)


class InMemoryStreamRepository:
    """In-memory unified stream with monotonic cursors."""

    __slots__ = ("_evidence",)

    def __init__(
        self, evidence: InMemoryScientificEvidenceRepository | None = None
    ) -> None:
        self._evidence = evidence or InMemoryScientificEvidenceRepository()

    async def publish(
        self, *, run_id: RunId, drafts: Sequence[StreamRecordDraft]
    ) -> tuple[StreamRecord, ...]:
        return await self._evidence._publish_stream(run_id, drafts)

    async def read_after(
        self, *, run_id: RunId, after_cursor: int, limit: int
    ) -> tuple[StreamRecord, ...]:
        records = self._evidence._stream.get(run_id.value, [])
        selected = [item for item in records if item.cursor > after_cursor][:limit]
        return tuple(selected)

    async def high_water(self, *, run_id: RunId) -> int:
        return self._evidence._stream_high_water.get(run_id.value, 0)
