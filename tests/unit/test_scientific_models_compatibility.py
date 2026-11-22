# mypy: ignore-errors

"""Supported activation, codec and pin combinations for predictive models."""

from __future__ import annotations

import dataclasses

import pytest

from analysis.specifications import METRIC_FAMILY_COUNT
from api.routes.scientific_models import SCIENTIFIC_MODELS_ROUTE_COUNT
from experiments.scientific_models_scenario import scientific_models_scenario
from simulation.models import RunId
from simulation.run_control import (
    FINALIZATION_COMMAND_ACCEPTED_VERSIONS,
    FINALIZATION_COMMAND_CODEC_VERSION,
    FINALIZATION_COMMAND_CODEC_VERSION_V2,
    FINALIZATION_COMMAND_CODEC_VERSION_V3,
    FINALIZATION_COMMAND_CODEC_VERSION_V4,
    FINALIZATION_COMMAND_CODEC_VERSION_V5,
    FINALIZATION_COMMAND_CODEC_VERSION_V6,
)
from simulation.runner import (
    RunnerDependencyFactories,
    SimulationRunner,
)
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V55,
    RUNNER_SCHEMA_VERSION_V56,
    BoundedExperimentationSpec,
    RunnerStopPolicy,
    V2CapabilityFlags,
    V4CapabilityFlags,
    example_experiment_law,
)
from simulation.v4_architecture import V4_CONTEXT_MAP_VERSION
from tests.unit.test_scientific_models_runtime import _arm, _base
from tests.unit.test_scientific_models_scenario import _base as _scenario_base
from world.production import example_production_catalog

pytestmark = pytest.mark.unit


def _science_config(*, predictive: bool = True, bounded: bool = True):
    base = _base()
    return dataclasses.replace(
        base,
        schema_version=RUNNER_SCHEMA_VERSION_V56,
        capability_flags=V2CapabilityFlags(predictive_world_model=predictive),
        v4_capability_flags=V4CapabilityFlags(science=True),
        bounded_experimentation=(
            BoundedExperimentationSpec(
                laws=(
                    example_experiment_law(
                        operator="vary_process",
                        operand_a_kind="item:tool",
                        operand_b_kind="none",
                        process_token="harvest",
                        outcome_class="failure",
                        delta="none",
                    ),
                ),
                max_hypotheses=4,
                max_trials_per_tick=1,
                repeat_threshold=2,
                learn_into_genealogy=False,
                allow_provider=False,
            )
            if bounded
            else None
        ),
    )


@pytest.mark.asyncio
async def test_science_requires_predictive_and_bounded_prerequisites() -> None:
    for kwargs in ({"predictive": False}, {"bounded": False}):
        with pytest.raises(ValueError, match="science"):
            config = _science_config(**kwargs)
            await SimulationRunner.from_config(
                config,
                run_id=RunId("run-model-prereq"),
                factories=RunnerDependencyFactories(),
            )


@pytest.mark.asyncio
async def test_v56_science_run_without_measurement_is_supported() -> None:
    runner = await SimulationRunner.from_config(
        _arm("science-enabled"),
        run_id=RunId("run-model-v56"),
        factories=RunnerDependencyFactories(),
    )
    assert runner.config.schema_version == RUNNER_SCHEMA_VERSION_V56
    assert runner.config.measurement_instruments is None
    async with runner:
        await runner.run()
    assert all(
        runtime._loop.scientific_model_ledger_if_present() is not None
        for runtime in runner.runtimes
    )
    assert all(
        runtime._loop.measurement_ledger_if_present() is None
        for runtime in runner.runtimes
    )


@pytest.mark.asyncio
async def test_v57_measurement_coexistence_carries_both_ledgers() -> None:
    definition = scientific_models_scenario(_scenario_base(), max_ticks=96)
    config = next(
        row.runner_config
        for row in definition.conditions
        if row.condition_id == "models-measurement-coexistence"
    )
    config = dataclasses.replace(
        config,
        stop_policy=RunnerStopPolicy(max_ticks=1),
        agents=tuple(
            dataclasses.replace(
                agent,
                cognition=dataclasses.replace(
                    agent.cognition,
                    production_catalog=example_production_catalog(),
                ),
            )
            for agent in config.agents
        ),
    )
    runner = await SimulationRunner.from_config(
        config,
        run_id=RunId("run-model-v57-coexistence"),
        factories=RunnerDependencyFactories(),
    )
    assert runner.config.schema_version == "runner-config-v57"
    async with runner:
        await runner.run()
    assert any(
        runtime._loop.measurement_ledger_if_present() is not None
        for runtime in runner.runtimes
    )
    assert any(
        runtime._loop.scientific_model_ledger_if_present() is not None
        for runtime in runner.runtimes
    )


def test_predictive_versions_are_independent_of_runner_and_replay() -> None:
    assert RUNNER_SCHEMA_VERSION_V55 == "runner-config-v55"
    assert RUNNER_SCHEMA_VERSION_V56 == "runner-config-v56"
    assert hasattr(
        __import__("simulation.runner_models", fromlist=["x"]),
        "RUNNER_SCHEMA_VERSION_V58",
    )
    assert not hasattr(
        __import__("simulation.runner_models", fromlist=["x"]),
        "RUNNER_SCHEMA_VERSION_V60",
    )
    assert FINALIZATION_COMMAND_ACCEPTED_VERSIONS == frozenset(
        {
            FINALIZATION_COMMAND_CODEC_VERSION,
            FINALIZATION_COMMAND_CODEC_VERSION_V2,
            FINALIZATION_COMMAND_CODEC_VERSION_V3,
            FINALIZATION_COMMAND_CODEC_VERSION_V4,
            FINALIZATION_COMMAND_CODEC_VERSION_V5,
            FINALIZATION_COMMAND_CODEC_VERSION_V6,
        }
    )
    from world.events import EVENT_SCHEMA_REPLAY_V27, EVENT_SCHEMA_REPLAY_V28

    assert EVENT_SCHEMA_REPLAY_V27 != EVENT_SCHEMA_REPLAY_V28


def test_catalog_context_api_and_route_pins() -> None:
    assert METRIC_FAMILY_COUNT == 275
    assert V4_CONTEXT_MAP_VERSION == "v4-context-map-v6"
    assert SCIENTIFIC_MODELS_ROUTE_COUNT == 8
    from simulation.scientific_models_models import (
        SCIENTIFIC_MODELS_SNAPSHOT_SCHEMA,
    )

    assert SCIENTIFIC_MODELS_SNAPSHOT_SCHEMA == "scientific-models-snapshot-v1"


def test_blank_slate_rejects_populated_predictive_state() -> None:
    from simulation.new_agent_initialization import (
        BlankSlateStoreCounts,
        assert_blank_slate_subjective_state,
    )
    from tests.unit.test_scientific_models_lifecycle import _season_ledger

    ledger = _season_ledger()
    assert_blank_slate_subjective_state(ledger.owner_id, BlankSlateStoreCounts())
    with pytest.raises(ValueError, match="scientific_model_ledger"):
        assert_blank_slate_subjective_state(
            ledger.owner_id,
            BlankSlateStoreCounts(scientific_model_ledger=1),
        )
