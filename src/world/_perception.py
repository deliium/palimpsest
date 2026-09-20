"""Private deterministic perception projector.

Visibility policy:
- Always expose self, hour/day-phase, visibility modifier, current weather,
  current location, and adjacent exits.
- Ground items, resource nodes, and other bodies appear only when effective
  visibility is at least ``CONTENT_VISIBILITY_THRESHOLD``.
- Held inventory remains visible below the content threshold.
- Dead registered observers still receive self/time/environment observations.
- Physical target validation is not visibility-gated (handled elsewhere).
- Prior-tick occurrences are redacted by audience using event occurrence context.
- Communication text is claim-only and delivered to speaker and private recipients.
"""

from __future__ import annotations

from collections.abc import Sequence

from world._state import WorldState
from world.events import (
    Asked,
    Talked,
    Told,
    WorldEvent,
    require_replayable_event,
)
from world.identifiers import EntityId, WorldId
from world.models import Item, copy_body
from world.observations import (
    CONTENT_VISIBILITY_THRESHOLD,
    Observation,
    ObservationAudienceRole,
    ObservationContext,
    ObservationProvenance,
    ObservationSourceKind,
    ObservedCommunication,
    ObservedItem,
    ObservedItemPlacement,
    ObservedLocation,
    ObservedOccurrence,
    ObservedResource,
    VisibleBody,
    VisibleExit,
    coarse_health_for,
    observed_self_from_body,
)
from world.values import WeatherCondition

__all__: list[str] = ["PerceptionService", "project_observations"]


class PerceptionService:
    """Sole objective-to-subjective projector for agent observations.

    Log-free and deterministic. Accepts world authority inputs only from
    approved simulation/private-world callers.
    """

    def project(
        self,
        *,
        world_id: WorldId,
        state: WorldState,
        observer_ids: Sequence[EntityId],
        context: ObservationContext,
        prior_events: Sequence[WorldEvent] = (),
    ) -> tuple[Observation, ...]:
        """Project exactly one detached observation per ordered observer id."""
        if type(world_id) is not WorldId:
            raise TypeError("PerceptionService.project requires WorldId")
        if type(state) is not WorldState:
            raise TypeError("PerceptionService.project requires WorldState")
        if type(context) is not ObservationContext:
            raise TypeError("PerceptionService.project requires ObservationContext")
        observers = _copy_observer_ids(observer_ids)
        events = _copy_prior_events(prior_events, observation_tick=context.tick)
        for observer_id in observers:
            if observer_id not in state.bodies:
                raise ValueError(
                    f"observer body {observer_id.value!r} is missing from world state"
                )
        return tuple(
            _project_one(
                world_id=world_id,
                state=state,
                observer_id=observer_id,
                context=context,
                prior_events=events,
            )
            for observer_id in observers
        )


def project_observations(
    *,
    world_id: WorldId,
    state: WorldState,
    observer_ids: Sequence[EntityId],
    context: ObservationContext | None = None,
    prior_events: Sequence[WorldEvent] = (),
) -> tuple[Observation, ...]:
    """Compatibility wrapper around :class:`PerceptionService`."""
    resolved = context if context is not None else ObservationContext(tick=0)
    return PerceptionService().project(
        world_id=world_id,
        state=state,
        observer_ids=observer_ids,
        context=resolved,
        prior_events=prior_events,
    )


def _project_one(
    *,
    world_id: WorldId,
    state: WorldState,
    observer_id: EntityId,
    context: ObservationContext,
    prior_events: tuple[WorldEvent, ...],
) -> Observation:
    body = state.bodies[observer_id]
    location_id = body.location_id
    location = state.locations.get(location_id)
    weather = state.weather.get(location_id)
    condition = (
        weather.condition if weather is not None else WeatherCondition.CLEAR
    )
    visibility = 1.0
    if location is not None:
        visibility = context.physical_rules.effective_visibility(
            location_visibility=location.visibility_factor.value,
            phase=context.day_phase,
            condition=condition,
        )
    content_visible = visibility >= CONTENT_VISIBILITY_THRESHOLD
    occurrences, communications = _project_event_window(
        observer_id=observer_id,
        location_id=location_id,
        content_visible=content_visible,
        prior_events=prior_events,
    )
    return Observation(
        world_id=world_id,
        observer_id=observer_id,
        revision=state.revision,
        tick=context.tick,
        self_body=observed_self_from_body(copy_body(body)),
        locations=_sorted_locations(state, location_id),
        items=_sorted_items(
            state,
            observer_id=observer_id,
            location_id=location_id,
            include_ground=content_visible,
        ),
        resources=(
            _sorted_resources(state, location_id) if content_visible else ()
        ),
        exits=_sorted_exits(state, location_id),
        visible_bodies=(
            _sorted_visible_bodies(state, location_id, observer_id)
            if content_visible
            else ()
        ),
        occurrences=occurrences,
        communications=communications,
        hour=context.hour,
        day_phase=context.day_phase,
        visibility=visibility,
        weather_condition=condition,
    )


def _copy_observer_ids(values: Sequence[EntityId]) -> tuple[EntityId, ...]:
    if isinstance(values, (set, frozenset)):
        raise TypeError("observer_ids must be an ordered sequence")
    if isinstance(values, (str, bytes, bytearray)) or not isinstance(
        values, Sequence
    ):
        raise TypeError("observer_ids must be an ordered sequence")
    copied = tuple(values)
    seen: set[EntityId] = set()
    for value in copied:
        if type(value) is not EntityId:
            raise TypeError("observer_ids entries must be EntityId")
        if value in seen:
            raise ValueError("observer_ids must not contain duplicates")
        seen.add(value)
    return copied


def _copy_prior_events(
    values: Sequence[WorldEvent], *, observation_tick: int
) -> tuple[WorldEvent, ...]:
    if isinstance(values, (set, frozenset)):
        raise TypeError("prior_events must be an ordered sequence")
    if isinstance(values, (str, bytes, bytearray)) or not isinstance(
        values, Sequence
    ):
        raise TypeError("prior_events must be an ordered sequence")
    copied = tuple(values)
    seen: set[object] = set()
    for event in copied:
        if type(event) is not WorldEvent:
            raise TypeError("prior_events entries must be WorldEvent")
        require_replayable_event(event)
        if event.event_id in seen:
            raise ValueError("prior_events must not contain duplicate event_id")
        seen.add(event.event_id)
        if event.tick >= observation_tick:
            raise ValueError(
                "prior_events must come from a committed tick before observation"
            )
        if event.occurrence is None:
            raise ValueError("prior_events require occurrence context")
    return copied


def _sorted_locations(
    state: WorldState, location_id: EntityId
) -> tuple[ObservedLocation, ...]:
    location = state.locations.get(location_id)
    if location is None:
        return ()
    return (
        ObservedLocation(entity_id=location.entity_id, name=location.name),
    )


def _sorted_exits(
    state: WorldState, location_id: EntityId
) -> tuple[VisibleExit, ...]:
    location = state.locations.get(location_id)
    if location is None:
        return ()
    exits: list[VisibleExit] = []
    for destination_id in location.adjacent:
        destination = state.locations.get(destination_id)
        if destination is None:
            continue
        exits.append(
            VisibleExit(destination_id=destination_id, name=destination.name)
        )
    exits.sort(key=lambda value: value.destination_id.value)
    return tuple(exits)


def _sorted_items(
    state: WorldState,
    *,
    observer_id: EntityId,
    location_id: EntityId,
    include_ground: bool,
) -> tuple[ObservedItem, ...]:
    selected: list[ObservedItem] = []
    for item_id in sorted(state.items, key=lambda entity: entity.value):
        item = state.items[item_id]
        projected = _project_item(
            item,
            observer_id=observer_id,
            location_id=location_id,
            include_ground=include_ground,
        )
        if projected is not None:
            selected.append(projected)
    return tuple(selected)


def _project_item(
    item: Item,
    *,
    observer_id: EntityId,
    location_id: EntityId,
    include_ground: bool,
) -> ObservedItem | None:
    if item.holder_id == observer_id:
        placement = ObservedItemPlacement.HELD_BY_SELF
    elif include_ground and item.location_id == location_id:
        placement = ObservedItemPlacement.GROUND_HERE
    else:
        return None
    return ObservedItem(
        entity_id=item.entity_id,
        name=item.name,
        kind=item.kind,
        load=item.load,
        placement=placement,
    )


def _sorted_resources(
    state: WorldState, location_id: EntityId
) -> tuple[ObservedResource, ...]:
    selected: list[ObservedResource] = []
    for resource_id in sorted(state.resources, key=lambda entity: entity.value):
        resource = state.resources[resource_id]
        if resource.location_id != location_id:
            continue
        selected.append(
            ObservedResource(
                entity_id=resource.entity_id,
                name=resource.name,
                kind=resource.kind,
                quantity=resource.quantity,
                unit=resource.unit,
            )
        )
    return tuple(selected)


def _sorted_visible_bodies(
    state: WorldState,
    location_id: EntityId,
    observer_id: EntityId,
) -> tuple[VisibleBody, ...]:
    selected: list[VisibleBody] = []
    for body_id in sorted(state.bodies, key=lambda entity: entity.value):
        if body_id == observer_id:
            continue
        body = state.bodies[body_id]
        if body.location_id != location_id:
            continue
        selected.append(
            VisibleBody(
                entity_id=body_id,
                life_status=body.life_status,
                coarse_health=coarse_health_for(body),
            )
        )
    return tuple(selected)


def _project_event_window(
    *,
    observer_id: EntityId,
    location_id: EntityId,
    content_visible: bool,
    prior_events: tuple[WorldEvent, ...],
) -> tuple[tuple[ObservedOccurrence, ...], tuple[ObservedCommunication, ...]]:
    occurrences: list[ObservedOccurrence] = []
    communications: list[ObservedCommunication] = []
    for event in prior_events:
        occurrence = event.occurrence
        assert occurrence is not None
        if _is_communication(event):
            communication = _project_communication(
                event, observer_id=observer_id
            )
            if communication is not None:
                communications.append(communication)
            continue
        role = _audience_role(
            event,
            observer_id=observer_id,
            location_id=location_id,
            content_visible=content_visible,
        )
        if role is None:
            continue
        occurrences.append(
            ObservedOccurrence(
                provenance=ObservationProvenance(
                    source_kind=ObservationSourceKind.OCCURRENCE,
                    source_tick=event.tick,
                    source_event_id=event.event_id,
                ),
                kind=event.event_type,
                audience_role=role,
                actor_id=event.actor_id,
                other_entity_id=_other_entity_for_role(event, role),
                destination_id=occurrence.destination_location_id,
                success=_success_fact(event),
                public_facts=_public_facts_for_role(event, role),
            )
        )
    return tuple(occurrences), tuple(communications)


def _is_communication(event: WorldEvent) -> bool:
    return isinstance(event.details, (Talked, Asked, Told))


def _project_communication(
    event: WorldEvent, *, observer_id: EntityId
) -> ObservedCommunication | None:
    occurrence = event.occurrence
    assert occurrence is not None
    details = event.details
    assert isinstance(details, (Talked, Asked, Told))
    speaker_id = event.actor_id
    if speaker_id is None:
        return None
    listener_id = details.recipient_id
    if observer_id not in {speaker_id, listener_id} and observer_id not in set(
        occurrence.private_recipient_ids
    ):
        return None
    return ObservedCommunication(
        provenance=ObservationProvenance(
            source_kind=ObservationSourceKind.COMMUNICATION,
            source_tick=event.tick,
            source_event_id=event.event_id,
        ),
        speaker_id=speaker_id,
        listener_id=listener_id,
        text=details.text,
    )


def _audience_role(
    event: WorldEvent,
    *,
    observer_id: EntityId,
    location_id: EntityId,
    content_visible: bool,
) -> ObservationAudienceRole | None:
    occurrence = event.occurrence
    assert occurrence is not None
    if event.actor_id == observer_id:
        return ObservationAudienceRole.ACTOR
    if event.target_id == observer_id or observer_id in set(
        occurrence.affected_entity_ids
    ):
        return ObservationAudienceRole.TARGET
    origin = occurrence.origin_location_id
    destination = occurrence.destination_location_id
    at_origin = origin is not None and location_id == origin
    at_destination = destination is not None and location_id == destination
    if not (at_origin or at_destination):
        return None
    # Movement witnesses can observe leave/arrive at the edge even in darkness.
    if destination is not None and (at_origin or at_destination):
        return ObservationAudienceRole.WITNESS
    if not content_visible:
        return None
    return ObservationAudienceRole.BYSTANDER


def _other_entity_for_role(
    event: WorldEvent, role: ObservationAudienceRole
) -> EntityId | None:
    if role in {
        ObservationAudienceRole.BYSTANDER,
        ObservationAudienceRole.WITNESS,
    }:
        return event.target_id if role is ObservationAudienceRole.WITNESS else None
    return event.target_id


def _success_fact(event: WorldEvent) -> bool | None:
    details = event.details
    success = getattr(details, "success", None)
    if type(success) is bool:
        return success
    hit = getattr(details, "hit", None)
    if type(hit) is bool:
        return hit
    return None


def _public_facts_for_role(
    event: WorldEvent, role: ObservationAudienceRole
) -> dict[str, object]:
    facts: dict[str, object] = {"kind": event.event_type}
    if role is ObservationAudienceRole.BYSTANDER:
        return facts
    if event.actor_id is not None:
        facts["actor_id"] = event.actor_id.value
    if event.target_id is not None:
        facts["target_id"] = event.target_id.value
    return facts
