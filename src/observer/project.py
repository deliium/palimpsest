"""Pure projection from a detached objective scene to an observer frame."""

from __future__ import annotations

import logging
from typing import Literal

from observer.contracts import (
    ObserverAgent,
    ObserverBodyMeasures,
    ObserverEvent,
    ObserverFrame,
    ObserverItem,
    ObserverLocation,
    ObserverPlaybackCursor,
    ObserverResource,
    ObserverWeather,
    ObserverWorldState,
    PresentationSlot,
)
from observer.layout import (
    ObserverLayoutCatalog,
    assign_slots,
    presentation_for,
    validate_layout,
    warn_missing_specs,
)
from observer.version import OBSERVER_PROTOCOL_VERSION
from simulation.bootstrap import AgentRegistration
from simulation.observer_facts import ObjectiveScene

_LOGGER = logging.getLogger("observer.project")


def project_frame(
    scene: ObjectiveScene,
    layout: ObserverLayoutCatalog,
    *,
    mode: Literal["live", "replay"],
    events: tuple[ObserverEvent, ...] | None = None,
) -> ObserverFrame:
    if type(scene) is not ObjectiveScene:
        raise TypeError("project_frame requires ObjectiveScene")
    if type(layout) is not ObserverLayoutCatalog:
        raise TypeError("project_frame requires ObserverLayoutCatalog")
    if mode not in ("live", "replay"):
        raise ValueError("invalid_mode")
    validate_layout(layout, scene.locations)
    warn_missing_specs(layout, tuple(item.entity_id.value for item in scene.locations))
    by_entity = {
        registration.entity_id.value: registration.agent_id.value
        for registration in scene.registrations
        if type(registration) is AgentRegistration
    }
    slots_by_entity: dict[str, PresentationSlot] = {}
    for location in scene.locations:
        occupants = tuple(
            body.entity_id.value
            for body in scene.bodies
            if body.location_id == location.entity_id
        )
        spec = layout.spec_for(location.entity_id.value)
        for slot in assign_slots(location.entity_id.value, occupants, spec):
            slots_by_entity[slot.entity_id] = PresentationSlot(
                slot_index=slot.slot_index,
                local_x=slot.local_x,
                local_y=slot.local_y,
            )
    locations: list[ObserverLocation] = []
    for location in scene.locations:
        spec = layout.spec_for(location.entity_id.value)
        presentation = None if spec is None else presentation_for(spec)
        display_name = location.name if spec is None else spec.display_name
        locations.append(
            ObserverLocation(
                location_id=location.entity_id.value,
                name=location.name,
                display_name=display_name,
                neighbor_ids=tuple(item.value for item in location.adjacent),
                presentation=presentation,
            )
        )
    agents: list[ObserverAgent] = []
    for body in scene.bodies:
        agent_id = by_entity.get(body.entity_id.value)
        if agent_id is None:
            _LOGGER.warning(
                "unregistered_body reason_code=%s entity_id=%s",
                "unregistered_body",
                body.entity_id.value,
            )
        agents.append(
            ObserverAgent(
                agent_id=agent_id,
                entity_id=body.entity_id.value,
                location_id=body.location_id.value,
                life_status=body.life_status.value,
                inventory_ids=tuple(item.value for item in body.inventory),
                measures=ObserverBodyMeasures(
                    health=body.health.value,
                    hunger=body.hunger.value,
                    thirst=body.thirst.value,
                    fatigue=body.fatigue.value,
                    temperature=body.temperature.value,
                ),
                presentation_slot=slots_by_entity.get(body.entity_id.value),
            )
        )
    items = tuple(
        ObserverItem(
            item_id=item.entity_id.value,
            name=item.name,
            kind=item.kind.value,
            location_id=None if item.location_id is None else item.location_id.value,
            holder_id=None if item.holder_id is None else item.holder_id.value,
        )
        for item in scene.items
    )
    resources = tuple(
        ObserverResource(
            resource_id=item.entity_id.value,
            name=item.name,
            kind=item.kind.value,
            location_id=item.location_id.value,
            quantity=item.quantity,
            unit=item.unit,
        )
        for item in scene.resources
    )
    weather = tuple(
        ObserverWeather(
            location_id=item.location_id.value,
            condition=item.condition.value,
        )
        for item in scene.weather
    )
    world = ObserverWorldState(
        tick=scene.tick,
        revision=scene.revision,
        locations=tuple(locations),
        agents=tuple(agents),
        items=items,
        resources=resources,
        weather=weather,
    )
    last = None if not events else events[-1]
    cursor = ObserverPlaybackCursor(
        run_id=scene.run_id,
        mode=mode,
        tick=scene.tick,
        sequence=None if last is None else last.sequence,
        protocol_version=OBSERVER_PROTOCOL_VERSION,
        after_tick=None if last is None else last.tick,
        after_sequence=None if last is None else last.sequence,
    )
    frame = ObserverFrame(
        protocol_version=OBSERVER_PROTOCOL_VERSION,
        cursor=cursor,
        world=world,
        events=events,
    )
    _LOGGER.debug(
        "observer_frame_projected run_id=%s tick=%s mode=%s "
        "agent_count=%s location_count=%s",
        scene.run_id,
        scene.tick,
        mode,
        len(agents),
        len(locations),
    )
    return frame


__all__ = ["project_frame"]
