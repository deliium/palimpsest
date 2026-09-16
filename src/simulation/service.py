"""Durable prepare → persist → finalize coordination for WorldEngine.

``PersistentSimulationService`` prepares a detached candidate, awaits one
repository append, then publishes only after a successful commit. Adapter
failure leaves the live engine unchanged. Ambiguous commit outcomes fence the
instance instead of blind retry. Prepared candidates are not part of the
public facade.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Final

from simulation.clock import Tick
from simulation.engine import WorldEngine, _PreparedTickCandidate
from simulation.identifiers import derive_scoped_id
from simulation.journal import (
    bind_snapshot_commit_hash,
    compute_commit_hash,
    hash_tick_events,
    hash_tick_payload,
)
from simulation.lifecycle import (
    ActionSubmission,
    EngineDiagnosticCode,
    require_action_submission,
)
from simulation.persistence import (
    CommitHash,
    TickAppendRequest,
    TickCommit,
    TickJournalRepository,
    WorldSnapshot,
)
from simulation.randomness import StreamScope
from world.identifiers import require_stable_id

_LOGGER = logging.getLogger("simulation.service")

__all__ = [
    "DurableCommitAmbiguity",
    "PersistentSimulationService",
]


class DurableCommitAmbiguity(RuntimeError):
    """Commit outcome is unknown; the durable service must fence and reload."""


class PersistentSimulationService:
    """Application service that persists each tick before publishing in-memory."""

    __slots__ = (
        "_engine",
        "_fenced",
        "_journal",
        "_predecessor_commit_hash",
    )

    def __init__(
        self,
        engine: WorldEngine,
        journal: TickJournalRepository,
        *,
        predecessor_commit_hash: CommitHash | None = None,
    ) -> None:
        if type(engine) is not WorldEngine:
            raise TypeError("PersistentSimulationService requires WorldEngine")
        self._engine = engine
        self._journal = journal
        if predecessor_commit_hash is not None and type(
            predecessor_commit_hash
        ) is not CommitHash:
            raise TypeError("predecessor_commit_hash must be CommitHash or None")
        self._predecessor_commit_hash = predecessor_commit_hash
        self._fenced = False

    @property
    def engine(self) -> WorldEngine:
        return self._engine

    @property
    def fenced(self) -> bool:
        return self._fenced

    @property
    def predecessor_commit_hash(self) -> CommitHash | None:
        return self._predecessor_commit_hash

    async def resolve_tick(
        self,
        submissions: Sequence[ActionSubmission],
        *,
        idempotency_key: str | None = None,
        snapshot: WorldSnapshot | None = None,
    ) -> TickCommit:
        """Prepare, persist, then finalize one tick.

        Empty and event-only ticks are persisted. Repository failure before
        finalize leaves the engine snapshot unchanged.
        """
        if self._fenced:
            _LOGGER.warning(
                "%s reason=already_fenced run_id=%s tick=%s",
                EngineDiagnosticCode.DURABLE_FENCED.value,
                self._engine.run_id.value,
                self._engine.tick.value,
            )
            raise RuntimeError("PersistentSimulationService is fenced")
        if isinstance(submissions, (set, frozenset)) or not isinstance(
            submissions, Sequence
        ):
            raise TypeError("submissions must be an ordered sequence")

        typed = tuple(require_action_submission(item) for item in submissions)
        live_before = self._engine._snapshot
        candidate = self._engine._prepare_tick_candidate(typed)
        if self._engine._snapshot is not live_before:
            self._engine._snapshot = live_before
            _LOGGER.error(
                "%s code=prepare_mutated_live run_id=%s tick=%s",
                EngineDiagnosticCode.DURABLE_FAILED.value,
                self._engine.run_id.value,
                candidate.tick.value,
            )
            raise RuntimeError("prepare must not mutate the live engine")

        key = self._resolve_idempotency_key(candidate.tick, idempotency_key)
        event_hashes = hash_tick_events(candidate.events)
        tick_payload = hash_tick_payload(candidate.events)
        expected_commit = compute_commit_hash(
            predecessor_commit_hash=self._predecessor_commit_hash,
            run_id=self._engine.run_id,
            tick=candidate.tick,
            base_revision=candidate.base_revision,
            resulting_revision=candidate.resulting_revision,
            event_hashes=event_hashes,
            payload_hash=tick_payload,
        )
        bound_snapshot: WorldSnapshot | None = None
        if snapshot is not None:
            if type(snapshot) is not WorldSnapshot:
                raise TypeError("snapshot must be WorldSnapshot or None")
            bound_snapshot = bind_snapshot_commit_hash(snapshot, expected_commit)
        request = TickAppendRequest(
            run_id=self._engine.run_id,
            tick=candidate.tick,
            expected_base_revision=candidate.base_revision,
            expected_predecessor_commit_hash=self._predecessor_commit_hash,
            idempotency_key=key,
            events=candidate.events,
            snapshot=bound_snapshot,
        )
        _LOGGER.debug(
            "%s run_id=%s tick=%s events=%s hash_prefix=%s",
            EngineDiagnosticCode.DURABLE_APPEND.value,
            self._engine.run_id.value,
            candidate.tick.value,
            len(candidate.events),
            expected_commit.value[:8],
        )
        existing: TickCommit | None = None
        try:
            existing = await self._journal.get_tick_commit(
                self._engine.run_id, candidate.tick
            )
            commit = await self._journal.append_tick(request)
        except DurableCommitAmbiguity:
            self._fence(candidate.tick, reason="ambiguous_commit")
            raise
        except Exception:
            _LOGGER.error(
                "%s code=append_failed run_id=%s tick=%s",
                EngineDiagnosticCode.DURABLE_FAILED.value,
                self._engine.run_id.value,
                candidate.tick.value,
            )
            if self._engine._snapshot is not live_before:
                self._engine._snapshot = live_before
            raise

        if type(commit) is not TickCommit:
            self._fence(candidate.tick, reason="invalid_commit_type")
            raise TypeError("append_tick must return TickCommit")
        if (
            commit.run_id != self._engine.run_id
            or commit.tick != candidate.tick
            or commit.resulting_tick != candidate.result.resulting_tick
            or commit.base_revision != candidate.base_revision
            or commit.resulting_revision != candidate.resulting_revision
            or commit.event_count != len(candidate.events)
            or commit.payload_hash != tick_payload
            or commit.commit_hash != expected_commit
            or commit.predecessor_commit_hash != self._predecessor_commit_hash
        ):
            self._fence(candidate.tick, reason="divergent_commit")
            raise ValueError("durable commit content conflict")
        if existing is not None and existing.commit_hash == commit.commit_hash:
            _LOGGER.warning(
                "%s run_id=%s tick=%s hash_prefix=%s",
                EngineDiagnosticCode.DURABLE_IDEMPOTENT.value,
                self._engine.run_id.value,
                candidate.tick.value,
                commit.commit_hash.value[:8],
            )

        if self._engine._snapshot is not live_before:
            self._engine._snapshot = live_before
            self._fence(candidate.tick, reason="live_mutated_before_finalize")
            raise RuntimeError("live engine mutated before finalize")

        self._engine._finalize_tick_candidate(candidate)
        self._predecessor_commit_hash = commit.commit_hash
        _LOGGER.info(
            "%s run_id=%s tick=%s resulting_tick=%s events=%s "
            "base_revision=%s resulting_revision=%s hash_prefix=%s",
            EngineDiagnosticCode.DURABLE_COMMITTED.value,
            commit.run_id.value,
            commit.tick.value,
            commit.resulting_tick.value,
            commit.event_count,
            commit.base_revision.value,
            commit.resulting_revision.value,
            commit.commit_hash.value[:8],
        )
        return commit

    def _resolve_idempotency_key(self, tick: Tick, provided: str | None) -> str:
        if provided is not None:
            return require_stable_id("idempotency_key", provided)
        return derive_scoped_id(
            self._engine._config,
            StreamScope(
                namespace="tick-idempotency",
                names=(
                    self._engine.run_id.value,
                    self._engine.world_id.value,
                    f"tick:{tick.value}",
                ),
            ),
        )

    def _fence(self, tick: Tick, *, reason: str) -> None:
        self._fenced = True
        _LOGGER.warning(
            "%s reason=%s run_id=%s tick=%s",
            EngineDiagnosticCode.DURABLE_FENCED.value,
            reason,
            self._engine.run_id.value,
            tick.value,
        )


# Keep private candidate type referenced so accidental public re-export is obvious.
_PRIVATE_CANDIDATE_TYPE: Final[type] = _PreparedTickCandidate
