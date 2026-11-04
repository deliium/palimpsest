"""Compose one completed-run representation snapshot and receipt.

Composition is pure, bounded, and read-only. It never imports the API,
persistence, the research runner, or live cognition.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from analysis.delegation_representation_identity import RepresentationAnalysis
from analysis.delegation_representation_rows import RepresentationHarvestRows
from experiments.delegation_representation_harvest import RepresentationHarvest
from simulation.delegation_representation_codec import (
    encode_delegation_representation_snapshot,
    finalize_delegation_representation_snapshot,
)
from simulation.delegation_representation_models import (
    MAX_SNAPSHOT_BYTES,
    DelegationRepresentationArtifactError,
    DelegationRepresentationCandidateRow,
    DelegationRepresentationConflictRow,
    DelegationRepresentationLineageRow,
    DelegationRepresentationMandateRow,
    DelegationRepresentationMetricProvenanceRow,
    DelegationRepresentationPositionRow,
    DelegationRepresentationRevocationRow,
    DelegationRepresentationSnapshot,
    DelegationRepresentationSummaryRow,
)
from simulation.delegation_representation_ports import (
    DelegationRepresentationPublication,
    DelegationRepresentationPublicationPort,
)

__all__ = [
    "RepresentationHarvestResult",
    "build_representation_harvest_result",
    "publish_representation_snapshot",
    "representations_publication_document",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.delegation_representation_publication"
)

_INCOMPLETE_STOP_CODES: Final[frozenset[str]] = frozenset(
    {
        "cancelled",
        "cognition_failure",
        "authority_failure",
        "finalization_recovery_required",
        "experiment_criterion_failure",
        "historical_artifact_failure",
    }
)


@dataclass(frozen=True, slots=True)
class RepresentationHarvestResult:
    snapshot: DelegationRepresentationSnapshot | None
    receipt: Mapping[str, object]
    published: bool


def _receipt(
    *,
    status: str,
    reason: str | None,
    snapshot: DelegationRepresentationSnapshot | None,
) -> dict[str, object]:
    return {
        "status": status,
        "reason": reason,
        "publication_id": None if snapshot is None else snapshot.publication_id,
        "digest": None if snapshot is None else snapshot.digest,
        "mandates": 0 if snapshot is None else snapshot.summary.mandate_count,
        "positions": 0 if snapshot is None else snapshot.summary.position_count,
        "revocations": 0 if snapshot is None else snapshot.summary.revocation_count,
        "coverage": "partial" if snapshot is None else snapshot.coverage,
    }


def _candidates(
    analysis: RepresentationAnalysis,
) -> tuple[DelegationRepresentationCandidateRow, ...]:
    lineage_by_target = {
        edge.to_candidate_id: edge.kind.value for edge in analysis.transitions
    }
    return tuple(
        DelegationRepresentationCandidateRow(
            candidate_id=candidate.candidate_id,
            principal_kind=candidate.principal_kind,
            principal_token=candidate.principal_token,
            scope_kind=candidate.scope_kind,
            scope_subject_token=candidate.scope_subject_token,
            status=candidate.status.value,
            representative_tokens=candidate.representative_tokens,
            lineage_kind=lineage_by_target.get(candidate.candidate_id, "emerged"),
            coverage=candidate.coverage.value,
        )
        for candidate in analysis.candidates
    )


def _mandates(
    rows: RepresentationHarvestRows,
) -> tuple[DelegationRepresentationMandateRow, ...]:
    return tuple(
        DelegationRepresentationMandateRow(
            mandate_id=row.mandate_id,
            owner_token=row.owner_token,
            principal_kind=row.principal_kind,
            principal_token=row.principal_token,
            representative_token=row.representative_token,
            scope_kind=row.scope_kind,
            scope_subject_token=row.scope_subject_token,
            duration_kind=row.duration_kind,
            start_tick=row.start_tick,
            end_tick=row.end_tick,
            provenance=row.provenance,
            status=row.status,
            recognition_basis=row.recognition_basis,
            support_roots=row.support_roots,
            opposition_roots=row.opposition_roots,
            confidence_band=row.confidence_band,
            coverage=row.coverage.value,
        )
        for row in rows.mandates
    )


def _positions(
    rows: RepresentationHarvestRows,
) -> tuple[DelegationRepresentationPositionRow, ...]:
    return tuple(
        DelegationRepresentationPositionRow(
            position_id=row.position_id,
            mandate_id=row.mandate_id,
            owner_token=row.owner_token,
            actor_token=row.actor_token,
            stance=row.stance,
            provenance=row.provenance,
            tick=row.tick,
            active=row.active,
        )
        for row in rows.positions
    )


def _revocations(
    rows: RepresentationHarvestRows,
) -> tuple[DelegationRepresentationRevocationRow, ...]:
    return tuple(
        DelegationRepresentationRevocationRow(
            revocation_id=row.revocation_id,
            mandate_id=row.mandate_id,
            owner_token=row.owner_token,
            actor_token=row.actor_token,
            kind=row.kind,
            provenance=row.provenance,
            tick=row.tick,
            contested=row.contested,
        )
        for row in rows.revocations
    )


def _conflicts(
    rows: RepresentationHarvestRows,
) -> tuple[DelegationRepresentationConflictRow, ...]:
    return tuple(
        DelegationRepresentationConflictRow(
            conflict_id=row.conflict_id,
            owner_token=row.owner_token,
            mandate_ids=row.mandate_ids,
            kind=row.kind,
            status=row.status,
            tick=row.tick,
        )
        for row in rows.conflicts
    )


def _metric_provenance(
    values: Sequence[object],
) -> tuple[DelegationRepresentationMetricProvenanceRow, ...]:
    rows: list[DelegationRepresentationMetricProvenanceRow] = []
    for value in values:
        family = getattr(value, "metric_family", None) or getattr(
            value, "family_id", None
        )
        version = getattr(value, "algorithm_version", None) or getattr(
            value, "family_version", None
        )
        digest = getattr(value, "fingerprint", None) or getattr(
            value, "document_digest", None
        )
        if (
            type(family) is not str
            or type(version) is not str
            or type(digest) is not str
        ):
            continue
        if len(digest) != 64:
            continue
        rows.append(
            DelegationRepresentationMetricProvenanceRow(
                family_id=f"{family}@{version}",
                family_version=int(version),
                document_digest=digest,
            )
        )
    return tuple(sorted(rows, key=lambda row: row.family_id))


def build_representation_harvest_result(
    *,
    harvest: RepresentationHarvest,
    stop_reason: object,
    metric_provenance: Sequence[object] = (),
) -> RepresentationHarvestResult:
    """Draft, cap, finalize, and verify one canonical snapshot."""

    if type(harvest) is not RepresentationHarvest:
        raise TypeError("harvest must be RepresentationHarvest")
    stop_code = getattr(stop_reason, "value", stop_reason)
    if stop_code is None or stop_code in _INCOMPLETE_STOP_CODES:
        return RepresentationHarvestResult(
            snapshot=None,
            receipt=_receipt(
                status="unavailable",
                reason="representation_run_incomplete",
                snapshot=None,
            ),
            published=False,
        )
    if not harvest.rows.mandates and not harvest.rows.positions:
        return RepresentationHarvestResult(
            snapshot=None,
            receipt=_receipt(
                status="disabled", reason="representation_disabled", snapshot=None
            ),
            published=False,
        )
    candidates = _candidates(harvest.analysis)
    mandates = _mandates(harvest.rows)
    positions = _positions(harvest.rows)
    revocations = _revocations(harvest.rows)
    conflicts = _conflicts(harvest.rows)
    lineage = tuple(
        DelegationRepresentationLineageRow(
            edge_id=edge.edge_id,
            from_candidate_id=edge.from_candidate_id,
            to_candidate_id=edge.to_candidate_id,
            kind=edge.kind.value,
            tick=edge.tick,
        )
        for edge in harvest.analysis.transitions
    )
    summary = DelegationRepresentationSummaryRow(
        mandate_count=len(mandates),
        position_count=len(positions),
        revocation_count=len(revocations),
        conflict_count=len(conflicts),
        candidate_count=len(candidates),
        lineage_edge_count=len(lineage),
        owner_count=len({row.owner_token for row in mandates}),
        coverage=harvest.rows.coverage.value,
    )
    try:
        snapshot = finalize_delegation_representation_snapshot(
            DelegationRepresentationSnapshot(
                run_id=harvest.run_id,
                generated_tick=harvest.generated_tick,
                created_from=_created_from(harvest),
                coverage=harvest.rows.coverage.value,
                summary=summary,
                candidates=candidates,
                mandates=mandates,
                positions=positions,
                revocations=revocations,
                conflicts=conflicts,
                lineage=lineage,
                metric_provenance=_metric_provenance(metric_provenance),
            )
        )
        encode_delegation_representation_snapshot(snapshot)
    except DelegationRepresentationArtifactError as exc:
        reason = (
            "representation_size_limit"
            if exc.code == "delegation_representation_size_limit"
            else "representation_publication_failed"
        )
        return RepresentationHarvestResult(
            snapshot=None,
            receipt=_receipt(status="failed", reason=reason, snapshot=None),
            published=False,
        )
    return RepresentationHarvestResult(
        snapshot=snapshot,
        receipt=_receipt(
            status="ready", reason="representation_ready", snapshot=snapshot
        ),
        published=True,
    )


def _created_from(harvest: RepresentationHarvest) -> str:
    import hashlib

    material = "\x1f".join(
        (
            harvest.run_id,
            str(harvest.generated_tick),
            str(len(harvest.rows.mandates)),
            str(len(harvest.rows.positions)),
            str(len(harvest.rows.revocations)),
            str(len(harvest.rows.conflicts)),
        )
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def publish_representation_snapshot(
    result: RepresentationHarvestResult,
    publisher: DelegationRepresentationPublicationPort,
) -> RepresentationHarvestResult:
    """Publish one snapshot exactly once through the supplied port."""

    if type(result) is not RepresentationHarvestResult:
        raise TypeError("result must be RepresentationHarvestResult")
    if not result.published or result.snapshot is None:
        return result
    publish = getattr(publisher, "publish", None)
    if not callable(publish):
        raise TypeError("publisher must provide publish()")
    try:
        payload = encode_delegation_representation_snapshot(result.snapshot)
        if len(payload) > MAX_SNAPSHOT_BYTES:
            raise DelegationRepresentationArtifactError(
                "delegation_representation_size_limit"
            )
        publish(
            DelegationRepresentationPublication(
                run_id=result.snapshot.run_id,
                publication_id=result.snapshot.publication_id,
                snapshot_digest=result.snapshot.digest,
                payload=payload,
                generated_tick=result.snapshot.generated_tick,
            )
        )
    except DelegationRepresentationArtifactError as exc:
        reason = (
            "representation_size_limit"
            if exc.code == "delegation_representation_size_limit"
            else exc.code
        )
        _LOG.warning("representation_publication_failed reason=%s", reason)
        return RepresentationHarvestResult(
            snapshot=result.snapshot,
            receipt=_receipt(status="failed", reason=reason, snapshot=result.snapshot),
            published=False,
        )
    except OSError:
        _LOG.warning("representation_publication_failed reason=os_error")
        return RepresentationHarvestResult(
            snapshot=result.snapshot,
            receipt=_receipt(
                status="failed",
                reason="representation_publication_failed",
                snapshot=result.snapshot,
            ),
            published=False,
        )
    _LOG.info("representation_publication status=published")
    return RepresentationHarvestResult(
        snapshot=result.snapshot,
        receipt=_receipt(status="published", reason=None, snapshot=result.snapshot),
        published=True,
    )


def representations_publication_document(
    result: RepresentationHarvestResult,
) -> dict[str, object]:
    """Return metadata-only publication content for receipts."""

    if type(result) is not RepresentationHarvestResult:
        raise TypeError("result must be RepresentationHarvestResult")
    snapshot = result.snapshot
    return {
        "run_id": None if snapshot is None else snapshot.run_id,
        "schema_version": None if snapshot is None else snapshot.schema_version,
        "publication_id": None if snapshot is None else snapshot.publication_id,
        "digest": None if snapshot is None else snapshot.digest,
        "mandates": 0 if snapshot is None else snapshot.summary.mandate_count,
        "positions": 0 if snapshot is None else snapshot.summary.position_count,
        "revocations": (0 if snapshot is None else snapshot.summary.revocation_count),
        "coverage": "partial" if snapshot is None else snapshot.coverage,
        "status": result.receipt["status"],
        "reason": result.receipt["reason"],
        "published": result.published,
    }
