"""Authoritative deterministic WorldEngine tick state machine.

``WorldEngine`` is the sole public component that advances objective world
state. Private world modules prepare candidates; this engine validates and
commits with one reference swap.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass, replace
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
    AgentRegistration,
    RegistrationTranslator,
    WorldBootstrap,
    _bootstrap_from_snapshot,
    _materialize_projected_world,
    _materialize_world,
    _translator_from_registrations,
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
from world._state import World, rebuild_world_state
from world.actions import (
    ActionRequest,
    Attack,
    Build,
    CopyRecord,
    Craft,
    EstablishRepository,
    Flee,
    Harvest,
    Help,
    Inscribe,
    Move,
    Repair,
    Search,
    Store,
)
from world.effects import (
    ActionCause,
    DeathCause,
    ResolvedActionEffect,
    ResolvedActionEffects,
    ResolvedArtifactCopyEffect,
    ResolvedArtifactInscribeEffect,
    ResolvedAttackEffect,
    ResolvedFleeEffect,
    ResolvedProductionEffect,
    ResolvedRepositoryEstablishEffect,
    ResolvedSearchEffect,
    ResolvedSystemEffects,
    ResolvedWeatherEffect,
    SystemCause,
    SystemEffectFamily,
)
from world.events import (
    AgentCreated,
    AgentEnteredWorld,
    AgentInitializationRecorded,
    CorpseCustodyOpened,
    Died,
    KinshipEdgeRecorded,
    LifecycleStageChanged,
    WorldEvent,
    build_occurrence_context,
    make_physical_replayable_event,
    normalize_events,
)
from world.identifiers import (
    EntityId,
    EventId,
    RequestId,
    WorldId,
    WorldRevision,
    require_exact_nonneg_int,
)
from world.lifecycle import (
    AgentLifecycleRecord,
    OriginProvenance,
    chronological_age,
    default_entrant_body,
    resolve_dependency_status,
    resolve_lifecycle_stage,
)
from world.models import AgentBody, LifeStatus, copy_body, default_physical_rules
from world.observations import (
    Observation,
    ObservationContext,
    ObservedLifecycle,
)
from world.values import Health, WeatherCondition, clamp_unit_interval

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
    registrations: tuple[AgentRegistration, ...] | None = None
    lifecycle_records: tuple[object, ...] | None = None
    translator: RegistrationTranslator | None = None


@dataclass(frozen=True, slots=True)
class PopulationEntryAdmission:
    """Public facts returned after a successful mid-run population admit."""

    agent_id: AgentId
    body_id: EntityId
    location_id: EntityId
    entry_tick: int
    generation_index: int
    cohort_id: str
    provenance: OriginProvenance
    name_prefix: str
    registration: AgentRegistration
    lifecycle_record: AgentLifecycleRecord
    events: tuple[WorldEvent, ...]
    creation_reason: str = "demographic_policy"
    origin_refs: tuple[object, ...] = ()
    creation_config_id: str | None = None


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
        "_artifacts_enabled",
        "_bootstrap",
        "_config",
        "_engine_id",
        "_environmental_dynamics",
        "_experiment_catalog",
        "_dependency_care_spec",
        "_dependency_need_registers",
        "_durable_records_spec",
        "_knowledge_repositories_spec",
        "_kinship_graph",
        "_kinship_spec",
        "_last_tick_result",
        "_lifecycle_records",
        "_new_agent_initialization",
        "_perception",
        "_population_lifecycle",
        "_possession_succession_active",
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
        artifacts_enabled: bool = False,
        population_lifecycle: object | None = None,
        lifecycle_records: Sequence[object] | None = None,
        new_agent_initialization: object | None = None,
        kinship_spec: object | None = None,
        kinship_graph: object | None = None,
        dependency_care_spec: object | None = None,
        durable_records_spec: object | None = None,
        knowledge_repositories_spec: object | None = None,
        experiment_laws: object | None = None,
        possession_succession_active: bool = False,
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
        self._perception = PerceptionService(
            durable_perception_mode=(
                None
                if durable_records_spec is None
                else getattr(durable_records_spec, "perception_mode", "marks_and_meta")
            ),
            repository_perception_mode=(
                None
                if knowledge_repositories_spec is None
                else getattr(
                    knowledge_repositories_spec,
                    "perception_mode",
                    "container_and_meta",
                )
            ),
        )
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
        self._experiment_catalog = _optional_experiment_catalog(
            experiment_laws, self._production_catalog
        )
        if type(possession_succession_active) is not bool:
            raise TypeError("possession_succession_active must be bool")
        self._possession_succession_active = possession_succession_active
        self._environmental_dynamics = _optional_environmental_dynamics(
            environmental_dynamics
        )
        if type(artifacts_enabled) is not bool:
            raise TypeError("artifacts_enabled must be bool")
        # Seeds alone activate artifact admission; explicit flag covers
        # empty-seed tests.
        self._artifacts_enabled = artifacts_enabled or bool(bootstrap.artifacts)
        self._population_lifecycle, self._lifecycle_records = (
            _optional_population_lifecycle(
                population_lifecycle, lifecycle_records=lifecycle_records
            )
        )
        if new_agent_initialization is not None:
            from simulation.new_agent_initialization import NewAgentInitializationSpec

            if type(new_agent_initialization) is not NewAgentInitializationSpec:
                raise TypeError(
                    "new_agent_initialization must be NewAgentInitializationSpec "
                    "or None"
                )
            if self._population_lifecycle is None:
                raise ValueError(
                    "new_agent_initialization requires population_lifecycle "
                    "(code=new_agent_init_requires_lifecycle)"
                )
        self._new_agent_initialization = new_agent_initialization
        from simulation.runner_models import KinshipSpec
        from world.kinship import KinshipGraph

        if kinship_spec is not None and type(kinship_spec) is not KinshipSpec:
            raise TypeError("kinship_spec must be KinshipSpec or None")
        self._kinship_spec = kinship_spec
        if kinship_graph is not None:
            if type(kinship_graph) is not KinshipGraph:
                raise TypeError("kinship_graph must be KinshipGraph or None")
            self._kinship_graph = kinship_graph
        elif kinship_spec is not None:
            self._kinship_graph = KinshipGraph.empty(
                max_parents_per_child=kinship_spec.max_parents_per_child
            )
            if kinship_spec.bootstrap_edges:
                from simulation.runner_models import seed_bootstrap_kinship_graph

                self._kinship_graph = seed_bootstrap_kinship_graph(  # type: ignore[assignment]
                    spec=kinship_spec,
                    registered_agent_ids=tuple(
                        registration.agent_id for registration in self._registrations
                    ),
                )
        else:
            self._kinship_graph = KinshipGraph.empty()
        from simulation.runner_models import DependencyCareSpec

        if dependency_care_spec is not None and type(
            dependency_care_spec
        ) is not DependencyCareSpec:
            raise TypeError("dependency_care_spec must be DependencyCareSpec or None")
        if dependency_care_spec is not None and self._population_lifecycle is None:
            raise ValueError(
                "dependency_care requires population_lifecycle "
                "(code=dependency_care_requires_lifecycle)"
            )
        self._dependency_care_spec = dependency_care_spec
        self._dependency_need_registers: dict[AgentId, object] = {}
        _LOGGER.info(
            "dependency_care_channel dependency_care_active=%s need_count=%s",
            self._dependency_care_spec is not None,
            (
                len(self._dependency_care_spec.enabled_needs)
                if self._dependency_care_spec is not None
                else 0
            ),
        )
        from simulation.runner_models import DurableRecordsSpec

        if durable_records_spec is not None and type(
            durable_records_spec
        ) is not DurableRecordsSpec:
            raise TypeError(
                "durable_records_spec must be DurableRecordsSpec or None"
            )
        self._durable_records_spec = durable_records_spec
        if self._durable_records_spec is not None and not self._artifacts_enabled:
            self._artifacts_enabled = True
            _LOGGER.debug(
                "durable_artifacts_enabled_for_channel "
                "durable_records_active=%s artifacts_enabled=%s",
                True,
                True,
            )
        _LOGGER.info(
            "durable_records_channel durable_records_active=%s genre_count=%s "
            "default_fidelity=%s tombstone_on_destroy=%s",
            self._durable_records_spec is not None,
            (
                len(self._durable_records_spec.enabled_genres)
                if self._durable_records_spec is not None
                else 0
            ),
            (
                self._durable_records_spec.copy_fidelity_policy.default_fidelity
                if self._durable_records_spec is not None
                else "-"
            ),
            (
                self._durable_records_spec.integrity_policy.tombstone_on_destroy
                if self._durable_records_spec is not None
                else False
            ),
        )
        from simulation.runner_models import KnowledgeRepositoriesSpec

        if knowledge_repositories_spec is not None and type(
            knowledge_repositories_spec
        ) is not KnowledgeRepositoriesSpec:
            raise TypeError(
                "knowledge_repositories_spec must be "
                "KnowledgeRepositoriesSpec or None"
            )
        if knowledge_repositories_spec is not None and self._durable_records_spec is None:
            raise ValueError(
                "knowledge_repositories requires durable_records "
                "(code=knowledge_repositories_requires_durable_records)"
            )
        self._knowledge_repositories_spec = knowledge_repositories_spec
        if self._knowledge_repositories_spec is not None and not self._artifacts_enabled:
            self._artifacts_enabled = True
            _LOGGER.debug(
                "repository_artifacts_enabled_for_channel "
                "knowledge_repositories_active=%s artifacts_enabled=%s",
                True,
                True,
            )
        _LOGGER.info(
            "knowledge_repositories_channel knowledge_repositories_active=%s "
            "max_repositories=%s neglect_ticks=%s default_access_mode=%s",
            self._knowledge_repositories_spec is not None,
            (
                self._knowledge_repositories_spec.capacity_policy.max_repositories
                if self._knowledge_repositories_spec is not None
                else 0
            ),
            (
                self._knowledge_repositories_spec.maintenance_policy.neglect_ticks
                if self._knowledge_repositories_spec is not None
                else 0
            ),
            (
                self._knowledge_repositories_spec.access_policy.default_access_mode
                if self._knowledge_repositories_spec is not None
                else "-"
            ),
        )
        _LOGGER.debug(
            "%s world_id=%s revision=%s tick=%s registrations=%s "
            "artifacts_enabled=%s lifecycle_channel=%s "
            "bootstrap_lifecycle_record_count=%s new_agent_provenance=%s "
            "kinship_channel=%s bootstrap_kinship_edge_count=%s "
            "dependency_care_active=%s durable_records_active=%s "
            "knowledge_repositories_active=%s",
            EngineDiagnosticCode.BOOTSTRAP_VALIDATED.value,
            bootstrap.world_id.value,
            bootstrap.revision.value,
            tick.value,
            len(self._registrations),
            self._artifacts_enabled,
            "on" if self._population_lifecycle is not None else "off",
            len(self._lifecycle_records),
            "on" if self._new_agent_initialization is not None else "off",
            "on" if self._kinship_spec is not None else "off",
            len(self._kinship_graph.edges),
            "on" if self._dependency_care_spec is not None else "off",
            "on" if self._durable_records_spec is not None else "off",
            "on" if self._knowledge_repositories_spec is not None else "off",
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
        artifacts_enabled: bool = False,
        population_lifecycle: object | None = None,
        new_agent_initialization: object | None = None,
        kinship_spec: object | None = None,
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
            artifacts=snapshot.artifacts,
            repositories=snapshot.repositories,
            corpse_custody_item_ids=frozenset(snapshot.corpse_custody_item_ids),
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
        # Perception mode rebound after durable_records_spec restore below.
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
        restored_laws = getattr(snapshot.config, "bounded_experimentation", None)
        engine._experiment_catalog = _optional_experiment_catalog(
            None if restored_laws is None else restored_laws.laws,
            engine._production_catalog,
        )
        engine._possession_succession_active = (
            getattr(snapshot.config, "possession_succession", None) is not None
        )
        engine._environmental_dynamics = _optional_environmental_dynamics(
            environmental_dynamics
        )
        if type(artifacts_enabled) is not bool:
            raise TypeError("artifacts_enabled must be bool")
        engine._artifacts_enabled = (
            artifacts_enabled
            or bool(snapshot.artifacts)
            or snapshot.persistence_codec_version
            in {"v5", "v6", "v7", "v8", "v9", "v10", "v11", "v12", "v13"}
            or bool(getattr(engine._bootstrap, "artifacts", ()))
        )
        if snapshot.persistence_codec_version in {
            "v6",
            "v7",
            "v8",
            "v9",
            "v10",
            "v11",
            "v12", "v13",
        }:
            if population_lifecycle is None and snapshot.lifecycle_records:
                raise ValueError(
                    "codec v6/v7/v8/v9 restore requires population_lifecycle "
                    "(code=lifecycle_restore_missing_spec)"
                )
            engine._population_lifecycle, engine._lifecycle_records = (
                _optional_population_lifecycle(
                    population_lifecycle,
                    lifecycle_records=snapshot.lifecycle_records,
                    synthesize_assigned_lifespan=True,
                )
            )
            engine._new_agent_initialization = None
            if new_agent_initialization is not None:
                from simulation.new_agent_initialization import (
                    NewAgentInitializationSpec,
                )

                if type(new_agent_initialization) is not NewAgentInitializationSpec:
                    raise TypeError(
                        "new_agent_initialization must be NewAgentInitializationSpec"
                    )
                if engine._population_lifecycle is None:
                    raise ValueError(
                        "new_agent_initialization requires population_lifecycle "
                        "(code=lifecycle_channel_off)"
                    )
                engine._new_agent_initialization = new_agent_initialization
            elif (
                snapshot.persistence_codec_version
                in {"v7", "v8", "v9", "v10", "v11", "v12", "v13"}
                and snapshot.event_schema_version in {10, 11, 12, 13, 14}
            ):
                # Prefer explicit restore arg; else pull from snapshot config when v25+.
                config_init = getattr(snapshot.config, "new_agent_initialization", None)
                if config_init is not None:
                    engine._new_agent_initialization = config_init
            _LOGGER.debug(
                "lifecycle_restore codec_version=%s lifecycle_record_count=%s "
                "lifecycle_channel=%s new_agent_provenance=%s",
                snapshot.persistence_codec_version,
                len(engine._lifecycle_records),
                "on" if engine._population_lifecycle is not None else "off",
                "on" if engine._new_agent_initialization is not None else "off",
            )
        else:
            engine._population_lifecycle = None
            engine._lifecycle_records = ()
            engine._new_agent_initialization = None
        from simulation.runner_models import KinshipSpec
        from world.kinship import KinshipEdge, KinshipGraph, establish_edge

        engine._kinship_spec = None
        engine._kinship_graph = KinshipGraph.empty()
        engine._dependency_care_spec = None
        engine._durable_records_spec = None
        engine._knowledge_repositories_spec = None
        engine._dependency_need_registers = {}
        if snapshot.persistence_codec_version in {"v10", "v11", "v12", "v13"}:
            from simulation.runner_models import DurableRecordsSpec

            resolved_durable = getattr(snapshot.config, "durable_records", None)
            if resolved_durable is not None and type(resolved_durable) is not DurableRecordsSpec:
                raise TypeError("durable_records must be DurableRecordsSpec or None")
            engine._durable_records_spec = resolved_durable
            if engine._durable_records_spec is not None and not engine._artifacts_enabled:
                engine._artifacts_enabled = True
            _LOGGER.debug(
                "durable_records_restore codec_version=%s durable_records_active=%s",
                snapshot.persistence_codec_version,
                engine._durable_records_spec is not None,
            )
        if snapshot.persistence_codec_version in {"v11", "v12", "v13"}:
            from simulation.runner_models import KnowledgeRepositoriesSpec

            resolved_repos = getattr(snapshot.config, "knowledge_repositories", None)
            if (
                resolved_repos is not None
                and type(resolved_repos) is not KnowledgeRepositoriesSpec
            ):
                raise TypeError(
                    "knowledge_repositories must be KnowledgeRepositoriesSpec or None"
                )
            engine._knowledge_repositories_spec = resolved_repos
            if engine._knowledge_repositories_spec is not None and not engine._artifacts_enabled:
                engine._artifacts_enabled = True
            _LOGGER.debug(
                "knowledge_repositories_restore codec_version=%s "
                "knowledge_repositories_active=%s repository_count=%s",
                snapshot.persistence_codec_version,
                engine._knowledge_repositories_spec is not None,
                len(snapshot.repositories),
            )
        if snapshot.persistence_codec_version in {"v10", "v11", "v12", "v13"}:
            durable_mode = (
                engine._durable_records_spec.perception_mode
                if engine._durable_records_spec is not None
                else None
            )
            repository_mode = (
                engine._knowledge_repositories_spec.perception_mode
                if engine._knowledge_repositories_spec is not None
                else None
            )
            if durable_mode is not None or repository_mode is not None:
                engine._perception = PerceptionService(
                    durable_perception_mode=durable_mode,
                    repository_perception_mode=repository_mode,
                )
        if snapshot.persistence_codec_version in {"v8", "v9", "v10", "v11", "v12", "v13"}:
            resolved_kinship = kinship_spec
            if resolved_kinship is None:
                resolved_kinship = getattr(snapshot.config, "kinship", None)
            if resolved_kinship is not None and type(resolved_kinship) is not KinshipSpec:
                raise TypeError("kinship_spec must be KinshipSpec or None")
            engine._kinship_spec = resolved_kinship
            max_parents = (
                resolved_kinship.max_parents_per_child
                if type(resolved_kinship) is KinshipSpec
                else 2
            )
            graph = KinshipGraph.empty(max_parents_per_child=max_parents)
            known_ids = {
                registration.agent_id for registration in engine._registrations
            }
            for raw_edge in snapshot.kinship_edges:
                if type(raw_edge) is not KinshipEdge:
                    raise TypeError("kinship_edges entries must be KinshipEdge")
                known_ids.add(raw_edge.parent_agent_id)
                known_ids.add(raw_edge.child_agent_id)
                graph, _ = establish_edge(
                    graph,
                    parent_agent_id=raw_edge.parent_agent_id,
                    child_agent_id=raw_edge.child_agent_id,
                    established_tick=raw_edge.established_tick,
                    max_parents_per_child=max_parents,
                    known_agent_ids=known_ids,
                )
            for event in normalized_events:
                details = event.details
                if type(details) is not KinshipEdgeRecorded:
                    continue
                parent = AgentId(details.parent_agent_id)
                child = AgentId(details.child_agent_id)
                known_ids.add(parent)
                known_ids.add(child)
                graph, _ = establish_edge(
                    graph,
                    parent_agent_id=parent,
                    child_agent_id=child,
                    established_tick=details.established_tick,
                    max_parents_per_child=max_parents,
                    known_agent_ids=known_ids,
                )
            engine._kinship_graph = graph
            _LOGGER.debug(
                "kinship_restore codec_version=%s edge_count=%s "
                "kinship_channel=%s events_applied=%s",
                snapshot.persistence_codec_version,
                len(graph.edges),
                "on" if engine._kinship_spec is not None else "off",
                sum(
                    1
                    for event in normalized_events
                    if type(event.details) is KinshipEdgeRecorded
                ),
            )
        if snapshot.persistence_codec_version in {"v9", "v10", "v11", "v12", "v13"}:
            from simulation.runner_models import DependencyCareSpec
            from world.dependency_care import DependencyNeedRegister

            resolved_care = getattr(snapshot.config, "dependency_care", None)
            if resolved_care is not None and type(resolved_care) is not DependencyCareSpec:
                raise TypeError("dependency_care must be DependencyCareSpec or None")
            engine._dependency_care_spec = resolved_care
            registers: dict[AgentId, object] = {}
            for raw_register in snapshot.dependency_need_registers:
                if type(raw_register) is not DependencyNeedRegister:
                    raise TypeError(
                        "dependency_need_registers entries must be DependencyNeedRegister"
                    )
                registers[raw_register.agent_id] = raw_register
            engine._dependency_need_registers = registers
            _LOGGER.debug(
                "dependency_care_restore codec_version=%s register_count=%s "
                "dependency_care_active=%s",
                snapshot.persistence_codec_version,
                len(registers),
                "on" if engine._dependency_care_spec is not None else "off",
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
    def lifecycle_channel_active(self) -> bool:
        return self._population_lifecycle is not None

    def learning_rate_by_entity(self, *, tick: int) -> dict[EntityId, float]:
        """Objective continuous learning-rate factors (entity_id → factor).

        Empty when lifecycle developmental extensions are off or every factor
        is the passthrough ``1.0``. Same map used for skill growth compose.
        """
        raw = self._lifecycle_learning_rate_map(tick=tick)
        if not raw:
            return {}
        return dict(raw)

    @property
    def kinship_channel_active(self) -> bool:
        return self._kinship_spec is not None

    @property
    def dependency_care_channel_active(self) -> bool:
        return self._dependency_care_spec is not None

    @property
    def dependency_care_spec(self) -> object | None:
        return self._dependency_care_spec

    @property
    def durable_records_channel_active(self) -> bool:
        return self._durable_records_spec is not None

    @property
    def durable_records_spec(self) -> object | None:
        return self._durable_records_spec

    @property
    def knowledge_repositories_channel_active(self) -> bool:
        return self._knowledge_repositories_spec is not None

    @property
    def bounded_experimentation_active(self) -> bool:
        return self._experiment_catalog is not None

    @property
    def possession_succession_active(self) -> bool:
        return self._possession_succession_active

    @property
    def knowledge_repositories_spec(self) -> object | None:
        return self._knowledge_repositories_spec

    @property
    def kinship_graph(self) -> object:
        return self._kinship_graph

    def establish_kinship_edge(
        self,
        *,
        parent_agent_id: AgentId,
        child_agent_id: AgentId,
        established_tick: int | None = None,
        emit_event: bool = True,
    ) -> KinshipEdgeRecorded:
        """Establish one objective parent→child edge (WorldEngine authority only).

        Relatedness never implies trust, affection, loyalty, obligation,
        inheritance rights, or group identity — no social/SelfModel writes.
        """
        from simulation.runner_models import KinshipSpec
        from world.kinship import KinshipGraph, establish_edge

        if type(self._kinship_spec) is not KinshipSpec:
            raise ValueError(
                "kinship channel inactive (code=kinship_channel_off)"
            )
        if type(parent_agent_id) is not AgentId or type(child_agent_id) is not AgentId:
            raise TypeError("parent_agent_id and child_agent_id must be AgentId")
        tick = (
            self._snapshot.tick.value
            if established_tick is None
            else require_exact_nonneg_int("established_tick", established_tick)
        )
        known = {registration.agent_id for registration in self._registrations}
        graph = self._kinship_graph
        if type(graph) is not KinshipGraph:
            raise TypeError("kinship_graph must be KinshipGraph")
        next_graph, edge = establish_edge(
            graph,
            parent_agent_id=parent_agent_id,
            child_agent_id=child_agent_id,
            established_tick=tick,
            max_parents_per_child=self._kinship_spec.max_parents_per_child,
            known_agent_ids=known,
        )
        self._kinship_graph = next_graph
        details = KinshipEdgeRecorded(
            parent_agent_id=parent_agent_id.value,
            child_agent_id=child_agent_id.value,
            established_tick=tick,
            edge_id=edge.edge_id,
        )
        _LOGGER.info(
            "kinship_edge_recorded parent_agent_id=%s child_agent_id=%s "
            "tick=%s edge_id=%s",
            parent_agent_id.value,
            child_agent_id.value,
            tick,
            edge.edge_id,
        )
        if emit_event:
            child_body_id = next(
                (
                    registration.entity_id
                    for registration in self._registrations
                    if registration.agent_id == child_agent_id
                ),
                None,
            )
            if child_body_id is None:
                raise ValueError(
                    "child agent not registered (code=kinship_unknown_agent)"
                )
            event_schema, _codec = select_checkpoint_schema(
                production_active=self._production_catalog is not None,
                dynamics_active=self._environmental_dynamics is not None,
                artifacts_active=self._artifacts_enabled,
                lifecycle_active=self.lifecycle_channel_active,
                new_agent_provenance_active=self.new_agent_provenance_active,
                kinship_active=True,
                dependency_care_active=self.dependency_care_channel_active,
                durable_records_active=self.durable_records_channel_active,
                knowledge_repositories_active=self.knowledge_repositories_channel_active,
                bounded_experimentation_active=self.bounded_experimentation_active,
                possession_succession_active=self.possession_succession_active,
            )
            snap = self._snapshot
            same_tick = [
                event for event in snap.event_history if event.tick == tick
            ]
            sequence = len(same_tick)
            origin_location = snap.world.state.bodies[child_body_id].location_id
            cause_id = derive_system_cause_id(
                self._config,
                run_id=self._run_id,
                world_id=self.world_id,
                tick=tick,
                effect_family=SystemEffectFamily.LIFECYCLE.value,
                entity_id=child_body_id,
                family_ordinal=sequence,
            )
            event = make_physical_replayable_event(
                event_id=derive_event_id(
                    self._config,
                    *canonical_system_effect_keys(
                        run_id=self._run_id,
                        world_id=self.world_id,
                        tick=Tick(tick),
                        effect_family=SystemEffectFamily.LIFECYCLE.value,
                        entity_id=child_body_id,
                        family_ordinal=sequence,
                        sequence=0,
                    ),
                ),
                run_id=run_id_for_event(self._run_id),
                world_id=self.world_id,
                tick=tick,
                sequence=sequence,
                cause=SystemCause(
                    cause_id,
                    SystemEffectFamily.LIFECYCLE,
                    child_body_id,
                    sequence,
                ),
                resulting_revision=snap.world.state.revision,
                details=details,
                occurrence=build_occurrence_context(
                    details,
                    origin_location_id=origin_location,
                ),
                schema_version=event_schema,
            )
            self._snapshot = _EngineSnapshot(
                world=snap.world,
                tick=snap.tick,
                phase=snap.phase,
                token=snap.token,
                observation_batch=snap.observation_batch,
                resolution_history=snap.resolution_history,
                event_history=(*snap.event_history, event),
                prior_event_window=(*snap.prior_event_window, event),
            )
        return details

    @property
    def lifecycle_records(self) -> tuple[object, ...]:
        return self._lifecycle_records

    @property
    def population_lifecycle(self) -> object | None:
        return self._population_lifecycle

    @property
    def new_agent_provenance_active(self) -> bool:
        return self._new_agent_initialization is not None

    @property
    def new_agent_initialization(self) -> object | None:
        return self._new_agent_initialization

    @property
    def registration_translator(self) -> RegistrationTranslator:
        """Current ordered registration translator (rebuilds on mid-run admit)."""
        return self._translator

    @property
    def ordered_registrations(self) -> tuple[AgentRegistration, ...]:
        return tuple(self._registrations)

    def admit_population_entry(
        self,
        candidate: object,
        *,
        body: AgentBody | None = None,
    ) -> PopulationEntryAdmission:
        """Admit one mid-run population entry when the lifecycle channel is on.

        Appends body + registration, rebuilds the translator, emits
        ``AgentCreated`` then ``AgentEnteredWorld``, and creates a lifecycle
        record. Flag-off and capacity violations fail closed with stable codes.
        """
        from simulation.demographic_policy import DemographicEntryCandidate
        from simulation.runner_models import PopulationLifecycleSpec

        if self._population_lifecycle is None:
            _LOGGER.error(
                "population_entry_rejected reason_code=lifecycle_channel_off"
            )
            raise RuntimeError(
                "admit_population_entry requires lifecycle channel "
                "(code=lifecycle_channel_off)"
            )
        spec = self._population_lifecycle
        if type(spec) is not PopulationLifecycleSpec:
            raise TypeError("population_lifecycle must be PopulationLifecycleSpec")
        if type(candidate) is not DemographicEntryCandidate:
            raise TypeError("candidate must be DemographicEntryCandidate")
        snap = self._snapshot
        if snap.phase is not EnginePhase.AWAITING_OBSERVATION or snap.token is not None:
            _LOGGER.error(
                "%s reason=admit_wrong_phase phase=%s tick=%s",
                EngineDiagnosticCode.LIFECYCLE_MISUSE.value,
                snap.phase.value,
                snap.tick.value,
            )
            raise RuntimeError(
                "admit_population_entry requires awaiting_observation "
                "(code=lifecycle_admit_wrong_phase)"
            )
        if candidate.provenance is OriginProvenance.BOOTSTRAP:
            _LOGGER.error(
                "population_entry_rejected "
                "reason_code=lifecycle_bootstrap_no_created_event"
            )
            raise ValueError(
                "admit_population_entry forbids bootstrap provenance "
                "(code=lifecycle_bootstrap_no_created_event)"
            )

        living = self._living_registered_population()
        if living >= spec.max_population:
            _LOGGER.error(
                "population_entry_rejected reason_code=population_cap "
                "living=%s max_population=%s",
                living,
                spec.max_population,
            )
            raise ValueError(
                "population cap reached (code=population_cap)"
            )

        state = snap.world.state
        known_agents = {reg.agent_id.value for reg in self._registrations}
        known_bodies = {reg.entity_id.value for reg in self._registrations}
        if (
            candidate.agent_id.value in known_agents
            or candidate.body_id.value in known_bodies
            or candidate.body_id in state.bodies
        ):
            _LOGGER.error(
                "population_entry_rejected reason_code=id_collision agent_id=%s "
                "body_id=%s",
                candidate.agent_id.value,
                candidate.body_id.value,
            )
            raise ValueError(
                "population entry id collision (code=id_collision)"
            )
        if candidate.spawn_location_id not in state.locations:
            _LOGGER.error(
                "population_entry_rejected reason_code=unknown_spawn_location "
                "location_id=%s",
                candidate.spawn_location_id.value,
            )
            raise ValueError(
                "spawn location unknown (code=unknown_spawn_location)"
            )

        entry_tick = snap.tick.value
        stage = resolve_lifecycle_stage(0, spec.stage_thresholds)
        dependency = resolve_dependency_status(
            stage,
            spec.dependent_until_stage,
            stage_order=spec.stage_order,
        )
        prepared = self._prepare_mid_run_entrant(
            candidate=candidate,
            stage=stage,
            dependency=dependency,
            demographic_policy_id=spec.demographic_policy_id,
            explicit_body=body,
            origin_body=None,
        )
        entrant_body = prepared.body
        spawn_location = prepared.location_id
        assert type(entrant_body) is AgentBody

        from simulation.lifespan_distribution import assign_lifespan_ticks

        assigned = assign_lifespan_ticks(
            spec=spec,
            run_config=self._config,
            run_id=self._run_id.value,
            world_id=self.world_id.value,
            agent_id=candidate.agent_id.value,
            entry_tick=entry_tick,
        )
        lifecycle_record = AgentLifecycleRecord(
            body_id=candidate.body_id,
            agent_id=candidate.agent_id.value,
            entry_tick=entry_tick,
            stage=stage,
            dependency_status=dependency,
            generation_index=candidate.generation_index,
            cohort_id=candidate.cohort_id,
            provenance=candidate.provenance,
            assigned_lifespan_ticks=assigned,
        )
        registration = AgentRegistration(
            agent_id=candidate.agent_id,
            entity_id=candidate.body_id,
        )

        bodies = dict(state.bodies)
        bodies[candidate.body_id] = entrant_body
        resulting_revision = WorldRevision(state.revision.value + 1)
        try:
            next_state = rebuild_world_state(
                state, revision=resulting_revision, bodies=bodies
            )
        except ValueError as exc:
            _LOGGER.error(
                "population_entry_rejected reason_code=world_invariant detail=%s",
                type(exc).__name__,
            )
            raise ValueError(
                f"population entry world invariant failed (code=world_invariant): {exc}"
            ) from exc

        event_schema, _codec = select_checkpoint_schema(
            production_active=self._production_catalog is not None,
            dynamics_active=self._environmental_dynamics is not None,
            artifacts_active=self._artifacts_enabled,
            lifecycle_active=True,
            new_agent_provenance_active=self.new_agent_provenance_active,
            kinship_active=self.kinship_channel_active,
            dependency_care_active=self.dependency_care_channel_active,
            durable_records_active=self.durable_records_channel_active,
            knowledge_repositories_active=self.knowledge_repositories_channel_active,
            bounded_experimentation_active=self.bounded_experimentation_active,
            possession_succession_active=self.possession_succession_active,
        )
        next_registrations = (*self._registrations, registration)
        self._registrations = next_registrations
        self._translator = _translator_from_registrations(next_registrations)
        self._lifecycle_records = (*self._lifecycle_records, lifecycle_record)
        detail_seq = self._population_entry_detail_sequence(
            candidate=candidate,
            entry_tick=entry_tick,
            spawn_location=spawn_location,
            prepared=prepared,
        )
        kinship_details = self._establish_admit_kinship_links(
            candidate=candidate,
            entry_tick=entry_tick,
        )
        detail_seq = (*detail_seq, *kinship_details)
        same_tick = [event for event in snap.event_history if event.tick == entry_tick]
        sequence_start = len(same_tick)
        events_list: list[WorldEvent] = []
        for ordinal, details in enumerate(detail_seq):
            cause_id = derive_system_cause_id(
                self._config,
                run_id=self._run_id,
                world_id=self.world_id,
                tick=entry_tick,
                effect_family=SystemEffectFamily.LIFECYCLE.value,
                entity_id=candidate.body_id,
                family_ordinal=ordinal,
            )
            events_list.append(
                make_physical_replayable_event(
                    event_id=derive_event_id(
                        self._config,
                        *canonical_system_effect_keys(
                            run_id=self._run_id,
                            world_id=self.world_id,
                            tick=Tick(entry_tick),
                            effect_family=SystemEffectFamily.LIFECYCLE.value,
                            entity_id=candidate.body_id,
                            family_ordinal=ordinal,
                            sequence=0,
                        ),
                    ),
                    run_id=run_id_for_event(self._run_id),
                    world_id=self.world_id,
                    tick=entry_tick,
                    sequence=sequence_start + ordinal,
                    cause=SystemCause(
                        cause_id,
                        SystemEffectFamily.LIFECYCLE,
                        candidate.body_id,
                        ordinal,
                    ),
                    resulting_revision=resulting_revision,
                    details=details,
                    occurrence=build_occurrence_context(
                        details,
                        origin_location_id=spawn_location,
                    ),
                    schema_version=event_schema,
                )
            )
        events = tuple(events_list)
        self._snapshot = _EngineSnapshot(
            world=World(self.world_id, next_state),
            tick=snap.tick,
            phase=snap.phase,
            token=None,
            observation_batch=None,
            resolution_history=snap.resolution_history,
            event_history=(*snap.event_history, *events),
            prior_event_window=(*snap.prior_event_window, *events),
        )
        _LOGGER.info(
            "population_entry_admitted agent_id=%s body_id=%s tick=%s "
            "population_count=%s provenance=%s creation_reason=%s",
            candidate.agent_id.value,
            candidate.body_id.value,
            entry_tick,
            living + 1,
            candidate.provenance.value,
            prepared.creation_reason,
        )
        _LOGGER.debug(
            "population_entry_events event_count=%s provenance_active=%s "
            "revision=%s registration_count=%s",
            len(events),
            self.new_agent_provenance_active,
            resulting_revision.value,
            len(next_registrations),
        )
        return PopulationEntryAdmission(
            agent_id=candidate.agent_id,
            body_id=candidate.body_id,
            location_id=spawn_location,
            entry_tick=entry_tick,
            generation_index=candidate.generation_index,
            cohort_id=candidate.cohort_id,
            provenance=candidate.provenance,
            name_prefix=candidate.name_prefix,
            registration=registration,
            lifecycle_record=lifecycle_record,
            events=events,
            creation_reason=prepared.creation_reason,
            origin_refs=prepared.origin_refs,
            creation_config_id=prepared.creation_config_id,
        )

    def _prepare_mid_run_entrant(
        self,
        *,
        candidate: object,
        stage: object,
        dependency: object,
        demographic_policy_id: str,
        explicit_body: AgentBody | None,
        origin_body: AgentBody | None,
    ) -> object:
        """Resolve spawn location, body, and provenance facts for one admit."""
        from simulation.demographic_policy import DemographicEntryCandidate
        from simulation.new_agent_initialization import (
            InitialConditionsSummary,
            NewAgentInitializationSpec,
            OriginRef,
            PreparedEntrantBody,
            build_entrant_body_from_init,
            creation_config_fingerprint,
            enforce_spawn_location_for_candidate,
        )

        if type(candidate) is not DemographicEntryCandidate:
            raise TypeError("candidate must be DemographicEntryCandidate")
        init_spec = self._new_agent_initialization
        if init_spec is None:
            spawn_location = candidate.spawn_location_id
            entrant_body = explicit_body
            if entrant_body is None:
                entrant_body = default_entrant_body(
                    body_id=candidate.body_id,
                    location_id=spawn_location,
                )
            elif type(entrant_body) is not AgentBody:
                raise TypeError("body must be AgentBody or None")
            elif entrant_body.entity_id != candidate.body_id:
                raise ValueError(
                    "body.entity_id must match candidate.body_id "
                    "(code=lifecycle_body_id_mismatch)"
                )
            elif entrant_body.location_id != spawn_location:
                raise ValueError(
                    "body.location_id must match candidate.spawn_location_id "
                    "(code=lifecycle_spawn_mismatch)"
                )
            assert type(entrant_body) is AgentBody
            summary = InitialConditionsSummary(
                location_id=spawn_location.value,
                dependency_status=str(getattr(dependency, "value", dependency)),
                stage=str(getattr(stage, "value", stage)),
                health=float(entrant_body.health.value),
                hunger=float(entrant_body.hunger.value),
                thirst=float(entrant_body.thirst.value),
                fatigue=float(entrant_body.fatigue.value),
                temperature=float(entrant_body.temperature.value),
                carry_capacity=float(entrant_body.carry_capacity.value),
            )
            return PreparedEntrantBody(
                body=entrant_body,
                location_id=spawn_location,
                creation_reason=candidate.creation_reason,
                origin_refs=tuple(candidate.origin_refs),
                creation_config_id=candidate.creation_config_id or "lifecycle-default",
                initial_conditions=summary,
                stage=stage,
                dependency_status=dependency,
            )

        if type(init_spec) is not NewAgentInitializationSpec:
            raise TypeError(
                "new_agent_initialization must be NewAgentInitializationSpec"
            )
        _LOGGER.debug(
            "new_agent_init_stage stage=resolve_creation_request agent_id=%s "
            "reason_code=%s",
            candidate.agent_id.value,
            candidate.creation_reason,
        )
        spawn_location = enforce_spawn_location_for_candidate(
            init_spec=init_spec,
            candidate_location_id=candidate.spawn_location_id,
            provenance_is_demographic=(
                candidate.provenance is OriginProvenance.DEMOGRAPHIC_POLICY
            ),
        )
        if explicit_body is not None:
            if type(explicit_body) is not AgentBody:
                raise TypeError("body must be AgentBody or None")
            if explicit_body.entity_id != candidate.body_id:
                raise ValueError(
                    "body.entity_id must match candidate.body_id "
                    "(code=lifecycle_body_id_mismatch)"
                )
            if explicit_body.location_id != spawn_location:
                raise ValueError(
                    "body.location_id must match resolved spawn location "
                    "(code=lifecycle_spawn_mismatch)"
                )
        config_id = candidate.creation_config_id
        if config_id is None:
            config_id = creation_config_fingerprint(
                init_spec, demographic_policy_id=demographic_policy_id
            )
        origin_refs = tuple(candidate.origin_refs)
        if not init_spec.provenance_policy.record_origin_refs:
            origin_refs = ()
        else:
            allowed = frozenset(init_spec.provenance_policy.allowed_roles)
            filtered: list[OriginRef] = []
            for ref in origin_refs:
                if type(ref) is not OriginRef:
                    raise TypeError("origin_refs entries must be OriginRef")
                if ref.role not in allowed:
                    _LOGGER.error(
                        "population_entry_rejected "
                        "reason_code=origin_ref_role_not_allowed role=%s",
                        ref.role,
                    )
                    raise ValueError(
                        f"origin_ref role {ref.role!r} not allowed "
                        "(code=origin_ref_role_not_allowed)"
                    )
                filtered.append(ref)
            origin_refs = tuple(filtered)
        _LOGGER.debug(
            "new_agent_init_stage stage=build_objective_body agent_id=%s "
            "reason_code=%s",
            candidate.agent_id.value,
            candidate.creation_reason,
        )
        if explicit_body is not None:
            assert type(explicit_body) is AgentBody
            summary = InitialConditionsSummary(
                location_id=spawn_location.value,
                dependency_status=str(getattr(dependency, "value", dependency)),
                stage=str(getattr(stage, "value", stage)),
                health=float(explicit_body.health.value),
                hunger=float(explicit_body.hunger.value),
                thirst=float(explicit_body.thirst.value),
                fatigue=float(explicit_body.fatigue.value),
                temperature=float(explicit_body.temperature.value),
                carry_capacity=float(explicit_body.carry_capacity.value),
            )
            return PreparedEntrantBody(
                body=explicit_body,
                location_id=spawn_location,
                creation_reason=candidate.creation_reason,
                origin_refs=origin_refs,
                creation_config_id=config_id,
                initial_conditions=summary,
                stage=stage,
                dependency_status=dependency,
            )
        return build_entrant_body_from_init(
            init_spec=init_spec,
            body_id=candidate.body_id,
            location_id=spawn_location,
            stage=stage,
            dependency_status=dependency,
            creation_reason=candidate.creation_reason,
            origin_refs=origin_refs,
            creation_config_id=config_id,
            origin_body=origin_body,
        )

    def _population_entry_detail_sequence(
        self,
        *,
        candidate: object,
        entry_tick: int,
        spawn_location: EntityId,
        prepared: object,
    ) -> tuple[object, ...]:
        """AgentCreated → optional AgentInitializationRecorded → AgentEnteredWorld."""
        from simulation.demographic_policy import DemographicEntryCandidate
        from simulation.new_agent_initialization import (
            OriginRef,
            PreparedEntrantBody,
        )

        if type(candidate) is not DemographicEntryCandidate:
            raise TypeError("candidate must be DemographicEntryCandidate")
        if type(prepared) is not PreparedEntrantBody:
            raise TypeError("prepared must be PreparedEntrantBody")
        created = AgentCreated(
            body_id=candidate.body_id,
            agent_id=candidate.agent_id.value,
            generation_index=candidate.generation_index,
            cohort_id=candidate.cohort_id,
            provenance=candidate.provenance.value,
        )
        entered = AgentEnteredWorld(
            body_id=candidate.body_id,
            agent_id=candidate.agent_id.value,
            location_id=spawn_location,
            entry_tick=entry_tick,
        )
        if not self.new_agent_provenance_active:
            return (created, entered)
        origin_payload = tuple(
            ref.canonical_payload() if type(ref) is OriginRef else dict(ref)
            for ref in prepared.origin_refs
        )
        recorded = AgentInitializationRecorded(
            body_id=candidate.body_id,
            agent_id=candidate.agent_id.value,
            creation_reason=prepared.creation_reason,
            origin_refs=origin_payload,
            initial_conditions=prepared.initial_conditions.canonical_payload(),
            creation_config_id=prepared.creation_config_id,
        )
        return (created, recorded, entered)

    def _establish_admit_kinship_links(
        self,
        *,
        candidate: object,
        entry_tick: int,
    ) -> tuple[KinshipEdgeRecorded, ...]:
        """Establish mid-run parent links when both kinship + lifecycle channels allow."""
        from simulation.demographic_policy import DemographicEntryCandidate
        from simulation.runner_models import KinshipSpec

        if type(candidate) is not DemographicEntryCandidate:
            raise TypeError("candidate must be DemographicEntryCandidate")
        if not candidate.parent_agent_ids:
            return ()
        if type(self._kinship_spec) is not KinshipSpec:
            raise ValueError(
                "admit parent links require kinship_inheritance "
                "(code=kinship_admit_requires_flag)"
            )
        if self._population_lifecycle is None:
            raise ValueError(
                "admit parent links require generational_population "
                "(code=kinship_admit_requires_lifecycle)"
            )
        policy = self._kinship_spec.admit_link_policy
        if not policy.allow_parent_links_on_admit:
            raise ValueError(
                "admit parent links disabled "
                "(code=kinship_admit_links_disabled)"
            )
        known = {registration.agent_id for registration in self._registrations}
        known.add(candidate.agent_id)
        recorded: list[KinshipEdgeRecorded] = []
        state = self._snapshot.world.state
        for parent_id in candidate.parent_agent_ids:
            if parent_id not in known:
                raise ValueError(
                    f"unknown parent agent {parent_id.value!r} "
                    "(code=kinship_unknown_agent)"
                )
            if policy.require_living_parent:
                parent_reg = next(
                    (
                        registration
                        for registration in self._registrations
                        if registration.agent_id == parent_id
                    ),
                    None,
                )
                if parent_reg is None:
                    raise ValueError(
                        f"unknown parent agent {parent_id.value!r} "
                        "(code=kinship_unknown_agent)"
                    )
                parent_body = state.bodies.get(parent_reg.entity_id)
                if parent_body is None or parent_body.life_status is not LifeStatus.ALIVE:
                    _LOGGER.warning(
                        "kinship_admit_parent_not_living parent=%s child=%s "
                        "reason_code=kinship_parent_not_living",
                        parent_id.value,
                        candidate.agent_id.value,
                    )
                    raise ValueError(
                        f"parent {parent_id.value!r} not living "
                        "(code=kinship_parent_not_living)"
                    )
            details = self.establish_kinship_edge(
                parent_agent_id=parent_id,
                child_agent_id=candidate.agent_id,
                established_tick=entry_tick,
                emit_event=False,
            )
            recorded.append(details)
        return tuple(recorded)

    def _living_registered_population(self) -> int:
        state = self._snapshot.world.state
        living = 0
        for registration in self._registrations:
            body = state.bodies.get(registration.entity_id)
            if body is not None and body.life_status is LifeStatus.ALIVE:
                living += 1
        return living

    def _apply_lifecycle_channel(
        self,
        *,
        snap: _EngineSnapshot,
        working_state: object,
        registrations: tuple[AgentRegistration, ...],
        lifecycle_records: tuple[object, ...],
    ) -> tuple[
        object,
        list[PendingEvent],
        tuple[AgentRegistration, ...],
        tuple[object, ...],
        RegistrationTranslator,
        bool,
        int,
        int,
        int,
    ]:
        """Progress stages / lifespan death, then consult demographic policy."""
        from simulation.demographic_policy import (
            DemographicPopulationSnapshot,
            demographic_policy_for,
        )
        from simulation.runner_models import PopulationLifecycleSpec
        from world._state import WorldState

        if type(working_state) is not WorldState:
            raise TypeError("working_state must be WorldState")
        spec = self._population_lifecycle
        if type(spec) is not PopulationLifecycleSpec:
            raise TypeError("population_lifecycle must be PopulationLifecycleSpec")

        tick = snap.tick.value
        pending: list[PendingEvent] = []
        family_ordinal = 0
        semantic_mutation = False
        stage_changed_count = 0
        lifespan_death_count = 0
        bodies = dict(working_state.bodies)
        records_by_body: dict[str, AgentLifecycleRecord] = {}
        ordered_records: list[AgentLifecycleRecord] = []
        for raw in lifecycle_records:
            if type(raw) is not AgentLifecycleRecord:
                raise TypeError(
                    "lifecycle_records entries must be AgentLifecycleRecord"
                )
            records_by_body[raw.body_id.value] = raw
            ordered_records.append(raw)

        for registration in registrations:
            record = records_by_body.get(registration.entity_id.value)
            if record is None:
                continue
            body = bodies.get(registration.entity_id)
            if body is None or body.life_status is not LifeStatus.ALIVE:
                continue
            age = chronological_age(entry_tick=record.entry_tick, current_tick=tick)
            stage_age = age
            assigned_lifespan = record.assigned_lifespan_ticks
            if spec.natural_death_on_lifespan and age >= assigned_lifespan:
                # Thresholds cover [0, assigned_lifespan-1]; death age is outside.
                stage_age = max(assigned_lifespan - 1, 0)
            stage = resolve_lifecycle_stage(stage_age, spec.stage_thresholds)
            dependency = resolve_dependency_status(
                stage,
                spec.dependent_until_stage,
                stage_order=spec.stage_order,
            )
            if (
                stage.value != record.stage.value
                or dependency is not record.dependency_status
            ):
                previous_stage = record.stage.value
                record = replace(
                    record, stage=stage, dependency_status=dependency
                )
                records_by_body[record.body_id.value] = record
                details = LifecycleStageChanged(
                    body_id=record.body_id,
                    previous_stage=previous_stage,
                    new_stage=stage.value,
                    chronological_age=age,
                    dependency_status=dependency.value,
                )
                _LOGGER.info(
                    "lifecycle_stage_transition body_id=%s age=%s "
                    "previous_stage=%s new_stage=%s assigned_lifespan_ticks=%s",
                    record.body_id.value,
                    age,
                    previous_stage,
                    stage.value,
                    assigned_lifespan,
                )
                cause_id = derive_system_cause_id(
                    self._config,
                    run_id=self._run_id,
                    world_id=self.world_id,
                    tick=tick,
                    effect_family=SystemEffectFamily.LIFECYCLE.value,
                    entity_id=record.body_id,
                    family_ordinal=family_ordinal,
                )
                pending.append(
                    PendingEvent(
                        cause=SystemCause(
                            cause_id,
                            SystemEffectFamily.LIFECYCLE,
                            record.body_id,
                            family_ordinal,
                        ),
                        details=details,
                        occurrence=build_occurrence_context(
                            details, origin_location_id=body.location_id
                        ),
                    )
                )
                family_ordinal += 1
                stage_changed_count += 1

            if spec.natural_death_on_lifespan and age >= assigned_lifespan:
                bodies[registration.entity_id] = copy_body(
                    body,
                    health=Health(0.0),
                    life_status=LifeStatus.DEAD,
                )
                semantic_mutation = True
                _LOGGER.info(
                    "lifecycle_lifespan_death body_id=%s age=%s stage=%s "
                    "assigned_lifespan_ticks=%s",
                    registration.entity_id.value,
                    age,
                    record.stage.value,
                    assigned_lifespan,
                )
                details = Died(
                    body_id=registration.entity_id,
                    death_cause=DeathCause.LIFESPAN,
                )
                cause_id = derive_system_cause_id(
                    self._config,
                    run_id=self._run_id,
                    world_id=self.world_id,
                    tick=tick,
                    effect_family=SystemEffectFamily.LIFECYCLE.value,
                    entity_id=registration.entity_id,
                    family_ordinal=family_ordinal,
                )
                pending.append(
                    PendingEvent(
                        cause=SystemCause(
                            cause_id,
                            SystemEffectFamily.LIFECYCLE,
                            registration.entity_id,
                            family_ordinal,
                        ),
                        details=details,
                        occurrence=build_occurrence_context(
                            details, origin_location_id=body.location_id
                        ),
                    )
                )
                family_ordinal += 1
                if self.possession_succession_active:
                    dead_body = bodies[registration.entity_id]
                    custody = CorpseCustodyOpened(
                        body_id=dead_body.entity_id,
                        location_id=dead_body.location_id,
                        item_ids=tuple(dead_body.inventory),
                    )
                    custody_cause = derive_system_cause_id(
                        self._config,
                        run_id=self._run_id,
                        world_id=self.world_id,
                        tick=tick,
                        effect_family=SystemEffectFamily.LIFECYCLE.value,
                        entity_id=registration.entity_id,
                        family_ordinal=family_ordinal,
                    )
                    pending.append(
                        PendingEvent(
                            cause=SystemCause(
                                custody_cause,
                                SystemEffectFamily.LIFECYCLE,
                                registration.entity_id,
                                family_ordinal,
                            ),
                            details=custody,
                            occurrence=build_occurrence_context(
                                custody, origin_location_id=body.location_id
                            ),
                        )
                    )
                    family_ordinal += 1
                    _LOGGER.info(
                        "corpse_custody_opened body_id=%s item_count=%s",
                        dead_body.entity_id.value,
                        len(dead_body.inventory),
                    )
                    _LOGGER.debug("corpse_custody_opened_cause death_cause=lifespan")
                lifespan_death_count += 1

        next_records = tuple(
            records_by_body[record.body_id.value] for record in ordered_records
        )
        if semantic_mutation or bodies != dict(working_state.bodies):
            working_state = rebuild_world_state(working_state, bodies=bodies)
            semantic_mutation = True

        # Demographic consult after progression / lifespan death.
        policy = demographic_policy_for(spec.demographic_policy_id)
        living = sum(
            1
            for registration in registrations
            if (body := working_state.bodies.get(registration.entity_id)) is not None
            and body.life_status is LifeStatus.ALIVE
        )
        known_agent_ids = frozenset(reg.agent_id.value for reg in registrations)
        known_body_ids = frozenset(reg.entity_id.value for reg in registrations)
        snapshot = DemographicPopulationSnapshot(
            tick=tick,
            living_population=living,
            max_population=spec.max_population,
            known_agent_ids=known_agent_ids,
            known_body_ids=known_body_ids,
        )
        rng = create_named_stream(
            self._config,
            StreamScope(
                namespace="demographic",
                names=(
                    self._run_id.value,
                    self.world_id.value,
                    f"tick:{tick}",
                ),
            ),
        )
        candidates = policy.propose_entries(
            snapshot=snapshot,
            params=spec.demographic_policy_params,
            rng_draw=rng.randrange(1_000_000_000),
        )
        next_registrations = list(registrations)
        next_lifecycle: list[AgentLifecycleRecord] = list(next_records)
        demographic_admit_count = 0
        for candidate in candidates:
            if living >= spec.max_population:
                _LOGGER.error(
                    "population_entry_rejected reason_code=population_cap "
                    "living=%s max_population=%s",
                    living,
                    spec.max_population,
                )
                break
            if (
                candidate.agent_id.value in known_agent_ids
                or candidate.body_id.value in known_body_ids
                or candidate.body_id in working_state.bodies
            ):
                _LOGGER.error(
                    "population_entry_rejected reason_code=id_collision "
                    "agent_id=%s body_id=%s",
                    candidate.agent_id.value,
                    candidate.body_id.value,
                )
                continue
            if candidate.spawn_location_id not in working_state.locations:
                _LOGGER.error(
                    "population_entry_rejected reason_code=unknown_spawn_location "
                    "location_id=%s",
                    candidate.spawn_location_id.value,
                )
                continue
            if candidate.provenance is OriginProvenance.BOOTSTRAP:
                continue

            stage = resolve_lifecycle_stage(0, spec.stage_thresholds)
            dependency = resolve_dependency_status(
                stage,
                spec.dependent_until_stage,
                stage_order=spec.stage_order,
            )
            try:
                prepared = self._prepare_mid_run_entrant(
                    candidate=candidate,
                    stage=stage,
                    dependency=dependency,
                    demographic_policy_id=spec.demographic_policy_id,
                    explicit_body=None,
                    origin_body=None,
                )
            except ValueError as exc:
                _LOGGER.error(
                    "population_entry_rejected reason_code=init_prepare_failed "
                    "detail=%s",
                    type(exc).__name__,
                )
                continue
            from simulation.new_agent_initialization import PreparedEntrantBody

            assert type(prepared) is PreparedEntrantBody
            entrant = prepared.body
            spawn_location = prepared.location_id
            assert type(entrant) is AgentBody
            if spawn_location not in working_state.locations:
                _LOGGER.error(
                    "population_entry_rejected reason_code=unknown_spawn_location "
                    "location_id=%s",
                    spawn_location.value,
                )
                continue
            bodies = dict(working_state.bodies)
            bodies[candidate.body_id] = entrant
            try:
                working_state = rebuild_world_state(working_state, bodies=bodies)
            except ValueError:
                _LOGGER.error(
                    "population_entry_rejected reason_code=world_invariant "
                    "body_id=%s",
                    candidate.body_id.value,
                )
                continue
            semantic_mutation = True
            from simulation.lifespan_distribution import assign_lifespan_ticks

            assigned = assign_lifespan_ticks(
                spec=spec,
                run_config=self._config,
                run_id=self._run_id.value,
                world_id=self.world_id.value,
                agent_id=candidate.agent_id.value,
                entry_tick=tick,
            )
            lifecycle_record = AgentLifecycleRecord(
                body_id=candidate.body_id,
                agent_id=candidate.agent_id.value,
                entry_tick=tick,
                stage=stage,
                dependency_status=dependency,
                generation_index=candidate.generation_index,
                cohort_id=candidate.cohort_id,
                provenance=candidate.provenance,
                assigned_lifespan_ticks=assigned,
            )
            registration = AgentRegistration(
                agent_id=candidate.agent_id,
                entity_id=candidate.body_id,
            )
            detail_seq = self._population_entry_detail_sequence(
                candidate=candidate,
                entry_tick=tick,
                spawn_location=spawn_location,
                prepared=prepared,
            )
            for ordinal_offset, details in enumerate(detail_seq):
                ordinal = family_ordinal + ordinal_offset
                cause_id = derive_system_cause_id(
                    self._config,
                    run_id=self._run_id,
                    world_id=self.world_id,
                    tick=tick,
                    effect_family=SystemEffectFamily.LIFECYCLE.value,
                    entity_id=candidate.body_id,
                    family_ordinal=ordinal,
                )
                pending.append(
                    PendingEvent(
                        cause=SystemCause(
                            cause_id,
                            SystemEffectFamily.LIFECYCLE,
                            candidate.body_id,
                            ordinal,
                        ),
                        details=details,
                        occurrence=build_occurrence_context(
                            details,
                            origin_location_id=spawn_location,
                        ),
                    )
                )
            family_ordinal += len(detail_seq)
            next_registrations.append(registration)
            next_lifecycle.append(lifecycle_record)
            known_agent_ids = frozenset({*known_agent_ids, candidate.agent_id.value})
            known_body_ids = frozenset({*known_body_ids, candidate.body_id.value})
            living += 1
            demographic_admit_count += 1
            _LOGGER.info(
                "population_entry_admitted agent_id=%s body_id=%s tick=%s "
                "population_count=%s provenance=%s creation_reason=%s",
                candidate.agent_id.value,
                candidate.body_id.value,
                tick,
                living,
                candidate.provenance.value,
                prepared.creation_reason,
            )

        regs_tuple = tuple(next_registrations)
        translator = _translator_from_registrations(regs_tuple)
        return (
            working_state,
            pending,
            regs_tuple,
            tuple(next_lifecycle),
            translator,
            semantic_mutation,
            stage_changed_count,
            lifespan_death_count,
            demographic_admit_count,
        )

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
        rules = self._config.physical_rules
        if rules is None:
            rules = default_physical_rules()
        locations = tuple(
            sorted(state.locations.values(), key=lambda item: item.entity_id.value)
        )
        weather = tuple(
            sorted(state.weather.values(), key=lambda item: item.location_id.value)
        )
        from simulation.observer_facts import environment_view

        season, bands, hazards = environment_view(
            spec=self._environmental_dynamics,
            tick=self.tick.value,
            locations=locations,
            weather=weather,
            active_hazards=state.active_hazards,
            rules=rules,
        )
        facts = ObjectiveFacts(
            run_id=self._run_id.value,
            world_id=self.world_id.value,
            tick=self.tick.value,
            revision=self.revision.value,
            locations=locations,
            bodies=self.detached_bodies(),
            items=tuple(
                sorted(state.items.values(), key=lambda item: item.entity_id.value)
            ),
            resources=tuple(
                sorted(state.resources.values(), key=lambda item: item.entity_id.value)
            ),
            weather=weather,
            registrations=tuple(self._registrations),
            structures=tuple(
                sorted(
                    state.structures.values(),
                    key=lambda item: (item.location_id.value, item.entity_id.value),
                )
            ),
            artifacts=tuple(
                sorted(
                    state.artifacts.values(),
                    key=lambda item: item.artifact_id.value,
                )
            ),
            repositories=tuple(
                sorted(
                    state.repositories.values(),
                    key=lambda item: item.repository_id.value,
                )
            ),
            season=season,
            temperature_bands=bands,
            hazards=hazards,
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

    def _observation_context(self, *, tick: int, rules: object) -> ObservationContext:
        lifecycle_by_body = None
        if self._population_lifecycle is not None and self._lifecycle_records:
            from world.lifecycle import AgentLifecycleRecord, chronological_age

            views: dict[EntityId, ObservedLifecycle] = {}
            for raw in self._lifecycle_records:
                if type(raw) is not AgentLifecycleRecord:
                    raise TypeError(
                        "lifecycle_records entries must be AgentLifecycleRecord"
                    )
                views[raw.body_id] = ObservedLifecycle(
                    chronological_age=chronological_age(
                        entry_tick=raw.entry_tick, current_tick=tick
                    ),
                    stage=raw.stage.value,
                    dependency_status=raw.dependency_status.value,
                )
            lifecycle_by_body = views
            _LOGGER.debug(
                "perception_lifecycle_field_count tick=%s count=%s",
                tick,
                len(views),
            )
        kinship_self_by_body = None
        kinship_agent_by_body = None
        from simulation.runner_models import KinshipSpec
        from world.kinship import KinshipGraph, children_of, parents_of
        from world.observations import ObservedKinshipVisible

        if (
            type(self._kinship_spec) is KinshipSpec
            and self._kinship_spec.perception_mode == "self_incident_public"
            and type(self._kinship_graph) is KinshipGraph
        ):
            agent_by_body = {
                registration.entity_id: registration.agent_id.value
                for registration in self._registrations
            }
            body_by_agent = {
                registration.agent_id: registration.entity_id
                for registration in self._registrations
            }
            self_views: dict[EntityId, ObservedKinshipVisible] = {}
            for registration in self._registrations:
                parent_ids = parents_of(
                    self._kinship_graph, registration.agent_id
                )
                child_ids = children_of(
                    self._kinship_graph, registration.agent_id
                )
                # Only include agents still addressable in the registration map.
                parents = tuple(
                    sorted(
                        agent.value
                        for agent in parent_ids
                        if agent in body_by_agent
                    )
                )
                children = tuple(
                    sorted(
                        agent.value
                        for agent in child_ids
                        if agent in body_by_agent
                    )
                )
                if parents or children:
                    self_views[registration.entity_id] = ObservedKinshipVisible(
                        parents=parents,
                        children=children,
                    )
            kinship_self_by_body = self_views
            kinship_agent_by_body = agent_by_body
            _LOGGER.debug(
                "perception_kinship_visible_count tick=%s observer_count=%s "
                "mode=self_incident_public",
                tick,
                len(self_views),
            )
        dependency_needs_by_body = None
        from simulation.runner_models import DependencyCareSpec
        from world.dependency_care import (
            CareNeedId,
            CareNeedPolicy,
            DependencyNeedRegister,
            is_need_critical,
        )
        from world.observations import (
            ObservedDependencyNeed,
            ObservedDependencyNeeds,
        )

        if (
            type(self._dependency_care_spec) is DependencyCareSpec
            and self._dependency_care_spec.perception_mode == "self_and_colocated"
            and lifecycle_by_body is not None
        ):
            spec = self._dependency_care_spec
            policies = spec.to_domain_policies()
            state = self._snapshot.world.state
            need_views: dict[EntityId, ObservedDependencyNeeds] = {}
            for body_id, lifecycle_view in lifecycle_by_body.items():
                body = state.bodies.get(body_id)
                if body is None:
                    continue
                location = state.locations.get(body.location_id)
                shelter = (
                    0.0 if location is None else float(location.shelter_factor.value)
                )
                agent_id = None
                for registration in self._registrations:
                    if registration.entity_id == body_id:
                        agent_id = registration.agent_id
                        break
                register = None
                if agent_id is not None:
                    register = self._dependency_need_registers.get(agent_id)
                rows: list[ObservedDependencyNeed] = []
                for need_name in spec.enabled_needs:
                    need = CareNeedId(need_name)
                    policy = policies.get(need)  # type: ignore[arg-type]
                    if type(policy) is not CareNeedPolicy:
                        continue
                    if need is CareNeedId.FOOD:
                        deficit = min(1.0, max(0.0, body.hunger.value / 100.0))
                    elif need is CareNeedId.WATER:
                        deficit = min(1.0, max(0.0, body.thirst.value / 100.0))
                    elif need is CareNeedId.SAFETY:
                        deficit = min(
                            1.0, max(0.0, 1.0 - (body.health.value / 100.0))
                        )
                    elif need is CareNeedId.SHELTER:
                        deficit = min(1.0, max(0.0, 1.0 - shelter))
                    elif need is CareNeedId.LEARNING:
                        deficit = (
                            float(register.deficit_of(CareNeedId.LEARNING))
                            if type(register) is DependencyNeedRegister
                            else 0.0
                        )
                    elif need is CareNeedId.MOVEMENT:
                        deficit = (
                            float(register.deficit_of(CareNeedId.MOVEMENT))
                            if type(register) is DependencyNeedRegister
                            else 0.0
                        )
                    else:
                        continue
                    rows.append(
                        ObservedDependencyNeed(
                            need_id=need.value,
                            deficit=deficit,
                            critical=is_need_critical(deficit=deficit, policy=policy),
                        )
                    )
                if rows:
                    need_views[body_id] = ObservedDependencyNeeds(needs=tuple(rows))
            dependency_needs_by_body = need_views or None
            _LOGGER.debug(
                "perception_dependency_need_fact_count tick=%s body_count=%s "
                "mode=self_and_colocated",
                tick,
                len(need_views),
            )
        return ObservationContext(
            tick=tick,
            physical_rules=rules,  # type: ignore[arg-type]
            lifecycle_by_body=lifecycle_by_body,
            kinship_self_by_body=kinship_self_by_body,
            kinship_agent_by_body=kinship_agent_by_body,
            dependency_needs_by_body=dependency_needs_by_body,
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
        context = self._observation_context(tick=snap.tick.value, rules=rules)
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
        context = self._observation_context(tick=snap.tick.value, rules=rules)
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
        resolutions, events, candidate_world, next_ledger, roster = (
            self._resolve_ordered(snap=snap, submissions=typed)
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
            registrations=roster[0],
            lifecycle_records=roster[1],
            translator=roster[2],
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
        if candidate.registrations is not None:
            self._registrations = candidate.registrations
        if candidate.lifecycle_records is not None:
            self._lifecycle_records = candidate.lifecycle_records
        if candidate.translator is not None:
            self._translator = candidate.translator
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
    ) -> tuple[
        tuple[ActionResolution, ...],
        tuple[WorldEvent, ...],
        World,
        object | None,
        tuple[
            tuple[AgentRegistration, ...],
            tuple[object, ...],
            RegistrationTranslator,
        ],
    ]:
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
            # Developmental effects are objective/ephemeral only — never write
            # stage/age into SelfModel, identity, or relationship authority.
            effective_carry_capacity=self._lifecycle_effective_carry_capacity(
                tick=snap.tick.value
            ),
            denied_command_kinds_by_entity=self._denied_command_kinds_by_entity(
                tick=snap.tick.value
            ),
            dependency_care_context=self._dependency_care_rule_context(),
            durable_records_context=self._durable_records_rule_context(),
            knowledge_repositories_context=self._knowledge_repositories_rule_context(),
            experiment_catalog=self._experiment_catalog,
            possession_succession_active=self.possession_succession_active,
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
            dep_extras = self._dependency_care_tick_extras(
                state=completion_state, tick=snap.tick.value
            )
            physical = apply_autonomous_physical_step(
                state=completion_state,
                rules=physical_rules,
                tick=snap.tick.value,
                hour=physical_rules.hour_for_tick(snap.tick.value),
                day_phase=physical_rules.day_phase_for_tick(snap.tick.value),
                resolved=system_effects,
                environmental_dynamics=self._environmental_dynamics,
                metabolism_fatigue_by_entity=self._lifecycle_metabolism_fatigue_map(
                    tick=snap.tick.value
                ),
                dependency_hunger_extra_by_entity=dep_extras["hunger"],
                dependency_thirst_extra_by_entity=dep_extras["thirst"],
                dependency_fatigue_extra_by_entity=dep_extras["fatigue"],
                dependency_health_damage_by_entity=dep_extras["health"],
                possession_succession_active=self.possession_succession_active,
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

        working_state = physical.working_state
        semantic_mutation = (
            action_pending.semantic_mutation
            or physical.semantic_mutation
            or completion_state is not action_pending.working_state
        )
        lifecycle_pending: list[PendingEvent] = []
        next_registrations = tuple(self._registrations)
        next_lifecycle_records = tuple(self._lifecycle_records)
        next_translator = self._translator
        if self._population_lifecycle is not None:
            (
                working_state,
                lifecycle_pending,
                next_registrations,
                next_lifecycle_records,
                next_translator,
                life_mutation,
                stage_changed_count,
                lifespan_death_count,
                demographic_admit_count,
            ) = self._apply_lifecycle_channel(
                snap=snap,
                working_state=working_state,
                registrations=next_registrations,
                lifecycle_records=next_lifecycle_records,
            )
            semantic_mutation = semantic_mutation or life_mutation
            _LOGGER.debug(
                "lifecycle_tick_applied tick=%s stage_changed=%s "
                "lifespan_death=%s demographic_admit=%s",
                snap.tick.value,
                stage_changed_count,
                lifespan_death_count,
                demographic_admit_count,
            )

        repository_pending: list[PendingEvent] = []
        if self.knowledge_repositories_channel_active:
            working_state, repository_pending, repo_mutation = (
                self._apply_repository_neglect_channel(
                    snap=snap, working_state=working_state
                )
            )
            semantic_mutation = semantic_mutation or repo_mutation

        merged = PendingBatch(
            working_state=working_state,
            semantic_mutation=semantic_mutation,
            outcomes=action_pending.outcomes,
            pending_events=(
                action_pending.pending_events
                + tuple(production_pending)
                + tuple(system_pending)
                + tuple(lifecycle_pending)
                + tuple(repository_pending)
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
            artifacts_active=self._artifacts_enabled,
            lifecycle_active=self.lifecycle_channel_active,
            new_agent_provenance_active=self.new_agent_provenance_active,
            kinship_active=self.kinship_channel_active,
            dependency_care_active=self.dependency_care_channel_active,
            durable_records_active=self.durable_records_channel_active,
            knowledge_repositories_active=self.knowledge_repositories_channel_active,
            bounded_experimentation_active=self.bounded_experimentation_active,
            possession_succession_active=self.possession_succession_active,
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
                "artifact_created",
                "artifact_modified",
                "artifact_moved",
                "artifact_destroyed",
            }:
                _LOGGER.info(
                    "artifact_event_committed event_id=%s tick=%s kind=%s",
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
        roster = (next_registrations, next_lifecycle_records, next_translator)
        return (
            tuple(resolutions),
            prepared.events,
            candidate_world,
            folded_ledger,
            roster,
        )

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
            learning_rate_by_entity=self._lifecycle_learning_rate_map(
                tick=snap.tick.value
            ),
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
            elif type(command) is Inscribe:
                by_request[request.request_id] = self._resolve_artifact_inscribe_effect(
                    snap=snap,
                    request=request,
                )
            elif type(command) is CopyRecord:
                by_request[request.request_id] = self._resolve_artifact_copy_effect(
                    snap=snap,
                    request=request,
                )
            elif type(command) is EstablishRepository:
                by_request[request.request_id] = (
                    self._resolve_repository_establish_effect(
                        snap=snap,
                        request=request,
                    )
                )
        return ResolvedActionEffects(by_request=by_request)

    def _resolve_artifact_inscribe_effect(
        self,
        *,
        snap: _EngineSnapshot,
        request: ActionRequest,
    ) -> ResolvedArtifactInscribeEffect:
        created_artifact_id = derive_entity_id(
            self._config,
            "information-artifact",
            self._run_id.value,
            self.world_id.value,
            f"tick:{snap.tick.value}",
            request.request_id.value,
        )
        _LOGGER.debug(
            "artifact_inscribe_id tick=%s request_id=%s artifact_id=%s",
            snap.tick.value,
            request.request_id.value,
            created_artifact_id.value,
        )
        return ResolvedArtifactInscribeEffect(
            request_id=request.request_id,
            created_artifact_id=created_artifact_id,
        )

    def _resolve_artifact_copy_effect(
        self,
        *,
        snap: _EngineSnapshot,
        request: ActionRequest,
    ) -> ResolvedArtifactCopyEffect:
        from simulation.randomness import StreamScope, create_named_stream
        from simulation.runner_models import DurableRecordsSpec
        from world.actions import CopyRecord as CopyRecordCommand
        from world.artifacts import ArtifactContent
        from world.durable_copy import apply_copy_fidelity

        created_artifact_id = derive_entity_id(
            self._config,
            "information-artifact-copy",
            self._run_id.value,
            self.world_id.value,
            f"tick:{snap.tick.value}",
            request.request_id.value,
        )
        command = request.command
        assert type(command) is CopyRecordCommand
        parent = snap.world.state.artifacts.get(command.artifact_id)
        parent_content = (
            parent.content if parent is not None else ArtifactContent()
        )
        fidelity = "perfect"
        max_mark_edits = 0
        max_relation_edits = 0
        rng = None
        if type(self._durable_records_spec) is DurableRecordsSpec:
            spec = self._durable_records_spec
            fidelity = (
                command.fidelity_override
                if command.fidelity_override is not None
                else spec.copy_fidelity_policy.default_fidelity
            )
            max_mark_edits = spec.copy_fidelity_policy.max_mark_edits
            max_relation_edits = spec.copy_fidelity_policy.max_relation_edits
            if fidelity != "perfect":
                rng = create_named_stream(
                    self._config,
                    StreamScope(
                        namespace=spec.rng_namespace,
                        names=(
                            self._run_id.value,
                            self.world_id.value,
                            f"tick:{snap.tick.value}",
                            request.request_id.value,
                            command.artifact_id.value,
                            "copy_fidelity",
                        ),
                    ),
                )
        fidelity_result = apply_copy_fidelity(
            parent_content,
            fidelity_mode=fidelity,
            max_mark_edits=max_mark_edits,
            max_relation_edits=max_relation_edits,
            rng=rng,
        )
        _LOGGER.debug(
            "artifact_copy_id tick=%s request_id=%s artifact_id=%s "
            "fidelity=%s mark_edits=%s relation_edits=%s",
            snap.tick.value,
            request.request_id.value,
            created_artifact_id.value,
            fidelity_result.fidelity_mode,
            fidelity_result.mark_edit_count,
            fidelity_result.relation_edit_count,
        )
        return ResolvedArtifactCopyEffect(
            request_id=request.request_id,
            created_artifact_id=created_artifact_id,
            child_content=fidelity_result.content,
            fidelity_mode=fidelity_result.fidelity_mode,
            mark_edit_count=fidelity_result.mark_edit_count,
            relation_edit_count=fidelity_result.relation_edit_count,
        )

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

    def _lifecycle_continuous_factors(
        self, *, entity_id: EntityId, tick: int
    ) -> object:
        """Resolve continuous developmental factors for one body (passthrough=1.0)."""
        from world.lifecycle import AgentLifecycleRecord, chronological_age
        from world.lifecycle_effects import (
            PASSTHROUGH_CONTINUOUS_FACTORS,
            interpolate_continuous_factors,
        )

        if self._population_lifecycle is None:
            return PASSTHROUGH_CONTINUOUS_FACTORS
        record = None
        for raw in self._lifecycle_records:
            if type(raw) is AgentLifecycleRecord and raw.body_id == entity_id:
                record = raw
                break
        if record is None:
            return PASSTHROUGH_CONTINUOUS_FACTORS
        age = chronological_age(entry_tick=record.entry_tick, current_tick=tick)
        # Effects cover ages through assigned_lifespan-1 (EOL age is outside).
        stage_age = min(age, max(record.assigned_lifespan_ticks - 1, 0))
        return interpolate_continuous_factors(
            stage_age,
            self._population_lifecycle.stage_thresholds,
            self._population_lifecycle.stage_capability_effects,
            enabled=(
                self._population_lifecycle.gradual_aging.intra_stage_interpolation
            ),
        )

    def _lifecycle_effective_carry_capacity(
        self, *, tick: int
    ) -> dict[EntityId, int] | None:
        """Ephemeral capacity map; None when lifecycle channel off (bit-identical)."""
        if self._population_lifecycle is None:
            return None
        if not self._population_lifecycle.has_developmental_extensions():
            # Passthrough factors: omit map so capacity checks use stored values.
            if len(self._population_lifecycle.stage_capability_effects) == 0:
                return None
        from world.lifecycle import AgentLifecycleRecord

        result: dict[EntityId, int] = {}
        bodies = self._snapshot.world.state.bodies
        for raw in self._lifecycle_records:
            if type(raw) is not AgentLifecycleRecord:
                continue
            body = bodies.get(raw.body_id)
            if body is None:
                continue
            factors = self._lifecycle_continuous_factors(
                entity_id=raw.body_id, tick=tick
            )
            factor = float(factors.physical_capacity_factor)  # type: ignore[attr-defined]
            if factor == 1.0:
                continue
            effective = max(0, round(body.carry_capacity.value * factor))
            result[raw.body_id] = effective
            _LOGGER.debug(
                "lifecycle_capacity_factor body_id=%s stage=%s factor=%s "
                "effective_capacity=%s reason_code=ephemeral_capacity",
                raw.body_id.value,
                raw.stage.value,
                factor,
                effective,
            )
        return result or None

    def _lifecycle_denied_command_kinds(
        self, *, tick: int
    ) -> dict[EntityId, frozenset[str]] | None:
        if self._population_lifecycle is None:
            return None
        if len(self._population_lifecycle.stage_capability_effects) == 0:
            return None
        from world.lifecycle import AgentLifecycleRecord
        from world.lifecycle_effects import resolve_stage_effect

        del tick  # denies stay discrete by current stage on the record
        result: dict[EntityId, frozenset[str]] = {}
        for raw in self._lifecycle_records:
            if type(raw) is not AgentLifecycleRecord:
                continue
            effect = resolve_stage_effect(
                raw.stage, self._population_lifecycle.stage_capability_effects
            )
            if effect.denied_command_kinds:
                result[raw.body_id] = frozenset(effect.denied_command_kinds)
        return result or None

    def _dependency_care_tick_extras(
        self, *, state: object, tick: int
    ) -> dict[str, dict[EntityId, float] | None]:
        """Accumulate DEPENDENT unmet-need extras and update need registers."""
        from simulation.runner_models import DependencyCareSpec
        from world.dependency_care import (
            CareNeedId,
            DependencyNeedRegister,
            compute_unmet_tick_effects,
            empty_need_register,
        )
        from world.lifecycle import AgentLifecycleRecord, DependencyStatus
        from world._production import shelter_factor_for

        empty: dict[str, dict[EntityId, float] | None] = {
            "hunger": None,
            "thirst": None,
            "fatigue": None,
            "health": None,
        }
        if type(self._dependency_care_spec) is not DependencyCareSpec:
            return empty
        spec = self._dependency_care_spec
        policies = spec.to_domain_policies()
        enabled = tuple(CareNeedId(need) for need in spec.enabled_needs)
        hunger_map: dict[EntityId, float] = {}
        thirst_map: dict[EntityId, float] = {}
        fatigue_map: dict[EntityId, float] = {}
        health_map: dict[EntityId, float] = {}
        bodies = getattr(state, "bodies", {})
        locations = getattr(state, "locations", {})
        for raw in self._lifecycle_records:
            if type(raw) is not AgentLifecycleRecord:
                continue
            if raw.dependency_status is not DependencyStatus.DEPENDENT:
                continue
            body = bodies.get(raw.body_id)
            if body is None or body.life_status.value != "alive":
                continue
            location = locations.get(body.location_id)
            shelter = 1.0
            if location is not None:
                shelter = float(
                    shelter_factor_for(
                        state, body.location_id, location.shelter_factor.value
                    )
                )
            agent_id = AgentId(raw.agent_id)
            register = self._dependency_need_registers.get(agent_id)
            if type(register) is not DependencyNeedRegister:
                register = empty_need_register(agent_id)
            effect = compute_unmet_tick_effects(
                body_id=raw.body_id,
                status=DependencyStatus.DEPENDENT,
                enabled_needs=enabled,
                policies=policies,  # type: ignore[arg-type]
                hunger=float(body.hunger.value),
                thirst=float(body.thirst.value),
                health=float(body.health.value),
                fatigue=float(body.fatigue.value),
                shelter_factor=shelter,
                learning_deficit=register.deficit_of(CareNeedId.LEARNING),
                movement_deficit=register.deficit_of(CareNeedId.MOVEMENT),
            )
            if effect.hunger_extra:
                hunger_map[raw.body_id] = effect.hunger_extra
            if effect.thirst_extra:
                thirst_map[raw.body_id] = effect.thirst_extra
            if effect.fatigue_extra:
                fatigue_map[raw.body_id] = effect.fatigue_extra
            if effect.health_damage_extra:
                health_map[raw.body_id] = effect.health_damage_extra
            next_register = register
            if effect.learning_deficit_delta:
                next_register = next_register.with_deficit(
                    CareNeedId.LEARNING,
                    register.deficit_of(CareNeedId.LEARNING)
                    + effect.learning_deficit_delta,
                )
            if effect.movement_deficit_delta:
                next_register = next_register.with_deficit(
                    CareNeedId.MOVEMENT,
                    next_register.deficit_of(CareNeedId.MOVEMENT)
                    + effect.movement_deficit_delta,
                )
            self._dependency_need_registers[agent_id] = next_register
            _LOGGER.debug(
                "dependency_care_unmet tick=%s agent_id=%s hunger_extra=%s "
                "thirst_extra=%s learning_deficit=%s",
                tick,
                agent_id.value,
                effect.hunger_extra,
                effect.thirst_extra,
                (
                    next_register.deficit_of(CareNeedId.LEARNING)
                    if type(next_register) is DependencyNeedRegister
                    else 0.0
                ),
            )
        return {
            "hunger": hunger_map or None,
            "thirst": thirst_map or None,
            "fatigue": fatigue_map or None,
            "health": health_map or None,
        }

    def _dependency_care_denied_command_kinds(
        self,
    ) -> dict[EntityId, dict[str, str]] | None:
        """DEPENDENT self-satisfy denials (union with stage denies at admission)."""
        from simulation.runner_models import DependencyCareSpec
        from world.dependency_care import (
            CareNeedId,
            self_satisfy_denied_kinds,
        )
        from world.lifecycle import AgentLifecycleRecord, DependencyStatus

        if type(self._dependency_care_spec) is not DependencyCareSpec:
            return None
        spec = self._dependency_care_spec
        policies = spec.to_domain_policies()
        enabled = tuple(CareNeedId(need) for need in spec.enabled_needs)
        result: dict[EntityId, dict[str, str]] = {}
        for raw in self._lifecycle_records:
            if type(raw) is not AgentLifecycleRecord:
                continue
            if raw.dependency_status is not DependencyStatus.DEPENDENT:
                continue
            denied = self_satisfy_denied_kinds(
                DependencyStatus.DEPENDENT,
                enabled,
                policies,  # type: ignore[arg-type]
            )
            if not denied:
                continue
            reason_map = {
                kind: "dependency_care_self_satisfy_denied" for kind in sorted(denied)
            }
            result[raw.body_id] = reason_map
            _LOGGER.debug(
                "dependency_care_self_satisfy_denied body_id=%s kinds=%s "
                "code=dependency_care_self_satisfy_denied",
                raw.body_id.value,
                sorted(denied),
            )
        return result or None

    def _dependency_care_rule_context(self) -> object | None:
        """Build ephemeral Feed/Transport legality context for this tick."""
        from simulation.runner_models import DependencyCareSpec
        from world.dependency_care import DependencyCareRuleContext
        from world.lifecycle import AgentLifecycleRecord, DependencyStatus

        if type(self._dependency_care_spec) is not DependencyCareSpec:
            return None
        spec = self._dependency_care_spec
        dependent_ids: set[EntityId] = set()
        for raw in self._lifecycle_records:
            if type(raw) is not AgentLifecycleRecord:
                continue
            if raw.dependency_status is DependencyStatus.DEPENDENT:
                dependent_ids.add(raw.body_id)
        policy = spec.care_action_policy
        return DependencyCareRuleContext(
            dependent_body_ids=frozenset(dependent_ids),
            allow_feed=policy.allow_feed,
            allow_transport=policy.allow_transport,
            require_colocated=policy.require_colocated,
        )

    def _durable_records_rule_context(self) -> object | None:
        """Build ephemeral durable-record legality context for this tick."""
        from simulation.runner_models import DurableRecordsSpec
        from world.artifacts import DurableRecordsRuleContext

        if type(self._durable_records_spec) is not DurableRecordsSpec:
            return None
        spec = self._durable_records_spec
        return DurableRecordsRuleContext(
            enabled_genres=frozenset(spec.enabled_genres),
            default_fidelity=spec.copy_fidelity_policy.default_fidelity,
            max_mark_edits=spec.copy_fidelity_policy.max_mark_edits,
            max_relation_edits=spec.copy_fidelity_policy.max_relation_edits,
            preserve_genre=spec.copy_fidelity_policy.preserve_genre,
            copy_requires_hold_or_colocation=(
                spec.copy_fidelity_policy.copy_requires_hold_or_colocation
            ),
            allow_damage=spec.integrity_policy.allow_damage,
            allow_partial_loss=spec.integrity_policy.allow_partial_loss,
            tombstone_on_destroy=spec.integrity_policy.tombstone_on_destroy,
            partial_loss_min_marks_remaining=(
                spec.integrity_policy.partial_loss_min_marks_remaining
            ),
            max_annotations_per_record=(
                spec.annotation_policy.max_annotations_per_record
            ),
            max_copy_generation=spec.lineage_policy.max_copy_generation,
            destroyed_parent_blocks_copy=(
                spec.lineage_policy.destroyed_parent_blocks_copy
            ),
        )

    def _knowledge_repositories_rule_context(self) -> object | None:
        """Build ephemeral knowledge-repository legality context for this tick."""
        from simulation.runner_models import KnowledgeRepositoriesSpec
        from world.repositories import KnowledgeRepositoriesRuleContext

        if type(self._knowledge_repositories_spec) is not KnowledgeRepositoriesSpec:
            return None
        spec = self._knowledge_repositories_spec
        return KnowledgeRepositoriesRuleContext(
            default_access_mode=spec.access_policy.default_access_mode,
            deposit_requires_colocation=spec.access_policy.deposit_requires_colocation,
            retrieve_requires_colocation=(
                spec.access_policy.retrieve_requires_colocation
            ),
            founder_list_survives_death=(
                spec.access_policy.founder_list_survives_death
            ),
            max_repositories=spec.capacity_policy.max_repositories,
            max_members_per_repository=(
                spec.capacity_policy.max_members_per_repository
            ),
            max_index_entries=spec.capacity_policy.max_index_entries,
            neglect_ticks=spec.maintenance_policy.neglect_ticks,
            allow_destruction=spec.maintenance_policy.allow_destruction,
            inaccessible_blocks_access=(
                spec.maintenance_policy.inaccessible_blocks_access
            ),
            neglect_corrupts_index=spec.maintenance_policy.neglect_corrupts_index,
            index_optional=spec.index_policy.index_optional,
            max_entries_per_index_op=spec.index_policy.max_entries_per_index_op,
            allow_corrupt_entries=spec.index_policy.allow_corrupt_entries,
        )

    def mark_repository_inaccessible(
        self,
        repository_id: EntityId,
        *,
        reason_code: str = "repository_location_sealed",
    ) -> None:
        """Experiment helper: seal a repository as inaccessible (channel-on only)."""
        from simulation.runner_models import KnowledgeRepositoriesSpec
        from world.repositories import KnowledgeRepository, RepositoryStatus

        if type(self._knowledge_repositories_spec) is not KnowledgeRepositoriesSpec:
            raise ValueError(
                "knowledge_repositories_inactive "
                "(code=knowledge_repositories_inactive)"
            )
        if type(repository_id) is not EntityId:
            raise TypeError("repository_id must be EntityId")
        if type(reason_code) is not str or not reason_code:
            raise ValueError("reason_code must be a non-empty str")
        snap = self._snapshot
        repository = snap.world.state.repositories.get(repository_id)
        if repository is None:
            raise ValueError(
                f"unknown repository {repository_id.value!r} "
                "(code=unknown_repository)"
            )
        if repository.status is RepositoryStatus.DESTROYED:
            raise ValueError(
                f"repository {repository_id.value!r} destroyed "
                "(code=repository_destroyed)"
            )
        updated = KnowledgeRepository(
            repository_id=repository.repository_id,
            location_id=repository.location_id,
            founder_ids=repository.founder_ids,
            established_tick=repository.established_tick,
            access_mode=repository.access_mode,
            status=RepositoryStatus.INACCESSIBLE,
            structure_id=repository.structure_id,
            member_artifact_ids=repository.member_artifact_ids,
            index_entries=repository.index_entries,
            last_maintained_tick=repository.last_maintained_tick,
            neglect_streak=repository.neglect_streak,
        )
        repositories = dict(snap.world.state.repositories)
        repositories[repository_id] = updated
        next_state = rebuild_world_state(snap.world.state, repositories=repositories)
        self._snapshot = _EngineSnapshot(
            world=World(self.world_id, next_state),
            tick=snap.tick,
            phase=snap.phase,
            token=snap.token,
            observation_batch=snap.observation_batch,
            resolution_history=snap.resolution_history,
            event_history=snap.event_history,
            prior_event_window=snap.prior_event_window,
        )
        _LOGGER.info(
            "repository_marked_inaccessible repository_id=%s status=%s "
            "reason_code=%s",
            repository_id.value,
            RepositoryStatus.INACCESSIBLE.value,
            reason_code,
        )

    def clear_repository_inaccessible(self, repository_id: EntityId) -> None:
        """Experiment helper: clear inaccessible status back to intact."""
        from simulation.runner_models import KnowledgeRepositoriesSpec
        from world.repositories import KnowledgeRepository, RepositoryStatus

        if type(self._knowledge_repositories_spec) is not KnowledgeRepositoriesSpec:
            raise ValueError(
                "knowledge_repositories_inactive "
                "(code=knowledge_repositories_inactive)"
            )
        if type(repository_id) is not EntityId:
            raise TypeError("repository_id must be EntityId")
        snap = self._snapshot
        repository = snap.world.state.repositories.get(repository_id)
        if repository is None:
            raise ValueError(
                f"unknown repository {repository_id.value!r} "
                "(code=unknown_repository)"
            )
        if repository.status is not RepositoryStatus.INACCESSIBLE:
            raise ValueError(
                f"repository {repository_id.value!r} not inaccessible "
                "(code=repository_not_inaccessible)"
            )
        updated = KnowledgeRepository(
            repository_id=repository.repository_id,
            location_id=repository.location_id,
            founder_ids=repository.founder_ids,
            established_tick=repository.established_tick,
            access_mode=repository.access_mode,
            status=RepositoryStatus.INTACT,
            structure_id=repository.structure_id,
            member_artifact_ids=repository.member_artifact_ids,
            index_entries=repository.index_entries,
            last_maintained_tick=repository.last_maintained_tick,
            neglect_streak=repository.neglect_streak,
        )
        repositories = dict(snap.world.state.repositories)
        repositories[repository_id] = updated
        next_state = rebuild_world_state(snap.world.state, repositories=repositories)
        self._snapshot = _EngineSnapshot(
            world=World(self.world_id, next_state),
            tick=snap.tick,
            phase=snap.phase,
            token=snap.token,
            observation_batch=snap.observation_batch,
            resolution_history=snap.resolution_history,
            event_history=snap.event_history,
            prior_event_window=snap.prior_event_window,
        )
        _LOGGER.info(
            "repository_inaccessible_cleared repository_id=%s status=%s",
            repository_id.value,
            RepositoryStatus.INTACT.value,
        )

    def _apply_repository_neglect_channel(
        self,
        *,
        snap: _EngineSnapshot,
        working_state: object,
    ) -> tuple[object, list[PendingEvent], bool]:
        """Advance neglect timers and emit RepositoryNeglected system events."""
        from simulation.runner_models import KnowledgeRepositoriesSpec
        from world._state import WorldState
        from world.events import RepositoryNeglected, build_occurrence_context
        from world.repositories import advance_repository_neglect

        if type(working_state) is not WorldState:
            raise TypeError("working_state must be WorldState")
        if type(self._knowledge_repositories_spec) is not KnowledgeRepositoriesSpec:
            return working_state, [], False
        spec = self._knowledge_repositories_spec
        tick = snap.tick.value
        pending: list[PendingEvent] = []
        repositories = dict(working_state.repositories)
        semantic_mutation = False
        family_ordinal = 0
        for repository_id in sorted(
            repositories.keys(), key=lambda value: value.value
        ):
            repository = repositories[repository_id]
            drop_entry_index: int | None = None
            # Corrupt index only on neglect onset (intact → neglected).
            if (
                spec.maintenance_policy.neglect_corrupts_index
                and repository.index_entries
                and repository.status.value == "intact"
            ):
                rng = create_named_stream(
                    self._config,
                    StreamScope(
                        namespace=spec.rng_namespace,
                        names=(
                            self._run_id.value,
                            self.world_id.value,
                            f"tick:{tick}",
                            repository_id.value,
                            "index_drop",
                        ),
                    ),
                )
                drop_entry_index = int(rng.randrange(len(repository.index_entries)))
            transition = advance_repository_neglect(
                repository,
                tick=tick,
                neglect_ticks=spec.maintenance_policy.neglect_ticks,
                neglect_corrupts_index=spec.maintenance_policy.neglect_corrupts_index,
                drop_entry_index=drop_entry_index,
            )
            if transition is None:
                continue
            repositories[repository_id] = transition.next_repository
            semantic_mutation = True
            if transition.prior_status is not transition.next_status:
                _LOGGER.info(
                    "repository_status_transition repository_id=%s "
                    "prior_status=%s next_status=%s neglect_streak=%s",
                    repository_id.value,
                    transition.prior_status.value,
                    transition.next_status.value,
                    transition.neglect_streak,
                )
            details = RepositoryNeglected(
                repository_id=repository_id,
                neglect_streak=transition.neglect_streak,
                prior_status=transition.prior_status.value,
                next_status=transition.next_status.value,
                index_entries_dropped=transition.index_entries_dropped,
            )
            cause_id = derive_system_cause_id(
                self._config,
                run_id=self._run_id,
                world_id=self.world_id,
                tick=tick,
                effect_family=SystemEffectFamily.KNOWLEDGE_REPOSITORY.value,
                entity_id=repository_id,
                family_ordinal=family_ordinal,
            )
            pending.append(
                PendingEvent(
                    cause=SystemCause(
                        cause_id,
                        SystemEffectFamily.KNOWLEDGE_REPOSITORY,
                        repository_id,
                        family_ordinal,
                    ),
                    details=details,
                    occurrence=build_occurrence_context(
                        details,
                        origin_location_id=transition.next_repository.location_id,
                    ),
                )
            )
            family_ordinal += 1
        if not semantic_mutation:
            return working_state, pending, False
        next_state = rebuild_world_state(working_state, repositories=repositories)
        return next_state, pending, True

    def _resolve_repository_establish_effect(
        self,
        *,
        snap: _EngineSnapshot,
        request: ActionRequest,
    ) -> ResolvedRepositoryEstablishEffect:
        created_repository_id = derive_entity_id(
            self._config,
            "knowledge-repository",
            self._run_id.value,
            self.world_id.value,
            f"tick:{snap.tick.value}",
            request.request_id.value,
        )
        _LOGGER.debug(
            "repository_establish_id tick=%s request_id=%s repository_id=%s",
            snap.tick.value,
            request.request_id.value,
            created_repository_id.value,
        )
        return ResolvedRepositoryEstablishEffect(
            request_id=request.request_id,
            created_repository_id=created_repository_id,
        )

    def _denied_command_kinds_by_entity(
        self, *, tick: int
    ) -> dict[EntityId, dict[str, str]] | None:
        """Union stage denials with dependency-care self-satisfy denials."""
        lifecycle = self._lifecycle_denied_command_kinds(tick=tick)
        dependency = self._dependency_care_denied_command_kinds()
        if lifecycle is None and dependency is None:
            return None
        merged: dict[EntityId, dict[str, str]] = {}
        if lifecycle is not None:
            for body_id, kinds in lifecycle.items():
                merged[body_id] = {
                    kind: "lifecycle_stage_action_denied" for kind in sorted(kinds)
                }
        if dependency is not None:
            for body_id, reason_map in dependency.items():
                existing = merged.setdefault(body_id, {})
                # Dependency reason wins when both deny the same kind.
                existing.update(reason_map)
        return merged or None

    def _lifecycle_fatigue_factor(self, *, entity_id: EntityId, tick: int) -> float:
        factors = self._lifecycle_continuous_factors(entity_id=entity_id, tick=tick)
        return float(factors.fatigue_accrual_factor)  # type: ignore[attr-defined]

    def _lifecycle_metabolism_fatigue_map(
        self, *, tick: int
    ) -> dict[EntityId, float] | None:
        if self._population_lifecycle is None:
            return None
        if not self._population_lifecycle.has_developmental_extensions():
            return None
        from world.lifecycle import AgentLifecycleRecord

        result: dict[EntityId, float] = {}
        for raw in self._lifecycle_records:
            if type(raw) is not AgentLifecycleRecord:
                continue
            factor = self._lifecycle_fatigue_factor(entity_id=raw.body_id, tick=tick)
            if factor != 1.0:
                result[raw.body_id] = factor
        return result or None

    def _lifecycle_learning_rate_map(
        self, *, tick: int
    ) -> dict[EntityId, float] | None:
        if self._population_lifecycle is None:
            return None
        if not self._population_lifecycle.has_developmental_extensions():
            return None
        from world.lifecycle import AgentLifecycleRecord

        result: dict[EntityId, float] = {}
        for raw in self._lifecycle_records:
            if type(raw) is not AgentLifecycleRecord:
                continue
            factors = self._lifecycle_continuous_factors(
                entity_id=raw.body_id, tick=tick
            )
            factor = float(factors.learning_rate_factor)  # type: ignore[attr-defined]
            if factor != 1.0:
                result[raw.body_id] = factor
                _LOGGER.debug(
                    "lifecycle_learning_rate entity_id=%s stage=%s "
                    "learning_rate_factor=%s",
                    raw.body_id.value,
                    raw.stage.value,
                    factor,
                )
        return result or None

    def _skill_efficiency_map(self, *, rules: object) -> dict[object, object] | None:
        if self._skill_policy is None or self._skill_ledger is None:
            # Lifecycle fatigue still applies when skill mode is off: synthesize
            # overrides from base rules x lifecycle factor when needed.
            if self._population_lifecycle is None:
                return None
            if not self._population_lifecycle.has_developmental_extensions():
                return None
            from world._skills import SkillEfficiencyOverride
            from world.lifecycle import AgentLifecycleRecord
            from world.models import PhysicalRules

            assert type(rules) is PhysicalRules
            overrides: dict[object, object] = {}
            tick = self._snapshot.tick.value
            for raw in self._lifecycle_records:
                if type(raw) is not AgentLifecycleRecord:
                    continue
                factor = self._lifecycle_fatigue_factor(
                    entity_id=raw.body_id, tick=tick
                )
                if factor == 1.0:
                    continue
                overrides[raw.body_id] = SkillEfficiencyOverride(
                    move_fatigue=factor * rules.move_fatigue,
                    flee_fatigue=factor * rules.flee_fatigue,
                    help_health_gain=rules.help_health_gain,
                )
                _LOGGER.debug(
                    "lifecycle_fatigue_factor body_id=%s factor=%s "
                    "reason_code=fatigue_accrual",
                    raw.body_id.value,
                    factor,
                )
            return overrides or None
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
        tick = self._snapshot.tick.value
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
            lifecycle_factor = self._lifecycle_fatigue_factor(
                entity_id=entity_id, tick=tick
            )
            # Skill divides cost; lifecycle multiplies accrual — compose explicitly.
            overrides[entity_id] = SkillEfficiencyOverride(
                move_fatigue=lifecycle_factor
                * adjusted_move_fatigue(
                    rules.move_fatigue, navigation, self._skill_policy
                ),
                flee_fatigue=lifecycle_factor
                * adjusted_flee_fatigue(
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
    *,
    production_active: bool,
    dynamics_active: bool,
    artifacts_active: bool = False,
    lifecycle_active: bool = False,
    new_agent_provenance_active: bool = False,
    kinship_active: bool = False,
    dependency_care_active: bool = False,
    durable_records_active: bool = False,
    knowledge_repositories_active: bool = False,
    bounded_experimentation_active: bool = False,
    possession_succession_active: bool = False,
) -> tuple[int, str]:
    """Return the legal event-schema and codec pair for this run."""
    from simulation.persistence import (
        EVENT_SCHEMA_VERSION,
        PERSISTENCE_CODEC_VERSION,
        checkpoint_schema_for_production,
    )
    from world.events import (
        EVENT_SCHEMA_REPLAY_V6,
        EVENT_SCHEMA_REPLAY_V7,
        EVENT_SCHEMA_REPLAY_V8,
        EVENT_SCHEMA_REPLAY_V9,
        EVENT_SCHEMA_REPLAY_V10,
        EVENT_SCHEMA_REPLAY_V11,
        EVENT_SCHEMA_REPLAY_V12,
        EVENT_SCHEMA_REPLAY_V13,
        EVENT_SCHEMA_REPLAY_V14, EVENT_SCHEMA_REPLAY_V15,
        EVENT_SCHEMA_REPLAY_V16,
    )

    schema_version, codec = checkpoint_schema_for_production(
        production_active=production_active,
        dynamics_active=dynamics_active,
        artifacts_active=artifacts_active,
        lifecycle_active=lifecycle_active,
        new_agent_provenance_active=new_agent_provenance_active,
        kinship_active=kinship_active,
        dependency_care_active=dependency_care_active,
        durable_records_active=durable_records_active,
        knowledge_repositories_active=knowledge_repositories_active,
        bounded_experimentation_active=bounded_experimentation_active,
        possession_succession_active=possession_succession_active,
    )
    agreed = (
        possession_succession_active
        and schema_version == EVENT_SCHEMA_REPLAY_V16
        and codec == "v13"
    ) or (
        not possession_succession_active
        and bounded_experimentation_active
        and schema_version == EVENT_SCHEMA_REPLAY_V15
        and codec == "v12"
    ) or (
        not bounded_experimentation_active
        and knowledge_repositories_active
        and durable_records_active
        and schema_version == EVENT_SCHEMA_REPLAY_V14
        and codec == "v11"
    ) or (
        not knowledge_repositories_active
        and durable_records_active
        and schema_version == EVENT_SCHEMA_REPLAY_V13
        and codec == "v10"
    ) or (
        not knowledge_repositories_active
        and not durable_records_active
        and dependency_care_active
        and schema_version == EVENT_SCHEMA_REPLAY_V12
        and codec == "v9"
    ) or (
        not durable_records_active
        and not dependency_care_active
        and kinship_active
        and schema_version == EVENT_SCHEMA_REPLAY_V11
        and codec == "v8"
    ) or (
        not durable_records_active
        and not dependency_care_active
        and not kinship_active
        and new_agent_provenance_active
        and schema_version == EVENT_SCHEMA_REPLAY_V10
        and codec == "v7"
    ) or (
        not durable_records_active
        and not dependency_care_active
        and not kinship_active
        and not new_agent_provenance_active
        and lifecycle_active
        and schema_version == EVENT_SCHEMA_REPLAY_V9
        and codec == "v6"
    ) or (
        not durable_records_active
        and not dependency_care_active
        and not kinship_active
        and not new_agent_provenance_active
        and not lifecycle_active
        and artifacts_active
        and schema_version == EVENT_SCHEMA_REPLAY_V8
        and codec == "v5"
    ) or (
        not durable_records_active
        and not dependency_care_active
        and not kinship_active
        and not new_agent_provenance_active
        and not lifecycle_active
        and not artifacts_active
        and dynamics_active
        and schema_version == EVENT_SCHEMA_REPLAY_V7
        and codec == "v4"
    ) or (
        not durable_records_active
        and not dependency_care_active
        and not kinship_active
        and not new_agent_provenance_active
        and not lifecycle_active
        and not artifacts_active
        and not dynamics_active
        and production_active
        and schema_version == EVENT_SCHEMA_REPLAY_V6
        and codec == "v3"
    ) or (
        not durable_records_active
        and not dependency_care_active
        and not kinship_active
        and not new_agent_provenance_active
        and not lifecycle_active
        and not artifacts_active
        and not dynamics_active
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
        raise ValueError(
            f"unsupported checkpoint schema pair schema={schema_version} codec={codec}"
        )
    _LOGGER.debug(
        "checkpoint_schema_selected event_schema=%s codec=%s "
        "durable_records_active=%s dependency_care_active=%s kinship_active=%s "
        "new_agent_provenance_active=%s lifecycle_active=%s artifacts_active=%s",
        schema_version,
        codec,
        durable_records_active,
        dependency_care_active,
        kinship_active,
        new_agent_provenance_active,
        lifecycle_active,
        artifacts_active,
    )
    if (
        artifacts_active
        and not durable_records_active
        and not dependency_care_active
        and not kinship_active
        and not new_agent_provenance_active
        and not lifecycle_active
    ):
        _LOGGER.debug(
            "artifact_schema_selected event_schema=%s codec=%s artifacts_active=%s",
            schema_version,
            codec,
            artifacts_active,
        )
    if dynamics_active and not artifacts_active and not lifecycle_active:
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


def _optional_population_lifecycle(
    value: object | None,
    *,
    lifecycle_records: Sequence[object] | None,
    synthesize_assigned_lifespan: bool = False,
) -> tuple[object | None, tuple[object, ...]]:
    if value is None:
        if lifecycle_records:
            raise ValueError(
                "lifecycle_records require population_lifecycle "
                "(code=lifecycle_channel_off)"
            )
        return None, ()
    from dataclasses import replace

    from simulation.journal import consume_pending_assigned_lifespan_synthesis
    from simulation.runner_models import PopulationLifecycleSpec
    from world.lifecycle import AgentLifecycleRecord

    if type(value) is not PopulationLifecycleSpec:
        raise TypeError(
            "population_lifecycle must be PopulationLifecycleSpec or None"
        )
    pending_synthesis = (
        consume_pending_assigned_lifespan_synthesis()
        if synthesize_assigned_lifespan
        else frozenset()
    )
    records_raw = () if lifecycle_records is None else tuple(lifecycle_records)
    frozen: list[AgentLifecycleRecord] = []
    seen_bodies: set[str] = set()
    for record in records_raw:
        if type(record) is not AgentLifecycleRecord:
            raise TypeError("lifecycle_records entries must be AgentLifecycleRecord")
        if record.body_id.value in seen_bodies:
            raise ValueError(
                "lifecycle_records body_id must be unique "
                "(code=lifecycle_record_duplicate)"
            )
        seen_bodies.add(record.body_id.value)
        if record.body_id.value in pending_synthesis:
            record = replace(
                record, assigned_lifespan_ticks=value.lifespan_ticks
            )
            _LOGGER.debug(
                "lifecycle_assigned_lifespan_synthesized body_id=%s "
                "assigned_lifespan_ticks=%s",
                record.body_id.value,
                record.assigned_lifespan_ticks,
            )
        frozen.append(record)
    return value, tuple(frozen)


def _optional_production_catalog(value: object | None) -> object | None:
    if value is None:
        return None
    from world.production import ProductionCatalog

    if type(value) is not ProductionCatalog:
        raise TypeError("production_catalog must be ProductionCatalog or None")
    if value.recipe_count == 0:
        return None
    return value


def _optional_experiment_catalog(
    laws: object | None, production_catalog: object | None
) -> object | None:
    if laws is None:
        return None
    if production_catalog is None:
        raise ValueError("bounded_experimentation_requires_production_catalog")
    if not isinstance(laws, tuple) or not laws:
        raise TypeError("experiment_laws must be a non-empty tuple or None")
    from world._experiment_laws import catalog_from_rows
    from world.production import ProductionCatalog

    if type(production_catalog) is not ProductionCatalog:
        raise TypeError("production_catalog must be ProductionCatalog")
    return catalog_from_rows(laws, production_catalog)


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
        "lifecycle_stage_action_denied": ActionResolutionReason.STRUCTURAL_REJECTION,
        "dependency_care_self_satisfy_denied": ActionResolutionReason.STRUCTURAL_REJECTION,
        "dependency_care_channel_off": ActionResolutionReason.STRUCTURAL_REJECTION,
        "dependency_care_target_invalid": ActionResolutionReason.STRUCTURAL_REJECTION,
        "dependency_care_action_disabled": ActionResolutionReason.STRUCTURAL_REJECTION,
        "durable_records_inactive": ActionResolutionReason.STRUCTURAL_REJECTION,
        "durable_genre_required": ActionResolutionReason.STRUCTURAL_REJECTION,
        "durable_genre_disabled": ActionResolutionReason.STRUCTURAL_REJECTION,
        "durable_copy_generation_cap": ActionResolutionReason.STRUCTURAL_REJECTION,
        "durable_parent_destroyed": ActionResolutionReason.STRUCTURAL_REJECTION,
        "durable_annotation_cap": ActionResolutionReason.STRUCTURAL_REJECTION,
        "durable_integrity_destroyed": ActionResolutionReason.STRUCTURAL_REJECTION,
        "durable_damage_disabled": ActionResolutionReason.STRUCTURAL_REJECTION,
        "durable_partial_loss_disabled": ActionResolutionReason.STRUCTURAL_REJECTION,
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
        "unknown_artifact": ActionResolutionReason.STRUCTURAL_REJECTION,
        "artifact_not_portable": ActionResolutionReason.STRUCTURAL_REJECTION,
        "artifact_not_held": ActionResolutionReason.STRUCTURAL_REJECTION,
        "artifact_not_colocated": ActionResolutionReason.STRUCTURAL_REJECTION,
        "artifact_content_invalid": ActionResolutionReason.STRUCTURAL_REJECTION,
        "invalid_artifact_kind": ActionResolutionReason.STRUCTURAL_REJECTION,
        "invalid_artifact_hold": ActionResolutionReason.STRUCTURAL_REJECTION,
        "artifact_transfer_mode_invalid": ActionResolutionReason.STRUCTURAL_REJECTION,
        "artifact_hold_cap": ActionResolutionReason.STRUCTURAL_REJECTION,
        "recipient_unavailable": ActionResolutionReason.STRUCTURAL_REJECTION,
        "not_an_item": ActionResolutionReason.STRUCTURAL_REJECTION,
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
