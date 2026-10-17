"""Outer composition: map neutral persistence snapshots into analysis sources.

May import ``analysis`` and ``simulation``. Must not import ``persistence`` or
SQLAlchemy. Composition roots inject protocol-typed readers.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from analysis.offline_consolidation_metrics import OfflineConsolidationReport
    from analysis.reflection_metrics import ReflectionReport

from analysis.contact_cultural_change import (
    ContactDigestRow,
    compute_contact_cultural_change,
)
from analysis.contact_hybrid_practice import (
    ContactCulturalLineageRow,
    ContactMergeRow,
    ContactNarrativeRootRow,
    ContactPracticalLineageRow,
    compute_contact_hybrid_practice,
)
from analysis.contact_inputs import ContactAnalysisInputs
from analysis.contact_knowledge_transfer import (
    ContactPracticalKnowledgeAuditRow,
    compute_contact_knowledge_transfer,
)
from analysis.contact_lexical_borrowing import (
    ContactNamingEvidenceRow,
    compute_contact_lexical_borrowing,
)
from analysis.contact_reputation_transfer import (
    ContactReputationEvidenceRow,
    compute_contact_reputation_transfer,
)
from analysis.models import (
    MEMORY_DYNAMICS_METRIC_VERSION,
    MemoryDynamicsAuditRow,
    MemoryDynamicsReport,
    SubjectiveDerivationEdge,
)
from analysis.prediction_calibration_metrics import CalibrationRow
from analysis.regional_destination_beliefs import RegionalDestinationEvidenceRow
from analysis.regional_population import (
    RegionalEventRow,
    RegionalInitialPlacementRow,
    RegionalLocationRow,
    RegionalPopulationInput,
)
from analysis.society_contact import (
    ContactEpisodeRow,
    ContactInteractionRow,
    ContactKinshipRow,
    ContactPairRow,
    ContactPresenceRow,
    compute_society_contact,
)
from analysis.society_divergence import (
    SOCIETY_DIMENSIONS,
    SocietyDigestRow,
    SocietyDivergenceResult,
    compute_society_divergence,
)
from analysis.society_emergence import (
    CandidateCommunityRow,
    SocietyEdgeRow,
    SocietyEmissionResult,
    SocietyResidenceRow,
    compute_candidate_communities,
)
from analysis.society_isolation import (
    SocietyEvidenceEdge,
    SocietyIsolationResult,
    SocietyJourneyRow,
    compute_society_isolation,
)
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
    PersistedRegionalContext,
    PersistedRegionalInitialPlacement,
    PersistedRegionalLocation,
)
from simulation.evidence import (
    EvidenceManifest,
    clamp_sequence_to_high_water,
    manifest_hash_prefix,
)
from world.events import WorldEvent
from world.identifiers import require_exact_nonneg_int

__all__ = [
    "ContactAnalysisInputs",
    "CulturalChannelRow",
    "EvidenceCompositionError",
    "EvidenceCompositionService",
    "artifact_interpretation_rows_from_ledgers",
    "artifact_memory_rows_from_traces",
    "artifact_objective_rows_from_artifacts",
    "calibration_rows_from_world_model_audits",
    "claim_rows_from_ledgers",
    "constrain_snapshot_to_manifest",
    "contact_analysis_inputs_from_snapshot",
    "contact_digest_rows_from_snapshot",
    "contact_episode_rows_from_events",
    "contact_interaction_rows_from_events",
    "contact_kinship_rows_from_events",
    "contact_presence_rows_from_regional_input",
    "convention_habit_rows_from_ledgers",
    "cultural_channel_rows_from_convention_habits",
    "cultural_channel_rows_from_norm_beliefs",
    "death_ticks_by_body_from_events",
    "durable_record_event_rows_from_events",
    "durable_record_harvest_from_run",
    "historical_memory_harvest_from_run",
    "knowledge_genealogy_harvest_from_run",
    "knowledge_repository_harvest_from_run",
    "map_consolidation_audits_to_report",
    "map_recall_audits_to_dynamics_report",
    "map_snapshot_to_analysis_sources",
    "norm_belief_rows_from_ledgers",
    "regional_context_from_run",
    "regional_destination_evidence_rows_from_traces",
    "regional_metric_inputs_from_snapshots",
    "regional_population_input_from_context",
    "regional_population_input_from_snapshot",
    "regional_population_rows_from_events",
    "repository_event_rows_from_events",
    "repository_event_rows_from_resolutions",
    "repository_objective_rows_from_repositories",
    "society_digest_rows_from_channel_rows",
    "society_digest_rows_from_snapshot",
    "society_emission_inputs_from_context",
    "society_emission_inputs_from_snapshot",
    "society_interaction_edges_from_events",
    "society_journeys_from_regional_input",
    "society_residence_rows_from_regional_input",
    "society_trust_edges_from_relationship_rows",
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

    async def load_regional_metric_inputs(
        self,
        *,
        run_id: str,
        owner_id: str,
        input_revision: str,
        window_end: int,
        experiment_id: str | None = None,
        manifest: EvidenceManifest | None = None,
        complete_through_boundary: int | None = None,
    ) -> tuple[
        RegionalPopulationInput | None,
        tuple[RegionalDestinationEvidenceRow, ...] | None,
        int | None,
    ]:
        """Load all owner-scoped evidence needed by read-only regional metrics."""
        anchor = await self._reader.load(
            run_id=run_id,
            owner_id=owner_id,
            experiment_id=experiment_id,
            manifest=manifest,
        )
        if manifest is not None:
            anchor = constrain_snapshot_to_manifest(anchor, manifest)
        context = anchor.regional_context
        if context is None:
            return None, None, None
        if owner_id not in context.owner_ids:
            raise EvidenceCompositionError("regional_owner_not_registered")
        snapshots = [anchor]
        for current_owner_id in context.owner_ids:
            if current_owner_id == owner_id:
                continue
            snapshot = await self._reader.load(
                run_id=run_id,
                owner_id=current_owner_id,
                experiment_id=experiment_id,
                manifest=manifest,
            )
            if manifest is not None:
                snapshot = constrain_snapshot_to_manifest(snapshot, manifest)
            snapshots.append(snapshot)
        result = regional_metric_inputs_from_snapshots(
            tuple(snapshots),
            input_revision=input_revision,
            window_end=window_end,
            complete_through_boundary=complete_through_boundary,
        )
        _LOG.debug(
            "regional_metric_evidence_loaded run_id=%s owner_count=%s "
            "trace_count=%s region_enabled=true",
            run_id,
            len(context.owner_ids),
            sum(len(snapshot.traces) for snapshot in snapshots),
        )
        return result


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
        regional_context=snapshot.regional_context,
        objective_complete_through_boundary=(
            snapshot.objective_complete_through_boundary
        ),
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


def regional_context_from_run(
    *,
    regions_spec: object | None,
    bodies: Sequence[object],
    known_location_ids: Sequence[object],
    owner_ids: Sequence[object],
    lifecycle_records: Sequence[object] = (),
) -> PersistedRegionalContext | None:
    """Project immutable bootstrap data into a neutral regional analysis DTO."""
    from agents.models import AgentId
    from world.identifiers import EntityId
    from world.lifecycle import AgentLifecycleRecord
    from world.models import AgentBody, LifeStatus
    from world.regions import RegionsMigrationSpec

    if regions_spec is None:
        return None
    if type(regions_spec) is not RegionsMigrationSpec:
        raise TypeError("regions_spec must be RegionsMigrationSpec or None")
    if isinstance(bodies, (str, bytes)) or not isinstance(bodies, Sequence):
        raise TypeError("bodies must be an ordered sequence")
    if isinstance(owner_ids, (str, bytes)) or not isinstance(owner_ids, Sequence):
        raise TypeError("owner_ids must be an ordered sequence")
    if isinstance(known_location_ids, (str, bytes)) or not isinstance(
        known_location_ids, Sequence
    ):
        raise TypeError("known_location_ids must be an ordered sequence")
    if isinstance(lifecycle_records, (str, bytes)) or not isinstance(
        lifecycle_records, Sequence
    ):
        raise TypeError("lifecycle_records must be an ordered sequence")
    stage_by_body: dict[str, tuple[str, str]] = {}
    for record in lifecycle_records:
        if type(record) is not AgentLifecycleRecord:
            raise TypeError("lifecycle_records entries must be AgentLifecycleRecord")
        stage_by_body[record.body_id.value] = (record.stage.value, record.cohort_id)
    placements = []
    for body in bodies:
        if type(body) is not AgentBody:
            raise TypeError("bodies entries must be AgentBody")
        stage, cohort = stage_by_body.get(body.entity_id.value, (None, None))
        placements.append(
            PersistedRegionalInitialPlacement(
                body_id=body.entity_id.value,
                location_id=body.location_id.value,
                alive=body.life_status is LifeStatus.ALIVE,
                stage_id=stage,
                cohort_id=cohort,
            )
        )
    owners: list[str] = []
    for item in owner_ids:
        if type(item) is AgentId:
            owners.append(item.value)
        elif type(item) is str:
            owners.append(item)
        else:
            raise TypeError("owner_ids entries must be AgentId or str")
    known_locations: list[str] = []
    for location in known_location_ids:
        if type(location) is EntityId:
            known_locations.append(location.value)
        elif type(location) is str:
            known_locations.append(location)
        else:
            raise TypeError("known_location_ids entries must be EntityId or str")
    return PersistedRegionalContext(
        region_ids=tuple(region.region_id for region in regions_spec.regions),
        known_location_ids=tuple(known_locations),
        locations=tuple(
            PersistedRegionalLocation(
                location_id=item.location_id.value,
                region_id=item.region_id,
            )
            for item in regions_spec.location_regions
        ),
        initial_placements=tuple(placements),
        owner_ids=tuple(owners),
        residence_min_ticks=regions_spec.residence_min_ticks,
    )


def regional_population_rows_from_events(
    events: Sequence[object],
) -> tuple[RegionalEventRow, ...]:
    """Project successful committed placement and lifecycle facts once."""
    from world.events import (
        AgentEnteredWorld,
        Died,
        Fled,
        JourneyArrived,
        LifecycleStageChanged,
        Moved,
        Transported,
    )

    if isinstance(events, (str, bytes)) or not isinstance(events, Sequence):
        raise TypeError("regional_population_rows_from_events: invalid_events")
    rows: list[RegionalEventRow] = []

    def add_relocation(
        event: WorldEvent,
        *,
        body_id: object,
        origin: object | None,
        destination: object | None,
        kind: str,
    ) -> None:
        body = _id_text_or_none(body_id)
        target = _id_text_or_none(destination)
        if body is None or target is None:
            raise EvidenceCompositionError("regional_relocation_identity_missing")
        rows.append(
            RegionalEventRow(
                tick=event.tick,
                sequence=event.sequence,
                kind="relocation",
                body_id=body,
                origin_location_id=_id_text_or_none(origin),
                destination_location_id=target,
                relocation_kind=kind,
            )
        )

    for event in events:
        if type(event) is not WorldEvent:
            raise EvidenceCompositionError("regional_event_type_invalid")
        details = event.details
        occurrence = event.occurrence
        if type(details) is Moved:
            origin = None if occurrence is None else occurrence.origin_location_id
            add_relocation(
                event,
                body_id=event.actor_id,
                origin=origin,
                destination=details.resulting_location_id or details.destination_id,
                kind="move",
            )
        elif type(details) is Transported:
            destination = details.destination_id
            origin = details.origin_location_id
            for body_id in sorted(
                (event.actor_id, details.target_id),
                key=lambda item: "" if item is None else item.value,
            ):
                add_relocation(
                    event,
                    body_id=body_id,
                    origin=origin,
                    destination=destination,
                    kind="transport",
                )
        elif type(details) is Fled:
            if details.success is not True:
                continue
            origin = None if occurrence is None else occurrence.origin_location_id
            add_relocation(
                event,
                body_id=event.actor_id,
                origin=origin,
                destination=details.destination_id,
                kind="flee",
            )
        elif type(details) is JourneyArrived:
            for body_id in details.participant_body_ids:
                add_relocation(
                    event,
                    body_id=body_id,
                    origin=details.origin_location_id,
                    destination=details.destination_location_id,
                    kind="journey",
                )
        elif type(details) is AgentEnteredWorld:
            rows.append(
                RegionalEventRow(
                    tick=event.tick,
                    sequence=event.sequence,
                    kind="entry",
                    body_id=details.body_id.value,
                    destination_location_id=details.location_id.value,
                )
            )
        elif type(details) is Died:
            rows.append(
                RegionalEventRow(
                    tick=event.tick,
                    sequence=event.sequence,
                    kind="death",
                    body_id=details.body_id.value,
                )
            )
        elif type(details) is LifecycleStageChanged:
            rows.append(
                RegionalEventRow(
                    tick=event.tick,
                    sequence=event.sequence,
                    kind="stage",
                    body_id=details.body_id.value,
                    stage_id=details.new_stage,
                )
            )
    rows.sort(key=lambda row: (row.tick, row.sequence, row.body_id, row.kind))
    _LOG.debug(
        "regional_population_events_projected event_count=%s row_count=%s",
        len(events),
        len(rows),
    )
    return tuple(rows)


def regional_population_input_from_snapshot(
    snapshot: PersistedAnalysisSnapshot,
    *,
    input_revision: str,
    window_end: int | None = None,
    complete_through_boundary: int | None = None,
) -> RegionalPopulationInput | None:
    """Build analysis input from detached bootstrap context and ordered events."""
    if type(snapshot) is not PersistedAnalysisSnapshot:
        raise TypeError("snapshot must be PersistedAnalysisSnapshot")
    context = snapshot.regional_context
    if context is None:
        return None
    resolved_window_end = window_end
    if resolved_window_end is None:
        resolved_window_end = snapshot.objective_complete_through_boundary
    if resolved_window_end is None:
        raise EvidenceCompositionError("regional_window_end_unavailable")
    resolved_complete_boundary = complete_through_boundary
    if resolved_complete_boundary is None:
        resolved_complete_boundary = snapshot.objective_complete_through_boundary
    return regional_population_input_from_context(
        context,
        events=snapshot.events,
        run_id=snapshot.run_id,
        input_revision=input_revision,
        window_end=resolved_window_end,
        complete_through_boundary=resolved_complete_boundary,
    )


def regional_metric_inputs_from_snapshots(
    snapshots: Sequence[PersistedAnalysisSnapshot],
    *,
    input_revision: str,
    window_end: int | None = None,
    complete_through_boundary: int | None = None,
) -> tuple[
    RegionalPopulationInput | None,
    tuple[RegionalDestinationEvidenceRow, ...] | None,
    int | None,
]:
    """Join owner-scoped detached slices without crossing objective authority."""
    from memory.models import MemoryTrace

    if isinstance(snapshots, (str, bytes)) or not isinstance(snapshots, Sequence):
        raise TypeError("snapshots must be an ordered sequence")
    if not snapshots:
        return None, None, None
    first = snapshots[0]
    if type(first) is not PersistedAnalysisSnapshot:
        raise TypeError("snapshot entries must be PersistedAnalysisSnapshot")
    context = first.regional_context
    if context is None:
        return None, None, None
    resolved_window_end = window_end
    if resolved_window_end is None:
        resolved_window_end = first.objective_complete_through_boundary
    if resolved_window_end is None:
        raise EvidenceCompositionError("regional_window_end_unavailable")
    resolved_complete_boundary = complete_through_boundary
    if resolved_complete_boundary is None:
        resolved_complete_boundary = first.objective_complete_through_boundary
    traces_by_owner_memory: dict[tuple[str, str], object] = {}
    for snapshot in snapshots:
        if type(snapshot) is not PersistedAnalysisSnapshot:
            raise TypeError("snapshot entries must be PersistedAnalysisSnapshot")
        if (
            snapshot.run_id != first.run_id
            or snapshot.regional_context != context
            or snapshot.events != first.events
            or snapshot.objective_complete_through_boundary
            != first.objective_complete_through_boundary
        ):
            raise EvidenceCompositionError("regional_snapshot_scope_mismatch")
        for trace in snapshot.traces:
            if type(trace) is not MemoryTrace:
                raise EvidenceCompositionError("regional_snapshot_trace_invalid")
            if trace.owner_id.value != snapshot.owner_id:
                raise EvidenceCompositionError("regional_snapshot_trace_owner_mismatch")
            key = trace.owner_id.value, trace.memory_id.value
            prior = traces_by_owner_memory.get(key)
            if prior is not None and prior != trace:
                raise EvidenceCompositionError("regional_snapshot_trace_conflict")
            traces_by_owner_memory[key] = trace
    traces = tuple(
        traces_by_owner_memory[key] for key in sorted(traces_by_owner_memory)
    )
    regional_input = regional_population_input_from_snapshot(
        first,
        input_revision=input_revision,
        window_end=resolved_window_end,
        complete_through_boundary=resolved_complete_boundary,
    )
    evidence_rows = regional_destination_evidence_rows_from_traces(traces)
    return regional_input, evidence_rows, len(context.owner_ids)


def regional_population_input_from_context(
    context: PersistedRegionalContext,
    *,
    events: Sequence[object],
    run_id: str,
    input_revision: str,
    window_end: int,
    complete_through_boundary: int | None = None,
) -> RegionalPopulationInput:
    if type(context) is not PersistedRegionalContext:
        raise TypeError("context must be PersistedRegionalContext")
    return RegionalPopulationInput(
        run_id=run_id,
        input_revision=input_revision,
        region_ids=context.region_ids,
        known_location_ids=context.known_location_ids,
        location_rows=tuple(
            RegionalLocationRow(item.location_id, item.region_id)
            for item in context.locations
        ),
        initial_placements=tuple(
            RegionalInitialPlacementRow(
                body_id=item.body_id,
                location_id=item.location_id,
                alive=item.alive,
                stage_id=item.stage_id,
                cohort_id=item.cohort_id,
            )
            for item in context.initial_placements
        ),
        events=regional_population_rows_from_events(events),
        residence_min_ticks=context.residence_min_ticks,
        window_end=window_end,
        complete_through_boundary=complete_through_boundary,
    )


def regional_destination_evidence_rows_from_traces(
    traces: Sequence[object],
) -> tuple[RegionalDestinationEvidenceRow, ...]:
    """Project destination-labeled trace metadata without proposition text."""
    from memory.models import MemoryTrace

    if isinstance(traces, (str, bytes)) or not isinstance(traces, Sequence):
        raise TypeError(
            "regional_destination_evidence_rows_from_traces: invalid_traces"
        )
    rows: list[RegionalDestinationEvidenceRow] = []
    for trace in traces:
        if type(trace) is not MemoryTrace:
            raise TypeError("regional destination traces must be MemoryTrace")
        if "destination" not in trace.context.tags:
            continue
        destination_ids = tuple(
            item.entity_id.value
            for item in trace.entities
            if item.label == "destination" and item.entity_id is not None
        )
        if not destination_ids:
            continue
        region_id = next(
            (
                item.concept.removeprefix("region_id:")
                for item in trace.concepts
                if item.concept.startswith("region_id:")
            ),
            None,
        )
        for destination_id in destination_ids:
            rows.append(
                RegionalDestinationEvidenceRow(
                    owner_id=trace.owner_id.value,
                    destination_id=destination_id,
                    region_id=region_id,
                    source_kind=trace.provenance.kind.value,
                    source_tick=trace.provenance.source_tick,
                    confidence=trace.confidence,
                )
            )
    rows.sort(
        key=lambda row: (
            row.owner_id,
            row.destination_id,
            row.source_tick,
            row.source_kind,
        )
    )
    return tuple(rows)


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
) -> OfflineConsolidationReport:
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
) -> ReflectionReport:
    """Map in-run reflection audits into count-only analysis inputs."""
    from analysis.reflection_metrics import ReflectionReport
    from simulation.cognition_contracts import ReflectionAudit

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
        raise TypeError("cultural_channel_rows_from_convention_habits: invalid_rows")
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
    _LOG.debug("norm_belief_rows_built ledgers=%s rows=%s", len(ledgers), len(rows))
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
                    "variant_count": len(getattr(belief, "competing_variant_ids", ())),
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
        genre = getattr(artifact, "record_genre", None)
        genre_text = _id_text_or_none(getattr(genre, "value", genre))
        integrity = getattr(artifact, "integrity", None)
        integrity_text = _id_text_or_none(getattr(integrity, "value", integrity))
        parent_id = _id_text_or_none(getattr(artifact, "parent_artifact_id", None))
        source_id = _id_text_or_none(getattr(artifact, "source_artifact_id", None))
        author_id = _id_text_or_none(getattr(artifact, "author_id", None))
        created_tick = getattr(artifact, "created_tick", None)
        copy_generation = getattr(artifact, "copy_generation", None)
        annotation_revisions = getattr(artifact, "annotation_revisions", None)
        lost_mark_count = getattr(artifact, "lost_mark_count", None)
        row: dict[str, object] = {
            "tick": tick,
            "artifact_id": _id_text(getattr(artifact, "artifact_id", None)),
            "kind": kind_text,
            "content_revision": int(getattr(artifact, "content_revision", 0) or 0),
            "present": bool(present),
            "marks": marks,
        }
        durable_signal = (
            genre_text is not None
            or parent_id is not None
            or (
                isinstance(copy_generation, int)
                and not isinstance(copy_generation, bool)
                and copy_generation > 0
            )
            or (integrity_text is not None and integrity_text != "intact")
            or (
                isinstance(annotation_revisions, int)
                and not isinstance(annotation_revisions, bool)
                and annotation_revisions > 0
            )
            or (
                isinstance(lost_mark_count, int)
                and not isinstance(lost_mark_count, bool)
                and lost_mark_count > 0
            )
        )
        if durable_signal:
            if genre_text is not None:
                row["record_genre"] = genre_text
            if parent_id is not None:
                row["parent_artifact_id"] = parent_id
            if source_id is not None:
                row["source_artifact_id"] = source_id
            if (
                isinstance(copy_generation, int)
                and not isinstance(copy_generation, bool)
                and copy_generation >= 0
            ):
                row["copy_generation"] = copy_generation
            if integrity_text is not None:
                row["integrity"] = integrity_text
            if (
                isinstance(annotation_revisions, int)
                and not isinstance(annotation_revisions, bool)
                and annotation_revisions >= 0
            ):
                row["annotation_revisions"] = annotation_revisions
            if (
                isinstance(lost_mark_count, int)
                and not isinstance(lost_mark_count, bool)
                and lost_mark_count >= 0
            ):
                row["lost_mark_count"] = lost_mark_count
            if author_id is not None:
                row["author_id"] = author_id
            location_id = _id_text_or_none(getattr(artifact, "location_id", None))
            if location_id is not None:
                row["location_id"] = location_id
            if (
                isinstance(created_tick, int)
                and not isinstance(created_tick, bool)
                and created_tick >= 0
            ):
                row["created_tick"] = created_tick
        rows.append(row)
    _LOG.debug(
        "artifact_objective_rows_built artifacts=%s rows=%s present=%s",
        len(values),
        len(rows),
        present,
    )
    return tuple(rows)


def possession_channel_active(config: object) -> bool:
    """True only when the runner object is present. Not an heir rule."""
    return getattr(config, "possession_succession", None) is not None


def structured_commitments_channel_active(config: object) -> bool:
    """True only when the runner object is present. Not a collection rule."""
    return getattr(config, "structured_commitments", None) is not None


def subjective_valuation_channel_active(config: object) -> bool:
    """True only when the runner object is present. Not a posted number."""
    return getattr(config, "subjective_valuation", None) is not None


def technique_node_rows_from_resources(
    resources: Sequence[object] | None,
) -> tuple[dict[str, object], ...] | None:
    """Detached resource-node rows. ``None`` when the lifecycle channel is off."""
    if resources is None:
        return None
    rows: list[dict[str, object]] = []
    for resource in resources:
        name = _id_text_or_none(getattr(resource, "name", None))
        location_id = _id_text_or_none(getattr(resource, "location_id", None))
        quantity = getattr(resource, "quantity", None)
        if name is None or location_id is None or isinstance(quantity, bool):
            continue
        if not isinstance(quantity, (int, float)):
            continue
        rows.append(
            {"name": name, "location_id": location_id, "quantity": float(quantity)}
        )
    _LOG.debug(
        "technique_lifecycle_harvest node_count=%s item_count=%s "
        "artifact_location_rows=%s",
        len(rows),
        0,
        0,
    )
    return tuple(rows)


def technique_item_rows_from_items(
    items: Sequence[object] | None,
    tool_marks: Sequence[object] | None = None,
) -> tuple[dict[str, object], ...] | None:
    """Detached item rows including inventory on dead holders."""
    if items is None:
        return None
    roles: dict[str, str] = {}
    for mark in tool_marks or ():
        item_id = _id_text_or_none(getattr(mark, "item_id", None))
        role = _id_text_or_none(getattr(getattr(mark, "role", None), "value", None))
        if role is None:
            role = _id_text_or_none(getattr(mark, "role", None))
        if item_id is not None and role is not None:
            roles[item_id] = role
    rows: list[dict[str, object]] = []
    for item in items:
        item_id = _id_text_or_none(getattr(item, "entity_id", None))
        kind = getattr(item, "kind", None)
        rows.append(
            {
                "item_kind": _id_text_or_none(getattr(kind, "value", kind)),
                "name": _id_text_or_none(getattr(item, "name", None)),
                "tool_role": roles.get(item_id or ""),
                "location_id": _id_text_or_none(getattr(item, "location_id", None)),
                "holder_id": _id_text_or_none(getattr(item, "holder_id", None)),
            }
        )
    return tuple(rows)


_DURABLE_EVENT_KINDS: Final[frozenset[str]] = frozenset(
    {
        "artifact_copied",
        "artifact_annotated",
        "artifact_damaged",
        "artifact_partially_lost",
        "artifact_destroyed",
    }
)


def durable_record_event_rows_from_events(
    events: Sequence[object],
) -> tuple[dict[str, object], ...]:
    """Copy durable copy/annotate/damage/destroy event rows (no mark payloads)."""
    if isinstance(events, (str, bytes)) or not isinstance(events, Sequence):
        raise TypeError("durable_record_event_rows_from_events: invalid_events")
    rows: list[dict[str, object]] = []
    for event in events:
        details = _event_details(event)
        kind = (
            _id_text_or_none(getattr(details, "kind", None))
            or _event_kind_name(event).lower()
        )
        if kind not in _DURABLE_EVENT_KINDS:
            continue
        tick = getattr(event, "tick", None)
        row: dict[str, object] = {
            "kind": kind,
            "tick": tick if type(tick) is int and not isinstance(tick, bool) else 0,
        }
        for field in (
            "artifact_id",
            "child_artifact_id",
            "parent_artifact_id",
            "source_artifact_id",
            "fidelity_mode",
            "record_genre",
            "integrity",
            "prior_integrity",
            "next_integrity",
        ):
            token = _id_text_or_none(getattr(details, field, None))
            if token is not None:
                row[field] = token
        for field in (
            "copy_generation",
            "content_revision",
            "annotation_revisions",
            "lost_mark_count",
            "lost_mark_count_delta",
            "marks_remaining",
        ):
            value = getattr(details, field, None)
            if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
                row[field] = value
        tombstone = getattr(details, "tombstone", None)
        if type(tombstone) is bool:
            row["tombstone"] = tombstone
        rows.append(row)
    _LOG.debug(
        "durable_record_event_rows_built event_count=%s durable_count=%s",
        len(events),
        len(rows),
    )
    return tuple(rows)


def death_ticks_by_body_from_events(
    events: Sequence[object],
) -> dict[str, int]:
    """Public wrapper: body_id → first death tick from Died events."""
    if isinstance(events, (str, bytes)) or not isinstance(events, Sequence):
        raise TypeError("death_ticks_by_body_from_events: invalid_events")
    return _death_ticks_from_events(events)


_REPOSITORY_EVENT_KINDS: Final[frozenset[str]] = frozenset(
    {
        "repository_established",
        "repository_member_deposited",
        "repository_member_retrieved",
        "repository_maintained",
        "repository_indexed",
        "repository_neglected",
    }
)
_REPOSITORY_DENY_COMMANDS: Final[Mapping[str, str]] = {
    "deposit_record": "deposit_denied",
    "retrieve_record": "retrieve_denied",
}


def repository_objective_rows_from_repositories(
    repositories: Sequence[object] | Mapping[object, object],
) -> tuple[dict[str, object], ...]:
    """Copy objective repository rows (no cultural labels / mark payloads)."""
    if isinstance(repositories, Mapping):
        values: Sequence[object] = tuple(repositories.values())
    elif isinstance(repositories, (str, bytes)) or not isinstance(
        repositories, Sequence
    ):
        raise TypeError(
            "repository_objective_rows_from_repositories: invalid_repositories"
        )
    else:
        values = repositories
    rows: list[dict[str, object]] = []
    for repository in values:
        repository_id = _id_text_or_none(getattr(repository, "repository_id", None))
        location_id = _id_text_or_none(getattr(repository, "location_id", None))
        if repository_id is None or location_id is None:
            continue
        status = _id_text_or_none(getattr(repository, "status", None)) or "intact"
        access_mode = (
            _id_text_or_none(getattr(repository, "access_mode", None)) or "open"
        )
        members = getattr(repository, "member_artifact_ids", ())
        if isinstance(members, (str, bytes)) or not isinstance(members, Sequence):
            members = ()
        member_ids = tuple(
            token for item in members if (token := _id_text_or_none(item)) is not None
        )
        index_entries = getattr(repository, "index_entries", ())
        if isinstance(index_entries, (str, bytes)) or not isinstance(
            index_entries, Sequence
        ):
            index_entries = ()
        index_artifact_ids: list[str] = []
        for entry in index_entries:
            artifact_token = _id_text_or_none(getattr(entry, "artifact_id", None))
            if artifact_token is None and isinstance(entry, Mapping):
                artifact_token = _id_text_or_none(entry.get("artifact_id"))
            if artifact_token is not None:
                index_artifact_ids.append(artifact_token)
        member_set = set(member_ids)
        dangling = sum(
            1 for artifact_id in index_artifact_ids if artifact_id not in member_set
        )
        founders_raw = getattr(repository, "founder_ids", ())
        if isinstance(founders_raw, (str, bytes)) or not isinstance(
            founders_raw, Sequence
        ):
            founders_raw = ()
        founder_ids = tuple(
            token
            for item in founders_raw
            if (token := _id_text_or_none(item)) is not None
        )
        established = getattr(repository, "established_tick", 0)
        last_maintained = getattr(repository, "last_maintained_tick", 0)
        neglect_streak = getattr(repository, "neglect_streak", 0)
        row: dict[str, object] = {
            "repository_id": repository_id,
            "location_id": location_id,
            "structure_id": _id_text_or_none(getattr(repository, "structure_id", None)),
            "status": status,
            "access_mode": access_mode,
            "member_count": len(member_ids),
            "index_entry_count": len(index_artifact_ids),
            "dangling_index_entry_count": dangling,
            "founder_ids": founder_ids,
            "established_tick": (
                established
                if type(established) is int and not isinstance(established, bool)
                else 0
            ),
            "last_maintained_tick": (
                last_maintained
                if type(last_maintained) is int
                and not isinstance(last_maintained, bool)
                else 0
            ),
            "neglect_streak": (
                neglect_streak
                if type(neglect_streak) is int and not isinstance(neglect_streak, bool)
                else 0
            ),
        }
        rows.append(row)
    _LOG.debug(
        "repository_objective_rows_built repository_count=%s rows=%s "
        "source_kind=knowledge_repositories",
        len(values),
        len(rows),
    )
    return tuple(rows)


def repository_event_rows_from_events(
    events: Sequence[object],
) -> tuple[dict[str, object], ...]:
    """Copy repository establish/membership/access/index/neglect event rows."""
    if isinstance(events, (str, bytes)) or not isinstance(events, Sequence):
        raise TypeError("repository_event_rows_from_events: invalid_events")
    rows: list[dict[str, object]] = []
    for event in events:
        details = _event_details(event)
        kind = (
            _id_text_or_none(getattr(details, "kind", None))
            or _event_kind_name(event).lower()
        )
        if kind not in _REPOSITORY_EVENT_KINDS:
            continue
        tick = getattr(event, "tick", None)
        row: dict[str, object] = {
            "event_kind": kind,
            "kind": kind,
            "tick": tick if type(tick) is int and not isinstance(tick, bool) else 0,
        }
        for field in (
            "repository_id",
            "artifact_id",
            "actor_id",
            "prior_status",
            "next_status",
            "mode",
            "access_mode",
        ):
            token = _id_text_or_none(getattr(details, field, None))
            if token is not None:
                row[field] = token
        for field in (
            "member_count",
            "index_entry_count",
            "index_entries_dropped",
            "neglect_streak",
            "established_tick",
            "last_maintained_tick",
            "revision_bump",
        ):
            value = getattr(details, field, None)
            if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
                row[field] = value
        rows.append(row)
    _LOG.debug(
        "repository_event_rows_built event_count=%s repository_count=%s "
        "source_kind=knowledge_repositories",
        len(events),
        len(rows),
    )
    return tuple(rows)


def repository_event_rows_from_resolutions(
    resolutions: Sequence[object],
) -> tuple[dict[str, object], ...]:
    """Synthesize deposit/retrieve deny rows from rejected action resolutions."""
    if isinstance(resolutions, (str, bytes)) or not isinstance(resolutions, Sequence):
        raise TypeError("repository_event_rows_from_resolutions: invalid_resolutions")
    rows: list[dict[str, object]] = []
    for resolution in resolutions:
        command_kind = _id_text_or_none(getattr(resolution, "command_kind", None))
        if command_kind is None:
            command = getattr(resolution, "command", None)
            command_kind = _id_text_or_none(getattr(command, "kind", None))
        if command_kind is None or command_kind not in _REPOSITORY_DENY_COMMANDS:
            continue
        status_token = _id_text_or_none(getattr(resolution, "status", None))
        if status_token != "rejected":
            continue
        deny_kind = _REPOSITORY_DENY_COMMANDS[command_kind]
        tick = getattr(resolution, "tick", 0)
        if hasattr(tick, "value"):
            tick = tick.value
        row: dict[str, object] = {
            "event_kind": deny_kind,
            "kind": deny_kind,
            "tick": tick if type(tick) is int and not isinstance(tick, bool) else 0,
        }
        command = getattr(resolution, "command", None)
        if command is not None:
            for field in ("repository_id", "artifact_id"):
                token = _id_text_or_none(getattr(command, field, None))
                if token is not None:
                    row[field] = token
        actor = _id_text_or_none(getattr(resolution, "agent_id", None))
        if actor is not None:
            row["actor_id"] = actor
        reason = _id_text_or_none(getattr(resolution, "reason_code", None))
        if reason is None:
            reason = _id_text_or_none(getattr(resolution, "reason", None))
        if reason is not None:
            row["reason_code"] = reason
        rows.append(row)
    _LOG.debug(
        "repository_resolution_deny_rows_built resolution_count=%s deny_count=%s "
        "source_kind=knowledge_repositories",
        len(resolutions),
        len(rows),
    )
    return tuple(rows)


def knowledge_genealogy_harvest_from_run(
    *,
    knowledge_genealogy_spec: object | None,
    practical_knowledge_audits: Sequence[object] | None = None,
    events: Sequence[object] | None = None,
    death_ticks: Mapping[str, int] | None = None,
) -> dict[str, object] | None:
    """Build genealogy harvest when knowledge_genealogy channel is on.

    Derives death_ticks from events when layers/durable absent. Returns None
    when the genealogy object is absent.
    """
    if knowledge_genealogy_spec is None:
        _LOG.debug("knowledge_genealogy_harvest_skip reason_code=genealogy_absent")
        return None
    audits = (
        () if practical_knowledge_audits is None else tuple(practical_knowledge_audits)
    )
    deaths = dict(death_ticks or {})
    if events is not None:
        derived = _death_ticks_from_events(events)
        for agent, tick in derived.items():
            if agent not in deaths or tick < deaths[agent]:
                deaths[agent] = tick
    if not audits:
        _LOG.warning(
            "knowledge_genealogy_harvest_empty "
            "reason_code=genealogy_enabled_rows_empty audit_count=%s",
            0,
        )
    origin_counts: dict[str, int] = {}
    for row in audits:
        origin = getattr(row, "origin", None)
        token = getattr(origin, "value", origin)
        if type(token) is str:
            origin_counts[token] = origin_counts.get(token, 0) + 1
    _LOG.debug(
        "knowledge_genealogy_harvest_built audit_count=%s death_count=%s "
        "origin_counts=%s source_kind=knowledge_genealogy",
        len(audits),
        len(deaths),
        origin_counts,
    )
    return {
        "practical_knowledge_audits": audits,
        "death_ticks": deaths,
        "origin_counts": origin_counts,
    }


def knowledge_repository_harvest_from_run(
    *,
    knowledge_repositories_spec: object | None,
    repositories: Sequence[object] | Mapping[object, object] | None = None,
    events: Sequence[object] | None = None,
    resolutions: Sequence[object] | None = None,
    inaccessible_expectations: Sequence[object] | None = None,
) -> dict[str, object] | None:
    """Build repository harvest payload when knowledge_repositories channel is on.

    Returns None when the repository object is absent. Never imports world._*.
    """
    if knowledge_repositories_spec is None:
        _LOG.debug("knowledge_repository_harvest_skip reason_code=repository_absent")
        return None
    objective_rows = (
        ()
        if repositories is None
        else repository_objective_rows_from_repositories(repositories)
    )
    event_rows = () if events is None else repository_event_rows_from_events(events)
    if resolutions is not None:
        event_rows = event_rows + repository_event_rows_from_resolutions(resolutions)
    deaths: dict[str, int] = (
        {} if events is None else death_ticks_by_body_from_events(events)
    )
    if not objective_rows and not event_rows:
        _LOG.warning(
            "knowledge_repository_harvest_empty "
            "reason_code=repository_enabled_rows_empty "
            "repository_count=%s event_count=%s",
            0 if repositories is None else len(repositories),
            0 if events is None else len(events),
        )
    _LOG.debug(
        "knowledge_repository_harvest_built repository_count=%s event_count=%s "
        "death_count=%s source_kind=knowledge_repositories",
        len(objective_rows),
        len(event_rows),
        len(deaths),
    )
    payload: dict[str, object] = {
        "repository_objective_rows": objective_rows,
        "repository_event_rows": event_rows,
        "founder_death_ticks": deaths,
    }
    if inaccessible_expectations is not None:
        payload["inaccessible_expectations"] = tuple(inaccessible_expectations)
    return payload


def durable_record_harvest_from_run(
    *,
    durable_records_spec: object | None,
    artifacts: Sequence[object] | Mapping[object, object] | None = None,
    events: Sequence[object] | None = None,
    tick: int = 0,
    false_record_expectations: Sequence[object] | None = None,
) -> dict[str, object] | None:
    """Build durable harvest payload when durable_records channel is on.

    Returns None when the durable object is absent. Never imports world._*.
    """
    if durable_records_spec is None:
        _LOG.debug("durable_record_harvest_skip reason_code=durable_absent")
        return None
    tick = require_exact_nonneg_int("tick", tick)
    record_rows = (
        ()
        if artifacts is None
        else artifact_objective_rows_from_artifacts(artifacts, tick=tick)
    )
    event_rows = () if events is None else durable_record_event_rows_from_events(events)
    deaths: dict[str, int] = (
        {} if events is None else death_ticks_by_body_from_events(events)
    )
    if not record_rows and not event_rows:
        _LOG.warning(
            "durable_record_harvest_empty reason_code=durable_enabled_rows_empty "
            "artifact_count=%s event_count=%s",
            0 if artifacts is None else len(artifacts),
            0 if events is None else len(events),
        )
    _LOG.debug(
        "durable_record_harvest_built record_count=%s event_count=%s "
        "death_count=%s source_kind=durable_records",
        len(record_rows),
        len(event_rows),
        len(deaths),
    )
    payload: dict[str, object] = {
        "durable_record_rows": record_rows,
        "durable_record_event_rows": event_rows,
        "death_ticks_by_body": deaths,
    }
    if false_record_expectations is not None:
        payload["false_record_expectations"] = tuple(false_record_expectations)
    return payload


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
        soft_forgotten = getattr(trace, "soft_forgotten", None)
        if soft_forgotten is not None:
            forgotten = bool(soft_forgotten)
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
        entries = getattr(ledger, "interpretations", getattr(ledger, "entries", ()))
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
    _LOG.debug("spatial_claim_rows_built ledgers=%s rows=%s", len(ledgers), len(rows))
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
        found = _id_text_or_none(getattr(occurrence, "destination_location_id", None))
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


@dataclass(frozen=True, slots=True)
class SocietyAnalysisInputs:
    """Detached candidate-society lanes ready for metric assembly."""

    emission: SocietyEmissionResult
    divergence: SocietyDivergenceResult
    isolation: SocietyIsolationResult
    living_person_ids: tuple[str, ...]


def society_residence_rows_from_regional_input(
    regional_input: RegionalPopulationInput,
    *,
    tick: int,
) -> tuple[SocietyResidenceRow, ...]:
    """Project final living region assignment from detached regional facts."""
    if type(regional_input) is not RegionalPopulationInput:
        raise TypeError("regional_input must be RegionalPopulationInput")
    tick = require_exact_nonneg_int("tick", tick)
    region_by_location = {
        row.location_id: row.region_id for row in regional_input.location_rows
    }
    final_region: dict[str, str] = {}
    alive: dict[str, bool] = {}
    for placement_row in regional_input.initial_placements:
        alive[placement_row.body_id] = placement_row.alive
        region = region_by_location.get(placement_row.location_id)
        if region is not None:
            final_region[placement_row.body_id] = region
    for event_row in regional_input.events:
        if (
            event_row.kind in {"relocation", "entry"}
            and event_row.destination_location_id
        ):
            region = region_by_location.get(event_row.destination_location_id)
            if region is not None:
                final_region[event_row.body_id] = region
            alive.setdefault(event_row.body_id, True)
        elif event_row.kind == "death":
            alive[event_row.body_id] = False
    rows = tuple(
        SocietyResidenceRow(
            person_id=body_id,
            region_id=final_region[body_id],
            first_tick=0,
            last_tick=tick,
        )
        for body_id in sorted(final_region)
        if alive.get(body_id, True)
    )
    _LOG.debug("society_residence_rows count=%s tick=%s", len(rows), tick)
    return rows


def society_journeys_from_regional_input(
    regional_input: RegionalPopulationInput,
) -> tuple[SocietyJourneyRow, ...]:
    """Project completed interregional journey arrivals as audit evidence."""
    if type(regional_input) is not RegionalPopulationInput:
        raise TypeError("regional_input must be RegionalPopulationInput")
    region_by_location = {
        row.location_id: row.region_id for row in regional_input.location_rows
    }
    rows: list[SocietyJourneyRow] = []
    for row in regional_input.events:
        if row.kind != "relocation" or row.relocation_kind != "journey":
            continue
        origin = region_by_location.get(row.origin_location_id or "")
        destination = region_by_location.get(row.destination_location_id or "")
        if origin is None or destination is None or origin == destination:
            continue
        rows.append(
            SocietyJourneyRow(
                person_id=row.body_id,
                origin_region_id=origin,
                destination_region_id=destination,
                arrival_tick=row.tick,
            )
        )
    return tuple(rows)


def society_interaction_edges_from_events(
    events: Sequence[object] | None,
) -> tuple[SocietyEdgeRow, ...]:
    """Project communication and exchange participation edges."""
    rows: list[SocietyEdgeRow] = []
    for edge in _communication_edges_from_events(events or ()):
        speaker = _id_text_or_none(getattr(edge, "speaker_id", None))
        listener = _id_text_or_none(getattr(edge, "listener_id", None))
        tick = getattr(edge, "at_tick", 0)
        if isinstance(tick, bool) or type(tick) is not int:
            tick = 0
        if speaker and listener and speaker != listener:
            rows.append(SocietyEdgeRow(speaker, listener, tick, lane="interaction"))
    for event in events or ():
        details = _event_details(event)
        kind = _event_kind_name(event).lower()
        raw_kind = getattr(event, "kind", None)
        if isinstance(raw_kind, str) and raw_kind:
            kind = raw_kind.lower()
        if kind not in {
            "exchangeproposed",
            "exchangecompleted",
            "negotiateexchange",
            "exchangeaccepted",
        }:
            continue
        tick = getattr(event, "tick", 0)
        if isinstance(tick, bool) or type(tick) is not int:
            tick = 0
        source = _id_text_or_none(
            getattr(details, "proposer_id", None)
            or getattr(event, "actor_id", None)
            or getattr(details, "actor_id", None)
        )
        target = _id_text_or_none(
            getattr(details, "recipient_id", None)
            or getattr(details, "partner_id", None)
            or getattr(details, "target_id", None)
        )
        if source and target and source != target:
            rows.append(SocietyEdgeRow(source, target, tick, lane="interaction"))
    _LOG.debug("society_interaction_edges count=%s", len(rows))
    return tuple(rows)


def society_trust_edges_from_relationship_rows(
    rows: Sequence[object] | None,
) -> tuple[SocietyEdgeRow, ...]:
    """Project latest active nonnegative trust into detached trust edges."""
    latest: dict[tuple[str, str], object] = {}
    for row in sorted(
        rows or (),
        key=lambda item: (
            getattr(item, "source_id", ""),
            getattr(item, "target_id", ""),
            getattr(item, "logical_tick", 0),
            getattr(item, "ordinal", 0),
        ),
    ):
        if getattr(row, "activation_state", "active") != "active":
            continue
        trust = getattr(row, "trust", None)
        if not isinstance(trust, (int, float)) or isinstance(trust, bool):
            continue
        if float(trust) <= 0.0:
            continue
        source = _id_text_or_none(getattr(row, "source_id", None))
        target = _id_text_or_none(getattr(row, "target_id", None))
        if source is None or target is None or source == target:
            continue
        latest[(source, target)] = row
    edges: list[SocietyEdgeRow] = []
    for (source, target), row in sorted(latest.items()):
        tick = getattr(row, "logical_tick", 0)
        if isinstance(tick, bool) or type(tick) is not int:
            tick = 0
        trust_value = getattr(row, "trust", 0.0)
        trust_weight = 1.0
        if isinstance(trust_value, (int, float)) and not isinstance(trust_value, bool):
            trust_weight = max(float(trust_value), 0.0)
        edges.append(
            SocietyEdgeRow(
                source,
                target,
                tick,
                lane="trust",
                weight=trust_weight,
            )
        )
    _LOG.debug("society_trust_edges count=%s", len(edges))
    return tuple(edges)


def society_digest_rows_from_channel_rows(
    dimension: str,
    rows: Sequence[object] | None,
) -> tuple[SocietyDigestRow, ...]:
    """Project detached channel rows into opaque per-person digest rows."""
    projected: list[SocietyDigestRow] = []
    for row in rows or ():
        person = _id_text_or_none(
            getattr(row, "person_id", None)
            or getattr(row, "agent_id", None)
            or getattr(row, "owner_id", None)
        )
        token = _id_text_or_none(
            getattr(row, "token", None)
            or getattr(row, "digest_id_token", None)
            or getattr(row, "head_token", None)
            or getattr(row, "variant_fingerprint", None)
            or getattr(row, "fingerprint", None)
            or getattr(row, "kind_token", None)
        )
        if person is None or token is None:
            continue
        projected.append(
            SocietyDigestRow(dimension=dimension, person_id=person, token=token)
        )
    return tuple(projected)


_TAG_DIMENSION_PREFIXES: Final[dict[str, str]] = {
    "term": "vocabulary",
    "name": "vocabulary",
    "vocabulary": "vocabulary",
    "norm": "norms",
    "habit": "conventions",
    "convention": "conventions",
    "technique": "technology",
    "skill": "technology",
    "story": "stories",
    "narrative": "stories",
    "project": "institutions",
    "institution": "institutions",
    "public_good": "institutions",
    "trade": "trade",
    "exchange": "trade",
}


def _dimension_for_token(token: str) -> str | None:
    key = token.split(":", 1)[0].strip().lower()
    return _TAG_DIMENSION_PREFIXES.get(key)


def society_digest_rows_from_snapshot(
    snapshot: PersistedAnalysisSnapshot,
    *,
    dimension_sources: Mapping[str, Sequence[object]] | None = None,
) -> tuple[SocietyDigestRow, ...]:
    """Derive opaque per-dimension digest rows from detached traces and rows."""
    if type(snapshot) is not PersistedAnalysisSnapshot:
        raise TypeError("snapshot must be PersistedAnalysisSnapshot")
    rows: list[SocietyDigestRow] = []
    for channel_dimension, source_rows in (dimension_sources or {}).items():
        if channel_dimension not in SOCIETY_DIMENSIONS:
            continue
        rows.extend(
            society_digest_rows_from_channel_rows(channel_dimension, source_rows)
        )
    for trace in snapshot.traces:
        person = _id_text_or_none(
            getattr(getattr(trace, "owner_id", None), "value", None)
        )
        if person is None:
            continue
        context = getattr(trace, "context", None)
        tags = tuple(getattr(context, "tags", ()) or ())
        for tag in tags:
            token = _id_text_or_none(tag)
            if token is None:
                continue
            token_dimension = _dimension_for_token(token)
            if token_dimension is None:
                continue
            rows.append(
                SocietyDigestRow(
                    dimension=token_dimension, person_id=person, token=token
                )
            )
        for entity in getattr(trace, "entities", ()) or ():
            entity_id = getattr(entity, "entity_id", None)
            token = _id_text_or_none(getattr(entity_id, "value", None))
            label = _id_text_or_none(getattr(entity, "label", None))
            if token is None or label is None:
                continue
            token_dimension = _dimension_for_token(label)
            if token_dimension is None:
                continue
            rows.append(
                SocietyDigestRow(
                    dimension=token_dimension, person_id=person, token=token
                )
            )
    deduped = {(row.dimension, row.person_id, row.token): row for row in rows}
    ordered = tuple(deduped[key] for key in sorted(deduped))
    _LOG.debug("society_digest_rows count=%s", len(ordered))
    return ordered


def _society_evidence_edges_from_events(
    events: Sequence[object] | None,
) -> tuple[SocietyEvidenceEdge, ...]:
    edges: list[SocietyEvidenceEdge] = []
    for index, edge in enumerate(society_interaction_edges_from_events(events)):
        edges.append(
            SocietyEvidenceEdge(
                edge_id=f"evidence-{index:06d}",
                kind="communication",
                source_person_id=edge.source_person_id,
                target_person_id=edge.target_person_id,
                tick=edge.tick,
            )
        )
    return tuple(edges)


def society_emission_inputs_from_context(
    *,
    run_id: str,
    input_revision: str,
    tick: int,
    living_person_ids: Sequence[str],
    residence_rows: Sequence[object] | None = None,
    interaction_edges: Sequence[object] | None = None,
    trust_edges: Sequence[object] | None = None,
    dimension_rows: Sequence[SocietyDigestRow] | None = None,
    evidence_edges: Sequence[SocietyEvidenceEdge] | None = None,
    journeys: Sequence[SocietyJourneyRow] | None = None,
) -> SocietyAnalysisInputs:
    """Build all three society-analysis results from detached lane rows."""
    emission = compute_candidate_communities(
        residence_rows,
        interaction_edges,
        trust_edges,
        living_person_ids,
        tick,
    )
    divergence = compute_society_divergence(emission.communities, dimension_rows or ())
    isolation = compute_society_isolation(
        emission.communities, evidence_edges or (), journeys or ()
    )
    _LOG.debug(
        "society_analysis_context_built run_id=%s community_count=%s "
        "singleton_count=%s dimension_present=%s cross_edges=%s journeys=%s",
        run_id,
        len(emission.communities),
        len(emission.singleton_person_ids),
        len(divergence.dimensions_present),
        len(isolation.rows),
        len(journeys or ()),
    )
    return SocietyAnalysisInputs(
        emission=emission,
        divergence=divergence,
        isolation=isolation,
        living_person_ids=tuple(sorted(living_person_ids)),
    )


def society_emission_inputs_from_snapshot(
    snapshot: PersistedAnalysisSnapshot,
    *,
    input_revision: str,
    tick: int | None = None,
    manifest: EvidenceManifest | None = None,
    dimension_rows: Sequence[SocietyDigestRow] | None = None,
    dimension_sources: Mapping[str, Sequence[object]] | None = None,
    trust_edges: Sequence[object] | None = None,
    evidence_edges: Sequence[SocietyEvidenceEdge] | None = None,
) -> SocietyAnalysisInputs | None:
    """Compose detached snapshot evidence without persistence imports."""
    if type(snapshot) is not PersistedAnalysisSnapshot:
        raise TypeError("snapshot must be PersistedAnalysisSnapshot")
    if manifest is not None:
        snapshot = constrain_snapshot_to_manifest(snapshot, manifest)
    context = snapshot.regional_context
    if context is None:
        return None
    resolved_tick = tick
    if resolved_tick is None:
        resolved_tick = snapshot.objective_complete_through_boundary
    if resolved_tick is None:
        raise EvidenceCompositionError("society_window_end_unavailable")
    regional_input = regional_population_input_from_snapshot(
        snapshot,
        input_revision=input_revision,
        window_end=resolved_tick,
    )
    if regional_input is None:
        return None
    residence = society_residence_rows_from_regional_input(
        regional_input, tick=resolved_tick
    )
    interaction = society_interaction_edges_from_events(snapshot.events)
    journeys = society_journeys_from_regional_input(regional_input)
    digest_rows = (
        tuple(dimension_rows)
        if dimension_rows is not None
        else society_digest_rows_from_snapshot(
            snapshot, dimension_sources=dimension_sources
        )
    )
    living = tuple(sorted(row.person_id for row in residence))
    derived_evidence = _society_evidence_edges_from_events(snapshot.events)
    return society_emission_inputs_from_context(
        run_id=snapshot.run_id,
        input_revision=input_revision,
        tick=resolved_tick,
        living_person_ids=living,
        residence_rows=residence,
        interaction_edges=interaction,
        trust_edges=trust_edges,
        dimension_rows=digest_rows,
        evidence_edges=tuple(derived_evidence) + tuple(evidence_edges or ()),
        journeys=journeys,
    )


def contact_episode_rows_from_events(
    events: Sequence[object] | None,
) -> tuple[ContactEpisodeRow, ...]:
    rows: list[ContactEpisodeRow] = []
    for event in events or ():
        details = _event_details(event)
        if details is None or getattr(details, "kind", None) != "contact_recorded":
            continue
        tick = getattr(event, "tick", 0)
        if isinstance(tick, bool) or type(tick) is not int:
            tick = 0
        rows.append(
            ContactEpisodeRow(
                participant_ids=tuple(
                    item.value for item in getattr(details, "participant_ids", ())
                ),
                present_ids=tuple(
                    item.value for item in getattr(details, "present_ids", ())
                ),
                location_id=details.location_id.value,
                tick=tick,
            )
        )
    return tuple(rows)


def contact_presence_rows_from_regional_input(
    regional_input: RegionalPopulationInput,
    *,
    window_end: int,
) -> tuple[ContactPresenceRow, ...]:
    """Fold initial placement, ordered relocations, entries, and deaths by tick."""
    if type(regional_input) is not RegionalPopulationInput:
        raise TypeError("regional_input must be RegionalPopulationInput")
    window_end = require_exact_nonneg_int("window_end", window_end)
    location: dict[str, str] = {
        row.body_id: row.location_id for row in regional_input.initial_placements
    }
    alive: dict[str, bool] = {
        row.body_id: row.alive for row in regional_input.initial_placements
    }
    by_tick: dict[int, list[RegionalEventRow]] = {}
    for event in regional_input.events:
        by_tick.setdefault(event.tick, []).append(event)
    rows: list[ContactPresenceRow] = []
    for tick in range(window_end + 1):
        for event in sorted(by_tick.get(tick, ()), key=lambda item: item.sequence):
            if event.kind in {"relocation", "entry"} and event.destination_location_id:
                location[event.body_id] = event.destination_location_id
                alive.setdefault(event.body_id, True)
            elif event.kind == "death":
                alive[event.body_id] = False
        for body_id in sorted(location):
            if alive.get(body_id, False):
                rows.append(ContactPresenceRow(body_id, location[body_id], tick))
    return tuple(rows)


def contact_interaction_rows_from_events(
    events: Sequence[object] | None,
    *,
    teaching_audits: Sequence[object] | None = None,
) -> tuple[ContactInteractionRow, ...]:
    rows: list[ContactInteractionRow] = []
    communication = {"talked", "asked", "told", "talk", "ask", "tell"}
    project_members: dict[str, set[str]] = {}
    for event in events or ():
        details = _event_details(event)
        if details is None:
            continue
        kind = _event_kind_text(event, details)
        if kind not in {"projectcontributed", "publicgoodmaintained"}:
            continue
        project_id = _id_text_or_none(getattr(details, "project_id", None))
        actor_id = _id_text_or_none(getattr(details, "actor_id", None))
        if project_id is not None and actor_id is not None:
            project_members.setdefault(project_id, set()).add(actor_id)
    for event in events or ():
        details = _event_details(event)
        if details is None:
            continue
        kind = _event_kind_text(event, details)
        tick = getattr(event, "tick", 0)
        if isinstance(tick, bool) or type(tick) is not int:
            tick = 0
        actor = _id_text_or_none(getattr(event, "actor_id", None))
        target = _id_text_or_none(getattr(event, "target_id", None))
        if actor is None:
            continue
        if kind in communication and target is not None:
            rows.append(ContactInteractionRow("communication", actor, target, tick))
        elif kind == "exchangecompleted":
            counterparty = _id_text_or_none(getattr(details, "counterparty_id", None))
            if counterparty is not None:
                rows.append(
                    ContactInteractionRow("exchange", actor, counterparty, tick)
                )
        elif kind == "helped" and target is not None:
            rows.append(ContactInteractionRow("cooperation", actor, target, tick))
        elif kind == "attacked" and target is not None:
            rows.append(ContactInteractionRow("conflict", actor, target, tick))
        elif kind == "kinshipedgerecorded":
            parent = _id_text_or_none(
                getattr(details, "parent_id", None)
                or getattr(details, "parent_agent_id", None)
            )
            child = _id_text_or_none(
                getattr(details, "child_id", None)
                or getattr(details, "child_agent_id", None)
            )
            if parent is not None and child is not None:
                rows.append(ContactInteractionRow("kinship", parent, child, tick))
        elif kind in {"projectcontributed", "publicgoodmaintained"}:
            project_id = _id_text_or_none(getattr(details, "project_id", None))
            kind_name = (
                "collective_project_contribution"
                if kind == "projectcontributed"
                else "public_good_maintenance"
            )
            rows.append(
                ContactInteractionRow(
                    kind_name,
                    actor,
                    None,
                    tick,
                    participant_person_ids=tuple(
                        sorted(project_members.get(project_id or "", set()))
                    ),
                )
            )
    for audit in teaching_audits or ():
        teacher = _id_text_or_none(
            getattr(audit, "teacher_agent_id", None)
            or getattr(audit, "teacher_id", None)
        )
        learner = _id_text_or_none(
            getattr(audit, "learner_agent_id", None)
            or getattr(audit, "learner_id", None)
            or getattr(audit, "owner_id", None)
        )
        tick = getattr(audit, "tick", 0)
        if teacher and learner and type(tick) is int and not isinstance(tick, bool):
            rows.append(ContactInteractionRow("teaching", teacher, learner, tick))
    return tuple(rows)


def _event_kind_text(event: object, details: object) -> str:
    raw_kind = getattr(event, "kind", None)
    kind = (
        raw_kind
        if isinstance(raw_kind, str) and raw_kind
        else getattr(details, "kind", None)
    )
    return str(kind).lower()


def contact_kinship_rows_from_events(
    events: Sequence[object] | None,
) -> tuple[ContactKinshipRow, ...]:
    rows: list[ContactKinshipRow] = []
    for event in events or ():
        details = _event_details(event)
        if details is None:
            continue
        kind = getattr(details, "kind", None)
        if str(kind).lower() != "kinshipedgerecorded":
            continue
        parent = _id_text_or_none(getattr(details, "parent_id", None))
        child = _id_text_or_none(getattr(details, "child_id", None))
        tick = getattr(event, "tick", 0)
        if parent and child and type(tick) is int and not isinstance(tick, bool):
            rows.append(ContactKinshipRow(parent, child, tick))
    return tuple(rows)


def contact_digest_rows_from_snapshot(
    snapshot: PersistedAnalysisSnapshot,
    *,
    dimension_sources: Mapping[str, Sequence[object]] | None = None,
) -> tuple[ContactDigestRow, ...]:
    rows: list[ContactDigestRow] = []
    for row in society_digest_rows_from_snapshot(
        snapshot, dimension_sources=dimension_sources
    ):
        rows.append(ContactDigestRow(row.dimension, row.person_id, row.token, 0))
    for trace in snapshot.traces:
        person = _id_text_or_none(
            getattr(getattr(trace, "owner_id", None), "value", None)
        )
        tick = getattr(trace, "created_tick", 0)
        if person is None or type(tick) is not int or isinstance(tick, bool):
            continue
        context = getattr(trace, "context", None)
        for tag in tuple(getattr(context, "tags", ()) or ()):
            dimension = _dimension_for_token(tag)
            if dimension is not None:
                rows.append(ContactDigestRow(dimension, person, tag, tick))
    deduped = {(row.dimension, row.person_id, row.token, row.tick): row for row in rows}
    return tuple(deduped[key] for key in sorted(deduped))


def contact_onset_rows(
    pairs: Sequence[ContactPairRow],
) -> tuple[ContactPairRow, ...]:
    """Shared pair/onset rows consumed by the five dependent contact families."""
    return tuple(
        sorted(pairs, key=lambda item: (item.community_a_id, item.community_b_id))
    )


def contact_onset_by_person(
    pairs: Sequence[ContactPairRow], communities: Sequence[object]
) -> dict[str, int]:
    """Earliest pair onset for each person in a community pair."""
    onsets: dict[str, int] = {}
    members: dict[str, tuple[str, ...]] = {
        community.community_id: tuple(community.person_ids) for community in communities
    }
    for pair in pairs:
        for community_id in (pair.community_a_id, pair.community_b_id):
            for person in members.get(community_id, ()):
                onsets[person] = min(
                    onsets.get(person, pair.onset_tick), pair.onset_tick
                )
    return onsets


def contact_pre_communities_at_onset(
    regional_input: RegionalPopulationInput,
    *,
    onset_tick: int,
    events: Sequence[object] | None = None,
) -> dict[str, str]:
    """Cluster residence as of ``onset_tick - 1`` for membership stability."""
    boundary = max(onset_tick - 1, 0)
    presence = contact_presence_rows_from_regional_input(
        regional_input, window_end=boundary
    )
    region_by_location = {
        row.location_id: row.region_id for row in regional_input.location_rows
    }
    residence = tuple(
        SocietyResidenceRow(
            person_id=row.person_id,
            region_id=region_by_location[row.location_id],
            first_tick=boundary,
            last_tick=boundary,
        )
        for row in presence
        if row.location_id in region_by_location
    )
    interaction = tuple(
        edge
        for edge in society_interaction_edges_from_events(events)
        if edge.tick <= boundary
    )
    living = tuple(sorted({row.person_id for row in presence}))
    emission = compute_candidate_communities(
        residence, interaction, None, living, boundary
    )
    return {
        person: community.community_id
        for community in emission.communities
        for person in community.person_ids
    }


def naming_borrowing_rows_from_ledgers(
    ledgers: object,
) -> tuple[ContactNamingEvidenceRow, ...]:
    """Export metadata-only naming evidence from detached terminology ledgers."""
    if ledgers is None:
        return ()
    if isinstance(ledgers, Mapping):
        values = tuple(ledgers.values())
    elif isinstance(ledgers, Sequence):
        values = tuple(ledgers)
    else:
        values = ()
    rows: list[ContactNamingEvidenceRow] = []
    for ledger in values or ():
        for binding in getattr(ledger, "bindings", ()):
            first_tick = getattr(binding, "first_tick", None)
            last_tick = getattr(binding, "last_tick", None)
            if first_tick is None:
                continue
            for evidence in getattr(binding, "evidence", ()):
                actor_id = getattr(evidence, "actor_id", None)
                rows.append(
                    ContactNamingEvidenceRow(
                        owner_id=binding.owner_id.value,
                        label_token=binding.label_token,
                        referent_kind=binding.referent_kind.value,
                        actor_id=None if actor_id is None else actor_id.value,
                        channel=evidence.channel.value,
                        first_tick=first_tick,
                        last_tick=first_tick if last_tick is None else last_tick,
                        evidence_tick=evidence.tick,
                        strength=float(binding.strength),
                        transmission=binding.transmission.value,
                    )
                )
    return tuple(rows)


def reputation_evidence_rows_from_ledgers(
    ledgers: object,
) -> tuple[ContactReputationEvidenceRow, ...]:
    """Export detached reputation evidence rows (no values, no group scores)."""
    if ledgers is None:
        return ()
    if isinstance(ledgers, Mapping):
        values = tuple(ledgers.values())
    elif isinstance(ledgers, Sequence):
        values = tuple(ledgers)
    else:
        values = ()
    rows: list[ContactReputationEvidenceRow] = []
    for ledger in values or ():
        for profile in getattr(ledger, "profiles", ()):
            for evidence in getattr(profile, "evidence", ()):
                rows.append(
                    ContactReputationEvidenceRow(
                        owner_id=evidence.owner_id.value,
                        target_id=evidence.target_id.value,
                        source_id=evidence.source_id.value,
                        dimension=evidence.dimension.value,
                        channel=evidence.channel.value,
                        trust_band=evidence.source_trust_band.value,
                        tick=evidence.tick,
                    )
                )
    return tuple(rows)


def practical_lineage_rows_from_audits(
    audits: Sequence[object] | None,
) -> tuple[ContactPracticalLineageRow, ...]:
    rows: list[ContactPracticalLineageRow] = []
    for audit in audits or ():
        owner = _id_text_or_none(
            getattr(audit, "owner_id", None) or getattr(audit, "agent_id", None)
        )
        origin = _id_text_or_none(
            getattr(audit, "origin", None) or getattr(audit, "channel", None)
        )
        parents = getattr(audit, "parent_person_ids", None) or getattr(
            audit, "parent_entry_ids", None
        )
        tick = getattr(audit, "tick", 0)
        if owner is None or origin is None or not parents:
            continue
        if type(tick) is not int or isinstance(tick, bool):
            continue
        rows.append(
            ContactPracticalLineageRow(
                owner_id=owner,
                parent_person_ids=tuple(str(item) for item in parents),
                origin=origin,
                tick=tick,
            )
        )
    return tuple(rows)


def cultural_lineage_rows_from_audits(
    audits: Sequence[object] | None,
) -> tuple[ContactCulturalLineageRow, ...]:
    rows: list[ContactCulturalLineageRow] = []
    for audit in audits or ():
        owner = _id_text_or_none(
            getattr(audit, "owner_id", None) or getattr(audit, "agent_id", None)
        )
        parents = getattr(audit, "parent_person_ids", None) or getattr(
            audit, "parent_belief_ids", None
        )
        tick = getattr(audit, "tick", 0)
        recombined = getattr(audit, "recombined", False)
        if (
            owner is None
            or not parents
            or type(tick) is not int
            or isinstance(tick, bool)
        ):
            continue
        rows.append(
            ContactCulturalLineageRow(
                owner_id=owner,
                parent_person_ids=tuple(str(item) for item in parents),
                recombined=bool(recombined),
                tick=tick,
            )
        )
    return tuple(rows)


def narrative_root_rows_from_rows(
    rows: Sequence[object] | None,
) -> tuple[ContactNarrativeRootRow, ...]:
    projected: list[ContactNarrativeRootRow] = []
    for row in rows or ():
        person = _id_text_or_none(
            getattr(row, "person_id", None) or getattr(row, "owner_id", None)
        )
        root = _id_text_or_none(
            getattr(row, "transmission_root_id", None)
            or getattr(row, "root_id", None)
            or getattr(row, "token", None)
        )
        tick = getattr(row, "tick", 0)
        if person and root and type(tick) is int and not isinstance(tick, bool):
            projected.append(ContactNarrativeRootRow(person, root, tick))
    return tuple(projected)


def contact_analysis_inputs_from_context(
    *,
    run_id: str,
    input_revision: str,
    window_end: int,
    communities: Sequence[CandidateCommunityRow],
    regional_input: RegionalPopulationInput,
    events: Sequence[object] | None = None,
    dimension_sources: Mapping[str, Sequence[object]] | None = None,
    practical_rows: Sequence[ContactPracticalLineageRow] = (),
    cultural_rows: Sequence[ContactCulturalLineageRow] = (),
    narrative_rows: Sequence[ContactNarrativeRootRow] = (),
    merge_rows: Sequence[ContactMergeRow] = (),
    knowledge_rows: Sequence[ContactPracticalKnowledgeAuditRow] = (),
    naming_rows: Sequence[ContactNamingEvidenceRow] = (),
    reputation_rows: Sequence[ContactReputationEvidenceRow] = (),
    teaching_audits: Sequence[object] | None = None,
) -> ContactAnalysisInputs:
    """Build all six analyses from detached rows; shared onset by construction."""
    presence = contact_presence_rows_from_regional_input(
        regional_input, window_end=window_end
    )
    episodes = contact_episode_rows_from_events(events)
    interactions = contact_interaction_rows_from_events(
        events, teaching_audits=teaching_audits
    )
    kinship = contact_kinship_rows_from_events(events)
    contact = compute_society_contact(
        communities,
        episodes=episodes,
        presence=presence,
        interactions=interactions,
        kinship=kinship,
    )
    pairs = contact_onset_rows(contact.pairs)
    onsets = contact_onset_by_person(pairs, communities)
    digest: list[ContactDigestRow] = []
    for dimension, source_rows in (dimension_sources or {}).items():
        for row in source_rows or ():
            person = _id_text_or_none(
                getattr(row, "person_id", None)
                or getattr(row, "agent_id", None)
                or getattr(row, "owner_id", None)
            )
            token = _id_text_or_none(
                getattr(row, "token", None)
                or getattr(row, "digest_id_token", None)
                or getattr(row, "head_token", None)
                or getattr(row, "fingerprint", None)
            )
            tick = getattr(row, "tick", 0)
            if (
                person is not None
                and token is not None
                and type(tick) is int
                and not isinstance(tick, bool)
            ):
                digest.append(ContactDigestRow(dimension, person, token, tick))
    pre_communities: dict[str, str] | None = None
    if pairs:
        onset = min(pair.onset_tick for pair in pairs)
        pre_communities = contact_pre_communities_at_onset(
            regional_input, onset_tick=onset, events=events
        )
    cultural_change = compute_contact_cultural_change(
        communities,
        pairs,
        tuple(digest),
        final_tick=window_end,
        pre_community_by_person=pre_communities,
    )
    hybrid = compute_contact_hybrid_practice(
        communities,
        practical=practical_rows,
        cultural=cultural_rows,
        narratives=narrative_rows,
        merges=merge_rows,
        onset_tick_by_person=onsets,
    )
    knowledge = compute_contact_knowledge_transfer(
        communities, knowledge_rows, onset_tick_by_person=onsets
    )
    lexical = compute_contact_lexical_borrowing(
        communities, naming_rows, onset_tick_by_person=onsets
    )
    reputation = compute_contact_reputation_transfer(
        communities, reputation_rows, onset_tick_by_person=onsets
    )
    _LOG.info(
        "contact_analysis_inputs run_id=%s contact_pairs=%s contact_events=%s "
        "window_end=%s",
        run_id,
        len(pairs),
        len(episodes),
        window_end,
    )
    return ContactAnalysisInputs(
        contact=contact,
        cultural_change=cultural_change,
        hybrid_practice=hybrid,
        knowledge_transfer=knowledge,
        lexical_borrowing=lexical,
        reputation_transfer=reputation,
    )


def contact_analysis_inputs_from_snapshot(
    snapshot: PersistedAnalysisSnapshot,
    *,
    input_revision: str,
    dimension_sources: Mapping[str, Sequence[object]] | None = None,
    practical_rows: Sequence[ContactPracticalLineageRow] = (),
    cultural_rows: Sequence[ContactCulturalLineageRow] = (),
    narrative_rows: Sequence[ContactNarrativeRootRow] = (),
    merge_rows: Sequence[ContactMergeRow] = (),
    knowledge_rows: Sequence[ContactPracticalKnowledgeAuditRow] = (),
    naming_rows: Sequence[ContactNamingEvidenceRow] = (),
    reputation_rows: Sequence[ContactReputationEvidenceRow] = (),
    teaching_audits: Sequence[object] | None = None,
) -> ContactAnalysisInputs | None:
    """Compose detached contact evidence without importing persistence."""
    if type(snapshot) is not PersistedAnalysisSnapshot:
        raise TypeError("snapshot must be PersistedAnalysisSnapshot")
    context = snapshot.regional_context
    if context is None:
        return None
    window_end = snapshot.objective_complete_through_boundary
    if window_end is None:
        raise EvidenceCompositionError("contact_window_end_unavailable")
    regional_input = regional_population_input_from_snapshot(
        snapshot, input_revision=input_revision, window_end=window_end
    )
    if regional_input is None:
        return None
    society = society_emission_inputs_from_snapshot(
        snapshot,
        input_revision=input_revision,
        tick=window_end,
        dimension_sources=dimension_sources,
    )
    if society is None:
        return None
    return contact_analysis_inputs_from_context(
        run_id=snapshot.run_id,
        input_revision=input_revision,
        window_end=window_end,
        communities=society.emission.communities,
        regional_input=regional_input,
        events=snapshot.events,
        dimension_sources=dimension_sources,
        practical_rows=practical_rows,
        cultural_rows=cultural_rows,
        narrative_rows=narrative_rows,
        merge_rows=merge_rows,
        knowledge_rows=knowledge_rows,
        naming_rows=naming_rows,
        reputation_rows=reputation_rows,
        teaching_audits=teaching_audits,
    )


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
        _LOG.debug("historical_memory_harvest_skip reason_code=layers_absent")
        return None
    if isinstance(as_of_tick, bool) or type(as_of_tick) is not int or as_of_tick < 0:
        raise ValueError("as_of_tick: out_of_range")

    audits = tuple(cultural_feature_audits or ())
    include_cultural = bool(getattr(layers_spec, "include_cultural_features", True))
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

    ticks = (
        tuple(transition_ticks)
        if transition_ticks is not None
        else (
            *sorted(set(deaths.values())),
            as_of_tick,
        )
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
