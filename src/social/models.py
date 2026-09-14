"""Opaque immutable communication envelopes."""

from __future__ import annotations

from collections.abc import Mapping, Sequence, Set
from dataclasses import dataclass

from agents.models import AgentId
from world.identifiers import EntityId
from world.observations import detached_mapping


def _require_non_empty(name: str, value: str) -> str:
    if not value:
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _assert_allowed_payload(value: object) -> None:
    if isinstance(value, (str, bytes, int, float, type(None), AgentId, EntityId)):
        return
    if isinstance(value, bool):
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            _assert_allowed_payload(key)
            _assert_allowed_payload(item)
        return
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for item in value:
            _assert_allowed_payload(item)
        return
    if isinstance(value, Set) and not isinstance(value, (str, bytes)):
        for item in value:
            _assert_allowed_payload(item)
        return
    raise TypeError(
        f"communication envelope cannot contain {type(value).__name__}; "
        "memory records, agent state, and mutable/custom objects are forbidden"
    )


@dataclass(frozen=True, slots=True)
class EnvelopeId:
    value: str

    def __post_init__(self) -> None:
        _require_non_empty("EnvelopeId.value", self.value)


@dataclass(frozen=True, slots=True)
class CommunicationEnvelope:
    """Immutable message. Payload cannot hold memories, agent state, or mutables."""

    envelope_id: EnvelopeId
    sender_id: AgentId
    recipient_id: AgentId
    payload: Mapping[str, object]

    def __post_init__(self) -> None:
        _assert_allowed_payload(self.payload)
        object.__setattr__(self, "payload", detached_mapping(self.payload))
