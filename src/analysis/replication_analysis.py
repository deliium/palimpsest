"""Deterministic detached replication fold over neutral facts."""

from __future__ import annotations

from typing import Final

from analysis.replication_contract import (
    REPLICATION_MAX_COLLABORATION_ROWS,
    REPLICATION_MAX_DESIGN_ROWS,
    REPLICATION_MAX_ROWS,
    REPLICATION_POLICY_VERSION,
    ReplicationAnalysis,
    replication_row_token,
    window_index,
)
from analysis.replication_rows import (
    ReplicationAppraisal,
    ReplicationAttemptRow,
    ReplicationAvailability,
    ReplicationCollaborationRow,
    ReplicationComparisonRow,
    ReplicationCoverageKind,
    ReplicationCoverageRow,
    ReplicationDesignRow,
    ReplicationEvidenceQualification,
    ReplicationExcludedReason,
    ReplicationFacts,
    ReplicationInterpretationRow,
    ReplicationLayer,
    ReplicationObjectiveRow,
    ReplicationOwnerReportRow,
)

_MATCHED: Final[str] = "matched"
_DIFFERENT: Final[str] = "different"
_UNKNOWN: Final[str] = "unknown"


def _row_token(record_type: str, payload: object) -> str:
    return replication_row_token(record_type, payload)


def _qualify(
    condition: str,
    source_outcome: str | None,
    child_outcome: str | None,
) -> tuple[str, bool | None, str | None]:
    difference = (
        None
        if source_outcome is None or child_outcome is None
        else source_outcome != child_outcome
    )
    if condition == _DIFFERENT:
        return (
            ReplicationAppraisal.NOT_COMPARABLE.value,
            difference,
            ReplicationExcludedReason.CONDITION_DIFFERENT.value,
        )
    if condition == _UNKNOWN:
        return (
            ReplicationAppraisal.INCONCLUSIVE.value,
            difference,
            ReplicationExcludedReason.CONDITION_UNKNOWN.value,
        )
    if source_outcome is None or child_outcome is None:
        return (
            ReplicationAppraisal.INCONCLUSIVE.value,
            difference,
            ReplicationExcludedReason.RESULT_MISSING.value,
        )
    if difference:
        return ReplicationAppraisal.CONFLICTING.value, True, None
    return ReplicationAppraisal.COMPATIBLE.value, False, None


def harvest_replication_analysis(
    facts: ReplicationFacts,
) -> ReplicationAnalysis:
    """Fold normalized facts into rows, comparisons, and coverage."""

    if type(facts) is not ReplicationFacts:
        from analysis.replication_contract import ReplicationAnalysisError

        raise ReplicationAnalysisError("replication_analysis_invalid_facts")
    notices: list[str] = list(facts.notices)
    designs = tuple(
        sorted(facts.designs, key=lambda row: (row.created_tick, row.design_token))
    )
    attempts = tuple(
        sorted(
            facts.attempts,
            key=lambda row: (
                row.observation_tick,
                row.attempt_token,
            ),
        )
    )
    executions = tuple(
        sorted(
            facts.executions,
            key=lambda row: (row.execution_tick, row.execution_token),
        )
    )
    reports = tuple(
        sorted(facts.reports, key=lambda row: (row.report_tick, row.local_report_token))
    )
    interpretation_facts = tuple(
        sorted(
            facts.interpretations,
            key=lambda row: (
                row.revision_tick,
                row.interpretation_token,
                row.revision_index,
            ),
        )
    )
    collaborations = tuple(
        sorted(
            facts.collaborations,
            key=lambda row: (row.created_tick, row.collaboration_token),
        )
    )

    design_rows = []
    for design_fact in designs[:REPLICATION_MAX_DESIGN_ROWS]:
        window = window_index(design_fact.created_tick)
        token = _row_token(
            "design", {"fact": design_fact, "window_index": window}
        )
        design_rows.append(
            ReplicationDesignRow(
                row_token=token,
                window_index=window,
                layer=ReplicationLayer.OWNER_SCOPED,
                fact=design_fact,
            )
        )
    if len(designs) > REPLICATION_MAX_DESIGN_ROWS:
        notices.append("cap_designs")

    attempt_rows = []
    for attempt_fact in attempts[:REPLICATION_MAX_ROWS]:
        window = window_index(attempt_fact.observation_tick)
        token = _row_token(
            "attempt", {"fact": attempt_fact, "window_index": window}
        )
        attempt_rows.append(
            ReplicationAttemptRow(
                row_token=token,
                window_index=window,
                layer=ReplicationLayer.OWNER_SCOPED,
                fact=attempt_fact,
            )
        )
    if len(attempts) > REPLICATION_MAX_ROWS:
        notices.append("cap_attempts")

    execution_rows = []
    for execution_fact in executions[:REPLICATION_MAX_ROWS]:
        window = window_index(execution_fact.execution_tick)
        token = _row_token(
            "execution", {"fact": execution_fact, "window_index": window}
        )
        execution_rows.append(
            ReplicationObjectiveRow(
                row_token=token,
                window_index=window,
                layer=ReplicationLayer.OBJECTIVE,
                row_kind="execution",
                fact=execution_fact,
            )
        )
    if len(executions) > REPLICATION_MAX_ROWS:
        notices.append("cap_executions")

    execution_by_root = {
        row.result_root_token: row for row in executions if row.result_root_token
    }
    report_rows = []
    for report_fact in reports[:REPLICATION_MAX_ROWS]:
        window = window_index(report_fact.report_tick)
        associated = execution_by_root.get(report_fact.result_root_token)
        token = _row_token(
            "report",
            {
                "fact": report_fact,
                "window_index": window,
                "associated_execution_token": (
                    None if associated is None else associated.execution_token
                ),
            },
        )
        report_rows.append(
            ReplicationOwnerReportRow(
                row_token=token,
                window_index=window,
                layer=ReplicationLayer.OWNER_SCOPED,
                row_kind="report",
                fact=report_fact,
                associated_execution_token=(
                    None if associated is None else associated.execution_token
                ),
            )
        )
    if len(reports) > REPLICATION_MAX_ROWS:
        notices.append("cap_reports")

    interpretation_rows = []
    for interpretation_fact in interpretation_facts[:REPLICATION_MAX_ROWS]:
        window = window_index(interpretation_fact.revision_tick)
        token = _row_token(
            "interpretation",
            {"fact": interpretation_fact, "window_index": window},
        )
        interpretation_rows.append(
            ReplicationInterpretationRow(
                row_token=token,
                window_index=window,
                layer=ReplicationLayer.OWNER_SCOPED,
                fact=interpretation_fact,
            )
        )
    if len(interpretation_facts) > REPLICATION_MAX_ROWS:
        notices.append("cap_interpretations")

    collaboration_rows = []
    for collaboration_fact in collaborations[:REPLICATION_MAX_COLLABORATION_ROWS]:
        window = window_index(collaboration_fact.created_tick)
        token = _row_token(
            "collaboration",
            {"fact": collaboration_fact, "window_index": window},
        )
        collaboration_rows.append(
            ReplicationCollaborationRow(
                row_token=token,
                window_index=window,
                layer=ReplicationLayer.OWNER_SCOPED,
                fact=collaboration_fact,
            )
        )
    if len(collaborations) > REPLICATION_MAX_COLLABORATION_ROWS:
        notices.append("cap_collaborations")

    reports_by_root = {
        row.result_root_token: row for row in reports if row.result_root_token
    }
    comparison_rows = []
    missing_source = 0
    missing_conditions = 0
    unresolved = 0
    observed = 0
    for attempt in attempts:
        design = next(
            (row for row in designs if row.design_token == attempt.design_token),
            None,
        )
        source_execution = execution_by_root.get(attempt.source_trial_token)
        child_execution = (
            None
            if attempt.result_root_token is None
            else execution_by_root.get(attempt.result_root_token)
        )
        source_report = reports_by_root.get(attempt.source_trial_token)
        child_report = (
            None
            if attempt.result_root_token is None
            else reports_by_root.get(attempt.result_root_token)
        )
        source_execution_token: str | None
        child_execution_token: str | None
        source_report_token: str | None
        child_report_token: str | None
        if source_execution is not None and child_execution is not None:
            basis = "execution"
            source_outcome: str | None = source_execution.outcome
            child_outcome: str | None = child_execution.outcome
            qualification = ReplicationEvidenceQualification.EXECUTION_BACKED.value
            participant = attempt.participant_token
            source_execution_token = source_execution.execution_token
            child_execution_token = child_execution.execution_token
            source_report_token = None
            child_report_token = None
        elif source_report is not None and child_report is not None:
            basis = "reported"
            source_outcome = source_report.measurement.outcome
            child_outcome = child_report.measurement.outcome
            qualification = ReplicationEvidenceQualification.DECLARED_ONLY.value
            participant = attempt.participant_token
            source_execution_token = (
                None
                if source_execution is None
                else source_execution.execution_token
            )
            child_execution_token = (
                None if child_execution is None else child_execution.execution_token
            )
            source_report_token = source_report.origin_report_token
            child_report_token = child_report.origin_report_token
        else:
            basis = "execution" if attempt.result_root_token else "reported"
            source_outcome = (
                None
                if source_execution is None
                else source_execution.outcome
            )
            child_outcome = (
                None if child_execution is None else child_execution.outcome
            )
            qualification = ReplicationEvidenceQualification.UNRESOLVED.value
            participant = attempt.participant_token
            source_execution_token = (
                None
                if source_execution is None
                else source_execution.execution_token
            )
            child_execution_token = (
                None if child_execution is None else child_execution.execution_token
            )
            source_report_token = (
                None
                if source_report is None
                else source_report.origin_report_token
            )
            child_report_token = (
                None if child_report is None else child_report.origin_report_token
            )
            unresolved += 1
        if source_execution is not None or source_report is not None:
            observed += 1
        else:
            missing_source += 1
        if attempt.condition_comparison == _UNKNOWN:
            missing_conditions += 1
        appraisal, difference, excluded = _qualify(
            attempt.condition_comparison,
            source_outcome,
            child_outcome,
        )
        relation = (
            "unknown"
            if design is None
            else ("adapted" if design.parent_design_token is not None else "repeat")
        )
        window = window_index(attempt.observation_tick)
        comparison_payload = {
            "basis": basis,
            "participant_token": participant,
            "source_trial_token": attempt.source_trial_token,
            "attempt_token": attempt.attempt_token,
            "source_execution_token": source_execution_token,
            "child_execution_token": child_execution_token,
            "source_report_token": source_report_token,
            "child_report_token": child_report_token,
            "source_outcome": source_outcome,
            "child_outcome": child_outcome,
            "design_token": attempt.design_token,
            "parent_design_token": (
                None if design is None else design.parent_design_token
            ),
            "relation_kind": relation,
            "condition_comparison": attempt.condition_comparison,
            "category_difference": difference,
            "appraisal": appraisal,
            "evidence_qualification": qualification,
            "excluded_reason": excluded,
            "collaboration_token": attempt.collaboration_token,
            "window_index": window,
        }
        token = _row_token("comparison", comparison_payload)
        comparison_rows.append(
            ReplicationComparisonRow(
                row_token=token,
                window_index=window,
                layer=ReplicationLayer.DETACHED_ANALYSIS,
                comparison_token="rpc-" + token[-32:],
                basis=basis,
                participant_token=participant,
                source_trial_token=attempt.source_trial_token,
                attempt_token=attempt.attempt_token,
                source_execution_token=source_execution_token,
                child_execution_token=child_execution_token,
                source_report_token=source_report_token,
                child_report_token=child_report_token,
                source_outcome=source_outcome,
                child_outcome=child_outcome,
                design_token=attempt.design_token,
                parent_design_token=(
                    None if design is None else design.parent_design_token
                ),
                relation_kind=relation,
                condition_comparison=attempt.condition_comparison,
                category_difference=difference,
                appraisal=appraisal,
                evidence_qualification=qualification,
                excluded_reason=excluded,
                collaboration_token=attempt.collaboration_token,
            )
        )
    if len(attempts) > REPLICATION_MAX_ROWS:
        notices.append("cap_comparisons")

    expected_participants = len({row.participant_token for row in attempts} | {
        row.participant_token for row in reports
    })
    exported_participants = len({row.participant_token for row in reports})
    coverage_kind = (
        ReplicationCoverageKind.COMPLETE.value
        if reports and unresolved == 0
        else ReplicationCoverageKind.PARTIAL.value
        if reports or attempts
        else ReplicationCoverageKind.MISSING.value
    )
    availability = (
        ReplicationAvailability.AVAILABLE.value
        if comparison_rows
        else ReplicationAvailability.UNAVAILABLE.value
    )
    coverage_by_window: dict[int, ReplicationCoverageRow] = {}
    for window in sorted({row.window_index for row in comparison_rows} or {0}):
        relevant = [row for row in comparison_rows if row.window_index == window]
        payload = {
            "expected_participants": expected_participants,
            "exported_participants": exported_participants,
            "submitted": len(attempts),
            "observed": observed,
            "unresolved": unresolved,
            "missing_source": missing_source,
            "missing_condition": missing_conditions,
            "unreported_uncertainty": sum(
                1
                for row in reports
                if row.measurement.uncertainty_kind == "unreported"
            ),
            "duplicate_source": 0,
            "excluded_overflow": 0,
            "window_index": window,
        }
        token = _row_token("coverage", payload)
        coverage_by_window[window] = ReplicationCoverageRow(
            row_token=token,
            window_index=window,
            layer=ReplicationLayer.DETACHED_ANALYSIS,
            expected_participants=expected_participants,
            exported_participants=exported_participants,
            submitted_count=len(attempts),
            observed_count=observed,
            unresolved_count=unresolved,
            missing_source_count=missing_source,
            missing_condition_count=missing_conditions,
            unreported_uncertainty_count=payload["unreported_uncertainty"],
            duplicate_source_count=0,
            excluded_overflow_count=0,
            coverage=coverage_kind,
            availability=availability,
            reason_codes=tuple(sorted(set(excluded for excluded in (
                row.excluded_reason for row in relevant
            ) if excluded))),
        )

    return ReplicationAnalysis(
        policy_version=REPLICATION_POLICY_VERSION,
        designs=tuple(design_rows),
        attempts=tuple(attempt_rows),
        executions=tuple(execution_rows),
        reports=tuple(report_rows),
        comparisons=tuple(comparison_rows),
        interpretations=tuple(interpretation_rows),
        collaborations=tuple(collaboration_rows),
        coverage=tuple(coverage_by_window.values()),
        notices=tuple(dict.fromkeys(notices)),
    )


__all__ = ["harvest_replication_analysis"]
