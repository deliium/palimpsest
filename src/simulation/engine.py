"""Authoritative deterministic WorldEngine tick state machine.

``WorldEngine`` is the sole public component that advances objective world
state. Private world modules prepare candidates; this engine validates and
commits with one reference swap.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from agents.models import AgentId
from simulation.actions import (
    admit_agent_command,
    canonical_admission_keys,
    derive_engine_event_id,
    run_id_for_event,
    tick_for_event,
)
from simulation.bootstrap import (
    WorldBootstrap,
    _bootstrap_from_snapshot,
    _materialize_projected_world,
    _materialize_world,
    registration_translator,
)
from simulation.clock import Tick
from simulation.contracts import make_export
from simulation.identifiers import derive_run_id, derive_scoped_id
from simulation.journal import hash_snapshot
from simulation.lifecycle import (
    ActionResolution,
    ActionResolutionReason,
    ActionResolutionStatus,
    ActionSubmission,
    EngineDiagnosticCode,
    ObservationBatch,
    TickEventRecord,
    TickResult,
    TickToken,
    require_action_submission,
)
from simulation.models import RunId, SimulationExport, SimulationRunConfig
from simulation.persistence import WorldSnapshot
from simulation.randomness import StreamScope
from world._operations import (
    BatchItemStatus,
    prepare_action_batch,
)
from world._perception import project_observations
from world._replay import ProjectionError, project_events
from world._state import World
from world.actions import ActionRequest
from world.events import WorldEvent, normalize_events
from world.identifiers import EventId, RequestId, WorldId, WorldRevision

_LOGGER = logging.getLogger("simulation.engine")

__all__ = ["EnginePhase", "WorldEngine"]


class EnginePhase(StrEnum):
    AWAITING_OBSERVATION = "awaiting_observation"
    AWAITING_SUBMISSIONS = "awaiting_submissions"


@dataclass(frozen=True, slots=True)
class _EngineSnapshot:
    world: World
    tick: Tick
    phase: EnginePhase
    token: TickToken | None
    observation_batch: ObservationBatch | None
    resolution_history: tuple[ActionResolution, ...]
    event_history: tuple[WorldEvent, ...]


class WorldEngine:
    """Public authority for observation and ordered tick resolution."""

    __slots__ = (
        "_bootstrap",
        "_config",
        "_engine_id",
        "_registrations",
        "_run_id",
        "_snapshot",
        "_translator",
    )

    def __init__(
        self,
        *,
        config: SimulationRunConfig,
        bootstrap: WorldBootstrap,
        run_id: RunId | None = None,
        start_tick: Tick | None = None,
    ) -> None:
        if type(config) is not SimulationRunConfig:
            raise TypeError("WorldEngine requires SimulationRunConfig")
        if type(bootstrap) is not WorldBootstrap:
            raise TypeError("WorldEngine requires WorldBootstrap")
        self._config = config
        self._bootstrap = bootstrap
        self._run_id = run_id if run_id is not None else derive_run_id(config)
        if type(self._run_id) is not RunId:
            raise TypeError("run_id must be RunId")
        tick = start_tick if start_tick is not None else Tick(0)
        if type(tick) is not Tick:
            raise TypeError("start_tick must be Tick")
        self._translator = registration_translator(bootstrap)
        self._registrations = bootstrap.registrations
        world = _materialize_world(bootstrap)
        self._engine_id = derive_scoped_id(
            config,
            StreamScope(
                namespace="engine",
                names=(self._run_id.value, bootstrap.world_id.value),
            ),
        )
        self._snapshot = _EngineSnapshot(
            world=world,
            tick=tick,
            phase=EnginePhase.AWAITING_OBSERVATION,
            token=None,
            observation_batch=None,
            resolution_history=(),
            event_history=(),
        )
        _LOGGER.debug(
            "%s world_id=%s revision=%s tick=%s registrations=%s",
            EngineDiagnosticCode.BOOTSTRAP_VALIDATED.value,
            bootstrap.world_id.value,
            bootstrap.revision.value,
            tick.value,
            len(self._registrations),
        )

    @classmethod
    def restore_from_snapshot(
        cls,
        snapshot: WorldSnapshot,
        *,
        events: Sequence[WorldEvent] = (),
    ) -> WorldEngine:
        """Restore an engine at ``AWAITING_OBSERVATION`` from a checkpoint.

        Validates snapshot integrity, folds subsequent ordered events with the
        private projector, and never restores observation tokens. Does not
        expose a public state-replacement hook on ``World``.
        """
        if type(snapshot) is not WorldSnapshot:
            raise TypeError("restore_from_snapshot requires WorldSnapshot")
        if isinstance(events, (set, frozenset)) or not isinstance(events, Sequence):
            raise TypeError("events must be an ordered sequence")

        _LOGGER.debug(
            "%s run_id=%s snapshot_id=%s next_tick=%s revision=%s "
            "event_schema_version=%s projector_version=%s event_count=%s",
            EngineDiagnosticCode.CHECKPOINT_RESTORE.value,
            snapshot.run_id.value,
            snapshot.snapshot_id.value,
            snapshot.next_tick.value,
            snapshot.revision.value,
            snapshot.event_schema_version,
            snapshot.projector_version,
            len(events) if not isinstance(events, (str, bytes)) else 0,
        )

        computed = hash_snapshot(snapshot)
        if computed != snapshot.integrity_hash:
            _LOGGER.error(
                "%s code=integrity_hash_mismatch run_id=%s snapshot_id=%s "
                "hash_prefix=%s",
                EngineDiagnosticCode.CHECKPOINT_CORRUPT.value,
                snapshot.run_id.value,
                snapshot.snapshot_id.value,
                snapshot.integrity_hash.value[:8],
            )
            raise ValueError("integrity_hash_mismatch")

        bootstrap = _bootstrap_from_snapshot(snapshot)
        from world._state import WorldState

        base_state = WorldState(
            snapshot.revision,
            locations=snapshot.locations,
            items=snapshot.items,
            resources=snapshot.resources,
            bodies=snapshot.bodies,
            weather=snapshot.weather,
        )
        try:
            normalized_events = normalize_events(events)
            projected = project_events(
                base_state,
                normalized_events,
                expected_run_id=snapshot.run_id.value,
                expected_world_id=snapshot.world_id,
            )
        except ProjectionError as exc:
            _LOGGER.error(
                "%s code=%s run_id=%s snapshot_id=%s",
                EngineDiagnosticCode.PROJECTION_FAILED.value,
                exc.code,
                snapshot.run_id.value,
                snapshot.snapshot_id.value,
            )
            raise
        except (TypeError, ValueError):
            _LOGGER.error(
                "%s code=invalid_events run_id=%s snapshot_id=%s",
                EngineDiagnosticCode.PROJECTION_FAILED.value,
                snapshot.run_id.value,
                snapshot.snapshot_id.value,
            )
            raise

        if normalized_events:
            last_tick = normalized_events[-1].tick
            restored_tick = Tick(last_tick + 1)
        else:
            restored_tick = snapshot.next_tick

        engine = cls.__new__(cls)
        engine._config = snapshot.config
        engine._bootstrap = bootstrap
        engine._run_id = snapshot.run_id
        engine._translator = registration_translator(bootstrap)
        engine._registrations = bootstrap.registrations
        engine._engine_id = derive_scoped_id(
            snapshot.config,
            StreamScope(
                namespace="engine",
                names=(snapshot.run_id.value, snapshot.world_id.value),
            ),
        )
        world = _materialize_projected_world(
            world_id=snapshot.world_id, state=projected
        )
        engine._snapshot = _EngineSnapshot(
            world=world,
            tick=restored_tick,
            phase=EnginePhase.AWAITING_OBSERVATION,
            token=None,
            observation_batch=None,
            resolution_history=(),
            event_history=normalized_events,
        )
        _LOGGER.info(
            "%s run_id=%s snapshot_id=%s next_tick=%s revision=%s "
            "events_applied=%s registrations=%s",
            EngineDiagnosticCode.CHECKPOINT_RESTORE.value,
            snapshot.run_id.value,
            snapshot.snapshot_id.value,
            restored_tick.value,
            projected.revision.value,
            len(normalized_events),
            len(engine._registrations),
        )
        return engine

    @property
    def world_id(self) -> WorldId:
        return self._bootstrap.world_id

    @property
    def tick(self) -> Tick:
        return self._snapshot.tick

    @property
    def revision(self) -> WorldRevision:
        return self._snapshot.world.state.revision

    @property
    def phase(self) -> EnginePhase:
        return self._snapshot.phase

    @property
    def run_id(self) -> RunId:
        return self._run_id

    def observe(self) -> ObservationBatch:
        """Issue or replay the immutable observation batch for the open tick."""
        snap = self._snapshot
        if (
            snap.phase is EnginePhase.AWAITING_SUBMISSIONS
            and snap.observation_batch is not None
        ):
            _LOGGER.debug(
                "%s tick=%s observers=%s revision=%s replay=1",
                EngineDiagnosticCode.OBSERVATIONS_ISSUED.value,
                snap.tick.value,
                len(snap.observation_batch.observations),
                snap.world.state.revision.value,
            )
            return snap.observation_batch
        if snap.phase is not EnginePhase.AWAITING_OBSERVATION:
            _LOGGER.warning(
                "%s reason=observe_wrong_phase phase=%s tick=%s",
                EngineDiagnosticCode.LIFECYCLE_MISUSE.value,
                snap.phase.value,
                snap.tick.value,
            )
            raise RuntimeError("observations unavailable in current engine phase")
        observer_ids = tuple(
            registration.entity_id for registration in self._registrations
        )
        observations = project_observations(
            world_id=self.world_id,
            state=snap.world.state,
            observer_ids=observer_ids,
        )
        token = TickToken(
            value=derive_scoped_id(
                self._config,
                StreamScope(
                    namespace="tick-token",
                    names=(
                        self._engine_id,
                        self._run_id.value,
                        self.world_id.value,
                        f"tick:{snap.tick.value}",
                    ),
                ),
            ),
            tick=snap.tick,
        )
        batch = ObservationBatch(
            tick=snap.tick,
            revision=snap.world.state.revision,
            token=token,
            observations=observations,
        )
        self._snapshot = _EngineSnapshot(
            world=snap.world,
            tick=snap.tick,
            phase=EnginePhase.AWAITING_SUBMISSIONS,
            token=token,
            observation_batch=batch,
            resolution_history=snap.resolution_history,
            event_history=snap.event_history,
        )
        _LOGGER.debug(
            "%s tick=%s observers=%s revision=%s replay=0",
            EngineDiagnosticCode.OBSERVATIONS_ISSUED.value,
            snap.tick.value,
            len(observations),
            snap.world.state.revision.value,
        )
        return batch

    def resolve_tick(
        self, submissions: Sequence[ActionSubmission]
    ) -> TickResult:
        """Admit ordered submissions, prepare a candidate, and commit atomically."""
        snap = self._snapshot
        if snap.phase is not EnginePhase.AWAITING_SUBMISSIONS or snap.token is None:
            _LOGGER.warning(
                "%s reason=resolve_wrong_phase phase=%s tick=%s",
                EngineDiagnosticCode.LIFECYCLE_MISUSE.value,
                snap.phase.value,
                snap.tick.value,
            )
            raise RuntimeError("resolve_tick requires an open observation token")
        if isinstance(submissions, (set, frozenset)) or not isinstance(
            submissions, Sequence
        ):
            raise TypeError("submissions must be an ordered sequence")
        prior = snap
        try:
            typed = tuple(
                require_action_submission(item) for item in submissions
            )
            for submission in typed:
                self._validate_token(submission.token, snap.token)
            resolutions, events, candidate_world = self._resolve_ordered(
                snap=snap, submissions=typed
            )
            result = TickResult(
                tick=snap.tick,
                resulting_tick=Tick(snap.tick.value + 1),
                base_revision=snap.world.state.revision,
                resulting_revision=candidate_world.state.revision,
                resolutions=resolutions,
                events=tuple(
                    TickEventRecord(sequence=index, event=event)
                    for index, event in enumerate(events)
                ),
            )
            next_snapshot = _EngineSnapshot(
                world=candidate_world,
                tick=Tick(snap.tick.value + 1),
                phase=EnginePhase.AWAITING_OBSERVATION,
                token=None,
                observation_batch=None,
                resolution_history=(*snap.resolution_history, *resolutions),
                event_history=(*snap.event_history, *events),
            )
            self._snapshot = next_snapshot
        except Exception:
            self._snapshot = prior
            _LOGGER.error(
                "%s tick=%s",
                EngineDiagnosticCode.CANDIDATE_ABORTED.value,
                prior.tick.value,
            )
            raise
        _LOGGER.info(
            "%s tick=%s resulting_tick=%s base_revision=%s resulting_revision=%s "
            "resolutions=%s events=%s",
            EngineDiagnosticCode.TICK_COMMITTED.value,
            result.tick.value,
            result.resulting_tick.value,
            result.base_revision.value,
            result.resulting_revision.value,
            len(result.resolutions),
            len(result.events),
        )
        return result

    def export_events(self) -> SimulationExport:
        return make_export(self._config, self._run_id, self._snapshot.event_history)

    def _validate_token(self, submitted: TickToken, expected: TickToken) -> None:
        if type(submitted) is not TickToken:
            raise TypeError("submission token must be TickToken")
        if submitted.tick != expected.tick:
            _LOGGER.warning(
                "%s tick=%s",
                EngineDiagnosticCode.TOKEN_STALE.value,
                expected.tick.value,
            )
            raise ValueError("stale tick token")
        if submitted.value != expected.value:
            _LOGGER.warning(
                "%s tick=%s",
                EngineDiagnosticCode.TOKEN_REPLAY.value,
                expected.tick.value,
            )
            raise ValueError("tick token mismatch")
        # Cross-engine rejection: token value embeds engine id derivation inputs.
        if not submitted.value:
            _LOGGER.warning(
                "%s tick=%s",
                EngineDiagnosticCode.TOKEN_CROSS_ENGINE.value,
                expected.tick.value,
            )
            raise ValueError("cross-engine tick token")

    def _resolve_ordered(
        self,
        *,
        snap: _EngineSnapshot,
        submissions: tuple[ActionSubmission, ...],
    ) -> tuple[tuple[ActionResolution, ...], tuple[WorldEvent, ...], World]:
        seen_agents: dict[AgentId, int] = {}
        admitted: list[ActionRequest | None] = []
        event_ids: list[EventId] = []
        early_resolutions: dict[int, ActionResolution] = {}
        base_revision = snap.world.state.revision

        for ordinal, submission in enumerate(submissions):
            agent_id = submission.agent_id
            if agent_id not in {
                registration.agent_id for registration in self._registrations
            }:
                raise ValueError(f"unregistered agent_id {agent_id.value!r}")
            if agent_id in seen_agents:
                keys = canonical_admission_keys(
                    run_id=self._run_id,
                    world_id=self.world_id,
                    tick=snap.tick,
                    ordinal=ordinal,
                    agent_id=agent_id,
                )
                _proposal, request = admit_agent_command(
                    config=self._config,
                    agent_id=agent_id,
                    command=submission.command,
                    translator=self._translator,
                    world_id=self.world_id,
                    revision=base_revision,
                    keys=keys,
                )
                early_resolutions[ordinal] = ActionResolution(
                    ordinal=ordinal,
                    agent_id=agent_id,
                    command=submission.command,
                    status=ActionResolutionStatus.DUPLICATE,
                    reason=ActionResolutionReason.DUPLICATE_SUBMISSION,
                    tick=snap.tick,
                    base_revision=base_revision,
                    resulting_revision=base_revision,
                    request_id=request.request_id,
                )
                admitted.append(None)
                event_ids.append(
                    derive_engine_event_id(
                        self._config,
                        run_id=self._run_id,
                        world_id=self.world_id,
                        tick=snap.tick,
                        ordinal=ordinal,
                        agent_id=agent_id,
                        sequence=0,
                    )
                )
                _LOGGER.debug(
                    "%s tick=%s ordinal=%s agent=%s",
                    EngineDiagnosticCode.RESOLUTION_DUPLICATE.value,
                    snap.tick.value,
                    ordinal,
                    agent_id.value,
                )
                continue
            seen_agents[agent_id] = ordinal
            keys = canonical_admission_keys(
                run_id=self._run_id,
                world_id=self.world_id,
                tick=snap.tick,
                ordinal=ordinal,
                agent_id=agent_id,
            )
            _proposal, request = admit_agent_command(
                config=self._config,
                agent_id=agent_id,
                command=submission.command,
                translator=self._translator,
                world_id=self.world_id,
                revision=base_revision,
                keys=keys,
            )
            admitted.append(request)
            event_ids.append(
                derive_engine_event_id(
                    self._config,
                    run_id=self._run_id,
                    world_id=self.world_id,
                    tick=snap.tick,
                    ordinal=ordinal,
                    agent_id=agent_id,
                    sequence=0,
                )
            )
            _LOGGER.debug(
                "%s tick=%s ordinal=%s kind=%s request_id=%s",
                EngineDiagnosticCode.SUBMISSION_ADMITTED.value,
                snap.tick.value,
                ordinal,
                getattr(submission.command, "kind", "?"),
                request.request_id.value,
            )

        batch_requests = tuple(
            request for request in admitted if request is not None
        )
        batch_event_ids = tuple(
            event_ids[index]
            for index, request in enumerate(admitted)
            if request is not None
        )
        prepared = prepare_action_batch(
            world_id=self.world_id,
            starting_state=snap.world.state,
            requests=batch_requests,
            event_ids=batch_event_ids,
            run_id=run_id_for_event(self._run_id),
            tick=tick_for_event(snap.tick),
        )

        # Map batch outcomes back onto full ordinal list.
        batch_by_request: dict[RequestId, object] = {
            outcome.request_id: outcome for outcome in prepared.outcomes
        }
        resulting_revision = prepared.candidate_state.revision
        resolutions: list[ActionResolution] = []
        for ordinal, submission in enumerate(submissions):
            if ordinal in early_resolutions:
                duplicate = early_resolutions[ordinal]
                resolutions.append(
                    ActionResolution(
                        ordinal=duplicate.ordinal,
                        agent_id=duplicate.agent_id,
                        command=duplicate.command,
                        status=duplicate.status,
                        reason=duplicate.reason,
                        tick=duplicate.tick,
                        base_revision=base_revision,
                        resulting_revision=resulting_revision,
                        request_id=duplicate.request_id,
                    )
                )
                continue
            maybe_request = admitted[ordinal]
            assert maybe_request is not None
            request = maybe_request
            batch_outcome = batch_by_request[request.request_id]
            status, reason = _map_batch_outcome(batch_outcome)
            resolutions.append(
                ActionResolution(
                    ordinal=ordinal,
                    agent_id=submission.agent_id,
                    command=submission.command,
                    status=status,
                    reason=reason,
                    tick=snap.tick,
                    base_revision=base_revision,
                    resulting_revision=resulting_revision,
                    request_id=request.request_id,
                )
            )
            _log_resolution(status, snap.tick.value, ordinal, request.request_id.value)

        candidate_world = World(self.world_id, prepared.candidate_state)
        return tuple(resolutions), prepared.events, candidate_world


def _map_batch_outcome(
    outcome: object,
) -> tuple[ActionResolutionStatus, ActionResolutionReason]:
    status = outcome.status  # type: ignore[attr-defined]
    reason_value = outcome.reason  # type: ignore[attr-defined]
    if status is BatchItemStatus.APPLIED:
        return ActionResolutionStatus.APPLIED, ActionResolutionReason.OCCURRENCE
    if status is BatchItemStatus.DEFERRED_POLICY:
        return (
            ActionResolutionStatus.DEFERRED_POLICY,
            ActionResolutionReason.DEFERRED_POLICY,
        )
    if status is BatchItemStatus.CONFLICTED:
        return (
            ActionResolutionStatus.CONFLICTED,
            ActionResolutionReason.CONFLICT_WITH_PRIOR,
        )
    if reason_value == "dead_actor":
        return ActionResolutionStatus.DEAD_ACTOR, ActionResolutionReason.DEAD_ACTOR
    # REJECTED
    reason_map: Final[dict[str, ActionResolutionReason]] = {
        "dead_actor": ActionResolutionReason.DEAD_ACTOR,
        "missing_actor_body": ActionResolutionReason.MISSING_ACTOR_BODY,
        "missing_target": ActionResolutionReason.INVALID_TARGET,
        "wrong_target_category": ActionResolutionReason.INVALID_TARGET,
        "not_held": ActionResolutionReason.STRUCTURAL_REJECTION,
        "not_at_location": ActionResolutionReason.STRUCTURAL_REJECTION,
        "not_colocated": ActionResolutionReason.STRUCTURAL_REJECTION,
        "dead_target": ActionResolutionReason.STRUCTURAL_REJECTION,
        "distinct_id_violation": ActionResolutionReason.STRUCTURAL_REJECTION,
        "malformed_envelope": ActionResolutionReason.MALFORMED_SUBMISSION,
        "wrong_trust_stage": ActionResolutionReason.MALFORMED_SUBMISSION,
        "wrong_world": ActionResolutionReason.STRUCTURAL_REJECTION,
        "stale_revision": ActionResolutionReason.STRUCTURAL_REJECTION,
        "invalid_actor_binding": ActionResolutionReason.STRUCTURAL_REJECTION,
    }
    return (
        ActionResolutionStatus.REJECTED,
        reason_map.get(reason_value, ActionResolutionReason.STRUCTURAL_REJECTION),
    )


def _log_resolution(
    status: ActionResolutionStatus, tick: int, ordinal: int, request_id: str
) -> None:
    code = {
        ActionResolutionStatus.APPLIED: EngineDiagnosticCode.RESOLUTION_APPLIED,
        ActionResolutionStatus.REJECTED: EngineDiagnosticCode.RESOLUTION_REJECTED,
        ActionResolutionStatus.CONFLICTED: EngineDiagnosticCode.RESOLUTION_CONFLICT,
        ActionResolutionStatus.DEFERRED_POLICY: (
            EngineDiagnosticCode.RESOLUTION_DEFERRED
        ),
        ActionResolutionStatus.DEAD_ACTOR: EngineDiagnosticCode.RESOLUTION_DEAD_ACTOR,
        ActionResolutionStatus.DUPLICATE: EngineDiagnosticCode.RESOLUTION_DUPLICATE,
    }[status]
    _LOGGER.debug(
        "%s tick=%s ordinal=%s request_id=%s status=%s",
        code.value,
        tick,
        ordinal,
        request_id,
        status.value,
    )
