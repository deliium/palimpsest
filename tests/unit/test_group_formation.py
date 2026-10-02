"""Owner-scoped group formation contracts."""

from __future__ import annotations

import dataclasses
import hashlib
import logging
from pathlib import Path

import pytest

from agents.cognition.configuration import CognitionGroupFormationMode
from agents.cognition.group_formation import (
    GROUP_FORMATION_POLICY_VERSION,
    GroupChannel,
    GroupConcept,
    GroupEvidenceItem,
    GroupFormationPolicy,
    GroupLedger,
    GroupMembershipBelief,
    GroupStance,
    GroupStatus,
    apply_group_update,
    default_group_formation_policy,
    empty_group_ledger,
    group_belief_id,
    group_concept_id,
    group_evidence_id,
)
from agents.cognition.models import CounterpartBinding, OwnerSafeSocialIdentity
from agents.models import AgentId
from simulation.runner_models import GroupFormationMode
from world.communications import (
    CommunicationContent,
    CommunicationId,
    CommunicationSourceBasis,
    DeclaredTransmission,
    StructuredUtterance,
)
from world.identifiers import EntityId, EventId, WorldId, WorldRevision
from world.models import LifeStatus
from world.observations import (
    CoarseHealth,
    Observation,
    ObservationAudienceRole,
    ObservationProvenance,
    ObservationSourceKind,
    ObservedCommunication,
    ObservedOccurrence,
    VisibleBody,
)

_BANNED_FIELDS = frozenset(
    {"team", "faction", "enemy", "friend", "leader", "shared_enemies"}
)


def _agent(value: str) -> AgentId:
    return AgentId(value)


def _members() -> tuple[AgentId, AgentId]:
    return (_agent("owner-a"), _agent("other-b"))


def _belief(**overrides: object) -> GroupMembershipBelief:
    owner = _agent("owner-a")
    members = _members()
    stance = GroupStance.WE
    payload: dict[str, object] = {
        "belief_id": group_belief_id(owner, stance, members),
        "owner_id": owner,
        "stance": stance,
        "member_ids": members,
        "support": 0.25,
        "social_evidence": False,
        "status": GroupStatus.ACTIVE,
    }
    payload.update(overrides)
    return GroupMembershipBelief(**payload)  # type: ignore[arg-type]


def test_policy_locks_thresholds() -> None:
    policy = default_group_formation_policy()
    assert policy.version == GROUP_FORMATION_POLICY_VERSION == "group-formation.v1"
    assert policy.concept_threshold == 0.4
    assert policy.retire_threshold == 0.2
    assert policy.decay == 0.05
    assert policy.trust_floor == 0.6
    assert policy.merge_jaccard == 0.5
    assert policy.max_beliefs == 16
    assert policy.max_concepts == 8
    assert policy.max_evidence == 64
    assert policy.min_set_size == 2
    assert policy.max_set_size == 8
    with pytest.raises(ValueError, match="unsupported_policy"):
        GroupFormationPolicy(concept_threshold=0.5)


def test_modes_match_and_disabled_is_default() -> None:
    assert CognitionGroupFormationMode.DISABLED.value == "disabled"
    assert CognitionGroupFormationMode.DETERMINISTIC.value == "deterministic"
    assert [mode.value for mode in CognitionGroupFormationMode] == [
        mode.value for mode in GroupFormationMode
    ]


def test_ids_follow_sorted_members_and_literal_concept() -> None:
    owner = _agent("owner-a")
    members = (_agent("other-b"), owner)
    belief = group_belief_id(owner, GroupStance.WE, members)
    ordered = f"{owner.value}|we|other-b,owner-a"
    assert belief == hashlib.sha256(ordered.encode("utf-8")).hexdigest()
    assert group_belief_id(owner, GroupStance.WE, _members()) == belief
    concept = group_concept_id(belief)
    assert concept == hashlib.sha256(f"{belief}|concept".encode()).hexdigest()
    evidence = group_evidence_id(
        belief_id=belief,
        ordinal=0,
        channel=GroupChannel.PROXIMITY,
        lineage_ref="1:other-b",
    )
    material = f"{belief}|0|proximity|1:other-b"
    assert evidence == hashlib.sha256(material.encode("utf-8")).hexdigest()


def test_records_omit_banned_field_names() -> None:
    for model in (
        GroupEvidenceItem,
        GroupMembershipBelief,
        GroupConcept,
        GroupLedger,
        GroupFormationPolicy,
    ):
        names = {item.name for item in dataclasses.fields(model)}
        assert names.isdisjoint(_BANNED_FIELDS)


def test_concept_rejects_we_missing_evidence_and_owner_rules(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.ERROR, logger="agents.cognition.group_formation")
    owner = _agent("owner-a")
    members = _members()
    belief_id = group_belief_id(owner, GroupStance.OUR_GROUP, members)
    with pytest.raises(ValueError, match="social_evidence_required"):
        GroupConcept(
            concept_id=group_concept_id(belief_id),
            belief_id=belief_id,
            owner_id=owner,
            stance=GroupStance.OUR_GROUP,
            member_ids=members,
            support=0.4,
            social_evidence=False,
            status=GroupStatus.ACTIVE,
        )
    we_id = group_belief_id(owner, GroupStance.WE, members)
    with pytest.raises(ValueError, match="concept_stance"):
        GroupConcept(
            concept_id=group_concept_id(we_id),
            belief_id=we_id,
            owner_id=owner,
            stance=GroupStance.WE,
            member_ids=members,
            support=0.4,
            social_evidence=True,
            status=GroupStatus.ACTIVE,
        )
    with pytest.raises(ValueError, match="owner_in_exclusive"):
        group_belief_id(owner, GroupStance.THOSE_AGENTS, members)
    outsiders = (_agent("south-a"), _agent("south-b"))
    with pytest.raises(ValueError, match="owner_missing"):
        group_belief_id(owner, GroupStance.OUR_GROUP, outsiders)
    with pytest.raises(ValueError, match="set_size"):
        group_belief_id(owner, GroupStance.WE, (owner,))
    with pytest.raises(ValueError, match="not_finite"):
        _belief(support=float("nan"))
    assert any(
        "field=social_evidence reason_code=social_evidence_required"
        in record.getMessage()
        for record in caplog.records
    )
    assert all("other-b" not in record.getMessage() for record in caplog.records)


def test_ledger_construction_log_omits_stance_and_members(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger="agents.cognition.group_formation")
    owner = _agent("owner-a")
    empty_group_ledger(owner)
    messages = [
        record.getMessage()
        for record in caplog.records
        if record.name == "agents.cognition.group_formation"
    ]
    constructed = [
        message for message in messages if "group_ledger_constructed" in message
    ]
    assert constructed
    text = constructed[-1]
    assert "owner_id=owner-a" in text
    assert "policy_version=group-formation.v1" in text
    assert "belief_count=0" in text
    assert "concept_count=0" in text
    assert "stance=" not in text
    assert "other-b" not in text
    assert "those_agents" not in text
    assert "our_group" not in text


def test_runner_v16_round_trip_and_closed_gates(
    caplog: pytest.LogCaptureFixture,
) -> None:
    import json
    from dataclasses import replace

    from simulation.runner import _cognition_config_for
    from simulation.runner_models import (
        RUNNER_SCHEMA_VERSION,
        RUNNER_SCHEMA_VERSION_V15,
        RUNNER_SCHEMA_VERSION_V16,
        CognitionTraceDetail,
        CognitionTraceSpec,
        MortalityMode,
        TerritorialClaimMode,
        V2CapabilityFlags,
    )
    from simulation.runner_serialization import (
        decode_runner_config,
        encode_runner_config,
    )
    from tests.unit.test_runner_serialization import _configured
    from world.environment import example_environmental_dynamics

    assert RUNNER_SCHEMA_VERSION == "runner-config-v4"
    flags = V2CapabilityFlags(multi_hop_testimony_tracking=True)
    assert flags.unimplemented_enabled_names() == ("multi_hop_testimony_tracking",)

    base = _configured(schema_version=RUNNER_SCHEMA_VERSION)
    quiet = json.loads(encode_runner_config(base).decode("utf-8"))
    assert quiet["schema_version"] == "runner-config-v4"
    assert "group_formation_mode" not in quiet["agents"][0]["cognition"]
    agent = base.agents[0]
    early = replace(
        agent,
        cognition=replace(
            agent.cognition,
            group_formation_mode=GroupFormationMode.DETERMINISTIC,
        ),
    )
    with pytest.raises(ValueError, match="group_formation_mode_requires_v16"):
        replace(base, agents=(early,))
    territorial_only = replace(
        agent,
        cognition=replace(
            agent.cognition,
            territorial_claim_mode=TerritorialClaimMode.DETERMINISTIC,
        ),
    )
    territorial = replace(
        base,
        agents=(territorial_only,),
        schema_version=RUNNER_SCHEMA_VERSION_V15,
    )
    territorial_doc = json.loads(encode_runner_config(territorial).decode("utf-8"))
    assert territorial_doc["schema_version"] == "runner-config-v15"
    assert "group_formation_mode" not in territorial_doc["agents"][0]["cognition"]
    with pytest.raises(ValueError, match="v16_requires_group_formation"):
        replace(territorial, schema_version=RUNNER_SCHEMA_VERSION_V16)
    enabled = replace(
        base,
        agents=(early,),
        schema_version=RUNNER_SCHEMA_VERSION_V16,
    )
    encoded = encode_runner_config(enabled)
    document = json.loads(encoded.decode("utf-8"))
    assert document["schema_version"] == "runner-config-v16"
    assert document["agents"][0]["cognition"]["group_formation_mode"] == "deterministic"
    assert decode_runner_config(encoded) == enabled
    both = replace(
        early,
        cognition=replace(
            early.cognition,
            territorial_claim_mode=TerritorialClaimMode.DETERMINISTIC,
        ),
    )
    paired = replace(base, agents=(both,), schema_version=RUNNER_SCHEMA_VERSION_V16)
    paired_doc = json.loads(encode_runner_config(paired).decode("utf-8"))
    assert paired_doc["schema_version"] == "runner-config-v16"
    assert paired_doc["agents"][0]["cognition"]["territorial_claim_mode"] == (
        "deterministic"
    )
    traced = replace(
        paired,
        environmental_dynamics=example_environmental_dynamics(),
        capability_flags=V2CapabilityFlags(extended_self_model=True),
        cognition_trace=CognitionTraceSpec(
            enabled=True,
            detail=CognitionTraceDetail.SUMMARY,
        ),
    )
    traced_doc = json.loads(encode_runner_config(traced).decode("utf-8"))
    assert traced_doc["schema_version"] == "runner-config-v16"
    assert "environmental_dynamics" in traced_doc
    assert traced_doc["capability_flags"]["extended_self_model"] is True
    assert traced_doc["cognition_trace"]["enabled"] is True
    assert decode_runner_config(encode_runner_config(traced)) == traced
    caplog.set_level(logging.DEBUG, logger="simulation.runner")
    built = _cognition_config_for(
        early.cognition,
        mortality_mode=MortalityMode.ENABLED,
        capability_flags=V2CapabilityFlags(),
    )
    assert built.group_formation_mode is CognitionGroupFormationMode.DETERMINISTIC
    assert built.group_formation_policy is not None
    assert built.group_formation_policy.version == "group-formation.v1"
    assert any(
        "cognition_config_group_formation_mode mode=deterministic "
        "policy_version=group-formation.v1" in record.getMessage()
        for record in caplog.records
    )


def _binding(agent: str, entity: str) -> CounterpartBinding:
    return CounterpartBinding(agent_id=_agent(agent), entity_id=EntityId(entity))


def _social(
    owner: str, entity: str, pairs: tuple[tuple[str, str], ...]
) -> OwnerSafeSocialIdentity:
    ordered = tuple(sorted(pairs, key=lambda item: item[1]))
    return OwnerSafeSocialIdentity(
        owner_id=_agent(owner),
        owner_entity_id=EntityId(entity),
        counterparts=tuple(_binding(agent, body) for agent, body in ordered),
    )


def _north_identity(owner: str = "north_a") -> OwnerSafeSocialIdentity:
    entities = {
        "north_a": "body-a",
        "north_b": "body-b",
        "lone": "body-l",
        "south_a": "body-s",
        "south_b": "body-t",
    }
    pairs = tuple(
        (agent, body) for agent, body in entities.items() if agent != owner
    )
    return _social(owner, entities[owner], pairs)


def _occur(
    kind: str,
    actor: str,
    other: str,
    event: str,
    *,
    tick: int = 1,
    success: bool | None = True,
) -> ObservedOccurrence:
    return ObservedOccurrence(
        provenance=ObservationProvenance(
            source_kind=ObservationSourceKind.OCCURRENCE,
            source_tick=tick,
            source_event_id=EventId(event),
        ),
        kind=kind,
        audience_role=ObservationAudienceRole.WITNESS,
        actor_id=EntityId(actor),
        other_entity_id=EntityId(other),
        success=success,
    )


def _body(entity: str) -> VisibleBody:
    return VisibleBody(
        entity_id=EntityId(entity),
        life_status=LifeStatus.ALIVE,
        coarse_health=CoarseHealth.STABLE,
    )


def _talk(
    speaker: str,
    listener: str,
    event: str,
    *,
    hop: int = 0,
    tick: int = 1,
) -> ObservedCommunication:
    chain = [EntityId(f"hop-{index}") for index in range(hop + 1)]
    chain[-1] = EntityId(speaker)
    root = CommunicationId(f"{event}-root")
    current = root if hop == 0 else CommunicationId(event)
    return ObservedCommunication(
        provenance=ObservationProvenance(
            source_kind=ObservationSourceKind.COMMUNICATION,
            source_tick=tick,
            source_event_id=EventId(event),
        ),
        speaker_id=EntityId(speaker),
        listener_id=EntityId(listener),
        action_kind="talk",
        utterance=StructuredUtterance(
            content=CommunicationContent(text="seen"),
            declared=DeclaredTransmission(
                communication_id=current,
                immediate_source_id=EntityId(speaker),
                parent_communication_id=None if hop == 0 else root,
                root_communication_id=(
                    root if hop == 0 else CommunicationId(f"{event}-origin")
                ),
                source_agent_chain=tuple(chain),
                hop_count=hop,
                sender_confidence=0.5,
                source_basis=CommunicationSourceBasis.UNREFERENCED,
            ),
        ),
    )


def _observe(
    *,
    tick: int = 2,
    owner_entity: str = "body-a",
    bodies: tuple[VisibleBody, ...] = (),
    occurrences: tuple[ObservedOccurrence, ...] = (),
    communications: tuple[ObservedCommunication, ...] = (),
) -> Observation:
    return Observation(
        world_id=WorldId("world-w"),
        observer_id=EntityId(owner_entity),
        revision=WorldRevision(1),
        tick=tick,
        visible_bodies=bodies,
        occurrences=occurrences,
        communications=communications,
    )


def _update(
    observation: Observation,
    *,
    owner: str = "north_a",
    ledger: GroupLedger | None = None,
    trust: dict[str, float] | None = None,
) -> GroupLedger:
    return apply_group_update(
        observation,
        _north_identity(owner),
        {} if trust is None else trust,
        ledger,
    )


def _active(
    ledger: GroupLedger, stance: GroupStance
) -> tuple[GroupMembershipBelief, ...]:
    return tuple(
        belief
        for belief in ledger.beliefs
        if belief.status is GroupStatus.ACTIVE and belief.stance is stance
    )


def _concept(
    owner: AgentId,
    stance: GroupStance,
    members: tuple[AgentId, ...],
    *,
    support: float,
    status: GroupStatus = GroupStatus.ACTIVE,
    parent_ids: tuple[str, ...] = (),
) -> tuple[GroupMembershipBelief, GroupConcept]:
    belief_id = group_belief_id(owner, stance, members)
    belief = GroupMembershipBelief(
        belief_id=belief_id,
        owner_id=owner,
        stance=stance,
        member_ids=members,
        support=support,
        social_evidence=True,
        status=status,
    )
    concept = GroupConcept(
        concept_id=group_concept_id(belief_id),
        belief_id=belief_id,
        owner_id=owner,
        stance=stance,
        member_ids=members,
        support=support,
        social_evidence=True,
        status=status,
        parent_ids=parent_ids,
    )
    return belief, concept


def test_proximity_trust_and_forbidden_inputs(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG, logger="agents.cognition.group_formation")
    observation = _observe(tick=3, bodies=(_body("body-b"), _body("missing-body")))
    ledger = _update(observation, trust={"north_b": 0.6, "lone": 0.4})
    beliefs = _active(ledger, GroupStance.WE)
    assert len(beliefs) == 1
    assert beliefs[0].support == 0.2
    assert beliefs[0].social_evidence is False
    assert ledger.concepts == ()
    assert "proximity_only" not in ledger.notices
    assert "unresolved_entity" in ledger.notices
    assert any(
        "group_belief_applied" in record.getMessage()
        and "channel=proximity" in record.getMessage()
        and "sign=positive" in record.getMessage()
        for record in caplog.records
    )
    assert any(
        "group_evidence_dropped" in record.getMessage()
        and "reason=unresolved_entity" in record.getMessage()
        for record in caplog.records
    )
    assert all("body-b" not in record.getMessage() for record in caplog.records)

    class WorldState:
        pass

    class WorldEvent:
        pass

    class CandidateCluster:
        pass

    identity = _north_identity()
    with pytest.raises(TypeError):
        apply_group_update(WorldState(), identity, {}, None)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        apply_group_update(observation, WorldEvent(), {}, None)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        apply_group_update(observation, identity, CandidateCluster(), None)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="owner_mismatch"):
        apply_group_update(observation, _north_identity("north_b"), {}, ledger)


def test_help_exchange_and_communication_evidence(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger="agents.cognition.group_formation")
    one_way = _update(
        _observe(
            occurrences=(
                _occur("help", "body-a", "body-b", "help-1"),
                _occur("sleep", "body-a", "body-b", "sleep-1"),
            )
        )
    )
    we = _active(one_way, GroupStance.WE)
    assert len(we) == 1
    assert we[0].support == 0.25
    assert we[0].social_evidence is False
    assert one_way.concepts == ()
    assert "ignored_kind" in one_way.notices
    both = _update(
        _observe(
            occurrences=(
                _occur("help", "body-a", "body-b", "help-1"),
                _occur("help", "body-b", "body-a", "help-2"),
            )
        )
    )
    groups = _active(both, GroupStance.OUR_GROUP)
    assert len(groups) == 1
    assert {member.value for member in groups[0].member_ids} == {"north_a", "north_b"}
    assert groups[0].social_evidence is True
    assert groups[0].support == 0.5
    assert len(both.concepts) == 1
    assert both.concepts[0].status is GroupStatus.ACTIVE
    witnessed = _update(
        _observe(
            owner_entity="body-b",
            occurrences=(_occur("give", "body-s", "body-t", "give-1"),),
        ),
        owner="north_b",
    )
    exclusive = _active(witnessed, GroupStance.THOSE_AGENTS)
    assert len(exclusive) == 1
    assert exclusive[0].support == 0.3
    assert exclusive[0].social_evidence is True
    assert witnessed.concepts == ()
    assert "below_threshold" in witnessed.notices
    talked = _update(
        _observe(communications=(_talk("body-a", "body-b", "talk-1"),))
    )
    assert _active(talked, GroupStance.WE)[0].support == 0.2
    assert _active(talked, GroupStance.WE)[0].social_evidence is True
    dropped = _update(
        _observe(communications=(_talk("body-a", "body-b", "talk-2", hop=2),))
    )
    assert dropped.beliefs == ()
    assert "hop_dropped" in dropped.notices
    assert any(
        "channel=assistance" in record.getMessage()
        and "sign=positive" in record.getMessage()
        for record in caplog.records
    )


def test_updater_does_not_revise_other_ledgers() -> None:
    source = Path("src/agents/cognition/group_formation.py").read_text()
    for name in (
        "revise_semantic_belief",
        "merge_relationship_revision",
        "apply_reputation_update",
        "apply_territorial_update",
    ):
        assert name not in source


def test_two_owners_keep_asymmetric_concepts() -> None:
    shared = (
        _occur("help", "body-a", "body-b", "help-ab"),
        _occur("help", "body-b", "body-a", "help-ba"),
        _occur("help", "body-a", "body-l", "help-al"),
        _occur("help", "body-l", "body-a", "help-la"),
    )
    north_a = _update(_observe(occurrences=shared))
    north_b = _update(
        _observe(
            owner_entity="body-b",
            occurrences=shared,
            communications=(_talk("body-s", "body-t", "talk-south"),),
        ),
        owner="north_b",
    )
    inclusive = {
        frozenset(member.value for member in concept.member_ids)
        for concept in north_a.concepts
        if concept.status is GroupStatus.ACTIVE
        and concept.stance is GroupStance.OUR_GROUP
    }
    assert inclusive == {
        frozenset({"north_a", "north_b"}),
        frozenset({"north_a", "lone"}),
    }
    exclusive = _active(north_b, GroupStance.THOSE_AGENTS)
    assert any(
        {member.value for member in belief.member_ids} == {"south_a", "south_b"}
        for belief in exclusive
    )
    b_inclusive = {
        frozenset(member.value for member in concept.member_ids)
        for concept in north_b.concepts
        if concept.stance is GroupStance.OUR_GROUP
    }
    assert frozenset({"north_a", "lone"}) not in b_inclusive
    assert north_a.owner_id != north_b.owner_id
    assert north_a is not north_b


def test_repeated_proximity_withholds_concept_and_caps() -> None:
    ledger = None
    for tick in range(1, 5):
        ledger = _update(
            _observe(tick=tick, bodies=(_body("body-b"),)),
            ledger=ledger,
        )
    assert ledger is not None
    belief = _active(ledger, GroupStance.WE)[0]
    assert belief.support == 0.4
    assert belief.social_evidence is False
    assert ledger.concepts == ()
    assert "proximity_only" in ledger.notices
    crowded = ledger
    for tick in range(5, 70):
        crowded = _update(
            _observe(tick=tick, bodies=(_body("body-b"),)),
            ledger=crowded,
        )
    stored = _active(crowded, GroupStance.WE)[0]
    assert len(stored.evidence) == 64
    assert "cap_exceeded" in crowded.notices


def test_decay_split_and_merge() -> None:
    owner = _agent("north_a")
    north_b = _agent("north_b")
    lone = _agent("lone")
    south = _agent("south_a")
    pair = _sorted_pair(owner, north_b)
    belief, concept = _concept(owner, GroupStance.OUR_GROUP, pair, support=0.4)
    ledger = GroupLedger(owner_id=owner, beliefs=(belief,), concepts=(concept,))
    for tick in range(3):
        ledger = _update(_observe(tick=tick + 1), ledger=ledger)
    active = _active(ledger, GroupStance.OUR_GROUP)
    assert active[0].support == 0.25
    assert active[0].status is GroupStatus.ACTIVE
    assert ledger.concepts[0].status is GroupStatus.ACTIVE
    assert ledger.concepts[0].support == 0.25
    low_belief, low_concept = _concept(
        owner, GroupStance.OUR_GROUP, pair, support=0.2
    )
    retired = _update(
        _observe(tick=9),
        ledger=GroupLedger(
            owner_id=owner, beliefs=(low_belief,), concepts=(low_concept,)
        ),
    )
    assert retired.beliefs[0].support == 0.15
    assert retired.beliefs[0].status is GroupStatus.RETIRED
    assert retired.concepts[0].status is GroupStatus.RETIRED
    members = _sorted_ids(owner, north_b, lone)
    parent_belief, parent_concept = _concept(
        owner, GroupStance.OUR_GROUP, members, support=0.4
    )
    split = _update(
        _observe(
            tick=5,
            occurrences=(
                _occur("attack", "body-s", "body-b", "atk-1", tick=4),
                _occur("attack", "body-s", "body-l", "atk-2", tick=4),
            ),
        ),
        ledger=GroupLedger(
            owner_id=owner, beliefs=(parent_belief,), concepts=(parent_concept,)
        ),
    )
    parent = next(
        item for item in split.concepts if item.concept_id == parent_concept.concept_id
    )
    assert parent.status is GroupStatus.SPLIT
    child = next(
        item for item in split.concepts if item.status is GroupStatus.ACTIVE
    )
    assert {member.value for member in child.member_ids} == {"north_a", "lone"}
    assert child.parent_ids == (parent.concept_id,)
    left_members = _sorted_ids(owner, north_b, lone)
    right_members = _sorted_ids(owner, north_b, south)
    left_belief, left_concept = _concept(
        owner, GroupStance.OUR_GROUP, left_members, support=0.4
    )
    right_belief, right_concept = _concept(
        owner, GroupStance.OUR_GROUP, right_members, support=0.55
    )
    merged = _update(
        _observe(tick=5),
        ledger=GroupLedger(
            owner_id=owner,
            beliefs=(left_belief, right_belief),
            concepts=(left_concept, right_concept),
        ),
    )
    child_concept = next(
        item for item in merged.concepts if item.status is GroupStatus.ACTIVE
    )
    assert {member.value for member in child_concept.member_ids} == {
        "north_a",
        "north_b",
        "lone",
        "south_a",
    }
    assert child_concept.support == 0.55
    assert set(child_concept.parent_ids) == {
        left_concept.concept_id,
        right_concept.concept_id,
    }
    assert "stance_mismatch" not in merged.notices


def _sorted_pair(left: AgentId, right: AgentId) -> tuple[AgentId, ...]:
    return tuple(sorted((left, right), key=lambda item: item.value))


def _sorted_ids(*agents: AgentId) -> tuple[AgentId, ...]:
    return tuple(sorted(agents, key=lambda item: item.value))


def test_overlap_stays_distinct_and_blocked_merges_are_recorded() -> None:
    owner = _agent("north_a")
    north_b = _agent("north_b")
    lone = _agent("lone")
    left_belief, left_concept = _concept(
        owner, GroupStance.OUR_GROUP, _sorted_pair(owner, north_b), support=0.4
    )
    right_belief, right_concept = _concept(
        owner, GroupStance.OUR_GROUP, _sorted_pair(owner, lone), support=0.4
    )
    distinct = _update(
        _observe(tick=3),
        ledger=GroupLedger(
            owner_id=owner,
            beliefs=(left_belief, right_belief),
            concepts=(left_concept, right_concept),
        ),
    )
    active = [
        concept for concept in distinct.concepts if concept.status is GroupStatus.ACTIVE
    ]
    assert len(active) == 2
    exclusive_belief, exclusive_concept = _concept(
        owner,
        GroupStance.THOSE_AGENTS,
        _sorted_ids(north_b, lone, _agent("south_a")),
        support=0.4,
    )
    inclusive_belief, inclusive_concept = _concept(
        owner,
        GroupStance.OUR_GROUP,
        _sorted_ids(owner, north_b, lone),
        support=0.4,
    )
    mismatch = _update(
        _observe(tick=4),
        ledger=GroupLedger(
            owner_id=owner,
            beliefs=(exclusive_belief, inclusive_belief),
            concepts=(exclusive_concept, inclusive_concept),
        ),
    )
    assert "stance_mismatch" in mismatch.notices
    assert sum(item.status is GroupStatus.ACTIVE for item in mismatch.concepts) == 2
    others = tuple(_agent(f"agent-{index}") for index in range(9))
    wide_left = _sorted_ids(owner, *others[:7])
    wide_right = _sorted_ids(owner, *others[:5], *others[7:])
    blocked_left = _concept(owner, GroupStance.OUR_GROUP, wide_left, support=0.4)
    blocked_right = _concept(owner, GroupStance.OUR_GROUP, wide_right, support=0.4)
    blocked = _update(
        _observe(tick=6),
        ledger=GroupLedger(
            owner_id=owner,
            beliefs=(blocked_left[0], blocked_right[0]),
            concepts=(blocked_left[1], blocked_right[1]),
        ),
    )
    assert "merge_blocked" in blocked.notices
    assert sum(item.status is GroupStatus.ACTIVE for item in blocked.concepts) == 2
