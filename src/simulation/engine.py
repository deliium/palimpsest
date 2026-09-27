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
from typing import TYPE_CHECKING, Final

from agents.models import AgentId
from simulation.actions import (
    PHYSICAL_PURPOSE_ATTACK_DAMAGE,
    PHYSICAL_PURPOSE_ATTACK_HIT,
    PHYSICAL_PURPOSE_FLEE_DESTINATION,
    PHYSICAL_PURPOSE_FLEE_SUCCESS,
    PHYSICAL_PURPOSE_SEARCH_SUCCESS,
    PHYSICAL_PURPOSE_WEATHER,
    admit_agent_command,
    canonical_admission_keys,
    canonical_system_effect_keys,
    derive_engine_event_id,
    physical_action_effect_scope,
    physical_system_effect_scope,
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
from simulation.identifiers import (
    derive_entity_id,
    derive_event_id,
    derive_run_id,
    derive_scoped_id,
    derive_system_cause_id,
)
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
from simulation.randomness import (
    StreamScope,
    create_named_stream,
    sample_attack_damage,
    sample_bernoulli,
    sample_destination_index,
    sample_weather_condition,
)
from world._operations import (
    BatchItemStatus,
    PendingBatch,
    PendingEvent,
    finalize_pending_batch,
    prepare_action_batch,
)
from world._perception import PerceptionService
from world._physical import apply_autonomous_physical_step
from world._replay import ProjectionError, project_events
from world._rules import (
    find_eligible_flee_destinations,
    find_eligible_search_resource,
)
from world._state import World
from world.actions import ActionRequest, Attack, Flee, Search
from world.effects import (
    ActionCause,
    ResolvedActionEffect,
    ResolvedActionEffects,
    ResolvedAttackEffect,
    ResolvedFleeEffect,
    ResolvedSearchEffect,
    ResolvedSystemEffects,
    ResolvedWeatherEffect,
    SystemCause,
    SystemEffectFamily,
)
from world.events import Died, WorldEvent, normalize_events
from world.identifiers import EntityId, EventId, RequestId, WorldId, WorldRevision
from world.models import AgentBody, LifeStatus, default_physical_rules
from world.observations import Observation, ObservationContext
from world.values import WeatherCondition, clamp_unit_interval

if TYPE_CHECKING:
    from simulation.observer_facts import ObjectiveFacts
    from simulation.runner_models import DetachedObjectiveProjection

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
    prior_event_window: tuple[WorldEvent, ...]


@dataclass(frozen=True, slots=True)
class _PreparedTickCandidate:
    """Detached prepare result. Not exported; no public mutation API."""

    tick: Tick
    base_revision: WorldRevision
    resulting_revision: WorldRevision
    result: TickResult
    next_snapshot: _EngineSnapshot
    events: tuple[WorldEvent, ...]


class WorldEngine:
    """Public authority for observation and ordered tick resolution."""

    __slots__ = (
        "_bootstrap",
        "_config",
        "_engine_id",
        "_last_tick_result",
        "_perception",
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
        self._perception = PerceptionService()
        self._last_tick_result: TickResult | None = None
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
            prior_event_window=(),
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
        committed_through_tick: Tick | None = None,
    ) -> WorldEngine:
        """Restore an engine at ``AWAITING_OBSERVATION`` from a checkpoint.

        Validates snapshot integrity, folds subsequent ordered events with the
        private projector, and never restores observation tokens. Does not
        expose a public state-replacement hook on ``World``.

        When ``committed_through_tick`` is set, the engine tick becomes
        ``committed_through_tick + 1`` so eventless durable ticks after the
        last projected event advance the logical cursor.
        """
        if type(snapshot) is not WorldSnapshot:
            raise TypeError("restore_from_snapshot requires WorldSnapshot")
        if isinstance(events, (set, frozenset)) or not isinstance(events, Sequence):
            raise TypeError("events must be an ordered sequence")
        if committed_through_tick is not None and type(committed_through_tick) is not (
            Tick
        ):
            raise TypeError("committed_through_tick must be Tick or None")

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
            event_next = Tick(last_tick + 1)
        else:
            event_next = snapshot.next_tick

        if committed_through_tick is None:
            restored_tick = event_next
        else:
            if normalized_events and last_tick > committed_through_tick.value:
                raise ValueError("committed_through_tick precedes last event tick")
            restored_tick = Tick(committed_through_tick.value + 1)
            if restored_tick.value < event_next.value:
                raise ValueError("committed_through_tick undershoots event cursor")

        engine = cls.__new__(cls)
        engine._config = snapshot.config
        engine._bootstrap = bootstrap
        engine._run_id = snapshot.run_id
        engine._translator = registration_translator(bootstrap)
        engine._registrations = bootstrap.registrations
        engine._perception = PerceptionService()
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
            prior_event_window=_prior_event_window_for_tick(
                normalized_events, observation_tick=restored_tick.value
            ),
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

    @property
    def last_tick_result(self) -> TickResult | None:
        """Most recent committed TickResult, if any."""
        return self._last_tick_result

    def detached_objective_facts(self) -> ObjectiveFacts:
        """Copied locations, bodies, items, resources, weather, and registrations.

        Reads the folded world only. Does not commit a tick or replace state.
        """
        from simulation.observer_facts import ObjectiveFacts

        state = self._snapshot.world.state
        tick_before = self._snapshot.tick
        revision_before = state.revision
        facts = ObjectiveFacts(
            run_id=self._run_id.value,
            world_id=self.world_id.value,
            tick=self.tick.value,
            revision=self.revision.value,
            locations=tuple(
                sorted(state.locations.values(), key=lambda item: item.entity_id.value)
            ),
            bodies=self.detached_bodies(),
            items=tuple(
                sorted(state.items.values(), key=lambda item: item.entity_id.value)
            ),
            resources=tuple(
                sorted(
                    state.resources.values(), key=lambda item: item.entity_id.value
                )
            ),
            weather=tuple(
                sorted(state.weather.values(), key=lambda item: item.location_id.value)
            ),
            registrations=tuple(self._registrations),
        )
        if self._snapshot.tick != tick_before or state.revision != revision_before:
            raise RuntimeError("detached_objective_facts mutated engine state")
        return facts

    def detached_bodies(self) -> tuple[AgentBody, ...]:
        """Ordered immutable body copies for public objective projection."""
        bodies = self._snapshot.world.state.bodies
        return tuple(
            bodies[entity_id]
            for entity_id in sorted(bodies.keys(), key=lambda item: item.value)
        )

    def detached_objective_projection(self) -> DetachedObjectiveProjection:
        """Public objective projection without mutating engine phase."""
        from simulation.runner_models import build_detached_objective_projection

        return build_detached_objective_projection(
            tick=self.tick.value,
            revision=self.revision.value,
            bodies=self.detached_bodies(),
        )

    def project_detached_observations(self) -> ObservationBatch:
        """Project agent-visible observations without mutating engine phase.

        Mirrors the PerceptionService path used by ``observe()`` but never
        advances phase, never stores a tick token, and never writes the batch
        onto the live snapshot. Intended for inspection/replay only.
        """
        snap = self._snapshot
        if (
            snap.phase is EnginePhase.AWAITING_SUBMISSIONS
            and snap.observation_batch is not None
        ):
            _LOGGER.debug(
                "%s tick=%s observers=%s revision=%s prior_events=%s "
                "detached_replay=1",
                EngineDiagnosticCode.OBSERVATIONS_ISSUED.value,
                snap.tick.value,
                len(snap.observation_batch.observations),
                snap.world.state.revision.value,
                len(snap.prior_event_window),
            )
            return snap.observation_batch
        if snap.phase not in {
            EnginePhase.AWAITING_OBSERVATION,
            EnginePhase.AWAITING_SUBMISSIONS,
        }:
            _LOGGER.error(
                "%s reason=detached_observe_wrong_phase phase=%s tick=%s",
                EngineDiagnosticCode.LIFECYCLE_MISUSE.value,
                snap.phase.value,
                snap.tick.value,
            )
            raise RuntimeError("detached observations unavailable in current phase")
        observer_ids = tuple(
            registration.entity_id for registration in self._registrations
        )
        rules = self._config.physical_rules
        if rules is None:
            rules = default_physical_rules()
        context = ObservationContext(tick=snap.tick.value, physical_rules=rules)
        prior_events = snap.prior_event_window
        try:
            observations = self._perception.project(
                world_id=self.world_id,
                state=snap.world.state,
                observer_ids=observer_ids,
                context=context,
                prior_events=prior_events,
            )
        except (TypeError, ValueError) as exc:
            _LOGGER.error(
                "%s tick=%s code=detached_observation_invariant reason=%s",
                EngineDiagnosticCode.CANDIDATE_ABORTED.value,
                snap.tick.value,
                type(exc).__name__,
            )
            raise
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
                        "detached-inspection",
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
        _LOGGER.debug(
            "%s tick=%s observers=%s revision=%s prior_events=%s "
            "detached_replay=0 phase_unchanged=%s",
            EngineDiagnosticCode.OBSERVATIONS_ISSUED.value,
            snap.tick.value,
            len(observations),
            snap.world.state.revision.value,
            len(prior_events),
            snap.phase.value,
        )
        return batch

    def project_agent_visible_detached(
        self, agent_id: AgentId
    ) -> tuple[EntityId, Observation]:
        """Return ``(entity_id, observation)`` for one agent without phase mutation."""
        if type(agent_id) is not AgentId:
            raise TypeError("project_agent_visible_detached requires AgentId")
        entity_id = self._translator.to_entity_id(agent_id)
        batch = self.project_detached_observations()
        observation = batch.for_observer(entity_id)
        _LOGGER.debug(
            "%s tick=%s agent=%s entity=%s revision=%s "
            "occurrences=%s communications=%s detached=1",
            EngineDiagnosticCode.OBSERVATION_ROUTED.value,
            self.tick.value,
            agent_id.value,
            entity_id.value,
            batch.revision.value,
            len(observation.occurrences),
            len(observation.communications),
        )
        return entity_id, observation

    def observe(self) -> ObservationBatch:
        """Issue or replay the immutable observation batch for the open tick.

        Projection uses only the tick-start world snapshot and the committed
        tick ``N-1`` occurrence window. Current-tick outcomes never appear.
        """
        snap = self._snapshot
        if (
            snap.phase is EnginePhase.AWAITING_SUBMISSIONS
            and snap.observation_batch is not None
        ):
            _LOGGER.debug(
                "%s tick=%s observers=%s revision=%s prior_events=%s replay=1",
                EngineDiagnosticCode.OBSERVATIONS_ISSUED.value,
                snap.tick.value,
                len(snap.observation_batch.observations),
                snap.world.state.revision.value,
                len(snap.prior_event_window),
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
        rules = self._config.physical_rules
        if rules is None:
            rules = default_physical_rules()
        context = ObservationContext(tick=snap.tick.value, physical_rules=rules)
        prior_events = snap.prior_event_window
        try:
            observations = self._perception.project(
                world_id=self.world_id,
                state=snap.world.state,
                observer_ids=observer_ids,
                context=context,
                prior_events=prior_events,
            )
        except (TypeError, ValueError) as exc:
            _LOGGER.error(
                "%s tick=%s code=observation_invariant reason=%s",
                EngineDiagnosticCode.CANDIDATE_ABORTED.value,
                snap.tick.value,
                type(exc).__name__,
            )
            raise
        projected_occurrences = sum(
            len(observation.occurrences) for observation in observations
        )
        projected_communications = sum(
            len(observation.communications) for observation in observations
        )
        visible_entities = sum(
            len(observation.items)
            + len(observation.resources)
            + len(observation.visible_bodies)
            for observation in observations
        )
        visibility_bands = {
            ("high" if (observation.visibility or 0.0) >= 0.5 else "low")
            for observation in observations
        }
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
            prior_event_window=snap.prior_event_window,
        )
        _LOGGER.debug(
            "%s tick=%s observers=%s revision=%s replay=0 "
            "prior_events=%s projected_occurrences=%s "
            "projected_communications=%s phase=%s visibility_bands=%s "
            "visible_entities=%s hour=%s",
            EngineDiagnosticCode.OBSERVATIONS_ISSUED.value,
            snap.tick.value,
            len(observations),
            snap.world.state.revision.value,
            len(prior_events),
            projected_occurrences,
            projected_communications,
            context.day_phase.value,
            ",".join(sorted(visibility_bands)) if visibility_bands else "-",
            visible_entities,
            context.hour,
        )
        return batch

    def observation_for(self, agent_id: AgentId) -> Observation:
        """Return the open-tick observation for one registered agent.

        Trusted orchestration must use this addressable route instead of
        handing the full ``ObservationBatch`` to cognition.
        """
        if type(agent_id) is not AgentId:
            raise TypeError("observation_for requires AgentId")
        snap = self._snapshot
        batch = snap.observation_batch
        if batch is None or snap.phase is not EnginePhase.AWAITING_SUBMISSIONS:
            _LOGGER.warning(
                "%s reason=observation_route_closed phase=%s tick=%s",
                EngineDiagnosticCode.LIFECYCLE_MISUSE.value,
                snap.phase.value,
                snap.tick.value,
            )
            raise RuntimeError("observation_for requires an open observation batch")
        try:
            entity_id = self._translator.to_entity_id(agent_id)
            observation = batch.for_observer(entity_id)
        except KeyError:
            _LOGGER.warning(
                "%s reason=observation_route_unknown agent=%s tick=%s",
                EngineDiagnosticCode.LIFECYCLE_MISUSE.value,
                agent_id.value,
                snap.tick.value,
            )
            raise
        _LOGGER.debug(
            "%s tick=%s agent=%s entity=%s revision=%s "
            "occurrences=%s communications=%s",
            EngineDiagnosticCode.OBSERVATION_ROUTED.value,
            snap.tick.value,
            agent_id.value,
            entity_id.value,
            batch.revision.value,
            len(observation.occurrences),
            len(observation.communications),
        )
        return observation

    def resolve_tick(self, submissions: Sequence[ActionSubmission]) -> TickResult:
        """Admit ordered submissions, prepare a candidate, and commit atomically."""
        prior = self._snapshot
        try:
            candidate = self._prepare_tick_candidate(submissions)
            return self._finalize_tick_candidate(candidate)
        except Exception:
            self._snapshot = prior
            _LOGGER.error(
                "%s tick=%s",
                EngineDiagnosticCode.CANDIDATE_ABORTED.value,
                prior.tick.value,
            )
            raise

    def _prepare_tick_candidate(
        self, submissions: Sequence[ActionSubmission]
    ) -> _PreparedTickCandidate:
        """Build a detached tick candidate without mutating the live engine."""
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
        _LOGGER.debug(
            "%s tick=%s revision=%s submissions=%s",
            EngineDiagnosticCode.DURABLE_PREPARE.value,
            snap.tick.value,
            snap.world.state.revision.value,
            len(submissions),
        )
        typed = tuple(require_action_submission(item) for item in submissions)
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
            prior_event_window=events,
        )
        return _PreparedTickCandidate(
            tick=snap.tick,
            base_revision=snap.world.state.revision,
            resulting_revision=candidate_world.state.revision,
            result=result,
            next_snapshot=next_snapshot,
            events=events,
        )

    def _finalize_tick_candidate(self, candidate: _PreparedTickCandidate) -> TickResult:
        """Infallible in-memory publish of a prepared candidate."""
        if type(candidate) is not _PreparedTickCandidate:
            raise TypeError("candidate must be _PreparedTickCandidate")
        _LOGGER.debug(
            "%s tick=%s resulting_tick=%s events=%s",
            EngineDiagnosticCode.DURABLE_FINALIZE.value,
            candidate.tick.value,
            candidate.result.resulting_tick.value,
            len(candidate.events),
        )
        self._snapshot = candidate.next_snapshot
        result = candidate.result
        self._last_tick_result = result
        death_count = sum(
            1 for record in result.events if type(record.event.details) is Died
        )
        _LOGGER.info(
            "%s tick=%s resulting_tick=%s base_revision=%s resulting_revision=%s "
            "resolutions=%s events=%s deaths=%s",
            EngineDiagnosticCode.TICK_COMMITTED.value,
            result.tick.value,
            result.resulting_tick.value,
            result.base_revision.value,
            result.resulting_revision.value,
            len(result.resolutions),
            len(result.events),
            death_count,
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
        early_resolutions: dict[int, ActionResolution] = {}
        base_revision = snap.world.state.revision
        request_ordinals: dict[RequestId, tuple[int, AgentId]] = {}

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
            request_ordinals[request.request_id] = (ordinal, agent_id)
            _LOGGER.debug(
                "%s tick=%s ordinal=%s kind=%s request_id=%s",
                EngineDiagnosticCode.SUBMISSION_ADMITTED.value,
                snap.tick.value,
                ordinal,
                getattr(submission.command, "kind", "?"),
                request.request_id.value,
            )

        batch_requests = tuple(request for request in admitted if request is not None)
        physical_rules = self._config.physical_rules
        if physical_rules is None:
            physical_rules = default_physical_rules()
        resolved_effects = self._resolve_action_effects(
            snap=snap,
            batch_requests=batch_requests,
            request_ordinals=request_ordinals,
            rules=physical_rules,
        )
        pending = prepare_action_batch(
            world_id=self.world_id,
            starting_state=snap.world.state,
            requests=batch_requests,
            resolved_effects=resolved_effects,
            rules=physical_rules,
            tick=snap.tick.value,
        )
        _LOGGER.debug(
            "%s tick=%s pending_actions=%s pending_events=%s mutation=%s",
            EngineDiagnosticCode.SUBMISSION_ADMITTED.value,
            snap.tick.value,
            len(batch_requests),
            len(pending.pending_events),
            pending.semantic_mutation,
        )
        for outcome in pending.outcomes:
            _LOGGER.debug(
                "%s tick=%s ordinal=%s kind=%s request_id=%s status=%s reason=%s",
                EngineDiagnosticCode.RESOLUTION_APPLIED.value,
                snap.tick.value,
                outcome.ordinal,
                outcome.action_kind,
                outcome.request_id.value,
                outcome.status.value,
                outcome.reason,
            )

        system_effects = self._resolve_system_effects(
            snap=snap,
            working_state=pending.working_state,
            rules=physical_rules,
        )
        physical = apply_autonomous_physical_step(
            state=pending.working_state,
            rules=physical_rules,
            tick=snap.tick.value,
            hour=physical_rules.hour_for_tick(snap.tick.value),
            day_phase=physical_rules.day_phase_for_tick(snap.tick.value),
            resolved=system_effects,
        )
        family_counts = {family.value: 0 for family in SystemEffectFamily}
        system_pending: list[PendingEvent] = []
        for detail in physical.pending_details:
            family_counts[detail.effect_family.value] += 1
            cause_id = derive_system_cause_id(
                self._config,
                run_id=self._run_id,
                world_id=self.world_id,
                tick=snap.tick.value,
                effect_family=detail.effect_family.value,
                entity_id=detail.entity_id,
                family_ordinal=detail.family_ordinal,
            )
            system_pending.append(
                PendingEvent(
                    cause=SystemCause(
                        cause_id=cause_id,
                        effect_family=detail.effect_family,
                        entity_id=detail.entity_id,
                        family_ordinal=detail.family_ordinal,
                    ),
                    details=detail.details,
                    occurrence=detail.occurrence,
                )
            )
        _LOGGER.debug(
            "%s tick=%s family_weather=%s family_regeneration=%s "
            "family_combined_needs=%s family_exposure=%s "
            "system_events=%s system_mutation=%s",
            EngineDiagnosticCode.RESOLUTION_APPLIED.value,
            snap.tick.value,
            family_counts[SystemEffectFamily.WEATHER.value],
            family_counts[SystemEffectFamily.REGENERATION.value],
            family_counts[SystemEffectFamily.COMBINED_NEEDS.value],
            family_counts[SystemEffectFamily.EXPOSURE.value],
            len(system_pending),
            physical.semantic_mutation,
        )
        merged = PendingBatch(
            working_state=physical.working_state,
            semantic_mutation=(pending.semantic_mutation or physical.semantic_mutation),
            outcomes=pending.outcomes,
            pending_events=pending.pending_events + tuple(system_pending),
        )

        # Allocate one deterministic ID per pending event. Action events are
        # keyed by original request identity; system events use family/entity
        # ordinals. Contiguous tick sequences are assigned in finalize.
        per_request_event_index: dict[RequestId, int] = {}
        allocated_ids: list[EventId] = []
        for pending_event in merged.pending_events:
            cause = pending_event.cause
            if type(cause) is ActionCause:
                request_id = cause.request_id
                try:
                    ordinal, agent_id = request_ordinals[request_id]
                except KeyError as exc:
                    _LOGGER.error(
                        "%s tick=%s request_id=%s",
                        EngineDiagnosticCode.CANDIDATE_ABORTED.value,
                        snap.tick.value,
                        request_id.value,
                    )
                    raise ValueError(
                        "pending event request_id is not admitted"
                    ) from exc
                local_index = per_request_event_index.get(request_id, 0)
                per_request_event_index[request_id] = local_index + 1
                allocated_ids.append(
                    derive_engine_event_id(
                        self._config,
                        run_id=self._run_id,
                        world_id=self.world_id,
                        tick=snap.tick,
                        ordinal=ordinal,
                        agent_id=agent_id,
                        sequence=local_index,
                    )
                )
            elif type(cause) is SystemCause:
                local_index = per_request_event_index.get(cause.cause_id, 0)
                per_request_event_index[cause.cause_id] = local_index + 1
                allocated_ids.append(
                    derive_event_id(
                        self._config,
                        *canonical_system_effect_keys(
                            run_id=self._run_id,
                            world_id=self.world_id,
                            tick=snap.tick,
                            effect_family=cause.effect_family.value,
                            entity_id=cause.entity_id,
                            family_ordinal=cause.family_ordinal,
                            sequence=local_index,
                        ),
                    )
                )
            else:
                _LOGGER.error(
                    "%s tick=%s code=invalid_pending_cause",
                    EngineDiagnosticCode.CANDIDATE_ABORTED.value,
                    snap.tick.value,
                )
                raise TypeError("pending event cause must be EventCause")

        prepared = finalize_pending_batch(
            merged,
            world_id=self.world_id,
            starting_revision=base_revision,
            event_ids=tuple(allocated_ids),
            run_id=run_id_for_event(self._run_id),
            tick=tick_for_event(snap.tick),
        )
        _LOGGER.debug(
            "%s tick=%s finalized_events=%s mutation=%s revision=%s",
            EngineDiagnosticCode.RESOLUTION_APPLIED.value,
            snap.tick.value,
            len(prepared.events),
            prepared.semantic_mutation,
            prepared.candidate_state.revision.value,
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

    def _resolve_system_effects(
        self,
        *,
        snap: _EngineSnapshot,
        working_state: object,
        rules: object,
    ) -> ResolvedSystemEffects:
        """Pre-resolve per-location weather samples when the period elapses."""
        from world._state import WorldState
        from world.models import PhysicalRules

        if type(rules) is not PhysicalRules:
            raise TypeError("physical rules must be PhysicalRules")
        if type(working_state) is not WorldState:
            raise TypeError("working_state must be WorldState")
        if (snap.tick.value + 1) % rules.weather_period_ticks != 0:
            return ResolvedSystemEffects(weather_by_location={})
        weather_by_location: dict[EntityId, ResolvedWeatherEffect] = {}
        for location_id in sorted(
            working_state.locations, key=lambda value: value.value
        ):
            current = working_state.weather[location_id].condition
            transitions = rules.weather_transitions
            assert transitions is not None
            location_transitions = transitions[current]
            scope = physical_system_effect_scope(
                config=self._config,
                run_id=self._run_id,
                world_id=self.world_id,
                tick=snap.tick,
                entity_id=location_id,
                purpose=PHYSICAL_PURPOSE_WEATHER,
            )
            condition = sample_weather_condition(
                create_named_stream(self._config, scope),
                location_transitions,
            )
            weather_by_location[location_id] = ResolvedWeatherEffect(
                location_id=location_id,
                condition=condition,
            )
        _LOGGER.debug(
            "%s tick=%s weather_samples=%s",
            EngineDiagnosticCode.RESOLUTION_APPLIED.value,
            snap.tick.value,
            len(weather_by_location),
        )
        return ResolvedSystemEffects(weather_by_location=weather_by_location)

    def _resolve_action_effects(
        self,
        *,
        snap: _EngineSnapshot,
        batch_requests: tuple[ActionRequest, ...],
        request_ordinals: dict[RequestId, tuple[int, AgentId]],
        rules: object,
    ) -> ResolvedActionEffects:
        """Pre-resolve Search/Attack/Flee draws for structurally eligible requests."""
        from world.models import PhysicalRules

        if type(rules) is not PhysicalRules:
            raise TypeError("physical rules must be PhysicalRules")
        starting_state = snap.world.state
        by_request: dict[RequestId, ResolvedActionEffect] = {}
        for request in batch_requests:
            command = request.command
            if type(command) is Search:
                search_effect = self._resolve_search_effect(
                    snap=snap,
                    request=request,
                    request_ordinals=request_ordinals,
                    rules=rules,
                    starting_state=starting_state,
                )
                if search_effect is not None:
                    by_request[request.request_id] = search_effect
            elif type(command) is Attack:
                attack_effect = self._resolve_attack_effect(
                    snap=snap,
                    request=request,
                    request_ordinals=request_ordinals,
                    rules=rules,
                    starting_state=starting_state,
                )
                if attack_effect is not None:
                    by_request[request.request_id] = attack_effect
            elif type(command) is Flee:
                flee_effect = self._resolve_flee_effect(
                    snap=snap,
                    request=request,
                    request_ordinals=request_ordinals,
                    rules=rules,
                    starting_state=starting_state,
                )
                if flee_effect is not None:
                    by_request[request.request_id] = flee_effect
        return ResolvedActionEffects(by_request=by_request)

    def _resolve_search_effect(
        self,
        *,
        snap: _EngineSnapshot,
        request: ActionRequest,
        request_ordinals: dict[RequestId, tuple[int, AgentId]],
        rules: object,
        starting_state: object,
    ) -> ResolvedSearchEffect | None:
        from world._state import WorldState
        from world.models import PhysicalRules

        assert type(rules) is PhysicalRules
        assert type(starting_state) is WorldState
        assert type(request.command) is Search
        resource_id = find_eligible_search_resource(
            starting_state, request.actor_id, request.command.target_id
        )
        if resource_id is None:
            return None
        ordinal, agent_id = request_ordinals[request.request_id]
        actor = starting_state.bodies[request.actor_id]
        location = starting_state.locations[actor.location_id]
        weather = starting_state.weather.get(actor.location_id)
        condition = weather.condition if weather is not None else WeatherCondition.CLEAR
        visibility = rules.effective_visibility(
            location_visibility=location.visibility_factor.value,
            phase=rules.day_phase_for_tick(snap.tick.value),
            condition=condition,
        )
        probability = clamp_unit_interval(
            rules.search_base_probability + rules.search_visibility_weight * visibility
        )
        scope = physical_action_effect_scope(
            config=self._config,
            run_id=self._run_id,
            world_id=self.world_id,
            tick=snap.tick,
            ordinal=ordinal,
            agent_id=agent_id,
            purpose=PHYSICAL_PURPOSE_SEARCH_SUCCESS,
        )
        success = sample_bernoulli(
            create_named_stream(self._config, scope), probability
        )
        created_item_id = None
        if success:
            created_item_id = derive_entity_id(
                self._config,
                "foraged-item",
                self._run_id.value,
                self.world_id.value,
                f"tick:{snap.tick.value}",
                request.request_id.value,
            )
        _LOGGER.debug(
            "%s tick=%s ordinal=%s kind=search request_id=%s outcome=%s",
            EngineDiagnosticCode.RESOLUTION_APPLIED.value,
            snap.tick.value,
            ordinal,
            request.request_id.value,
            "success" if success else "miss",
        )
        return ResolvedSearchEffect(
            request_id=request.request_id,
            success=success,
            resource_id=resource_id,
            created_item_id=created_item_id,
        )

    def _resolve_attack_effect(
        self,
        *,
        snap: _EngineSnapshot,
        request: ActionRequest,
        request_ordinals: dict[RequestId, tuple[int, AgentId]],
        rules: object,
        starting_state: object,
    ) -> ResolvedAttackEffect | None:
        from world._state import WorldState
        from world.models import PhysicalRules

        assert type(rules) is PhysicalRules
        assert type(starting_state) is WorldState
        assert type(request.command) is Attack
        actor = starting_state.bodies.get(request.actor_id)
        target = starting_state.bodies.get(request.command.target_id)
        if (
            actor is None
            or target is None
            or actor.life_status is LifeStatus.DEAD
            or target.life_status is LifeStatus.DEAD
            or target.location_id != actor.location_id
        ):
            return None
        ordinal, agent_id = request_ordinals[request.request_id]
        hit_scope = physical_action_effect_scope(
            config=self._config,
            run_id=self._run_id,
            world_id=self.world_id,
            tick=snap.tick,
            ordinal=ordinal,
            agent_id=agent_id,
            purpose=PHYSICAL_PURPOSE_ATTACK_HIT,
        )
        hit = sample_bernoulli(
            create_named_stream(self._config, hit_scope),
            rules.attack_hit_probability,
        )
        damage = None
        if hit:
            damage_scope = physical_action_effect_scope(
                config=self._config,
                run_id=self._run_id,
                world_id=self.world_id,
                tick=snap.tick,
                ordinal=ordinal,
                agent_id=agent_id,
                purpose=PHYSICAL_PURPOSE_ATTACK_DAMAGE,
            )
            damage = sample_attack_damage(
                create_named_stream(self._config, damage_scope),
                minimum=rules.attack_damage_min,
                maximum_exclusive=rules.attack_damage_max_exclusive,
            )
        _LOGGER.debug(
            "%s tick=%s ordinal=%s kind=attack request_id=%s outcome=%s",
            EngineDiagnosticCode.RESOLUTION_APPLIED.value,
            snap.tick.value,
            ordinal,
            request.request_id.value,
            "hit" if hit else "miss",
        )
        return ResolvedAttackEffect(
            request_id=request.request_id,
            hit=hit,
            damage=damage,
        )

    def _resolve_flee_effect(
        self,
        *,
        snap: _EngineSnapshot,
        request: ActionRequest,
        request_ordinals: dict[RequestId, tuple[int, AgentId]],
        rules: object,
        starting_state: object,
    ) -> ResolvedFleeEffect | None:
        from world._state import WorldState
        from world.models import PhysicalRules

        assert type(rules) is PhysicalRules
        assert type(starting_state) is WorldState
        assert type(request.command) is Flee
        actor = starting_state.bodies.get(request.actor_id)
        if actor is None or actor.life_status is LifeStatus.DEAD:
            return None
        threat_id = request.command.threat_id
        if threat_id is not None:
            threat = starting_state.bodies.get(threat_id)
            if (
                threat is None
                or threat.life_status is LifeStatus.DEAD
                or threat.location_id != actor.location_id
            ):
                return None
        eligible = find_eligible_flee_destinations(starting_state, request.actor_id)
        if not eligible:
            return None
        ordinal, agent_id = request_ordinals[request.request_id]
        success_scope = physical_action_effect_scope(
            config=self._config,
            run_id=self._run_id,
            world_id=self.world_id,
            tick=snap.tick,
            ordinal=ordinal,
            agent_id=agent_id,
            purpose=PHYSICAL_PURPOSE_FLEE_SUCCESS,
        )
        success = sample_bernoulli(
            create_named_stream(self._config, success_scope),
            rules.flee_success_probability,
        )
        destination_index = None
        if success:
            dest_scope = physical_action_effect_scope(
                config=self._config,
                run_id=self._run_id,
                world_id=self.world_id,
                tick=snap.tick,
                ordinal=ordinal,
                agent_id=agent_id,
                purpose=PHYSICAL_PURPOSE_FLEE_DESTINATION,
            )
            destination_index = sample_destination_index(
                create_named_stream(self._config, dest_scope),
                len(eligible),
            )
        _LOGGER.debug(
            "%s tick=%s ordinal=%s kind=flee request_id=%s outcome=%s",
            EngineDiagnosticCode.RESOLUTION_APPLIED.value,
            snap.tick.value,
            ordinal,
            request.request_id.value,
            "success" if success else "failure",
        )
        return ResolvedFleeEffect(
            request_id=request.request_id,
            success=success,
            destination_index=destination_index,
        )


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
        "not_adjacent": ActionResolutionReason.STRUCTURAL_REJECTION,
        "no_body_capacity": ActionResolutionReason.STRUCTURAL_REJECTION,
        "no_item_capacity": ActionResolutionReason.STRUCTURAL_REJECTION,
        "no_carry_capacity": ActionResolutionReason.STRUCTURAL_REJECTION,
        "resource_depleted": ActionResolutionReason.STRUCTURAL_REJECTION,
        "wrong_kind": ActionResolutionReason.STRUCTURAL_REJECTION,
        "missing_resolved_effect": ActionResolutionReason.STRUCTURAL_REJECTION,
        "already_at_destination": ActionResolutionReason.STRUCTURAL_REJECTION,
        "dead_target": ActionResolutionReason.STRUCTURAL_REJECTION,
        "distinct_id_violation": ActionResolutionReason.STRUCTURAL_REJECTION,
        "communication_invisible": ActionResolutionReason.STRUCTURAL_REJECTION,
        "communication_source_mismatch": ActionResolutionReason.STRUCTURAL_REJECTION,
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


def _prior_event_window_for_tick(
    events: Sequence[WorldEvent], *, observation_tick: int
) -> tuple[WorldEvent, ...]:
    """Select committed events from tick ``observation_tick - 1`` only.

    Legacy events without occurrence context are omitted (never fabricated)
    so restored engines remain observable without inventing audience data.
    """
    prior_tick = observation_tick - 1
    if prior_tick < 0:
        return ()
    return tuple(
        event
        for event in events
        if event.tick == prior_tick and event.occurrence is not None
    )
