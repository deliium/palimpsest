"""Owner-scoped territorial claim contracts."""

from __future__ import annotations

import dataclasses
import logging
import math

import pytest

from agents.cognition.configuration import CognitionTerritorialClaimMode
from agents.cognition.models import CounterpartBinding, OwnerSafeSocialIdentity
from agents.cognition.territorial import (
    TERRITORIAL_CLAIM_POLICY_VERSION,
    ClaimChannel,
    ClaimTargetKind,
    TerritorialClaim,
    TerritorialClaimLedger,
    TerritorialClaimPolicy,
    TerritorialEvidenceItem,
    apply_territorial_update,
    default_territorial_claim_policy,
    empty_territorial_ledger,
    territorial_claim_id,
    territorial_evidence_id,
    territorial_respect_penalties,
    territorial_wait_replacement,
)
from agents.models import AgentId
from memory.models import (
    MemoryId,
    MemoryProvenance,
    MemorySituationContext,
    MemorySourceKind,
    MemoryTrace,
)
from simulation.runner_models import TerritorialClaimMode
from world.identifiers import EntityId, EventId, WorldId, WorldRevision
from world.models import LifeStatus
from world.observations import (
    Observation,
    ObservationAudienceRole,
    ObservationProvenance,
    ObservationSourceKind,
    ObservedOccurrence,
    ObservedSelf,
    ObservedStructure,
)
from world.production import StructureKind
from world.values import (
    CarryCapacity,
    Fatigue,
    Health,
    Hunger,
    TemperatureCelsius,
    Thirst,
)

_LOGGER = "agents.cognition.territorial"
_BANNED_FIELDS = frozenset(
    {
        "territory_owner",
        "owner",
        "controller",
        "grid",
        "cell",
        "property",
        "mine",
    }
)
_TYPES = (
    ClaimTargetKind,
    ClaimChannel,
    TerritorialEvidenceItem,
    TerritorialClaim,
    TerritorialClaimLedger,
    TerritorialClaimPolicy,
)


def _agent(value: str) -> AgentId:
    return AgentId(value)


def _entity(value: str) -> EntityId:
    return EntityId(value)


def _item(
    owner: AgentId,
    target: EntityId,
    *,
    kind: ClaimTargetKind = ClaimTargetKind.LOCATION,
    ordinal: int = 0,
    channel: ClaimChannel = ClaimChannel.DIRECT_ACTION,
    lineage_ref: str = "event-1",
    source: AgentId | None = None,
    delta: float = 0.50,
    tick: int = 1,
) -> TerritorialEvidenceItem:
    return TerritorialEvidenceItem(
        owner_id=owner,
        target_kind=kind,
        target_entity_id=target,
        channel=channel,
        lineage_ref=lineage_ref,
        source_id=owner if source is None else source,
        pre_scale_delta=delta,
        tick=tick,
        policy_version=TERRITORIAL_CLAIM_POLICY_VERSION,
        claim_id=territorial_claim_id(owner, kind, target),
        ordinal=ordinal,
    )


def _claim(
    owner: AgentId,
    target: EntityId,
    *,
    kind: ClaimTargetKind = ClaimTargetKind.LOCATION,
    strength: float = 0.50,
    support_mass: float = 0.50,
    contradiction_mass: float = 0.0,
    evidence: tuple[TerritorialEvidenceItem, ...] = (),
) -> TerritorialClaim:
    return TerritorialClaim(
        claim_id=territorial_claim_id(owner, kind, target),
        owner_id=owner,
        target_kind=kind,
        target_entity_id=target,
        strength=strength,
        support_mass=support_mass,
        contradiction_mass=contradiction_mass,
        evidence=evidence,
    )


def test_modes_match_and_disabled_allocates_nothing() -> None:
    assert {item.value for item in CognitionTerritorialClaimMode} == {
        "disabled",
        "deterministic",
    }
    assert {item.value for item in TerritorialClaimMode} == {
        item.value for item in CognitionTerritorialClaimMode
    }
    assert CognitionTerritorialClaimMode.DISABLED.value == "disabled"
    assert CognitionTerritorialClaimMode.DISABLED is not (
        CognitionTerritorialClaimMode.DETERMINISTIC
    )


def test_banned_field_names_are_absent() -> None:
    for cls in _TYPES:
        if not dataclasses.is_dataclass(cls):
            continue
        names = {item.name for item in dataclasses.fields(cls)}
        assert names.isdisjoint(_BANNED_FIELDS)


def test_policy_locks_version_and_numbers() -> None:
    policy = default_territorial_claim_policy()
    assert policy.version == "territorial-claims.v1"
    assert policy.direct_action_floor == 0.50
    assert policy.frequent_area_step == 0.15
    assert policy.frequent_area_activation == 0.40
    assert policy.frequent_area_cap == 1.0
    assert policy.testimony_target_scale == 0.70
    assert policy.testimony_rate == 0.50
    assert policy.max_testimony_hop == 1
    assert policy.violation_contradiction == 0.25
    assert policy.respect_strength == 0.40
    assert policy.respect_trust == 0.60
    assert policy.respect_penalty == 0.35
    assert policy.ignore_trust_below == 0.40
    assert policy.missing_profile_trust == 0.50
    assert policy.missing_profile_resentment == 0.0
    assert policy.missing_profile_fear == 0.0
    assert policy.critical_need == 0.75
    assert policy.defend_resentment == 0.40
    assert policy.defend_fear_below == 0.60
    assert policy.announce_strength == 0.40
    assert policy.max_heads == 32
    assert policy.max_evidence == 64
    assert policy.repeated_control_window == 2
    with pytest.raises(ValueError, match="version: unsupported_policy"):
        TerritorialClaimPolicy(version="territorial-claims.v0")
    with pytest.raises(ValueError, match="respect_penalty: unsupported_policy"):
        TerritorialClaimPolicy(respect_penalty=0.10)


def test_ledger_construction_logs_identity_without_strength(
    caplog: pytest.LogCaptureFixture,
) -> None:
    owner = _agent("owner-a")
    target = _entity("place-1")
    caplog.set_level(logging.DEBUG, logger=_LOGGER)
    ledger = TerritorialClaimLedger(owner_id=owner, claims=(_claim(owner, target),))
    assert ledger.claim_for(ClaimTargetKind.LOCATION, target) is not None
    assert ledger.claim_for(ClaimTargetKind.SHELTER, target) is None
    messages = [record.getMessage() for record in caplog.records]
    assert any(
        "territorial_ledger_constructed" in message
        and owner.value in message
        and "territorial-claims.v1" in message
        and "head_count=1" in message
        for message in messages
    )
    assert all("0.5" not in message for message in messages)


def test_claim_ids_are_sha256_of_owner_kind_and_entity() -> None:
    owner = _agent("owner-a")
    other = _agent("owner-b")
    target = _entity("place-1")
    left = territorial_claim_id(owner, ClaimTargetKind.LOCATION, target)
    right = territorial_claim_id(other, ClaimTargetKind.LOCATION, target)
    frequent = territorial_claim_id(owner, ClaimTargetKind.FREQUENT_AREA, target)
    assert left != right
    assert left != frequent
    assert len(left) == 64
    claim = _claim(owner, target)
    assert claim.claim_id == left
    item = _item(owner, target)
    assert item.evidence_id == territorial_evidence_id(
        claim_id=left,
        ordinal=0,
        channel=ClaimChannel.DIRECT_ACTION,
        lineage_ref="event-1",
    )
    assert item.pre_scale_delta == 0.5


def test_constructors_reject_bad_numbers_and_enums(
    caplog: pytest.LogCaptureFixture,
) -> None:
    owner = _agent("owner-a")
    target = _entity("place-1")
    caplog.set_level(logging.ERROR, logger=_LOGGER)
    with pytest.raises(ValueError, match="target_kind: unknown_target_kind"):
        territorial_claim_id(owner, "location", target)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="channel: unknown_channel"):
        territorial_evidence_id(
            claim_id="a" * 64,
            ordinal=0,
            channel="testimony",  # type: ignore[arg-type]
            lineage_ref="event-1",
        )
    with pytest.raises(ValueError, match="strength: not_finite"):
        _claim(owner, target, strength=float("nan"))
    with pytest.raises(ValueError, match="strength: out_of_range"):
        _claim(owner, target, strength=1.1)
    with pytest.raises(ValueError, match="support_mass: not_finite"):
        _claim(owner, target, support_mass=math.inf)
    errors = [record.getMessage() for record in caplog.records]
    assert any(
        "field=strength" in message and "not_finite" in message for message in errors
    )
    assert any(
        "field=strength" in message and "out_of_range" in message for message in errors
    )


def test_duplicate_heads_owner_mismatch_and_evidence_cap() -> None:
    owner = _agent("owner-a")
    other = _agent("owner-b")
    target = _entity("place-1")
    head = _claim(owner, target, evidence=(_item(owner, target),))
    with pytest.raises(ValueError, match="claims: duplicate_head"):
        TerritorialClaimLedger(owner_id=owner, claims=(head, head))
    foreign = _claim(other, target)
    with pytest.raises(ValueError, match=r"claims\.owner_id: owner_mismatch"):
        TerritorialClaimLedger(owner_id=owner, claims=(foreign,))
    mismatched = _item(other, target)
    with pytest.raises(ValueError, match=r"evidence\.owner_id: owner_mismatch"):
        _claim(owner, target, evidence=(mismatched,))
    crowded = tuple(
        _item(owner, target, ordinal=index, lineage_ref=f"event-{index}")
        for index in range(65)
    )
    with pytest.raises(ValueError, match="evidence: cap_exceeded"):
        _claim(owner, target, evidence=crowded)
    many = tuple(
        _claim(owner, _entity(f"place-{index}"), kind=ClaimTargetKind.LOCATION)
        for index in range(33)
    )
    with pytest.raises(ValueError, match="claims: cap_exceeded"):
        TerritorialClaimLedger(owner_id=owner, claims=many)


def test_runner_v15_round_trip_and_closed_gates(
    caplog: pytest.LogCaptureFixture,
) -> None:
    import json
    from dataclasses import replace

    from simulation.runner import _cognition_config_for
    from simulation.runner_models import (
        RUNNER_SCHEMA_VERSION,
        RUNNER_SCHEMA_VERSION_V14,
        RUNNER_SCHEMA_VERSION_V15,
        AgentCognitionSpec,
        MortalityMode,
        ReputationMode,
        SimulationRunnerConfig,
        V2CapabilityFlags,
    )
    from simulation.runner_serialization import (
        decode_runner_config,
        encode_runner_config,
    )
    from tests.unit.test_runner_serialization import _configured
    from world.environment import example_environmental_dynamics
    from world.models import Location

    assert RUNNER_SCHEMA_VERSION == "runner-config-v4"
    assert "territorial_behavior" not in V2CapabilityFlags.__dataclass_fields__
    flags = V2CapabilityFlags(multi_hop_testimony_tracking=True)
    assert flags.unimplemented_enabled_names() == ("multi_hop_testimony_tracking",)
    with pytest.raises(TypeError):
        Location(territory_owner="ada")  # type: ignore[call-arg]

    base = _configured(schema_version=RUNNER_SCHEMA_VERSION)
    quiet = json.loads(encode_runner_config(base).decode("utf-8"))
    assert quiet["schema_version"] == "runner-config-v4"
    assert "territorial_claim_mode" not in quiet["agents"][0]["cognition"]
    agent = base.agents[0]
    early = replace(
        agent,
        cognition=replace(
            agent.cognition,
            territorial_claim_mode=TerritorialClaimMode.DETERMINISTIC,
        ),
    )
    with pytest.raises(ValueError, match="territorial_claim_mode_requires_v15"):
        replace(base, agents=(early,))
    claimed = replace(
        agent,
        cognition=replace(
            early.cognition,
            reputation_mode=ReputationMode.DETERMINISTIC,
        ),
    )
    with pytest.raises(ValueError, match="v15_requires_territorial_claims"):
        replace(base, schema_version=RUNNER_SCHEMA_VERSION_V15)
    enabled = replace(base, agents=(claimed,), schema_version=RUNNER_SCHEMA_VERSION_V15)
    encoded = encode_runner_config(enabled)
    document = json.loads(encoded.decode("utf-8"))
    assert document["schema_version"] == "runner-config-v15"
    cognition = document["agents"][0]["cognition"]
    assert cognition["territorial_claim_mode"] == "deterministic"
    assert cognition["reputation_mode"] == "deterministic"
    assert cognition["production_knowledge_mode"] == "disabled"
    assert "environmental_dynamics" not in document
    assert decode_runner_config(encoded) == enabled
    spec = example_environmental_dynamics()
    dynamics = replace(enabled, environmental_dynamics=spec)
    dynamics_doc = json.loads(encode_runner_config(dynamics).decode("utf-8"))
    assert dynamics_doc["schema_version"] == "runner-config-v15"
    assert "environmental_dynamics" in dynamics_doc
    dynamics_only = SimulationRunnerConfig(
        seed=base.seed,
        stochastic_identity=base.stochastic_identity,
        scenario=base.scenario,
        agents=base.agents,
        stop_policy=base.stop_policy,
        schema_version=RUNNER_SCHEMA_VERSION_V14,
        environmental_dynamics=spec,
        capability_flags=base.capability_flags,
        cognition_trace=base.cognition_trace,
    )
    only = json.loads(encode_runner_config(dynamics_only).decode("utf-8"))
    assert only["schema_version"] == "runner-config-v14"
    assert "territorial_claim_mode" not in only["agents"][0]["cognition"]
    caplog.set_level(logging.DEBUG, logger="simulation.runner")
    built = _cognition_config_for(
        claimed.cognition,
        mortality_mode=MortalityMode.ENABLED,
        capability_flags=V2CapabilityFlags(),
    )
    assert built.territorial_claim_mode.value == "deterministic"
    assert built.territorial_claim_policy is not None
    assert any(
        "cognition_config_territorial_claim_mode mode=deterministic "
        "policy_version=territorial-claims.v1" in record.getMessage()
        for record in caplog.records
    )
    assert (
        AgentCognitionSpec(agent_id=agent.agent_id).territorial_claim_mode
        is TerritorialClaimMode.DISABLED
    )


def test_empty_ledger_and_quantized_strength() -> None:
    owner = _agent("owner-a")
    ledger = empty_territorial_ledger(owner)
    assert ledger.claims == ()
    claim = _claim(owner, _entity("place-1"), strength=0.5000004)
    assert claim.strength == 0.5


def _identity(owner: str, owner_entity: str) -> OwnerSafeSocialIdentity:
    return OwnerSafeSocialIdentity(
        owner_id=_agent(owner),
        owner_entity_id=EntityId(owner_entity),
        counterparts=(),
    )


def _occurrence(
    kind: str,
    *,
    actor: str,
    event: str,
    other: str | None = None,
    source_tick: int = 1,
) -> ObservedOccurrence:
    return ObservedOccurrence(
        provenance=ObservationProvenance(
            source_kind=ObservationSourceKind.OCCURRENCE,
            source_tick=source_tick,
            source_event_id=EventId(event),
        ),
        kind=kind,
        audience_role=ObservationAudienceRole.WITNESS,
        actor_id=EntityId(actor),
        other_entity_id=None if other is None else EntityId(other),
        success=True,
    )


def _self(entity: str, location: str) -> ObservedSelf:
    return ObservedSelf(
        entity_id=EntityId(entity),
        location_id=EntityId(location),
        health=Health(100),
        hunger=Hunger(0),
        thirst=Thirst(0),
        fatigue=Fatigue(0),
        temperature=TemperatureCelsius(36.5),
        inventory=(),
        life_status=LifeStatus.ALIVE,
        carry_capacity=CarryCapacity(10),
    )


def _observation(
    *occurrences: ObservedOccurrence,
    body: ObservedSelf,
    structures: tuple[ObservedStructure, ...] = (),
    tick: int = 2,
) -> Observation:
    return Observation(
        observer_id=body.entity_id,
        world_id=WorldId("world-1"),
        revision=WorldRevision(1),
        tick=tick,
        self_body=body,
        occurrences=occurrences,
        structures=structures,
    )


def _memory(
    owner: AgentId, memory_id: str, tick: int, location: str | None
) -> MemoryTrace:
    return MemoryTrace(
        memory_id=MemoryId(memory_id),
        owner_id=owner,
        world_revision=WorldRevision(0),
        concepts=(),
        entities=(),
        relations=(),
        context=MemorySituationContext(
            location_id=None if location is None else EntityId(location)
        ),
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


def _update(
    owner: str,
    entity: str,
    observation: Observation,
    *,
    memories: tuple[MemoryTrace, ...] = (),
) -> TerritorialClaimLedger:
    return apply_territorial_update(
        owner_id=_agent(owner),
        tick=observation.tick,
        observation=observation,
        social_identity=_identity(owner, entity),
        ledger=None,
        policy=default_territorial_claim_policy(),
        memories=memories,
    )


def test_sleep_sets_location_claim_and_rejects_world(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger=_LOGGER)
    body = _self("body-a", "place-1")
    ledger = _update(
        "owner-a",
        "body-a",
        _observation(
            _occurrence("sleep", actor="body-a", event="evt-sleep"),
            body=body,
        ),
    )
    head = ledger.claims[0]
    assert head.target_kind is ClaimTargetKind.LOCATION
    assert head.target_entity_id == EntityId("place-1")
    assert head.strength >= 0.50
    assert any(
        "territorial_update owner_id=owner-a tick=2 heads=1 channels="
        in record.getMessage()
        for record in caplog.records
    )
    with pytest.raises(TypeError, match="forbidden_input"):
        apply_territorial_update(
            owner_id=_agent("owner-a"),
            tick=1,
            observation=_observation(body=body),
            social_identity=_identity("owner-a", "body-a"),
            ledger=None,
            policy=default_territorial_claim_policy(),
            world_state=object(),
        )


def test_two_owners_hold_different_strengths_for_one_location() -> None:
    place = EntityId("place-1")
    slept = _update(
        "owner-a",
        "body-a",
        _observation(
            _occurrence("sleep", actor="body-a", event="evt-sleep"),
            body=_self("body-a", "place-1"),
        ),
    )
    owner_b = _agent("owner-b")
    remembered = _update(
        "owner-b",
        "body-b",
        _observation(body=_self("body-b", "place-1"), tick=4),
        memories=(
            _memory(owner_b, "mem-1", 1, "place-1"),
            _memory(owner_b, "mem-2", 2, "place-1"),
            _memory(owner_b, "mem-3", 3, "place-1"),
        ),
    )
    assert slept.claims[0].target_entity_id == place
    assert remembered.claims[0].target_kind is ClaimTargetKind.FREQUENT_AREA
    assert remembered.claims[0].target_entity_id == place
    assert slept.claims[0].strength != remembered.claims[0].strength


def test_frequent_area_waits_for_the_third_tick() -> None:
    owner = _agent("owner-c")
    body = _self("body-c", "place-1")
    two = _update(
        "owner-c",
        "body-c",
        _observation(body=body, tick=3),
        memories=(
            _memory(owner, "mem-1", 1, "place-1"),
            _memory(owner, "mem-2", 2, "place-1"),
            _memory(owner, "mem-blank", 9, None),
        ),
    )
    three = _update(
        "owner-c",
        "body-c",
        _observation(body=body, tick=4),
        memories=(
            _memory(owner, "mem-1", 1, "place-1"),
            _memory(owner, "mem-2", 2, "place-1"),
            _memory(owner, "mem-3", 3, "place-1"),
        ),
    )
    assert two.claims == ()
    head = three.claims[0]
    assert head.target_kind is ClaimTargetKind.FREQUENT_AREA
    assert head.strength == 0.45


def test_unseen_shelter_and_take_create_no_head(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING, logger=_LOGGER)
    body = _self("body-a", "place-1")
    unseen = _update(
        "owner-a",
        "body-a",
        _observation(
            _occurrence(
                "structure_built",
                actor="body-a",
                event="evt-build",
                other="hut-1",
            ),
            body=body,
        ),
    )
    taken = _update(
        "owner-a",
        "body-a",
        _observation(
            _occurrence("take", actor="body-a", event="evt-take", other="item-1"),
            body=body,
        ),
    )
    seen = _update(
        "owner-a",
        "body-a",
        _observation(
            _occurrence(
                "structure_built",
                actor="body-a",
                event="evt-build",
                other="hut-1",
            ),
            body=body,
            structures=(
                ObservedStructure(
                    entity_id=EntityId("hut-1"),
                    location_id=EntityId("place-1"),
                    kind=StructureKind.SHELTER,
                    integrity=1.0,
                    stored_quantity=0,
                ),
            ),
        ),
    )
    assert unseen.claims == ()
    assert taken.claims == ()
    assert seen.claims[0].target_kind is ClaimTargetKind.SHELTER
    assert seen.claims[0].strength >= 0.50
    assert any(
        "reason_code=shelter_unseen entity_id=hut-1" in record.getMessage()
        for record in caplog.records
    )


@pytest.mark.asyncio
async def test_disabled_mode_keeps_ledger_none_and_the_same_command() -> None:
    from agents.cognition.configuration import (
        CognitionLoopConfig,
        build_cognitive_loop,
    )
    from agents.cognition.defaults import default_cognitive_loop
    from agents.cognition.models import CognitiveLoopInput, InternalAgentState
    from world.actions import Wait

    loop_input = CognitiveLoopInput(
        agent_id=_agent("agent-1"),
        observation=_observation(body=_self("body-1", "loc-1"), tick=1),
        internal_state=InternalAgentState(owner_id=_agent("agent-1")),
    )
    disabled = await default_cognitive_loop().run(loop_input, invocation_id="inv-off")
    enabled_loop = build_cognitive_loop(
        CognitionLoopConfig(
            territorial_claim_mode=CognitionTerritorialClaimMode.DETERMINISTIC
        )
    )
    enabled = await enabled_loop.run(loop_input, invocation_id="inv-on")
    assert disabled.territorial_claims is None
    assert type(disabled.command) is Wait
    assert type(enabled.command) is Wait
    assert type(enabled.territorial_claims) is TerritorialClaimLedger
    assert enabled.territorial_claims.claims == ()


def test_take_at_a_claim_stays_physical_and_records_a_private_breach(
    caplog: pytest.LogCaptureFixture,
) -> None:
    from tests.unit.test_world_rules import _state
    from world._state import World, WorldState
    from world.actions import ActionRequest, Take, TransitionOutcome
    from world.identifiers import ProposalId, RequestId
    from world.models import Location

    caplog.set_level(logging.DEBUG, logger=_LOGGER)
    state = _state()
    world = World(WorldId("world-1"), state)
    result = world.apply_admitted_request(
        ActionRequest(
            request_id=RequestId("r-take"),
            proposal_id=ProposalId("p-take"),
            world_id=WorldId("world-1"),
            actor_id=EntityId("body-1"),
            revision=WorldRevision(1),
            command=Take(EntityId("item-ground")),
        ),
        event_ids=(EventId("evt-take"),),
        run_id="run-1",
        tick=0,
    )
    assert result.outcome is TransitionOutcome.APPLIED
    assert "territorial_claims" not in WorldState.__slots__
    assert "owner" not in Location.__dataclass_fields__
    assert "territory_owner" not in Location.__dataclass_fields__

    owner = _agent("owner-a")
    place = EntityId("place-1")
    prior = TerritorialClaimLedger(
        owner_id=owner,
        claims=(_claim(owner, place, strength=0.50),),
    )
    body = _self("body-a", "place-1")
    observation = _observation(
        _occurrence("take", actor="body-b", event="evt-take", other="item-1"),
        body=body,
    )
    identity = OwnerSafeSocialIdentity(
        owner_id=owner,
        owner_entity_id=EntityId("body-a"),
        counterparts=(
            CounterpartBinding(
                agent_id=_agent("owner-b"),
                entity_id=EntityId("body-b"),
            ),
        ),
    )
    updated = apply_territorial_update(
        owner_id=owner,
        tick=observation.tick,
        observation=observation,
        social_identity=identity,
        ledger=prior,
        policy=default_territorial_claim_policy(),
    )
    head = updated.claim_for(ClaimTargetKind.LOCATION, place)
    assert head is not None
    assert head.strength == 0.50
    assert head.contradiction_mass == 0.25
    assert head.evidence[-1].channel is ClaimChannel.VIOLATION
    assert any(
        "territorial_violation owner_id=owner-a target_kind=location tick=2 "
        "target_entity_id=place-1 reason=violated" in record.getMessage()
        for record in caplog.records
    )
    from agents.cognition.memory import (
        build_direct_observation_memory_trace,
        with_violation_relation,
    )

    plain = build_direct_observation_memory_trace(
        owner_id=owner,
        observation_tick=observation.tick,
        observation_revision=observation.revision,
        occurrence=observation.occurrences[0],
        location_id=place,
    )
    assert all(relation.predicate != "violated" for relation in plain.relations)
    remembered = with_violation_relation(
        plain,
        subject_entity_id=EntityId("body-b"),
        object_entity_id=place,
    )
    assert any(relation.predicate == "violated" for relation in remembered.relations)


@pytest.mark.asyncio
async def test_disabled_memory_omits_violated_relation() -> None:
    from agents.cognition.configuration import (
        CognitionLoopConfig,
        build_cognitive_loop,
    )
    from agents.cognition.models import (
        CognitiveLoopInput,
        CognitiveLoopResult,
        InternalAgentState,
        SubjectiveSnapshot,
    )

    owner = _agent("owner-a")
    place = EntityId("place-1")
    body = _self("body-a", "place-1")
    observation = _observation(
        _occurrence("take", actor="body-b", event="evt-breach", other="item-1"),
        body=body,
    )
    identity = OwnerSafeSocialIdentity(
        owner_id=owner,
        owner_entity_id=EntityId("body-a"),
        counterparts=(
            CounterpartBinding(
                agent_id=_agent("owner-b"),
                entity_id=EntityId("body-b"),
            ),
        ),
    )
    ledger = TerritorialClaimLedger(
        owner_id=owner,
        claims=(_claim(owner, place),),
    )
    snapshot = SubjectiveSnapshot(
        owner_id=owner,
        revision=0,
        memories=(),
        legacy_beliefs=(),
        semantic_beliefs=(),
        social_identity=identity,
        territorial_claims=ledger,
    )
    loop_input = CognitiveLoopInput(
        agent_id=owner,
        observation=observation,
        internal_state=InternalAgentState(owner_id=owner),
        snapshot=snapshot,
    )
    enabled = await build_cognitive_loop(
        CognitionLoopConfig(
            territorial_claim_mode=CognitionTerritorialClaimMode.DETERMINISTIC
        )
    ).run(loop_input, invocation_id="inv-breach")
    disabled = await build_cognitive_loop(CognitionLoopConfig()).run(
        loop_input, invocation_id="inv-quiet"
    )

    def predicates(result: CognitiveLoopResult) -> set[str]:
        found: set[str] = set()
        for intent in result.memory_update_intents:
            memory = intent.memory
            if memory is None:
                continue
            found.update(relation.predicate for relation in memory.relations)
        return found

    assert "violated" in predicates(enabled)
    assert "violated" not in predicates(disabled)
    assert disabled.territorial_claims is None


def _signed_trust(projected: float) -> float:
    return (projected - 0.5) * 2


def _relationship(
    source: AgentId, target: AgentId, *, trust: float, resentment: float, fear: float
) -> object:
    from social.relationships import (
        DirectedRelationshipProfile,
        RelationshipActivationState,
        RelationshipConfidence,
        RelationshipDimension,
        RelationshipDimensionState,
        RelationshipId,
        RelationshipPolicyRef,
        RelationshipRevisionId,
    )

    policy = RelationshipPolicyRef(policy_id="rel-v1", version="1")
    confidence = RelationshipConfidence(
        confidence=1.0, support_mass=1.0, contradiction_mass=0.0
    )
    dimensions = []
    for dimension, value in (
        (RelationshipDimension.TRUST, trust),
        (RelationshipDimension.RESENTMENT, resentment),
        (RelationshipDimension.FEAR, fear),
    ):
        dimensions.append(
            RelationshipDimensionState(
                dimension=dimension,
                value=value,
                confidence=confidence,
                evidence=(),
                logical_tick=1,
                policy=policy,
            )
        )
    return DirectedRelationshipProfile(
        relationship_id=RelationshipId(f"rel-{target.value}"),
        source_id=source,
        target_id=target,
        dimensions=tuple(dimensions),
        activation_state=RelationshipActivationState.ACTIVE,
        current_revision_id=RelationshipRevisionId(f"rrev-{target.value}"),
        revision_ordinal=1,
        created_tick=1,
        updated_tick=1,
        policy=policy,
    )


def test_respect_penalty_follows_trust_and_need(
    caplog: pytest.LogCaptureFixture,
) -> None:
    from agents.cognition.models import ActionDirection

    caplog.set_level(logging.DEBUG, logger=_LOGGER)
    owner = _agent("owner-a")
    other = _agent("owner-b")
    place = _entity("place-1")
    heard = _item(
        owner,
        place,
        channel=ClaimChannel.TESTIMONY,
        source=other,
        lineage_ref="heard-1",
        delta=0.40,
    )
    ledger = TerritorialClaimLedger(
        owner_id=owner,
        claims=(_claim(owner, place, strength=0.40, evidence=(heard,)),),
    )

    class _Future:
        def __init__(
            self, future_id: str, direction: ActionDirection, target: str
        ) -> None:
            self.future_id = future_id
            self.direction = direction
            self.target_entity_id = target

    futures = (
        _Future("move-there", ActionDirection.MOVE, "place-1"),
        _Future("wait-here", ActionDirection.WAIT, "place-1"),
    )
    high = territorial_respect_penalties(
        owner_id=owner,
        futures=futures,
        ledger=ledger,
        relationships=(
            _relationship(
                owner,
                other,
                trust=_signed_trust(0.80),
                resentment=0.0,
                fear=0.0,
            ),
        ),
        hunger=0.0,
        thirst=0.0,
        mode=CognitionTerritorialClaimMode.DETERMINISTIC,
    )
    assert high["move-there"] == -0.35
    assert "wait-here" not in high
    hungry = territorial_respect_penalties(
        owner_id=owner,
        futures=futures,
        ledger=ledger,
        relationships=(
            _relationship(
                owner,
                other,
                trust=_signed_trust(0.80),
                resentment=0.0,
                fear=0.0,
            ),
        ),
        hunger=75.0,
        thirst=0.0,
        mode=CognitionTerritorialClaimMode.DETERMINISTIC,
    )
    low = territorial_respect_penalties(
        owner_id=owner,
        futures=futures,
        ledger=ledger,
        relationships=(
            _relationship(
                owner,
                other,
                trust=_signed_trust(0.39),
                resentment=0.0,
                fear=0.0,
            ),
        ),
        hunger=0.0,
        thirst=0.0,
        mode=CognitionTerritorialClaimMode.DETERMINISTIC,
    )
    neutral = territorial_respect_penalties(
        owner_id=owner,
        futures=futures,
        ledger=ledger,
        relationships=(
            _relationship(
                owner, other, trust=_signed_trust(0.50), resentment=0.0, fear=0.0
            ),
        ),
        hunger=0.0,
        thirst=0.0,
        mode=CognitionTerritorialClaimMode.DETERMINISTIC,
    )
    missing = territorial_respect_penalties(
        owner_id=owner,
        futures=futures,
        ledger=ledger,
        relationships=(),
        hunger=0.0,
        thirst=0.0,
        mode=CognitionTerritorialClaimMode.DETERMINISTIC,
    )
    assert hungry["move-there"] == 0.0
    assert low["move-there"] == 0.0
    assert neutral["move-there"] == 0.0
    assert missing["move-there"] == 0.0
    messages = [record.getMessage() for record in caplog.records]
    assert any("reason=ignore_need direction=move" in message for message in messages)
    assert any(
        "reason=ignore_relationship direction=move" in message for message in messages
    )
    assert any(
        "reason=relationship_neutral direction=move" in message for message in messages
    )
    assert any(
        "reason=source_relationship_missing direction=move" in message
        for message in messages
    )
    assert territorial_respect_penalties(
        owner_id=owner,
        futures=futures,
        ledger=ledger,
        relationships=(),
        hunger=0.0,
        thirst=0.0,
        mode=CognitionTerritorialClaimMode.DISABLED,
    ) == {}


def test_wait_becomes_claim_challenge_or_defense(
    caplog: pytest.LogCaptureFixture,
) -> None:
    from dataclasses import replace

    from world.actions import Eat, Flee, Tell, Wait
    from world.models import LifeStatus
    from world.observations import CoarseHealth, VisibleBody

    caplog.set_level(logging.DEBUG, logger=_LOGGER)
    owner = _agent("owner-a")
    other = _agent("owner-b")
    place = _entity("place-1")
    body = _self("body-a", "place-1")
    observation = replace(
        _observation(body=body),
        visible_bodies=(
            VisibleBody(
                entity_id=EntityId("body-b"),
                life_status=LifeStatus.ALIVE,
                coarse_health=CoarseHealth.STABLE,
            ),
        ),
    )
    identity = OwnerSafeSocialIdentity(
        owner_id=owner,
        owner_entity_id=EntityId("body-a"),
        counterparts=(
            CounterpartBinding(agent_id=other, entity_id=EntityId("body-b")),
        ),
    )
    quiet = TerritorialClaimLedger(
        owner_id=owner,
        claims=(_claim(owner, place, strength=0.39),),
    )
    announced = TerritorialClaimLedger(
        owner_id=owner,
        claims=(_claim(owner, place, strength=0.40),),
    )
    command, audits = territorial_wait_replacement(
        Wait(),
        owner_id=owner,
        tick=observation.tick,
        observation=observation,
        identity=identity,
        ledger=announced,
        relationships=(),
        mode=CognitionTerritorialClaimMode.DETERMINISTIC,
    )
    assert type(command) is Tell
    assert command.utterance.content.text == "claims"
    assert audits is not None and audits[0].reason_code == "communicate"
    held, held_audits = territorial_wait_replacement(
        Wait(),
        owner_id=owner,
        tick=observation.tick,
        observation=observation,
        identity=identity,
        ledger=quiet,
        relationships=(),
        mode=CognitionTerritorialClaimMode.DETERMINISTIC,
    )
    assert type(held) is Wait
    assert held_audits == ()
    meal, _meal_audits = territorial_wait_replacement(
        Eat(EntityId("item-1")),
        owner_id=owner,
        tick=observation.tick,
        observation=observation,
        identity=identity,
        ledger=announced,
        relationships=(),
        mode=CognitionTerritorialClaimMode.DETERMINISTIC,
    )
    assert type(meal) is Eat
    breach = _observation(
        _occurrence("take", actor="body-b", event="evt-take", other="item-1"),
        body=body,
    )
    breach = replace(
        breach,
        visible_bodies=observation.visible_bodies,
    )
    evidence = (
        _item(owner, place, ordinal=0, lineage_ref="direct-1"),
        _item(
            owner,
            place,
            ordinal=1,
            channel=ClaimChannel.VIOLATION,
            source=other,
            lineage_ref="evt-take",
            tick=breach.tick,
            delta=0.25,
        ),
    )
    claimed = TerritorialClaimLedger(
        owner_id=owner,
        claims=(
            _claim(
                owner,
                place,
                evidence=evidence,
                contradiction_mass=0.25,
            ),
        ),
    )
    defend, defend_audits = territorial_wait_replacement(
        Wait(),
        owner_id=owner,
        tick=breach.tick,
        observation=breach,
        identity=identity,
        ledger=claimed,
        relationships=(
            _relationship(owner, other, trust=0.0, resentment=0.40, fear=0.59),
        ),
        mode=CognitionTerritorialClaimMode.DETERMINISTIC,
    )
    challenge, challenge_audits = territorial_wait_replacement(
        Wait(),
        owner_id=owner,
        tick=breach.tick,
        observation=breach,
        identity=identity,
        ledger=claimed,
        relationships=(
            _relationship(owner, other, trust=0.0, resentment=0.40, fear=0.60),
        ),
        mode=CognitionTerritorialClaimMode.DETERMINISTIC,
    )
    fled, fled_audits = territorial_wait_replacement(
        Flee(EntityId("body-b")),
        owner_id=owner,
        tick=breach.tick,
        observation=breach,
        identity=identity,
        ledger=claimed,
        relationships=(
            _relationship(owner, other, trust=0.0, resentment=0.40, fear=0.20),
        ),
        mode=CognitionTerritorialClaimMode.DETERMINISTIC,
    )
    disabled, disabled_audits = territorial_wait_replacement(
        Wait(),
        owner_id=owner,
        tick=breach.tick,
        observation=breach,
        identity=identity,
        ledger=claimed,
        relationships=(),
        mode=CognitionTerritorialClaimMode.DISABLED,
    )
    from world.actions import Attack

    assert type(defend) is Attack
    assert defend_audits is not None and defend_audits[0].reason_code == "defend"
    assert type(challenge) is Tell
    assert challenge.utterance.content.text == "disputes"
    assert (
        challenge_audits is not None
        and challenge_audits[0].reason_code == "challenge"
    )
    assert type(fled) is Flee
    assert fled_audits == ()
    assert type(disabled) is Wait
    assert disabled_audits is None
    messages = [record.getMessage() for record in caplog.records]
    assert any(
        "territorial_tell owner_id=owner-a predicate=claims target_kind=location"
        in message
        for message in messages
    )
    assert any(
        "territorial_response owner_id=owner-a reason=defend command=Attack"
        in message
        for message in messages
    )
    assert any("reason=command_already_selected" in message for message in messages)
