"""Ports for typed communication envelopes and subjective relationships."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from agents.models import AgentId
from social.models import CommunicationEnvelope, RelationshipId
from social.relationships import (
    DirectedRelationshipProfile,
    RelationshipHistory,
    RelationshipRevisionRequest,
    RelationshipRevisionResult,
)

__all__ = [
    "EnvelopeSender",
    "RelationshipReader",
    "RelationshipService",
    "RelationshipWriter",
]


class EnvelopeSender(Protocol):
    def send(self, envelope: CommunicationEnvelope) -> None:
        """Transmit an immutable envelope. Must not share mutable payloads."""
        ...


class RelationshipReader(Protocol):
    def snapshot(self) -> tuple[DirectedRelationshipProfile, ...]:
        """Return directed profiles owned by the bound source."""
        ...

    def history(self, relationship_id: RelationshipId) -> RelationshipHistory | None:
        """Return append-only history for one directed profile."""
        ...


class RelationshipWriter(Protocol):
    def write(self, history: RelationshipHistory) -> None:
        """Persist history if it belongs to this source aggregate."""
        ...


@runtime_checkable
class RelationshipService(Protocol):
    """Owner-bound directed relationship revision service."""

    @property
    def source_id(self) -> AgentId:
        """Fixed source agent for this service instance."""
        ...

    async def revise(
        self, request: RelationshipRevisionRequest
    ) -> RelationshipRevisionResult:
        """Revise one directed profile; never mutates the reverse direction."""
        ...

    async def get(
        self, relationship_id: RelationshipId
    ) -> DirectedRelationshipProfile | None: ...

    async def snapshot(self) -> tuple[DirectedRelationshipProfile, ...]: ...
