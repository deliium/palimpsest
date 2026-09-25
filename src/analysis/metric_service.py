"""Run-level metric orchestration from one EvidenceManifest (Task 16).

Assembles catalog metric families into canonical quantized documents. Lifecycle
and persistence live in ``experiments``; this module stays analysis-only.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from analysis.behavior_metrics import (
    compute_behavioral_specialization,
    compute_repeated_conventions,
)
from analysis.belief_metrics import (
    compute_belief_accuracy,
    compute_false_belief_persistence,
)
from analysis.memory_drift import compute_memory_drift
from analysis.memory_dynamics_metrics import compute_memory_dynamics
from analysis.models import (
    ActionResolutionRow,
    AppliedActionRow,
    BeliefClaimRow,
    GoalTransitionRow,
    MemoryDriftReport,
    MemoryDynamicsReport,
    MetricDocument,
    RelationshipEdgeRow,
    ResourceHoldingRow,
    SocialTransmissionReport,
    SurvivalAgentRow,
    TransmissionHopRecord,
)
from analysis.network_metrics import (
    compute_group_community_structure,
    compute_trust_network_structure,
)
from analysis.objective_metrics import (
    compute_action_resolution_rates,
    compute_conflict,
    compute_cooperation,
    compute_goal_completion,
    compute_resource_inequality,
    compute_survival,
)
from analysis.offline_consolidation_metrics import (
    OfflineConsolidationReport,
    compute_offline_consolidation,
)
from analysis.reflection_metrics import ReflectionReport, compute_reflection
from analysis.relationship_metrics import compute_relationship_stability
from analysis.serialization import (
    encode_metric_document,
    metric_document_fingerprint,
)
from analysis.specifications import MetricFamilyId, metric_specification
from analysis.transmission_metrics import (
    compute_knowledge_diffusion,
    compute_rumor_distortion,
)
from analysis.truth import ClaimTruthSpec
from world.identifiers import require_exact_nonneg_int, require_stable_id

__all__ = [
    "MetricBundle",
    "MetricComputationInputs",
    "assemble_metric_documents",
    "compare_metric_documents",
    "documents_compatible",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.metric_service")


@dataclass(frozen=True, slots=True)
class MetricComputationInputs:
    """Detached evidence slices for one manifest-scoped metric assembly."""

    run_id: str
    input_revision: str
    window_end: int
    applied_actions: Sequence[AppliedActionRow] = ()
    action_resolutions: Sequence[ActionResolutionRow] = ()
    resource_holdings: Sequence[ResourceHoldingRow] = ()
    survival_agents: Sequence[SurvivalAgentRow] = ()
    goal_transitions: Sequence[GoalTransitionRow] = ()
    belief_claims: Sequence[BeliefClaimRow] = ()
    truth_specs: Sequence[ClaimTruthSpec] = ()
    relationship_rows: Sequence[RelationshipEdgeRow] = ()
    agent_ids: Sequence[str] = ()
    death_ticks: Mapping[str, int] | None = None
    memory_drift_report: MemoryDriftReport | None = None
    memory_dynamics_report: MemoryDynamicsReport | None = None
    offline_consolidation_report: OfflineConsolidationReport | None = None
    reflection_report: ReflectionReport | None = None
    transmission_hops: Sequence[TransmissionHopRecord] = ()
    transmission_report: SocialTransmissionReport | None = None
    eligible_agent_ids: Sequence[str] = ()


@dataclass(frozen=True, slots=True)
class MetricBundle:
    """Ordered metric documents for one evidence revision."""

    run_id: str
    input_revision: str
    documents: tuple[MetricDocument, ...]
    fingerprints: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "run_id", require_stable_id("MetricBundle.run_id", self.run_id)
        )
        object.__setattr__(
            self,
            "input_revision",
            require_stable_id("MetricBundle.input_revision", self.input_revision),
        )


def documents_compatible(left: MetricDocument, right: MetricDocument) -> bool:
    """True when schema/algorithm/library/population/denominator/revision match."""
    if left.schema_version != right.schema_version:
        return False
    if left.metric_family != right.metric_family:
        return False
    if left.algorithm_version != right.algorithm_version:
        return False
    if left.population != right.population:
        return False
    if left.denominator != right.denominator:
        return False
    if left.input_revision != right.input_revision:
        return False
    if dict(left.library_versions) != dict(right.library_versions):
        return False
    return True


def compare_metric_documents(
    left: MetricDocument, right: MetricDocument
) -> Mapping[str, object] | None:
    """Return value deltas when compatible; None when incompatible."""
    if not documents_compatible(left, right):
        _LOG.warning(
            "metric_compare_incompatible",
            extra={
                "operation": "compare_metric_documents",
                "reason_code": "incompatible",
                "metric_family": left.metric_family,
            },
        )
        return None
    keys = sorted(set(left.values) | set(right.values))
    deltas: dict[str, object] = {}
    for key in keys:
        lv = left.values.get(key)
        rv = right.values.get(key)
        if lv == rv:
            continue
        if isinstance(lv, float) and isinstance(rv, float):
            deltas[key] = rv - lv
        else:
            deltas[key] = {"left": lv, "right": rv}
    return deltas


def assemble_metric_documents(inputs: MetricComputationInputs) -> MetricBundle:
    """Compute all available V1 metric families from one detached input set."""
    started = time.perf_counter()
    if type(inputs) is not MetricComputationInputs:
        raise TypeError("assemble_metric_documents: invalid_inputs")
    run_id = require_stable_id("run_id", inputs.run_id)
    revision = require_stable_id("input_revision", inputs.input_revision)
    window_end = require_exact_nonneg_int("window_end", inputs.window_end)
    deaths = dict(inputs.death_ticks or {})
    documents: list[MetricDocument] = []

    def _safe(label: str, factory: object) -> None:
        try:
            doc = factory()  # type: ignore[operator]
        except Exception:
            _LOG.error(
                "metric_family_failed",
                extra={
                    "operation": "assemble_metric_documents",
                    "run_id": run_id,
                    "metric_family": label,
                    "reason_code": "calculation_failed",
                },
            )
            raise
        documents.append(doc)

    _safe(
        "resource_inequality",
        lambda: compute_resource_inequality(
            inputs.resource_holdings,
            run_id=run_id,
            input_revision=revision,
            measure_id="inventory_count",
        ),
    )
    _safe(
        "cooperation",
        lambda: compute_cooperation(
            inputs.applied_actions,
            run_id=run_id,
            input_revision=revision,
            window_start=0,
            window_end=window_end,
            death_ticks=deaths,
            agent_ids=inputs.agent_ids,
        ),
    )
    _safe(
        "conflict",
        lambda: compute_conflict(
            inputs.applied_actions,
            run_id=run_id,
            input_revision=revision,
            window_start=0,
            window_end=window_end,
            death_ticks=deaths,
            agent_ids=inputs.agent_ids,
        ),
    )
    _safe(
        "survival",
        lambda: compute_survival(
            inputs.survival_agents,
            run_id=run_id,
            input_revision=revision,
            final_tick=window_end,
        ),
    )
    _safe(
        "goal_completion",
        lambda: compute_goal_completion(
            inputs.goal_transitions,
            run_id=run_id,
            input_revision=revision,
        ),
    )
    _safe(
        "action_resolution_rates",
        lambda: compute_action_resolution_rates(
            inputs.action_resolutions,
            run_id=run_id,
            input_revision=revision,
        ),
    )
    _safe(
        "repeated_conventions",
        lambda: compute_repeated_conventions(
            inputs.applied_actions,
            run_id=run_id,
            input_revision=revision,
            window_end=window_end,
        ),
    )
    _safe(
        "behavioral_specialization",
        lambda: compute_behavioral_specialization(
            inputs.applied_actions,
            run_id=run_id,
            input_revision=revision,
            window_end=window_end,
            death_ticks=deaths,
        ),
    )
    if inputs.memory_drift_report is not None:
        _safe(
            "memory_drift",
            lambda: compute_memory_drift(
                inputs.memory_drift_report, input_revision=revision
            ),
        )
    if inputs.memory_dynamics_report is not None:
        _safe(
            "memory_dynamics",
            lambda: compute_memory_dynamics(
                inputs.memory_dynamics_report, input_revision=revision
            ),
        )
    if inputs.offline_consolidation_report is not None:
        _safe(
            "offline_consolidation",
            lambda: compute_offline_consolidation(
                inputs.offline_consolidation_report, input_revision=revision
            ),
        )
    if inputs.reflection_report is not None:
        _safe(
            "reflection",
            lambda: compute_reflection(
                inputs.reflection_report, input_revision=revision
            ),
        )
    _safe(
        "belief_accuracy",
        lambda: compute_belief_accuracy(
            inputs.belief_claims,
            inputs.truth_specs,
            run_id=run_id,
            input_revision=revision,
        ),
    )
    _safe(
        "false_belief_persistence",
        lambda: compute_false_belief_persistence(
            inputs.belief_claims,
            inputs.truth_specs,
            run_id=run_id,
            input_revision=revision,
            run_end_tick=window_end,
            death_ticks=deaths,
        ),
    )
    _safe(
        "relationship_stability",
        lambda: compute_relationship_stability(
            inputs.relationship_rows,
            run_id=run_id,
            input_revision=revision,
            window_end=window_end,
            death_ticks=deaths,
        ),
    )
    _safe(
        "trust_network_structure",
        lambda: compute_trust_network_structure(
            inputs.relationship_rows,
            run_id=run_id,
            input_revision=revision,
            agent_ids=inputs.agent_ids,
            death_ticks=deaths,
        ),
    )
    _safe(
        "group_community_structure",
        lambda: compute_group_community_structure(
            inputs.relationship_rows,
            run_id=run_id,
            input_revision=revision,
            agent_ids=inputs.agent_ids,
            death_ticks=deaths,
        ),
    )
    eligible = inputs.eligible_agent_ids or inputs.agent_ids
    hops = inputs.transmission_hops
    if inputs.transmission_report is not None:
        hops = inputs.transmission_report.hops
    _safe(
        "knowledge_diffusion",
        lambda: compute_knowledge_diffusion(
            hops,
            run_id=run_id,
            input_revision=revision,
            eligible_agent_ids=eligible,
            death_ticks=deaths,
            branch_count=(
                None
                if inputs.transmission_report is None
                else inputs.transmission_report.branch_count
            ),
        ),
    )
    _safe(
        "rumor_distortion",
        lambda: compute_rumor_distortion(
            inputs.transmission_report,
            hops=hops,
            run_id=run_id,
            input_revision=revision,
            unresolved_link_count=(
                None
                if inputs.transmission_report is None
                else inputs.transmission_report.unresolved_link_count
            ),
        ),
    )

    documents.sort(key=lambda doc: doc.metric_family)
    fingerprints = tuple(metric_document_fingerprint(doc) for doc in documents)
    # Touch encode path to ensure canonical bytes are stable.
    for doc in documents:
        encode_metric_document(doc)
        # Validate family is known when present in catalog.
        if doc.metric_family != "action_resolution_rates":
            metric_specification(MetricFamilyId(doc.metric_family))

    duration_ms = int((time.perf_counter() - started) * 1000)
    _LOG.debug(
        "metric_assembly_complete",
        extra={
            "operation": "assemble_metric_documents",
            "run_id": run_id,
            "document_count": len(documents),
            "input_revision_prefix": revision[:12],
            "duration_ms": duration_ms,
        },
    )
    return MetricBundle(
        run_id=run_id,
        input_revision=revision,
        documents=tuple(documents),
        fingerprints=fingerprints,
    )
