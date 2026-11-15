"""Harvest the five requested objective disruption classes.

Only committed ``WorldEvent`` values are read. No ``WorldState``, inventory
object, runtime, store, or API object is consulted. Missing evidence stays
absent; it is never replaced by a zero or a guessed cause.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from analysis.economic_cascades_contract import (
    CascadeCoverage,
    CascadeDisruptionKind,
    EconomicCascadesError,
)
from analysis.economic_cascades_policy import (
    EconomicCascadesPolicy,
    default_policy,
    window_index,
    window_tick,
)
from analysis.economic_cascades_rows import CascadeDisruptionRow
from world.events import (
    Died,
    InfrastructureDestroyed,
    ResourceHarvested,
    ResourceNodeDepleted,
    ResourceNodeRecovered,
    RouteConditionChanged,
    WorldEvent,
)

__all__ = [
    "CascadeDisruptionResult",
    "harvest_economic_cascade_disruptions",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.economic_cascades.events")

_CLOSED_STATUS: Final[str] = "closed"


@dataclass(frozen=True, slots=True)
class CascadeDisruptionResult:
    """Bounded objective disruption rows plus explicit coverage."""

    rows: tuple[CascadeDisruptionRow, ...] = ()
    notices: tuple[str, ...] = ()
    coverage: CascadeCoverage = CascadeCoverage.MISSING
    event_count: int = 0
    kind_counts: tuple[tuple[str, int], ...] = ()

    def __post_init__(self) -> None:
        for name in ("rows", "notices", "kind_counts"):
            value = getattr(self, name)
            if isinstance(value, (str, bytes)) or not isinstance(value, tuple):
                raise EconomicCascadesError("economic_cascades_invalid_chain")
        if type(self.coverage) is not CascadeCoverage:
            raise EconomicCascadesError("economic_cascades_invalid_chain")
        if (
            isinstance(self.event_count, bool)
            or type(self.event_count) is not int
            or self.event_count < 0
        ):
            raise EconomicCascadesError("economic_cascades_invalid_chain")


def _sorted_events(events: Sequence[WorldEvent]) -> tuple[WorldEvent, ...]:
    if isinstance(events, (str, bytes)) or not isinstance(events, Sequence):
        raise EconomicCascadesError("economic_cascades_invalid_event_order")
    for event in events:
        if type(event) is not WorldEvent:
            raise EconomicCascadesError("economic_cascades_invalid_event_order")
    ordered = tuple(sorted(events, key=lambda event: (event.tick, event.sequence)))
    seen_ids: set[str] = set()
    previous: tuple[int, int] | None = None
    for event in ordered:
        token = event.event_id.value
        if token in seen_ids:
            raise EconomicCascadesError("economic_cascades_invalid_event_order")
        seen_ids.add(token)
        key = (event.tick, event.sequence)
        if key == previous:
            raise EconomicCascadesError("economic_cascades_invalid_event_order")
        previous = key
    return ordered


def _route_subject(event: WorldEvent) -> str:
    details = event.details
    if not isinstance(details, RouteConditionChanged):
        raise EconomicCascadesError("economic_cascades_invalid_event_order")
    origin = details.origin_location_id.value
    destination = details.destination_location_id.value
    return f"route:{origin}->{destination}"


def harvest_economic_cascade_disruptions(
    events: Sequence[WorldEvent],
    *,
    policy: EconomicCascadesPolicy | None = None,
) -> CascadeDisruptionResult:
    """Harvest resource, route, infrastructure, and population disruptions."""

    active = default_policy() if policy is None else policy
    if type(active) is not EconomicCascadesPolicy:
        raise EconomicCascadesError("economic_cascades_invalid_policy")
    ordered = _sorted_events(events)
    notices: set[str] = set()
    event_count = len(ordered)
    if event_count > active.max_events:
        ordered = ordered[: active.max_events]
        notices.add("events_truncated")
        event_count = len(ordered)
        _LOG.warning(
            "economic_cascades_events_truncated retained=%s cap=%s",
            event_count,
            active.max_events,
        )

    rows: list[CascadeDisruptionRow] = []
    recipe_by_node: dict[str, str] = {}
    depleted_nodes: set[str] = set()

    for event in ordered:
        details = event.details
        if isinstance(details, ResourceHarvested):
            recipe_by_node[details.resource_id.value] = details.recipe_id.value
            continue
        if isinstance(details, ResourceNodeRecovered):
            depleted_nodes.discard(details.resource_id.value)
            continue
        if isinstance(details, ResourceNodeDepleted):
            node = details.resource_id.value
            if node in depleted_nodes:
                continue
            depleted_nodes.add(node)
            subject = recipe_by_node.get(node, f"resource:{node}")
            rows.append(
                CascadeDisruptionRow(
                    window_index=window_index(event.tick, active),
                    window_tick=window_tick(
                        window_index(event.tick, active), active
                    ),
                    sequence=event.sequence,
                    kind=CascadeDisruptionKind.RESOURCE_LOSS,
                    subject_token=subject,
                    magnitude_count=1,
                    evidence_event_token=event.event_id.value,
                    coverage=CascadeCoverage.COMPLETE,
                )
            )
            continue
        if isinstance(details, RouteConditionChanged):
            previous = details.previous_status
            if (
                details.current_status == _CLOSED_STATUS
                and previous != _CLOSED_STATUS
            ):
                rows.append(
                    CascadeDisruptionRow(
                        window_index=window_index(event.tick, active),
                        window_tick=window_tick(
                            window_index(event.tick, active), active
                        ),
                        sequence=event.sequence,
                        kind=CascadeDisruptionKind.ROUTE_CLOSURE,
                        subject_token=_route_subject(event),
                        magnitude_count=1,
                        evidence_event_token=event.event_id.value,
                        coverage=CascadeCoverage.COMPLETE,
                    )
                )
            continue
        if isinstance(details, InfrastructureDestroyed):
            rows.append(
                CascadeDisruptionRow(
                    window_index=window_index(event.tick, active),
                    window_tick=window_tick(
                        window_index(event.tick, active), active
                    ),
                    sequence=event.sequence,
                    kind=CascadeDisruptionKind.INFRASTRUCTURE_DESTRUCTION,
                    subject_token=details.asset_id.value,
                    magnitude_count=1,
                    evidence_event_token=event.event_id.value,
                    coverage=CascadeCoverage.COMPLETE,
                )
            )
            continue
        if isinstance(details, Died):
            rows.append(
                CascadeDisruptionRow(
                    window_index=window_index(event.tick, active),
                    window_tick=window_tick(
                        window_index(event.tick, active), active
                    ),
                    sequence=event.sequence,
                    kind=CascadeDisruptionKind.POPULATION_LOSS,
                    subject_token=details.body_id.value,
                    magnitude_count=1,
                    evidence_event_token=event.event_id.value,
                    coverage=CascadeCoverage.COMPLETE,
                )
            )
            continue

    rows.sort(
        key=lambda row: (
            row.window_index,
            row.kind.value,
            row.sequence,
            row.subject_token,
        )
    )
    truncated = False
    if len(rows) > active.max_disruptions:
        rows = rows[: active.max_disruptions]
        notices.add("disruptions_truncated")
        truncated = True
        _LOG.warning(
            "economic_cascades_disruptions_truncated retained=%s cap=%s",
            len(rows),
            active.max_disruptions,
        )

    counts: dict[str, int] = {}
    for row in rows:
        counts[row.kind.value] = counts.get(row.kind.value, 0) + 1
    kind_counts = tuple(sorted(counts.items()))

    if not rows:
        coverage = CascadeCoverage.MISSING
    elif notices:
        coverage = CascadeCoverage.PARTIAL
    else:
        coverage = CascadeCoverage.COMPLETE

    _LOG.debug(
        "economic_cascades_disruptions_scanned events=%s kinds=%s rows=%s",
        event_count,
        len(kind_counts),
        len(rows),
    )
    _LOG.info(
        "economic_cascades_disruptions_complete rows=%s truncated=%s",
        len(rows),
        truncated,
    )
    if coverage is CascadeCoverage.PARTIAL:
        _LOG.warning(
            "economic_cascades_partial_coverage notices=%s",
            ",".join(sorted(notices)),
        )
    return CascadeDisruptionResult(
        rows=tuple(rows),
        notices=tuple(sorted(notices)),
        coverage=coverage,
        event_count=event_count,
        kind_counts=kind_counts,
    )
