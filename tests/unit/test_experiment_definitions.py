"""Unit tests for experiment A-E definitions."""

from __future__ import annotations

from agents.models import AgentId, DriveKind
from experiments import (
    definition_fingerprint,
    experiment_a_memory,
    experiment_b_imagination,
    experiment_c_mortality,
    experiment_d_drives,
)
from experiments.catalog import base_runner_config_from_scenario
from simulation.runner_models import (
    AgentCognitionSpec,
    AgentRunnerSpec,
    ImaginationMode,
    MemoryMode,
    MortalityMode,
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
    definition = experiment_a_memory(_base())
    assert len(definition.conditions) == 2
    modes = {
        item.runner_config.agents[0].cognition.memory_mode
        for item in definition.conditions
    }
    assert modes == {MemoryMode.REFERENCE, MemoryMode.RECONSTRUCTIVE}
    assert (
        definition.conditions[0].runner_config.stochastic_identity
        == definition.conditions[1].runner_config.stochastic_identity
    )


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
