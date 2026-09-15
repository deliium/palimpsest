"""Opaque immutable communication envelopes and relationships."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass

from agents.models import AgentId
from world.identifiers import require_bounded_text, require_stable_id
from world.observations import detached_mapping


def _affinity(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite float in [-1.0, 1.0]")
    number = float(value)
    if not math.isfinite(number) or number < -1.0 or number > 1.0:
        raise ValueError(f"{name} must be a finite float in [-1.0, 1.0]")
    return 0.0 if number == 0.0 else number


@dataclass(frozen=True, slots=True)
class EnvelopeId:
    value: str

    def __post_init__(self) -> None:
        require_stable_id("EnvelopeId.value", self.value)


@dataclass(frozen=True, slots=True)
class RelationshipId:
    """Stable identity for a directed agent relationship."""

    value: str

    def __post_init__(self) -> None:
        require_stable_id("RelationshipId.value", self.value)


@dataclass(frozen=True, slots=True)
class Relationship:
    """Constructor-only directed relationship between distinct agents."""

    relationship_id: RelationshipId
    source_id: AgentId
    target_id: AgentId
    kind: str
    affinity: float

    def __post_init__(self) -> None:
        if type(self.relationship_id) is not RelationshipId:
            raise TypeError("Relationship.relationship_id must be RelationshipId")
        if type(self.source_id) is not AgentId:
            raise TypeError("Relationship.source_id must be AgentId")
        if type(self.target_id) is not AgentId:
            raise TypeError("Relationship.target_id must be AgentId")
        if self.source_id == self.target_id:
            raise ValueError("Relationship cannot link an agent to itself")
        require_bounded_text("Relationship.kind", self.kind, max_length=128)
        object.__setattr__(
            self, "affinity", _affinity("Relationship.affinity", self.affinity)
        )


@dataclass(frozen=True, slots=True)
class CommunicationEnvelope:
    """Immutable message. Payload uses the closed domain content grammar."""

    envelope_id: EnvelopeId
    sender_id: AgentId
    recipient_id: AgentId
    payload: Mapping[str, object]

    def __post_init__(self) -> None:
        object.__setattr__(self, "payload", detached_mapping(self.payload))
