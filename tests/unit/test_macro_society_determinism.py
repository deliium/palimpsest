"""Determinism: permutation invariance and repeated-run stability."""

from __future__ import annotations

import random

from hypothesis import given, settings
from hypothesis import strategies as st

from analysis.macro_society_contract import MacroSocietyLane
from analysis.macro_society_detection import detect_macro_society_candidates
from analysis.macro_society_evidence import (
    MacroSocietyEdge,
    MacroSocietyToken,
    MacroSocietyWindowEvidence,
)
from analysis.macro_society_identity import assign_macro_society_identities
from analysis.macro_society_lineage import build_macro_society_analysis

PERSONS = tuple(f"person-{index}" for index in range(1, 13))


def _edges() -> tuple[MacroSocietyEdge, ...]:
    return tuple(
        MacroSocietyEdge(MacroSocietyLane.INTERACTION, source, target, 0)
        for index, source in enumerate(PERSONS[:6])
        for target in PERSONS[:6][index + 1 :]
    )


def _tokens() -> tuple[MacroSocietyToken, ...]:
    return tuple(
        MacroSocietyToken(MacroSocietyLane.CULTURE, person, "trait-1")
        for person in PERSONS[:6]
    )


def _window(
    edges: tuple[MacroSocietyEdge, ...],
    tokens: tuple[MacroSocietyToken, ...],
    persons: tuple[str, ...],
) -> MacroSocietyWindowEvidence:
    return MacroSocietyWindowEvidence(
        window_index=0,
        tick_start=0,
        tick_end=9,
        person_ids=persons,
        edges=edges,
        tokens=tokens,
    )


def _fingerprint(
    window: MacroSocietyWindowEvidence,
) -> tuple[tuple[object, ...], tuple[str, ...], str]:
    result = detect_macro_society_candidates(window)
    assignment = assign_macro_society_identities((result,))
    analysis = build_macro_society_analysis(windows=(result,), assignment=assignment)
    return (
        tuple((c.candidate_key, c.member_ids, c.status) for c in result.candidates),
        tuple(r.macro_society_id for r in analysis.records),
        analysis.determinism_digest,
    )


@given(seed=st.integers(min_value=0, max_value=10_000))
@settings(max_examples=25, deadline=None)
def test_permutation_never_changes_detection_or_identity(seed: int) -> None:
    rng = random.Random(seed)
    edges = list(_edges())
    tokens = list(_tokens())
    persons = list(PERSONS)
    rng.shuffle(edges)
    rng.shuffle(tokens)
    rng.shuffle(persons)
    permuted = _window(tuple(edges), tuple(tokens), tuple(persons))
    assert _fingerprint(permuted) == _fingerprint(
        _window(_edges(), _tokens(), PERSONS)
    )


def test_repeated_runs_are_byte_identical() -> None:
    first = _fingerprint(_window(_edges(), _tokens(), PERSONS))
    second = _fingerprint(_window(_edges(), _tokens(), PERSONS))
    assert first == second


def test_disjoint_candidate_never_changes_existing_ids() -> None:
    base = detect_macro_society_candidates(_window(_edges(), _tokens(), PERSONS))
    base_assignment = assign_macro_society_identities((base,))
    extra = (
        MacroSocietyToken(MacroSocietyLane.CULTURE, person, "trait-2")
        for person in PERSONS[6:]
    )
    extended = detect_macro_society_candidates(
        _window(_edges(), (*_tokens(), *extra), PERSONS)
    )
    extended_assignment = assign_macro_society_identities((extended,))
    base_ids = {record.macro_society_id for record in base_assignment.records}
    extended_ids = {record.macro_society_id for record in extended_assignment.records}
    assert base_ids <= extended_ids
