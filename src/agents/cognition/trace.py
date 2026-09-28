"""Cognition-owned cognitive execution trace stage summaries.

Pure projection helpers and closed summary types for scientific observability.
These types carry **no** ``run_id`` and perform **no** persistence. Run-scoped
envelopes and repositories live in ``simulation``.

Forbidden on public types (mirrored from ``ComponentBoundaryRecord``):
``rationale``, ``chain_of_thought``, ``prompt``, ``raw_response``,
``credentials``, ``endpoint``.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from agents.cognition.loop import CognitiveLoopFailure
from agents.cognition.models import (
    ActionPlan,
    CognitiveLoopInput,
    CognitiveLoopResult,
    ComponentBoundaryRecord,
    ComponentKind,
    ComponentStatus,
    DecisionMetadata,
    EmotionalStateEvaluation,
    GoalBoard,
    InterpretedPerception,
    MotivationEvaluation,
    PossibleFutures,
    RetrievedMemoryContext,
    SelectedIntention,
    SelfBeliefState,
    SelfModel,
    SituationModel,
    SubjectiveSnapshot,
    UncertaintyBand,
    intensity_band,
    require_confidence,
)
from agents.models import GoalHorizon, GoalStatus
from world.identifiers import require_exact_nonneg_int, require_stable_id
from world.observations import Observation

_LOG: Final[logging.Logger] = logging.getLogger("agents.cognition.trace")

__all__ = [
    "COGNITION_TRACE_SUMMARY_SCHEMA",
    "FORBIDDEN_TRACE_ATTRIBUTES",
    "SCIENTIFIC_TRACE_STAGE_SEQUENCE",
    "TOM_UNAVAILABLE_REASON",
    "CognitionTraceCountKey",
    "CognitionTraceIdRef",
    "CognitionTraceLlmMeta",
    "CognitionTraceRefKind",
    "CognitionTraceStageKind",
    "CognitionTraceStageStatus",
    "CognitionTraceStageSummary",
    "CognitionTraceValidationError",
    "component_kinds_for_stage",
    "project_cognition_trace_stages",
    "reject_forbidden_trace_attributes",
    "stage_summaries_content_hash",
    "unavailable_stage_summary",
]

COGNITION_TRACE_SUMMARY_SCHEMA: Final[str] = "cognition-trace-stage-summary-v1"
TOM_UNAVAILABLE_REASON: Final[str] = "tom_not_implemented"
_STAGE_MISSING_REASON: Final[str] = "stage_missing"
_OWNERSHIP_MISMATCH_REASON: Final[str] = "ownership_mismatch"

FORBIDDEN_TRACE_ATTRIBUTES: Final[frozenset[str]] = frozenset(
    {
        "rationale",
        "chain_of_thought",
        "prompt",
        "raw_response",
        "credentials",
        "endpoint",
    }
)

_MAX_SELECTION_CODES: Final[int] = 64
_MAX_ID_REFS: Final[int] = 256
_MAX_COUNT_ENTRIES: Final[int] = 64
_MAX_REASON_CODE_CHARS: Final[int] = 128


class CognitionTraceValidationError(ValueError):
    """Fail-closed validation for cognition trace summary construction."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


class CognitionTraceStageKind(StrEnum):
    """Scientific trace-view stage kinds (not necessarily CognitiveLoop stages).

    Map 1:1 to ``ComponentKind`` where possible; projection-only kinds cover
    beliefs/goals/emotional state and theory-of-mind placeholders.
    """

    OBSERVATION = "observation"
    RETRIEVED_MEMORIES = "retrieved_memories"
    RECONSTRUCTED_MEMORIES = "reconstructed_memories"
    SITUATION_MODEL = "situation_model"
    BELIEFS = "beliefs"
    EMOTIONAL_STATE = "emotional_state"
    GOALS = "goals"
    IMAGINED_FUTURES = "imagined_futures"
    THEORY_OF_MIND = "theory_of_mind"
    SELECTED_INTENTION = "selected_intention"
    PLANNED_ACTION = "planned_action"


SCIENTIFIC_TRACE_STAGE_SEQUENCE: Final[tuple[CognitionTraceStageKind, ...]] = (
    CognitionTraceStageKind.OBSERVATION,
    CognitionTraceStageKind.RETRIEVED_MEMORIES,
    CognitionTraceStageKind.RECONSTRUCTED_MEMORIES,
    CognitionTraceStageKind.SITUATION_MODEL,
    CognitionTraceStageKind.BELIEFS,
    CognitionTraceStageKind.EMOTIONAL_STATE,
    CognitionTraceStageKind.GOALS,
    CognitionTraceStageKind.IMAGINED_FUTURES,
    CognitionTraceStageKind.THEORY_OF_MIND,
    CognitionTraceStageKind.SELECTED_INTENTION,
    CognitionTraceStageKind.PLANNED_ACTION,
)


class CognitionTraceStageStatus(StrEnum):
    """Closed completion status for one trace-view stage summary."""

    COMPLETED = "completed"
    FAILED = "failed"
    UNAVAILABLE = "unavailable"
    SKIPPED = "skipped"
    TRUNCATED = "truncated"


class CognitionTraceRefKind(StrEnum):
    """Closed identity-reference kinds for stage summaries."""

    MEMORY = "memory"
    BELIEF = "belief"
    SEMANTIC_BELIEF = "semantic_belief"
    GOAL = "goal"
    FUTURE = "future"
    DRIVE = "drive"
    EMOTION = "emotion"
    COMMAND = "command"
    INTENTION = "intention"
    MOTIVE = "motive"
    CLAIM = "claim"
    AGENT = "agent"
    INVOCATION = "invocation"


class CognitionTraceCountKey(StrEnum):
    """Closed count keys allowed on stage summaries."""

    MEMORY_HIT_COUNT = "memory_hit_count"
    RECONSTRUCTION_COUNT = "reconstruction_count"
    REFERENCE_EPISODE_COUNT = "reference_episode_count"
    BELIEF_COUNT = "belief_count"
    SEMANTIC_BELIEF_COUNT = "semantic_belief_count"
    GOAL_COUNT = "goal_count"
    GOAL_STATUS_ACTIVE = "goal_status_active"
    GOAL_STATUS_COMPLETED = "goal_status_completed"
    GOAL_STATUS_FAILED = "goal_status_failed"
    GOAL_STATUS_ABANDONED = "goal_status_abandoned"
    GOAL_STATUS_SUSPENDED = "goal_status_suspended"
    GOAL_HORIZON_DESIRE = "goal_horizon_desire"
    GOAL_HORIZON_LONG_TERM = "goal_horizon_long_term"
    GOAL_HORIZON_MEDIUM_TERM = "goal_horizon_medium_term"
    GOAL_HORIZON_SUBGOAL = "goal_horizon_subgoal"
    GOAL_HORIZON_CURRENT_INTENTION = "goal_horizon_current_intention"
    GOAL_FOCI_COUNT = "goal_foci_count"
    DRIVE_COUNT = "drive_count"
    EMOTION_KIND_COUNT = "emotion_kind_count"
    FUTURE_COUNT = "future_count"
    CLAIM_COUNT = "claim_count"
    CANDIDATE_COUNT = "candidate_count"
    SELECTION_CODE_COUNT = "selection_code_count"
    COMMUNICATION_COUNT = "communication_count"
    VISIBLE_BODY_COUNT = "visible_body_count"
    ITEM_COUNT = "item_count"
    RESOURCE_COUNT = "resource_count"


# ComponentKind → trace stage(s). Projection-only stages are absent here.
_COMPONENT_TO_TRACE: Final[
    Mapping[ComponentKind, tuple[CognitionTraceStageKind, ...]]
] = {
    ComponentKind.PERCEPTION: (CognitionTraceStageKind.OBSERVATION,),
    ComponentKind.MEMORY_RETRIEVAL: (
        CognitionTraceStageKind.RETRIEVED_MEMORIES,
        CognitionTraceStageKind.RECONSTRUCTED_MEMORIES,
    ),
    ComponentKind.SITUATION: (CognitionTraceStageKind.SITUATION_MODEL,),
    ComponentKind.GOAL_MANAGEMENT: (CognitionTraceStageKind.GOALS,),
    ComponentKind.EMOTIONAL_STATE: (CognitionTraceStageKind.EMOTIONAL_STATE,),
    ComponentKind.FUTURES: (CognitionTraceStageKind.IMAGINED_FUTURES,),
    ComponentKind.INTENTION: (CognitionTraceStageKind.SELECTED_INTENTION,),
    ComponentKind.PLANNING: (CognitionTraceStageKind.PLANNED_ACTION,),
}


def component_kinds_for_stage(
    stage: CognitionTraceStageKind,
) -> frozenset[ComponentKind]:
    """Return CognitiveLoop component kinds that feed a trace stage (may be empty)."""
    matched: set[ComponentKind] = set()
    for component, stages in _COMPONENT_TO_TRACE.items():
        if stage in stages:
            matched.add(component)
    return frozenset(matched)


def reject_forbidden_trace_attributes(value: object, *, type_name: str) -> None:
    """Raise if a public trace type exposes forbidden payload/CoT attributes."""
    for forbidden in FORBIDDEN_TRACE_ATTRIBUTES:
        if hasattr(value, forbidden):
            _LOG.error(
                "cognition_trace_forbidden_attribute",
                extra={
                    "reason_code": "forbidden_attribute",
                    "type_name": type_name,
                    "attribute": forbidden,
                },
            )
            raise TypeError(f"{type_name} must not expose {forbidden!r}")


@dataclass(frozen=True, slots=True)
class CognitionTraceIdRef:
    """Opaque typed identity reference (no narrative payload)."""

    kind: CognitionTraceRefKind
    value: str

    def __post_init__(self) -> None:
        if type(self.kind) is not CognitionTraceRefKind:
            raise TypeError("CognitionTraceIdRef.kind must be CognitionTraceRefKind")
        object.__setattr__(
            self,
            "value",
            require_stable_id("CognitionTraceIdRef.value", self.value),
        )
        reject_forbidden_trace_attributes(self, type_name="CognitionTraceIdRef")

    def __repr__(self) -> str:
        return f"CognitionTraceIdRef(kind={self.kind.value!r}, value={self.value!r})"


@dataclass(frozen=True, slots=True)
class CognitionTraceLlmMeta:
    """Allowlisted LLM operational metadata only (no prompts/bodies/credentials).

    Callers extract fields from ``LLMResultMetadata`` outside this module when
    needed; cognition does not import ``llm`` here.
    """

    provider_name: str | None = None
    model_name: str | None = None
    finish_reason: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    attempts: int | None = None

    def __post_init__(self) -> None:
        for field_name in ("provider_name", "model_name", "finish_reason"):
            raw = getattr(self, field_name)
            if raw is not None:
                object.__setattr__(
                    self,
                    field_name,
                    require_stable_id(f"CognitionTraceLlmMeta.{field_name}", raw),
                )
        for field_name in (
            "input_tokens",
            "output_tokens",
            "total_tokens",
            "attempts",
        ):
            raw = getattr(self, field_name)
            if raw is not None:
                object.__setattr__(
                    self,
                    field_name,
                    require_exact_nonneg_int(
                        f"CognitionTraceLlmMeta.{field_name}", raw
                    ),
                )
        reject_forbidden_trace_attributes(self, type_name="CognitionTraceLlmMeta")

    def __repr__(self) -> str:
        return (
            "CognitionTraceLlmMeta("
            f"provider_name={self.provider_name!r}, "
            f"model_name={self.model_name!r}, "
            f"finish_reason={self.finish_reason!r}, "
            f"attempts={self.attempts})"
        )


@dataclass(frozen=True, slots=True)
class CognitionTraceStageSummary:
    """One scientific-sequence stage envelope (cognition-owned, no run_id).

    ``latency_ms`` is intentionally omitted — CognitiveLoop has no stage timer.
    """

    stage_kind: CognitionTraceStageKind
    status: CognitionTraceStageStatus
    ordinal: int
    confidence: float | None = None
    uncertainty_band: UncertaintyBand | None = None
    selection_codes: tuple[str, ...] = ()
    id_refs: tuple[CognitionTraceIdRef, ...] = ()
    counts: Mapping[str, int] | None = None
    reason_code: str | None = None
    decision_metadata: DecisionMetadata | None = None
    command_kind: str | None = None
    intention_code: str | None = None
    llm_meta: CognitionTraceLlmMeta | None = None
    schema_version: str = COGNITION_TRACE_SUMMARY_SCHEMA

    def __post_init__(self) -> None:
        if type(self.stage_kind) is not CognitionTraceStageKind:
            raise TypeError(
                "CognitionTraceStageSummary.stage_kind must be CognitionTraceStageKind"
            )
        if type(self.status) is not CognitionTraceStageStatus:
            raise TypeError(
                "CognitionTraceStageSummary.status must be CognitionTraceStageStatus"
            )
        object.__setattr__(
            self,
            "ordinal",
            require_exact_nonneg_int(
                "CognitionTraceStageSummary.ordinal", self.ordinal
            ),
        )
        if self.confidence is not None:
            object.__setattr__(
                self,
                "confidence",
                require_confidence(
                    "CognitionTraceStageSummary.confidence", self.confidence
                ),
            )
        if self.uncertainty_band is not None and type(self.uncertainty_band) is not (
            UncertaintyBand
        ):
            raise TypeError(
                "CognitionTraceStageSummary.uncertainty_band must be "
                "UncertaintyBand or None"
            )
        object.__setattr__(
            self,
            "selection_codes",
            _require_selection_codes(self.selection_codes),
        )
        object.__setattr__(self, "id_refs", _require_id_refs(self.id_refs))
        object.__setattr__(self, "counts", _require_counts(self.counts))
        if self.reason_code is not None:
            text = require_stable_id(
                "CognitionTraceStageSummary.reason_code", self.reason_code
            )
            if len(text) > _MAX_REASON_CODE_CHARS:
                raise CognitionTraceValidationError(
                    "reason_code_too_long",
                    "CognitionTraceStageSummary.reason_code exceeds maximum length",
                )
            object.__setattr__(self, "reason_code", text)
        if self.decision_metadata is not None and type(self.decision_metadata) is not (
            DecisionMetadata
        ):
            raise TypeError(
                "CognitionTraceStageSummary.decision_metadata must be "
                "DecisionMetadata or None"
            )
        if self.command_kind is not None:
            object.__setattr__(
                self,
                "command_kind",
                require_stable_id(
                    "CognitionTraceStageSummary.command_kind", self.command_kind
                ),
            )
        if self.intention_code is not None:
            object.__setattr__(
                self,
                "intention_code",
                require_stable_id(
                    "CognitionTraceStageSummary.intention_code", self.intention_code
                ),
            )
        if (
            self.llm_meta is not None
            and type(self.llm_meta) is not CognitionTraceLlmMeta
        ):
            raise TypeError(
                "CognitionTraceStageSummary.llm_meta must be CognitionTraceLlmMeta "
                "or None"
            )
        object.__setattr__(
            self,
            "schema_version",
            require_stable_id(
                "CognitionTraceStageSummary.schema_version", self.schema_version
            ),
        )
        if self.schema_version != COGNITION_TRACE_SUMMARY_SCHEMA:
            _LOG.error(
                "cognition_trace_unsupported_schema",
                extra={
                    "reason_code": "unsupported_version",
                    "schema_version": self.schema_version,
                },
            )
            raise CognitionTraceValidationError(
                "unsupported_version",
                f"CognitionTraceStageSummary.schema_version must be "
                f"{COGNITION_TRACE_SUMMARY_SCHEMA!r}",
            )
        if (
            self.status is CognitionTraceStageStatus.UNAVAILABLE
            and self.reason_code is None
        ):
            raise CognitionTraceValidationError(
                "unavailable_requires_reason",
                "unavailable stage summaries require reason_code",
            )
        reject_forbidden_trace_attributes(self, type_name="CognitionTraceStageSummary")
        _LOG.debug(
            "cognition_trace_stage_summary_constructed",
            extra={
                "stage_kind": self.stage_kind.value,
                "status": self.status.value,
                "ordinal": self.ordinal,
                "id_ref_count": len(self.id_refs),
                "count_entry_count": 0 if self.counts is None else len(self.counts),
                "selection_code_count": len(self.selection_codes),
                "has_llm_meta": self.llm_meta is not None,
            },
        )

    def __repr__(self) -> str:
        return (
            f"CognitionTraceStageSummary(stage_kind={self.stage_kind.value!r}, "
            f"status={self.status.value!r}, ordinal={self.ordinal}, "
            f"confidence={self.confidence})"
        )


def unavailable_stage_summary(
    stage_kind: CognitionTraceStageKind,
    *,
    ordinal: int,
    reason_code: str,
) -> CognitionTraceStageSummary:
    """Build an explicit unavailable placeholder (e.g. theory-of-mind)."""
    return CognitionTraceStageSummary(
        stage_kind=stage_kind,
        status=CognitionTraceStageStatus.UNAVAILABLE,
        ordinal=ordinal,
        reason_code=reason_code,
    )


def _project_theory_of_mind(
    *,
    snap: SubjectiveSnapshot | None,
    loop_result: CognitiveLoopResult | None,
    ordinal: int,
) -> CognitionTraceStageSummary:
    from agents.cognition.theory_of_mind import (
        TheoryOfMind,
        default_theory_of_mind_policy,
    )

    carried = None if snap is None else snap.theory_of_mind
    if carried is None and loop_result is not None:
        carried = loop_result.theory_of_mind
    owner = ""
    if type(carried) is TheoryOfMind:
        owner = carried.owner_id.value
        threshold = default_theory_of_mind_policy().action_threshold
        aspects: list[str] = []
        refs: list[CognitionTraceIdRef] = []
        seen: set[str] = set()
        claims = 0
        peak = 0.0
        for item in carried.hypotheses:
            if item.aspect.value not in aspects:
                aspects.append(item.aspect.value)
            if item.subject_id.value not in seen:
                seen.add(item.subject_id.value)
                refs.append(
                    CognitionTraceIdRef(
                        kind=CognitionTraceRefKind.AGENT,
                        value=item.subject_id.value,
                    )
                )
            if item.confidence >= threshold:
                claims += 1
            peak = max(peak, item.confidence)
        _LOG.debug(
            "theory_of_mind_trace owner_id=%s status=completed hypothesis_count=%s "
            "reason_code=%s",
            owner,
            len(carried.hypotheses),
            "none",
        )
        return CognitionTraceStageSummary(
            stage_kind=CognitionTraceStageKind.THEORY_OF_MIND,
            status=CognitionTraceStageStatus.COMPLETED,
            ordinal=ordinal,
            confidence=peak,
            selection_codes=tuple(aspects),
            counts={
                CognitionTraceCountKey.CANDIDATE_COUNT.value: len(carried.hypotheses),
                CognitionTraceCountKey.CLAIM_COUNT.value: claims,
            },
            id_refs=tuple(refs),
        )
    _LOG.debug(
        "theory_of_mind_trace owner_id=%s status=unavailable hypothesis_count=0 "
        "reason_code=%s",
        owner,
        TOM_UNAVAILABLE_REASON,
    )
    return unavailable_stage_summary(
        CognitionTraceStageKind.THEORY_OF_MIND,
        ordinal=ordinal,
        reason_code=TOM_UNAVAILABLE_REASON,
    )


def project_cognition_trace_stages(
    *,
    boundary_records: Sequence[ComponentBoundaryRecord] | None = None,
    loop_result: CognitiveLoopResult | None = None,
    loop_failure: CognitiveLoopFailure | None = None,
    loop_input: CognitiveLoopInput | None = None,
    snapshot: SubjectiveSnapshot | None = None,
    agent_id: str | None = None,
    tick: int | None = None,
    invocation_id: str | None = None,
    llm_meta_by_stage: (
        Mapping[CognitionTraceStageKind, CognitionTraceLlmMeta] | None
    ) = None,
) -> tuple[CognitionTraceStageSummary, ...]:
    """Project loop receipts + snapshot context into the scientific stage sequence.

    Never embeds full ``Observation``, ``WorldEvent``, prompts, or CoT. ``run_id``
    is applied later by simulation. ``latency_ms`` is omitted.
    """
    records = _resolve_boundary_records(
        boundary_records=boundary_records,
        loop_result=loop_result,
        loop_failure=loop_failure,
    )
    resolved_agent, resolved_tick, resolved_invocation = _resolve_identity(
        records=records,
        loop_result=loop_result,
        loop_failure=loop_failure,
        loop_input=loop_input,
        agent_id=agent_id,
        tick=tick,
        invocation_id=invocation_id,
    )
    snap = snapshot
    if snap is None and loop_input is not None:
        snap = loop_input.snapshot
    if snap is not None and resolved_agent is not None:
        if snap.owner_id.value != resolved_agent:
            _LOG.error(
                "cognition_trace_ownership_mismatch",
                extra={
                    "reason_code": _OWNERSHIP_MISMATCH_REASON,
                    "agent_id": resolved_agent,
                    "snapshot_owner": snap.owner_id.value,
                },
            )
            raise CognitionTraceValidationError(
                _OWNERSHIP_MISMATCH_REASON,
                "SubjectiveSnapshot.owner_id must match agent_id",
            )

    by_kind = _index_records_by_kind(records)
    meta = {} if llm_meta_by_stage is None else dict(llm_meta_by_stage)
    stages: list[CognitionTraceStageSummary] = []

    for ordinal, stage_kind in enumerate(SCIENTIFIC_TRACE_STAGE_SEQUENCE):
        if stage_kind is CognitionTraceStageKind.OBSERVATION:
            stages.append(
                _project_observation(
                    by_kind.get(ComponentKind.PERCEPTION),
                    ordinal=ordinal,
                    llm_meta=meta.get(stage_kind),
                )
            )
        elif stage_kind is CognitionTraceStageKind.RETRIEVED_MEMORIES:
            stages.append(
                _project_retrieved_memories(
                    by_kind.get(ComponentKind.MEMORY_RETRIEVAL),
                    ordinal=ordinal,
                    llm_meta=meta.get(stage_kind),
                )
            )
        elif stage_kind is CognitionTraceStageKind.RECONSTRUCTED_MEMORIES:
            stages.append(
                _project_reconstructed_memories(
                    by_kind.get(ComponentKind.MEMORY_RETRIEVAL),
                    ordinal=ordinal,
                    llm_meta=meta.get(stage_kind),
                )
            )
        elif stage_kind is CognitionTraceStageKind.SITUATION_MODEL:
            stages.append(
                _project_situation(
                    by_kind.get(ComponentKind.SITUATION),
                    ordinal=ordinal,
                    llm_meta=meta.get(stage_kind),
                )
            )
        elif stage_kind is CognitionTraceStageKind.BELIEFS:
            stages.append(
                _project_beliefs(
                    snap=snap,
                    self_record=by_kind.get(ComponentKind.SELF_STATE),
                    ordinal=ordinal,
                    llm_meta=meta.get(stage_kind),
                )
            )
        elif stage_kind is CognitionTraceStageKind.EMOTIONAL_STATE:
            stages.append(
                _project_emotional_state(
                    emotion_record=by_kind.get(ComponentKind.EMOTIONAL_STATE),
                    motivation_record=by_kind.get(ComponentKind.MOTIVATION),
                    memory_record=by_kind.get(ComponentKind.MEMORY_RETRIEVAL),
                    snap=snap,
                    ordinal=ordinal,
                    llm_meta=meta.get(stage_kind),
                )
            )
        elif stage_kind is CognitionTraceStageKind.GOALS:
            stages.append(
                _project_goals(
                    snap=snap,
                    goal_record=by_kind.get(ComponentKind.GOAL_MANAGEMENT),
                    motivation_record=by_kind.get(ComponentKind.MOTIVATION),
                    self_record=by_kind.get(ComponentKind.SELF_STATE),
                    ordinal=ordinal,
                    llm_meta=meta.get(stage_kind),
                )
            )
        elif stage_kind is CognitionTraceStageKind.IMAGINED_FUTURES:
            stages.append(
                _project_futures(
                    by_kind.get(ComponentKind.FUTURES),
                    ordinal=ordinal,
                    llm_meta=meta.get(stage_kind),
                )
            )
        elif stage_kind is CognitionTraceStageKind.THEORY_OF_MIND:
            stages.append(
                _project_theory_of_mind(
                    snap=snap,
                    loop_result=loop_result,
                    ordinal=ordinal,
                )
            )
        elif stage_kind is CognitionTraceStageKind.SELECTED_INTENTION:
            stages.append(
                _project_intention(
                    by_kind.get(ComponentKind.INTENTION),
                    ordinal=ordinal,
                    llm_meta=meta.get(stage_kind),
                )
            )
        elif stage_kind is CognitionTraceStageKind.PLANNED_ACTION:
            stages.append(
                _project_planned_action(
                    by_kind.get(ComponentKind.PLANNING),
                    loop_result=loop_result,
                    ordinal=ordinal,
                    llm_meta=meta.get(stage_kind),
                )
            )
        else:  # pragma: no cover - closed enum
            raise CognitionTraceValidationError(
                "unsupported_stage",
                f"unsupported stage kind {stage_kind!r}",
            )

    result = tuple(stages)
    _LOG.debug(
        "cognition_trace_projected",
        extra={
            "invocation_id": resolved_invocation,
            "agent_id": resolved_agent,
            "tick": resolved_tick,
            "stage_count": len(result),
            "boundary_count": len(records),
        },
    )
    return result


def _resolve_boundary_records(
    *,
    boundary_records: Sequence[ComponentBoundaryRecord] | None,
    loop_result: CognitiveLoopResult | None,
    loop_failure: CognitiveLoopFailure | None,
) -> tuple[ComponentBoundaryRecord, ...]:
    if boundary_records is not None:
        return tuple(boundary_records)
    if loop_result is not None:
        return loop_result.boundary_records
    if loop_failure is not None:
        return loop_failure.boundary_records
    return ()


def _resolve_identity(
    *,
    records: Sequence[ComponentBoundaryRecord],
    loop_result: CognitiveLoopResult | None,
    loop_failure: CognitiveLoopFailure | None,
    loop_input: CognitiveLoopInput | None,
    agent_id: str | None,
    tick: int | None,
    invocation_id: str | None,
) -> tuple[str | None, int | None, str | None]:
    resolved_agent = agent_id
    resolved_tick = tick
    resolved_invocation = invocation_id
    if loop_result is not None:
        resolved_agent = resolved_agent or loop_result.agent_id.value
        resolved_invocation = resolved_invocation or loop_result.invocation_id
    if loop_failure is not None:
        resolved_agent = resolved_agent or loop_failure.agent_id
        resolved_invocation = resolved_invocation or loop_failure.invocation_id
    if loop_input is not None:
        resolved_agent = resolved_agent or loop_input.agent_id.value
        resolved_tick = (
            resolved_tick if resolved_tick is not None else loop_input.observation.tick
        )
    if resolved_invocation is None and records:
        resolved_invocation = records[0].invocation_id
    return resolved_agent, resolved_tick, resolved_invocation


def _index_records_by_kind(
    records: Sequence[ComponentBoundaryRecord],
) -> dict[ComponentKind, ComponentBoundaryRecord]:
    indexed: dict[ComponentKind, ComponentBoundaryRecord] = {}
    for record in records:
        # Last write wins if duplicates; CognitiveLoop emits one per kind.
        indexed[record.component_kind] = record
    return indexed


def _status_from_component(status: ComponentStatus) -> CognitionTraceStageStatus:
    if status is ComponentStatus.COMPLETED:
        return CognitionTraceStageStatus.COMPLETED
    if status is ComponentStatus.FAILED:
        return CognitionTraceStageStatus.FAILED
    return CognitionTraceStageStatus.SKIPPED


def _missing_stage(
    stage_kind: CognitionTraceStageKind,
    *,
    ordinal: int,
    llm_meta: CognitionTraceLlmMeta | None,
) -> CognitionTraceStageSummary:
    return CognitionTraceStageSummary(
        stage_kind=stage_kind,
        status=CognitionTraceStageStatus.SKIPPED,
        ordinal=ordinal,
        reason_code=_STAGE_MISSING_REASON,
        llm_meta=llm_meta,
    )


def _reject_authority_artifact(value: object, *, field: str) -> None:
    if type(value) is Observation:
        _LOG.error(
            "cognition_trace_authority_artifact",
            extra={"reason_code": "authority_artifact", "field": field},
        )
        raise CognitionTraceValidationError(
            "authority_artifact",
            f"trace projection must not embed Observation in {field}",
        )
    type_name = type(value).__name__
    if type_name in {"WorldState", "WorldEvent", "ObservationBatch"}:
        _LOG.error(
            "cognition_trace_authority_artifact",
            extra={
                "reason_code": "authority_artifact",
                "field": field,
                "type_name": type_name,
            },
        )
        raise CognitionTraceValidationError(
            "authority_artifact",
            f"trace projection must not embed {type_name} in {field}",
        )


def _project_observation(
    record: ComponentBoundaryRecord | None,
    *,
    ordinal: int,
    llm_meta: CognitionTraceLlmMeta | None,
) -> CognitionTraceStageSummary:
    if record is None:
        return _missing_stage(
            CognitionTraceStageKind.OBSERVATION, ordinal=ordinal, llm_meta=llm_meta
        )
    # Boundary records may carry Observation as typed input; summaries never embed it.
    output = record.output_artifact
    if output is not None:
        _reject_authority_artifact(output, field="perception.output")
    codes: tuple[str, ...] = ()
    counts: dict[str, int] = {}
    confidence = record.confidence
    if type(output) is InterpretedPerception:
        codes = tuple(code.value for code in output.claim_codes)
        confidence = output.confidence
        for key, value in output.counts.items():
            if key in {
                "communications",
                "visible_bodies",
                "items",
                "resources",
                "exits",
                "occurrences",
            }:
                mapped = {
                    "communications": CognitionTraceCountKey.COMMUNICATION_COUNT,
                    "visible_bodies": CognitionTraceCountKey.VISIBLE_BODY_COUNT,
                    "items": CognitionTraceCountKey.ITEM_COUNT,
                    "resources": CognitionTraceCountKey.RESOURCE_COUNT,
                }.get(key)
                if mapped is not None:
                    counts[mapped.value] = int(value)
        counts[CognitionTraceCountKey.CLAIM_COUNT.value] = len(output.claim_codes)
    return CognitionTraceStageSummary(
        stage_kind=CognitionTraceStageKind.OBSERVATION,
        status=_status_from_component(record.status),
        ordinal=ordinal,
        confidence=confidence,
        selection_codes=codes,
        counts=counts or None,
        decision_metadata=record.decision_metadata,
        reason_code=(
            None if record.failure_reason is None else record.failure_reason.value
        ),
        llm_meta=llm_meta,
    )


def _memory_context_from_record(
    record: ComponentBoundaryRecord | None,
) -> RetrievedMemoryContext | None:
    if record is None:
        return None
    output = record.output_artifact
    if type(output) is RetrievedMemoryContext:
        return output
    return None


def _project_retrieved_memories(
    record: ComponentBoundaryRecord | None,
    *,
    ordinal: int,
    llm_meta: CognitionTraceLlmMeta | None,
) -> CognitionTraceStageSummary:
    if record is None:
        return _missing_stage(
            CognitionTraceStageKind.RETRIEVED_MEMORIES,
            ordinal=ordinal,
            llm_meta=llm_meta,
        )
    context = _memory_context_from_record(record)
    refs: list[CognitionTraceIdRef] = []
    counts: dict[str, int] = {}
    confidence = record.confidence
    if context is not None:
        confidence = context.confidence
        for memory_id in context.memory_ids:
            refs.append(
                CognitionTraceIdRef(
                    kind=CognitionTraceRefKind.MEMORY, value=memory_id.value
                )
            )
        for belief_id in context.belief_ids:
            refs.append(
                CognitionTraceIdRef(
                    kind=CognitionTraceRefKind.BELIEF, value=belief_id.value
                )
            )
        counts[CognitionTraceCountKey.MEMORY_HIT_COUNT.value] = len(context.ranked_hits)
        counts[CognitionTraceCountKey.REFERENCE_EPISODE_COUNT.value] = len(
            context.reference_episodes
        )
        counts[CognitionTraceCountKey.CANDIDATE_COUNT.value] = context.candidate_count
    return CognitionTraceStageSummary(
        stage_kind=CognitionTraceStageKind.RETRIEVED_MEMORIES,
        status=_status_from_component(record.status),
        ordinal=ordinal,
        confidence=confidence,
        id_refs=tuple(refs),
        counts=counts or None,
        decision_metadata=record.decision_metadata,
        reason_code=(
            None if record.failure_reason is None else record.failure_reason.value
        ),
        llm_meta=llm_meta,
    )


def _project_reconstructed_memories(
    record: ComponentBoundaryRecord | None,
    *,
    ordinal: int,
    llm_meta: CognitionTraceLlmMeta | None,
) -> CognitionTraceStageSummary:
    if record is None:
        return _missing_stage(
            CognitionTraceStageKind.RECONSTRUCTED_MEMORIES,
            ordinal=ordinal,
            llm_meta=llm_meta,
        )
    context = _memory_context_from_record(record)
    refs: list[CognitionTraceIdRef] = []
    counts: dict[str, int] = {}
    confidence = record.confidence
    if context is not None:
        confidence = context.confidence
        for reconstruction in context.reconstructions:
            refs.append(
                CognitionTraceIdRef(
                    kind=CognitionTraceRefKind.MEMORY,
                    value=reconstruction.reconstruction_id.value,
                )
            )
        counts[CognitionTraceCountKey.RECONSTRUCTION_COUNT.value] = len(
            context.reconstructions
        )
        if context.reconstruction_policy_version is not None:
            # Keep policy id as selection code (stable identifier, not narrative).
            pass
    return CognitionTraceStageSummary(
        stage_kind=CognitionTraceStageKind.RECONSTRUCTED_MEMORIES,
        status=_status_from_component(record.status),
        ordinal=ordinal,
        confidence=confidence,
        id_refs=tuple(refs),
        counts=counts or None,
        decision_metadata=record.decision_metadata,
        reason_code=(
            None if record.failure_reason is None else record.failure_reason.value
        ),
        llm_meta=llm_meta,
    )


def _project_situation(
    record: ComponentBoundaryRecord | None,
    *,
    ordinal: int,
    llm_meta: CognitionTraceLlmMeta | None,
) -> CognitionTraceStageSummary:
    if record is None:
        return _missing_stage(
            CognitionTraceStageKind.SITUATION_MODEL, ordinal=ordinal, llm_meta=llm_meta
        )
    output = record.output_artifact
    codes: tuple[str, ...] = ()
    confidence = record.confidence
    counts: dict[str, int] = {}
    if type(output) is SituationModel:
        codes = tuple(code.value for code in output.claim_codes)
        confidence = output.confidence
        counts[CognitionTraceCountKey.CLAIM_COUNT.value] = len(output.claim_codes)
    return CognitionTraceStageSummary(
        stage_kind=CognitionTraceStageKind.SITUATION_MODEL,
        status=_status_from_component(record.status),
        ordinal=ordinal,
        confidence=confidence,
        selection_codes=codes,
        counts=counts or None,
        decision_metadata=record.decision_metadata,
        reason_code=(
            None if record.failure_reason is None else record.failure_reason.value
        ),
        llm_meta=llm_meta,
    )


def _project_beliefs(
    *,
    snap: SubjectiveSnapshot | None,
    self_record: ComponentBoundaryRecord | None,
    ordinal: int,
    llm_meta: CognitionTraceLlmMeta | None,
) -> CognitionTraceStageSummary:
    refs: list[CognitionTraceIdRef] = []
    counts: dict[str, int] = {}
    confidence: float | None = None
    decision = None
    status = CognitionTraceStageStatus.COMPLETED

    if self_record is not None:
        status = _status_from_component(self_record.status)
        confidence = self_record.confidence
        decision = self_record.decision_metadata
        output = self_record.output_artifact
        if type(output) is SelfModel:
            for belief in output.beliefs:
                refs.append(
                    CognitionTraceIdRef(
                        kind=CognitionTraceRefKind.SEMANTIC_BELIEF,
                        value=belief.belief_id.value,
                    )
                )
            confidence = output.confidence
            counts[CognitionTraceCountKey.SEMANTIC_BELIEF_COUNT.value] = len(
                output.beliefs
            )
            counts[CognitionTraceCountKey.CANDIDATE_COUNT.value] = (
                output.candidate_count
            )
        elif type(output) is SelfBeliefState:
            for belief_id in output.belief_ids:
                refs.append(
                    CognitionTraceIdRef(
                        kind=CognitionTraceRefKind.BELIEF, value=belief_id.value
                    )
                )
            confidence = output.confidence
            counts[CognitionTraceCountKey.BELIEF_COUNT.value] = len(output.belief_ids)

    if snap is not None:
        if not refs:
            for belief in snap.legacy_beliefs:
                refs.append(
                    CognitionTraceIdRef(
                        kind=CognitionTraceRefKind.BELIEF,
                        value=belief.belief_id.value,
                    )
                )
            for belief in snap.semantic_beliefs:
                refs.append(
                    CognitionTraceIdRef(
                        kind=CognitionTraceRefKind.SEMANTIC_BELIEF,
                        value=belief.belief_id.value,
                    )
                )
        counts.setdefault(
            CognitionTraceCountKey.BELIEF_COUNT.value, len(snap.legacy_beliefs)
        )
        counts.setdefault(
            CognitionTraceCountKey.SEMANTIC_BELIEF_COUNT.value,
            len(snap.semantic_beliefs),
        )

    if snap is None and self_record is None:
        status = CognitionTraceStageStatus.SKIPPED
        return CognitionTraceStageSummary(
            stage_kind=CognitionTraceStageKind.BELIEFS,
            status=status,
            ordinal=ordinal,
            reason_code=_STAGE_MISSING_REASON,
            llm_meta=llm_meta,
        )

    return CognitionTraceStageSummary(
        stage_kind=CognitionTraceStageKind.BELIEFS,
        status=status,
        ordinal=ordinal,
        confidence=confidence,
        id_refs=tuple(refs),
        counts=counts or None,
        decision_metadata=decision,
        llm_meta=llm_meta,
    )


def _mean_emotional_salience(context: RetrievedMemoryContext | None) -> float | None:
    if context is None:
        return None
    values: list[float] = []
    for hit in context.ranked_hits:
        values.append(hit.trace.emotional_salience)
    for reconstruction in context.reconstructions:
        values.append(reconstruction.emotional_salience)
    for episode in context.reference_episodes:
        values.append(episode.emotional_salience)
    if not values:
        return None
    return sum(values) / len(values)


def _band_from_unit(value: float) -> UncertaintyBand:
    if value < 0.34:
        return UncertaintyBand.LOW
    if value < 0.67:
        return UncertaintyBand.MEDIUM
    return UncertaintyBand.HIGH


def _project_emotional_state(
    *,
    emotion_record: ComponentBoundaryRecord | None = None,
    motivation_record: ComponentBoundaryRecord | None,
    memory_record: ComponentBoundaryRecord | None,
    snap: SubjectiveSnapshot | None,
    ordinal: int,
    llm_meta: CognitionTraceLlmMeta | None,
) -> CognitionTraceStageSummary:
    refs: list[CognitionTraceIdRef] = []
    counts: dict[str, int] = {}
    confidence: float | None = None
    codes: list[str] = []
    band: UncertaintyBand | None = None
    decision = None

    # Prefer live EMOTIONAL_STATE stage intensities + driver codes.
    if (
        emotion_record is not None
        and type(emotion_record.output_artifact) is EmotionalStateEvaluation
    ):
        evaluation = emotion_record.output_artifact
        confidence = evaluation.confidence
        decision = emotion_record.decision_metadata
        state = evaluation.state
        if not state.is_neutral():
            band = intensity_band(state.max_intensity())
            for entry in state.intensities:
                if entry.intensity <= 0.0:
                    continue
                refs.append(
                    CognitionTraceIdRef(
                        kind=CognitionTraceRefKind.EMOTION,
                        value=entry.kind.value,
                    )
                )
            counts[CognitionTraceCountKey.EMOTION_KIND_COUNT.value] = len(refs)
        for driver in evaluation.driver_codes:
            codes.append(driver.value)
        if emotion_record.decision_metadata.selection_codes:
            for code in emotion_record.decision_metadata.selection_codes:
                if code not in codes:
                    codes.append(code)
        return CognitionTraceStageSummary(
            stage_kind=CognitionTraceStageKind.EMOTIONAL_STATE,
            status=CognitionTraceStageStatus.COMPLETED,
            ordinal=ordinal,
            confidence=confidence,
            uncertainty_band=band,
            selection_codes=tuple(codes),
            id_refs=tuple(refs),
            counts=counts or None,
            decision_metadata=decision,
            llm_meta=llm_meta,
        )

    motivation = None
    if motivation_record is not None and type(motivation_record.output_artifact) is (
        MotivationEvaluation
    ):
        motivation = motivation_record.output_artifact
        confidence = motivation.confidence
        decision = motivation_record.decision_metadata
        for drive in motivation.active_drive_kinds:
            refs.append(
                CognitionTraceIdRef(kind=CognitionTraceRefKind.DRIVE, value=drive.value)
            )
            codes.append(drive.value)
        counts[CognitionTraceCountKey.DRIVE_COUNT.value] = len(
            motivation.active_drive_kinds
        )

    if snap is not None and snap.drives is not None and not refs:
        for disposition in snap.drives.dispositions:
            refs.append(
                CognitionTraceIdRef(
                    kind=CognitionTraceRefKind.DRIVE, value=disposition.kind.value
                )
            )
        counts[CognitionTraceCountKey.DRIVE_COUNT.value] = len(snap.drives.dispositions)

    salience = _mean_emotional_salience(_memory_context_from_record(memory_record))
    if salience is not None:
        band = _band_from_unit(salience)
        if confidence is None:
            confidence = salience

    if (
        motivation_record is None
        and memory_record is None
        and (snap is None or snap.drives is None)
    ):
        return CognitionTraceStageSummary(
            stage_kind=CognitionTraceStageKind.EMOTIONAL_STATE,
            status=CognitionTraceStageStatus.SKIPPED,
            ordinal=ordinal,
            reason_code=_STAGE_MISSING_REASON,
            llm_meta=llm_meta,
        )

    return CognitionTraceStageSummary(
        stage_kind=CognitionTraceStageKind.EMOTIONAL_STATE,
        status=CognitionTraceStageStatus.COMPLETED,
        ordinal=ordinal,
        confidence=confidence,
        uncertainty_band=band,
        selection_codes=tuple(codes),
        id_refs=tuple(refs),
        counts=counts or None,
        decision_metadata=decision,
        llm_meta=llm_meta,
    )


def _project_goals(
    *,
    snap: SubjectiveSnapshot | None,
    goal_record: ComponentBoundaryRecord | None,
    motivation_record: ComponentBoundaryRecord | None,
    self_record: ComponentBoundaryRecord | None,
    ordinal: int,
    llm_meta: CognitionTraceLlmMeta | None,
) -> CognitionTraceStageSummary:
    refs: list[CognitionTraceIdRef] = []
    counts: dict[str, int] = {}
    confidence: float | None = None
    decision = None

    if goal_record is not None and type(goal_record.output_artifact) is GoalBoard:
        board = goal_record.output_artifact
        confidence = board.confidence
        decision = goal_record.decision_metadata
        status_hist: dict[GoalStatus, int] = {}
        horizon_hist: dict[GoalHorizon, int] = {}
        for goal in board.goals:
            status_hist[goal.status] = status_hist.get(goal.status, 0) + 1
            horizon_hist[goal.horizon] = horizon_hist.get(goal.horizon, 0) + 1
        for focus_id in board.foci_ids:
            refs.append(
                CognitionTraceIdRef(
                    kind=CognitionTraceRefKind.GOAL, value=focus_id.value
                )
            )
        if not refs:
            for goal in board.goals:
                if goal.status is GoalStatus.ACTIVE:
                    refs.append(
                        CognitionTraceIdRef(
                            kind=CognitionTraceRefKind.GOAL, value=goal.goal_id.value
                        )
                    )
        counts[CognitionTraceCountKey.GOAL_COUNT.value] = len(board.goals)
        counts[CognitionTraceCountKey.GOAL_FOCI_COUNT.value] = len(board.foci_ids)
        _STATUS_COUNT_KEYS = {
            GoalStatus.ACTIVE: CognitionTraceCountKey.GOAL_STATUS_ACTIVE,
            GoalStatus.COMPLETED: CognitionTraceCountKey.GOAL_STATUS_COMPLETED,
            GoalStatus.FAILED: CognitionTraceCountKey.GOAL_STATUS_FAILED,
            GoalStatus.ABANDONED: CognitionTraceCountKey.GOAL_STATUS_ABANDONED,
            GoalStatus.SUSPENDED: CognitionTraceCountKey.GOAL_STATUS_SUSPENDED,
        }
        _HORIZON_COUNT_KEYS = {
            GoalHorizon.DESIRE: CognitionTraceCountKey.GOAL_HORIZON_DESIRE,
            GoalHorizon.LONG_TERM: CognitionTraceCountKey.GOAL_HORIZON_LONG_TERM,
            GoalHorizon.MEDIUM_TERM: CognitionTraceCountKey.GOAL_HORIZON_MEDIUM_TERM,
            GoalHorizon.SUBGOAL: CognitionTraceCountKey.GOAL_HORIZON_SUBGOAL,
            GoalHorizon.CURRENT_INTENTION: (
                CognitionTraceCountKey.GOAL_HORIZON_CURRENT_INTENTION
            ),
        }
        for status, key in _STATUS_COUNT_KEYS.items():
            counts[key.value] = status_hist.get(status, 0)
        for horizon, key in _HORIZON_COUNT_KEYS.items():
            counts[key.value] = horizon_hist.get(horizon, 0)
        return CognitionTraceStageSummary(
            stage_kind=CognitionTraceStageKind.GOALS,
            status=CognitionTraceStageStatus.COMPLETED,
            ordinal=ordinal,
            confidence=confidence,
            id_refs=tuple(refs),
            counts=counts or None,
            decision_metadata=decision,
            llm_meta=llm_meta,
        )

    if motivation_record is not None and type(motivation_record.output_artifact) is (
        MotivationEvaluation
    ):
        motivation = motivation_record.output_artifact
        confidence = motivation.confidence
        decision = motivation_record.decision_metadata
        for goal_id in motivation.active_goal_ids:
            refs.append(
                CognitionTraceIdRef(
                    kind=CognitionTraceRefKind.GOAL, value=goal_id.value
                )
            )
        counts[CognitionTraceCountKey.GOAL_COUNT.value] = len(
            motivation.active_goal_ids
        )

    if self_record is not None and not refs:
        output = self_record.output_artifact
        if type(output) is SelfModel:
            for goal_id in output.goal_ids:
                refs.append(
                    CognitionTraceIdRef(
                        kind=CognitionTraceRefKind.GOAL, value=goal_id.value
                    )
                )
            confidence = output.confidence
            counts[CognitionTraceCountKey.GOAL_COUNT.value] = len(output.goal_ids)
        elif type(output) is SelfBeliefState:
            for goal_id in output.goal_ids:
                refs.append(
                    CognitionTraceIdRef(
                        kind=CognitionTraceRefKind.GOAL, value=goal_id.value
                    )
                )
            confidence = output.confidence
            counts[CognitionTraceCountKey.GOAL_COUNT.value] = len(output.goal_ids)

    if snap is not None and not refs:
        active = [goal for goal in snap.goals if goal.status is GoalStatus.ACTIVE]
        for goal in active:
            refs.append(
                CognitionTraceIdRef(
                    kind=CognitionTraceRefKind.GOAL, value=goal.goal_id.value
                )
            )
        counts[CognitionTraceCountKey.GOAL_COUNT.value] = len(active)

    if (
        not refs
        and snap is None
        and motivation_record is None
        and self_record is None
        and goal_record is None
    ):
        return CognitionTraceStageSummary(
            stage_kind=CognitionTraceStageKind.GOALS,
            status=CognitionTraceStageStatus.SKIPPED,
            ordinal=ordinal,
            reason_code=_STAGE_MISSING_REASON,
            llm_meta=llm_meta,
        )

    return CognitionTraceStageSummary(
        stage_kind=CognitionTraceStageKind.GOALS,
        status=CognitionTraceStageStatus.COMPLETED,
        ordinal=ordinal,
        confidence=confidence,
        id_refs=tuple(refs),
        counts=counts or None,
        decision_metadata=decision,
        llm_meta=llm_meta,
    )


def _project_futures(
    record: ComponentBoundaryRecord | None,
    *,
    ordinal: int,
    llm_meta: CognitionTraceLlmMeta | None,
) -> CognitionTraceStageSummary:
    if record is None:
        return _missing_stage(
            CognitionTraceStageKind.IMAGINED_FUTURES,
            ordinal=ordinal,
            llm_meta=llm_meta,
        )
    output = record.output_artifact
    refs: list[CognitionTraceIdRef] = []
    counts: dict[str, int] = {}
    confidence = record.confidence
    if type(output) is PossibleFutures:
        confidence = output.confidence
        for future in output.futures:
            refs.append(
                CognitionTraceIdRef(
                    kind=CognitionTraceRefKind.FUTURE, value=future.future_id
                )
            )
        counts[CognitionTraceCountKey.FUTURE_COUNT.value] = len(output.futures)
    return CognitionTraceStageSummary(
        stage_kind=CognitionTraceStageKind.IMAGINED_FUTURES,
        status=_status_from_component(record.status),
        ordinal=ordinal,
        confidence=confidence,
        id_refs=tuple(refs),
        counts=counts or None,
        decision_metadata=record.decision_metadata,
        reason_code=(
            None if record.failure_reason is None else record.failure_reason.value
        ),
        llm_meta=llm_meta,
    )


def _project_intention(
    record: ComponentBoundaryRecord | None,
    *,
    ordinal: int,
    llm_meta: CognitionTraceLlmMeta | None,
) -> CognitionTraceStageSummary:
    if record is None:
        return _missing_stage(
            CognitionTraceStageKind.SELECTED_INTENTION,
            ordinal=ordinal,
            llm_meta=llm_meta,
        )
    output = record.output_artifact
    intention_code = None
    confidence = record.confidence
    refs: list[CognitionTraceIdRef] = []
    if type(output) is SelectedIntention:
        intention_code = output.intention.value
        confidence = output.confidence
        refs.append(
            CognitionTraceIdRef(
                kind=CognitionTraceRefKind.INTENTION, value=output.intention.value
            )
        )
        if output.source_motive is not None:
            refs.append(
                CognitionTraceIdRef(
                    kind=CognitionTraceRefKind.MOTIVE,
                    value=output.source_motive.value,
                )
            )
    return CognitionTraceStageSummary(
        stage_kind=CognitionTraceStageKind.SELECTED_INTENTION,
        status=_status_from_component(record.status),
        ordinal=ordinal,
        confidence=confidence,
        id_refs=tuple(refs),
        intention_code=intention_code,
        decision_metadata=record.decision_metadata,
        reason_code=(
            None if record.failure_reason is None else record.failure_reason.value
        ),
        llm_meta=llm_meta,
    )


def _command_kind(command: object) -> str:
    kind = getattr(command, "kind", None)
    if type(kind) is str and kind:
        return kind
    return type(command).__name__.lower()


def _project_planned_action(
    record: ComponentBoundaryRecord | None,
    *,
    loop_result: CognitiveLoopResult | None,
    ordinal: int,
    llm_meta: CognitionTraceLlmMeta | None,
) -> CognitionTraceStageSummary:
    if record is None and loop_result is None:
        return _missing_stage(
            CognitionTraceStageKind.PLANNED_ACTION, ordinal=ordinal, llm_meta=llm_meta
        )
    command_kind = None
    confidence: float | None = None
    decision = None
    status = CognitionTraceStageStatus.COMPLETED
    reason = None
    refs: list[CognitionTraceIdRef] = []

    if record is not None:
        status = _status_from_component(record.status)
        confidence = record.confidence
        decision = record.decision_metadata
        reason = None if record.failure_reason is None else record.failure_reason.value
        output = record.output_artifact
        if type(output) is ActionPlan:
            command_kind = _command_kind(output.command)
            confidence = output.confidence
            decision = output.decision_metadata
    if command_kind is None and loop_result is not None:
        command_kind = _command_kind(loop_result.command)
        if confidence is None:
            confidence = loop_result.final_confidence
    if command_kind is not None:
        refs.append(
            CognitionTraceIdRef(kind=CognitionTraceRefKind.COMMAND, value=command_kind)
        )

    return CognitionTraceStageSummary(
        stage_kind=CognitionTraceStageKind.PLANNED_ACTION,
        status=status,
        ordinal=ordinal,
        confidence=confidence,
        id_refs=tuple(refs),
        command_kind=command_kind,
        decision_metadata=decision,
        reason_code=reason,
        llm_meta=llm_meta,
    )


def stage_summaries_content_hash(
    stages: Sequence[CognitionTraceStageSummary],
) -> str:
    """Deterministic SHA-256 hex digest over canonical stage summary bytes."""
    payload = [_stage_summary_canonical(stage) for stage in stages]
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    digest = hashlib.sha256(encoded).hexdigest()
    _LOG.debug(
        "cognition_trace_stage_hash",
        extra={"stage_count": len(stages), "hash_prefix": digest[:12]},
    )
    return digest


def _stage_summary_canonical(stage: CognitionTraceStageSummary) -> dict[str, object]:
    counts = None if stage.counts is None else dict(sorted(stage.counts.items()))
    decision = None
    if stage.decision_metadata is not None:
        decision = {
            "selection_codes": list(stage.decision_metadata.selection_codes),
            "candidate_count": stage.decision_metadata.candidate_count,
            "tie_break_applied": stage.decision_metadata.tie_break_applied,
        }
    llm = None
    if stage.llm_meta is not None:
        llm = {
            "provider_name": stage.llm_meta.provider_name,
            "model_name": stage.llm_meta.model_name,
            "finish_reason": stage.llm_meta.finish_reason,
            "input_tokens": stage.llm_meta.input_tokens,
            "output_tokens": stage.llm_meta.output_tokens,
            "total_tokens": stage.llm_meta.total_tokens,
            "attempts": stage.llm_meta.attempts,
        }
    return {
        "schema_version": stage.schema_version,
        "stage_kind": stage.stage_kind.value,
        "status": stage.status.value,
        "ordinal": stage.ordinal,
        "confidence": stage.confidence,
        "uncertainty_band": (
            None if stage.uncertainty_band is None else stage.uncertainty_band.value
        ),
        "selection_codes": list(stage.selection_codes),
        "id_refs": [
            {"kind": ref.kind.value, "value": ref.value} for ref in stage.id_refs
        ],
        "counts": counts,
        "reason_code": stage.reason_code,
        "decision_metadata": decision,
        "command_kind": stage.command_kind,
        "intention_code": stage.intention_code,
        "llm_meta": llm,
    }


def _require_selection_codes(value: object) -> tuple[str, ...]:
    if isinstance(value, (set, frozenset, Mapping)):
        raise TypeError("selection_codes must be ordered")
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise TypeError("selection_codes must be ordered")
    codes = tuple(value)
    if len(codes) > _MAX_SELECTION_CODES:
        raise CognitionTraceValidationError(
            "selection_codes_too_long",
            "selection_codes exceeds maximum length",
        )
    normalized: list[str] = []
    seen: set[str] = set()
    for code in codes:
        text = require_stable_id("selection_codes", code)
        if text in seen:
            raise CognitionTraceValidationError(
                "selection_codes_duplicate",
                "selection_codes must be unique",
            )
        seen.add(text)
        normalized.append(text)
    return tuple(normalized)


def _require_id_refs(value: object) -> tuple[CognitionTraceIdRef, ...]:
    if isinstance(value, (set, frozenset, Mapping)):
        raise TypeError("id_refs must be ordered")
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise TypeError("id_refs must be ordered")
    refs = tuple(value)
    if len(refs) > _MAX_ID_REFS:
        raise CognitionTraceValidationError(
            "id_refs_too_long",
            "id_refs exceeds maximum length",
        )
    seen: set[tuple[str, str]] = set()
    for ref in refs:
        if type(ref) is not CognitionTraceIdRef:
            raise TypeError("id_refs entries must be CognitionTraceIdRef")
        key = (ref.kind.value, ref.value)
        if key in seen:
            raise CognitionTraceValidationError(
                "id_refs_duplicate",
                "id_refs must be unique by kind+value",
            )
        seen.add(key)
    return refs


def _require_counts(value: object) -> Mapping[str, int] | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise TypeError("counts must be a mapping or None")
    if len(value) > _MAX_COUNT_ENTRIES:
        raise CognitionTraceValidationError(
            "counts_too_long",
            "counts exceeds maximum length",
        )
    normalized: dict[str, int] = {}
    for key, raw in value.items():
        if type(key) is not str:
            raise TypeError("counts keys must be str")
        try:
            count_key = CognitionTraceCountKey(key)
        except ValueError as exc:
            raise CognitionTraceValidationError(
                "invalid_count_key",
                f"unsupported count key {key!r}",
            ) from exc
        count = require_exact_nonneg_int(f"counts[{count_key.value}]", raw)
        normalized[count_key.value] = count
    return dict(sorted(normalized.items()))
