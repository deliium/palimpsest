"""Deterministic objective venue, gathering, market, and participation detection.

No price, allocation, quota, score, ranking, severity, or recommendation is
computed. Venue status is objective and never depends on owner expectations.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import replace
from typing import Final

from analysis.market_institutions_contract import (
    MARKET_CANDIDATE_PREFIX,
    MARKET_FORBIDDEN_KEYS,
    MARKET_LAYER_FORBIDDEN_PREFIXES,
    MARKET_VENUE_PREFIX,
    MarketCoverage,
    MarketGatheringStatus,
    MarketInstitutionsError,
    MarketLayer,
    MarketVenueStatus,
    market_candidate_token,
    market_venue_token,
)
from analysis.market_institutions_events import (
    MarketAttemptRow,
    MarketEvidenceHarvest,
    MarketExchangeRow,
)
from analysis.market_institutions_policy import (
    MarketInstitutionsAnalysisPolicy,
    default_market_institutions_analysis_policy,
)
from analysis.market_institutions_rows import (
    MarketCandidateRow,
    MarketGatheringRow,
    MarketParticipationRow,
    MarketVenueRow,
)

__all__ = [
    "assert_market_layer_separation",
    "detect_gatherings",
    "detect_market_candidates",
    "detect_participation",
    "detect_venues",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "analysis.market_institutions.detection"
)


def _policy(
    policy: MarketInstitutionsAnalysisPolicy | None,
) -> MarketInstitutionsAnalysisPolicy:
    active = (
        default_market_institutions_analysis_policy()
        if policy is None
        else policy
    )
    if type(active) is not MarketInstitutionsAnalysisPolicy:
        raise MarketInstitutionsError("market_institutions_invalid_policy")
    return active


def _require_harvest(harvest: object) -> MarketEvidenceHarvest:
    if type(harvest) is not MarketEvidenceHarvest:
        raise MarketInstitutionsError("market_institutions_invalid_input")
    return harvest


def detect_gatherings(
    harvest: MarketEvidenceHarvest,
    *,
    policy: MarketInstitutionsAnalysisPolicy | None = None,
) -> tuple[MarketGatheringRow, ...]:
    """Group evidence by window and location and qualify gatherings."""

    active = _policy(policy)
    harvest = _require_harvest(harvest)
    exchanges: dict[tuple[int, str], list[MarketExchangeRow]] = defaultdict(list)
    attempts: dict[tuple[int, str], list[MarketAttemptRow]] = defaultdict(list)
    for exchange_row in harvest.exchanges:
        exchanges[(exchange_row.window_index, exchange_row.location_token)].append(
            exchange_row
        )
    for attempt_row in harvest.attempts:
        attempts[(attempt_row.window_index, attempt_row.location_token)].append(
            attempt_row
        )

    rows: list[MarketGatheringRow] = []
    for key in sorted(set(exchanges) | set(attempts)):
        window_index, location_token = key
        venue_id = market_venue_token(location_token)
        exchange_rows = exchanges.get(key, [])
        attempt_rows = attempts.get(key, [])
        parties: set[str] = set()
        actors: set[str] = set()
        for exchange_row in exchange_rows:
            parties.update(exchange_row.party_tokens)
            actors.add(exchange_row.actor_token)
        exchange_count = len(exchange_rows)
        status = (
            MarketGatheringStatus.GATHERING
            if exchange_count >= active.min_gathering_exchanges
            and len(parties) >= active.min_gathering_participants
            else MarketGatheringStatus.BELOW_THRESHOLD
        )
        coverage = (
            MarketCoverage.PARTIAL
            if harvest.coverage is MarketCoverage.PARTIAL
            else MarketCoverage.COMPLETE
        )
        rows.append(
            MarketGatheringRow(
                venue_id=venue_id,
                window_index=window_index,
                location_token=location_token,
                exchange_count=exchange_count,
                proposal_count=sum(
                    1
                    for attempt_row in attempt_rows
                    if attempt_row.attempt_kind.value in {"offer", "counteroffer"}
                ),
                withdrawn_count=sum(
                    1
                    for attempt_row in attempt_rows
                    if attempt_row.attempt_kind.value == "withdraw"
                ),
                distinct_party_count=len(parties),
                distinct_actor_count=len(actors),
                status=status,
                coverage=coverage,
            )
        )
    rows.sort(key=lambda row: (row.window_index, row.venue_id))
    if len(rows) > active.max_gathering_rows:
        rows = rows[: active.max_gathering_rows]
        rows = [replace(row, coverage=MarketCoverage.PARTIAL) for row in rows]
        _LOG.warning(
            "market_gatherings_truncated rows=%s cap=%s",
            len(rows),
            active.max_gathering_rows,
        )
    return tuple(rows)


def _participants_by_venue_window(
    harvest: MarketEvidenceHarvest,
) -> dict[tuple[int, str], set[str]]:
    participants: dict[tuple[int, str], set[str]] = defaultdict(set)
    for row in harvest.exchanges:
        key = (row.window_index, market_venue_token(row.location_token))
        participants[key].update(row.party_tokens)
    return participants


def detect_venues(
    harvest: MarketEvidenceHarvest,
    *,
    policy: MarketInstitutionsAnalysisPolicy | None = None,
    window_end: int,
) -> tuple[MarketVenueRow, ...]:
    """Emit one row per active venue window plus at most one dormant row."""

    active = _policy(policy)
    harvest = _require_harvest(harvest)
    if (
        isinstance(window_end, bool)
        or type(window_end) is not int
        or window_end < 0
    ):
        raise MarketInstitutionsError("market_institutions_invalid_window")
    gatherings = detect_gatherings(harvest, policy=active)
    participants = _participants_by_venue_window(harvest)
    by_venue: dict[str, list[MarketGatheringRow]] = defaultdict(list)
    for row in gatherings:
        if row.status is MarketGatheringStatus.GATHERING:
            by_venue[row.venue_id].append(row)

    rows: list[MarketVenueRow] = []
    for venue_id in sorted(by_venue):
        window_rows = sorted(by_venue[venue_id], key=lambda item: item.window_index)
        first_window = window_rows[0].window_index
        last_window = window_rows[-1].window_index
        observed = max(1, window_end - first_window + 1)
        active_count = 0
        qualifying_windows = 0
        for window_row in window_rows:
            active_count += 1
            if window_row.distinct_party_count >= active.min_gathering_participants:
                qualifying_windows += 1
            recurrence = min(1_000, active_count * 1_000 // observed)
            if active_count == 1:
                status = MarketVenueStatus.SINGLE_GATHERING
            elif active_count >= active.min_persistent_windows and (
                recurrence >= active.persistent_recurrence_milli
                and qualifying_windows >= active.min_recurring_windows
            ):
                status = MarketVenueStatus.MARKET_LIKE_PERSISTENT
            else:
                status = MarketVenueStatus.RECURRING_GATHERING
            coverage = window_row.coverage
            rows.append(
                MarketVenueRow(
                    venue_id=venue_id,
                    window_index=window_row.window_index,
                    location_token=window_row.location_token,
                    exchange_count=window_row.exchange_count,
                    proposal_count=window_row.proposal_count,
                    withdrawn_count=window_row.withdrawn_count,
                    distinct_party_count=window_row.distinct_party_count,
                    distinct_actor_count=window_row.distinct_actor_count,
                    active_window_count=active_count,
                    recurrence_milli=recurrence,
                    status=status,
                    market_like=status is MarketVenueStatus.MARKET_LIKE_PERSISTENT,
                    coverage=coverage,
                    participant_tokens=tuple(
                        sorted(
                            participants.get(
                                (window_row.window_index, venue_id), set()
                            )
                        )
                    ),
                )
            )
        dormant_count = min(
            active.max_dormant_windows_per_venue, max(0, window_end - last_window)
        )
        for offset in range(1, dormant_count + 1):
            rows.append(
                MarketVenueRow(
                    venue_id=venue_id,
                    window_index=last_window + offset,
                    location_token=window_rows[-1].location_token,
                    exchange_count=0,
                    proposal_count=0,
                    withdrawn_count=0,
                    distinct_party_count=0,
                    distinct_actor_count=0,
                    active_window_count=active_count,
                    recurrence_milli=0,
                    status=MarketVenueStatus.DORMANT,
                    market_like=False,
                    coverage=MarketCoverage.PARTIAL,
                )
            )
    rows.sort(key=lambda row: (row.window_index, row.venue_id))
    if len(rows) > active.max_venue_rows:
        rows = rows[: active.max_venue_rows]
        rows = [replace(row, coverage=MarketCoverage.PARTIAL) for row in rows]
        _LOG.warning(
            "market_venues_truncated venues=%s cap=%s",
            len(rows),
            active.max_venue_rows,
        )
    _LOG.debug(
        "market_venues_detected venues=%s gatherings=%s markets=%s participants=%s",
        len(rows),
        len(gatherings),
        0,
        0,
    )
    return tuple(rows)


def _find(parent: dict[str, str], value: str) -> str:
    while parent[value] != value:
        parent[value] = parent[parent[value]]
        value = parent[value]
    return value


def _union(parent: dict[str, str], left: str, right: str) -> None:
    left_root = _find(parent, left)
    right_root = _find(parent, right)
    if left_root != right_root:
        parent[max(left_root, right_root)] = min(left_root, right_root)


def _components(
    windows: Mapping[int, Sequence[MarketVenueRow]],
) -> list[tuple[int, tuple[str, ...]]]:
    components: list[tuple[int, tuple[str, ...]]] = []
    for window_index in sorted(windows):
        rows = windows[window_index]
        parent = {row.venue_id: row.venue_id for row in rows}
        by_participant: dict[str, list[str]] = defaultdict(list)
        for row in rows:
            for token in row.participant_tokens:
                by_participant[token].append(row.venue_id)
        for venue_ids in by_participant.values():
            for index in range(1, len(venue_ids)):
                _union(parent, venue_ids[0], venue_ids[index])
        grouped: dict[str, list[str]] = defaultdict(list)
        for row in rows:
            grouped[_find(parent, row.venue_id)].append(row.venue_id)
        for venue_ids in grouped.values():
            components.append((window_index, tuple(sorted(set(venue_ids)))))
    components.sort()
    return components


def detect_market_candidates(
    venues: Sequence[MarketVenueRow],
    *,
    policy: MarketInstitutionsAnalysisPolicy | None = None,
) -> tuple[MarketCandidateRow, ...]:
    """Group contemporaneous venues connected by shared participants."""

    active = _policy(policy)
    if isinstance(venues, (str, bytes)) or not isinstance(venues, Sequence):
        raise MarketInstitutionsError("market_institutions_invalid_input")
    for row in venues:
        if type(row) is not MarketVenueRow:
            raise MarketInstitutionsError("market_institutions_invalid_input")
    windows: dict[int, list[MarketVenueRow]] = defaultdict(list)
    for row in venues:
        if row.status is MarketVenueStatus.DORMANT:
            continue
        windows[row.window_index].append(row)

    rows: list[MarketCandidateRow] = []
    for window_index, venue_ids in _components(windows):
        members = [
            row
            for row in windows[window_index]
            if row.venue_id in set(venue_ids)
        ]
        participants: set[str] = set()
        for row in members:
            participants.update(row.participant_tokens)
        coverage = (
            MarketCoverage.PARTIAL
            if any(row.coverage is MarketCoverage.PARTIAL for row in members)
            else MarketCoverage.COMPLETE
        )
        rows.append(
            MarketCandidateRow(
                market_token=market_candidate_token(venue_ids),
                window_index=window_index,
                venue_ids=venue_ids,
                exchange_count=sum(row.exchange_count for row in members),
                distinct_party_count=len(participants),
                coverage=coverage,
            )
        )
    rows.sort(key=lambda row: (row.window_index, row.market_token))
    if len(rows) > active.max_markets:
        rows = rows[: active.max_markets]
        rows = [replace(row, coverage=MarketCoverage.PARTIAL) for row in rows]
        _LOG.warning(
            "market_candidates_truncated markets=%s cap=%s",
            len(rows),
            active.max_markets,
        )
    return tuple(rows)


def detect_participation(
    harvest: MarketEvidenceHarvest,
    *,
    policy: MarketInstitutionsAnalysisPolicy | None = None,
) -> tuple[MarketParticipationRow, ...]:
    """Emit broker-like participation counts per venue window and actor."""

    active = _policy(policy)
    harvest = _require_harvest(harvest)
    counts: dict[tuple[int, str, str], int] = defaultdict(int)
    counterparties: dict[tuple[int, str, str], set[str]] = defaultdict(set)
    windows: dict[tuple[str, str], set[int]] = defaultdict(set)
    for row in harvest.exchanges:
        venue_id = market_venue_token(row.location_token)
        key = (row.window_index, venue_id, row.actor_token)
        counts[key] += 1
        counterparties[key].add(row.counterparty_token)
        windows[(venue_id, row.actor_token)].add(row.window_index)

    coverage = (
        MarketCoverage.PARTIAL
        if harvest.coverage is MarketCoverage.PARTIAL
        else MarketCoverage.COMPLETE
    )
    rows: list[MarketParticipationRow] = []
    for key in sorted(counts):
        window_index, venue_id, actor_token = key
        exchange_count = counts[key]
        counterparty_count = len(counterparties[key])
        active_windows = len(windows[(venue_id, actor_token)])
        broker_like = (
            exchange_count >= active.broker_min_exchanges
            and counterparty_count >= active.broker_min_counterparties
            and active_windows >= active.broker_min_windows
        )
        rows.append(
            MarketParticipationRow(
                venue_id=venue_id,
                window_index=window_index,
                actor_token=actor_token,
                exchange_count=exchange_count,
                counterparty_count=counterparty_count,
                active_window_count=active_windows,
                broker_like=broker_like,
                coverage=coverage,
            )
        )
    if len(rows) > active.max_participation_rows:
        rows = rows[: active.max_participation_rows]
        rows = [replace(row, coverage=MarketCoverage.PARTIAL) for row in rows]
        _LOG.warning(
            "market_participation_truncated rows=%s cap=%s",
            len(rows),
            active.max_participation_rows,
        )
    return tuple(rows)


def assert_market_layer_separation(
    layers: Mapping[MarketLayer, Sequence[object]]
    | Sequence[object],
) -> None:
    """Raise ``market_institutions_layer_leak`` on a cross-layer field/value."""

    entries: list[tuple[MarketLayer, object]] = []
    if isinstance(layers, Mapping):
        for layer, rows in layers.items():
            if type(layer) is not MarketLayer:
                raise MarketInstitutionsError("market_institutions_invalid_input")
            if isinstance(rows, (str, bytes)) or not isinstance(rows, Sequence):
                raise MarketInstitutionsError("market_institutions_invalid_input")
            entries.extend((layer, row) for row in rows)
    elif isinstance(layers, (str, bytes)) or not isinstance(layers, Sequence):
        raise MarketInstitutionsError("market_institutions_invalid_input")
    else:
        for row in layers:
            layer = _infer_layer(row)
            entries.append((layer, row))

    for layer, row in entries:
        fields = getattr(type(row), "__dataclass_fields__", {})
        if set(fields) & MARKET_FORBIDDEN_KEYS:
            raise MarketInstitutionsError("market_institutions_layer_leak")
        forbidden = MARKET_LAYER_FORBIDDEN_PREFIXES[layer]
        for name, value in (
            (name, getattr(row, name)) for name in fields
        ):
            if name in forbidden:
                raise MarketInstitutionsError("market_institutions_layer_leak")
            values = value if isinstance(value, (tuple, list)) else (value,)
            for item in values:
                if type(item) is not str:
                    continue
                for prefix in forbidden:
                    if prefix.endswith("-") and item.startswith(prefix):
                        raise MarketInstitutionsError(
                            "market_institutions_layer_leak"
                        )
                if layer is MarketLayer.OBJECTIVE_EXCHANGE and item.startswith(
                    (MARKET_VENUE_PREFIX, MARKET_CANDIDATE_PREFIX)
                ):
                    raise MarketInstitutionsError(
                        "market_institutions_layer_leak"
                    )


def _infer_layer(row: object) -> MarketLayer:
    from analysis.market_institutions_events import (
        MarketAttemptRow,
        MarketExchangeRow,
    )

    if isinstance(row, (MarketExchangeRow, MarketAttemptRow)):
        return MarketLayer.OBJECTIVE_EXCHANGE
    return MarketLayer.ANALYTICAL_MARKET
