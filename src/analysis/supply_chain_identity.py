"""Content-addressed supply identities and forward-only lineage."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from analysis.supply_chain_contract import (
    SUPPLY_CHAIN_PREFIX,
    SUPPLY_EDGE_PREFIX,
    SUPPLY_STAGE_PREFIX,
    SupplyChainError,
    SupplyCoverage,
    analysis_supply_token,
)
from analysis.supply_chain_graph import SupplyChainPath
from analysis.supply_chain_policy import (
    CHAIN_OVERLAP_MILLI,
    SupplyChainAnalysisPolicy,
)

__all__ = [
    "SupplyChainLineageRow",
    "group_chains_by_window",
    "link_supply_chain_lineage",
    "mint_chain_token",
    "mint_edge_token",
    "mint_stage_token",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.supply_chain.identity")

_LINEAGE_STATUSES: Final[frozenset[str]] = frozenset(
    {"emerged", "continued", "transformed", "split", "merge", "dissolved"}
)


@dataclass(frozen=True, slots=True)
class SupplyChainLineageRow:
    chain_token: str
    window_index: int
    status: str
    predecessor_tokens: tuple[str, ...]
    successor_tokens: tuple[str, ...]
    shared_edge_count: int
    overlap_milli: int
    coverage: SupplyCoverage

    def __post_init__(self) -> None:
        if self.status not in _LINEAGE_STATUSES:
            raise SupplyChainError("supply_chain_invalid_policy")
        for name in (
            "window_index",
            "shared_edge_count",
            "overlap_milli",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or type(value) is not int or value < 0:
                raise SupplyChainError("supply_chain_invalid_policy")


def mint_stage_token(window_index: int, recipe_id: str) -> str:
    return analysis_supply_token(SUPPLY_STAGE_PREFIX, f"{window_index}\x1f{recipe_id}")


def mint_edge_token(
    window_index: int, edge_kind: str, from_token: str, to_token: str
) -> str:
    return analysis_supply_token(
        SUPPLY_EDGE_PREFIX,
        f"{window_index}\x1f{edge_kind}\x1f{from_token}\x1f{to_token}",
    )


def mint_chain_token(window_index: int, edge_tokens: Sequence[str]) -> str:
    payload = f"{window_index}\x1f" + "|".join(edge_tokens)
    return analysis_supply_token(SUPPLY_CHAIN_PREFIX, payload)


def group_chains_by_window(
    chains: Sequence[SupplyChainPath],
) -> dict[int, tuple[SupplyChainPath, ...]]:
    """Return every window from first to last observed, including empty gaps."""
    if isinstance(chains, (str, bytes)) or not isinstance(chains, Sequence):
        raise SupplyChainError("supply_chain_invalid_policy")
    grouped: dict[int, list[SupplyChainPath]] = {}
    for chain in chains:
        if type(chain) is not SupplyChainPath:
            raise SupplyChainError("supply_chain_invalid_policy")
        grouped.setdefault(chain.window_index, []).append(chain)
    if not grouped:
        return {}
    first, last = min(grouped), max(grouped)
    result: dict[int, tuple[SupplyChainPath, ...]] = {}
    for window in range(first, last + 1):
        rows = grouped.get(window, [])
        result[window] = tuple(
            sorted(rows, key=lambda chain: (chain.chain_token, chain.depth))
        )
    return result


def _edge_set(chain: SupplyChainPath) -> set[str]:
    return set(chain.edge_tokens)


def _overlap(previous: SupplyChainPath, current: SupplyChainPath) -> int:
    shared = len(_edge_set(previous) & _edge_set(current))
    denominator = max(min(len(previous.edge_tokens), len(current.edge_tokens)), 1)
    return shared * 1000 // denominator


def link_supply_chain_lineage(
    chains: Sequence[SupplyChainPath],
    *,
    policy: SupplyChainAnalysisPolicy,
    notices: set[str] | None = None,
) -> tuple[SupplyChainLineageRow, ...]:
    """Link consecutive windows only, including explicit empty-window gaps."""
    grouped = group_chains_by_window(chains)
    if not grouped:
        return ()
    windows = sorted(grouped)
    rows: list[SupplyChainLineageRow] = []
    previous_window_chains: tuple[SupplyChainPath, ...] = ()
    gap = False
    for window in windows:
        current_chains = grouped[window]
        if not current_chains:
            for previous in previous_window_chains:
                rows.append(
                    SupplyChainLineageRow(
                        chain_token=previous.chain_token,
                        window_index=window,
                        status="dissolved",
                        predecessor_tokens=(),
                        successor_tokens=(),
                        shared_edge_count=0,
                        overlap_milli=0,
                        coverage=SupplyCoverage.PARTIAL,
                    )
                )
            previous_window_chains = ()
            gap = True
            continue
        links: dict[str, list[SupplyChainPath]] = {}
        predecessors: dict[str, list[SupplyChainPath]] = {}
        for previous in previous_window_chains:
            for current in current_chains:
                overlap = _overlap(previous, current)
                if overlap >= CHAIN_OVERLAP_MILLI:
                    links.setdefault(previous.chain_token, []).append(current)
                    predecessors.setdefault(current.chain_token, []).append(previous)
        for previous in previous_window_chains:
            successors = links.get(previous.chain_token, [])
            if len(successors) > 1:
                rows.append(
                    SupplyChainLineageRow(
                        chain_token=previous.chain_token,
                        window_index=window,
                        status="split",
                        predecessor_tokens=(),
                        successor_tokens=tuple(
                            sorted(item.chain_token for item in successors)
                        ),
                        shared_edge_count=max(
                            len(_edge_set(previous) & _edge_set(item))
                            for item in successors
                        ),
                        overlap_milli=max(
                            _overlap(previous, item) for item in successors
                        ),
                        coverage=SupplyCoverage.PARTIAL,
                    )
                )
            elif not successors:
                rows.append(
                    SupplyChainLineageRow(
                        chain_token=previous.chain_token,
                        window_index=window,
                        status="dissolved",
                        predecessor_tokens=(),
                        successor_tokens=(),
                        shared_edge_count=0,
                        overlap_milli=0,
                        coverage=SupplyCoverage.PARTIAL,
                    )
                )
        for current in current_chains:
            preds = predecessors.get(current.chain_token, [])
            if not preds or gap:
                status = "emerged"
            elif len(preds) > 1:
                status = "merge"
            elif _edge_set(preds[0]) == _edge_set(current):
                status = "continued"
            else:
                status = "transformed"
            shared = max(
                (len(_edge_set(item) & _edge_set(current)) for item in preds),
                default=0,
            )
            overlap = max((_overlap(item, current) for item in preds), default=0)
            rows.append(
                SupplyChainLineageRow(
                    chain_token=current.chain_token,
                    window_index=window,
                    status=status,
                    predecessor_tokens=tuple(
                        sorted(item.chain_token for item in preds)
                    ),
                    successor_tokens=(),
                    shared_edge_count=shared,
                    overlap_milli=overlap,
                    coverage=(
                        SupplyCoverage.PARTIAL
                        if gap or len(preds) > 1
                        else SupplyCoverage.COMPLETE
                    ),
                )
            )
        previous_window_chains = current_chains
        gap = False
    rows.sort(key=lambda row: (row.window_index, row.chain_token, row.status))
    if len(rows) > policy.max_lineage_edges:
        rows = rows[: policy.max_lineage_edges]
        if notices is not None:
            notices.add("lineage_truncated")
        _LOG.warning("supply_chain_lineage_truncated kept=%s", len(rows))
    _LOG.debug(
        "supply_chain_lineage_linked status=%s count=%s",
        "multi" if rows else "none",
        len(rows),
    )
    return tuple(rows)
