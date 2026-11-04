"""V4-10 runner seam: diplomacy activates only on runner-config-v56."""

from __future__ import annotations

from dataclasses import replace

import pytest

from agents.cognition import (
    DIPLOMACY_POLICY_VERSION,
    DiplomacyPolicy,
    default_diplomacy_policy,
)
from agents.cognition.configuration import (
    CognitionDiplomacyMode,
    CognitionLoopConfig,
    build_cognitive_loop,
)
from agents.models import AgentId
from experiments.catalog import base_runner_config_from_scenario
from simulation.models import RunId
from simulation.runner import SimulationRunner, _cognition_config_for
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V4,
    RUNNER_SCHEMA_VERSION_V55,
    RUNNER_SCHEMA_VERSION_V56,
    AgentCognitionSpec,
    AgentRunnerSpec,
    MortalityMode,
    SimulationRunnerConfig,
    V2CapabilityFlags,
    V4CapabilityFlags,
    WorldScenarioSpec,
)
from simulation.runner_serialization import decode_runner_config, encode_runner_config
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.identifiers import WorldId, WorldRevision
from world.models import default_physical_rules

pytestmark = pytest.mark.unit


def _base() -> SimulationRunnerConfig:
    body = alive_body("body-1")
    agent_id = AgentId("agent-1")
    return base_runner_config_from_scenario(
        seed=11,
        stochastic_identity="cmp-v4-diplomacy-config",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-v4-diplomacy-config"),
            revision=WorldRevision(0),
            physical_rules=default_physical_rules(),
            locations=(make_location(),),
            bodies=(body,),
            weather=(make_weather(),),
        ),
        agents=(
            AgentRunnerSpec(
                agent_id=agent_id,
                entity_id=body.entity_id,
                cognition=AgentCognitionSpec(agent_id=agent_id),
            ),
        ),
        max_ticks=2,
    )


def _v56_config(*, flags: V4CapabilityFlags | None = None) -> SimulationRunnerConfig:
    return replace(
        _base(),
        schema_version=RUNNER_SCHEMA_VERSION_V56,
        v4_capability_flags=flags if flags is not None else V4CapabilityFlags(),
    )


@pytest.mark.parametrize(
    "schema_version",
    (RUNNER_SCHEMA_VERSION_V4, RUNNER_SCHEMA_VERSION_V55),
)
def test_diplomacy_requires_v56_on_older_schemas(schema_version: str) -> None:
    with pytest.raises(ValueError, match="code=v4_capability_requires_v56"):
        replace(
            _base(),
            schema_version=schema_version,
            v4_capability_flags=V4CapabilityFlags(diplomacy=True),
        )


@pytest.mark.asyncio
async def test_diplomacy_constructs_on_v56() -> None:
    config = _v56_config(flags=V4CapabilityFlags(diplomacy=True))
    decoded = decode_runner_config(encode_runner_config(config))
    assert decoded.schema_version == RUNNER_SCHEMA_VERSION_V56
    assert decoded.v4_capability_flags.diplomacy is True

    runner = await SimulationRunner.from_config(
        config, run_id=RunId("run-v4-diplomacy-construct")
    )
    assert runner.config.v4_capability_flags.owned_enabled_names() == ("diplomacy",)
    assert runner.config.v4_capability_flags.unimplemented_enabled_names() == ()


@pytest.mark.asyncio
async def test_diplomacy_runs_with_organizations_disabled() -> None:
    config = _v56_config(flags=V4CapabilityFlags(diplomacy=True))
    assert config.v4_capability_flags.organizations is False

    runner = await SimulationRunner.from_config(
        config, run_id=RunId("run-v4-diplomacy-without-organizations")
    )
    assert runner.config.v4_capability_flags.enabled_names() == ("diplomacy",)


def test_all_flags_off_stays_byte_identical() -> None:
    config = _v56_config()
    assert config.v4_capability_flags.any_enabled() is False
    assert encode_runner_config(config) == encode_runner_config(
        replace(config, v4_capability_flags=V4CapabilityFlags())
    )
    assert decode_runner_config(encode_runner_config(config)) == config


def test_default_diplomacy_mode_is_disabled_and_policy_is_none() -> None:
    config = CognitionLoopConfig()
    assert config.diplomacy_mode is CognitionDiplomacyMode.DISABLED
    assert config.diplomacy_policy is None


def test_deterministic_diplomacy_mode_installs_locked_policy() -> None:
    config = CognitionLoopConfig(diplomacy_mode=CognitionDiplomacyMode.DETERMINISTIC)
    assert config.diplomacy_policy == default_diplomacy_policy()
    assert DIPLOMACY_POLICY_VERSION == "diplomacy.v1"


def test_disabled_mode_clears_supplied_policy() -> None:
    config = CognitionLoopConfig(
        diplomacy_mode=CognitionDiplomacyMode.DISABLED,
        diplomacy_policy=default_diplomacy_policy(),
    )
    assert config.diplomacy_policy is None


def test_foreign_policy_and_mode_types_are_rejected() -> None:
    with pytest.raises(TypeError, match="diplomacy_policy"):
        CognitionLoopConfig(
            diplomacy_mode=CognitionDiplomacyMode.DETERMINISTIC,
            diplomacy_policy=object(),  # type: ignore[arg-type]
        )

    with pytest.raises(TypeError, match="diplomacy_mode"):
        CognitionLoopConfig(
            diplomacy_mode="deterministic",  # type: ignore[arg-type]
        )


def test_explicit_locked_policy_is_retained() -> None:
    policy = default_diplomacy_policy()
    config = CognitionLoopConfig(
        diplomacy_mode=CognitionDiplomacyMode.DETERMINISTIC,
        diplomacy_policy=policy,
    )
    assert type(config.diplomacy_policy) is DiplomacyPolicy
    assert config.diplomacy_policy is policy


def test_condition_fingerprint_omits_disabled_diplomacy_fields() -> None:
    disabled = CognitionLoopConfig().condition_fingerprint_material()
    assert "diplomacy_mode" not in disabled
    assert "diplomacy_policy_version" not in disabled

    deterministic = CognitionLoopConfig(
        diplomacy_mode=CognitionDiplomacyMode.DETERMINISTIC
    ).condition_fingerprint_material()
    assert deterministic["diplomacy_mode"] == "deterministic"
    assert deterministic["diplomacy_policy_version"] == DIPLOMACY_POLICY_VERSION


def _cognition_config_for_diplomacy(enabled: bool) -> CognitionLoopConfig:
    return _cognition_config_for(
        AgentCognitionSpec(agent_id=AgentId("agent-1")),
        mortality_mode=MortalityMode.DISABLED,
        capability_flags=V2CapabilityFlags(),
        organizations_enabled=False,
        formal_rules_enabled=False,
        legal_disputes_enabled=False,
        diplomacy_enabled=enabled,
    )


def test_diplomacy_seam_is_derived_from_the_owned_flag() -> None:
    disabled = _cognition_config_for_diplomacy(False)
    assert disabled.diplomacy_mode is CognitionDiplomacyMode.DISABLED
    assert disabled.diplomacy_policy is None

    enabled = _cognition_config_for_diplomacy(True)
    assert enabled.diplomacy_mode is CognitionDiplomacyMode.DETERMINISTIC
    assert enabled.diplomacy_policy == default_diplomacy_policy()


@pytest.mark.parametrize(
    "flag_name",
    (
        "organizations",
        "formal_rules",
        "legal_disputes",
        "diplomacy",
        "organized_conflict",
        "infrastructure_networks",
        "supply_chains",
        "markets_credit",
        "science",
        "epidemics",
        "ecological_feedback",
        "disasters",
    ),
)
def test_only_the_diplomacy_flag_activates_the_seam(flag_name: str) -> None:
    kwargs = {
        "organizations_enabled": flag_name == "organizations",
        "formal_rules_enabled": flag_name == "formal_rules",
        "legal_disputes_enabled": flag_name == "legal_disputes",
        "diplomacy_enabled": flag_name == "diplomacy",
    }
    config = _cognition_config_for(
        AgentCognitionSpec(agent_id=AgentId("agent-1")),
        mortality_mode=MortalityMode.DISABLED,
        capability_flags=V2CapabilityFlags(),
        **kwargs,
    )
    expected = (
        CognitionDiplomacyMode.DETERMINISTIC
        if flag_name == "diplomacy"
        else CognitionDiplomacyMode.DISABLED
    )
    assert config.diplomacy_mode is expected
    if expected is CognitionDiplomacyMode.DETERMINISTIC:
        assert config.diplomacy_policy == default_diplomacy_policy()
    else:
        assert config.diplomacy_policy is None


def test_no_per_agent_diplomacy_runner_key() -> None:
    spec = AgentCognitionSpec(agent_id=AgentId("agent-1"))
    assert not hasattr(spec, "diplomacy_mode")
    assert not hasattr(spec, "diplomacy_policy")
    assert "diplomacy_mode" not in SimulationRunnerConfig.__dataclass_fields__
    assert "diplomacy_policy" not in SimulationRunnerConfig.__dataclass_fields__


def test_cognitive_loop_installs_the_disabled_by_default_seam() -> None:
    disabled = build_cognitive_loop(CognitionLoopConfig())
    assert disabled._diplomacy_mode is CognitionDiplomacyMode.DISABLED
    assert disabled._diplomacy_policy is None
    assert disabled._prepared_diplomacy is None

    enabled = build_cognitive_loop(
        CognitionLoopConfig(diplomacy_mode=CognitionDiplomacyMode.DETERMINISTIC)
    )
    assert enabled._diplomacy_mode is CognitionDiplomacyMode.DETERMINISTIC
    assert enabled._diplomacy_policy == default_diplomacy_policy()
    assert enabled._prepared_diplomacy is None
