"""Institution emergence and persistence metric families."""

from __future__ import annotations

from analysis.institution_emergence import (
    InstitutionLane,
    InstitutionLaneRow,
    compute_institution_candidates,
    compute_institution_emergence,
)
from analysis.institutional_persistence import (
    InstitutionPersistenceClassification,
    compute_institutional_persistence,
    compute_institutional_persistence_metric,
)
from analysis.specifications import MetricFamilyId, metric_specification


def _row(
    lane: InstitutionLane,
    subject: str,
    evidence: str,
    *,
    start: int,
    end: int,
    count: int = 1,
    generation: tuple[int, int] | None = None,
) -> InstitutionLaneRow:
    return InstitutionLaneRow(
        lane=lane,
        subject_digest=subject,
        evidence_digest=evidence,
        tick_start=start,
        tick_end=end,
        occurrence_count=count,
        generation_start=None if generation is None else generation[0],
        generation_end=None if generation is None else generation[1],
    )


def _lane_char(value: str) -> str:
    return value * 16


def test_strong_bundle_and_short_burst_classify_differently() -> None:
    role = _row(
        InstitutionLane.ROLE, _lane_char("a"), _lane_char("b"), start=1, end=8, count=3
    )
    procedure = _row(
        InstitutionLane.PROCEDURE,
        _lane_char("a"),
        _lane_char("c"),
        start=1,
        end=8,
        count=3,
    )
    expectation = _row(
        InstitutionLane.EXPECTATION,
        _lane_char("a"),
        _lane_char("d"),
        start=1,
        end=8,
        count=3,
    )
    succession = _row(
        InstitutionLane.SUCCESSION, _lane_char("a"), _lane_char("e"), start=4, end=8
    )
    burst = _row(InstitutionLane.ROLE, _lane_char("f"), _lane_char("0"), start=9, end=9)
    result = compute_institution_candidates(
        role_rows=(role, burst),
        procedure_rows=(procedure,),
        expectation_rows=(expectation,),
        succession_rows=(succession,),
    )
    assert len(result.candidates) == 1
    assert result.candidates[0].above_floor is True
    weak = compute_institution_candidates(expectation_rows=(expectation,))
    assert len(weak.candidates) == 0
    assert len(weak.sub_threshold) == 1


def test_missing_lanes_report_absent_without_errors() -> None:
    result = compute_institution_candidates(role_rows=(), tick=3)
    document = compute_institution_emergence(
        result, run_id="run-1", input_revision="rev-1", tick=3
    )
    assert document.metric_family == "institution_emergence"
    assert document.availability.value == "absent"
    assert document.values["candidate_count"] == 0


def test_candidate_ids_are_content_stable() -> None:
    row = _row(InstitutionLane.ROLE, _lane_char("a"), _lane_char("b"), start=1, end=4)
    first = compute_institution_candidates(role_rows=(row,))
    second = compute_institution_candidates(role_rows=(row,))
    assert (
        first.candidates[0].candidate_id
        if first.candidates
        else first.sub_threshold[0].candidate_id
    ) == (
        second.candidates[0].candidate_id
        if second.candidates
        else second.sub_threshold[0].candidate_id
    )


def test_family_specifications_are_registered() -> None:
    assert (
        metric_specification(MetricFamilyId.INSTITUTION_EMERGENCE).family_id
        is MetricFamilyId.INSTITUTION_EMERGENCE
    )
    assert (
        metric_specification(MetricFamilyId.INSTITUTIONAL_PERSISTENCE).family_id
        is MetricFamilyId.INSTITUTIONAL_PERSISTENCE
    )


def test_persistence_classifies_temporary_and_persistent() -> None:
    persistent_rows = (
        _row(
            InstitutionLane.ROLE,
            _lane_char("a"),
            _lane_char("b"),
            start=1,
            end=10,
            count=3,
        ),
        _row(
            InstitutionLane.CONTINUITY,
            _lane_char("a"),
            _lane_char("c"),
            start=1,
            end=10,
            generation=(0, 2),
        ),
        _row(
            InstitutionLane.SUCCESSION,
            _lane_char("a"),
            _lane_char("d"),
            start=5,
            end=10,
        ),
    )
    burst = _row(InstitutionLane.ROLE, _lane_char("e"), _lane_char("f"), start=3, end=3)
    persistent_result = compute_institution_candidates(
        role_rows=(persistent_rows[0],),
        continuity_rows=(persistent_rows[1],),
        succession_rows=(persistent_rows[2],),
    )
    burst_result = compute_institution_candidates(role_rows=(burst,))
    persistence = compute_institutional_persistence(persistent_result)
    burst_persistence = compute_institutional_persistence(burst_result)
    assert all(
        row.classification
        is InstitutionPersistenceClassification.PERSISTENT_INSTITUTION_LIKE
        for row in persistence.rows
    )
    assert all(
        row.classification
        is InstitutionPersistenceClassification.TEMPORARY_COORDINATION
        for row in burst_persistence.rows
    )
    document = compute_institutional_persistence_metric(
        persistence, run_id="run-1", input_revision="rev-1"
    )
    assert document.metric_family == "institutional_persistence"
    assert document.values["candidate_count"] == 1
    assert document.values["persistent_institution_like_count"] == 1
    assert document.values["temporary_coordination_count"] == 0
    assert document.values["survival_curve"]


def test_persistence_absent_without_candidates() -> None:
    result = compute_institution_candidates(role_rows=())
    persistence = compute_institutional_persistence(result)
    document = compute_institutional_persistence_metric(
        persistence, run_id="run-1", input_revision="rev-1"
    )
    assert document.availability.value == "absent"
