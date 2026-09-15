"""Deeply immutable observations delivered to agents."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from world._freeze import freeze_mapping
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import AgentBody, Item, Location, Resource, Weather


def detached_mapping(value: Mapping[str, object]) -> Mapping[str, object]:
    """Return a deeply immutable copy detached from the caller's containers."""
    return freeze_mapping(value)


def _copy_models(
    name: str, values: Sequence[object], *, model_type: type
) -> tuple[object, ...]:
    if isinstance(values, (set, frozenset, Mapping)):
        raise TypeError(f"{name} must be an ordered sequence")
    if isinstance(values, (str, bytes, bytearray)) or not isinstance(values, Sequence):
        raise TypeError(f"{name} must be an ordered sequence")
    copied = tuple(values)
    for value in copied:
        if type(value) is not model_type:
            raise TypeError(f"{name} entries must be {model_type.__name__}")
    return copied


@dataclass(frozen=True, slots=True)
class Observation:
    """Typed partial projection. Nested values are detached from the source."""

    world_id: WorldId
    observer_id: EntityId
    revision: WorldRevision
    self_body: AgentBody | None = None
    locations: Sequence[Location] = field(default_factory=tuple)
    items: Sequence[Item] = field(default_factory=tuple)
    resources: Sequence[Resource] = field(default_factory=tuple)
    weather: Sequence[Weather] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if type(self.world_id) is not WorldId:
            raise TypeError("Observation.world_id must be WorldId")
        if type(self.observer_id) is not EntityId:
            raise TypeError("Observation.observer_id must be EntityId")
        if type(self.revision) is not WorldRevision:
            raise TypeError("Observation.revision must be WorldRevision")
        if self.self_body is not None and type(self.self_body) is not AgentBody:
            raise TypeError("Observation.self_body must be AgentBody or None")
        object.__setattr__(
            self,
            "locations",
            _copy_models("Observation.locations", self.locations, model_type=Location),
        )
        object.__setattr__(
            self,
            "items",
            _copy_models("Observation.items", self.items, model_type=Item),
        )
        object.__setattr__(
            self,
            "resources",
            _copy_models(
                "Observation.resources", self.resources, model_type=Resource
            ),
        )
        object.__setattr__(
            self,
            "weather",
            _copy_models("Observation.weather", self.weather, model_type=Weather),
        )
        if self.self_body is not None and self.self_body.entity_id != self.observer_id:
            raise ValueError("Observation.self_body must match observer_id")
