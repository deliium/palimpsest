"""Reflection triggers, decision journal, and checkpoint carry."""

from __future__ import annotations

import pytest

from agents.cognition.reflection import (
    DecisionOutcomeCode,
    ReflectionCursor,
    ReflectionEngine,
    ReflectionPolicy,
    ReflectionTriggerInput,
    ReflectionTriggerKind,
    SubjectiveDecisionRecord,
    advance_decision_journal,
    remember_relationship_ordinals,
)
from agents.models import AgentId, GoalId
from tests.unit.test_agent_runtime import _runtime


def _cursor(last: int | None = None) -> ReflectionCursor:
    return ReflectionCursor(owner_id=AgentId("agent-1"), last_reflection_tick=last)


def _input(**kwargs: object) -> ReflectionTriggerInput:
    policy = kwargs.pop("policy", ReflectionPolicy(interval_ticks=100, min_gap_ticks=1))
    data = {
        "owner_id": AgentId("agent-1"),
        "tick": 0,
        "policy": policy,
        "cursor": _cursor(),
        "mode": "deterministic",
    }
    data.update(kwargs)
    return ReflectionTriggerInput(**data)  # type: ignore[arg-type]


def test_disabled_never_evaluates_and_gap_blocks_a_true_trigger() -> None:
    engine = ReflectionEngine()
    hot = _input(emotion_max_intensity=0.9, tick=0, mode="disabled")
    assert engine.triggers(hot).matched == ()
    held = _input(
        emotion_max_intensity=0.9,
        tick=1,
        policy=ReflectionPolicy(interval_ticks=8, min_gap_ticks=8),
    )
    blocked = engine.triggers(held)
    assert blocked.matched == ()
    assert blocked.skipped == (ReflectionTriggerKind.STRONG_EMOTION,)
    opened = engine.triggers(
        _input(
            tick=7,
            policy=ReflectionPolicy(),
            cursor=_cursor(None),
        )
    )
    assert ReflectionTriggerKind.ELAPSED_TICKS in opened.matched


def test_each_trigger_fires_alone_and_stays_silent_when_false() -> None:
    engine = ReflectionEngine()
    assert engine.triggers(_input(emotion_max_intensity=None)).matched == ()
    emotion = engine.triggers(_input(emotion_max_intensity=0.9))
    assert emotion.matched == (ReflectionTriggerKind.STRONG_EMOTION,)
    quiet_kinds = engine.triggers(
        _input(occurrence_kinds=("injury",), policy=ReflectionPolicy(min_gap_ticks=1))
    )
    assert ReflectionTriggerKind.SIGNIFICANT_OCCURRENCES not in quiet_kinds.matched
    kinds = engine.triggers(
        _input(
            occurrence_kinds=("injury", "injury"),
            policy=ReflectionPolicy(
                interval_ticks=100,
                min_gap_ticks=1,
                significant_occurrence_kinds=("injury",),
                significant_occurrence_count=2,
            ),
        )
    )
    assert kinds.matched == (ReflectionTriggerKind.SIGNIFICANT_OCCURRENCES,)
    failures = tuple(
        SubjectiveDecisionRecord(
            record_id=f"decision-{index}",
            owner_id=AgentId("agent-1"),
            tick=index,
            command_kind="Search",
            outcome_code=DecisionOutcomeCode.NO_PROGRESS,
        )
        for index in range(3)
    )
    unknown = SubjectiveDecisionRecord(
        record_id="decision-open",
        owner_id=AgentId("agent-1"),
        tick=9,
        command_kind="Search",
        outcome_code=DecisionOutcomeCode.UNKNOWN,
    )
    assert (
        ReflectionTriggerKind.REPEATED_FAILURE
        not in engine.triggers(_input(journal=(unknown,))).matched
    )
    repeated = engine.triggers(_input(journal=failures))
    assert repeated.matched == (ReflectionTriggerKind.REPEATED_FAILURE,)
    goals = engine.triggers(_input(completed_goal_ids=(GoalId("goal-1"),)))
    assert goals.matched == (ReflectionTriggerKind.MAJOR_GOAL_COMPLETION,)
    contradiction = engine.triggers(_input(contradiction_masses=(0.9,)))
    assert contradiction.matched == (ReflectionTriggerKind.BELIEF_CONTRADICTION,)
    initial = engine.triggers(
        _input(relationship_ordinals=(("agent-1", "bob", 0),))
    )
    assert ReflectionTriggerKind.RELATIONSHIP_CHANGE not in initial.matched
    marked = ReflectionCursor(
        owner_id=AgentId("agent-1"),
        relationship_ordinals=(),
    )
    stored = remember_relationship_ordinals(
        marked, ((AgentId("agent-1"), AgentId("bob"), 0),)
    )
    changed = engine.triggers(
        _input(
            cursor=stored,
            relationship_ordinals=(("agent-1", "bob", 2),),
        )
    )
    assert changed.matched == (ReflectionTriggerKind.RELATIONSHIP_CHANGE,)


def test_journal_backfill_keeps_the_new_record_unknown() -> None:
    cursor = _cursor()
    cursor, journal = advance_decision_journal(
        cursor=cursor,
        journal=(),
        policy=ReflectionPolicy(max_decision_records=4),
        tick=1,
        command_kind="Search",
        day_phase="night",
        place_id="forest",
        previous_outcome=None,
    )
    assert journal[-1].outcome_code is DecisionOutcomeCode.UNKNOWN
    _, filled = advance_decision_journal(
        cursor=cursor,
        journal=journal,
        policy=ReflectionPolicy(max_decision_records=4),
        tick=2,
        command_kind="Wait",
        day_phase="day",
        place_id="forest",
        previous_outcome=DecisionOutcomeCode.NO_PROGRESS,
    )
    assert filled[0].outcome_code is DecisionOutcomeCode.NO_PROGRESS
    assert filled[-1].outcome_code is DecisionOutcomeCode.UNKNOWN
    assert cursor.last_reflection_tick is None


def test_owner_mismatch_is_rejected() -> None:
    engine = ReflectionEngine()
    with pytest.raises(ValueError, match="owner_mismatch"):
        engine.triggers(
            _input(cursor=ReflectionCursor(owner_id=AgentId("agent-2")))
        )


def test_enabled_finalize_appends_a_journal_without_moving_the_cursor_tick() -> None:
    from agents.cognition.configuration import CognitionReflectionMode

    runtime, _, _ = _runtime()
    runtime._loop._reflection_mode = CognitionReflectionMode.DETERMINISTIC
    runtime._loop._reflection_policy = ReflectionPolicy(
        interval_ticks=8, min_gap_ticks=8
    )
    runtime._reflection_capture = (
        "Search",
        "night",
        "forest",
        DecisionOutcomeCode.NO_PROGRESS,
        (),
    )
    runtime._apply_reflection_journal(3)
    assert runtime._decision_journal is not None
    assert runtime._decision_journal[-1].command_kind == "Search"
    assert runtime._decision_journal[-1].outcome_code is DecisionOutcomeCode.UNKNOWN
    assert runtime._reflection_cursor is not None
    assert runtime._reflection_cursor.last_reflection_tick is None
    assert runtime._reflection_capture is None


def test_disabled_checkpoint_is_empty_and_restore_keeps_the_tick() -> None:
    runtime, _, _ = _runtime()
    checkpoint = runtime.export_runtime_checkpoint()
    assert checkpoint.reflection_cursor is None
    assert checkpoint.decision_journal is None
    cursor = ReflectionCursor(owner_id=AgentId("agent-1"), last_reflection_tick=7)
    runtime._reflection_cursor = cursor
    runtime._decision_journal = ()
    saved = runtime.export_runtime_checkpoint()
    other, _, _ = _runtime()
    other.restore_runtime_checkpoint(saved)
    assert other._reflection_cursor is not None
    assert other._reflection_cursor.last_reflection_tick == 7
