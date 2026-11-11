"""V4-20 market seam: cognition config, loop construction, fingerprint."""

from __future__ import annotations

import pytest

from agents.cognition import (
    MARKET_INSTITUTIONS_POLICY_VERSION,
    MarketInstitutionPolicy,
    build_cognitive_loop,
    default_market_institution_policy,
)
from agents.cognition.configuration import (
    CognitionLoopConfig,
    CognitionMarketMode,
)
from agents.models import AgentId
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V55,
    RUNNER_SCHEMA_VERSION_V56,
    SUPPORTED_RUNNER_SCHEMA_VERSIONS,
    AgentCognitionSpec,
    MortalityMode,
    V2CapabilityFlags,
    V4CapabilityFlags,
)

pytestmark = pytest.mark.unit


def test_disabled_mode_allocates_no_policy() -> None:
    config = CognitionLoopConfig()
    assert config.market_institution_mode is CognitionMarketMode.DISABLED
    assert config.market_institution_policy is None


def test_deterministic_mode_installs_the_locked_policy() -> None:
    config = CognitionLoopConfig(
        market_institution_mode=CognitionMarketMode.DETERMINISTIC
    )
    assert config.market_institution_policy is default_market_institution_policy()
    assert config.market_institution_policy.max_venues == 8


def test_custom_policy_is_preserved_and_invalid_type_fails_closed() -> None:
    custom = MarketInstitutionPolicy()
    config = CognitionLoopConfig(
        market_institution_mode=CognitionMarketMode.DETERMINISTIC,
        market_institution_policy=custom,
    )
    assert config.market_institution_policy is custom
    with pytest.raises(TypeError):
        CognitionLoopConfig(
            market_institution_mode=CognitionMarketMode.DETERMINISTIC,
            market_institution_policy=object(),  # type: ignore[arg-type]
        )
    with pytest.raises(TypeError):
        CognitionLoopConfig(market_institution_mode="enabled")  # type: ignore[arg-type]


def test_fingerprint_includes_market_version_only_when_enabled() -> None:
    disabled = CognitionLoopConfig().condition_fingerprint_material()
    assert "market_institution_policy_version" not in disabled
    enabled = CognitionLoopConfig(
        market_institution_mode=CognitionMarketMode.DETERMINISTIC
    ).condition_fingerprint_material()
    assert enabled["market_institution_mode"] == "deterministic"
    assert enabled["market_institution_policy_version"] == (
        MARKET_INSTITUTIONS_POLICY_VERSION
    )


def test_build_cognitive_loop_forwards_the_market_policy() -> None:
    loop = build_cognitive_loop(
        CognitionLoopConfig(market_institution_mode=CognitionMarketMode.DETERMINISTIC)
    )
    assert loop._market_institution_mode is CognitionMarketMode.DETERMINISTIC
    assert loop._market_institution_policy is default_market_institution_policy()
    disabled = build_cognitive_loop(CognitionLoopConfig())
    assert disabled._market_institution_policy is None


def test_runner_seam_keeps_v56_and_allocates_the_market_policy() -> None:
    from simulation.runner import _cognition_config_for

    assert RUNNER_SCHEMA_VERSION_V56 in SUPPORTED_RUNNER_SCHEMA_VERSIONS
    assert RUNNER_SCHEMA_VERSION_V55 in SUPPORTED_RUNNER_SCHEMA_VERSIONS
    assert "runner-config-v57" not in SUPPORTED_RUNNER_SCHEMA_VERSIONS
    assert V4CapabilityFlags(markets_credit=True).owned_enabled_names() == (
        "markets_credit",
    )
    assert V4CapabilityFlags(markets_credit=True).unimplemented_enabled_names() == ()

    spec = AgentCognitionSpec(agent_id=AgentId("agent-1"))
    disabled = _cognition_config_for(
        spec,
        mortality_mode=MortalityMode.DISABLED,
        capability_flags=V2CapabilityFlags(),
        markets_enabled=False,
    )
    assert disabled.market_institution_mode is CognitionMarketMode.DISABLED
    assert disabled.market_institution_policy is None

    enabled = _cognition_config_for(
        spec,
        mortality_mode=MortalityMode.DISABLED,
        capability_flags=V2CapabilityFlags(),
        markets_enabled=True,
    )
    assert enabled.market_institution_mode is CognitionMarketMode.DETERMINISTIC
    assert enabled.market_institution_policy is default_market_institution_policy()
