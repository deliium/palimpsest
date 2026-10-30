"""Candidate detection: lanes, overlap, fragmentation, and contention."""

from __future__ import annotations

from analysis.macro_society_contract import (
    MacroSocietyLane,
    MacroSocietyMembershipStatus,
    MacroSocietyStatus,
)
from analysis.macro_society_detection import detect_macro_society_candidates
from analysis.macro_society_evidence import (
    MacroSocietyEdge,
    MacroSocietyToken,
    MacroSocietyWindowEvidence,
)

PERSONS = tuple(f"person-{index}" for index in range(1, 9))


def _edges(lane: MacroSocietyLane, members: tuple[str, ...]) -> list[MacroSocietyEdge]:
    edges: list[MacroSocietyEdge] = []
    for index, source in enumerate(members):
        for target in members[index + 1 :]:
            edges.append(MacroSocietyEdge(lane, source, target, 0))
    return edges


def _tokens(
    lane: MacroSocietyLane, members: tuple[str, ...], token: str
) -> list[MacroSocietyToken]:
    return [MacroSocietyToken(lane, member, token) for member in members]


def _window(
    *,
    persons: tuple[str, ...] = PERSONS,
    edges: tuple[MacroSocietyEdge, ...] = (),
    tokens: tuple[MacroSocietyToken, ...] = (),
    index: int = 0,
) -> MacroSocietyWindowEvidence:
    return MacroSocietyWindowEvidence(
        window_index=index,
        tick_start=index * 10,
        tick_end=index * 10 + 9,
        person_ids=persons,
        edges=edges,
        tokens=tokens,
    )


def test_two_disjoint_cliques_produce_two_candidates() -> None:
    left = PERSONS[:4]
    right = PERSONS[4:]
    result = detect_macro_society_candidates(
        _window(
            edges=tuple(
                _edges(MacroSocietyLane.INTERACTION, left)
                + _edges(MacroSocietyLane.INTERACTION, right)
            )
        )
    )
    assert len(result.candidates) == 2
    assert {candidate.member_ids for candidate in result.candidates} == {
        tuple(sorted(left)),
        tuple(sorted(right)),
    }
    assert result.overlap_person_ids == ()
    assert result.fragment_person_ids == ()


def test_shared_culture_token_merges_two_interaction_clusters() -> None:
    left = PERSONS[:4]
    right = PERSONS[4:]
    result = detect_macro_society_candidates(
        _window(
            edges=tuple(
                _edges(MacroSocietyLane.INTERACTION, left)
                + _edges(MacroSocietyLane.INTERACTION, right)
            ),
            tokens=tuple(
                _tokens(MacroSocietyLane.CULTURE, PERSONS, "trait-1")
            ),
        )
    )
    assert len(result.candidates) == 1
    candidate = result.candidates[0]
    assert set(candidate.lanes) == {
        MacroSocietyLane.INTERACTION,
        MacroSocietyLane.CULTURE,
    }
    assert candidate.status is MacroSocietyStatus.SUPPORTED


def test_person_in_two_token_groups_is_overlap_not_error() -> None:
    culture_members = PERSONS[:4]
    territory_members = (PERSONS[0], *PERSONS[4:7])
    result = detect_macro_society_candidates(
        _window(
            tokens=tuple(
                _tokens(MacroSocietyLane.CULTURE, culture_members, "trait-1")
            )
            + tuple(
                _tokens(
                    MacroSocietyLane.TERRITORY, territory_members, "region:r-1"
                )
            )
        )
    )
    assert len(result.candidates) == 2
    assert result.overlap_person_ids == (PERSONS[0],)
    assert all(
        candidate.status is MacroSocietyStatus.FRAGMENTED
        for candidate in result.candidates
    )


def test_single_lane_below_coverage_floor_is_fragmented() -> None:
    persons = tuple(f"person-{index}" for index in range(1, 21))
    result = detect_macro_society_candidates(
        _window(
            persons=persons,
            tokens=tuple(
                _tokens(MacroSocietyLane.CULTURE, persons[:4], "trait-1")
            ),
        )
    )
    assert len(result.candidates) == 1
    assert result.candidates[0].status is MacroSocietyStatus.FRAGMENTED
    assert len(result.fragment_person_ids) == 16


def test_self_identification_claim_elsewhere_contests_the_candidate() -> None:
    core = PERSONS[:4]
    rival = (PERSONS[2], PERSONS[3], PERSONS[4], PERSONS[5])
    result = detect_macro_society_candidates(
        _window(
            edges=tuple(_edges(MacroSocietyLane.INTERACTION, core))
            + tuple(_edges(MacroSocietyLane.EXCHANGE, core)),
            tokens=tuple(
                _tokens(MacroSocietyLane.SELF_IDENTIFICATION, rival, "group-2")
            ),
        )
    )
    contested = [
        candidate
        for candidate in result.candidates
        if candidate.status is MacroSocietyStatus.CONTESTED
    ]
    assert len(contested) == 1
    membership = dict(contested[0].membership)
    assert membership[PERSONS[2]] is MacroSocietyMembershipStatus.CONTESTED
    assert membership[PERSONS[3]] is MacroSocietyMembershipStatus.CONTESTED


def test_member_missing_from_most_lanes_is_partial() -> None:
    core = PERSONS[:4]
    extra = (*PERSONS[0:3], PERSONS[4])
    result = detect_macro_society_candidates(
        _window(
            tokens=tuple(_tokens(MacroSocietyLane.CULTURE, core, "trait-1"))
            + tuple(_tokens(MacroSocietyLane.INSTITUTION, core, "pattern-1"))
            + tuple(_tokens(MacroSocietyLane.TERRITORY, core, "region:r-1"))
            + tuple(
                _tokens(MacroSocietyLane.SELF_IDENTIFICATION, extra, "group-1")
            ),
        )
    )
    assert len(result.candidates) == 1
    membership = dict(result.candidates[0].membership)
    assert membership[PERSONS[4]] is MacroSocietyMembershipStatus.PARTIAL


def test_empty_evidence_reports_fragments_not_zero_societies() -> None:
    result = detect_macro_society_candidates(_window())
    assert result.candidates == ()
    assert result.fragment_person_ids == PERSONS
    assert result.coverage.ratio == 0.0
    assert all(present is False for _, present in result.lane_presence)


def test_detection_is_order_independent() -> None:
    left = PERSONS[:4]
    right = PERSONS[4:]
    edges = _edges(MacroSocietyLane.INTERACTION, left) + _edges(
        MacroSocietyLane.INTERACTION, right
    )
    tokens = _tokens(MacroSocietyLane.CULTURE, PERSONS, "trait-1")
    forward = detect_macro_society_candidates(
        _window(edges=tuple(edges), tokens=tuple(tokens))
    )
    backward = detect_macro_society_candidates(
        _window(
            edges=tuple(reversed(edges)), tokens=tuple(reversed(tokens))
        )
    )
    assert forward == backward


def test_candidate_keys_are_stable_and_opaque() -> None:
    left = PERSONS[:4]
    result = detect_macro_society_candidates(
        _window(tokens=tuple(_tokens(MacroSocietyLane.CULTURE, left, "trait-1")))
    )
    key = result.candidates[0].candidate_key
    assert key.startswith("msoc-candidate-")
    assert len(key) == len("msoc-candidate-") + 16
