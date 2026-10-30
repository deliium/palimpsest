"""Split, merge, dissolve, and emerge lineage across adjacent windows."""

from __future__ import annotations

import pytest

from analysis.macro_society_contract import (
    MacroSocietyError,
    MacroSocietyLane,
    MacroSocietyLineageKind,
    MacroSocietyStatus,
    derive_macro_society_id,
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
)
from analysis.macro_society_lineage import (
    MacroSocietyAnalysis,
    MacroSocietyLineageEdge,
    build_macro_society_analysis,
    validate_macro_society_lineage,
)


def _persons(start: int, count: int) -> tuple[str, ...]:
    return tuple(f"person-{index}" for index in range(start, start + count))


def _window(
    index: int, groups: dict[str, tuple[str, ...]]
) -> MacroSocietyWindowResult:
    tokens = tuple(
        MacroSocietyToken(MacroSocietyLane.CULTURE, person, token)
        for token, members in groups.items()
        for person in members
    )
    persons = tuple(
        sorted({person for members in groups.values() for person in members})
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


def _analysis(
    windows: list[MacroSocietyWindowResult],
) -> MacroSocietyAnalysis:
    assignment = assign_macro_society_identities(windows)
    return build_macro_society_analysis(windows=windows, assignment=assignment)


def _record(macro_id: str, tick: int, members: tuple[str, ...]) -> MacroSocietyRecord:
    return MacroSocietyRecord(
        macro_society_id=macro_id,
        creation_tick=tick,
        first_tick=tick,
        last_tick=tick + 9,
        status=MacroSocietyStatus.SUPPORTED,
        member_ids=members,
        lane_signature=("culture",),
        window_indexes=(0,),
    )


def test_stable_candidate_yields_continued_edges() -> None:
    group = _persons(1, 6)
    analysis = _analysis([_window(index, {"trait-1": group}) for index in (0, 1, 2)])
    kinds = [edge.kind for edge in analysis.edges]
    assert kinds.count(MacroSocietyLineageKind.CONTINUED) == 2
    assert all(
        edge.jaccard == 1.0
        for edge in analysis.edges
        if edge.kind is MacroSocietyLineageKind.CONTINUED
    )


def test_split_produces_two_children_with_new_identities() -> None:
    parent = _persons(1, 8)
    analysis = _analysis(
        [
            _window(0, {"trait-1": parent}),
            _window(1, {"trait-a": _persons(1, 4), "trait-b": _persons(5, 4)}),
        ]
    )
    splits = [
        edge for edge in analysis.edges if edge.kind is MacroSocietyLineageKind.SPLIT
    ]
    assert len(splits) == 2
    children = {edge.to_id for edge in splits}
    assert len(children) == 2
    assert all(
        record.creation_tick == 10
        for record in analysis.records
        if record.macro_society_id in children
    )


def test_merge_produces_a_new_identity_from_two_parents() -> None:
    analysis = _analysis(
        [
            _window(0, {"trait-a": _persons(1, 6), "trait-b": _persons(3, 6)}),
            _window(1, {"trait-c": _persons(1, 8)}),
        ]
    )
    merges = [
        edge for edge in analysis.edges if edge.kind is MacroSocietyLineageKind.MERGE
    ]
    assert len(merges) == 2
    assert len({edge.to_id for edge in merges}) == 1
    merged_id = merges[0].to_id
    record = next(
        record
        for record in analysis.records
        if record.macro_society_id == merged_id
    )
    assert record.creation_tick == 10


def test_unrelated_successor_dissolves_and_emerges() -> None:
    analysis = _analysis(
        [
            _window(0, {"trait-1": _persons(1, 5)}),
            _window(1, {"trait-2": _persons(20, 5)}),
        ]
    )
    kinds = [edge.kind for edge in analysis.edges]
    assert kinds.count(MacroSocietyLineageKind.DISSOLVED) == 1
    assert kinds.count(MacroSocietyLineageKind.EMERGED) == 2
    dissolved = next(
        edge
        for edge in analysis.edges
        if edge.kind is MacroSocietyLineageKind.DISSOLVED
    )
    assert dissolved.to_id is None


def test_lineage_edges_are_forward_only() -> None:
    group = _persons(1, 6)
    analysis = _analysis([_window(index, {"trait-1": group}) for index in (0, 1)])
    assert all(edge.from_tick <= edge.to_tick for edge in analysis.edges)


def test_cycle_is_rejected() -> None:
    first = derive_macro_society_id(
        creation_tick=0,
        founding_member_ids=_persons(1, 4),
        lane_signature=("culture",),
    )
    second = derive_macro_society_id(
        creation_tick=10,
        founding_member_ids=_persons(5, 4),
        lane_signature=("culture",),
    )
    records = (
        _record(first, 0, _persons(1, 4)),
        _record(second, 10, _persons(5, 4)),
    )
    edges = (
        MacroSocietyLineageEdge(
            first,
            second,
            MacroSocietyLineageKind.CONTINUED,
            0,
            10,
            1.0,
        ),
        MacroSocietyLineageEdge(
            second,
            first,
            MacroSocietyLineageKind.CONTINUED,
            10,
            20,
            1.0,
        ),
    )
    with pytest.raises(MacroSocietyError, match="macro_society_lineage_cycle"):
        validate_macro_society_lineage(edges, records)


def test_backward_tick_is_rejected_at_construction() -> None:
    first = derive_macro_society_id(
        creation_tick=0,
        founding_member_ids=_persons(1, 4),
        lane_signature=("culture",),
    )
    with pytest.raises(
        MacroSocietyError, match="macro_society_lineage_nonmonotonic_tick"
    ):
        MacroSocietyLineageEdge(
            first, first, MacroSocietyLineageKind.CONTINUED, 20, 10, 1.0
        )


def test_single_child_split_is_ambiguous() -> None:
    first = derive_macro_society_id(
        creation_tick=0,
        founding_member_ids=_persons(1, 4),
        lane_signature=("culture",),
    )
    second = derive_macro_society_id(
        creation_tick=10,
        founding_member_ids=_persons(5, 4),
        lane_signature=("culture",),
    )
    records = (
        _record(first, 0, _persons(1, 4)),
        _record(second, 10, _persons(5, 4)),
    )
    edges = (
        MacroSocietyLineageEdge(
            first, second, MacroSocietyLineageKind.SPLIT, 0, 10, 0.5
        ),
    )
    with pytest.raises(
        MacroSocietyError, match="macro_society_lineage_ambiguous_parent"
    ):
        validate_macro_society_lineage(edges, records)


def test_digest_changes_with_membership() -> None:
    first = _window(0, {"trait-1": _persons(1, 6)})
    second = _window(1, {"trait-1": _persons(1, 6)})
    baseline = _analysis([first, second])
    changed = _analysis(
        [
            _window(0, {"trait-1": _persons(1, 6)}),
            _window(1, {"trait-1": _persons(1, 5)}),
        ]
    )
    assert baseline.determinism_digest != changed.determinism_digest
    assert len(baseline.determinism_digest) == 64
