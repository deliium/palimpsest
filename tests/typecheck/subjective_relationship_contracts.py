"""Mypy fixtures for subjective relationship contracts."""

from __future__ import annotations

from agents.models import AgentId
from social.contracts import RelationshipService
from social.models import RelationshipId
from social.relationships import (
    DirectedRelationshipProfile,
    RelationshipActivationState,
    RelationshipFormationPolicy,
    RelationshipHistory,
    RelationshipInteractionSignal,
    RelationshipRevisionId,
    RelationshipRevisionRequest,
    RelationshipRevisionResult,
    RelationshipSignalKind,
)


class _StubRelationshipService:
    def __init__(self) -> None:
        self._source_id = AgentId("alice")

    @property
    def source_id(self) -> AgentId:
        return self._source_id

    async def revise(
        self, request: RelationshipRevisionRequest
    ) -> RelationshipRevisionResult:
        _ = request
        return RelationshipRevisionResult(
            relationship_id=RelationshipId("rp-1"),
            revision_id=RelationshipRevisionId("rr-1"),
            revision_ordinal=0,
            changed_dimension_count=1,
            evidence_count=1,
            idempotent=False,
            created=True,
            activation_state=RelationshipActivationState.ACTIVE,
        )

    async def get(
        self, relationship_id: RelationshipId
    ) -> DirectedRelationshipProfile | None:
        _ = relationship_id
        return None

    async def snapshot(self) -> tuple[DirectedRelationshipProfile, ...]:
        return ()


def _service_is_protocol() -> RelationshipService:
    return _StubRelationshipService()


def _request() -> RelationshipRevisionRequest:
    return RelationshipRevisionRequest(
        source_id=AgentId("alice"),
        target_id=AgentId("bob"),
        operation_id="op-1",
        logical_tick=0,
        signals=(
            RelationshipInteractionSignal(
                counterpart_id=AgentId("bob"),
                kind=RelationshipSignalKind.COMMUNICATION,
                strength=0.5,
                memory_ref="m-1",
                lineage_root_ref="m-1",
                source_tick=0,
            ),
        ),
        policy=RelationshipFormationPolicy(policy_id="rel", version="1").as_ref(),
    )


def _history_type() -> type[RelationshipHistory]:
    return RelationshipHistory
