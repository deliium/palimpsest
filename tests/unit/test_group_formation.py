"""Owner-scoped group formation contracts."""

from __future__ import annotations

import dataclasses
import hashlib
import logging

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
    default_group_formation_policy,
    empty_group_ledger,
    group_belief_id,
    group_concept_id,
    group_evidence_id,
)
from agents.models import AgentId
from simulation.runner_models import GroupFormationMode

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
