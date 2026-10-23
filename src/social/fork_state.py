"""Immutable owner-scoped fork state for the in-memory relationship service."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from agents.models import AgentId
from social.models import RelationshipId
from social.relationships import (
    DirectedRelationshipProfile,
    RelationshipFormationPolicy,
    RelationshipRevision,
    RelationshipRevisionResult,
)

RELATIONSHIP_FORK_STATE_VERSION: Final[str] = "relationship-fork-state-v1"


class RelationshipForkStateError(ValueError):
    """Fail-closed relationship fork-state validation with a stable code."""

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        super().__init__(f"{code}: {detail or code}")


def _ordered[T](name: str, values: object, model_type: type[T]) -> tuple[T, ...]:
    if isinstance(values, (set, frozenset, Mapping)):
        raise RelationshipForkStateError(
            "fork_state_invalid", f"{name} must be ordered"
        )
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise RelationshipForkStateError(
            "fork_state_invalid", f"{name} must be a sequence"
        )
    items = tuple(values)
    for item in items:
        if type(item) is not model_type:
            raise RelationshipForkStateError(
                "fork_state_invalid", f"{name} entries must be {model_type.__name__}"
            )
    return items


@dataclass(frozen=True, slots=True)
class RelationshipOperation:
    """One idempotency receipt retained by the relationship service."""

    operation_id: str
    fingerprint: str
    result: RelationshipRevisionResult

    def __post_init__(self) -> None:
        if type(self.operation_id) is not str or not self.operation_id:
            raise RelationshipForkStateError(
                "fork_state_invalid", "invalid operation_id"
            )
        if type(self.fingerprint) is not str or not self.fingerprint:
            raise RelationshipForkStateError(
                "fork_state_invalid", "invalid fingerprint"
            )
        if type(self.result) is not RelationshipRevisionResult:
            raise RelationshipForkStateError("fork_state_invalid", "invalid result")


@dataclass(frozen=True, slots=True)
class RelationshipForkState:
    """Complete continuation state for one directed relationship service."""

    owner_id: AgentId
    policy: RelationshipFormationPolicy
    profiles: tuple[DirectedRelationshipProfile, ...]
    histories: tuple[tuple[RelationshipId, tuple[RelationshipRevision, ...]], ...]
    operations: tuple[RelationshipOperation, ...]
    state_format_version: str = RELATIONSHIP_FORK_STATE_VERSION

    def __post_init__(self) -> None:
        if self.state_format_version != RELATIONSHIP_FORK_STATE_VERSION:
            raise RelationshipForkStateError(
                "fork_state_unsupported", "unsupported relationship fork-state version"
            )
        if type(self.owner_id) is not AgentId:
            raise RelationshipForkStateError("fork_state_invalid", "invalid owner")
        if type(self.policy) is not RelationshipFormationPolicy:
            raise RelationshipForkStateError("fork_state_invalid", "invalid policy")
        profiles = _ordered(
            "profiles", self.profiles, DirectedRelationshipProfile
        )
        if isinstance(self.histories, (set, frozenset, Mapping)) or not isinstance(
            self.histories, Sequence
        ):
            raise RelationshipForkStateError("fork_state_invalid", "invalid histories")
        histories: list[
            tuple[RelationshipId, tuple[RelationshipRevision, ...]]
        ] = []
        profile_ids: set[RelationshipId] = set()
        for entry in self.histories:
            if not isinstance(entry, tuple) or len(entry) != 2:
                raise RelationshipForkStateError(
                    "fork_state_invalid", "invalid history entry"
                )
            relationship_id, revisions = entry
            if type(relationship_id) is not RelationshipId:
                raise RelationshipForkStateError(
                    "fork_state_invalid", "invalid history key"
                )
            if isinstance(revisions, (str, bytes)) or not isinstance(
                revisions, Sequence
            ):
                raise RelationshipForkStateError(
                    "fork_state_invalid", "invalid history revisions"
                )
            raw_revisions = tuple(revisions)
            if not raw_revisions:
                raise RelationshipForkStateError(
                    "fork_state_invalid", "empty history"
                )
            for revision in raw_revisions:
                if type(revision) is not RelationshipRevision:
                    raise RelationshipForkStateError(
                        "fork_state_invalid", "invalid revision"
                    )
                if revision.relationship_id != relationship_id:
                    raise RelationshipForkStateError(
                        "fork_state_invalid", "history relationship mismatch"
                    )
            histories.append((relationship_id, raw_revisions))
        for profile in profiles:
            if profile.source_id != self.owner_id:
                raise RelationshipForkStateError(
                    "fork_owner_mismatch", "profile owner does not match state owner"
                )
            if profile.relationship_id in profile_ids:
                raise RelationshipForkStateError(
                    "fork_state_invalid", "duplicate relationship_id"
                )
            profile_ids.add(profile.relationship_id)
        history_ids = {relationship_id for relationship_id, _ in histories}
        if history_ids != profile_ids:
            raise RelationshipForkStateError(
                "fork_state_invalid", "profiles and histories disagree"
            )
        for profile in profiles:
            history = next(
                revisions
                for relationship_id, revisions in histories
                if relationship_id == profile.relationship_id
            )
            if history[-1].revision_id != profile.current_revision_id:
                raise RelationshipForkStateError(
                    "fork_state_invalid", "relationship history head mismatch"
                )
        operations = _ordered(
            "operations", self.operations, RelationshipOperation
        )
        seen_ops: set[str] = set()
        for operation in operations:
            if operation.operation_id in seen_ops:
                raise RelationshipForkStateError(
                    "fork_state_invalid", "duplicate relationship operation"
                )
            seen_ops.add(operation.operation_id)
            if operation.result.relationship_id not in profile_ids:
                raise RelationshipForkStateError(
                    "fork_state_invalid", "operation references unknown relationship"
                )
        object.__setattr__(self, "profiles", profiles)
        object.__setattr__(self, "histories", tuple(histories))
        object.__setattr__(self, "operations", operations)

    def history_for(
        self, relationship_id: RelationshipId
    ) -> tuple[RelationshipRevision, ...]:
        for current_id, revisions in self.histories:
            if current_id == relationship_id:
                return revisions
        raise RelationshipForkStateError(
            "fork_state_invalid", "missing relationship history"
        )


__all__ = [
    "RELATIONSHIP_FORK_STATE_VERSION",
    "RelationshipForkState",
    "RelationshipForkStateError",
    "RelationshipOperation",
]
