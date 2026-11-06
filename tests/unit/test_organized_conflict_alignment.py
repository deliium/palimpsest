# ruff: noqa: E501
# mypy: disable-error-code="arg-type,assignment,union-attr,attr-defined,no-untyped-def,no-untyped-call,call-overload,index,type-arg,unused-ignore"
from __future__ import annotations

from types import SimpleNamespace

from analysis.organized_conflict_alignment import (
    align_conflict_interpretations,
    summarize_organized_conflict,
)
from analysis.organized_conflict_detection import ConflictEpisodeCandidate


def _candidate(classification: str, start: int = 1, end: int = 10, events=("attack",)):
    return ConflictEpisodeCandidate(
        candidate_key="k",
        classification=classification,
        start_tick=start,
        end_tick=end,
        participant_tokens=("a" * 16,),
        opponent_tokens=("b" * 16,),
        event_classes=events,
        candidate_id="oc-" + "a" * 16,
    )


def _interpretation(kind: str, tick: int = 5, ident: str = "oci-" + "a" * 16):
    return SimpleNamespace(
        kind=kind,
        tick=tick,
        interpretation_id=ident,
        owner_token="c" * 16,
    )


def test_alignment_values() -> None:
    individual = (_candidate("individual_violence"),)
    persistent = (_candidate("persistent_inter_group_conflict"),)
    coordinated = (_candidate("coordinated_conflict"),)
    rows = align_conflict_interpretations(
        (
            _interpretation("individual_violence"),
            _interpretation("coordinated_conflict"),
            _interpretation("defense"),
            _interpretation("unclear"),
            _interpretation("assistance", tick=100),
        ),
        coordinated,
    )
    assert [row.alignment.value for row in rows] == [
        "inconsistent",
        "consistent",
        "consistent",
        "unresolved",
        "unresolved",
    ]
    assert (
        align_conflict_interpretations(
            (_interpretation("individual_violence"),), individual
        )[0].alignment.value
        == "consistent"
    )
    assert (
        align_conflict_interpretations(
            (_interpretation("coordinated_conflict"),), persistent
        )[0].alignment.value
        == "consistent"
    )
    assert (
        align_conflict_interpretations(
            (_interpretation("coordinated_conflict", tick=100),), ()
        )[0].alignment.value
        == "not_applicable"
    )


def test_token_mismatch_is_not_matched_by_tick_alone() -> None:
    candidate = (_candidate("coordinated_conflict"),)
    interpretation = _interpretation("coordinated_conflict")
    interpretation.participant_tokens = ("d" * 16,)
    row = align_conflict_interpretations((interpretation,), candidate)[0]
    assert row.alignment.value == "unresolved"
    assert row.candidate_id == ""


def test_summary_counts_disagreement() -> None:
    candidates = (_candidate("coordinated_conflict"),)
    interpretations = (
        _interpretation("coordinated_conflict", ident="oci-" + "a" * 16),
        _interpretation("individual_violence", ident="oci-" + "b" * 16),
    )
    rows = align_conflict_interpretations(interpretations, candidates)
    summary = summarize_organized_conflict(
        SimpleNamespace(owner_interpretations=interpretations), candidates, rows
    )
    assert summary.interpretation_count == 2
    assert summary.owner_disagreement_count == 1
    assert summary.consistent_count >= 1
