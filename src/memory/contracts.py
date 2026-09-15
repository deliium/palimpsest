"""Ports for owner-validating memory and belief writes."""

from __future__ import annotations

from typing import Protocol

from memory.models import Belief, MemoryTrace, OwnershipError

__all__ = [
    "BeliefReader",
    "BeliefWriter",
    "MemoryReader",
    "MemoryWriter",
    "OwnershipError",
]


class MemoryReader(Protocol):
    def snapshot(self) -> tuple[MemoryTrace, ...]:
        """Return a defensive immutable snapshot of owned memories."""
        ...


class MemoryWriter(Protocol):
    def write(self, record: MemoryTrace) -> None:
        """Persist ``record`` if it belongs to this aggregate's owner."""
        ...


class BeliefReader(Protocol):
    def snapshot(self) -> tuple[Belief, ...]:
        """Return a defensive immutable snapshot of owned beliefs."""
        ...


class BeliefWriter(Protocol):
    def write(self, belief: Belief) -> None:
        """Persist ``belief`` if it belongs to this aggregate's owner."""
        ...
