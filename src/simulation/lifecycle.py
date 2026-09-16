"""Immutable tick lifecycle contracts for the public world engine.

Value construction is side-effect free. Stable diagnostic codes are intended
for engine DEBUG logs only — never log command text, observations, or private
state alongside them.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from agents.models import AgentId
from simulation.clock import Tick, require_exact_nonneg_int
from world.actions import AgentCommand, require_agent_command
from world.events import WorldEvent, normalize_events
from world.identifiers import (
    RequestId,
    WorldRevision,
    require_stable_id,
)
from world.observations import Observation

__all__ = [
    "ActionResolution",
    "ActionResolutionReason",
    "ActionResolutionStatus",
    "ActionSubmission",
    "EngineDiagnosticCode",
    "ObservationBatch",
    "TickEventRecord",
    "TickResult",
    "TickToken",
    "require_action_submission",
]


class EngineDiagnosticCode(StrEnum):
    """Stable non-sensitive codes for WorldEngine DEBUG/WARN/ERROR logs."""

    BOOTSTRAP_VALIDATED = "bootstrap_validated"
    OBSERVATIONS_ISSUED = "observations_issued"
    SUBMISSION_ADMITTED = "submission_admitted"
    SUBMISSION_REJECTED = "submission_rejected"
    RESOLUTION_APPLIED = "resolution_applied"
    RESOLUTION_REJECTED = "resolution_rejected"
    RESOLUTION_CONFLICT = "resolution_conflict"
    RESOLUTION_DUPLICATE = "resolution_duplicate"
    RESOLUTION_DEAD_ACTOR = "resolution_dead_actor"
    RESOLUTION_DEFERRED = "resolution_deferred"
    TICK_COMMITTED = "tick_committed"
    CANDIDATE_ABORTED = "candidate_aborted"
    LIFECYCLE_MISUSE = "lifecycle_misuse"
    TOKEN_STALE = "token_stale"
    TOKEN_REPLAY = "token_replay"
    TOKEN_CROSS_ENGINE = "token_cross_engine"
    CHECKPOINT_RESTORE = "checkpoint_restore"
    CHECKPOINT_FALLBACK = "checkpoint_fallback"
    CHECKPOINT_CORRUPT = "checkpoint_corrupt"
    PROJECTION_FAILED = "projection_failed"
    DURABLE_PREPARE = "durable_prepare"
    DURABLE_APPEND = "durable_append"
    DURABLE_FINALIZE = "durable_finalize"
    DURABLE_COMMITTED = "durable_committed"
    DURABLE_IDEMPOTENT = "durable_idempotent_retry"
    DURABLE_FENCED = "durable_fenced"
    DURABLE_FAILED = "durable_failed"


class ActionResolutionStatus(StrEnum):
    """Closed per-submission outcome category for one resolved tick."""

    APPLIED = "applied"
    REJECTED = "rejected"
    CONFLICTED = "conflicted"
    DUPLICATE = "duplicate"
    DEAD_ACTOR = "dead_actor"
    DEFERRED_POLICY = "deferred_policy"


class ActionResolutionReason(StrEnum):
    """Closed reason codes correlating status to validation/rule outcomes."""

    OCCURRENCE = "occurrence"
    STRUCTURAL_REJECTION = "structural_rejection"
    INVALID_TARGET = "invalid_target"
    MISSING_ACTOR_BODY = "missing_actor_body"
    DEAD_ACTOR = "dead_actor"
    DUPLICATE_SUBMISSION = "duplicate_submission"
    CONFLICT_WITH_PRIOR = "conflict_with_prior"
    DEFERRED_POLICY = "deferred_policy"
    MALFORMED_SUBMISSION = "malformed_submission"


_STATUS_TYPES: Final[frozenset[ActionResolutionStatus]] = frozenset(
    ActionResolutionStatus
)
_REASON_TYPES: Final[frozenset[ActionResolutionReason]] = frozenset(
    ActionResolutionReason
)


@dataclass(frozen=True, slots=True)
class TickToken:
    """Engine-issued capability binding submissions to one open tick.

    Callers must not invent tokens for authority; only the issuing engine
    accepts the token it produced for the current open tick.
    """

    value: str
    tick: Tick

    def __post_init__(self) -> None:
        require_stable_id("TickToken.value", self.value)
        if type(self.tick) is not Tick:
            raise TypeError("TickToken.tick must be Tick")


@dataclass(frozen=True, slots=True)
class ObservationBatch:
    """Ordered observations produced from one tick starting snapshot."""

    tick: Tick
    revision: WorldRevision
    token: TickToken
    observations: Sequence[Observation]

    def __post_init__(self) -> None:
        if type(self.tick) is not Tick:
            raise TypeError("ObservationBatch.tick must be Tick")
        if type(self.revision) is not WorldRevision:
            raise TypeError("ObservationBatch.revision must be WorldRevision")
        if type(self.token) is not TickToken:
            raise TypeError("ObservationBatch.token must be TickToken")
        if self.token.tick != self.tick:
            raise ValueError("ObservationBatch.token.tick must match batch tick")
        object.__setattr__(
            self,
            "observations",
            _copy_observations("ObservationBatch.observations", self.observations),
        )


@dataclass(frozen=True, slots=True)
class ActionSubmission:
    """Authenticated public submission. No ordinals, request IDs, or actor EntityIds."""

    token: TickToken
    agent_id: AgentId
    command: AgentCommand

    def __post_init__(self) -> None:
        if type(self.token) is not TickToken:
            raise TypeError("ActionSubmission.token must be TickToken")
        if type(self.agent_id) is not AgentId:
            raise TypeError("ActionSubmission.agent_id must be AgentId")
        object.__setattr__(
            self, "command", require_agent_command(self.command)
        )


def require_action_submission(value: object) -> ActionSubmission:
    """Accept only exact ActionSubmission; reject mappings and subclasses."""
    if isinstance(value, Mapping):
        raise TypeError("raw mappings are not action submissions")
    if isinstance(value, (set, frozenset)):
        raise TypeError("sets are not action submissions")
    if type(value) is not ActionSubmission:
        raise TypeError(
            f"action submission must be ActionSubmission, not {type(value).__name__}"
        )
    return value


@dataclass(frozen=True, slots=True)
class ActionResolution:
    """Immutable per-submission outcome after deterministic tick resolution."""

    ordinal: int
    agent_id: AgentId
    command: AgentCommand
    status: ActionResolutionStatus
    reason: ActionResolutionReason
    tick: Tick
    base_revision: WorldRevision
    resulting_revision: WorldRevision
    request_id: RequestId

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "ordinal",
            require_exact_nonneg_int("ActionResolution.ordinal", self.ordinal),
        )
        if type(self.agent_id) is not AgentId:
            raise TypeError("ActionResolution.agent_id must be AgentId")
        object.__setattr__(
            self, "command", require_agent_command(self.command)
        )
        if type(self.status) is not ActionResolutionStatus:
            raise TypeError(
                "ActionResolution.status must be ActionResolutionStatus"
            )
        if self.status not in _STATUS_TYPES:
            raise ValueError("ActionResolution.status must be a closed status")
        if type(self.reason) is not ActionResolutionReason:
            raise TypeError(
                "ActionResolution.reason must be ActionResolutionReason"
            )
        if self.reason not in _REASON_TYPES:
            raise ValueError("ActionResolution.reason must be a closed reason")
        if type(self.tick) is not Tick:
            raise TypeError("ActionResolution.tick must be Tick")
        if type(self.base_revision) is not WorldRevision:
            raise TypeError("ActionResolution.base_revision must be WorldRevision")
        if type(self.resulting_revision) is not WorldRevision:
            raise TypeError(
                "ActionResolution.resulting_revision must be WorldRevision"
            )
        if type(self.request_id) is not RequestId:
            raise TypeError("ActionResolution.request_id must be RequestId")
        if self.resulting_revision.value < self.base_revision.value:
            raise ValueError(
                "ActionResolution.resulting_revision must be >= base_revision"
            )


@dataclass(frozen=True, slots=True)
class TickEventRecord:
    """Objective event paired with engine-assigned intra-tick emission order."""

    sequence: int
    event: WorldEvent

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "sequence",
            require_exact_nonneg_int("TickEventRecord.sequence", self.sequence),
        )
        if type(self.event) is not WorldEvent:
            raise TypeError("TickEventRecord.event must be WorldEvent")
        if self.event.sequence != self.sequence:
            raise ValueError(
                "TickEventRecord.sequence must match WorldEvent.sequence"
            )


@dataclass(frozen=True, slots=True)
class TickResult:
    """Detached outcome of one successfully committed tick resolution."""

    tick: Tick
    resulting_tick: Tick
    base_revision: WorldRevision
    resulting_revision: WorldRevision
    resolutions: Sequence[ActionResolution]
    events: Sequence[TickEventRecord]

    def __post_init__(self) -> None:
        if type(self.tick) is not Tick:
            raise TypeError("TickResult.tick must be Tick")
        if type(self.resulting_tick) is not Tick:
            raise TypeError("TickResult.resulting_tick must be Tick")
        if self.resulting_tick.value != self.tick.value + 1:
            raise ValueError(
                "TickResult.resulting_tick must be exactly tick + 1"
            )
        if type(self.base_revision) is not WorldRevision:
            raise TypeError("TickResult.base_revision must be WorldRevision")
        if type(self.resulting_revision) is not WorldRevision:
            raise TypeError("TickResult.resulting_revision must be WorldRevision")
        if self.resulting_revision.value < self.base_revision.value:
            raise ValueError(
                "TickResult.resulting_revision must be >= base_revision"
            )
        if self.resulting_revision.value > self.base_revision.value + 1:
            raise ValueError(
                "TickResult.resulting_revision may advance by at most one"
            )
        object.__setattr__(
            self,
            "resolutions",
            _copy_resolutions("TickResult.resolutions", self.resolutions),
        )
        object.__setattr__(
            self,
            "events",
            _copy_tick_events("TickResult.events", self.events),
        )
        for resolution in self.resolutions:
            if resolution.tick != self.tick:
                raise ValueError("ActionResolution.tick must match TickResult.tick")
            if resolution.base_revision != self.base_revision:
                raise ValueError(
                    "ActionResolution.base_revision must match TickResult"
                )
            if resolution.resulting_revision != self.resulting_revision:
                raise ValueError(
                    "ActionResolution.resulting_revision must match TickResult"
                )
        for record in self.events:
            if record.event.resulting_revision != self.resulting_revision:
                raise ValueError(
                    "TickEventRecord.event.revision must match resulting_revision"
                )
            if record.event.tick != self.tick.value:
                raise ValueError(
                    "TickEventRecord.event.tick must match TickResult.tick"
                )


def _copy_observations(
    name: str, values: Sequence[Observation]
) -> tuple[Observation, ...]:
    if isinstance(values, (set, frozenset, Mapping)):
        raise TypeError(f"{name} must be an ordered sequence")
    if isinstance(values, (str, bytes, bytearray)) or not isinstance(values, Sequence):
        raise TypeError(f"{name} must be an ordered sequence")
    copied = tuple(values)
    for value in copied:
        if type(value) is not Observation:
            raise TypeError(f"{name} entries must be Observation")
    return copied


def _copy_resolutions(
    name: str, values: Sequence[ActionResolution]
) -> tuple[ActionResolution, ...]:
    if isinstance(values, (set, frozenset, Mapping)):
        raise TypeError(f"{name} must be an ordered sequence")
    if isinstance(values, (str, bytes, bytearray)) or not isinstance(values, Sequence):
        raise TypeError(f"{name} must be an ordered sequence")
    copied = tuple(values)
    seen_ordinals: set[int] = set()
    for value in copied:
        if type(value) is not ActionResolution:
            raise TypeError(f"{name} entries must be ActionResolution")
        if value.ordinal in seen_ordinals:
            raise ValueError(f"{name} must not contain duplicate ordinals")
        seen_ordinals.add(value.ordinal)
    return copied


def _copy_tick_events(
    name: str, values: Sequence[TickEventRecord]
) -> tuple[TickEventRecord, ...]:
    if isinstance(values, (set, frozenset, Mapping)):
        raise TypeError(f"{name} must be an ordered sequence")
    if isinstance(values, (str, bytes, bytearray)) or not isinstance(values, Sequence):
        raise TypeError(f"{name} must be an ordered sequence")
    copied = tuple(values)
    seen_sequences: set[int] = set()
    events: list[WorldEvent] = []
    for index, value in enumerate(copied):
        if type(value) is not TickEventRecord:
            raise TypeError(f"{name} entries must be TickEventRecord")
        if value.sequence in seen_sequences:
            raise ValueError(f"{name} must not contain duplicate sequences")
        seen_sequences.add(value.sequence)
        if value.sequence != index:
            raise ValueError(f"{name} sequences must be contiguous from 0")
        events.append(value.event)
    normalize_events(events)
    return copied
