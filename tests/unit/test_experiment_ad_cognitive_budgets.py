"""Experiment AD: low-cost vs high-cost cognitive budgets."""

from __future__ import annotations

from dataclasses import replace

import pytest

from agents.cognition.budget import high_cost_budget_limits, low_cost_budget_limits
from experiments.catalog import experiment_ad_cognitive_budgets
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V22,
    CognitiveBudgetMode,
    ProspectiveImaginationMode,
)
from tests.unit.test_runner_serialization import _configured

pytestmark = pytest.mark.unit


def test_experiment_ad_arms_share_world_differ_only_by_limits() -> None:
    base = _configured(schema_version="runner-config-v4")
    definition = experiment_ad_cognitive_budgets(base)
    assert definition.experiment_id == "experiment-ad-cognitive-budgets"
    by_id = {item.condition_id: item for item in definition.conditions}
    assert set(by_id) == {"ad-low-cost", "ad-high-cost"}
    low = by_id["ad-low-cost"].runner_config
    high = by_id["ad-high-cost"].runner_config
    assert low.schema_version == RUNNER_SCHEMA_VERSION_V22
    assert high.schema_version == RUNNER_SCHEMA_VERSION_V22
    assert low.seed == high.seed == base.seed
    assert low.scenario == high.scenario
    assert low.stochastic_identity == high.stochastic_identity
    low_preset = low_cost_budget_limits()
    high_preset = high_cost_budget_limits()
    for agent in low.agents:
        assert agent.cognition.cognitive_budget_mode is CognitiveBudgetMode.ENFORCED
        assert (
            agent.cognition.prospective_mode
            is ProspectiveImaginationMode.DETERMINISTIC
        )
        limits = agent.cognition.cognitive_budget_limits
        assert limits is not None
        assert limits.max_llm_calls_per_tick == low_preset.max_llm_calls_per_tick
        assert limits.max_imagination_branches == low_preset.max_imagination_branches
    for agent in high.agents:
        limits = agent.cognition.cognitive_budget_limits
        assert limits is not None
        assert limits.max_llm_calls_per_tick == high_preset.max_llm_calls_per_tick
        assert limits.max_imagination_branches == high_preset.max_imagination_branches
    # Only limits differ across matching agent slots.
    for left, right in zip(low.agents, high.agents, strict=True):
        stripped_left = replace(
            left.cognition,
            cognitive_budget_limits=None,
            cognitive_budget_mode=CognitiveBudgetMode.DISABLED,
        )
        stripped_right = replace(
            right.cognition,
            cognitive_budget_limits=None,
            cognitive_budget_mode=CognitiveBudgetMode.DISABLED,
        )
        assert stripped_left == stripped_right


def test_experiment_ad_absent_from_v1_gate() -> None:
    from pathlib import Path

    gate = Path("tests/unit/test_v1_regression_gate.py").read_text(encoding="utf-8")
    assert "experiment-ad-cognitive-budgets" not in gate
    assert "experiment_ad_cognitive_budgets" not in gate


@pytest.mark.asyncio
async def test_experiment_ad_arms_low_charges_strictly_fewer() -> None:
    from dataclasses import replace

    from analysis.cognitive_budget_metrics import compute_cognitive_budget_metrics
    from simulation.models import RunId
    from simulation.runner import SimulationRunner
    from simulation.runner_models import RunnerStopPolicy

    base = _configured(schema_version="runner-config-v4")
    definition = experiment_ad_cognitive_budgets(base)
    by_id = {item.condition_id: item for item in definition.conditions}
    low_cfg = replace(
        by_id["ad-low-cost"].runner_config,
        stop_policy=RunnerStopPolicy(max_ticks=2),
    )
    high_cfg = replace(
        by_id["ad-high-cost"].runner_config,
        stop_policy=RunnerStopPolicy(max_ticks=2),
    )
    async with await SimulationRunner.from_config(
        low_cfg, run_id=RunId("run-ad-low")
    ) as runner:
        low_result = await runner.run()
        low_audits = runner.export_cognitive_budget_audits()
    async with await SimulationRunner.from_config(
        high_cfg, run_id=RunId("run-ad-high")
    ) as runner:
        high_result = await runner.run()
        high_audits = runner.export_cognitive_budget_audits()
    assert low_audits
    assert high_audits
    assert low_result.cognitive_budget_audits == low_audits
    # Objective receipt schema stays closed / compatible across arms.
    assert low_result.finalized_tick_receipts
    assert high_result.finalized_tick_receipts
    assert {
        type(item).__name__ for item in low_result.finalized_tick_receipts
    } == {type(item).__name__ for item in high_result.finalized_tick_receipts}
    doc = compute_cognitive_budget_metrics(
        (),
        run_id="run-ad-compare",
        input_revision="rev-1",
        low_cost_rows=low_audits,
        high_cost_rows=high_audits,
    )
    low_llm = sum(getattr(row, "llm_calls_used", 0) or 0 for row in low_audits)
    high_llm = sum(getattr(row, "llm_calls_used", 0) or 0 for row in high_audits)
    low_branches = sum(
        getattr(row, "imagination_branches_used", 0) or 0 for row in low_audits
    )
    high_branches = sum(
        getattr(row, "imagination_branches_used", 0) or 0 for row in high_audits
    )
    # Low-cost hard-caps LLM at 0; provider-less arms often charge 0 LLM on both.
    assert low_llm <= high_llm
    if high_llm > 0:
        assert doc.values["low_vs_high_llm_calls_strictly_fewer"] is True
    assert low_branches < high_branches
    assert doc.values["low_vs_high_branches_strictly_fewer"] is True
