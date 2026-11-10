# mypy: ignore-errors
"""Cross-society analytical exchange rows over existing ``msoc-`` candidates."""

from __future__ import annotations

import pytest

from analysis.inter_society_relations_detection import (
    InterSocietyMacroCandidate,
)
from analysis.trade_networks_contract import TradeCoverage, TradeFlowClass
from analysis.trade_networks_cross_society import detect_cross_society_trade
from analysis.trade_networks_events import TradeTransferRow
from analysis.trade_networks_policy import default_trade_networks_analysis_policy

POLICY = default_trade_networks_analysis_policy()

SOC_A = "msoc-aaaaaaaaaaaaaaaa"
SOC_B = "msoc-bbbbbbbbbbbbbbbb"
SOC_C = "msoc-cccccccccccccccc"
SOC_D = "msoc-dddddddddddddddd"


def _candidate(society: str, members: tuple[str, ...], tick: int = 0):
    return InterSocietyMacroCandidate(
        society_id=society, member_ids=members, window_tick=tick
    )


def _transfer(
    *,
    actor: str,
    counterparty: str,
    tick: int = 0,
    location: str = "loc-a",
    previous: str = "loc-0",
    flow_class: TradeFlowClass = TradeFlowClass.FOOD,
):
    return TradeTransferRow(
        entity_kind="item",
        entity_token=f"item-{actor}-{counterparty}-{tick}",
        flow_class=flow_class,
        tick=tick,
        event_token=f"evt-{actor}-{counterparty}-{tick}",
        location_token=location,
        previous_location_token=previous,
        origin_location_token=previous,
        actor_token=actor,
        counterparty_token=counterparty,
        direction="give",
        source_kind="exchange",
        consumed=False,
    )


def test_no_candidates_yields_missing_coverage() -> None:
    result = detect_cross_society_trade(
        (_transfer(actor="a", counterparty="c"),), (), POLICY
    )
    assert result.rows == ()
    assert result.coverage is TradeCoverage.MISSING


def test_two_societies_get_one_canonical_pair() -> None:
    candidates = (_candidate(SOC_A, ("a",)), _candidate(SOC_B, ("c",)))
    result = detect_cross_society_trade(
        (_transfer(actor="a", counterparty="c"),), candidates, POLICY
    )
    assert len(result.rows) == 1
    assert (result.rows[0].society_a, result.rows[0].society_b) == (SOC_A, SOC_B)
    assert result.coverage is TradeCoverage.COMPLETE


def test_direction_counts_follow_exchange_bundle_side() -> None:
    candidates = (_candidate(SOC_A, ("a",)), _candidate(SOC_B, ("c",)))
    transfers = (
        _transfer(actor="a", counterparty="c"),
        _transfer(actor="c", counterparty="a", tick=1),
    )
    result = detect_cross_society_trade(transfers, candidates, POLICY)
    row = result.rows[0]
    assert row.society_a_to_b_count == 1
    assert row.society_b_to_a_count == 1
    assert row.transfer_count == 2


def test_overlapping_candidates_are_legal_and_not_partitioned() -> None:
    candidates = (
        _candidate(SOC_A, ("a", "b")),
        _candidate(SOC_B, ("b", "c")),
    )
    result = detect_cross_society_trade(
        (_transfer(actor="a", counterparty="c"),), candidates, POLICY
    )
    assert len(result.rows) == 1
    assert result.rows[0].overlap_member_count == 1
    assert "trade_networks_overlap_membership" in result.notices
    assert result.coverage is TradeCoverage.COMPLETE


def test_unmapped_participant_marks_partial() -> None:
    candidates = (_candidate(SOC_A, ("a",)), _candidate(SOC_B, ("c",)))
    result = detect_cross_society_trade(
        (
            _transfer(actor="a", counterparty="c"),
            _transfer(actor="a", counterparty="unknown", tick=1),
        ),
        candidates,
        POLICY,
    )
    assert result.coverage is TradeCoverage.PARTIAL


def test_dominant_location_anchor_is_deterministic() -> None:
    candidates = (_candidate(SOC_A, ("a",)), _candidate(SOC_B, ("c",)))
    transfers = (
        _transfer(actor="a", counterparty="c", location="loc-b", tick=0),
        _transfer(actor="a", counterparty="c", location="loc-a", tick=1),
    )
    result = detect_cross_society_trade(transfers, candidates, POLICY)
    row = result.rows[0]
    assert row.society_a_location_id == "loc-a"
    assert row.society_b_location_id == "loc-a"


def test_missing_anchor_uses_none_token() -> None:
    candidates = (_candidate(SOC_A, ("a",)), _candidate(SOC_B, ("c",)))
    result = detect_cross_society_trade(
        (
            _transfer(
                actor="a",
                counterparty="c",
                location="none",
                previous="none",
            ),
        ),
        candidates,
        POLICY,
    )
    assert result.rows[0].society_a_location_id == "none"
    assert result.rows[0].society_b_location_id == "none"


def test_overlap_member_count_is_retained() -> None:
    candidates = (
        _candidate(SOC_A, ("a", "shared")),
        _candidate(SOC_B, ("shared", "c")),
    )
    result = detect_cross_society_trade(
        (_transfer(actor="a", counterparty="c"),), candidates, POLICY
    )
    assert result.rows[0].overlap_member_count == 1


def test_pair_cap_truncates_deterministically() -> None:
    candidates = (
        _candidate(SOC_A, ("a",)),
        _candidate(SOC_B, ("b",)),
        _candidate(SOC_C, ("c",)),
        _candidate(SOC_D, ("d",)),
    )
    transfers = (
        _transfer(actor="a", counterparty="b"),
        _transfer(actor="c", counterparty="d", tick=1),
    )
    policy = type(POLICY)(max_cross_society_pairs=1)
    result = detect_cross_society_trade(transfers, candidates, policy)
    assert len(result.rows) == 1
    assert result.coverage is TradeCoverage.PARTIAL
    assert "trade_networks_cross_society_truncated" in result.notices


def test_invalid_candidate_window_is_rejected() -> None:
    candidates = (_candidate(SOC_A, ("a",), tick=32 * 5_000),)
    with pytest.raises(ValueError):
        detect_cross_society_trade((), candidates, POLICY)
