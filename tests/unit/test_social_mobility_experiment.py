# mypy: ignore-errors
"""Off-gate ``social_mobility@1`` registration and arm discipline."""

# mypy: ignore-errors

from __future__ import annotations

import pytest

from agents.models import AgentId
from experiments.catalog import (
    EXPERIMENT_A_V1_CONDITION_IDS,
    OFF_GATE_MATRIX_EXPERIMENT_IDS,
    base_runner_config_from_scenario,
    experiment_social_mobility,
)
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V56,
    AgentCognitionSpec,
    AgentRunnerSpec,
    WorldScenarioSpec,
)
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.identifiers import WorldId, WorldRevision
from world.models import default_physical_rules

pytestmark = pytest.mark.unit


def _base(agents: int = 2):
    bodies = tuple(alive_body(f"body-{index}") for index in range(agents))
    specs = tuple(
        AgentRunnerSpec(
            agent_id=AgentId(f"agent-{index}"),
            entity_id=body.entity_id,
            cognition=AgentCognitionSpec(agent_id=AgentId(f"agent-{index}")),
        )
        for index, body in enumerate(bodies)
    )
    return base_runner_config_from_scenario(
        seed=17,
        stochastic_identity="cmp-v4-social-mobility",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-v4-social-mobility"),
            revision=WorldRevision(0),
            physical_rules=default_physical_rules(),
            locations=(make_location(),),
            bodies=bodies,
            weather=(make_weather(),),
        ),
        agents=specs,
        max_ticks=96,
    )


def test_experiment_is_registered_once_and_off_gate() -> None:
    definition = experiment_social_mobility(_base())
    assert definition.experiment_id == "social_mobility@1"
    assert "social_mobility@1" in OFF_GATE_MATRIX_EXPERIMENT_IDS
    assert "social_mobility@1" not in EXPERIMENT_A_V1_CONDITION_IDS


def test_three_arms_are_ordered_and_valid_v56() -> None:
    definition = experiment_social_mobility(_base())
    assert [condition.condition_id for condition in definition.conditions] == [
        "sm-baseline",
        "sm-kinship",
        "sm-full",
    ]
    baseline, kinship, full = (
        condition.runner_config for condition in definition.conditions
    )
    for config in (baseline, kinship, full):
        assert config.schema_version == RUNNER_SCHEMA_VERSION_V56
        assert config.v3_capability_flags.generational_population is True
        assert config.stop_policy.max_ticks == 96

    assert baseline.v3_capability_flags.kinship_inheritance is False
    assert baseline.kinship is None
    assert kinship.v3_capability_flags.kinship_inheritance is True
    assert full.v3_capability_flags.kinship_inheritance is True
    assert kinship.kinship is not None
    assert full.kinship is not None

    assert baseline.durable_records is None
    assert baseline.knowledge_repositories is None
    assert baseline.v4_capability_flags.organizations is False
    assert baseline.v4_capability_flags.markets_credit is False

    assert kinship.durable_records is not None
    assert kinship.knowledge_repositories is not None
    assert kinship.cultural_feature_provenance is not None
    assert kinship.mentorship is not None

    assert full.v4_capability_flags.organizations is True
    assert full.v4_capability_flags.markets_credit is True
    assert full.v4_capability_flags.infrastructure_networks is True
    assert full.v4_capability_flags.supply_chains is True
    assert full.structured_commitments is not None
    assert full.subjective_valuation is not None


def test_short_horizon_is_rejected() -> None:
    with pytest.raises(ValueError, match="social_mobility_requires_three_windows"):
        experiment_social_mobility(_base(), max_ticks=95)


def test_kinship_bootstrap_edge_links_the_first_two_agents() -> None:
    kinship = experiment_social_mobility(_base()).conditions[1].runner_config.kinship
    assert kinship is not None
    assert tuple(edge.child_agent_id.value for edge in kinship.bootstrap_edges) == (
        "agent-1",
    )
