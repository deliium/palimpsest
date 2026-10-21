"""Experiment BK opportunity arms, reproducibility, and neutral structure."""

from __future__ import annotations

import pytest

from agents.cognition.institutional_decay import InstitutionDecayLedger
from experiments.catalog import OFF_GATE_MATRIX_EXPERIMENT_IDS
from experiments.institutional_decay_scenario import (
    assert_institutional_decay_structure,
    experiment_bk_institutional_decay,
    institutional_decay_scenario,
)
from experiments.institutionalization_scenario import institutionalization_scenario
from simulation.models import RunId
from simulation.runner import SimulationRunner
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V53,
    RUNNER_SCHEMA_VERSION_V54,
    InstitutionalDecayMode,
    InstitutionConceptMode,
    SimulationRunnerConfig,
)


def _base(seed: int = 23) -> SimulationRunnerConfig:
    definition = institutionalization_scenario(seed=seed, max_ticks=2)
    return next(
        condition.runner_config
        for condition in definition.conditions
        if condition.condition_id == "bf-baseline"
    )


def test_bk_registration_and_off_gate_arms() -> None:
    definition = experiment_bk_institutional_decay(_base(), max_ticks=2)
    assert definition.experiment_id == "institutional_decay@1"
    assert [condition.condition_id for condition in definition.conditions] == [
        "bk-baseline",
        "bk-decay-off",
        "bk-decay-on",
        "bk-record-opportunities",
        "bk-teaching-opportunities",
        "bk-limited-opportunities",
    ]
    assert "institutional_decay@1" in OFF_GATE_MATRIX_EXPERIMENT_IDS
    assert_institutional_decay_structure(definition)


def test_decay_off_and_on_share_world_and_seed_surface() -> None:
    definition = institutional_decay_scenario(seed=23, max_ticks=2)
    by_id = {
        condition.condition_id: condition.runner_config
        for condition in definition.conditions
    }
    off = by_id["bk-decay-off"]
    on = by_id["bk-decay-on"]
    assert off.seed == on.seed
    assert off.scenario.world_id == on.scenario.world_id
    assert [agent.agent_id for agent in off.agents] == [
        agent.agent_id for agent in on.agents
    ]
    assert off.schema_version == RUNNER_SCHEMA_VERSION_V53
    assert on.schema_version == RUNNER_SCHEMA_VERSION_V54
    assert all(
        agent.cognition.institutional_decay_mode is InstitutionalDecayMode.DETERMINISTIC
        for agent in on.agents
    )
    assert all(
        agent.cognition.institution_concept_mode is InstitutionConceptMode.DETERMINISTIC
        for agent in on.agents
    )


def test_opportunity_arms_are_distinct_treatments() -> None:
    definition = institutional_decay_scenario(seed=23, max_ticks=2)
    by_id = {
        condition.condition_id: condition.runner_config
        for condition in definition.conditions
    }
    assert by_id["bk-record-opportunities"] != by_id["bk-decay-on"]
    assert by_id["bk-teaching-opportunities"] != by_id["bk-decay-on"]
    assert by_id["bk-limited-opportunities"] != by_id["bk-teaching-opportunities"]


def test_no_scripted_collapse_arms() -> None:
    definition = institutional_decay_scenario(seed=23, max_ticks=2)
    for condition in definition.conditions:
        assert not hasattr(condition.runner_config, "collapse_at_tick")
        assert condition.label_code.startswith("institutional_decay_")


@pytest.mark.asyncio
async def test_decay_on_arm_runs_and_exports_without_requiring_collapse() -> None:
    definition = institutional_decay_scenario(seed=23, max_ticks=2)
    config = next(
        condition.runner_config
        for condition in definition.conditions
        if condition.condition_id == "bk-decay-on"
    )
    async with await SimulationRunner.from_config(
        config, run_id=RunId("run-bk-decay")
    ) as runner:
        await runner.run()
        ledgers = runner.export_institutional_decay_ledgers()
    assert all(
        isinstance(ledger, InstitutionDecayLedger) and ledger.owner_id is not None
        for ledger in ledgers
    )
    # Zero patterns is a valid research outcome.
    assert isinstance(ledgers, tuple)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "condition_id",
    [
        "bk-record-opportunities",
        "bk-teaching-opportunities",
        "bk-limited-opportunities",
    ],
)
async def test_opportunity_arms_run_with_real_evidence(condition_id: str) -> None:
    definition = institutional_decay_scenario(seed=23, max_ticks=2)
    config = next(
        condition.runner_config
        for condition in definition.conditions
        if condition.condition_id == condition_id
    )
    async with await SimulationRunner.from_config(
        config, run_id=RunId("run-" + condition_id)
    ) as runner:
        await runner.run()
        ledgers = runner.export_institutional_decay_ledgers()
    assert ledgers
    assert all(
        isinstance(ledger, InstitutionDecayLedger) and ledger.owner_id is not None
        for ledger in ledgers
    )


@pytest.mark.asyncio
async def test_repeated_seed_produces_reproducible_decay_state() -> None:
    definition = institutional_decay_scenario(seed=23, max_ticks=2)
    config = next(
        condition.runner_config
        for condition in definition.conditions
        if condition.condition_id == "bk-decay-on"
    )
    snapshots = []
    for _ in range(2):
        async with await SimulationRunner.from_config(
            config, run_id=RunId("run-bk-repro")
        ) as runner:
            await runner.run()
            snapshots.append(runner.export_institutional_decay_ledgers())
    assert snapshots[0] == snapshots[1]
