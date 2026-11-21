# mypy: ignore-errors
"""V4-32 off-gate scenario and explicit bounded capture composition."""

from __future__ import annotations

import dataclasses

import pytest

from agents.models import AgentId
from experiments.catalog import experiment_scientific_institutions
from experiments.scientific_institutions_capture import (
    capture_supported,
    run_with_scientific_institution_capture,
)
from experiments.scientific_institutions_scenario import (
    SCIENTIFIC_INSTITUTIONS_EXPERIMENT_ID,
    scientific_institutions_scenario,
)
from simulation.models import RunId, StochasticIdentity
from simulation.runner import RunnerDependencyFactories, SimulationRunner
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V57,
    AgentCognitionSpec,
    AgentRunnerSpec,
    MortalityMode,
    RunnerStopPolicy,
    WorldScenarioSpec,
)
from tests.simulation_helpers import (
    alive_body,
    make_item,
    make_location,
    make_weather,
)
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import default_physical_rules
from world.values import ItemKind

pytestmark = pytest.mark.unit

RUN = "run-sci-inst-scenario"


def _base():
    body_1 = alive_body("body-1", inventory=(EntityId("wood-1"), EntityId("tool-1")))
    body_2 = alive_body(
        "body-2",
        location_id="loc-2",
        inventory=(EntityId("wood-2"), EntityId("tool-2")),
    )
    return _runner_base(body_1, body_2)


def _runner_base(body_1, body_2):
    from experiments.catalog import base_runner_config_from_scenario

    return base_runner_config_from_scenario(
        seed=73,
        stochastic_identity=StochasticIdentity("sci-inst-scenario"),
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-sci-inst-scenario"),
            revision=WorldRevision(0),
            physical_rules=default_physical_rules(),
            locations=(
                make_location("loc-1", adjacent=("loc-2",)),
                make_location("loc-2", adjacent=("loc-1",)),
            ),
            bodies=(body_1, body_2),
            items=(
                make_item(
                    "wood-1",
                    name="wood",
                    kind=ItemKind.MATERIAL,
                    location_id=None,
                    holder_id="body-1",
                ),
                make_item(
                    "wood-2",
                    name="wood",
                    kind=ItemKind.MATERIAL,
                    location_id=None,
                    holder_id="body-2",
                ),
                make_item(
                    "tool-1",
                    name="Chisel",
                    kind=ItemKind.TOOL,
                    location_id=None,
                    holder_id="body-1",
                ),
                make_item(
                    "tool-2",
                    name="Chisel",
                    kind=ItemKind.TOOL,
                    location_id=None,
                    holder_id="body-2",
                ),
            ),
            weather=(make_weather("loc-1"), make_weather("loc-2")),
        ),
        agents=(
            AgentRunnerSpec(
                agent_id=AgentId("agent-1"),
                entity_id=body_1.entity_id,
                cognition=AgentCognitionSpec(agent_id=AgentId("agent-1")),
            ),
            AgentRunnerSpec(
                agent_id=AgentId("agent-2"),
                entity_id=body_2.entity_id,
                cognition=AgentCognitionSpec(agent_id=AgentId("agent-2")),
            ),
        ),
        max_ticks=96,
    )


def _definition():
    return scientific_institutions_scenario(_base(), max_ticks=96)


def _conditions():
    return {
        row.condition_id: row.runner_config for row in _definition().conditions
    }


def test_experiment_registers_four_declared_arms() -> None:
    definition = _definition()
    assert definition.experiment_id == SCIENTIFIC_INSTITUTIONS_EXPERIMENT_ID
    assert [row.condition_id for row in definition.conditions] == [
        "institutions-combined-v56",
        "institutions-org-off",
        "institutions-science-off",
        "institutions-instruments-v57",
    ]
    assert definition.paired_world_group
    assert all(
        row.runner_config.stop_policy.max_ticks == 96
        for row in definition.conditions
    )
    assert all(
        row.runner_config.new_agent_initialization is None
        for row in definition.conditions
    )


def test_combined_and_control_flags_are_exact() -> None:
    conditions = _conditions()
    combined = conditions["institutions-combined-v56"]
    assert combined.v4_capability_flags.organizations is True
    assert combined.v4_capability_flags.science is True
    assert combined.durable_records is not None
    assert combined.knowledge_repositories is not None
    assert combined.collective_projects is not None
    assert conditions["institutions-org-off"].v4_capability_flags.organizations is False
    assert conditions["institutions-org-off"].v4_capability_flags.science is True
    assert conditions["institutions-science-off"].v4_capability_flags.science is False
    assert (
        conditions["institutions-instruments-v57"].schema_version
        == RUNNER_SCHEMA_VERSION_V57
    )
    assert (
        conditions["institutions-instruments-v57"].measurement_instruments
        is not None
    )


def test_no_a_to_e_registration_and_catalog_factory() -> None:
    definition = experiment_scientific_institutions(_base(), max_ticks=96)
    assert definition.experiment_id == "scientific_institutions@1"
    assert len(definition.conditions) == 4


def test_capture_support_requires_owned_channels_and_bounds() -> None:
    conditions = _conditions()
    assert capture_supported(conditions["institutions-combined-v56"]) is True
    assert capture_supported(conditions["institutions-org-off"]) is False
    assert capture_supported(conditions["institutions-science-off"]) is False
    long_config = dataclasses.replace(
        conditions["institutions-combined-v56"],
        stop_policy=RunnerStopPolicy(max_ticks=513),
    )
    assert capture_supported(long_config) is False


@pytest.mark.asyncio
async def test_capture_orders_boundaries_and_disabled_capture_skips_exports() -> None:
    config = _conditions()["institutions-combined-v56"]
    runner = await SimulationRunner.from_config(
        config,
        run_id=RunId(RUN),
        factories=RunnerDependencyFactories(),
    )
    async with runner:
        captured = await run_with_scientific_institution_capture(runner)
    assert captured.status == "captured"
    assert captured.result.ticks_committed == 96
    assert [row.boundary.boundary_tick.value for row in captured.boundaries] == [
        0,
        32,
        64,
        96,
    ]
    assert captured.evidence is not None
    assert len(captured.evidence.windows) == 3
    assert captured.context is not None

    disabled_config = dataclasses.replace(
        config, mortality_mode=MortalityMode.DISABLED
    )
    other = await SimulationRunner.from_config(
        disabled_config,
        run_id=RunId(RUN + "-disabled"),
        factories=RunnerDependencyFactories(),
    )
    async with other:
        skipped = await run_with_scientific_institution_capture(
            other, capture=False
        )
    assert skipped.status == "unavailable"
    assert skipped.evidence is None
    assert skipped.boundaries == ()


@pytest.mark.asyncio
async def test_capture_error_leaves_execution_result(monkeypatch) -> None:
    config = _conditions()["institutions-combined-v56"]
    runner = await SimulationRunner.from_config(
        config,
        run_id=RunId(RUN + "-capture-error"),
        factories=RunnerDependencyFactories(),
    )

    async def _boom(_runner):
        raise RuntimeError("capture_bounds")

    monkeypatch.setattr(
        "experiments.scientific_institutions_capture._capture",
        _boom,
    )
    async with runner:
        failed = await run_with_scientific_institution_capture(runner)
    assert failed.status == "capture_failed"
    assert failed.result.ticks_committed == 96
    assert failed.evidence is None
    assert failed.boundaries == ()


@pytest.mark.asyncio
async def test_partial_terminal_tail_is_not_a_full_window() -> None:
    config = dataclasses.replace(
        _conditions()["institutions-combined-v56"],
        stop_policy=RunnerStopPolicy(max_ticks=40),
    )
    runner = await SimulationRunner.from_config(
        config,
        run_id=RunId(RUN + "-partial"),
        factories=RunnerDependencyFactories(),
    )
    async with runner:
        captured = await run_with_scientific_institution_capture(runner)
    assert captured.status == "captured"
    assert captured.result.ticks_committed == 40
    assert [row.boundary.boundary_tick.value for row in captured.boundaries] == [
        0,
        32,
        40,
    ]
    assert captured.evidence is not None
    assert any(not window.window.complete for window in captured.evidence.windows)
