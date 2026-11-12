"""V4-21 price seam: activation, cognition config, runner wiring."""

from __future__ import annotations

import pytest

from agents.cognition import (
    EMERGENT_PRICES_POLICY_VERSION,
    EmergentPricePolicy,
    build_cognitive_loop,
    default_emergent_price_policy,
)
from agents.cognition.configuration import (
    CognitionLoopConfig,
    CognitionPriceMode,
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
    assert config.price_expectation_mode is CognitionPriceMode.DISABLED
    assert config.price_expectation_policy is None


def test_deterministic_mode_installs_the_locked_policy() -> None:
    config = CognitionLoopConfig(
        price_expectation_mode=CognitionPriceMode.DETERMINISTIC
    )
    assert config.price_expectation_policy is default_emergent_price_policy()
    assert config.price_expectation_policy.max_rows == 32


def test_custom_policy_is_preserved_and_invalid_type_fails_closed() -> None:
    custom = EmergentPricePolicy()
    config = CognitionLoopConfig(
        price_expectation_mode=CognitionPriceMode.DETERMINISTIC,
        price_expectation_policy=custom,
    )
    assert config.price_expectation_policy is custom
    with pytest.raises(TypeError):
        CognitionLoopConfig(
            price_expectation_mode=CognitionPriceMode.DETERMINISTIC,
            price_expectation_policy=object(),  # type: ignore[arg-type]
        )
    with pytest.raises(TypeError):
        CognitionLoopConfig(price_expectation_mode="enabled")  # type: ignore[arg-type]


def test_disabled_mode_clears_a_supplied_policy() -> None:
    config = CognitionLoopConfig(price_expectation_policy=EmergentPricePolicy())
    assert config.price_expectation_mode is CognitionPriceMode.DISABLED
    assert config.price_expectation_policy is None


def test_fingerprint_includes_price_version_only_when_enabled() -> None:
    disabled = CognitionLoopConfig().condition_fingerprint_material()
    assert "price_expectation_policy_version" not in disabled
    enabled = CognitionLoopConfig(
        price_expectation_mode=CognitionPriceMode.DETERMINISTIC
    ).condition_fingerprint_material()
    assert enabled["price_expectation_mode"] == "deterministic"
    assert enabled["price_expectation_policy_version"] == (
        EMERGENT_PRICES_POLICY_VERSION
    )


def test_build_cognitive_loop_forwards_the_price_mode() -> None:
    loop = build_cognitive_loop(
        CognitionLoopConfig(price_expectation_mode=CognitionPriceMode.DETERMINISTIC)
    )
    assert loop._price_expectation_mode is CognitionPriceMode.DETERMINISTIC
    assert loop._price_expectation_policy is default_emergent_price_policy()
    disabled = build_cognitive_loop(CognitionLoopConfig())
    assert disabled._price_expectation_policy is None


def test_runner_activation_requires_flag_and_valuation() -> None:
    from simulation.runner import _cognition_config_for

    assert RUNNER_SCHEMA_VERSION_V56 in SUPPORTED_RUNNER_SCHEMA_VERSIONS
    assert "runner-config-v57" not in SUPPORTED_RUNNER_SCHEMA_VERSIONS
    spec = AgentCognitionSpec(agent_id=AgentId("agent-1"))
    flag_off_valuation_on = _cognition_config_for(
        spec,
        mortality_mode=MortalityMode.DISABLED,
        capability_flags=V2CapabilityFlags(),
        markets_enabled=False,
        subjective_valuation_active=True,
    )
    assert (
        flag_off_valuation_on.price_expectation_mode
        is CognitionPriceMode.DISABLED
    )
    assert flag_off_valuation_on.price_expectation_policy is None

    flag_on_valuation_off = _cognition_config_for(
        spec,
        mortality_mode=MortalityMode.DISABLED,
        capability_flags=V2CapabilityFlags(),
        markets_enabled=True,
        subjective_valuation_active=False,
    )
    assert (
        flag_on_valuation_off.price_expectation_mode
        is CognitionPriceMode.DISABLED
    )
    assert flag_on_valuation_off.price_expectation_policy is None

    both = _cognition_config_for(
        spec,
        mortality_mode=MortalityMode.DISABLED,
        capability_flags=V2CapabilityFlags(),
        markets_enabled=True,
        subjective_valuation_active=True,
    )
    assert both.price_expectation_mode is CognitionPriceMode.DETERMINISTIC
    assert both.price_expectation_policy is default_emergent_price_policy()
    assert both.market_institution_mode.value == "deterministic"


def test_market_institution_wiring_is_unchanged_without_valuation() -> None:
    from simulation.runner import _cognition_config_for

    spec = AgentCognitionSpec(agent_id=AgentId("agent-1"))
    market_only = _cognition_config_for(
        spec,
        mortality_mode=MortalityMode.DISABLED,
        capability_flags=V2CapabilityFlags(),
        markets_enabled=True,
        subjective_valuation_active=False,
    )
    assert market_only.market_institution_mode.value == "deterministic"
    assert market_only.price_expectation_mode is CognitionPriceMode.DISABLED
