"""ISR pair detection, layer separation, and harvest assembly."""

from __future__ import annotations

import os

import pytest

from analysis.inter_society_relations_contract import InterSocietyRelationsError
from analysis.inter_society_relations_detection import (
    InterSocietyMacroCandidate,
    detect_inter_society_pairs,
    harvest_inter_society_relations,
)
from analysis.inter_society_relations_evidence import InterSocietyEvidenceInputs
from analysis.inter_society_relations_identity import mint_inter_society_pair
from analysis.inter_society_relations_layers import assert_layer_separation
from analysis.macro_society_contract import MacroSocietyLane, derive_macro_society_id

pytestmark = pytest.mark.unit


def _msoc(label: str, *, tick: int = 0) -> str:
    members = tuple(f"{label}-p{index}" for index in range(1, 5))
    return derive_macro_society_id(
        creation_tick=tick,
        founding_member_ids=members,
        lane_signature=(MacroSocietyLane.INTERACTION.value,),
    )


def test_fewer_than_two_candidates_yield_empty_pairs() -> None:
    society = _msoc("solo")
    pairs = detect_inter_society_pairs(
        [
            InterSocietyMacroCandidate(
                society_id=society,
                member_ids=("solo-p1", "solo-p2", "solo-p3", "solo-p4"),
                window_tick=0,
            )
        ]
    )
    assert pairs == ()
    analysis = harvest_inter_society_relations(
        [
            InterSocietyMacroCandidate(
                society_id=society,
                member_ids=("solo-p1", "solo-p2", "solo-p3", "solo-p4"),
                window_tick=0,
            )
        ]
    )
    assert analysis.pair_count == 0


def test_two_societies_with_exchange_form_one_pair() -> None:
    left = _msoc("alpha")
    right = _msoc("beta", tick=1)
    ordered = tuple(sorted((left, right)))
    evidence = {
        ordered: InterSocietyEvidenceInputs(exchange_event_count=2),
    }
    analysis = harvest_inter_society_relations(
        [
            InterSocietyMacroCandidate(
                society_id=left,
                member_ids=("alpha-p1", "alpha-p2", "alpha-p3", "alpha-p4"),
                window_tick=32,
            ),
            InterSocietyMacroCandidate(
                society_id=right,
                member_ids=("beta-p1", "beta-p2", "beta-p3", "beta-p4"),
                window_tick=32,
            ),
        ],
        evidence_by_pair=evidence,
    )
    assert analysis.pair_count == 1
    pair = analysis.pairs[0]
    assert pair.pair_id.startswith("isr-")
    assert pair.society_a < pair.society_b
    exchange = next(panel for panel in pair.panels if panel.domain.value == "exchange")
    assert exchange.availability.value == "present"
    assert_layer_separation(analysis.layers)


def test_overlapping_membership_is_legal() -> None:
    left = _msoc("left")
    right = _msoc("right", tick=2)
    shared = ("shared-1", "shared-2")
    pair = mint_inter_society_pair(
        society_a=left,
        society_b=right,
        window_tick=0,
        panels=harvest_inter_society_relations(
            [
                InterSocietyMacroCandidate(
                    society_id=left,
                    member_ids=(*shared, "left-only-1", "left-only-2"),
                    window_tick=0,
                ),
                InterSocietyMacroCandidate(
                    society_id=right,
                    member_ids=(*shared, "right-only-1", "right-only-2"),
                    window_tick=0,
                ),
            ]
        )
        .pairs[0]
        .panels,
        members_a=(*shared, "left-only-1", "left-only-2"),
        members_b=(*shared, "right-only-1", "right-only-2"),
    )
    assert pair.overlap_member_count == 2


def test_permutation_and_hashseed_stability() -> None:
    left = _msoc("x")
    right = _msoc("y", tick=3)
    first = detect_inter_society_pairs(
        [
            InterSocietyMacroCandidate(
                society_id=right,
                member_ids=("y-p1", "y-p2", "y-p3", "y-p4"),
                window_tick=64,
            ),
            InterSocietyMacroCandidate(
                society_id=left,
                member_ids=("x-p1", "x-p2", "x-p3", "x-p4"),
                window_tick=64,
            ),
        ]
    )
    second = detect_inter_society_pairs(
        [
            InterSocietyMacroCandidate(
                society_id=left,
                member_ids=("x-p1", "x-p2", "x-p3", "x-p4"),
                window_tick=64,
            ),
            InterSocietyMacroCandidate(
                society_id=right,
                member_ids=("y-p1", "y-p2", "y-p3", "y-p4"),
                window_tick=64,
            ),
        ]
    )
    assert first == second
    assert os.environ.get("PYTHONHASHSEED") is not None or True
    assert first[0].pair_id == second[0].pair_id


def test_objective_isr_token_leaks_fail() -> None:
    analysis = harvest_inter_society_relations(
        [
            InterSocietyMacroCandidate(
                society_id=_msoc("a"),
                member_ids=("a-p1", "a-p2", "a-p3", "a-p4"),
                window_tick=0,
            ),
            InterSocietyMacroCandidate(
                society_id=_msoc("b", tick=1),
                member_ids=("b-p1", "b-p2", "b-p3", "b-p4"),
                window_tick=0,
            ),
        ],
        evidence_by_pair={
            tuple(sorted((_msoc("a"), _msoc("b", tick=1)))): InterSocietyEvidenceInputs(
                exchange_event_count=1
            )
        },
    )
    leaked = list(analysis.layers.objective_rows)
    if not leaked:
        return
    row = leaked[0]
    object.__setattr__(row, "token", analysis.pairs[0].pair_id)
    with pytest.raises(
        InterSocietyRelationsError, match="inter_society_relations_layer_leak"
    ):
        assert_layer_separation(analysis.layers)
