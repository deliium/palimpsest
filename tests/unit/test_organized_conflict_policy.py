# ruff: noqa: E501
# mypy: disable-error-code="arg-type,assignment,union-attr,attr-defined,no-untyped-def,no-untyped-call,call-overload,index,type-arg,unused-ignore"
from __future__ import annotations

from dataclasses import FrozenInstanceError, replace

import pytest

from agents.cognition.organized_conflict import (
    ORGANIZED_CONFLICT_POLICY_VERSION,
    OrganizedConflictError,
    OrganizedConflictPolicy,
    default_organized_conflict_policy,
)
from analysis.organized_conflict_policy import (
    ORGANIZED_CONFLICT_ANALYSIS_POLICY_VERSION,
    OrganizedConflictAnalysisError,
    OrganizedConflictAnalysisPolicy,
    default_organized_conflict_analysis_policy,
)


def test_cognition_policy_values_are_exact() -> None:
    policy = default_organized_conflict_policy()
    assert ORGANIZED_CONFLICT_POLICY_VERSION == "organized-conflict.v1"
    assert policy.max_plans == 8
    assert policy.max_participants_per_plan == 16
    assert policy.max_observations == 64
    assert policy.max_interpretations == 16
    assert policy.max_outcomes == 32
    assert policy.max_contradictions == 8
    assert policy.max_terminations == 16
    assert policy.max_total_records == 128
    assert policy.max_frame_chars == 256
    assert policy.plan_ttl_ticks == 24
    assert policy.max_target_refs == 8
    assert policy == OrganizedConflictPolicy()


def test_analysis_thresholds_are_exact_and_frozen() -> None:
    policy = default_organized_conflict_analysis_policy()
    assert (
        ORGANIZED_CONFLICT_ANALYSIS_POLICY_VERSION == "organized-conflict-analysis.v1"
    )
    assert policy.window_ticks == 6
    assert policy.min_side_actors == 2
    assert policy.min_hostile_events == 2
    assert policy.min_coordinated_windows == 2
    assert policy.min_windows == 3
    assert policy.sustained_span_ticks == 24
    assert policy.sustained_min_hostile_events == 6
    assert policy.sustained_min_active_ticks == 3
    assert policy.inter_group_min_sides == 2
    assert policy.inter_group_min_actors_per_side == 2
    assert policy.reciprocal_min_windows == 2
    assert policy.max_episodes == 2048
    assert policy.max_windows == 4096
    assert policy.max_participants_per_episode == 64
    assert policy.confidence_bands == (0.25, 0.5, 0.75)
    with pytest.raises(FrozenInstanceError):
        policy.window_ticks = 7  # type: ignore[misc]


def test_policy_rejects_bool_as_int() -> None:
    with pytest.raises(OrganizedConflictError):
        replace(default_organized_conflict_policy(), max_plans=True)
    with pytest.raises(OrganizedConflictAnalysisError):
        replace(default_organized_conflict_analysis_policy(), window_ticks=True)
    with pytest.raises(OrganizedConflictError):
        OrganizedConflictPolicy(max_plans=9)
    with pytest.raises(OrganizedConflictAnalysisError):
        OrganizedConflictAnalysisPolicy(window_ticks=7)


def test_default_policies_are_deterministic() -> None:
    assert default_organized_conflict_policy() == default_organized_conflict_policy()
    assert (
        default_organized_conflict_analysis_policy()
        == default_organized_conflict_analysis_policy()
    )
