"""The only bridge from organization analysis to the published artifact.

The bridge composes detached analysis into one canonical snapshot and injects it
through the publication port. It never runs inside simulation, API, or
persistence, never mutates the snapshot after encoding, and a storage failure
changes only the publication receipt, never scientific status.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Final

from analysis.organization_detection import OrganizationCandidate
from analysis.organization_identity import OrganizationRecord
from experiments.organization_harvest import OrganizationHarvest
from simulation.organization_codec import (
    compute_organization_publication_id,
    decode_organization_snapshot,
    encode_organization_snapshot,
    organization_digest,
)
from simulation.organization_models import (
    MAX_SNAPSHOT_MEMBERS,
    ORGANIZATION_SNAPSHOT_POLICY_VERSION,
    ORGANIZATION_SNAPSHOT_SCHEMA_VERSION,
    OrganizationArtifactError,
    OrganizationCandidateRecord,
    OrganizationCoverage,
    OrganizationLineageEdgeRecord,
    OrganizationMemberRecord,
    OrganizationObjectiveRow,
    OrganizationSnapshot,
    OrganizationStructuralRecord,
    OrganizationWindowRecord,
)
from simulation.organization_ports import (
    OrganizationPublication,
    OrganizationPublicationPort,
)

__all__ = [
    "OrganizationHarvestResult",
    "build_organization_harvest_result",
    "organization_publication_document",
    "publish_organization_snapshot",
]

_LOG: Final[logging.Logger] = logging.getLogger("experiments.organization_publication")

_STATUS_RANK: Final[dict[str, int]] = {
    "explicit": 0,
    "disputed": 1,
    "perceived": 2,
    "unknown": 3,
    "former": 4,
}
_STRENGTH: Final[dict[str, float]] = {
    "explicit": 1.0,
    "disputed": 0.5,
    "perceived": 0.75,
    "unknown": 0.25,
    "former": 0.1,
}


@dataclass(frozen=True, slots=True)
class OrganizationHarvestResult:
    snapshot: OrganizationSnapshot
    publication_id: str
    snapshot_bytes: bytes
    provenance_code: str

    @property
    def snapshot_digest(self) -> str:
        return organization_digest(self.snapshot_bytes)


def _member_records(
    candidate: OrganizationCandidate,
) -> tuple[tuple[OrganizationMemberRecord, ...], bool]:
    members = [
        OrganizationMemberRecord(
            member_id=claim.member_id,
            status=claim.status.value,
            basis=claim.basis,
            temporal_scope=claim.temporal_scope.value,
            first_tick=candidate.first_tick,
            last_tick=candidate.last_tick,
            strength=_STRENGTH.get(claim.status.value, 0.25),
            owner_support_count=max(1, len(claim.owner_ids)),
        )
        for claim in candidate.member_claims
    ]
    members.sort(
        key=lambda item: (
            _STATUS_RANK.get(item.status, 9),
            -item.strength,
            item.member_id,
        )
    )
    truncated = len(members) > MAX_SNAPSHOT_MEMBERS
    return tuple(members[:MAX_SNAPSHOT_MEMBERS]), truncated


def _structural_rows(
    candidate: OrganizationCandidate,
) -> tuple[OrganizationStructuralRecord, ...]:
    rows: list[OrganizationStructuralRecord] = []
    for kind, anchors in (
        ("role", candidate.role_anchor_ids),
        ("goal", candidate.goal_anchor_ids),
        ("resource", candidate.resource_anchor_ids),
        ("procedure", candidate.procedure_anchor_ids),
        ("record", candidate.record_anchor_ids),
        ("commitment", candidate.commitment_ids),
        ("identity", candidate.identity_tokens),
    ):
        for anchor in anchors:
            rows.append(
                OrganizationStructuralRecord(
                    kind=kind,
                    anchor_id=anchor,
                    status=candidate.status.value,
                    first_tick=candidate.first_tick,
                    last_tick=candidate.last_tick,
                )
            )
    return tuple(rows)


def _candidate_record(
    candidate: OrganizationCandidate,
    record: OrganizationRecord,
) -> tuple[OrganizationCandidateRecord, bool]:
    members, truncated = _member_records(candidate)
    return (
        OrganizationCandidateRecord(
            organization_id=record.organization_id,
            creation_tick=record.creation_tick,
            first_tick=record.first_tick,
            last_tick=record.last_tick,
            status=candidate.status.value,
            temporal_scope=candidate.temporal_scope.value,
            self_identified=candidate.self_identified,
            members=members,
            structure=_structural_rows(candidate),
            window_indexes=record.window_indexes,
        ),
        truncated,
    )


def _dissolved_record(record: OrganizationRecord) -> OrganizationCandidateRecord:
    return OrganizationCandidateRecord(
        organization_id=record.organization_id,
        creation_tick=record.creation_tick,
        first_tick=record.first_tick,
        last_tick=record.last_tick,
        status="dissolved",
        temporal_scope="unknown",
        self_identified=False,
        members=tuple(
            OrganizationMemberRecord(
                member_id=member_id,
                status="former",
                basis="inference",
                temporal_scope="unknown",
                first_tick=record.first_tick,
                last_tick=record.last_tick,
                strength=0.1,
                owner_support_count=1,
            )
            for member_id in record.member_ids
        ),
        window_indexes=record.window_indexes,
    )


def build_organization_harvest_result(
    harvest: OrganizationHarvest,
) -> OrganizationHarvestResult:
    """Build one canonical snapshot from a completed-run harvest."""
    analysis = harvest.analysis
    assignment = harvest.assignment
    if analysis is None or assignment is None:
        snapshot = OrganizationSnapshot(
            schema_version=ORGANIZATION_SNAPSHOT_SCHEMA_VERSION,
            policy_version=ORGANIZATION_SNAPSHOT_POLICY_VERSION,
            run_id=harvest.run_id,
            input_revision=harvest.input_revision,
            generated_tick=harvest.generated_tick,
            publication_id="",
            coverage=OrganizationCoverage(observed=0, expected=0, ratio=None),
            provenance_code="ok",
        )
        return _finalize(snapshot, harvest)
    mapping = dict(assignment.candidate_ids)
    latest: dict[str, OrganizationCandidate] = {}
    for window in analysis.windows:
        for candidate in window.candidates:
            organization_id = mapping.get(candidate.candidate_key)
            if organization_id is not None:
                latest[organization_id] = candidate
    records: list[OrganizationCandidateRecord] = []
    truncated = False
    seen_ids: set[str] = set()
    for organization_id in sorted(latest):
        record = assignment.record_for(organization_id)
        if record is None:
            continue
        candidate_record, cut = _candidate_record(latest[organization_id], record)
        records.append(candidate_record)
        truncated = truncated or cut
        seen_ids.add(organization_id)
    for record in analysis.records:
        if record.organization_id in seen_ids:
            continue
        records.append(_dissolved_record(record))
        seen_ids.add(record.organization_id)

    windows = tuple(
        OrganizationWindowRecord(
            window_index=window.window_index,
            start_tick=window.start_tick,
            end_tick=window.end_tick,
            candidate_ids=tuple(
                sorted(
                    mapping[candidate.candidate_key]
                    for candidate in window.candidates
                    if candidate.candidate_key in mapping
                )
            ),
            member_count=sum(
                len(candidate.member_claims) for candidate in window.candidates
            ),
            overlap_member_count=len(window.overlap_person_ids),
            lane_presence=window.lane_presence,
        )
        for window in analysis.windows
    )
    edges = tuple(
        OrganizationLineageEdgeRecord(
            kind=edge.kind.value,
            tick=edge.tick,
            from_id=edge.from_id,
            to_id=edge.to_id,
            jaccard=edge.jaccard,
            containment=edge.containment,
        )
        for edge in analysis.edges
    )
    objective_rows: tuple[OrganizationObjectiveRow, ...] = ()
    if analysis.layer_view is not None:
        objective_rows = tuple(
            OrganizationObjectiveRow(
                window_index=row.window_index,
                tick=row.tick,
                member_count=row.member_count,
                role_count=row.role_count,
                goal_count=row.goal_count,
                resource_count=row.resource_count,
                procedure_count=row.procedure_count,
                record_count=row.record_count,
                commitment_count=row.commitment_count,
                identity_count=row.identity_count,
                resolved_anchor_count=row.resolved_anchor_count,
                unresolved_anchor_count=row.unresolved_anchor_count,
            )
            for row in analysis.layer_view.objective
        )
    coverage = OrganizationCoverage(
        observed=analysis.coverage.observed,
        expected=analysis.coverage.expected,
        ratio=analysis.coverage.ratio,
    )
    provenance = "member_list_truncated" if truncated else harvest.provenance_code
    snapshot = OrganizationSnapshot(
        schema_version=ORGANIZATION_SNAPSHOT_SCHEMA_VERSION,
        policy_version=ORGANIZATION_SNAPSHOT_POLICY_VERSION,
        run_id=harvest.run_id,
        input_revision=harvest.input_revision,
        generated_tick=harvest.generated_tick,
        publication_id="",
        coverage=coverage,
        windows=windows,
        candidates=tuple(records),
        edges=edges,
        objective_rows=objective_rows,
        provenance_code=provenance,
    )
    return _finalize(snapshot, harvest)


def _finalize(
    snapshot: OrganizationSnapshot, harvest: OrganizationHarvest
) -> OrganizationHarvestResult:
    from dataclasses import replace

    publication_id = compute_organization_publication_id(snapshot)
    published = replace(snapshot, publication_id=publication_id)
    payload = encode_organization_snapshot(published)
    if payload != encode_organization_snapshot(decode_organization_snapshot(payload)):
        raise OrganizationArtifactError("organization_digest_mismatch")
    if published.provenance_code != "ok":
        _LOG.warning(
            "organization_publication_partial run_id=%s reason=%s",
            harvest.run_id,
            published.provenance_code,
        )
    _LOG.info(
        "organization_publication_built run_id=%s publication_id=%s "
        "candidates=%s edges=%s bytes=%s",
        harvest.run_id,
        publication_id,
        len(published.candidates),
        len(published.edges),
        len(payload),
    )
    return OrganizationHarvestResult(
        snapshot=published,
        publication_id=publication_id,
        snapshot_bytes=payload,
        provenance_code=published.provenance_code,
    )


def publish_organization_snapshot(
    result: OrganizationHarvestResult,
    port: OrganizationPublicationPort,
) -> None:
    """Inject exactly one publication through the publication port."""
    if type(result) is not OrganizationHarvestResult:
        raise OrganizationArtifactError("organization_invalid_value")
    port.publish(
        OrganizationPublication(
            run_id=result.snapshot.run_id,
            publication_id=result.publication_id,
            snapshot_digest=result.snapshot_digest,
            payload=result.snapshot_bytes,
            generated_tick=result.snapshot.generated_tick,
        )
    )


def organization_publication_document(
    result: OrganizationHarvestResult,
    *,
    status: str = "published",
) -> dict[str, object]:
    """Return safe receipt fields; never ids, labels, or anchors."""
    coverage = result.snapshot.coverage
    return {
        "status": status,
        "schema_version": result.snapshot.schema_version,
        "publication_id": result.publication_id,
        "window_count": len(result.snapshot.windows),
        "candidate_count": len(result.snapshot.candidates),
        "edge_count": len(result.snapshot.edges),
        "coverage_observed": coverage.observed,
        "coverage_expected": coverage.expected,
        "coverage_ratio": coverage.ratio,
        "provenance_code": result.provenance_code,
        "snapshot_bytes": len(result.snapshot_bytes),
    }
