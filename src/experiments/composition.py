"""Outer composition: map neutral persistence snapshots into analysis sources.

May import ``analysis`` and ``simulation``. Must not import ``persistence`` or
SQLAlchemy. Composition roots inject protocol-typed readers.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Final

from analysis.models import (
    MEMORY_DYNAMICS_METRIC_VERSION,
    MemoryDynamicsAuditRow,
    MemoryDynamicsReport,
    SubjectiveDerivationEdge,
)
from analysis.sources import (
    InMemoryMemoryEvidenceSource,
    InMemoryObjectiveEventSource,
    reconstruction_evidence_from_durable,
)
from analysis.spatial_control_metrics import SpatialActionRow, SpatialClaimRow
from experiments.persistence import (
    AnalysisEvidenceSnapshotReader,
    PersistedAnalysisSnapshot,
)
from simulation.evidence import (
    EvidenceManifest,
    clamp_sequence_to_high_water,
    manifest_hash_prefix,
)
from world.events import WorldEvent
from world.identifiers import require_exact_nonneg_int

__all__ = [
    "EvidenceCompositionError",
    "EvidenceCompositionService",
    "claim_rows_from_ledgers",
    "constrain_snapshot_to_manifest",
    "map_consolidation_audits_to_report",
    "map_recall_audits_to_dynamics_report",
    "map_snapshot_to_analysis_sources",
    "norm_belief_rows_from_ledgers",
    "spatial_action_rows_from_events",
]

_LOG: Final[logging.Logger] = logging.getLogger("experiments.composition")


class EvidenceCompositionError(ValueError):
    """Stable composition failure codes (no payloads)."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class EvidenceCompositionService:
    """Assembles protocol readers into analysis evidence sources."""

    __slots__ = ("_reader",)

    def __init__(self, reader: AnalysisEvidenceSnapshotReader) -> None:
        self._reader = reader

    async def load_analysis_sources(
        self,
        *,
        experiment_id: str,
        run_id: str,
        owner_id: str,
        manifest: EvidenceManifest | None = None,
    ) -> tuple[InMemoryObjectiveEventSource, InMemoryMemoryEvidenceSource]:
        _LOG.debug(
            "evidence_composition_load_start",
            extra={
                "operation": "load_analysis_sources",
                "experiment_id": experiment_id,
                "run_id": run_id,
                "owner_id": owner_id,
                "has_manifest": manifest is not None,
                "manifest_hash_prefix": (
                    None if manifest is None else manifest_hash_prefix(manifest)
                ),
            },
        )
        snapshot = await self._reader.load(
            experiment_id=experiment_id,
            run_id=run_id,
            owner_id=owner_id,
            manifest=manifest,
        )
        if manifest is not None:
            if manifest.run_id != run_id:
                _LOG.error(
                    "evidence_composition_scope_mismatch",
                    extra={
                        "operation": "load_analysis_sources",
                        "reason_code": "manifest_run_scope_mismatch",
                        "run_id": run_id,
                    },
                )
                raise EvidenceCompositionError("manifest_run_scope_mismatch")
            # Idempotent clamp if the adapter did not already constrain.
            snapshot = constrain_snapshot_to_manifest(snapshot, manifest)
        sources = map_snapshot_to_analysis_sources(snapshot)
        _LOG.debug(
            "evidence_composition_load_complete",
            extra={
                "operation": "load_analysis_sources",
                "experiment_id": experiment_id,
                "run_id": run_id,
                "owner_id": owner_id,
                "trace_count": len(snapshot.traces),
                "reconstruction_count": len(snapshot.reconstructions),
                "edge_count": len(snapshot.derivation_edges),
                "event_count": len(snapshot.events),
                "transaction_status": "detached",
            },
        )
        return sources


def constrain_snapshot_to_manifest(
    snapshot: PersistedAnalysisSnapshot,
    manifest: EvidenceManifest,
) -> PersistedAnalysisSnapshot:
    """Clamp ordered snapshot collections to manifest high-water marks.

    Direct and communicated memories are split by ``MemorySourceKind`` when
    provenance is present; unknown kinds are treated as incomplete/legacy.
    """
    from memory.models import MemorySourceKind

    if type(snapshot) is not PersistedAnalysisSnapshot:
        raise TypeError("constrain_snapshot_to_manifest: invalid_snapshot")
    if type(manifest) is not EvidenceManifest:
        raise TypeError("constrain_snapshot_to_manifest: invalid_manifest")
    if snapshot.run_id != manifest.run_id:
        raise EvidenceCompositionError("manifest_run_scope_mismatch")

    marks = manifest.high_water
    direct = tuple(
        trace
        for trace in snapshot.traces
        if trace.provenance.kind is MemorySourceKind.DIRECT_OBSERVATION
    )
    communicated = tuple(
        trace
        for trace in snapshot.traces
        if trace.provenance.kind is MemorySourceKind.COMMUNICATED
    )
    unknown = tuple(
        trace
        for trace in snapshot.traces
        if trace.provenance.kind
        not in {
            MemorySourceKind.DIRECT_OBSERVATION,
            MemorySourceKind.COMMUNICATED,
        }
    )
    if unknown:
        _LOG.warning(
            "evidence_composition_legacy_trace_kind",
            extra={
                "operation": "constrain_snapshot_to_manifest",
                "reason_code": "legacy_or_unknown_trace_kind",
                "run_id": snapshot.run_id,
                "unknown_count": len(unknown),
            },
        )
    clamped_direct = clamp_sequence_to_high_water(
        direct,
        marks.direct_memories,
        source_label="direct_memories",
    )
    clamped_communicated = clamp_sequence_to_high_water(
        communicated,
        marks.communicated_memories,
        source_label="communicated_memories",
    )
    traces = clamped_direct + clamped_communicated
    reconstructions = clamp_sequence_to_high_water(
        snapshot.reconstructions,
        marks.reconstructions,
        source_label="reconstructions",
    )
    kept_memory_ids = {trace.memory_id.value for trace in traces}
    kept_reconstruction_ids = {row.reconstruction_id for row in reconstructions}
    filtered_edges = tuple(
        edge
        for edge in snapshot.derivation_edges
        if edge.derived_memory_id in kept_memory_ids
        or (
            edge.reconstruction_id is not None
            and edge.reconstruction_id in kept_reconstruction_ids
        )
    )
    _LOG.debug(
        "evidence_composition_manifest_applied",
        extra={
            "operation": "constrain_snapshot_to_manifest",
            "run_id": snapshot.run_id,
            "manifest_hash_prefix": manifest_hash_prefix(manifest),
            "high_water": marks.as_canonical_dict(),
            "trace_count": len(traces),
            "reconstruction_count": len(reconstructions),
            "edge_count": len(filtered_edges),
            "event_count": len(snapshot.events),
        },
    )
    return PersistedAnalysisSnapshot(
        experiment_id=snapshot.experiment_id,
        run_id=snapshot.run_id,
        owner_id=snapshot.owner_id,
        traces=traces,
        reconstructions=reconstructions,
        derivation_edges=filtered_edges,
        events=snapshot.events,
    )


def map_snapshot_to_analysis_sources(
    snapshot: PersistedAnalysisSnapshot,
) -> tuple[InMemoryObjectiveEventSource, InMemoryMemoryEvidenceSource]:
    """Map a neutral detached snapshot into analysis in-memory sources."""
    if type(snapshot) is not PersistedAnalysisSnapshot:
        raise TypeError("map_snapshot_to_analysis_sources: invalid_snapshot")
    events: list[WorldEvent] = []
    for index, item in enumerate(snapshot.events):
        if type(item) is not WorldEvent:
            _LOG.error(
                "evidence_composition_invalid_event",
                extra={
                    "operation": "map_snapshot_to_analysis_sources",
                    "reason_code": "invalid_event_type",
                    "run_id": snapshot.run_id,
                    "event_index": index,
                },
            )
            raise EvidenceCompositionError("invalid_event_type")
        events.append(item)

    reconstructions = tuple(
        reconstruction_evidence_from_durable(
            reconstruction_id=row.reconstruction_id,
            run_id=snapshot.run_id,
            owner_id=snapshot.owner_id,
            source_memory_ids=row.source_memory_ids,
            generation=row.generation,
            created_tick=row.created_tick,
            policy_id=row.policy_id,
            policy_version=row.policy_version,
            payload_sha256=row.payload_sha256,
            derived_trace=None,
        )
        for row in snapshot.reconstructions
    )
    edges = tuple(
        SubjectiveDerivationEdge(
            run_id=snapshot.run_id,
            owner_id=snapshot.owner_id,
            derived_memory_id=edge.derived_memory_id,
            source_memory_id=edge.source_memory_id,
            ordinal=edge.ordinal,
            reconstruction_id=edge.reconstruction_id,
        )
        for edge in snapshot.derivation_edges
    )
    objective = InMemoryObjectiveEventSource({snapshot.run_id: tuple(events)})
    memory = InMemoryMemoryEvidenceSource(
        traces=snapshot.traces,
        reconstructions=reconstructions,
        derivation_edges=edges,
    )
    _LOG.debug(
        "evidence_composition_mapped",
        extra={
            "operation": "map_snapshot_to_analysis_sources",
            "run_id": snapshot.run_id,
            "owner_id": snapshot.owner_id,
            "trace_count": len(snapshot.traces),
            "reconstruction_count": len(reconstructions),
            "edge_count": len(edges),
            "event_count": len(events),
        },
    )
    return objective, memory


def map_recall_audits_to_dynamics_report(
    *,
    experiment_id: str,
    run_id: str,
    condition_id: str,
    memory_mode: str,
    audits: tuple[object, ...],
) -> MemoryDynamicsReport:
    """Map in-run ``RecallAuditRecord`` values into a neutral analysis report.

    Agents never see these audits. Empty audits yield an empty report (V1 /
    REFERENCE arms). Distortion codes and IDs only — never narratives.
    """
    from memory.models import RecallAuditRecord

    rows: list[MemoryDynamicsAuditRow] = []
    for item in audits:
        if type(item) is not RecallAuditRecord:
            raise TypeError("map_recall_audits_to_dynamics_report: invalid_audit")
        rows.append(
            MemoryDynamicsAuditRow(
                reconstruction_id=item.reconstruction_id.value,
                owner_id=item.owner_id.value,
                tick=item.tick,
                source_count=len(item.source_memory_ids),
                competitor_count=len(item.competitor_ids),
                selected_count=len(item.selected_ids),
                distortion_codes=tuple(code.value for code in item.distortion_codes),
                confidence_before=item.confidence_before,
                confidence_after=item.confidence_after,
                strength_delta_count=len(item.strength_deltas),
                source_memory_ids=tuple(mid.value for mid in item.source_memory_ids),
                competitor_ids=tuple(mid.value for mid in item.competitor_ids),
                selected_ids=tuple(mid.value for mid in item.selected_ids),
            )
        )
    report = MemoryDynamicsReport(
        experiment_id=experiment_id,
        run_id=run_id,
        condition_id=condition_id,
        metric_version=MEMORY_DYNAMICS_METRIC_VERSION,
        audits=tuple(rows),
        memory_mode=memory_mode,
    )
    _LOG.debug(
        "memory_dynamics_audit_composed",
        extra={
            "operation": "map_recall_audits_to_dynamics_report",
            "experiment_id": experiment_id,
            "run_id": run_id,
            "condition_id": condition_id,
            "audit_export_count": len(rows),
            "memory_mode": memory_mode,
        },
    )
    return report


def map_consolidation_audits_to_report(
    *,
    run_id: str,
    audits: tuple[object, ...],
) -> object:
    """Map in-run consolidation audits into count-only analysis inputs."""
    from analysis.offline_consolidation_metrics import OfflineConsolidationReport
    from memory.models import OfflineConsolidationAudit

    invocations = 0
    strengthened = 0
    forgotten = 0
    merged = 0
    beliefs = 0
    relationships = 0
    goals = 0
    for item in audits:
        if type(item) is not OfflineConsolidationAudit:
            raise TypeError("map_consolidation_audits_to_report: invalid_audit")
        invocations += 1
        strengthened += item.strengthen_count
        forgotten += item.soft_forget_count
        merged += item.merge_count
        beliefs += item.belief_count
        relationships += item.relationship_count
        goals += item.goal_count
    report = OfflineConsolidationReport(
        run_id=run_id,
        consolidation_invocations=invocations,
        traces_strengthened=strengthened,
        traces_soft_forgotten=forgotten,
        patterns_merged=merged,
        belief_revisions=beliefs,
        relationship_revisions=relationships,
        goal_transitions=goals,
    )
    _LOG.debug(
        "offline_consolidation_audit_composed run_id=%s audit_count=%s",
        run_id,
        invocations,
    )
    return report


def map_reflection_audits_to_report(
    *,
    run_id: str,
    audits: tuple[object, ...],
) -> object:
    """Map in-run reflection audits into count-only analysis inputs."""
    from agents.cognition.reflection import ReflectionAudit
    from analysis.reflection_metrics import ReflectionReport

    kind_fields = {
        "revised_belief": "belief_revisions",
        "updated_self_belief": "belief_revisions",
        "new_hypothesis": "hypotheses",
        "new_long_term_goal": "goals_adopted",
        "abandoned_goal": "goals_abandoned",
        "relationship_reassessment": "relationship_reassessments",
    }

    counts = {name: 0 for name in ReflectionReport.__dataclass_fields__}
    invocations = 0
    patterns = 0
    for item in audits:
        if type(item) is not ReflectionAudit:
            raise TypeError("map_reflection_audits_to_report: invalid_audit")
        invocations += 1
        for kind, count in item.conclusion_kind_counts:
            field = kind_fields.get(kind)
            if field is None:
                raise ValueError("map_reflection_audits_to_report: invalid_kind")
            counts[field] += count
            patterns += count
    report = ReflectionReport(
        run_id=run_id,
        reflection_invocations=invocations,
        belief_revisions=counts["belief_revisions"],
        hypotheses=counts["hypotheses"],
        goals_adopted=counts["goals_adopted"],
        goals_abandoned=counts["goals_abandoned"],
        relationship_reassessments=counts["relationship_reassessments"],
        patterns_detected=patterns,
    )
    _LOG.debug(
        "reflection_audit_composed run_id=%s audit_count=%s",
        run_id,
        invocations,
    )
    return report


_SPATIAL_KINDS: Final[frozenset[str]] = frozenset(
    {
        "move",
        "sleep",
        "take",
        "search",
        "resource_harvested",
        "structure_built",
        "structure_repaired",
        "item_stored",
        "eat",
        "drink",
    }
)


def spatial_action_rows_from_events(
    events: Sequence[object],
) -> tuple[SpatialActionRow, ...]:
    """Project committed events into spatial action rows, including production.

    This walks the event log directly. It does not call
    ``applied_actions_from_world_events`` and does not apply the V1
    vocabulary filter, so production kinds survive.
    """
    if isinstance(events, (str, bytes)) or not isinstance(events, Sequence):
        raise TypeError("spatial_action_rows_from_events: invalid_events")
    rows: list[SpatialActionRow] = []
    for event in events:
        row = _spatial_row_from_event(event)
        if row is not None:
            rows.append(row)
    rows.sort(
        key=lambda item: (item.tick, item.ordinal, item.agent_id, item.action_kind)
    )
    _LOG.debug(
        "spatial_action_rows_built events=%s rows=%s",
        len(events),
        len(rows),
    )
    return tuple(rows)


def norm_belief_rows_from_ledgers(
    ledgers: Sequence[object],
    *,
    tick: int = 0,
) -> tuple[dict[str, object], ...]:
    """Copy detached norm beliefs for analysis. Empty ledgers stay empty."""
    if isinstance(ledgers, (str, bytes)) or not isinstance(ledgers, Sequence):
        raise TypeError("norm_belief_rows_from_ledgers: invalid_ledgers")
    tick = require_exact_nonneg_int("tick", tick)
    rows: list[dict[str, object]] = []
    for ledger in ledgers:
        owner = _id_text(getattr(ledger, "owner_id", None))
        beliefs = getattr(ledger, "beliefs", ())
        if not isinstance(beliefs, tuple):
            raise TypeError("norm_belief_rows_from_ledgers: invalid_ledger")
        for belief in beliefs:
            pattern = _id_text(getattr(belief, "pattern", None))
            status = _id_text(getattr(belief, "status", None))
            response = getattr(belief, "response", None)
            response_text = _id_text(response)
            consequences = getattr(belief, "consequences", ())
            consequence_names = tuple(
                _id_text(getattr(item, "sanction", item))
                for item in consequences
                if _id_text(getattr(item, "sanction", item)) is not None
            )
            rows.append(
                {
                    "tick": tick,
                    "owner_id": owner,
                    "pattern": pattern,
                    "status": status,
                    "confidence": float(getattr(belief, "confidence", 0.0)),
                    "supporter_count": len(getattr(belief, "supporters", ())),
                    "consequences": consequence_names,
                    "response": response_text,
                }
            )
    _LOG.debug(
        "norm_belief_rows_built ledgers=%s rows=%s", len(ledgers), len(rows)
    )
    return tuple(rows)


def claim_rows_from_ledgers(
    ledgers: Sequence[object],
) -> tuple[SpatialClaimRow, ...]:
    """Copy detached heads. An empty ledger sequence stays empty."""
    if isinstance(ledgers, (str, bytes)) or not isinstance(ledgers, Sequence):
        raise TypeError("claim_rows_from_ledgers: invalid_ledgers")
    rows: list[SpatialClaimRow] = []
    for ledger in ledgers:
        claims = getattr(ledger, "claims", ())
        if not isinstance(claims, tuple):
            raise TypeError("claim_rows_from_ledgers: invalid_ledger")
        for head in claims:
            rows.append(
                SpatialClaimRow(
                    owner_id=_id_text(getattr(head, "owner_id", None)),
                    target_kind=_id_text(getattr(head, "target_kind", None)),
                    target_entity_id=_id_text(getattr(head, "target_entity_id", None)),
                    strength=float(head.strength),
                )
            )
    _LOG.debug(
        "spatial_claim_rows_built ledgers=%s rows=%s", len(ledgers), len(rows)
    )
    return tuple(rows)


def _spatial_row_from_event(event: object) -> SpatialActionRow | None:
    details = getattr(event, "details", None)
    kind = getattr(details, "kind", None)
    if not isinstance(kind, str) or kind not in _SPATIAL_KINDS:
        return None
    success = getattr(details, "success", True)
    if success is False:
        return None
    actor = getattr(event, "actor_id", None)
    agent_id = getattr(actor, "value", actor)
    if not isinstance(agent_id, str) or not agent_id:
        return None
    location_id = _event_location_id(event, details, kind)
    if location_id is None:
        return None
    tick = getattr(event, "tick", None)
    ordinal = getattr(event, "sequence", getattr(event, "ordinal", None))
    if isinstance(tick, bool) or not isinstance(tick, int):
        return None
    if isinstance(ordinal, bool) or not isinstance(ordinal, int):
        return None
    return SpatialActionRow(
        tick=tick,
        ordinal=ordinal,
        agent_id=agent_id,
        action_kind=kind,
        location_id=location_id,
        success=True,
    )


def _event_location_id(event: object, details: object, kind: str) -> str | None:
    for name in ("location_id", "resulting_location_id"):
        found = _id_text_or_none(getattr(details, name, None))
        if found is not None:
            return found
    if kind == "move":
        found = _id_text_or_none(getattr(details, "destination_id", None))
        if found is not None:
            return found
    occurrence = getattr(event, "occurrence", None)
    if occurrence is None:
        return None
    if kind == "move":
        found = _id_text_or_none(
            getattr(occurrence, "destination_location_id", None)
        )
        if found is not None:
            return found
    return _id_text_or_none(getattr(occurrence, "origin_location_id", None))


def _id_text(value: object) -> str:
    raw = getattr(value, "value", value)
    if not isinstance(raw, str) or not raw:
        raise TypeError("claim_rows_from_ledgers: invalid_id")
    return raw


def _id_text_or_none(value: object) -> str | None:
    raw = getattr(value, "value", value)
    if not isinstance(raw, str) or not raw:
        return None
    return raw
