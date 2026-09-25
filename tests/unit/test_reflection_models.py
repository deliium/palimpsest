"""Contracts for reflection modes, policy, cursor, and conclusions."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from agents.cognition import (
    REFLECTION_POLICY_VERSION,
    CognitionLoopConfig,
    CognitionReflectionMode,
    DecisionOutcomeCode,
    ReflectionAudit,
    ReflectionCandidate,
    ReflectionConclusionKind,
    ReflectionCursor,
    ReflectionPatternCode,
    ReflectionPolicy,
    SubjectiveDecisionRecord,
    default_reflection_policy,
)
from agents.models import AgentId, GoalHorizon, GoalId
from memory.models import SCORE_QUANTUM
from simulation.runner_models import ConsolidationMode, ReflectionMode

_ROOT = Path(__file__).resolve().parents[2]


def test_disabled_is_the_default_and_modes_are_lockstep() -> None:
    assert ReflectionMode.DISABLED.value == "disabled"
    assert CognitionReflectionMode.DISABLED.value == "disabled"
    assert {mode.value for mode in ReflectionMode} == {
        mode.value for mode in CognitionReflectionMode
    }
    assert {mode.value for mode in ReflectionMode} == {
        mode.value for mode in ConsolidationMode
    }
    assert default_reflection_policy().allow_provider is False
    assert default_reflection_policy().version == REFLECTION_POLICY_VERSION
    assert default_reflection_policy().interval_ticks == 8
    assert default_reflection_policy().min_gap_ticks == 8
    assert CognitionLoopConfig().reflection_policy is None


def test_cursor_accepts_missing_tick_and_rejects_negative() -> None:
    owner = AgentId("agent-1")
    cursor = ReflectionCursor(owner_id=owner)
    assert cursor.last_reflection_tick is None
    with pytest.raises(ValueError, match="non-negative"):
        ReflectionCursor(owner_id=owner, last_reflection_tick=-1)


def test_policy_quantizes_thresholds_and_fails_closed() -> None:
    raw_intensity = 0.7 + (SCORE_QUANTUM * 0.6)
    policy = ReflectionPolicy(emotion_intensity=raw_intensity)
    assert policy.emotion_intensity == pytest.approx(0.7 + SCORE_QUANTUM)
    assert policy.emotion_intensity != raw_intensity
    override = ReflectionPolicy(interval_ticks=1)
    assert override.interval_ticks == 1
    assert override.min_gap_ticks == 1
    explicit_gap = ReflectionPolicy(interval_ticks=8, min_gap_ticks=2)
    assert explicit_gap.min_gap_ticks == 2
    with pytest.raises(ValueError):
        ReflectionPolicy(emotion_intensity=float("nan"))
    with pytest.raises(ValueError):
        ReflectionPolicy(interval_ticks=0)
    with pytest.raises(ValueError):
        ReflectionPolicy(interval_ticks=-1)
    with pytest.raises(TypeError):
        ReflectionPolicy(allow_provider=1)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        ReflectionPolicy(version="reflection-v0")
    kinds = ReflectionPolicy(significant_occurrence_kinds=("injury",))
    assert kinds.significant_occurrence_kinds == ("injury",)
    assert kinds.major_goal_horizons == (GoalHorizon.DESIRE, GoalHorizon.LONG_TERM)
    with pytest.raises(TypeError):
        ReflectionPolicy(significant_occurrence_kinds={"injury"})  # type: ignore[arg-type]


def test_candidate_and_audit_repr_omit_claim_text() -> None:
    owner = AgentId("agent-1")
    candidate = ReflectionCandidate(
        candidate_id="cand-1",
        owner_id=owner,
        tick=3,
        kind=ReflectionConclusionKind.NEW_HYPOTHESIS,
        pattern_code=ReflectionPatternCode.REPEATED_HELP,
        evidence_ids=("mem-1", "mem-2"),
        count=2,
        predicate="helped",
        counterpart_id="agent-2",
    )
    rendered = repr(candidate)
    assert "helped" not in rendered
    assert "agent-2" not in rendered
    assert "evidence_count=2" in rendered
    with pytest.raises(ValueError, match="empty_evidence"):
        ReflectionCandidate(
            candidate_id="cand-empty",
            owner_id=owner,
            tick=1,
            kind=ReflectionConclusionKind.REVISED_BELIEF,
            pattern_code=ReflectionPatternCode.REPEATED_ACTION,
            evidence_ids=(),
            count=1,
        )
    audit = ReflectionAudit(
        owner_id=owner,
        tick=4,
        mode="deterministic",
        trigger_codes=("elapsed_ticks",),
        conclusion_kind_counts=(("new_hypothesis", 1),),
        evidence_id_count=2,
        fallback_used=False,
        reason_code="applied",
    )
    audit_text = repr(audit)
    assert "helped" not in audit_text
    assert "new_hypothesis" not in audit_text
    assert "reason_code='applied'" in audit_text
    with pytest.raises(ValueError, match="invalid_mode"):
        ReflectionAudit(
            owner_id=owner,
            tick=0,
            mode="emergent",
            trigger_codes=(),
            conclusion_kind_counts=(),
            evidence_id_count=0,
            fallback_used=False,
        )


def test_decision_record_keeps_outcome_code_without_narrative() -> None:
    record = SubjectiveDecisionRecord(
        record_id="decision-1",
        owner_id=AgentId("agent-1"),
        tick=2,
        command_kind="SearchCommand",
        outcome_code=DecisionOutcomeCode.UNKNOWN,
        day_phase="night",
        place_id="place-1",
    )
    assert record.outcome_code is DecisionOutcomeCode.UNKNOWN
    assert "night" not in repr(record)
    assert "place-1" not in repr(record)
    cursor = ReflectionCursor(
        owner_id=AgentId("agent-1"),
        acknowledged_goal_ids=(GoalId("goal-1"),),
    )
    assert "goal-1" not in repr(cursor)


def test_loop_config_may_carry_policy_for_tests() -> None:
    policy = ReflectionPolicy(interval_ticks=1, allow_provider=False)
    config = CognitionLoopConfig(reflection_policy=policy)
    assert config.reflection_policy == policy
    with pytest.raises(TypeError):
        CognitionLoopConfig(reflection_policy="reflection-v1")  # type: ignore[arg-type]


def test_reflection_module_does_not_import_world_events_or_simulation() -> None:
    path = _ROOT / "src" / "agents" / "cognition" / "reflection.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.add(node.module)
    banned = [
        name
        for name in imported
        if name == "simulation" or name.startswith("simulation.")
    ]
    banned.extend(
        name
        for name in imported
        if name == "world.events" or name.startswith("world.events.")
    )
    assert banned == []
