"""Four detached accounting ledger metric families (catalog 216 -> 220)."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Final

from analysis.accounting_ledgers_analysis import AccountingLedgersAnalysis
from analysis.accounting_ledgers_contract import (
    ACCOUNTING_ANALYSIS_FORBIDDEN_KEYS,
    ACCOUNTING_LEDGERS_ANALYSIS_POLICY_VERSION,
    AccountingAnalysisError,
    AccountingCoverage,
    AccountingEntryDirection,
    AccountingEntryKindToken,
    AccountingRecordAssessmentToken,
    AccountingRecordIntegrityToken,
)
from analysis.models import (
    METRIC_DOCUMENT_SCHEMA_VERSION,
    MetricAvailability,
    MetricCoverage,
    MetricDocument,
    MetricProvenance,
)
from analysis.numerical import library_versions, quantize_float
from analysis.specifications import MetricFamilyId, metric_specification
from world.identifiers import require_stable_id

__all__ = [
    "compute_accounting_entry_alignment",
    "compute_accounting_flow_structure",
    "compute_accounting_record_condition",
    "compute_accounting_record_coverage",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "analysis.accounting_ledgers.metrics"
)

_ABSENT_COVERAGE: Final[MetricCoverage] = MetricCoverage(
    observed=0, expected=0, ratio=None
)
_POLICY_TOKEN: Final[str] = "accounting-ledgers"


def _require(analysis: object) -> AccountingLedgersAnalysis:
    if type(analysis) is not AccountingLedgersAnalysis:
        raise AccountingAnalysisError("accounting_analysis_invalid_row")
    return analysis


def _ratio(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return quantize_float(numerator / denominator)


def _state(coverage: AccountingCoverage) -> str:
    if coverage is AccountingCoverage.MISSING:
        return "unknown"
    if coverage is AccountingCoverage.PARTIAL:
        return "partial"
    return "present"


def _reject_forbidden_fields(values: Mapping[str, object]) -> None:
    for key in values:
        if str(key).lower() in ACCOUNTING_ANALYSIS_FORBIDDEN_KEYS:
            raise AccountingAnalysisError("accounting_analysis_forbidden_key")


def _document(
    family: MetricFamilyId,
    *,
    state: str,
    observed: int,
    expected: int,
    run_id: str,
    input_revision: str,
    values: Mapping[str, object],
) -> MetricDocument:
    spec = metric_specification(family)
    if state == "unknown":
        availability = MetricAvailability.UNKNOWN
        coverage = _ABSENT_COVERAGE
        payload: dict[str, object] = {}
    else:
        availability = (
            MetricAvailability.PRESENT
            if state == "present"
            else MetricAvailability.PARTIAL
        )
        coverage = MetricCoverage(
            observed=observed, expected=expected, ratio=_ratio(observed, expected)
        )
        _reject_forbidden_fields(values)
        payload = dict(values)
    return MetricDocument(
        schema_version=METRIC_DOCUMENT_SCHEMA_VERSION,
        metric_family=spec.family_id.value,
        algorithm_version=spec.algorithm_version,
        library_versions=library_versions(),
        run_id=run_id,
        input_revision=input_revision,
        evidence_stages=frozenset(spec.evidence_inputs),
        population=spec.population,
        denominator=spec.denominator,
        coverage=coverage,
        availability=availability,
        values=payload,
        provenance=MetricProvenance(
            source_kind="accounting_ledgers_analysis",
            source_ids=(
                run_id,
                input_revision,
                ACCOUNTING_LEDGERS_ANALYSIS_POLICY_VERSION,
                _POLICY_TOKEN,
            ),
            notes_code="detached_accounting_analysis",
        ),
    )


def _ids(run_id: str, input_revision: str) -> tuple[str, str]:
    return (
        require_stable_id("run_id", run_id),
        require_stable_id("input_revision", input_revision),
    )


def _window_tick(analysis: AccountingLedgersAnalysis) -> int:
    ticks: list[int] = [entry.last_tick for entry in analysis.entries]
    ticks.extend(record.tick for record in analysis.records)
    ticks.extend(flow.window_index * 32 for flow in analysis.flows)
    return max(ticks, default=0)


def compute_accounting_record_coverage(
    analysis: object, *, run_id: str, input_revision: str
) -> MetricDocument:
    """Describe record/entry coverage counts; never an objective ledger."""

    rows = _require(analysis)
    run_id, input_revision = _ids(run_id, input_revision)
    state = _state(rows.coverage["records"])
    if state == "unknown":
        return _document(
            MetricFamilyId.ACCOUNTING_RECORD_COVERAGE,
            state=state,
            observed=0,
            expected=0,
            run_id=run_id,
            input_revision=input_revision,
            values={},
        )
    record_tokens = {record.record_token for record in rows.records}
    backed = sum(
        1 for entry in rows.entries if entry.record_token in record_tokens
    )
    values = {
        "accounting_ledgers_window_tick": _window_tick(rows),
        "record_row_count": len(rows.records),
        "entry_row_count": len(rows.entries),
        "record_backed_entry_count": backed,
        "unbacked_entry_count": len(rows.entries) - backed,
        "intact_row_count": sum(
            1
            for record in rows.records
            if record.observed_integrity is AccountingRecordIntegrityToken.INTACT
        ),
        "damaged_row_count": sum(
            1
            for record in rows.records
            if record.observed_integrity
            is AccountingRecordIntegrityToken.DAMAGED
        ),
        "tombstoned_row_count": sum(
            1 for record in rows.records if record.tombstoned
        ),
        "coverage": rows.coverage["records"].value,
        "availability": state,
    }
    return _document(
        MetricFamilyId.ACCOUNTING_RECORD_COVERAGE,
        state=state,
        observed=len(rows.records),
        expected=len(rows.records) + len(rows.entries),
        run_id=run_id,
        input_revision=input_revision,
        values=values,
    )


def compute_accounting_entry_alignment(
    analysis: object, *, run_id: str, input_revision: str
) -> MetricDocument:
    """Describe researcher-only alignment counts; never cognition input."""

    rows = _require(analysis)
    run_id, input_revision = _ids(run_id, input_revision)
    state = _state(rows.coverage["alignments"])
    if state == "unknown":
        return _document(
            MetricFamilyId.ACCOUNTING_ENTRY_ALIGNMENT,
            state=state,
            observed=0,
            expected=0,
            run_id=run_id,
            input_revision=input_revision,
            values={},
        )
    counts = {
        name: sum(1 for row in rows.alignments if row.alignment.value == name)
        for name in ("consistent", "unresolved", "inconsistent", "not_applicable")
    }
    total = len(rows.alignments)
    values = {
        "accounting_ledgers_window_tick": _window_tick(rows),
        "consistent_count": counts["consistent"],
        "unresolved_count": counts["unresolved"],
        "inconsistent_count": counts["inconsistent"],
        "not_applicable_count": counts["not_applicable"],
        "owner_row_count": len(rows.owners),
        "evidence_row_count": len(rows.records) + len(rows.alignments),
        "alignment_share_milli": (
            0 if total == 0 else counts["consistent"] * 1_000 // total
        ),
        "coverage": rows.coverage["alignments"].value,
        "availability": state,
    }
    return _document(
        MetricFamilyId.ACCOUNTING_ENTRY_ALIGNMENT,
        state=state,
        observed=total,
        expected=len(rows.owners),
        run_id=run_id,
        input_revision=input_revision,
        values=values,
    )


def compute_accounting_record_condition(
    analysis: object, *, run_id: str, input_revision: str
) -> MetricDocument:
    """Describe owner appraisals; never a truth, fraud, or audit finding."""

    rows = _require(analysis)
    run_id, input_revision = _ids(run_id, input_revision)
    state = _state(rows.coverage["conditions"])
    if state == "unknown":
        return _document(
            MetricFamilyId.ACCOUNTING_RECORD_CONDITION,
            state=state,
            observed=0,
            expected=0,
            run_id=run_id,
            input_revision=input_revision,
            values={},
        )
    counts = {
        assessment.value: sum(
            1
            for entry in rows.entries
            if entry.assessment is assessment
        )
        for assessment in AccountingRecordAssessmentToken
    }
    total = len(rows.entries)
    damaged = counts[AccountingRecordAssessmentToken.DAMAGED.value]
    values = {
        "accounting_ledgers_window_tick": _window_tick(rows),
        "unassessed_count": counts["unassessed"],
        "consistent_count": counts["consistent"],
        "contradicted_count": counts["contradicted"],
        "outdated_count": counts["outdated"],
        "suspected_fraudulent_count": counts["suspected_fraudulent"],
        "damaged_count": damaged,
        "total_row_count": total,
        "assessed_share_milli": (
            0
            if total == 0
            else (total - counts["unassessed"]) * 1_000 // total
        ),
        "damaged_share_milli": 0 if total == 0 else damaged * 1_000 // total,
        "coverage": rows.coverage["conditions"].value,
        "availability": state,
    }
    return _document(
        MetricFamilyId.ACCOUNTING_RECORD_CONDITION,
        state=state,
        observed=len(rows.conditions),
        expected=total,
        run_id=run_id,
        input_revision=input_revision,
        values=values,
    )


def compute_accounting_flow_structure(
    analysis: object, *, run_id: str, input_revision: str
) -> MetricDocument:
    """Describe claim sums and direction counts; never a wealth total."""

    rows = _require(analysis)
    run_id, input_revision = _ids(run_id, input_revision)
    state = _state(rows.coverage["flows"])
    if state == "unknown":
        return _document(
            MetricFamilyId.ACCOUNTING_FLOW_STRUCTURE,
            state=state,
            observed=0,
            expected=0,
            run_id=run_id,
            input_revision=input_revision,
            values={},
        )
    kind_counts = {
        kind.value: sum(1 for entry in rows.entries if entry.entry_kind is kind)
        for kind in AccountingEntryKindToken
    }
    direction_counts = {
        direction.value: sum(
            1 for entry in rows.entries if entry.direction is direction
        )
        for direction in AccountingEntryDirection
    }
    values = {
        "accounting_ledgers_window_tick": _window_tick(rows),
        "exchange_count": kind_counts["exchange"],
        "debt_count": kind_counts["debt"],
        "inventory_count": kind_counts["inventory"],
        "organizational_resource_count": kind_counts["organizational_resource"],
        "contribution_count": kind_counts["contribution"],
        "inflow_count": direction_counts["inflow"],
        "outflow_count": direction_counts["outflow"],
        "holding_count": direction_counts["holding"],
        "counterparty_count": len(rows.counterparties),
        "coverage": rows.coverage["flows"].value,
        "availability": state,
    }
    return _document(
        MetricFamilyId.ACCOUNTING_FLOW_STRUCTURE,
        state=state,
        observed=len(rows.flows),
        expected=len(rows.entries),
        run_id=run_id,
        input_revision=input_revision,
        values=values,
    )
