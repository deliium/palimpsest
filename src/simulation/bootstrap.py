"""Public immutable world bootstrap and agent registration boundary.

Bootstrap values validate at construction and never expose private ``World`` /
``WorldState`` in public annotations. Engine materialization stays internal.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import TYPE_CHECKING

from agents.models import AgentId
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import AgentBody, Item, Location, Resource, Weather

if TYPE_CHECKING:
    from world._state import World

__all__ = [
    "AgentRegistration",
    "RegistrationTranslator",
    "WorldBootstrap",
    "registration_translator",
]


@dataclass(frozen=True, slots=True)
class AgentRegistration:
    """Ordered AgentId to body EntityId binding for one simulation participant."""

    agent_id: AgentId
    entity_id: EntityId

    def __post_init__(self) -> None:
        if type(self.agent_id) is not AgentId:
            raise TypeError("AgentRegistration.agent_id must be AgentId")
        if type(self.entity_id) is not EntityId:
            raise TypeError("AgentRegistration.entity_id must be EntityId")


@dataclass(frozen=True, slots=True)
class RegistrationTranslator:
    """Deterministic IdentityTranslator derived from ordered registrations."""

    _forward: Mapping[AgentId, EntityId]
    _reverse: Mapping[EntityId, AgentId]
    _order: tuple[AgentRegistration, ...]

    def to_entity_id(self, agent_id: AgentId) -> EntityId:
        if type(agent_id) is not AgentId:
            raise TypeError("to_entity_id requires AgentId")
        try:
            return self._forward[agent_id]
        except KeyError as exc:
            raise KeyError(f"unknown agent_id {agent_id.value!r}") from exc

    def to_agent_id(self, entity_id: EntityId) -> AgentId:
        if type(entity_id) is not EntityId:
            raise TypeError("to_agent_id requires EntityId")
        try:
            return self._reverse[entity_id]
        except KeyError as exc:
            raise KeyError(f"unknown entity_id {entity_id.value!r}") from exc

    @property
    def ordered_registrations(self) -> tuple[AgentRegistration, ...]:
        return self._order


@dataclass(frozen=True, slots=True)
class WorldBootstrap:
    """Public factory input for WorldEngine. Contains no private authority types.

    Dead bodies may be registered for observation/history but cannot act once
    the engine enforces life status. Registration order is canonical for later
    observation and admission sequencing.
    """

    world_id: WorldId
    revision: WorldRevision
    locations: Sequence[Location] = field(default_factory=tuple)
    items: Sequence[Item] = field(default_factory=tuple)
    resources: Sequence[Resource] = field(default_factory=tuple)
    bodies: Sequence[AgentBody] = field(default_factory=tuple)
    weather: Sequence[Weather] = field(default_factory=tuple)
    registrations: Sequence[AgentRegistration] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if type(self.world_id) is not WorldId:
            raise TypeError("WorldBootstrap.world_id must be WorldId")
        if type(self.revision) is not WorldRevision:
            raise TypeError("WorldBootstrap.revision must be WorldRevision")
        locations = _copy_models(
            "WorldBootstrap.locations", self.locations, model_type=Location
        )
        items = _copy_models("WorldBootstrap.items", self.items, model_type=Item)
        resources = _copy_models(
            "WorldBootstrap.resources", self.resources, model_type=Resource
        )
        bodies = _copy_models(
            "WorldBootstrap.bodies", self.bodies, model_type=AgentBody
        )
        weather = _copy_models(
            "WorldBootstrap.weather", self.weather, model_type=Weather
        )
        registrations = _copy_registrations(
            "WorldBootstrap.registrations", self.registrations
        )
        object.__setattr__(self, "locations", locations)
        object.__setattr__(self, "items", items)
        object.__setattr__(self, "resources", resources)
        object.__setattr__(self, "bodies", bodies)
        object.__setattr__(self, "weather", weather)
        object.__setattr__(self, "registrations", registrations)
        _validate_registrations_against_models(
            locations=locations,
            items=items,
            resources=resources,
            bodies=bodies,
            registrations=registrations,
        )
        # Reuse authoritative graph validation without exposing WorldState.
        from world._state import WorldState

        WorldState(
            self.revision,
            locations=locations,
            items=items,
            resources=resources,
            bodies=bodies,
            weather=weather,
        )
        translator = registration_translator(self)
        for registration in registrations:
            entity_id = translator.to_entity_id(registration.agent_id)
            if entity_id != registration.entity_id:
                raise ValueError("registration translator forward mismatch")
            if translator.to_agent_id(entity_id) != registration.agent_id:
                raise ValueError("registration translator round-trip mismatch")


def registration_translator(bootstrap: WorldBootstrap) -> RegistrationTranslator:
    """Build a deterministic translator from a validated bootstrap."""
    if type(bootstrap) is not WorldBootstrap:
        raise TypeError("registration_translator requires WorldBootstrap")
    return _translator_from_registrations(bootstrap.registrations)


def _materialize_world(bootstrap: WorldBootstrap) -> World:
    """Internal: construct private World authority from a validated bootstrap."""
    from world._state import World, WorldState

    if type(bootstrap) is not WorldBootstrap:
        raise TypeError("_materialize_world requires WorldBootstrap")
    state = WorldState(
        bootstrap.revision,
        locations=bootstrap.locations,
        items=bootstrap.items,
        resources=bootstrap.resources,
        bodies=bootstrap.bodies,
        weather=bootstrap.weather,
    )
    return World(bootstrap.world_id, state)


def _bootstrap_from_snapshot(snapshot: object) -> WorldBootstrap:
    """Internal: derive a WorldBootstrap view from an immutable checkpoint."""
    from simulation.persistence import WorldSnapshot

    if type(snapshot) is not WorldSnapshot:
        raise TypeError("_bootstrap_from_snapshot requires WorldSnapshot")
    return WorldBootstrap(
        world_id=snapshot.world_id,
        revision=snapshot.revision,
        locations=snapshot.locations,
        items=snapshot.items,
        resources=snapshot.resources,
        bodies=snapshot.bodies,
        weather=snapshot.weather,
        registrations=snapshot.registrations,
    )


def _materialize_projected_world(
    *, world_id: WorldId, state: object
) -> World:
    """Internal: wrap a projected ``WorldState`` without a mutation hook."""
    from world._state import World, WorldState

    if type(world_id) is not WorldId:
        raise TypeError("world_id must be WorldId")
    if type(state) is not WorldState:
        raise TypeError("state must be WorldState")
    return World(world_id, state)


def _translator_from_registrations(
    registrations: Sequence[AgentRegistration],
) -> RegistrationTranslator:
    forward: dict[AgentId, EntityId] = {}
    reverse: dict[EntityId, AgentId] = {}
    order = tuple(registrations)
    for registration in order:
        if registration.agent_id in forward:
            raise ValueError(
                f"duplicate agent_id in registrations "
                f"{registration.agent_id.value!r}"
            )
        if registration.entity_id in reverse:
            raise ValueError(
                f"duplicate entity_id in registrations "
                f"{registration.entity_id.value!r}"
            )
        forward[registration.agent_id] = registration.entity_id
        reverse[registration.entity_id] = registration.agent_id
    return RegistrationTranslator(
        _forward=MappingProxyType(forward),
        _reverse=MappingProxyType(reverse),
        _order=order,
    )


def _validate_registrations_against_models(
    *,
    locations: Sequence[Location],
    items: Sequence[Item],
    resources: Sequence[Resource],
    bodies: Sequence[AgentBody],
    registrations: Sequence[AgentRegistration],
) -> None:
    body_ids = {body.entity_id for body in bodies}
    location_ids = {location.entity_id for location in locations}
    item_ids = {item.entity_id for item in items}
    resource_ids = {resource.entity_id for resource in resources}
    _translator_from_registrations(registrations)
    for registration in registrations:
        entity_id = registration.entity_id
        if entity_id in location_ids:
            raise ValueError(
                f"registration entity_id {entity_id.value!r} refers to a location"
            )
        if entity_id in item_ids:
            raise ValueError(
                f"registration entity_id {entity_id.value!r} refers to an item"
            )
        if entity_id in resource_ids:
            raise ValueError(
                f"registration entity_id {entity_id.value!r} refers to a resource"
            )
        if entity_id not in body_ids:
            raise ValueError(
                f"registration entity_id {entity_id.value!r} has no matching body"
            )


def _copy_models[T](
    name: str, values: Sequence[T], *, model_type: type[T]
) -> tuple[T, ...]:
    if isinstance(values, (set, frozenset, Mapping)):
        raise TypeError(f"{name} must be an ordered sequence")
    if isinstance(values, (str, bytes, bytearray)) or not isinstance(values, Sequence):
        raise TypeError(f"{name} must be an ordered sequence")
    copied = tuple(values)
    for value in copied:
        if type(value) is not model_type:
            raise TypeError(f"{name} entries must be {model_type.__name__}")
    return copied


def _copy_registrations(
    name: str, values: Sequence[AgentRegistration]
) -> tuple[AgentRegistration, ...]:
    if isinstance(values, (set, frozenset, Mapping)):
        raise TypeError(f"{name} must be an ordered sequence")
    if isinstance(values, (str, bytes, bytearray)) or not isinstance(values, Sequence):
        raise TypeError(f"{name} must be an ordered sequence")
    copied = tuple(values)
    for value in copied:
        if type(value) is not AgentRegistration:
            raise TypeError(f"{name} entries must be AgentRegistration")
    return copied
