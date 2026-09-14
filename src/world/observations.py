"""Deeply immutable observations delivered to agents."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from world._freeze import freeze_mapping
from world.identifiers import EntityId, WorldRevision


def detached_mapping(value: Mapping[str, object]) -> Mapping[str, object]:
    """Return a deeply immutable copy detached from the caller's containers."""
    return freeze_mapping(value)


@dataclass(frozen=True, slots=True)
class Observation:
    """Agent-facing snapshot. Nested containers are detached from the source."""

    observer_id: EntityId
    revision: WorldRevision
    payload: Mapping[str, object] = field(compare=True)

    def __post_init__(self) -> None:
        object.__setattr__(self, "payload", detached_mapping(self.payload))
