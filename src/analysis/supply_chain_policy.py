"""Locked detached-analysis policy for multi-stage supply chains."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Final

from analysis.supply_chain_contract import SupplyChainError

__all__ = [
    "BOTTLENECK_DEMAND_MIN",
    "BOTTLENECK_MIN_EVENTS",
    "BOTTLENECK_SHARE_MILLI",
    "BOTTLENECK_SHORTFALL_MILLI",
    "CHAIN_OVERLAP_MILLI",
    "DEFAULT_SUPPLY_WINDOW_TICKS",
    "LOW_SKILL_LEVEL",
    "MAX_CHAIN_DEPTH",
    "SupplyChainAnalysisPolicy",
    "default_supply_chain_analysis_policy",
    "window_bounds",
    "window_index_for_tick",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.supply_chain.policy")

DEFAULT_SUPPLY_WINDOW_TICKS: Final[int] = 32
BOTTLENECK_MIN_EVENTS: Final[int] = 3
BOTTLENECK_SHARE_MILLI: Final[int] = 750
BOTTLENECK_SHORTFALL_MILLI: Final[int] = 250
BOTTLENECK_DEMAND_MIN: Final[int] = 3
CHAIN_OVERLAP_MILLI: Final[int] = 500
LOW_SKILL_LEVEL: Final[float] = 0.125
MAX_CHAIN_DEPTH: Final[int] = 8

_INT_RANGES: Final[dict[str, tuple[int, int]]] = {
    "window_ticks": (8, 256),
    "max_windows": (1, 512),
    "max_evidence_rows": (1, 200_000),
    "max_stages": (1, 4_096),
    "max_edges": (1, 16_384),
    "max_chains": (1, 4_096),
    "max_bottlenecks": (1, 4_096),
    "max_locations": (1, 4_096),
    "max_organizations": (1, 2_048),
    "max_lineage_edges": (1, 16_384),
}


@dataclass(frozen=True, slots=True)
class SupplyChainAnalysisPolicy:
    """Validated detached supply-chain analysis policy."""

    window_ticks: int = DEFAULT_SUPPLY_WINDOW_TICKS
    max_windows: int = 512
    max_evidence_rows: int = 200_000
    max_stages: int = 4_096
    max_edges: int = 16_384
    max_chains: int = 4_096
    max_bottlenecks: int = 4_096
    max_locations: int = 4_096
    max_organizations: int = 2_048
    max_lineage_edges: int = 16_384

    def __post_init__(self) -> None:
        for name, (minimum, maximum) in _INT_RANGES.items():
            value = getattr(self, name)
            if isinstance(value, bool) or type(value) is not int:
                _invalid(name)
            if value < minimum or value > maximum:
                _invalid(name)
        _LOG.debug(
            "supply_chain_policy_resolved window_ticks=%s max_edges=%s",
            self.window_ticks,
            self.max_edges,
        )


def _invalid(field: str) -> None:
    _LOG.warning(
        "supply_chain_policy_invalid field=%s code=supply_chain_invalid_policy",
        field,
    )
    raise SupplyChainError("supply_chain_invalid_policy")


def default_supply_chain_analysis_policy() -> SupplyChainAnalysisPolicy:
    return SupplyChainAnalysisPolicy()


def window_index_for_tick(
    tick: int, policy: SupplyChainAnalysisPolicy | None = None
) -> int:
    if isinstance(tick, bool) or type(tick) is not int or tick < 0:
        raise SupplyChainError("supply_chain_invalid_window")
    window_ticks = (
        DEFAULT_SUPPLY_WINDOW_TICKS if policy is None else policy.window_ticks
    )
    index = tick // window_ticks
    if policy is not None and index >= policy.max_windows:
        raise SupplyChainError("supply_chain_invalid_window")
    return index


def window_bounds(
    window_index: int, policy: SupplyChainAnalysisPolicy
) -> tuple[int, int]:
    if (
        isinstance(window_index, bool)
        or type(window_index) is not int
        or window_index < 0
        or window_index >= policy.max_windows
    ):
        raise SupplyChainError("supply_chain_invalid_window")
    start = window_index * policy.window_ticks
    return start, start + policy.window_ticks
