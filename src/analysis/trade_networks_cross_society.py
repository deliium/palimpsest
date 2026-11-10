"""Cross-society analytical exchange views over existing ``msoc-`` candidates.

Societies are read-only contemporaneous candidates. Overlapping membership is
legal, no society is minted, and no partition is created.
"""

from __future__ import annotations

import logging
from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from analysis.inter_society_relations_detection import (
    InterSocietyMacroCandidate,
)
from analysis.trade_networks_contract import (
    NONE_TOKEN,
    TradeCoverage,
    TradeNetworksError,
)
from analysis.trade_networks_events import TradeTransferRow
from analysis.trade_networks_identity import mint_cross_society_pair_token
from analysis.trade_networks_policy import (
    TradeNetworksAnalysisPolicy,
    window_index_for_tick,
)
from analysis.trade_networks_rows import CrossSocietyTradeRow

__all__ = ["CrossSocietyDetection", "detect_cross_society_trade"]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.trade_networks.cross_society")


@dataclass(frozen=True, slots=True)
class CrossSocietyDetection:
    """Bounded cross-society rows with their own coverage and notices."""

    rows: tuple[CrossSocietyTradeRow, ...] = ()
    coverage: TradeCoverage = TradeCoverage.MISSING
    notices: tuple[str, ...] = ()


def _pair_key(left: str, right: str) -> tuple[str, str]:
    return (left, right) if left < right else (right, left)


def detect_cross_society_trade(
    transfers: Sequence[TradeTransferRow],
    candidates: Sequence[InterSocietyMacroCandidate],
    policy: TradeNetworksAnalysisPolicy,
) -> CrossSocietyDetection:
    """Resolve exchange participants to contemporaneous societies per window."""
    if isinstance(candidates, (str, bytes)) or not isinstance(candidates, Sequence):
        raise TradeNetworksError("trade_networks_invalid_input")
    if not candidates:
        return CrossSocietyDetection(
            rows=(), coverage=TradeCoverage.MISSING, notices=()
        )

    membership: dict[int, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    society_members: dict[tuple[int, str], set[str]] = defaultdict(set)
    for candidate in candidates:
        if type(candidate) is not InterSocietyMacroCandidate:
            raise TradeNetworksError("trade_networks_invalid_candidate")
        try:
            window_index = window_index_for_tick(candidate.window_tick, policy)
        except TradeNetworksError as exc:
            raise TradeNetworksError("trade_networks_invalid_candidate") from exc
        if not candidate.member_ids:
            raise TradeNetworksError("trade_networks_invalid_candidate")
        for member in candidate.member_ids:
            membership[window_index][member].add(candidate.society_id)
            society_members[(window_index, candidate.society_id)].add(member)

    notices: set[str] = set()
    for window_index, members in membership.items():
        if any(len(societies) > 1 for societies in members.values()):
            notices.add("trade_networks_overlap_membership")
            _LOG.debug(
                "trade_networks_overlap_membership window_index=%s", window_index
            )

    pair_transfers: Counter[tuple[int, str, str]] = Counter()
    pair_flows: dict[tuple[int, str, str], Counter[str]] = defaultdict(Counter)
    pair_a_to_b: Counter[tuple[int, str, str]] = Counter()
    pair_b_to_a: Counter[tuple[int, str, str]] = Counter()
    pair_members: dict[tuple[int, str, str], tuple[frozenset[str], frozenset[str]]] = {}
    society_locations: dict[tuple[int, str], Counter[str]] = defaultdict(Counter)
    unmapped = False

    for row in transfers:
        window_index = window_index_for_tick(row.tick, policy)
        window_members = membership.get(window_index)
        if not window_members:
            unmapped = True
            continue
        source_societies = window_members.get(row.actor_token, set())
        destination_societies = window_members.get(row.counterparty_token, set())
        if not source_societies or not destination_societies:
            unmapped = True
        for society in source_societies | destination_societies:
            if row.location_token != NONE_TOKEN:
                society_locations[(window_index, society)][row.location_token] += 1
        unique_pairs: dict[tuple[str, str], tuple[bool, bool]] = {}
        for source in source_societies:
            for destination in destination_societies:
                if source == destination:
                    continue
                pair = _pair_key(source, destination)
                forward, backward = unique_pairs.get(pair, (False, False))
                if source < destination:
                    forward = True
                else:
                    backward = True
                unique_pairs[pair] = (forward, backward)
        for (society_a, society_b), (forward, backward) in unique_pairs.items():
            key = (window_index, society_a, society_b)
            pair_transfers[key] += 1
            pair_flows[key][row.flow_class.value] += 1
            pair_a_to_b[key] += 1 if forward else 0
            pair_b_to_a[key] += 1 if backward else 0
            pair_members[key] = (
                frozenset(society_members[(window_index, society_a)]),
                frozenset(society_members[(window_index, society_b)]),
            )

    rows: list[CrossSocietyTradeRow] = []
    for (window_index, society_a, society_b), transfer_count in pair_transfers.items():
        members_a, members_b = pair_members[(window_index, society_a, society_b)]
        coverage = TradeCoverage.PARTIAL if unmapped else TradeCoverage.COMPLETE
        rows.append(
            CrossSocietyTradeRow(
                pair_token=mint_cross_society_pair_token(society_a, society_b),
                window_index=window_index,
                society_a=society_a,
                society_b=society_b,
                society_a_location_id=_dominant_location(
                    society_locations[(window_index, society_a)]
                ),
                society_b_location_id=_dominant_location(
                    society_locations[(window_index, society_b)]
                ),
                overlap_member_count=len(members_a & members_b),
                flow_counts=tuple(
                    sorted(
                        (key, int(value))
                        for key, value in pair_flows[
                            (window_index, society_a, society_b)
                        ].items()
                    )
                ),
                transfer_count=int(transfer_count),
                society_a_to_b_count=int(
                    pair_a_to_b[(window_index, society_a, society_b)]
                ),
                society_b_to_a_count=int(
                    pair_b_to_a[(window_index, society_a, society_b)]
                ),
                coverage=coverage,
            )
        )
    rows.sort(key=lambda row: (row.window_index, row.pair_token))
    if len(rows) > policy.max_cross_society_pairs:
        rows = rows[: policy.max_cross_society_pairs]
        notices.add("trade_networks_cross_society_truncated")
        unmapped = True
        _LOG.warning(
            "trade_networks_cross_society_truncated retained=%s cap=%s",
            len(rows),
            policy.max_cross_society_pairs,
        )
        rows = [
            CrossSocietyTradeRow(
                pair_token=row.pair_token,
                window_index=row.window_index,
                society_a=row.society_a,
                society_b=row.society_b,
                society_a_location_id=row.society_a_location_id,
                society_b_location_id=row.society_b_location_id,
                overlap_member_count=row.overlap_member_count,
                flow_counts=row.flow_counts,
                transfer_count=row.transfer_count,
                society_a_to_b_count=row.society_a_to_b_count,
                society_b_to_a_count=row.society_b_to_a_count,
                coverage=TradeCoverage.PARTIAL,
            )
            for row in rows
        ]
    coverage = TradeCoverage.PARTIAL if unmapped else TradeCoverage.COMPLETE
    _LOG.debug(
        "trade_networks_cross_society pairs=%s mapped=%s coverage=%s",
        len(rows),
        not unmapped,
        coverage.value,
    )
    return CrossSocietyDetection(
        rows=tuple(rows),
        coverage=coverage,
        notices=tuple(sorted(notices)),
    )


def _dominant_location(counts: Counter[str]) -> str:
    if not counts:
        return NONE_TOKEN
    return min(counts.items(), key=lambda item: (-item[1], item[0]))[0]
