"""Per-agent runtime lifecycle bridging cognition and WorldEngine admission.

Owns start/active/terminal transitions, builds perspectives, invokes
``CognitiveLoop``, applies owner-scoped memory update intents, and constructs
``ActionSubmission`` values from a caller-supplied ``TickToken``. Never calls
private world admission/operations and never exposes ``TickToken`` to cognition.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Sequence
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import TYPE_CHECKING, Final, Protocol

from agents.cognition.loop import CognitiveLoop, CognitiveLoopError
from agents.cognition.models import (
    AgentEmotionalState,
    CognitiveLoopInput,
    CognitiveLoopProposal,
    CognitiveLoopResult,
    ComponentKind,
    EmotionalStateEvaluation,
    GoalBoard,
    GoalTransitionIntent,
    GoalTransitionIntentReason,
    InternalAgentState,
    MemoryUpdateIntent,
    MemoryUpdateKind,
)
from agents.models import Agent, AgentId, GoalOutcomeKind, GoalStatus
from memory.contracts import (
    BeliefReader,
    BeliefWriter,
    MemoryReader,
    MemoryService,
    MemoryWriter,
    SemanticBeliefReader,
)
from memory.models import (
    Belief,
    MemoryAccessReceipt,
    MemoryMutationBatch,
    MemoryTrace,
)
from memory.service import MemoryServiceError
from simulation.bootstrap import RegistrationTranslator
from simulation.cognition_trace import (
    CognitionTraceRepository,
    NullCognitionTraceRepository,
    maybe_append_cognition_trace,
)
from simulation.evidence import GoalRevisionRecord, encode_goal_transition_receipt
from simulation.lifecycle import ActionSubmission, TickToken, require_action_submission
from simulation.models import RunId
from simulation.perception import build_perspective
from simulation.runner_models import (
    CognitionTraceSpec,
    GoalTransitionReasonCode,
    GoalTransitionReceipt,
)
from simulation.subjective_state import (
    SubjectiveMutationBatch,
    SubjectiveStateError,
    SubjectiveStateService,
    subjective_operation_id,
)
from social.contracts import RelationshipReader
from social.models import CommunicationEnvelope
from world.actions import AgentCommand, require_agent_command
from world.identifiers import require_stable_id
from world.models import LifeStatus
from world.observations import Observation

if TYPE_CHECKING:
    from simulation.persistence import ScientificEvidenceRepository

__all__ = [
    "AgentRuntime",
    "AgentRuntimeError",
    "AgentRuntimeErrorCode",
    "AgentRuntimeStatus",
    "AgentStepResult",
    "InboxSource",
    "InvocationIdSource",
    "PendingRuntimeFinalization",
    "PreparedObservation",
    "pending_from_finalization_command",
]

_LOG: Final[logging.Logger] = logging.getLogger("simulation.agent_runtime")


class AgentRuntimeStatus(StrEnum):
    """Closed runtime lifecycle states."""

    CREATED = "created"
    ACTIVE = "active"
    TERMINAL = "terminal"


class AgentRuntimeErrorCode(StrEnum):
    """Stable lifecycle failure codes for WARN/ERROR logs."""

    NOT_STARTED = "not_started"
    ALREADY_STARTED = "already_started"
    TERMINAL = "terminal"
    DUPLICATE_OBSERVATION = "duplicate_observation"
    OWNERSHIP = "ownership"
    COGNITION_FAILED = "cognition_failed"
    INVALID_UPDATE = "invalid_update"
    INVALID_INPUT = "invalid_input"
    MEMORY_APPLY_FAILED = "memory_apply_failed"
    SUBJECTIVE_APPLY_FAILED = "subjective_apply_failed"
    PENDING_EXISTS = "pending_exists"
    PENDING_MISSING = "pending_missing"
    PENDING_MISMATCH = "pending_mismatch"
    FINALIZE_IDEMPOTENT = "finalize_idempotent"
    RECOVERY_CORRUPT = "recovery_corrupt"
    RECOVERY_LEGACY = "recovery_legacy"


class AgentRuntimeError(Exception):
    """Fail-closed runtime error with metadata-only public surface."""

    def __init__(
        self,
        code: AgentRuntimeErrorCode,
        *,
        agent_id: str,
        invocation_id: str | None = None,
        tick: int | None = None,
    ) -> None:
        if type(code) is not AgentRuntimeErrorCode:
            raise TypeError("code must be AgentRuntimeErrorCode")
        self.code = code
        self.agent_id = agent_id
        self.invocation_id = invocation_id
        self.tick = tick
        parts = [f"code={code.value}", f"agent_id={agent_id}"]
        if invocation_id is not None:
            parts.append(f"invocation_id={invocation_id}")
        if tick is not None:
            parts.append(f"tick={tick}")
        super().__init__(",".join(parts))

    def log_fields(self) -> dict[str, object]:
        fields: dict[str, object] = {
            "code": self.code.value,
            "agent_id": self.agent_id,
        }
        if self.invocation_id is not None:
            fields["invocation_id"] = self.invocation_id
        if self.tick is not None:
            fields["tick"] = self.tick
        return fields

    def __repr__(self) -> str:
        return f"AgentRuntimeError({self})"


class InboxSource(Protocol):
    """Out-of-band social inbox for one agent (may return empty)."""

    def envelopes_for(self, agent_id: AgentId) -> Sequence[CommunicationEnvelope]: ...


class InvocationIdSource(Protocol):
    """Deterministic opaque invocation id allocator."""

    def next_id(self, *, agent_id: AgentId, tick: int) -> str: ...


@dataclass(frozen=True, slots=True)
class PreparedObservation:
    """Deliberation-only result. No subjective mutation has occurred."""

    observation_key: tuple[int, int]
    tick: int
    invocation_id: str
    token: TickToken
    proposal: CognitiveLoopProposal
    prior_status: AgentRuntimeStatus

    def __post_init__(self) -> None:
        require_stable_id("PreparedObservation.invocation_id", self.invocation_id)
        if type(self.proposal) is not CognitiveLoopProposal:
            raise TypeError("proposal must be CognitiveLoopProposal")
        if type(self.token) is not TickToken:
            raise TypeError("token must be TickToken")
        if type(self.prior_status) is not AgentRuntimeStatus:
            raise TypeError("prior_status must be AgentRuntimeStatus")

    def __repr__(self) -> str:
        return (
            f"PreparedObservation(invocation_id={self.invocation_id!r}, "
            f"tick={self.tick}, status={self.prior_status.value!r})"
        )


@dataclass(frozen=True, slots=True)
class PendingRuntimeFinalization:
    """Detached runtime transition awaiting post-objective finalize."""

    observation_key: tuple[int, int]
    tick: int
    invocation_id: str
    submission: ActionSubmission
    loop_result: CognitiveLoopResult
    prior_status: AgentRuntimeStatus
    next_status: AgentRuntimeStatus
    next_internal_state: InternalAgentState
    subjective_batch: SubjectiveMutationBatch | None
    effective_command_kind: str
    integrity_hash: str
    has_futures_boundary: bool = False
    finalized: bool = False

    def __post_init__(self) -> None:
        require_stable_id(
            "PendingRuntimeFinalization.invocation_id", self.invocation_id
        )
        object.__setattr__(
            self, "submission", require_action_submission(self.submission)
        )
        if type(self.loop_result) is not CognitiveLoopResult:
            raise TypeError("loop_result must be CognitiveLoopResult")
        if type(self.next_internal_state) is not InternalAgentState:
            raise TypeError("next_internal_state must be InternalAgentState")
        require_stable_id(
            "PendingRuntimeFinalization.effective_command_kind",
            self.effective_command_kind,
        )
        require_stable_id(
            "PendingRuntimeFinalization.integrity_hash", self.integrity_hash
        )
        if type(self.has_futures_boundary) is not bool:
            raise TypeError("has_futures_boundary must be bool")
        if type(self.finalized) is not bool:
            raise TypeError("finalized must be bool")

    def __repr__(self) -> str:
        return (
            f"PendingRuntimeFinalization(invocation_id={self.invocation_id!r}, "
            f"tick={self.tick}, command_kind={self.effective_command_kind!r}, "
            f"finalized={self.finalized})"
        )

    def to_finalization_command(self, *, run_id: object) -> object:
        """Build the durable finalization command for this pending transition."""
        from simulation.models import RunId
        from simulation.run_control import (
            FINALIZATION_COMMAND_CODEC_VERSION,
            FinalizationCommand,
        )

        if type(run_id) is not RunId:
            raise TypeError("run_id must be RunId")
        legacy_beliefs: list[Belief] = []
        for intent in self.loop_result.memory_update_intents:
            if (
                intent.kind is MemoryUpdateKind.WRITE_BELIEF
                and intent.belief is not None
            ):
                legacy_beliefs.append(intent.belief)
        delivery_id = f"{run_id.value}:{self.invocation_id}:delivery"
        content_material = (
            f"{run_id.value}|{self.invocation_id}|{self.integrity_hash}|tick"
        ).encode()
        delivery_hash = hashlib.sha256(content_material).hexdigest()
        return FinalizationCommand(
            codec_version=FINALIZATION_COMMAND_CODEC_VERSION,
            run_id=run_id,
            agent_id=self.submission.agent_id,
            tick=self.tick,
            invocation_id=self.invocation_id,
            observation_key=self.observation_key,
            prior_status=self.prior_status,
            next_status=self.next_status,
            effective_command_kind=self.effective_command_kind,
            integrity_hash=self.integrity_hash,
            next_internal_state=self.next_internal_state,
            submission=self.submission,
            subjective_batch=self.subjective_batch,
            has_futures_boundary=self.has_futures_boundary,
            final_confidence=self.loop_result.final_confidence,
            legacy_belief_writes=tuple(legacy_beliefs),
            delivery_id=delivery_id,
            delivery_content_hash=delivery_hash,
            delivery_acknowledged=False,
        )


def pending_from_finalization_command(command: object) -> PendingRuntimeFinalization:
    """Rehydrate a pending transition from a durable finalization command."""
    from memory.models import Belief
    from simulation.run_control import FinalizationCommand

    if type(command) is not FinalizationCommand:
        raise TypeError("command must be FinalizationCommand")
    intents: list[MemoryUpdateIntent] = []
    for belief in command.legacy_belief_writes:
        if type(belief) is not Belief:
            raise TypeError("legacy_belief_writes entries must be Belief")
        intents.append(
            MemoryUpdateIntent(
                owner_id=command.agent_id,
                kind=MemoryUpdateKind.WRITE_BELIEF,
                belief=belief,
            )
        )
    loop_result = CognitiveLoopResult(
        invocation_id=command.invocation_id,
        agent_id=command.agent_id,
        command=command.submission.command,
        boundary_records=(),
        memory_update_intents=tuple(intents),
        final_confidence=command.final_confidence,
        internal_state=command.next_internal_state,
        pending_accesses=(),
        pending_reconsolidation=None,
    )
    return PendingRuntimeFinalization(
        observation_key=command.observation_key,
        tick=command.tick,
        invocation_id=command.invocation_id,
        submission=command.submission,
        loop_result=loop_result,
        prior_status=command.prior_status,
        next_status=command.next_status,
        next_internal_state=command.next_internal_state,
        subjective_batch=command.subjective_batch,
        effective_command_kind=command.effective_command_kind,
        integrity_hash=command.integrity_hash,
        has_futures_boundary=command.has_futures_boundary,
    )


@dataclass(frozen=True, slots=True)
class AgentStepResult:
    """Immutable result of one observation processing attempt."""

    status: AgentRuntimeStatus
    invocation_id: str | None
    tick: int
    submission: ActionSubmission | None
    loop_result: CognitiveLoopResult | None
    terminal: bool

    def __post_init__(self) -> None:
        if type(self.status) is not AgentRuntimeStatus:
            raise TypeError("status must be AgentRuntimeStatus")
        if self.invocation_id is not None:
            require_stable_id("AgentStepResult.invocation_id", self.invocation_id)
        if type(self.terminal) is not bool:
            raise TypeError("terminal must be bool")
        if self.submission is not None:
            object.__setattr__(
                self, "submission", require_action_submission(self.submission)
            )
        if (
            self.loop_result is not None
            and type(self.loop_result) is not CognitiveLoopResult
        ):
            raise TypeError("loop_result must be CognitiveLoopResult or None")

    def __repr__(self) -> str:
        return (
            f"AgentStepResult(status={self.status.value!r}, "
            f"invocation_id={self.invocation_id!r}, tick={self.tick}, "
            f"has_submission={self.submission is not None}, "
            f"terminal={self.terminal})"
        )


class EmptyInbox:
    """Default inbox source with no envelopes."""

    def envelopes_for(self, agent_id: AgentId) -> Sequence[CommunicationEnvelope]:
        _ = agent_id
        return ()


class SequentialInvocationIds:
    """Deterministic invocation ids: ``{agent}-{tick}-{n}``."""

    __slots__ = ("_counts",)

    def __init__(self) -> None:
        self._counts: dict[tuple[str, int], int] = {}

    def next_id(self, *, agent_id: AgentId, tick: int) -> str:
        key = (agent_id.value, tick)
        n = self._counts.get(key, 0)
        self._counts[key] = n + 1
        return f"{agent_id.value}-t{tick}-i{n}"


class AgentRuntime:
    """Trusted per-agent composition boundary for cognition and submission."""

    __slots__ = (
        "_agent",
        "_applied_reflection_operation_ids",
        "_belief_reader",
        "_belief_writer",
        "_cognition_trace_repository",
        "_cognition_trace_spec",
        "_decision_journal",
        "_emotional_state",
        "_finalized_hashes",
        "_goal_revision_counters",
        "_inbox",
        "_internal_state",
        "_invocation_ids",
        "_last_observation_key",
        "_loop",
        "_memory_reader",
        "_memory_service",
        "_memory_writer",
        "_offline_consolidation_audits",
        "_pending",
        "_processed_invocations",
        "_reflection_audits",
        "_reflection_capture",
        "_reflection_cursor",
        "_relationship_reader",
        "_run_id",
        "_scientific_evidence",
        "_semantic_belief_reader",
        "_status",
        "_subjective_state",
        "_translator",
    )

    def __init__(
        self,
        *,
        agent: Agent,
        translator: RegistrationTranslator,
        cognitive_loop: CognitiveLoop,
        memory_reader: MemoryReader,
        memory_writer: MemoryWriter,
        belief_reader: BeliefReader,
        belief_writer: BeliefWriter,
        memory_service: MemoryService | None = None,
        semantic_belief_reader: SemanticBeliefReader | None = None,
        relationship_reader: RelationshipReader | None = None,
        subjective_state: SubjectiveStateService | None = None,
        inbox_source: InboxSource | None = None,
        invocation_id_source: InvocationIdSource | None = None,
        run_id: RunId | None = None,
        cognition_trace_repository: CognitionTraceRepository | None = None,
        cognition_trace_spec: CognitionTraceSpec | None = None,
        scientific_evidence: ScientificEvidenceRepository | None = None,
    ) -> None:
        if type(agent) is not Agent:
            raise TypeError("agent must be Agent")
        if type(translator) is not RegistrationTranslator:
            raise TypeError("translator must be RegistrationTranslator")
        if type(cognitive_loop) is not CognitiveLoop:
            raise TypeError("cognitive_loop must be CognitiveLoop")
        if run_id is not None and type(run_id) is not RunId:
            raise TypeError("run_id must be RunId or None")
        if cognition_trace_repository is not None and not hasattr(
            cognition_trace_repository, "append_invocation"
        ):
            raise TypeError(
                "cognition_trace_repository must implement CognitionTraceRepository"
            )
        if cognition_trace_spec is not None and type(cognition_trace_spec) is not (
            CognitionTraceSpec
        ):
            raise TypeError("cognition_trace_spec must be CognitionTraceSpec or None")
        if scientific_evidence is not None and not hasattr(
            scientific_evidence, "append_goal_revision"
        ):
            raise TypeError(
                "scientific_evidence must implement ScientificEvidenceRepository"
            )
        self._agent = agent
        self._translator = translator
        self._loop = cognitive_loop
        self._memory_reader = memory_reader
        self._memory_writer = memory_writer
        self._belief_reader = belief_reader
        self._belief_writer = belief_writer
        self._memory_service = memory_service
        self._offline_consolidation_audits: list[object] = []
        self._reflection_audits: list[object] = []
        self._applied_reflection_operation_ids: set[str] = set()
        self._semantic_belief_reader = semantic_belief_reader
        self._relationship_reader = relationship_reader
        self._subjective_state = subjective_state
        self._inbox = inbox_source if inbox_source is not None else EmptyInbox()
        self._invocation_ids = (
            invocation_id_source
            if invocation_id_source is not None
            else SequentialInvocationIds()
        )
        self._run_id = run_id
        self._cognition_trace_repository = (
            cognition_trace_repository
            if cognition_trace_repository is not None
            else NullCognitionTraceRepository()
        )
        self._cognition_trace_spec = (
            cognition_trace_spec
            if cognition_trace_spec is not None
            else CognitionTraceSpec()
        )
        self._scientific_evidence = scientific_evidence
        self._goal_revision_counters: dict[str, int] = {}
        self._status = AgentRuntimeStatus.CREATED
        self._internal_state = InternalAgentState(owner_id=agent.agent_id)
        self._emotional_state: AgentEmotionalState | None = None
        self._reflection_cursor: object | None = None
        self._decision_journal: tuple[object, ...] | None = None
        self._reflection_capture: object | None = None
        self._last_observation_key: tuple[int, int] | None = None
        self._processed_invocations: set[str] = set()
        self._pending: PendingRuntimeFinalization | None = None
        self._finalized_hashes: set[str] = set()

    @property
    def agent_id(self) -> AgentId:
        return self._agent.agent_id

    @property
    def agent(self) -> Agent:
        """Immutable agent identity used for this runtime."""
        return self._agent

    @property
    def status(self) -> AgentRuntimeStatus:
        return self._status

    @property
    def internal_state(self) -> InternalAgentState:
        return self._internal_state

    @property
    def emotional_state(self) -> AgentEmotionalState | None:
        """Prior-tick owner-scoped emotional carry (None when unset)."""
        return self._emotional_state

    def _commit_emotional_state(
        self, state: AgentEmotionalState | None
    ) -> None:
        """Store post-stage emotional state for the next snapshot (N+1)."""
        if state is None:
            _LOG.debug(
                "emotional_state_commit_skipped",
                extra={
                    "runtime": {
                        "agent_id": self._agent.agent_id.value,
                        "emotional_state_present": False,
                        "kind_count": 0,
                    }
                },
            )
            return
        if type(state) is not AgentEmotionalState:
            raise TypeError("emotional_state must be AgentEmotionalState")
        if state.owner_id != self._agent.agent_id:
            raise AgentRuntimeError(
                AgentRuntimeErrorCode.OWNERSHIP,
                agent_id=self._agent.agent_id.value,
            )
        self._emotional_state = state
        _LOG.debug(
            "emotional_state_committed",
            extra={
                "runtime": {
                    "agent_id": self._agent.agent_id.value,
                    "emotional_state_present": True,
                    "kind_count": len(state.intensities),
                    "tick": state.tick,
                    "max_intensity": state.max_intensity(),
                }
            },
        )

    def apply_goal_status_transitions(
        self,
        receipts: Sequence[GoalTransitionReceipt],
    ) -> tuple[GoalTransitionReceipt, ...]:
        """Apply owner-scoped objective receipts to live ``Agent.goals``.

        Deterministic order is ``(tick, goal_id.value)``. Foreign owners are
        skipped. Returns receipts that mutated local goals.
        """
        if isinstance(receipts, (set, frozenset)):
            raise TypeError("receipts must be ordered")
        owner = self._agent.agent_id
        owned = [
            item
            for item in receipts
            if type(item) is GoalTransitionReceipt and item.owner_id == owner
        ]
        owned.sort(key=lambda item: (item.tick, item.goal_id.value))
        if not owned:
            return ()
        by_id = {goal.goal_id: goal for goal in self._agent.goals}
        order = [goal.goal_id for goal in self._agent.goals]
        applied: list[GoalTransitionReceipt] = []
        for receipt in owned:
            existing = by_id.get(receipt.goal_id)
            if existing is None:
                _LOG.debug(
                    "goal_status_transition_skipped",
                    extra={
                        "runtime": {
                            "agent_id": owner.value,
                            "tick": receipt.tick,
                            "goal_id": receipt.goal_id.value,
                            "reason_code": receipt.reason_code.value,
                            "skip": "missing_goal",
                        }
                    },
                )
                continue
            updated = replace(existing, status=receipt.to_status)
            by_id[receipt.goal_id] = updated
            applied.append(receipt)
            _LOG.debug(
                "goal_status_transition_applied",
                extra={
                    "runtime": {
                        "agent_id": owner.value,
                        "tick": receipt.tick,
                        "goal_id": receipt.goal_id.value,
                        "from_status": receipt.from_status.value,
                        "to_status": receipt.to_status.value,
                        "reason_code": receipt.reason_code.value,
                    }
                },
            )
        if not applied:
            return ()
        self._agent = Agent(
            agent_id=self._agent.agent_id,
            name=self._agent.name,
            goals=tuple(by_id[goal_id] for goal_id in order),
            drives=self._agent.drives,
        )
        return tuple(applied)

    def apply_goal_transition_intents(
        self,
        intents: Sequence[GoalTransitionIntent],
    ) -> tuple[GoalTransitionReceipt, ...]:
        """Apply owner-scoped GoalBoard intents to live ``Agent.goals``.

        Upserts ``resulting_goal`` when present. Refuses subjective
        ``FAILED`` / ``SUSPENDED`` over already ``COMPLETED`` / ``ABANDONED``.
        Returns revision receipts mapped for scientific publish.
        """
        if isinstance(intents, (set, frozenset)):
            raise TypeError("intents must be ordered")
        owner = self._agent.agent_id
        owned = [
            item
            for item in intents
            if type(item) is GoalTransitionIntent and item.owner_id == owner
        ]
        owned.sort(key=lambda item: (item.tick, item.goal_id.value))
        if not owned:
            return ()
        by_id = {goal.goal_id: goal for goal in self._agent.goals}
        order = [goal.goal_id for goal in self._agent.goals]
        applied_receipts: list[GoalTransitionReceipt] = []
        for intent in owned:
            existing = by_id.get(intent.goal_id)
            if existing is not None and existing.status in (
                GoalStatus.COMPLETED,
                GoalStatus.ABANDONED,
            ):
                if intent.reason_code in (
                    GoalTransitionIntentReason.FAILED,
                    GoalTransitionIntentReason.SUSPENDED,
                ) or intent.to_status in (
                    GoalStatus.FAILED,
                    GoalStatus.SUSPENDED,
                ):
                    _LOG.debug(
                        "goal_transition_intent_skipped",
                        extra={
                            "runtime": {
                                "agent_id": owner.value,
                                "tick": intent.tick,
                                "goal_id": intent.goal_id.value,
                                "from_status": existing.status.value,
                                "to_status": intent.to_status.value,
                                "reason_code": intent.reason_code.value,
                                "skip": "terminal_precedence",
                            }
                        },
                    )
                    continue
            if intent.resulting_goal is not None:
                updated = intent.resulting_goal
            elif existing is not None:
                updated = replace(existing, status=intent.to_status)
            else:
                _LOG.debug(
                    "goal_transition_intent_skipped",
                    extra={
                        "runtime": {
                            "agent_id": owner.value,
                            "tick": intent.tick,
                            "goal_id": intent.goal_id.value,
                            "reason_code": intent.reason_code.value,
                            "skip": "missing_goal",
                        }
                    },
                )
                continue
            if intent.goal_id not in by_id:
                order.append(intent.goal_id)
            from_status = (
                existing.status if existing is not None else intent.from_status
            )
            by_id[intent.goal_id] = updated
            receipt = GoalTransitionReceipt(
                goal_id=intent.goal_id,
                owner_id=owner,
                outcome_kind=(
                    updated.outcome.kind
                    if updated.outcome is not None
                    else GoalOutcomeKind.ACHIEVE_CODE
                ),
                from_status=from_status,
                to_status=updated.status,
                tick=intent.tick,
                reason_code=_intent_reason_to_receipt_code(intent.reason_code),
            )
            applied_receipts.append(receipt)
            _LOG.debug(
                "goal_transition_intent_applied",
                extra={
                    "runtime": {
                        "agent_id": owner.value,
                        "tick": intent.tick,
                        "goal_id": intent.goal_id.value,
                        "from_status": from_status.value,
                        "to_status": updated.status.value,
                        "reason_code": intent.reason_code.value,
                    }
                },
            )
        if not applied_receipts:
            return ()
        self._agent = Agent(
            agent_id=self._agent.agent_id,
            name=self._agent.name,
            goals=tuple(by_id[goal_id] for goal_id in order),
            drives=self._agent.drives,
        )
        _LOG.info(
            "goal_transition_intents_committed",
            extra={
                "runtime": {
                    "agent_id": owner.value,
                    "tick": owned[0].tick,
                    "transition_count": len(applied_receipts),
                    "reason_codes": tuple(
                        item.reason_code.value for item in applied_receipts
                    ),
                    "goal_ids": tuple(item.goal_id.value for item in applied_receipts),
                }
            },
        )
        return tuple(applied_receipts)

    async def publish_goal_revisions(
        self,
        receipts: Sequence[GoalTransitionReceipt],
    ) -> None:
        """Append scientific goal revisions. Soft-skips when no repo is wired."""
        if not receipts:
            return
        if self._scientific_evidence is None:
            _LOG.debug(
                "goal_revision_publish_skipped",
                extra={
                    "runtime": {
                        "agent_id": self._agent.agent_id.value,
                        "receipt_count": len(receipts),
                        "reason_code": "no_scientific_evidence",
                    }
                },
            )
            return
        if self._run_id is None:
            _LOG.debug(
                "goal_revision_publish_skipped",
                extra={
                    "runtime": {
                        "agent_id": self._agent.agent_id.value,
                        "receipt_count": len(receipts),
                        "reason_code": "missing_run_id",
                    }
                },
            )
            return
        ordered = sorted(
            (item for item in receipts if type(item) is GoalTransitionReceipt),
            key=lambda item: (item.tick, item.goal_id.value),
        )
        for receipt in ordered:
            if receipt.owner_id != self._agent.agent_id:
                continue
            key = receipt.goal_id.value
            revision = self._goal_revision_counters.get(key, 0) + 1
            self._goal_revision_counters[key] = revision
            envelope = encode_goal_transition_receipt(receipt)
            record = GoalRevisionRecord(
                run_id=self._run_id.value,
                goal_id=receipt.goal_id.value,
                revision=revision,
                owner_id=receipt.owner_id.value,
                tick=receipt.tick,
                envelope=envelope,
            )
            try:
                await self._scientific_evidence.append_goal_revision(record)
            except Exception:
                _LOG.error(
                    "goal_revision_append_failed",
                    extra={
                        "runtime": {
                            "agent_id": self._agent.agent_id.value,
                            "goal_id": receipt.goal_id.value,
                            "tick": receipt.tick,
                            "revision": revision,
                            "reason_code": receipt.reason_code.value,
                        }
                    },
                )
                raise
            _LOG.debug(
                "goal_revision_appended",
                extra={
                    "runtime": {
                        "agent_id": self._agent.agent_id.value,
                        "goal_id": receipt.goal_id.value,
                        "tick": receipt.tick,
                        "revision": revision,
                        "reason_code": receipt.reason_code.value,
                        "hash_prefix": envelope.content_hash[:12],
                    }
                },
            )

    def start(self) -> None:
        """Transition CREATED → ACTIVE. Rejects repeats."""
        if self._status is AgentRuntimeStatus.ACTIVE:
            _LOG.warning(
                "runtime_start_rejected",
                extra={
                    "runtime": {
                        "code": AgentRuntimeErrorCode.ALREADY_STARTED.value,
                        "agent_id": self._agent.agent_id.value,
                        "status": self._status.value,
                    }
                },
            )
            raise AgentRuntimeError(
                AgentRuntimeErrorCode.ALREADY_STARTED,
                agent_id=self._agent.agent_id.value,
            )
        if self._status is AgentRuntimeStatus.TERMINAL:
            _LOG.warning(
                "runtime_start_rejected",
                extra={
                    "runtime": {
                        "code": AgentRuntimeErrorCode.TERMINAL.value,
                        "agent_id": self._agent.agent_id.value,
                        "status": self._status.value,
                    }
                },
            )
            raise AgentRuntimeError(
                AgentRuntimeErrorCode.TERMINAL,
                agent_id=self._agent.agent_id.value,
            )
        self._status = AgentRuntimeStatus.ACTIVE
        _LOG.info(
            "runtime_started",
            extra={
                "runtime": {
                    "agent_id": self._agent.agent_id.value,
                    "status": self._status.value,
                }
            },
        )

    async def prepare_observation(
        self,
        observation: Observation,
        *,
        token: TickToken,
    ) -> PreparedObservation | AgentStepResult:
        """Deliberate only. Does not mutate subjective or internal state."""
        if type(observation) is not Observation:
            raise TypeError("observation must be Observation")
        if type(token) is not TickToken:
            raise TypeError("token must be TickToken")

        agent_id = self._agent.agent_id
        tick = observation.tick

        if self._status is AgentRuntimeStatus.CREATED:
            _LOG.warning(
                "runtime_process_rejected",
                extra={
                    "runtime": {
                        "code": AgentRuntimeErrorCode.NOT_STARTED.value,
                        "agent_id": agent_id.value,
                        "tick": tick,
                    }
                },
            )
            raise AgentRuntimeError(
                AgentRuntimeErrorCode.NOT_STARTED,
                agent_id=agent_id.value,
                tick=tick,
            )

        if self._status is AgentRuntimeStatus.TERMINAL:
            _LOG.debug(
                "runtime_terminal_skip",
                extra={
                    "runtime": {
                        "agent_id": agent_id.value,
                        "tick": tick,
                        "status": self._status.value,
                    }
                },
            )
            return AgentStepResult(
                status=self._status,
                invocation_id=None,
                tick=tick,
                submission=None,
                loop_result=None,
                terminal=True,
            )

        if self._pending is not None:
            raise AgentRuntimeError(
                AgentRuntimeErrorCode.PENDING_EXISTS,
                agent_id=agent_id.value,
                tick=tick,
            )

        obs_key = (observation.tick, observation.revision.value)
        if self._last_observation_key == obs_key:
            _LOG.warning(
                "runtime_duplicate_observation",
                extra={
                    "runtime": {
                        "code": AgentRuntimeErrorCode.DUPLICATE_OBSERVATION.value,
                        "agent_id": agent_id.value,
                        "tick": tick,
                    }
                },
            )
            raise AgentRuntimeError(
                AgentRuntimeErrorCode.DUPLICATE_OBSERVATION,
                agent_id=agent_id.value,
                tick=tick,
            )

        try:
            semantic_beliefs = (
                ()
                if self._semantic_belief_reader is None
                else self._semantic_belief_reader.snapshot()
            )
            relationships = (
                ()
                if self._relationship_reader is None
                else self._relationship_reader.snapshot()
            )
            perspective = build_perspective(
                agent_id=agent_id,
                observation=observation,
                translator=self._translator,
                memories=self._memory_reader.snapshot(),
                beliefs=self._belief_reader.snapshot(),
                inbox=self._inbox.envelopes_for(agent_id),
                semantic_beliefs=semantic_beliefs,
                relationships=relationships,
                snapshot_revision=self._internal_state.invocation_count,
                goals=self._agent.goals,
                drives=self._agent.drives,
                emotional_state=self._emotional_state,
            )
        except TypeError:
            raise
        except Exception:
            _LOG.error(
                "runtime_ownership_failed",
                extra={
                    "runtime": {
                        "code": AgentRuntimeErrorCode.OWNERSHIP.value,
                        "agent_id": agent_id.value,
                        "tick": tick,
                    }
                },
            )
            raise AgentRuntimeError(
                AgentRuntimeErrorCode.OWNERSHIP,
                agent_id=agent_id.value,
                tick=tick,
            ) from None

        snapshot = perspective.to_snapshot()
        _LOG.debug(
            "runtime_snapshot_frozen",
            extra={
                "runtime": {
                    "agent_id": agent_id.value,
                    "tick": tick,
                    "snapshot_revision": snapshot.revision,
                    "memory_count": len(snapshot.memories),
                    "legacy_belief_count": len(snapshot.legacy_beliefs),
                    "semantic_belief_count": len(snapshot.semantic_beliefs),
                    "relationship_count": len(snapshot.relationships),
                    "goal_count": len(snapshot.goals),
                    "drive_count": (
                        0
                        if snapshot.drives is None
                        else len(snapshot.drives.dispositions)
                    ),
                    "inbox_count": len(snapshot.inbox),
                    "counterpart_count": (
                        0
                        if snapshot.social_identity is None
                        else len(snapshot.social_identity.counterparts)
                    ),
                }
            },
        )

        if _is_dead_self(observation):
            self._status = AgentRuntimeStatus.TERMINAL
            self._last_observation_key = obs_key
            _LOG.info(
                "runtime_terminal",
                extra={
                    "runtime": {
                        "agent_id": agent_id.value,
                        "tick": tick,
                        "status": self._status.value,
                        "reason": "dead_self",
                    }
                },
            )
            return AgentStepResult(
                status=self._status,
                invocation_id=None,
                tick=tick,
                submission=None,
                loop_result=None,
                terminal=True,
            )

        invocation_id = self._invocation_ids.next_id(agent_id=agent_id, tick=tick)
        require_stable_id("invocation_id", invocation_id)
        if invocation_id in self._processed_invocations:
            raise AgentRuntimeError(
                AgentRuntimeErrorCode.DUPLICATE_OBSERVATION,
                agent_id=agent_id.value,
                invocation_id=invocation_id,
                tick=tick,
            )

        _LOG.debug(
            "runtime_prepare_start",
            extra={
                "runtime": {
                    "agent_id": agent_id.value,
                    "tick": tick,
                    "invocation_id": invocation_id,
                    "status": self._status.value,
                }
            },
        )

        loop_input = CognitiveLoopInput(
            agent_id=agent_id,
            observation=observation,
            internal_state=self._internal_state,
            snapshot=snapshot,
        )
        try:
            proposal = await self._loop.prepare(loop_input, invocation_id=invocation_id)
        except CognitiveLoopError as exc:
            _LOG.error(
                "runtime_cognition_failed",
                extra={
                    "runtime": {
                        "code": AgentRuntimeErrorCode.COGNITION_FAILED.value,
                        "agent_id": agent_id.value,
                        "tick": tick,
                        "invocation_id": invocation_id,
                        "reason": exc.failure.reason.value,
                        "component_kind": exc.failure.component_kind.value,
                        "ordinal": exc.failure.ordinal,
                    }
                },
            )
            raise AgentRuntimeError(
                AgentRuntimeErrorCode.COGNITION_FAILED,
                agent_id=agent_id.value,
                invocation_id=invocation_id,
                tick=tick,
            ) from None

        prepared = PreparedObservation(
            observation_key=obs_key,
            tick=tick,
            invocation_id=invocation_id,
            token=token,
            proposal=proposal,
            prior_status=self._status,
        )
        _LOG.debug(
            "runtime_prepare_complete",
            extra={
                "runtime": {
                    "agent_id": agent_id.value,
                    "tick": tick,
                    "invocation_id": invocation_id,
                    "boundary_count": len(proposal.boundary_records),
                    "status": "prepared",
                }
            },
        )
        return prepared

    async def bind_effective_command(
        self,
        prepared: PreparedObservation,
        *,
        effective_command: AgentCommand | None = None,
    ) -> PendingRuntimeFinalization:
        """Bind the effective command into a detached pending finalization."""
        if type(prepared) is not PreparedObservation:
            raise TypeError("prepared must be PreparedObservation")
        if self._pending is not None:
            raise AgentRuntimeError(
                AgentRuntimeErrorCode.PENDING_EXISTS,
                agent_id=self._agent.agent_id.value,
                invocation_id=prepared.invocation_id,
                tick=prepared.tick,
            )
        command = require_agent_command(
            prepared.proposal.proposed_command
            if effective_command is None
            else effective_command
        )
        try:
            loop_result = await self._loop.complete(
                prepared.proposal,
                effective_command=command,
                reflection_cursor=self._reflection_cursor,
                decision_journal=self._decision_journal,
            )
        except CognitiveLoopError as exc:
            await self._soft_append_cognition_trace(
                tick=prepared.tick,
                invocation_id=prepared.invocation_id,
                loop_failure=exc.failure,
                loop_input=prepared.proposal.loop_input,
                command_kind=type(command).__name__.lower(),
            )
            _LOG.error(
                "runtime_cognition_failed",
                extra={
                    "runtime": {
                        "code": AgentRuntimeErrorCode.COGNITION_FAILED.value,
                        "agent_id": self._agent.agent_id.value,
                        "tick": prepared.tick,
                        "invocation_id": prepared.invocation_id,
                        "reason": exc.failure.reason.value,
                        "component_kind": exc.failure.component_kind.value,
                        "ordinal": exc.failure.ordinal,
                    }
                },
            )
            raise AgentRuntimeError(
                AgentRuntimeErrorCode.COGNITION_FAILED,
                agent_id=self._agent.agent_id.value,
                invocation_id=prepared.invocation_id,
                tick=prepared.tick,
            ) from None

        observation = prepared.proposal.loop_input.observation
        intents = loop_result.memory_update_intents
        kind_counts = {
            "write_memory": 0,
            "write_belief": 0,
            "revise_semantic_belief": 0,
            "revise_relationship": 0,
        }
        for intent in intents:
            kind_counts[intent.kind.value] = kind_counts.get(intent.kind.value, 0) + 1
        _LOG.debug(
            "runtime_intent_counts",
            extra={
                "runtime": {
                    "agent_id": self._agent.agent_id.value,
                    "tick": prepared.tick,
                    "invocation_id": prepared.invocation_id,
                    "intent_counts": kind_counts,
                }
            },
        )
        _prevalidate_updates(
            self._agent.agent_id,
            intents,
            observation=observation,
        )
        subjective_batch = self._build_subjective_batch(
            agent_id=self._agent.agent_id,
            tick=prepared.tick,
            invocation_id=prepared.invocation_id,
            intents=intents,
            pending_accesses=loop_result.pending_accesses,
            pending_reconsolidation=loop_result.pending_reconsolidation,
            pending_semanticization=loop_result.pending_semanticization,
            offline_consolidation=loop_result.offline_consolidation,
            reflection=loop_result.reflection,
        )
        submission = ActionSubmission(
            token=prepared.token,
            agent_id=self._agent.agent_id,
            command=command,
        )
        command_kind = type(command).__name__.lower()
        await self._soft_append_cognition_trace(
            tick=prepared.tick,
            invocation_id=prepared.invocation_id,
            loop_result=loop_result,
            loop_input=prepared.proposal.loop_input,
            command_kind=command_kind,
            final_confidence=loop_result.final_confidence,
        )
        integrity = _pending_integrity_hash(
            invocation_id=prepared.invocation_id,
            tick=prepared.tick,
            command_kind=command_kind,
            next_status=prepared.prior_status.value,
            revision_hint=(
                0 if subjective_batch is None else subjective_batch.expected_revision
            ),
        )
        has_futures = any(
            record.component_kind is ComponentKind.FUTURES
            for record in loop_result.boundary_records
        )
        pending = PendingRuntimeFinalization(
            observation_key=prepared.observation_key,
            tick=prepared.tick,
            invocation_id=prepared.invocation_id,
            submission=submission,
            loop_result=loop_result,
            prior_status=prepared.prior_status,
            next_status=prepared.prior_status,
            next_internal_state=loop_result.internal_state,
            subjective_batch=subjective_batch,
            effective_command_kind=command_kind,
            integrity_hash=integrity,
            has_futures_boundary=has_futures,
        )
        self._pending = pending
        self._capture_reflection_facts(
            prepared.proposal.loop_input.observation,
            command,
            prepared.proposal.loop_input.snapshot,
        )
        _LOG.debug(
            "runtime_bind_complete",
            extra={
                "runtime": {
                    "agent_id": self._agent.agent_id.value,
                    "tick": prepared.tick,
                    "invocation_id": prepared.invocation_id,
                    "command_type": type(command).__name__,
                    "has_subjective_batch": subjective_batch is not None,
                    "status": "pending",
                }
            },
        )
        return pending

    async def _soft_append_cognition_trace(
        self,
        *,
        tick: int,
        invocation_id: str,
        loop_result: CognitiveLoopResult | None = None,
        loop_failure: object | None = None,
        loop_input: CognitiveLoopInput | None = None,
        command_kind: str | None = None,
        final_confidence: float | None = None,
    ) -> None:
        """Best-effort cognition trace append; never affects bind outcomes."""
        if self._run_id is None:
            if self._cognition_trace_spec.enabled:
                _LOG.debug(
                    "cognition_trace_skipped",
                    extra={
                        "reason_code": "missing_run_id",
                        "agent_id": self._agent.agent_id.value,
                        "tick": tick,
                        "invocation_id": invocation_id,
                    },
                )
            return
        await maybe_append_cognition_trace(
            repository=self._cognition_trace_repository,
            spec=self._cognition_trace_spec,
            run_id=self._run_id,
            agent_id=self._agent.agent_id,
            tick=tick,
            invocation_id=invocation_id,
            loop_result=loop_result,
            loop_failure=loop_failure,
            loop_input=loop_input,
            command_kind=command_kind,
            final_confidence=final_confidence,
        )

    async def finalize_pending(
        self, pending: PendingRuntimeFinalization
    ) -> AgentStepResult:
        """Apply a previously bound transition after objective commit."""
        if type(pending) is not PendingRuntimeFinalization:
            raise TypeError("pending must be PendingRuntimeFinalization")
        agent_id = self._agent.agent_id
        if pending.integrity_hash in self._finalized_hashes:
            _LOG.warning(
                "runtime_finalize_idempotent",
                extra={
                    "runtime": {
                        "code": AgentRuntimeErrorCode.FINALIZE_IDEMPOTENT.value,
                        "agent_id": agent_id.value,
                        "tick": pending.tick,
                        "invocation_id": pending.invocation_id,
                    }
                },
            )
            return AgentStepResult(
                status=self._status,
                invocation_id=pending.invocation_id,
                tick=pending.tick,
                submission=pending.submission,
                loop_result=pending.loop_result,
                terminal=False,
            )
        if (
            self._pending is None
            or self._pending.integrity_hash != pending.integrity_hash
        ):
            raise AgentRuntimeError(
                AgentRuntimeErrorCode.PENDING_MISMATCH
                if self._pending is not None
                else AgentRuntimeErrorCode.PENDING_MISSING,
                agent_id=agent_id.value,
                invocation_id=pending.invocation_id,
                tick=pending.tick,
            )

        await self._apply_pending_side_effects(pending)
        extra_goals = _consolidation_goal_intents(pending.loop_result)
        reflection_goals = _reflection_goal_intents(
            pending.loop_result, self._applied_reflection_operation_ids
        )
        intent_receipts = self.apply_goal_transition_intents(
            tuple(_goal_board_intents(pending.loop_result))
            + extra_goals
            + reflection_goals
        )
        await self.publish_goal_revisions(intent_receipts)
        self._commit_emotional_state(
            _emotional_state_from_result(pending.loop_result)
        )
        self._apply_reflection_journal(pending.tick)
        self._record_reflection_application(pending)
        self._internal_state = pending.next_internal_state
        self._last_observation_key = pending.observation_key
        self._processed_invocations.add(pending.invocation_id)
        self._finalized_hashes.add(pending.integrity_hash)
        self._pending = None
        emotion = self._emotional_state
        _LOG.info(
            "runtime_finalize_complete",
            extra={
                "runtime": {
                    "agent_id": agent_id.value,
                    "tick": pending.tick,
                    "invocation_id": pending.invocation_id,
                    "status": self._status.value,
                    "memory_update_count": len(
                        pending.loop_result.memory_update_intents
                    ),
                    "goal_transition_count": len(intent_receipts),
                    "emotional_state_present": emotion is not None,
                    "emotional_kind_count": (
                        0 if emotion is None else len(emotion.intensities)
                    ),
                }
            },
        )
        return AgentStepResult(
            status=self._status,
            invocation_id=pending.invocation_id,
            tick=pending.tick,
            submission=pending.submission,
            loop_result=pending.loop_result,
            terminal=False,
        )

    def _capture_reflection_facts(
        self, observation: Observation, command: object, snapshot: object | None
    ) -> None:
        """Remember self-visible command facts until a successful finalize."""

        from agents.cognition.configuration import CognitionReflectionMode

        mode = getattr(self._loop, "_reflection_mode", None)
        if mode is not CognitionReflectionMode.DETERMINISTIC and mode is not (
            CognitionReflectionMode.LLM_ASSISTED
        ):
            self._reflection_capture = None
            return
        day_phase = (
            None if observation.day_phase is None else observation.day_phase.value
        )
        place_id = None
        body = observation.self_body
        if body is not None and body.location_id is not None:
            place_id = body.location_id.value
        owner_entity = observation.observer_id
        successes = 0
        failures = 0
        for occurrence in observation.occurrences:
            if occurrence.actor_id != owner_entity:
                continue
            if occurrence.success is True:
                successes += 1
            elif occurrence.success is False:
                failures += 1
        from agents.cognition.reflection import classify_subjective_outcome

        previous = classify_subjective_outcome(
            perceived_success=successes > 0,
            owner_failure_count=failures,
            place_changed=False,
        )
        from social.relationships import DirectedRelationshipProfile

        pairs: tuple[tuple[object, object, int], ...] = ()
        relationships = getattr(snapshot, "relationships", ())
        if relationships:
            collected = []
            for profile in relationships:
                if type(profile) is not DirectedRelationshipProfile:
                    continue
                if profile.source_id != self._agent.agent_id:
                    continue
                collected.append(
                    (profile.source_id, profile.target_id, profile.revision_ordinal)
                )
            pairs = tuple(collected)
        self._reflection_capture = (
            type(command).__name__,
            day_phase,
            place_id,
            previous,
            pairs,
        )

    def _apply_reflection_journal(self, tick: int) -> None:
        """Append one decision record after a successful enabled finalize."""

        from agents.cognition.configuration import CognitionReflectionMode
        from agents.cognition.reflection import (
            ReflectionCursor,
            ReflectionPolicy,
            advance_decision_journal,
            remember_relationship_ordinals,
        )

        mode = getattr(self._loop, "_reflection_mode", None)
        capture = self._reflection_capture
        self._reflection_capture = None
        if capture is None:
            return
        if mode is not CognitionReflectionMode.DETERMINISTIC and mode is not (
            CognitionReflectionMode.LLM_ASSISTED
        ):
            return
        policy = getattr(self._loop, "_reflection_policy", None)
        if type(policy) is not ReflectionPolicy:
            policy = ReflectionPolicy(
                allow_provider=mode is CognitionReflectionMode.LLM_ASSISTED
            )
        cursor = self._reflection_cursor
        if type(cursor) is not ReflectionCursor:
            cursor = ReflectionCursor(owner_id=self._agent.agent_id)
        journal = self._decision_journal
        if journal is None:
            journal = ()
        command_kind, day_phase, place_id, previous, pairs = capture
        cursor = remember_relationship_ordinals(cursor, pairs)
        cursor, records = advance_decision_journal(
            cursor=cursor,
            journal=journal,
            policy=policy,
            tick=tick,
            command_kind=command_kind,
            day_phase=day_phase,
            place_id=place_id,
            previous_outcome=previous if journal else None,
        )
        self._reflection_cursor = cursor
        self._decision_journal = records

    def abort_pending(self, pending: PendingRuntimeFinalization) -> None:
        """Discard an uncommitted pending transition without applying it."""
        if type(pending) is not PendingRuntimeFinalization:
            raise TypeError("pending must be PendingRuntimeFinalization")
        if self._pending is None:
            raise AgentRuntimeError(
                AgentRuntimeErrorCode.PENDING_MISSING,
                agent_id=self._agent.agent_id.value,
                invocation_id=pending.invocation_id,
                tick=pending.tick,
            )
        if self._pending.integrity_hash != pending.integrity_hash:
            raise AgentRuntimeError(
                AgentRuntimeErrorCode.PENDING_MISMATCH,
                agent_id=self._agent.agent_id.value,
                invocation_id=pending.invocation_id,
                tick=pending.tick,
            )
        self._pending = None
        self._reflection_capture = None
        _LOG.warning(
            "runtime_pending_aborted",
            extra={
                "runtime": {
                    "agent_id": self._agent.agent_id.value,
                    "tick": pending.tick,
                    "invocation_id": pending.invocation_id,
                    "status": "aborted",
                }
            },
        )

    def restore_pending_from_command(
        self, command: object
    ) -> PendingRuntimeFinalization:
        """Install a recovered pending transition without cognition/provider calls."""
        from simulation.run_control import FinalizationCommand

        if type(command) is not FinalizationCommand:
            raise TypeError("command must be FinalizationCommand")
        if command.agent_id != self._agent.agent_id:
            raise AgentRuntimeError(
                AgentRuntimeErrorCode.OWNERSHIP,
                agent_id=self._agent.agent_id.value,
                invocation_id=command.invocation_id,
                tick=command.tick,
            )
        if command.integrity_hash in self._finalized_hashes:
            _LOG.warning(
                "runtime_restore_pending_idempotent",
                extra={
                    "runtime": {
                        "code": AgentRuntimeErrorCode.FINALIZE_IDEMPOTENT.value,
                        "agent_id": self._agent.agent_id.value,
                        "tick": command.tick,
                        "invocation_id": command.invocation_id,
                    }
                },
            )
            return pending_from_finalization_command(command)
        if self._pending is not None:
            if self._pending.integrity_hash == command.integrity_hash:
                return self._pending
            raise AgentRuntimeError(
                AgentRuntimeErrorCode.PENDING_EXISTS,
                agent_id=self._agent.agent_id.value,
                invocation_id=command.invocation_id,
                tick=command.tick,
            )
        pending = pending_from_finalization_command(command)
        self._pending = pending
        _LOG.debug(
            "runtime_pending_restored",
            extra={
                "runtime": {
                    "agent_id": self._agent.agent_id.value,
                    "tick": command.tick,
                    "invocation_id": command.invocation_id,
                    "status": "restored",
                }
            },
        )
        return pending

    def restore_runtime_checkpoint(self, checkpoint: object) -> None:
        """Restore status/internal state/goals from a detached checkpoint."""
        from agents.models import Agent, Goal
        from simulation.run_control import AgentRuntimeCheckpoint

        if type(checkpoint) is not AgentRuntimeCheckpoint:
            raise TypeError("checkpoint must be AgentRuntimeCheckpoint")
        if checkpoint.agent_id != self._agent.agent_id:
            raise AgentRuntimeError(
                AgentRuntimeErrorCode.OWNERSHIP,
                agent_id=self._agent.agent_id.value,
            )
        goals = tuple(checkpoint.goals)
        for goal in goals:
            if type(goal) is not Goal:
                raise TypeError("goals entries must be Goal")
        self._agent = Agent(
            agent_id=self._agent.agent_id,
            name=self._agent.name,
            goals=goals,
            drives=self._agent.drives,
        )
        self._status = checkpoint.status
        self._internal_state = checkpoint.internal_state
        self._last_observation_key = checkpoint.last_observation_key
        self._emotional_state = checkpoint.emotional_state
        self._reflection_cursor = checkpoint.reflection_cursor
        self._decision_journal = checkpoint.decision_journal
        self._pending = None
        emotion = self._emotional_state
        _LOG.debug(
            "runtime_checkpoint_restored",
            extra={
                "runtime": {
                    "agent_id": self._agent.agent_id.value,
                    "status": self._status.value,
                    "processed_invocation_count": checkpoint.processed_invocation_count,
                    "finalized_hash_count": checkpoint.finalized_hash_count,
                    "emotional_state_present": emotion is not None,
                    "emotional_kind_count": (
                        0 if emotion is None else len(emotion.intensities)
                    ),
                }
            },
        )

    def export_runtime_checkpoint(self) -> object:
        """Export detached runtime state for rehydration."""
        from simulation.run_control import AgentRuntimeCheckpoint

        return AgentRuntimeCheckpoint(
            agent_id=self._agent.agent_id,
            status=self._status,
            internal_state=self._internal_state,
            last_observation_key=self._last_observation_key,
            processed_invocation_count=len(self._processed_invocations),
            finalized_hash_count=len(self._finalized_hashes),
            goals=self._agent.goals,
            emotional_state=self._emotional_state,
            reflection_cursor=self._reflection_cursor,
            decision_journal=self._decision_journal,
        )

    async def process_observation(
        self,
        observation: Observation,
        *,
        token: TickToken,
    ) -> AgentStepResult:
        """One-call path: prepare, bind proposed command, finalize immediately.

        Prefer prepare/bind/finalize around objective commit for runner ticks.
        """
        prepared = await self.prepare_observation(observation, token=token)
        if type(prepared) is AgentStepResult:
            return prepared
        pending = await self.bind_effective_command(prepared)
        return await self.finalize_pending(pending)

    async def _apply_pending_side_effects(
        self, pending: PendingRuntimeFinalization
    ) -> None:
        # Legacy WRITE_BELIEF intents still use the sync belief writer.
        for intent in pending.loop_result.memory_update_intents:
            if intent.kind is MemoryUpdateKind.WRITE_BELIEF:
                assert intent.belief is not None
                self._belief_writer.write(intent.belief)
        if pending.subjective_batch is not None:
            if self._subjective_state is None:
                raise AgentRuntimeError(
                    AgentRuntimeErrorCode.SUBJECTIVE_APPLY_FAILED,
                    agent_id=self._agent.agent_id.value,
                    invocation_id=pending.invocation_id,
                    tick=pending.tick,
                )
            try:
                receipt = await self._subjective_state.commit(pending.subjective_batch)
            except SubjectiveStateError as exc:
                _LOG.error(
                    "runtime_subjective_apply_failed",
                    extra={
                        "runtime": {
                            "code": AgentRuntimeErrorCode.SUBJECTIVE_APPLY_FAILED.value,
                            "agent_id": self._agent.agent_id.value,
                            "tick": pending.tick,
                            "invocation_id": pending.invocation_id,
                            "reason_code": exc.code.value,
                            "adapter": exc.adapter,
                        }
                    },
                )
                raise AgentRuntimeError(
                    AgentRuntimeErrorCode.SUBJECTIVE_APPLY_FAILED,
                    agent_id=self._agent.agent_id.value,
                    invocation_id=pending.invocation_id,
                    tick=pending.tick,
                ) from None
            _LOG.debug(
                "runtime_subjective_apply_complete",
                extra={
                    "runtime": {
                        "agent_id": self._agent.agent_id.value,
                        "tick": pending.tick,
                        "invocation_id": pending.invocation_id,
                        "revision": receipt.revision,
                        "idempotent": receipt.idempotent,
                        "status": "ok",
                    }
                },
            )
            await self._finish_offline_consolidation(pending)
            return
        await self._apply_memory_side_effects(
            agent_id=self._agent.agent_id,
            tick=pending.tick,
            invocation_id=pending.invocation_id,
            intents=pending.loop_result.memory_update_intents,
            pending_accesses=pending.loop_result.pending_accesses,
            pending_reconsolidation=pending.loop_result.pending_reconsolidation,
            pending_semanticization=pending.loop_result.pending_semanticization,
            offline_consolidation=pending.loop_result.offline_consolidation,
            reflection=pending.loop_result.reflection,
        )
        await self._finish_offline_consolidation(pending)

    def _build_subjective_batch(
        self,
        *,
        agent_id: AgentId,
        tick: int,
        invocation_id: str,
        intents: Sequence[MemoryUpdateIntent],
        pending_accesses: Sequence[MemoryAccessReceipt],
        pending_reconsolidation: object | None,
        pending_semanticization: object | None = None,
        offline_consolidation: object | None = None,
        reflection: object | None = None,
    ) -> SubjectiveMutationBatch | None:
        if self._subjective_state is None:
            return None
        from memory.beliefs import BeliefRevisionRequest
        from memory.models import ReconsolidationIntent, ReconstructionRecord
        from social.relationships import RelationshipRevisionRequest

        writes: list[MemoryTrace] = []
        belief_revisions: list[BeliefRevisionRequest] = []
        relationship_revisions: list[RelationshipRevisionRequest] = []
        for intent in intents:
            if intent.kind is MemoryUpdateKind.WRITE_MEMORY:
                assert intent.memory is not None
                writes.append(intent.memory)
            elif intent.kind is MemoryUpdateKind.WRITE_BELIEF:
                continue
            elif intent.kind is MemoryUpdateKind.REVISE_SEMANTIC_BELIEF:
                assert type(intent.belief_revision) is BeliefRevisionRequest
                belief_revisions.append(intent.belief_revision)
            elif intent.kind is MemoryUpdateKind.REVISE_RELATIONSHIP:
                assert type(intent.relationship_revision) is RelationshipRevisionRequest
                relationship_revisions.append(intent.relationship_revision)
        reconstructions: tuple[ReconstructionRecord, ...] = ()
        if pending_reconsolidation is not None:
            if type(pending_reconsolidation) is not ReconsolidationIntent:
                raise AgentRuntimeError(
                    AgentRuntimeErrorCode.INVALID_UPDATE,
                    agent_id=agent_id.value,
                    invocation_id=invocation_id,
                    tick=tick,
                )
            writes.append(pending_reconsolidation.derived_trace)
            reconstructions = (pending_reconsolidation.record,)
        if pending_semanticization is not None:
            if type(pending_semanticization) is not BeliefRevisionRequest:
                raise AgentRuntimeError(
                    AgentRuntimeErrorCode.INVALID_UPDATE,
                    agent_id=agent_id.value,
                    invocation_id=invocation_id,
                    tick=tick,
                )
            if pending_semanticization.owner_id != agent_id:
                raise AgentRuntimeError(
                    AgentRuntimeErrorCode.OWNERSHIP,
                    agent_id=agent_id.value,
                    invocation_id=invocation_id,
                    tick=tick,
                )
            belief_revisions.append(pending_semanticization)
            _LOG.debug(
                "runtime_semanticization_queued",
                extra={
                    "runtime": {
                        "agent_id": agent_id.value,
                        "tick": tick,
                        "invocation_id": invocation_id,
                        "semanticization_pending": True,
                        "belief_id_present": pending_semanticization.belief_id
                        is not None,
                    }
                },
            )
        _extend_consolidation_writes(
            offline_consolidation,
            writes=writes,
            belief_revisions=belief_revisions,
            relationship_revisions=relationship_revisions,
        )
        _extend_reflection_writes(
            reflection,
            belief_revisions=belief_revisions,
            relationship_revisions=relationship_revisions,
            applied=self._applied_reflection_operation_ids,
        )
        return SubjectiveMutationBatch(
            operation_id=subjective_operation_id(
                owner_id=agent_id, invocation_id=invocation_id
            ),
            logical_tick=tick,
            memory_writes=tuple(writes),
            memory_accesses=tuple(pending_accesses),
            reconstructions=reconstructions,
            belief_revisions=tuple(belief_revisions),
            relationship_revisions=tuple(relationship_revisions),
            expected_revision=self._subjective_state.revision,
        )

    async def _apply_memory_side_effects(
        self,
        *,
        agent_id: AgentId,
        tick: int,
        invocation_id: str,
        intents: Sequence[MemoryUpdateIntent],
        pending_accesses: Sequence[MemoryAccessReceipt],
        pending_reconsolidation: object | None = None,
        pending_semanticization: object | None = None,
        offline_consolidation: object | None = None,
        reflection: object | None = None,
    ) -> None:
        from memory.beliefs import BeliefRevisionRequest
        from memory.models import ReconsolidationIntent, ReconstructionRecord
        from social.relationships import RelationshipRevisionRequest

        writes: list[MemoryTrace] = []
        belief_revisions: list[BeliefRevisionRequest] = []
        relationship_revisions: list[RelationshipRevisionRequest] = []
        for intent in intents:
            if intent.kind is MemoryUpdateKind.WRITE_MEMORY:
                assert intent.memory is not None
                writes.append(intent.memory)
            elif intent.kind is MemoryUpdateKind.WRITE_BELIEF:
                assert intent.belief is not None
                self._belief_writer.write(intent.belief)
            elif intent.kind is MemoryUpdateKind.REVISE_SEMANTIC_BELIEF:
                assert type(intent.belief_revision) is BeliefRevisionRequest
                belief_revisions.append(intent.belief_revision)
            elif intent.kind is MemoryUpdateKind.REVISE_RELATIONSHIP:
                assert type(intent.relationship_revision) is RelationshipRevisionRequest
                relationship_revisions.append(intent.relationship_revision)
            else:  # pragma: no cover - closed enum
                raise AgentRuntimeError(
                    AgentRuntimeErrorCode.INVALID_UPDATE,
                    agent_id=agent_id.value,
                    invocation_id=invocation_id,
                    tick=tick,
                )

        reconsolidation_count = 0
        reconstructions: tuple[ReconstructionRecord, ...] = ()
        if pending_reconsolidation is not None:
            if type(pending_reconsolidation) is not ReconsolidationIntent:
                raise AgentRuntimeError(
                    AgentRuntimeErrorCode.INVALID_UPDATE,
                    agent_id=agent_id.value,
                    invocation_id=invocation_id,
                    tick=tick,
                )
            if pending_reconsolidation.record.owner_id != agent_id:
                raise AgentRuntimeError(
                    AgentRuntimeErrorCode.OWNERSHIP,
                    agent_id=agent_id.value,
                    invocation_id=invocation_id,
                    tick=tick,
                )
            derived = pending_reconsolidation.derived_trace
            if derived.owner_id != agent_id:
                raise AgentRuntimeError(
                    AgentRuntimeErrorCode.OWNERSHIP,
                    agent_id=agent_id.value,
                    invocation_id=invocation_id,
                    tick=tick,
                )
            writes.append(derived)
            reconsolidation_count = 1
            reconstructions = (pending_reconsolidation.record,)

        if pending_semanticization is not None:
            if type(pending_semanticization) is not BeliefRevisionRequest:
                raise AgentRuntimeError(
                    AgentRuntimeErrorCode.INVALID_UPDATE,
                    agent_id=agent_id.value,
                    invocation_id=invocation_id,
                    tick=tick,
                )
            if pending_semanticization.owner_id != agent_id:
                raise AgentRuntimeError(
                    AgentRuntimeErrorCode.OWNERSHIP,
                    agent_id=agent_id.value,
                    invocation_id=invocation_id,
                    tick=tick,
                )
            belief_revisions.append(pending_semanticization)
            _LOG.debug(
                "runtime_semanticization_apply",
                extra={
                    "runtime": {
                        "agent_id": agent_id.value,
                        "tick": tick,
                        "invocation_id": invocation_id,
                        "semanticization_pending": True,
                        "belief_id_present": pending_semanticization.belief_id
                        is not None,
                    }
                },
            )

        if self._subjective_state is not None:
            if self._subjective_state.scope.owner_id != agent_id:
                raise AgentRuntimeError(
                    AgentRuntimeErrorCode.OWNERSHIP,
                    agent_id=agent_id.value,
                    invocation_id=invocation_id,
                    tick=tick,
                )
            subjective_batch = SubjectiveMutationBatch(
                operation_id=subjective_operation_id(
                    owner_id=agent_id, invocation_id=invocation_id
                ),
                logical_tick=tick,
                memory_writes=tuple(writes),
                memory_accesses=tuple(pending_accesses),
                reconstructions=reconstructions,
                belief_revisions=tuple(belief_revisions),
                relationship_revisions=tuple(relationship_revisions),
                expected_revision=self._subjective_state.revision,
            )
            try:
                receipt = await self._subjective_state.commit(subjective_batch)
            except SubjectiveStateError as exc:
                _LOG.error(
                    "runtime_subjective_apply_failed",
                    extra={
                        "runtime": {
                            "code": AgentRuntimeErrorCode.SUBJECTIVE_APPLY_FAILED.value,
                            "agent_id": agent_id.value,
                            "tick": tick,
                            "invocation_id": invocation_id,
                            "reason_code": exc.code.value,
                            "adapter": exc.adapter,
                        }
                    },
                )
                raise AgentRuntimeError(
                    AgentRuntimeErrorCode.SUBJECTIVE_APPLY_FAILED,
                    agent_id=agent_id.value,
                    invocation_id=invocation_id,
                    tick=tick,
                ) from None
            _LOG.debug(
                "runtime_subjective_apply_complete",
                extra={
                    "runtime": {
                        "agent_id": agent_id.value,
                        "tick": tick,
                        "invocation_id": invocation_id,
                        "revision": receipt.revision,
                        "memory_write_count": receipt.memory_written_count,
                        "belief_revision_count": receipt.belief_revision_count,
                        "relationship_revision_count": (
                            receipt.relationship_revision_count
                        ),
                        "idempotent": receipt.idempotent,
                        "status": "ok",
                    }
                },
            )
            return

        if belief_revisions or relationship_revisions:
            _LOG.debug(
                "runtime_deferred_subjective_intents",
                extra={
                    "runtime": {
                        "agent_id": agent_id.value,
                        "tick": tick,
                        "invocation_id": invocation_id,
                        "deferred_count": (
                            len(belief_revisions) + len(relationship_revisions)
                        ),
                    }
                },
            )

        _extend_consolidation_writes(
            offline_consolidation,
            writes=writes,
            belief_revisions=belief_revisions,
            relationship_revisions=relationship_revisions,
        )
        _extend_reflection_writes(
            reflection,
            belief_revisions=belief_revisions,
            relationship_revisions=relationship_revisions,
            applied=self._applied_reflection_operation_ids,
        )
        if self._memory_service is not None:
            if self._memory_service.scope.owner_id != agent_id:
                raise AgentRuntimeError(
                    AgentRuntimeErrorCode.OWNERSHIP,
                    agent_id=agent_id.value,
                    invocation_id=invocation_id,
                    tick=tick,
                )
            memory_batch = MemoryMutationBatch(
                writes=tuple(writes),
                accesses=tuple(pending_accesses),
                reconstructions=reconstructions,
                operation_id=invocation_id,
            )
            try:
                applied = await self._memory_service.apply(memory_batch)
            except MemoryServiceError as exc:
                _LOG.error(
                    "runtime_memory_apply_failed",
                    extra={
                        "runtime": {
                            "code": AgentRuntimeErrorCode.MEMORY_APPLY_FAILED.value,
                            "agent_id": agent_id.value,
                            "tick": tick,
                            "invocation_id": invocation_id,
                            "reason_code": exc.code.value,
                        }
                    },
                )
                raise AgentRuntimeError(
                    AgentRuntimeErrorCode.MEMORY_APPLY_FAILED,
                    agent_id=agent_id.value,
                    invocation_id=invocation_id,
                    tick=tick,
                ) from None
            _LOG.debug(
                "runtime_memory_apply_complete",
                extra={
                    "runtime": {
                        "agent_id": agent_id.value,
                        "tick": tick,
                        "invocation_id": invocation_id,
                        "write_count": applied.written_count,
                        "access_count": applied.access_applied_count,
                        "access_idempotent_count": applied.access_idempotent_count,
                        "reconstruction_written_count": (
                            applied.reconstruction_written_count
                        ),
                        "reconsolidation_count": reconsolidation_count,
                        "status": "ok",
                    }
                },
            )
            if reconsolidation_count:
                _LOG.info(
                    "runtime_reconsolidation_committed",
                    extra={
                        "runtime": {
                            "agent_id": agent_id.value,
                            "tick": tick,
                            "invocation_id": invocation_id,
                            "reconsolidation_count": reconsolidation_count,
                        }
                    },
                )
            return

        if pending_accesses:
            _LOG.warning(
                "runtime_pending_accesses_dropped",
                extra={
                    "runtime": {
                        "agent_id": agent_id.value,
                        "tick": tick,
                        "invocation_id": invocation_id,
                        "access_count": len(pending_accesses),
                        "reason_code": "memory_service_absent",
                    }
                },
            )
        for write in writes:
            self._memory_writer.write(write)

    async def _finish_offline_consolidation(
        self, pending: PendingRuntimeFinalization
    ) -> None:
        plan = pending.loop_result.offline_consolidation
        if plan is None:
            return
        forget_ids = plan.selection.soft_forget_ids
        try:
            if self._memory_service is not None and forget_ids:
                await self._memory_service.forget_selected_ids(
                    forget_ids, tick=pending.tick
                )
        except Exception as exc:
            _LOG.error(
                "offline_consolidation_aborted agent_id=%s tick=%s "
                "reason_code=apply_failed error_type=%s",
                self._agent.agent_id.value,
                pending.tick,
                type(exc).__name__,
            )
            raise
        self._offline_consolidation_audits.append(plan.audit)
        _LOG.debug(
            "offline_consolidation_applied agent_id=%s tick=%s mode=%s "
            "merge_count=%s strengthen_count=%s soft_forget_count=%s",
            self._agent.agent_id.value,
            pending.tick,
            plan.audit.mode,
            plan.audit.merge_count,
            plan.audit.strengthen_count,
            plan.audit.soft_forget_count,
        )

    def export_offline_consolidation_audits(self) -> tuple[object, ...]:
        return tuple(self._offline_consolidation_audits)

    def export_reflection_audits(self) -> tuple[object, ...]:
        return tuple(self._reflection_audits)

    def _record_reflection_application(
        self, pending: PendingRuntimeFinalization
    ) -> None:
        """Move the cursor only after a pass is applied. Journal stays separate."""

        from agents.cognition.reflection import (
            ReflectionCursor,
            ReflectionPlan,
            commit_reflection_cursor,
            log_reflection_aborted,
            log_reflection_applied,
            reflection_operation_ids,
        )

        plan = pending.loop_result.reflection
        if type(plan) is not ReflectionPlan:
            return
        operation_ids = reflection_operation_ids(plan)
        applied = self._applied_reflection_operation_ids
        if operation_ids and all(item in applied for item in operation_ids):
            return
        applied.update(operation_ids)
        cursor = self._reflection_cursor
        if type(cursor) is not ReflectionCursor:
            cursor = ReflectionCursor(owner_id=self._agent.agent_id)
        try:
            self._reflection_cursor = commit_reflection_cursor(
                cursor,
                tick=pending.tick,
                acknowledged_goal_ids=plan.acknowledged_goal_ids,
            )
        except (TypeError, ValueError):
            log_reflection_aborted(
                owner_id=self._agent.agent_id.value,
                tick=pending.tick,
                reason_code="schema_invalid",
            )
            raise
        self._reflection_audits.append(plan.audit)
        log_reflection_applied(plan)


def _extend_consolidation_writes(
    plan: object | None,
    *,
    writes: list[MemoryTrace],
    belief_revisions: list[object],
    relationship_revisions: list[object],
) -> None:
    if plan is None:
        return
    from agents.cognition.consolidation import OfflineConsolidationPlan

    if type(plan) is not OfflineConsolidationPlan:
        return
    writes.extend(plan.selection.derived_traces)
    belief_revisions.extend(plan.belief_revisions)
    relationship_revisions.extend(plan.relationship_revisions)


def _consolidation_goal_intents(
    loop_result: CognitiveLoopResult,
) -> tuple[GoalTransitionIntent, ...]:
    plan = loop_result.offline_consolidation
    if plan is None:
        return ()
    from agents.cognition.consolidation import OfflineConsolidationPlan

    if type(plan) is not OfflineConsolidationPlan:
        return ()
    return plan.goal_intents


def _extend_reflection_writes(
    plan: object | None,
    *,
    belief_revisions: list[object],
    relationship_revisions: list[object],
    applied: set[str],
) -> None:
    if plan is None:
        return
    from agents.cognition.reflection import ReflectionPlan, without_applied_operations

    if type(plan) is not ReflectionPlan:
        return
    filtered = without_applied_operations(plan, applied)
    belief_revisions.extend(filtered.belief_revisions)
    relationship_revisions.extend(filtered.relationship_revisions)


def _reflection_goal_intents(
    loop_result: CognitiveLoopResult,
    applied: set[str],
) -> tuple[GoalTransitionIntent, ...]:
    plan = loop_result.reflection
    if plan is None:
        return ()
    from agents.cognition.reflection import ReflectionPlan, without_applied_operations

    if type(plan) is not ReflectionPlan:
        return ()
    return without_applied_operations(plan, applied).goal_intents


def _goal_board_intents(
    loop_result: CognitiveLoopResult,
) -> tuple[GoalTransitionIntent, ...]:
    """Extract GoalBoard transition intents from GOAL_MANAGEMENT boundaries."""
    intents: list[GoalTransitionIntent] = []
    for record in loop_result.boundary_records:
        if record.component_kind is not ComponentKind.GOAL_MANAGEMENT:
            continue
        board = record.output_artifact
        if type(board) is not GoalBoard:
            continue
        intents.extend(board.transition_intents)
    return tuple(intents)


def _emotional_state_from_result(
    loop_result: CognitiveLoopResult,
) -> AgentEmotionalState | None:
    """Extract post-update emotional state from EMOTIONAL_STATE boundaries."""
    for record in loop_result.boundary_records:
        if record.component_kind is not ComponentKind.EMOTIONAL_STATE:
            continue
        evaluation = record.output_artifact
        if type(evaluation) is not EmotionalStateEvaluation:
            continue
        return evaluation.state
    return None


def _intent_reason_to_receipt_code(
    reason: GoalTransitionIntentReason,
) -> GoalTransitionReasonCode:
    """Map subjective intent reasons onto revision receipt reason codes."""
    if reason is GoalTransitionIntentReason.FAILED:
        return GoalTransitionReasonCode.FAILED
    if reason is GoalTransitionIntentReason.SUSPENDED:
        return GoalTransitionReasonCode.SUSPENDED
    if reason is GoalTransitionIntentReason.RESUMED:
        return GoalTransitionReasonCode.RESUMED
    if reason is GoalTransitionIntentReason.ABANDONED:
        return GoalTransitionReasonCode.ABANDONED
    if reason is GoalTransitionIntentReason.DECOMPOSED:
        return GoalTransitionReasonCode.DECOMPOSED
    if reason is GoalTransitionIntentReason.REVISED:
        return GoalTransitionReasonCode.REVISED
    if reason is GoalTransitionIntentReason.ADOPTED:
        return GoalTransitionReasonCode.REVISED
    # PROGRESS_UPDATED / FOCUS_SELECTED are subjective revisions without a
    # dedicated objective receipt code.
    return GoalTransitionReasonCode.REVISED


def _is_dead_self(observation: Observation) -> bool:
    self_body = observation.self_body
    return self_body is not None and self_body.life_status is LifeStatus.DEAD


def _pending_integrity_hash(
    *,
    invocation_id: str,
    tick: int,
    command_kind: str,
    next_status: str,
    revision_hint: int,
) -> str:
    material = (
        f"{invocation_id}|{tick}|{command_kind}|{next_status}|{revision_hint}"
    ).encode()
    return hashlib.sha256(material).hexdigest()


def _prevalidate_updates(
    agent_id: AgentId,
    intents: Sequence[MemoryUpdateIntent],
    *,
    observation: Observation,
) -> None:
    for intent in intents:
        if type(intent) is not MemoryUpdateIntent:
            raise AgentRuntimeError(
                AgentRuntimeErrorCode.INVALID_UPDATE,
                agent_id=agent_id.value,
            )
        if intent.owner_id != agent_id:
            raise AgentRuntimeError(
                AgentRuntimeErrorCode.OWNERSHIP,
                agent_id=agent_id.value,
            )
        if intent.kind is MemoryUpdateKind.WRITE_MEMORY:
            if type(intent.memory) is not MemoryTrace:
                raise AgentRuntimeError(
                    AgentRuntimeErrorCode.INVALID_UPDATE,
                    agent_id=agent_id.value,
                )
            if intent.memory.owner_id != agent_id:
                raise AgentRuntimeError(
                    AgentRuntimeErrorCode.OWNERSHIP,
                    agent_id=agent_id.value,
                )
            if intent.memory.created_tick != observation.tick:
                raise AgentRuntimeError(
                    AgentRuntimeErrorCode.INVALID_UPDATE,
                    agent_id=agent_id.value,
                )
            if intent.memory.world_revision != observation.revision:
                raise AgentRuntimeError(
                    AgentRuntimeErrorCode.INVALID_UPDATE,
                    agent_id=agent_id.value,
                )
        elif intent.kind is MemoryUpdateKind.WRITE_BELIEF:
            if type(intent.belief) is not Belief:
                raise AgentRuntimeError(
                    AgentRuntimeErrorCode.INVALID_UPDATE,
                    agent_id=agent_id.value,
                )
        elif intent.kind is MemoryUpdateKind.REVISE_SEMANTIC_BELIEF:
            from memory.beliefs import BeliefRevisionRequest

            if type(intent.belief_revision) is not BeliefRevisionRequest:
                raise AgentRuntimeError(
                    AgentRuntimeErrorCode.INVALID_UPDATE,
                    agent_id=agent_id.value,
                )
            if intent.belief_revision.owner_id != agent_id:
                raise AgentRuntimeError(
                    AgentRuntimeErrorCode.OWNERSHIP,
                    agent_id=agent_id.value,
                )
            if intent.belief_revision.logical_tick != observation.tick:
                raise AgentRuntimeError(
                    AgentRuntimeErrorCode.INVALID_UPDATE,
                    agent_id=agent_id.value,
                )
        elif intent.kind is MemoryUpdateKind.REVISE_RELATIONSHIP:
            from social.relationships import RelationshipRevisionRequest

            if type(intent.relationship_revision) is not RelationshipRevisionRequest:
                raise AgentRuntimeError(
                    AgentRuntimeErrorCode.INVALID_UPDATE,
                    agent_id=agent_id.value,
                )
            if intent.relationship_revision.source_id != agent_id:
                raise AgentRuntimeError(
                    AgentRuntimeErrorCode.OWNERSHIP,
                    agent_id=agent_id.value,
                )
            if intent.relationship_revision.logical_tick != observation.tick:
                raise AgentRuntimeError(
                    AgentRuntimeErrorCode.INVALID_UPDATE,
                    agent_id=agent_id.value,
                )
        else:
            raise AgentRuntimeError(
                AgentRuntimeErrorCode.INVALID_UPDATE,
                agent_id=agent_id.value,
            )
