"""Owner-bound memory and belief aggregates."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass

from agents.models import AgentId
from world.identifiers import (
    WorldRevision,
    require_bounded_text,
    require_ordered_unique,
    require_stable_id,
)
from world.observations import detached_mapping


class OwnershipError(PermissionError):
    """Raised when a write targets a different owner than the aggregate."""


def _unit_interval(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite float in [0.0, 1.0]")
    number = float(value)
    if not math.isfinite(number) or number < 0.0 or number > 1.0:
        raise ValueError(f"{name} must be a finite float in [0.0, 1.0]")
    return 0.0 if number == 0.0 else number


@dataclass(frozen=True, slots=True)
class MemoryId:
    value: str

    def __post_init__(self) -> None:
        require_stable_id("MemoryId.value", self.value)


@dataclass(frozen=True, slots=True)
class BeliefId:
    value: str

    def __post_init__(self) -> None:
        require_stable_id("BeliefId.value", self.value)


@dataclass(frozen=True, slots=True)
class MemoryTrace:
    """Immutable memory snapshot. Nested payload is detached from the source."""

    memory_id: MemoryId
    owner_id: AgentId
    world_revision: WorldRevision
    content: Mapping[str, object]

    def __post_init__(self) -> None:
        if type(self.memory_id) is not MemoryId:
            raise TypeError("MemoryTrace.memory_id must be MemoryId")
        if type(self.owner_id) is not AgentId:
            raise TypeError("MemoryTrace.owner_id must be AgentId")
        if type(self.world_revision) is not WorldRevision:
            raise TypeError("MemoryTrace.world_revision must be WorldRevision")
        object.__setattr__(self, "content", detached_mapping(self.content))


@dataclass(frozen=True, slots=True)
class Belief:
    """Immutable belief snapshot with confidence and evidence links."""

    belief_id: BeliefId
    owner_id: AgentId
    proposition: str
    confidence: float
    evidence_memory_ids: tuple[MemoryId, ...]

    def __post_init__(self) -> None:
        if type(self.belief_id) is not BeliefId:
            raise TypeError("Belief.belief_id must be BeliefId")
        if type(self.owner_id) is not AgentId:
            raise TypeError("Belief.owner_id must be AgentId")
        require_bounded_text("Belief.proposition", self.proposition)
        object.__setattr__(
            self, "confidence", _unit_interval("Belief.confidence", self.confidence)
        )
        evidence = require_ordered_unique(
            "Belief.evidence_memory_ids",
            self.evidence_memory_ids,
            item_type=MemoryId,
        )
        object.__setattr__(self, "evidence_memory_ids", evidence)


class MemoryStore:
    """Mutable memory aggregate bound to a single owner."""

    __slots__ = ("_owner_id", "_records")

    def __init__(self, owner_id: AgentId) -> None:
        self._owner_id = owner_id
        self._records: dict[MemoryId, MemoryTrace] = {}

    @property
    def owner_id(self) -> AgentId:
        return self._owner_id

    def snapshot(self) -> tuple[MemoryTrace, ...]:
        return tuple(self._records.values())

    def write(self, record: MemoryTrace) -> None:
        if type(record) is not MemoryTrace:
            raise TypeError("MemoryStore.write requires MemoryTrace")
        if record.owner_id != self._owner_id:
            raise OwnershipError(
                f"memory write owner {record.owner_id.value!r} does not match "
                f"store owner {self._owner_id.value!r}"
            )
        self._records[record.memory_id] = MemoryTrace(
            memory_id=record.memory_id,
            owner_id=record.owner_id,
            world_revision=record.world_revision,
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
        if type(belief) is not Belief:
            raise TypeError("BeliefStore.write requires Belief")
        if belief.owner_id != self._owner_id:
            raise OwnershipError(
                f"belief write owner {belief.owner_id.value!r} does not match "
                f"store owner {self._owner_id.value!r}"
            )
        self._beliefs[belief.belief_id] = Belief(
            belief_id=belief.belief_id,
            owner_id=belief.owner_id,
            proposition=belief.proposition,
            confidence=belief.confidence,
            evidence_memory_ids=belief.evidence_memory_ids,
        )
