# mypy: ignore-errors

"""Off-gate supply_chains@1 experiment registration."""

from __future__ import annotations

import asyncio

import pytest

from experiments.catalog import OFF_GATE_MATRIX_EXPERIMENT_IDS
from experiments.supply_chain_scenario import (
    SUPPLY_CHAINS_EXPERIMENT_ID,
    supply_chain_scenario,
)
from simulation.runner import SimulationRunner
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V56,
    SUPPORTED_RUNNER_SCHEMA_VERSIONS,
    ProductionKnowledgeMode,
)
from tests.unit.test_supply_chain_mechanics import _v56_config
from world.production import example_production_catalog
from world.supply_chain import supply_chain_production_catalog

pytestmark = pytest.mark.unit


def test_experiment_id() -> None:
    assert SUPPLY_CHAINS_EXPERIMENT_ID == "supply_chains@1"


def test_two_paired_conditions() -> None:
    definition = supply_chain_scenario(_v56_config())
    assert len(definition.conditions) == 2
    assert [condition.condition_id for condition in definition.conditions] == [
        "supply-chain-off",
        "supply-chain-on",
    ]


def test_conditions_share_seed_and_world() -> None:
    definition = supply_chain_scenario(_v56_config())
    control, treatment = definition.conditions
    assert control.runner_config.seed == treatment.runner_config.seed
    assert control.runner_config.stochastic_identity == (
        treatment.runner_config.stochastic_identity
    )
    assert control.runner_config.scenario.world_id == (
        treatment.runner_config.scenario.world_id
    )


def test_treatment_enables_flag_and_catalog() -> None:
    definition = supply_chain_scenario(_v56_config())
    control, treatment = definition.conditions
    assert control.runner_config.v4_capability_flags.supply_chains is False
    assert treatment.runner_config.v4_capability_flags.supply_chains is True
    assert control.runner_config.agents[0].cognition.production_catalog == (
        example_production_catalog()
    )
    assert treatment.runner_config.agents[0].cognition.production_catalog == (
        supply_chain_production_catalog(example_production_catalog())
    )


def test_control_keeps_legacy_catalog() -> None:
    definition = supply_chain_scenario(_v56_config())
    control = definition.conditions[0]
    assert (
        control.runner_config.agents[0].cognition.production_catalog.recipe_count == 6
    )


def test_conditions_enable_production_knowledge() -> None:
    definition = supply_chain_scenario(_v56_config())
    for condition in definition.conditions:
        assert (
            condition.runner_config.agents[0].cognition.production_knowledge_mode
            is ProductionKnowledgeMode.DETERMINISTIC
        )


def test_off_gate_registry_contains_id() -> None:
    assert "supply_chains@1" in OFF_GATE_MATRIX_EXPERIMENT_IDS


def test_absent_from_v1_gate() -> None:
    from experiments.catalog import EXPERIMENT_A_V1_CONDITION_IDS

    assert "supply_chains@1" not in EXPERIMENT_A_V1_CONDITION_IDS


def test_no_new_runner_schema() -> None:
    assert RUNNER_SCHEMA_VERSION_V56 in SUPPORTED_RUNNER_SCHEMA_VERSIONS
    assert "runner-config-v57" not in SUPPORTED_RUNNER_SCHEMA_VERSIONS


def test_both_conditions_construct() -> None:
    def build() -> None:
        definition = supply_chain_scenario(_v56_config())
        for index, condition in enumerate(definition.conditions):
            asyncio.run(
                SimulationRunner.from_config(
                    condition.runner_config,
                    run_id=__import__("simulation.models", fromlist=["RunId"]).RunId(
                        f"run-supply-exp-{index}"
                    ),
                )
            )

    build()
