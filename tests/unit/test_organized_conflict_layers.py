# ruff: noqa: E501
# mypy: disable-error-code="arg-type,assignment,union-attr,attr-defined,no-untyped-def,no-untyped-call,call-overload,index,type-arg,unused-ignore"
from __future__ import annotations

import pytest

from analysis.organized_conflict_layers import (
    ConflictAnalyticalRow,
    ConflictLayerView,
    ConflictObjectiveRow,
    ConflictSubjectiveRow,
    assert_conflict_layer_separation,
    project_conflict_layers,
)
from analysis.organized_conflict_policy import (
    default_organized_conflict_analysis_policy,
)
from analysis.organized_conflict_rows import harvest_organized_conflict_rows

POLICY = default_organized_conflict_analysis_policy()


def test_objective_rows_have_no_owner_or_candidate() -> None:
    row = ConflictObjectiveRow(tick=1, hostile_event_count=2)
    assert not hasattr(row, "owner_token")
    assert not hasattr(row, "candidate_id")


def test_subjective_rows_have_no_candidate_id() -> None:
    row = ConflictSubjectiveRow(owner_token="a" * 16, plan_count=1)
    assert not hasattr(row, "candidate_id")
    assert row.owner_token == "a" * 16


def test_analytical_rows_reject_forbidden_fields() -> None:
    with pytest.raises(ValueError):
        ConflictAnalyticalRow(candidate_id="dip-" + "a" * 16, classification="x")
    with pytest.raises(TypeError):
        ConflictAnalyticalRow(
            candidate_id="oc-" + "a" * 16,
            classification="coordinated_conflict",
            winner="a",  # type: ignore[call-arg]
        )


def test_projection_is_sorted_and_guarded() -> None:
    harvest = harvest_organized_conflict_rows((), (), policy=POLICY)
    view = project_conflict_layers(harvest, ())
    assert isinstance(view, ConflictLayerView)
    assert view.objective == ()
    assert view.subjective == ()
    assert view.analytical == ()
    assert_conflict_layer_separation(view)
    with pytest.raises(ValueError):
        assert_conflict_layer_separation(
            ConflictLayerView(
                objective=(ConflictObjectiveRow(tick=1),),
                analytical=(
                    ConflictAnalyticalRow(
                        candidate_id="bad", classification="coordinated_conflict"
                    ),
                ),
            )
        )
