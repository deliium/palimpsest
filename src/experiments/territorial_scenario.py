"""Paired scarce and abundant worlds, plus the territorial condition matrix.

The worlds share seed, topology, bodies, and stochastic identity. Claims stay
on the owner ledger. Neither world carries an owner or territory field.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from agents.cognition.configuration import CognitionTerritorialClaimMode
from agents.cognition.models import (
    ActionDirection,
    CounterpartBinding,
    OwnerSafeSocialIdentity,
)
from agents.cognition.territorial import (
    TERRITORIAL_CLAIM_POLICY_VERSION,
    ClaimChannel,
    ClaimTargetKind,
    TerritorialClaim,
    TerritorialClaimLedger,
    TerritorialEvidenceItem,
    apply_territorial_update,
    default_territorial_claim_policy,
    territorial_claim_id,
    territorial_respect_penalties,
    territorial_wait_replacement,
)
from agents.models import AgentId
from experiments.models import (
    EXPERIMENT_SCHEMA_VERSION,
    ExperimentCondition,
    ExperimentDefinition,
    ExperimentSeedMatrix,
    require_stochastic,
)
from memory.models import (
    MemoryId,
    MemoryProvenance,
    MemorySituationContext,
    MemorySourceKind,
    MemoryTrace,
)
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V4,
    RUNNER_SCHEMA_VERSION_V15,
    AgentCognitionSpec,
    AgentRunnerSpec,
    RunnerStopPolicy,
    SimulationRunnerConfig,
    TerritorialClaimMode,
    WorldScenarioSpec,
)
from world.actions import Wait
from world.identifiers import EntityId, EventId, WorldId, WorldRevision
from world.models import (
    AgentBody,
    LifeStatus,
    Location,
    Resource,
    Weather,
    default_physical_rules,
)
from world.observations import (
    Observation,
    ObservationAudienceRole,
    ObservationProvenance,
    ObservationSourceKind,
    ObservedOccurrence,
    ObservedSelf,
)
from world.values import (
    BodyCapacity,
    CarryCapacity,
    Fatigue,
    Health,
    Hunger,
    ItemCapacity,
    ResourceKind,
    TemperatureCelsius,
    Thirst,
    UnitInterval,
    WeatherCondition,
)

_LOG: Final[logging.Logger] = logging.getLogger("experiments.catalog")
_BIAS_LOG: Final[logging.Logger] = logging.getLogger("agents.cognition.territorial")
_OWNER = AgentId("agent-1")
_OTHER = AgentId("agent-2")
_LOCATION = EntityId("loc-1")
_OWNER_BODY = EntityId("body-1")
_OTHER_BODY = EntityId("body-2")


@dataclass(frozen=True, slots=True)
class TerritorialConditionRow:
    """One policy reading from the scarce or abundant world."""

    row_id: str
    reason: str
    penalty: float
    command_name: str
    frequent_area: bool


def territorial_worlds() -> tuple[WorldScenarioSpec, WorldScenarioSpec]:
    """One shared camp. Food is scarce in the first world and abundant in the second."""
    scarce = _world(maximum_quantity=1.0, regeneration_per_tick=0.0)
    abundant = _world(maximum_quantity=8.0, regeneration_per_tick=1.0)
    return scarce, abundant


def territorial_claims_scenario(
    *,
    seed: int = 11,
    max_ticks: int = 4,
) -> ExperimentDefinition:
    """Disabled, scarce, and abundant arms. Absent from the V1 regression gate."""
    scarce, abundant = territorial_worlds()
    identity = require_stochastic("cmp-territorial")
    disabled = _config(
        seed=seed,
        identity=identity,
        world=scarce,
        mode=TerritorialClaimMode.DISABLED,
        schema_version=RUNNER_SCHEMA_VERSION_V4,
        max_ticks=max_ticks,
    )
    scarce_arm = _config(
        seed=seed,
        identity=identity,
        world=scarce,
        mode=TerritorialClaimMode.DETERMINISTIC,
        schema_version=RUNNER_SCHEMA_VERSION_V15,
        max_ticks=max_ticks,
    )
    abundant_arm = _config(
        seed=seed,
        identity=identity,
        world=abundant,
        mode=TerritorialClaimMode.DETERMINISTIC,
        schema_version=RUNNER_SCHEMA_VERSION_V15,
        max_ticks=max_ticks,
    )
    arms = (
        ("v-disabled", disabled),
        ("v-scarce", scarce_arm),
        ("v-abundant", abundant_arm),
    )
    for arm_id, config in arms:
        _LOG.debug(
            "territorial_scenario arm_id=%s schema_version=%s resource_max=%s",
            arm_id,
            config.schema_version,
            config.scenario.resources[0].maximum_quantity,
        )
    return ExperimentDefinition(
        experiment_id="experiment-v-territorial-claims",
        schema_version=EXPERIMENT_SCHEMA_VERSION,
        seed_matrix=ExperimentSeedMatrix(seeds=(seed,)),
        conditions=tuple(
            ExperimentCondition(
                condition_id=arm_id,
                label_code=arm_id.removeprefix("v-"),
                runner_config=config,
            )
            for arm_id, config in arms
        ),
        paired_world_group="experiment-v-territorial-claims-world",
    )


def evaluate_territorial_conditions(
    scarce: WorldScenarioSpec,
    abundant: WorldScenarioSpec,
    *,
    scarce_trust_relationships: Sequence[object],
    scarce_breach_relationships: Sequence[object],
    abundant_trust_relationships: Sequence[object],
) -> tuple[TerritorialConditionRow, ...]:
    """Apply the claim policy to observations taken from these worlds.

    Hunger, resentment, and trust are the caller's relationship and need
    inputs. Target locations and actors come from the world bodies.
    """
    location = scarce.locations[0].entity_id
    abundant_location = abundant.locations[0].entity_id
    ledger = _heard_claim(location)
    move = _Future("move-place", ActionDirection.MOVE, location.value)
    ignored, ignore_reason = _recorded_penalties(
        owner_id=_OWNER,
        futures=(move,),
        ledger=ledger,
        relationships=scarce_trust_relationships,
        hunger=75.0,
        thirst=0.0,
        mode=CognitionTerritorialClaimMode.DETERMINISTIC,
    )
    respected, respect_reason = _recorded_penalties(
        owner_id=_OWNER,
        futures=(
            _Future("move-place", ActionDirection.MOVE, abundant_location.value),
        ),
        ledger=_heard_claim(abundant_location),
        relationships=abundant_trust_relationships,
        hunger=0.0,
        thirst=0.0,
        mode=CognitionTerritorialClaimMode.DETERMINISTIC,
    )
    defended, _audits = _defend(scarce, scarce_breach_relationships)
    quiet, _quiet_audits = territorial_wait_replacement(
        Wait(),
        owner_id=_OWNER,
        tick=2,
        observation=_body_observation(abundant, tick=2),
        identity=_identity(abundant),
        ledger=_heard_claim(abundant_location),
        relationships=abundant_trust_relationships,
        mode=CognitionTerritorialClaimMode.DETERMINISTIC,
    )
    frequent = _frequent_area(abundant)
    return (
        TerritorialConditionRow(
            row_id="scarce-ignore-need",
            reason=ignore_reason,
            penalty=ignored.get(move.future_id, 0.0),
            command_name="Wait",
            frequent_area=False,
        ),
        TerritorialConditionRow(
            row_id="scarce-defend",
            reason="defend" if type(defended).__name__ == "Attack" else "other",
            penalty=0.0,
            command_name=type(defended).__name__,
            frequent_area=False,
        ),
        TerritorialConditionRow(
            row_id="abundant-respect",
            reason=respect_reason,
            penalty=respected.get("move-place", 0.0),
            command_name=type(quiet).__name__,
            frequent_area=False,
        ),
        TerritorialConditionRow(
            row_id="abundant-two-ticks",
            reason="below_frequent_area",
            penalty=0.0,
            command_name="Wait",
            frequent_area=frequent,
        ),
    )


class _Future:
    def __init__(
        self, future_id: str, direction: ActionDirection, target_entity_id: str
    ) -> None:
        self.future_id = future_id
        self.direction = direction
        self.target_entity_id = target_entity_id


def _recorded_penalties(**kwargs: object) -> tuple[dict[str, float], str]:
    captured: list[str] = []

    class _Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            captured.append(record.getMessage())

    handler = _Capture()
    previous = _BIAS_LOG.level
    _BIAS_LOG.addHandler(handler)
    _BIAS_LOG.setLevel(logging.DEBUG)
    try:
        penalties = territorial_respect_penalties(**kwargs)
    finally:
        _BIAS_LOG.removeHandler(handler)
        _BIAS_LOG.setLevel(previous)
    reason = "unmatched"
    for line in captured:
        marker = "reason="
        if marker in line:
            reason = line.split(marker, 1)[1].split(" ", 1)[0]
    return penalties, reason


def _world(
    *, maximum_quantity: float, regeneration_per_tick: float
) -> WorldScenarioSpec:
    body = _body(_OWNER_BODY)
    other = _body(_OTHER_BODY)
    return WorldScenarioSpec(
        world_id=WorldId("world-territorial"),
        revision=WorldRevision(0),
        physical_rules=default_physical_rules(),
        locations=(
            Location(
                entity_id=_LOCATION,
                name="Camp",
                adjacent=(),
                body_capacity=BodyCapacity(8),
                item_capacity=ItemCapacity(16),
                base_temperature=TemperatureCelsius(20.0),
                shelter_factor=UnitInterval(0.0),
                visibility_factor=UnitInterval(1.0),
            ),
        ),
        bodies=(body, other),
        resources=(
            Resource(
                entity_id=EntityId("res-food"),
                name="Cache",
                kind=ResourceKind.FOOD,
                location_id=_LOCATION,
                quantity=maximum_quantity,
                maximum_quantity=maximum_quantity,
                regeneration_per_tick=regeneration_per_tick,
                unit="portions",
            ),
        ),
        weather=(Weather(location_id=_LOCATION, condition=WeatherCondition.CLEAR),),
    )


def _body(entity_id: EntityId) -> AgentBody:
    return AgentBody(
        entity_id=entity_id,
        location_id=_LOCATION,
        health=Health(100.0),
        hunger=Hunger(0.0),
        thirst=Thirst(0.0),
        fatigue=Fatigue(0.0),
        temperature=TemperatureCelsius(36.5),
        inventory=(),
        life_status=LifeStatus.ALIVE,
        carry_capacity=CarryCapacity(10),
    )


def _config(
    *,
    seed: int,
    identity: object,
    world: WorldScenarioSpec,
    mode: TerritorialClaimMode,
    schema_version: str,
    max_ticks: int,
) -> SimulationRunnerConfig:
    agents = tuple(
        AgentRunnerSpec(
            agent_id=agent_id,
            entity_id=entity_id,
            cognition=AgentCognitionSpec(
                agent_id=agent_id,
                territorial_claim_mode=mode,
            ),
        )
        for agent_id, entity_id in ((_OWNER, _OWNER_BODY), (_OTHER, _OTHER_BODY))
    )
    return SimulationRunnerConfig(
        seed=seed,
        stochastic_identity=identity,
        scenario=world,
        agents=agents,
        stop_policy=RunnerStopPolicy(max_ticks=max_ticks),
        schema_version=schema_version,
    )


def _identity(world: WorldScenarioSpec) -> OwnerSafeSocialIdentity:
    return OwnerSafeSocialIdentity(
        owner_id=_OWNER,
        owner_entity_id=world.bodies[0].entity_id,
        counterparts=(
            CounterpartBinding(agent_id=_OTHER, entity_id=world.bodies[1].entity_id),
        ),
    )


def _self(world: WorldScenarioSpec) -> ObservedSelf:
    body = world.bodies[0]
    return ObservedSelf(
        entity_id=body.entity_id,
        location_id=body.location_id,
        health=Health(100),
        hunger=Hunger(0),
        thirst=Thirst(0),
        fatigue=Fatigue(0),
        temperature=TemperatureCelsius(36.5),
        inventory=(),
        life_status=LifeStatus.ALIVE,
        carry_capacity=CarryCapacity(10),
    )


def _body_observation(world: WorldScenarioSpec, *, tick: int) -> Observation:
    return Observation(
        observer_id=world.bodies[0].entity_id,
        world_id=world.world_id,
        revision=WorldRevision(1),
        tick=tick,
        self_body=_self(world),
    )


def _occurrence(
    kind: str, *, actor: EntityId, event: str, tick: int
) -> ObservedOccurrence:
    return ObservedOccurrence(
        provenance=ObservationProvenance(
            source_kind=ObservationSourceKind.OCCURRENCE,
            source_tick=tick,
            source_event_id=EventId(event),
        ),
        kind=kind,
        audience_role=ObservationAudienceRole.WITNESS,
        actor_id=actor,
        other_entity_id=None,
        success=True,
    )


def _heard_claim(location: EntityId) -> TerritorialClaimLedger:
    claim_id = territorial_claim_id(_OWNER, ClaimTargetKind.LOCATION, location)
    evidence = TerritorialEvidenceItem(
        owner_id=_OWNER,
        target_kind=ClaimTargetKind.LOCATION,
        target_entity_id=location,
        channel=ClaimChannel.TESTIMONY,
        lineage_ref="heard-place",
        source_id=_OTHER,
        pre_scale_delta=0.40,
        tick=1,
        policy_version=TERRITORIAL_CLAIM_POLICY_VERSION,
        claim_id=claim_id,
        ordinal=0,
    )
    return TerritorialClaimLedger(
        owner_id=_OWNER,
        claims=(
            TerritorialClaim(
                claim_id=claim_id,
                owner_id=_OWNER,
                target_kind=ClaimTargetKind.LOCATION,
                target_entity_id=location,
                strength=0.40,
                support_mass=0.40,
                contradiction_mass=0.0,
                evidence=(evidence,),
            ),
        ),
    )


def _defend(
    world: WorldScenarioSpec, relationships: Sequence[object]
) -> tuple[object, object]:
    identity = _identity(world)
    policy = default_territorial_claim_policy()
    slept = Observation(
        observer_id=world.bodies[0].entity_id,
        world_id=world.world_id,
        revision=WorldRevision(1),
        tick=2,
        self_body=_self(world),
        occurrences=(
            _occurrence(
                "sleep",
                actor=world.bodies[0].entity_id,
                event="sleep-1",
                tick=1,
            ),
        ),
    )
    ledger = apply_territorial_update(
        owner_id=_OWNER,
        tick=2,
        observation=slept,
        social_identity=identity,
        ledger=None,
        policy=policy,
    )
    breached = Observation(
        observer_id=world.bodies[0].entity_id,
        world_id=world.world_id,
        revision=WorldRevision(1),
        tick=2,
        self_body=_self(world),
        occurrences=(
            _occurrence(
                "take",
                actor=world.bodies[1].entity_id,
                event="take-1",
                tick=1,
            ),
        ),
    )
    ledger = apply_territorial_update(
        owner_id=_OWNER,
        tick=2,
        observation=breached,
        social_identity=identity,
        ledger=ledger,
        policy=policy,
    )
    return territorial_wait_replacement(
        Wait(),
        owner_id=_OWNER,
        tick=2,
        observation=breached,
        identity=identity,
        ledger=ledger,
        relationships=relationships,
        mode=CognitionTerritorialClaimMode.DETERMINISTIC,
    )


def _frequent_area(world: WorldScenarioSpec) -> bool:
    location = world.locations[0].entity_id
    memories = tuple(
        MemoryTrace(
            memory_id=MemoryId(f"mem-{tick}"),
            owner_id=_OWNER,
            world_revision=WorldRevision(0),
            concepts=(),
            entities=(),
            relations=(),
            context=MemorySituationContext(location_id=location),
            emotional_salience=0.0,
            confidence=1.0,
            provenance=MemoryProvenance(
                kind=MemorySourceKind.DIRECT_OBSERVATION,
                source_tick=tick,
            ),
            created_tick=tick,
            source_tick=tick,
            last_access_tick=tick,
            access_count=0,
        )
        for tick in (1, 2)
    )
    ledger = apply_territorial_update(
        owner_id=_OWNER,
        tick=3,
        observation=_body_observation(world, tick=3),
        social_identity=_identity(world),
        ledger=None,
        policy=default_territorial_claim_policy(),
        memories=memories,
    )
    return any(
        claim.target_kind is ClaimTargetKind.FREQUENT_AREA for claim in ledger.claims
    )
