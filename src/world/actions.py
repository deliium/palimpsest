"""Closed agent commands, non-authoritative proposals, and requests.

Commands and proposals carry no actor authority. Only a later private
world validation step promotes a request to an authority-bearing operation.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Final, Literal, Protocol, runtime_checkable

from world.identifiers import (
    EntityId,
    ProposalId,
    RequestId,
    WorldId,
    WorldRevision,
    require_bounded_text,
)


@dataclass(frozen=True, slots=True)
class Move:
    destination_id: EntityId
    kind: Literal["move"] = field(default="move", init=False)

    def __post_init__(self) -> None:
        if type(self.destination_id) is not EntityId:
            raise TypeError("Move.destination_id must be EntityId")


@dataclass(frozen=True, slots=True)
class Search:
    target_id: EntityId | None = None
    kind: Literal["search"] = field(default="search", init=False)

    def __post_init__(self) -> None:
        if self.target_id is not None and type(self.target_id) is not EntityId:
            raise TypeError("Search.target_id must be EntityId or None")


@dataclass(frozen=True, slots=True)
class Take:
    item_id: EntityId
    kind: Literal["take"] = field(default="take", init=False)

    def __post_init__(self) -> None:
        if type(self.item_id) is not EntityId:
            raise TypeError("Take.item_id must be EntityId")


@dataclass(frozen=True, slots=True)
class Drop:
    item_id: EntityId
    kind: Literal["drop"] = field(default="drop", init=False)

    def __post_init__(self) -> None:
        if type(self.item_id) is not EntityId:
            raise TypeError("Drop.item_id must be EntityId")


@dataclass(frozen=True, slots=True)
class Give:
    recipient_id: EntityId
    item_id: EntityId
    kind: Literal["give"] = field(default="give", init=False)

    def __post_init__(self) -> None:
        if type(self.recipient_id) is not EntityId:
            raise TypeError("Give.recipient_id must be EntityId")
        if type(self.item_id) is not EntityId:
            raise TypeError("Give.item_id must be EntityId")


@dataclass(frozen=True, slots=True)
class Eat:
    item_id: EntityId
    kind: Literal["eat"] = field(default="eat", init=False)

    def __post_init__(self) -> None:
        if type(self.item_id) is not EntityId:
            raise TypeError("Eat.item_id must be EntityId")


@dataclass(frozen=True, slots=True)
class Drink:
    source_id: EntityId
    kind: Literal["drink"] = field(default="drink", init=False)

    def __post_init__(self) -> None:
        if type(self.source_id) is not EntityId:
            raise TypeError("Drink.source_id must be EntityId")


@dataclass(frozen=True, slots=True)
class Sleep:
    kind: Literal["sleep"] = field(default="sleep", init=False)


@dataclass(frozen=True, slots=True)
class Talk:
    recipient_id: EntityId
    text: str
    kind: Literal["talk"] = field(default="talk", init=False)

    def __post_init__(self) -> None:
        if type(self.recipient_id) is not EntityId:
            raise TypeError("Talk.recipient_id must be EntityId")
        require_bounded_text("Talk.text", self.text)


@dataclass(frozen=True, slots=True)
class Ask:
    recipient_id: EntityId
    text: str
    kind: Literal["ask"] = field(default="ask", init=False)

    def __post_init__(self) -> None:
        if type(self.recipient_id) is not EntityId:
            raise TypeError("Ask.recipient_id must be EntityId")
        require_bounded_text("Ask.text", self.text)


@dataclass(frozen=True, slots=True)
class Tell:
    recipient_id: EntityId
    text: str
    kind: Literal["tell"] = field(default="tell", init=False)

    def __post_init__(self) -> None:
        if type(self.recipient_id) is not EntityId:
            raise TypeError("Tell.recipient_id must be EntityId")
        require_bounded_text("Tell.text", self.text)


@dataclass(frozen=True, slots=True)
class Help:
    target_id: EntityId
    kind: Literal["help"] = field(default="help", init=False)

    def __post_init__(self) -> None:
        if type(self.target_id) is not EntityId:
            raise TypeError("Help.target_id must be EntityId")


@dataclass(frozen=True, slots=True)
class Attack:
    target_id: EntityId
    kind: Literal["attack"] = field(default="attack", init=False)

    def __post_init__(self) -> None:
        if type(self.target_id) is not EntityId:
            raise TypeError("Attack.target_id must be EntityId")


@dataclass(frozen=True, slots=True)
class Flee:
    threat_id: EntityId | None = None
    kind: Literal["flee"] = field(default="flee", init=False)

    def __post_init__(self) -> None:
        if self.threat_id is not None and type(self.threat_id) is not EntityId:
            raise TypeError("Flee.threat_id must be EntityId or None")


@dataclass(frozen=True, slots=True)
class Wait:
    kind: Literal["wait"] = field(default="wait", init=False)


AgentCommand = (
    Move
    | Search
    | Take
    | Drop
    | Give
    | Eat
    | Drink
    | Sleep
    | Talk
    | Ask
    | Tell
    | Help
    | Attack
    | Flee
    | Wait
)

_COMMAND_TYPES: Final[frozenset[type]] = frozenset(
    {
        Move,
        Search,
        Take,
        Drop,
        Give,
        Eat,
        Drink,
        Sleep,
        Talk,
        Ask,
        Tell,
        Help,
        Attack,
        Flee,
        Wait,
    }
)


def require_agent_command(value: object) -> AgentCommand:
    """Accept only exact closed command classes; reject subclasses and mappings."""
    if isinstance(value, Mapping):
        raise TypeError("raw mappings are not agent commands")
    command_type = type(value)
    if command_type not in _COMMAND_TYPES:
        raise TypeError(
            f"unsupported agent command type {command_type.__name__}"
        )
    return value  # type: ignore[return-value]


@dataclass(frozen=True, slots=True)
class ActionProposal:
    """Non-authoritative proposal envelope. Never mutates the world."""

    proposal_id: ProposalId
    command: AgentCommand

    def __post_init__(self) -> None:
        if type(self.proposal_id) is not ProposalId:
            raise TypeError("ActionProposal.proposal_id must be ProposalId")
        object.__setattr__(
            self, "command", require_agent_command(self.command)
        )


@dataclass(frozen=True, slots=True)
class ActionRequest:
    """Non-authoritative bound request. Not yet a private world operation."""

    request_id: RequestId
    proposal_id: ProposalId
    world_id: WorldId
    actor_id: EntityId
    revision: WorldRevision
    command: AgentCommand

    def __post_init__(self) -> None:
        if type(self.request_id) is not RequestId:
            raise TypeError("ActionRequest.request_id must be RequestId")
        if type(self.proposal_id) is not ProposalId:
            raise TypeError("ActionRequest.proposal_id must be ProposalId")
        if type(self.world_id) is not WorldId:
            raise TypeError("ActionRequest.world_id must be WorldId")
        if type(self.actor_id) is not EntityId:
            raise TypeError("ActionRequest.actor_id must be EntityId")
        if type(self.revision) is not WorldRevision:
            raise TypeError("ActionRequest.revision must be WorldRevision")
        object.__setattr__(
            self, "command", require_agent_command(self.command)
        )


class TransitionOutcome(StrEnum):
    APPLIED = "applied"
    NOT_APPLIED = "not_applied"


@dataclass(frozen=True, slots=True)
class ActionOutcome:
    """Post-validation transition outcome. Validation failures never become events."""

    request_id: RequestId
    outcome: TransitionOutcome
    revision: WorldRevision

    def __post_init__(self) -> None:
        if type(self.request_id) is not RequestId:
            raise TypeError("ActionOutcome.request_id must be RequestId")
        if type(self.outcome) is not TransitionOutcome:
            raise TypeError("ActionOutcome.outcome must be TransitionOutcome")
        if type(self.revision) is not WorldRevision:
            raise TypeError("ActionOutcome.revision must be WorldRevision")


@runtime_checkable
class WorldGateway(Protocol):
    """Trusted world entry point. Must call :func:`accept_action_request`."""

    def submit(self, request: ActionRequest) -> ActionOutcome:
        """Apply a validated request and return an applied/not-applied outcome."""
        ...


def accept_action_request(value: object) -> ActionRequest:
    """Reject proposals and raw mappings; only :class:`ActionRequest` is trusted."""
    if isinstance(value, ActionProposal):
        raise TypeError("ActionProposal cannot be submitted to the world gateway")
    if isinstance(value, Mapping):
        raise TypeError("raw mappings cannot be submitted to the world gateway")
    if type(value) is not ActionRequest:
        raise TypeError(
            f"world gateway accepts ActionRequest, not {type(value).__name__}"
        )
    return value
