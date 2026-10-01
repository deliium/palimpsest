"""Adapt committed world events into semantic observer events."""

from __future__ import annotations

import logging
from collections.abc import Sequence

from observer.contracts import ObserverEvent
from observer.version import OBSERVER_PROTOCOL_VERSION, SEMANTIC_TYPE_BY_KIND
from world.events import (
    CraftStarted,
    Died,
    Dropped,
    Drunk,
    Eaten,
    ExposureApplied,
    Fled,
    Given,
    ItemCrafted,
    ItemStored,
    Moved,
    NeedsApplied,
    ResourceHarvested,
    ResourceRegenerated,
    Searched,
    StructureBuilt,
    StructureRepaired,
    Taken,
    WeatherChanged,
    WorldEvent,
)
from world.identifiers import EntityId

_LOGGER = logging.getLogger("observer.adapt")


def _text(value: EntityId | None) -> str | None:
    if value is None:
        return None
    return value.value


def adapt_event(event: WorldEvent) -> ObserverEvent:
    if type(event) is not WorldEvent:
        _LOGGER.error(
            "observer_event_rejected event_id=%s reason_code=%s",
            "-",
            "unknown_event_kind",
        )
        raise TypeError("unknown_event_kind")
    kind = event.details.kind
    semantic = SEMANTIC_TYPE_BY_KIND.get(kind)
    if semantic is None:
        _LOGGER.error(
            "observer_event_rejected event_id=%s reason_code=%s",
            event.event_id.value,
            "unknown_event_kind",
        )
        raise TypeError("unknown_event_kind")
    occurrence = event.occurrence
    origin = None if occurrence is None else _text(occurrence.origin_location_id)
    destination = (
        None if occurrence is None else _text(occurrence.destination_location_id)
    )
    actor_id = _text(event.actor_id)
    target_id = _text(event.target_id)
    item_id: str | None = None
    resource_id: str | None = None
    recipe_id: str | None = None
    structure_id: str | None = None
    details = event.details
    if isinstance(details, Moved):
        destination = _text(details.destination_id)
    elif isinstance(details, Fled):
        if details.destination_id is not None:
            destination = _text(details.destination_id)
    elif isinstance(details, (Taken, Dropped, Eaten)):
        item_id = _text(details.item_id)
    elif isinstance(details, Given):
        target_id = _text(details.recipient_id)
        item_id = _text(details.item_id)
        if occurrence is not None:
            origin = _text(occurrence.origin_location_id)
    elif isinstance(details, Drunk):
        if details.consumed_item is False:
            resource_id = _text(details.source_id)
        else:
            item_id = _text(details.source_id)
    elif isinstance(details, Searched) and details.created_item_id is not None:
        item_id = _text(details.created_item_id)
    elif isinstance(details, WeatherChanged):
        origin = _text(details.location_id)
    elif isinstance(details, ResourceRegenerated):
        resource_id = _text(details.resource_id)
    elif isinstance(details, (NeedsApplied, ExposureApplied, Died)):
        target_id = _text(details.body_id)
    elif isinstance(details, ResourceHarvested):
        recipe_id = details.recipe_id.value
        resource_id = _text(details.resource_id)
        item_id = _text(details.created_item_id)
    elif isinstance(details, CraftStarted):
        recipe_id = details.recipe_id.value
    elif isinstance(details, ItemCrafted):
        recipe_id = details.recipe_id.value
        item_id = _text(details.created_item_id)
    elif isinstance(details, (StructureBuilt, StructureRepaired, ItemStored)):
        recipe_id = details.recipe_id.value
        structure_id = _text(details.structure_id)
    adapted = ObserverEvent(
        protocol_version=OBSERVER_PROTOCOL_VERSION,
        type=semantic,
        domain_kind=kind,
        event_id=event.event_id.value,
        tick=event.tick,
        sequence=event.sequence,
        actor_id=actor_id,
        target_id=target_id,
        item_id=item_id,
        resource_id=resource_id,
        origin_location_id=origin,
        destination_location_id=destination,
        recipe_id=recipe_id,
        structure_id=structure_id,
    )
    if recipe_id is not None:
        _LOGGER.debug(
            "production_projected structure_count=%s event_kind=%s",
            0 if structure_id is None else 1,
            kind,
        )
    _LOGGER.debug(
        "observer_event_adapted event_id=%s tick=%s sequence=%s "
        "domain_kind=%s semantic_type=%s",
        adapted.event_id,
        adapted.tick,
        adapted.sequence,
        adapted.domain_kind,
        adapted.type,
    )
    return adapted


def adapt_events(events: Sequence[WorldEvent]) -> tuple[ObserverEvent, ...]:
    return tuple(adapt_event(event) for event in events)


__all__ = ["adapt_event", "adapt_events"]
