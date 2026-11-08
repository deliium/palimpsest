# ruff: noqa: E501
# mypy: disable-error-code="arg-type,assignment,union-attr,index,call-overload,attr-defined,no-untyped-def,unused-ignore,type-arg,comparison-overlap,redundant-cast,operator,misc,return-value,valid-type,override"
"""Completed-run migration-displacement harvest composition."""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from analysis.migration_displacement_events import (
    migration_communication_pairs_from_events,
    migration_integration_rows_from_events,
    migration_kinship_pairs_from_events,
    migration_movement_rows_from_events,
    migration_movement_rows_with_coverage,
)
from analysis.migration_displacement_policy import (
    MigrationDisplacementAnalysisPolicy,
    default_migration_displacement_analysis_policy,
)
from analysis.migration_displacement_rows import (
    MigrationDisplacementHarvestRows,
    harvest_migration_displacement_rows,
)
from analysis.specifications import metric_specification
from simulation.migration_displacement_codec import (
    finalize_migration_displacement_snapshot,
)
from simulation.migration_displacement_export import (
    migration_displacement_owner_export,
)
from simulation.migration_displacement_models import (
    MIGRATION_DISPLACEMENT_SNAPSHOT_POLICY,
    MIGRATION_DISPLACEMENT_SNAPSHOT_VERSION,
    MigrationAlignmentSnapshotRow,
    MigrationCauseSnapshotRow,
    MigrationClusterSnapshotRow,
    MigrationDisplacementCandidateRow,
    MigrationDisplacementSnapshot,
    MigrationDisplacementSummaryRow,
    MigrationLineageSnapshotRow,
    MigrationMetricProvenanceRow,
    MigrationMovementRow,
    MigrationOutcomeSnapshotRow,
    MigrationRouteSnapshotRow,
    MigrationWaveSnapshotRow,
    empty_migration_displacement_snapshot,
)

__all__ = [
    "MigrationDisplacementHarvest",
    "build_completed_run_migration_displacement_harvest",
    "compose_migration_displacement_snapshot",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.migration_displacement.harvest"
)

_FAMILIES: Final[tuple[str, ...]] = (
    "migration_wave_structure",
    "migration_cause_evidence",
    "migration_cluster_cohesion",
    "migration_integration_outcome",
)


@dataclass(frozen=True, slots=True)
class MigrationDisplacementHarvest:
    """One completed run's detached migration-displacement harvest."""

    run_id: str
    rows: MigrationDisplacementHarvestRows
    snapshot: MigrationDisplacementSnapshot
    coverage: str
    notices: tuple[str, ...] = ()


def _topology(regions_spec: object | None) -> dict[str, str] | None:
    locations = getattr(regions_spec, "location_regions", None)
    if locations is None:
        return None
    return {item.location_id.value: item.region_id for item in locations}


def _provenance(coverage: str) -> tuple[MigrationMetricProvenanceRow, ...]:
    rows: list[MigrationMetricProvenanceRow] = []
    for family in _FAMILIES:
        spec = metric_specification(family)
        rows.append(
            MigrationMetricProvenanceRow(
                family=spec.family_id.value,
                version=spec.algorithm_version,
                document_digest="",
                coverage=(
                    coverage
                    if coverage in {"complete", "partial", "missing"}
                    else "not_applicable"
                ),
            )
        )
    rows.sort(key=lambda item: item.family)
    return tuple(rows)


def _summary_counts(
    *,
    candidates: Sequence[MigrationDisplacementCandidateRow],
    waves: Sequence[MigrationWaveSnapshotRow],
    clusters: Sequence[MigrationClusterSnapshotRow],
    outcomes: Sequence[MigrationOutcomeSnapshotRow],
    movements: Sequence[MigrationMovementRow],
    causes: Sequence[MigrationCauseSnapshotRow],
) -> dict[str, int]:
    displacement = {
        "displacement_like": 0,
        "mixed": 0,
        "not_displacement_like": 0,
        "unknown": 0,
    }
    for row in waves:
        displacement[row.displacement_classification] += 1
    integration = {
        "settled": 0,
        "transient": 0,
        "returned": 0,
        "onward": 0,
        "unknown": 0,
    }
    for row in outcomes:
        integration[row.classification] += 1
    return {
        "candidate_count": len(candidates),
        "wave_count": len(waves),
        "cluster_count": len(clusters),
        "outcome_count": len(outcomes),
        "movement_count": len(movements),
        "cause_count": len(causes),
        "displacement_like_count": displacement["displacement_like"],
        "mixed_count": displacement["mixed"],
        "not_displacement_like_count": displacement["not_displacement_like"],
        "unknown_count": displacement["unknown"],
        "integration_settled_count": integration["settled"],
        "integration_transient_count": integration["transient"],
        "integration_returned_count": integration["returned"],
        "integration_onward_count": integration["onward"],
        "integration_unknown_count": integration["unknown"],
    }


def compose_migration_displacement_snapshot(
    rows: MigrationDisplacementHarvestRows,
    run_id: str,
) -> MigrationDisplacementSnapshot:
    """Map harvest rows into a finalized canonical snapshot."""
    if type(rows) is not MigrationDisplacementHarvestRows:
        raise TypeError("rows must be MigrationDisplacementHarvestRows")
    movements = tuple(
        sorted(
            (
                MigrationMovementRow(
                    participant_token=item.participant_token,
                    origin_token=item.origin_token,
                    destination_token=item.destination_token,
                    route_tokens=item.route_tokens,
                    start_tick=item.start_tick,
                    end_tick=item.end_tick,
                    relocation_kind=item.relocation_kind,
                    group_size=item.group_size,
                    arrival_status=item.arrival_status,
                    coverage=item.coverage,
                )
                for item in rows.movements
            ),
            key=lambda row: (
                row.start_tick,
                row.participant_token,
                row.origin_token,
                row.destination_token,
            ),
        )
    )
    causes = tuple(
        sorted(
            (
                MigrationCauseSnapshotRow(
                    owner_token=item.owner_token,
                    cause_token=item.cause_token,
                    cause_kind=item.cause_kind,
                    source_kind=item.source_kind,
                    anchor_token=item.anchor_token,
                    confidence=float(item.confidence),
                    tick=item.tick,
                    status=item.status,
                )
                for item in rows.causes
            ),
            key=lambda row: (row.owner_token, row.tick, row.cause_token),
        )
    )
    routes = tuple(
        sorted(
            (
                MigrationRouteSnapshotRow(
                    owner_token=item.owner_token,
                    route_token=item.route_token,
                    origin_token=item.origin_token,
                    destination_token=item.destination_token,
                    route_tokens=item.route_tokens,
                    observed_duration_ticks=item.observed_duration_ticks,
                    fatigue_cost=float(item.fatigue_cost),
                    basis=item.basis,
                    status=item.status,
                    first_tick=item.first_tick,
                    last_tick=item.last_tick,
                )
                for item in rows.routes
            ),
            key=lambda row: (row.owner_token, row.first_tick, row.route_token),
        )
    )
    clusters = tuple(
        sorted(
            (
                MigrationClusterSnapshotRow(
                    cluster_token=item.cluster_token,
                    member_tokens=item.member_tokens,
                    basis_counts=item.basis_counts,
                    coverage=item.coverage,
                    first_tick=item.first_tick,
                    last_tick=item.last_tick,
                )
                for item in rows.clusters
            ),
            key=lambda row: row.cluster_token,
        )
    )
    waves = tuple(
        sorted(
            (
                MigrationWaveSnapshotRow(
                    wave_token=item.wave_token,
                    origin_token=item.origin_token,
                    destination_token=item.destination_token,
                    participant_tokens=item.participant_tokens,
                    route_tokens=item.route_tokens,
                    start_tick=item.start_tick,
                    end_tick=item.end_tick,
                    cause_support_counts=item.cause_support_counts,
                    displacement_classification=item.displacement_classification,
                    displacement_bases=tuple(sorted(item.displacement_bases)),
                    independent_cause_count=item.independent_cause_count,
                    cluster_tokens=item.cluster_tokens,
                    coverage=item.coverage,
                )
                for item in rows.waves
            ),
            key=lambda row: (row.start_tick, row.wave_token),
        )
    )
    outcomes = tuple(
        sorted(
            (
                MigrationOutcomeSnapshotRow(
                    outcome_token=item.outcome_token,
                    participant_token=item.participant_token,
                    destination_token=item.destination_token,
                    residence_ticks=item.residence_ticks,
                    access_evidence_count=item.access_evidence_count,
                    participation_evidence_count=item.participation_evidence_count,
                    relationship_evidence_count=item.relationship_evidence_count,
                    conflict_evidence_count=item.conflict_evidence_count,
                    classification=item.classification,
                    coverage=item.coverage,
                    censored=item.censored,
                )
                for item in rows.outcomes
            ),
            key=lambda row: (
                row.participant_token,
                row.destination_token,
                row.outcome_token,
            ),
        )
    )
    candidates = tuple(
        sorted(
            (
                MigrationDisplacementCandidateRow(
                    candidate_token=item.candidate_token,
                    kind=item.kind,
                    status=item.status,
                    first_tick=item.first_tick,
                    last_tick=item.last_tick,
                    member_count=item.member_count,
                    origin_token=item.origin_token,
                    destination_token=item.destination_token,
                    classification=item.classification,
                    coverage=item.coverage,
                )
                for item in rows.candidates
            ),
            key=lambda row: row.candidate_token,
        )
    )
    candidate_tokens = {row.candidate_token for row in candidates}
    lineage = tuple(
        sorted(
            (
                MigrationLineageSnapshotRow(
                    candidate_token=item.candidate_token,
                    previous_token=item.previous_token,
                    relation=item.relation,
                    first_tick=item.first_tick,
                    last_tick=item.last_tick,
                )
                for item in rows.lineage
            ),
            key=lambda row: (
                row.first_tick,
                row.candidate_token,
                row.previous_token,
                row.relation,
            ),
        )
    )
    for row in lineage:
        if (
            row.candidate_token != "none"
            and row.candidate_token not in candidate_tokens
        ):
            raise ValueError("migration_displacement_snapshot: unresolved_candidate")
        if (
            row.previous_token != "none"
            and row.previous_token not in candidate_tokens
        ):
            raise ValueError("migration_displacement_snapshot: unresolved_candidate")
    alignment = tuple(
        sorted(
            (
                MigrationAlignmentSnapshotRow(
                    owner_token=item.owner_token,
                    candidate_token=item.candidate_token,
                    alignment=item.alignment,
                    basis=item.basis,
                )
                for item in rows.alignment
                if item.candidate_token in candidate_tokens
            ),
            key=lambda row: (row.owner_token, row.candidate_token),
        )
    )
    coverage = rows.coverage
    counts = _summary_counts(
        candidates=candidates,
        waves=waves,
        clusters=clusters,
        outcomes=outcomes,
        movements=movements,
        causes=causes,
    )
    summary = MigrationDisplacementSummaryRow(
        run_id=run_id,
        publication_id="",
        digest="",
        schema_version=MIGRATION_DISPLACEMENT_SNAPSHOT_VERSION,
        policy_version=MIGRATION_DISPLACEMENT_SNAPSHOT_POLICY,
        coverage=coverage,
        unresolved_anchor_count=sum(
            1 for item in rows.causes if not item.anchor_token
        ),
        truncated=any(
            notice.endswith("_cap_reached") for notice in rows.notices
        ),
        **counts,
    )
    snapshot = MigrationDisplacementSnapshot(
        summary=summary,
        candidates=candidates,
        movements=movements,
        causes=causes,
        routes=routes,
        clusters=clusters,
        waves=waves,
        outcomes=outcomes,
        lineage=lineage,
        alignment=alignment,
        metric_provenance=_provenance(coverage),
        digest="",
        publication_id="",
        schema_version=MIGRATION_DISPLACEMENT_SNAPSHOT_VERSION,
        policy_version=MIGRATION_DISPLACEMENT_SNAPSHOT_POLICY,
    )
    return finalize_migration_displacement_snapshot(snapshot)


def build_completed_run_migration_displacement_harvest(
    runner_result: object,
    *,
    committed_events: Sequence[object],
    run_id: str,
    policy: MigrationDisplacementAnalysisPolicy | None = None,
    input_revision: str = "rev-run",
    entity_to_agent: Mapping[str, str] | None = None,
    regions_spec: object | None = None,
    window_end: int | None = None,
    complete_through_boundary: int | None = None,
) -> MigrationDisplacementHarvest:
    """Compose one completed run's detached migration-displacement harvest."""
    resolved = policy or default_migration_displacement_analysis_policy()
    ledgers = tuple(getattr(runner_result, "migration_displacement_ledgers", ()) or ())
    if not ledgers:
        from dataclasses import replace

        empty = empty_migration_displacement_snapshot(
            run_id, digest="", publication_id=""
        )
        empty = replace(
            empty,
            summary=replace(empty.summary, coverage="missing"),
        )
        finalized = finalize_migration_displacement_snapshot(empty)
        _LOG.debug("migration_displacement_harvest_missing")
        return MigrationDisplacementHarvest(
            run_id=run_id,
            rows=MigrationDisplacementHarvestRows(coverage="missing"),
            snapshot=finalized,
            coverage="missing",
            notices=(),
        )
    events = tuple(committed_events or ())
    topology = _topology(regions_spec)
    exported = migration_displacement_owner_export(ledgers)
    if window_end is None and complete_through_boundary is None:
        movements = migration_movement_rows_from_events(
            events,
            run_id=run_id,
            input_revision=input_revision,
            region_topology=topology,
            max_pairs=resolved.max_pairs_per_run,
            entity_to_agent=entity_to_agent,
        )
    else:
        movements, _coverage = migration_movement_rows_with_coverage(
            events,
            run_id=run_id,
            input_revision=input_revision,
            region_topology=topology,
            max_pairs=resolved.max_pairs_per_run,
            entity_to_agent=entity_to_agent,
            window_end=window_end,
            complete_through_boundary=complete_through_boundary,
        )
    evidence = migration_integration_rows_from_events(
        events,
        run_id=run_id,
        input_revision=input_revision,
        region_topology=topology,
        max_pairs=resolved.max_pairs_per_run,
        entity_to_agent=entity_to_agent,
        window_end=window_end,
        complete_through_boundary=complete_through_boundary,
    )
    rows = harvest_migration_displacement_rows(
        exported,
        movements,
        evidence,
        kinship_pairs=migration_kinship_pairs_from_events(events),
        communication_pairs=migration_communication_pairs_from_events(
            events, entity_to_agent=entity_to_agent
        ),
        policy=resolved,
    )
    snapshot = compose_migration_displacement_snapshot(rows, run_id)
    notices = tuple(sorted(set(rows.notices)))
    _LOG.debug(
        "migration_displacement_harvest_built owners=%s movements=%s waves=%s",
        len(ledgers),
        len(movements),
        len(rows.waves),
    )
    return MigrationDisplacementHarvest(
        run_id=run_id,
        rows=rows,
        snapshot=snapshot,
        coverage=rows.coverage,
        notices=notices,
    )
