"""Compose one completed-run diplomacy snapshot and receipt.

Composition is pure, bounded, and read-only. It never imports the API,
persistence, the research runner, or live cognition.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

from experiments.diplomacy_harvest import DiplomacyHarvest
from simulation.diplomacy_codec import (
    finalize_diplomacy_snapshot,
)
from simulation.diplomacy_models import (
    DiplomacyArtifactError,
    DiplomacySnapshot,
    DiplomacySnapshotConflictRow,
    DiplomacySnapshotContactRow,
    DiplomacySnapshotDeclarationRow,
    DiplomacySnapshotEnvoyRow,
    DiplomacySnapshotInstrumentRow,
    DiplomacySnapshotLineageRow,
    DiplomacySnapshotMetricProvenanceRow,
    DiplomacySnapshotMisrepresentationRow,
    DiplomacySnapshotNegotiationRow,
    DiplomacySnapshotPartyRow,
    DiplomacySnapshotRelationRow,
    DiplomacySnapshotSummaryRow,
    DiplomacySnapshotTerminationRow,
)
from simulation.diplomacy_ports import (
    DiplomacyPublication,
    DiplomacyPublicationPort,
)

__all__ = [
    "DiplomacyHarvestResult",
    "build_diplomacy_harvest_result",
    "diplomacy_publication_document",
    "publish_diplomacy_snapshot",
]

_LOG: Final[logging.Logger] = logging.getLogger("experiments.diplomacy_publication")

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
class DiplomacyHarvestResult:
    harvest: DiplomacyHarvest | None
    snapshot: DiplomacySnapshot | None
    receipt: Mapping[str, object]
    published: bool


def _receipt(
    *, status: str, reason: str | None, snapshot: DiplomacySnapshot | None
) -> dict[str, object]:
    return {
        "status": status,
        "reason": reason,
        "publication_id": None if snapshot is None else snapshot.publication_id,
        "digest": None if snapshot is None else snapshot.digest,
        "relations": 0 if snapshot is None else snapshot.summary.relation_count,
        "instruments": 0 if snapshot is None else snapshot.summary.instrument_count,
        "terminations": 0 if snapshot is None else snapshot.summary.termination_count,
        "coverage": "partial" if snapshot is None else snapshot.coverage,
    }


def _snapshot(
    harvest: DiplomacyHarvest, *, run_id: str, revision: str, window_end: int
) -> DiplomacySnapshot:
    rows = harvest.rows
    party_tokens = {
        row.party_token for row in rows.parties if row.party_token is not None
    }
    relations = tuple(
        DiplomacySnapshotRelationRow(
            relation_id=row.relation_id,
            owner_token=row.owner_token,
            party_tokens=row.party_tokens,
            opened_tick=row.opened_tick,
            last_tick=row.last_tick,
            provenance="communicated",
        )
        for row in rows.relations
        if len(row.party_tokens) >= 2
    )
    parties = tuple(
        DiplomacySnapshotPartyRow(
            party_id="dpp-" + hashlib.sha256(row.party_token.encode()).hexdigest()[:16],
            owner_token=row.owner_token,
            party_token=row.party_token,
            party_kind=row.party_kind,
            resolution=row.resolution,
            first_seen_tick=row.first_seen_tick,
            provenance="communicated",
        )
        for row in rows.parties
        if row.party_token is not None and row.party_token in party_tokens
    )
    contacts = tuple(
        DiplomacySnapshotContactRow(
            contact_id="dpc-" + f"{index:016x}",
            relation_id=row.relation_id,
            owner_token=row.owner_token,
            tick=row.tick,
            contact_kind=row.contact_kind,
            location_anchor=None,
            participant_count=row.participant_count,
            provenance="witnessed_contact",
        )
        for index, row in enumerate(rows.contacts, start=1)
    )
    envoys = tuple(
        DiplomacySnapshotEnvoyRow(
            envoy_id="dpe-" + f"{index:016x}",
            relation_id=row.relation_id,
            owner_token=row.owner_token,
            party_token=row.party_token,
            envoy_token=row.envoy_token,
            mandate_token=None,
            status=row.status,
            accredited_tick=row.accredited_tick,
            end_tick=row.end_tick,
            provenance="communicated",
        )
        for index, row in enumerate(rows.envoys, start=1)
    )
    negotiations = tuple(
        DiplomacySnapshotNegotiationRow(
            negotiation_id=row.negotiation_id,
            relation_id=row.relation_id,
            owner_token=row.owner_token,
            subject_token=row.subject_token,
            status=row.status,
            opened_tick=row.opened_tick,
            last_tick=row.last_tick,
            term_kind="unknown",
            provenance="communicated",
        )
        for row in rows.negotiations
    )
    instruments = tuple(
        DiplomacySnapshotInstrumentRow(
            instrument_id=row.instrument_id,
            relation_id=row.relation_id,
            owner_token=row.owner_token,
            party_tokens=row.party_tokens,
            instrument_kind=row.instrument_kind,
            term_kind=row.term_kind,
            subject_token=row.subject_token,
            opener_envoy_token=None,
            opened_tick=row.opened_tick,
            end_tick=row.end_tick,
            anchor_refs=row.anchor_refs,
            provenance="communicated",
        )
        for row in rows.instruments
    )
    declarations = tuple(
        DiplomacySnapshotDeclarationRow(
            declaration_id="dpd-" + f"{index:016x}",
            instrument_id=row.instrument_id,
            owner_token=row.owner_token,
            party_token=row.party_token,
            envoy_token=row.envoy_token,
            act=row.act,
            declared_tick=row.declared_tick,
            provenance="communicated",
        )
        for index, row in enumerate(rows.declarations, start=1)
    )
    misrepresentations = tuple(
        DiplomacySnapshotMisrepresentationRow(
            misrepresentation_id="dps-" + f"{index:016x}",
            instrument_id=row.instrument_id,
            owner_token=row.owner_token,
            kind=row.kind,
            observed_tick=row.observed_tick,
            envoy_token=row.envoy_token,
            party_token=None,
            provenance="representation_belief",
        )
        for index, row in enumerate(rows.misrepresentations, start=1)
    )
    terminations = tuple(
        DiplomacySnapshotTerminationRow(
            termination_id="dpt-" + f"{index:016x}",
            owner_token=row.owner_token,
            target_kind=row.target_kind,
            target_ref=row.target_ref,
            kind=row.kind,
            tick=row.tick,
            provenance="communicated",
        )
        for index, row in enumerate(rows.terminations, start=1)
        if row.target_ref
    )
    conflicts = tuple(
        DiplomacySnapshotConflictRow(
            conflict_id="dpx-" + f"{index:016x}",
            relation_id=row.relation_id,
            owner_token=row.owner_token,
            kind=row.kind,
            observed_tick=row.observed_tick,
            instrument_refs=(),
            party_tokens=(),
            provenance="communicated",
        )
        for index, row in enumerate(rows.conflicts, start=1)
    )
    lineage = tuple(
        DiplomacySnapshotLineageRow(
            edge_id=edge.edge_id,
            from_candidate_id=edge.from_candidate_id,
            to_candidate_id=edge.to_candidate_id,
            kind=edge.kind,
            tick=edge.tick,
        )
        for edge in ()
    )
    relations = tuple(
        sorted(relations, key=lambda row: (row.opened_tick, row.relation_id))
    )
    parties = tuple(
        sorted(parties, key=lambda row: (row.first_seen_tick, row.party_id))
    )
    contacts = tuple(sorted(contacts, key=lambda row: (row.tick, row.contact_id)))
    envoys = tuple(sorted(envoys, key=lambda row: (row.accredited_tick, row.envoy_id)))
    negotiations = tuple(
        sorted(negotiations, key=lambda row: (row.opened_tick, row.negotiation_id))
    )
    instruments = tuple(
        sorted(instruments, key=lambda row: (row.opened_tick, row.instrument_id))
    )
    declarations = tuple(
        sorted(declarations, key=lambda row: (row.declared_tick, row.declaration_id))
    )
    misrepresentations = tuple(
        sorted(
            misrepresentations,
            key=lambda row: (row.observed_tick, row.misrepresentation_id),
        )
    )
    terminations = tuple(
        sorted(terminations, key=lambda row: (row.tick, row.termination_id))
    )
    conflicts = tuple(
        sorted(conflicts, key=lambda row: (row.observed_tick, row.conflict_id))
    )
    summary = DiplomacySnapshotSummaryRow(
        relation_count=len(relations),
        party_count=len(parties),
        contact_count=len(contacts),
        envoy_count=len(envoys),
        negotiation_count=len(negotiations),
        instrument_count=len(instruments),
        declaration_count=len(declarations),
        misrepresentation_count=len(misrepresentations),
        termination_count=len(terminations),
        conflict_count=len(conflicts),
        candidate_count=len(harvest.candidates),
        lineage_edge_count=len(lineage),
        last_activity_tick=window_end,
        coverage=rows.coverage.value,
    )
    provenance = tuple(
        DiplomacySnapshotMetricProvenanceRow(
            family_id=family,
            family_version=1,
            document_digest="0" * 64,
        )
        for family in harvest.summary.lane_histogram
        if family
    )
    return finalize_diplomacy_snapshot(
        DiplomacySnapshot(
            run_id=run_id,
            created_revision=revision,
            window_end=window_end,
            coverage=rows.coverage.value,
            summary=summary,
            relations=relations,
            parties=parties,
            contacts=contacts,
            envoys=envoys,
            negotiations=negotiations,
            instruments=instruments,
            declarations=declarations,
            misrepresentations=misrepresentations,
            terminations=terminations,
            conflicts=conflicts,
            lineage=lineage,
            metric_provenance=provenance,
            metric_families=tuple(
                family for family, _ in harvest.summary.lane_histogram
            ),
        )
    )


def build_diplomacy_harvest_result(
    harvest: DiplomacyHarvest | None,
    *,
    run_id: str,
    revision: str,
    window_end: int,
    stop_reason: str | None = None,
) -> DiplomacyHarvestResult:
    """Build one canonical snapshot or a safe unavailable receipt."""

    if stop_reason in _INCOMPLETE_STOP_CODES:
        return DiplomacyHarvestResult(
            harvest=harvest,
            snapshot=None,
            receipt=_receipt(
                status="unavailable", reason="diplomacy_run_incomplete", snapshot=None
            ),
            published=False,
        )
    if harvest is None or not harvest.rows.has_any_rows():
        return DiplomacyHarvestResult(
            harvest=harvest,
            snapshot=None,
            receipt=_receipt(
                status="disabled", reason="diplomacy_input_unavailable", snapshot=None
            ),
            published=False,
        )
    try:
        snapshot = _snapshot(
            harvest, run_id=run_id, revision=revision, window_end=window_end
        )
    except DiplomacyArtifactError as exc:
        return DiplomacyHarvestResult(
            harvest=harvest,
            snapshot=None,
            receipt=_receipt(
                status="failed",
                reason=(
                    "diplomacy_size_limit"
                    if exc.code == "diplomacy_snapshot_size_limit"
                    else exc.code
                ),
                snapshot=None,
            ),
            published=False,
        )
    return DiplomacyHarvestResult(
        harvest=harvest,
        snapshot=snapshot,
        receipt=_receipt(status="ready", reason=None, snapshot=snapshot),
        published=False,
    )


def publish_diplomacy_snapshot(
    result: DiplomacyHarvestResult,
    port: DiplomacyPublicationPort,
) -> DiplomacyHarvestResult:
    """Publish a ready snapshot; failures change only the receipt."""

    if result.snapshot is None:
        return result
    publication = DiplomacyPublication(
        run_id=result.snapshot.run_id,
        publication_id=result.snapshot.publication_id,
        snapshot_digest=result.snapshot.digest,
        snapshot=result.snapshot,
    )
    try:
        port.publish(publication)
    except DiplomacyArtifactError as exc:
        _LOG.error("diplomacy_publication_failed reason=storage")
        return DiplomacyHarvestResult(
            harvest=result.harvest,
            snapshot=result.snapshot,
            receipt=_receipt(
                status="failed", reason=exc.code, snapshot=result.snapshot
            ),
            published=False,
        )
    _LOG.info("diplomacy_publication state=published")
    return DiplomacyHarvestResult(
        harvest=result.harvest,
        snapshot=result.snapshot,
        receipt=_receipt(status="published", reason=None, snapshot=result.snapshot),
        published=True,
    )


def diplomacy_publication_document(receipt: Mapping[str, object]) -> dict[str, object]:
    return {
        "status": receipt.get("status"),
        "reason": receipt.get("reason"),
        "publication_id": receipt.get("publication_id"),
        "digest": receipt.get("digest"),
        "coverage": receipt.get("coverage"),
    }
