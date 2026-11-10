# mypy: ignore-errors
"""Deterministic trade identities and forward-only network lineage."""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from analysis.trade_networks_identity import (
    group_networks_by_window,
    link_trade_network_lineage,
    mint_corridor_token,
    mint_cross_society_pair_token,
    mint_network_token,
)
from analysis.trade_networks_policy import default_trade_networks_analysis_policy
from analysis.trade_networks_rows import TradeNetworkRow

POLICY = default_trade_networks_analysis_policy()


def _network(tokens: tuple[str, ...], window: int = 0) -> TradeNetworkRow:
    locations = sorted(
        {
            token
            for corridor in tokens
            for token in (f"loc-{corridor}", f"loc-{corridor}-b")
        }
    )
    return TradeNetworkRow(
        network_token=mint_network_token(tokens),
        window_index=window,
        corridor_tokens=tuple(sorted(tokens)),
        location_tokens=tuple(locations),
        flow_counts=(("food", len(tokens)),),
        transfer_count=len(tokens),
    )


def test_corridor_and_network_ids_are_stable() -> None:
    first = mint_corridor_token("loc-a", "loc-b")
    second = mint_corridor_token("loc-a", "loc-b")
    assert first == second
    assert first.startswith("trd-cor-")
    assert mint_network_token(("b", "a")) == mint_network_token(("a", "b", "a"))
    assert mint_cross_society_pair_token("msoc-b", "msoc-a") == (
        mint_cross_society_pair_token("msoc-a", "msoc-b")
    )


def test_reverse_corridors_mint_distinct_tokens() -> None:
    assert mint_corridor_token("loc-a", "loc-b") != mint_corridor_token(
        "loc-b", "loc-a"
    )


def test_identical_corridor_sets_are_continued() -> None:
    previous = (_network(("c1", "c2"), 0),)
    current = (_network(("c1", "c2"), 1),)
    edges = link_trade_network_lineage(previous, current, POLICY)
    assert len(edges) == 1
    assert edges[0].relation == "continued"
    assert edges[0].sustained is True
    assert edges[0].rerouted is False


def test_changed_corridor_set_is_transformed_and_rerouted() -> None:
    previous = (_network(("c1", "c2"), 0),)
    current = (_network(("c1", "c3"), 1),)
    edges = link_trade_network_lineage(previous, current, POLICY)
    assert edges[0].relation == "transformed"
    assert edges[0].rerouted is True
    assert edges[0].sustained is True


def test_two_successors_are_split() -> None:
    previous = (_network(("c1", "c2"), 0),)
    current = (_network(("c1",), 1), _network(("c2",), 1))
    edges = link_trade_network_lineage(previous, current, POLICY)
    assert {edge.relation for edge in edges} == {"split"}
    assert all(edge.sustained is False for edge in edges)


def test_two_predecessors_are_merge() -> None:
    previous = (_network(("c1",), 0), _network(("c2",), 0))
    current = (_network(("c1", "c2"), 1),)
    edges = link_trade_network_lineage(previous, current, POLICY)
    assert {edge.relation for edge in edges} == {"merge"}


def test_absent_successor_is_dissolved() -> None:
    edges = link_trade_network_lineage((_network(("c1",), 0),), (), POLICY)
    assert len(edges) == 1
    assert edges[0].relation == "dissolved"
    assert edges[0].network_token == "none"
    assert edges[0].sustained is False


def test_absent_predecessor_is_emerged() -> None:
    edges = link_trade_network_lineage((), (_network(("c1",), 1),), POLICY)
    assert len(edges) == 1
    assert edges[0].relation == "emerged"
    assert edges[0].previous_token == "none"


def test_empty_window_forces_dissolved_then_emerged() -> None:
    previous = (_network(("c1",), 0),)
    current = (_network(("c1",), 2),)
    first = link_trade_network_lineage(previous, (), POLICY)
    second = link_trade_network_lineage((), current, POLICY)
    assert [edge.relation for edge in first + second] == ["dissolved", "emerged"]


def test_continued_and_transformed_are_sustained() -> None:
    continued = link_trade_network_lineage(
        (_network(("c1", "c2"), 0),), (_network(("c1", "c2"), 1),), POLICY
    )
    transformed = link_trade_network_lineage(
        (_network(("c1", "c2"), 0),), (_network(("c1", "c3"), 1),), POLICY
    )
    assert continued[0].sustained and transformed[0].sustained


def test_group_networks_materializes_empty_windows() -> None:
    grouped = group_networks_by_window(
        (_network(("c1",), 0), _network(("c2",), 2)), first_window=0, last_window=2
    )
    assert [window for window, _ in grouped] == [0, 1, 2]
    assert grouped[1][1] == ()


token_strategy = st.text(alphabet="abcdef", min_size=1, max_size=4)


@given(tokens=st.lists(token_strategy, min_size=1, max_size=4, unique=True))
def test_lineage_is_forward_only(tokens) -> None:
    previous = (
        TradeNetworkRow(
            network_token=mint_network_token(tokens),
            window_index=0,
            corridor_tokens=tuple(sorted(tokens)),
            location_tokens=("loc-a", "loc-b"),
            flow_counts=(("food", len(tokens)),),
            transfer_count=len(tokens),
        ),
    )
    edges = link_trade_network_lineage(previous, (), POLICY)
    assert all(edge.last_tick >= edge.first_tick for edge in edges)
    assert all(
        edge.relation
        in {"emerged", "continued", "transformed", "split", "merge", "dissolved"}
        for edge in edges
    )
