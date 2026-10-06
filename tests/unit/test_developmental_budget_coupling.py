"""Cognitive budget coupling for developmental acquisition."""

from __future__ import annotations

from dataclasses import replace

from agents.cognition.budget import (
    BudgetDimension,
    TickBudgetLedger,
    default_cognitive_budget_policy,
)
from agents.cognition.developmental_learning import apply_developmental_budget_coupling
from agents.models import AgentId


def _exhausted_ledger() -> TickBudgetLedger:
    policy = replace(default_cognitive_budget_policy(), max_recalled_memories=1)
    ledger = TickBudgetLedger(owner_id=AgentId("b"), tick=1, policy=policy)
    assert ledger.try_consume(BudgetDimension.MEMORIES, 1)
    assert ledger.remaining(BudgetDimension.MEMORIES) == 0
    return ledger


def test_ignore_mode_passthrough() -> None:
    decision = apply_developmental_budget_coupling(
        owner_id=AgentId("b"),
        effective_rate=0.8,
        coupling_mode="ignore",
        degrade_policy="skip_acquisition",
        acquisition_cost_units=5,
        budget_enforced=True,
        budget_ledger=None,
    )
    assert decision.proceed is True
    assert decision.effective_rate == 0.8
    assert decision.reason_code == "budget_passthrough"


def test_skip_acquisition_when_exhausted() -> None:
    ledger = _exhausted_ledger()
    decision = apply_developmental_budget_coupling(
        owner_id=AgentId("b"),
        effective_rate=1.0,
        coupling_mode="respect_enforced",
        degrade_policy="skip_acquisition",
        acquisition_cost_units=1,
        budget_enforced=True,
        budget_ledger=ledger,
    )
    assert decision.proceed is False
    assert decision.reason_code == "budget_skip_acquisition"


def test_reduce_rate_when_exhausted() -> None:
    ledger = _exhausted_ledger()
    decision = apply_developmental_budget_coupling(
        owner_id=AgentId("b"),
        effective_rate=0.8,
        coupling_mode="respect_enforced",
        degrade_policy="reduce_rate",
        acquisition_cost_units=1,
        budget_enforced=True,
        budget_ledger=ledger,
    )
    assert decision.proceed is True
    assert decision.effective_rate == 0.4
    assert decision.reason_code == "budget_reduce_rate"
