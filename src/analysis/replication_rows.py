"""Neutral detached replication facts and output rows.

No cognition, world authority, or private ledger type is imported here.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ReplicationLayer(StrEnum):
    OBJECTIVE = "objective"
    OWNER_SCOPED = "owner_scoped"
    DETACHED_ANALYSIS = "detached_analysis"


class ReplicationCoverageKind(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    MISSING = "missing"


class ReplicationAvailability(StrEnum):
    AVAILABLE = "available"
    INSUFFICIENT_SAMPLES = "insufficient_samples"
    UNAVAILABLE = "unavailable"


class ReplicationEvidenceQualification(StrEnum):
    EXECUTION_BACKED = "execution_backed"
    DECLARED_ONLY = "declared_only"
    DUPLICATE_SOURCE = "duplicate_source"
    UNRESOLVED = "unresolved"
    UNAVAILABLE = "unavailable"


class ReplicationAppraisal(StrEnum):
    COMPATIBLE = "compatible"
    CONFLICTING = "conflicting"
    INCONCLUSIVE = "inconclusive"
    NOT_COMPARABLE = "not_comparable"


class ReplicationExcludedReason(StrEnum):
    SOURCE_MISSING = "source_missing"
    RESULT_MISSING = "result_missing"
    CONDITION_UNKNOWN = "condition_unknown"
    CONDITION_DIFFERENT = "condition_different"
    EXECUTION_AMBIGUOUS = "execution_ambiguous"
    REPORT_EXECUTION_MISMATCH = "report_execution_mismatch"
    RETENTION_CAP = "retention_cap"


@dataclass(frozen=True, slots=True)
class ReplicationSelectorFact:
    family: str
    kind: str
    binding_mode: str
    exact_entity_token: str | None = None


@dataclass(frozen=True, slots=True)
class ReplicationConditionFact:
    slot: str
    token: str


@dataclass(frozen=True, slots=True)
class ReplicationMeasurementFact:
    outcome: str | None
    resolution: str
    uncertainty_kind: str
    possible_outcomes: tuple[str, ...]
    basis: str


@dataclass(frozen=True, slots=True)
class ReplicationDesignFact:
    design_token: str
    source_design_digest: str
    origin_token: str
    parent_design_token: str | None
    source_hypothesis_token: str
    source_trial_token: str
    created_tick: int
    operator: str
    process_token: str
    operand_a_selector: ReplicationSelectorFact
    operand_b_selector: ReplicationSelectorFact | None
    predicted_outcome: str | None
    conditions: tuple[ReplicationConditionFact, ...] = ()


@dataclass(frozen=True, slots=True)
class ReplicationAttemptFact:
    attempt_token: str
    participant_token: str
    design_token: str
    source_trial_token: str
    collaboration_token: str | None
    hypothesis_token: str
    request_tick: int
    submission_tick: int | None
    observation_tick: int
    operand_a_token: str | None
    operand_b_token: str | None
    condition_snapshot: tuple[ReplicationConditionFact, ...]
    condition_comparison: str
    state: str
    result_root_token: str | None
    reason_codes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ReplicationReportFact:
    local_report_token: str
    origin_report_token: str
    participant_token: str
    performer_claim_token: str
    design_token: str
    attempt_token: str
    source_trial_token: str
    result_root_token: str
    report_tick: int
    measurement: ReplicationMeasurementFact
    declared_measurement_basis: str
    condition_snapshot: tuple[ReplicationConditionFact, ...]
    collaboration_token: str | None
    delivery_token: str | None
    provenance_kind: str
    claim_digest: str


@dataclass(frozen=True, slots=True)
class ReplicationInterpretationFact:
    interpretation_token: str
    participant_token: str
    design_token: str
    origin_report_token: str
    local_report_token: str
    invitation_token: str | None
    collaboration_token: str | None
    revision_index: int
    revision_tick: int
    appraisal: str
    condition_comparison: str
    source_appraisal: str
    uncertainty_notice: str
    reason_codes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ReplicationDeclarationFact:
    participant_token: str
    act: str
    tick: int
    delivery_token: str | None


@dataclass(frozen=True, slots=True)
class ReplicationCollaborationFact:
    collaboration_token: str
    participant_token: str
    invitation_token: str
    design_token: str
    source_trial_token: str
    inviter_token: str
    group_claim_token: str | None
    status: str
    created_tick: int
    updated_tick: int
    participant_declarations: tuple[ReplicationDeclarationFact, ...] = ()


@dataclass(frozen=True, slots=True)
class ReplicationExecutionFact:
    execution_token: str
    result_root_token: str
    participant_token: str
    execution_tick: int
    operator: str
    process_token: str
    operand_a_token: str | None
    operand_b_token: str | None
    outcome: str


@dataclass(frozen=True, slots=True)
class ReplicationFacts:
    designs: tuple[ReplicationDesignFact, ...] = ()
    attempts: tuple[ReplicationAttemptFact, ...] = ()
    executions: tuple[ReplicationExecutionFact, ...] = ()
    reports: tuple[ReplicationReportFact, ...] = ()
    interpretations: tuple[ReplicationInterpretationFact, ...] = ()
    collaborations: tuple[ReplicationCollaborationFact, ...] = ()
    notices: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ReplicationDesignRow:
    row_token: str
    window_index: int
    layer: ReplicationLayer
    fact: ReplicationDesignFact
    record_type: str = "design"


@dataclass(frozen=True, slots=True)
class ReplicationAttemptRow:
    row_token: str
    window_index: int
    layer: ReplicationLayer
    fact: ReplicationAttemptFact
    record_type: str = "attempt"


@dataclass(frozen=True, slots=True)
class ReplicationObjectiveRow:
    row_token: str
    window_index: int
    layer: ReplicationLayer
    row_kind: str
    fact: ReplicationExecutionFact
    record_type: str = "execution"


@dataclass(frozen=True, slots=True)
class ReplicationOwnerReportRow:
    row_token: str
    window_index: int
    layer: ReplicationLayer
    row_kind: str
    fact: ReplicationReportFact
    associated_execution_token: str | None = None
    record_type: str = "report"


@dataclass(frozen=True, slots=True)
class ReplicationInterpretationRow:
    row_token: str
    window_index: int
    layer: ReplicationLayer
    fact: ReplicationInterpretationFact
    record_type: str = "interpretation"


@dataclass(frozen=True, slots=True)
class ReplicationCollaborationRow:
    row_token: str
    window_index: int
    layer: ReplicationLayer
    fact: ReplicationCollaborationFact
    record_type: str = "collaboration"


@dataclass(frozen=True, slots=True)
class ReplicationComparisonRow:
    row_token: str
    window_index: int
    layer: ReplicationLayer
    comparison_token: str
    basis: str
    participant_token: str | None
    source_trial_token: str
    attempt_token: str
    source_execution_token: str | None
    child_execution_token: str | None
    source_report_token: str | None
    child_report_token: str | None
    source_outcome: str | None
    child_outcome: str | None
    design_token: str
    parent_design_token: str | None
    relation_kind: str
    condition_comparison: str
    category_difference: bool | None
    appraisal: str
    evidence_qualification: str
    excluded_reason: str | None
    collaboration_token: str | None
    record_type: str = "comparison"


@dataclass(frozen=True, slots=True)
class ReplicationCoverageRow:
    row_token: str
    window_index: int
    layer: ReplicationLayer
    expected_participants: int
    exported_participants: int
    submitted_count: int
    observed_count: int
    unresolved_count: int
    missing_source_count: int
    missing_condition_count: int
    unreported_uncertainty_count: int
    duplicate_source_count: int
    excluded_overflow_count: int
    coverage: str
    availability: str
    reason_codes: tuple[str, ...] = ()
    record_type: str = "coverage"


__all__ = [
    "ReplicationAppraisal",
    "ReplicationAttemptFact",
    "ReplicationAttemptRow",
    "ReplicationAvailability",
    "ReplicationCollaborationFact",
    "ReplicationCollaborationRow",
    "ReplicationComparisonRow",
    "ReplicationConditionFact",
    "ReplicationCoverageKind",
    "ReplicationCoverageRow",
    "ReplicationDeclarationFact",
    "ReplicationDesignFact",
    "ReplicationDesignRow",
    "ReplicationEvidenceQualification",
    "ReplicationExcludedReason",
    "ReplicationExecutionFact",
    "ReplicationFacts",
    "ReplicationInterpretationFact",
    "ReplicationInterpretationRow",
    "ReplicationLayer",
    "ReplicationMeasurementFact",
    "ReplicationObjectiveRow",
    "ReplicationOwnerReportRow",
    "ReplicationSelectorFact",
]
