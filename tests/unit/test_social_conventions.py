"""Owner-scoped social convention contracts and policy locks."""

from __future__ import annotations

import hashlib

import pytest

from agents.cognition.configuration import CognitionSocialConventionMode
from agents.cognition.social_conventions import (
    SOCIAL_CONVENTION_POLICY_VERSION,
    ConventionBelief,
    ConventionConceptualization,
    ConventionContent,
    ConventionEvidenceChannel,
    ConventionEvidenceItem,
    ConventionExplanation,
    ConventionLedger,
    ConventionSituation,
    ConventionStatus,
    ConventionTransmission,
    SocialConventionPolicy,
    convention_belief_id,
    convention_evidence_id,
    default_social_convention_policy,
    empty_convention_ledger,
    require_owner_social_conventions,
)
from agents.models import AgentId
from simulation.runner_models import SocialConventionMode
from world.identifiers import EntityId


def _agent(value: str) -> AgentId:
    return AgentId(value)


def _content(
    *,
    situation: ConventionSituation = ConventionSituation.COLOCATED_MEETING,
    usual_action: str = "wait",
) -> ConventionContent:
    return ConventionContent(situation=situation, usual_action=usual_action)


def test_policy_locks_constants_and_modes_match() -> None:
    policy = default_social_convention_policy()
    assert (
        policy.version
        == SOCIAL_CONVENTION_POLICY_VERSION
        == "social-conventions.v1"
    )
    assert policy.active_strength == 0.40
    assert policy.retire_strength == 0.20
    assert policy.decay == 0.05
    assert policy.conforming_colocated_meeting == 0.12
    assert policy.conforming_timed_gathering == 0.15
    assert policy.conforming_greeting_exchange == 0.12
    assert policy.conforming_habitual_exchange == 0.15
    assert policy.conforming_collective_action == 0.15
    assert policy.transmission_delta == 0.10
    assert policy.remembered_delta == 0.08
    assert policy.penalty == 0.30
    assert policy.promotion_count == 3
    assert policy.explanation_fade_ticks == 8
    assert policy.utterance_interval == 4
    assert policy.max_beliefs == 8
    assert policy.max_evidence == 32
    assert policy.max_participants == 8
    assert policy.max_variants == 4
    with pytest.raises(ValueError, match="unsupported_policy"):
        SocialConventionPolicy(active_strength=0.5)
    assert [mode.value for mode in CognitionSocialConventionMode] == [
        mode.value for mode in SocialConventionMode
    ]
    assert CognitionSocialConventionMode.DISABLED.value == "disabled"
    assert CognitionSocialConventionMode.DETERMINISTIC.value == "deterministic"


def test_belief_id_is_sha256_of_owner_and_content_key() -> None:
    owner = _agent("ada")
    content = _content()
    belief_id = convention_belief_id(owner, content)
    expected = hashlib.sha256(
        f"{owner.value}|{content.situation.value}|{content.usual_action}"
        f"|-|-|{content.counterpart_class.value}|-".encode()
    ).hexdigest()
    assert belief_id == expected
    assert len(belief_id) == 64


def test_belief_rejects_unknown_enums_and_oversized_participants() -> None:
    owner = _agent("ada")
    content = _content()
    belief_id = convention_belief_id(owner, content)
    with pytest.raises(ValueError, match="unknown_status"):
        ConventionBelief(
            belief_id=belief_id,
            owner_id=owner,
            content=content,
            status="active",  # type: ignore[arg-type]
            strength=0.4,
        )
    participants = tuple(_agent(f"p{index}") for index in range(9))
    with pytest.raises(ValueError, match="cap_exceeded"):
        ConventionBelief(
            belief_id=belief_id,
            owner_id=owner,
            content=content,
            status=ConventionStatus.CANDIDATE,
            strength=0.12,
            participant_ids=participants,
        )


def test_named_custom_requires_communicated_custom_lineage() -> None:
    owner = _agent("ada")
    content = _content(
        situation=ConventionSituation.GREETING_EXCHANGE,
        usual_action="talk",
    )
    belief_id = convention_belief_id(owner, content)
    with pytest.raises(ValueError, match="custom_lineage_required"):
        ConventionBelief(
            belief_id=belief_id,
            owner_id=owner,
            content=content,
            status=ConventionStatus.ACTIVE,
            strength=0.40,
            conceptualization=ConventionConceptualization.NAMED_CUSTOM,
        )
    evidence = ConventionEvidenceItem(
        evidence_id=convention_evidence_id(
            belief_id,
            0,
            ConventionEvidenceChannel.COMMUNICATED,
            "tick-1-0",
        ),
        ordinal=0,
        channel=ConventionEvidenceChannel.COMMUNICATED,
        lineage_ref="tick-1-0",
        tick=1,
        predicate="custom",
    )
    belief = ConventionBelief(
        belief_id=belief_id,
        owner_id=owner,
        content=content,
        status=ConventionStatus.ACTIVE,
        strength=0.40,
        conceptualization=ConventionConceptualization.NAMED_CUSTOM,
        transmission=ConventionTransmission.COMMUNICATED,
        remembered_explanation=ConventionExplanation.SOCIAL_CONTACT,
        evidence=(evidence,),
    )
    assert belief.conceptualization is ConventionConceptualization.NAMED_CUSTOM


def test_disabled_mode_accepts_none_ledger() -> None:
    owner = _agent("ada")
    require_owner_social_conventions(None, owner, field_name="social_conventions")
    ledger = empty_convention_ledger(owner)
    assert isinstance(ledger, ConventionLedger)
    assert ledger.beliefs == ()
    require_owner_social_conventions(
        ledger, owner, field_name="social_conventions"
    )
    with pytest.raises(ValueError, match="owner_id mismatch"):
        require_owner_social_conventions(
            ledger, _agent("ben"), field_name="social_conventions"
        )
    with pytest.raises(TypeError, match="ConventionLedger"):
        require_owner_social_conventions(
            object(), owner, field_name="social_conventions"
        )


def test_runner_v18_wires_deterministic_convention_mode(
    caplog: pytest.LogCaptureFixture,
) -> None:
    import json
    import logging
    from dataclasses import replace

    from agents.cognition.configuration import CognitionSocialConventionMode
    from simulation.runner import _cognition_config_for
    from simulation.runner_models import (
        RUNNER_SCHEMA_VERSION,
        RUNNER_SCHEMA_VERSION_V17,
        RUNNER_SCHEMA_VERSION_V18,
        CognitionTraceDetail,
        CognitionTraceSpec,
        GroupFormationMode,
        MortalityMode,
        SocialConventionMode,
        SocialNormMode,
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
    assert "social_convention_mode" not in quiet["agents"][0]["cognition"]
    agent = base.agents[0]
    early = replace(
        agent,
        cognition=replace(
            agent.cognition,
            social_convention_mode=SocialConventionMode.DETERMINISTIC,
        ),
    )
    with pytest.raises(ValueError, match="social_convention_mode_requires_v18"):
        replace(base, agents=(early,))
    norms_only = replace(
        agent,
        cognition=replace(
            agent.cognition, social_norm_mode=SocialNormMode.DETERMINISTIC
        ),
    )
    norms_config = replace(
        base, agents=(norms_only,), schema_version=RUNNER_SCHEMA_VERSION_V17
    )
    norms_doc = json.loads(encode_runner_config(norms_config).decode("utf-8"))
    assert norms_doc["schema_version"] == "runner-config-v17"
    assert "social_convention_mode" not in norms_doc["agents"][0]["cognition"]
    assert norms_doc["agents"][0]["cognition"]["social_norm_mode"] == "deterministic"
    with pytest.raises(ValueError, match="v18_requires_social_conventions"):
        replace(norms_config, schema_version=RUNNER_SCHEMA_VERSION_V18)
    enabled = replace(base, agents=(early,), schema_version=RUNNER_SCHEMA_VERSION_V18)
    encoded = encode_runner_config(enabled)
    document = json.loads(encoded.decode("utf-8"))
    assert document["schema_version"] == "runner-config-v18"
    assert (
        document["agents"][0]["cognition"]["social_convention_mode"] == "deterministic"
    )
    assert decode_runner_config(encoded) == enabled
    both = replace(
        early,
        cognition=replace(
            early.cognition,
            social_norm_mode=SocialNormMode.DETERMINISTIC,
            group_formation_mode=GroupFormationMode.DETERMINISTIC,
        ),
    )
    traced = replace(
        base,
        agents=(both,),
        schema_version=RUNNER_SCHEMA_VERSION_V18,
        environmental_dynamics=example_environmental_dynamics(),
        capability_flags=V2CapabilityFlags(extended_self_model=True),
        cognition_trace=CognitionTraceSpec(
            enabled=True,
            detail=CognitionTraceDetail.SUMMARY,
        ),
    )
    traced_doc = json.loads(encode_runner_config(traced).decode("utf-8"))
    assert traced_doc["capability_flags"]["extended_self_model"] is True
    assert traced_doc["cognition_trace"]["enabled"] is True
    assert "environmental_dynamics" in traced_doc
    cognition = traced_doc["agents"][0]["cognition"]
    assert cognition["social_norm_mode"] == "deterministic"
    assert cognition["social_convention_mode"] == "deterministic"
    assert cognition["group_formation_mode"] == "deterministic"
    assert decode_runner_config(encode_runner_config(traced)) == traced
    caplog.set_level(logging.DEBUG, logger="simulation.runner")
    built = _cognition_config_for(
        early.cognition,
        mortality_mode=MortalityMode.ENABLED,
        capability_flags=V2CapabilityFlags(),
    )
    assert built.social_convention_mode is CognitionSocialConventionMode.DETERMINISTIC
    assert built.social_convention_policy is not None
    assert built.social_convention_policy.version == "social-conventions.v1"
    assert any(
        "cognition_config_social_convention_mode mode=deterministic "
        "policy_version=social-conventions.v1" in record.getMessage()
        for record in caplog.records
    )


def test_content_rejects_unknown_situation_and_action() -> None:
    with pytest.raises(ValueError, match="unknown_situation"):
        ConventionContent(
            situation="ritual",  # type: ignore[arg-type]
            usual_action="wait",
        )
    with pytest.raises(ValueError, match="unknown_action"):
        ConventionContent(
            situation=ConventionSituation.COLOCATED_MEETING,
            usual_action="ritual",
        )
    with pytest.raises(ValueError, match="unexpected_day_phase"):
        from world.values import DayPhase

        ConventionContent(
            situation=ConventionSituation.COLOCATED_MEETING,
            usual_action="wait",
            day_phase=DayPhase.DAY,
        )
    location = EntityId("clearing")
    content = ConventionContent(
        situation=ConventionSituation.COLOCATED_MEETING,
        usual_action="wait",
        location_id=location,
    )
    assert content.location_id == location
