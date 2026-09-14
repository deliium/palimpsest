"""Ports for owner-validating memory and belief writes."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from memory.models import Belief, MemoryRecord, OwnershipError

__all__ = [
    "BeliefReader",
    "BeliefWriter",
    "MemoryReader",
    "MemoryWriter",
    "OwnershipError",
]


class MemoryReader(Protocol):
    def snapshot(self) -> Sequence[MemoryRecord]:
        """Return a defensive immutable snapshot of owned memories."""
        ...


class MemoryWriter(Protocol):
    def write(self, record: MemoryRecord) -> None:
        """Persist ``record`` if it belongs to this aggregate's owner."""
        ...


class BeliefReader(Protocol):
    def snapshot(self) -> Sequence[Belief]:
        """Return a defensive immutable snapshot of owned beliefs."""
        ...


class BeliefWriter(Protocol):
    def write(self, belief: Belief) -> None:
        """Persist ``belief`` if it belongs to this aggregate's owner."""
        ...
