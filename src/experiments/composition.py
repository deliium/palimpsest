"""Outer composition: map neutral persistence snapshots into analysis sources.

May import ``analysis`` and ``simulation``. Must not import ``persistence`` or
SQLAlchemy. Composition roots inject protocol-typed readers.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from analysis.models import (
    MEMORY_DYNAMICS_METRIC_VERSION,
    MemoryDynamicsAuditRow,
    MemoryDynamicsReport,
    SubjectiveDerivationEdge,
)
from analysis.prediction_calibration_metrics import CalibrationRow
from analysis.sources import (
    InMemoryMemoryEvidenceSource,
    InMemoryObjectiveEventSource,
    reconstruction_evidence_from_durable,
)
from analysis.spatial_control_metrics import SpatialActionRow, SpatialClaimRow
from analysis.territorial_concentration_metrics import TerritorialConcentrationRow
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
    "CulturalChannelRow",
    "EvidenceCompositionError",
    "EvidenceCompositionService",
    "artifact_interpretation_rows_from_ledgers",
    "artifact_memory_rows_from_traces",
    "artifact_objective_rows_from_artifacts",
    "calibration_rows_from_world_model_audits",
    "claim_rows_from_ledgers",
    "constrain_snapshot_to_manifest",
    "convention_habit_rows_from_ledgers",
    "cultural_channel_rows_from_convention_habits",
    "cultural_channel_rows_from_norm_beliefs",
    "historical_memory_harvest_from_run",
    "map_consolidation_audits_to_report",
    "map_recall_audits_to_dynamics_report",
    "map_snapshot_to_analysis_sources",
    "norm_belief_rows_from_ledgers",
    "spatial_action_rows_from_events",
    "territorial_control_rows_from_spatial_actions",
    "territorial_presence_rows_from_spatial_actions",
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
_CONTROL_KINDS: Final[frozenset[str]] = frozenset(
    {
        "take",
        "resource_harvested",
        "structure_built",
        "structure_repaired",
        "item_stored",
    }
)


@dataclass(frozen=True, slots=True)
class CulturalChannelRow:
    """Detached per-owner cultural token for cultural_similarity@1."""

    owner_id: str
    token: str


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


def territorial_presence_rows_from_spatial_actions(
    actions: Sequence[object],
) -> tuple[TerritorialConcentrationRow, ...]:
    """Map successful spatial actions into presence-concentration rows."""
    if isinstance(actions, (str, bytes)) or not isinstance(actions, Sequence):
        raise TypeError(
            "territorial_presence_rows_from_spatial_actions: invalid_actions"
        )
    rows: list[TerritorialConcentrationRow] = []
    for action in actions:
        if not bool(getattr(action, "success", True)):
            continue
        location_id = _id_text_or_none(getattr(action, "location_id", None))
        if location_id is None:
            continue
        agent_id = _id_text_or_none(getattr(action, "agent_id", None)) or ""
        tick = int(getattr(action, "tick", 0) or 0)
        rows.append(
            TerritorialConcentrationRow(
                location_id=location_id,
                tick=tick,
                agent_id=agent_id,
            )
        )
    _LOG.debug(
        "territorial_presence_rows_built actions=%s rows=%s",
        len(actions),
        len(rows),
    )
    return tuple(rows)


def territorial_control_rows_from_spatial_actions(
    actions: Sequence[object],
) -> tuple[TerritorialConcentrationRow, ...]:
    """Map control-like spatial actions into control-concentration rows."""
    if isinstance(actions, (str, bytes)) or not isinstance(actions, Sequence):
        raise TypeError(
            "territorial_control_rows_from_spatial_actions: invalid_actions"
        )
    rows: list[TerritorialConcentrationRow] = []
    for action in actions:
        if not bool(getattr(action, "success", True)):
            continue
        kind = _id_text_or_none(getattr(action, "action_kind", None))
        if kind is None or kind not in _CONTROL_KINDS:
            continue
        location_id = _id_text_or_none(getattr(action, "location_id", None))
        if location_id is None:
            continue
        agent_id = _id_text_or_none(getattr(action, "agent_id", None)) or ""
        tick = int(getattr(action, "tick", 0) or 0)
        rows.append(
            TerritorialConcentrationRow(
                location_id=location_id,
                tick=tick,
                agent_id=agent_id,
            )
        )
    _LOG.debug(
        "territorial_control_rows_built actions=%s rows=%s",
        len(actions),
        len(rows),
    )
    return tuple(rows)


def calibration_rows_from_world_model_audits(
    audits: Sequence[object],
    events: Sequence[object],
    *,
    physical_rules: object,
) -> tuple[CalibrationRow, ...]:
    """Join world-model audits to empirical outcomes for calibration rows.

    Reuses causal comparison matching. Unmatched hypotheses are dropped, not
    zeroed. Does not invent engine probabilities.
    """
    from analysis.causal_world_model_metrics import compute_causal_world_model_metrics
    from world.events import WorldEvent
    from world.models import PhysicalRules

    if isinstance(audits, (str, bytes)) or not isinstance(audits, Sequence):
        raise TypeError("calibration_rows_from_world_model_audits: invalid_audits")
    if isinstance(events, (str, bytes)) or not isinstance(events, Sequence):
        raise TypeError("calibration_rows_from_world_model_audits: invalid_events")
    if type(physical_rules) is not PhysicalRules:
        raise TypeError("calibration_rows_from_world_model_audits: invalid_rules")
    world_events: list[WorldEvent] = []
    for event in events:
        if type(event) is not WorldEvent:
            raise TypeError("calibration_rows_from_world_model_audits: invalid_event")
        world_events.append(event)
    if not audits:
        _LOG.debug(
            "calibration_rows_skip",
            extra={"reason_code": "no_world_model_audits", "row_count": 0},
        )
        return ()
    result = compute_causal_world_model_metrics(
        audits,
        tuple(world_events),
        physical_rules=physical_rules,
        run_id="compose-calibration",
        input_revision="compose-calibration",
    )
    rows: list[CalibrationRow] = []
    for comparison in result.comparisons:
        if comparison.empirical_status != "matched":
            continue
        if comparison.empirical_rate is None:
            continue
        rows.append(
            CalibrationRow(
                predicted_confidence=float(comparison.predicted_confidence),
                empirical_outcome=float(comparison.empirical_rate),
            )
        )
    _LOG.debug(
        "calibration_rows_built audits=%s matched_rows=%s",
        len(audits),
        len(rows),
    )
    return tuple(rows)


def cultural_channel_rows_from_norm_beliefs(
    rows: Sequence[object],
) -> tuple[CulturalChannelRow, ...]:
    """Project detached norm belief dict/rows into cultural channel tokens."""
    if isinstance(rows, (str, bytes)) or not isinstance(rows, Sequence):
        raise TypeError("cultural_channel_rows_from_norm_beliefs: invalid_rows")
    out: list[CulturalChannelRow] = []
    for row in rows:
        owner = _cultural_owner(row)
        pattern = _cultural_field(row, "pattern", "norm_head")
        status = _cultural_field(row, "status")
        response = _cultural_field(row, "response")
        if owner is None or pattern is None:
            continue
        token = "|".join(part for part in (pattern, status, response) if part)
        out.append(CulturalChannelRow(owner_id=owner, token=token))
    _LOG.debug(
        "cultural_norm_channel_rows_built source_rows=%s channel_rows=%s",
        len(rows),
        len(out),
    )
    return tuple(out)


def cultural_channel_rows_from_convention_habits(
    rows: Sequence[object],
) -> tuple[CulturalChannelRow, ...]:
    """Project detached convention habit dict/rows into cultural tokens."""
    if isinstance(rows, (str, bytes)) or not isinstance(rows, Sequence):
        raise TypeError(
            "cultural_channel_rows_from_convention_habits: invalid_rows"
        )
    out: list[CulturalChannelRow] = []
    for row in rows:
        owner = _cultural_owner(row)
        situation = _cultural_field(row, "situation")
        usual_action = _cultural_field(row, "usual_action", "habit_token")
        if owner is None or situation is None or usual_action is None:
            continue
        out.append(
            CulturalChannelRow(
                owner_id=owner,
                token=f"{situation}|{usual_action}",
            )
        )
    _LOG.debug(
        "cultural_convention_channel_rows_built source_rows=%s channel_rows=%s",
        len(rows),
        len(out),
    )
    return tuple(out)


def _cultural_owner(row: object) -> str | None:
    if isinstance(row, Mapping):
        return _id_text_or_none(row.get("owner_id"))
    return _id_text_or_none(getattr(row, "owner_id", None))


def _cultural_field(row: object, *names: str) -> str | None:
    for name in names:
        if isinstance(row, Mapping):
            value = row.get(name)
        else:
            value = getattr(row, name, None)
        text = _id_text_or_none(value)
        if text is not None:
            return text
    return None


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


def convention_habit_rows_from_ledgers(
    ledgers: Sequence[object],
    *,
    tick: int = 0,
) -> tuple[dict[str, object], ...]:
    """Copy detached convention habits for analysis. Empty ledgers stay empty."""
    if isinstance(ledgers, (str, bytes)) or not isinstance(ledgers, Sequence):
        raise TypeError("convention_habit_rows_from_ledgers: invalid_ledgers")
    tick = require_exact_nonneg_int("tick", tick)
    rows: list[dict[str, object]] = []
    for ledger in ledgers:
        owner = _id_text(getattr(ledger, "owner_id", None))
        beliefs = getattr(ledger, "beliefs", ())
        if not isinstance(beliefs, tuple):
            raise TypeError("convention_habit_rows_from_ledgers: invalid_ledger")
        for belief in beliefs:
            content = getattr(belief, "content", None)
            situation = _id_text(getattr(content, "situation", None))
            usual_action = _id_text(getattr(content, "usual_action", None))
            first_tick = int(getattr(belief, "first_tick", 0) or 0)
            last_tick = int(getattr(belief, "last_tick", 0) or 0)
            rows.append(
                {
                    "tick": tick,
                    "owner_id": owner,
                    "situation": situation,
                    "usual_action": usual_action,
                    "status": _id_text(getattr(belief, "status", None)),
                    "strength": float(getattr(belief, "strength", 0.0)),
                    "participant_count": len(getattr(belief, "participant_ids", ())),
                    "transmission": _id_text(getattr(belief, "transmission", None)),
                    "explanation": _id_text(
                        getattr(belief, "remembered_explanation", None)
                    ),
                    "conceptualization": _id_text(
                        getattr(belief, "conceptualization", None)
                    ),
                    "duration_ticks": max(0, last_tick - first_tick),
                    "variant_count": len(
                        getattr(belief, "competing_variant_ids", ())
                    ),
                }
            )
    _LOG.debug(
        "convention_habit_rows_built ledgers=%s rows=%s", len(ledgers), len(rows)
    )
    return tuple(rows)


def artifact_objective_rows_from_artifacts(
    artifacts: Sequence[object] | Mapping[object, object],
    *,
    tick: int = 0,
    present: bool = True,
) -> tuple[dict[str, object], ...]:
    """Copy detached objective artifact rows for analysis."""
    tick = require_exact_nonneg_int("tick", tick)
    if isinstance(artifacts, Mapping):
        values: Sequence[object] = tuple(artifacts.values())
    elif isinstance(artifacts, (str, bytes)) or not isinstance(artifacts, Sequence):
        raise TypeError("artifact_objective_rows_from_artifacts: invalid_artifacts")
    else:
        values = artifacts
    rows: list[dict[str, object]] = []
    for artifact in values:
        kind = getattr(artifact, "kind", None)
        kind_text = _id_text_or_none(getattr(kind, "value", kind))
        content = getattr(artifact, "content", None)
        marks = tuple(
            _id_text(mark)
            for mark in getattr(content, "marks", ())
            if _id_text_or_none(mark) is not None
        )
        rows.append(
            {
                "tick": tick,
                "artifact_id": _id_text(getattr(artifact, "artifact_id", None)),
                "kind": kind_text,
                "content_revision": int(
                    getattr(artifact, "content_revision", 0) or 0
                ),
                "present": bool(present),
                "marks": marks,
            }
        )
    _LOG.debug(
        "artifact_objective_rows_built artifacts=%s rows=%s present=%s",
        len(values),
        len(rows),
        present,
    )
    return tuple(rows)


def artifact_memory_rows_from_traces(
    traces: Sequence[object],
    *,
    tick: int = 0,
    cue_concepts: Sequence[str] = (),
) -> tuple[dict[str, object], ...]:
    """Copy detached episodic cue rows for soft-forget analysis."""
    if isinstance(traces, (str, bytes)) or not isinstance(traces, Sequence):
        raise TypeError("artifact_memory_rows_from_traces: invalid_traces")
    tick = require_exact_nonneg_int("tick", tick)
    cues = frozenset(str(item) for item in cue_concepts if isinstance(item, str))
    rows: list[dict[str, object]] = []
    for trace in traces:
        owner = _id_text(getattr(trace, "owner_id", getattr(trace, "agent_id", None)))
        concepts = getattr(trace, "concepts", ())
        if isinstance(concepts, (str, bytes)) or not isinstance(concepts, Sequence):
            concepts = ()
        concept_tokens: list[str] = []
        for item in concepts:
            token = _id_text_or_none(getattr(item, "concept", item))
            if token is not None:
                concept_tokens.append(token)
        if cues:
            has_cue = any(token in cues for token in concept_tokens)
        else:
            has_cue = any(
                "scarce" in token or token.startswith("artifact_reading:")
                for token in concept_tokens
            )
        forgotten = bool(getattr(trace, "forgotten", False))
        if getattr(trace, "soft_forgotten", None) is not None:
            forgotten = bool(trace.soft_forgotten)
        strength = getattr(trace, "strength", None)
        if strength is not None:
            try:
                if float(strength) <= 0.0:
                    forgotten = True
            except (TypeError, ValueError):
                pass
        rows.append(
            {
                "tick": tick,
                "owner_id": owner,
                "has_cue_concept": has_cue,
                "forgotten": forgotten,
            }
        )
    _LOG.debug(
        "artifact_memory_rows_built traces=%s rows=%s cue_count=%s",
        len(traces),
        len(rows),
        len(cues),
    )
    return tuple(rows)


def artifact_interpretation_rows_from_ledgers(
    ledgers: Sequence[object],
) -> tuple[dict[str, object], ...]:
    """Copy detached interpretation readings for analysis. Empty stays empty."""
    if isinstance(ledgers, (str, bytes)) or not isinstance(ledgers, Sequence):
        raise TypeError("artifact_interpretation_rows_from_ledgers: invalid_ledgers")
    rows: list[dict[str, object]] = []
    for ledger in ledgers:
        owner = _id_text(getattr(ledger, "owner_id", None))
        entries = getattr(
            ledger, "interpretations", getattr(ledger, "entries", ())
        )
        if not isinstance(entries, tuple):
            raise TypeError("artifact_interpretation_rows_from_ledgers: invalid_ledger")
        for entry in entries:
            marks = tuple(
                _id_text(mark)
                for mark in getattr(entry, "reading_marks", ())
                if _id_text_or_none(mark) is not None
            )
            rows.append(
                {
                    "owner_id": owner,
                    "artifact_id": _id_text(getattr(entry, "artifact_id", None)),
                    "observed_revision": int(
                        getattr(entry, "observed_revision", 0) or 0
                    ),
                    "reading_marks": marks,
                    "distorted": bool(getattr(entry, "distorted", False)),
                }
            )
    _LOG.debug(
        "artifact_interpretation_rows_built ledgers=%s rows=%s",
        len(ledgers),
        len(rows),
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


def _event_details(event: object) -> object:
    details = getattr(event, "details", None)
    if details is None:
        return event
    return details


def _event_kind_name(event: object) -> str:
    details = _event_details(event)
    kind = getattr(details, "kind", None)
    if isinstance(kind, str) and kind:
        return kind
    name = type(details).__name__
    return name


def _death_ticks_from_events(events: Sequence[object]) -> dict[str, int]:
    deaths: dict[str, int] = {}
    for event in events:
        details = _event_details(event)
        name = type(details).__name__
        kind = getattr(details, "kind", None)
        if name not in {"Died", "DiedEvent"} and kind != "Died":
            if getattr(event, "kind", None) != "Died":
                continue
        agent = _id_text_or_none(
            getattr(details, "agent_id", None)
            or getattr(details, "body_id", None)
            or getattr(event, "agent_id", None)
        )
        tick = getattr(event, "tick", getattr(details, "tick", None))
        if agent is None or isinstance(tick, bool) or type(tick) is not int:
            continue
        if agent not in deaths or tick < deaths[agent]:
            deaths[agent] = tick
    return deaths


def _communication_edges_from_events(
    events: Sequence[object],
) -> tuple[object, ...]:
    from types import SimpleNamespace

    rows: list[object] = []
    for event in events:
        details = _event_details(event)
        kind = _event_kind_name(event).lower()
        if kind not in {"talk", "talked", "tell", "told", "ask", "asked"}:
            continue
        speaker = _id_text_or_none(
            getattr(event, "actor_id", None)
            or getattr(details, "speaker_id", None)
            or getattr(details, "sender_id", None)
        )
        listener = _id_text_or_none(
            getattr(details, "recipient_id", None)
            or getattr(details, "listener_id", None)
        )
        tick = getattr(event, "tick", None)
        if speaker is None or listener is None:
            continue
        rows.append(
            SimpleNamespace(
                speaker_id=speaker,
                listener_id=listener,
                at_tick=tick if type(tick) is int else None,
            )
        )
    return tuple(rows)


def _teaching_edges_from_audits(
    teaching_audits: Sequence[object] | None,
) -> tuple[object, ...]:
    from types import SimpleNamespace

    if not teaching_audits:
        return ()
    rows: list[object] = []
    for row in teaching_audits:
        teacher = _id_text_or_none(
            getattr(row, "teacher_id", None) or getattr(row, "mentor_id", None)
        )
        learner = _id_text_or_none(
            getattr(row, "learner_id", None) or getattr(row, "mentee_id", None)
        )
        tick = getattr(row, "tick", getattr(row, "at_tick", None))
        if teacher is None or learner is None:
            continue
        rows.append(
            SimpleNamespace(
                teacher_id=teacher,
                learner_id=learner,
                at_tick=tick if type(tick) is int else None,
            )
        )
    return tuple(rows)


def historical_memory_harvest_from_run(
    *,
    layers_spec: object | None,
    as_of_tick: int,
    cultural_feature_audits: Sequence[object] | None = None,
    events: Sequence[object] | None = None,
    witness_rows: Sequence[object] | None = None,
    narrative_rows: Sequence[object] | None = None,
    artifact_rows: Sequence[object] | None = None,
    teaching_audits: Sequence[object] | None = None,
    communication_edges: Sequence[object] | None = None,
    teaching_edges: Sequence[object] | None = None,
    death_ticks: Mapping[str, int] | None = None,
    generation_index_by_agent: Mapping[str, int] | None = None,
    sources: Sequence[object] | None = None,
    living_roster: Sequence[str] | None = None,
    transition_ticks: Sequence[int] | None = None,
    generation_boundary_ticks: Sequence[int] | None = None,
) -> object | None:
    """Build a duck-typed HistoricalMemoryHarvest when layers_spec is present.

    Returns None when layers are off. Never imports subjective ledger classes.
    """
    from analysis.historical_memory import (
        HistoricalMemoryHarvest,
        HistoricalSourceRef,
    )

    if layers_spec is None:
        _LOG.debug(
            "historical_memory_harvest_skip reason_code=layers_absent"
        )
        return None
    if isinstance(as_of_tick, bool) or type(as_of_tick) is not int or as_of_tick < 0:
        raise ValueError("as_of_tick: out_of_range")

    audits = tuple(cultural_feature_audits or ())
    include_cultural = bool(
        getattr(layers_spec, "include_cultural_features", True)
    )
    if include_cultural and not audits:
        _LOG.warning(
            "historical_memory_harvest_empty_audits "
            "reason_code=layers_enabled_cultural_audits_empty"
        )

    event_rows = tuple(events or ())
    deaths = dict(death_ticks or {})
    if event_rows and not deaths:
        deaths = _death_ticks_from_events(event_rows)

    comm = tuple(communication_edges or ())
    if not comm and event_rows:
        comm = _communication_edges_from_events(event_rows)
    teach = tuple(teaching_edges or ())
    if not teach:
        teach = _teaching_edges_from_audits(teaching_audits)

    witnesses = tuple(witness_rows or ())
    narratives = tuple(narrative_rows or ())
    artifacts = tuple(artifact_rows or ())

    source_refs: list[HistoricalSourceRef] = []
    seen: set[str] = set()

    def _add_source(
        source_event_id: str,
        *,
        cultural_digest_token: str | None = None,
        transmission_root_id: str | None = None,
        content_key: str | None = None,
    ) -> None:
        if source_event_id in seen:
            return
        seen.add(source_event_id)
        source_refs.append(
            HistoricalSourceRef(
                source_event_id=source_event_id,
                content_key=content_key,
                transmission_root_id=transmission_root_id,
                cultural_digest_token=cultural_digest_token,
            )
        )

    if sources is not None:
        for raw in sources:
            token = _id_text_or_none(getattr(raw, "source_event_id", raw))
            if token is not None:
                _add_source(token)
    for row in witnesses:
        token = _id_text_or_none(getattr(row, "source_event_id", None))
        if token is not None:
            _add_source(token)
    for row in narratives:
        token = _id_text_or_none(getattr(row, "source_event_id", None))
        if token is not None:
            _add_source(
                token,
                transmission_root_id=_id_text_or_none(
                    getattr(row, "transmission_root_id", None)
                ),
            )
    for row in artifacts:
        token = _id_text_or_none(getattr(row, "source_event_id", None))
        if token is not None:
            _add_source(token)
    for row in audits:
        digest = _id_text_or_none(getattr(row, "digest_id_token", None))
        source_id = _id_text_or_none(getattr(row, "source_event_id", None))
        if source_id is not None:
            _add_source(source_id, cultural_digest_token=digest)
        elif digest is not None:
            _add_source(digest, cultural_digest_token=digest)

    ticks = tuple(transition_ticks) if transition_ticks is not None else (
        *sorted(set(deaths.values())),
        as_of_tick,
    )
    harvest = HistoricalMemoryHarvest(
        as_of_tick=as_of_tick,
        sources=tuple(source_refs),
        witness_rows=witnesses,
        communication_edges=comm,
        teaching_edges=teach,
        death_ticks=deaths or None,
        died_events=event_rows,
        generation_index_by_agent=generation_index_by_agent,
        narrative_rows=narratives,
        cultural_feature_audits=audits,
        artifact_rows=artifacts,
        layers_spec=layers_spec,
        transition_ticks=ticks,
        generation_boundary_ticks=tuple(generation_boundary_ticks or ()),
        living_roster=tuple(living_roster) if living_roster is not None else None,
    )
    _LOG.debug(
        "historical_memory_harvest_built source_count=%s "
        "witness_count=%s communication_count=%s teaching_count=%s "
        "cultural_audit_count=%s narrative_count=%s artifact_count=%s "
        "death_count=%s as_of_tick=%s",
        len(harvest.sources),
        len(harvest.witness_rows),
        len(harvest.communication_edges),
        len(harvest.teaching_edges),
        len(harvest.cultural_feature_audits),
        len(harvest.narrative_rows),
        len(harvest.artifact_rows),
        len(harvest.death_ticks or {}),
        as_of_tick,
    )
    return harvest
