"""Unit tests for experiment A-E definitions."""

from __future__ import annotations

from agents.models import AgentId, DriveKind
from experiments import (
    definition_fingerprint,
    experiment_a_memory,
    experiment_b_imagination,
    experiment_c_mortality,
    experiment_d_drives,
    experiment_f_sleep_consolidation,
    experiment_g_reflection,
    experiment_h_identity,
)
from experiments.catalog import base_runner_config_from_scenario
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V4,
    RUNNER_SCHEMA_VERSION_V5,
    RUNNER_SCHEMA_VERSION_V6,
    AgentCognitionSpec,
    AgentRunnerSpec,
    ConsolidationMode,
    ImaginationMode,
    MemoryMode,
    MortalityMode,
    ReflectionMode,
    WorldScenarioSpec,
)
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.identifiers import WorldId, WorldRevision
from world.models import default_physical_rules


def _base():
    body = alive_body("body-1")
    agent_id = AgentId("agent-1")
    return base_runner_config_from_scenario(
        seed=7,
        stochastic_identity="cmp-exp",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-1"),
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
        max_ticks=5,
    )


def test_experiment_a_pairs_reference_and_reconstructive() -> None:
    from experiments.catalog import (
        EXPERIMENT_A_V1_CONDITION_IDS,
        experiment_a_memory_v1_arms,
    )

    definition = experiment_a_memory(_base())
    assert len(definition.conditions) == 3
    modes = {
        item.runner_config.agents[0].cognition.memory_mode
        for item in definition.conditions
    }
    assert modes == {
        MemoryMode.REFERENCE,
        MemoryMode.RECONSTRUCTIVE,
        MemoryMode.RECONSTRUCTIVE_V2,
    }
    assert {item.condition_id for item in definition.conditions} == {
        "a-reference",
        "a-reconstructive",
        "a-reconstructive-v2",
    }
    assert (
        definition.conditions[0].runner_config.stochastic_identity
        == definition.conditions[1].runner_config.stochastic_identity
        == definition.conditions[2].runner_config.stochastic_identity
    )
    v1 = experiment_a_memory_v1_arms(_base())
    assert len(v1.conditions) == 2
    assert {item.condition_id for item in v1.conditions} == (
        EXPERIMENT_A_V1_CONDITION_IDS
    )
    assert MemoryMode.RECONSTRUCTIVE_V2 not in {
        item.runner_config.agents[0].cognition.memory_mode for item in v1.conditions
    }


def test_experiment_b_c_d_and_stable_fingerprint() -> None:
    base = _base()
    b = experiment_b_imagination(base)
    c = experiment_c_mortality(base)
    d = experiment_d_drives(base)
    assert {
        item.runner_config.agents[0].cognition.imagination_mode for item in b.conditions
    } == {
        ImaginationMode.DISABLED,
        ImaginationMode.ENABLED,
    }
    assert {item.runner_config.mortality_mode for item in c.conditions} == {
        MortalityMode.DISABLED,
        MortalityMode.ENABLED,
    }
    assert len(d.conditions) == 4
    kinds = {
        item.runner_config.agents[0].cognition.drive_overrides[0].kind
        for item in d.conditions
    }
    assert kinds == {
        DriveKind.CURIOSITY,
        DriveKind.SAFETY,
        DriveKind.BELONGING,
        DriveKind.STATUS,
    }
    # Builder order independence: re-building yields same fingerprint.
    assert definition_fingerprint(experiment_a_memory(base)) == definition_fingerprint(
        experiment_a_memory(base)
    )


def test_experiment_f_pairs_disabled_v4_and_deterministic_v5() -> None:
    definition = experiment_f_sleep_consolidation(_base())
    assert [item.condition_id for item in definition.conditions] == [
        "f-disabled",
        "f-deterministic",
    ]
    disabled, deterministic = definition.conditions
    assert disabled.runner_config.schema_version == RUNNER_SCHEMA_VERSION_V4
    assert (
        disabled.runner_config.agents[0].cognition.consolidation_mode
        is ConsolidationMode.DISABLED
    )
    assert deterministic.runner_config.schema_version == RUNNER_SCHEMA_VERSION_V5
    assert (
        deterministic.runner_config.agents[0].cognition.consolidation_mode
        is ConsolidationMode.DETERMINISTIC
    )
    assert disabled.runner_config.seed == deterministic.runner_config.seed
    assert (
        disabled.runner_config.stochastic_identity
        == deterministic.runner_config.stochastic_identity
    )
    assert disabled.runner_config.scenario.bodies[0].fatigue.value == 80
    assert (
        disabled.runner_config.agents[0].cognition.memory_mode
        == deterministic.runner_config.agents[0].cognition.memory_mode
    )


def test_experiment_g_pairs_disabled_v4_and_deterministic_v6() -> None:
    definition = experiment_g_reflection(_base())
    assert [item.condition_id for item in definition.conditions] == [
        "g-disabled",
        "g-deterministic",
    ]
    disabled, deterministic = definition.conditions
    assert disabled.runner_config.schema_version == RUNNER_SCHEMA_VERSION_V4
    assert (
        disabled.runner_config.agents[0].cognition.reflection_mode
        is ReflectionMode.DISABLED
    )
    assert deterministic.runner_config.schema_version == RUNNER_SCHEMA_VERSION_V6
    assert (
        deterministic.runner_config.agents[0].cognition.reflection_mode
        is ReflectionMode.DETERMINISTIC
    )
    assert disabled.runner_config.seed == deterministic.runner_config.seed
    assert (
        disabled.runner_config.stochastic_identity
        == deterministic.runner_config.stochastic_identity
    )
    assert disabled.runner_config.stop_policy.max_ticks == 8
    assert (
        disabled.runner_config.agents[0].cognition.consolidation_mode
        is deterministic.runner_config.agents[0].cognition.consolidation_mode
    )


def test_experiment_h_pairs_v4_flag_off_and_on(caplog) -> None:
    import logging

    from experiments.models import EXPERIMENT_SCHEMA_VERSION

    caplog.set_level(logging.DEBUG, logger="experiments.catalog")
    definition = experiment_h_identity(_base())
    assert definition.experiment_id == "experiment-h-identity"
    assert definition.schema_version == EXPERIMENT_SCHEMA_VERSION
    assert [item.condition_id for item in definition.conditions] == [
        "h-disabled",
        "h-enabled",
    ]
    disabled, enabled = definition.conditions
    assert disabled.runner_config.schema_version == RUNNER_SCHEMA_VERSION_V4
    assert enabled.runner_config.schema_version == RUNNER_SCHEMA_VERSION_V4
    assert disabled.runner_config.capability_flags.extended_self_model is False
    assert enabled.runner_config.capability_flags.extended_self_model is True
    assert disabled.runner_config.seed == enabled.runner_config.seed
    assert (
        disabled.runner_config.stochastic_identity
        == enabled.runner_config.stochastic_identity
    )
    assert disabled.runner_config.scenario == enabled.runner_config.scenario
    text = " ".join(record.message for record in caplog.records)
    assert "experiment-h-identity" in text
    assert "h-enabled" in text
    assert RUNNER_SCHEMA_VERSION_V4 in text
    assert "identity." not in text
