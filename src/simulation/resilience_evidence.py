"""Narrow finalized-boundary evidence for societal-resilience capture.

Inspect-only DTOs. Analysis never imports cognition ledgers; simulation projects
allowlisted keys and physical facts at sealed boundaries only.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from world.identifiers import require_exact_nonneg_int, require_stable_id
from world.values import round_physical

__all__ = [
    "MAX_RESILIENCE_APPLIED_SHOCK_TICKS",
    "MAX_RESILIENCE_CUMULATIVE_EVENTS",
    "MAX_RESILIENCE_CUMULATIVE_FRAME_ROWS",
    "MAX_RESILIENCE_FRAME_ROWS",
    "MAX_RESILIENCE_HORIZON",
    "MAX_RESILIENCE_INFRASTRUCTURE_ASSETS",
    "MAX_RESILIENCE_MANAGED_STOCKS",
    "MAX_RESILIENCE_ROSTER",
    "OwnerLaneState",
    "ResilienceBatchEvents",
    "ResilienceBodyRow",
    "ResilienceBoundaryFacts",
    "ResilienceDeathRow",
    "ResilienceEvidenceError",
    "ResilienceExchangeRow",
    "ResilienceFeedRow",
    "ResilienceHelpRow",
    "ResilienceInfrastructureRow",
    "ResilienceJourneyArrivalRow",
    "ResilienceOwnerKeys",
    "ResilienceProjectContributionRow",
    "ResilienceShockReceiptRow",
    "ResilienceStockRow",
    "count_normalized_rows",
    "project_resilience_batch_events",
    "quantity_tenths",
]

MAX_RESILIENCE_HORIZON: Final[int] = 512
MAX_RESILIENCE_CUMULATIVE_EVENTS: Final[int] = 50_000
MAX_RESILIENCE_CUMULATIVE_FRAME_ROWS: Final[int] = 65_536
MAX_RESILIENCE_APPLIED_SHOCK_TICKS: Final[int] = 32

_LOG: Final[logging.Logger] = logging.getLogger("simulation.resilience_evidence")

MAX_RESILIENCE_ROSTER: Final[int] = 128
MAX_RESILIENCE_MANAGED_STOCKS: Final[int] = 256
MAX_RESILIENCE_INFRASTRUCTURE_ASSETS: Final[int] = 512
MAX_RESILIENCE_FRAME_ROWS: Final[int] = 4_096

_ERROR_CODES: Final[frozenset[str]] = frozenset(
    {
        "resilience_evidence_invalid_integer",
        "resilience_evidence_invalid_token",
        "resilience_evidence_invalid_input",
        "resilience_evidence_roster_overflow",
        "resilience_evidence_stock_overflow",
        "resilience_evidence_infra_overflow",
        "resilience_evidence_frame_overflow",
        "resilience_evidence_body_hash_mismatch",
        "resilience_evidence_receipt_missing",
        "resilience_evidence_quantity_grid",
    }
)


class ResilienceEvidenceError(ValueError):
    """Fail-closed evidence projection error with a stable reason code."""

    @property
    def reason_code(self) -> str:
        if not self.args:
            return "resilience_evidence_invalid_input"
        return str(self.args[0])


class OwnerLaneState(StrEnum):
    """Per-owner knowledge/institution projection state."""

    OFF = "off"
    COMPLETE = "complete"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True, slots=True)
class ResilienceBodyRow:
    """Living or registered body token with held-item count (zeros included)."""

    body_id: str
    agent_id: str
    living: bool
    held_item_count: int
    region_id: str | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "body_id", require_stable_id("body_id", self.body_id))
        object.__setattr__(
            self, "agent_id", require_stable_id("agent_id", self.agent_id)
        )
        if type(self.living) is not bool:
            raise ResilienceEvidenceError("resilience_evidence_invalid_input")
        object.__setattr__(
            self,
            "held_item_count",
            require_exact_nonneg_int("held_item_count", self.held_item_count),
        )
        if self.region_id is not None:
            object.__setattr__(
                self, "region_id", require_stable_id("region_id", self.region_id)
            )


@dataclass(frozen=True, slots=True)
class ResilienceStockRow:
    """One managed ecological stock at a boundary."""

    stock_id: str
    resource_kind: str
    unit: str
    quantity_tenths: int
    effective_capacity_tenths: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "stock_id", require_stable_id("stock_id", self.stock_id)
        )
        object.__setattr__(
            self,
            "resource_kind",
            require_stable_id("resource_kind", self.resource_kind),
        )
        object.__setattr__(self, "unit", require_stable_id("unit", self.unit))
        object.__setattr__(
            self,
            "quantity_tenths",
            require_exact_nonneg_int("quantity_tenths", self.quantity_tenths),
        )
        object.__setattr__(
            self,
            "effective_capacity_tenths",
            require_exact_nonneg_int(
                "effective_capacity_tenths", self.effective_capacity_tenths
            ),
        )


@dataclass(frozen=True, slots=True)
class ResilienceInfrastructureRow:
    """One infrastructure asset identity and operational status."""

    asset_id: str
    kind: str
    location_id: str
    endpoint_location_id: str | None
    status: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "asset_id", require_stable_id("asset_id", self.asset_id)
        )
        object.__setattr__(self, "kind", require_stable_id("kind", self.kind))
        object.__setattr__(
            self, "location_id", require_stable_id("location_id", self.location_id)
        )
        if self.endpoint_location_id is not None:
            object.__setattr__(
                self,
                "endpoint_location_id",
                require_stable_id("endpoint_location_id", self.endpoint_location_id),
            )
        object.__setattr__(self, "status", require_stable_id("status", self.status))


@dataclass(frozen=True, slots=True)
class ResilienceOwnerKeys:
    """Allowlisted owner concept/content keys; never raw ledgers."""

    agent_id: str
    body_id: str
    living: bool
    institution_state: OwnerLaneState
    knowledge_state: OwnerLaneState
    recognized_concept_ids: tuple[str, ...]
    active_content_keys: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "agent_id", require_stable_id("agent_id", self.agent_id)
        )
        object.__setattr__(self, "body_id", require_stable_id("body_id", self.body_id))
        if type(self.living) is not bool:
            raise ResilienceEvidenceError("resilience_evidence_invalid_input")
        if type(self.institution_state) is not OwnerLaneState:
            raise ResilienceEvidenceError("resilience_evidence_invalid_input")
        if type(self.knowledge_state) is not OwnerLaneState:
            raise ResilienceEvidenceError("resilience_evidence_invalid_input")
        if type(self.recognized_concept_ids) is not tuple:
            raise ResilienceEvidenceError("resilience_evidence_invalid_input")
        if type(self.active_content_keys) is not tuple:
            raise ResilienceEvidenceError("resilience_evidence_invalid_input")
        object.__setattr__(
            self,
            "recognized_concept_ids",
            tuple(
                require_stable_id("concept_id", item)
                for item in self.recognized_concept_ids
            ),
        )
        object.__setattr__(
            self,
            "active_content_keys",
            tuple(
                require_stable_id("content_key", item)
                for item in self.active_content_keys
            ),
        )
        if self.institution_state is not OwnerLaneState.COMPLETE:
            if self.recognized_concept_ids:
                raise ResilienceEvidenceError("resilience_evidence_invalid_input")
        if self.knowledge_state is not OwnerLaneState.COMPLETE:
            if self.active_content_keys:
                raise ResilienceEvidenceError("resilience_evidence_invalid_input")


@dataclass(frozen=True, slots=True)
class ResilienceBoundaryFacts:
    """Sanitized boundary witness for one finalized capture sample."""

    run_id: str
    config_fingerprint: str
    boundary_tick: int
    revision: int
    body_projection_hash: str | None
    history_length: int
    infrastructure_channel: OwnerLaneState
    ecology_channel: OwnerLaneState
    bodies: tuple[ResilienceBodyRow, ...]
    stocks: tuple[ResilienceStockRow, ...]
    infrastructure: tuple[ResilienceInfrastructureRow, ...]
    owners: tuple[ResilienceOwnerKeys, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_id", require_stable_id("run_id", self.run_id))
        object.__setattr__(
            self,
            "config_fingerprint",
            require_stable_id("config_fingerprint", self.config_fingerprint),
        )
        object.__setattr__(
            self,
            "boundary_tick",
            require_exact_nonneg_int("boundary_tick", self.boundary_tick),
        )
        object.__setattr__(
            self, "revision", require_exact_nonneg_int("revision", self.revision)
        )
        if self.body_projection_hash is not None:
            object.__setattr__(
                self,
                "body_projection_hash",
                require_stable_id("body_projection_hash", self.body_projection_hash),
            )
        object.__setattr__(
            self,
            "history_length",
            require_exact_nonneg_int("history_length", self.history_length),
        )
        if type(self.infrastructure_channel) is not OwnerLaneState:
            raise ResilienceEvidenceError("resilience_evidence_invalid_input")
        if type(self.ecology_channel) is not OwnerLaneState:
            raise ResilienceEvidenceError("resilience_evidence_invalid_input")
        for _name, rows, model in (
            ("bodies", self.bodies, ResilienceBodyRow),
            ("stocks", self.stocks, ResilienceStockRow),
            ("infrastructure", self.infrastructure, ResilienceInfrastructureRow),
            ("owners", self.owners, ResilienceOwnerKeys),
        ):
            if type(rows) is not tuple:
                raise ResilienceEvidenceError("resilience_evidence_invalid_input")
            for row in rows:
                if type(row) is not model:
                    raise ResilienceEvidenceError("resilience_evidence_invalid_input")
        total = count_normalized_rows(
            bodies=self.bodies,
            stocks=self.stocks,
            infrastructure=self.infrastructure,
            owners=self.owners,
        )
        if total > MAX_RESILIENCE_FRAME_ROWS:
            raise ResilienceEvidenceError("resilience_evidence_frame_overflow")


def quantity_tenths(value: float) -> int:
    """Convert a physical quantity onto the exact tenths grid."""

    rounded = round_physical(value)
    tenths = round(rounded * 10.0)
    if type(tenths) is not int or isinstance(tenths, bool):
        raise ResilienceEvidenceError("resilience_evidence_quantity_grid")
    if abs(rounded * 10.0 - tenths) > 1e-9:
        raise ResilienceEvidenceError("resilience_evidence_quantity_grid")
    if tenths < 0:
        raise ResilienceEvidenceError("resilience_evidence_quantity_grid")
    return tenths


def count_normalized_rows(
    *,
    bodies: Sequence[ResilienceBodyRow],
    stocks: Sequence[ResilienceStockRow],
    infrastructure: Sequence[ResilienceInfrastructureRow],
    owners: Sequence[ResilienceOwnerKeys],
) -> int:
    """Count normalized frame entries including owner key leaves."""

    total = len(bodies) + len(stocks) + len(infrastructure) + len(owners)
    for owner in owners:
        total += len(owner.recognized_concept_ids) + len(owner.active_content_keys)
    return total


def region_id_for_location(
    location_regions: Mapping[str, str] | None, location_id: str
) -> str | None:
    """Map a location to a region id when regions_migration is configured."""

    if location_regions is None:
        return None
    return location_regions.get(location_id)


@dataclass(frozen=True, slots=True)
class ResilienceDeathRow:
    """Committed death of a registered body."""

    event_id: str
    tick: int
    sequence: int
    body_id: str


@dataclass(frozen=True, slots=True)
class ResilienceJourneyArrivalRow:
    """Committed cross-region journey arrival participant."""

    event_id: str
    tick: int
    sequence: int
    journey_id: str
    body_id: str
    origin_region_id: str | None
    destination_region_id: str | None


@dataclass(frozen=True, slots=True)
class ResilienceHelpRow:
    """Committed Helped act."""

    event_id: str
    tick: int
    sequence: int
    actor_body_id: str
    target_body_id: str


@dataclass(frozen=True, slots=True)
class ResilienceFeedRow:
    """Committed Fed act."""

    event_id: str
    tick: int
    sequence: int
    actor_body_id: str
    target_body_id: str


@dataclass(frozen=True, slots=True)
class ResilienceProjectContributionRow:
    """Committed collective-project contribution."""

    event_id: str
    tick: int
    sequence: int
    actor_body_id: str
    project_id: str


@dataclass(frozen=True, slots=True)
class ResilienceExchangeRow:
    """Committed completed exchange with optional venue location."""

    event_id: str
    tick: int
    sequence: int
    venue_location_id: str | None
    item_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ResilienceShockReceiptRow:
    """Safe disaster receipt metadata for schedule/episode joins."""

    event_id: str
    tick: int
    sequence: int
    rule_id: str
    kind: str
    origin: str
    outcome: str


@dataclass(frozen=True, slots=True)
class ResilienceBatchEvents:
    """Typed last-tick batch projection; never whole-history export."""

    tick: int
    resulting_revision: int
    deaths: tuple[ResilienceDeathRow, ...]
    journey_arrivals: tuple[ResilienceJourneyArrivalRow, ...]
    helps: tuple[ResilienceHelpRow, ...]
    feeds: tuple[ResilienceFeedRow, ...]
    contributions: tuple[ResilienceProjectContributionRow, ...]
    exchanges: tuple[ResilienceExchangeRow, ...]
    shock_receipts: tuple[ResilienceShockReceiptRow, ...]
    event_count: int


def project_resilience_batch_events(
    events: Sequence[object],
    *,
    tick: int,
    resulting_revision: int,
) -> ResilienceBatchEvents:
    """Project allowlisted committed events from one tick batch."""

    from world.events import (
        Died,
        DisasterResolved,
        ExchangeCompleted,
        Fed,
        Helped,
        JourneyArrived,
        ProjectContributed,
        WorldEvent,
    )

    require_exact_nonneg_int("tick", tick)
    require_exact_nonneg_int("resulting_revision", resulting_revision)
    deaths: list[ResilienceDeathRow] = []
    arrivals: list[ResilienceJourneyArrivalRow] = []
    helps: list[ResilienceHelpRow] = []
    feeds: list[ResilienceFeedRow] = []
    contributions: list[ResilienceProjectContributionRow] = []
    exchanges: list[ResilienceExchangeRow] = []
    shocks: list[ResilienceShockReceiptRow] = []
    for event in events:
        if type(event) is not WorldEvent:
            raise ResilienceEvidenceError("resilience_evidence_invalid_input")
        if event.tick != tick:
            raise ResilienceEvidenceError("resilience_evidence_invalid_input")
        details = event.details
        event_id = event.event_id.value
        sequence = event.sequence
        if type(details) is Died:
            deaths.append(
                ResilienceDeathRow(
                    event_id=event_id,
                    tick=tick,
                    sequence=sequence,
                    body_id=details.body_id.value,
                )
            )
        elif type(details) is JourneyArrived:
            for participant in details.participant_body_ids:
                arrivals.append(
                    ResilienceJourneyArrivalRow(
                        event_id=event_id,
                        tick=tick,
                        sequence=sequence,
                        journey_id=details.journey_id,
                        body_id=participant.value,
                        origin_region_id=None,
                        destination_region_id=None,
                    )
                )
        elif type(details) is Helped:
            if event.actor_id is None:
                raise ResilienceEvidenceError("resilience_evidence_invalid_input")
            helps.append(
                ResilienceHelpRow(
                    event_id=event_id,
                    tick=tick,
                    sequence=sequence,
                    actor_body_id=event.actor_id.value,
                    target_body_id=details.target_id.value,
                )
            )
        elif type(details) is Fed:
            if event.actor_id is None:
                raise ResilienceEvidenceError("resilience_evidence_invalid_input")
            feeds.append(
                ResilienceFeedRow(
                    event_id=event_id,
                    tick=tick,
                    sequence=sequence,
                    actor_body_id=event.actor_id.value,
                    target_body_id=details.target_id.value,
                )
            )
        elif type(details) is ProjectContributed:
            contributions.append(
                ResilienceProjectContributionRow(
                    event_id=event_id,
                    tick=tick,
                    sequence=sequence,
                    actor_body_id=details.actor_id.value,
                    project_id=details.project_id.value,
                )
            )
        elif type(details) is ExchangeCompleted:
            item_ids = tuple(
                sorted(
                    {
                        *(item.value for item in details.give_item_ids),
                        *(item.value for item in details.take_item_ids),
                    }
                )
            )
            occurrence = event.occurrence
            venue = None if occurrence is None else occurrence.origin_location_id
            exchanges.append(
                ResilienceExchangeRow(
                    event_id=event_id,
                    tick=tick,
                    sequence=sequence,
                    venue_location_id=None if venue is None else venue.value,
                    item_ids=item_ids,
                )
            )
        elif type(details) is DisasterResolved:
            shocks.append(
                ResilienceShockReceiptRow(
                    event_id=event_id,
                    tick=tick,
                    sequence=sequence,
                    rule_id=details.rule_id,
                    kind=details.disaster_kind.value,
                    origin=details.origin.value,
                    outcome=details.outcome.value,
                )
            )
    return ResilienceBatchEvents(
        tick=tick,
        resulting_revision=resulting_revision,
        deaths=tuple(deaths),
        journey_arrivals=tuple(arrivals),
        helps=tuple(helps),
        feeds=tuple(feeds),
        contributions=tuple(contributions),
        exchanges=tuple(exchanges),
        shock_receipts=tuple(shocks),
        event_count=len(events),
    )
