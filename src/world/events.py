"""Immutable objective world events."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from world._freeze import freeze_mapping, require_non_empty
from world.identifiers import EventId, WorldRevision


@dataclass(frozen=True, slots=True)
class WorldEvent:
    """Objective event. Immutable and detached from the producing aggregate."""

    event_id: EventId
    revision: WorldRevision
    kind: str
    payload: Mapping[str, object] = field(compare=True)

    def __post_init__(self) -> None:
        require_non_empty("WorldEvent.kind", self.kind)
        object.__setattr__(self, "payload", freeze_mapping(self.payload))
