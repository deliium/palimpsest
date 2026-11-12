"""V4-22 credit seam: activation, cognition config, runner wiring."""

from __future__ import annotations

import pytest

from agents.cognition import (
    CREDIT_RELATIONSHIPS_POLICY_VERSION,
    CreditRelationshipPolicy,
    build_cognitive_loop,
    default_credit_relationship_policy,
)
from agents.cognition.configuration import (
    CognitionCreditMode,
    CognitionLoopConfig,
)
from agents.models import AgentId
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V56,
    SUPPORTED_RUNNER_SCHEMA_VERSIONS,
    AgentCognitionSpec,
    MortalityMode,
    V2CapabilityFlags,
)

pytestmark = pytest.mark.unit


def test_disabled_mode_allocates_no_policy() -> None:
    config = CognitionLoopConfig()
    assert config.credit_relationship_mode is CognitionCreditMode.DISABLED
    assert config.credit_relationship_policy is None


def test_deterministic_mode_installs_the_locked_policy() -> None:
    config = CognitionLoopConfig(
        credit_relationship_mode=CognitionCreditMode.DETERMINISTIC
    )
    assert config.credit_relationship_policy is default_credit_relationship_policy()
    assert config.credit_relationship_policy.max_rows == 32


def test_custom_policy_is_preserved_and_invalid_type_fails_closed() -> None:
    custom = CreditRelationshipPolicy()
    config = CognitionLoopConfig(
        credit_relationship_mode=CognitionCreditMode.DETERMINISTIC,
        credit_relationship_policy=custom,
    )
    assert config.credit_relationship_policy is custom
    with pytest.raises(TypeError):
        CognitionLoopConfig(
            credit_relationship_mode=CognitionCreditMode.DETERMINISTIC,
            credit_relationship_policy=object(),  # type: ignore[arg-type]
        )
    with pytest.raises(TypeError):
        CognitionLoopConfig(credit_relationship_mode="enabled")  # type: ignore[arg-type]


def test_disabled_mode_clears_a_supplied_policy() -> None:
    config = CognitionLoopConfig(
        credit_relationship_policy=CreditRelationshipPolicy()
    )
    assert config.credit_relationship_mode is CognitionCreditMode.DISABLED
    assert config.credit_relationship_policy is None


def test_fingerprint_includes_credit_version_only_when_enabled() -> None:
    disabled = CognitionLoopConfig().condition_fingerprint_material()
    assert "credit_relationship_policy_version" not in disabled
    enabled = CognitionLoopConfig(
        credit_relationship_mode=CognitionCreditMode.DETERMINISTIC
    ).condition_fingerprint_material()
    assert enabled["credit_relationship_mode"] == "deterministic"
    assert enabled["credit_relationship_policy_version"] == (
        CREDIT_RELATIONSHIPS_POLICY_VERSION
    )


def test_build_cognitive_loop_forwards_the_credit_mode() -> None:
    loop = build_cognitive_loop(
        CognitionLoopConfig(
            credit_relationship_mode=CognitionCreditMode.DETERMINISTIC
        )
    )
    assert loop._credit_relationship_mode is CognitionCreditMode.DETERMINISTIC
    assert (
        loop._credit_relationship_policy is default_credit_relationship_policy()
    )
    disabled = build_cognitive_loop(CognitionLoopConfig())
    assert disabled._credit_relationship_policy is None


def test_runner_activation_requires_flag_and_commitments() -> None:
    from simulation.runner import _cognition_config_for

    assert RUNNER_SCHEMA_VERSION_V56 in SUPPORTED_RUNNER_SCHEMA_VERSIONS
    assert "runner-config-v57" not in SUPPORTED_RUNNER_SCHEMA_VERSIONS
    spec = AgentCognitionSpec(agent_id=AgentId("agent-1"))
    flag_off = _cognition_config_for(
        spec,
        mortality_mode=MortalityMode.DISABLED,
        capability_flags=V2CapabilityFlags(),
        markets_enabled=False,
        structured_commitments_active=True,
    )
    assert flag_off.credit_relationship_mode is CognitionCreditMode.DISABLED
    assert flag_off.credit_relationship_policy is None

    commitments_off = _cognition_config_for(
        spec,
        mortality_mode=MortalityMode.DISABLED,
        capability_flags=V2CapabilityFlags(),
        markets_enabled=True,
        structured_commitments_active=False,
    )
    assert (
        commitments_off.credit_relationship_mode
        is CognitionCreditMode.DISABLED
    )
    assert commitments_off.credit_relationship_policy is None

    both = _cognition_config_for(
        spec,
        mortality_mode=MortalityMode.DISABLED,
        capability_flags=V2CapabilityFlags(),
        markets_enabled=True,
        structured_commitments_active=True,
    )
    assert both.credit_relationship_mode is CognitionCreditMode.DETERMINISTIC
    assert both.credit_relationship_policy is default_credit_relationship_policy()
    assert both.market_institution_mode.value == "deterministic"


def test_market_and_price_wiring_unchanged_without_commitments() -> None:
    from simulation.runner import _cognition_config_for

    spec = AgentCognitionSpec(agent_id=AgentId("agent-1"))
    market_only = _cognition_config_for(
        spec,
        mortality_mode=MortalityMode.DISABLED,
        capability_flags=V2CapabilityFlags(),
        markets_enabled=True,
        structured_commitments_active=False,
        subjective_valuation_active=True,
    )
    assert market_only.market_institution_mode.value == "deterministic"
    assert market_only.price_expectation_mode.value == "deterministic"
    assert market_only.credit_relationship_mode is CognitionCreditMode.DISABLED
