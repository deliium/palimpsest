# mypy: ignore-errors

"""Off-gate scenario: declared arms, shared identity, no seeded content."""

from __future__ import annotations

import pytest

from agents.models import AgentId
from experiments.catalog import (
    base_runner_config_from_scenario,
    experiment_scientific_models,
)
from experiments.models import ExperimentSeedMatrix
from experiments.scientific_models_scenario import (
    SCIENTIFIC_MODELS_EXPERIMENT_ID,
    scientific_models_scenario,
)
from simulation.runner_models import (
    AgentCognitionSpec,
    AgentRunnerSpec,
    WorldScenarioSpec,
)
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.identifiers import WorldId, WorldRevision
from world.models import default_physical_rules

pytestmark = pytest.mark.unit

_ARMS = (
    "models-science-off",
    "models-season-resource",
    "models-production",
    "models-measurement-coexistence",
)


def _base():
    bodies = (alive_body("body-1"), alive_body("body-2"))
    agents = tuple(
        AgentRunnerSpec(
            agent_id=AgentId(f"agent-{index + 1}"),
            entity_id=bodies[index].entity_id,
            cognition=AgentCognitionSpec(agent_id=AgentId(f"agent-{index + 1}")),
        )
        for index in range(2)
    )
    return base_runner_config_from_scenario(
        seed=51,
        stochastic_identity="scientific-models-scenario",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-scientific-models-scenario"),
            revision=WorldRevision(0),
            physical_rules=default_physical_rules(),
            locations=(make_location(),),
            bodies=bodies,
            weather=(make_weather(),),
        ),
        agents=agents,
        max_ticks=96,
    )


def _definition():
    return scientific_models_scenario(_base(), max_ticks=96)


def test_four_declared_arms_share_seed_and_world() -> None:
    definition = _definition()
    assert definition.experiment_id == SCIENTIFIC_MODELS_EXPERIMENT_ID
    assert [row.condition_id for row in definition.conditions] == list(_ARMS)
    seeds = {row.runner_config.seed for row in definition.conditions}
    identities = {
        row.runner_config.stochastic_identity for row in definition.conditions
    }
    assert seeds == {51}
    assert len(identities) == 1


def test_off_arm_is_inert_and_science_arms_activate_only_the_flag() -> None:
    arms = {row.condition_id: row.runner_config for row in _definition().conditions}
    off = arms["models-science-off"]
    assert off.v4_capability_flags.science is False
    assert off.bounded_experimentation is None
    assert off.environmental_dynamics is None
    living = arms["models-season-resource"]
    assert living.v4_capability_flags.science is True
    assert living.bounded_experimentation is not None
    assert living.environmental_dynamics is not None
    production = arms["models-production"]
    assert production.environmental_dynamics is None
    assert production.bounded_experimentation is not None
    coexistence = arms["models-measurement-coexistence"]
    assert coexistence.measurement_instruments is not None
    assert coexistence.v4_capability_flags.science is True


def test_no_reserved_capability_is_silently_enabled() -> None:
    for row in _definition().conditions:
        flags = row.runner_config.v4_capability_flags
        assert flags.epidemics is False
        assert flags.ecological_feedback is False
        assert flags.disasters is False


def test_seeded_owner_content_is_absent() -> None:
    definition = _definition()
    for row in definition.conditions:
        config = row.runner_config
        for agent in config.agents:
            for field in agent.cognition.__dataclass_fields__:
                assert "scientific_model" not in field
                assert "prediction" not in field
        assert not any(
            "scientific_model" in field for field in config.__dataclass_fields__
        )


def test_deterministic_twins_and_seed_matrix() -> None:
    first = _definition()
    second = _definition()
    assert first.conditions == second.conditions
    matrix = ExperimentSeedMatrix(seeds=(51, 52))
    custom = scientific_models_scenario(_base(), seed_matrix=matrix, max_ticks=96)
    assert custom.seed_matrix == matrix


def test_invalid_horizon_and_catalog_wrapper() -> None:
    with pytest.raises(ValueError, match="scientific_models_min_ticks"):
        scientific_models_scenario(_base(), max_ticks=95)
    definition = experiment_scientific_models(_base(), max_ticks=96)
    assert definition.experiment_id == SCIENTIFIC_MODELS_EXPERIMENT_ID
    assert len(definition.conditions) == 4
    assert all(
        row.runner_config.v4_capability_flags.epidemics is False
        for row in definition.conditions
    )
