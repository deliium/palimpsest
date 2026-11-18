# mypy: ignore-errors

"""Completed-run exports, result validation and blank-slate separation."""

from __future__ import annotations

from dataclasses import replace

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
from tests.unit.test_scientific_models_runtime import _arm

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
