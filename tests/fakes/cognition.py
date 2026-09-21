"""Deterministic scripted cognition stage fakes for network-free tests.

Scripted outcomes are keyed by ``(invocation_id, stage_ordinal)``. Call records
retain only metadata (component, invocation, ordinal, status, counts) — never
observation, memory, prompt, or artifact payloads.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from agents.cognition.models import (
    ActionPlan,
    CognitiveLoopInput,
    ComponentKind,
    ComponentStatus,
    InterpretedPerception,
    MemoryUpdateIntent,
    MotivationEvaluation,
    PossibleFutures,
    RetrievedMemoryContext,
    SelectedIntention,
    SelfBeliefState,
    SituationModel,
)

__all__ = [
    "FakeCognitionCallRecord",
    "FakeCognitionFailureCode",
    "FakeCognitionHarnessError",
    "FakeFutureImagination",
    "FakeIntentionSelector",
    "FakeMemoryRetriever",
    "FakeMemoryUpdateHook",
    "FakeMotivationEvaluator",
    "FakePerceptionInterpreter",
    "FakePlanner",
    "FakeSelfStateProjector",
    "FakeSituationModeler",
    "ScriptedStageFailure",
    "ScriptedStageSuccess",
    "bind_invocation",
    "clear_invocation",
    "invocation_context",
]


class FakeCognitionFailureCode(StrEnum):
    """Stable harness failure codes (not cognition domain codes)."""

    UNEXPECTED_KEY = "unexpected_key"
    EXHAUSTED_SCRIPT = "exhausted_script"
    DUPLICATE_ORDINAL = "duplicate_ordinal"
    TYPE_MISMATCH = "type_mismatch"


class FakeCognitionHarnessError(Exception):
    """Test-harness failure with metadata-only messaging."""

    def __init__(
        self,
        code: FakeCognitionFailureCode,
        *,
        invocation_id: str | None = None,
        component: str | None = None,
        ordinal: int | None = None,
    ) -> None:
        if type(code) is not FakeCognitionFailureCode:
            raise TypeError("code must be FakeCognitionFailureCode")
        self.code = code
        self.invocation_id = invocation_id
        self.component = component
        self.ordinal = ordinal
        parts = [f"code={code.value}"]
        if invocation_id is not None:
            parts.append(f"invocation_id={invocation_id}")
        if component is not None:
            parts.append(f"component={component}")
        if ordinal is not None:
            parts.append(f"ordinal={ordinal}")
        super().__init__(",".join(parts))


@dataclass(frozen=True, slots=True)
class FakeCognitionCallRecord:
    """Metadata-only call history entry."""

    invocation_id: str
    component_kind: ComponentKind
    ordinal: int
    status: ComponentStatus
    output_type: str | None

    def __repr__(self) -> str:
        return (
            f"FakeCognitionCallRecord(invocation_id={self.invocation_id!r}, "
            f"component_kind={self.component_kind.value!r}, "
            f"ordinal={self.ordinal}, status={self.status.value!r})"
        )


@dataclass(frozen=True, slots=True)
class ScriptedStageSuccess:
    """Scripted successful stage output (defensively copied on consume)."""

    ordinal: int
    output: object


@dataclass(frozen=True, slots=True)
class ScriptedStageFailure:
    """Scripted stage failure raised as a plain Exception with safe code."""

    ordinal: int
    code: str = "scripted_failure"


_STAGE_OUTPUT_TYPES: Final[Mapping[ComponentKind, type | tuple[type, ...]]] = {
    ComponentKind.PERCEPTION: InterpretedPerception,
    ComponentKind.MEMORY_RETRIEVAL: RetrievedMemoryContext,
    ComponentKind.SITUATION: SituationModel,
    ComponentKind.SELF_STATE: SelfBeliefState,
    ComponentKind.FUTURES: PossibleFutures,
    ComponentKind.MOTIVATION: MotivationEvaluation,
    ComponentKind.INTENTION: SelectedIntention,
    ComponentKind.PLANNING: ActionPlan,
    ComponentKind.MEMORY_UPDATE: tuple,
}


class _ScriptQueue:
    def __init__(
        self,
        *,
        component_kind: ComponentKind,
        scripts: Mapping[str, Sequence[ScriptedStageSuccess | ScriptedStageFailure]],
    ) -> None:
        self.component_kind = component_kind
        self._queues: dict[str, list[ScriptedStageSuccess | ScriptedStageFailure]] = {}
        self._seen_ordinals: dict[str, set[int]] = {}
        self.calls: list[FakeCognitionCallRecord] = []
        for invocation_id, entries in scripts.items():
            if not isinstance(invocation_id, str) or not invocation_id.strip():
                raise ValueError("invocation_id must be non-blank")
            queue: list[ScriptedStageSuccess | ScriptedStageFailure] = []
            seen: set[int] = set()
            for entry in entries:
                if type(entry) not in (ScriptedStageSuccess, ScriptedStageFailure):
                    raise TypeError("script entries must be success or failure")
                if entry.ordinal in seen:
                    raise FakeCognitionHarnessError(
                        FakeCognitionFailureCode.DUPLICATE_ORDINAL,
                        invocation_id=invocation_id,
                        component=component_kind.value,
                        ordinal=entry.ordinal,
                    )
                seen.add(entry.ordinal)
                if type(entry) is ScriptedStageSuccess:
                    expected = _STAGE_OUTPUT_TYPES[component_kind]
                    if component_kind is ComponentKind.MEMORY_UPDATE:
                        if type(entry.output) is not tuple:
                            raise FakeCognitionHarnessError(
                                FakeCognitionFailureCode.TYPE_MISMATCH,
                                invocation_id=invocation_id,
                                component=component_kind.value,
                                ordinal=entry.ordinal,
                            )
                        for item in entry.output:
                            if type(item) is not MemoryUpdateIntent:
                                raise FakeCognitionHarnessError(
                                    FakeCognitionFailureCode.TYPE_MISMATCH,
                                    invocation_id=invocation_id,
                                    component=component_kind.value,
                                    ordinal=entry.ordinal,
                                )
                    elif type(entry.output) is not expected:
                        raise FakeCognitionHarnessError(
                            FakeCognitionFailureCode.TYPE_MISMATCH,
                            invocation_id=invocation_id,
                            component=component_kind.value,
                            ordinal=entry.ordinal,
                        )
                queue.append(deepcopy(entry))
            self._queues[invocation_id] = queue
            self._seen_ordinals[invocation_id] = set()

    def consume(self, *, invocation_id: str, ordinal: int) -> object:
        queue = self._queues.get(invocation_id)
        if queue is None:
            raise FakeCognitionHarnessError(
                FakeCognitionFailureCode.UNEXPECTED_KEY,
                invocation_id=invocation_id,
                component=self.component_kind.value,
                ordinal=ordinal,
            )
        if not queue:
            raise FakeCognitionHarnessError(
                FakeCognitionFailureCode.EXHAUSTED_SCRIPT,
                invocation_id=invocation_id,
                component=self.component_kind.value,
                ordinal=ordinal,
            )
        entry = queue.pop(0)
        if entry.ordinal != ordinal:
            raise FakeCognitionHarnessError(
                FakeCognitionFailureCode.UNEXPECTED_KEY,
                invocation_id=invocation_id,
                component=self.component_kind.value,
                ordinal=ordinal,
            )
        seen = self._seen_ordinals[invocation_id]
        if ordinal in seen:
            raise FakeCognitionHarnessError(
                FakeCognitionFailureCode.DUPLICATE_ORDINAL,
                invocation_id=invocation_id,
                component=self.component_kind.value,
                ordinal=ordinal,
            )
        seen.add(ordinal)
        if type(entry) is ScriptedStageFailure:
            self.calls.append(
                FakeCognitionCallRecord(
                    invocation_id=invocation_id,
                    component_kind=self.component_kind,
                    ordinal=ordinal,
                    status=ComponentStatus.FAILED,
                    output_type=None,
                )
            )
            raise RuntimeError(entry.code)
        output = deepcopy(entry.output)
        self.calls.append(
            FakeCognitionCallRecord(
                invocation_id=invocation_id,
                component_kind=self.component_kind,
                ordinal=ordinal,
                status=ComponentStatus.COMPLETED,
                output_type=type(output).__name__,
            )
        )
        return output


@dataclass
class _InvocationBinder:
    current: str | None = None


_BINDER: Final[_InvocationBinder] = _InvocationBinder()


def bind_invocation(invocation_id: str) -> None:
    """Bind the active invocation id for scripted fakes (test helper)."""
    _BINDER.current = invocation_id


def clear_invocation() -> None:
    _BINDER.current = None


@contextmanager
def invocation_context(invocation_id: str) -> Iterator[str]:
    """Bind ``invocation_id`` for the duration of a scripted loop run."""
    previous = _BINDER.current
    _BINDER.current = invocation_id
    try:
        yield invocation_id
    finally:
        _BINDER.current = previous


def _active_invocation() -> str:
    if _BINDER.current is None:
        raise FakeCognitionHarnessError(FakeCognitionFailureCode.UNEXPECTED_KEY)
    return _BINDER.current


class FakePerceptionInterpreter:
    def __init__(
        self,
        scripts: Mapping[str, Sequence[ScriptedStageSuccess | ScriptedStageFailure]],
    ) -> None:
        self._queue = _ScriptQueue(
            component_kind=ComponentKind.PERCEPTION, scripts=scripts
        )

    @property
    def calls(self) -> tuple[FakeCognitionCallRecord, ...]:
        return tuple(self._queue.calls)

    async def interpret(self, loop_input: CognitiveLoopInput) -> InterpretedPerception:
        _ = loop_input
        output = self._queue.consume(invocation_id=_active_invocation(), ordinal=0)
        assert type(output) is InterpretedPerception
        return output


class FakeMemoryRetriever:
    def __init__(
        self,
        scripts: Mapping[str, Sequence[ScriptedStageSuccess | ScriptedStageFailure]],
    ) -> None:
        self._queue = _ScriptQueue(
            component_kind=ComponentKind.MEMORY_RETRIEVAL, scripts=scripts
        )

    @property
    def calls(self) -> tuple[FakeCognitionCallRecord, ...]:
        return tuple(self._queue.calls)

    async def retrieve(
        self,
        loop_input: CognitiveLoopInput,
        perception: InterpretedPerception,
    ) -> RetrievedMemoryContext:
        _ = loop_input, perception
        output = self._queue.consume(invocation_id=_active_invocation(), ordinal=1)
        assert type(output) is RetrievedMemoryContext
        return output


class FakeSituationModeler:
    def __init__(
        self,
        scripts: Mapping[str, Sequence[ScriptedStageSuccess | ScriptedStageFailure]],
    ) -> None:
        self._queue = _ScriptQueue(
            component_kind=ComponentKind.SITUATION, scripts=scripts
        )

    @property
    def calls(self) -> tuple[FakeCognitionCallRecord, ...]:
        return tuple(self._queue.calls)

    async def model(
        self,
        loop_input: CognitiveLoopInput,
        perception: InterpretedPerception,
        memory: RetrievedMemoryContext,
    ) -> SituationModel:
        _ = loop_input, perception, memory
        output = self._queue.consume(invocation_id=_active_invocation(), ordinal=2)
        assert type(output) is SituationModel
        return output


class FakeSelfStateProjector:
    def __init__(
        self,
        scripts: Mapping[str, Sequence[ScriptedStageSuccess | ScriptedStageFailure]],
    ) -> None:
        self._queue = _ScriptQueue(
            component_kind=ComponentKind.SELF_STATE, scripts=scripts
        )

    @property
    def calls(self) -> tuple[FakeCognitionCallRecord, ...]:
        return tuple(self._queue.calls)

    async def project(
        self,
        loop_input: CognitiveLoopInput,
        situation: SituationModel,
        memory: RetrievedMemoryContext,
    ) -> SelfBeliefState:
        _ = loop_input, situation, memory
        output = self._queue.consume(invocation_id=_active_invocation(), ordinal=3)
        assert type(output) is SelfBeliefState
        return output


class FakeFutureImagination:
    def __init__(
        self,
        scripts: Mapping[str, Sequence[ScriptedStageSuccess | ScriptedStageFailure]],
    ) -> None:
        self._queue = _ScriptQueue(
            component_kind=ComponentKind.FUTURES, scripts=scripts
        )

    @property
    def calls(self) -> tuple[FakeCognitionCallRecord, ...]:
        return tuple(self._queue.calls)

    async def imagine(
        self,
        loop_input: CognitiveLoopInput,
        situation: SituationModel,
        self_state: SelfBeliefState,
    ) -> PossibleFutures:
        _ = loop_input, situation, self_state
        output = self._queue.consume(invocation_id=_active_invocation(), ordinal=4)
        assert type(output) is PossibleFutures
        return output


class FakeMotivationEvaluator:
    def __init__(
        self,
        scripts: Mapping[str, Sequence[ScriptedStageSuccess | ScriptedStageFailure]],
    ) -> None:
        self._queue = _ScriptQueue(
            component_kind=ComponentKind.MOTIVATION, scripts=scripts
        )

    @property
    def calls(self) -> tuple[FakeCognitionCallRecord, ...]:
        return tuple(self._queue.calls)

    async def evaluate(
        self,
        loop_input: CognitiveLoopInput,
        situation: SituationModel,
        self_state: SelfBeliefState,
        futures: PossibleFutures,
    ) -> MotivationEvaluation:
        _ = loop_input, situation, self_state, futures
        output = self._queue.consume(invocation_id=_active_invocation(), ordinal=5)
        assert type(output) is MotivationEvaluation
        return output


class FakeIntentionSelector:
    def __init__(
        self,
        scripts: Mapping[str, Sequence[ScriptedStageSuccess | ScriptedStageFailure]],
    ) -> None:
        self._queue = _ScriptQueue(
            component_kind=ComponentKind.INTENTION, scripts=scripts
        )

    @property
    def calls(self) -> tuple[FakeCognitionCallRecord, ...]:
        return tuple(self._queue.calls)

    async def select(
        self,
        loop_input: CognitiveLoopInput,
        motivation: MotivationEvaluation,
    ) -> SelectedIntention:
        _ = loop_input, motivation
        output = self._queue.consume(invocation_id=_active_invocation(), ordinal=6)
        assert type(output) is SelectedIntention
        return output


class FakePlanner:
    def __init__(
        self,
        scripts: Mapping[str, Sequence[ScriptedStageSuccess | ScriptedStageFailure]],
    ) -> None:
        self._queue = _ScriptQueue(
            component_kind=ComponentKind.PLANNING, scripts=scripts
        )

    @property
    def calls(self) -> tuple[FakeCognitionCallRecord, ...]:
        return tuple(self._queue.calls)

    async def plan(
        self,
        loop_input: CognitiveLoopInput,
        intention: SelectedIntention,
        futures: PossibleFutures,
    ) -> ActionPlan:
        _ = loop_input, intention, futures
        output = self._queue.consume(invocation_id=_active_invocation(), ordinal=7)
        assert type(output) is ActionPlan
        return output


class FakeMemoryUpdateHook:
    def __init__(
        self,
        scripts: Mapping[str, Sequence[ScriptedStageSuccess | ScriptedStageFailure]],
    ) -> None:
        self._queue = _ScriptQueue(
            component_kind=ComponentKind.MEMORY_UPDATE, scripts=scripts
        )

    @property
    def calls(self) -> tuple[FakeCognitionCallRecord, ...]:
        return tuple(self._queue.calls)

    async def propose_updates(
        self,
        loop_input: CognitiveLoopInput,
        plan: ActionPlan,
        perception: InterpretedPerception,
        memory: RetrievedMemoryContext,
        intention: SelectedIntention,
    ) -> tuple[MemoryUpdateIntent, ...]:
        _ = loop_input, plan, perception, memory, intention
        output = self._queue.consume(invocation_id=_active_invocation(), ordinal=8)
        assert type(output) is tuple
        return output
