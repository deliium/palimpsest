# mypy: ignore-errors

"""Completed-run exports, result validation and blank-slate separation."""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest

from agents.cognition.scientific_models import (
    ScientificModelLedger,
    empty_scientific_model_ledger,
    scientific_model_content_count,
)
from agents.models import AgentId
from simulation.models import RunId
from simulation.new_agent_initialization import (
    BlankSlateStoreCounts,
    assert_blank_slate_subjective_state,
)
from simulation.runner import RunnerDependencyFactories, SimulationRunner
from simulation.runner_models import RunnerStopPolicy
from tests.unit.test_scientific_models_lifecycle import _observation, _season_ledger
from tests.unit.test_scientific_models_runtime import _arm
from tests.unit.test_scientific_models_scenario import _base

pytestmark = pytest.mark.unit

_OWNER = AgentId("agent-1")


def test_content_count_distinguishes_pristine_and_populated_state() -> None:
    assert scientific_model_content_count(None) == 0
    assert scientific_model_content_count(empty_scientific_model_ledger(_OWNER)) == 0
    from tests.unit.test_scientific_models_lifecycle import _season_ledger

    assert scientific_model_content_count(_season_ledger()) > 0
    with pytest.raises(ValueError, match="invalid_type"):
        scientific_model_content_count(object())


def test_pristine_blank_slate_counts_pass_and_populated_fail() -> None:
    assert_blank_slate_subjective_state(_OWNER, BlankSlateStoreCounts())
    with pytest.raises(ValueError, match="scientific_model_ledger"):
        assert_blank_slate_subjective_state(
            _OWNER, BlankSlateStoreCounts(scientific_model_ledger=1)
        )


@pytest.mark.asyncio
async def test_completed_science_result_carries_owner_predictive_ledgers() -> None:
    runner = await SimulationRunner.from_config(
        _arm("science-enabled"),
        run_id=RunId("run-scientific-model-result"),
        factories=RunnerDependencyFactories(),
    )
    async with runner:
        result = await runner.run()
    ledgers = runner.export_scientific_model_ledgers()
    assert len(ledgers) == 2
    assert all(type(ledger) is ScientificModelLedger for ledger in ledgers)
    assert [ledger.owner_id.value for ledger in ledgers] == [
        "agent-1",
        "agent-2",
    ]
    assert result.scientific_model_ledgers == ledgers
    with pytest.raises(TypeError, match="duplicate_owner"):
        replace(
            result,
            scientific_model_ledgers=(ledgers[0], ledgers[0]),
        )


@pytest.mark.asyncio
async def test_science_off_result_carries_no_predictive_ledgers() -> None:
    runner = await SimulationRunner.from_config(
        _arm("science-baseline"),
        run_id=RunId("run-scientific-model-result-baseline"),
        factories=RunnerDependencyFactories(),
    )
    async with runner:
        result = await runner.run()
    assert runner.export_scientific_model_ledgers() == ()
    assert result.scientific_model_ledgers == ()


@pytest.mark.asyncio
async def test_fork_digest_tracks_same_count_predictive_content() -> None:
    from experiments.scientific_models_scenario import scientific_models_scenario
    from simulation.fork_checkpoint import fork_state_digest

    definition = scientific_models_scenario(_base(), max_ticks=96)
    config = next(
        row.runner_config
        for row in definition.conditions
        if row.condition_id == "models-season-resource"
    )
    config = replace(config, stop_policy=RunnerStopPolicy(max_ticks=40))
    runner = await SimulationRunner.from_config(
        config,
        run_id=RunId("run-scientific-model-fork-digest"),
        factories=RunnerDependencyFactories(),
    )
    async with runner:
        for _ in range(20):
            await runner.run_tick()
        checkpoint = await runner.capture_fork_checkpoint()

    baseline = fork_state_digest(checkpoint)
    index = next(
        position
        for position, state in enumerate(checkpoint.runtime_states)
        if state.checkpoint.scientific_model_ledger is not None
    )
    state = checkpoint.runtime_states[index]
    ledger = state.checkpoint.scientific_model_ledger
    assert ledger.cases
    mutated_ledger = replace(
        ledger,
        last_issued_tick=ledger.last_issued_tick + 1,
    )
    mutated_state = replace(
        state,
        checkpoint=replace(
            state.checkpoint,
            scientific_model_ledger=mutated_ledger,
        ),
    )
    mutated = replace(
        checkpoint,
        runtime_states=(
            *checkpoint.runtime_states[:index],
            mutated_state,
            *checkpoint.runtime_states[index + 1 :],
        ),
    )
    assert len(mutated_ledger.cases) == len(ledger.cases)
    assert fork_state_digest(mutated) != baseline


def test_fork_children_settle_independently_without_rewriting_parent() -> None:
    from agents.cognition.scientific_model_observation import resolve_due_model_cases
    from agents.cognition.scientific_models import ForecastCaseState
    from world.environment import Season

    parent = _season_ledger()
    case = max(parent.pending_cases, key=lambda row: row.target_observation_tick)
    target = case.target_observation_tick

    twin_a = resolve_due_model_cases(
        parent, _observation(target, season=Season.SUMMER)
    )
    twin_b = resolve_due_model_cases(
        parent, _observation(target, season=Season.SUMMER)
    )
    divergent = resolve_due_model_cases(
        parent, _observation(target, season=Season.AUTUMN)
    )

    assert twin_a == twin_b
    parent_case = next(row for row in parent.cases if row.case_id == case.case_id)
    assert parent_case.state is ForecastCaseState.PENDING
    assert parent_case.observed is None

    for child in (twin_a, divergent):
        child_case = next(row for row in child.cases if row.case_id == case.case_id)
        assert child_case.predictions == case.predictions
        assert child_case.state is ForecastCaseState.SCORED

    twin_outcome = next(row for row in twin_a.cases if row.case_id == case.case_id)
    divergent_outcome = next(
        row for row in divergent.cases if row.case_id == case.case_id
    )
    assert twin_outcome.observed is not None
    assert divergent_outcome.observed is not None
    assert twin_outcome.observed.observed_class == "summer"
    assert divergent_outcome.observed.observed_class == "autumn"
    assert (
        twin_outcome.observed.observed_class
        != divergent_outcome.observed.observed_class
    )


def test_retired_owner_export_uses_the_retired_runtime_checkpoint() -> None:
    ledger = _season_ledger()
    live = SimpleNamespace(
        export_runtime_checkpoint=lambda: SimpleNamespace(
            scientific_model_ledger=None
        ),
        retired_record=None,
    )
    retired = SimpleNamespace(
        export_runtime_checkpoint=lambda: SimpleNamespace(
            scientific_model_ledger=None
        ),
        retired_record=SimpleNamespace(
            runtime_checkpoint=SimpleNamespace(scientific_model_ledger=ledger)
        ),
    )
    exported = SimulationRunner.export_scientific_model_ledgers(
        SimpleNamespace(_runtimes=(live, retired))
    )
    assert exported == (ledger,)
