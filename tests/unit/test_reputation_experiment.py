"""Experiment Q pairs modes without putting the metric inside cognition."""

from __future__ import annotations

import dataclasses
from pathlib import Path

from analysis.models import MetricAvailability
from analysis.reputation_metrics import compute_distributed_reputation
from experiments.catalog import experiment_q_distributed_reputation
from experiments.reputation_scenario import distributed_reputation_scenario
from simulation.runner_models import RUNNER_SCHEMA_VERSION_V4, RUNNER_SCHEMA_VERSION_V10
from world._state import WorldState

_ROOT = Path(__file__).resolve().parents[2]


def test_experiment_q_pairs_schema_and_mode_without_running_the_metric() -> None:
    base = distributed_reputation_scenario()
    definition = experiment_q_distributed_reputation(base)
    disabled, enabled = definition.conditions
    assert disabled.condition_id == "q-disabled"
    assert enabled.condition_id == "q-enabled"
    assert disabled.runner_config.schema_version == RUNNER_SCHEMA_VERSION_V4
    assert enabled.runner_config.schema_version == RUNNER_SCHEMA_VERSION_V10
    assert disabled.runner_config.seed == enabled.runner_config.seed
    assert (
        disabled.runner_config.stochastic_identity
        == enabled.runner_config.stochastic_identity
    )
    assert disabled.runner_config.scenario == enabled.runner_config.scenario
    assert all(
        agent.cognition.reputation_mode.value == "disabled"
        for agent in disabled.runner_config.agents
    )
    assert all(
        agent.cognition.reputation_mode.value == "deterministic"
        for agent in enabled.runner_config.agents
    )


def test_split_starts_pass_topology_and_weather() -> None:
    config = distributed_reputation_scenario()
    scenario = config.scenario
    WorldState(
        scenario.revision,
        locations=scenario.locations,
        bodies=scenario.bodies,
        weather=scenario.weather,
    )
    by_agent = {agent.agent_id.value: agent.entity_id.value for agent in config.agents}
    assert by_agent["focal"] == "body-focal"
    assert by_agent["east_a"].startswith("body-")
    assert by_agent["west_a"] != "west_a"
    starts = {
        body.entity_id.value: body.location_id.value for body in scenario.bodies
    }
    assert starts["body-focal"] == "east"
    assert starts["body-east-a"] == "east"
    assert starts["body-east-b"] == "east"
    assert starts["body-west-a"] == "west"
    assert starts["body-west-b"] == "west"


def test_neighborhood_means_disagree_and_readings_stay_outside_cognition() -> None:
    from agents.cognition.reputation import (
        ReputationDimensionState,
        ReputationLedger,
        ReputationProfile,
        neutral_dimension_state,
        reputation_profile_id,
    )
    from agents.models import AgentId

    def ledger(owner: str, *, reliability: float, harm: float) -> ReputationLedger:
        owner_id = AgentId(owner)
        target = AgentId("focal")
        return ReputationLedger(
            owner_id=owner_id,
            profiles=(
                ReputationProfile(
                    profile_id=reputation_profile_id(owner_id, target),
                    owner_id=owner_id,
                    target_id=target,
                    reliability=ReputationDimensionState(
                        value=reliability,
                        support_mass=max(reliability, 0.0),
                        contradiction_mass=max(-reliability, 0.0),
                    ),
                    harm=ReputationDimensionState(
                        value=harm,
                        support_mass=max(harm, 0.0),
                        contradiction_mass=max(-harm, 0.0),
                    ),
                    generosity=neutral_dimension_state(),
                    competence=neutral_dimension_state(),
                ),
            ),
        )

    east = ledger("east_a", reliability=0.4, harm=-0.05)
    west = ledger("west_b", reliability=0.0, harm=0.4)
    result = compute_distributed_reputation(
        (east, west),
        {"east_a": "east", "west_b": "west"},
        target_id="focal",
        run_id="run-q",
        input_revision="rev-q",
    )
    assert result.document.availability is MetricAvailability.PRESENT
    assert result.gaps["harm"] >= 0.4
    by_neighborhood = {row.neighborhood_id: row for row in result.neighborhoods}
    assert "trustworthy" in by_neighborhood["east"].readings
    assert "dangerous" in by_neighborhood["west"].readings
    names = {field.name for field in dataclasses.fields(type(east))}
    assert "trustworthy" not in names
    assert "dangerous" not in names
    empty = compute_distributed_reputation(
        (),
        {},
        target_id="focal",
        run_id="run-q",
        input_revision="rev-q",
    )
    assert empty.document.availability is MetricAvailability.ABSENT
    loop = (_ROOT / "src/agents/cognition/loop.py").read_text(encoding="utf-8")
    runtime = (_ROOT / "src/simulation/agent_runtime.py").read_text(encoding="utf-8")
    assert "analysis.reputation_metrics" not in loop
    assert "analysis.reputation_metrics" not in runtime
