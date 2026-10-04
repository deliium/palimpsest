"""Strict Pydantic request/response schemas for the research API.

Schemas never embed live engines, private world state, seeds as free text,
or subjective narrative payloads on public surfaces.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

STREAM_ENVELOPE_VERSION: Literal["stream-envelope-v1"] = "stream-envelope-v1"
MAX_CONFIG_BYTES: int = 1_048_576


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class LifecycleStateOut(StrEnum):
    CONFIGURED = "configured"
    READY = "ready"
    PAUSED = "paused"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    COMPLETED = "completed"
    FAILED = "failed"
    FENCED = "fenced"
    RECOVERY_REQUIRED = "recovery-required"
    INTERRUPTED = "interrupted"


class ConfigAvailabilityOut(StrEnum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


class CreateSimulationRequest(StrictModel):
    run_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._-]+$")
    # Default stays v2 for existing clients; v1/v2/v3 payloads are all accepted.
    # Decode happens at runner construction (not at create).
    config_schema_version: str = Field(
        default="runner-config-v2", min_length=1, max_length=64
    )
    config_fingerprint: str = Field(
        min_length=64, max_length=64, pattern=r"^[a-f0-9]+$"
    )
    config_payload_b64: str = Field(min_length=1, max_length=2_000_000)


class ConfigureSimulationRequest(StrictModel):
    config_schema_version: str = Field(min_length=1, max_length=64)
    config_fingerprint: str = Field(
        min_length=64, max_length=64, pattern=r"^[a-f0-9]+$"
    )
    config_payload_b64: str = Field(min_length=1, max_length=2_000_000)
    expected_version: int = Field(ge=0)


class IdempotencyHeaderModel(StrictModel):
    """Marker type documenting idempotency-key expectations."""

    idempotency_key: str = Field(min_length=1, max_length=128)


class RunControlStatusOut(StrictModel):
    run_id: str
    lifecycle_state: LifecycleStateOut
    lifecycle_version: int = Field(ge=0)
    config_availability: ConfigAvailabilityOut
    ticks_committed: int = Field(ge=0)
    progress_cursor: int = Field(ge=0)
    config_schema_version: str | None = None
    config_fingerprint: str | None = None
    has_lease: bool
    terminal_reason_code: str | None = None


class RunListOut(StrictModel):
    items: tuple[RunControlStatusOut, ...]
    next_cursor: str | None = None
    count: int = Field(ge=0)


class TickResultOut(StrictModel):
    run_id: str
    lifecycle_state: LifecycleStateOut
    ticks_committed: int = Field(ge=0)
    progress_cursor: int = Field(ge=0)
    stop_reason: str | None = None


class AvailabilityOut(StrEnum):
    AVAILABLE = "available"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"


class EventCursorIn(StrictModel):
    tick: int = Field(ge=0)
    sequence: int = Field(ge=0)


class EventSummaryOut(StrictModel):
    tick: int = Field(ge=0)
    sequence: int = Field(ge=0)
    kind: str = Field(min_length=1, max_length=128)


class EventPageOut(StrictModel):
    run_id: str
    limit: int = Field(ge=0)
    count: int = Field(ge=0)
    next_cursor: EventCursorIn | None = None
    availability: AvailabilityOut
    manifest_hash: str | None = None
    # Opaque event summaries: kind + tick + sequence only (no payloads).
    events: tuple[EventSummaryOut, ...] = ()


class ObjectiveWorldOut(StrictModel):
    run_id: str
    tick: int = Field(ge=0)
    revision: int = Field(ge=0)
    availability: AvailabilityOut
    body_count: int = Field(ge=0)
    location_count: int = Field(ge=0)


class AgentVisibleOut(StrictModel):
    run_id: str
    tick: int = Field(ge=0)
    agent_id: str
    entity_id: str
    surface: Literal["public"] = "public"
    availability: AvailabilityOut
    occurrence_count: int = Field(ge=0)
    communication_count: int = Field(ge=0)


class ExperimentalStateOut(StrictModel):
    """Metadata-only experiment membership (never condition values/seeds)."""

    run_id: str
    experiment_id: str | None = None
    membership_source: str | None = None
    has_assignment: bool = False
    availability: AvailabilityOut = AvailabilityOut.UNAVAILABLE


class SubjectivePageOut(StrictModel):
    run_id: str
    owner_id: str
    limit: int = Field(ge=0)
    item_count: int = Field(ge=0)
    next_cursor: str | None = None
    availability: AvailabilityOut
    surface: Literal["debug"] = "debug"
    content_available: bool = False
    kind: Literal["memories", "beliefs", "relationships"]


class TerritorialClaimHeadOut(StrictModel):
    owner_id: str
    target_kind: str
    target_entity_id: str
    strength: float


class SubjectiveClaimsOut(StrictModel):
    schema_version: Literal["subjective-claims-v1"] = "subjective-claims-v1"
    owner_id: str
    layer: Literal["subjective_claims"] = "subjective_claims"
    heads: tuple[TerritorialClaimHeadOut, ...] = ()


class GoalSummaryOut(StrictModel):
    goal_id: str
    status: str
    horizon: str
    priority: float
    confidence: float | None = None
    created_tick: int = Field(ge=0)
    parent_goal_id: str | None = None
    dependency_count: int = Field(ge=0)


class GoalsProjectionOut(StrictModel):
    schema_version: Literal["research-goals-v1"] = "research-goals-v1"
    owner_id: str
    availability: AvailabilityOut
    head_count: int = Field(ge=0)
    items: tuple[GoalSummaryOut, ...] = ()


class EmotionIntensityOut(StrictModel):
    kind: str
    intensity: float


class EmotionalStateProjectionOut(StrictModel):
    schema_version: Literal["research-emotional-state-v1"] = (
        "research-emotional-state-v1"
    )
    owner_id: str
    availability: AvailabilityOut
    tick: int | None = None
    last_update_tick: int | None = None
    policy_version: str | None = None
    head_count: int = Field(ge=0)
    intensities: tuple[EmotionIntensityOut, ...] = ()


class SelfModelProjectionOut(StrictModel):
    schema_version: Literal["research-self-model-v1"] = "research-self-model-v1"
    owner_id: str
    availability: AvailabilityOut
    identity_tick: int | None = None
    identity_operation_count: int = Field(ge=0)
    goal_count: int = Field(ge=0)
    goal_ids: tuple[str, ...] = ()
    note: str = ""


class LedgerItemSummaryOut(StrictModel):
    item_id: str
    kind_code: str
    status: str | None = None
    strength: float | None = None
    target_id: str | None = None
    evidence_count: int = Field(ge=0)


class TheoryOfMindProjectionOut(StrictModel):
    schema_version: Literal["research-theory-of-mind-v1"] = (
        "research-theory-of-mind-v1"
    )
    owner_id: str
    availability: AvailabilityOut
    head_count: int = Field(ge=0)
    items: tuple[LedgerItemSummaryOut, ...] = ()


class GroupFormationProjectionOut(StrictModel):
    schema_version: Literal["research-group-formation-v1"] = (
        "research-group-formation-v1"
    )
    owner_id: str
    availability: AvailabilityOut
    head_count: int = Field(ge=0)
    concept_count: int = Field(ge=0)
    items: tuple[LedgerItemSummaryOut, ...] = ()


class SocialNormsProjectionOut(StrictModel):
    schema_version: Literal["research-social-norms-v1"] = "research-social-norms-v1"
    owner_id: str
    availability: AvailabilityOut
    head_count: int = Field(ge=0)
    items: tuple[LedgerItemSummaryOut, ...] = ()


class SocialConventionsProjectionOut(StrictModel):
    schema_version: Literal["research-social-conventions-v1"] = (
        "research-social-conventions-v1"
    )
    owner_id: str
    availability: AvailabilityOut
    head_count: int = Field(ge=0)
    items: tuple[LedgerItemSummaryOut, ...] = ()


class CulturalNarrativesProjectionOut(StrictModel):
    schema_version: Literal["research-cultural-narratives-v1"] = (
        "research-cultural-narratives-v1"
    )
    owner_id: str
    availability: AvailabilityOut
    head_count: int = Field(ge=0)
    items: tuple[LedgerItemSummaryOut, ...] = ()


class GraphNodeSummaryOut(StrictModel):
    """Metadata-safe graph node (no proposition/utterance/prompt bodies)."""

    node_id: str
    created_tick: int = Field(ge=0)
    source_kind: str | None = None
    strength: float | None = None
    target_id: str | None = None
    lineage_ref_ids: tuple[str, ...] = ()


class SubjectiveGraphSummaryOut(StrictModel):
    run_id: str
    owner_id: str
    kind: Literal["memories", "beliefs"]
    availability: AvailabilityOut
    limit: int = Field(ge=0)
    count: int = Field(ge=0)
    next_cursor: str | None = None
    items: tuple[GraphNodeSummaryOut, ...] = ()
    surface: Literal["debug"] = "debug"


class MetricCatalogItemOut(StrictModel):
    metric_set_id: str
    metric_family: str
    evidence_manifest_hash: str
    schema_version: str
    content_hash_prefix: str = Field(min_length=1, max_length=16)


class MetricCatalogOut(StrictModel):
    run_id: str
    items: tuple[MetricCatalogItemOut, ...]
    count: int = Field(ge=0)
    availability: AvailabilityOut


class MetricDocumentOut(StrictModel):
    """Opaque metric document metadata + base64 payload for research clients."""

    run_id: str
    metric_set_id: str
    metric_family: str
    evidence_manifest_hash: str
    schema_version: str
    content_hash: str
    payload_b64: str
    availability: AvailabilityOut = AvailabilityOut.AVAILABLE


class ReplayRequest(StrictModel):
    to_tick: int = Field(ge=0)
    agent_id: str | None = Field(default=None, max_length=128)


class ReplayResultOut(StrictModel):
    run_id: str
    status: str
    availability: AvailabilityOut
    ticks_replayed: int = Field(ge=0)
    objective: ObjectiveWorldOut | None = None
    agent_visible: AgentVisibleOut | None = None
    reason_code: str | None = None


class StreamFrameKind(StrEnum):
    STATUS = "status"
    EVENTLESS_TICK = "eventless_tick"
    EVENT = "event"
    METRIC = "metric"
    RESULT = "result"
    ERROR = "error"
    COMPLETION = "completion"
    HEARTBEAT = "heartbeat"


class StreamEnvelopeOut(StrictModel):
    """Versioned WebSocket frame. Body is opaque base64 — never logged."""

    envelope_version: Literal["stream-envelope-v1"] = STREAM_ENVELOPE_VERSION
    run_id: str
    cursor: int = Field(ge=0)
    kind: StreamFrameKind
    related_tick: int | None = Field(default=None, ge=0)
    content_hash_prefix: str | None = Field(default=None, max_length=16)
    payload_b64: str | None = None
    high_water: int | None = Field(default=None, ge=0)


class StreamSubscribeIn(StrictModel):
    after_cursor: int = Field(default=0, ge=0)

    @field_validator("after_cursor")
    @classmethod
    def non_negative(cls, value: int) -> int:
        if value < 0:
            raise ValueError("after_cursor must be >= 0")
        return value


class DebuggerAvailabilityOut(StrEnum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    NOT_APPLICABLE = "not_applicable"


class DebuggerNodeStatusOut(StrEnum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    SKIPPED = "skipped"
    FAILED = "failed"
    TRUNCATED = "truncated"


class DebuggerFocusOut(StrictModel):
    """Wire ``observer_focus`` handle for observer seek/focus."""

    run_id: str
    tick: int = Field(ge=0)
    sequence: int | None = Field(default=None, ge=0)
    event_id: str | None = None


class CausalTraceNodeOut(StrictModel):
    stage_code: str
    status: DebuggerNodeStatusOut
    reason_code: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    uncertainty_band: str | None = None
    selection_codes: tuple[str, ...] = ()
    id_refs: tuple[tuple[str, str], ...] = ()
    counts: dict[str, int] | None = None
    command_kind: str | None = None
    intention_code: str | None = None
    observer_focus: tuple[DebuggerFocusOut, ...] = ()
    secondary: bool = False


class DebuggerAddressOut(StrictModel):
    run_id: str
    tick: int = Field(ge=0)
    event_id: str | None = None
    sequence: int | None = Field(default=None, ge=0)
    agent_id: str | None = None


class CausalTraceOut(StrictModel):
    """Read-only observational causal chain (non-mutating)."""

    address: DebuggerAddressOut
    availability: DebuggerAvailabilityOut
    nodes: tuple[CausalTraceNodeOut, ...]
    invocation_id: str | None = None
    ambiguity: bool = False
    reason_code: str | None = None
    command_kind: str | None = None
    supporting_nodes: tuple[CausalTraceNodeOut, ...] = ()


class DebuggerInvocationSummaryOut(StrictModel):
    invocation_id: str
    agent_id: str
    tick: int = Field(ge=0)
    command_kind: str | None = None
    content_hash_prefix: str = Field(min_length=1, max_length=16)


class DebuggerInvocationPageOut(StrictModel):
    run_id: str
    agent_id: str
    tick: int | None = Field(default=None, ge=0)
    items: tuple[DebuggerInvocationSummaryOut, ...]
    count: int = Field(ge=0)
    availability: DebuggerAvailabilityOut


class DebuggerLineageEntryOut(StrictModel):
    entry_id: str
    kind: str
    related_ids: tuple[str, ...] = ()
    reason_codes: tuple[str, ...] = ()
    counts: dict[str, int] | None = None
    observer_focus: tuple[DebuggerFocusOut, ...] = ()
    parent_ids: tuple[str, ...] = ()
    status_code: str | None = None


class DebuggerLineageOut(StrictModel):
    run_id: str
    owner_id: str
    kind: str
    subject_id: str
    availability: DebuggerAvailabilityOut
    entries: tuple[DebuggerLineageEntryOut, ...] = ()
    reason_code: str | None = None


class BeliefPatchIn(StrictModel):
    owner_id: str = Field(min_length=1, max_length=128)
    belief_id: str = Field(min_length=1, max_length=128)
    subject_kind: Literal["agent", "entity", "self"]
    subject_id: str = Field(min_length=1, max_length=128)
    predicate: str = Field(min_length=1, max_length=128)
    value_kind: Literal["bool", "number", "text", "agent", "entity"]
    bool_value: bool | None = None
    number_value: float | None = None
    text_value: str | None = None
    agent_value: str | None = None
    entity_value: str | None = None


class CommunicationRemoveIn(StrictModel):
    event_id: str | None = Field(default=None, min_length=1, max_length=128)
    tick: int | None = Field(default=None, ge=0)
    sequence: int | None = Field(default=None, ge=0)


class CognitiveBudgetLimitsIn(StrictModel):
    max_llm_calls_per_tick: int = Field(ge=0)
    max_tokens_per_tick: int = Field(ge=0)
    max_imagination_branches: int = Field(ge=1)
    max_planning_depth: int = Field(ge=1)
    max_recalled_memories: int = Field(ge=1)
    max_tom_targets: int = Field(ge=0)
    reflection_interval_ticks: int = Field(ge=1)
    timeout_seconds: float = Field(gt=0)


class ResearchInterventionIn(StrictModel):
    kind: str = Field(min_length=1, max_length=64)
    agent_ids: tuple[str, ...] = ()
    memory_mode: str | None = None
    belief_patch: BeliefPatchIn | None = None
    communication_remove: CommunicationRemoveIn | None = None
    mortality_mode: str | None = None
    cognitive_budget_mode: str | None = None
    cognitive_budget_limits: CognitiveBudgetLimitsIn | None = None
    architecture_id: str | None = None
    alternate_stochastic_identity: str | None = None


class BranchCreateIn(StrictModel):
    fork_tick: int = Field(ge=0)
    intervention: ResearchInterventionIn


class BranchLineageOut(StrictModel):
    child_run_id: str
    parent_run_id: str
    fork_tick: int = Field(ge=0)
    intervention_kind: str
    intervention_fingerprint: str
    intervention_summary: str
    branch_id: str
    created_as_of_parent_head: int = Field(ge=0)


class BranchCreateOut(StrictModel):
    child_run_id: str
    branch_id: str
    lineage: BranchLineageOut
    idempotent_hit: bool
    run: RunControlStatusOut | None = None


class BranchListOut(StrictModel):
    items: tuple[BranchLineageOut, ...]
    next_cursor: str | None = None
    count: int = Field(ge=0)


class BranchForkPointOut(StrictModel):
    parent_run_id: str
    child_run_id: str
    fork_tick: int = Field(ge=0)
    parent_observer_tick: int = Field(ge=0)
    child_observer_tick: int = Field(ge=0)


class BranchStateOut(StrictModel):
    run_id: str
    parent_run_id: str | None = None
    fork_tick: int | None = None
    intervention_summary: str | None = None
    branch_id: str | None = None
    ticks_committed: int = Field(ge=0)
    progress_cursor: int = Field(ge=0)
    lifecycle_state: LifecycleStateOut | None = None


class BranchTimelineCompareIn(StrictModel):
    left_run_id: str = Field(min_length=1, max_length=128)
    right_run_id: str = Field(min_length=1, max_length=128)
    fork_tick: int | None = Field(default=None, ge=0)
    include_event_kind_counts: bool = False


class BranchTimelineCompareOut(StrictModel):
    left_run_id: str
    right_run_id: str
    fork_tick: int = Field(ge=0)
    prefix_equivalent: bool
    diverge_tick: int | None = None
    diverge_sequence: int | None = None
    reason_code: str | None = None
    left_post_fork_trajectory_hash: str | None = None
    right_post_fork_trajectory_hash: str | None = None
    event_kind_counts: dict[str, dict[str, int]] | None = None


def stable_jsonable(value: Any) -> Any:
    """Convert nested structures for JSON without leaking bytes."""
    if isinstance(value, bytes):
        return f"<bytes:{len(value)}>"
    return value
