"""Public replay and recovery orchestration for durable simulation runs.

Loads manifests/checkpoints/events, validates versions and hash-chain
continuity, and restores a ``WorldEngine`` at a target tick. Continuation is
allowed only at the durable head.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from simulation.clock import Tick
from simulation.engine import WorldEngine
from simulation.journal import PersistenceSerializationError, verify_commit_chain
from simulation.lifecycle import EngineDiagnosticCode
from simulation.models import DERIVATION_VERSION, RunId
from simulation.persistence import (
    ACCEPTED_EVENT_SCHEMA_VERSIONS,
    ACCEPTED_PERSISTENCE_CODEC_VERSIONS,
    ACCEPTED_PROJECTOR_VERSIONS,
    EVENT_SCHEMA_VERSION,
    PERSISTENCE_CODEC_VERSION,
    PROJECTOR_VERSION,
    CommitHash,
    ReplayCommitPage,
    ReplayEventPage,
    ReplayFallbackPolicy,
    ReplayMode,
    ReplayRequest,
    ReplayResult,
    ReplayStatus,
    RunManifest,
    SimulationRunRepository,
    SnapshotId,
    SnapshotRepository,
    TickCommit,
    TickJournalRepository,
    WorldEvent,
    WorldSnapshot,
    schema_projector_compatible,
)
from simulation.service import PersistentSimulationService

_LOGGER = logging.getLogger("simulation.replay")

__all__ = [
    "ReplayOutcome",
    "ReplayService",
]

_DEFAULT_PAGE_SIZE = 100
_MAX_PAGE_SIZE = 1000


def _clamp_page_limit(limit: int) -> int:
    if isinstance(limit, bool) or type(limit) is not int or limit < 1:
        _LOGGER.error(
            "%s code=invalid_page_limit",
            EngineDiagnosticCode.CHECKPOINT_CORRUPT.value,
        )
        raise ValueError("invalid_page_limit")
    if limit > _MAX_PAGE_SIZE:
        _LOGGER.error(
            "%s code=page_limit_exceeded limit=%s maximum=%s",
            EngineDiagnosticCode.CHECKPOINT_CORRUPT.value,
            limit,
            _MAX_PAGE_SIZE,
        )
        raise ValueError("page_limit_exceeded")
    return limit


@dataclass(frozen=True, slots=True)
class ReplayOutcome:
    """Detached replay metadata plus an optional restored engine."""

    result: ReplayResult
    engine: WorldEngine | None
    predecessor_commit_hash: CommitHash | None

    def __post_init__(self) -> None:
        if type(self.result) is not ReplayResult:
            raise TypeError("ReplayOutcome.result must be ReplayResult")
        if self.engine is not None and type(self.engine) is not WorldEngine:
            raise TypeError("ReplayOutcome.engine must be WorldEngine or None")
        if (
            self.predecessor_commit_hash is not None
            and type(self.predecessor_commit_hash) is not CommitHash
        ):
            raise TypeError(
                "ReplayOutcome.predecessor_commit_hash must be CommitHash or None"
            )
        if self.result.status is ReplayStatus.OK and self.engine is None:
            raise ValueError("OK replay outcomes require an engine")
        if self.result.status is not ReplayStatus.OK and self.engine is not None:
            raise ValueError("failed replay outcomes must not include an engine")


class ReplayService:
    """Async reconstruction of objective world state from durable history."""

    __slots__ = ("_journal", "_runs", "_snapshots")

    def __init__(
        self,
        runs: SimulationRunRepository,
        journal: TickJournalRepository,
        snapshots: SnapshotRepository,
    ) -> None:
        self._runs = runs
        self._journal = journal
        self._snapshots = snapshots

    async def replay(self, request: ReplayRequest) -> ReplayOutcome:
        if type(request) is not ReplayRequest:
            raise TypeError("replay requires ReplayRequest")
        run_id = request.run_id
        _LOGGER.info(
            "%s run_id=%s target_tick=%s policy=%s",
            EngineDiagnosticCode.CHECKPOINT_RESTORE.value,
            run_id.value,
            None if request.target_tick is None else request.target_tick.value,
            request.fallback_policy.value,
        )

        manifest = await self._runs.get_run(run_id)
        if manifest is None:
            _LOGGER.error(
                "%s code=run_missing run_id=%s",
                EngineDiagnosticCode.CHECKPOINT_CORRUPT.value,
                run_id.value,
            )
            return self._failed(
                run_id,
                ReplayStatus.TARGET_UNREACHABLE,
                request.target_tick,
            )

        if not _versions_compatible(
            event_schema_version=manifest.event_schema_version,
            projector_version=manifest.projector_version,
            persistence_codec_version=manifest.persistence_codec_version,
            derivation_version=manifest.derivation_version,
        ):
            _LOGGER.error(
                "%s code=version_incompatible run_id=%s",
                EngineDiagnosticCode.CHECKPOINT_CORRUPT.value,
                run_id.value,
            )
            return self._failed(
                run_id,
                ReplayStatus.VERSION_INCOMPATIBLE,
                request.target_tick,
                event_schema_version=manifest.event_schema_version,
                projector_version=manifest.projector_version,
                persistence_codec_version=manifest.persistence_codec_version,
            )

        compatibility_path = (
            "current"
            if manifest.event_schema_version == EVENT_SCHEMA_VERSION
            else "legacy_compatible"
        )
        _LOGGER.debug(
            "replay_versions_accepted run_id=%s event_schema_version=%s "
            "projector_version=%s persistence_codec_version=%s "
            "compatibility_path=%s",
            run_id.value,
            manifest.event_schema_version,
            manifest.projector_version,
            manifest.persistence_codec_version,
            compatibility_path,
        )

        head_next = await self._durable_head_next_tick(run_id)
        if request.target_tick is None:
            target_tick = head_next
        else:
            target_tick = request.target_tick
        if target_tick.value > head_next.value:
            _LOGGER.error(
                "%s code=target_past_head run_id=%s target_tick=%s head=%s",
                EngineDiagnosticCode.CHECKPOINT_CORRUPT.value,
                run_id.value,
                target_tick.value,
                head_next.value,
            )
            return self._failed(
                run_id,
                ReplayStatus.TARGET_UNREACHABLE,
                target_tick,
                event_schema_version=manifest.event_schema_version,
                projector_version=manifest.projector_version,
                persistence_codec_version=manifest.persistence_codec_version,
            )

        snapshot = await self._snapshots.get_latest_at_or_before(run_id, target_tick)
        if snapshot is None:
            _LOGGER.error(
                "%s code=snapshot_missing run_id=%s target_tick=%s",
                EngineDiagnosticCode.CHECKPOINT_CORRUPT.value,
                run_id.value,
                target_tick.value,
            )
            return self._failed(
                run_id,
                ReplayStatus.SNAPSHOT_MISSING,
                target_tick,
                event_schema_version=manifest.event_schema_version,
                projector_version=manifest.projector_version,
                persistence_codec_version=manifest.persistence_codec_version,
            )

        if request.fallback_policy is ReplayFallbackPolicy.REQUIRE_EXACT:
            if snapshot.next_tick != target_tick:
                _LOGGER.error(
                    "%s code=exact_snapshot_missing run_id=%s target_tick=%s",
                    EngineDiagnosticCode.CHECKPOINT_CORRUPT.value,
                    run_id.value,
                    target_tick.value,
                )
                return self._failed(
                    run_id,
                    ReplayStatus.SNAPSHOT_MISSING,
                    target_tick,
                    snapshot_id=snapshot.snapshot_id,
                    snapshot_next_tick=snapshot.next_tick,
                    event_schema_version=manifest.event_schema_version,
                    projector_version=manifest.projector_version,
                    persistence_codec_version=manifest.persistence_codec_version,
                )
        elif snapshot.next_tick.value < target_tick.value:
            # Older checkpoint than the target cursor under explicit fallback policy.
            _LOGGER.warning(
                "%s run_id=%s snapshot_next_tick=%s target_tick=%s",
                EngineDiagnosticCode.CHECKPOINT_FALLBACK.value,
                run_id.value,
                snapshot.next_tick.value,
                target_tick.value,
            )

        if not _snapshot_matches_manifest(snapshot, manifest):
            _LOGGER.error(
                "%s code=snapshot_version_mismatch run_id=%s snapshot_id=%s",
                EngineDiagnosticCode.CHECKPOINT_CORRUPT.value,
                run_id.value,
                snapshot.snapshot_id.value,
            )
            return self._failed(
                run_id,
                ReplayStatus.VERSION_INCOMPATIBLE,
                target_tick,
                snapshot_id=snapshot.snapshot_id,
                snapshot_next_tick=snapshot.next_tick,
                event_schema_version=snapshot.event_schema_version,
                projector_version=snapshot.projector_version,
                persistence_codec_version=snapshot.persistence_codec_version,
            )

        if snapshot.next_tick.value > target_tick.value:
            _LOGGER.error(
                "%s code=snapshot_after_target run_id=%s",
                EngineDiagnosticCode.CHECKPOINT_CORRUPT.value,
                run_id.value,
            )
            return self._failed(
                run_id,
                ReplayStatus.TARGET_UNREACHABLE,
                target_tick,
                snapshot_id=snapshot.snapshot_id,
                snapshot_next_tick=snapshot.next_tick,
                event_schema_version=manifest.event_schema_version,
                projector_version=manifest.projector_version,
                persistence_codec_version=manifest.persistence_codec_version,
            )

        to_commit_tick: Tick | None
        if target_tick.value == 0:
            to_commit_tick = None
            commits: tuple[TickCommit, ...] = ()
        else:
            to_commit_tick = Tick(target_tick.value - 1)
            commits = await self._journal.list_tick_commits(
                run_id,
                from_tick=snapshot.next_tick,
                to_tick=to_commit_tick,
            )

        _LOGGER.debug(
            "%s run_id=%s snapshot_id=%s from_tick=%s to_tick=%s "
            "commit_count=%s target_tick=%s",
            EngineDiagnosticCode.CHECKPOINT_RESTORE.value,
            run_id.value,
            snapshot.snapshot_id.value,
            snapshot.next_tick.value,
            None if to_commit_tick is None else to_commit_tick.value,
            len(commits),
            target_tick.value,
        )

        if not _commits_cover_range(commits, snapshot.next_tick, to_commit_tick):
            _LOGGER.error(
                "%s code=commit_gap run_id=%s",
                EngineDiagnosticCode.CHECKPOINT_CORRUPT.value,
                run_id.value,
            )
            return self._failed(
                run_id,
                ReplayStatus.STREAM_DISCONTINUITY,
                target_tick,
                snapshot_id=snapshot.snapshot_id,
                snapshot_next_tick=snapshot.next_tick,
                event_schema_version=manifest.event_schema_version,
                projector_version=manifest.projector_version,
                persistence_codec_version=manifest.persistence_codec_version,
            )

        try:
            verify_commit_chain(commits)
        except PersistenceSerializationError as exc:
            _LOGGER.error(
                "%s code=%s run_id=%s",
                EngineDiagnosticCode.CHECKPOINT_CORRUPT.value,
                exc.code,
                run_id.value,
            )
            return self._failed(
                run_id,
                ReplayStatus.STREAM_DISCONTINUITY,
                target_tick,
                snapshot_id=snapshot.snapshot_id,
                snapshot_next_tick=snapshot.next_tick,
                event_schema_version=manifest.event_schema_version,
                projector_version=manifest.projector_version,
                persistence_codec_version=manifest.persistence_codec_version,
            )

        if commits:
            first = commits[0]
            if first.tick != snapshot.next_tick:
                return self._failed(
                    run_id,
                    ReplayStatus.STREAM_DISCONTINUITY,
                    target_tick,
                    snapshot_id=snapshot.snapshot_id,
                    snapshot_next_tick=snapshot.next_tick,
                    event_schema_version=manifest.event_schema_version,
                    projector_version=manifest.projector_version,
                    persistence_codec_version=manifest.persistence_codec_version,
                )
            if first.predecessor_commit_hash != snapshot.predecessor_commit_hash:
                _LOGGER.error(
                    "%s code=predecessor_mismatch run_id=%s",
                    EngineDiagnosticCode.CHECKPOINT_CORRUPT.value,
                    run_id.value,
                )
                return self._failed(
                    run_id,
                    ReplayStatus.STREAM_DISCONTINUITY,
                    target_tick,
                    snapshot_id=snapshot.snapshot_id,
                    snapshot_next_tick=snapshot.next_tick,
                    event_schema_version=manifest.event_schema_version,
                    projector_version=manifest.projector_version,
                    persistence_codec_version=manifest.persistence_codec_version,
                )

        events: tuple[WorldEvent, ...] = ()
        if to_commit_tick is not None:
            events = await self._journal.list_events(
                run_id,
                from_tick=snapshot.next_tick,
                to_tick=to_commit_tick,
                limit=10_000_000,
                offset=0,
            )
            if not _events_match_commits(events, commits):
                _LOGGER.error(
                    "%s code=event_commit_mismatch run_id=%s",
                    EngineDiagnosticCode.CHECKPOINT_CORRUPT.value,
                    run_id.value,
                )
                return self._failed(
                    run_id,
                    ReplayStatus.STREAM_DISCONTINUITY,
                    target_tick,
                    snapshot_id=snapshot.snapshot_id,
                    snapshot_next_tick=snapshot.next_tick,
                    event_schema_version=manifest.event_schema_version,
                    projector_version=manifest.projector_version,
                    persistence_codec_version=manifest.persistence_codec_version,
                )

        committed_through = to_commit_tick
        try:
            engine = WorldEngine.restore_from_snapshot(
                snapshot,
                events=events,
                committed_through_tick=committed_through,
            )
        except Exception as exc:
            _LOGGER.error(
                "%s code=restore_failed error=%s run_id=%s",
                EngineDiagnosticCode.PROJECTION_FAILED.value,
                type(exc).__name__,
                run_id.value,
            )
            return self._failed(
                run_id,
                ReplayStatus.STREAM_DISCONTINUITY,
                target_tick,
                snapshot_id=snapshot.snapshot_id,
                snapshot_next_tick=snapshot.next_tick,
                event_schema_version=manifest.event_schema_version,
                projector_version=manifest.projector_version,
                persistence_codec_version=manifest.persistence_codec_version,
            )

        mode = (
            ReplayMode.CONTINUATION if target_tick == head_next else ReplayMode.READONLY
        )
        predecessor = (
            commits[-1].commit_hash if commits else snapshot.predecessor_commit_hash
        )
        result = ReplayResult(
            run_id=run_id,
            status=ReplayStatus.OK,
            mode=mode,
            snapshot_id=snapshot.snapshot_id,
            snapshot_next_tick=snapshot.next_tick,
            target_tick=target_tick,
            events_applied=len(events),
            event_schema_version=manifest.event_schema_version,
            projector_version=manifest.projector_version,
            persistence_codec_version=manifest.persistence_codec_version,
        )
        _LOGGER.info(
            "%s run_id=%s target_tick=%s mode=%s events_applied=%s",
            EngineDiagnosticCode.CHECKPOINT_RESTORE.value,
            run_id.value,
            target_tick.value,
            mode.value,
            len(events),
        )
        return ReplayOutcome(
            result=result,
            engine=engine,
            predecessor_commit_hash=predecessor,
        )

    def open_durable(
        self,
        outcome: ReplayOutcome,
        journal: TickJournalRepository,
    ) -> PersistentSimulationService:
        """Bind a continuation-ready engine to durable tick coordination."""
        if type(outcome) is not ReplayOutcome:
            raise TypeError("open_durable requires ReplayOutcome")
        if outcome.result.status is not ReplayStatus.OK:
            raise RuntimeError("open_durable requires a successful replay")
        if outcome.result.mode is not ReplayMode.CONTINUATION:
            raise RuntimeError("open_durable rejects read-only historical replay")
        if outcome.engine is None:
            raise RuntimeError("open_durable requires a restored engine")
        return PersistentSimulationService(
            outcome.engine,
            journal,
            predecessor_commit_hash=outcome.predecessor_commit_hash,
        )

    async def read_event_page(
        self,
        run_id: RunId,
        *,
        from_tick: Tick,
        to_tick: Tick | None = None,
        limit: int = _DEFAULT_PAGE_SIZE,
        offset: int = 0,
    ) -> ReplayEventPage:
        """Return a detached page of objective events (no live engine)."""
        if type(run_id) is not RunId:
            raise TypeError("run_id must be RunId")
        if type(from_tick) is not Tick:
            raise TypeError("from_tick must be Tick")
        if to_tick is not None and type(to_tick) is not Tick:
            raise TypeError("to_tick must be Tick or None")
        limit = _clamp_page_limit(limit)
        if isinstance(offset, bool) or type(offset) is not int or offset < 0:
            raise ValueError("offset must be a non-negative int")
        events = await self._journal.list_events(
            run_id,
            from_tick=from_tick,
            to_tick=to_tick,
            limit=limit,
            offset=offset,
        )
        next_offset = offset + len(events) if len(events) == limit else None
        _LOGGER.debug(
            "replay_event_page run_id=%s from_tick=%s to_tick=%s "
            "limit=%s offset=%s event_count=%s next_offset=%s",
            run_id.value,
            from_tick.value,
            None if to_tick is None else to_tick.value,
            limit,
            offset,
            len(events),
            next_offset if next_offset is not None else "-",
        )
        return ReplayEventPage(
            run_id=run_id,
            from_tick=from_tick,
            to_tick=to_tick,
            limit=limit,
            offset=offset,
            events=events,
            next_offset=next_offset,
        )

    async def read_event_keyset_page(
        self,
        run_id: RunId,
        *,
        after_tick: int = 0,
        after_sequence: int = -1,
        to_tick: Tick | None = None,
        limit: int = _DEFAULT_PAGE_SIZE,
    ) -> ReplayEventPage:
        """Detached keyset page of events ordered by ``(tick, sequence)``.

        Pass ``after_sequence=-1`` with ``after_tick=0`` to start from the head.
        Chunked reads request ``limit + 1`` rows to compute the next cursor.
        """
        if type(run_id) is not RunId:
            raise TypeError("run_id must be RunId")
        if to_tick is not None and type(to_tick) is not Tick:
            raise TypeError("to_tick must be Tick or None")
        limit = _clamp_page_limit(limit)
        if (
            isinstance(after_tick, bool)
            or type(after_tick) is not int
            or after_tick < 0
        ):
            raise ValueError("after_tick must be a non-negative int")
        if isinstance(after_sequence, bool) or type(after_sequence) is not int:
            raise ValueError("after_sequence must be an int")
        if after_sequence < -1:
            raise ValueError("after_sequence must be >= -1")
        list_events_keyset = getattr(self._journal, "list_events_keyset", None)
        if list_events_keyset is None:
            # Fallback: offset scan from from_tick (tests/fakes without keyset).
            raw = await self._journal.list_events(
                run_id,
                from_tick=Tick(after_tick),
                to_tick=to_tick,
                limit=limit + 1 + max(0, after_sequence + 1),
                offset=0,
            )
            filtered = tuple(
                event
                for event in raw
                if (event.tick, event.sequence) > (after_tick, after_sequence)
            )[: limit + 1]
        else:
            filtered = await list_events_keyset(
                run_id,
                after_tick=after_tick,
                after_sequence=after_sequence,
                to_tick=to_tick,
                limit=limit + 1,
            )
        page = filtered[:limit]
        next_offset = None
        if len(filtered) > limit:
            next_offset = 0  # signal more pages; callers should use keyset cursor
        _LOGGER.debug(
            "replay_event_keyset_page run_id=%s after_tick=%s after_sequence=%s "
            "to_tick=%s limit=%s event_count=%s has_more=%s",
            run_id.value,
            after_tick,
            after_sequence,
            None if to_tick is None else to_tick.value,
            limit,
            len(page),
            len(filtered) > limit,
        )
        return ReplayEventPage(
            run_id=run_id,
            from_tick=Tick(after_tick),
            to_tick=to_tick,
            limit=limit,
            offset=0,
            events=page,
            next_offset=next_offset,
        )

    async def inspect_at_tick(
        self,
        request: ReplayRequest,
        *,
        agent_id: object | None = None,
    ) -> object:
        """Replay then project public inspection DTOs (never returns an engine)."""
        from agents.models import AgentId as AgentIdType
        from simulation.inspection import project_replay_for_inspection

        outcome = await self.replay(request)
        resolved_agent: AgentIdType | None = None
        if agent_id is not None:
            if type(agent_id) is not AgentIdType:
                raise TypeError("agent_id must be AgentId or None")
            resolved_agent = agent_id
        return project_replay_for_inspection(outcome, agent_id=resolved_agent)

    async def read_commit_page(
        self,
        run_id: RunId,
        *,
        from_tick: Tick,
        to_tick: Tick | None = None,
        limit: int = _DEFAULT_PAGE_SIZE,
    ) -> ReplayCommitPage:
        """Return a detached keyset page of tick commits (no live engine)."""
        if type(run_id) is not RunId:
            raise TypeError("run_id must be RunId")
        if type(from_tick) is not Tick:
            raise TypeError("from_tick must be Tick")
        if to_tick is not None and type(to_tick) is not Tick:
            raise TypeError("to_tick must be Tick or None")
        limit = _clamp_page_limit(limit)
        commits = await self._journal.list_tick_commits(
            run_id, from_tick=from_tick, to_tick=to_tick
        )
        page = commits[:limit]
        next_from_tick: Tick | None = None
        if len(commits) > limit:
            next_from_tick = Tick(page[-1].tick.value + 1)
        _LOGGER.debug(
            "replay_commit_page run_id=%s from_tick=%s to_tick=%s "
            "limit=%s commit_count=%s next_from_tick=%s",
            run_id.value,
            from_tick.value,
            None if to_tick is None else to_tick.value,
            limit,
            len(page),
            None if next_from_tick is None else next_from_tick.value,
        )
        return ReplayCommitPage(
            run_id=run_id,
            from_tick=from_tick,
            to_tick=to_tick,
            commits=page,
            next_from_tick=next_from_tick,
        )

    async def _durable_head_next_tick(self, run_id: RunId) -> Tick:
        commits = await self._journal.list_tick_commits(
            run_id, from_tick=Tick(0), to_tick=None
        )
        if not commits:
            return Tick(0)
        return Tick(commits[-1].tick.value + 1)

    def _failed(
        self,
        run_id: RunId,
        status: ReplayStatus,
        target_tick: Tick | None,
        *,
        snapshot_id: SnapshotId | None = None,
        snapshot_next_tick: Tick | None = None,
        event_schema_version: int = EVENT_SCHEMA_VERSION,
        projector_version: str = PROJECTOR_VERSION,
        persistence_codec_version: str = PERSISTENCE_CODEC_VERSION,
    ) -> ReplayOutcome:
        return ReplayOutcome(
            result=ReplayResult(
                run_id=run_id,
                status=status,
                mode=ReplayMode.READONLY,
                snapshot_id=snapshot_id,
                snapshot_next_tick=snapshot_next_tick,
                target_tick=target_tick,
                events_applied=0,
                event_schema_version=event_schema_version,
                projector_version=projector_version,
                persistence_codec_version=persistence_codec_version,
            ),
            engine=None,
            predecessor_commit_hash=None,
        )


def _versions_compatible(
    *,
    event_schema_version: int,
    projector_version: str,
    persistence_codec_version: str,
    derivation_version: str,
) -> bool:
    if event_schema_version not in ACCEPTED_EVENT_SCHEMA_VERSIONS:
        return False
    if projector_version not in ACCEPTED_PROJECTOR_VERSIONS:
        return False
    if persistence_codec_version not in ACCEPTED_PERSISTENCE_CODEC_VERSIONS:
        return False
    if derivation_version not in {DERIVATION_VERSION, "v1", "v2", "v3"}:
        return False
    return schema_projector_compatible(
        event_schema_version=event_schema_version,
        projector_version=projector_version,
    )


def _snapshot_matches_manifest(snapshot: WorldSnapshot, manifest: RunManifest) -> bool:
    return (
        snapshot.event_schema_version == manifest.event_schema_version
        and snapshot.projector_version == manifest.projector_version
        and snapshot.persistence_codec_version == manifest.persistence_codec_version
        and snapshot.derivation_version == manifest.derivation_version
        and snapshot.run_id == manifest.run_id
        and snapshot.world_id == manifest.world_id
        and snapshot.seed == manifest.seed
        and snapshot.config == manifest.config
    )


def _commits_cover_range(
    commits: tuple[TickCommit, ...],
    from_tick: Tick,
    to_tick: Tick | None,
) -> bool:
    if to_tick is None:
        return len(commits) == 0
    expected = to_tick.value - from_tick.value + 1
    if expected < 0:
        return False
    if len(commits) != expected:
        return False
    for index, commit in enumerate(commits):
        if commit.tick.value != from_tick.value + index:
            return False
    return True


def _events_match_commits(
    events: tuple[WorldEvent, ...], commits: tuple[TickCommit, ...]
) -> bool:
    by_tick: dict[int, int] = {}
    for event in events:
        by_tick[event.tick] = by_tick.get(event.tick, 0) + 1
    for commit in commits:
        count = by_tick.get(commit.tick.value, 0)
        if count != commit.event_count:
            return False
        by_tick.pop(commit.tick.value, None)
    return not by_tick
