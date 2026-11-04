"""Objective contact, exchange, and attack anchors for diplomacy analysis."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from analysis.diplomacy_contract import DiplomacyAnalysisError

__all__ = [
    "DiplomacyObjectiveAnchorRow",
    "build_diplomacy_windows",
    "diplomacy_objective_anchor_rows_from_events",
]

_ATTACK_KINDS: Final[frozenset[str]] = frozenset({"attack", "harm"})


@dataclass(frozen=True, slots=True)
class DiplomacyObjectiveAnchorRow:
    tick: int
    region_token: str
    contact_event_count: int = 0
    exchange_event_count: int = 0
    attack_event_count: int = 0

    def __post_init__(self) -> None:
        for value in (
            self.tick,
            self.contact_event_count,
            self.exchange_event_count,
            self.attack_event_count,
        ):
            if type(value) is not int or isinstance(value, bool) or value < 0:
                raise DiplomacyAnalysisError("diplomacy_invalid_row")


def diplomacy_objective_anchor_rows_from_events(
    events: Sequence[object],
    entity_to_agent: Callable[[object], object] | Mapping[object, object] | None = None,
) -> tuple[DiplomacyObjectiveAnchorRow, ...]:
    """Count objective acts by tick and region. No owner token is carried."""

    counts: dict[tuple[int, str], list[int]] = defaultdict(lambda: [0, 0, 0])
    for event in events:
        tick = getattr(event, "tick", 0)
        details = getattr(event, "details", None)
        location = getattr(details, "location_id", None)
        region = getattr(location, "value", location) or "unknown"
        name = type(details).__name__
        bucket = counts[(tick, str(region))]
        if name == "ContactRecorded":
            bucket[0] += 1
        elif name == "ExchangeCompleted":
            bucket[1] += 1
        elif getattr(details, "action_kind", None) in _ATTACK_KINDS or name in {
            "AttackApplied",
            "HarmApplied",
        }:
            bucket[2] += 1
    return tuple(
        DiplomacyObjectiveAnchorRow(
            tick=tick,
            region_token=region,
            contact_event_count=values[0],
            exchange_event_count=values[1],
            attack_event_count=values[2],
        )
        for (tick, region), values in sorted(counts.items())
    )


def build_diplomacy_windows(
    rows: Sequence[DiplomacyObjectiveAnchorRow],
    *,
    window_ticks: int = 1,
) -> tuple[DiplomacyObjectiveAnchorRow, ...]:
    """Sum objective anchors into fixed deterministic windows."""

    if type(window_ticks) is not int or window_ticks <= 0:
        raise DiplomacyAnalysisError("diplomacy_analysis_invalid_input")
    totals: dict[tuple[int, str], list[int]] = defaultdict(lambda: [0, 0, 0])
    for row in rows:
        start = (row.tick // window_ticks) * window_ticks
        bucket = totals[(start, row.region_token)]
        bucket[0] += row.contact_event_count
        bucket[1] += row.exchange_event_count
        bucket[2] += row.attack_event_count
    return tuple(
        DiplomacyObjectiveAnchorRow(
            tick=tick,
            region_token=region,
            contact_event_count=values[0],
            exchange_event_count=values[1],
            attack_event_count=values[2],
        )
        for (tick, region), values in sorted(totals.items())
    )
