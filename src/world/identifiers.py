"""Opaque world identifiers. These are not operational request IDs or UUIDs."""

from __future__ import annotations

from dataclasses import dataclass

from world._freeze import require_non_empty


@dataclass(frozen=True, slots=True)
class EntityId:
    """Opaque world identity. Agents never mint or inspect internal structure."""

    value: str

    def __post_init__(self) -> None:
        require_non_empty("EntityId.value", self.value)


@dataclass(frozen=True, slots=True)
class WorldRevision:
    """Monotonic world revision token. Not a wall-clock or HTTP correlation ID."""

    value: int

    def __post_init__(self) -> None:
        if isinstance(self.value, bool) or self.value < 0:
            raise ValueError("WorldRevision.value must be a non-negative integer")
