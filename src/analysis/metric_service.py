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
from analysis.belief_convergence_metrics import compute_belief_convergence
from analysis.belief_metrics import (
    compute_belief_accuracy,
    compute_false_belief_persistence,
)
from analysis.cultural_feature_metrics import (
    compute_cultural_feature_mutation,
    compute_cultural_feature_provenance,
    compute_cultural_trait_diffusion,
)
from analysis.cultural_similarity_metrics import compute_cultural_similarity
from analysis.dependency_care_metrics import (
    compute_caregiver_diversity,
    compute_caregiving_burden,
    compute_dependency_survival,
    compute_intergenerational_cooperation,
)
from analysis.developmental_learning_metrics import (
    compute_developmental_acquisition,
    compute_developmental_divergence,
    compute_developmental_source_mix,
)
from analysis.durable_record_metrics import (
    compute_durable_record_fidelity,
    compute_durable_record_lineage,
    compute_durable_record_survival,
)
from analysis.historical_memory_metrics import (
    compute_historical_memory_layers,
    compute_historical_memory_queries,
    compute_historical_memory_transitions,
)
from analysis.kinship_genealogy_metrics import compute_kinship_genealogy
from analysis.memory_drift import compute_memory_drift
from analysis.memory_dynamics_metrics import compute_memory_dynamics
from analysis.mentorship_metrics import (
    compute_mentorship_bonds,
    compute_mentorship_fidelity,
    compute_mentorship_mutation,
)
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
    compute_survival_cohort_contrast,
)
from analysis.offline_consolidation_metrics import (
    OfflineConsolidationReport,
    compute_offline_consolidation,
)
from analysis.prediction_calibration_metrics import compute_prediction_calibration
from analysis.reflection_metrics import ReflectionReport, compute_reflection
from analysis.relationship_metrics import compute_relationship_stability
from analysis.reputation_metrics import compute_distributed_reputation
from analysis.serialization import (
    encode_metric_document,
    metric_document_fingerprint,
)
from analysis.spatial_control_metrics import compute_spatial_control
from analysis.specifications import MetricFamilyId, metric_specification
from analysis.territorial_concentration_metrics import compute_territorial_concentration
from analysis.transmission_metrics import (
    compute_knowledge_diffusion,
    compute_rumor_distortion,
)
from analysis.truth import ClaimTruthSpec
from world.identifiers import require_exact_nonneg_int, require_stable_id

_NON_CATALOG_FAMILIES: Final[frozenset[str]] = frozenset(
    {"action_resolution_rates", "survival_cohort_contrast"}
)

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
    spatial_action_rows: Sequence[object] | None = None
    spatial_claim_rows: Sequence[object] | None = None
    kinship_edge_rows: Sequence[object] | None = None
    kinship_known_agent_ids: Sequence[str] | None = None
    kinship_max_depth: int = 8
    dependency_agent_rows: Sequence[object] | None = None
    dependency_care_act_rows: Sequence[object] | None = None
    developmental_acquisition_audits: Sequence[object] | None = None
    developmental_knowledge_ledgers: Sequence[object] | None = None
    mentorship_audits: Sequence[object] | None = None
    mentorship_ledgers: Sequence[object] | None = None
    cultural_feature_audits: Sequence[object] | None = None
    cultural_feature_generation_index: Mapping[str, int] | None = None
    historical_memory_harvest: object | None = None
    durable_record_rows: Sequence[object] | None = None
    durable_record_event_rows: Sequence[object] | None = None
    death_ticks_by_body: Mapping[str, int] | None = None
    false_record_expectations: Sequence[object] | None = None
    territorial_presence_rows: Sequence[object] | None = None
    territorial_control_rows: Sequence[object] | None = None
    belief_convergence_claims: Sequence[object] | None = None
    cultural_naming_rows: Sequence[object] | None = None
    cultural_norms_rows: Sequence[object] | None = None
    cultural_conventions_rows: Sequence[object] | None = None
    cultural_narratives_rows: Sequence[object] | None = None
    prediction_calibration_rows: Sequence[object] | None = None
    reputation_ledgers: Sequence[object] | None = None
    reputation_neighborhoods: Mapping[str, str] | None = None
    reputation_target_id: str | None = None
    survival_cohort_map: Mapping[str, Sequence[str]] | None = None


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
    if inputs.spatial_action_rows is not None:
        actions = inputs.spatial_action_rows
        claims = inputs.spatial_claim_rows
        _safe(
            "spatial_control",
            lambda: compute_spatial_control(
                actions,
                claims,
                run_id=run_id,
                input_revision=revision,
            ),
        )
    if inputs.kinship_edge_rows is not None:
        kinship_rows = inputs.kinship_edge_rows
        known = inputs.kinship_known_agent_ids
        depth = inputs.kinship_max_depth
        _safe(
            "kinship_genealogy",
            lambda: compute_kinship_genealogy(
                kinship_rows,
                run_id=run_id,
                input_revision=revision,
                known_agent_ids=known,
                max_depth=depth,
            ),
        )
    if inputs.dependency_agent_rows is not None:
        dep_agents = inputs.dependency_agent_rows
        _safe(
            "dependency_survival",
            lambda: compute_dependency_survival(
                dep_agents,
                run_id=run_id,
                input_revision=revision,
            ),
        )
    if inputs.dependency_care_act_rows is not None:
        care_acts = inputs.dependency_care_act_rows
        _safe(
            "caregiver_diversity",
            lambda: compute_caregiver_diversity(
                care_acts,
                run_id=run_id,
                input_revision=revision,
            ),
        )
        _safe(
            "caregiving_burden",
            lambda: compute_caregiving_burden(
                care_acts,
                run_id=run_id,
                input_revision=revision,
            ),
        )
        _safe(
            "intergenerational_cooperation",
            lambda: compute_intergenerational_cooperation(
                care_acts,
                run_id=run_id,
                input_revision=revision,
            ),
        )
    if inputs.developmental_acquisition_audits is not None:
        dev_audits = inputs.developmental_acquisition_audits
        _safe(
            "developmental_acquisition",
            lambda: compute_developmental_acquisition(
                dev_audits,
                run_id=run_id,
                input_revision=revision,
            ),
        )
        _safe(
            "developmental_source_mix",
            lambda: compute_developmental_source_mix(
                dev_audits,
                run_id=run_id,
                input_revision=revision,
            ),
        )
    if inputs.developmental_knowledge_ledgers is not None:
        ledgers = inputs.developmental_knowledge_ledgers
        _safe(
            "developmental_divergence",
            lambda: compute_developmental_divergence(
                ledgers,
                run_id=run_id,
                input_revision=revision,
            ),
        )
    if inputs.mentorship_audits is not None:
        mentorship_rows = inputs.mentorship_audits
        _safe(
            "mentorship_fidelity",
            lambda: compute_mentorship_fidelity(
                mentorship_rows,
                run_id=run_id,
                input_revision=revision,
            ),
        )
        _safe(
            "mentorship_mutation",
            lambda: compute_mentorship_mutation(
                mentorship_rows,
                run_id=run_id,
                input_revision=revision,
            ),
        )
        _safe(
            "mentorship_bonds",
            lambda: compute_mentorship_bonds(
                mentorship_rows,
                run_id=run_id,
                input_revision=revision,
                ledgers=inputs.mentorship_ledgers,
            ),
        )
    elif inputs.mentorship_ledgers is not None:
        _safe(
            "mentorship_bonds",
            lambda: compute_mentorship_bonds(
                (),
                run_id=run_id,
                input_revision=revision,
                ledgers=inputs.mentorship_ledgers,
            ),
        )
    if inputs.cultural_feature_audits is not None:
        cultural_rows = inputs.cultural_feature_audits
        gen_map = inputs.cultural_feature_generation_index
        _safe(
            "cultural_feature_provenance",
            lambda: compute_cultural_feature_provenance(
                cultural_rows,
                run_id=run_id,
                input_revision=revision,
            ),
        )
        _safe(
            "cultural_trait_diffusion",
            lambda: compute_cultural_trait_diffusion(
                cultural_rows,
                run_id=run_id,
                input_revision=revision,
                generation_index_by_owner=gen_map,
            ),
        )
        _safe(
            "cultural_feature_mutation",
            lambda: compute_cultural_feature_mutation(
                cultural_rows,
                run_id=run_id,
                input_revision=revision,
            ),
        )
    if inputs.historical_memory_harvest is not None:
        hm_harvest = inputs.historical_memory_harvest
        _safe(
            "historical_memory_layers",
            lambda: compute_historical_memory_layers(
                hm_harvest,
                run_id=run_id,
                input_revision=revision,
            ),
        )
        _safe(
            "historical_memory_transitions",
            lambda: compute_historical_memory_transitions(
                hm_harvest,
                run_id=run_id,
                input_revision=revision,
            ),
        )
        _safe(
            "historical_memory_queries",
            lambda: compute_historical_memory_queries(
                hm_harvest,
                run_id=run_id,
                input_revision=revision,
            ),
        )
    if (
        inputs.durable_record_rows is not None
        or inputs.durable_record_event_rows is not None
    ):
        durable_rows = tuple(inputs.durable_record_rows or ())
        durable_events = tuple(inputs.durable_record_event_rows or ())
        death_by_body = dict(inputs.death_ticks_by_body or deaths)
        false_expectations = tuple(inputs.false_record_expectations or ())
        _LOG.debug(
            "metric_assemble family_id=durable_record_lineage source_count=%s",
            len(durable_rows),
        )
        _safe(
            "durable_record_lineage",
            lambda: compute_durable_record_lineage(
                durable_rows,
                run_id=run_id,
                input_revision=revision,
            ),
        )
        _LOG.debug(
            "metric_assemble family_id=durable_record_fidelity source_count=%s",
            len(durable_events),
        )
        _safe(
            "durable_record_fidelity",
            lambda: compute_durable_record_fidelity(
                durable_events,
                run_id=run_id,
                input_revision=revision,
                record_rows=durable_rows,
            ),
        )
        _LOG.debug(
            "metric_assemble family_id=durable_record_survival source_count=%s",
            len(durable_rows),
        )
        _safe(
            "durable_record_survival",
            lambda: compute_durable_record_survival(
                durable_rows,
                run_id=run_id,
                input_revision=revision,
                death_ticks_by_body=death_by_body,
                false_record_expectations=false_expectations,
            ),
        )
    optional_blocks = {
        "kinship_genealogy": inputs.kinship_edge_rows is not None,
        "dependency_care": (
            inputs.dependency_agent_rows is not None
            or inputs.dependency_care_act_rows is not None
        ),
        "developmental_learning": (
            inputs.developmental_acquisition_audits is not None
            or inputs.developmental_knowledge_ledgers is not None
        ),
        "mentorship": (
            inputs.mentorship_audits is not None
            or inputs.mentorship_ledgers is not None
        ),
        "cultural_features": inputs.cultural_feature_audits is not None,
        "historical_memory": inputs.historical_memory_harvest is not None,
        "durable_records": (
            inputs.durable_record_rows is not None
            or inputs.durable_record_event_rows is not None
        ),
        "territorial_presence": inputs.territorial_presence_rows is not None,
        "territorial_control": inputs.territorial_control_rows is not None,
        "belief_convergence": inputs.belief_convergence_claims is not None,
        "cultural_channels": any(
            block is not None
            for block in (
                inputs.cultural_naming_rows,
                inputs.cultural_norms_rows,
                inputs.cultural_conventions_rows,
                inputs.cultural_narratives_rows,
            )
        ),
        "prediction_calibration": inputs.prediction_calibration_rows is not None,
        "reputation": inputs.reputation_ledgers is not None,
        "survival_cohort": inputs.survival_cohort_map is not None,
    }
    _LOG.debug(
        "metric_optional_inputs",
        extra={
            "operation": "assemble_metric_documents",
            "run_id": run_id,
            "optional_blocks_attached": {
                key: value for key, value in optional_blocks.items() if value
            },
        },
    )
    if (
        inputs.territorial_presence_rows is not None
        or inputs.territorial_control_rows is not None
    ):
        presence = inputs.territorial_presence_rows
        control = inputs.territorial_control_rows
        _safe(
            "territorial_concentration",
            lambda: compute_territorial_concentration(
                presence,
                control,
                run_id=run_id,
                input_revision=revision,
            ),
        )
    if inputs.belief_convergence_claims is not None:
        claims = inputs.belief_convergence_claims
        _safe(
            "belief_convergence",
            lambda: compute_belief_convergence(
                claims,
                run_id=run_id,
                input_revision=revision,
            ),
        )
    if optional_blocks["cultural_channels"]:
        naming = inputs.cultural_naming_rows
        norms = inputs.cultural_norms_rows
        conventions = inputs.cultural_conventions_rows
        narratives = inputs.cultural_narratives_rows
        _safe(
            "cultural_similarity",
            lambda: compute_cultural_similarity(
                naming_rows=naming,
                norms_rows=norms,
                conventions_rows=conventions,
                narratives_rows=narratives,
                run_id=run_id,
                input_revision=revision,
            ),
        )
    if inputs.prediction_calibration_rows is not None:
        calibration_rows = inputs.prediction_calibration_rows
        _safe(
            "prediction_calibration",
            lambda: compute_prediction_calibration(
                calibration_rows,
                run_id=run_id,
                input_revision=revision,
            ),
        )
    if inputs.reputation_ledgers is not None:
        ledgers = inputs.reputation_ledgers
        neighborhoods = inputs.reputation_neighborhoods or {}
        target = inputs.reputation_target_id or "target"
        _safe(
            "distributed_reputation",
            lambda: compute_distributed_reputation(
                ledgers,
                neighborhoods,
                target_id=target,
                run_id=run_id,
                input_revision=revision,
            ).document,
        )
    if inputs.survival_cohort_map is not None:
        cohort_map = inputs.survival_cohort_map
        sibling = compute_survival_cohort_contrast(
            inputs.survival_agents,
            cohort_map,
            run_id=run_id,
            input_revision=revision,
            final_tick=window_end,
        )
        if sibling is not None:
            documents.append(sibling)
        else:
            _LOG.warning(
                "metric_optional_skip",
                extra={
                    "operation": "assemble_metric_documents",
                    "run_id": run_id,
                    "metric_family": "survival_cohort_contrast",
                    "reason_code": "empty_cohort_map",
                },
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
        if doc.metric_family not in _NON_CATALOG_FAMILIES:
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
