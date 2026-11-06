# ruff: noqa: E501
# mypy: disable-error-code="arg-type,assignment,union-attr,attr-defined,no-untyped-def,no-untyped-call,call-overload,index,type-arg,unused-ignore"
from __future__ import annotations

import pytest

from analysis.organized_conflict_alignment import (
    ConflictAlignmentRow,
    ConflictAnalysisSummary,
)
from analysis.organized_conflict_contract import ConflictAlignment
from analysis.organized_conflict_detection import ConflictEpisodeCandidate
from analysis.organized_conflict_metrics import (
    compute_organized_conflict_interpretation,
    compute_organized_conflict_outcomes,
    compute_organized_conflict_participation,
    compute_organized_conflict_persistence,
)
from analysis.organized_conflict_rows import OrganizedConflictHarvestRows
from analysis.specifications import MetricFamilyId, metric_specification

PARTICIPATION_KEYS = (
    "episode_count",
    "individual_episode_count",
    "coordinated_episode_count",
    "persistent_inter_group_episode_count",
    "participant_count",
    "side_count",
    "attacker_count",
    "defender_count",
    "scout_count",
    "blocker_count",
    "capturer_count",
    "assistant_count",
    "retreater_count",
    "messenger_count",
    "unknown_role_count",
    "organized_episode_ratio",
    "role_coverage_ratio",
)
PERSISTENCE_KEYS = (
    "active_window_count",
    "episode_duration_ticks_total",
    "episode_duration_ticks_max",
    "recurrent_episode_count",
    "sustained_episode_count",
    "inter_group_episode_count",
    "reciprocal_window_count",
    "escalation_count",
    "deescalation_count",
    "hostile_event_count",
    "persistence_ratio",
)
OUTCOME_KEYS = (
    "attack_event_count",
    "hit_count",
    "miss_count",
    "damage_total",
    "lethal_attack_count",
    "death_count",
    "flee_success_count",
    "flee_failure_count",
    "custody_capture_count",
    "structure_opposition_count",
    "assistance_count",
    "co_movement_count",
    "route_denial_evidence_count",
    "outcome_coverage_ratio",
)
INTERPRETATION_KEYS = (
    "interpretation_count",
    "individual_interpretation_count",
    "coordinated_interpretation_count",
    "persistent_inter_group_interpretation_count",
    "defense_interpretation_count",
    "retreat_interpretation_count",
    "assistance_interpretation_count",
    "resource_capture_interpretation_count",
    "route_blocking_interpretation_count",
    "structure_attack_interpretation_count",
    "unclear_interpretation_count",
    "aligned_count",
    "unresolved_count",
    "inconsistent_count",
    "not_applicable_count",
    "owner_disagreement_count",
    "interpretation_coverage_ratio",
)


def _candidate() -> ConflictEpisodeCandidate:
    return ConflictEpisodeCandidate(
        candidate_key="k",
        classification="coordinated_conflict",
        start_tick=1,
        end_tick=5,
        participant_tokens=("a" * 16,),
        opponent_tokens=("b" * 16,),
        side_count=1,
        hostile_event_count=2,
        active_window_count=2,
    )


def test_value_keys_match_specifications_exactly() -> None:
    assert (
        metric_specification(MetricFamilyId.ORGANIZED_CONFLICT_PARTICIPATION).value_keys
        == PARTICIPATION_KEYS
    )
    assert (
        metric_specification(MetricFamilyId.ORGANIZED_CONFLICT_PERSISTENCE).value_keys
        == PERSISTENCE_KEYS
    )
    assert (
        metric_specification(MetricFamilyId.ORGANIZED_CONFLICT_OUTCOMES).value_keys
        == OUTCOME_KEYS
    )
    assert (
        metric_specification(
            MetricFamilyId.ORGANIZED_CONFLICT_INTERPRETATION
        ).value_keys
        == INTERPRETATION_KEYS
    )


def test_absent_rows_emit_empty_values() -> None:
    candidate = (_candidate(),)
    documents = (
        compute_organized_conflict_participation(
            None, candidate, run_id="run", input_revision="rev"
        ),
        compute_organized_conflict_persistence(
            None, candidate, run_id="run", input_revision="rev"
        ),
        compute_organized_conflict_outcomes(
            None, candidate, run_id="run", input_revision="rev"
        ),
        compute_organized_conflict_interpretation(
            None,
            candidate,
            (),
            ConflictAnalysisSummary(),
            run_id="run",
            input_revision="rev",
        ),
    )
    for document in documents:
        assert document.values == {}
        assert document.availability.value == "absent"


def test_role_coverage_and_roles_use_owner_rows() -> None:
    from types import SimpleNamespace

    rows = OrganizedConflictHarvestRows(
        owner_participations=(
            SimpleNamespace(role="attacker", participant_ref="a" * 16),
            SimpleNamespace(role="defender", participant_ref="b" * 16),
            SimpleNamespace(role="unknown", participant_ref="c" * 16),
        )
    )
    document = compute_organized_conflict_participation(
        rows, (_candidate(),), run_id="run", input_revision="rev"
    )
    assert document.values["attacker_count"] == 1
    assert document.values["defender_count"] == 1
    assert document.values["unknown_role_count"] == 1
    assert document.values["role_coverage_ratio"] == pytest.approx(2 / 3, abs=1e-9)


def test_escalation_and_route_denial_are_derived() -> None:
    from analysis.organized_conflict_events import ConflictEventRow

    rows = OrganizedConflictHarvestRows(
        objective_events=(
            ConflictEventRow(
                tick=1,
                sequence=0,
                event_class="attack",
                actor_token="a" * 16,
                other_token="b" * 16,
            ),
            ConflictEventRow(
                tick=2,
                sequence=1,
                event_class="attack",
                actor_token="a" * 16,
                other_token="b" * 16,
            ),
            ConflictEventRow(
                tick=2,
                sequence=2,
                event_class="route_denial",
                actor_token="b" * 16,
                other_token="a" * 16,
            ),
        )
    )
    persistence = compute_organized_conflict_persistence(
        rows, (_candidate(),), run_id="run", input_revision="rev"
    )
    assert persistence.values["escalation_count"] == 1
    outcomes = compute_organized_conflict_outcomes(
        rows, (_candidate(),), run_id="run", input_revision="rev"
    )
    assert outcomes.values["route_denial_evidence_count"] == 1


def test_present_rows_emit_counts() -> None:
    rows = OrganizedConflictHarvestRows(
        owner_interpretations=(),
        coverage=ConflictAlignment.CONSISTENT,
    )
    candidate = (_candidate(),)
    participation = compute_organized_conflict_participation(
        rows, candidate, run_id="run", input_revision="rev"
    )
    assert participation.values["episode_count"] == 1
    assert participation.values["coordinated_episode_count"] == 1
    assert participation.values["participant_count"] == 1
    alignment = (
        ConflictAlignmentRow(
            interpretation_id="oci-" + "a" * 16,
            owner_token="c" * 16,
            candidate_id="oc-" + "a" * 16,
            alignment=ConflictAlignment.CONSISTENT,
            interpretation_kind="coordinated_conflict",
            candidate_classification="coordinated_conflict",
        ),
    )
    interpretation = compute_organized_conflict_interpretation(
        rows,
        candidate,
        alignment,
        ConflictAnalysisSummary(consistent_count=1),
        run_id="run",
        input_revision="rev",
    )
    assert interpretation.values["aligned_count"] == 1
    assert set(interpretation.values) == set(INTERPRETATION_KEYS)
