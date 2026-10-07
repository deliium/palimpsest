"""Pure projection from a detached objective scene to an observer frame."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal

from observer.contracts import (
    ObserverAgent,
    ObserverArtifact,
    ObserverBodyMeasures,
    ObserverEvent,
    ObserverFrame,
    ObserverHazard,
    ObserverItem,
    ObserverLocation,
    ObserverPlaybackCursor,
    ObserverResource,
    ObserverStructure,
    ObserverTemperatureBand,
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
from observer.presentation import entity_presentation
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
            presentation=entity_presentation(item.kind.value, item.name),
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
            presentation=entity_presentation(item.kind.value, item.name),
        )
        for item in scene.resources
    )
    structures = tuple(
        ObserverStructure(
            structure_id=item.entity_id.value,
            location_id=item.location_id.value,
            kind=item.kind.value,
            integrity=item.integrity,
            stored_quantity=item.stored_quantity,
            presentation=entity_presentation(item.kind.value, item.kind.value),
        )
        for item in sorted(
            scene.structures,
            key=lambda item: (item.location_id.value, item.entity_id.value),
        )
    )
    artifacts = tuple(
        ObserverArtifact(
            artifact_id=item.artifact_id.value,
            kind=item.kind.value,
            author_id=item.author_id.value,
            created_tick=item.created_tick,
            content_revision=item.content_revision,
            location_id=(
                None if item.location_id is None else item.location_id.value
            ),
            holder_id=None if item.holder_id is None else item.holder_id.value,
            marks=tuple(item.content.marks),
            presentation=entity_presentation(item.kind.value, item.kind.value),
            record_genre=(
                None
                if getattr(item, "record_genre", None) is None
                else item.record_genre.value
            ),
            parent_artifact_id=(
                None
                if getattr(item, "parent_artifact_id", None) is None
                else item.parent_artifact_id.value
            ),
            source_artifact_id=(
                None
                if getattr(item, "source_artifact_id", None) is None
                else item.source_artifact_id.value
            ),
            copy_generation=(
                None
                if getattr(item, "record_genre", None) is None
                and getattr(item, "parent_artifact_id", None) is None
                and int(getattr(item, "copy_generation", 0) or 0) == 0
                else int(getattr(item, "copy_generation", 0) or 0)
            ),
            integrity=(
                None
                if getattr(item, "record_genre", None) is None
                and getattr(item, "parent_artifact_id", None) is None
                and int(getattr(item, "copy_generation", 0) or 0) == 0
                and int(getattr(item, "lost_mark_count", 0) or 0) == 0
                and getattr(getattr(item, "integrity", None), "value", "intact")
                == "intact"
                else getattr(getattr(item, "integrity", None), "value", None)
            ),
            annotation_revisions=(
                None
                if getattr(item, "record_genre", None) is None
                and int(getattr(item, "annotation_revisions", 0) or 0) == 0
                else int(getattr(item, "annotation_revisions", 0) or 0)
            ),
            lost_mark_count=(
                None
                if getattr(item, "record_genre", None) is None
                and int(getattr(item, "lost_mark_count", 0) or 0) == 0
                else int(getattr(item, "lost_mark_count", 0) or 0)
            ),
        )
        for item in sorted(
            scene.artifacts,
            key=lambda item: item.artifact_id.value,
        )
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
        structures=structures,
        artifacts=artifacts,
        season=scene.season,
        temperature_bands=tuple(
            ObserverTemperatureBand(location_id=location_id, band=band)
            for location_id, band in scene.temperature_bands
        ),
        hazards=tuple(
            ObserverHazard(
                location_id=location_id,
                hazard_kind=kind,
                remaining_ticks=remaining,
            )
            for location_id, kind, remaining in scene.hazards
        ),
    )
    if scene.season is not None:
        last_kind = "-" if not events else events[-1].domain_kind
        _LOGGER.debug(
            "environment_projected season=%s band_count=%s hazard_count=%s "
            "event_kind=%s",
            scene.season,
            len(scene.temperature_bands),
            len(scene.hazards),
            last_kind,
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
    if structures:
        _LOGGER.debug(
            "production_projected structure_count=%s event_kind=%s",
            len(structures),
            "-" if not events else events[-1].domain_kind,
        )
    _LOGGER.debug(
        "artifacts_projected count=%s event_kind=%s",
        len(artifacts),
        "-" if not events else events[-1].domain_kind,
    )
    return frame


PHYSICAL_CONTROL_SCHEMA: Literal["physical-control-v1"] = "physical-control-v1"


@dataclass(frozen=True, slots=True)
class PhysicalControlLocation:
    """Occupants and items at one location. Possession is not a claim."""

    location_id: str
    agent_ids: tuple[str, ...]
    item_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PhysicalControlDocument:
    """Objective grouping of who is present and what is held."""

    schema_version: str
    authority: str
    locations: tuple[PhysicalControlLocation, ...]


def project_physical_control(frame: ObserverFrame) -> PhysicalControlDocument:
    """Group the objective frame by location. No claim or contest field is read."""
    if type(frame) is not ObserverFrame:
        raise TypeError("project_physical_control requires an observer frame")
    world = frame.world
    agents_at: dict[str, list[str]] = {}
    entity_at: dict[str, str] = {}
    for agent in world.agents:
        agents_at.setdefault(agent.location_id, []).append(agent.entity_id)
        entity_at[agent.entity_id] = agent.location_id
    items_at: dict[str, list[str]] = {}
    for item in world.items:
        site = item.location_id
        if site is None and item.holder_id is not None:
            site = entity_at.get(item.holder_id)
        if site is None:
            continue
        items_at.setdefault(site, []).append(item.item_id)
    location_ids = sorted(
        set(agents_at)
        | set(items_at)
        | {item.location_id for item in world.locations}
    )
    locations = tuple(
        PhysicalControlLocation(
            location_id=location_id,
            agent_ids=tuple(sorted(agents_at.get(location_id, ()))),
            item_ids=tuple(sorted(set(items_at.get(location_id, ())))),
        )
        for location_id in location_ids
    )
    _LOGGER.debug("physical_control_projected locations=%s", len(locations))
    return PhysicalControlDocument(
        schema_version=PHYSICAL_CONTROL_SCHEMA,
        authority="physical_possession",
        locations=locations,
    )


__all__ = [
    "PHYSICAL_CONTROL_SCHEMA",
    "PhysicalControlDocument",
    "PhysicalControlLocation",
    "project_frame",
    "project_physical_control",
]
