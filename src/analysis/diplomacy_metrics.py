"""Four detached inter-society diplomacy metric documents."""

from __future__ import annotations

import json
import logging
from collections.abc import Sequence
from typing import Final

from analysis.diplomacy_alignment import (
    DiplomacyAlignmentStatus,
    DiplomacyAnalysisSummary,
    DiplomacyEnvoyAlignmentRow,
)
from analysis.diplomacy_contract import InterSocietyLane
from analysis.diplomacy_layers import DiplomacyLayerView
from analysis.diplomacy_rows import DiplomacyHarvestRows, treaty_version_accepted
from analysis.models import (
    METRIC_DOCUMENT_SCHEMA_VERSION,
    MetricAvailability,
    MetricCoverage,
    MetricDocument,
    MetricProvenance,
)
from analysis.numerical import library_versions, quantize_float
from analysis.specifications import MetricFamilyId, metric_specification

__all__ = [
    "compute_diplomatic_contact_structure",
    "compute_diplomatic_envoy_alignment",
    "compute_diplomatic_instrument_outcomes",
    "compute_inter_society_relation_lanes",
    "compute_treaty_anchor_coverage",
    "compute_treaty_recollection",
    "compute_treaty_structure",
    "compute_treaty_version_lineage",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.diplomacy_metrics")

_ABSENT_COVERAGE: Final[MetricCoverage] = MetricCoverage(
    observed=0, expected=0, ratio=None
)


def _histogram(values: dict[str, int]) -> str:
    return json.dumps(dict(sorted(values.items())), separators=(",", ":"))


def _ratio(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return quantize_float(numerator / denominator)


def _availability(rows: DiplomacyHarvestRows | None) -> MetricAvailability:
    if rows is None:
        return MetricAvailability.ABSENT
    if rows.coverage.value == "partial":
        return MetricAvailability.PARTIAL
    return MetricAvailability.PRESENT


def _coverage(rows: DiplomacyHarvestRows | None) -> MetricCoverage:
    if rows is None:
        return _ABSENT_COVERAGE
    observed = sum(
        len(getattr(rows, name))
        for name in (
            "relations",
            "parties",
            "contacts",
            "envoys",
            "negotiations",
            "instruments",
            "declarations",
            "misrepresentations",
            "terminations",
            "conflicts",
        )
    )
    expected = max(observed, 1)
    return MetricCoverage(
        observed=observed,
        expected=expected,
        ratio=quantize_float(observed / expected),
    )


def _document(
    family: MetricFamilyId,
    rows: DiplomacyHarvestRows | None,
    *,
    run_id: str,
    input_revision: str,
    values: dict[str, object],
    notes_code: str,
) -> MetricDocument:
    spec = metric_specification(family)
    availability = _availability(rows)
    document = MetricDocument(
        schema_version=METRIC_DOCUMENT_SCHEMA_VERSION,
        metric_family=spec.family_id.value,
        algorithm_version=spec.algorithm_version,
        library_versions=library_versions(),
        run_id=run_id,
        input_revision=input_revision,
        evidence_stages=frozenset(spec.evidence_inputs),
        population=spec.population,
        denominator=spec.denominator,
        coverage=_coverage(rows),
        availability=availability,
        values={} if availability is MetricAvailability.ABSENT else values,
        provenance=MetricProvenance(
            source_kind="diplomacy_analysis",
            source_ids=(run_id,),
            notes_code=notes_code,
        ),
    )
    _LOG.info(
        "diplomacy_metric family=%s availability=%s",
        spec.family_id.value,
        availability.value,
    )
    return document


def _counts(values: list[str]) -> dict[str, int]:
    result: dict[str, int] = {}
    for value in values:
        result[value] = result.get(value, 0) + 1
    return result


def compute_diplomatic_contact_structure(
    rows: DiplomacyHarvestRows | None,
    summary: DiplomacyAnalysisSummary | None,
    layers: DiplomacyLayerView | None,
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    if rows is None or summary is None or layers is None:
        values: dict[str, object] = {}
    else:
        values = {
            "relation_count": len(rows.relations),
            "party_count": len(rows.parties),
            "contact_count": len(rows.contacts),
            "envoy_count": len(rows.envoys),
            "negotiation_count": len(rows.negotiations),
            "party_kind_histogram": _histogram(
                _counts([row.party_kind for row in rows.parties])
            ),
            "contact_kind_histogram": _histogram(
                _counts([row.contact_kind for row in rows.contacts])
            ),
            "envoy_status_histogram": _histogram(
                _counts([row.status for row in rows.envoys])
            ),
            "negotiation_status_histogram": _histogram(
                _counts([row.status for row in rows.negotiations])
            ),
            "coverage": summary.coverage.value,
        }
    return _document(
        MetricFamilyId.DIPLOMATIC_CONTACT_STRUCTURE,
        rows,
        run_id=run_id,
        input_revision=input_revision,
        values=values,
        notes_code="diplomatic_contact_structure_v1",
    )


def compute_diplomatic_instrument_outcomes(
    rows: DiplomacyHarvestRows | None,
    summary: DiplomacyAnalysisSummary | None,
    layers: DiplomacyLayerView | None,
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    if rows is None or summary is None or layers is None:
        values: dict[str, object] = {}
    else:
        kinds = _counts([row.instrument_kind for row in rows.instruments])
        superseded = sum(
            1
            for row in rows.terminations
            if row.kind == "superseded" and row.target_kind == "instrument"
        )
        total = len(rows.instruments)
        values = {
            "instrument_count": total,
            "proposal_count": kinds.get("proposal", 0),
            "promise_count": kinds.get("promise", 0),
            "agreement_count": summary.agreement_count,
            "dispute_count": kinds.get("dispute", 0),
            "shared_project_count": kinds.get("shared_project", 0),
            "apparently_accepted_count": summary.agreement_count,
            "rejected_count": sum(
                1 for row in rows.declarations if row.act == "reject"
            ),
            "withdrawn_count": sum(
                1 for row in rows.declarations if row.act == "withdraw"
            ),
            "unresolved_count": sum(
                1 for row in rows.declarations if row.act == "dispute"
            ),
            "superseded_count": superseded,
            "misrepresentation_count": len(rows.misrepresentations),
            "misrepresentation_kind_histogram": _histogram(
                _counts([row.kind for row in rows.misrepresentations])
            ),
            "declaration_count": len(rows.declarations),
            "acceptance_ratio": _ratio(summary.agreement_count, total),
            "coverage": summary.coverage.value,
        }
    return _document(
        MetricFamilyId.DIPLOMATIC_INSTRUMENT_OUTCOMES,
        rows,
        run_id=run_id,
        input_revision=input_revision,
        values=values,
        notes_code="diplomatic_instrument_outcomes_v1",
    )


def compute_diplomatic_envoy_alignment(
    rows: DiplomacyHarvestRows | None,
    summary: DiplomacyAnalysisSummary | None,
    layers: DiplomacyLayerView | None,
    *,
    run_id: str,
    input_revision: str,
    alignment: tuple[DiplomacyEnvoyAlignmentRow, ...] = (),
) -> MetricDocument:
    if rows is None or summary is None or layers is None:
        values: dict[str, object] = {}
    else:
        counts = {
            status.value: sum(1 for row in alignment if row.status == status.value)
            for status in DiplomacyAlignmentStatus
        }
        aligned = (
            counts[DiplomacyAlignmentStatus.CONSISTENT.value]
            + counts[DiplomacyAlignmentStatus.INCONSISTENT.value]
        )
        values = {
            "consistent_count": counts[DiplomacyAlignmentStatus.CONSISTENT.value],
            "unresolved_count": counts[DiplomacyAlignmentStatus.UNRESOLVED.value],
            "inconsistent_count": counts[DiplomacyAlignmentStatus.INCONSISTENT.value],
            "not_applicable_count": counts[
                DiplomacyAlignmentStatus.NOT_APPLICABLE.value
            ],
            "aligned_declaration_count": aligned,
            "consistency_ratio": _ratio(
                counts[DiplomacyAlignmentStatus.CONSISTENT.value], aligned
            ),
            "inconsistency_ratio": _ratio(
                counts[DiplomacyAlignmentStatus.INCONSISTENT.value], aligned
            ),
            "coverage": summary.coverage.value,
        }
    return _document(
        MetricFamilyId.DIPLOMATIC_ENVOY_ALIGNMENT,
        rows,
        run_id=run_id,
        input_revision=input_revision,
        values=values,
        notes_code="diplomatic_envoy_alignment_v1",
    )


def compute_inter_society_relation_lanes(
    rows: DiplomacyHarvestRows | None,
    summary: DiplomacyAnalysisSummary | None,
    layers: DiplomacyLayerView | None,
    *,
    run_id: str,
    input_revision: str,
    candidates: tuple[object, ...] = (),
) -> MetricDocument:
    if rows is None or summary is None or layers is None:
        values: dict[str, object] = {}
    else:
        pair_count = summary.candidate_count
        lane_counts = dict(summary.lane_histogram)
        lane_pair_histogram = _counts(
            [str(len(getattr(row, "lanes", ()))) for row in candidates]
        )
        any_lane = sum(1 for row in candidates if getattr(row, "lanes", ()))
        multiple = sum(1 for row in candidates if len(getattr(row, "lanes", ())) >= 2)
        values = {
            "pair_count": pair_count,
            "lane_pair_count_histogram": _histogram(lane_pair_histogram),
            "agent_relationship_pair_count": lane_counts.get(
                InterSocietyLane.AGENT_RELATIONSHIPS.value, 0
            ),
            "trade_pair_count": lane_counts.get(InterSocietyLane.TRADE.value, 0),
            "conflict_pair_count": lane_counts.get(InterSocietyLane.CONFLICT.value, 0),
            "agreement_pair_count": lane_counts.get(
                InterSocietyLane.AGREEMENTS.value, 0
            ),
            "narrative_pair_count": lane_counts.get(
                InterSocietyLane.NARRATIVES.value, 0
            ),
            "institutional_interaction_pair_count": lane_counts.get(
                InterSocietyLane.INSTITUTIONAL_INTERACTION.value, 0
            ),
            "pairs_with_any_lane": any_lane,
            "pairs_with_multiple_lanes": multiple,
            "lane_coverage_ratio": _ratio(any_lane, pair_count),
            "coverage": summary.coverage.value,
        }
    return _document(
        MetricFamilyId.INTER_SOCIETY_RELATION_LANES,
        rows,
        run_id=run_id,
        input_revision=input_revision,
        values=values,
        notes_code="inter_society_relation_lanes_v1",
    )


def compute_treaty_structure(
    rows: DiplomacyHarvestRows | None,
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    if rows is None:
        values: dict[str, object] = {}
    else:
        accepted_versions = [
            row
            for row in rows.treaty_versions
            if treaty_version_accepted(row, rows.treaty_declarations)
        ]
        expired_count = sum(
            1
            for row in rows.terminations
            if row.target_kind == "treaty_version" and row.kind == "expired"
        )
        superseded_count = sum(
            1
            for row in rows.terminations
            if row.target_kind == "treaty_version" and row.kind == "superseded"
        )
        values = {
            "treaty_count": len(rows.treaties),
            "participant_count": sum(len(row.party_tokens) for row in rows.treaties),
            "multi_party_count": sum(
                1 for row in rows.treaties if len(row.party_tokens) >= 3
            ),
            "apparently_accepted_count": len(accepted_versions),
            "suspended_count": sum(
                1 for row in rows.treaty_versions if row.change_kind == "suspension"
            ),
            "terminated_count": sum(
                1 for row in rows.treaty_versions if row.change_kind == "termination"
            ),
            "expired_count": expired_count,
            "superseded_count": superseded_count,
            "subject_kind_histogram": _histogram(
                _counts([row.subject_token for row in rows.treaties])
            ),
            "participant_count_histogram": _histogram(
                _counts([str(len(row.party_tokens)) for row in rows.treaties])
            ),
            "coverage": rows.coverage.value,
        }
    return _document(
        MetricFamilyId.TREATY_STRUCTURE,
        rows,
        run_id=run_id,
        input_revision=input_revision,
        values=values,
        notes_code="treaty_structure_v1",
    )


def compute_treaty_version_lineage(
    rows: DiplomacyHarvestRows | None,
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    if rows is None:
        values: dict[str, object] = {}
    else:
        changes = _counts([row.change_kind for row in rows.treaty_versions])
        version_by_id = {row.version_id: row for row in rows.treaty_versions}

        def _depth(version_id: str, seen: frozenset[str] = frozenset()) -> int:
            row = version_by_id.get(version_id)
            if row is None or version_id in seen:
                return 0
            parents = tuple(
                parent
                for parent in row.parent_version_ids
                if parent in version_by_id and parent not in seen
            )
            if not parents:
                return 1
            return 1 + max(
                _depth(parent, seen | {version_id}) for parent in parents
            )

        values = {
            "version_count": len(rows.treaty_versions),
            "original_count": changes.get("original", 0),
            "amendment_count": changes.get("amendment", 0),
            "renewal_count": changes.get("renewal", 0),
            "accession_count": changes.get("accession", 0),
            "withdrawal_count": changes.get("withdrawal", 0),
            "suspension_count": changes.get("suspension", 0),
            "termination_count": changes.get("termination", 0),
            "lineage_edge_count": len(rows.treaty_lineage),
            "max_lineage_depth": max(
                (_depth(version_id) for version_id in version_by_id), default=0
            ),
            "renewal_ratio": _ratio(
                changes.get("renewal", 0), len(rows.treaty_versions)
            ),
            "coverage": rows.coverage.value,
        }
    return _document(
        MetricFamilyId.TREATY_VERSION_LINEAGE,
        rows,
        run_id=run_id,
        input_revision=input_revision,
        values=values,
        notes_code="treaty_version_lineage_v1",
    )


def compute_treaty_recollection(
    rows: DiplomacyHarvestRows | None,
    alignment: Sequence[object] = (),
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    if rows is None:
        values: dict[str, object] = {}
    else:
        stance_counts = _counts([row.stance for row in rows.treaty_recollections])
        basis_counts = _counts([row.basis for row in rows.treaty_recollections])
        statuses = _counts([getattr(row, "status", "unknown") for row in alignment])
        consistent = statuses.get("consistent", 0)
        inconsistent = statuses.get("inconsistent", 0)
        aligned = consistent + inconsistent
        values = {
            "recollection_count": len(rows.treaty_recollections),
            "remember_count": stance_counts.get("remember", 0),
            "reinterpret_count": stance_counts.get("reinterpret", 0),
            "ignore_count": stance_counts.get("ignore", 0),
            "renew_count": stance_counts.get("renew", 0),
            "basis_histogram": _histogram(basis_counts),
            "consistent_count": consistent,
            "unresolved_count": statuses.get("unresolved", 0),
            "inconsistent_count": inconsistent,
            "not_applicable_count": statuses.get("not_applicable", 0),
            "aligned_recollection_count": aligned,
            "consistency_ratio": _ratio(consistent, aligned),
            "inconsistency_ratio": _ratio(inconsistent, aligned),
            "coverage": rows.coverage.value,
        }
    return _document(
        MetricFamilyId.TREATY_RECOLLECTION,
        rows,
        run_id=run_id,
        input_revision=input_revision,
        values=values,
        notes_code="treaty_recollection_v1",
    )


def compute_treaty_anchor_coverage(
    rows: DiplomacyHarvestRows | None,
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    if rows is None:
        values: dict[str, object] = {}
    else:
        version_count = len(rows.treaty_anchors)
        record_count = sum(row.record_anchor_count for row in rows.treaty_anchors)
        memory_count = sum(
            row.institutional_memory_anchor_count for row in rows.treaty_anchors
        )
        with_record = sum(1 for row in rows.treaty_anchors if row.has_record_anchor)
        with_memory = sum(
            1 for row in rows.treaty_anchors if row.has_institutional_memory_anchor
        )
        without_any = sum(1 for row in rows.treaty_anchors if not row.has_any_anchor)
        values = {
            "version_count": version_count,
            "record_anchor_count": record_count,
            "institutional_memory_anchor_count": memory_count,
            "versions_with_record_anchor": with_record,
            "versions_with_institutional_memory_anchor": with_memory,
            "versions_without_any_anchor": without_any,
            "record_anchor_coverage_ratio": _ratio(with_record, version_count),
            "institutional_memory_coverage_ratio": _ratio(with_memory, version_count),
            "coverage": rows.coverage.value,
        }
    return _document(
        MetricFamilyId.TREATY_ANCHOR_COVERAGE,
        rows,
        run_id=run_id,
        input_revision=input_revision,
        values=values,
        notes_code="treaty_anchor_coverage_v1",
    )
