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
    DiplomacySnapshotTreatyDeclarationRow,
    DiplomacySnapshotTreatyLineageRow,
    DiplomacySnapshotTreatyMisrepresentationRow,
    DiplomacySnapshotTreatyRecollectionRow,
    DiplomacySnapshotTreatyRow,
    DiplomacySnapshotTreatyVersionRow,
)
from simulation.diplomacy_ports import (
    DiplomacyPublication,
    DiplomacyPublisherPort,
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
        "treaties": 0 if snapshot is None else len(snapshot.treaties),
        "treaty_versions": (0 if snapshot is None else len(snapshot.treaty_versions)),
        "treaty_accepted": (
            0
            if snapshot is None
            else sum(
                1
                for row in snapshot.treaty_versions
                if row.status == "apparently_accepted"
            )
        ),
        "treaty_recollections": (
            0 if snapshot is None else len(snapshot.treaty_recollections)
        ),
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
    parties_by_id = {
        "dpp-" + hashlib.sha256(row.party_token.encode()).hexdigest()[:16]: (
            DiplomacySnapshotPartyRow(
                party_id="dpp-"
                + hashlib.sha256(row.party_token.encode()).hexdigest()[:16],
                owner_token=row.owner_token,
                party_token=row.party_token,
                party_kind=row.party_kind,
                resolution=row.resolution,
                first_seen_tick=row.first_seen_tick,
                provenance="communicated",
            )
        )
        for row in rows.parties
        if row.party_token is not None and row.party_token in party_tokens
    }
    parties = tuple(parties_by_id.values())
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
    envoy_ids = [f"dpe-{index:016x}" for index in range(1, len(rows.envoys) + 1)]
    envoy_ids_by_owner_token = {
        (row.owner_token, row.envoy_token): envoy_ids[index]
        for index, row in enumerate(rows.envoys)
    }
    envoys = tuple(
        DiplomacySnapshotEnvoyRow(
            envoy_id=envoy_ids[index],
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
        for index, row in enumerate(rows.envoys)
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
            target_ref=(
                envoy_ids_by_owner_token.get(
                    (row.owner_token, row.target_ref), row.target_ref
                )
                if row.target_kind == "envoy"
                else row.target_ref
            ),
            kind=row.kind,
            tick=row.tick,
            provenance="communicated",
        )
        for index, row in enumerate(rows.terminations, start=1)
        if row.target_ref
    )
    _LOG.debug("[FIX] diplomacy_snapshot_envoys_remapped count=%s", len(envoy_ids))
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
    lineage: tuple[DiplomacySnapshotLineageRow, ...] = ()
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
    version_status: dict[tuple[str, str], tuple[str, str]] = {
        (row.treaty_id, row.version_id): (row.status, row.acceptance_basis)
        for row in harvest.treaty_statuses
    }
    treaties = tuple(
        DiplomacySnapshotTreatyRow(
            treaty_id=row.treaty_id,
            relation_id=row.relation_id,
            owner_token=row.owner_token,
            party_tokens=row.party_tokens,
            subject_kind=row.subject_token,
            current_version_id=row.current_version_id,
            status=version_status.get(
                (row.treaty_id, row.current_version_id), ("proposed", "none")
            )[0],
            opened_tick=row.opened_tick,
            last_tick=row.last_tick,
            provenance=row.provenance,
        )
        for row in rows.treaties
    )
    treaty_versions = tuple(
        DiplomacySnapshotTreatyVersionRow(
            version_id=row.version_id,
            treaty_id=row.treaty_id,
            owner_token=row.owner_token,
            version_index=row.version_index,
            parent_version_ids=row.parent_version_ids,
            change_kind=row.change_kind,
            status=version_status.get(
                (row.treaty_id, row.version_id), ("proposed", "none")
            )[0],
            acceptance_basis=version_status.get(
                (row.treaty_id, row.version_id), ("proposed", "none")
            )[1],
            party_tokens=row.party_tokens,
            provision_kinds=row.provision_kinds,
            terms_digest=row.terms_digest,
            record_refs=row.record_refs,
            institutional_memory_refs=row.institutional_memory_refs,
            effective_tick=row.effective_tick,
            end_tick=row.end_tick,
            proposer_party_token=row.proposer_party_token,
            proposer_envoy_token=row.proposer_envoy_token,
            provenance=row.provenance,
        )
        for row in rows.treaty_versions
    )
    treaty_declarations = tuple(
        DiplomacySnapshotTreatyDeclarationRow(
            declaration_id="dpq-" + f"{index:016x}",
            treaty_id=row.treaty_id,
            version_id=row.version_id,
            owner_token=row.owner_token,
            party_token=row.party_token,
            envoy_token=row.envoy_token,
            act=row.act,
            declared_tick=row.declared_tick,
            provenance=row.provenance,
        )
        for index, row in enumerate(rows.treaty_declarations, start=1)
    )
    treaty_recollections = tuple(
        DiplomacySnapshotTreatyRecollectionRow(
            recollection_id="dpz-" + f"{index:016x}",
            owner_token=row.owner_token,
            treaty_ref=row.treaty_ref,
            version_ref=row.version_ref,
            subject_kind=row.subject_token,
            basis=row.basis,
            stance=row.stance,
            claimed_terms_digest=row.claimed_terms_digest,
            confidence=row.confidence,
            first_tick=row.first_tick,
            last_tick=row.last_tick,
            provenance=row.provenance,
        )
        for index, row in enumerate(rows.treaty_recollections, start=1)
    )
    treaty_misrepresentations = tuple(
        DiplomacySnapshotTreatyMisrepresentationRow(
            misrepresentation_id="dpj-" + f"{index:016x}",
            version_id=row.version_id,
            owner_token=row.owner_token,
            kind=row.kind,
            observed_tick=row.observed_tick,
            envoy_token=row.envoy_token,
            party_token=row.party_token,
            provenance=row.provenance,
        )
        for index, row in enumerate(rows.treaty_misrepresentations, start=1)
    )
    treaty_lineage = tuple(
        DiplomacySnapshotTreatyLineageRow(
            edge_id=edge.edge_id,
            treaty_id=edge.treaty_id,
            from_version_id=edge.from_version_id,
            to_version_id=edge.to_version_id,
            change_kind=edge.change_kind,
            tick=edge.tick,
        )
        for edge in harvest.treaty_lineage
    )
    treaties = tuple(sorted(treaties, key=lambda row: (row.opened_tick, row.treaty_id)))
    treaty_versions = tuple(
        sorted(treaty_versions, key=lambda row: (row.effective_tick, row.version_id))
    )
    treaty_declarations = tuple(
        sorted(
            treaty_declarations,
            key=lambda row: (row.declared_tick, row.declaration_id),
        )
    )
    treaty_recollections = tuple(
        sorted(
            treaty_recollections,
            key=lambda row: (row.first_tick, row.recollection_id),
        )
    )
    treaty_misrepresentations = tuple(
        sorted(
            treaty_misrepresentations,
            key=lambda row: (row.observed_tick, row.misrepresentation_id),
        )
    )
    treaty_lineage = tuple(
        sorted(treaty_lineage, key=lambda row: (row.tick, row.edge_id))
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
        for family, _ in harvest.summary.lane_histogram
        if family
    )
    treaty_families = (
        (
            "treaty_structure",
            "treaty_version_lineage",
            "treaty_recollection",
            "treaty_anchor_coverage",
        )
        if rows.has_any_rows()
        else ()
    )
    provenance = tuple(
        sorted(
            (*provenance, *tuple(
                DiplomacySnapshotMetricProvenanceRow(
                    family_id=family,
                    family_version=1,
                    document_digest="0" * 64,
                )
                for family in treaty_families
            )),
            key=lambda row: (row.family_id, row.family_version),
        )
    )
    metric_families = tuple(
        sorted(
            {family for family, _ in harvest.summary.lane_histogram}
            | set(treaty_families)
        )
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
            treaties=treaties,
            treaty_versions=treaty_versions,
            treaty_declarations=treaty_declarations,
            treaty_recollections=treaty_recollections,
            treaty_misrepresentations=treaty_misrepresentations,
            treaty_lineage=treaty_lineage,
            metric_provenance=provenance,
            metric_families=metric_families,
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
    port: DiplomacyPublisherPort,
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
        "treaties": receipt.get("treaties"),
        "treaty_versions": receipt.get("treaty_versions"),
        "treaty_accepted": receipt.get("treaty_accepted"),
        "treaty_recollections": receipt.get("treaty_recollections"),
    }
