"""Detached institutional-decay windows, known-answer aggregation, lifecycle."""

from __future__ import annotations

from dataclasses import replace

import pytest

from analysis.institutional_decay import (
    InstitutionDecayAnalysisError,
    InstitutionDecayAvailability,
    InstitutionKnowledgeAssessment,
    InstitutionTemporalRow,
    compute_institutional_decay,
)


def _agent(value: str) -> str:
    return value


def _row(
    tick: int,
    *,
    supporters: tuple[tuple[str, str], ...] = (),
    participant_actions: tuple[tuple[str, str], ...] = (),
    procedure: tuple[str, ...] = (),
    succession: tuple[str, ...] = (),
    completed: tuple[str, ...] = (),
    assessments: tuple[InstitutionKnowledgeAssessment, ...] = (),
    role: float = 0.6,
    legitimacy: float = 0.5,
) -> InstitutionTemporalRow:
    a, b, c = _agent("a"), _agent("b"), _agent("c")
    return InstitutionTemporalRow(
        owner_id="owner",
        local_pattern_id="p" * 64,
        observation_tick=tick,
        source_first_tick=max(tick - 1, 0),
        source_last_tick=tick,
        role_recognition=role,
        procedure_recurrence=0.6,
        social_expectation=0.5,
        legitimacy_belief=legitimacy,
        succession_observed=0.0,
        generational_continuity=0.0,
        recognized=True,
        observed_cohort=(a, b, c),
        supporters=supporters,
        participant_actions=participant_actions,
        performed_procedure_keys=procedure,
        succession_transitions=succession,
        completed_transitions=completed,
        knowledge_assessments=assessments,
        structural_components=("a" * 16, "b" * 16),
    )


def test_known_answer_five_dimension_window() -> None:
    a, b, c = _agent("a"), _agent("b"), _agent("c")
    supporters = ((a, "r1"), (b, "r2"))
    actions = ((a, "action-a"), (c, "action-c"), (a, "action-a"))
    assessment = InstitutionKnowledgeAssessment(
        transition_id="t1",
        before_entry_ids=("e1", "e2", "e3"),
        retained_entry_ids=("e1", "e2"),
    )
    rows = tuple(
        _row(
            tick,
            supporters=supporters,
            participant_actions=actions,
            procedure=("proc",) if tick <= 3 else (),
            succession=("t1", "t2") if tick == 1 else (),
            completed=("t1",) if tick == 1 else (),
            assessments=(assessment,) if tick == 1 else (),
        )
        for tick in (1, 2, 3, 4)
    )
    result = compute_institutional_decay(rows, as_of_tick=4)
    assert len(result.windows) == 1
    window = result.windows[0]
    assert window.complete is True
    assert window.support_ratio == pytest.approx(2 / 3)
    assert window.participation_ratio == pytest.approx(2 / 3)
    assert window.procedure_ratio == pytest.approx(3 / 4)
    assert window.succession_ratio == pytest.approx(1 / 2)
    assert window.knowledge_ratio == pytest.approx(2 / 3)
    assert result.state_for[("owner", "p" * 64)] == "stable"


def test_gapped_window_is_incomplete_and_unknown() -> None:
    rows = tuple(_row(tick) for tick in (1, 2, 3))
    result = compute_institutional_decay(rows, as_of_tick=4)
    assert len(result.windows) == 1
    assert result.windows[0].complete is False
    assert result.state_for[("owner", "p" * 64)] == "unknown"


def test_future_evidence_is_rejected() -> None:
    with pytest.raises(InstitutionDecayAnalysisError, match="future_evidence"):
        compute_institutional_decay((_row(5),), as_of_tick=4)


def test_missing_denominators_are_unknown_not_zero() -> None:
    rows = tuple(
        replace(
            _row(tick, supporters=(), participant_actions=(), procedure=()),
            observed_cohort=(),
        )
        for tick in (1, 2, 3, 4)
    )
    result = compute_institutional_decay(rows, as_of_tick=4)
    window = result.windows[0]
    assert window.support_availability is InstitutionDecayAvailability.UNKNOWN
    assert window.support_ratio is None
    assert window.participation_ratio is None
    assert window.procedure_ratio == 0.0


def test_two_concurrent_patterns_stay_separate() -> None:
    rows = []
    for pattern, tick in (("a" * 64, 1), ("b" * 64, 1)):
        row = _row(tick)
        rows.append(
            InstitutionTemporalRow(
                owner_id=row.owner_id,
                local_pattern_id=pattern,
                observation_tick=row.observation_tick,
                source_first_tick=row.source_first_tick,
                source_last_tick=row.source_last_tick,
                role_recognition=row.role_recognition,
                procedure_recurrence=row.procedure_recurrence,
                social_expectation=row.social_expectation,
                legitimacy_belief=row.legitimacy_belief,
                succession_observed=0.0,
                generational_continuity=0.0,
                recognized=True,
            )
        )
    result = compute_institutional_decay(rows, as_of_tick=4)
    assert len(result.states) == 2


def test_legitimacy_decline_classifies_weakening() -> None:
    a, b = _agent("a"), _agent("b")
    rows = []
    for tick in range(1, 5):
        rows.append(
            _row(
                tick,
                legitimacy=0.8,
                supporters=((a, "r1"), (b, "r2")),
                participant_actions=((a, "act-a"), (b, "act-b")),
                procedure=("p",),
            )
        )
    for tick in range(5, 9):
        rows.append(_row(tick, legitimacy=0.6, role=0.6, procedure=("p",)))
    result = compute_institutional_decay(tuple(rows), as_of_tick=8)
    assert result.state_for[("owner", "p" * 64)] == "weakening"


def test_stable_then_two_low_windows_confirms_collapse() -> None:
    a, b = _agent("a"), _agent("b")
    rows = []
    for tick in (1, 2, 3, 4):
        rows.append(
            _row(
                tick,
                supporters=((a, "r1"), (b, "r2")),
                participant_actions=((a, "act-a"), (b, "act-b")),
                procedure=("proc",),
            )
        )
    for tick in range(5, 13):
        rows.append(_row(tick))
    result = compute_institutional_decay(tuple(rows), as_of_tick=12)
    assert result.state_for[("owner", "p" * 64)] == "collapsed"
    assert result.collapsed_intervals == (("owner", "p" * 64, 5, 12),)


def test_single_low_window_is_weakening_not_collapse() -> None:
    a, b = _agent("a"), _agent("b")
    rows = [
        _row(
            tick,
            supporters=((a, "r1"), (b, "r2")),
            participant_actions=((a, "act-a"), (b, "act-b")),
            procedure=("proc",),
        )
        for tick in (1, 2, 3, 4)
    ]
    rows.extend(_row(tick) for tick in range(5, 9))
    result = compute_institutional_decay(tuple(rows), as_of_tick=8)
    assert result.state_for[("owner", "p" * 64)] == "weakening"
    assert result.collapsed_intervals == ()


def test_pruned_low_window_censors_collapse() -> None:
    a, b = _agent("a"), _agent("b")
    rows = [
        _row(
            tick,
            supporters=((a, "r1"), (b, "r2")),
            participant_actions=((a, "act-a"), (b, "act-b")),
            procedure=("proc",),
        )
        for tick in (1, 2, 3, 4)
    ]
    for tick in range(5, 13):
        rows.append(replace(_row(tick), pruned=True))
    result = compute_institutional_decay(tuple(rows), as_of_tick=12)
    assert result.state_for[("owner", "p" * 64)] != "collapsed"
