"""Stable identity assignment across windows."""

from __future__ import annotations

import pytest

from analysis.macro_society_contract import (
    MacroSocietyError,
    MacroSocietyLane,
    MacroSocietyStatus,
)
from analysis.macro_society_detection import (
    MacroSocietyWindowResult,
    detect_macro_society_candidates,
)
from analysis.macro_society_evidence import (
    MacroSocietyToken,
    MacroSocietyWindowEvidence,
)
from analysis.macro_society_identity import (
    MacroSocietyRecord,
    assign_macro_society_identities,
    record_at,
    record_for,
)


def _window(
    index: int, groups: dict[str, tuple[str, ...]], *, extra: tuple[str, ...] = ()
) -> MacroSocietyWindowResult:
    tokens = tuple(
        MacroSocietyToken(MacroSocietyLane.CULTURE, person, token)
        for token, members in groups.items()
        for person in members
    )
    persons = tuple(
        sorted(
            {person for members in groups.values() for person in members} | set(extra)
        )
    )
    return detect_macro_society_candidates(
        MacroSocietyWindowEvidence(
            window_index=index,
            tick_start=index * 10,
            tick_end=index * 10 + 9,
            person_ids=persons,
            tokens=tokens,
        )
    )


def _persons(start: int, count: int) -> tuple[str, ...]:
    return tuple(f"person-{index}" for index in range(start, start + count))


def test_identical_windows_keep_one_identity() -> None:
    group = _persons(1, 6)
    windows = [_window(index, {"trait-1": group}) for index in (0, 1, 2)]
    assignment = assign_macro_society_identities(windows)
    assert len(assignment.records) == 1
    record = assignment.records[0]
    assert record.window_indexes == (0, 1, 2)
    assert record.first_tick == 0
    assert record.creation_tick == 0
    assert record.last_tick == 29


def test_small_churn_keeps_the_identity() -> None:
    first = _persons(1, 10)
    second = (*_persons(1, 9), "person-11")
    assignment = assign_macro_society_identities(
        [_window(0, {"trait-1": first}), _window(1, {"trait-1": second})]
    )
    assert len(assignment.records) == 1
    assert assignment.records[0].window_indexes == (0, 1)


def test_large_churn_mints_a_new_identity() -> None:
    first = _persons(1, 10)
    # Six of ten founders leave; containment 0.4 is below the absorption floor.
    second = (*_persons(1, 4), *_persons(11, 6))
    assignment = assign_macro_society_identities(
        [_window(0, {"trait-1": first}), _window(1, {"trait-1": second})]
    )
    assert len(assignment.records) == 2
    created = [record for record in assignment.records if record.creation_tick == 10]
    assert len(created) == 1


def test_disappearance_and_appearance_are_distinct_identities() -> None:
    assignment = assign_macro_society_identities(
        [
            _window(0, {"trait-1": _persons(1, 5)}),
            _window(1, {"trait-2": _persons(20, 5)}),
        ]
    )
    assert len(assignment.records) == 2
    ids = {record.macro_society_id for record in assignment.records}
    assert len(ids) == 2


def test_assignment_is_order_independent() -> None:
    first = _window(0, {"trait-1": _persons(1, 6)})
    second = _window(1, {"trait-1": _persons(1, 6)})
    forward = assign_macro_society_identities([first, second])
    backward = assign_macro_society_identities([first, second])
    assert forward.records == backward.records
    assert forward.window_assignments == backward.window_assignments


def test_non_monotonic_windows_are_rejected() -> None:
    with pytest.raises(MacroSocietyError, match="macro_society_nonmonotonic_window"):
        assign_macro_society_identities(
            [
                _window(1, {"trait-1": _persons(1, 5)}),
                _window(0, {"trait-1": _persons(1, 5)}),
            ]
        )


def test_empty_input_is_rejected() -> None:
    with pytest.raises(MacroSocietyError, match="macro_society_empty_window"):
        assign_macro_society_identities([])


def test_lookup_helpers_resolve_known_and_unknown_identities() -> None:
    window = _window(0, {"trait-1": _persons(1, 5)})
    assignment = assign_macro_society_identities([window])
    record = assignment.records[0]
    assert record_for(assignment, record.macro_society_id) == record
    assert (
        record_at(assignment, 0, window.candidates[0].candidate_key)
        == assignment.records[0]
    )
    with pytest.raises(MacroSocietyError, match="macro_society_unknown_society"):
        record_for(assignment, "msoc-0000000000000000")


def test_record_rejects_creation_tick_mismatch() -> None:
    with pytest.raises(MacroSocietyError, match="macro_society_invalid_creation_tick"):
        MacroSocietyRecord(
            macro_society_id="msoc-0123456789abcdef",
            creation_tick=5,
            first_tick=4,
            last_tick=9,
            status=MacroSocietyStatus.SUPPORTED,
            member_ids=_persons(1, 4),
            lane_signature=("culture",),
            window_indexes=(0,),
        )
