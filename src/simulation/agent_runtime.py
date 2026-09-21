"""Per-agent runtime lifecycle bridging cognition and WorldEngine admission.

Owns start/active/terminal transitions, builds perspectives, invokes
``CognitiveLoop``, applies owner-scoped memory update intents, and constructs
``ActionSubmission`` values from a caller-supplied ``TickToken``. Never calls
private world admission/operations and never exposes ``TickToken`` to cognition.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final, Protocol

from agents.cognition.loop import CognitiveLoop, CognitiveLoopError
from agents.cognition.models import (
    CognitiveLoopInput,
    CognitiveLoopResult,
    InternalAgentState,
    MemoryUpdateIntent,
    MemoryUpdateKind,
)
from agents.models import Agent, AgentId
from memory.contracts import (
    BeliefReader,
    BeliefWriter,
    MemoryReader,
    MemoryService,
    MemoryWriter,
)
from memory.models import (
    Belief,
    MemoryAccessReceipt,
    MemoryMutationBatch,
    MemoryTrace,
)
from memory.service import MemoryServiceError
from simulation.bootstrap import RegistrationTranslator
from simulation.lifecycle import ActionSubmission, TickToken, require_action_submission
from simulation.perception import build_perspective
from social.models import CommunicationEnvelope
from world.actions import require_agent_command
from world.identifiers import require_stable_id
from world.models import LifeStatus
from world.observations import Observation

__all__ = [
    "AgentRuntime",
    "AgentRuntimeError",
    "AgentRuntimeErrorCode",
    "AgentRuntimeStatus",
    "AgentStepResult",
    "InboxSource",
    "InvocationIdSource",
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
        "_belief_reader",
        "_belief_writer",
        "_inbox",
        "_internal_state",
        "_invocation_ids",
        "_last_observation_key",
        "_loop",
        "_memory_reader",
        "_memory_service",
        "_memory_writer",
        "_processed_invocations",
        "_status",
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
        inbox_source: InboxSource | None = None,
        invocation_id_source: InvocationIdSource | None = None,
    ) -> None:
        if type(agent) is not Agent:
            raise TypeError("agent must be Agent")
        if type(translator) is not RegistrationTranslator:
            raise TypeError("translator must be RegistrationTranslator")
        if type(cognitive_loop) is not CognitiveLoop:
            raise TypeError("cognitive_loop must be CognitiveLoop")
        self._agent = agent
        self._translator = translator
        self._loop = cognitive_loop
        self._memory_reader = memory_reader
        self._memory_writer = memory_writer
        self._belief_reader = belief_reader
        self._belief_writer = belief_writer
        self._memory_service = memory_service
        self._inbox = inbox_source if inbox_source is not None else EmptyInbox()
        self._invocation_ids = (
            invocation_id_source
            if invocation_id_source is not None
            else SequentialInvocationIds()
        )
        self._status = AgentRuntimeStatus.CREATED
        self._internal_state = InternalAgentState(owner_id=agent.agent_id)
        self._last_observation_key: tuple[int, int] | None = None
        self._processed_invocations: set[str] = set()

    @property
    def agent_id(self) -> AgentId:
        return self._agent.agent_id

    @property
    def status(self) -> AgentRuntimeStatus:
        return self._status

    @property
    def internal_state(self) -> InternalAgentState:
        return self._internal_state

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

    async def process_observation(
        self,
        observation: Observation,
        *,
        token: TickToken,
    ) -> AgentStepResult:
        """Process one owned observation into at most one ``ActionSubmission``."""
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

        # Ownership check via existing perspective builder.
        try:
            build_perspective(
                agent_id=agent_id,
                observation=observation,
                translator=self._translator,
                memories=self._memory_reader.snapshot(),
                beliefs=self._belief_reader.snapshot(),
                inbox=self._inbox.envelopes_for(agent_id),
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
            "runtime_cognition_start",
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
        )
        try:
            loop_result = await self._loop.run(loop_input, invocation_id=invocation_id)
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

        command = require_agent_command(loop_result.command)
        intents = loop_result.memory_update_intents
        _prevalidate_updates(
            agent_id,
            intents,
            observation=observation,
        )
        await self._apply_memory_side_effects(
            agent_id=agent_id,
            tick=tick,
            invocation_id=invocation_id,
            intents=intents,
            pending_accesses=loop_result.pending_accesses,
        )

        submission = ActionSubmission(
            token=token,
            agent_id=agent_id,
            command=command,
        )
        self._internal_state = loop_result.internal_state
        self._last_observation_key = obs_key
        self._processed_invocations.add(invocation_id)

        _LOG.debug(
            "runtime_cognition_complete",
            extra={
                "runtime": {
                    "agent_id": agent_id.value,
                    "tick": tick,
                    "invocation_id": invocation_id,
                    "status": self._status.value,
                    "memory_update_count": len(intents),
                    "pending_access_count": len(loop_result.pending_accesses),
                    "command_type": type(command).__name__,
                    "boundary_count": len(loop_result.boundary_records),
                }
            },
        )
        return AgentStepResult(
            status=self._status,
            invocation_id=invocation_id,
            tick=tick,
            submission=submission,
            loop_result=loop_result,
            terminal=False,
        )

    async def _apply_memory_side_effects(
        self,
        *,
        agent_id: AgentId,
        tick: int,
        invocation_id: str,
        intents: Sequence[MemoryUpdateIntent],
        pending_accesses: Sequence[MemoryAccessReceipt],
    ) -> None:
        writes: list[MemoryTrace] = []
        for intent in intents:
            if intent.kind is MemoryUpdateKind.WRITE_MEMORY:
                assert intent.memory is not None
                writes.append(intent.memory)
            elif intent.kind is MemoryUpdateKind.WRITE_BELIEF:
                assert intent.belief is not None
                self._belief_writer.write(intent.belief)

        if self._memory_service is not None:
            if self._memory_service.scope.owner_id != agent_id:
                raise AgentRuntimeError(
                    AgentRuntimeErrorCode.OWNERSHIP,
                    agent_id=agent_id.value,
                    invocation_id=invocation_id,
                    tick=tick,
                )
            batch = MemoryMutationBatch(
                writes=tuple(writes),
                accesses=tuple(pending_accesses),
                operation_id=invocation_id,
            )
            try:
                applied = await self._memory_service.apply(batch)
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
                        "status": "ok",
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


def _is_dead_self(observation: Observation) -> bool:
    self_body = observation.self_body
    return self_body is not None and self_body.life_status is LifeStatus.DEAD


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
        else:
            raise AgentRuntimeError(
                AgentRuntimeErrorCode.INVALID_UPDATE,
                agent_id=agent_id.value,
            )
