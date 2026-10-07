"""Executable V1 metric specifications (formulas, populations, edge cases).

Declarative validators for Tasks 11-15 - not metric implementations.
Log-free. Validation errors expose only ``metric_family``, ``algorithm_version``,
and stable reason codes - never fixture values or evidence content.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from analysis.evidence import EvidenceStage
from analysis.models import METRIC_DOCUMENT_SCHEMA_VERSION, MetricAvailability
from analysis.numerical import (
    ACCUMULATION_POLICY,
    CANONICAL_FLOAT_DECIMAL_PLACES,
    CANONICAL_OUTPUT_CLAIM,
    GRAPH_NODE_ORDER_POLICY,
    MINIMUM_LIBRARY_VERSIONS,
    PANDAS_NULL_SENTINEL_POLICY,
    SCIPY_DEGENERATE_POLICY,
    SUPPORTED_COMMUNITY_ALGORITHM,
)
from world.identifiers import require_stable_id

__all__ = [
    "ACTION_VOCABULARY_V1",
    "ADOPTION_STAGES_V1",
    "CONFLICT_ACTION_KINDS",
    "COOPERATION_ACTION_KINDS",
    "METRIC_CATALOG_VERSION",
    "METRIC_FAMILY_COUNT",
    "AdoptionStage",
    "DenominatorKind",
    "MetricFamilyId",
    "MetricSpecification",
    "MetricSpecificationError",
    "ResourceMeasureId",
    "SharedActionResolutionRateSpec",
    "action_resolution_rate_spec",
    "all_metric_specifications",
    "metric_specification",
    "require_metric_family_id",
    "validate_metric_catalog",
    "validate_metric_specification",
]

METRIC_CATALOG_VERSION: Final[str] = "metric-catalog-v1"
METRIC_FAMILY_COUNT: Final[int] = 65

# Align with existing memory-drift / transmission document versions.
_ALGO_V1: Final[str] = "1"


class MetricSpecificationError(ValueError):
    """Fail-closed specification error; message is codes only."""

    def __init__(
        self,
        *,
        metric_family: str,
        algorithm_version: str,
        reason_code: str,
    ) -> None:
        self.metric_family = metric_family
        self.algorithm_version = algorithm_version
        self.reason_code = reason_code
        super().__init__(
            f"{metric_family}:{algorithm_version}:{reason_code}"
        )


class MetricFamilyId(StrEnum):
    """Closed catalog of metric families (V1, memory, consolidation, reflection)."""

    RESOURCE_INEQUALITY = "resource_inequality"
    COOPERATION = "cooperation"
    CONFLICT = "conflict"
    SURVIVAL = "survival"
    GOAL_COMPLETION = "goal_completion"
    REPEATED_CONVENTIONS = "repeated_conventions"
    BEHAVIORAL_SPECIALIZATION = "behavioral_specialization"
    MEMORY_DRIFT = "memory_drift"
    BELIEF_ACCURACY = "belief_accuracy"
    FALSE_BELIEF_PERSISTENCE = "false_belief_persistence"
    RELATIONSHIP_STABILITY = "relationship_stability"
    TRUST_NETWORK_STRUCTURE = "trust_network_structure"
    GROUP_COMMUNITY_STRUCTURE = "group_community_structure"
    KNOWLEDGE_DIFFUSION = "knowledge_diffusion"
    RUMOR_DISTORTION = "rumor_distortion"
    MEMORY_DYNAMICS = "memory_dynamics"
    OFFLINE_CONSOLIDATION = "offline_consolidation"
    REFLECTION = "reflection"
    IDENTITY_DYNAMICS = "identity_dynamics"
    CAUSAL_WORLD_MODEL = "causal_world_model"
    THEORY_OF_MIND = "theory_of_mind"
    COMMUNICATION_STRATEGY = "communication_strategy"
    PROSPECTIVE_IMAGINATION = "prospective_imagination"
    COUNTERFACTUAL_REASONING = "counterfactual_reasoning"
    DISTRIBUTED_REPUTATION = "distributed_reputation"
    SKILL_LEARNING = "skill_learning"
    CULTURAL_TRANSMISSION = "cultural_transmission"
    SPATIAL_CONTROL = "spatial_control"
    EMERGENT_GROUP_FORMATION = "emergent_group_formation"
    EMERGENT_SOCIAL_NORMS = "emergent_social_norms"
    PERSISTENT_SOCIAL_CONVENTIONS = "persistent_social_conventions"
    EXTERNAL_ARTIFACT_MEMORY = "external_artifact_memory"
    EMERGENT_SEMANTIC_NAMING = "emergent_semantic_naming"
    CULTURAL_NARRATIVE_LINEAGE = "cultural_narrative_lineage"
    COGNITIVE_BUDGET = "cognitive_budget"
    TERRITORIAL_CONCENTRATION = "territorial_concentration"
    PREDICTION_CALIBRATION = "prediction_calibration"
    BELIEF_CONVERGENCE = "belief_convergence"
    CULTURAL_SIMILARITY = "cultural_similarity"
    KINSHIP_GENEALOGY = "kinship_genealogy"
    DEPENDENCY_SURVIVAL = "dependency_survival"
    CAREGIVER_DIVERSITY = "caregiver_diversity"
    CAREGIVING_BURDEN = "caregiving_burden"
    INTERGENERATIONAL_COOPERATION = "intergenerational_cooperation"
    DEVELOPMENTAL_ACQUISITION = "developmental_acquisition"
    DEVELOPMENTAL_SOURCE_MIX = "developmental_source_mix"
    DEVELOPMENTAL_DIVERGENCE = "developmental_divergence"
    MENTORSHIP_FIDELITY = "mentorship_fidelity"
    MENTORSHIP_MUTATION = "mentorship_mutation"
    MENTORSHIP_BONDS = "mentorship_bonds"
    CULTURAL_FEATURE_PROVENANCE = "cultural_feature_provenance"
    CULTURAL_TRAIT_DIFFUSION = "cultural_trait_diffusion"
    CULTURAL_FEATURE_MUTATION = "cultural_feature_mutation"
    HISTORICAL_MEMORY_LAYERS = "historical_memory_layers"
    HISTORICAL_MEMORY_TRANSITIONS = "historical_memory_transitions"
    HISTORICAL_MEMORY_QUERIES = "historical_memory_queries"
    DURABLE_RECORD_LINEAGE = "durable_record_lineage"
    DURABLE_RECORD_FIDELITY = "durable_record_fidelity"
    DURABLE_RECORD_SURVIVAL = "durable_record_survival"
    KNOWLEDGE_REPOSITORY_SURVIVAL = "knowledge_repository_survival"
    KNOWLEDGE_REPOSITORY_ACCESS = "knowledge_repository_access"
    KNOWLEDGE_REPOSITORY_ORGANIZATION = "knowledge_repository_organization"
    KNOWLEDGE_GENEALOGY_HOLDERS = "knowledge_genealogy_holders"
    KNOWLEDGE_GENEALOGY_LINEAGE = "knowledge_genealogy_lineage"
    KNOWLEDGE_GENEALOGY_MUTATION = "knowledge_genealogy_mutation"


class DenominatorKind(StrEnum):
    """Occurrence versus opportunity denominator classes."""

    OCCURRENCE = "occurrence"
    OPPORTUNITY = "opportunity"
    POPULATION_SIZE = "population_size"
    EVALUABLE_CLAIMS = "evaluable_claims"
    ACTIVE_EDGES = "active_edges"
    ADOPTION_ELIGIBLE = "adoption_eligible"


class ResourceMeasureId(StrEnum):
    """Named resource measures — never labeled generic wealth."""

    INVENTORY_COUNT = "inventory_count"
    INVENTORY_LOAD = "inventory_load"
    EXTRACTION = "extraction"
    TRANSFER = "transfer"
    CONSUMPTION_ACCESS = "consumption_access"


class AdoptionStage(StrEnum):
    """Stage-specific social-transmission adoption points (Task 15)."""

    WORLD_DELIVERY = "world_delivery"
    RECEIVER_TRACE = "receiver_trace"
    BELIEF_CANDIDATE = "belief_candidate"
    BELIEF_ACTIVATION = "belief_activation"
    RECONSTRUCTION = "reconstruction"
    RETELL = "retell"


ACTION_VOCABULARY_V1: Final[tuple[str, ...]] = (
    "move",
    "search",
    "take",
    "drop",
    "give",
    "eat",
    "drink",
    "sleep",
    "talk",
    "ask",
    "tell",
    "help",
    "attack",
    "flee",
    "wait",
)

COOPERATION_ACTION_KINDS: Final[frozenset[str]] = frozenset(
    {"help", "give", "talk", "ask", "tell", "feed", "transport"}
)
CONFLICT_ACTION_KINDS: Final[frozenset[str]] = frozenset({"attack", "flee"})

ADOPTION_STAGES_V1: Final[tuple[str, ...]] = tuple(
    stage.value for stage in AdoptionStage
)

_NUM_POLICY: Final[str] = (
    f"{ACCUMULATION_POLICY}; claim={CANONICAL_OUTPUT_CLAIM}; "
    f"quantize_decimal_places={CANONICAL_FLOAT_DECIMAL_PLACES}; "
    f"min_libs={dict(MINIMUM_LIBRARY_VERSIONS)}"
)
_PANDAS_POLICY: Final[str] = PANDAS_NULL_SENTINEL_POLICY
_SCIPY_POLICY: Final[str] = SCIPY_DEGENERATE_POLICY
_NX_POLICY: Final[str] = (
    f"{GRAPH_NODE_ORDER_POLICY}; community={SUPPORTED_COMMUNITY_ALGORITHM}"
)


@dataclass(frozen=True, slots=True)
class MetricSpecification:
    """Executable definition for one metric family (not a computed result)."""

    family_id: MetricFamilyId
    algorithm_version: str
    schema_version: str
    evidence_inputs: frozenset[EvidenceStage]
    population: str
    denominator: str
    denominator_kind: DenominatorKind
    cohort_window: str
    deceased_policy: str
    zero_holding_policy: str
    opportunity_vs_occurrence: str
    self_edge_policy: str
    censoring_policy: str
    action_vocabulary: tuple[str, ...]
    motif_tokenization: str
    motif_gap_policy: str
    motif_support_policy: str
    adoption_stages: tuple[str, ...]
    evidence_stage_deduplication: str
    signed_trust_policy: str
    graph_projection: str
    community_algorithm: str
    empty_case: str
    one_case: str
    all_zero_case: str
    unknown_case: str
    availability_behavior: str
    numpy_policy: str
    pandas_policy: str
    scipy_policy: str
    networkx_policy: str
    quantization: str
    formula_ids: tuple[str, ...]
    formulas: Mapping[str, str]
    value_keys: tuple[str, ...]

    def __post_init__(self) -> None:
        if type(self.family_id) is not MetricFamilyId:
            raise TypeError("MetricSpecification.family_id: invalid_type")
        object.__setattr__(
            self,
            "algorithm_version",
            require_stable_id(
                "MetricSpecification.algorithm_version", self.algorithm_version
            ),
        )
        object.__setattr__(
            self,
            "schema_version",
            require_stable_id(
                "MetricSpecification.schema_version", self.schema_version
            ),
        )
        if type(self.denominator_kind) is not DenominatorKind:
            raise TypeError("MetricSpecification.denominator_kind: invalid_type")
        if not isinstance(self.evidence_inputs, frozenset) or not self.evidence_inputs:
            raise ValueError("MetricSpecification.evidence_inputs: empty_or_invalid")
        if not isinstance(self.formulas, Mapping) or not self.formulas:
            raise ValueError("MetricSpecification.formulas: empty_or_invalid")
        object.__setattr__(self, "formulas", MappingProxyType(dict(self.formulas)))

    @property
    def version_identifier(self) -> str:
        """Canonical ``family@algorithm`` version tag for documents and fixtures."""
        return f"{self.family_id.value}@{self.algorithm_version}"

    def __repr__(self) -> str:
        return (
            f"MetricSpecification(family_id={self.family_id.value!r}, "
            f"algorithm_version={self.algorithm_version!r}, "
            f"formula_count={len(self.formula_ids)}, "
            f"stage_count={len(self.evidence_inputs)})"
        )


@dataclass(frozen=True, slots=True)
class SharedActionResolutionRateSpec:
    """Supporting formulas for attempted/rejected/conflicted rates (Task 11).

    Not a separate Acceptance-Criteria family. Rates come only from
    ``ActionResolution`` evidence — never inferred from absent events.
    """

    algorithm_version: str
    evidence_inputs: frozenset[EvidenceStage]
    population: str
    denominator: str
    deceased_policy: str
    opportunity_vs_occurrence: str
    empty_case: str
    unknown_case: str
    availability_behavior: str
    numpy_policy: str
    pandas_policy: str
    quantization: str
    formulas: Mapping[str, str]
    value_keys: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "algorithm_version",
            require_stable_id(
                "SharedActionResolutionRateSpec.algorithm_version",
                self.algorithm_version,
            ),
        )
        object.__setattr__(self, "formulas", MappingProxyType(dict(self.formulas)))

    @property
    def version_identifier(self) -> str:
        return f"action_resolution_rates@{self.algorithm_version}"

    def __repr__(self) -> str:
        return (
            f"SharedActionResolutionRateSpec("
            f"algorithm_version={self.algorithm_version!r}, "
            f"formula_count={len(self.formulas)})"
        )


def require_metric_family_id(label: str, value: object) -> MetricFamilyId:
    """Validate a closed metric family id."""
    if type(value) is MetricFamilyId:
        return value
    if isinstance(value, str):
        try:
            return MetricFamilyId(value)
        except ValueError as exc:
            raise MetricSpecificationError(
                metric_family=str(value),
                algorithm_version="unknown",
                reason_code="unknown_metric_family",
            ) from exc
    raise MetricSpecificationError(
        metric_family="unknown",
        algorithm_version="unknown",
        reason_code="invalid_family_type",
    )


def validate_metric_specification(spec: MetricSpecification) -> None:
    """Fail-closed structural validation; codes only on error."""
    family = spec.family_id.value
    version = spec.algorithm_version
    if spec.schema_version != METRIC_DOCUMENT_SCHEMA_VERSION:
        raise MetricSpecificationError(
            metric_family=family,
            algorithm_version=version,
            reason_code="unsupported_schema_version",
        )
    if not spec.formula_ids:
        raise MetricSpecificationError(
            metric_family=family,
            algorithm_version=version,
            reason_code="empty_formula_ids",
        )
    if tuple(sorted(spec.formula_ids)) != tuple(sorted(set(spec.formula_ids))):
        raise MetricSpecificationError(
            metric_family=family,
            algorithm_version=version,
            reason_code="duplicate_formula_ids",
        )
    if set(spec.formula_ids) != set(spec.formulas):
        raise MetricSpecificationError(
            metric_family=family,
            algorithm_version=version,
            reason_code="formula_id_mismatch",
        )
    if not spec.value_keys:
        raise MetricSpecificationError(
            metric_family=family,
            algorithm_version=version,
            reason_code="empty_value_keys",
        )
    if tuple(sorted(spec.value_keys)) != tuple(sorted(set(spec.value_keys))):
        raise MetricSpecificationError(
            metric_family=family,
            algorithm_version=version,
            reason_code="duplicate_value_keys",
        )
    if "unknown" not in spec.unknown_case and "UNKNOWN" not in spec.unknown_case:
        # Require explicit unknown policy text mentioning unknown availability.
        if MetricAvailability.UNKNOWN.value not in spec.unknown_case:
            raise MetricSpecificationError(
                metric_family=family,
                algorithm_version=version,
                reason_code="missing_unknown_policy",
            )
    for stage in spec.evidence_inputs:
        if type(stage) is not EvidenceStage:
            raise MetricSpecificationError(
                metric_family=family,
                algorithm_version=version,
                reason_code="invalid_evidence_stage",
            )
    if not spec.population or not spec.denominator:
        raise MetricSpecificationError(
            metric_family=family,
            algorithm_version=version,
            reason_code="missing_population_or_denominator",
        )
    if not spec.quantization:
        raise MetricSpecificationError(
            metric_family=family,
            algorithm_version=version,
            reason_code="missing_quantization",
        )


def _base(
    *,
    family_id: MetricFamilyId,
    evidence_inputs: frozenset[EvidenceStage],
    population: str,
    denominator: str,
    denominator_kind: DenominatorKind,
    cohort_window: str,
    deceased_policy: str,
    zero_holding_policy: str,
    opportunity_vs_occurrence: str,
    self_edge_policy: str,
    censoring_policy: str,
    formulas: Mapping[str, str],
    value_keys: tuple[str, ...],
    action_vocabulary: tuple[str, ...] = (),
    motif_tokenization: str = "not_applicable",
    motif_gap_policy: str = "not_applicable",
    motif_support_policy: str = "not_applicable",
    adoption_stages: tuple[str, ...] = (),
    evidence_stage_deduplication: str = (
        "dedupe_by_lineage_root_within_stage; never_merge_across_stages"
    ),
    signed_trust_policy: str = "not_applicable",
    graph_projection: str = "not_applicable",
    community_algorithm: str = "not_applicable",
    empty_case: str = "availability=unknown; omit numeric values",
    one_case: str = "compute_defined_scalars; mark_coverage_singleton",
    all_zero_case: str = "finite_zeros_are_present_equality; never_coerce_unknown",
    unknown_case: str = (
        "missing_or_unobservable_evidence -> availability=unknown; "
        "never_coerce_to_zero_or_false"
    ),
    availability_behavior: str = (
        "present|partial|absent|unknown per MetricAvailability; "
        "partial when coverage.observed < coverage.expected"
    ),
    networkx_policy: str = "not_applicable",
) -> MetricSpecification:
    return MetricSpecification(
        family_id=family_id,
        algorithm_version=_ALGO_V1,
        schema_version=METRIC_DOCUMENT_SCHEMA_VERSION,
        evidence_inputs=evidence_inputs,
        population=population,
        denominator=denominator,
        denominator_kind=denominator_kind,
        cohort_window=cohort_window,
        deceased_policy=deceased_policy,
        zero_holding_policy=zero_holding_policy,
        opportunity_vs_occurrence=opportunity_vs_occurrence,
        self_edge_policy=self_edge_policy,
        censoring_policy=censoring_policy,
        action_vocabulary=action_vocabulary,
        motif_tokenization=motif_tokenization,
        motif_gap_policy=motif_gap_policy,
        motif_support_policy=motif_support_policy,
        adoption_stages=adoption_stages,
        evidence_stage_deduplication=evidence_stage_deduplication,
        signed_trust_policy=signed_trust_policy,
        graph_projection=graph_projection,
        community_algorithm=community_algorithm,
        empty_case=empty_case,
        one_case=one_case,
        all_zero_case=all_zero_case,
        unknown_case=unknown_case,
        availability_behavior=availability_behavior,
        numpy_policy=_NUM_POLICY,
        pandas_policy=_PANDAS_POLICY,
        scipy_policy=_SCIPY_POLICY,
        networkx_policy=networkx_policy,
        quantization=(
            f"quantize_float banker's ROUND_HALF_EVEN to "
            f"{CANONICAL_FLOAT_DECIMAL_PLACES} decimal places; "
            f"normalize_signed_zero; {CANONICAL_OUTPUT_CLAIM}"
        ),
        formula_ids=tuple(sorted(formulas)),
        formulas=formulas,
        value_keys=value_keys,
    )


def _spec_resource_inequality() -> MetricSpecification:
    measures = ", ".join(m.value for m in ResourceMeasureId)
    return _base(
        family_id=MetricFamilyId.RESOURCE_INEQUALITY,
        evidence_inputs=frozenset(
            {
                EvidenceStage.OBJECTIVE_EVENT_STATE,
            }
        ),
        population="registered_agents_alive_at_tick_or_window_end",
        denominator=f"named_measure_vector_over_population ({measures})",
        denominator_kind=DenominatorKind.POPULATION_SIZE,
        cohort_window=(
            "per_tick snapshot and optional [t0,t1] inclusive window; "
            "aggregate window uses last observation per agent in window"
        ),
        deceased_policy=(
            "exclude deceased from living inequality cohort; "
            "lifetime extraction/transfer may include pre-death ticks only"
        ),
        zero_holding_policy=(
            "zero inventory/load/extraction included as exact 0.0 when observed; "
            "unobserved holdings are unknown and drop agent from that measure"
        ),
        opportunity_vs_occurrence=(
            "inequality is distributional over holdings/flows — not an "
            "opportunity rate; missing measure -> unknown not zero"
        ),
        self_edge_policy="not_applicable",
        censoring_policy=(
            "right-censor agents leaving observation mid-window as partial "
            "coverage; never impute holdings"
        ),
        formulas={
            "gini": (
                "sort measure vector x ascending length n>=2, S=sum(x); "
                "if S==0 return 0.0; "
                "G=(2*sum((i+1)*x[i] for i in range(n))-(n+1)*S)/(n*S); "
                "NumPy float64; quantize on export"
            ),
            "theil_t": (
                "mean mu=S/n; if mu==0 return 0.0; "
                "T=(1/n)*sum((x_i/mu)*ln(x_i/mu) for x_i>0); "
                "zeros contribute 0 by lim x ln x -> 0; SciPy/NumPy float64"
            ),
            "atkinson_eps_1": (
                "A=1-exp(mean(ln(x_i)) for x_i>0)/mu when all x_i>0; "
                "if any zero holding A=1.0; empty/unknown -> unknown"
            ),
            "share_top_1": (
                "max(x)/S when S>0 else 0.0; population sorted by agent_id for ties"
            ),
        },
        value_keys=(
            "gini",
            "theil_t",
            "atkinson_eps_1",
            "share_top_1",
            "population_size",
            "measure_id",
        ),
        empty_case="n==0 -> availability=unknown",
        one_case="n==1 -> gini=0.0 theil_t=0.0 atkinson=0.0 share_top_1=1.0 present",
        all_zero_case="all x_i==0 -> gini=0.0 theil_t=0.0 share_top_1=0.0 present",
    )


def _spec_cooperation() -> MetricSpecification:
    return _base(
        family_id=MetricFamilyId.COOPERATION,
        evidence_inputs=frozenset(
            {
                EvidenceStage.OBJECTIVE_EVENT_STATE,
                EvidenceStage.ACTION_RESOLUTION,
            }
        ),
        population="living_registered_agents_in_window",
        denominator="agent_ticks_alive (opportunity) and applied_events (occurrence)",
        denominator_kind=DenominatorKind.OPPORTUNITY,
        cohort_window="inclusive tick window on run evidence manifest",
        deceased_policy="post-death agent-ticks excluded from opportunity denominator",
        zero_holding_policy="not_applicable",
        opportunity_vs_occurrence=(
            "occurrence_rate = applied coop events / applied events of vocab; "
            "opportunity_rate = applied coop events / living_agent_ticks; "
            "report both; never infer from absent ActionResolution"
        ),
        self_edge_policy=(
            "self-targeted help/give excluded from dyadic counts; "
            "self talk/ask/tell counted as self-communication separately"
        ),
        censoring_policy="window end right-censors incomplete ticks as partial",
        action_vocabulary=tuple(
            sorted(COOPERATION_ACTION_KINDS | {"give", "help", "talk", "ask", "tell"})
        ),
        formulas={
            "coop_occurrence_rate": (
                "count WorldEvent applied kinds in COOPERATION_ACTION_KINDS / "
                "count all applied action events in window; float64"
            ),
            "coop_opportunity_rate": (
                "coop applied events / sum over agents of alive ticks in window"
            ),
            "coop_by_kind": (
                "pandas groupby action_kind counts sorted by kind; "
                "NA kinds -> unknown row excluded from rates"
            ),
        },
        value_keys=(
            "coop_occurrence_rate",
            "coop_opportunity_rate",
            "coop_event_count",
            "opportunity_agent_ticks",
        ),
    )


def _spec_conflict() -> MetricSpecification:
    return _base(
        family_id=MetricFamilyId.CONFLICT,
        evidence_inputs=frozenset(
            {
                EvidenceStage.OBJECTIVE_EVENT_STATE,
                EvidenceStage.ACTION_RESOLUTION,
            }
        ),
        population="living_registered_agents_in_window",
        denominator="agent_ticks_alive (opportunity) and applied_events (occurrence)",
        denominator_kind=DenominatorKind.OPPORTUNITY,
        cohort_window="inclusive tick window on run evidence manifest",
        deceased_policy="post-death agent-ticks excluded from opportunity denominator",
        zero_holding_policy="not_applicable",
        opportunity_vs_occurrence=(
            "distinguish attack vs flee; never merge into cooperation; "
            "occurrence vs opportunity parallel to cooperation family"
        ),
        self_edge_policy="self-attack impossible; self-flee allowed as solo action",
        censoring_policy="window end right-censors incomplete ticks as partial",
        action_vocabulary=tuple(sorted(CONFLICT_ACTION_KINDS)),
        formulas={
            "conflict_occurrence_rate": (
                "applied attack+flee events / applied action events in window"
            ),
            "attack_occurrence_rate": "applied attack / applied action events",
            "flee_occurrence_rate": "applied flee / applied action events",
            "conflict_opportunity_rate": (
                "applied attack+flee / living_agent_ticks in window"
            ),
        },
        value_keys=(
            "conflict_occurrence_rate",
            "attack_occurrence_rate",
            "flee_occurrence_rate",
            "conflict_opportunity_rate",
            "conflict_event_count",
        ),
    )


def _spec_survival() -> MetricSpecification:
    return _base(
        family_id=MetricFamilyId.SURVIVAL,
        evidence_inputs=frozenset({EvidenceStage.OBJECTIVE_EVENT_STATE}),
        population="agents_registered_at_run_start",
        denominator="n_registered (Kaplan-Meier at-risk set)",
        denominator_kind=DenominatorKind.POPULATION_SIZE,
        cohort_window="ticks [0, T] through final committed tick",
        deceased_policy=(
            "death tick from objective LifeStatus transition; "
            "include death event; post-death no-action is expected not censoring"
        ),
        zero_holding_policy="not_applicable",
        opportunity_vs_occurrence="survival is time-to-event not action rate",
        self_edge_policy="not_applicable",
        censoring_policy=(
            "alive at run end are right-censored at final tick; "
            "never treat missing death evidence as survived without coverage flag"
        ),
        formulas={
            "survival_rate_at_T": "n_alive_at_T / n_registered",
            "median_survival_tick": (
                "smallest t with KM(t)<=0.5 else None with availability=partial "
                "when fewer than half died"
            ),
            "km_survival": (
                "deterministic Kaplan-Meier over sorted death ticks; "
                "pandas time table sorted by tick then agent_id"
            ),
        },
        value_keys=(
            "survival_rate_at_T",
            "deaths",
            "censored_alive",
            "median_survival_tick",
            "population_size",
        ),
        one_case="single agent: rate 0 or 1 from death evidence; KM defined",
        empty_case="n==0 -> availability=unknown",
    )


def _spec_goal_completion() -> MetricSpecification:
    return _base(
        family_id=MetricFamilyId.GOAL_COMPLETION,
        evidence_inputs=frozenset({EvidenceStage.GOAL_TRANSITION}),
        population="goals_with_transition_receipts_in_window",
        denominator="goals_started_or_active_in_window",
        denominator_kind=DenominatorKind.OCCURRENCE,
        cohort_window="goal logical ticks within run window",
        deceased_policy=(
            "owner death maps to documented death outcome; "
            "do not treat imagined GoalEffect as completion"
        ),
        zero_holding_policy="not_applicable",
        opportunity_vs_occurrence=(
            "completion_rate = completed / (completed+abandoned+death+run_end); "
            "active-at-end are run_end censored not failures"
        ),
        self_edge_policy="not_applicable",
        censoring_policy="active at run end -> outcome=run_end censored",
        formulas={
            "completion_rate": "n_completed / n_terminal_or_censored",
            "abandonment_rate": "n_abandoned / n_terminal_or_censored",
            "death_interrupt_rate": "n_death_outcome / n_terminal_or_censored",
            "by_outcome_kind": (
                "pandas counts keyed by GoalOutcomeKind / GoalStatus codes; "
                "sorted keys"
            ),
        },
        value_keys=(
            "completion_rate",
            "abandonment_rate",
            "death_interrupt_rate",
            "goals_total",
            "goals_censored_run_end",
        ),
        empty_case="no goals -> availability=absent",
        unknown_case=(
            "legacy runs without goal receipts -> availability=unknown; "
            "never invent outcomes"
        ),
    )


def _spec_repeated_conventions() -> MetricSpecification:
    return _base(
        family_id=MetricFamilyId.REPEATED_CONVENTIONS,
        evidence_inputs=frozenset(
            {
                EvidenceStage.OBJECTIVE_EVENT_STATE,
                EvidenceStage.ACTION_RESOLUTION,
            }
        ),
        population="living_agents_with_applied_actions",
        denominator="token_sequence_length and motif opportunity windows",
        denominator_kind=DenominatorKind.OPPORTUNITY,
        cohort_window=(
            "inclusive tick window; sequences per actor sorted by tick,ordinal"
        ),
        deceased_policy="truncate token stream at death tick exclusive of post-death",
        zero_holding_policy="not_applicable",
        opportunity_vs_occurrence=(
            "support = motif count; coverage = support / opportunity windows; "
            "idle wait tokens included unless excluded by gap policy"
        ),
        self_edge_policy="actor-self motifs allowed; dyadic motifs drop self pairs",
        censoring_policy=(
            "short sequences below n-gram order -> partial not zero support"
        ),
        action_vocabulary=ACTION_VOCABULARY_V1,
        motif_tokenization=(
            "token = action_kind[+optional location_id][+optional target_class]; "
            "lexicographic canonical string; no role/culture labels"
        ),
        motif_gap_policy=(
            "max_gap_ticks=0 for contiguous n-grams; "
            "optional gapped motifs declare max_gap explicitly in document values"
        ),
        motif_support_policy=(
            "min_support=2 occurrences; report support, recurrence_span_ticks, "
            "opportunity_coverage; sort motifs by (-support, motif_id)"
        ),
        formulas={
            "ngram_support_table": (
                "pandas n-gram counts for n in {2,3}; NumPy optional; "
                "permutation: sort input rows by (tick, ordinal, agent_id)"
            ),
            "top_motif_support": "max support among motifs meeting min_support else 0",
            "motif_opportunity_coverage": (
                "sum motif windows matched / sum eligible windows; unknown if none"
            ),
        },
        value_keys=(
            "top_motif_support",
            "motif_count",
            "motif_opportunity_coverage",
            "ngram_order_max",
        ),
        empty_case="no tokens -> availability=unknown",
        one_case="one agent ok; motifs may still form",
        all_zero_case="no recurring motif -> support 0 present with motif_count=0",
    )


def _spec_behavioral_specialization() -> MetricSpecification:
    return _base(
        family_id=MetricFamilyId.BEHAVIORAL_SPECIALIZATION,
        evidence_inputs=frozenset(
            {
                EvidenceStage.OBJECTIVE_EVENT_STATE,
                EvidenceStage.ACTION_RESOLUTION,
            }
        ),
        population="living_agents_with_action_mass_gt_0",
        denominator="per_agent action counts over vocabulary",
        denominator_kind=DenominatorKind.OCCURRENCE,
        cohort_window="inclusive tick window",
        deceased_policy="exclude dead-period ticks; terminal agent pre-death included",
        zero_holding_policy="agents with zero actions excluded from entropy cohort",
        opportunity_vs_occurrence="distributions over observed actions only",
        self_edge_policy="not_applicable",
        censoring_policy="insufficient mass (<1 action) -> agent unknown for entropy",
        action_vocabulary=ACTION_VOCABULARY_V1,
        formulas={
            "shannon_entropy": (
                "H=-sum p_k log2(p_k) over action_kind probs; "
                "SciPy entropy or NumPy; empty -> unknown never 0"
            ),
            "normalized_entropy": "H / log2(|vocab_used|); singleton -> 0.0",
            "herfindahl": "sum p_k^2 concentration",
            "js_divergence_from_population": (
                "Jensen-Shannon vs population mixture; SciPy; "
                "one-agent population -> unknown divergence"
            ),
        },
        value_keys=(
            "mean_normalized_entropy",
            "mean_herfindahl",
            "mean_js_divergence",
            "agents_scored",
        ),
        empty_case="no agents with actions -> availability=unknown",
        one_case="entropy defined; js_divergence unknown",
        all_zero_case="not reachable after excluding zero-action agents",
    )


def _spec_memory_drift() -> MetricSpecification:
    return _base(
        family_id=MetricFamilyId.MEMORY_DRIFT,
        evidence_inputs=frozenset(
            {
                EvidenceStage.AGENT_VISIBLE_PROJECTION,
                EvidenceStage.DIRECT_TRACE,
                EvidenceStage.COMMUNICATED_TRACE,
                EvidenceStage.RECONSTRUCTION,
                EvidenceStage.RECONSOLIDATED_TRACE,
            }
        ),
        population="reconstruction_chains_per_owner",
        denominator="comparable_fact_set_pairs with both sides present",
        denominator_kind=DenominatorKind.OCCURRENCE,
        cohort_window="owner memory lifetime within run",
        deceased_policy="owner death truncates new traces; existing chains remain",
        zero_holding_policy="empty fact sets are ABSENT not unknown",
        opportunity_vs_occurrence=(
            "primary drift vs agent-visible projection; "
            "optional separately labeled authoritative-world gap"
        ),
        self_edge_policy="not_applicable",
        censoring_policy="incomplete lineage -> ComparisonStatus before/after unknown",
        evidence_stage_deduplication=(
            "dedupe corroboration by lineage root; preserve stage on every row; "
            "never collapse stages"
        ),
        formulas={
            "mean_concept_jaccard_loss": (
                "1 - |C_before n C_after|/|C_before u C_after| when both PRESENT"
            ),
            "linked_chain_rate": "linked_count / chain_count",
            "stage_labeled_step_counts": "counts by (from_kind,to_kind) sorted",
        },
        value_keys=(
            "mean_concept_jaccard_loss",
            "linked_chain_rate",
            "chain_count",
            "unlinked_count",
        ),
        empty_case="no chains -> availability=absent",
        unknown_case=(
            "missing projection or trace content -> availability=unknown; "
            "MetricAvailability.unknown"
        ),
    )


def _spec_memory_dynamics() -> MetricSpecification:
    return _base(
        family_id=MetricFamilyId.MEMORY_DYNAMICS,
        evidence_inputs=frozenset({EvidenceStage.RECONSTRUCTION}),
        population="v2_recall_audits_per_run",
        denominator="recall audits with reconstruction_id",
        denominator_kind=DenominatorKind.OCCURRENCE,
        cohort_window="run window covering harvested V2 recalls",
        deceased_policy="owner death stops new audits; existing audits remain",
        zero_holding_policy="empty audit set -> availability=absent",
        opportunity_vs_occurrence=(
            "rates over harvested RecallAuditRecord exports only; "
            "REFERENCE/V1 arms produce no audits"
        ),
        self_edge_policy="not_applicable",
        censoring_policy="missing audits -> absent; never invent competitor sets",
        formulas={
            "recall_accuracy": (
                "mean Jaccard(|source_memory_ids n selected_ids| / "
                "|source_memory_ids u selected_ids|) over audits"
            ),
            "source_confusion": (
                "fraction of audits with distortion_code source_confusion"
            ),
            "memory_survival": (
                "mean selected_count / (source_count + competitor_count)"
            ),
            "interference": "fraction of audits with distortion_code interference",
            "confidence_calibration": (
                "mean clamp(confidence_after / confidence_before, 0, 1); "
                "before<=0 -> 1 if after<=0 else 0"
            ),
        },
        value_keys=(
            "recall_accuracy",
            "source_confusion",
            "memory_survival",
            "interference",
            "confidence_calibration",
        ),
        empty_case="no audits -> availability=absent",
        unknown_case=(
            "incomplete audit export -> availability=unknown; "
            "MetricAvailability.unknown"
        ),
    )


def _spec_reflection() -> MetricSpecification:
    return _base(
        family_id=MetricFamilyId.REFLECTION,
        evidence_inputs=frozenset({EvidenceStage.BELIEF_REVISION_TESTIMONY}),
        population="reflection_audits_per_run",
        denominator="harvested reflection audits",
        denominator_kind=DenominatorKind.OCCURRENCE,
        cohort_window="run window covering harvested reflection passes",
        deceased_policy="terminal agents stop new audits; existing audits remain",
        zero_holding_policy="no audits -> availability=absent",
        opportunity_vs_occurrence=(
            "counts over harvested audits only; disabled arms absent"
        ),
        self_edge_policy="not_applicable",
        censoring_policy="missing report -> omitted; never invent counts",
        formulas={
            "reflection_invocations": "count of harvested reflection audits",
            "belief_revisions": "sum of revised and self-belief conclusion counts",
            "hypotheses": "sum of new-hypothesis conclusion counts",
            "goals_adopted": "sum of adopted long-term goal counts",
            "goals_abandoned": "sum of abandoned goal counts",
            "relationship_reassessments": "sum of relationship reassessment counts",
            "patterns_detected": "sum of all conclusion kind counts",
        },
        value_keys=(
            "reflection_invocations",
            "belief_revisions",
            "hypotheses",
            "goals_adopted",
            "goals_abandoned",
            "relationship_reassessments",
            "patterns_detected",
        ),
        empty_case="no audits -> availability=absent",
        unknown_case=(
            "incomplete audit export -> availability=unknown; "
            "MetricAvailability.unknown"
        ),
    )


def _spec_causal_world_model() -> MetricSpecification:
    return _base(
        family_id=MetricFamilyId.CAUSAL_WORLD_MODEL,
        evidence_inputs=frozenset({EvidenceStage.OBJECTIVE_EVENT_STATE}),
        population="causal_hypothesis_snapshots_per_run",
        denominator="harvested hypothesis snapshots",
        denominator_kind=DenominatorKind.OCCURRENCE,
        cohort_window="run window covering committed events and audits",
        deceased_policy="terminal agents stop new audits; existing audits remain",
        zero_holding_policy="no snapshots -> availability=absent",
        opportunity_vs_occurrence=(
            "compares harvested snapshots with committed events; flag-off runs absent"
        ),
        self_edge_policy="not_applicable",
        censoring_policy="unjoinable atoms stay unmatched; never invent a rate",
        formulas={
            "hypothesis_count": "count of harvested hypothesis snapshots",
            "matched_count": "snapshots with a joinable empirical rate",
            "unmatched_count": "snapshots whose atoms cannot be joined",
            "max_absolute_error": "largest absolute confidence error among matches",
        },
        value_keys=(
            "hypothesis_count",
            "matched_count",
            "unmatched_count",
            "max_absolute_error",
        ),
    )


def _spec_distributed_reputation() -> MetricSpecification:
    return _base(
        family_id=MetricFamilyId.DISTRIBUTED_REPUTATION,
        evidence_inputs=frozenset({EvidenceStage.AGENT_VISIBLE_PROJECTION}),
        population="owner_ledgers_per_neighborhood",
        denominator="owner heads for the requested target",
        denominator_kind=DenominatorKind.POPULATION_SIZE,
        cohort_window="caller-supplied ledgers and neighborhood map",
        deceased_policy="not_applicable",
        zero_holding_policy="empty ledgers -> availability=absent",
        opportunity_vs_occurrence=(
            "means of private heads; no score across dimensions"
        ),
        self_edge_policy="not_applicable",
        censoring_policy="owners outside the map are omitted; never invent a mean",
        formulas={
            "reliability_gap": "max neighborhood mean minus min for reliability",
            "harm_gap": "max neighborhood mean minus min for harm",
            "generosity_gap": "max neighborhood mean minus min for generosity",
            "competence_gap": "max neighborhood mean minus min for competence",
            "neighborhood_count": "number of neighborhoods with at least one reading",
            "mean_pairwise_gap": (
                "mean over neighborhood pairs of mean absolute dimension gap; "
                "absent when neighborhood_count < 2"
            ),
            "max_pairwise_gap": (
                "max over neighborhood pairs of mean absolute dimension gap; "
                "absent when neighborhood_count < 2"
            ),
        },
        value_keys=(
            "reliability_gap",
            "harm_gap",
            "generosity_gap",
            "competence_gap",
            "neighborhood_count",
            "mean_pairwise_gap",
            "max_pairwise_gap",
        ),
        empty_case="availability=absent; omit numeric values",
    )


def _spec_skill_learning() -> MetricSpecification:
    return _base(
        family_id=MetricFamilyId.SKILL_LEARNING,
        evidence_inputs=frozenset({EvidenceStage.AGENT_VISIBLE_PROJECTION}),
        population="skill_audit_rows_per_agent_domain",
        denominator="joined objective and subjective rows",
        denominator_kind=DenominatorKind.OCCURRENCE,
        cohort_window="audits harvested after the run",
        deceased_policy="not_applicable",
        zero_holding_policy="no rows -> availability=absent",
        opportunity_vs_occurrence="absolute gap between harvested sides",
        self_edge_policy="not_applicable",
        censoring_policy="a missing side is unmatched and is not guessed",
        formulas={
            "gap": "absolute difference of quantized objective and believed levels",
            "matched_count": "agent-domain pairs with both sides",
            "unmatched_count": "agent-domain pairs missing one side",
        },
        value_keys=("matched_count", "unmatched_count", "max_gap"),
        empty_case="availability=absent; omit numeric values",
    )


def _spec_kinship_genealogy() -> MetricSpecification:
    return _base(
        family_id=MetricFamilyId.KINSHIP_GENEALOGY,
        evidence_inputs=frozenset({EvidenceStage.OBJECTIVE_EVENT_STATE}),
        population="detached_kinship_edge_rows",
        denominator="registered_agents",
        denominator_kind=DenominatorKind.POPULATION_SIZE,
        cohort_window="caller-supplied kinship edges after the run",
        deceased_policy="include_dead_by_default",
        zero_holding_policy=(
            "empty edge rows with no known agents -> availability=absent"
        ),
        opportunity_vs_occurrence=(
            "parent→child edges only; sibling/ancestor/descendant are derived elsewhere"
        ),
        self_edge_policy="self_parent rejected",
        censoring_policy=(
            "relatedness never implies social valence or inheritance rights"
        ),
        formulas={
            "edge_count": "number of directed parent→child edges",
            "component_sizes": "weakly connected component sizes (desc)",
            "mean_depth_reached": "mean max outbound depth within cap",
            "orphan_count": "agents with degree zero in the genealogy digraph",
        },
        value_keys=(
            "component_sizes",
            "edge_count",
            "mean_depth_reached",
            "orphan_count",
        ),
        empty_case="availability=absent; no_kinship_rows",
        networkx_policy="weak_components_and_outbound_depth_only",
    )


def _spec_dependency_survival() -> MetricSpecification:
    return _base(
        family_id=MetricFamilyId.DEPENDENCY_SURVIVAL,
        evidence_inputs=frozenset({EvidenceStage.OBJECTIVE_EVENT_STATE}),
        population="detached_dependency_agent_rows",
        denominator="dependent_agents",
        denominator_kind=DenominatorKind.POPULATION_SIZE,
        cohort_window="caller-supplied lifecycle/survival rows after the run",
        deceased_policy="include_dead_by_default",
        zero_holding_policy="empty agent rows -> availability=absent",
        opportunity_vs_occurrence=(
            "DEPENDENT survival vs INDEPENDENT contrast when present"
        ),
        self_edge_policy="not_applicable",
        censoring_policy="never invents biology or caregiver roles",
        formulas={
            "dependent_survival_rate": "survived / dependent_count",
            "independent_survival_rate": "survived / independent_count",
            "mean_dependent_lifespan_ticks": "mean lifespan among DEPENDENT rows",
        },
        value_keys=(
            "dependent_count",
            "dependent_survival_rate",
            "independent_count",
            "independent_survival_rate",
            "mean_dependent_lifespan_ticks",
        ),
        empty_case="availability=absent; no_dependency_agent_rows",
    )


def _spec_caregiver_diversity() -> MetricSpecification:
    return _base(
        family_id=MetricFamilyId.CAREGIVER_DIVERSITY,
        evidence_inputs=frozenset({EvidenceStage.OBJECTIVE_EVENT_STATE}),
        population="detached_care_act_rows",
        denominator="care_acts",
        denominator_kind=DenominatorKind.OCCURRENCE,
        cohort_window="caller-supplied care acts after the run",
        deceased_policy="include_dead_by_default",
        zero_holding_policy="empty care rows -> availability=absent",
        opportunity_vs_occurrence=(
            "unique caregivers per dependent; entropy over caregiver act shares"
        ),
        self_edge_policy="self_care allowed if present in rows",
        censoring_policy="never assigns caregivers; analysis-only",
        formulas={
            "mean_unique_caregivers": "mean unique caregivers per dependent",
            "caregiver_entropy": "normalized Shannon entropy of caregiver act counts",
        },
        value_keys=(
            "care_act_count",
            "caregiver_entropy",
            "dependent_count",
            "mean_unique_caregivers",
            "unique_caregiver_counts",
        ),
        empty_case="availability=absent; no_care_act_rows",
    )


def _spec_caregiving_burden() -> MetricSpecification:
    return _base(
        family_id=MetricFamilyId.CAREGIVING_BURDEN,
        evidence_inputs=frozenset({EvidenceStage.OBJECTIVE_EVENT_STATE}),
        population="detached_care_act_rows",
        denominator="care_acts",
        denominator_kind=DenominatorKind.OCCURRENCE,
        cohort_window="caller-supplied care acts after the run",
        deceased_policy="include_dead_by_default",
        zero_holding_policy="empty care rows -> availability=absent",
        opportunity_vs_occurrence="acts and fatigue deltas attributed to caregivers",
        self_edge_policy="not_applicable",
        censoring_policy="analysis-only; never feeds cognition",
        formulas={
            "mean_fatigue_delta": "mean summed fatigue_delta per caregiver",
            "max_care_time_share": "max caregiver act share of total care acts",
        },
        value_keys=(
            "care_act_count",
            "caregiver_count",
            "max_care_time_share",
            "mean_fatigue_delta",
        ),
        empty_case="availability=absent; no_care_act_rows",
    )


def _spec_intergenerational_cooperation() -> MetricSpecification:
    return _base(
        family_id=MetricFamilyId.INTERGENERATIONAL_COOPERATION,
        evidence_inputs=frozenset({EvidenceStage.OBJECTIVE_EVENT_STATE}),
        population="detached_care_act_rows",
        denominator="care_acts",
        denominator_kind=DenominatorKind.OCCURRENCE,
        cohort_window="caller-supplied care acts with generation_index",
        deceased_policy="include_dead_by_default",
        zero_holding_policy="empty care rows -> availability=absent",
        opportunity_vs_occurrence=(
            "acts where caregiver_generation_index != dependent_generation_index"
        ),
        self_edge_policy="not_applicable",
        censoring_policy="kinship optional; generation_index from lifecycle only",
        formulas={
            "cross_generation_rate": "cross_generation_act_count / care_act_count",
        },
        value_keys=(
            "care_act_count",
            "cross_generation_act_count",
            "cross_generation_rate",
        ),
        empty_case="availability=absent; no_care_act_rows",
    )


def _spec_developmental_acquisition() -> MetricSpecification:
    return _base(
        family_id=MetricFamilyId.DEVELOPMENTAL_ACQUISITION,
        evidence_inputs=frozenset({EvidenceStage.AGENT_VISIBLE_PROJECTION}),
        population="developmental_acquisition_audits",
        denominator="acquired_audit_rows",
        denominator_kind=DenominatorKind.OCCURRENCE,
        cohort_window="audits harvested after the run",
        deceased_policy="not_applicable",
        zero_holding_policy="no audits -> availability=absent",
        opportunity_vs_occurrence="acquired rows only; skips do not inflate coverage",
        self_edge_policy="not_applicable",
        censoring_policy="metadata-only; never concept payloads",
        formulas={
            "mean_domain_coverage": "mean unique domains acquired per agent",
            "mean_confidence_mass": "mean confidence-band mass over acquired rows",
            "mean_time_to_first_entry": "mean tick of first acquired row per agent",
            "mean_exposures_to_acquisition": (
                "mean exposures_to_acquisition over first-write acquired rows"
            ),
        },
        value_keys=(
            "acquired_count",
            "agent_count",
            "mean_confidence_mass",
            "mean_domain_coverage",
            "mean_exposures_to_acquisition",
            "mean_time_to_first_entry",
        ),
        empty_case="availability=absent; no_developmental_audits",
    )


def _spec_developmental_source_mix() -> MetricSpecification:
    return _base(
        family_id=MetricFamilyId.DEVELOPMENTAL_SOURCE_MIX,
        evidence_inputs=frozenset({EvidenceStage.AGENT_VISIBLE_PROJECTION}),
        population="developmental_acquisition_audits",
        denominator="acquired_audit_rows",
        denominator_kind=DenominatorKind.OCCURRENCE,
        cohort_window="audits harvested after the run",
        deceased_policy="not_applicable",
        zero_holding_policy="no acquired rows -> availability=absent",
        opportunity_vs_occurrence="source share among acquired rows",
        self_edge_policy="not_applicable",
        censoring_policy=(
            "teacher ids metadata-only; never overloads cultural_transmission"
        ),
        formulas={
            "share_<source>": "count(source) / acquired_count",
            "dominant_source_share": "max source share",
            "teacher_entropy": "normalized Shannon entropy over teacher ids",
        },
        value_keys=(
            "acquired_count",
            "dominant_source_share",
            "source_kind_count",
            "teacher_entropy",
            "teacher_present_count",
        ),
        empty_case="availability=absent; no_acquired_audits",
    )


def _spec_developmental_divergence() -> MetricSpecification:
    return _base(
        family_id=MetricFamilyId.DEVELOPMENTAL_DIVERGENCE,
        evidence_inputs=frozenset({EvidenceStage.AGENT_VISIBLE_PROJECTION}),
        population="developmental_knowledge_ledgers",
        denominator="owner_ledger_pairs",
        denominator_kind=DenominatorKind.OCCURRENCE,
        cohort_window="caller-supplied owner ledgers after the run",
        deceased_policy="not_applicable",
        zero_holding_policy="fewer than two ledgers -> availability=absent",
        opportunity_vs_occurrence="pairwise Jaccard distance of concept keys",
        self_edge_policy="self_pairs_excluded",
        censoring_policy="never imports knowledge_diffusion; analysis-only",
        formulas={
            "mean_pairwise_distance": "mean 1 - |A cap B|/|A cup B| over pairs",
            "max_pairwise_distance": "max pairwise Jaccard distance",
        },
        value_keys=(
            "max_pairwise_distance",
            "mean_pairwise_distance",
            "pair_count",
        ),
        empty_case="availability=absent; insufficient_agents",
    )


def _spec_cultural_feature_provenance() -> MetricSpecification:
    return _base(
        family_id=MetricFamilyId.CULTURAL_FEATURE_PROVENANCE,
        evidence_inputs=frozenset({EvidenceStage.AGENT_VISIBLE_PROJECTION}),
        population="cultural_feature_audits",
        denominator="cultural_feature_audit_rows",
        denominator_kind=DenominatorKind.OCCURRENCE,
        cohort_window="audits harvested after the run",
        deceased_policy="not_applicable",
        zero_holding_policy="no audits -> availability=absent",
        opportunity_vs_occurrence="channel/kind histogram over audit rows",
        self_edge_policy="not_applicable",
        censoring_policy="metadata-only; never overloads cultural_transmission@1",
        formulas={
            "independent_rediscovery_share": (
                "count(independent_rediscovery) / audit_count"
            ),
            "evidence_coverage_share": "rows with provenance / audit_count",
        },
        value_keys=(
            "audit_count",
            "channel_count",
            "dominant_channel",
            "evidence_coverage_share",
            "feature_kind_count",
            "independent_rediscovery_share",
        ),
        empty_case="availability=absent; no_cultural_feature_audits",
    )


def _spec_cultural_trait_diffusion() -> MetricSpecification:
    return _base(
        family_id=MetricFamilyId.CULTURAL_TRAIT_DIFFUSION,
        evidence_inputs=frozenset({EvidenceStage.AGENT_VISIBLE_PROJECTION}),
        population="analytical_cultural_traits",
        denominator="trait_clusters",
        denominator_kind=DenominatorKind.OCCURRENCE,
        cohort_window="traits derived from harvested audits",
        deceased_policy="not_applicable",
        zero_holding_policy="no traits -> availability=absent",
        opportunity_vs_occurrence="carrier counts per analytical trait cluster",
        self_edge_policy="not_applicable",
        censoring_policy="analysis-only AnalyticalCulturalTrait; never cognition",
        formulas={
            "mean_carrier_count": "mean carrier_count over traits",
            "mean_hop_index": "mean hop over traits",
        },
        value_keys=(
            "max_carrier_count",
            "mean_carrier_count",
            "mean_generation_spread",
            "mean_hop_index",
            "trait_count",
        ),
        empty_case="availability=absent; no_analytical_traits",
    )


def _spec_cultural_feature_mutation() -> MetricSpecification:
    return _base(
        family_id=MetricFamilyId.CULTURAL_FEATURE_MUTATION,
        evidence_inputs=frozenset({EvidenceStage.AGENT_VISIBLE_PROJECTION}),
        population="cultural_feature_audits",
        denominator="cultural_feature_audit_rows",
        denominator_kind=DenominatorKind.OCCURRENCE,
        cohort_window="audits harvested after the run",
        deceased_policy="not_applicable",
        zero_holding_policy="no audits -> availability=absent",
        opportunity_vs_occurrence="mutation/recombination rates over audit rows",
        self_edge_policy="not_applicable",
        censoring_policy="metadata-only fingerprint digests; never payloads",
        formulas={
            "mutation_rate": "count(mutated) / audit_count",
            "recombination_rate": "count(recombined) / audit_count",
            "mean_parent_count": "mean parent_count over audits",
        },
        value_keys=(
            "audit_count",
            "mean_parent_count",
            "mean_recombined_parent_count",
            "mutated_count",
            "mutation_rate",
            "recombined_count",
            "recombination_rate",
        ),
        empty_case="availability=absent; no_cultural_feature_audits",
    )


def _spec_historical_memory_layers() -> MetricSpecification:
    return _base(
        family_id=MetricFamilyId.HISTORICAL_MEMORY_LAYERS,
        evidence_inputs=frozenset({EvidenceStage.AGENT_VISIBLE_PROJECTION}),
        population="historical_memory_sources",
        denominator="tracked_source_count",
        denominator_kind=DenominatorKind.OCCURRENCE,
        cohort_window="as_of tick after harvest",
        deceased_policy=(
            "death-exclusive living; post-death agents excluded from living"
        ),
        zero_holding_policy="no sources -> availability=absent",
        opportunity_vs_occurrence="layer histogram over tracked sources",
        self_edge_policy="not_applicable",
        censoring_policy=(
            "analysis-only historical memory; never cognition"
        ),
        formulas={
            "mean_living_witness_count": (
                "sum living_witness_ids / source_count"
            ),
            "communicative_carrier_share": (
                "communicative_carriers / "
                "(communicative_carriers + cultural_carriers)"
            ),
            "cultural_carrier_share": (
                "cultural_carriers / "
                "(communicative_carriers + cultural_carriers)"
            ),
        },
        value_keys=(
            "assignment_count",
            "communicative_carrier_share",
            "communicative_count",
            "cultural_carrier_share",
            "cultural_count",
            "living_count",
            "mean_living_witness_count",
            "source_count",
            "unattested_count",
        ),
        empty_case="availability=absent; no_historical_memory_sources",
    )


def _spec_historical_memory_transitions() -> MetricSpecification:
    return _base(
        family_id=MetricFamilyId.HISTORICAL_MEMORY_TRANSITIONS,
        evidence_inputs=frozenset({EvidenceStage.AGENT_VISIBLE_PROJECTION}),
        population="historical_memory_transitions",
        denominator="transition_count",
        denominator_kind=DenominatorKind.OCCURRENCE,
        cohort_window="sampled ticks under transition_tick_resolution",
        deceased_policy=(
            "death-linked causes when last witness dies or chain expires"
        ),
        zero_holding_policy="no transitions -> availability=absent",
        opportunity_vs_occurrence="transition rates by cause and from->to",
        self_edge_policy="not_applicable",
        censoring_policy=(
            "analysis-only historical memory; never cognition"
        ),
        formulas={
            "living_to_communicative_rate": (
                "count(living->communicative) / transition_count"
            ),
            "communicative_to_cultural_rate": (
                "count(communicative->cultural) / transition_count"
            ),
            "death_linked_share": (
                "count(death-linked causes) / transition_count"
            ),
        },
        value_keys=(
            "communicative_to_cultural_count",
            "communicative_to_cultural_rate",
            "death_linked_share",
            "living_to_communicative_count",
            "living_to_communicative_rate",
            "transition_count",
        ),
        empty_case="availability=absent; no_historical_memory_transitions",
    )


def _spec_durable_record_lineage() -> MetricSpecification:
    return _base(
        family_id=MetricFamilyId.DURABLE_RECORD_LINEAGE,
        evidence_inputs=frozenset({EvidenceStage.OBJECTIVE_EVENT_STATE}),
        population="durable_record_harvest_rows",
        denominator="durable_records_or_copy_events",
        denominator_kind=DenominatorKind.OCCURRENCE,
        cohort_window="caller-supplied durable harvest rows",
        deceased_policy="author death does not remove records from lineage",
        zero_holding_policy="no durable rows -> availability=absent",
        opportunity_vs_occurrence="copy-tree depth and generation histogram",
        self_edge_policy="not_applicable",
        censoring_policy="analysis-only durable records; never cognition",
        formulas={
            "max_copy_generation": "max copy_generation among rows",
            "mean_copy_generation": "mean copy_generation among rows",
            "parent_coverage": "rows with parent_artifact_id / record_count",
            "source_coverage": "rows with source_artifact_id / record_count",
            "tombstone_share": "destroyed/tombstone rows / record_count",
        },
        value_keys=(
            "max_copy_generation",
            "mean_copy_generation",
            "parent_coverage",
            "record_count",
            "source_coverage",
            "tombstone_count",
            "tombstone_share",
        ),
        empty_case="availability=absent; no_durable_record_rows",
    )


def _spec_durable_record_fidelity() -> MetricSpecification:
    return _base(
        family_id=MetricFamilyId.DURABLE_RECORD_FIDELITY,
        evidence_inputs=frozenset({EvidenceStage.OBJECTIVE_EVENT_STATE}),
        population="durable_record_copy_events",
        denominator="durable_records_or_copy_events",
        denominator_kind=DenominatorKind.OCCURRENCE,
        cohort_window="caller-supplied copy event rows",
        deceased_policy="not_applicable",
        zero_holding_policy="no copy events -> availability=absent",
        opportunity_vs_occurrence="perfect/mutation/lossy rates over copies",
        self_edge_policy="not_applicable",
        censoring_policy="analysis-only durable records; never cognition",
        formulas={
            "perfect_rate": "perfect copies / copy_event_count",
            "deterministic_mutation_rate": (
                "deterministic_mutation copies / copy_event_count"
            ),
            "lossy_rate": "lossy copies / copy_event_count",
            "mean_mark_edit_distance": "mean parent→child mark L1 distance",
            "mean_relation_edit_distance": (
                "mean parent→child relation L1 distance"
            ),
        },
        value_keys=(
            "copy_event_count",
            "deterministic_mutation_rate",
            "lossy_rate",
            "mean_mark_edit_distance",
            "mean_relation_edit_distance",
            "perfect_rate",
        ),
        empty_case="availability=absent; no_copy_events",
    )


def _spec_durable_record_survival() -> MetricSpecification:
    return _base(
        family_id=MetricFamilyId.DURABLE_RECORD_SURVIVAL,
        evidence_inputs=frozenset({EvidenceStage.OBJECTIVE_EVENT_STATE}),
        population="durable_record_harvest_rows",
        denominator="durable_records_or_copy_events",
        denominator_kind=DenominatorKind.OCCURRENCE,
        cohort_window="caller-supplied durable harvest + death ticks",
        deceased_policy="author death measured; records may remain intact",
        zero_holding_policy="no durable rows -> availability=absent",
        opportunity_vs_occurrence="integrity and false-record persistence rates",
        self_edge_policy="not_applicable",
        censoring_policy="analysis-only durable records; never cognition",
        formulas={
            "intact_after_author_death_count": (
                "intact rows whose author_id has a death tick >= created_tick"
            ),
            "false_record_persistence_rate": (
                "seeded false records still present / expectations"
            ),
        },
        value_keys=(
            "damaged_count",
            "destroyed_count",
            "false_record_persistence_rate",
            "intact_after_author_death_count",
            "intact_count",
            "partially_lost_count",
            "record_count",
        ),
        empty_case="availability=absent; no_durable_record_rows",
    )


def _spec_knowledge_repository_survival() -> MetricSpecification:
    return _base(
        family_id=MetricFamilyId.KNOWLEDGE_REPOSITORY_SURVIVAL,
        evidence_inputs=frozenset({EvidenceStage.OBJECTIVE_EVENT_STATE}),
        population="repository_objective_harvest_rows",
        denominator="knowledge_repositories",
        denominator_kind=DenominatorKind.OCCURRENCE,
        cohort_window="caller-supplied repository harvest + founder death ticks",
        deceased_policy="founder death measured; repositories may remain",
        zero_holding_policy="no repository rows -> availability=absent",
        opportunity_vs_occurrence="status and orphaned-member retention counts",
        self_edge_policy="not_applicable",
        censoring_policy="analysis-only knowledge repositories; never cognition",
        formulas={
            "surviving_after_founder_death_count": (
                "non-destroyed repos with a founder death tick >= established_tick"
            ),
            "orphaned_member_count": (
                "sum member_count over surviving-after-founder-death repos"
            ),
        },
        value_keys=(
            "destroyed_count",
            "inaccessible_count",
            "intact_count",
            "neglected_count",
            "orphaned_member_count",
            "repository_count",
            "surviving_after_founder_death_count",
        ),
        empty_case="availability=absent; no_repository_objective_rows",
    )


def _spec_knowledge_repository_access() -> MetricSpecification:
    return _base(
        family_id=MetricFamilyId.KNOWLEDGE_REPOSITORY_ACCESS,
        evidence_inputs=frozenset({EvidenceStage.OBJECTIVE_EVENT_STATE}),
        population="repository_access_event_rows",
        denominator="deposit_retrieve_attempts",
        denominator_kind=DenominatorKind.OCCURRENCE,
        cohort_window="caller-supplied repository event + objective rows",
        deceased_policy="not_applicable",
        zero_holding_policy="no access activity -> availability=absent",
        opportunity_vs_occurrence="deposit/retrieve success vs deny rates",
        self_edge_policy="not_applicable",
        censoring_policy="analysis-only knowledge repositories; never cognition",
        formulas={
            "deposit_success_count": "count repository_member_deposited events",
            "deposit_deny_count": "count deposit_denied event rows",
            "retrieve_success_count": "count repository_member_retrieved events",
            "retrieve_deny_count": "count retrieve_denied event rows",
            "inaccessible_block_count": (
                "count inaccessible block reasons / expectation hooks"
            ),
        },
        value_keys=(
            "deposit_deny_count",
            "deposit_success_count",
            "inaccessible_block_count",
            "retrieve_deny_count",
            "retrieve_success_count",
        ),
        empty_case="availability=absent; no_repository_access_activity",
    )


def _spec_knowledge_repository_organization() -> MetricSpecification:
    return _base(
        family_id=MetricFamilyId.KNOWLEDGE_REPOSITORY_ORGANIZATION,
        evidence_inputs=frozenset({EvidenceStage.OBJECTIVE_EVENT_STATE}),
        population="repository_objective_and_event_rows",
        denominator="knowledge_repositories_or_history",
        denominator_kind=DenominatorKind.OCCURRENCE,
        cohort_window="caller-supplied repository harvest rows",
        deceased_policy="not_applicable",
        zero_holding_policy="no organization rows -> availability=absent",
        opportunity_vs_occurrence="index coverage and neglect-driven drops",
        self_edge_policy="not_applicable",
        censoring_policy="analysis-only knowledge repositories; never cognition",
        formulas={
            "index_coverage_ratio": (
                "index_entry_count_total / member_count_total (0 if no members)"
            ),
            "dangling_index_entry_count": "sum dangling_index_entry_count",
            "neglect_index_drop_count": (
                "sum index_entries_dropped on repository_neglected"
            ),
            "history_event_count": "len(repository_event_rows)",
        },
        value_keys=(
            "dangling_index_entry_count",
            "history_event_count",
            "index_coverage_ratio",
            "index_entry_count_total",
            "member_count_total",
            "neglect_index_drop_count",
        ),
        empty_case="availability=absent; no_repository_organization_rows",
    )


def _spec_knowledge_genealogy_holders() -> MetricSpecification:
    return _base(
        family_id=MetricFamilyId.KNOWLEDGE_GENEALOGY_HOLDERS,
        evidence_inputs=frozenset({EvidenceStage.AGENT_VISIBLE_PROJECTION}),
        population="practical_knowledge_audit_rows",
        denominator="active_technique_holders",
        denominator_kind=DenominatorKind.OCCURRENCE,
        cohort_window="caller-supplied practical-knowledge audits + death_ticks",
        deceased_policy="dead holders counted separately; who_currently_knows filters living",
        zero_holding_policy="no practical-knowledge audits -> availability=absent",
        opportunity_vs_occurrence="active holders living vs dead; mean hop; teacher coverage",
        self_edge_policy="not_applicable",
        censoring_policy="analysis-only knowledge genealogy; never cognition",
        formulas={
            "living_holder_count": "active entries whose owner is living at as_of_tick",
            "dead_holder_count": "active entries whose owner is dead at as_of_tick",
            "mean_hop_index": "mean hop_index over active entries",
            "teacher_coverage_share": "audits with teacher/source id / audit_count",
        },
        value_keys=(
            "active_entry_count",
            "dead_holder_count",
            "living_holder_count",
            "mean_hop_index",
            "teacher_coverage_share",
            "technique_count",
        ),
        empty_case="availability=absent; no_practical_knowledge_audits",
    )


def _spec_knowledge_genealogy_lineage() -> MetricSpecification:
    return _base(
        family_id=MetricFamilyId.KNOWLEDGE_GENEALOGY_LINEAGE,
        evidence_inputs=frozenset({EvidenceStage.AGENT_VISIBLE_PROJECTION}),
        population="practical_knowledge_audit_rows",
        denominator="practical_knowledge_audits",
        denominator_kind=DenominatorKind.OCCURRENCE,
        cohort_window="caller-supplied practical-knowledge audits",
        deceased_policy="death_ticks used for surviving-root queries only",
        zero_holding_policy="no practical-knowledge audits -> availability=absent",
        opportunity_vs_occurrence="root counts, multi-parent share, dual emergence, unresolved joins",
        self_edge_policy="not_applicable",
        censoring_policy="analysis-only knowledge genealogy; never cognition",
        formulas={
            "multi_parent_share": "rows with >=2 parent_entry_ids / audit_count",
            "combination_rate": "origin=combination / audit_count",
            "dual_independent_emergence_rate": (
                "techniques with >=2 independent roots / technique_count"
            ),
            "unresolved_transmission_count": "analysis peer joins without source entry",
        },
        value_keys=(
            "combination_rate",
            "dual_independent_emergence_rate",
            "independent_root_count",
            "max_analysis_dag_depth",
            "max_owner_local_hop",
            "multi_parent_share",
            "unresolved_transmission_count",
        ),
        empty_case="availability=absent; no_practical_knowledge_audits",
    )


def _spec_knowledge_genealogy_mutation() -> MetricSpecification:
    return _base(
        family_id=MetricFamilyId.KNOWLEDGE_GENEALOGY_MUTATION,
        evidence_inputs=frozenset({EvidenceStage.AGENT_VISIBLE_PROJECTION}),
        population="practical_knowledge_audit_rows",
        denominator="practical_knowledge_audits",
        denominator_kind=DenominatorKind.OCCURRENCE,
        cohort_window="caller-supplied practical-knowledge audits",
        deceased_policy="not_applicable",
        zero_holding_policy="no practical-knowledge audits -> availability=absent",
        opportunity_vs_occurrence="mutated share and mean fingerprint_distance_q",
        self_edge_policy="not_applicable",
        censoring_policy="analysis-only knowledge genealogy; never cognition",
        formulas={
            "mutated_hop_share": "mutated audits / audit_count",
            "mean_fingerprint_distance_q": "mean fingerprint_distance_q over audits",
        },
        value_keys=(
            "audit_count",
            "mean_fingerprint_distance_q",
            "mutated_count",
            "mutated_hop_share",
        ),
        empty_case="availability=absent; no_practical_knowledge_audits",
    )



def _spec_historical_memory_queries() -> MetricSpecification:
    return _base(
        family_id=MetricFamilyId.HISTORICAL_MEMORY_QUERIES,
        evidence_inputs=frozenset({EvidenceStage.AGENT_VISIBLE_PROJECTION}),
        population="historical_memory_query_answers",
        denominator="tracked_source_count",
        denominator_kind=DenominatorKind.OCCURRENCE,
        cohort_window="as_of tick query report",
        deceased_policy=(
            "death-exclusive living witnesses; dead witnesses excluded"
        ),
        zero_holding_policy="no sources -> availability=absent",
        opportunity_vs_occurrence="true-counts for three locked queries",
        self_edge_policy="not_applicable",
        censoring_policy=(
            "analysis-only historical memory; never cognition"
        ),
        formulas={
            "true_share_any_direct_witnesses_alive": (
                "true_count / source_count"
            ),
            "true_share_anyone_remembers_speaking_to_witness": (
                "true_count / source_count"
            ),
            "true_share_event_known_only_from_stories_or_artifacts": (
                "true_count / source_count"
            ),
        },
        value_keys=(
            "answer_count",
            "as_of_tick",
            "source_count",
            "true_count_any_direct_witnesses_alive",
            "true_count_anyone_remembers_speaking_to_witness",
            "true_count_event_known_only_from_stories_or_artifacts",
            "true_share_any_direct_witnesses_alive",
            "true_share_anyone_remembers_speaking_to_witness",
            "true_share_event_known_only_from_stories_or_artifacts",
        ),
        empty_case="availability=absent; no_historical_memory_sources",
    )


def _spec_mentorship_fidelity() -> MetricSpecification:
    return _base(
        family_id=MetricFamilyId.MENTORSHIP_FIDELITY,
        evidence_inputs=frozenset({EvidenceStage.AGENT_VISIBLE_PROJECTION}),
        population="mentorship_audits",
        denominator="mentorship_audit_rows",
        denominator_kind=DenominatorKind.OCCURRENCE,
        cohort_window="audits harvested after the run",
        deceased_policy="not_applicable",
        zero_holding_policy="no audits -> availability=absent",
        opportunity_vs_occurrence="faithful share among mentorship audit rows",
        self_edge_policy="not_applicable",
        censoring_policy="metadata-only; never overloads cultural_transmission",
        formulas={
            "faithful_share": "count(not mutated) / audit_count",
            "mean_hop_index": "mean hop_index over audits",
            "max_hop_index": "max hop_index over audits",
        },
        value_keys=(
            "audit_count",
            "faithful_share",
            "max_hop_index",
            "mean_hop_index",
        ),
        empty_case="availability=absent; no_mentorship_audits",
    )


def _spec_mentorship_mutation() -> MetricSpecification:
    return _base(
        family_id=MetricFamilyId.MENTORSHIP_MUTATION,
        evidence_inputs=frozenset({EvidenceStage.AGENT_VISIBLE_PROJECTION}),
        population="mentorship_audits",
        denominator="mentorship_audit_rows",
        denominator_kind=DenominatorKind.OCCURRENCE,
        cohort_window="audits harvested after the run",
        deceased_policy="not_applicable",
        zero_holding_policy="no audits -> availability=absent",
        opportunity_vs_occurrence="mutation rate among mentorship audit rows",
        self_edge_policy="not_applicable",
        censoring_policy="metadata-only; never content fingerprints as payloads",
        formulas={
            "mutation_rate": "count(mutated) / audit_count",
            "mean_mutated_hop_index": "mean hop_index over mutated rows",
        },
        value_keys=(
            "audit_count",
            "mean_mutated_hop_index",
            "mutated_count",
            "mutation_rate",
        ),
        empty_case="availability=absent; no_mentorship_audits",
    )


def _spec_mentorship_bonds() -> MetricSpecification:
    return _base(
        family_id=MetricFamilyId.MENTORSHIP_BONDS,
        evidence_inputs=frozenset({EvidenceStage.AGENT_VISIBLE_PROJECTION}),
        population="mentorship_audits_or_ledgers",
        denominator="directed_bond_pairs",
        denominator_kind=DenominatorKind.OCCURRENCE,
        cohort_window="audits/ledgers harvested after the run",
        deceased_policy="not_applicable",
        zero_holding_policy="no bonds -> availability=absent",
        opportunity_vs_occurrence="directed owner→partner pairs from audits/ledgers",
        self_edge_policy="self_pairs_excluded",
        censoring_policy="never WorldEngine mentor role labels",
        formulas={
            "active_bond_count": "ledger bonds or unique directed pairs",
            "mean_bond_strength": "mean strength when ledgers supplied",
        },
        value_keys=(
            "active_bond_count",
            "apprentice_audit_count",
            "directed_pair_count",
            "mean_bond_strength",
            "mentor_audit_count",
        ),
        empty_case="availability=absent; no_mentorship_bonds",
    )


def _spec_spatial_control() -> MetricSpecification:
    return _base(
        family_id=MetricFamilyId.SPATIAL_CONTROL,
        evidence_inputs=frozenset({EvidenceStage.OBJECTIVE_EVENT_STATE}),
        population="committed_spatial_action_rows",
        denominator="exclusive_windows",
        denominator_kind=DenominatorKind.OCCURRENCE,
        cohort_window="caller-supplied committed rows after the run",
        deceased_policy="not_applicable",
        zero_holding_policy="empty action rows -> availability=absent",
        opportunity_vs_occurrence=(
            "exclusive windows of length at least 2; contests are readings"
        ),
        self_edge_policy="not_applicable",
        censoring_policy=(
            "omitted claim rows leave claim_contest absent; "
            "never invent a head"
        ),
        formulas={
            "repeated_control": (
                "an agent has two or more exclusive windows at one location"
            ),
            "control_contest": (
                "two agents each have two exclusive windows at one location"
            ),
            "claim_contest": (
                "two owners hold strength at least 0.40 on one location; "
                "absent when claim rows were omitted"
            ),
            "intervals": "canonical exclusive-window spans per location",
        },
        value_keys=(
            "claim_contest",
            "control_contest",
            "intervals",
            "repeated_control",
        ),
        empty_case="availability=absent; empty action rows are not zero control",
    )


def _spec_emergent_group_formation() -> MetricSpecification:
    return _base(
        family_id=MetricFamilyId.EMERGENT_GROUP_FORMATION,
        evidence_inputs=frozenset({EvidenceStage.OBJECTIVE_EVENT_STATE}),
        population="caller_supplied_interaction_rows",
        denominator="maximal_cliques",
        denominator_kind=DenominatorKind.OCCURRENCE,
        cohort_window="caller-supplied rows after the run",
        deceased_policy="not_applicable",
        zero_holding_policy="omitted rows -> availability=absent for that signal",
        opportunity_vs_occurrence=(
            "an edge requires the signal threshold; "
            "absent rows are not a zero cluster"
        ),
        self_edge_policy="self pairs are dropped",
        censoring_policy=(
            "omitted belief triples leave shared_beliefs absent; "
            "shared_enemies is a shared_harm reading only"
        ),
        formulas={
            "signal_count": "signals whose input rows were supplied",
            "cluster_count": "maximal cliques of size at least 2",
            "agent_count": "agents that belong to at least one cluster",
            "shared_enemies": "shared_harm cluster count stored as a reading",
        },
        value_keys=(
            "agent_count",
            "cluster_count",
            "shared_enemies",
            "signal_count",
        ),
        empty_case="availability=absent when every signal lacks rows",
    )


def _spec_emergent_social_norms() -> MetricSpecification:
    return _base(
        family_id=MetricFamilyId.EMERGENT_SOCIAL_NORMS,
        evidence_inputs=frozenset({EvidenceStage.OBJECTIVE_EVENT_STATE}),
        population="caller_supplied_behavior_and_belief_rows",
        denominator="opened_windows_or_active_beliefs",
        denominator_kind=DenominatorKind.OCCURRENCE,
        cohort_window="caller-supplied rows after the run",
        deceased_policy="not_applicable",
        zero_holding_policy="empty windows -> availability=absent for that key",
        opportunity_vs_occurrence=(
            "a return counts only after an opposite give; "
            "absent windows are not a zero rate"
        ),
        self_edge_policy="self pairs are dropped",
        censoring_policy=(
            "a missing belief row is not an active belief; "
            "the metric is not fed back into a ledger"
        ),
        formulas={
            "return_transfer_rate": "opposite gives within 8 ticks / opened windows",
            "share_under_scarcity_rate": "gives while food <= 1 / scarce ticks",
            "spare_after_sleep_rate": "unattacked sleeps / sleep occurrences",
            "reciprocal_exchange_rate": "later gives / established-pair opportunities",
            "active_belief_count": "rows whose status is active",
            "mean_confidence": "mean confidence of active rows",
            "repetition_without_belief": "rates at least 0.50 with no active belief",
            "belief_without_repetition": "active beliefs whose rate is below 0.50",
            "behavior_persistence": "adjacent ticks whose rate stays at least 0.50",
            "belief_persistence": "adjacent ticks that keep the same active belief",
        },
        value_keys=(
            "active_belief_count",
            "behavior_persistence",
            "belief_persistence",
            "belief_without_repetition",
            "mean_confidence",
            "reciprocal_exchange_rate",
            "repetition_without_belief",
            "return_transfer_rate",
            "share_under_scarcity_rate",
            "spare_after_sleep_rate",
        ),
        empty_case="availability=absent; empty rows are not zero belief",
    )


def _spec_cognitive_budget() -> MetricSpecification:
    return _base(
        family_id=MetricFamilyId.COGNITIVE_BUDGET,
        evidence_inputs=frozenset({EvidenceStage.OBJECTIVE_EVENT_STATE}),
        population="caller_supplied_cognitive_budget_audit_rows",
        denominator="audit_rows_per_arm",
        denominator_kind=DenominatorKind.OCCURRENCE,
        cohort_window="caller-supplied audits after the run",
        deceased_policy="not_applicable",
        zero_holding_policy="empty audit sequence -> availability=absent",
        opportunity_vs_occurrence=(
            "consumption totals sum used counts; empty rows are not zero use"
        ),
        self_edge_policy="not_applicable",
        censoring_policy=(
            "missing audits are not zero consumption; "
            "analysis never re-enters cognition"
        ),
        formulas={
            "total_llm_calls": "sum llm_calls_used",
            "total_tokens": "sum tokens_used",
            "total_imagination_branches": "sum imagination_branches_used",
            "degraded_tick_rate": "degraded audits / audits",
            "low_vs_high_llm_calls_strictly_fewer": (
                "low_cost total llm calls < high_cost total llm calls"
            ),
            "low_vs_high_branches_strictly_fewer": (
                "low_cost total branches < high_cost total branches"
            ),
        },
        value_keys=(
            "total_llm_calls",
            "total_tokens",
            "total_imagination_branches",
            "total_memories_recalled",
            "total_tom_targets",
            "mean_llm_calls_per_tick",
            "mean_branches_per_tick",
            "degraded_tick_count",
            "degraded_tick_rate",
            "exhausted_reason_count",
            "low_cost_total_llm_calls",
            "high_cost_total_llm_calls",
            "low_cost_total_branches",
            "high_cost_total_branches",
            "low_vs_high_llm_calls_strictly_fewer",
            "low_vs_high_branches_strictly_fewer",
        ),
        empty_case="availability=absent; empty audits are not zero consumption",
    )


def _spec_cultural_narrative_lineage() -> MetricSpecification:
    return _base(
        family_id=MetricFamilyId.CULTURAL_NARRATIVE_LINEAGE,
        evidence_inputs=frozenset({EvidenceStage.OBJECTIVE_EVENT_STATE}),
        population="caller_supplied_narrative_variant_history_rows",
        denominator="active_variants_or_founding_lineages",
        denominator_kind=DenominatorKind.OCCURRENCE,
        cohort_window="caller-supplied rows after the run",
        deceased_policy="not_applicable",
        zero_holding_policy="empty denominators -> availability=absent for that key",
        opportunity_vs_occurrence=(
            "a lineage persists only when an active or merged-into-active "
            "variant remains; empty rows are not a zero persistence rate"
        ),
        self_edge_policy="self pairs are dropped",
        censoring_policy=(
            "a missing variant row is not an active narrative; "
            "analysis joins never re-enter cognition"
        ),
        formulas={
            "active_variant_count": "rows with status active at final tick",
            "mean_active_strength": "mean strength of active rows",
            "mean_duration_ticks": "mean last_tick - first_tick of active/merged",
            "persistence_rate": (
                "founding fingerprints still represented by active/merged lineage"
            ),
            "branch_rate": "child variants / founding variants",
            "mean_mutation_generation": "mean generation over active rows",
            "fingerprint_churn": "mean distinct fingerprints per transmission root",
            "token_add_rate": "mean added tokens vs founding per active child",
            "token_loss_rate": "mean lost tokens vs founding per active child",
            "inaccuracy_vs_objective": (
                "active variants failing caller-supplied covers_source / covered"
            ),
            "source_event_drop_rate": (
                "active lineages that lost has_source_event from founding"
            ),
            "origin_shift_rate": "active children whose origin differs from founding",
            "orphan_retell_rate": "active retold_story without source ids / active",
            "merge_rate": "merged parents / variants that ever reached active",
            "mean_parents_per_merge": "mean parent arity on merge results",
            "competing_variant_share": "active with competitors / active",
            "mean_location_span": "mean distinct location_ids on active rows",
            "mean_carrier_span": "mean distinct carrier_agent_ids on active rows",
            "multi_location_rate": "active with location_count >= 2 / active",
            "social_reach_rate": "active with carrier_count >= 3 / active",
        },
        value_keys=(
            "active_variant_count",
            "branch_rate",
            "competing_variant_share",
            "fingerprint_churn",
            "inaccuracy_vs_objective",
            "mean_active_strength",
            "mean_carrier_span",
            "mean_duration_ticks",
            "mean_location_span",
            "mean_mutation_generation",
            "mean_parents_per_merge",
            "merge_rate",
            "multi_location_rate",
            "orphan_retell_rate",
            "origin_shift_rate",
            "persistence_rate",
            "social_reach_rate",
            "source_event_drop_rate",
            "token_add_rate",
            "token_loss_rate",
        ),
        empty_case="availability=absent; empty rows are not zero persistence",
    )


def _spec_emergent_semantic_naming() -> MetricSpecification:
    return _base(
        family_id=MetricFamilyId.EMERGENT_SEMANTIC_NAMING,
        evidence_inputs=frozenset({EvidenceStage.OBJECTIVE_EVENT_STATE}),
        population="caller_supplied_terminology_binding_rows",
        denominator="entities_owners_or_active_bindings",
        denominator_kind=DenominatorKind.OCCURRENCE,
        cohort_window="caller-supplied rows after the run",
        deceased_policy="not_applicable",
        zero_holding_policy="empty denominators -> availability=absent for that key",
        opportunity_vs_occurrence=(
            "a shared label counts only when two owners hold the same active token; "
            "absent rows are not a zero convergence rate"
        ),
        self_edge_policy="self pairs are dropped",
        censoring_policy=(
            "a missing binding row is not an active label; "
            "analysis joins never re-enter cognition"
        ),
        formulas={
            "shared_label_rate": (
                "entities with the same active top token on >=2 owners / entities"
            ),
            "mean_labels_per_entity": "mean distinct active tokens per entity",
            "mean_owners_per_label": "mean distinct owners per active token",
            "preferred_label_agreement": (
                "owner-pairs whose max-strength labels match / owner-pairs"
            ),
            "empty_lexicon_owner_rate": "owners with zero active bindings / owners",
            "mean_sense_revision": "mean sense_revision of active bindings",
            "label_turnover_rate": (
                "adjacent preferred-label changes / adjacent owner-entity windows"
            ),
            "meaning_shift_rate": "active bindings with sense_revision >= 1 / active",
            "merge_rate": "retired bindings with merged_into / retired+active",
            "competition_rate": "active bindings with competitors / active",
            "extinction_rate": (
                "labels active at window start and retired at end / start-active"
            ),
            "label_persistence": (
                "adjacent ticks keeping owner+token+candidate active at >=0.40"
            ),
            "sense_stability": (
                "adjacent ticks keeping active sense_revision unchanged"
            ),
        },
        value_keys=(
            "competition_rate",
            "empty_lexicon_owner_rate",
            "extinction_rate",
            "label_persistence",
            "label_turnover_rate",
            "mean_labels_per_entity",
            "mean_owners_per_label",
            "mean_sense_revision",
            "meaning_shift_rate",
            "merge_rate",
            "preferred_label_agreement",
            "sense_stability",
            "shared_label_rate",
        ),
        empty_case="availability=absent; empty rows are not zero convergence",
    )


def _spec_external_artifact_memory() -> MetricSpecification:
    return _base(
        family_id=MetricFamilyId.EXTERNAL_ARTIFACT_MEMORY,
        evidence_inputs=frozenset({EvidenceStage.OBJECTIVE_EVENT_STATE}),
        population="caller_supplied_artifact_memory_and_reading_rows",
        denominator="cue_rows_readers_or_owner_pairs",
        denominator_kind=DenominatorKind.OCCURRENCE,
        cohort_window="caller-supplied rows after soft-forget",
        deceased_policy="not_applicable",
        zero_holding_policy="empty denominators -> availability=absent for that key",
        opportunity_vs_occurrence=(
            "a record counts when present on or after the forget tick; "
            "absent readers are not a zero recovery rate"
        ),
        self_edge_policy="self pairs are dropped",
        censoring_policy=(
            "a missing interpretation row is not a recovered reading; "
            "empty cue rows stay absent"
        ),
        formulas={
            "record_present_after_forget": (
                "1.0 when the scenario record is present on/after forget tick; else 0.0"
            ),
            "mean_content_revision": (
                "mean content_revision among present rows at/after forget tick"
            ),
            "memory_loss_rate": "forgotten cue rows / cue rows for owner A",
            "reading_recovery_rate": (
                "owners with exact undistorted reading_marks / readers"
            ),
            "interpretation_divergence": (
                "owner-pairs with differing reading_marks on "
                "identical objective content"
            ),
        },
        value_keys=(
            "interpretation_divergence",
            "mean_content_revision",
            "memory_loss_rate",
            "reading_recovery_rate",
            "record_present_after_forget",
        ),
        empty_case="availability=absent; empty rows are not zero recovery",
    )


def _spec_persistent_social_conventions() -> MetricSpecification:
    return _base(
        family_id=MetricFamilyId.PERSISTENT_SOCIAL_CONVENTIONS,
        evidence_inputs=frozenset({EvidenceStage.OBJECTIVE_EVENT_STATE}),
        population="caller_supplied_objective_and_habit_rows",
        denominator="colocated_ticks_or_active_habits",
        denominator_kind=DenominatorKind.OCCURRENCE,
        cohort_window="caller-supplied rows after the run",
        deceased_policy="not_applicable",
        zero_holding_policy="empty denominators -> availability=absent for that key",
        opportunity_vs_occurrence=(
            "a meeting counts only on multi-agent colocated ticks; "
            "absent windows are not a zero rate"
        ),
        self_edge_policy="self pairs are dropped",
        censoring_policy=(
            "a missing habit row is not an active habit; "
            "ritual and tradition labels stay analysis-only"
        ),
        formulas={
            "recurrent_meeting_rate": (
                "colocated wait/talk ticks / multi-agent colocated ticks"
            ),
            "timed_gathering_rate": (
                "matching day-phase meetings across at least 3 ticks / colocated"
            ),
            "habitual_exchange_rate": (
                "repeated give pairs within 8 ticks / opened give opportunities"
            ),
            "collective_action_rate": (
                "shared action-kind ticks / multi-agent colocated ticks"
            ),
            "active_habit_count": "rows whose status is active",
            "mean_habit_strength": "mean strength of active rows",
            "mean_duration_ticks": "mean last_tick - first_tick of active rows",
            "mean_participant_count": "mean participants on active rows",
            "transmission_adoption_rate": (
                "active rows with communicated or both / active rows"
            ),
            "forgotten_reason_rate": "active rows with forgotten explanation / active",
            "competing_variant_share": "active rows with variant_count >= 1 / active",
            "named_custom_rate": "active rows with named_custom / active",
            "repetition_without_habit": (
                "situation rates at least 0.50 with no active habit"
            ),
            "habit_without_repetition": (
                "active habits whose situation rate is below 0.50"
            ),
            "reason_loss_persistence": (
                "adjacent history with active forgotten habits at strength >= 0.40"
            ),
            "ritual_like_persistence": (
                "history steps with forgotten/unknown, duration >= 8, "
                "participants >= 2, strength >= 0.40"
            ),
            "behavior_persistence": "adjacent ticks whose rate stays at least 0.50",
            "habit_persistence": (
                "adjacent ticks that keep the same owner+situation+action habit"
            ),
        },
        value_keys=(
            "active_habit_count",
            "behavior_persistence",
            "collective_action_rate",
            "competing_variant_share",
            "forgotten_reason_rate",
            "habit_persistence",
            "habit_without_repetition",
            "habitual_exchange_rate",
            "mean_duration_ticks",
            "mean_habit_strength",
            "mean_participant_count",
            "named_custom_rate",
            "reason_loss_persistence",
            "recurrent_meeting_rate",
            "repetition_without_habit",
            "ritual_like_persistence",
            "timed_gathering_rate",
            "transmission_adoption_rate",
        ),
        empty_case="availability=absent; empty rows are not zero habit",
    )


def _spec_cultural_transmission() -> MetricSpecification:
    return _base(
        family_id=MetricFamilyId.CULTURAL_TRANSMISSION,
        evidence_inputs=frozenset({EvidenceStage.AGENT_VISIBLE_PROJECTION}),
        population="teaching_audit_rows_and_practice_events",
        denominator="harvested teaching rows",
        denominator_kind=DenominatorKind.OCCURRENCE,
        cohort_window="audits harvested after the run",
        deceased_policy="not_applicable",
        zero_holding_policy="empty skill mass -> availability=unknown",
        opportunity_vs_occurrence="entropy of harvested objective vectors",
        self_edge_policy="not_applicable",
        censoring_policy="a missing side is unmatched and is not guessed",
        formulas={
            "normalized_entropy": "mean Shannon entropy of objective skill vectors",
            "js_divergence": (
                "mean Jensen-Shannon divergence from the population mixture"
            ),
            "advice_count": "count of advice rows",
            "belief_matches_advice": (
                "explain rows whose band matches the believed band"
            ),
            "objective_gains_without_practice": (
                "positive objective rows with no practice event"
            ),
            "misinformation_count": (
                "high explain bands whose source objective level is below the low band"
            ),
        },
        value_keys=(
            "advice_count",
            "belief_matches_advice",
            "misinformation_count",
            "normalized_entropy",
        ),
        empty_case="availability=unknown; empty skill mass is not zero",
    )


def _spec_theory_of_mind() -> MetricSpecification:
    return _base(
        family_id=MetricFamilyId.THEORY_OF_MIND,
        evidence_inputs=frozenset({EvidenceStage.OBJECTIVE_EVENT_STATE}),
        population="future_action_snapshots_per_run",
        denominator="harvested future-action snapshots",
        denominator_kind=DenominatorKind.OCCURRENCE,
        cohort_window="run window covering committed events and audits",
        deceased_policy="terminal agents stop new audits; existing audits remain",
        zero_holding_policy="no snapshots -> availability=absent",
        opportunity_vs_occurrence=(
            "compares harvested future actions with later occurrences"
        ),
        self_edge_policy="not_applicable",
        censoring_policy="no later occurrence stays unmatched; never invent a rate",
        formulas={
            "hypothesis_count": "count of harvested future-action snapshots",
            "matched_count": "snapshots with a later occurrence by that subject",
            "unmatched_count": "snapshots with no later occurrence",
            "max_absolute_error": "largest absolute confidence error among matches",
        },
        value_keys=(
            "hypothesis_count",
            "matched_count",
            "unmatched_count",
            "max_absolute_error",
        ),
    )


def _spec_communication_strategy() -> MetricSpecification:
    return _base(
        family_id=MetricFamilyId.COMMUNICATION_STRATEGY,
        evidence_inputs=frozenset({EvidenceStage.OBJECTIVE_EVENT_STATE}),
        population="communication_intent_audits_per_run",
        denominator="harvested communication intent audits",
        denominator_kind=DenominatorKind.OCCURRENCE,
        cohort_window="run window covering committed events and audits",
        deceased_policy="terminal agents stop new audits; existing audits remain",
        zero_holding_policy="no audits -> availability=absent",
        opportunity_vs_occurrence=(
            "joins hidden audits to committed occurrences; does not invent a rate"
        ),
        self_edge_policy="not_applicable",
        censoring_policy="missing cited events stay unmatched; never invent a rate",
        formulas={
            "memory_error": "assert_match whose cited occurrence does not cover atoms",
            "uncertain_inference": "hedged utterances",
            "deliberate_deception": "substituted, inflated, or dropped atoms",
            "not_asserted": "refusals and omissions",
            "veridical": "assert_match covered by the cited occurrence",
            "unmatched": "assert_match with no cited occurrence",
            "cascade_count": "later assert_match repeats a substituted render",
        },
        value_keys=(
            "memory_error",
            "uncertain_inference",
            "deliberate_deception",
            "not_asserted",
            "veridical",
            "unmatched",
            "cascade_count",
        ),
    )


def _spec_prospective_imagination() -> MetricSpecification:
    return _base(
        family_id=MetricFamilyId.PROSPECTIVE_IMAGINATION,
        evidence_inputs=frozenset({EvidenceStage.OBJECTIVE_EVENT_STATE}),
        population="prospective_audits_per_run",
        denominator="harvested prospective audits",
        denominator_kind=DenominatorKind.OCCURRENCE,
        cohort_window="run window covering committed events and audits",
        deceased_policy="terminal agents stop new audits; existing audits remain",
        zero_holding_policy="no audits -> availability=absent",
        opportunity_vs_occurrence=(
            "compares harvested audits with committed events after the run"
        ),
        self_edge_policy="not_applicable",
        censoring_policy="missing command events stay unmatched",
        formulas={
            "matched_count": "audits whose direction matches the first command",
            "unmatched_count": "audits whose direction does not match",
            "harm_count": "harm events at the copied place id",
            "absolute_error": "largest gap between confidence band and harm",
        },
        value_keys=(
            "matched_count",
            "unmatched_count",
            "harm_count",
            "absolute_error",
        ),
    )


def _spec_counterfactual_reasoning() -> MetricSpecification:
    return _base(
        family_id=MetricFamilyId.COUNTERFACTUAL_REASONING,
        evidence_inputs=frozenset({EvidenceStage.OBJECTIVE_EVENT_STATE}),
        population="counterfactual_audits_per_run",
        denominator="harvested counterfactual audits",
        denominator_kind=DenominatorKind.OCCURRENCE,
        cohort_window="run window covering committed events and audits",
        deceased_policy="terminal agents stop new audits; existing audits remain",
        zero_holding_policy="no audits -> availability=absent",
        opportunity_vs_occurrence=(
            "counts harvested scenario audits against committed event ids "
            "after the run"
        ),
        self_edge_policy="not_applicable",
        censoring_policy="audits without a scenario count stay absent",
        formulas={
            "scenario_count": "sum of audit scenario counts",
            "event_overlap_count": "scenario ids that equal a committed event id",
        },
        value_keys=("scenario_count", "event_overlap_count"),
    )


def _spec_identity_dynamics() -> MetricSpecification:
    return _base(
        family_id=MetricFamilyId.IDENTITY_DYNAMICS,
        evidence_inputs=frozenset({EvidenceStage.BELIEF_REVISION_TESTIMONY}),
        population="identity_audits_per_run",
        denominator="owners with history-derived identity beliefs",
        denominator_kind=DenominatorKind.OCCURRENCE,
        cohort_window="run window covering harvested identity belief heads",
        deceased_policy="terminal agents stop new heads; existing heads remain",
        zero_holding_policy="no identity predicates -> availability=absent",
        opportunity_vs_occurrence=(
            "counts over harvested identity heads only; flags-off runs absent"
        ),
        self_edge_policy="not_applicable",
        censoring_policy="missing report -> omitted; never invent counts",
        formulas={
            "aspect_ability": "count of ability views across owners",
            "aspect_weakness": "count of weakness views across owners",
            "aspect_recurring_behavior": "count of recurring-behavior views",
            "aspect_inferred_value": "count of inferred-value views",
            "aspect_social_role": "count of social-role views",
            "aspect_relationship": "count of relationship views",
            "aspect_commitment": "count of commitment views",
            "aspect_perceived_status": "count of perceived-status views",
            "aspect_reliability": "count of reliability views",
            "aspect_risk_tolerance": "count of risk-tolerance views",
            "aspect_competence": "count of competence views",
            "stability_low": "views in the low stability band",
            "stability_mid": "views in the mid stability band",
            "stability_high": "views in the high stability band",
            "dissonance_commitment_command": "commitment conflict notices",
            "dissonance_inferred_value_command": "inferred-value conflict notices",
            "dissonance_risk_above_tolerance": "risk-tolerance conflict notices",
            "owner_divergence": "mean pairwise aspect-multiset distance",
        },
        value_keys=(
            "aspect_ability",
            "aspect_weakness",
            "aspect_recurring_behavior",
            "aspect_inferred_value",
            "aspect_social_role",
            "aspect_relationship",
            "aspect_commitment",
            "aspect_perceived_status",
            "aspect_reliability",
            "aspect_risk_tolerance",
            "aspect_competence",
            "stability_low",
            "stability_mid",
            "stability_high",
            "dissonance_commitment_command",
            "dissonance_inferred_value_command",
            "dissonance_risk_above_tolerance",
            "owner_divergence",
        ),
        empty_case="no identity predicates -> availability=absent",
        unknown_case=(
            "incomplete audit export -> availability=unknown; "
            "MetricAvailability.unknown"
        ),
    )


def _spec_offline_consolidation() -> MetricSpecification:
    return _base(
        family_id=MetricFamilyId.OFFLINE_CONSOLIDATION,
        evidence_inputs=frozenset({EvidenceStage.RECONSTRUCTION}),
        population="offline_consolidation_audits_per_run",
        denominator="harvested sleep-consolidation audits",
        denominator_kind=DenominatorKind.OCCURRENCE,
        cohort_window="run window covering harvested sleep consolidations",
        deceased_policy="terminal agents stop new audits; existing audits remain",
        zero_holding_policy="no audits -> availability=absent",
        opportunity_vs_occurrence=(
            "counts over harvested audits only; disabled arms absent"
        ),
        self_edge_policy="not_applicable",
        censoring_policy="missing report -> omitted; never invent counts",
        formulas={
            "consolidation_invocations": "count of harvested audits",
            "traces_strengthened": "sum of strengthen counts",
            "traces_soft_forgotten": "sum of soft-forget counts",
            "patterns_merged": "sum of merge counts",
            "belief_revisions": "sum of belief revision counts",
            "relationship_revisions": "sum of relationship revision counts",
            "goal_transitions": "sum of goal transition counts",
        },
        value_keys=(
            "consolidation_invocations",
            "traces_strengthened",
            "traces_soft_forgotten",
            "patterns_merged",
            "belief_revisions",
            "relationship_revisions",
            "goal_transitions",
        ),
        empty_case="no audits -> availability=absent",
        unknown_case=(
            "incomplete audit export -> availability=unknown; "
            "MetricAvailability.unknown"
        ),
    )


def _spec_belief_accuracy() -> MetricSpecification:
    return _base(
        family_id=MetricFamilyId.BELIEF_ACCURACY,
        evidence_inputs=frozenset({EvidenceStage.BELIEF_REVISION_TESTIMONY}),
        population="claims_with_ClaimTruthSpec_coverage",
        denominator="evaluable_claim_revisions in validity interval",
        denominator_kind=DenominatorKind.EVALUABLE_CLAIMS,
        cohort_window="truth-spec validity ticks intersect run window",
        deceased_policy=(
            "owner death freezes further revisions; evaluate last in window"
        ),
        zero_holding_policy="not_applicable",
        opportunity_vs_occurrence=(
            "only ClaimTruthSpec-covered claims enter denominator; "
            "ordinary claims without evaluability remain unknown and excluded"
        ),
        self_edge_policy="not_applicable",
        censoring_policy=(
            "claims outside validity interval excluded; "
            "confidence-weighted accuracy uses belief confidence when present"
        ),
        formulas={
            "accuracy": (
                "n_correct / n_evaluable under TruthEvaluatorPolicy; "
                "categorical/numeric/boolean per ClaimTruthSpec"
            ),
            "confidence_weighted_accuracy": (
                "sum(confidence_i * correct_i)/sum(confidence_i); "
                "missing confidence -> unweighted subset or unknown if all missing"
            ),
        },
        value_keys=(
            "accuracy",
            "confidence_weighted_accuracy",
            "evaluable_count",
            "unknown_excluded_count",
        ),
        empty_case="no ClaimTruthSpec -> availability=absent",
        unknown_case=(
            "unevaluable claims excluded; if evaluable_count==0 -> unknown; "
            "MetricAvailability.unknown"
        ),
    )


def _spec_false_belief_persistence() -> MetricSpecification:
    return _base(
        family_id=MetricFamilyId.FALSE_BELIEF_PERSISTENCE,
        evidence_inputs=frozenset({EvidenceStage.BELIEF_REVISION_TESTIMONY}),
        population="false_evaluable_belief_onsets",
        denominator="onset events with ClaimTruthSpec false evaluation",
        denominator_kind=DenominatorKind.EVALUABLE_CLAIMS,
        cohort_window="from onset tick through correction/retirement/run_end",
        deceased_policy="death retires persistence clock as censored",
        zero_holding_policy="not_applicable",
        opportunity_vs_occurrence="persistence durations over false onsets only",
        self_edge_policy="not_applicable",
        censoring_policy=(
            "uncorrected at run end or death -> right-censored duration; "
            "report Kaplan-Meier-style median with censor counts"
        ),
        formulas={
            "mean_false_duration_ticks": (
                "mean observed durations treating censored as observed length "
                "only when labeled censored_mean policy; primary = KM median"
            ),
            "median_false_duration_ticks": "KM median duration; None if unidentified",
            "correction_rate": "n_corrected / n_onsets",
            "censored_fraction": "n_right_censored / n_onsets",
        },
        value_keys=(
            "median_false_duration_ticks",
            "correction_rate",
            "censored_fraction",
            "onset_count",
        ),
        empty_case="no false onsets -> availability=absent",
        unknown_case=(
            "missing truth specs -> unknown; MetricAvailability.unknown"
        ),
    )


def _spec_relationship_stability() -> MetricSpecification:
    return _base(
        family_id=MetricFamilyId.RELATIONSHIP_STABILITY,
        evidence_inputs=frozenset({EvidenceStage.RELATIONSHIP_REVISION}),
        population="directed_pairs_with_active_or_retired_revisions",
        denominator="tick_or_revision weighted active intervals",
        denominator_kind=DenominatorKind.ACTIVE_EDGES,
        cohort_window="relationship logical ticks in run",
        deceased_policy="endpoint death retires directed edges at death tick",
        zero_holding_policy=(
            "missing dimension -> exclude that dimension from pair score; "
            "not treat as 0.0"
        ),
        opportunity_vs_occurrence="stability over observed revision weight",
        self_edge_policy=(
            "self-loops forbidden; RelationshipRevision rejects self_target"
        ),
        censoring_policy="active at run end contribute open interval weight",
        signed_trust_policy=(
            "trust dimension uses signed unit [-1,1]; "
            "stability uses absolute delta and sign-change indicators"
        ),
        formulas={
            "mean_abs_delta": (
                "revision-weighted mean |Δdimension| over TRUST..DEPENDENCY; "
                "sorted pair_ids"
            ),
            "sign_change_rate": (
                "n_sign_changes(trust) / n_trust_intervals with defined signs"
            ),
            "activation_retirement_counts": "pandas counts by activation_state",
            "duration_weighted_variance": (
                "variance of dimension values weighted by active duration ticks"
            ),
        },
        value_keys=(
            "mean_abs_delta",
            "sign_change_rate",
            "active_edge_count",
            "retired_edge_count",
        ),
        empty_case="no relationships -> availability=absent",
        one_case="one directed edge ok",
    )


def _spec_trust_network() -> MetricSpecification:
    return _base(
        family_id=MetricFamilyId.TRUST_NETWORK_STRUCTURE,
        evidence_inputs=frozenset(
            {
                EvidenceStage.RELATIONSHIP_REVISION,
                EvidenceStage.OBJECTIVE_EVENT_STATE,
            }
        ),
        population="agents_as_graph_nodes",
        denominator="possible_directed_edges n*(n-1)",
        denominator_kind=DenominatorKind.ACTIVE_EDGES,
        cohort_window="latest active relationship revision at window end",
        deceased_policy=(
            "deceased nodes retained as isolates unless drop_dead=true policy"
        ),
        zero_holding_policy="missing trust -> no edge (not zero weight)",
        opportunity_vs_occurrence="graph metrics over projected edges",
        self_edge_policy="self-loops dropped; isolates allowed",
        censoring_policy="partial relationship evidence -> MetricAvailability.partial",
        signed_trust_policy=(
            "signed trust in [-1,1]; confidence threshold τ default 0.0; "
            "edges with |trust|<τ or missing confidence excluded"
        ),
        graph_projection=(
            "DiGraph sorted nodes; edge weight=trust; "
            "optional interaction multiplicity as separate parallel graph"
        ),
        community_algorithm="not_applicable_on_signed_graph_use_nonnegative_family",
        formulas={
            "density": "m / (n*(n-1)) for n>=2 else unknown",
            "reciprocity": "NetworkX reciprocity on unweighted projection",
            "mean_in_degree_weight": "mean weighted in-degree; sorted nodes",
            "mean_out_degree_weight": "mean weighted out-degree",
            "weak_components": "number of weakly connected components",
            "centralization_out": (
                "Freeman out-degree centralization on nonnegative abs(trust) "
                "projection for ranking only; n<2 -> unknown (never coerce to 0)"
            ),
            "mean_degree_centrality": (
                "mean NetworkX degree_centrality on nonnegative undirected "
                "projection; lexicographic node order; self-loops dropped; "
                "n<2 -> unknown"
            ),
            "mean_betweenness_centrality": (
                "mean NetworkX betweenness_centrality (exact) on nonnegative "
                "undirected projection; lexicographic node order; self-loops "
                "dropped; n<2 -> unknown"
            ),
            "mean_closeness_centrality": (
                "mean NetworkX closeness_centrality (exact) on nonnegative "
                "undirected projection; lexicographic node order; self-loops "
                "dropped; n<2 -> unknown"
            ),
        },
        value_keys=(
            "density",
            "reciprocity",
            "mean_in_degree_weight",
            "mean_out_degree_weight",
            "weak_components",
            "node_count",
            "edge_count",
            "centralization_out",
            "mean_degree_centrality",
            "mean_betweenness_centrality",
            "mean_closeness_centrality",
        ),
        networkx_policy=_NX_POLICY,
        empty_case="n==0 -> unknown",
        one_case=(
            "n==1 -> density/centralization/centrality means unknown; "
            "components=1; degrees 0"
        ),
        all_zero_case="all trust zero below τ -> empty edge set density=0 present",
    )


def _spec_group_community() -> MetricSpecification:
    return _base(
        family_id=MetricFamilyId.GROUP_COMMUNITY_STRUCTURE,
        evidence_inputs=frozenset({EvidenceStage.RELATIONSHIP_REVISION}),
        population="agents_as_graph_nodes",
        denominator="nonnegative_undirected_projection edges",
        denominator_kind=DenominatorKind.ACTIVE_EDGES,
        cohort_window="same snapshot as trust_network_structure",
        deceased_policy="same as trust network",
        zero_holding_policy="nonpositive projected weights dropped",
        opportunity_vs_occurrence="community partition over projection",
        self_edge_policy="self-loops dropped before community detection",
        censoring_policy=(
            "disconnected graphs still partitioned; report component count"
        ),
        signed_trust_policy=(
            "project signed trust to nonnegative weight w=max(trust,0); "
            "negative trust never enters community graph"
        ),
        graph_projection=(
            "undirected Graph; combine u->v and v->u by max(w_uv,w_vu); "
            "nodes lexicographically sorted before algorithm"
        ),
        community_algorithm=SUPPORTED_COMMUNITY_ALGORITHM,
        formulas={
            "community_count": (
                "len(greedy_modularity_communities(G)); "
                "tie-break via sorted node iteration; canonicalize labels by "
                "sorted(min(node) for community)"
            ),
            "modularity": "NetworkX modularity of returned partition",
            "largest_community_share": "max community size / n",
        },
        value_keys=(
            "community_count",
            "modularity",
            "largest_community_share",
            "node_count",
        ),
        networkx_policy=_NX_POLICY,
        empty_case="n==0 -> unknown",
        one_case="one community size 1; modularity 0.0 or unknown per NX degenerate",
        all_zero_case="no edges -> n singleton communities; modularity 0.0 present",
    )


def _spec_knowledge_diffusion() -> MetricSpecification:
    return _base(
        family_id=MetricFamilyId.KNOWLEDGE_DIFFUSION,
        evidence_inputs=frozenset(
            {
                EvidenceStage.OBJECTIVE_EVENT_STATE,
                EvidenceStage.COMMUNICATED_TRACE,
                EvidenceStage.BELIEF_REVISION_TESTIMONY,
                EvidenceStage.RECONSTRUCTION,
            }
        ),
        population="transmission_roots_in_run",
        denominator="adoption_eligible_agents_per_stage",
        denominator_kind=DenominatorKind.ADOPTION_ELIGIBLE,
        cohort_window="from root emission through run end",
        deceased_policy="dead agents ineligible for new adoption after death tick",
        zero_holding_policy="not_applicable",
        opportunity_vs_occurrence=(
            "stage-specific reach = first adopters / eligible; "
            "never merge declared lineage with verified world truth"
        ),
        self_edge_policy="speaker-to-self delivery ignored",
        censoring_policy="non-adopters at run end remain eligible non-events",
        adoption_stages=ADOPTION_STAGES_V1,
        evidence_stage_deduplication=(
            "prefer explicit transmission_root_id; reject cycles; "
            "never infer parents from sorted hop order"
        ),
        formulas={
            "reach_by_stage": (
                "for each AdoptionStage: unique adopters / eligible; "
                "pandas columns sorted"
            ),
            "mean_first_adoption_tick": "mean first tick per stage among adopters",
            "mean_hops_to_adoption": "mean hop_count at first receiver_trace",
            "branch_count": "transmission branches per SocialTransmissionReport policy",
        },
        value_keys=(
            "reach_world_delivery",
            "reach_receiver_trace",
            "reach_belief_activation",
            "mean_first_adoption_tick",
            "mean_hops_to_adoption",
            "branch_count",
            "root_count",
        ),
        empty_case="no roots -> availability=absent",
        unknown_case=(
            "unresolved lineage links counted separately; "
            "if all unresolved -> partial/unknown; MetricAvailability.unknown"
        ),
    )


def _spec_rumor_distortion() -> MetricSpecification:
    return _base(
        family_id=MetricFamilyId.RUMOR_DISTORTION,
        evidence_inputs=frozenset(
            {
                EvidenceStage.OBJECTIVE_EVENT_STATE,
                EvidenceStage.COMMUNICATED_TRACE,
                EvidenceStage.BELIEF_REVISION_TESTIMONY,
            }
        ),
        population="multi_hop_transmission_chains",
        denominator="hop_pairs_with_structured_content_both_sides",
        denominator_kind=DenominatorKind.OCCURRENCE,
        cohort_window="per transmission_root",
        deceased_policy="hops involving dead speaker after death excluded",
        zero_holding_policy="empty concept sets allowed as zero edits",
        opportunity_vs_occurrence=(
            "distortion counts additions/losses/edits; "
            "unsupported additions never treated as objective truth"
        ),
        self_edge_policy="ignore self retells for distortion edges",
        censoring_policy="unresolved parent links excluded from pair denominator",
        adoption_stages=ADOPTION_STAGES_V1,
        evidence_stage_deduplication=(
            "compare consecutive hops on declared parent links only"
        ),
        formulas={
            "mean_concepts_added": "mean concepts_added over TransmissionDistortion",
            "mean_concepts_removed": "mean concepts_removed",
            "mean_relations_changed": (
                "mean(relations_added+relations_removed)"
            ),
            "mean_confidence_attenuation": (
                "mean max(0, sender_confidence-receiver_confidence) when both known"
            ),
            "unresolved_coverage": "unresolved_link_count / hop_count",
        },
        value_keys=(
            "mean_concepts_added",
            "mean_concepts_removed",
            "mean_relations_changed",
            "mean_confidence_attenuation",
            "unresolved_coverage",
            "distortion_edge_count",
        ),
        empty_case="no multi-hop pairs -> availability=absent",
        unknown_case=(
            "missing structured content -> unknown; MetricAvailability.unknown"
        ),
    )


def action_resolution_rate_spec() -> SharedActionResolutionRateSpec:
    """Shared attempted/rejected/conflicted rate formulas for Task 11."""
    return SharedActionResolutionRateSpec(
        algorithm_version=_ALGO_V1,
        evidence_inputs=frozenset({EvidenceStage.ACTION_RESOLUTION}),
        population="action_resolutions_in_window",
        denominator="submitted_resolutions (never absent-event inference)",
        deceased_policy="DEAD_ACTOR status counted in rejected/dead class not applied",
        opportunity_vs_occurrence=(
            "attempted = all resolutions; "
            "applied/rejected/conflicted/duplicate/deferred are partitions; "
            "occurrence rates over attempts"
        ),
        empty_case="no resolutions -> availability=absent",
        unknown_case=(
            "legacy runs without ActionResolution evidence -> unknown; "
            "never infer rejected from missing WorldEvent"
        ),
        availability_behavior=(
            "present when ActionResolution stream complete for window; "
            "partial if manifest high-water incomplete"
        ),
        numpy_policy=_NUM_POLICY,
        pandas_policy=_PANDAS_POLICY,
        quantization=(
            f"quantize_float to {CANONICAL_FLOAT_DECIMAL_PLACES} d.p.; "
            f"{CANONICAL_OUTPUT_CLAIM}"
        ),
        formulas={
            "attempt_count": "count all ActionResolution rows in window",
            "applied_rate": "count APPLIED / attempt_count",
            "rejected_rate": (
                "count REJECTED+DEAD_ACTOR+DUPLICATE+DEFERRED_POLICY / attempt_count"
            ),
            "conflicted_rate": "count CONFLICTED / attempt_count",
            "by_status": "pandas value_counts status sorted by status code",
        },
        value_keys=(
            "attempt_count",
            "applied_rate",
            "rejected_rate",
            "conflicted_rate",
        ),
    )


def _spec_territorial_concentration() -> MetricSpecification:
    return _base(
        family_id=MetricFamilyId.TERRITORIAL_CONCENTRATION,
        evidence_inputs=frozenset({EvidenceStage.OBJECTIVE_EVENT_STATE}),
        population="detached_presence_and_control_spatial_rows",
        denominator="location_share_mass",
        denominator_kind=DenominatorKind.OCCURRENCE,
        cohort_window="caller-supplied detached spatial rows after the run",
        deceased_policy="living-agent presence rows only as supplied by caller",
        zero_holding_policy="missing presence/control rows -> channel keys absent",
        opportunity_vs_occurrence=(
            "HHI and top shares over observed location mass; "
            "missing channels stay absent"
        ),
        self_edge_policy="not_applicable",
        censoring_policy=(
            "empty both channels -> availability=absent; never invent zeros"
        ),
        formulas={
            "presence_hhi": "sum of squared presence location shares",
            "presence_top1_share": "largest presence location share",
            "presence_top3_share": "sum of three largest presence location shares",
            "control_hhi": "sum of squared control location shares",
            "control_top1_share": "largest control location share",
            "control_top3_share": "sum of three largest control location shares",
            "presence_location_count": "distinct presence locations",
            "control_location_count": "distinct control locations",
        },
        value_keys=(
            "presence_hhi",
            "presence_top1_share",
            "presence_top3_share",
            "control_hhi",
            "control_top1_share",
            "control_top3_share",
            "presence_location_count",
            "control_location_count",
        ),
        empty_case="availability=absent; reason no_spatial_rows",
    )


def _spec_prediction_calibration() -> MetricSpecification:
    return _base(
        family_id=MetricFamilyId.PREDICTION_CALIBRATION,
        evidence_inputs=frozenset(
            {
                EvidenceStage.AGENT_VISIBLE_PROJECTION,
                EvidenceStage.OBJECTIVE_EVENT_STATE,
            }
        ),
        population="joined_confidence_outcome_rows",
        denominator="evaluated_prediction_rows",
        denominator_kind=DenominatorKind.OCCURRENCE,
        cohort_window="caller-joined hypothesis confidence to empirical outcomes",
        deceased_policy="not_applicable",
        zero_holding_policy="empty evaluable rows -> availability=absent",
        opportunity_vs_occurrence=(
            "Brier and calibration error over joined rows; "
            "never invent engine probabilities"
        ),
        self_edge_policy="not_applicable",
        censoring_policy="unjoined hypotheses omitted by caller before compute",
        formulas={
            "brier_score": (
                "mean squared error of predicted_confidence vs empirical_outcome"
            ),
            "mean_absolute_calibration_error": (
                "mean over nonempty fixed bins of "
                "|mean(pred)-mean(outcome)|; bin edges "
                "(0.0, 0.2, 0.4, 0.6, 0.8, 1.0]"
            ),
            "evaluated_count": "number of joined confidence/outcome rows",
            "bin_count_used": "number of fixed bins with at least one sample",
        },
        value_keys=(
            "brier_score",
            "mean_absolute_calibration_error",
            "evaluated_count",
            "bin_count_used",
        ),
        empty_case="availability=absent; omit numeric values",
    )


def _spec_belief_convergence() -> MetricSpecification:
    return _base(
        family_id=MetricFamilyId.BELIEF_CONVERGENCE,
        evidence_inputs=frozenset({EvidenceStage.BELIEF_REVISION_TESTIMONY}),
        population="detached_belief_claim_rows",
        denominator="owner_pairs_with_active_claim_sets",
        denominator_kind=DenominatorKind.POPULATION_SIZE,
        cohort_window="ordered claim rows after the run",
        deceased_policy="not_applicable",
        zero_holding_policy="empty or single-owner -> availability=absent",
        opportunity_vs_occurrence=(
            "pairwise Jaccard on active claim overlap identity "
            "(claim_id, value_kind, normalized value); convergence != accuracy"
        ),
        self_edge_policy="not_applicable",
        censoring_policy="inactive claims excluded from overlap sets",
        formulas={
            "mean_pairwise_jaccard_final": (
                "mean pairwise Jaccard of active claim sets at final tick"
            ),
            "mean_pairwise_jaccard_delta": (
                "final mean pairwise Jaccard minus first-tick mean"
            ),
            "owner_count": "distinct claim owners",
            "claim_universe_size": "distinct overlap identity tokens",
        },
        value_keys=(
            "mean_pairwise_jaccard_final",
            "mean_pairwise_jaccard_delta",
            "owner_count",
            "claim_universe_size",
        ),
        empty_case="availability=absent; unevaluable_claims",
    )


def _spec_cultural_similarity() -> MetricSpecification:
    return _base(
        family_id=MetricFamilyId.CULTURAL_SIMILARITY,
        evidence_inputs=frozenset({EvidenceStage.AGENT_VISIBLE_PROJECTION}),
        population="detached_naming_norm_convention_narrative_rows",
        denominator="owner_pairs_per_channel",
        denominator_kind=DenominatorKind.POPULATION_SIZE,
        cohort_window="caller-supplied channel rows after the run",
        deceased_policy="not_applicable",
        zero_holding_policy=(
            "missing channel -> that channel key absent without zeroing others"
        ),
        opportunity_vs_occurrence=(
            "per-channel mean pairwise Jaccard; no blended culture score"
        ),
        self_edge_policy="not_applicable",
        censoring_policy="all channels empty -> availability=absent",
        formulas={
            "naming_mean_pairwise_similarity": (
                "mean pairwise Jaccard of naming token sets"
            ),
            "norms_mean_pairwise_similarity": (
                "mean pairwise Jaccard of norm head sets"
            ),
            "conventions_mean_pairwise_similarity": (
                "mean pairwise Jaccard of convention habit sets"
            ),
            "narratives_mean_pairwise_similarity": (
                "mean pairwise Jaccard of narrative variant fingerprints"
            ),
            "channels_present": "count of channels with evaluable owner pairs",
        },
        value_keys=(
            "naming_mean_pairwise_similarity",
            "norms_mean_pairwise_similarity",
            "conventions_mean_pairwise_similarity",
            "narratives_mean_pairwise_similarity",
            "channels_present",
        ),
        empty_case="availability=absent; all_channels_empty",
    )


_BUILDERS: Final[tuple[Callable[[], MetricSpecification], ...]] = (
    _spec_resource_inequality,
    _spec_cooperation,
    _spec_conflict,
    _spec_survival,
    _spec_goal_completion,
    _spec_repeated_conventions,
    _spec_behavioral_specialization,
    _spec_memory_drift,
    _spec_memory_dynamics,
    _spec_offline_consolidation,
    _spec_reflection,
    _spec_identity_dynamics,
    _spec_causal_world_model,
    _spec_theory_of_mind,
    _spec_communication_strategy,
    _spec_prospective_imagination,
    _spec_belief_accuracy,
    _spec_false_belief_persistence,
    _spec_relationship_stability,
    _spec_trust_network,
    _spec_group_community,
    _spec_knowledge_diffusion,
    _spec_rumor_distortion,
    _spec_counterfactual_reasoning,
    _spec_distributed_reputation,
    _spec_skill_learning,
    _spec_cultural_transmission,
    _spec_spatial_control,
    _spec_kinship_genealogy,
    _spec_dependency_survival,
    _spec_caregiver_diversity,
    _spec_caregiving_burden,
    _spec_intergenerational_cooperation,
    _spec_developmental_acquisition,
    _spec_developmental_source_mix,
    _spec_developmental_divergence,
    _spec_mentorship_fidelity,
    _spec_mentorship_mutation,
    _spec_mentorship_bonds,
    _spec_cultural_feature_provenance,
    _spec_cultural_trait_diffusion,
    _spec_cultural_feature_mutation,
    _spec_historical_memory_layers,
    _spec_historical_memory_transitions,
    _spec_historical_memory_queries,
    _spec_durable_record_lineage,
    _spec_durable_record_fidelity,
    _spec_durable_record_survival,
    _spec_knowledge_repository_survival,
    _spec_knowledge_repository_access,
    _spec_knowledge_repository_organization,
    _spec_knowledge_genealogy_holders,
    _spec_knowledge_genealogy_lineage,
    _spec_knowledge_genealogy_mutation,
    _spec_emergent_group_formation,
    _spec_emergent_social_norms,
    _spec_persistent_social_conventions,
    _spec_external_artifact_memory,
    _spec_emergent_semantic_naming,
    _spec_cultural_narrative_lineage,
    _spec_cognitive_budget,
    _spec_territorial_concentration,
    _spec_prediction_calibration,
    _spec_belief_convergence,
    _spec_cultural_similarity,
)


def all_metric_specifications() -> tuple[MetricSpecification, ...]:
    """Return the closed ordered catalog of family specifications."""
    return tuple(builder() for builder in _BUILDERS)


def metric_specification(family: MetricFamilyId | str) -> MetricSpecification:
    """Lookup one family specification; fail-closed on unknown ids."""
    family_id = require_metric_family_id("metric_specification", family)
    for spec in all_metric_specifications():
        if spec.family_id is family_id:
            return spec
    raise MetricSpecificationError(
        metric_family=family_id.value,
        algorithm_version="unknown",
        reason_code="family_not_in_catalog",
    )


def validate_metric_catalog() -> tuple[MetricSpecification, ...]:
    """Validate every family and catalog cardinality/uniqueness."""
    specs = all_metric_specifications()
    if len(specs) != METRIC_FAMILY_COUNT:
        raise MetricSpecificationError(
            metric_family="catalog",
            algorithm_version=METRIC_CATALOG_VERSION,
            reason_code="family_count_mismatch",
        )
    seen: set[MetricFamilyId] = set()
    for spec in specs:
        validate_metric_specification(spec)
        if spec.family_id in seen:
            raise MetricSpecificationError(
                metric_family=spec.family_id.value,
                algorithm_version=spec.algorithm_version,
                reason_code="duplicate_family",
            )
        seen.add(spec.family_id)
    expected = frozenset(MetricFamilyId)
    if seen != expected:
        raise MetricSpecificationError(
            metric_family="catalog",
            algorithm_version=METRIC_CATALOG_VERSION,
            reason_code="family_set_mismatch",
        )
    shared = action_resolution_rate_spec()
    if not shared.formulas or not shared.value_keys:
        raise MetricSpecificationError(
            metric_family="action_resolution_rates",
            algorithm_version=shared.algorithm_version,
            reason_code="shared_spec_incomplete",
        )
    return specs
