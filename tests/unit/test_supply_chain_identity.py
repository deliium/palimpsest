# mypy: ignore-errors

"""Content-addressed supply identity and forward-only lineage."""

from __future__ import annotations

import pytest

from analysis.supply_chain_contract import SupplyCoverage
from analysis.supply_chain_graph import SupplyChainPath
from analysis.supply_chain_identity import (
    group_chains_by_window,
    link_supply_chain_lineage,
    mint_chain_token,
    mint_edge_token,
    mint_stage_token,
)
from analysis.supply_chain_policy import SupplyChainAnalysisPolicy

pytestmark = pytest.mark.unit


def _chain(
    window: int, edges: tuple[str, ...], *, token: str | None = None
) -> SupplyChainPath:
    return SupplyChainPath(
        chain_token=token or mint_chain_token(window, edges),
        window_index=window,
        stage_tokens=("a", "b"),
        edge_tokens=edges,
        depth=len(edges) + 1,
        location_tokens=(),
        organization_tokens=(),
        completed_count=1,
        coverage=SupplyCoverage.COMPLETE,
    )


def test_tokens_are_deterministic() -> None:
    assert mint_stage_token(0, "mill_grain") == mint_stage_token(0, "mill_grain")
    assert mint_edge_token(0, "item_to_item", "a", "b") == mint_edge_token(
        0, "item_to_item", "a", "b"
    )
    assert mint_chain_token(0, ("e1", "e2")) == mint_chain_token(0, ("e1", "e2"))
    assert mint_chain_token(0, ("e1", "e2")).startswith("sc-chain-")


def test_group_includes_empty_windows() -> None:
    grouped = group_chains_by_window([_chain(0, ("e1",)), _chain(2, ("e2",))])
    assert sorted(grouped) == [0, 1, 2]
    assert grouped[1] == ()


def test_equal_edges_continue() -> None:
    rows = link_supply_chain_lineage(
        [_chain(0, ("e1",)), _chain(1, ("e1",))],
        policy=SupplyChainAnalysisPolicy(),
    )
    assert any(row.status == "continued" for row in rows)


def test_changed_edge_transforms() -> None:
    rows = link_supply_chain_lineage(
        [_chain(0, ("e1", "e2")), _chain(1, ("e1", "e3"))],
        policy=SupplyChainAnalysisPolicy(),
    )
    assert any(row.status == "transformed" for row in rows)


def test_split() -> None:
    previous = _chain(0, ("e1", "e2"), token="sc-chain-prev")
    left = _chain(1, ("e1",), token="sc-chain-left")
    right = _chain(1, ("e2",), token="sc-chain-right")
    rows = link_supply_chain_lineage(
        [previous, left, right], policy=SupplyChainAnalysisPolicy()
    )
    assert any(row.status == "split" for row in rows)


def test_merge() -> None:
    left = _chain(0, ("e1",), token="sc-chain-left")
    right = _chain(0, ("e2",), token="sc-chain-right")
    current = _chain(1, ("e1", "e2"), token="sc-chain-current")
    rows = link_supply_chain_lineage(
        [left, right, current], policy=SupplyChainAnalysisPolicy()
    )
    assert any(row.status == "merge" for row in rows)


def test_dissolve() -> None:
    rows = link_supply_chain_lineage(
        [_chain(0, ("e1",)), _chain(1, ("e2",))],
        policy=SupplyChainAnalysisPolicy(),
    )
    assert any(row.status == "dissolved" for row in rows)


def test_emerge() -> None:
    rows = link_supply_chain_lineage(
        [_chain(0, ("e1",)), _chain(1, ("e2",))],
        policy=SupplyChainAnalysisPolicy(),
    )
    assert any(row.status == "emerged" for row in rows)


def test_empty_window_breaks_continuity() -> None:
    rows = link_supply_chain_lineage(
        [_chain(0, ("e1",)), _chain(2, ("e1",))],
        policy=SupplyChainAnalysisPolicy(),
    )
    statuses = {row.status for row in rows}
    assert "continued" not in statuses
    assert {"dissolved", "emerged"} <= statuses


def test_parents_are_immutable() -> None:
    rows = link_supply_chain_lineage(
        [_chain(0, ("e1",)), _chain(1, ("e1",))],
        policy=SupplyChainAnalysisPolicy(),
    )
    assert all(type(row.predecessor_tokens) is tuple for row in rows)
    assert all(row.window_index <= 1 for row in rows)


def test_overlap_is_floor_milli() -> None:
    rows = link_supply_chain_lineage(
        [_chain(0, ("e1", "e2", "e3")), _chain(1, ("e1",))],
        policy=SupplyChainAnalysisPolicy(),
    )
    linked = [row for row in rows if row.overlap_milli]
    assert linked
    assert linked[0].overlap_milli == 1000


def test_cap_sets_notice() -> None:
    rows = link_supply_chain_lineage(
        [_chain(0, ("e1",)), _chain(1, ("e1",)), _chain(2, ("e1",))],
        policy=SupplyChainAnalysisPolicy(max_lineage_edges=1),
    )
    assert len(rows) == 1
