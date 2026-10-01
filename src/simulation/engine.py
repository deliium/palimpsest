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
    PHYSICAL_PURPOSE_PRODUCTION_SUCCESS,
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
from world._replay import ProjectionError, project_event_prefix, project_events
from world._rules import (
    find_eligible_flee_destinations,
    find_eligible_search_resource,
)
from world._state import World
from world.actions import (
    ActionRequest,
    Attack,
    Build,
    Craft,
    Flee,
    Harvest,
    Help,
    Move,
    Repair,
    Search,
    Store,
)
from world.effects import (
    ActionCause,
    ResolvedActionEffect,
    ResolvedActionEffects,
    ResolvedAttackEffect,
    ResolvedFleeEffect,
    ResolvedProductionEffect,
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

__all__ = ["EnginePhase", "EventPrefixError", "WorldEngine"]


class EnginePhase(StrEnum):
    AWAITING_OBSERVATION = "awaiting_observation"
    AWAITING_SUBMISSIONS = "awaiting_submissions"


class EventPrefixError(ValueError):
    """A same-tick event prefix could not be folded. ``code`` is stable."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


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
    skill_ledger: object | None = None


def _request_id_set(value: object | None) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, (str, bytes)) or not isinstance(value, frozenset):
        raise TypeError("skill_untargeted_request_ids must be a frozenset")
    checked: set[str] = set()
    for item in value:
        if type(item) is not str or not item:
            raise TypeError("skill_untargeted_request_ids entries must be request ids")
        checked.add(item)
    return checked


def _project_skill_prefix(
    initial_state: object,
    events: object,
    expected_run_id: str,
    expected_world_id: object,
    environmental_dynamics: object | None = None,
) -> object:
    from world._replay import project_events

    return project_events(
        initial_state,
        events,
        expected_run_id=expected_run_id,
        expected_world_id=expected_world_id,
        environmental_dynamics=environmental_dynamics,
    )


class WorldEngine:
    """Public authority for observation and ordered tick resolution."""

    __slots__ = (
        "_bootstrap",
        "_config",
        "_engine_id",
        "_environmental_dynamics",
        "_last_tick_result",
        "_perception",
        "_production_catalog",
        "_registrations",
        "_run_id",
        "_skill_entity_ids",
        "_skill_ledger",
        "_skill_policy",
        "_skill_untargeted_requests",
        "_snapshot",
        "_teaching_entity_ids",
        "_teaching_policy",
        "_translator",
    )

    def __init__(
        self,
        *,
        config: SimulationRunConfig,
        bootstrap: WorldBootstrap,
        run_id: RunId | None = None,
        start_tick: Tick | None = None,
        skill_policy: object | None = None,
        skill_entity_ids: Sequence[object] | None = None,
        skill_ledger: object | None = None,
        skill_untargeted_request_ids: object | None = None,
        teaching_policy: object | None = None,
        teaching_entity_ids: Sequence[object] | None = None,
        production_catalog: object | None = None,
        environmental_dynamics: object | None = None,
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
        self._bind_skill_state(
            skill_policy=skill_policy,
            skill_entity_ids=skill_entity_ids,
            skill_ledger=skill_ledger,
            skill_untargeted_request_ids=skill_untargeted_request_ids,
            restored=False,
        )
        self._bind_teaching_state(
            teaching_policy=teaching_policy,
            teaching_entity_ids=teaching_entity_ids,
        )
        self._production_catalog = _optional_production_catalog(production_catalog)
        self._environmental_dynamics = _optional_environmental_dynamics(
            environmental_dynamics
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
        skill_policy: object | None = None,
        skill_entity_ids: Sequence[object] | None = None,
        skill_ledger: object | None = None,
        skill_untargeted_request_ids: object | None = None,
        teaching_policy: object | None = None,
        teaching_entity_ids: Sequence[object] | None = None,
        teaching_offers: object | None = None,
        production_catalog: object | None = None,
        environmental_dynamics: object | None = None,
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
            structures=snapshot.structures,
            production_jobs=snapshot.production_jobs,
            tool_marks=snapshot.tool_marks,
            active_hazards=snapshot.active_hazards,
        )
        resolved_catalog = _optional_production_catalog(production_catalog)
        if snapshot.persistence_codec_version == "v3" and resolved_catalog is None:
            from world.production import production_catalog_digest

            _LOGGER.error(
                "production_catalog_mismatch digest=%s",
                production_catalog_digest(()),
            )
            raise ValueError("production_catalog_mismatch")
        try:
            normalized_events = normalize_events(events)
            projected = project_events(
                base_state,
                normalized_events,
                expected_run_id=snapshot.run_id.value,
                expected_world_id=snapshot.world_id,
                production_catalog=resolved_catalog,  # type: ignore[arg-type]
                environmental_dynamics=environmental_dynamics,
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
        engine._bind_skill_state(
            skill_policy=skill_policy,
            skill_entity_ids=skill_entity_ids,
            skill_ledger=engine._refolded_skill_ledger(
                skill_policy=skill_policy,
                skill_entity_ids=skill_entity_ids,
                skill_ledger=skill_ledger,
                initial_state=base_state,
                events=normalized_events,
                rules=snapshot.config.physical_rules,
                expected_run_id=snapshot.run_id.value,
                expected_world_id=snapshot.world_id,
                untargeted_request_ids=skill_untargeted_request_ids,
            ),
            skill_untargeted_request_ids=skill_untargeted_request_ids,
            restored=True,
        )
        engine._bind_teaching_state(
            teaching_policy=teaching_policy,
            teaching_entity_ids=teaching_entity_ids,
        )
        engine._production_catalog = _optional_production_catalog(production_catalog)
        engine._environmental_dynamics = _optional_environmental_dynamics(
            environmental_dynamics
        )
        engine._require_refolded_teaching_offers(
            teaching_offers=teaching_offers,
            initial_state=base_state,
            events=normalized_events,
            expected_run_id=snapshot.run_id.value,
            expected_world_id=snapshot.world_id,
            tick=restored_tick.value,
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
                sorted(state.resources.values(), key=lambda item: item.entity_id.value)
            ),
            weather=tuple(
                sorted(state.weather.values(), key=lambda item: item.location_id.value)
            ),
            registrations=tuple(self._registrations),
        )
        if self._snapshot.tick != tick_before or state.revision != revision_before:
            raise RuntimeError("detached_objective_facts mutated engine state")
        return facts

    def _project_dynamics_prefix(
        self,
        initial_state: object,
        events: object,
        expected_run_id: str,
        expected_world_id: object,
    ) -> object:
        return _project_skill_prefix(
            initial_state,
            events,
            expected_run_id,
            expected_world_id,
            self._environmental_dynamics,
        )

    def _apply_event_prefix(
        self,
        events: Sequence[WorldEvent],
        *,
        includes_last_event: bool,
    ) -> None:
        """Fold one tick's event prefix onto this restored engine.

        Effects apply in sequence order. The tick revision and the clock
        (``committed_through_tick + 1``) advance only when the prefix includes
        that tick's last event. Does not write a snapshot.
        """
        if type(includes_last_event) is not bool:
            raise TypeError("includes_last_event must be bool")
        if isinstance(events, (str, bytes, set, frozenset)) or not isinstance(
            events, Sequence
        ):
            raise TypeError("events must be an ordered sequence")
        state = self._snapshot.world.state
        tick_before = self._snapshot.tick
        try:
            projected = project_event_prefix(
                state,
                events,
                expected_run_id=self._run_id.value,
                expected_world_id=self.world_id,
                includes_last_event=includes_last_event,
                environmental_dynamics=self._environmental_dynamics,
            )
        except ProjectionError as exc:
            _LOGGER.error(
                "%s code=%s run_id=%s tick=%s",
                EngineDiagnosticCode.PROJECTION_FAILED.value,
                exc.code,
                self._run_id.value,
                tick_before.value,
            )
            raise EventPrefixError(exc.code) from exc
        restored_tick = (
            Tick(tick_before.value + 1) if includes_last_event else tick_before
        )
        folded = self._snapshot.event_history + tuple(events)
        world = _materialize_projected_world(world_id=self.world_id, state=projected)
        self._snapshot = _EngineSnapshot(
            world=world,
            tick=restored_tick,
            phase=self._snapshot.phase,
            token=None,
            observation_batch=None,
            resolution_history=self._snapshot.resolution_history,
            event_history=folded,
            prior_event_window=self._snapshot.prior_event_window,
        )
        _LOGGER.debug(
            "event_prefix_applied tick=%s sequence_count=%s includes_last=%s "
            "revision=%s restored_tick=%s",
            tick_before.value,
            len(folded),
            includes_last_event,
            projected.revision.value,
            restored_tick.value,
        )

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
                "%s tick=%s observers=%s revision=%s prior_events=%s detached_replay=1",
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
                environmental_dynamics=self._environmental_dynamics,
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
                environmental_dynamics=self._environmental_dynamics,
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
        resolutions, events, candidate_world, next_ledger = self._resolve_ordered(
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
            skill_ledger=next_ledger,
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
        self._skill_ledger = candidate.skill_ledger
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

    def skill_untargeted_request_ids(self) -> frozenset[str]:
        """Request ids whose search command had no target.

        A committed search event stores the found resource, so replay uses
        this set to keep untargeted search on foraging.
        """
        return frozenset(self._skill_untargeted_requests)

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
        self._log_skill_efficiency(
            snap=snap, requests=batch_requests, rules=physical_rules
        )
        pending = prepare_action_batch(
            world_id=self.world_id,
            starting_state=snap.world.state,
            requests=batch_requests,
            resolved_effects=resolved_effects,
            rules=physical_rules,
            tick=snap.tick.value,
            skill_efficiency=self._skill_efficiency_map(rules=physical_rules),
            witness_resource_nodes=self._environmental_dynamics is not None,
        )
        start_ledger = self._skill_ledger
        folded_ledger, skill_facts = self._fold_skill_ledger(
            snap=snap, pending=pending, requests=batch_requests, rules=physical_rules
        )
        if self._teaching_policy is not None:
            folded_ledger = self._fold_teaching_ledger(
                snap=snap,
                rules=physical_rules,
                start_ledger=start_ledger,
                folded_ledger=folded_ledger,
                skill_facts=skill_facts,
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

        action_pending = pending
        completion_state = action_pending.working_state
        completion_details: tuple[object, ...] = ()
        catalog = self._production_catalog
        if catalog is not None and completion_state.production_jobs:
            from world._production import complete_due_jobs

            completion_state, completion_details = complete_due_jobs(
                completion_state,
                tick=snap.tick.value,
                catalog=catalog,
            )

        system_effects = self._resolve_system_effects(
            snap=snap,
            working_state=completion_state,
            rules=physical_rules,
        )
        try:
            physical = apply_autonomous_physical_step(
                state=completion_state,
                rules=physical_rules,
                tick=snap.tick.value,
                hour=physical_rules.hour_for_tick(snap.tick.value),
                day_phase=physical_rules.day_phase_for_tick(snap.tick.value),
                resolved=system_effects,
                environmental_dynamics=self._environmental_dynamics,
            )
        except ValueError as exc:
            message = str(exc)
            if "yield_undefined" in message:
                _LOGGER.warning("yield_undefined reason_code=yield_undefined")
            if "duplicate_shortage_window" in message:
                _LOGGER.warning(
                    "duplicate_shortage_window reason_code=duplicate_shortage_window"
                )
            raise
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
            "family_season=%s family_temperature_band=%s family_hazard=%s "
            "family_resource_node=%s "
            "system_events=%s system_mutation=%s",
            EngineDiagnosticCode.RESOLUTION_APPLIED.value,
            snap.tick.value,
            family_counts[SystemEffectFamily.WEATHER.value],
            family_counts[SystemEffectFamily.REGENERATION.value],
            family_counts[SystemEffectFamily.COMBINED_NEEDS.value],
            family_counts[SystemEffectFamily.EXPOSURE.value],
            family_counts[SystemEffectFamily.SEASON.value],
            family_counts[SystemEffectFamily.TEMPERATURE_BAND.value],
            family_counts[SystemEffectFamily.HAZARD.value],
            family_counts[SystemEffectFamily.RESOURCE_NODE.value],
            len(system_pending),
            physical.semantic_mutation,
        )
        from world.events import (
            CraftStarted,
            ItemCrafted,
            ItemStored,
            ResourceHarvested,
            StructureBuilt,
            StructureRepaired,
            build_occurrence_context,
        )

        production_pending: list[PendingEvent] = []
        for family_ordinal, detail in enumerate(completion_details):
            if type(detail) is not ItemCrafted:
                continue
            holder = detail.resulting_holder_id
            cause_id = derive_system_cause_id(
                self._config,
                run_id=self._run_id,
                world_id=self.world_id,
                tick=snap.tick.value,
                effect_family=SystemEffectFamily.PRODUCTION.value,
                entity_id=holder,
                family_ordinal=family_ordinal,
            )
            production_pending.append(
                PendingEvent(
                    cause=SystemCause(
                        cause_id=cause_id,
                        effect_family=SystemEffectFamily.PRODUCTION,
                        entity_id=holder,
                        family_ordinal=family_ordinal,
                    ),
                    details=detail,
                    occurrence=build_occurrence_context(
                        detail,
                        origin_location_id=completion_state.bodies[holder].location_id,
                    ),
                )
            )
        merged = PendingBatch(
            working_state=physical.working_state,
            semantic_mutation=(
                action_pending.semantic_mutation
                or physical.semantic_mutation
                or completion_state is not action_pending.working_state
            ),
            outcomes=action_pending.outcomes,
            pending_events=(
                action_pending.pending_events
                + tuple(production_pending)
                + tuple(system_pending)
            ),
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

        event_schema, _codec = select_checkpoint_schema(
            production_active=self._production_catalog is not None,
            dynamics_active=self._environmental_dynamics is not None,
        )
        prepared = finalize_pending_batch(
            merged,
            world_id=self.world_id,
            starting_revision=base_revision,
            event_ids=tuple(allocated_ids),
            run_id=run_id_for_event(self._run_id),
            tick=tick_for_event(snap.tick),
            schema_version=event_schema,
        )
        _LOGGER.debug(
            "%s tick=%s finalized_events=%s mutation=%s revision=%s",
            EngineDiagnosticCode.RESOLUTION_APPLIED.value,
            snap.tick.value,
            len(prepared.events),
            prepared.semantic_mutation,
            prepared.candidate_state.revision.value,
        )
        for event in prepared.events:
            if type(event.details) in {
                ResourceHarvested,
                CraftStarted,
                ItemCrafted,
                StructureBuilt,
                StructureRepaired,
                ItemStored,
            }:
                _LOGGER.info(
                    "production_event_committed event_id=%s tick=%s kind=%s",
                    event.event_id.value,
                    event.tick,
                    event.details.kind,
                )
            if event.details.kind in {
                "season_changed",
                "temperature_band_changed",
                "resource_node_depleted",
                "resource_node_recovered",
                "environmental_hazard_started",
                "environmental_hazard_ended",
            }:
                _LOGGER.info(
                    "environment_event_committed event_id=%s tick=%s kind=%s",
                    event.event_id.value,
                    event.tick,
                    event.details.kind,
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
        return tuple(resolutions), prepared.events, candidate_world, folded_ledger

    def _fold_skill_ledger(
        self,
        *,
        snap: _EngineSnapshot,
        pending: object,
        requests: tuple[ActionRequest, ...],
        rules: object,
    ) -> tuple[object | None, tuple[object, ...]]:
        if self._skill_ledger is None or self._skill_policy is None:
            return None, ()
        from world._operations import PendingBatch
        from world._skills import SkillGrowthInput, fold_skill_growth
        from world.effects import ActionCause

        if type(pending) is not PendingBatch:
            raise TypeError("pending must be PendingBatch")
        if type(self._skill_ledger).__name__ == "CompetenceSelfModel":
            raise TypeError("skill growth accepts only the objective skill ledger")
        by_request: dict[object, list[object]] = {}
        for pending_event in pending.pending_events:
            cause = pending_event.cause
            if type(cause) is not ActionCause:
                continue
            by_request.setdefault(cause.request_id, []).append(pending_event)
        requests_by_id = {request.request_id: request for request in requests}
        facts: list[SkillGrowthInput] = []
        for outcome in pending.outcomes:
            request = requests_by_id.get(outcome.request_id)
            if request is None:
                continue
            untargeted = None
            if type(request.command) is Search:
                untargeted = request.command.target_id is None
                if untargeted:
                    self._skill_untargeted_requests.add(request.request_id.value)
                    _LOGGER.debug(
                        "skill_search_command request_id=%s untargeted=true",
                        request.request_id.value,
                    )
            matched = by_request.get(outcome.request_id, [])
            if not matched:
                facts.append(
                    SkillGrowthInput(
                        actor_id=request.actor_id,
                        status=outcome.status.value,
                        action_kind=outcome.action_kind,
                        untargeted_search=untargeted,
                    )
                )
                continue
            for pending_event in matched:
                facts.append(
                    SkillGrowthInput(
                        actor_id=request.actor_id,
                        status=outcome.status.value,
                        action_kind=outcome.action_kind,
                        details=pending_event.details,
                        origin_location_id=pending_event.occurrence.origin_location_id,
                        untargeted_search=untargeted,
                    )
                )
        folded = fold_skill_growth(
            self._skill_ledger,
            tuple(facts),
            self._skill_policy,
            world_state=snap.world.state,
            tick=snap.tick.value,
            rules=rules,
        )
        return folded, tuple(facts)

    def _fold_teaching_ledger(
        self,
        *,
        snap: _EngineSnapshot,
        rules: object,
        start_ledger: object | None,
        folded_ledger: object | None,
        skill_facts: tuple[object, ...],
    ) -> object | None:
        if start_ledger is None or folded_ledger is None:
            _LOGGER.error(
                "teaching_validation_failed field=%s reason_code=%s",
                "entity_id",
                "missing_entity",
            )
            return folded_ledger
        from world._teaching import fold_teaching_opportunities

        return fold_teaching_opportunities(
            folded_ledger,
            start_ledger=start_ledger,
            applied_actions=skill_facts,
            prior_events=snap.event_history,
            policy=self._teaching_policy,
            teaching_entity_ids=self._teaching_entity_ids,
            world_state=snap.world.state,
            tick=snap.tick.value,
            rules=rules,
            untargeted_request_ids=frozenset(self._skill_untargeted_requests),
        )

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
            elif type(command) in {Harvest, Craft, Build, Repair, Store}:
                production_effect = self._resolve_production_effect(
                    snap=snap,
                    request=request,
                    request_ordinals=request_ordinals,
                    starting_state=starting_state,
                )
                if production_effect is not None:
                    by_request[request.request_id] = production_effect
        return ResolvedActionEffects(by_request=by_request)

    def _bind_skill_state(
        self,
        *,
        skill_policy: object | None,
        skill_entity_ids: Sequence[object] | None,
        skill_ledger: object | None,
        skill_untargeted_request_ids: object | None = None,
        restored: bool,
    ) -> None:
        from world._skills import (
            OBJECTIVE_SKILL_POLICY_VERSION,
            ObjectiveSkillLedger,
            ObjectiveSkillPolicy,
            SkillDomain,
        )
        from world.identifiers import EntityId

        if type(skill_policy).__name__ == "CompetenceSelfModel" or (
            skill_ledger is not None
            and type(skill_ledger).__name__ == "CompetenceSelfModel"
        ):
            raise TypeError("skill state accepts only the objective skill ledger")
        if skill_policy is None:
            if skill_entity_ids is not None or skill_ledger is not None:
                raise TypeError("skill_policy is required with skill ids or a ledger")
            self._skill_policy = None
            self._skill_entity_ids = frozenset()
            self._skill_ledger = None
            self._skill_untargeted_requests = set()
            _LOGGER.debug("skill_ledger=absent")
            return
        if type(skill_policy) is not ObjectiveSkillPolicy:
            raise TypeError("skill_policy must be ObjectiveSkillPolicy")
        if (
            skill_entity_ids is None
            or isinstance(skill_entity_ids, (str, bytes, set, frozenset))
            or not isinstance(skill_entity_ids, Sequence)
        ):
            raise TypeError("skill_entity_ids must be an ordered sequence")
        enabled: list[EntityId] = []
        for entity_id in skill_entity_ids:
            if type(entity_id) is not EntityId:
                raise TypeError("skill_entity_ids entries must be EntityId")
            enabled.append(entity_id)
        if skill_ledger is None:
            ledger = ObjectiveSkillLedger.bootstrap(tuple(enabled))
        elif type(skill_ledger) is not ObjectiveSkillLedger:
            raise TypeError("skill_ledger must be ObjectiveSkillLedger")
        else:
            ledger = skill_ledger
        self._skill_policy = skill_policy
        self._skill_entity_ids = frozenset(enabled)
        self._skill_ledger = ledger
        self._skill_untargeted_requests = _request_id_set(skill_untargeted_request_ids)
        if restored:
            _LOGGER.info(
                "skill_ledger_restored entity_count=%s domain_count=%s",
                len(ledger.entity_ids()),
                len(SkillDomain),
            )
        else:
            _LOGGER.debug(
                "skill_ledger_bound policy_version=%s entity_count=%s",
                OBJECTIVE_SKILL_POLICY_VERSION,
                len(enabled),
            )

    def _bind_teaching_state(
        self,
        *,
        teaching_policy: object | None,
        teaching_entity_ids: Sequence[object] | None,
    ) -> None:
        """Store the opt-in teaching policy. ``None`` skips the teaching fold."""
        from world._teaching import TeachingInteractionPolicy
        from world.identifiers import EntityId

        if teaching_policy is None:
            if teaching_entity_ids not in (None, (), frozenset()):
                raise TypeError("teaching_policy is required with teaching entity ids")
            self._teaching_policy = None
            self._teaching_entity_ids = frozenset()
            return
        if type(teaching_policy) is not TeachingInteractionPolicy:
            raise TypeError("teaching_policy must be TeachingInteractionPolicy")
        if teaching_entity_ids is None or isinstance(
            teaching_entity_ids, (str, bytes, set)
        ):
            raise TypeError("teaching_entity_ids must be an ordered sequence")
        if not isinstance(teaching_entity_ids, (Sequence, frozenset)):
            raise TypeError("teaching_entity_ids must be an ordered sequence")
        enabled: list[EntityId] = []
        for entity_id in teaching_entity_ids:
            if type(entity_id) is not EntityId:
                raise TypeError("teaching_entity_ids entries must be EntityId")
            enabled.append(entity_id)
        self._teaching_policy = teaching_policy
        self._teaching_entity_ids = frozenset(enabled)

    def _require_refolded_teaching_offers(
        self,
        *,
        teaching_offers: object | None,
        initial_state: object,
        events: Sequence[object],
        expected_run_id: str,
        expected_world_id: object,
        tick: int,
    ) -> None:
        """Refold open offers. A disagreeing caller set fails closed."""
        if self._teaching_policy is None:
            from world._teaching import reject_supplied_offers_without_policy

            reject_supplied_offers_without_policy(teaching_offers)
            return
        from world._teaching import refold_teaching_offers

        supplied = None if teaching_offers is None else tuple(teaching_offers)
        refold_teaching_offers(
            events,
            self._teaching_policy,
            self._teaching_entity_ids,
            tick=tick,
            untargeted_request_ids=self._skill_untargeted_requests,
            project_prefix=self._project_dynamics_prefix,
            initial_state=initial_state,
            expected_run_id=expected_run_id,
            expected_world_id=expected_world_id,
            supplied=supplied,
        )

    def _refolded_skill_ledger(
        self,
        *,
        skill_policy: object | None,
        skill_entity_ids: Sequence[object] | None,
        skill_ledger: object | None,
        initial_state: object,
        events: Sequence[object],
        rules: object,
        expected_run_id: str,
        expected_world_id: object,
        untargeted_request_ids: object | None = None,
    ) -> object | None:
        if skill_policy is None:
            return skill_ledger
        from world._skills import (
            ObjectiveSkillLedger,
            ObjectiveSkillPolicy,
            refold_objective_ledger,
            skill_ledger_mismatch,
        )
        from world.identifiers import EntityId
        from world.models import PhysicalRules, default_physical_rules

        if type(skill_policy) is not ObjectiveSkillPolicy:
            raise TypeError("skill_policy must be ObjectiveSkillPolicy")
        if skill_entity_ids is None:
            raise TypeError("skill_entity_ids must be an ordered sequence")
        entity_ids = tuple(entity for entity in skill_entity_ids)
        for entity_id in entity_ids:
            if type(entity_id) is not EntityId:
                raise TypeError("skill_entity_ids entries must be EntityId")
        physical_rules = rules if rules is not None else default_physical_rules()
        if type(physical_rules) is not PhysicalRules:
            raise TypeError("rules must be PhysicalRules")
        refolded = refold_objective_ledger(
            initial_state,
            events,
            skill_policy,
            entity_ids,
            rules=physical_rules,
            expected_run_id=expected_run_id,
            expected_world_id=expected_world_id,
            project_prefix=self._project_dynamics_prefix,
            untargeted_request_ids=untargeted_request_ids,
        )
        if skill_ledger is None:
            return refolded
        if type(skill_ledger) is not ObjectiveSkillLedger:
            raise TypeError("skill_ledger must be ObjectiveSkillLedger")
        mismatch = skill_ledger_mismatch(skill_ledger, refolded)
        if mismatch is not None:
            entity_id, domain = mismatch
            _LOGGER.error(
                "skill_ledger_mismatch entity_id=%s domain=%s "
                "reason_code=skill_ledger_mismatch",
                entity_id.value,
                domain.value,
            )
            raise ValueError("skill_ledger_mismatch")
        return refolded

    def _skill_level(
        self,
        entity_id: object,
        domain: object,
        *,
        ledger: object,
        tick: Tick,
    ) -> float:
        from world._skills import ObjectiveSkillLedger, SkillDomain
        from world.identifiers import EntityId

        assert type(ledger) is ObjectiveSkillLedger
        assert type(entity_id) is EntityId
        assert type(domain) is SkillDomain
        try:
            return ledger.level(entity_id, domain)
        except ValueError:
            _LOGGER.error(
                "skill_modifier_failed tick=%s entity_id=%s domain=%s "
                "reason_code=missing_domain",
                tick.value,
                entity_id.value,
                domain.value,
            )
            raise ValueError("missing_domain") from None

    def _skill_efficiency_map(self, *, rules: object) -> dict[object, object] | None:
        if self._skill_policy is None or self._skill_ledger is None:
            return None
        from world._skills import (
            SkillDomain,
            SkillEfficiencyOverride,
            adjusted_flee_fatigue,
            adjusted_help_gain,
            adjusted_move_fatigue,
        )
        from world.models import PhysicalRules

        assert type(rules) is PhysicalRules
        overrides: dict[object, object] = {}
        for entity_id in self._skill_entity_ids:
            navigation = self._skill_level(
                entity_id,
                SkillDomain.NAVIGATION,
                ledger=self._skill_ledger,
                tick=self._snapshot.tick,
            )
            healing = self._skill_level(
                entity_id,
                SkillDomain.HEALING,
                ledger=self._skill_ledger,
                tick=self._snapshot.tick,
            )
            overrides[entity_id] = SkillEfficiencyOverride(
                move_fatigue=adjusted_move_fatigue(
                    rules.move_fatigue, navigation, self._skill_policy
                ),
                flee_fatigue=adjusted_flee_fatigue(
                    rules.flee_fatigue, navigation, self._skill_policy
                ),
                help_health_gain=adjusted_help_gain(
                    rules.help_health_gain, healing, self._skill_policy
                ),
            )
        return overrides

    def _log_skill_efficiency(
        self,
        *,
        snap: _EngineSnapshot,
        requests: tuple[ActionRequest, ...],
        rules: object,
    ) -> None:
        if self._skill_policy is None or self._skill_ledger is None:
            return
        from world._skills import SkillDomain

        del rules
        for request in requests:
            if request.actor_id not in self._skill_entity_ids:
                continue
            if type(request.command) is Move or type(request.command) is Flee:
                domain = SkillDomain.NAVIGATION
            elif type(request.command) is Help:
                domain = SkillDomain.HEALING
            else:
                continue
            level = self._skill_level(
                request.actor_id,
                domain,
                ledger=self._skill_ledger,
                tick=snap.tick,
            )
            _LOGGER.debug(
                "skill_modifier tick=%s entity_id=%s domain=%s level=%s outcome=%s",
                snap.tick.value,
                request.actor_id.value,
                domain.value,
                level,
                "efficiency",
            )

    def _resolve_search_effect(
        self,
        *,
        snap: _EngineSnapshot,
        request: ActionRequest,
        request_ordinals: dict[RequestId, tuple[int, AgentId]],
        rules: object,
        starting_state: object,
        skill_ledger: object | None = None,
    ) -> ResolvedSearchEffect | None:
        if type(skill_ledger).__name__ == "CompetenceSelfModel":
            raise TypeError("search resolution accepts only the objective skill ledger")
        if skill_ledger is not None:
            from world._skills import ObjectiveSkillLedger

            if type(skill_ledger) is not ObjectiveSkillLedger:
                raise TypeError("skill_ledger must be ObjectiveSkillLedger")
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
        ledger = self._skill_ledger if skill_ledger is None else skill_ledger
        if (
            self._skill_policy is not None
            and request.actor_id in self._skill_entity_ids
            and ledger is not None
        ):
            from world._skills import SkillDomain, adjusted_search_probability

            foraging = self._skill_level(
                request.actor_id, SkillDomain.FORAGING, ledger=ledger, tick=snap.tick
            )
            detection = self._skill_level(
                request.actor_id,
                SkillDomain.RESOURCE_DETECTION,
                ledger=ledger,
                tick=snap.tick,
            )
            probability = adjusted_search_probability(
                search_base_probability=rules.search_base_probability,
                search_visibility_weight=rules.search_visibility_weight,
                visibility=visibility,
                foraging_level=foraging,
                resource_detection_level=detection,
                policy=self._skill_policy,
            )
            domain = (
                SkillDomain.FORAGING
                if request.command.target_id is None
                else SkillDomain.RESOURCE_DETECTION
            )
            logged_level = foraging if domain is SkillDomain.FORAGING else detection
        else:
            probability = clamp_unit_interval(
                rules.search_base_probability
                + rules.search_visibility_weight * visibility
            )
            domain = None
            logged_level = None
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
        if domain is not None:
            _LOGGER.debug(
                "skill_modifier tick=%s entity_id=%s domain=%s level=%s outcome=%s",
                snap.tick.value,
                request.actor_id.value,
                domain.value,
                logged_level,
                "success" if success else "miss",
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

    def _resolve_production_effect(
        self,
        *,
        snap: _EngineSnapshot,
        request: ActionRequest,
        request_ordinals: dict[RequestId, tuple[int, AgentId]],
        starting_state: object,
    ) -> ResolvedProductionEffect | None:
        """Draw ``production_success`` only when the adjusted chance is below 1."""
        from world._production import (
            adjusted_production_probability,
            block_reason,
            effective_duration,
            skill_domain_for_recipe,
        )
        from world._state import WorldState
        from world.identifiers import RecipeId
        from world.production import ItemProduct

        catalog = self._production_catalog
        if catalog is None:
            return None
        assert type(starting_state) is WorldState
        command = request.command
        recipe_id = getattr(command, "recipe_id", None)
        if type(recipe_id) is not RecipeId:
            raise TypeError("production command requires RecipeId")
        recipe = catalog.recipe(recipe_id)
        if recipe is None:
            return ResolvedProductionEffect(
                request_id=request.request_id,
                recipe_id=recipe_id,
                success=False,
                duration_ticks=1,
                reason_code="unknown_recipe",
            )
        blocked = block_reason(starting_state, request.actor_id, command, recipe)
        duration = effective_duration(starting_state, request.actor_id, recipe)
        if blocked is not None:
            return ResolvedProductionEffect(
                request_id=request.request_id,
                recipe_id=recipe.recipe_id,
                success=False,
                duration_ticks=duration,
                reason_code=blocked,
                recipe=recipe,
            )
        probability = recipe.success_probability
        domain_name = skill_domain_for_recipe(recipe.recipe_id)
        if (
            domain_name is not None
            and self._skill_policy is not None
            and self._skill_ledger is not None
            and request.actor_id in self._skill_entity_ids
        ):
            from world._skills import SkillDomain

            level = self._skill_level(
                request.actor_id,
                SkillDomain(domain_name),
                ledger=self._skill_ledger,
                tick=snap.tick,
            )
            probability = adjusted_production_probability(
                probability,
                level=level,
                probability_gain=self._skill_policy.probability_gain,
            )
            _LOGGER.debug(
                "skill_modifier tick=%s entity_id=%s domain=%s level=%s outcome=%s",
                snap.tick.value,
                request.actor_id.value,
                domain_name,
                level,
                "production",
            )
        success = True
        if probability < 1.0:
            ordinal, agent_id = request_ordinals[request.request_id]
            scope = physical_action_effect_scope(
                config=self._config,
                run_id=self._run_id,
                world_id=self.world_id,
                tick=snap.tick,
                ordinal=ordinal,
                agent_id=agent_id,
                purpose=PHYSICAL_PURPOSE_PRODUCTION_SUCCESS,
            )
            success = sample_bernoulli(
                create_named_stream(self._config, scope), probability
            )
            _LOGGER.debug(
                "production_success_draw tick=%s ordinal=%s request_id=%s success=%s",
                snap.tick.value,
                ordinal,
                request.request_id.value,
                success,
            )
        created_entity_id = None
        if success and _production_creates_entity(
            starting_state, request.actor_id, recipe.output
        ):
            key = (
                "produced-item"
                if type(recipe.output) is ItemProduct
                else "produced-structure"
            )
            created_entity_id = derive_entity_id(
                self._config,
                key,
                self._run_id.value,
                self.world_id.value,
                f"tick:{snap.tick.value}",
                request.request_id.value,
            )
        return ResolvedProductionEffect(
            request_id=request.request_id,
            recipe_id=recipe.recipe_id,
            success=success,
            duration_ticks=duration,
            created_entity_id=created_entity_id,
            recipe=recipe,
        )


def _production_creates_entity(
    state: object, actor_id: EntityId, output: object
) -> bool:
    from world._state import WorldState
    from world.production import (
        ItemProduct,
        ShelterProduct,
        StoreProduct,
        StructureKind,
    )

    assert type(state) is WorldState
    if type(output) is ItemProduct or type(output) is ShelterProduct:
        return True
    if type(output) is not StoreProduct:
        return False
    actor = state.bodies[actor_id]
    return not any(
        structure.location_id == actor.location_id
        and structure.kind is StructureKind.STORE
        for structure in state.structures.values()
    )


def select_checkpoint_schema(
    *, production_active: bool, dynamics_active: bool
) -> tuple[int, str]:
    """Return the legal event-schema and codec pair for this run."""
    from simulation.persistence import (
        EVENT_SCHEMA_VERSION,
        PERSISTENCE_CODEC_VERSION,
        checkpoint_schema_for_production,
    )
    from world.events import EVENT_SCHEMA_REPLAY_V6, EVENT_SCHEMA_REPLAY_V7

    schema_version, codec = checkpoint_schema_for_production(
        production_active=production_active,
        dynamics_active=dynamics_active,
    )
    agreed = (
        dynamics_active
        and schema_version == EVENT_SCHEMA_REPLAY_V7
        and codec == "v4"
    ) or (
        not dynamics_active
        and production_active
        and schema_version == EVENT_SCHEMA_REPLAY_V6
        and codec == "v3"
    ) or (
        not dynamics_active
        and not production_active
        and schema_version == EVENT_SCHEMA_VERSION
        and codec == PERSISTENCE_CODEC_VERSION
    )
    if not agreed:
        _LOGGER.error(
            "unsupported_schema_version schema_version=%s codec=%s",
            schema_version,
            codec,
        )
        raise ValueError("unsupported_schema_version")
    _LOGGER.debug(
        "environment_schema_selected schema_version=%s codec=%s",
        schema_version,
        codec,
    )
    return schema_version, codec


def _optional_environmental_dynamics(value: object | None) -> object | None:
    if value is None:
        return None
    from world.environment import EnvironmentalDynamicsSpec

    if type(value) is not EnvironmentalDynamicsSpec:
        raise TypeError(
            "environmental_dynamics must be EnvironmentalDynamicsSpec or None"
        )
    return value


def _optional_production_catalog(value: object | None) -> object | None:
    if value is None:
        return None
    from world.production import ProductionCatalog

    if type(value) is not ProductionCatalog:
        raise TypeError("production_catalog must be ProductionCatalog or None")
    if value.recipe_count == 0:
        return None
    return value


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
        "production_disabled": ActionResolutionReason.STRUCTURAL_REJECTION,
        "unknown_recipe": ActionResolutionReason.STRUCTURAL_REJECTION,
        "recipe_action_mismatch": ActionResolutionReason.STRUCTURAL_REJECTION,
        "actor_busy": ActionResolutionReason.STRUCTURAL_REJECTION,
        "materials_unavailable": ActionResolutionReason.STRUCTURAL_REJECTION,
        "structure_intact": ActionResolutionReason.STRUCTURAL_REJECTION,
        "shelter_already_present": ActionResolutionReason.STRUCTURAL_REJECTION,
        "store_already_present": ActionResolutionReason.STRUCTURAL_REJECTION,
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
