"""Reflection conclusions stay inside subjective evidence."""

from __future__ import annotations

from agents.cognition.reflection import (
    DecisionOutcomeCode,
    ReflectionContext,
    ReflectionPolicy,
    ReflectionTriggerKind,
    ReflectionTriggerResult,
    SubjectiveDecisionRecord,
    drop_unprovenanced_candidates,
    materialize_reflection_candidates,
    plan_reflection,
)
from agents.models import AgentId
from tests.unit.test_reflection_policy import _context, _trace


def test_foreign_evidence_is_dropped() -> None:
    traces = tuple(
        _trace(
            f"mem-{index}",
            predicate="is_safe",
            subject_id="ridge",
            object_id="agent-1",
        )
        for index in range(3)
    )
    candidates = materialize_reflection_candidates(_context(memories=traces))
    assert candidates
    dropped = drop_unprovenanced_candidates(
        _context(memories=()),
        candidates,
    )
    assert dropped == ()


def test_decision_records_do_not_become_beliefs() -> None:
    owner = AgentId("agent-1")
    records = tuple(
        SubjectiveDecisionRecord(
            record_id=f"decision-{index}",
            owner_id=owner,
            tick=index,
            command_kind="Search",
            outcome_code=DecisionOutcomeCode.NO_PROGRESS,
            day_phase="night",
            place_id="forest",
        )
        for index in range(3)
    )
    candidates = materialize_reflection_candidates(_context(decisions=records))
    assert candidates
    assert all(item.belief_request is None for item in candidates)
    assert any(item.goal_intent is not None for item in candidates)


def test_false_memory_is_not_corrected_from_outside_facts() -> None:
    traces = tuple(
        _trace(
            f"mem-{index}",
            predicate="is_safe",
            subject_id="ridge",
            object_id="agent-1",
        )
        for index in range(3)
    )
    outside_fact = {"place": "ridge", "predicate": "is_dangerous"}
    context = _context(memories=traces)
    plan = plan_reflection(
        context=context,
        triggers=ReflectionTriggerResult(
            matched=(ReflectionTriggerKind.ELAPSED_TICKS,),
            skipped=(),
            gap_elapsed=True,
        ),
        mode="deterministic",
    )
    assert plan is not None
    assert plan.belief_revisions
    assert plan.belief_revisions[0].claim.predicate == "is_safe"
    assert outside_fact["predicate"] != plan.belief_revisions[0].claim.predicate
    assert type(context) is ReflectionContext
    assert type(context.policy) is ReflectionPolicy
