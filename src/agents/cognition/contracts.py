"""Architecture-neutral cognition strategy and async component protocols.

``Perspective`` remains the sole ``CognitionStrategy.propose()`` input.
``CognitiveLoop`` uses narrow async stage protocols with typed Task-1
artifacts. Components must not accept ``WorldState``, ``World``, engine
snapshots, raw event batches, repositories, mutable writers, or another
agent's observation.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from agents.cognition.models import (
    ActionPlan,
    CognitiveLoopInput,
    InterpretedPerception,
    MemoryUpdateIntent,
    MotivationEvaluation,
    PossibleFutures,
    RetrievedMemoryContext,
    SelectedIntention,
    SelfModel,
    SituationModel,
    SubjectiveSnapshot,
)
from agents.models import AgentId
from memory.beliefs import SemanticBelief
from memory.models import Belief, MemoryTrace
from social.models import CommunicationEnvelope
from social.relationships import DirectedRelationshipProfile
from world.actions import AgentCommand
from world.observations import Observation

__all__ = [
    "CognitionContractError",
    "CognitionContractErrorCode",
    "CognitionStrategy",
    "FutureImagination",
    "IntentionSelector",
    "MemoryRetriever",
    "MemoryUpdateHook",
    "MotivationEvaluator",
    "PerceptionInterpreter",
    "Perspective",
    "Planner",
    "SelfStateProjector",
    "SituationModeler",
]


class CognitionContractErrorCode(StrEnum):
    """Stable contract failure codes (no payload or exception text)."""

    TYPE_MISMATCH = "type_mismatch"
    OWNERSHIP = "ownership"
    INVALID_SEQUENCE = "invalid_sequence"


class CognitionContractError(Exception):
    """Fail-closed boundary error exposing only safe identifiers."""

    def __init__(
        self,
        code: CognitionContractErrorCode,
        *,
        component: str,
        ordinal: int | None = None,
    ) -> None:
        if type(code) is not CognitionContractErrorCode:
            raise TypeError("code must be CognitionContractErrorCode")
        component_name = component.strip()
        if not component_name:
            raise ValueError("component must be non-blank")
        self.code = code
        self.component = component_name
        self.ordinal = ordinal
        parts = [f"code={code.value}", f"component={component_name}"]
        if ordinal is not None:
            parts.append(f"ordinal={ordinal}")
        super().__init__(",".join(parts))

    def log_fields(self) -> dict[str, object]:
        fields: dict[str, object] = {
            "code": self.code.value,
            "component": self.component,
        }
        if self.ordinal is not None:
            fields["ordinal"] = self.ordinal
        return fields

    def __repr__(self) -> str:
        return f"CognitionContractError({self})"


def _owned_tuple(
    name: str,
    values: Sequence[object],
    *,
    model_type: type,
    owner_id: AgentId,
) -> tuple[object, ...]:
    if isinstance(values, (set, frozenset)):
        raise TypeError(f"{name} must be an ordered sequence")
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise TypeError(f"{name} must be an ordered sequence")
    items = tuple(values)
    for item in items:
        if type(item) is not model_type:
            raise TypeError(f"{name} entries must be {model_type.__name__}")
        item_owner = item.owner_id  # type: ignore[attr-defined]
        if item_owner != owner_id:
            raise ValueError(f"{name} entries must belong to perspective agent")
    return items


@dataclass(frozen=True, slots=True)
class Perspective:
    """Immutable cognition context. Contains no LLM, store, or world authority.

    ``inbox`` is out-of-band social mail addressed to ``agent_id``. Perceived
    communication claims remain on ``observation.communications`` only.
    """

    agent_id: AgentId
    observation: Observation
    memories: tuple[MemoryTrace, ...]
    beliefs: tuple[Belief, ...]
    inbox: tuple[CommunicationEnvelope, ...]
    semantic_beliefs: tuple[SemanticBelief, ...] = ()
    relationships: tuple[DirectedRelationshipProfile, ...] = ()
    snapshot_revision: int = 0

    def __post_init__(self) -> None:
        if type(self.agent_id) is not AgentId:
            raise TypeError("Perspective.agent_id must be AgentId")
        if type(self.observation) is not Observation:
            raise TypeError("Perspective.observation must be Observation")
        object.__setattr__(
            self,
            "memories",
            _owned_tuple(
                "Perspective.memories",
                self.memories,
                model_type=MemoryTrace,
                owner_id=self.agent_id,
            ),
        )
        object.__setattr__(
            self,
            "beliefs",
            _owned_tuple(
                "Perspective.beliefs",
                self.beliefs,
                model_type=Belief,
                owner_id=self.agent_id,
            ),
        )
        object.__setattr__(
            self,
            "semantic_beliefs",
            _owned_tuple(
                "Perspective.semantic_beliefs",
                self.semantic_beliefs,
                model_type=SemanticBelief,
                owner_id=self.agent_id,
            ),
        )
        if isinstance(self.relationships, (set, frozenset)):
            raise TypeError("Perspective.relationships must be an ordered sequence")
        if isinstance(self.relationships, (str, bytes)) or not isinstance(
            self.relationships, Sequence
        ):
            raise TypeError("Perspective.relationships must be an ordered sequence")
        relationships = tuple(self.relationships)
        for profile in relationships:
            if type(profile) is not DirectedRelationshipProfile:
                raise TypeError(
                    "Perspective.relationships entries must be "
                    "DirectedRelationshipProfile"
                )
            if profile.source_id != self.agent_id:
                raise ValueError(
                    "Perspective.relationships source_id must match agent_id"
                )
        object.__setattr__(self, "relationships", relationships)
        from world.identifiers import require_exact_nonneg_int

        object.__setattr__(
            self,
            "snapshot_revision",
            require_exact_nonneg_int(
                "Perspective.snapshot_revision", self.snapshot_revision
            ),
        )
        if isinstance(self.inbox, (set, frozenset)):
            raise TypeError("Perspective.inbox must be an ordered sequence")
        if isinstance(self.inbox, (str, bytes)) or not isinstance(self.inbox, Sequence):
            raise TypeError("Perspective.inbox must be an ordered sequence")
        inbox = tuple(self.inbox)
        for envelope in inbox:
            if type(envelope) is not CommunicationEnvelope:
                raise TypeError(
                    "Perspective.inbox entries must be CommunicationEnvelope"
                )
            if envelope.recipient_id != self.agent_id:
                raise ValueError(
                    "Perspective.inbox envelope recipient_id must match agent_id"
                )
        object.__setattr__(self, "inbox", inbox)

    def to_snapshot(self) -> SubjectiveSnapshot:
        """Freeze this perspective into a ``SubjectiveSnapshot``."""
        return SubjectiveSnapshot(
            owner_id=self.agent_id,
            revision=self.snapshot_revision,
            memories=self.memories,
            legacy_beliefs=self.beliefs,
            semantic_beliefs=self.semantic_beliefs,
            relationships=self.relationships,
        )

    def __repr__(self) -> str:
        return (
            f"Perspective(agent_id={self.agent_id.value!r}, "
            f"memory_count={len(self.memories)}, "
            f"belief_count={len(self.beliefs)}, "
            f"semantic_belief_count={len(self.semantic_beliefs)}, "
            f"relationship_count={len(self.relationships)}, "
            f"inbox_count={len(self.inbox)}, "
            f"snapshot_revision={self.snapshot_revision})"
        )


class CognitionStrategy(Protocol):
    """Produce a non-authoritative command from an immutable perspective."""

    def propose(self, perspective: Perspective) -> AgentCommand:
        """Return an agent command. Must not mutate world state."""
        ...


class PerceptionInterpreter(Protocol):
    """Interpret one observation into structured perception claims."""

    async def interpret(self, loop_input: CognitiveLoopInput) -> InterpretedPerception:
        """Return interpreted perception for ``loop_input.agent_id`` only."""
        ...


class MemoryRetriever(Protocol):
    """Read-only owner-scoped memory/belief retrieval."""

    async def retrieve(
        self,
        loop_input: CognitiveLoopInput,
        perception: InterpretedPerception,
    ) -> RetrievedMemoryContext:
        """Return references only; must not mutate memory stores."""
        ...


class SituationModeler(Protocol):
    """Build a situation model from perception and memory context."""

    async def model(
        self,
        loop_input: CognitiveLoopInput,
        perception: InterpretedPerception,
        memory: RetrievedMemoryContext,
    ) -> SituationModel: ...


class SelfStateProjector(Protocol):
    """Project an emergent self-model from owner-scoped beliefs."""

    async def project(
        self,
        loop_input: CognitiveLoopInput,
        situation: SituationModel,
        memory: RetrievedMemoryContext,
    ) -> SelfModel: ...


class FutureImagination(Protocol):
    """Produce bounded imagined futures (placeholder or later LLM-backed)."""

    async def imagine(
        self,
        loop_input: CognitiveLoopInput,
        situation: SituationModel,
        self_state: SelfModel,
    ) -> PossibleFutures: ...


class MotivationEvaluator(Protocol):
    """Score closed motives from situation, self-state, and futures."""

    async def evaluate(
        self,
        loop_input: CognitiveLoopInput,
        situation: SituationModel,
        self_state: SelfModel,
        futures: PossibleFutures,
    ) -> MotivationEvaluation: ...


class IntentionSelector(Protocol):
    """Select one closed intention from motivation scores."""

    async def select(
        self,
        loop_input: CognitiveLoopInput,
        motivation: MotivationEvaluation,
    ) -> SelectedIntention: ...


class Planner(Protocol):
    """Construct a fresh closed ``AgentCommand`` plan from the intention."""

    async def plan(
        self,
        loop_input: CognitiveLoopInput,
        intention: SelectedIntention,
        futures: PossibleFutures,
    ) -> ActionPlan: ...


class MemoryUpdateHook(Protocol):
    """Return post-cognition memory/belief write intents (no store mutation)."""

    async def propose_updates(
        self,
        loop_input: CognitiveLoopInput,
        plan: ActionPlan,
        perception: InterpretedPerception,
        memory: RetrievedMemoryContext,
        intention: SelectedIntention,
    ) -> tuple[MemoryUpdateIntent, ...]: ...
