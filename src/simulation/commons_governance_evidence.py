"""Neutral finalized-boundary evidence for commons governance capture.

Detached observational DTOs only. The runner may emit these at fully finalized
boundaries; analysis and experiments never feed them back into cognition.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import StrEnum
from typing import Final, Protocol, runtime_checkable

from agents.models import AgentId
from simulation.lifecycle import ActionResolution, TickResult
from world.events import WorldEvent
from world.identifiers import EntityId, require_exact_nonneg_int, require_stable_id

__all__ = [
    "MAX_COMMONS_BOUNDARY_EVENTS",
    "MAX_COMMONS_BOUNDARY_TICKS",
    "MAX_COMMONS_OWNER_TRANSITION_ROWS",
    "CommonsGovernanceBoundaryExport",
    "CommonsGovernanceBoundarySink",
    "CommonsGovernanceCaptureStatus",
    "CommonsGovernanceConsiderationDelta",
    "CommonsGovernanceOwnerDelta",
    "CommonsGovernanceOwnerThirst",
    "CommonsGovernanceProposalHead",
    "CommonsGovernanceResolutionDelta",
    "CommonsGovernanceTransitionDelta",
    "CommonsLaneStatus",
    "boundary_from_tick_result",
    "resolution_delta_from_action",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "simulation.commons_governance_evidence"
)

MAX_COMMONS_BOUNDARY_TICKS: Final[int] = 512
MAX_COMMONS_BOUNDARY_EVENTS: Final[int] = 100_000
MAX_COMMONS_OWNER_TRANSITION_ROWS: Final[int] = 16_384


class CommonsLaneStatus(StrEnum):
    """Per-lane capture availability; absence is never reported as zero."""

    DISABLED = "disabled"
    UNAVAILABLE = "unavailable"
    PARTIAL = "partial"
    COMPLETE = "complete"
    INAPPLICABLE = "inapplicable"


class CommonsGovernanceCaptureStatus(StrEnum):
    """Aggregate capture health for one sealed run."""

    DISABLED = "disabled"
    UNAVAILABLE = "unavailable"
    PARTIAL = "partial"
    COMPLETE = "complete"


@dataclass(frozen=True, slots=True)
class CommonsGovernanceTransitionDelta:
    """One owner-scoped transition finalized on a boundary tick."""

    owner_id: AgentId
    stock_id: EntityId
    source_tick: int
    code: str
    transition_id: str
    quantity_tenths: int | None = None
    signal: str | None = None
    proposal_id: str | None = None
    actor_id: EntityId | None = None
    stance: str | None = None
    reported_tick: int | None = None
    occurrence_ref: str | None = None

    def __post_init__(self) -> None:
        if type(self.owner_id) is not AgentId:
            raise TypeError("owner_id must be AgentId")
        if type(self.stock_id) is not EntityId:
            raise TypeError("stock_id must be EntityId")
        object.__setattr__(
            self,
            "source_tick",
            require_exact_nonneg_int("source_tick", self.source_tick),
        )
        object.__setattr__(self, "code", require_stable_id("code", self.code))
        object.__setattr__(
            self,
            "transition_id",
            require_stable_id("transition_id", self.transition_id),
        )
        if self.quantity_tenths is not None and (
            type(self.quantity_tenths) is not int
            or isinstance(self.quantity_tenths, bool)
            or self.quantity_tenths < 0
        ):
            raise ValueError("quantity_tenths must be None or non-negative int")
        if self.signal is not None:
            object.__setattr__(
                self, "signal", require_stable_id("signal", self.signal)
            )
        if self.proposal_id is not None:
            object.__setattr__(
                self,
                "proposal_id",
                require_stable_id("proposal_id", self.proposal_id),
            )
        if self.actor_id is not None and type(self.actor_id) is not EntityId:
            raise TypeError("actor_id must be EntityId or None")
        if self.stance is not None:
            object.__setattr__(
                self, "stance", require_stable_id("stance", self.stance)
            )
        if self.reported_tick is not None:
            object.__setattr__(
                self,
                "reported_tick",
                require_exact_nonneg_int("reported_tick", self.reported_tick),
            )
        if self.occurrence_ref is not None:
            object.__setattr__(
                self,
                "occurrence_ref",
                require_stable_id("occurrence_ref", self.occurrence_ref),
            )


@dataclass(frozen=True, slots=True)
class CommonsGovernanceConsiderationDelta:
    """One Drink consideration finalized for an owner on a boundary tick."""

    owner_id: AgentId
    tick: int
    target_id: EntityId
    opportunity: str
    choice: str
    proposal_id: str | None = None

    def __post_init__(self) -> None:
        if type(self.owner_id) is not AgentId:
            raise TypeError("owner_id must be AgentId")
        object.__setattr__(
            self, "tick", require_exact_nonneg_int("tick", self.tick)
        )
        if type(self.target_id) is not EntityId:
            raise TypeError("target_id must be EntityId")
        object.__setattr__(
            self,
            "opportunity",
            require_stable_id("opportunity", self.opportunity),
        )
        object.__setattr__(self, "choice", require_stable_id("choice", self.choice))
        if self.proposal_id is not None:
            object.__setattr__(
                self,
                "proposal_id",
                require_stable_id("proposal_id", self.proposal_id),
            )


@dataclass(frozen=True, slots=True)
class CommonsGovernanceProposalHead:
    """Detached proposal head snapshot retained at a boundary."""

    owner_id: AgentId
    stock_id: EntityId
    proposal_id: str
    topic: str
    proposer_id: EntityId
    peer_id: EntityId | None
    origin_tick: int
    supported: bool
    opposed: bool
    contested: bool
    support_count: int
    oppose_count: int
    access_claim_count: int
    criticism_count: int
    monitor_check_count: int
    eligible_recipient_ids: tuple[EntityId, ...] = ()

    def __post_init__(self) -> None:
        if type(self.owner_id) is not AgentId:
            raise TypeError("owner_id must be AgentId")
        if type(self.stock_id) is not EntityId:
            raise TypeError("stock_id must be EntityId")
        object.__setattr__(
            self,
            "proposal_id",
            require_stable_id("proposal_id", self.proposal_id),
        )
        object.__setattr__(self, "topic", require_stable_id("topic", self.topic))
        if type(self.proposer_id) is not EntityId:
            raise TypeError("proposer_id must be EntityId")
        if self.peer_id is not None and type(self.peer_id) is not EntityId:
            raise TypeError("peer_id must be EntityId or None")
        object.__setattr__(
            self,
            "origin_tick",
            require_exact_nonneg_int("origin_tick", self.origin_tick),
        )
        for name in ("supported", "opposed", "contested"):
            if type(getattr(self, name)) is not bool:
                raise TypeError(f"{name} must be bool")
        for name in (
            "support_count",
            "oppose_count",
            "access_claim_count",
            "criticism_count",
            "monitor_check_count",
        ):
            value = getattr(self, name)
            if type(value) is not int or isinstance(value, bool) or value < 0:
                raise ValueError(f"{name} must be a non-negative int")
        recipients = tuple(self.eligible_recipient_ids)
        for item in recipients:
            if type(item) is not EntityId:
                raise TypeError("eligible_recipient_ids entries must be EntityId")
        object.__setattr__(self, "eligible_recipient_ids", recipients)


@dataclass(frozen=True, slots=True)
class CommonsGovernanceOwnerThirst:
    """Terminal living-founder thirst observation with coverage."""

    owner_id: AgentId
    entity_id: EntityId
    living: bool
    thirst_tenths: int | None

    def __post_init__(self) -> None:
        if type(self.owner_id) is not AgentId:
            raise TypeError("owner_id must be AgentId")
        if type(self.entity_id) is not EntityId:
            raise TypeError("entity_id must be EntityId")
        if type(self.living) is not bool:
            raise TypeError("living must be bool")
        if self.thirst_tenths is not None and (
            type(self.thirst_tenths) is not int
            or isinstance(self.thirst_tenths, bool)
            or self.thirst_tenths < 0
        ):
            raise ValueError("thirst_tenths must be None or non-negative int")


@dataclass(frozen=True, slots=True)
class CommonsGovernanceResolutionDelta:
    """Detached effective-command resolution with optional Drink source."""

    ordinal: int
    agent_id: AgentId
    command_kind: str
    status: str
    reason: str
    tick: int
    source_id: EntityId | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "ordinal",
            require_exact_nonneg_int("ordinal", self.ordinal),
        )
        if type(self.agent_id) is not AgentId:
            raise TypeError("agent_id must be AgentId")
        object.__setattr__(
            self,
            "command_kind",
            require_stable_id("command_kind", self.command_kind),
        )
        object.__setattr__(self, "status", require_stable_id("status", self.status))
        object.__setattr__(self, "reason", require_stable_id("reason", self.reason))
        object.__setattr__(
            self, "tick", require_exact_nonneg_int("tick", self.tick)
        )
        if self.source_id is not None and type(self.source_id) is not EntityId:
            raise TypeError("source_id must be EntityId or None")


@dataclass(frozen=True, slots=True)
class CommonsGovernanceOwnerDelta:
    """Just-finalized owner deltas for one absolute boundary."""

    owner_id: AgentId
    living: bool
    transitions: tuple[CommonsGovernanceTransitionDelta, ...] = ()
    considerations: tuple[CommonsGovernanceConsiderationDelta, ...] = ()
    proposals: tuple[CommonsGovernanceProposalHead, ...] = ()
    thirst_tenths: int | None = None

    def __post_init__(self) -> None:
        if type(self.owner_id) is not AgentId:
            raise TypeError("owner_id must be AgentId")
        if type(self.living) is not bool:
            raise TypeError("living must be bool")
        transitions = tuple(self.transitions)
        for transition in transitions:
            if type(transition) is not CommonsGovernanceTransitionDelta:
                raise TypeError("transitions entries must be TransitionDelta")
            if transition.owner_id != self.owner_id:
                raise ValueError("transition owner mismatch")
        considerations = tuple(self.considerations)
        for consideration in considerations:
            if type(consideration) is not CommonsGovernanceConsiderationDelta:
                raise TypeError("considerations entries must be ConsiderationDelta")
            if consideration.owner_id != self.owner_id:
                raise ValueError("consideration owner mismatch")
        proposals = tuple(self.proposals)
        for proposal in proposals:
            if type(proposal) is not CommonsGovernanceProposalHead:
                raise TypeError("proposals entries must be ProposalHead")
            if proposal.owner_id != self.owner_id:
                raise ValueError("proposal owner mismatch")
        if self.thirst_tenths is not None and (
            type(self.thirst_tenths) is not int
            or isinstance(self.thirst_tenths, bool)
            or self.thirst_tenths < 0
        ):
            raise ValueError("thirst_tenths must be None or non-negative int")
        object.__setattr__(self, "transitions", transitions)
        object.__setattr__(self, "considerations", considerations)
        object.__setattr__(self, "proposals", proposals)


@dataclass(frozen=True, slots=True)
class CommonsGovernanceBoundaryExport:
    """Immutable evidence for one fully finalized absolute boundary.

    ``boundary_tick`` is the state-after boundary (tick + 1). Objective events
    and resolutions belong to the just-committed tick ``boundary_tick - 1``
    when ``boundary_tick > 0``.
    """

    run_id: str
    boundary_tick: int
    events: tuple[WorldEvent, ...] = ()
    resolutions: tuple[CommonsGovernanceResolutionDelta, ...] = ()
    owners: tuple[CommonsGovernanceOwnerDelta, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_id", require_stable_id("run_id", self.run_id))
        object.__setattr__(
            self,
            "boundary_tick",
            require_exact_nonneg_int("boundary_tick", self.boundary_tick),
        )
        events = tuple(self.events)
        for event in events:
            if type(event) is not WorldEvent:
                raise TypeError("events entries must be WorldEvent")
        resolutions = tuple(self.resolutions)
        for resolution in resolutions:
            if type(resolution) is not CommonsGovernanceResolutionDelta:
                raise TypeError("resolutions entries must be ResolutionDelta")
        owners = list(self.owners)
        for owner in owners:
            if type(owner) is not CommonsGovernanceOwnerDelta:
                raise TypeError("owners entries must be OwnerDelta")
        owners.sort(key=lambda item: item.owner_id.value)
        seen: set[str] = set()
        for owner in owners:
            token = owner.owner_id.value
            if token in seen:
                raise ValueError("duplicate_owner")
            seen.add(token)
        object.__setattr__(self, "events", events)
        object.__setattr__(self, "resolutions", resolutions)
        object.__setattr__(self, "owners", tuple(owners))

    @property
    def transition_row_count(self) -> int:
        return sum(len(owner.transitions) for owner in self.owners)

    @property
    def event_count(self) -> int:
        return len(self.events)


@runtime_checkable
class CommonsGovernanceBoundarySink(Protocol):
    """Synchronous observational sink for complete finalized boundaries."""

    def capture(self, frame: CommonsGovernanceBoundaryExport) -> None: ...


def resolution_delta_from_action(
    resolution: ActionResolution,
) -> CommonsGovernanceResolutionDelta:
    """Project one ActionResolution into a detached resolution delta."""
    if type(resolution) is not ActionResolution:
        raise TypeError("resolution must be ActionResolution")
    from world.actions import Drink, agent_command_tag

    source_id: EntityId | None = None
    if type(resolution.command) is Drink:
        source_id = resolution.command.source_id
    return CommonsGovernanceResolutionDelta(
        ordinal=resolution.ordinal,
        agent_id=resolution.agent_id,
        command_kind=agent_command_tag(resolution.command),
        status=resolution.status.value,
        reason=resolution.reason.value,
        tick=resolution.tick.value,
        source_id=source_id,
    )


def boundary_from_tick_result(
    *,
    run_id: str,
    boundary_tick: int,
    result: TickResult | None,
    owners: tuple[CommonsGovernanceOwnerDelta, ...],
) -> CommonsGovernanceBoundaryExport:
    """Build a boundary export from an optional TickResult and owner deltas."""
    if result is None:
        return CommonsGovernanceBoundaryExport(
            run_id=run_id,
            boundary_tick=boundary_tick,
            events=(),
            resolutions=(),
            owners=owners,
        )
    if type(result) is not TickResult:
        raise TypeError("result must be TickResult")
    if boundary_tick != result.tick.value + 1:
        raise ValueError("boundary_tick must equal tick + 1")
    events = tuple(record.event for record in result.events)
    resolutions = tuple(
        resolution_delta_from_action(item) for item in result.resolutions
    )
    return CommonsGovernanceBoundaryExport(
        run_id=run_id,
        boundary_tick=boundary_tick,
        events=events,
        resolutions=resolutions,
        owners=owners,
    )


_LOG.debug(
    "commons_governance_evidence_loaded max_ticks=%s max_events=%s max_transitions=%s",
    MAX_COMMONS_BOUNDARY_TICKS,
    MAX_COMMONS_BOUNDARY_EVENTS,
    MAX_COMMONS_OWNER_TRANSITION_ROWS,
)
