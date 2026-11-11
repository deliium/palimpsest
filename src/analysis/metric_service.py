"""Run-level metric orchestration from one EvidenceManifest (Task 16).

Assembles catalog metric families into canonical quantized documents. Lifecycle
and persistence live in ``experiments``; this module stays analysis-only.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final, cast

from analysis.behavior_metrics import (
    compute_behavioral_specialization,
    compute_repeated_conventions,
)
from analysis.belief_convergence_metrics import compute_belief_convergence
from analysis.belief_metrics import (
    compute_belief_accuracy,
    compute_false_belief_persistence,
)
from analysis.contact_cultural_change import compute_contact_cultural_change_metric
from analysis.contact_hybrid_practice import compute_contact_hybrid_practice_metric
from analysis.contact_inputs import ContactAnalysisInputs
from analysis.contact_knowledge_transfer import (
    compute_contact_knowledge_transfer_metric,
)
from analysis.contact_lexical_borrowing import compute_contact_lexical_borrowing_metric
from analysis.contact_reputation_transfer import (
    compute_contact_reputation_transfer_metric,
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
from analysis.generational_cohort import (
    compute_generational_cohort_comparison,
)
from analysis.generational_narratives import (
    compute_generational_narrative_continuity,
    compute_narrative_historical_alignment,
    compute_narrative_source_loss,
    generational_narrative_inputs_from_harvest,
)
from analysis.historical_memory_metrics import (
    compute_historical_memory_layers,
    compute_historical_memory_queries,
    compute_historical_memory_transitions,
)
from analysis.infrastructure_metrics import (
    InfrastructureNetworksAnalysis,
    compute_infrastructure_condition_lifecycle,
    compute_infrastructure_effect_coverage,
    compute_infrastructure_maintenance_burden,
    compute_infrastructure_network_structure,
    compute_travel_route_belief_alignment,
    compute_travel_route_blockage,
    compute_travel_route_condition,
    compute_travel_route_structure,
)
from analysis.inter_society_relations_detection import InterSocietyRelationsAnalysis
from analysis.inter_society_relations_metrics import (
    compute_inter_society_domain_evidence,
    compute_inter_society_pair_comparison,
    compute_inter_society_relation_structure,
    compute_inter_society_relation_timeseries,
)
from analysis.kinship_genealogy_metrics import compute_kinship_genealogy
from analysis.knowledge_genealogy_metrics import (
    compute_knowledge_genealogy_holders,
    compute_knowledge_genealogy_lineage,
    compute_knowledge_genealogy_mutation,
)
from analysis.knowledge_repository_metrics import (
    compute_knowledge_repository_access,
    compute_knowledge_repository_organization,
    compute_knowledge_repository_survival,
)
from analysis.macro_society_lineage import MacroSocietyAnalysis
from analysis.macro_society_metrics import (
    compute_macro_society_identity_alignment_metric,
    compute_macro_society_lineage_metric,
    compute_macro_society_membership_dispute_metric,
    compute_macro_society_structure_metric,
)
from analysis.market_institutions_analysis import MarketInstitutionsAnalysis
from analysis.market_institutions_metrics import (
    compute_market_expectation_structure,
    compute_market_role_structure,
    compute_market_venue_persistence,
    compute_market_venue_recurrence,
)
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
from analysis.possession_succession_metrics import (
    assemble_possession_succession_metrics,
)
from analysis.prediction_calibration_metrics import compute_prediction_calibration
from analysis.reflection_metrics import ReflectionReport, compute_reflection
from analysis.regional_destination_beliefs import (
    RegionalDestinationEvidenceRow,
    compute_regional_destination_beliefs,
)
from analysis.regional_migration_metrics import compute_regional_migration_metrics
from analysis.regional_population import (
    RegionalPopulationInput,
    compute_regional_population,
)
from analysis.relationship_metrics import compute_relationship_stability
from analysis.reputation_metrics import compute_distributed_reputation
from analysis.semantic_drift_metrics import (
    SemanticAnalysisInputs,
    compute_semantic_divergence,
    compute_semantic_divergence_metric,
    compute_semantic_drift,
    compute_semantic_drift_metric,
    compute_semantic_stability,
    compute_semantic_stability_metric,
)
from analysis.serialization import (
    encode_metric_document,
    metric_document_fingerprint,
)
from analysis.society_contact import compute_society_contact_metric
from analysis.society_divergence import (
    SocietyDivergenceResult,
    compute_society_divergence_metric,
)
from analysis.society_emergence import (
    SocietyEmissionResult,
    compute_society_emergence,
)
from analysis.society_isolation import (
    SocietyIsolationResult,
    compute_society_isolation_metric,
)
from analysis.spatial_control_metrics import compute_spatial_control
from analysis.specifications import MetricFamilyId, metric_specification
from analysis.structured_commitments_metrics import (
    assemble_structured_commitment_metrics,
)
from analysis.subjective_value_metrics import assemble_subjective_value_metrics
from analysis.supply_chain_analysis import SupplyChainAnalysis
from analysis.supply_chain_metrics import (
    compute_supply_bottleneck_pressure,
    compute_supply_chain_structure,
    compute_supply_dependency_graph,
    compute_supply_location_infrastructure_reliance,
    compute_supply_organization_coordination,
    compute_supply_resource_tool_dependency,
)
from analysis.symbolic_language_metrics import (
    SymbolicAnalysisInputs,
    compute_symbolic_composition,
    compute_symbolic_composition_metric,
    compute_symbolic_message_flow,
    compute_symbolic_message_flow_metric,
    compute_symbolic_social_distribution,
    compute_symbolic_social_distribution_metric,
)
from analysis.technique_lifecycle_metrics import assemble_technique_lifecycle_metrics
from analysis.territorial_concentration_metrics import compute_territorial_concentration
from analysis.trade_networks_analysis import TradeNetworksAnalysis
from analysis.trade_networks_metrics import (
    compute_cross_society_trade_flows,
    compute_trade_corridor_structure,
    compute_trade_dependence,
    compute_trade_flow_composition,
    compute_trade_location_centrality,
    compute_trade_network_lineage,
)
from analysis.translation_metrics import (
    compute_cross_group_translation,
    compute_cross_group_translation_metric,
    compute_translation_influence,
    compute_translation_influence_metric,
    compute_translation_learning,
    compute_translation_learning_metric,
)
from analysis.transmission_metrics import (
    compute_knowledge_diffusion,
    compute_rumor_distortion,
)
from analysis.truth import ClaimTruthSpec
from simulation.generational_models import PopulationProgress
from simulation.runner_models import TechniqueLifecycleSpec
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
    repository_objective_rows: Sequence[object] | None = None
    repository_event_rows: Sequence[object] | None = None
    founder_death_ticks: Mapping[str, int] | None = None
    inaccessible_expectations: Sequence[object] | None = None
    practical_knowledge_audits: Sequence[object] | None = None
    technique_lifecycle_spec: TechniqueLifecycleSpec | None = None
    possession_succession_spec: object | None = None
    possession_events: Sequence[object] | None = None
    possession_ledgers: Sequence[object] | None = None
    structured_commitments_spec: object | None = None
    structured_commitment_events: Sequence[object] | None = None
    structured_commitment_ledgers: Sequence[object] | None = None
    structured_commitment_owner_ids: Sequence[str] | None = None
    structured_commitment_consequence_counts: Mapping[str, int] | None = None
    subjective_valuation_spec: object | None = None
    resource_exchange_profile_spec: object | None = None
    collective_projects_spec: object | None = None
    public_goods_spec: object | None = None
    collective_project_events: Sequence[object] | None = None
    subjective_valuation_events: Sequence[object] | None = None
    subjective_valuation_ledgers: Sequence[object] | None = None
    subjective_valuation_owner_ids: Sequence[str] | None = None
    technique_node_rows: Sequence[object] | None = None
    technique_item_rows: Sequence[object] | None = None
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
    institutional_decay_rows: Sequence[object] | None = None
    institutional_decay_context_rows: Sequence[object] | None = None
    institutional_memory_rows: Sequence[object] | None = None
    institutional_memory_carrier_rows: Sequence[object] | None = None
    institutional_memory_identity_rows: Sequence[object] | None = None
    regional_population: RegionalPopulationInput | None = None
    generational_progress: PopulationProgress | None = None
    regional_destination_evidence: Sequence[RegionalDestinationEvidenceRow] | None = (
        None
    )
    regional_destination_expected_owner_count: int | None = None
    society_emission: SocietyEmissionResult | None = None
    society_divergence: SocietyDivergenceResult | None = None
    society_isolation: SocietyIsolationResult | None = None
    society_community_count: int = 0
    macro_society_analysis: MacroSocietyAnalysis | None = None
    organization_rows: Sequence[object] | None = None
    organization_operation_rows: Sequence[object] | None = None
    organization_agency_rows: Sequence[object] | None = None
    formal_rule_rows: object | None = None
    dispute_rows: object | None = None
    dispute_objective_rows: Sequence[object] | None = None
    evidence_rows: object | None = None
    evidence_objective_rows: Sequence[object] | None = None
    representation_rows: object | None = None
    representation_objective_rows: Sequence[object] | None = None
    diplomacy_rows: object | None = None
    diplomacy_objective_rows: Sequence[object] | None = None
    diplomacy_lane_rows: Sequence[object] | None = None
    diplomacy_treaty_alignment: Sequence[object] | None = None
    organized_conflict_rows: object | None = None
    organized_conflict_objective_rows: Sequence[object] | None = None
    organized_conflict_interpretation_alignment: Sequence[object] | None = None
    border_rows: object | None = None
    border_claim_rows: Sequence[object] | None = None
    border_agreement_rows: Sequence[object] | None = None
    border_physical_rows: Sequence[object] | None = None
    border_pattern_rows: Sequence[object] | None = None
    border_alignment_rows: Sequence[object] | None = None
    border_overlap_rows: Sequence[object] | None = None
    migration_displacement_rows: object | None = None
    migration_displacement_movement_rows: Sequence[object] | None = None
    migration_displacement_evidence_rows: Sequence[object] | None = None
    migration_displacement_kinship_pairs: Sequence[tuple[str, str]] | None = None
    migration_displacement_communication_pairs: Sequence[tuple[str, str]] | None = None
    migration_displacement_organization_pairs: Sequence[tuple[str, str]] | None = None
    inter_society_relations_analysis: InterSocietyRelationsAnalysis | None = None
    infrastructure_networks_analysis: InfrastructureNetworksAnalysis | None = None
    travel_network_analysis: InfrastructureNetworksAnalysis | None = None
    trade_networks_analysis: TradeNetworksAnalysis | None = None
    supply_chain_analysis: SupplyChainAnalysis | None = None
    market_institutions_analysis: MarketInstitutionsAnalysis | None = None
    contact_analysis: object | None = None
    symbolic_analysis: object | None = None
    semantic_drift_analysis: SemanticAnalysisInputs | None = None
    translation_analysis: object | None = None
    institution_role_rows: Sequence[object] | None = None
    institution_procedure_rows: Sequence[object] | None = None
    institution_expectation_rows: Sequence[object] | None = None
    institution_legitimacy_rows: Sequence[object] | None = None
    institution_succession_rows: Sequence[object] | None = None
    institution_continuity_rows: Sequence[object] | None = None
    institution_known_person_ids: Sequence[str] | None = None
    office_rows: Sequence[object] | None = None
    collective_decision_rows: Sequence[object] | None = None
    mediation_rows: Sequence[object] | None = None
    mediation_effects: Sequence[object] | None = None
    collective_decision_effects: Sequence[object] | None = None
    cultural_evolution: object | None = None
    cultural_evolution_evidence_digest: str | None = None


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
    if inputs.regional_population is not None and (
        inputs.regional_population.run_id != run_id
        or inputs.regional_population.input_revision != revision
    ):
        raise ValueError("regional_population_scope_mismatch")
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
        if getattr(hm_harvest, "layers_spec", None) is not None:
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
        if getattr(hm_harvest, "cultural_narrative_ledgers", ()):
            gen_inputs = generational_narrative_inputs_from_harvest(hm_harvest)
            _safe(
                "generational_narrative_continuity",
                lambda: compute_generational_narrative_continuity(
                    gen_inputs.generation_rows,
                    run_id=run_id,
                    input_revision=revision,
                    tick=inputs.window_end,
                    transition_counts=gen_inputs.transition_counts,
                ),
            )
            _safe(
                "narrative_source_loss",
                lambda: compute_narrative_source_loss(
                    gen_inputs.source_loss_rows,
                    run_id=run_id,
                    input_revision=revision,
                    tick=inputs.window_end,
                ),
            )
            _safe(
                "narrative_historical_alignment",
                lambda: compute_narrative_historical_alignment(
                    gen_inputs.comparison_rows,
                    run_id=run_id,
                    input_revision=revision,
                    tick=inputs.window_end,
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
    if (
        inputs.repository_objective_rows is not None
        or inputs.repository_event_rows is not None
    ):
        repository_rows = tuple(inputs.repository_objective_rows or ())
        repository_events = tuple(inputs.repository_event_rows or ())
        founder_deaths = dict(inputs.founder_death_ticks or {})
        inaccessible_expectations = tuple(inputs.inaccessible_expectations or ())
        _LOG.debug(
            "metric_assemble family_id=knowledge_repository_survival source_count=%s",
            len(repository_rows),
        )
        _safe(
            "knowledge_repository_survival",
            lambda: compute_knowledge_repository_survival(
                repository_rows,
                run_id=run_id,
                input_revision=revision,
                founder_death_ticks=founder_deaths,
            ),
        )
        _LOG.debug(
            "metric_assemble family_id=knowledge_repository_access source_count=%s",
            len(repository_events),
        )
        _safe(
            "knowledge_repository_access",
            lambda: compute_knowledge_repository_access(
                repository_events,
                run_id=run_id,
                input_revision=revision,
                objective_rows=repository_rows,
                inaccessible_expectations=inaccessible_expectations,
            ),
        )
        _LOG.debug(
            "metric_assemble family_id=knowledge_repository_organization "
            "source_count=%s",
            len(repository_rows) + len(repository_events),
        )
        _safe(
            "knowledge_repository_organization",
            lambda: compute_knowledge_repository_organization(
                repository_rows,
                run_id=run_id,
                input_revision=revision,
                event_rows=repository_events,
            ),
        )
    if inputs.practical_knowledge_audits is not None:
        pk_audits = tuple(inputs.practical_knowledge_audits)
        _LOG.debug(
            "metric_assemble family_id=knowledge_genealogy_holders source_count=%s",
            len(pk_audits),
        )
        _safe(
            "knowledge_genealogy_holders",
            lambda: compute_knowledge_genealogy_holders(
                pk_audits,
                run_id=run_id,
                input_revision=revision,
                as_of_tick=inputs.window_end,
                death_ticks=inputs.death_ticks,
            ),
        )
        _LOG.debug(
            "metric_assemble family_id=knowledge_genealogy_lineage source_count=%s",
            len(pk_audits),
        )
        _safe(
            "knowledge_genealogy_lineage",
            lambda: compute_knowledge_genealogy_lineage(
                pk_audits,
                run_id=run_id,
                input_revision=revision,
                as_of_tick=inputs.window_end,
                death_ticks=inputs.death_ticks,
            ),
        )
        _LOG.debug(
            "metric_assemble family_id=knowledge_genealogy_mutation source_count=%s",
            len(pk_audits),
        )
        _safe(
            "knowledge_genealogy_mutation",
            lambda: compute_knowledge_genealogy_mutation(
                pk_audits,
                run_id=run_id,
                input_revision=revision,
            ),
        )
    if inputs.technique_lifecycle_spec is not None and (
        inputs.practical_knowledge_audits is not None
    ):
        lifecycle_audits = tuple(inputs.practical_knowledge_audits)
        node_rows = tuple(inputs.technique_node_rows or ())
        item_rows = tuple(inputs.technique_item_rows or ())
        artifact_rows = tuple(inputs.durable_record_rows or ())
        _LOG.debug(
            "technique_lifecycle_harvest node_count=%s item_count=%s "
            "artifact_location_rows=%s",
            len(node_rows),
            len(item_rows),
            sum(
                1
                for row in artifact_rows
                if isinstance(row, Mapping) and row.get("location_id")
            ),
        )

        try:
            documents.extend(
                assemble_technique_lifecycle_metrics(
                    lifecycle_audits,
                    run_id=run_id,
                    input_revision=revision,
                    spec=inputs.technique_lifecycle_spec,
                    as_of_tick=window_end,
                    death_ticks=inputs.death_ticks,
                    artifact_rows=artifact_rows,
                    applied_actions=inputs.applied_actions,
                    mentorship_audits=tuple(inputs.mentorship_audits or ()),
                    node_rows=node_rows,
                    item_rows=item_rows,
                )
            )
        except Exception:
            _LOG.error(
                "metric_family_failed",
                extra={
                    "operation": "assemble_metric_documents",
                    "run_id": run_id,
                    "metric_family": "technique_lifecycle",
                    "reason_code": "calculation_failed",
                },
            )
            raise
    if inputs.possession_succession_spec is not None:
        possession_events = tuple(inputs.possession_events or ())
        possession_ledgers = tuple(inputs.possession_ledgers or ())
        try:
            documents.extend(
                assemble_possession_succession_metrics(
                    possession_events,  # type: ignore[arg-type]
                    run_id=run_id,
                    input_revision=revision,
                    spec=inputs.possession_succession_spec,
                    as_of_tick=window_end,
                    ledgers=possession_ledgers,  # type: ignore[arg-type]
                )
            )
        except Exception:
            _LOG.error(
                "metric_family_failed",
                extra={
                    "operation": "assemble_metric_documents",
                    "run_id": run_id,
                    "metric_family": "possession_succession",
                    "reason_code": "calculation_failed",
                },
            )
            raise
    if inputs.structured_commitments_spec is not None:
        commitment_events = tuple(inputs.structured_commitment_events or ())
        commitment_ledgers = tuple(inputs.structured_commitment_ledgers or ())
        owner_ids = tuple(inputs.structured_commitment_owner_ids or ())
        try:
            documents.extend(
                assemble_structured_commitment_metrics(
                    commitment_events,  # type: ignore[arg-type]
                    run_id=run_id,
                    input_revision=revision,
                    spec=inputs.structured_commitments_spec,
                    as_of_tick=window_end,
                    ledgers=commitment_ledgers,  # type: ignore[arg-type]
                    owner_ids=owner_ids,
                    consequence_counts=inputs.structured_commitment_consequence_counts,
                )
            )
        except Exception:
            _LOG.error(
                "metric_family_failed",
                extra={
                    "operation": "assemble_metric_documents",
                    "run_id": run_id,
                    "metric_family": "structured_commitments",
                    "reason_code": "calculation_failed",
                },
            )
            raise
    if inputs.subjective_valuation_spec is not None:
        valuation_events = tuple(inputs.subjective_valuation_events or ())
        valuation_ledgers = tuple(inputs.subjective_valuation_ledgers or ())
        valuation_owners = tuple(inputs.subjective_valuation_owner_ids or ())
        try:
            documents.extend(
                assemble_subjective_value_metrics(
                    valuation_events,  # type: ignore[arg-type]
                    run_id=run_id,
                    input_revision=revision,
                    spec=inputs.subjective_valuation_spec,
                    as_of_tick=window_end,
                    ledgers=valuation_ledgers,  # type: ignore[arg-type]
                    owner_ids=valuation_owners,
                )
            )
        except Exception:
            _LOG.error(
                "metric_family_failed",
                extra={
                    "operation": "assemble_metric_documents",
                    "run_id": run_id,
                    "metric_family": "subjective_valuation",
                    "reason_code": "calculation_failed",
                },
            )
            raise
    if inputs.resource_exchange_profile_spec is None:
        _LOG.info(
            "exchange_functions_metrics_empty reason=resource_exchange_profile_absent"
        )
    else:
        from analysis.exchange_functions_metrics import (
            assemble_exchange_function_metrics,
        )
        from analysis.specifications import METRIC_FAMILY_COUNT, validate_metric_catalog

        try:
            catalog = validate_metric_catalog()
        except Exception:
            _LOG.error(
                "metric_catalog_count_drift expected=%s",
                METRIC_FAMILY_COUNT,
            )
            raise
        if len(catalog) != METRIC_FAMILY_COUNT:
            _LOG.error(
                "metric_catalog_count_drift expected=%s observed=%s",
                METRIC_FAMILY_COUNT,
                len(catalog),
            )
            raise ValueError(
                f"validate_metric_catalog count drifted from {METRIC_FAMILY_COUNT}"
            )
        try:
            documents.extend(
                assemble_exchange_function_metrics(
                    tuple(inputs.subjective_valuation_events or ()),  # type: ignore[arg-type]
                    run_id=run_id,
                    input_revision=revision,
                    spec=inputs.resource_exchange_profile_spec,
                    as_of_tick=window_end,
                    ledgers=tuple(inputs.subjective_valuation_ledgers or ()),
                )
            )
        except Exception:
            _LOG.error(
                "metric_family_failed",
                extra={
                    "operation": "assemble_metric_documents",
                    "run_id": run_id,
                    "metric_family": "resource_exchange_profile",
                    "reason_code": "calculation_failed",
                },
            )
            raise
    if inputs.collective_projects_spec is None:
        logging.getLogger("analysis.collective_project_metrics").info(
            "collective_project_metrics_empty reason=collective_projects_absent"
        )
    else:
        from analysis.collective_project_metrics import (
            assemble_collective_project_metrics,
        )

        try:
            documents.extend(
                assemble_collective_project_metrics(
                    tuple(inputs.collective_project_events or ()),  # type: ignore[arg-type]
                    run_id=run_id,
                    input_revision=revision,
                    spec=inputs.collective_projects_spec,
                    as_of_tick=window_end,
                )
            )
        except Exception:
            _LOG.error(
                "metric_family_failed",
                extra={
                    "operation": "assemble_metric_documents",
                    "run_id": run_id,
                    "metric_family": "collective_projects",
                    "reason_code": "calculation_failed",
                },
            )
            raise
    if inputs.public_goods_spec is None:
        logging.getLogger("analysis.public_good_metrics").info(
            "public_good_metrics_empty reason=public_goods_absent"
        )
    else:
        from analysis.public_good_metrics import assemble_public_good_metrics

        try:
            documents.extend(
                assemble_public_good_metrics(
                    tuple(inputs.collective_project_events or ()),  # type: ignore[arg-type]
                    run_id=run_id,
                    input_revision=revision,
                    spec=inputs.public_goods_spec,
                    as_of_tick=window_end,
                )
            )
        except Exception:
            _LOG.error(
                "metric_family_failed",
                extra={
                    "operation": "assemble_metric_documents",
                    "run_id": run_id,
                    "metric_family": "public_goods",
                    "reason_code": "calculation_failed",
                },
            )
            raise
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
        "knowledge_repositories": (
            inputs.repository_objective_rows is not None
            or inputs.repository_event_rows is not None
        ),
        "knowledge_genealogy": inputs.practical_knowledge_audits is not None,
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
        "society_emergence": inputs.society_emission is not None,
        "society_divergence": inputs.society_divergence is not None,
        "society_isolation": inputs.society_isolation is not None,
        "contact_analysis": inputs.contact_analysis is not None,
        "translation_analysis": inputs.translation_analysis is not None,
        "generational_cohort_comparison": inputs.generational_progress is not None,
        "institution_analysis": any(
            block is not None
            for block in (
                inputs.institution_role_rows,
                inputs.institution_procedure_rows,
                inputs.institution_expectation_rows,
                inputs.institution_legitimacy_rows,
                inputs.institution_succession_rows,
                inputs.institution_continuity_rows,
            )
        ),
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
            lambda: (
                compute_distributed_reputation(
                    ledgers,
                    neighborhoods,
                    target_id=target,
                    run_id=run_id,
                    input_revision=revision,
                ).document
            ),
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
    if inputs.society_emission is not None:
        emission = inputs.society_emission
        _safe(
            "society_emergence",
            lambda: compute_society_emergence(
                emission,
                run_id=run_id,
                input_revision=revision,
            ),
        )

    if inputs.society_divergence is not None:
        divergence = inputs.society_divergence
        community_count = inputs.society_community_count
        _safe(
            "society_divergence",
            lambda: compute_society_divergence_metric(
                divergence,
                run_id=run_id,
                input_revision=revision,
                community_count=community_count,
            ),
        )
    if inputs.society_isolation is not None:
        isolation = inputs.society_isolation
        community_count = inputs.society_community_count
        _safe(
            "society_isolation",
            lambda: compute_society_isolation_metric(
                isolation,
                run_id=run_id,
                input_revision=revision,
                community_count=community_count,
            ),
        )

    if inputs.macro_society_analysis is not None:
        macro_analysis = inputs.macro_society_analysis
        _safe(
            "macro_society_structure",
            lambda: compute_macro_society_structure_metric(
                macro_analysis,
                run_id=run_id,
                input_revision=revision,
            ),
        )
        _safe(
            "macro_society_identity_alignment",
            lambda: compute_macro_society_identity_alignment_metric(
                macro_analysis,
                run_id=run_id,
                input_revision=revision,
            ),
        )
        _safe(
            "macro_society_lineage",
            lambda: compute_macro_society_lineage_metric(
                macro_analysis,
                run_id=run_id,
                input_revision=revision,
            ),
        )
        _safe(
            "macro_society_membership_dispute",
            lambda: compute_macro_society_membership_dispute_metric(
                macro_analysis,
                run_id=run_id,
                input_revision=revision,
            ),
        )

    if inputs.organization_rows:
        from analysis.organization_agency import (
            harvest_organization_agency_rows,
            summarize_organization_agency,
        )
        from analysis.organization_detection import detect_organization_candidates
        from analysis.organization_evidence import build_organization_windows
        from analysis.organization_identity import assign_organization_identities
        from analysis.organization_layers import project_organization_layers
        from analysis.organization_lineage import derive_organization_lineage
        from analysis.organization_metrics import (
            compute_organization_collective_agency_metric,
            compute_organization_collective_implementation_metric,
            compute_organization_formation_metric,
            compute_organization_lineage_metric,
            compute_organization_membership_metric,
            compute_organization_operation_authority_metric,
            compute_organization_operations_metric,
            compute_organization_structure_metric,
        )
        from analysis.organization_operations import (
            harvest_organization_operation_rows,
            summarize_organization_operations,
        )
        from analysis.organizations import harvest_organization_rows

        organization_rows = harvest_organization_rows(inputs.organization_rows)
        windows = build_organization_windows(organization_rows, 100)
        detection = detect_organization_candidates(windows)
        assignment = assign_organization_identities(detection)
        operation_rows = harvest_organization_operation_rows(
            inputs.organization_operation_rows
        )
        operation_summary = summarize_organization_operations(
            operation_rows, assignment
        )
        agency_rows = harvest_organization_agency_rows(inputs.organization_agency_rows)
        agency_summary = summarize_organization_agency(
            agency_rows, assignment, member_rows=organization_rows
        )
        layers = project_organization_layers(
            assignment,
            organization_rows,
            operation_rows=operation_rows,
            operation_summary=operation_summary,
            agency_rows=agency_rows,
            agency_summary=agency_summary,
        )
        organization_analysis = derive_organization_lineage(
            assignment,
            layer_view=layers,
            operation_summary=operation_summary,
            agency_summary=agency_summary,
            history_truncated=any(
                "history_truncated" in row.owner.notices for row in organization_rows
            ),
        )
        _safe(
            "organization_formation",
            lambda: compute_organization_formation_metric(
                organization_analysis,
                run_id=run_id,
                input_revision=revision,
                tick=window_end,
            ),
        )
        _safe(
            "organization_membership",
            lambda: compute_organization_membership_metric(
                organization_analysis,
                run_id=run_id,
                input_revision=revision,
                tick=window_end,
            ),
        )
        _safe(
            "organization_structure",
            lambda: compute_organization_structure_metric(
                organization_analysis,
                run_id=run_id,
                input_revision=revision,
                tick=window_end,
            ),
        )
        _safe(
            "organization_lineage",
            lambda: compute_organization_lineage_metric(
                organization_analysis,
                run_id=run_id,
                input_revision=revision,
            ),
        )
        _safe(
            "organization_operations",
            lambda: compute_organization_operations_metric(
                operation_summary,
                run_id=run_id,
                input_revision=revision,
                tick=window_end,
            ),
        )
        _safe(
            "organization_operation_authority",
            lambda: compute_organization_operation_authority_metric(
                operation_summary,
                run_id=run_id,
                input_revision=revision,
                tick=window_end,
            ),
        )
        _safe(
            "organization_collective_agency",
            lambda: compute_organization_collective_agency_metric(
                organization_analysis,
                run_id=run_id,
                input_revision=revision,
                tick=window_end,
            ),
        )
        _safe(
            "organization_collective_implementation",
            lambda: compute_organization_collective_implementation_metric(
                organization_analysis,
                run_id=run_id,
                input_revision=revision,
                tick=window_end,
            ),
        )

    if inputs.formal_rule_rows:
        from analysis.formal_rule_evidence import build_formal_rule_windows
        from analysis.formal_rule_layers import project_formal_rule_layers
        from analysis.formal_rule_lineage import (
            derive_formal_rule_lineage,
            summarize_formal_rules,
        )
        from analysis.formal_rule_metrics import (
            compute_formal_rule_authority_metric,
            compute_formal_rule_development_metric,
            compute_formal_rule_response_metric,
        )
        from analysis.formal_rules import (
            FormalRuleHarvestRows,
            harvest_formal_rule_rows,
        )

        formal_rows = (
            inputs.formal_rule_rows
            if type(inputs.formal_rule_rows) is FormalRuleHarvestRows
            else harvest_formal_rule_rows(
                cast("Sequence[object]", inputs.formal_rule_rows),
                window_ticks=100,
            )
        )
        formal_windows = build_formal_rule_windows(formal_rows, window_ticks=100)
        formal_analysis = derive_formal_rule_lineage(formal_rows, formal_windows)
        formal_summary = summarize_formal_rules(formal_rows, formal_analysis)
        formal_layers = project_formal_rule_layers(
            formal_rows,
            formal_analysis,
            formal_summary,
            windows=formal_windows,
        )
        _safe(
            "formal_rule_development",
            lambda: compute_formal_rule_development_metric(
                formal_summary,
                formal_layers,
                run_id=run_id,
                input_revision=revision,
            ),
        )
        _safe(
            "formal_rule_authority",
            lambda: compute_formal_rule_authority_metric(
                formal_summary,
                formal_layers,
                run_id=run_id,
                input_revision=revision,
            ),
        )
        _safe(
            "formal_rule_response",
            lambda: compute_formal_rule_response_metric(
                formal_summary,
                formal_layers,
                run_id=run_id,
                input_revision=revision,
            ),
        )

    if inputs.dispute_rows is not None:
        from analysis.dispute_evidence import (
            DisputeObjectiveAnchorRow,
            build_dispute_windows,
        )
        from analysis.dispute_layers import project_dispute_layers
        from analysis.dispute_lineage import (
            derive_dispute_lineage,
            summarize_disputes,
        )
        from analysis.dispute_metrics import (
            compute_dispute_claim_structure,
            compute_dispute_resolution_alignment,
            compute_dispute_testimony_independence,
        )
        from analysis.disputes import (
            DisputeHarvestRows,
            harvest_dispute_rows,
        )

        dispute_rows = (
            inputs.dispute_rows
            if type(inputs.dispute_rows) is DisputeHarvestRows
            else harvest_dispute_rows(
                cast("Sequence[object]", inputs.dispute_rows),
                window_ticks=100,
            )
        )
        dispute_anchors = cast(
            "Sequence[DisputeObjectiveAnchorRow]",
            tuple(inputs.dispute_objective_rows or ()),
        )
        dispute_windows = build_dispute_windows(
            dispute_rows,
            window_ticks=100,
            objective_rows=dispute_anchors,
        )
        dispute_analysis = derive_dispute_lineage(
            dispute_rows,
            dispute_windows,
            objective_rows=dispute_anchors,
        )
        dispute_summary = summarize_disputes(dispute_rows, dispute_analysis)
        dispute_layers = project_dispute_layers(
            dispute_rows,
            dispute_analysis,
            dispute_summary,
            windows=dispute_windows,
            objective_rows=dispute_anchors,
        )
        _safe(
            "dispute_claim_structure",
            lambda: compute_dispute_claim_structure(
                dispute_summary,
                dispute_layers,
                run_id=run_id,
                input_revision=revision,
            ),
        )
        _safe(
            "dispute_testimony_independence",
            lambda: compute_dispute_testimony_independence(
                dispute_summary,
                dispute_rows,
                run_id=run_id,
                input_revision=revision,
            ),
        )
        _safe(
            "dispute_resolution_alignment",
            lambda: compute_dispute_resolution_alignment(
                dispute_summary,
                dispute_analysis,
                dispute_layers,
                run_id=run_id,
                input_revision=revision,
            ),
        )

    if inputs.evidence_rows is not None:
        from analysis.evidence_testimony_alignment import derive_evidence_lineage
        from analysis.evidence_testimony_layers import project_evidence_layers
        from analysis.evidence_testimony_metrics import (
            compute_evidence_objective_alignment,
            compute_evidence_provenance_continuity,
            compute_evidence_source_structure,
        )
        from analysis.evidence_testimony_objective import (
            EvidenceObjectiveAnchorRow,
            build_evidence_windows,
        )
        from analysis.evidence_testimony_rows import (
            EvidenceHarvestRows,
            harvest_evidence_rows,
        )

        evidence_rows = (
            inputs.evidence_rows
            if type(inputs.evidence_rows) is EvidenceHarvestRows
            else harvest_evidence_rows(
                cast("Sequence[object]", inputs.evidence_rows),
                window_ticks=100,
            )
        )
        evidence_anchors = cast(
            "Sequence[EvidenceObjectiveAnchorRow]",
            tuple(inputs.evidence_objective_rows or ()),
        )
        evidence_windows = build_evidence_windows(
            evidence_rows,
            window_ticks=100,
            objective_rows=evidence_anchors,
        )
        evidence_analysis = derive_evidence_lineage(
            evidence_rows,
            objective_rows=evidence_anchors,
            window_ticks=100,
        )
        evidence_layers = project_evidence_layers(
            evidence_rows,
            evidence_analysis,
            evidence_analysis.summary,
            windows=evidence_windows,
            objective_rows=evidence_anchors,
        )
        _safe(
            "evidence_source_structure",
            lambda: compute_evidence_source_structure(
                evidence_rows,
                evidence_analysis,
                evidence_analysis.summary,
                evidence_layers,
                run_id=run_id,
                input_revision=revision,
            ),
        )
        _safe(
            "evidence_provenance_continuity",
            lambda: compute_evidence_provenance_continuity(
                evidence_rows,
                evidence_analysis,
                evidence_analysis.summary,
                evidence_layers,
                run_id=run_id,
                input_revision=revision,
            ),
        )
        _safe(
            "evidence_objective_alignment",
            lambda: compute_evidence_objective_alignment(
                evidence_rows,
                evidence_analysis,
                evidence_analysis.summary,
                evidence_layers,
                run_id=run_id,
                input_revision=revision,
            ),
        )

    if inputs.representation_rows is not None:
        from analysis.delegation_representation_alignment import (
            summarize_representation,
        )
        from analysis.delegation_representation_identity import (
            derive_representation_lineage,
        )
        from analysis.delegation_representation_layers import (
            project_representation_layers,
        )
        from analysis.delegation_representation_metrics import (
            compute_representation_mandate_structure,
            compute_representation_recognition_support,
            compute_representation_scope_alignment,
        )
        from analysis.delegation_representation_objective import (
            RepresentationObjectiveAnchorRow,
            build_representation_windows,
        )
        from analysis.delegation_representation_rows import (
            RepresentationHarvestRows,
            harvest_representation_rows,
        )

        representation_rows = (
            inputs.representation_rows
            if type(inputs.representation_rows) is RepresentationHarvestRows
            else harvest_representation_rows(
                cast("Sequence[object]", inputs.representation_rows),
                entity_to_agent={},
            )
        )
        representation_anchors = cast(
            "Sequence[RepresentationObjectiveAnchorRow]",
            tuple(inputs.representation_objective_rows or ()),
        )
        representation_windows = build_representation_windows(
            representation_rows,
            window_ticks=100,
            objective_rows=representation_anchors,
        )
        representation_analysis = derive_representation_lineage(
            representation_rows,
            objective_rows=tuple(representation_anchors),
            window_ticks=100,
        )
        representation_summary = summarize_representation(
            representation_rows,
            representation_analysis,
            anchors=representation_anchors,
            windows=representation_windows,
        )
        representation_layers = project_representation_layers(
            representation_rows,
            representation_analysis,
            representation_summary,
            windows=representation_windows,
            objective_rows=representation_anchors,
        )
        _safe(
            "representation_mandate_structure",
            lambda: compute_representation_mandate_structure(
                representation_rows,
                representation_analysis,
                representation_summary,
                representation_layers,
                run_id=run_id,
                input_revision=revision,
            ),
        )
        _safe(
            "representation_recognition_support",
            lambda: compute_representation_recognition_support(
                representation_rows,
                representation_analysis,
                representation_summary,
                representation_layers,
                run_id=run_id,
                input_revision=revision,
            ),
        )
        _safe(
            "representation_scope_alignment",
            lambda: compute_representation_scope_alignment(
                representation_rows,
                representation_analysis,
                representation_summary,
                representation_layers,
                run_id=run_id,
                input_revision=revision,
            ),
        )

    if inputs.diplomacy_rows is not None:
        from analysis.diplomacy_alignment import (
            TreatyRecollectionAlignmentRow,
            classify_diplomacy_envoy_alignment,
            classify_treaty_recollection_alignment,
            summarize_diplomacy,
        )
        from analysis.diplomacy_detection import detect_diplomacy_candidates
        from analysis.diplomacy_identity import (
            assign_diplomacy_identities,
        )
        from analysis.diplomacy_lanes import InterSocietyRelationRow
        from analysis.diplomacy_layers import project_diplomacy_layers
        from analysis.diplomacy_metrics import (
            compute_diplomatic_contact_structure,
            compute_diplomatic_envoy_alignment,
            compute_diplomatic_instrument_outcomes,
            compute_inter_society_relation_lanes,
            compute_treaty_anchor_coverage,
            compute_treaty_recollection,
            compute_treaty_structure,
            compute_treaty_version_lineage,
        )
        from analysis.diplomacy_objective import DiplomacyObjectiveAnchorRow
        from analysis.diplomacy_rows import (
            DiplomacyHarvestRows,
            harvest_diplomacy_rows,
        )

        diplomacy_rows = (
            inputs.diplomacy_rows
            if type(inputs.diplomacy_rows) is DiplomacyHarvestRows
            else harvest_diplomacy_rows(
                cast("Sequence[object]", inputs.diplomacy_rows),
                entity_to_agent={},
            )
        )
        diplomacy_lane_rows = tuple(
            cast("Sequence[InterSocietyRelationRow]", inputs.diplomacy_lane_rows or ())
        )
        diplomacy_candidates = detect_diplomacy_candidates(
            diplomacy_rows, diplomacy_lane_rows
        )
        diplomacy_analysis = assign_diplomacy_identities(diplomacy_candidates)
        diplomacy_alignment = classify_diplomacy_envoy_alignment(diplomacy_rows)
        diplomacy_treaty_alignment = (
            tuple(inputs.diplomacy_treaty_alignment)
            if inputs.diplomacy_treaty_alignment is not None
            else classify_treaty_recollection_alignment(diplomacy_rows)
        )
        diplomacy_layers = project_diplomacy_layers(
            diplomacy_rows,
            diplomacy_candidates,
            diplomacy_analysis,
            objective_rows=cast(
                "tuple[DiplomacyObjectiveAnchorRow, ...]",
                tuple(inputs.diplomacy_objective_rows or ()),
            ),
            coverage=diplomacy_rows.coverage.value,
        )
        diplomacy_summary = summarize_diplomacy(
            diplomacy_rows,
            diplomacy_candidates,
            diplomacy_layers,
            diplomacy_alignment,
            cast(
                "Sequence[TreatyRecollectionAlignmentRow]",
                diplomacy_treaty_alignment,
            ),
        )
        _safe(
            "diplomatic_contact_structure",
            lambda: compute_diplomatic_contact_structure(
                diplomacy_rows,
                diplomacy_summary,
                diplomacy_layers,
                run_id=run_id,
                input_revision=revision,
            ),
        )
        _safe(
            "diplomatic_instrument_outcomes",
            lambda: compute_diplomatic_instrument_outcomes(
                diplomacy_rows,
                diplomacy_summary,
                diplomacy_layers,
                run_id=run_id,
                input_revision=revision,
            ),
        )
        _safe(
            "diplomatic_envoy_alignment",
            lambda: compute_diplomatic_envoy_alignment(
                diplomacy_rows,
                diplomacy_summary,
                diplomacy_layers,
                run_id=run_id,
                input_revision=revision,
                alignment=diplomacy_alignment,
            ),
        )
        _safe(
            "inter_society_relation_lanes",
            lambda: compute_inter_society_relation_lanes(
                diplomacy_rows,
                diplomacy_summary,
                diplomacy_layers,
                run_id=run_id,
                input_revision=revision,
                candidates=diplomacy_candidates,
            ),
        )
        _safe(
            "treaty_structure",
            lambda: compute_treaty_structure(
                diplomacy_rows,
                run_id=run_id,
                input_revision=revision,
            ),
        )
        _safe(
            "treaty_version_lineage",
            lambda: compute_treaty_version_lineage(
                diplomacy_rows,
                run_id=run_id,
                input_revision=revision,
            ),
        )
        _safe(
            "treaty_recollection",
            lambda: compute_treaty_recollection(
                diplomacy_rows,
                diplomacy_treaty_alignment,
                run_id=run_id,
                input_revision=revision,
            ),
        )
        _safe(
            "treaty_anchor_coverage",
            lambda: compute_treaty_anchor_coverage(
                diplomacy_rows,
                run_id=run_id,
                input_revision=revision,
            ),
        )

    if inputs.organized_conflict_rows is not None:
        from analysis.organized_conflict_alignment import (
            ConflictAlignmentRow,
            align_conflict_interpretations,
            summarize_organized_conflict,
        )
        from analysis.organized_conflict_detection import (
            detect_organized_conflict_episodes,
        )
        from analysis.organized_conflict_identity import (
            assign_organized_conflict_identities,
            derive_organized_conflict_lineage,
            join_organized_conflict_identities,
        )
        from analysis.organized_conflict_layers import project_conflict_layers
        from analysis.organized_conflict_metrics import (
            compute_organized_conflict_interpretation,
            compute_organized_conflict_outcomes,
            compute_organized_conflict_participation,
            compute_organized_conflict_persistence,
        )
        from analysis.organized_conflict_policy import (
            default_organized_conflict_analysis_policy,
        )
        from analysis.organized_conflict_rows import (
            OrganizedConflictHarvestRows,
            harvest_organized_conflict_rows,
        )

        conflict_policy = default_organized_conflict_analysis_policy()
        if type(inputs.organized_conflict_rows) is OrganizedConflictHarvestRows:
            organized_conflict_rows = inputs.organized_conflict_rows
        else:
            organized_conflict_rows = harvest_organized_conflict_rows(
                cast("Sequence[object]", inputs.organized_conflict_rows),
                tuple(inputs.organized_conflict_objective_rows or ()),
                policy=conflict_policy,
            )
        conflict_candidates = detect_organized_conflict_episodes(
            organized_conflict_rows.objective_events, policy=conflict_policy
        )
        conflict_candidates = assign_organized_conflict_identities(conflict_candidates)
        _ = derive_organized_conflict_lineage(conflict_candidates)
        conflict_candidates = join_organized_conflict_identities(conflict_candidates)
        _ = project_conflict_layers(organized_conflict_rows, conflict_candidates)
        conflict_alignment = (
            cast(
                "Sequence[ConflictAlignmentRow]",
                tuple(inputs.organized_conflict_interpretation_alignment),
            )
            if inputs.organized_conflict_interpretation_alignment is not None
            else align_conflict_interpretations(
                organized_conflict_rows.owner_interpretations,
                conflict_candidates,
            )
        )
        conflict_summary = summarize_organized_conflict(
            organized_conflict_rows,
            conflict_candidates,
            conflict_alignment,
        )
        _safe(
            "organized_conflict_participation",
            lambda: compute_organized_conflict_participation(
                organized_conflict_rows,
                conflict_candidates,
                run_id=run_id,
                input_revision=revision,
            ),
        )
        _safe(
            "organized_conflict_persistence",
            lambda: compute_organized_conflict_persistence(
                organized_conflict_rows,
                conflict_candidates,
                run_id=run_id,
                input_revision=revision,
            ),
        )
        _safe(
            "organized_conflict_outcomes",
            lambda: compute_organized_conflict_outcomes(
                organized_conflict_rows,
                conflict_candidates,
                run_id=run_id,
                input_revision=revision,
            ),
        )
        _safe(
            "organized_conflict_interpretation",
            lambda: compute_organized_conflict_interpretation(
                organized_conflict_rows,
                conflict_candidates,
                conflict_alignment,
                conflict_summary,
                run_id=run_id,
                input_revision=revision,
            ),
        )

    if inputs.border_rows is not None or inputs.border_claim_rows is not None:
        from analysis.borders_alignment import align_border_interpretations
        from analysis.borders_contract import (
            BorderAgreementRow,
            BorderAlignmentRow,
            BorderClaimRow,
            BorderOverlapRow,
            BorderPatternRow,
        )
        from analysis.borders_detection import (
            detect_border_disputes,
            detect_border_overlaps,
            detect_control_patterns,
        )
        from analysis.borders_events import BorderPhysicalRow
        from analysis.borders_metrics import (
            compute_border_agreement_recognition,
            compute_border_claim_structure,
            compute_border_control_alignment,
            compute_border_overlap_contest,
        )
        from analysis.borders_policy import default_borders_analysis_policy
        from analysis.borders_rows import BorderHarvestRows

        border_policy = default_borders_analysis_policy()
        if type(inputs.border_rows) is BorderHarvestRows:
            border_rows = inputs.border_rows
        else:
            border_rows = BorderHarvestRows(
                physical=tuple(
                    cast(
                        "Sequence[BorderPhysicalRow]",
                        inputs.border_physical_rows or (),
                    )
                ),
                claims=tuple(
                    cast("Sequence[BorderClaimRow]", inputs.border_claim_rows or ())
                ),
                agreements=tuple(
                    cast(
                        "Sequence[BorderAgreementRow]",
                        inputs.border_agreement_rows or (),
                    )
                ),
                coverage="partial",
            )
        overlaps = (
            tuple(cast("Sequence[BorderOverlapRow]", inputs.border_overlap_rows))
            if inputs.border_overlap_rows is not None
            else detect_border_disputes(
                detect_border_overlaps(border_rows.claims, policy=border_policy),
                border_rows.agreements,
                policy=border_policy,
            )
        )
        patterns = (
            tuple(cast("Sequence[BorderPatternRow]", inputs.border_pattern_rows))
            if inputs.border_pattern_rows is not None
            else detect_control_patterns(
                border_rows.physical,
                border_rows.claims,
                border_rows.agreements,
                border_rows.disputes,
                policy=border_policy,
            )
        )
        alignment = (
            tuple(cast("Sequence[BorderAlignmentRow]", inputs.border_alignment_rows))
            if inputs.border_alignment_rows is not None
            else align_border_interpretations(
                border_rows.claims,
                border_rows.agreements,
                patterns,
                disputes=border_rows.disputes,
            )
        )
        _safe(
            "border_claim_structure",
            lambda: compute_border_claim_structure(
                border_rows,
                run_id=run_id,
                input_revision=revision,
            ),
        )
        _safe(
            "border_overlap_contest",
            lambda: compute_border_overlap_contest(
                border_rows,
                overlaps,
                run_id=run_id,
                input_revision=revision,
            ),
        )
        _safe(
            "border_agreement_recognition",
            lambda: compute_border_agreement_recognition(
                border_rows,
                run_id=run_id,
                input_revision=revision,
            ),
        )
        _safe(
            "border_control_alignment",
            lambda: compute_border_control_alignment(
                border_rows,
                patterns,
                alignment,
                run_id=run_id,
                input_revision=revision,
            ),
        )
    if inputs.migration_displacement_rows is not None:
        from analysis.migration_displacement_events import (
            MigrationIntegrationEvidenceRow,
            MigrationMovementRow,
        )
        from analysis.migration_displacement_metrics import (
            compute_migration_cause_evidence,
            compute_migration_cluster_cohesion,
            compute_migration_integration_outcome,
            compute_migration_wave_structure,
        )
        from analysis.migration_displacement_policy import (
            default_migration_displacement_analysis_policy,
        )
        from analysis.migration_displacement_rows import (
            harvest_migration_displacement_rows,
        )

        # An already-normalized collector harvest is accepted idempotently; the
        # raw owner rows are never projected a second time.
        migration_rows = harvest_migration_displacement_rows(
            inputs.migration_displacement_rows,
            tuple(
                cast(
                    "Sequence[MigrationMovementRow]",
                    inputs.migration_displacement_movement_rows or (),
                )
            ),
            tuple(
                cast(
                    "Sequence[MigrationIntegrationEvidenceRow]",
                    inputs.migration_displacement_evidence_rows or (),
                )
            ),
            kinship_pairs=tuple(inputs.migration_displacement_kinship_pairs or ()),
            organization_pairs=tuple(
                inputs.migration_displacement_organization_pairs or ()
            ),
            communication_pairs=tuple(
                inputs.migration_displacement_communication_pairs or ()
            ),
            policy=default_migration_displacement_analysis_policy(),
        )
        _safe(
            "migration_wave_structure",
            lambda: compute_migration_wave_structure(
                migration_rows, run_id=run_id, input_revision=revision
            ),
        )
        _safe(
            "migration_cause_evidence",
            lambda: compute_migration_cause_evidence(
                migration_rows, run_id=run_id, input_revision=revision
            ),
        )
        _safe(
            "migration_cluster_cohesion",
            lambda: compute_migration_cluster_cohesion(
                migration_rows, run_id=run_id, input_revision=revision
            ),
        )
        _safe(
            "migration_integration_outcome",
            lambda: compute_migration_integration_outcome(
                migration_rows, run_id=run_id, input_revision=revision
            ),
        )
        _LOG.info("migration_metrics_emitted families=4")
    else:
        _LOG.debug("migration_metrics_disabled")
    if inputs.inter_society_relations_analysis is not None:
        isr_analysis = inputs.inter_society_relations_analysis
        _safe(
            "inter_society_relation_structure",
            lambda: compute_inter_society_relation_structure(
                isr_analysis, run_id=run_id, input_revision=revision
            ),
        )
        _safe(
            "inter_society_domain_evidence",
            lambda: compute_inter_society_domain_evidence(
                isr_analysis, run_id=run_id, input_revision=revision
            ),
        )
        _safe(
            "inter_society_relation_timeseries",
            lambda: compute_inter_society_relation_timeseries(
                isr_analysis, run_id=run_id, input_revision=revision
            ),
        )
        _safe(
            "inter_society_pair_comparison",
            lambda: compute_inter_society_pair_comparison(
                isr_analysis, run_id=run_id, input_revision=revision
            ),
        )
        _LOG.info("inter_society_relations_metrics_emitted families=4")
    else:
        _LOG.debug("inter_society_relations_metrics_disabled")
    if inputs.infrastructure_networks_analysis is not None:
        infra_analysis = inputs.infrastructure_networks_analysis
        _safe(
            "infrastructure_network_structure",
            lambda: compute_infrastructure_network_structure(
                infra_analysis, run_id=run_id, input_revision=revision
            ),
        )
        _safe(
            "infrastructure_condition_lifecycle",
            lambda: compute_infrastructure_condition_lifecycle(
                infra_analysis, run_id=run_id, input_revision=revision
            ),
        )
        _safe(
            "infrastructure_effect_coverage",
            lambda: compute_infrastructure_effect_coverage(
                infra_analysis, run_id=run_id, input_revision=revision
            ),
        )
        _safe(
            "infrastructure_maintenance_burden",
            lambda: compute_infrastructure_maintenance_burden(
                infra_analysis, run_id=run_id, input_revision=revision
            ),
        )
        _LOG.info("infrastructure_networks_metrics_emitted families=4")
    else:
        _LOG.debug("infrastructure_networks_metrics_disabled")
    route_candidate = (
        inputs.travel_network_analysis or inputs.infrastructure_networks_analysis
    )
    if route_candidate is not None:
        route_analysis = route_candidate
        _safe(
            "travel_route_structure",
            lambda: compute_travel_route_structure(
                route_analysis, run_id=run_id, input_revision=revision
            ),
        )
        _safe(
            "travel_route_condition",
            lambda: compute_travel_route_condition(
                route_analysis, run_id=run_id, input_revision=revision
            ),
        )
        _safe(
            "travel_route_blockage",
            lambda: compute_travel_route_blockage(
                route_analysis, run_id=run_id, input_revision=revision
            ),
        )
        _safe(
            "travel_route_belief_alignment",
            lambda: compute_travel_route_belief_alignment(
                route_analysis, run_id=run_id, input_revision=revision
            ),
        )
        _LOG.info("travel_network_metrics_emitted families=4 catalog=192")
    else:
        _LOG.debug("travel_network_metrics_disabled")
    if inputs.trade_networks_analysis is not None:
        trade_analysis = inputs.trade_networks_analysis
        _safe(
            "trade_corridor_structure",
            lambda: compute_trade_corridor_structure(
                trade_analysis, run_id=run_id, input_revision=revision
            ),
        )
        _safe(
            "trade_flow_composition",
            lambda: compute_trade_flow_composition(
                trade_analysis, run_id=run_id, input_revision=revision
            ),
        )
        _safe(
            "trade_location_centrality",
            lambda: compute_trade_location_centrality(
                trade_analysis, run_id=run_id, input_revision=revision
            ),
        )
        _safe(
            "trade_dependence",
            lambda: compute_trade_dependence(
                trade_analysis, run_id=run_id, input_revision=revision
            ),
        )
        _safe(
            "cross_society_trade_flows",
            lambda: compute_cross_society_trade_flows(
                trade_analysis, run_id=run_id, input_revision=revision
            ),
        )
        _safe(
            "trade_network_lineage",
            lambda: compute_trade_network_lineage(
                trade_analysis, run_id=run_id, input_revision=revision
            ),
        )
        _LOG.info("trade_networks_metrics_emitted families=6")
    else:
        _LOG.debug("trade_networks_metrics_disabled")
    if inputs.supply_chain_analysis is not None:
        supply = inputs.supply_chain_analysis
        _safe(
            "supply_chain_structure",
            lambda: compute_supply_chain_structure(
                supply, run_id=run_id, input_revision=revision
            ),
        )
        _safe(
            "supply_dependency_graph",
            lambda: compute_supply_dependency_graph(
                supply, run_id=run_id, input_revision=revision
            ),
        )
        _safe(
            "supply_bottleneck_pressure",
            lambda: compute_supply_bottleneck_pressure(
                supply, run_id=run_id, input_revision=revision
            ),
        )
        _safe(
            "supply_resource_tool_dependency",
            lambda: compute_supply_resource_tool_dependency(
                supply, run_id=run_id, input_revision=revision
            ),
        )
        _safe(
            "supply_location_infrastructure_reliance",
            lambda: compute_supply_location_infrastructure_reliance(
                supply, run_id=run_id, input_revision=revision
            ),
        )
        _safe(
            "supply_organization_coordination",
            lambda: compute_supply_organization_coordination(
                supply, run_id=run_id, input_revision=revision
            ),
        )
        _LOG.info("metric_families_assembled source=supply_chain families=6")
    else:
        _LOG.debug("supply_chain_metrics_disabled")
    if inputs.market_institutions_analysis is not None:
        market = inputs.market_institutions_analysis
        _safe(
            "market_venue_recurrence",
            lambda: compute_market_venue_recurrence(
                market, run_id=run_id, input_revision=revision
            ),
        )
        _safe(
            "market_venue_persistence",
            lambda: compute_market_venue_persistence(
                market, run_id=run_id, input_revision=revision
            ),
        )
        _safe(
            "market_expectation_structure",
            lambda: compute_market_expectation_structure(
                market, run_id=run_id, input_revision=revision
            ),
        )
        _safe(
            "market_role_structure",
            lambda: compute_market_role_structure(
                market, run_id=run_id, input_revision=revision
            ),
        )
        _LOG.info("market_institutions_metrics_emitted families=4 catalog=208")
    else:
        _LOG.debug("market_institutions_metrics_disabled")
    if inputs.contact_analysis is not None:
        if type(inputs.contact_analysis) is ContactAnalysisInputs:
            contact = inputs.contact_analysis
            _safe(
                "society_contact",
                lambda: compute_society_contact_metric(
                    contact.contact,
                    run_id=run_id,
                    input_revision=revision,
                ),
            )
            _safe(
                "contact_cultural_change",
                lambda: compute_contact_cultural_change_metric(
                    contact.cultural_change,
                    run_id=run_id,
                    input_revision=revision,
                ),
            )
            _safe(
                "contact_hybrid_practice",
                lambda: compute_contact_hybrid_practice_metric(
                    contact.hybrid_practice,
                    run_id=run_id,
                    input_revision=revision,
                ),
            )
            _safe(
                "contact_knowledge_transfer",
                lambda: compute_contact_knowledge_transfer_metric(
                    contact.knowledge_transfer,
                    run_id=run_id,
                    input_revision=revision,
                ),
            )
            _safe(
                "contact_lexical_borrowing",
                lambda: compute_contact_lexical_borrowing_metric(
                    contact.lexical_borrowing,
                    run_id=run_id,
                    input_revision=revision,
                ),
            )
            _safe(
                "contact_reputation_transfer",
                lambda: compute_contact_reputation_transfer_metric(
                    contact.reputation_transfer,
                    run_id=run_id,
                    input_revision=revision,
                ),
            )

    if inputs.symbolic_analysis is not None:
        if type(inputs.symbolic_analysis) is SymbolicAnalysisInputs:
            symbolic = inputs.symbolic_analysis
            composition = compute_symbolic_composition(
                symbolic.compositions,
                symbolic.interpretations,
                expected_owner_count=(symbolic.expected_owner_count or None),
            )
            _safe(
                "symbolic_composition",
                lambda: compute_symbolic_composition_metric(
                    composition,
                    run_id=run_id,
                    input_revision=revision,
                ),
            )
            distribution = compute_symbolic_social_distribution(symbolic)
            _safe(
                "symbolic_social_distribution",
                lambda: compute_symbolic_social_distribution_metric(
                    distribution,
                    run_id=run_id,
                    input_revision=revision,
                ),
            )
            flow = compute_symbolic_message_flow(symbolic.messages)
            _safe(
                "symbolic_message_flow",
                lambda: compute_symbolic_message_flow_metric(
                    flow,
                    run_id=run_id,
                    input_revision=revision,
                ),
            )

    if inputs.translation_analysis is not None:
        from analysis.translation_metrics import TranslationAnalysisInputs

        if type(inputs.translation_analysis) is TranslationAnalysisInputs:
            translation_inputs = inputs.translation_analysis
            _safe(
                "translation_learning",
                lambda: compute_translation_learning_metric(
                    compute_translation_learning(translation_inputs),
                    run_id=run_id,
                    input_revision=revision,
                ),
            )
            _safe(
                "cross_group_translation",
                lambda: compute_cross_group_translation_metric(
                    compute_cross_group_translation(translation_inputs),
                    run_id=run_id,
                    input_revision=revision,
                ),
            )
            _safe(
                "translation_influence",
                lambda: compute_translation_influence_metric(
                    compute_translation_influence(translation_inputs),
                    run_id=run_id,
                    input_revision=revision,
                ),
            )

    if any(
        block is not None
        for block in (
            inputs.institution_role_rows,
            inputs.institution_procedure_rows,
            inputs.institution_expectation_rows,
            inputs.institution_legitimacy_rows,
            inputs.institution_succession_rows,
            inputs.institution_continuity_rows,
        )
    ):
        from analysis.institution_emergence import (
            compute_institution_candidates,
            compute_institution_emergence,
        )
        from analysis.institutional_persistence import (
            compute_institutional_persistence,
            compute_institutional_persistence_metric,
        )

        institution_result = compute_institution_candidates(
            role_rows=inputs.institution_role_rows,
            procedure_rows=inputs.institution_procedure_rows,
            expectation_rows=inputs.institution_expectation_rows,
            legitimacy_rows=inputs.institution_legitimacy_rows,
            succession_rows=inputs.institution_succession_rows,
            continuity_rows=inputs.institution_continuity_rows,
            known_person_ids=inputs.institution_known_person_ids or (),
            tick=window_end,
        )
        _safe(
            "institution_emergence",
            lambda: compute_institution_emergence(
                institution_result,
                run_id=run_id,
                input_revision=revision,
                tick=window_end,
            ),
        )
        _safe(
            "institutional_persistence",
            lambda: compute_institutional_persistence_metric(
                compute_institutional_persistence(institution_result),
                run_id=run_id,
                input_revision=revision,
            ),
        )

    if inputs.office_rows is not None:
        from analysis.offices import (
            OfficeSnapshotRow,
            align_office_roles,
            compute_office_continuity,
            compute_office_succession,
        )

        office_rows = cast("tuple[OfficeSnapshotRow, ...]", tuple(inputs.office_rows))
        office_alignments = align_office_roles(office_rows)
        _safe(
            "office_continuity",
            lambda: compute_office_continuity(
                office_rows,
                run_id=run_id,
                input_revision=revision,
                tick=window_end,
            ),
        )
        _safe(
            "office_succession",
            lambda: compute_office_succession(
                office_rows,
                office_alignments,
                run_id=run_id,
                input_revision=revision,
                tick=window_end,
            ),
        )

    if inputs.mediation_rows is not None:
        from analysis.mediation import (
            MediationEffectRow,
            MediationSnapshot,
            compute_conflict_mediation,
            compute_mediation_role_emergence,
        )

        mediation_rows = cast(
            "tuple[MediationSnapshot, ...]", tuple(inputs.mediation_rows)
        )
        mediation_effects = cast(
            "tuple[MediationEffectRow, ...]",
            tuple(inputs.mediation_effects or ()),
        )
        _safe(
            "conflict_mediation",
            lambda: compute_conflict_mediation(
                mediation_rows,
                run_id=run_id,
                input_revision=revision,
                tick=window_end,
                effects=mediation_effects,
            ),
        )
        _safe(
            "mediation_role_emergence",
            lambda: compute_mediation_role_emergence(
                mediation_rows,
                run_id=run_id,
                input_revision=revision,
                tick=window_end,
            ),
        )

    if inputs.collective_decision_rows is not None:
        from analysis.collective_decisions import (
            CollectiveDecisionSnapshot,
            CollectiveEffectRow,
            compute_collective_decision_disagreement,
            compute_collective_decision_outcomes,
            compute_collective_decision_process,
        )

        decision_rows = cast(
            "tuple[CollectiveDecisionSnapshot, ...]",
            tuple(inputs.collective_decision_rows),
        )
        decision_effects = cast(
            "tuple[CollectiveEffectRow, ...]",
            tuple(inputs.collective_decision_effects or ()),
        )
        _safe(
            "collective_decision_process",
            lambda: compute_collective_decision_process(
                decision_rows,
                run_id=run_id,
                input_revision=revision,
                tick=window_end,
            ),
        )
        _safe(
            "collective_decision_outcomes",
            lambda: compute_collective_decision_outcomes(
                decision_rows,
                run_id=run_id,
                input_revision=revision,
                tick=window_end,
                effects=decision_effects,
            ),
        )
        _safe(
            "collective_decision_disagreement",
            lambda: compute_collective_decision_disagreement(
                decision_rows,
                run_id=run_id,
                input_revision=revision,
                tick=window_end,
            ),
        )

    if inputs.semantic_drift_analysis is not None:
        semantic = inputs.semantic_drift_analysis
        _safe(
            "semantic_stability",
            lambda: compute_semantic_stability_metric(
                compute_semantic_stability(semantic),
                run_id=run_id,
                input_revision=revision,
            ),
        )
        _safe(
            "semantic_drift",
            lambda: compute_semantic_drift_metric(
                compute_semantic_drift(semantic),
                run_id=run_id,
                input_revision=revision,
            ),
        )
        _safe(
            "semantic_divergence",
            lambda: compute_semantic_divergence_metric(
                compute_semantic_divergence(semantic),
                run_id=run_id,
                input_revision=revision,
            ),
        )

    if inputs.regional_population is not None:
        regional_inputs = inputs.regional_population
        _safe(
            "regional_population",
            lambda: compute_regional_population(regional_inputs),
        )
        _safe(
            "regional_migration",
            lambda: compute_regional_migration_metrics(regional_inputs),
        )
        destination_rows = inputs.regional_destination_evidence
        _safe(
            "regional_destination_beliefs",
            lambda: compute_regional_destination_beliefs(
                destination_rows,
                run_id=run_id,
                input_revision=revision,
                as_of_tick=window_end,
                expected_owner_count=(inputs.regional_destination_expected_owner_count),
            ),
        )

    progress = inputs.generational_progress
    if progress is not None:
        _safe(
            "generational_cohort_comparison",
            lambda: compute_generational_cohort_comparison(
                progress,
                run_id=run_id,
                input_revision=revision,
                window_end=window_end,
            ),
        )

    if inputs.institutional_decay_rows is not None:
        from analysis.institutional_decay_metrics import (
            compute_institution_lifecycle_metric,
            compute_institution_lineage_metric,
            compute_institutional_decay_metric,
        )

        _safe(
            "institutional_decay",
            lambda: compute_institutional_decay_metric(
                inputs.institutional_decay_rows,
                run_id=run_id,
                input_revision=revision,
                as_of_tick=window_end,
                context_rows=inputs.institutional_decay_context_rows or (),  # type: ignore[arg-type]
            ),
        )
        _safe(
            "institution_lifecycle",
            lambda: compute_institution_lifecycle_metric(
                inputs.institutional_decay_rows,
                run_id=run_id,
                input_revision=revision,
                as_of_tick=window_end,
                context_rows=inputs.institutional_decay_context_rows or (),  # type: ignore[arg-type]
            ),
        )
        _safe(
            "institution_lineage",
            lambda: compute_institution_lineage_metric(
                inputs.institutional_decay_rows,
                run_id=run_id,
                input_revision=revision,
                as_of_tick=window_end,
            ),
        )

    if inputs.institutional_memory_rows is not None:
        from analysis.institutional_memory import (
            compute_institutional_memory_continuity,
            compute_institutional_memory_provenance,
        )

        _safe(
            "institutional_memory_continuity",
            lambda: compute_institutional_memory_continuity(
                inputs.institutional_memory_rows,
                run_id=run_id,
                input_revision=revision,
                tick=window_end,
                carrier_rows=inputs.institutional_memory_carrier_rows,
                identity_rows=inputs.institutional_memory_identity_rows,
            ),
        )
        _safe(
            "institutional_memory_provenance",
            lambda: compute_institutional_memory_provenance(
                inputs.institutional_memory_rows,
                run_id=run_id,
                input_revision=revision,
                tick=window_end,
                carrier_rows=inputs.institutional_memory_carrier_rows,
                identity_rows=inputs.institutional_memory_identity_rows,
            ),
        )

    if inputs.cultural_evolution is not None:
        from analysis.cultural_evolution_evidence import (
            CulturalEvolutionInputs,
        )
        from analysis.cultural_evolution_metrics import (
            assemble_cultural_evolution_documents,
        )

        if type(inputs.cultural_evolution) is not CulturalEvolutionInputs:
            raise TypeError("cultural_evolution: invalid_type")
        if inputs.cultural_evolution_evidence_digest is None:
            raise ValueError("cultural_evolution_evidence_digest_required")
        documents.extend(
            assemble_cultural_evolution_documents(
                inputs.cultural_evolution,
                evidence_manifest_digest=(inputs.cultural_evolution_evidence_digest),
            )
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
