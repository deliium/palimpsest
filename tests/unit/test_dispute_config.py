"""V4-07 dispute policy seam: cognition config and runner wiring."""

from __future__ import annotations

import pytest

from agents.cognition import (
    DISPUTE_POLICY_VERSION,
    DisputePolicy,
    default_dispute_policy,
)
from agents.cognition.configuration import (
    CognitionDisputeMode,
    CognitionLoopConfig,
)
from agents.models import AgentId
from simulation.runner import _cognition_config_for
from simulation.runner_models import (
    AgentCognitionSpec,
    MortalityMode,
    SimulationRunnerConfig,
    V2CapabilityFlags,
)

pytestmark = pytest.mark.unit


def test_default_dispute_mode_is_disabled_and_policy_is_none() -> None:
    config = CognitionLoopConfig()
    assert config.dispute_mode is CognitionDisputeMode.DISABLED
    assert config.dispute_policy is None


def test_deterministic_dispute_mode_installs_locked_policy() -> None:
    config = CognitionLoopConfig(dispute_mode=CognitionDisputeMode.DETERMINISTIC)
    assert config.dispute_policy is default_dispute_policy()
    assert config.dispute_policy is not None
    assert config.dispute_policy.version == DISPUTE_POLICY_VERSION


def test_disabled_mode_clears_supplied_policy() -> None:
    config = CognitionLoopConfig(
        dispute_mode=CognitionDisputeMode.DISABLED,
        dispute_policy=default_dispute_policy(),
    )
    assert config.dispute_policy is None


def test_foreign_policy_and_mode_types_are_rejected() -> None:
    with pytest.raises(TypeError, match="dispute_policy"):
        CognitionLoopConfig(
            dispute_mode=CognitionDisputeMode.DETERMINISTIC,
            dispute_policy=object(),  # type: ignore[arg-type]
        )

    with pytest.raises(TypeError, match="dispute_mode"):
        CognitionLoopConfig(
            dispute_mode="deterministic",  # type: ignore[arg-type]
        )


def test_explicit_policy_remains_locked() -> None:
    policy = default_dispute_policy()
    config = CognitionLoopConfig(
        dispute_mode=CognitionDisputeMode.DETERMINISTIC,
        dispute_policy=policy,
    )
    assert type(config.dispute_policy) is DisputePolicy
    assert config.dispute_policy is policy


def test_condition_fingerprint_omits_disabled_dispute_fields() -> None:
    disabled = CognitionLoopConfig().condition_fingerprint_material()
    other_disabled = CognitionLoopConfig().condition_fingerprint_material()
    assert disabled == other_disabled
    assert "dispute_mode" not in disabled
    assert "dispute_policy_version" not in disabled

    deterministic = CognitionLoopConfig(
        dispute_mode=CognitionDisputeMode.DETERMINISTIC
    ).condition_fingerprint_material()
    assert deterministic["dispute_mode"] == "deterministic"
    assert deterministic["dispute_policy_version"] == DISPUTE_POLICY_VERSION


def test_legal_disputes_flag_derives_deterministic_mode() -> None:
    spec = AgentCognitionSpec(agent_id=AgentId("agent-1"))

    disabled = _cognition_config_for(
        spec,
        mortality_mode=MortalityMode.DISABLED,
        capability_flags=V2CapabilityFlags(),
        legal_disputes_enabled=False,
    )
    assert disabled.dispute_mode is CognitionDisputeMode.DISABLED
    assert disabled.dispute_policy is None

    enabled = _cognition_config_for(
        spec,
        mortality_mode=MortalityMode.DISABLED,
        capability_flags=V2CapabilityFlags(),
        legal_disputes_enabled=True,
    )
    assert enabled.dispute_mode is CognitionDisputeMode.DETERMINISTIC
    assert enabled.dispute_policy is default_dispute_policy()


def test_no_per_agent_dispute_runner_key() -> None:
    spec = AgentCognitionSpec(agent_id=AgentId("agent-1"))
    assert not hasattr(spec, "dispute_mode")
    assert not hasattr(spec, "dispute_policy")
    assert "dispute_mode" not in SimulationRunnerConfig.__dataclass_fields__
    assert "dispute_policy" not in SimulationRunnerConfig.__dataclass_fields__
