"""Committed-event reconstruction of trade transfers and local supply.

This is the only trade-analysis module that knows event shapes. It never reads
``WorldState`` or final inventories, and it never imports cognition,
experiments, API, persistence, or observer modules.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Final

from analysis.trade_networks_contract import (
    NONE_TOKEN,
    TradeCoverage,
    TradeFlowClass,
    TradeNetworksError,
)
from analysis.trade_networks_policy import (
    TradeNetworksAnalysisPolicy,
    flow_class_for_item,
    flow_class_for_media_candidate,
)
from world.events import (
    ArtifactCopied,
    ArtifactCreated,
    ArtifactMoved,
    CraftStarted,
    Eaten,
    ExchangeCompleted,
    Given,
    ItemCrafted,
    ItemStored,
    ResourceHarvested,
    Searched,
    StructureBuilt,
    StructureRepaired,
    WorldEvent,
)
from world.identifiers import EntityId, require_exact_nonneg_int, require_stable_id
from world.values import ItemKind

__all__ = [
    "TradeEvidenceHarvest",
    "TradeLocalSupplyRow",
    "TradeTransferRow",
    "trade_transfer_rows_from_events",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.trade_networks.events")

_DIRECTIONS: Final[frozenset[str]] = frozenset({"give", "take"})
_TRANSFER_SOURCES: Final[frozenset[str]] = frozenset(
    {"exchange", "gift", "artifact_move", "artifact_copy"}
)
_SUPPLY_SOURCES: Final[frozenset[str]] = frozenset(
    {"harvest", "craft", "artifact_create", "artifact_copy", "search"}
)
_FLOW_VALUES: Final[frozenset[str]] = frozenset(item.value for item in TradeFlowClass)


def _require_token(name: str, value: object) -> str:
    if not isinstance(value, str) or not value:
        raise TradeNetworksError("trade_networks_invalid_input")
    return require_stable_id(name, value)


def _optional_token(value: object) -> str:
    return NONE_TOKEN if value is None else _require_token("trade_token", value)


@dataclass(frozen=True, slots=True)
class TradeTransferRow:
    """One observed movement of one item or artifact."""

    entity_kind: str
    entity_token: str
    flow_class: TradeFlowClass
    tick: int
    event_token: str
    location_token: str
    previous_location_token: str
    origin_location_token: str
    actor_token: str
    counterparty_token: str
    direction: str
    source_kind: str
    consumed: bool

    def __post_init__(self) -> None:
        if self.entity_kind not in {"item", "artifact"}:
            raise TradeNetworksError("trade_networks_invalid_input")
        for name in (
            "entity_token",
            "event_token",
            "location_token",
            "previous_location_token",
            "origin_location_token",
            "actor_token",
            "counterparty_token",
        ):
            _require_token(name, getattr(self, name))
        if self.flow_class.value not in _FLOW_VALUES:
            raise TradeNetworksError("trade_networks_invalid_input")
        object.__setattr__(
            self, "tick", require_exact_nonneg_int("TradeTransferRow.tick", self.tick)
        )
        if self.direction not in _DIRECTIONS:
            raise TradeNetworksError("trade_networks_invalid_input")
        if self.source_kind not in _TRANSFER_SOURCES:
            raise TradeNetworksError("trade_networks_invalid_input")
        if type(self.consumed) is not bool:
            raise TradeNetworksError("trade_networks_invalid_input")


@dataclass(frozen=True, slots=True)
class TradeLocalSupplyRow:
    """Observed local creation of one exchangeable entity."""

    flow_class: TradeFlowClass
    location_token: str
    tick: int
    entity_token: str
    source_kind: str

    def __post_init__(self) -> None:
        if self.flow_class.value not in _FLOW_VALUES:
            raise TradeNetworksError("trade_networks_invalid_input")
        _require_token("location_token", self.location_token)
        _require_token("entity_token", self.entity_token)
        object.__setattr__(
            self,
            "tick",
            require_exact_nonneg_int("TradeLocalSupplyRow.tick", self.tick),
        )
        if self.source_kind not in _SUPPLY_SOURCES:
            raise TradeNetworksError("trade_networks_invalid_input")


@dataclass(frozen=True, slots=True)
class TradeEvidenceHarvest:
    """Bounded transfer and local-supply evidence for one completed run."""

    transfers: tuple[TradeTransferRow, ...] = ()
    supplies: tuple[TradeLocalSupplyRow, ...] = ()
    coverage: TradeCoverage = TradeCoverage.MISSING
    notices: tuple[str, ...] = ()
    transfer_count: int = 0
    supply_count: int = 0

    def __post_init__(self) -> None:
        if self.coverage.value not in {"complete", "partial", "missing"}:
            raise TradeNetworksError("trade_networks_invalid_input")
        if self.transfer_count != len(self.transfers):
            raise TradeNetworksError("trade_networks_invalid_input")
        if self.supply_count != len(self.supplies):
            raise TradeNetworksError("trade_networks_invalid_input")


def _event_token(event: WorldEvent) -> str:
    return event.event_id.value


def _entity_token(entity: EntityId | None) -> str | None:
    if entity is None:
        return None
    return entity.value


def _occurrence_origin(event: WorldEvent) -> str | None:
    occurrence = event.occurrence
    if occurrence is None or occurrence.origin_location_id is None:
        return None
    return occurrence.origin_location_id.value


def _item_kind_value(kind: object) -> ItemKind | None:
    if isinstance(kind, ItemKind):
        return kind
    if isinstance(kind, str):
        try:
            return ItemKind(kind)
        except ValueError:
            return None
    return None


def _record_kind(
    kinds: dict[str, ItemKind],
    *,
    item_token: str,
    kind: ItemKind | None,
    notices: set[str],
) -> None:
    if kind is None:
        notices.add("trade_networks_unknown_item_kind")
        return
    existing = kinds.get(item_token)
    if existing is not None and existing is not kind:
        raise TradeNetworksError("trade_networks_conflicting_item_kind")
    kinds[item_token] = kind


def trade_transfer_rows_from_events(
    events: Sequence[WorldEvent],
    *,
    policy: TradeNetworksAnalysisPolicy,
    recipe_item_kinds: Mapping[str, ItemKind] | None = None,
    item_kind_by_id: Mapping[str, ItemKind] | None = None,
) -> TradeEvidenceHarvest:
    """Reconstruct bounded trade evidence from committed events only."""
    if isinstance(events, (str, bytes)) or not isinstance(events, Sequence):
        raise TradeNetworksError("trade_networks_invalid_input")
    recipe_kinds = recipe_item_kinds or {}
    explicit_kinds = item_kind_by_id or {}
    notices: set[str] = set()

    ordered = sorted(events, key=lambda item: (item.tick, item.sequence))
    seen_events: set[str] = set()
    for event in ordered:
        token = _event_token(event)
        if token in seen_events:
            raise TradeNetworksError("trade_networks_duplicate_event")
        seen_events.add(token)

    item_kinds: dict[str, ItemKind] = {}
    for token, kind in explicit_kinds.items():
        _record_kind(item_kinds, item_token=token, kind=kind, notices=notices)

    # Pass one: index exchange bundle kinds so gifts and trajectories can use
    # them even when they occur later in the run.
    for event in ordered:
        details = event.details
        if isinstance(details, ExchangeCompleted):
            if len(details.give_item_ids) != len(details.give_item_kinds) or len(
                details.take_item_ids
            ) != len(details.take_item_kinds):
                raise TradeNetworksError("trade_networks_invalid_exchange")
            for raw, kind_text in zip(
                details.give_item_ids, details.give_item_kinds, strict=True
            ):
                if raw.value in explicit_kinds:
                    continue
                _record_kind(
                    item_kinds,
                    item_token=raw.value,
                    kind=_item_kind_value(kind_text),
                    notices=notices,
                )
            for raw, kind_text in zip(
                details.take_item_ids, details.take_item_kinds, strict=True
            ):
                if raw.value in explicit_kinds:
                    continue
                _record_kind(
                    item_kinds,
                    item_token=raw.value,
                    kind=_item_kind_value(kind_text),
                    notices=notices,
                )
        elif isinstance(details, (ItemCrafted, ResourceHarvested)):
            recipe_token = details.recipe_id.value
            created = details.created_item_id
            if created is None:
                continue
            if created.value in item_kinds:
                # Explicit and exchange evidence take precedence over recipes.
                continue
            mapped = recipe_kinds.get(recipe_token)
            if mapped is None:
                notices.add("trade_networks_missing_recipe_kind")
                continue
            _record_kind(
                item_kinds,
                item_token=created.value,
                kind=_item_kind_value(mapped),
                notices=notices,
            )

    item_origins: dict[str, str | None] = {}
    artifact_origins: dict[str, str | None] = {}
    entity_locations: dict[str, str] = {}
    artifact_locations: dict[str, str] = {}
    transfer_counts: dict[str, int] = {}
    transfer_parties: dict[str, set[str]] = {}
    consumed_items: set[str] = set()
    transfers: list[TradeTransferRow] = []
    supplies: list[TradeLocalSupplyRow] = []
    unknown_kind_count = 0

    def note_origin(entity: str, location: str | None, *, artifact: bool) -> None:
        origins = artifact_origins if artifact else item_origins
        if entity not in origins:
            origins[entity] = location
        if location is None:
            notices.add("trade_networks_unresolved_item_origin")

    def current_location(entity: str, *, artifact: bool) -> tuple[str, str]:
        origins = artifact_origins if artifact else item_origins
        locations = artifact_locations if artifact else entity_locations
        previous = locations.get(entity)
        if previous is None:
            previous = origins.get(entity)
        origin_token = origins.get(entity)
        return (
            previous if previous is not None else NONE_TOKEN,
            origin_token if origin_token is not None else NONE_TOKEN,
        )

    def emit_transfer(
        *,
        entity_kind: str,
        entity: str,
        kind: ItemKind | None,
        event: WorldEvent,
        location: str | None,
        actor: str,
        counterparty: str,
        direction: str,
        source_kind: str,
    ) -> None:
        artifact = entity_kind == "artifact"
        previous, origin_token = current_location(entity, artifact=artifact)
        location_token = location if location is not None else NONE_TOKEN
        if location is None:
            notices.add("trade_networks_unresolved_item_origin")
        if previous == NONE_TOKEN:
            notices.add("trade_networks_unresolved_item_origin")
        if artifact:
            flow_class = TradeFlowClass.RECORDS
        else:
            flow_class = (
                flow_class_for_item(kind)
                if kind is not None
                else (TradeFlowClass.OTHER)
            )
        transfers.append(
            TradeTransferRow(
                entity_kind=entity_kind,
                entity_token=entity,
                flow_class=flow_class,
                tick=event.tick,
                event_token=_event_token(event),
                location_token=location_token,
                previous_location_token=previous,
                origin_location_token=origin_token,
                actor_token=actor,
                counterparty_token=counterparty,
                direction=direction,
                source_kind=source_kind,
                consumed=False,
            )
        )
        if artifact:
            artifact_locations[entity] = location_token
        else:
            entity_locations[entity] = location_token
            transfer_counts[entity] = transfer_counts.get(entity, 0) + 1
            transfer_parties.setdefault(entity, set()).add(counterparty)

    def emit_supply(
        *,
        kind: ItemKind | None,
        location: str | None,
        tick: int,
        entity: str,
        source_kind: str,
        artifact: bool = False,
    ) -> None:
        if location is None:
            notices.add("trade_networks_unresolved_item_origin")
            return
        note_origin(entity, location, artifact=artifact)
        if artifact:
            flow_class = TradeFlowClass.RECORDS
            artifact_locations[entity] = location
        else:
            flow_class = (
                flow_class_for_item(kind)
                if kind is not None
                else (TradeFlowClass.OTHER)
            )
            entity_locations[entity] = location
        supplies.append(
            TradeLocalSupplyRow(
                flow_class=flow_class,
                location_token=location,
                tick=tick,
                entity_token=entity,
                source_kind=source_kind,
            )
        )

    for event in ordered:
        details = event.details
        origin = _occurrence_origin(event)
        actor = _entity_token(event.actor_id) or NONE_TOKEN
        if isinstance(details, ResourceHarvested):
            if details.success and details.created_item_id is not None:
                entity = details.created_item_id.value
                emit_supply(
                    kind=item_kinds.get(entity),
                    location=origin,
                    tick=event.tick,
                    entity=entity,
                    source_kind="harvest",
                )
        elif isinstance(details, ItemCrafted):
            entity = details.created_item_id.value
            emit_supply(
                kind=item_kinds.get(entity),
                location=origin,
                tick=event.tick,
                entity=entity,
                source_kind="craft",
            )
        elif isinstance(details, Searched):
            if details.success is not False and details.created_item_id is not None:
                entity = details.created_item_id.value
                emit_supply(
                    kind=item_kinds.get(entity),
                    location=origin,
                    tick=event.tick,
                    entity=entity,
                    source_kind="search",
                )
        elif isinstance(details, ArtifactCreated):
            entity = details.artifact_id.value
            location = (
                details.resulting_location_id.value
                if details.resulting_location_id is not None
                else origin
            )
            emit_supply(
                kind=None,
                location=location,
                tick=event.tick,
                entity=entity,
                source_kind="artifact_create",
                artifact=True,
            )
        elif isinstance(details, ArtifactCopied):
            entity = details.child_artifact_id.value
            emit_supply(
                kind=None,
                location=origin,
                tick=event.tick,
                entity=entity,
                source_kind="artifact_copy",
                artifact=True,
            )
        elif isinstance(details, ArtifactMoved):
            entity = details.artifact_id.value
            location = (
                details.resulting_location_id.value
                if details.resulting_location_id is not None
                else origin
            )
            if location is not None:
                previous = artifact_locations.get(entity, artifact_origins.get(entity))
                if previous is not None and previous != location:
                    emit_transfer(
                        entity_kind="artifact",
                        entity=entity,
                        kind=None,
                        event=event,
                        location=location,
                        actor=actor,
                        counterparty=actor,
                        direction="give",
                        source_kind="artifact_move",
                    )
                else:
                    artifact_locations[entity] = location
        elif isinstance(details, ExchangeCompleted):
            location = origin
            actor_id = details.actor_id.value
            counterparty_id = details.counterparty_id.value
            for raw in details.give_item_ids:
                entity = raw.value
                emit_transfer(
                    entity_kind="item",
                    entity=entity,
                    kind=item_kinds.get(entity),
                    event=event,
                    location=location,
                    actor=actor_id,
                    counterparty=counterparty_id,
                    direction="give",
                    source_kind="exchange",
                )
            for raw in details.take_item_ids:
                entity = raw.value
                emit_transfer(
                    entity_kind="item",
                    entity=entity,
                    kind=item_kinds.get(entity),
                    event=event,
                    location=location,
                    actor=counterparty_id,
                    counterparty=actor_id,
                    direction="take",
                    source_kind="exchange",
                )
        elif isinstance(details, Given):
            entity = details.item_id.value
            if item_kinds.get(entity) is None:
                notices.add("trade_networks_unknown_item_kind")
                unknown_kind_count += 1
            emit_transfer(
                entity_kind="item",
                entity=entity,
                kind=item_kinds.get(entity),
                event=event,
                location=origin,
                actor=actor,
                counterparty=details.recipient_id.value,
                direction="give",
                source_kind="gift",
            )
        elif isinstance(details, Eaten):
            consumed_items.add(details.item_id.value)
        elif isinstance(details, CraftStarted):
            consumed_items.update(item.value for item in details.consumed_item_ids)
        elif isinstance(details, (StructureBuilt, StructureRepaired, ItemStored)):
            consumed_items.add(details.consumed_item_id.value)
        else:
            _LOG.debug("trade_networks_unknown_event_detail ignored")

    transfers.sort(
        key=lambda row: (
            row.tick,
            row.event_token,
            row.entity_token,
            row.direction,
        )
    )
    supplies.sort(key=lambda row: (row.tick, row.entity_token, row.source_kind))

    if unknown_kind_count:
        _LOG.warning("trade_networks_unknown_item_kind count=%s", unknown_kind_count)

    # Retrospective media classification over the completed run.
    reclassified: list[TradeTransferRow] = []
    for row in transfers:
        entity = row.entity_token
        entity_kind = item_kinds.get(entity)
        if row.entity_kind != "item":
            reclassified.append(row)
            continue
        consumed = entity in consumed_items
        flow_class = row.flow_class
        if entity_kind is ItemKind.GENERIC:
            flow_class = flow_class_for_media_candidate(
                entity_kind,
                transfer_counts.get(entity, 0),
                len(transfer_parties.get(entity, set())),
                consumed,
            )
        reclassified.append(
            replace(row, flow_class=flow_class, consumed=consumed)
        )
    transfers = reclassified

    if len(transfers) > policy.max_transfer_rows:
        transfers = transfers[: policy.max_transfer_rows]
        notices.add("trade_networks_transfer_truncated")
        _LOG.warning(
            "trade_networks_transfer_truncated retained=%s cap=%s",
            len(transfers),
            policy.max_transfer_rows,
        )

    if not transfers and not supplies:
        coverage = TradeCoverage.MISSING
    elif notices:
        coverage = TradeCoverage.PARTIAL
    elif any(
        row.previous_location_token == NONE_TOKEN
        or row.location_token == NONE_TOKEN
        or row.origin_location_token == NONE_TOKEN
        for row in transfers
    ):
        coverage = TradeCoverage.PARTIAL
    else:
        coverage = TradeCoverage.COMPLETE

    _LOG.debug(
        "trade_networks_evidence transfers=%s supplies=%s coverage=%s",
        len(transfers),
        len(supplies),
        coverage.value,
    )
    return TradeEvidenceHarvest(
        transfers=tuple(transfers),
        supplies=tuple(supplies),
        coverage=coverage,
        notices=tuple(sorted(notices)),
        transfer_count=len(transfers),
        supply_count=len(supplies),
    )
