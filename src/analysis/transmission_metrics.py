"""Stage-specific knowledge diffusion and rumor distortion metrics (Task 15)."""

from __future__ import annotations

import logging
import time
from collections.abc import Mapping, Sequence
from typing import Final

import numpy as np

from analysis.evidence import EvidenceStage
from analysis.models import (
    METRIC_DOCUMENT_SCHEMA_VERSION,
    MetricAvailability,
    MetricCoverage,
    MetricDocument,
    MetricProvenance,
    SocialTransmissionReport,
    TransmissionDistortion,
    TransmissionHopRecord,
)
from analysis.numerical import library_versions, quantize_float, require_finite
from analysis.specifications import (
    ADOPTION_STAGES_V1,
    AdoptionStage,
    MetricFamilyId,
    metric_specification,
)
from analysis.social_transmission import build_lineage_edges
from world.identifiers import require_stable_id

__all__ = [
    "compute_knowledge_diffusion",
    "compute_rumor_distortion",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.transmission_metrics")


def _document(
    *,
    family: str,
    algorithm_version: str,
    run_id: str,
    input_revision: str,
    evidence_stages: frozenset[EvidenceStage],
    population: str,
    denominator: str,
    availability: MetricAvailability,
    values: Mapping[str, object],
    coverage: MetricCoverage | None,
    notes_code: str,
) -> MetricDocument:
    return MetricDocument(
        schema_version=METRIC_DOCUMENT_SCHEMA_VERSION,
        metric_family=family,
        algorithm_version=algorithm_version,
        library_versions=library_versions(),
        run_id=run_id,
        input_revision=input_revision,
        evidence_stages=evidence_stages,
        population=population,
        denominator=denominator,
        coverage=coverage,
        availability=availability,
        values=dict(values),
        provenance=MetricProvenance(
            source_kind="transmission_metrics",
            source_ids=(),
            notes_code=notes_code,
        ),
    )


def compute_knowledge_diffusion(
    hops: Sequence[TransmissionHopRecord],
    *,
    run_id: str,
    input_revision: str,
    eligible_agent_ids: Sequence[str],
    death_ticks: Mapping[str, int] | None = None,
    branch_count: int | None = None,
) -> MetricDocument:
    """Stage-specific reach, first adoption, hops, and branching."""
    started = time.perf_counter()
    run_id = require_stable_id("run_id", run_id)
    input_revision = require_stable_id("input_revision", input_revision)
    deaths = dict(death_ticks or {})
    spec = metric_specification(MetricFamilyId.KNOWLEDGE_DIFFUSION)
    eligible = sorted({require_stable_id("agent_id", item) for item in eligible_agent_ids})

    roots = sorted({hop.transmission_root_id for hop in hops})
    if not roots:
        return _document(
            family=spec.family_id.value,
            algorithm_version=spec.algorithm_version,
            run_id=run_id,
            input_revision=input_revision,
            evidence_stages=frozenset(spec.evidence_inputs),
            population=spec.population,
            denominator=spec.denominator,
            availability=MetricAvailability.ABSENT,
            values={},
            coverage=None,
            notes_code="no_roots",
        )

    lineage = build_lineage_edges(hops)
    unresolved = sum(1 for edge in lineage if edge.unresolved)
    if unresolved == len(lineage) and lineage:
        availability = MetricAvailability.UNKNOWN
    else:
        availability = MetricAvailability.PRESENT

    # Map hop adoption stages; events default world_delivery, traces receiver_trace.
    stage_first: dict[str, dict[str, int]] = {stage: {} for stage in ADOPTION_STAGES_V1}
    hop_at_first_trace: list[int] = []
    first_ticks: list[int] = []

    for hop in sorted(hops, key=lambda item: (item.tick, item.communication_id)):
        stage = hop.adoption_stage or (
            AdoptionStage.WORLD_DELIVERY.value
            if hop.event_id is not None and hop.receiver_confidence is None
            else AdoptionStage.RECEIVER_TRACE.value
        )
        adopter = hop.listener_id
        if adopter is None:
            continue
        if adopter == hop.speaker_id:
            continue
        death = deaths.get(adopter)
        if death is not None and hop.tick > death:
            continue
        if adopter not in eligible and eligible:
            continue
        bucket = stage_first.setdefault(stage, {})
        if adopter not in bucket:
            bucket[adopter] = hop.tick
            if stage == AdoptionStage.RECEIVER_TRACE.value:
                hop_at_first_trace.append(hop.hop_count)
            first_ticks.append(hop.tick)

    eligible_n = max(len(eligible), 1)
    reach_world = quantize_float(
        require_finite(
            float(len(stage_first.get(AdoptionStage.WORLD_DELIVERY.value, {})))
            / float(eligible_n)
        )
    )
    reach_trace = quantize_float(
        require_finite(
            float(len(stage_first.get(AdoptionStage.RECEIVER_TRACE.value, {})))
            / float(eligible_n)
        )
    )
    reach_belief = quantize_float(
        require_finite(
            float(len(stage_first.get(AdoptionStage.BELIEF_ACTIVATION.value, {})))
            / float(eligible_n)
        )
    )
    mean_first = (
        quantize_float(
            require_finite(float(np.mean(np.asarray(first_ticks, dtype=np.float64))))
        )
        if first_ticks
        else None
    )
    mean_hops = (
        quantize_float(
            require_finite(
                float(np.mean(np.asarray(hop_at_first_trace, dtype=np.float64)))
            )
        )
        if hop_at_first_trace
        else None
    )
    if branch_count is None:
        children: dict[str, int] = {}
        for edge in lineage:
            if edge.parent_communication_id and not edge.unresolved:
                children[edge.parent_communication_id] = (
                    children.get(edge.parent_communication_id, 0) + 1
                )
        branch_count = sum(1 for count in children.values() if count > 1)

    duration_ms = int((time.perf_counter() - started) * 1000)
    _LOG.debug(
        "knowledge_diffusion_complete",
        extra={
            "operation": "compute_knowledge_diffusion",
            "run_id": run_id,
            "root_count": len(roots),
            "unresolved_count": unresolved,
            "duration_ms": duration_ms,
        },
    )
    return _document(
        family=spec.family_id.value,
        algorithm_version=spec.algorithm_version,
        run_id=run_id,
        input_revision=input_revision,
        evidence_stages=frozenset(spec.evidence_inputs),
        population=spec.population,
        denominator=spec.denominator,
        availability=availability,
        values={
            "reach_world_delivery": reach_world,
            "reach_receiver_trace": reach_trace,
            "reach_belief_activation": reach_belief,
            "mean_first_adoption_tick": mean_first,
            "mean_hops_to_adoption": mean_hops,
            "branch_count": int(branch_count),
            "root_count": len(roots),
        },
        coverage=MetricCoverage(
            observed=len(hops) - unresolved,
            expected=len(hops),
            ratio=None if not hops else float(len(hops) - unresolved) / float(len(hops)),
        ),
        notes_code="ok" if availability is MetricAvailability.PRESENT else "unresolved",
    )


def compute_rumor_distortion(
    report: SocialTransmissionReport | None = None,
    *,
    distortions: Sequence[TransmissionDistortion] | None = None,
    hops: Sequence[TransmissionHopRecord] | None = None,
    run_id: str,
    input_revision: str,
    unresolved_link_count: int | None = None,
) -> MetricDocument:
    """Structured concept/relation edits and confidence attenuation."""
    started = time.perf_counter()
    run_id = require_stable_id("run_id", run_id)
    input_revision = require_stable_id("input_revision", input_revision)
    spec = metric_specification(MetricFamilyId.RUMOR_DISTORTION)

    if report is not None:
        distortions = report.distortions
        hops = report.hops
        unresolved_link_count = report.unresolved_link_count
        run_id = report.run_id
    distortions = tuple(distortions or ())
    hops = tuple(hops or ())
    unresolved = (
        0 if unresolved_link_count is None else int(unresolved_link_count)
    )

    if not distortions:
        return _document(
            family=spec.family_id.value,
            algorithm_version=spec.algorithm_version,
            run_id=run_id,
            input_revision=input_revision,
            evidence_stages=frozenset(spec.evidence_inputs),
            population=spec.population,
            denominator=spec.denominator,
            availability=MetricAvailability.ABSENT,
            values={},
            coverage=None,
            notes_code="no_multi_hop_pairs",
        )

    concepts_added = [float(item.concepts_added) for item in distortions]
    concepts_removed = [float(item.concepts_removed) for item in distortions]
    relations_changed = [
        float(item.relations_added + item.relations_removed) for item in distortions
    ]
    attenuations: list[float] = []
    by_id = {hop.communication_id: hop for hop in hops}
    for item in distortions:
        prior = by_id.get(item.from_communication_id)
        current = by_id.get(item.to_communication_id)
        if (
            prior is not None
            and current is not None
            and prior.sender_confidence is not None
            and current.receiver_confidence is not None
        ):
            attenuations.append(
                max(0.0, float(prior.sender_confidence) - float(current.receiver_confidence))
            )

    hop_count = max(len(hops), 1)
    unresolved_coverage = quantize_float(
        require_finite(float(unresolved) / float(hop_count))
    )
    duration_ms = int((time.perf_counter() - started) * 1000)
    _LOG.debug(
        "rumor_distortion_complete",
        extra={
            "operation": "compute_rumor_distortion",
            "run_id": run_id,
            "distortion_edge_count": len(distortions),
            "duration_ms": duration_ms,
        },
    )
    return _document(
        family=spec.family_id.value,
        algorithm_version=spec.algorithm_version,
        run_id=run_id,
        input_revision=input_revision,
        evidence_stages=frozenset(spec.evidence_inputs),
        population=spec.population,
        denominator=spec.denominator,
        availability=MetricAvailability.PRESENT,
        values={
            "mean_concepts_added": quantize_float(
                require_finite(float(np.mean(concepts_added)))
            ),
            "mean_concepts_removed": quantize_float(
                require_finite(float(np.mean(concepts_removed)))
            ),
            "mean_relations_changed": quantize_float(
                require_finite(float(np.mean(relations_changed)))
            ),
            "mean_confidence_attenuation": (
                quantize_float(require_finite(float(np.mean(attenuations))))
                if attenuations
                else None
            ),
            "unresolved_coverage": unresolved_coverage,
            "distortion_edge_count": len(distortions),
        },
        coverage=MetricCoverage(
            observed=len(distortions),
            expected=len(distortions),
            ratio=1.0,
        ),
        notes_code="ok",
    )
