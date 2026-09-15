"""Typed action proposals, trusted requests, and outcomes.

Concrete action kinds and resolution behavior are deferred. A trusted
world gateway accepts :class:`ActionRequest` only.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol, runtime_checkable

from world._freeze import freeze_mapping, require_non_empty
from world.identifiers import EntityId, ProposalId, RequestId, WorldRevision


class OutcomeCategory(StrEnum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    INVALID = "invalid"


@dataclass(frozen=True, slots=True)
class ActionProposal:
    """Non-authoritative proposal produced by cognition. Never mutates the world."""

    proposal_id: ProposalId
    actor_id: EntityId
    kind: str
    payload: Mapping[str, object] = field(compare=True)

    def __post_init__(self) -> None:
        require_non_empty("ActionProposal.kind", self.kind)
        object.__setattr__(self, "payload", freeze_mapping(self.payload))


@dataclass(frozen=True, slots=True)
class ActionRequest:
    """Trusted request accepted only by a world gateway."""

    request_id: RequestId
    actor_id: EntityId
    kind: str
    revision: WorldRevision
    payload: Mapping[str, object] = field(compare=True)

    def __post_init__(self) -> None:
        require_non_empty("ActionRequest.kind", self.kind)
        object.__setattr__(self, "payload", freeze_mapping(self.payload))


@dataclass(frozen=True, slots=True)
class ActionOutcome:
    request_id: RequestId
    category: OutcomeCategory
    revision: WorldRevision


@runtime_checkable
class WorldGateway(Protocol):
    """Trusted world entry point. Must call :func:`accept_action_request`."""

    def submit(self, request: ActionRequest) -> ActionOutcome:
        """Apply a trusted request and return an outcome category."""
        ...


def accept_action_request(value: object) -> ActionRequest:
    """Reject proposals and raw mappings; only :class:`ActionRequest` is trusted."""
    if isinstance(value, ActionProposal):
        raise TypeError("ActionProposal cannot be submitted to the world gateway")
    if isinstance(value, Mapping):
        raise TypeError("raw mappings cannot be submitted to the world gateway")
    if not isinstance(value, ActionRequest):
        raise TypeError(
            f"world gateway accepts ActionRequest, not {type(value).__name__}"
        )
    return value
