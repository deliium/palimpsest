"""Outer composition: map neutral persistence snapshots into analysis sources.

May import ``analysis`` and ``simulation``. Must not import ``persistence`` or
SQLAlchemy. Composition roots inject protocol-typed readers.
"""

from __future__ import annotations

import logging
from typing import Final

from analysis.models import SubjectiveDerivationEdge
from analysis.sources import (
    InMemoryMemoryEvidenceSource,
    InMemoryObjectiveEventSource,
    reconstruction_evidence_from_durable,
)
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

__all__ = [
    "EvidenceCompositionError",
    "EvidenceCompositionService",
    "constrain_snapshot_to_manifest",
    "map_snapshot_to_analysis_sources",
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
