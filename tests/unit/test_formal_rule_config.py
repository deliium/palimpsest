"""V4-06 formal-rule policy seam: cognition config and runner wiring."""

from __future__ import annotations

import pytest

from agents.cognition import (
    FORMAL_RULE_POLICY_VERSION,
    FormalRulePolicy,
    default_formal_rule_policy,
)
from agents.cognition.configuration import (
    CognitionFormalRuleMode,
    CognitionLoopConfig,
)
from agents.models import AgentId
from simulation.runner import _cognition_config_for
from simulation.runner_models import (
    AgentCognitionSpec,
    MortalityMode,
    V2CapabilityFlags,
)

pytestmark = pytest.mark.unit


def test_default_config_is_disabled_and_allocates_no_policy() -> None:
    config = CognitionLoopConfig()
    assert config.formal_rule_mode is CognitionFormalRuleMode.DISABLED
    assert config.formal_rule_policy is None


def test_deterministic_mode_installs_the_locked_policy() -> None:
    config = CognitionLoopConfig(
        formal_rule_mode=CognitionFormalRuleMode.DETERMINISTIC
    )
    assert config.formal_rule_policy is default_formal_rule_policy()
    assert config.formal_rule_policy is not None
    assert config.formal_rule_policy.version == FORMAL_RULE_POLICY_VERSION


def test_disabled_mode_clears_a_supplied_policy() -> None:
    config = CognitionLoopConfig(
        formal_rule_mode=CognitionFormalRuleMode.DISABLED,
        formal_rule_policy=default_formal_rule_policy(),
    )
    assert config.formal_rule_policy is None


def test_foreign_policy_type_is_rejected() -> None:
    with pytest.raises(TypeError, match="formal_rule_policy"):
        CognitionLoopConfig(
            formal_rule_mode=CognitionFormalRuleMode.DETERMINISTIC,
            formal_rule_policy=object(),  # type: ignore[arg-type]
        )


def test_foreign_mode_type_is_rejected() -> None:
    with pytest.raises(TypeError, match="formal_rule_mode"):
        CognitionLoopConfig(
            formal_rule_mode="deterministic",  # type: ignore[arg-type]
        )


def test_policy_remains_locked_when_supplied_explicitly() -> None:
    policy = default_formal_rule_policy()
    config = CognitionLoopConfig(
        formal_rule_mode=CognitionFormalRuleMode.DETERMINISTIC,
        formal_rule_policy=policy,
    )
    assert type(config.formal_rule_policy) is FormalRulePolicy
    assert config.formal_rule_policy is policy


def test_runner_seam_derives_the_mode_from_the_owned_flag() -> None:
    spec = AgentCognitionSpec(agent_id=AgentId("agent-1"))

    disabled = _cognition_config_for(
        spec,
        mortality_mode=MortalityMode.DISABLED,
        capability_flags=V2CapabilityFlags(),
        formal_rules_enabled=False,
    )
    assert disabled.formal_rule_mode is CognitionFormalRuleMode.DISABLED
    assert disabled.formal_rule_policy is None

    enabled = _cognition_config_for(
        spec,
        mortality_mode=MortalityMode.DISABLED,
        capability_flags=V2CapabilityFlags(),
        formal_rules_enabled=True,
    )
    assert enabled.formal_rule_mode is CognitionFormalRuleMode.DETERMINISTIC
    assert enabled.formal_rule_policy is default_formal_rule_policy()


def test_fingerprint_tracks_the_mode_and_stays_stable_within_it() -> None:
    disabled = CognitionLoopConfig().condition_fingerprint_material()
    other_disabled = CognitionLoopConfig().condition_fingerprint_material()
    assert disabled == other_disabled
    assert "formal_rule_mode" not in disabled
    assert "formal_rule_policy_version" not in disabled

    enabled = CognitionLoopConfig(
        formal_rule_mode=CognitionFormalRuleMode.DETERMINISTIC
    ).condition_fingerprint_material()
    other_enabled = CognitionLoopConfig(
        formal_rule_mode=CognitionFormalRuleMode.DETERMINISTIC
    ).condition_fingerprint_material()
    assert enabled == other_enabled
    assert enabled != disabled
    assert enabled["formal_rule_mode"] == "deterministic"
    assert enabled["formal_rule_policy_version"] == FORMAL_RULE_POLICY_VERSION
