"""Owner-bound memory and belief aggregates."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from agents.models import AgentId
from world.observations import detached_mapping


class OwnershipError(PermissionError):
    """Raised when a write targets a different owner than the aggregate."""


def _require_non_empty(name: str, value: str) -> str:
    if not value:
        raise ValueError(f"{name} must be a non-empty string")
    return value


@dataclass(frozen=True, slots=True)
class MemoryId:
    value: str

    def __post_init__(self) -> None:
        _require_non_empty("MemoryId.value", self.value)


@dataclass(frozen=True, slots=True)
class BeliefId:
    value: str

    def __post_init__(self) -> None:
        _require_non_empty("BeliefId.value", self.value)


@dataclass(frozen=True, slots=True)
class MemoryRecord:
    """Immutable memory snapshot. Nested payload is detached from the source."""

    memory_id: MemoryId
    owner_id: AgentId
    content: Mapping[str, object]

    def __post_init__(self) -> None:
        object.__setattr__(self, "content", detached_mapping(self.content))


@dataclass(frozen=True, slots=True)
class Belief:
    """Immutable belief snapshot. Nested payload is detached from the source."""

    belief_id: BeliefId
    owner_id: AgentId
    content: Mapping[str, object]

    def __post_init__(self) -> None:
        object.__setattr__(self, "content", detached_mapping(self.content))


class MemoryStore:
    """Mutable memory aggregate bound to a single owner."""

    __slots__ = ("_owner_id", "_records")

    def __init__(self, owner_id: AgentId) -> None:
        self._owner_id = owner_id
        self._records: dict[MemoryId, MemoryRecord] = {}

    @property
    def owner_id(self) -> AgentId:
        return self._owner_id

    def snapshot(self) -> tuple[MemoryRecord, ...]:
        return tuple(self._records.values())

    def write(self, record: MemoryRecord) -> None:
        if record.owner_id != self._owner_id:
            raise OwnershipError(
                f"memory write owner {record.owner_id.value!r} does not match "
                f"store owner {self._owner_id.value!r}"
            )
        self._records[record.memory_id] = MemoryRecord(
            memory_id=record.memory_id,
            owner_id=record.owner_id,
            content=dict(record.content),
        )


class BeliefStore:
    """Mutable belief aggregate bound to a single owner."""

    __slots__ = ("_beliefs", "_owner_id")

    def __init__(self, owner_id: AgentId) -> None:
        self._owner_id = owner_id
        self._beliefs: dict[BeliefId, Belief] = {}

    @property
    def owner_id(self) -> AgentId:
        return self._owner_id

    def snapshot(self) -> tuple[Belief, ...]:
        return tuple(self._beliefs.values())

    def write(self, belief: Belief) -> None:
        if belief.owner_id != self._owner_id:
            raise OwnershipError(
                f"belief write owner {belief.owner_id.value!r} does not match "
                f"store owner {self._owner_id.value!r}"
            )
        self._beliefs[belief.belief_id] = Belief(
            belief_id=belief.belief_id,
            owner_id=belief.owner_id,
            content=dict(belief.content),
        )
