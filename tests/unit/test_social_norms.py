"""Owner-scoped social norm contracts and runner-config-v17 wiring."""

from __future__ import annotations

import logging

import pytest

from agents.cognition.configuration import CognitionSocialNormMode
from agents.cognition.social_norms import (
    SOCIAL_NORM_POLICY_VERSION,
    NormBelief,
    NormConsequence,
    NormConsequenceChannel,
    NormContext,
    NormExpectation,
    NormPattern,
    NormSanction,
    NormStatus,
    SocialNormPolicy,
    default_social_norm_policy,
    norm_belief_id,
)
from agents.models import AgentId
from simulation.runner_models import SocialNormMode


def _agent(value: str) -> AgentId:
    return AgentId(value)


def test_policy_locks_constants_and_modes_match() -> None:
    policy = default_social_norm_policy()
    assert policy.version == SOCIAL_NORM_POLICY_VERSION == "social-norms.v1"
    assert policy.active_confidence == 0.40
    assert policy.enforce_confidence == 0.50
    assert policy.retire_confidence == 0.20
    assert policy.decay == 0.05
    assert policy.conforming_delta == 0.15
    assert policy.violation_delta == -0.20
    assert policy.penalty == 0.35
    assert policy.conforming_count == 3
    assert policy.return_window_ticks == 8
    assert policy.spare_window_ticks == 1
    assert policy.utterance_interval == 4
    assert policy.exclusion_window_ticks == 8
    assert policy.scarcity_quantity == 1.0
    assert policy.critical_need_ratio == 0.75
    assert policy.trust_delta == -0.25
    assert policy.max_beliefs == 8
    assert policy.max_evidence == 32
    assert policy.max_supporters == 8
    with pytest.raises(ValueError, match="unsupported_policy"):
        SocialNormPolicy(active_confidence=0.5)
    assert [mode.value for mode in CognitionSocialNormMode] == [
        mode.value for mode in SocialNormMode
    ]
    assert CognitionSocialNormMode.DISABLED.value == "disabled"


def test_belief_rejects_mismatched_expectation_and_witnessed_own_sanctions() -> None:
    owner = _agent("ada")
    belief_id = norm_belief_id(owner, NormPattern.RETURN_TRANSFER, ())
    with pytest.raises(ValueError, match="pattern_mismatch"):
        NormBelief(
            belief_id=belief_id,
            owner_id=owner,
            pattern=NormPattern.RETURN_TRANSFER,
            expectation=NormExpectation.GIVE,
            context=NormContext(pattern=NormPattern.RETURN_TRANSFER),
            status=NormStatus.CANDIDATE,
            confidence=0.15,
        )
    with pytest.raises(ValueError, match="witnessed_forbidden"):
        NormConsequence(
            sanction=NormSanction.REFUSAL,
            channel=NormConsequenceChannel.WITNESSED,
            tick=1,
        )
    supporters = tuple(_agent(f"agent-{index}") for index in range(9))
    with pytest.raises(ValueError, match="cap_exceeded"):
        NormBelief(
            belief_id=norm_belief_id(owner, NormPattern.SHARE_UNDER_SCARCITY, ()),
            owner_id=owner,
            pattern=NormPattern.SHARE_UNDER_SCARCITY,
            expectation=NormExpectation.GIVE,
            context=NormContext(pattern=NormPattern.SHARE_UNDER_SCARCITY),
            status=NormStatus.CANDIDATE,
            confidence=0.15,
            supporters=supporters,
        )


def test_runner_v17_round_trips_social_norms(caplog: pytest.LogCaptureFixture) -> None:
    import json
    from dataclasses import replace

    from simulation.runner import _cognition_config_for
    from simulation.runner_models import (
        RUNNER_SCHEMA_VERSION,
        RUNNER_SCHEMA_VERSION_V16,
        RUNNER_SCHEMA_VERSION_V17,
        CognitionTraceDetail,
        CognitionTraceSpec,
        GroupFormationMode,
        MortalityMode,
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
    assert "social_norm_mode" not in quiet["agents"][0]["cognition"]
    agent = base.agents[0]
    early = replace(
        agent,
        cognition=replace(
            agent.cognition, social_norm_mode=SocialNormMode.DETERMINISTIC
        ),
    )
    with pytest.raises(ValueError, match="social_norm_mode_requires_v17"):
        replace(base, agents=(early,))
    grouped = replace(
        agent,
        cognition=replace(
            agent.cognition, group_formation_mode=GroupFormationMode.DETERMINISTIC
        ),
    )
    group_only = replace(
        base, agents=(grouped,), schema_version=RUNNER_SCHEMA_VERSION_V16
    )
    group_doc = json.loads(encode_runner_config(group_only).decode("utf-8"))
    assert group_doc["schema_version"] == "runner-config-v16"
    assert "social_norm_mode" not in group_doc["agents"][0]["cognition"]
    with pytest.raises(ValueError, match="v17_requires_social_norms"):
        replace(group_only, schema_version=RUNNER_SCHEMA_VERSION_V17)
    enabled = replace(base, agents=(early,), schema_version=RUNNER_SCHEMA_VERSION_V17)
    encoded = encode_runner_config(enabled)
    document = json.loads(encoded.decode("utf-8"))
    assert document["schema_version"] == "runner-config-v17"
    assert document["agents"][0]["cognition"]["social_norm_mode"] == "deterministic"
    assert decode_runner_config(encoded) == enabled
    both = replace(
        early,
        cognition=replace(
            early.cognition,
            group_formation_mode=GroupFormationMode.DETERMINISTIC,
        ),
    )
    traced = replace(
        base,
        agents=(both,),
        schema_version=RUNNER_SCHEMA_VERSION_V17,
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
    assert cognition["group_formation_mode"] == "deterministic"
    assert decode_runner_config(encode_runner_config(traced)) == traced
    caplog.set_level(logging.DEBUG, logger="simulation.runner")
    built = _cognition_config_for(
        early.cognition,
        mortality_mode=MortalityMode.ENABLED,
        capability_flags=V2CapabilityFlags(),
    )
    assert built.social_norm_mode is CognitionSocialNormMode.DETERMINISTIC
    assert built.social_norm_policy is not None
    assert built.social_norm_policy.version == "social-norms.v1"
    assert any(
        "cognition_config_social_norm_mode mode=deterministic "
        "policy_version=social-norms.v1" in record.getMessage()
        for record in caplog.records
    )
