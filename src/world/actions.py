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
    DurableRecordGenre,
    artifact_kind_is_durable_capable,
    artifact_kind_is_portable,
    require_artifact_content,
    require_artifact_kind,
    require_durable_record_genre,
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
class Feed:
    """Caregiver applies held food/water relief to a colocated DEPENDENT."""

    target_id: EntityId
    item_id: EntityId
    kind: Literal["feed"] = field(default="feed", init=False)

    def __post_init__(self) -> None:
        if type(self.target_id) is not EntityId:
            raise TypeError("Feed.target_id must be EntityId")
        if type(self.item_id) is not EntityId:
            raise TypeError("Feed.item_id must be EntityId")


@dataclass(frozen=True, slots=True)
class Transport:
    """Caregiver relocates self and a colocated DEPENDENT together."""

    target_id: EntityId
    destination_id: EntityId
    kind: Literal["transport"] = field(default="transport", init=False)

    def __post_init__(self) -> None:
        if type(self.target_id) is not EntityId:
            raise TypeError("Transport.target_id must be EntityId")
        if type(self.destination_id) is not EntityId:
            raise TypeError("Transport.destination_id must be EntityId")


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


_COPY_FIDELITY_OVERRIDES: Final[frozenset[str]] = frozenset(
    {"perfect", "deterministic_mutation", "lossy"}
)
_MAINTAIN_REPOSITORY_MODES: Final[frozenset[str]] = frozenset(
    {"maintain", "destroy"}
)
_DAMAGE_RECORD_MODES: Final[frozenset[str]] = frozenset(
    {"damage", "partial_loss", "destroy"}
)


@dataclass(frozen=True, slots=True)
class Inscribe:
    """Create an artifact at the actor location, or held when ``hold`` is true."""

    kind: ArtifactKind
    content: ArtifactContent
    hold: bool = False
    record_genre: DurableRecordGenre | None = None

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
        if self.record_genre is not None:
            require_durable_record_genre(
                self.record_genre, field_name="Inscribe.record_genre"
            )
            if not artifact_kind_is_durable_capable(self.kind):
                _ARTIFACT_LOG.error(
                    "artifact_validation_failed field=%s reason_code=%s",
                    "Inscribe.record_genre",
                    "durable_genre_kind_mismatch",
                )
                raise ValueError("Inscribe.record_genre: durable_genre_kind_mismatch")
        _ARTIFACT_LOG.debug(
            "inscribe_constructed kind=%s mark_count=%s relation_count=%s hold=%s "
            "genre=%s",
            self.kind.value,
            len(self.content.marks),
            len(self.content.relations),
            self.hold,
            self.record_genre.value if self.record_genre is not None else "-",
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


@dataclass(frozen=True, slots=True)
class CopyRecord:
    """Create a durable copy with parent/source lineage."""

    artifact_id: EntityId
    hold: bool = False
    fidelity_override: str | None = None
    kind: Literal["copy_record"] = field(default="copy_record", init=False)

    def __post_init__(self) -> None:
        if type(self.artifact_id) is not EntityId:
            raise TypeError("CopyRecord.artifact_id must be EntityId")
        if type(self.hold) is not bool:
            _ARTIFACT_LOG.error(
                "artifact_validation_failed field=%s reason_code=%s",
                "CopyRecord.hold",
                "invalid_artifact_hold",
            )
            raise ValueError("CopyRecord.hold: invalid_artifact_hold")
        if self.fidelity_override is not None:
            if (
                type(self.fidelity_override) is not str
                or self.fidelity_override not in _COPY_FIDELITY_OVERRIDES
            ):
                _ARTIFACT_LOG.error(
                    "artifact_validation_failed field=%s reason_code=%s",
                    "CopyRecord.fidelity_override",
                    "durable_copy_fidelity_invalid",
                )
                raise ValueError(
                    "CopyRecord.fidelity_override: durable_copy_fidelity_invalid"
                )
        _ARTIFACT_LOG.debug(
            "command_constructed tag=copy_record hold=%s fidelity_override=%s",
            self.hold,
            self.fidelity_override if self.fidelity_override is not None else "-",
        )


@dataclass(frozen=True, slots=True)
class AnnotateRecord:
    """Merge annotation marks into a durable record's content."""

    artifact_id: EntityId
    content: ArtifactContent
    kind: Literal["annotate_record"] = field(default="annotate_record", init=False)

    def __post_init__(self) -> None:
        if type(self.artifact_id) is not EntityId:
            raise TypeError("AnnotateRecord.artifact_id must be EntityId")
        require_artifact_content(self.content, field_name="AnnotateRecord.content")
        _ARTIFACT_LOG.debug(
            "command_constructed tag=annotate_record mark_count=%s",
            len(self.content.marks),
        )


@dataclass(frozen=True, slots=True)
class DamageRecord:
    """Damage, partially lose, or destroy a durable record."""

    artifact_id: EntityId
    mode: Literal["damage", "partial_loss", "destroy"]
    kind: Literal["damage_record"] = field(default="damage_record", init=False)

    def __post_init__(self) -> None:
        if type(self.artifact_id) is not EntityId:
            raise TypeError("DamageRecord.artifact_id must be EntityId")
        if self.mode not in _DAMAGE_RECORD_MODES:
            _ARTIFACT_LOG.error(
                "artifact_validation_failed field=%s reason_code=%s",
                "DamageRecord.mode",
                "durable_damage_mode_invalid",
            )
            raise ValueError("DamageRecord.mode: durable_damage_mode_invalid")
        _ARTIFACT_LOG.debug(
            "command_constructed tag=damage_record mode=%s",
            self.mode,
        )


@dataclass(frozen=True, slots=True)
class EstablishRepository:
    """Create a knowledge repository container at a location."""

    location_id: EntityId
    access_mode: str | None = None
    structure_id: EntityId | None = None
    kind: Literal["establish_repository"] = field(
        default="establish_repository", init=False
    )

    def __post_init__(self) -> None:
        if type(self.location_id) is not EntityId:
            raise TypeError("EstablishRepository.location_id must be EntityId")
        if self.structure_id is not None and type(self.structure_id) is not EntityId:
            raise TypeError(
                "EstablishRepository.structure_id must be EntityId or None"
            )
        if self.access_mode is not None:
            if type(self.access_mode) is not str or self.access_mode not in {
                "open",
                "colocated_only",
                "founder_list",
            }:
                _ARTIFACT_LOG.error(
                    "artifact_validation_failed field=%s reason_code=%s",
                    "EstablishRepository.access_mode",
                    "repository_access_mode_invalid",
                )
                raise ValueError(
                    "EstablishRepository.access_mode: repository_access_mode_invalid"
                )
        _ARTIFACT_LOG.debug(
            "command_constructed tag=establish_repository access_mode=%s",
            self.access_mode if self.access_mode is not None else "default",
        )


@dataclass(frozen=True, slots=True)
class DepositRecord:
    """Move a durable artifact into repository custody."""

    repository_id: EntityId
    artifact_id: EntityId
    kind: Literal["deposit_record"] = field(default="deposit_record", init=False)

    def __post_init__(self) -> None:
        if type(self.repository_id) is not EntityId:
            raise TypeError("DepositRecord.repository_id must be EntityId")
        if type(self.artifact_id) is not EntityId:
            raise TypeError("DepositRecord.artifact_id must be EntityId")
        _ARTIFACT_LOG.debug(
            "command_constructed tag=deposit_record repository_id=%s",
            self.repository_id.value,
        )


@dataclass(frozen=True, slots=True)
class RetrieveRecord:
    """Remove a durable artifact from repository custody."""

    repository_id: EntityId
    artifact_id: EntityId
    hold: bool = True
    kind: Literal["retrieve_record"] = field(default="retrieve_record", init=False)

    def __post_init__(self) -> None:
        if type(self.repository_id) is not EntityId:
            raise TypeError("RetrieveRecord.repository_id must be EntityId")
        if type(self.artifact_id) is not EntityId:
            raise TypeError("RetrieveRecord.artifact_id must be EntityId")
        if type(self.hold) is not bool:
            raise ValueError("RetrieveRecord.hold: invalid_artifact_hold")
        _ARTIFACT_LOG.debug(
            "command_constructed tag=retrieve_record hold=%s",
            self.hold,
        )


@dataclass(frozen=True, slots=True)
class MaintainRepository:
    """Maintain or destroy a knowledge repository."""

    repository_id: EntityId
    mode: Literal["maintain", "destroy"] = "maintain"
    kind: Literal["maintain_repository"] = field(
        default="maintain_repository", init=False
    )

    def __post_init__(self) -> None:
        if type(self.repository_id) is not EntityId:
            raise TypeError("MaintainRepository.repository_id must be EntityId")
        if self.mode not in _MAINTAIN_REPOSITORY_MODES:
            _ARTIFACT_LOG.error(
                "artifact_validation_failed field=%s reason_code=%s",
                "MaintainRepository.mode",
                "repository_maintain_mode_invalid",
            )
            raise ValueError(
                "MaintainRepository.mode: repository_maintain_mode_invalid"
            )
        _ARTIFACT_LOG.debug(
            "command_constructed tag=maintain_repository mode=%s",
            self.mode,
        )


@dataclass(frozen=True, slots=True)
class IndexRepository:
    """Append or replace imperfect organization index entries."""

    repository_id: EntityId
    entries: tuple[Mapping[str, object], ...]
    kind: Literal["index_repository"] = field(default="index_repository", init=False)

    def __post_init__(self) -> None:
        if type(self.repository_id) is not EntityId:
            raise TypeError("IndexRepository.repository_id must be EntityId")
        if isinstance(self.entries, (str, bytes)) or not isinstance(
            self.entries, tuple
        ):
            raise TypeError("IndexRepository.entries must be a tuple")
        for index, entry in enumerate(self.entries):
            if not isinstance(entry, Mapping):
                raise TypeError(
                    f"IndexRepository.entries[{index}] must be a mapping"
                )
        _ARTIFACT_LOG.debug(
            "command_constructed tag=index_repository entry_count=%s",
            len(self.entries),
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
    | Feed
    | Transport
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
    | CopyRecord
    | AnnotateRecord
    | DamageRecord
    | EstablishRepository
    | DepositRecord
    | RetrieveRecord
    | MaintainRepository
    | IndexRepository
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
        Feed,
        Transport,
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
        CopyRecord,
        AnnotateRecord,
        DamageRecord,
        EstablishRepository,
        DepositRecord,
        RetrieveRecord,
        MaintainRepository,
        IndexRepository,
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
