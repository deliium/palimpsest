"""Explicit async CognitiveLoop with fixed stage order and boundary records.

No LangGraph, LangChain, DAG engine, plugin discovery, or hidden callbacks.
Components are constructor-injected and invoked sequentially.
"""

from __future__ import annotations

import logging
from asyncio import CancelledError
from collections.abc import Awaitable
from dataclasses import dataclass
from typing import Any, Final, TypeVar, cast

from agents.cognition.contracts import (
    FutureImagination,
    IntentionSelector,
    MemoryRetriever,
    MemoryUpdateHook,
    MotivationEvaluator,
    PerceptionInterpreter,
    Planner,
    SelfStateProjector,
    SituationModeler,
)
from agents.cognition.models import (
    ActionPlan,
    CognitionFailureReason,
    CognitiveLoopInput,
    CognitiveLoopResult,
    ComponentBoundaryRecord,
    ComponentKind,
    ComponentStatus,
    DecisionMetadata,
    IntentionCode,
    InternalAgentState,
    InterpretedPerception,
    MemoryUpdateIntent,
    MotivationEvaluation,
    PossibleFutures,
    RetrievedMemoryContext,
    SelectedIntention,
    SelfModel,
    SituationModel,
)
from world.actions import require_agent_command

__all__ = [
    "COMPONENT_VERSION",
    "CognitiveLoop",
    "CognitiveLoopError",
    "CognitiveLoopFailure",
]

_LOG: Final[logging.Logger] = logging.getLogger("agents.cognition.loop")
COMPONENT_VERSION: Final[str] = "v1"

_STAGE_ORDER: Final[tuple[ComponentKind, ...]] = (
    ComponentKind.PERCEPTION,
    ComponentKind.MEMORY_RETRIEVAL,
    ComponentKind.SITUATION,
    ComponentKind.SELF_STATE,
    ComponentKind.FUTURES,
    ComponentKind.MOTIVATION,
    ComponentKind.INTENTION,
    ComponentKind.PLANNING,
    ComponentKind.MEMORY_UPDATE,
)

T = TypeVar("T")


class CognitiveLoopError(Exception):
    """Terminal loop failure with a safe receipt of completed boundaries."""

    def __init__(self, failure: CognitiveLoopFailure) -> None:
        if type(failure) is not CognitiveLoopFailure:
            raise TypeError("failure must be CognitiveLoopFailure")
        self.failure = failure
        super().__init__(
            f"code={failure.reason.value},component={failure.component_kind.value},"
            f"ordinal={failure.ordinal}"
        )

    def log_fields(self) -> dict[str, object]:
        return self.failure.log_fields()

    def __repr__(self) -> str:
        return f"CognitiveLoopError({self})"


@dataclass(frozen=True, slots=True)
class CognitiveLoopFailure:
    """Typed failure receipt without private model reasoning payloads."""

    invocation_id: str
    agent_id: str
    reason: CognitionFailureReason
    component_kind: ComponentKind
    ordinal: int
    boundary_records: tuple[ComponentBoundaryRecord, ...]

    def __post_init__(self) -> None:
        if type(self.reason) is not CognitionFailureReason:
            raise TypeError("reason must be CognitionFailureReason")
        if type(self.component_kind) is not ComponentKind:
            raise TypeError("component_kind must be ComponentKind")
        if type(self.boundary_records) is not tuple:
            raise TypeError("boundary_records must be a tuple")
        for record in self.boundary_records:
            if type(record) is not ComponentBoundaryRecord:
                raise TypeError(
                    "boundary_records entries must be ComponentBoundaryRecord"
                )

    def log_fields(self) -> dict[str, object]:
        return {
            "invocation_id": self.invocation_id,
            "agent_id": self.agent_id,
            "reason": self.reason.value,
            "component_kind": self.component_kind.value,
            "ordinal": self.ordinal,
            "boundary_count": len(self.boundary_records),
        }

    def __repr__(self) -> str:
        return (
            f"CognitiveLoopFailure(invocation_id={self.invocation_id!r}, "
            f"reason={self.reason.value!r}, "
            f"component_kind={self.component_kind.value!r}, "
            f"ordinal={self.ordinal}, "
            f"boundary_count={len(self.boundary_records)})"
        )


class CognitiveLoop:
    """Sequential cognitive pipeline returning one closed ``AgentCommand``."""

    __slots__ = (
        "_futures",
        "_intention",
        "_memory",
        "_memory_updates",
        "_motivation",
        "_perception",
        "_planner",
        "_self_state",
        "_situation",
    )

    def __init__(
        self,
        *,
        perception: PerceptionInterpreter,
        memory: MemoryRetriever,
        situation: SituationModeler,
        self_state: SelfStateProjector,
        futures: FutureImagination,
        motivation: MotivationEvaluator,
        intention: IntentionSelector,
        planner: Planner,
        memory_updates: MemoryUpdateHook,
    ) -> None:
        self._perception = perception
        self._memory = memory
        self._situation = situation
        self._self_state = self_state
        self._futures = futures
        self._motivation = motivation
        self._intention = intention
        self._planner = planner
        self._memory_updates = memory_updates

    async def run(
        self,
        loop_input: CognitiveLoopInput,
        *,
        invocation_id: str,
    ) -> CognitiveLoopResult:
        if type(loop_input) is not CognitiveLoopInput:
            raise TypeError("CognitiveLoop.run requires CognitiveLoopInput")
        if not isinstance(invocation_id, str) or not invocation_id.strip():
            raise ValueError("invocation_id must be a non-blank str")

        records: list[ComponentBoundaryRecord] = []
        agent_id = loop_input.agent_id.value

        def fail(
            *,
            reason: CognitionFailureReason,
            kind: ComponentKind,
            ordinal: int,
            input_artifact: object,
            status: ComponentStatus = ComponentStatus.FAILED,
        ) -> None:
            failure_reason = (
                CognitionFailureReason.CANCELLED
                if status is ComponentStatus.CANCELLED
                else reason
            )
            records.append(
                ComponentBoundaryRecord(
                    invocation_id=invocation_id,
                    component_kind=kind,
                    component_version=COMPONENT_VERSION,
                    ordinal=ordinal,
                    status=status,
                    confidence=0.0,
                    input_artifact=input_artifact,
                    output_artifact=None,
                    decision_metadata=DecisionMetadata(),
                    failure_reason=failure_reason,
                )
            )
            failure = CognitiveLoopFailure(
                invocation_id=invocation_id,
                agent_id=agent_id,
                reason=failure_reason,
                component_kind=kind,
                ordinal=ordinal,
                boundary_records=tuple(records),
            )
            _LOG.error(
                "cognitive_loop_failed",
                extra={"cognition": failure.log_fields()},
            )
            raise CognitiveLoopError(failure)

        async def run_stage(
            *,
            kind: ComponentKind,
            ordinal: int,
            input_artifact: object,
            awaitable: Awaitable[T],
            expected_type: type[T],
        ) -> T:
            _LOG.debug(
                "cognitive_stage_start",
                extra={
                    "cognition": {
                        "invocation_id": invocation_id,
                        "agent_id": agent_id,
                        "component_kind": kind.value,
                        "component_version": COMPONENT_VERSION,
                        "ordinal": ordinal,
                    }
                },
            )
            try:
                output = await awaitable
            except CancelledError:
                fail(
                    reason=CognitionFailureReason.CANCELLED,
                    kind=kind,
                    ordinal=ordinal,
                    input_artifact=input_artifact,
                    status=ComponentStatus.CANCELLED,
                )
                raise  # pragma: no cover
            except Exception:
                fail(
                    reason=CognitionFailureReason.COMPONENT_FAILED,
                    kind=kind,
                    ordinal=ordinal,
                    input_artifact=input_artifact,
                )
                raise  # pragma: no cover

            if type(output) is not expected_type:
                fail(
                    reason=CognitionFailureReason.TYPE_MISMATCH,
                    kind=kind,
                    ordinal=ordinal,
                    input_artifact=input_artifact,
                )
            owner = getattr(output, "owner_id", None)
            if owner is not None and owner != loop_input.agent_id:
                fail(
                    reason=CognitionFailureReason.OWNERSHIP,
                    kind=kind,
                    ordinal=ordinal,
                    input_artifact=input_artifact,
                )

            if kind is ComponentKind.MEMORY_UPDATE:
                if not isinstance(output, tuple):
                    fail(
                        reason=CognitionFailureReason.TYPE_MISMATCH,
                        kind=kind,
                        ordinal=ordinal,
                        input_artifact=input_artifact,
                    )
                intents = cast(tuple[object, ...], output)
                for item in intents:
                    if type(item) is not MemoryUpdateIntent:
                        fail(
                            reason=CognitionFailureReason.TYPE_MISMATCH,
                            kind=kind,
                            ordinal=ordinal,
                            input_artifact=input_artifact,
                        )
                    intent = cast(MemoryUpdateIntent, item)
                    if intent.owner_id != loop_input.agent_id:
                        fail(
                            reason=CognitionFailureReason.OWNERSHIP,
                            kind=kind,
                            ordinal=ordinal,
                            input_artifact=input_artifact,
                        )
                confidence = 1.0
                metadata = DecisionMetadata(
                    selection_codes=(),
                    candidate_count=len(intents),
                )
                output_artifact: object = intents
            else:
                typed = cast(Any, output)
                confidence = float(typed.confidence)
                metadata_obj = typed.decision_metadata
                if type(metadata_obj) is not DecisionMetadata:
                    fail(
                        reason=CognitionFailureReason.INVALID_OUTPUT,
                        kind=kind,
                        ordinal=ordinal,
                        input_artifact=input_artifact,
                    )
                metadata = metadata_obj
                output_artifact = output

            records.append(
                ComponentBoundaryRecord(
                    invocation_id=invocation_id,
                    component_kind=kind,
                    component_version=COMPONENT_VERSION,
                    ordinal=ordinal,
                    status=ComponentStatus.COMPLETED,
                    confidence=confidence,
                    input_artifact=input_artifact,
                    output_artifact=output_artifact,
                    decision_metadata=metadata,
                )
            )
            _LOG.debug(
                "cognitive_stage_complete",
                extra={
                    "cognition": {
                        "invocation_id": invocation_id,
                        "agent_id": agent_id,
                        "component_kind": kind.value,
                        "component_version": COMPONENT_VERSION,
                        "ordinal": ordinal,
                        "status": ComponentStatus.COMPLETED.value,
                        "confidence": confidence,
                        "boundary_count": len(records),
                    }
                },
            )
            return output

        perception = await run_stage(
            kind=ComponentKind.PERCEPTION,
            ordinal=0,
            input_artifact=loop_input,
            awaitable=self._perception.interpret(loop_input),
            expected_type=InterpretedPerception,
        )
        memory = await run_stage(
            kind=ComponentKind.MEMORY_RETRIEVAL,
            ordinal=1,
            input_artifact=perception,
            awaitable=self._memory.retrieve(loop_input, perception),
            expected_type=RetrievedMemoryContext,
        )
        situation = await run_stage(
            kind=ComponentKind.SITUATION,
            ordinal=2,
            input_artifact=memory,
            awaitable=self._situation.model(loop_input, perception, memory),
            expected_type=SituationModel,
        )
        self_state = await run_stage(
            kind=ComponentKind.SELF_STATE,
            ordinal=3,
            input_artifact=situation,
            awaitable=self._self_state.project(loop_input, situation, memory),
            expected_type=SelfModel,
        )
        futures = await run_stage(
            kind=ComponentKind.FUTURES,
            ordinal=4,
            input_artifact=self_state,
            awaitable=self._futures.imagine(loop_input, situation, self_state, memory),
            expected_type=PossibleFutures,
        )
        motivation = await run_stage(
            kind=ComponentKind.MOTIVATION,
            ordinal=5,
            input_artifact=futures,
            awaitable=self._motivation.evaluate(
                loop_input, situation, self_state, futures
            ),
            expected_type=MotivationEvaluation,
        )
        intention = await run_stage(
            kind=ComponentKind.INTENTION,
            ordinal=6,
            input_artifact=motivation,
            awaitable=self._intention.select(loop_input, motivation, futures),
            expected_type=SelectedIntention,
        )
        plan = await run_stage(
            kind=ComponentKind.PLANNING,
            ordinal=7,
            input_artifact=intention,
            awaitable=self._planner.plan(loop_input, intention, futures, memory),
            expected_type=ActionPlan,
        )
        try:
            command = require_agent_command(plan.command)
        except TypeError:
            fail(
                reason=CognitionFailureReason.COMMAND_REJECTED,
                kind=ComponentKind.PLANNING,
                ordinal=7,
                input_artifact=intention,
            )
            raise  # pragma: no cover

        updates = await run_stage(
            kind=ComponentKind.MEMORY_UPDATE,
            ordinal=8,
            input_artifact=plan,
            awaitable=self._memory_updates.propose_updates(
                loop_input, plan, perception, memory, intention
            ),
            expected_type=tuple,
        )
        assert type(updates) is tuple

        next_state = InternalAgentState(
            owner_id=loop_input.agent_id,
            invocation_count=loop_input.internal_state.invocation_count + 1,
            last_intention=(
                intention.intention
                if type(intention.intention) is IntentionCode
                else None
            ),
            last_command_kind=type(command).__name__.lower(),
        )
        result = CognitiveLoopResult(
            invocation_id=invocation_id,
            agent_id=loop_input.agent_id,
            command=command,
            boundary_records=tuple(records),
            memory_update_intents=updates,
            final_confidence=plan.confidence,
            internal_state=next_state,
            pending_accesses=memory.pending_accesses,
            pending_reconsolidation=memory.reconsolidation,
        )
        _LOG.debug(
            "cognitive_loop_complete",
            extra={
                "cognition": {
                    "invocation_id": invocation_id,
                    "agent_id": agent_id,
                    "boundary_count": len(records),
                    "memory_update_count": len(updates),
                    "pending_access_count": len(memory.pending_accesses),
                    "reconstruction_count": len(memory.reconstructions),
                    "pending_write_count": 1 if memory.reconsolidation else 0,
                    "final_confidence": plan.confidence,
                    "command_type": type(command).__name__,
                }
            },
        )
        _ = _STAGE_ORDER  # documented stage identity for callers/tests
        return result
