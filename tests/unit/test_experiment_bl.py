"""Experiment BL exercises real generations over the AY regional world."""

from __future__ import annotations

import pytest

from experiments.coordinator import ExperimentCoordinator
from experiments.generational_runner_scenario import (
    EXPERIMENT_ID,
    generational_runner_arbiter,
    generational_runner_scenario,
)
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V55,
    SimulationRunnerConfig,
)
from simulation.runner_serialization import (
    decode_runner_config,
    encode_runner_config,
)


def _conditions(max_ticks: int = 8) -> dict[str, SimulationRunnerConfig]:
    definition = generational_runner_scenario(seed=23, max_ticks=max_ticks)
    return {item.condition_id: item.runner_config for item in definition.conditions}


def test_bl_conditions_are_v55_and_real_regions() -> None:
    conditions = _conditions()
    assert set(conditions) == {
        "bl-single-cohort",
        "bl-generational-unassisted",
        "bl-generational-contact",
    }
    for config in conditions.values():
        assert config.schema_version == RUNNER_SCHEMA_VERSION_V55
        assert config.generational_run is not None
        assert config.population_lifecycle is not None
        assert config.new_agent_initialization is not None
        assert config.regions_migration is not None
        assert config.stop_policy.stop_on_all_agents_terminal is False
        decoded = decode_runner_config(encode_runner_config(config))
        assert decoded == config
    assert conditions["bl-single-cohort"].population_lifecycle is not None
    assert (
        conditions["bl-single-cohort"].population_lifecycle.demographic_policy_id
        == "disabled"
    )
    assert (
        conditions[
            "bl-generational-unassisted"
        ].population_lifecycle.demographic_policy_id
        == "generational_interval_entry"
    )


def test_only_contact_installs_the_versioned_intervention() -> None:
    conditions = _conditions()
    assert (
        generational_runner_arbiter(
            "bl-single-cohort", conditions["bl-single-cohort"]
        )
        is None
    )
    assert (
        generational_runner_arbiter(
            "bl-generational-unassisted",
            conditions["bl-generational-unassisted"],
        )
        is None
    )
    assert (
        generational_runner_arbiter(
            "bl-generational-contact", conditions["bl-generational-contact"]
        )
        is not None
    )


@pytest.mark.asyncio
async def test_bl_runs_produce_multiple_generations_and_movement() -> None:
    definition = generational_runner_scenario(seed=23, max_ticks=8)
    results = await ExperimentCoordinator(definition).run_all()
    assert {item.assignment.experiment_id for item in results} == {EXPERIMENT_ID}
    generations = set()
    for arm in results:
        result = arm.runner_result
        assert result.generational_progress is not None
        generations.add(result.generational_progress.max_generation_index_seen)
    assert max(generations) >= 2
    contact = next(
        item
        for item in results
        if item.assignment.condition_id == "bl-generational-contact"
    )
    assert contact.committed_events
