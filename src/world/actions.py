"""Closed agent commands, non-authoritative proposals, and requests.

Commands and proposals carry no actor authority. Only a later private
world validation step promotes a request to an authority-bearing operation.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import InitVar, dataclass, field
from enum import StrEnum
from typing import Final, Literal, Protocol, runtime_checkable

from world.artifacts import (
    ArtifactContent,
    ArtifactKind,
    artifact_kind_is_portable,
    require_artifact_content,
    require_artifact_kind,
)
from world.communications import StructuredUtterance, confidence_band
from world.identifiers import (
    EntityId,
    ProposalId,
    RecipeId,
    RequestId,
    WorldId,
    WorldRevision,
)
from world.production import require_production_command_fields

_ARTIFACT_LOG: Final[logging.Logger] = logging.getLogger("world.artifacts")


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
    utterance: StructuredUtterance
    kind: Literal["talk"] = field(default="talk", init=False)

    def __post_init__(self) -> None:
        if type(self.recipient_id) is not EntityId:
            raise TypeError("Talk.recipient_id must be EntityId")
        if type(self.utterance) is not StructuredUtterance:
            raise TypeError("Talk.utterance must be StructuredUtterance")

    def __repr__(self) -> str:
        return (
            f"Talk(recipient_id={self.recipient_id.value!r}, "
            f"hop_count={self.utterance.declared.hop_count}, "
            f"confidence_band="
            f"{confidence_band(self.utterance.declared.sender_confidence)!r})"
        )


@dataclass(frozen=True, slots=True)
class Ask:
    recipient_id: EntityId
    utterance: StructuredUtterance
    kind: Literal["ask"] = field(default="ask", init=False)

    def __post_init__(self) -> None:
        if type(self.recipient_id) is not EntityId:
            raise TypeError("Ask.recipient_id must be EntityId")
        if type(self.utterance) is not StructuredUtterance:
            raise TypeError("Ask.utterance must be StructuredUtterance")

    def __repr__(self) -> str:
        return (
            f"Ask(recipient_id={self.recipient_id.value!r}, "
            f"hop_count={self.utterance.declared.hop_count})"
        )


@dataclass(frozen=True, slots=True)
class Tell:
    recipient_id: EntityId
    utterance: StructuredUtterance
    kind: Literal["tell"] = field(default="tell", init=False)

    def __post_init__(self) -> None:
        if type(self.recipient_id) is not EntityId:
            raise TypeError("Tell.recipient_id must be EntityId")
        if type(self.utterance) is not StructuredUtterance:
            raise TypeError("Tell.utterance must be StructuredUtterance")

    def __repr__(self) -> str:
        return (
            f"Tell(recipient_id={self.recipient_id.value!r}, "
            f"hop_count={self.utterance.declared.hop_count})"
        )


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


@dataclass(frozen=True, slots=True)
class Harvest:
    recipe_id: RecipeId
    resource_id: EntityId
    action: InitVar[str] = "harvest"
    kind: Literal["harvest"] = field(default="harvest", init=False)

    def __post_init__(self, action: str) -> None:
        require_production_command_fields(
            class_name="Harvest",
            class_action="harvest",
            action=action,
            recipe_id=self.recipe_id,
        )
        if type(self.resource_id) is not EntityId:
            raise TypeError("Harvest.resource_id must be EntityId")


@dataclass(frozen=True, slots=True)
class Craft:
    recipe_id: RecipeId
    action: InitVar[str] = "craft"
    kind: Literal["craft"] = field(default="craft", init=False)

    def __post_init__(self, action: str) -> None:
        require_production_command_fields(
            class_name="Craft",
            class_action="craft",
            action=action,
            recipe_id=self.recipe_id,
        )


@dataclass(frozen=True, slots=True)
class Build:
    recipe_id: RecipeId
    action: InitVar[str] = "build"
    kind: Literal["build"] = field(default="build", init=False)

    def __post_init__(self, action: str) -> None:
        require_production_command_fields(
            class_name="Build",
            class_action="build",
            action=action,
            recipe_id=self.recipe_id,
        )


@dataclass(frozen=True, slots=True)
class Repair:
    recipe_id: RecipeId
    structure_id: EntityId
    action: InitVar[str] = "repair"
    kind: Literal["repair"] = field(default="repair", init=False)

    def __post_init__(self, action: str) -> None:
        require_production_command_fields(
            class_name="Repair",
            class_action="repair",
            action=action,
            recipe_id=self.recipe_id,
        )
        if type(self.structure_id) is not EntityId:
            raise TypeError("Repair.structure_id must be EntityId")


@dataclass(frozen=True, slots=True)
class Store:
    recipe_id: RecipeId
    item_id: EntityId
    action: InitVar[str] = "store"
    kind: Literal["store"] = field(default="store", init=False)

    def __post_init__(self, action: str) -> None:
        require_production_command_fields(
            class_name="Store",
            class_action="store",
            action=action,
            recipe_id=self.recipe_id,
        )
        if type(self.item_id) is not EntityId:
            raise TypeError("Store.item_id must be EntityId")


@dataclass(frozen=True, slots=True)
class Inscribe:
    """Create an artifact at the actor location, or held when ``hold`` is true."""

    kind: ArtifactKind
    content: ArtifactContent
    hold: bool = False

    def __post_init__(self) -> None:
        require_artifact_kind(self.kind, field_name="Inscribe.kind")
        require_artifact_content(self.content, field_name="Inscribe.content")
        if type(self.hold) is not bool:
            _ARTIFACT_LOG.error(
                "artifact_validation_failed field=%s reason_code=%s",
                "Inscribe.hold",
                "invalid_artifact_hold",
            )
            raise ValueError("Inscribe.hold: invalid_artifact_hold")
        if self.hold and not artifact_kind_is_portable(self.kind):
            _ARTIFACT_LOG.error(
                "artifact_validation_failed field=%s reason_code=%s",
                "Inscribe.hold",
                "invalid_artifact_hold",
            )
            raise ValueError("Inscribe.hold: invalid_artifact_hold")
        _ARTIFACT_LOG.debug(
            "inscribe_constructed kind=%s mark_count=%s relation_count=%s hold=%s",
            self.kind.value,
            len(self.content.marks),
            len(self.content.relations),
            self.hold,
        )


@dataclass(frozen=True, slots=True)
class Amend:
    artifact_id: EntityId
    content: ArtifactContent
    kind: Literal["amend"] = field(default="amend", init=False)

    def __post_init__(self) -> None:
        if type(self.artifact_id) is not EntityId:
            raise TypeError("Amend.artifact_id must be EntityId")
        require_artifact_content(self.content, field_name="Amend.content")


@dataclass(frozen=True, slots=True)
class Erase:
    artifact_id: EntityId
    kind: Literal["erase"] = field(default="erase", init=False)

    def __post_init__(self) -> None:
        if type(self.artifact_id) is not EntityId:
            raise TypeError("Erase.artifact_id must be EntityId")


@dataclass(frozen=True, slots=True)
class TransferArtifact:
    artifact_id: EntityId
    mode: Literal["deposit", "claim", "give"]
    recipient_id: EntityId | None = None
    kind: Literal["transfer_artifact"] = field(
        default="transfer_artifact", init=False
    )

    def __post_init__(self) -> None:
        if type(self.artifact_id) is not EntityId:
            raise TypeError("TransferArtifact.artifact_id must be EntityId")
        if self.mode not in ("deposit", "claim", "give"):
            raise ValueError("TransferArtifact.mode: artifact_transfer_mode_invalid")
        if self.mode in ("deposit", "claim"):
            if self.recipient_id is not None:
                raise ValueError(
                    "TransferArtifact.recipient_id: artifact_transfer_mode_invalid"
                )
        elif self.recipient_id is None or type(self.recipient_id) is not EntityId:
            raise ValueError(
                "TransferArtifact.recipient_id: artifact_transfer_mode_invalid"
            )


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
    | Harvest
    | Craft
    | Build
    | Repair
    | Store
    | Inscribe
    | Amend
    | Erase
    | TransferArtifact
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
        Harvest,
        Craft,
        Build,
        Repair,
        Store,
        Inscribe,
        Amend,
        Erase,
        TransferArtifact,
    }
)


def agent_command_tag(command: AgentCommand) -> str:
    """Stable wire/command tag. ``Inscribe.kind`` is the artifact kind."""
    if type(command) is Inscribe:
        return "inscribe"
    tag = command.kind
    if type(tag) is not str:
        raise TypeError(f"unsupported agent command tag type {type(tag).__name__}")
    return tag


def require_agent_command(value: object) -> AgentCommand:
    """Accept only exact closed command classes; reject subclasses and mappings."""
    if isinstance(value, Mapping):
        raise TypeError("raw mappings are not agent commands")
    command_type = type(value)
    if command_type not in _COMMAND_TYPES:
        raise TypeError(f"unsupported agent command type {command_type.__name__}")
    return value  # type: ignore[return-value]


@dataclass(frozen=True, slots=True)
class ActionProposal:
    """Non-authoritative proposal envelope. Never mutates the world."""

    proposal_id: ProposalId
    command: AgentCommand

    def __post_init__(self) -> None:
        if type(self.proposal_id) is not ProposalId:
            raise TypeError("ActionProposal.proposal_id must be ProposalId")
        object.__setattr__(self, "command", require_agent_command(self.command))


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
        object.__setattr__(self, "command", require_agent_command(self.command))


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
