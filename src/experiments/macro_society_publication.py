"""Completed-run bridge from macro-society analysis to a snapshot artifact."""

from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from typing import Final

from analysis.macro_society_contract import MacroSocietyError
from analysis.macro_society_detection import detect_macro_society_candidates
from analysis.macro_society_evidence import MacroSocietyWindowEvidence
from analysis.macro_society_identity import assign_macro_society_identities
from analysis.macro_society_layers import (
    MacroSocietyObjectiveRow as AnalysisObjectiveRow,
)
from analysis.macro_society_layers import (
    project_macro_society_layers,
)
from analysis.macro_society_lineage import (
    MacroSocietyAnalysis,
    build_macro_society_analysis,
)
from simulation.macro_society_codec import (
    compute_macro_society_publication_id,
    encode_macro_society_snapshot,
)
from simulation.macro_society_models import (
    MACRO_SOCIETY_SNAPSHOT_SCHEMA_VERSION,
    MAX_SNAPSHOT_MEMBERS,
    MacroSocietyArtifactError,
    MacroSocietyCandidateRecord,
    MacroSocietyCoverage,
    MacroSocietyLineageEdgeRecord,
    MacroSocietyObjectiveRow,
    MacroSocietySnapshot,
    MacroSocietySnapshotRef,
    MacroSocietyWindowRecord,
)
from simulation.macro_society_ports import (
    MacroSocietyPublication,
    MacroSocietyPublicationPort,
)
from world.identifiers import require_exact_nonneg_int, require_stable_id

__all__ = [
    "MacroSocietyHarvest",
    "MacroSocietyHarvestResult",
    "build_macro_society_harvest_result",
    "macro_society_publication_document",
    "publish_macro_society_snapshot",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.macro_society_publication"
)

_PLACEHOLDER_PUBLICATION_ID: Final[str] = "msoc-edge-0000000000000000"


@dataclass(frozen=True, slots=True)
class MacroSocietyHarvest:
    """Detached evidence for one completed run."""

    run_id: str
    input_revision: str
    windows: tuple[MacroSocietyWindowEvidence, ...]
    objective_rows: tuple[object, ...] = ()
    subjective_rows: tuple[object, ...] = ()
    generated_tick: int = 0

    def __post_init__(self) -> None:
        require_stable_id("run_id", self.run_id)
        require_stable_id("input_revision", self.input_revision)
        require_exact_nonneg_int("generated_tick", self.generated_tick)
        if not self.windows:
            raise MacroSocietyError("macro_society_empty_window")
        indexes = [window.window_index for window in self.windows]
        if indexes != sorted(indexes) or len(set(indexes)) != len(indexes):
            raise MacroSocietyError("macro_society_nonmonotonic_window")


@dataclass(frozen=True, slots=True)
class MacroSocietyHarvestResult:
    """Analysis plus its immutable snapshot and publication identity."""

    analysis: MacroSocietyAnalysis
    snapshot: MacroSocietySnapshot
    publication_id: str
    snapshot_bytes: int


def _objective_rows(rows: tuple[object, ...]) -> tuple[MacroSocietyObjectiveRow, ...]:
    converted: list[MacroSocietyObjectiveRow] = []
    for row in rows:
        if type(row) is AnalysisObjectiveRow:
            converted.append(
                MacroSocietyObjectiveRow(
                    region_id=row.region_id,
                    tick=row.tick,
                    population_count=row.population_count,
                    cohort_id=row.cohort_id,
                    stage_id=row.stage_id,
                )
            )
        elif type(row) is MacroSocietyObjectiveRow:
            converted.append(row)
        else:
            raise MacroSocietyError("macro_society_invalid_objective_row")
    return tuple(converted)


def _bounded_members(members: tuple[str, ...]) -> tuple[tuple[str, ...], bool]:
    """Truncate deterministically at the snapshot member cap."""
    if len(members) <= MAX_SNAPSHOT_MEMBERS:
        return members, False
    return members[:MAX_SNAPSHOT_MEMBERS], True


def _candidate_records(
    analysis: MacroSocietyAnalysis,
) -> tuple[tuple[MacroSocietyCandidateRecord, ...], bool]:
    truncated = False
    records: list[MacroSocietyCandidateRecord] = []
    final = analysis.windows[-1]
    overlap = set(final.overlap_person_ids)
    for record in analysis.records:
        members, clipped = _bounded_members(record.member_ids)
        if clipped:
            truncated = True
        records.append(
            MacroSocietyCandidateRecord(
                macro_society_id=record.macro_society_id,
                creation_tick=record.creation_tick,
                first_tick=record.first_tick,
                last_tick=record.last_tick,
                status=record.status.value,
                member_ids=members,
                lane_signature=record.lane_signature,
                overlap_person_ids=tuple(
                    person for person in members if person in overlap
                ),
            )
        )
    return tuple(records), truncated


def build_macro_society_harvest_result(
    harvest: MacroSocietyHarvest,
) -> MacroSocietyHarvestResult:
    """Detect, identify, publish-map, and encode one completed run."""
    window_results = tuple(
        detect_macro_society_candidates(window) for window in harvest.windows
    )
    layer_views = tuple(
        project_macro_society_layers(
            window_result=result,
            objective_rows=harvest.objective_rows,
            subjective_rows=harvest.subjective_rows,
        )
        for result in window_results
    )
    assignment = assign_macro_society_identities(window_results)
    analysis = build_macro_society_analysis(
        windows=window_results,
        assignment=assignment,
        layer_view=layer_views[-1],
    )
    candidates, truncated = _candidate_records(analysis)
    assigned = {
        index: dict(pairs) for index, pairs in assignment.window_assignments
    }
    snapshots = tuple(
        MacroSocietyWindowRecord(
            window_index=window.window_index,
            tick_start=window.tick_start,
            tick_end=window.tick_end,
            candidate_ids=tuple(
                assigned[window.window_index][candidate.candidate_key]
                for candidate in window.candidates
            ),
            overlap_person_count=len(window.overlap_person_ids),
            known_person_count=len(window.known_person_ids),
            lane_presence=window.lane_presence,
        )
        for window in window_results
    )
    edges = tuple(
        MacroSocietyLineageEdgeRecord(
            from_id=edge.from_id,
            to_id=edge.to_id,
            kind=edge.kind.value,
            from_tick=edge.from_tick,
            to_tick=edge.to_tick,
            jaccard=edge.jaccard,
        )
        for edge in analysis.edges
    )
    snapshot = MacroSocietySnapshot(
        schema_version=MACRO_SOCIETY_SNAPSHOT_SCHEMA_VERSION,
        policy_version=analysis.policy_version,
        run_id=harvest.run_id,
        input_revision=harvest.input_revision,
        generated_tick=harvest.generated_tick,
        publication_id=_PLACEHOLDER_PUBLICATION_ID,
        windows=snapshots,
        candidates=candidates,
        edges=edges,
        objective_rows=_objective_rows(tuple(layer_views[-1].objective_rows)),
        coverage=MacroSocietyCoverage(
            observed=analysis.coverage.observed,
            expected=analysis.coverage.expected,
            ratio=analysis.coverage.ratio,
        ),
        provenance_code="member_list_truncated" if truncated else "ok",
    )
    provisional = encode_macro_society_snapshot(snapshot)
    publication_id = compute_macro_society_publication_id(
        provisional, run_id=harvest.run_id
    )
    snapshot = replace(snapshot, publication_id=publication_id)
    payload = encode_macro_society_snapshot(snapshot)
    if compute_macro_society_publication_id(payload, run_id=harvest.run_id) != (
        publication_id
    ):
        raise MacroSocietyArtifactError("macro_society_digest_mismatch")
    _LOG.info(
        "macro_society_harvest run=%s publication=%s candidates=%s edges=%s bytes=%s",
        harvest.run_id,
        publication_id,
        len(snapshot.candidates),
        len(snapshot.edges),
        len(payload),
    )
    return MacroSocietyHarvestResult(
        analysis=analysis,
        snapshot=snapshot,
        publication_id=publication_id,
        snapshot_bytes=len(payload),
    )


def publish_macro_society_snapshot(
    *,
    harvest: MacroSocietyHarvest,
    port: MacroSocietyPublicationPort,
    created_at_utc: str,
) -> MacroSocietySnapshotRef:
    """Build one publication and hand it to the injected port."""
    result = build_macro_society_harvest_result(harvest)
    payload = encode_macro_society_snapshot(result.snapshot)
    publication = MacroSocietyPublication(
        snapshot=result.snapshot, payload=payload, created_at_utc=created_at_utc
    )
    ref = port.publish(publication)
    _LOG.info(
        "macro_society_published run=%s publication=%s digest=%s",
        harvest.run_id,
        ref.publication_id,
        ref.digest,
    )
    return ref


def macro_society_publication_document(
    result: MacroSocietyHarvestResult,
) -> dict[str, object]:
    """Safe CLI receipt content; never includes member or owner ids."""
    snapshot = result.snapshot
    return {
        "schema_version": snapshot.schema_version,
        "publication_id": snapshot.publication_id,
        "window_count": len(snapshot.windows),
        "candidate_count": len(snapshot.candidates),
        "edge_count": len(snapshot.edges),
        "coverage_observed": snapshot.coverage.observed,
        "coverage_expected": snapshot.coverage.expected,
        "coverage_ratio": snapshot.coverage.ratio,
        "provenance_code": snapshot.provenance_code,
        "snapshot_bytes": result.snapshot_bytes,
    }
