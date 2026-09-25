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
    EmotionalStateAppraiser,
    FutureImagination,
    GoalManager,
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
    CognitiveLoopProposal,
    CognitiveLoopResult,
    ComponentBoundaryRecord,
    ComponentKind,
    ComponentStatus,
    DecisionMetadata,
    EmotionalStateEvaluation,
    GoalBoard,
    IntentionCode,
    InternalAgentState,
    InterpretedPerception,
    MemoryUpdateIntent,
    MemoryUpdateKind,
    MotivationEvaluation,
    PossibleFutures,
    RetrievedMemoryContext,
    SelectedIntention,
    SelfModel,
    SituationModel,
)
from world.actions import AgentCommand, require_agent_command

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
    ComponentKind.GOAL_MANAGEMENT,
    ComponentKind.EMOTIONAL_STATE,
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


def _tick_memories(
    proposal: CognitiveLoopProposal, updates: tuple[object, ...]
) -> tuple[object, ...]:
    from memory.models import MemoryTrace

    snapshot = proposal.loop_input.snapshot
    memories: list[MemoryTrace] = [] if snapshot is None else list(snapshot.memories)
    seen = {memory.memory_id.value for memory in memories}
    for intent in updates:
        if type(intent) is not MemoryUpdateIntent:
            continue
        if intent.kind is not MemoryUpdateKind.WRITE_MEMORY:
            continue
        memory = intent.memory
        if type(memory) is not MemoryTrace or memory.memory_id.value in seen:
            continue
        memories.append(memory)
        seen.add(memory.memory_id.value)
    return tuple(memories)

class CognitiveLoop:
    """Sequential cognitive pipeline returning one closed ``AgentCommand``."""

    __slots__ = (
        "_consolidation_mode",
        "_consolidation_policy",
        "_consolidation_selector",
        "_deferred_dissonance",
        "_emotional_state",
        "_futures",
        "_goal_manager",
        "_identity_mode",
        "_intention",
        "_memory",
        "_memory_updates",
        "_motivation",
        "_perception",
        "_planner",
        "_reflection_mode",
        "_reflection_policy",
        "_reflection_selector",
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
        goal_manager: GoalManager,
        emotional_state: EmotionalStateAppraiser,
        futures: FutureImagination,
        motivation: MotivationEvaluator,
        intention: IntentionSelector,
        planner: Planner,
        memory_updates: MemoryUpdateHook,
        consolidation_mode: object | None = None,
        consolidation_policy: object | None = None,
        consolidation_selector: object | None = None,
        reflection_mode: object | None = None,
        reflection_policy: object | None = None,
        reflection_selector: object | None = None,
        identity_mode: object | None = None,
    ) -> None:
        self._perception = perception
        self._memory = memory
        self._situation = situation
        self._self_state = self_state
        self._goal_manager = goal_manager
        self._emotional_state = emotional_state
        self._futures = futures
        self._motivation = motivation
        self._intention = intention
        self._planner = planner
        self._memory_updates = memory_updates
        from agents.cognition.configuration import CognitionConsolidationMode

        mode = (
            CognitionConsolidationMode.DISABLED
            if consolidation_mode is None
            else consolidation_mode
        )
        if type(mode) is not CognitionConsolidationMode:
            raise TypeError("consolidation_mode must be CognitionConsolidationMode")
        self._consolidation_mode = mode
        self._consolidation_policy = consolidation_policy
        self._consolidation_selector = consolidation_selector
        from agents.cognition.configuration import CognitionReflectionMode

        reflection = (
            CognitionReflectionMode.DISABLED
            if reflection_mode is None
            else reflection_mode
        )
        if type(reflection) is not CognitionReflectionMode:
            raise TypeError("reflection_mode must be CognitionReflectionMode")
        self._reflection_mode = reflection
        self._reflection_policy = reflection_policy
        self._reflection_selector = reflection_selector
        from agents.cognition.configuration import CognitionIdentityMode

        identity = (
            CognitionIdentityMode.PASSTHROUGH
            if identity_mode is None
            else identity_mode
        )
        if type(identity) is not CognitionIdentityMode:
            raise TypeError("identity_mode must be CognitionIdentityMode")
        self._identity_mode = identity
        self._deferred_dissonance: tuple[object, ...] = ()

    async def prepare(
        self,
        loop_input: CognitiveLoopInput,
        *,
        invocation_id: str,
    ) -> CognitiveLoopProposal:
        """Run perception through planning without memory updates or next state."""
        if type(loop_input) is not CognitiveLoopInput:
            raise TypeError("CognitiveLoop.prepare requires CognitiveLoopInput")
        if not isinstance(invocation_id, str) or not invocation_id.strip():
            raise ValueError("invocation_id must be a non-blank str")

        records: list[ComponentBoundaryRecord] = []
        agent_id = loop_input.agent_id.value
        fail = self._make_fail(
            records=records, invocation_id=invocation_id, agent_id=agent_id
        )
        run_stage = self._make_run_stage(
            loop_input=loop_input,
            records=records,
            invocation_id=invocation_id,
            agent_id=agent_id,
            fail=fail,
        )

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
        goal_board = await run_stage(
            kind=ComponentKind.GOAL_MANAGEMENT,
            ordinal=4,
            input_artifact=self_state,
            awaitable=self._goal_manager.manage(
                loop_input, situation, self_state, memory
            ),
            expected_type=GoalBoard,
        )
        prior_emotion = None
        if loop_input.snapshot is not None:
            prior_emotion = loop_input.snapshot.emotional_state
        emotional_evaluation = await run_stage(
            kind=ComponentKind.EMOTIONAL_STATE,
            ordinal=5,
            input_artifact=goal_board,
            awaitable=self._emotional_state.appraise(
                loop_input,
                perception,
                situation,
                memory,
                self_state,
                goal_board,
                prior_emotion,
            ),
            expected_type=EmotionalStateEvaluation,
        )
        futures = await run_stage(
            kind=ComponentKind.FUTURES,
            ordinal=6,
            input_artifact=emotional_evaluation,
            awaitable=self._futures.imagine(
                loop_input,
                situation,
                self_state,
                memory,
                goal_board,
                emotional_evaluation,
            ),
            expected_type=PossibleFutures,
        )
        motivation = await run_stage(
            kind=ComponentKind.MOTIVATION,
            ordinal=7,
            input_artifact=futures,
            awaitable=self._motivation.evaluate(
                loop_input,
                situation,
                self_state,
                futures,
                goal_board,
                emotional_evaluation,
            ),
            expected_type=MotivationEvaluation,
        )
        intention = await run_stage(
            kind=ComponentKind.INTENTION,
            ordinal=8,
            input_artifact=motivation,
            awaitable=self._intention.select(
                loop_input,
                motivation,
                futures,
                goal_board,
                emotional_evaluation,
                self_state,
            ),
            expected_type=SelectedIntention,
        )
        plan = await run_stage(
            kind=ComponentKind.PLANNING,
            ordinal=9,
            input_artifact=intention,
            awaitable=self._planner.plan(
                loop_input,
                intention,
                futures,
                memory,
                goal_board,
                emotional_evaluation,
            ),
            expected_type=ActionPlan,
        )
        try:
            command = require_agent_command(plan.command)
        except TypeError:
            fail(
                reason=CognitionFailureReason.COMMAND_REJECTED,
                kind=ComponentKind.PLANNING,
                ordinal=9,
                input_artifact=intention,
            )
            raise  # pragma: no cover

        proposal = CognitiveLoopProposal(
            invocation_id=invocation_id,
            agent_id=loop_input.agent_id,
            loop_input=loop_input,
            perception=perception,
            memory=memory,
            situation=situation,
            self_state=self_state,
            goal_board=goal_board,
            emotional_state=emotional_evaluation,
            futures=futures,
            motivation=motivation,
            intention=intention,
            plan=plan,
            proposed_command=command,
            boundary_records=tuple(records),
            final_confidence=plan.confidence,
        )
        _LOG.debug(
            "cognitive_loop_prepared",
            extra={
                "cognition": {
                    "invocation_id": invocation_id,
                    "agent_id": agent_id,
                    "boundary_count": len(records),
                    "final_confidence": plan.confidence,
                    "command_type": type(command).__name__,
                    "goal_count": len(goal_board.goals),
                    "status": "prepared",
                }
            },
        )
        return proposal

    async def complete(
        self,
        proposal: CognitiveLoopProposal,
        *,
        effective_command: AgentCommand,
        reflection_cursor: object | None = None,
        decision_journal: tuple[object, ...] | None = None,
    ) -> CognitiveLoopResult:
        """Bind the effective command and complete memory-update / next state.

        ``effective_command`` may differ from ``proposal.proposed_command`` after
        trusted intervention. Memory hooks and ``last_command_kind`` always use
        the effective command, never a suppressed proposal.
        """
        if type(proposal) is not CognitiveLoopProposal:
            raise TypeError("complete requires CognitiveLoopProposal")
        command = require_agent_command(effective_command)
        records = list(proposal.boundary_records)
        loop_input = proposal.loop_input
        agent_id = loop_input.agent_id.value
        invocation_id = proposal.invocation_id
        fail = self._make_fail(
            records=records, invocation_id=invocation_id, agent_id=agent_id
        )
        run_stage = self._make_run_stage(
            loop_input=loop_input,
            records=records,
            invocation_id=invocation_id,
            agent_id=agent_id,
            fail=fail,
        )

        effective_plan = ActionPlan(
            owner_id=proposal.plan.owner_id,
            command=command,
            confidence=proposal.plan.confidence,
            decision_metadata=proposal.plan.decision_metadata,
        )
        updates = await run_stage(
            kind=ComponentKind.MEMORY_UPDATE,
            ordinal=10,
            input_artifact=effective_plan,
            awaitable=self._memory_updates.propose_updates(
                loop_input,
                effective_plan,
                proposal.perception,
                proposal.memory,
                proposal.intention,
                proposal.self_state,
            ),
            expected_type=tuple,
        )
        assert type(updates) is tuple
        consolidation = await self._plan_sleep_consolidation(
            proposal=proposal,
            command=command,
            updates=updates,
        )
        reflection = await self._plan_reflection(
            proposal=proposal,
            updates=updates,
            consolidation=consolidation,
            reflection_cursor=reflection_cursor,
            decision_journal=decision_journal,
        )
        identity_revisions, identity_dissonance = self._identity_revisions(
            proposal=proposal,
            updates=updates,
            consolidation=consolidation,
            reflection=reflection,
            command=command,
        )

        next_state = InternalAgentState(
            owner_id=loop_input.agent_id,
            invocation_count=loop_input.internal_state.invocation_count + 1,
            last_intention=(
                proposal.intention.intention
                if type(proposal.intention.intention) is IntentionCode
                else None
            ),
            last_command_kind=type(command).__name__.lower(),
        )
        pending_accesses = proposal.memory.pending_accesses
        if consolidation is not None:
            from memory.models import MemoryAccessReceipt

            stored_ids = {
                trace.memory_id
                for trace in proposal.loop_input.snapshot.memories
            }
            pending_accesses = pending_accesses + tuple(
                MemoryAccessReceipt(
                    memory_id=memory_id,
                    access_tick=consolidation.audit.tick,
                    operation_id=(
                        f"offline-consolidation:{consolidation.audit.tick}:"
                        f"{memory_id.value}"
                    ),
                )
                for memory_id in consolidation.selection.strengthen_ids
                if memory_id in stored_ids
            )
        result = CognitiveLoopResult(
            invocation_id=invocation_id,
            agent_id=loop_input.agent_id,
            command=command,
            boundary_records=tuple(records),
            memory_update_intents=updates,
            final_confidence=proposal.final_confidence,
            internal_state=next_state,
            pending_accesses=pending_accesses,
            pending_reconsolidation=proposal.memory.reconsolidation,
            pending_semanticization=proposal.memory.pending_semanticization,
            offline_consolidation=consolidation,
            reflection=reflection,
            identity_revisions=identity_revisions,
            identity_dissonance=identity_dissonance,
        )
        _LOG.debug(
            "cognitive_loop_complete",
            extra={
                "cognition": {
                    "invocation_id": invocation_id,
                    "agent_id": agent_id,
                    "boundary_count": len(records),
                    "memory_update_count": len(updates),
                    "pending_access_count": len(proposal.memory.pending_accesses),
                    "reconstruction_count": len(proposal.memory.reconstructions),
                    "pending_write_count": 1 if proposal.memory.reconsolidation else 0,
                    "semanticization_pending": (
                        proposal.memory.pending_semanticization is not None
                    ),
                    "final_confidence": proposal.final_confidence,
                    "command_type": type(command).__name__,
                    "effective_matches_proposal": command == proposal.proposed_command,
                    "status": "completed",
                }
            },
        )
        _ = _STAGE_ORDER
        return result

    def _identity_revisions(
            self,
            *,
            proposal: CognitiveLoopProposal,
            updates: tuple[object, ...],
            consolidation: object | None,
            reflection: object | None,
            command: object,
        ) -> tuple[tuple[object, ...], tuple[object, ...]]:
            from agents.cognition.configuration import CognitionIdentityMode
            from agents.cognition.identity import (
                appraise_identity,
                detect_identity_dissonance,
                parse_identity_predicate,
                without_overlapping_identity_requests,
            )
            from social.relationships import DirectedRelationshipProfile

            if self._identity_mode is not CognitionIdentityMode.ENABLED:
                return (), ()
            snapshot = proposal.loop_input.snapshot
            memories = list(_tick_memories(proposal, updates))
            relationships = (
                ()
                if snapshot is None
                else tuple(
                    item
                    for item in snapshot.relationships
                    if type(item) is DirectedRelationshipProfile
                )
            )
            beliefs = () if snapshot is None else snapshot.semantic_beliefs
            appraisal = appraise_identity(
                owner_id=proposal.agent_id,
                tick=proposal.loop_input.observation.tick,
                memories=tuple(memories),
                occurrences=proposal.loop_input.observation.occurrences,
                goals=proposal.goal_board.goals,
                relationships=relationships,
                futures=proposal.futures,
                beliefs=beliefs,
                self_model=proposal.self_state,
            )
            kept = without_overlapping_identity_requests(
                appraisal.requests,
                consolidation=consolidation,
                reflection=reflection,
            )
            aspect_counts: dict[str, int] = {}
            for request in kept:
                aspect, _provenance, _token = parse_identity_predicate(
                    request.claim.predicate
                )
                aspect_counts[aspect.value] = aspect_counts.get(aspect.value, 0) + 1
            _LOG.debug(
                "identity_pending",
                extra={
                    "request_count": len(kept),
                    "aspect_counts": aspect_counts,
                },
            )
            selected_future_id = getattr(proposal.intention, "selected_future_id", None)
            dissonance = detect_identity_dissonance(
                owner_id=proposal.agent_id,
                tick=proposal.loop_input.observation.tick,
                command=command,
                goals=proposal.goal_board.goals,
                futures=proposal.futures,
                identity=proposal.self_state.identity,
                memories=tuple(memories),
                selected_future_id=(
                    selected_future_id if type(selected_future_id) is str else None
                ),
                deferred=self._deferred_dissonance,  # type: ignore[arg-type]
            )
            self._deferred_dissonance = dissonance.deferred
            combined = without_overlapping_identity_requests(
                (*kept, *dissonance.requests),
                consolidation=consolidation,
                reflection=reflection,
            )
            return combined, dissonance.notices

    async def _plan_reflection(
        self,
        *,
        proposal: CognitiveLoopProposal,
        updates: tuple[object, ...],
        consolidation: object | None,
        reflection_cursor: object | None,
        decision_journal: tuple[object, ...] | None,
    ) -> object | None:
        from agents.cognition.configuration import CognitionReflectionMode
        from agents.cognition.models import EmotionDriverCode, MemoryUpdateKind
        from agents.cognition.reflection import (
            LLMReflectionSelector,
            ReflectionContext,
            ReflectionCursor,
            ReflectionEngine,
            ReflectionTriggerInput,
            SubjectiveDecisionRecord,
            _drop_consolidation_overlaps,
            default_reflection_policy,
            drop_unprovenanced_candidates,
            log_reflection_aborted,
            materialize_reflection_candidates,
            plan_reflection,
        )
        from agents.models import GoalId, GoalStatus
        from memory.models import MemoryTrace
        from social.relationships import DirectedRelationshipProfile

        mode = self._reflection_mode
        if mode is CognitionReflectionMode.DISABLED:
            return None
        owner = proposal.agent_id
        observation = proposal.loop_input.observation
        tick = observation.tick
        if type(proposal.self_state) is not SelfModel:
            log_reflection_aborted(
                owner_id=owner.value, tick=tick, reason_code="invalid_type"
            )
            return None
        snapshot = proposal.loop_input.snapshot
        if snapshot is None or snapshot.owner_id != owner:
            log_reflection_aborted(
                owner_id=owner.value, tick=tick, reason_code="snapshot_missing"
            )
            return None
        policy = self._reflection_policy
        if policy is None:
            policy = default_reflection_policy(
                allow_provider=mode is CognitionReflectionMode.LLM_ASSISTED
            )
        cursor = reflection_cursor
        if cursor is None:
            cursor = ReflectionCursor(owner_id=owner)
        if type(cursor) is not ReflectionCursor:
            log_reflection_aborted(
                owner_id=owner.value, tick=tick, reason_code="invalid_type"
            )
            return None
        journal_items = () if decision_journal is None else decision_journal
        journal: list[SubjectiveDecisionRecord] = []
        for record in journal_items:
            if type(record) is not SubjectiveDecisionRecord:
                log_reflection_aborted(
                    owner_id=owner.value, tick=tick, reason_code="invalid_type"
                )
                return None
            if record.tick == tick and record.outcome_code.value == "unknown":
                continue
            journal.append(record)
        evaluation = proposal.emotional_state
        intensity = None
        if EmotionDriverCode.PASSTHROUGH not in evaluation.driver_codes:
            intensity = evaluation.state.max_intensity()
        occurrence_kinds = tuple(item.kind for item in observation.occurrences)
        failures = sum(
            1
            for item in observation.occurrences
            if item.actor_id == observation.observer_id and item.success is False
        )
        horizons = set(policy.major_goal_horizons)
        completed: list[GoalId] = []
        for goal in snapshot.goals:
            if goal.status is not GoalStatus.COMPLETED:
                continue
            if goal.horizon not in horizons:
                continue
            completed.append(goal.goal_id)
        masses = tuple(
            belief.confidence.contradiction_mass for belief in snapshot.semantic_beliefs
        )
        counts = tuple(
            belief.evidence_contradiction_count for belief in snapshot.semantic_beliefs
        )
        ordinals: list[tuple[str, str, int]] = []
        cited: list[str] = []
        for profile in snapshot.relationships:
            if type(profile) is not DirectedRelationshipProfile:
                continue
            if profile.source_id != owner:
                continue
            ordinals.append(
                (
                    profile.source_id.value,
                    profile.target_id.value,
                    profile.revision_ordinal,
                )
            )
            for dimension in profile.dimensions:
                for evidence in dimension.evidence:
                    cited.append(evidence.memory_ref)
        memories = list(snapshot.memories)
        for intent in updates:
            if (
                type(intent) is MemoryUpdateIntent
                and intent.kind is MemoryUpdateKind.WRITE_MEMORY
                and type(intent.memory) is MemoryTrace
            ):
                memories.append(intent.memory)
        try:
            matched = ReflectionEngine().triggers(
                ReflectionTriggerInput(
                    owner_id=owner,
                    tick=tick,
                    policy=policy,
                    cursor=cursor,
                    mode=mode.value,
                    occurrence_kinds=occurrence_kinds,
                    emotion_max_intensity=intensity,
                    journal=tuple(journal),
                    observation_owner_failures=failures,
                    completed_goal_ids=tuple(completed),
                    contradiction_masses=masses,
                    contradiction_counts=counts,
                    relationship_ordinals=tuple(ordinals),
                )
            )
            if not matched.matched:
                return None
            from agents.cognition.configuration import CognitionIdentityMode
            from agents.cognition.identity import (
                IdentityState,
                reflection_cue_memory_ids,
            )

            identity = proposal.self_state.identity
            if (
                self._identity_mode is CognitionIdentityMode.ENABLED
                and type(identity) is IdentityState
            ):
                cues = reflection_cue_memory_ids(identity)
                cited.extend(cues)
                known = {trace.memory_id.value for trace in memories}
                preferred = sum(1 for item in dict.fromkeys(cues) if item in known)
                remaining = policy.max_memories - min(preferred, policy.max_memories)
                _LOG.debug(
                    "identity_reflection_cue",
                    extra={
                        "owner_id": owner.value,
                        "tick": tick,
                        "preferred_count": preferred,
                        "remaining_cap": remaining,
                    },
                )
            context = ReflectionContext(
                owner_id=owner,
                tick=tick,
                policy=policy,
                memories=tuple(memories),
                beliefs=snapshot.semantic_beliefs,
                goals=snapshot.goals,
                decisions=tuple(journal),
                owner_entity_id=observation.observer_id,
                cited_memory_ids=tuple(dict.fromkeys(cited)),
            )
            candidates = _drop_consolidation_overlaps(
                drop_unprovenanced_candidates(
                    context, materialize_reflection_candidates(context)
                ),
                consolidation,
            )
            selected_ids = None
            fallback_used = False
            if mode is CognitionReflectionMode.LLM_ASSISTED:
                selector = self._reflection_selector
                if type(selector) is not LLMReflectionSelector:
                    selector = LLMReflectionSelector(None)
                selected_ids, fallback_used = await selector.select(
                    candidates,
                    policy=policy,
                    owner_id=owner,
                    tick=tick,
                )
            return plan_reflection(
                context=context,
                triggers=matched,
                mode=mode.value,
                consolidation=consolidation,
                acknowledged_goal_ids=tuple(completed),
                selected_ids=selected_ids,
                fallback_used=fallback_used,
            )
        except (TypeError, ValueError):
            log_reflection_aborted(
                owner_id=owner.value, tick=tick, reason_code="schema_invalid"
            )
            return None

    async def _plan_sleep_consolidation(
        self,
        *,
        proposal: CognitiveLoopProposal,
        command: AgentCommand,
        updates: tuple[object, ...],
    ) -> object | None:
        from agents.cognition.configuration import CognitionConsolidationMode
        from agents.cognition.consolidation import orchestrate_offline_consolidation
        from agents.cognition.models import MemoryUpdateIntent, MemoryUpdateKind
        from memory.models import OfflineConsolidationPolicy
        from world.actions import Sleep
        from world.models import LifeStatus

        mode = self._consolidation_mode
        terminal = proposal.perception.life_status is LifeStatus.DEAD
        is_sleep = type(command) is Sleep
        if mode is CognitionConsolidationMode.DISABLED or not is_sleep or terminal:
            if is_sleep or mode is not CognitionConsolidationMode.DISABLED:
                if mode is CognitionConsolidationMode.DISABLED:
                    reason = "disabled"
                elif terminal and is_sleep:
                    reason = "terminal"
                else:
                    reason = "not_sleep"
                _LOG.info(
                    "offline_consolidation_skipped reason=%s agent_id=%s tick=%s",
                    reason,
                    proposal.agent_id.value,
                    proposal.loop_input.observation.tick,
                )
            return None
        snapshot = proposal.loop_input.snapshot
        if snapshot is None:
            _LOG.error(
                "offline_consolidation_aborted agent_id=%s tick=%s "
                "reason_code=snapshot_missing",
                proposal.agent_id.value,
                proposal.loop_input.observation.tick,
            )
            return None
        write_intents = tuple(
            intent
            for intent in updates
            if type(intent) is MemoryUpdateIntent
            and intent.kind is MemoryUpdateKind.WRITE_MEMORY
        )
        policy = self._consolidation_policy
        if type(policy) is not OfflineConsolidationPolicy:
            policy = OfflineConsolidationPolicy(
                allow_provider=mode is CognitionConsolidationMode.LLM_ASSISTED
            )
        plan = orchestrate_offline_consolidation(
            snapshot=snapshot,
            self_model=proposal.self_state,
            write_intents=write_intents,
            tick=proposal.loop_input.observation.tick,
            mode=mode.value,
            policy=policy,
        )
        if mode is CognitionConsolidationMode.LLM_ASSISTED:
            from agents.cognition.consolidation import LLMOfflineConsolidationSelector

            selector = self._consolidation_selector
            if type(selector) is not LLMOfflineConsolidationSelector:
                selector = LLMOfflineConsolidationSelector(None)
            restricted = await selector.restrict(plan.selection, policy=policy)
            if restricted != plan.selection:
                plan = orchestrate_offline_consolidation(
                    snapshot=snapshot,
                    self_model=proposal.self_state,
                    write_intents=write_intents,
                    tick=proposal.loop_input.observation.tick,
                    mode=mode.value,
                    policy=policy,
                    selection_override=restricted,
                )
        _LOG.debug(
            "offline_consolidation_pending agent_id=%s tick=%s mode=%s "
            "merge_count=%s strengthen_count=%s soft_forget_count=%s",
            proposal.agent_id.value,
            plan.audit.tick,
            mode.value,
            plan.audit.merge_count,
            plan.audit.strengthen_count,
            plan.audit.soft_forget_count,
        )
        return plan

    async def run(
        self,
        loop_input: CognitiveLoopInput,
        *,
        invocation_id: str,
    ) -> CognitiveLoopResult:
        """Prepare then complete with the proposed command (one-call path)."""
        proposal = await self.prepare(loop_input, invocation_id=invocation_id)
        return await self.complete(
            proposal, effective_command=proposal.proposed_command
        )

    def _make_fail(
        self,
        *,
        records: list[ComponentBoundaryRecord],
        invocation_id: str,
        agent_id: str,
    ):
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

        return fail

    def _make_run_stage(
        self,
        *,
        loop_input: CognitiveLoopInput,
        records: list[ComponentBoundaryRecord],
        invocation_id: str,
        agent_id: str,
        fail: object,
    ):
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
                fail(  # type: ignore[operator]
                    reason=CognitionFailureReason.CANCELLED,
                    kind=kind,
                    ordinal=ordinal,
                    input_artifact=input_artifact,
                    status=ComponentStatus.CANCELLED,
                )
                raise  # pragma: no cover
            except Exception:
                fail(  # type: ignore[operator]
                    reason=CognitionFailureReason.COMPONENT_FAILED,
                    kind=kind,
                    ordinal=ordinal,
                    input_artifact=input_artifact,
                )
                raise  # pragma: no cover

            if type(output) is not expected_type:
                fail(  # type: ignore[operator]
                    reason=CognitionFailureReason.TYPE_MISMATCH,
                    kind=kind,
                    ordinal=ordinal,
                    input_artifact=input_artifact,
                )
            owner = getattr(output, "owner_id", None)
            if owner is not None and owner != loop_input.agent_id:
                fail(  # type: ignore[operator]
                    reason=CognitionFailureReason.OWNERSHIP,
                    kind=kind,
                    ordinal=ordinal,
                    input_artifact=input_artifact,
                )

            if kind is ComponentKind.MEMORY_UPDATE:
                if not isinstance(output, tuple):
                    fail(  # type: ignore[operator]
                        reason=CognitionFailureReason.TYPE_MISMATCH,
                        kind=kind,
                        ordinal=ordinal,
                        input_artifact=input_artifact,
                    )
                intents = cast(tuple[object, ...], output)
                for item in intents:
                    if type(item) is not MemoryUpdateIntent:
                        fail(  # type: ignore[operator]
                            reason=CognitionFailureReason.TYPE_MISMATCH,
                            kind=kind,
                            ordinal=ordinal,
                            input_artifact=input_artifact,
                        )
                    intent = cast(MemoryUpdateIntent, item)
                    if intent.owner_id != loop_input.agent_id:
                        fail(  # type: ignore[operator]
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
                    fail(  # type: ignore[operator]
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

        return run_stage
