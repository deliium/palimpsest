"""Ordered 30-case V3 generational civilization benchmark registry.

Every numbered research request owns one discoverable case with an explicit
mechanism lane and an autonomous (or declared grouped) research lane. The
registry is metadata only: it never scripts a civilizational outcome and never
derives a passing invariant from an unavailable measurement.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Final

from experiments.civilization_benchmark_models import (
    V3_BENCHMARK_ID_PREFIX,
    V3_BENCHMARK_SCENARIO_COUNT,
    V3_BENCHMARK_SUITE_ID,
    V3_BENCHMARK_SUITE_VERSION,
    V3BenchmarkContrastKind,
    V3BenchmarkError,
    V3BenchmarkEvidenceSelector,
    V3BenchmarkExecutionKind,
    V3BenchmarkLane,
    V3BenchmarkProfile,
    V3BenchmarkRecipe,
    V3BenchmarkSpec,
    V3BenchmarkTreatmentScope,
)
from world.identifiers import require_stable_id

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.civilization_benchmark_suite"
)

V3_BENCH_01_BLANK_SLATE: Final[str] = "v3-bench-01-blank-slate"
V3_BENCH_02_DEPENDENT_CARE: Final[str] = "v3-bench-02-dependent-care"
V3_BENCH_03_INTERGENERATIONAL_TEACHING: Final[str] = (
    "v3-bench-03-intergenerational-teaching"
)
V3_BENCH_04_CULTURAL_MUTATION: Final[str] = "v3-bench-04-cultural-mutation"
V3_BENCH_05_MEMORY_LAYERS: Final[str] = "v3-bench-05-memory-layers"
V3_BENCH_06_RECORD_AFTER_WITNESSES: Final[str] = "v3-bench-06-record-after-witnesses"
V3_BENCH_07_FALSE_RECORD: Final[str] = "v3-bench-07-false-record"
V3_BENCH_08_TECHNOLOGY_DISCOVERY: Final[str] = "v3-bench-08-technology-discovery"
V3_BENCH_09_TECHNOLOGY_DIFFUSION: Final[str] = "v3-bench-09-technology-diffusion"
V3_BENCH_10_TECHNOLOGY_LOSS: Final[str] = "v3-bench-10-technology-loss"
V3_BENCH_11_TECHNOLOGY_REDISCOVERY: Final[str] = "v3-bench-11-technology-rediscovery"
V3_BENCH_12_INHERITANCE_PRACTICES: Final[str] = "v3-bench-12-inheritance-practices"
V3_BENCH_13_LONG_TERM_COMMITMENTS: Final[str] = "v3-bench-13-long-term-commitments"
V3_BENCH_14_SUBJECTIVE_BARTER: Final[str] = "v3-bench-14-subjective-barter"
V3_BENCH_15_CANDIDATE_EXCHANGE_MEDIUM: Final[str] = (
    "v3-bench-15-candidate-exchange-medium"
)
V3_BENCH_16_COLLECTIVE_PROJECT: Final[str] = "v3-bench-16-collective-project"
V3_BENCH_17_PUBLIC_GOOD_PATTERNS: Final[str] = "v3-bench-17-public-good-patterns"
V3_BENCH_18_REGIONAL_MIGRATION: Final[str] = "v3-bench-18-regional-migration"
V3_BENCH_19_ISOLATED_DIVERGENCE: Final[str] = "v3-bench-19-isolated-divergence"
V3_BENCH_20_RECONTACT_EXCHANGE: Final[str] = "v3-bench-20-recontact-exchange"
V3_BENCH_21_VOCABULARY_DIVERGENCE: Final[str] = "v3-bench-21-vocabulary-divergence"
V3_BENCH_22_GENERATIONAL_SEMANTIC_DRIFT: Final[str] = (
    "v3-bench-22-generational-semantic-drift"
)
V3_BENCH_23_CROSS_CULTURAL_MISTRANSLATION: Final[str] = (
    "v3-bench-23-cross-cultural-mistranslation"
)
V3_BENCH_24_NARRATIVE_AFTER_WITNESSES: Final[str] = (
    "v3-bench-24-narrative-after-witnesses"
)
V3_BENCH_25_PERSISTENT_ROLE: Final[str] = "v3-bench-25-persistent-role"
V3_BENCH_26_OFFICE_SUCCESSION: Final[str] = "v3-bench-26-office-succession"
V3_BENCH_27_INSTITUTIONAL_PERSISTENCE: Final[str] = (
    "v3-bench-27-institutional-persistence"
)
V3_BENCH_28_INSTITUTIONAL_DECAY: Final[str] = "v3-bench-28-institutional-decay"
V3_BENCH_29_FOUNDER_CONTINGENCY: Final[str] = "v3-bench-29-founder-contingency"
V3_BENCH_30_MULTIGENERATION_FORK: Final[str] = "v3-bench-30-multigeneration-fork"

V3_BENCHMARK_SCENARIO_IDS: Final[tuple[str, ...]] = (
    V3_BENCH_01_BLANK_SLATE,
    V3_BENCH_02_DEPENDENT_CARE,
    V3_BENCH_03_INTERGENERATIONAL_TEACHING,
    V3_BENCH_04_CULTURAL_MUTATION,
    V3_BENCH_05_MEMORY_LAYERS,
    V3_BENCH_06_RECORD_AFTER_WITNESSES,
    V3_BENCH_07_FALSE_RECORD,
    V3_BENCH_08_TECHNOLOGY_DISCOVERY,
    V3_BENCH_09_TECHNOLOGY_DIFFUSION,
    V3_BENCH_10_TECHNOLOGY_LOSS,
    V3_BENCH_11_TECHNOLOGY_REDISCOVERY,
    V3_BENCH_12_INHERITANCE_PRACTICES,
    V3_BENCH_13_LONG_TERM_COMMITMENTS,
    V3_BENCH_14_SUBJECTIVE_BARTER,
    V3_BENCH_15_CANDIDATE_EXCHANGE_MEDIUM,
    V3_BENCH_16_COLLECTIVE_PROJECT,
    V3_BENCH_17_PUBLIC_GOOD_PATTERNS,
    V3_BENCH_18_REGIONAL_MIGRATION,
    V3_BENCH_19_ISOLATED_DIVERGENCE,
    V3_BENCH_20_RECONTACT_EXCHANGE,
    V3_BENCH_21_VOCABULARY_DIVERGENCE,
    V3_BENCH_22_GENERATIONAL_SEMANTIC_DRIFT,
    V3_BENCH_23_CROSS_CULTURAL_MISTRANSLATION,
    V3_BENCH_24_NARRATIVE_AFTER_WITNESSES,
    V3_BENCH_25_PERSISTENT_ROLE,
    V3_BENCH_26_OFFICE_SUCCESSION,
    V3_BENCH_27_INSTITUTIONAL_PERSISTENCE,
    V3_BENCH_28_INSTITUTIONAL_DECAY,
    V3_BENCH_29_FOUNDER_CONTINGENCY,
    V3_BENCH_30_MULTIGENERATION_FORK,
)

RESEARCH_SEEDS: Final[tuple[int, ...]] = (11, 23, 37, 53, 71)
RESEARCH_HORIZON_TICKS: Final[int] = 192
SMOKE_SEED: Final[int] = 23
SMOKE_HORIZON_TICKS: Final[int] = 96

RESEARCH_SCHEDULE_ID: Final[str] = "v3-bench-research-v1"
FAST_COHORT_SCHEDULE_ID: Final[str] = "v3-bench-fast-cohort-v1"

_INDEPENDENT_LANES: Final[tuple[V3BenchmarkLane, ...]] = (
    V3BenchmarkLane.MECHANISM,
    V3BenchmarkLane.RESEARCH,
)

_NULL_RESULT_NOTE: Final[str] = (
    "Absence of the phenomenon in a complete window is a valid null result."
)


def _sel(selector_id: str) -> V3BenchmarkEvidenceSelector:
    return V3BenchmarkEvidenceSelector(selector_id=selector_id, selector_version=1)


def _recipe(
    *,
    arm_count: int = 1,
    treatment_scope: V3BenchmarkTreatmentScope = V3BenchmarkTreatmentScope.NONE,
    contrast_kind: V3BenchmarkContrastKind = V3BenchmarkContrastKind.NONE,
    schedule_id: str = RESEARCH_SCHEDULE_ID,
    schedule_notes: tuple[str, ...] = (),
) -> V3BenchmarkRecipe:
    return V3BenchmarkRecipe(
        profile=V3BenchmarkProfile.RESEARCH,
        schedule_id=schedule_id,
        schedule_version=1,
        horizon_ticks=RESEARCH_HORIZON_TICKS,
        seeds=RESEARCH_SEEDS,
        arm_count=arm_count,
        treatment_scope=treatment_scope,
        contrast_kind=contrast_kind,
        schedule_notes=schedule_notes,
    )


def _independent(
    *,
    request_number: int,
    scenario_id: str,
    title: str,
    required_specs: tuple[str, ...],
    required_modes: tuple[str, ...],
    selectors: tuple[str, ...],
    comparison_axis: str,
    non_goals: tuple[str, ...],
    capture_lanes: tuple[str, ...],
) -> V3BenchmarkSpec:
    return V3BenchmarkSpec(
        request_number=request_number,
        scenario_id=scenario_id,
        title=title,
        execution_kind=V3BenchmarkExecutionKind.INDEPENDENT,
        lanes=_INDEPENDENT_LANES,
        recipe=_recipe(),
        required_specs=required_specs,
        required_modes=required_modes,
        evidence_selectors=tuple(_sel(item) for item in selectors),
        comparison_axis=comparison_axis,
        non_goals=non_goals,
        required_capture_lanes=capture_lanes,
    )


def _grouped(
    *,
    request_number: int,
    scenario_id: str,
    title: str,
    required_specs: tuple[str, ...],
    required_modes: tuple[str, ...],
    selectors: tuple[str, ...],
    comparison_axis: str,
    non_goals: tuple[str, ...],
    capture_lanes: tuple[str, ...],
    schedule_id: str = RESEARCH_SCHEDULE_ID,
    schedule_notes: tuple[str, ...] = (),
) -> V3BenchmarkSpec:
    return V3BenchmarkSpec(
        request_number=request_number,
        scenario_id=scenario_id,
        title=title,
        execution_kind=V3BenchmarkExecutionKind.GROUPED,
        lanes=_INDEPENDENT_LANES,
        recipe=_recipe(
            arm_count=2,
            treatment_scope=V3BenchmarkTreatmentScope.RUN_OPPORTUNITY,
            contrast_kind=V3BenchmarkContrastKind.SINGLE_FACTOR,
            schedule_id=schedule_id,
            schedule_notes=schedule_notes,
        ),
        required_specs=required_specs,
        required_modes=required_modes,
        evidence_selectors=tuple(_sel(item) for item in selectors),
        comparison_axis=comparison_axis,
        non_goals=non_goals,
        required_capture_lanes=capture_lanes,
    )


def _build_registry() -> dict[str, V3BenchmarkSpec]:
    specs: tuple[V3BenchmarkSpec, ...] = (
        _independent(
            request_number=1,
            scenario_id=V3_BENCH_01_BLANK_SLATE,
            title="New agents enter a society without inherited memories",
            required_specs=("population_lifecycle", "new_agent_initialization"),
            required_modes=("generational_population",),
            selectors=(
                "new_agent_initialization_evidence",
                "population_lifecycle_evidence",
                "objective_event_journal",
            ),
            comparison_axis="descriptive_single_arm",
            non_goals=(
                _NULL_RESULT_NOTE,
                "Do not copy founder episodic, semantic or cultural state to entrants.",
            ),
            capture_lanes=("objective_journal", "cultural_evidence"),
        ),
        _independent(
            request_number=2,
            scenario_id=V3_BENCH_02_DEPENDENT_CARE,
            title="Dependent young agents require social care",
            required_specs=(
                "population_lifecycle",
                "new_agent_initialization",
                "dependency_care",
            ),
            required_modes=("generational_population",),
            selectors=(
                "dependency_care_evidence",
                "population_lifecycle_evidence",
            ),
            comparison_axis="descriptive_single_arm",
            non_goals=(
                _NULL_RESULT_NOTE,
                "Do not hard-code a parent as caregiver or mandate care success.",
            ),
            capture_lanes=("objective_journal",),
        ),
        _independent(
            request_number=3,
            scenario_id=V3_BENCH_03_INTERGENERATIONAL_TEACHING,
            title="Intergenerational skill transmission",
            required_specs=("mentorship", "developmental_learning"),
            required_modes=(
                "skill_learning_mode",
                "teaching_interaction_mode",
            ),
            selectors=("mentorship_evidence", "developmental_learning_evidence"),
            comparison_axis="descriptive_single_arm",
            non_goals=(
                _NULL_RESULT_NOTE,
                "Do not grant an entrant a skill without an actual learning channel.",
            ),
            capture_lanes=("objective_journal", "lineage_snapshot"),
        ),
        _independent(
            request_number=4,
            scenario_id=V3_BENCH_04_CULTURAL_MUTATION,
            title="Cultural knowledge mutates across generations",
            required_specs=("cultural_feature_provenance",),
            required_modes=("cultural_historical_memory",),
            selectors=("cultural_feature_evidence", "objective_event_journal"),
            comparison_axis="descriptive_single_arm",
            non_goals=(
                _NULL_RESULT_NOTE,
                "Do not force a mutation or recombination event.",
            ),
            capture_lanes=("objective_journal", "cultural_evidence"),
        ),
        _independent(
            request_number=5,
            scenario_id=V3_BENCH_05_MEMORY_LAYERS,
            title="Eyewitness memory becomes communicative then cultural memory",
            required_specs=("historical_memory_layers", "cultural_feature_provenance"),
            required_modes=("cultural_historical_memory",),
            selectors=(
                "historical_memory_evidence",
                "cultural_feature_evidence",
            ),
            comparison_axis="descriptive_single_arm",
            non_goals=(
                _NULL_RESULT_NOTE,
                "Do not expose analysis layer labels to agent cognition.",
            ),
            capture_lanes=("objective_journal", "cultural_evidence"),
        ),
        _independent(
            request_number=6,
            scenario_id=V3_BENCH_06_RECORD_AFTER_WITNESSES,
            title="A written record preserves information after all witnesses die",
            required_specs=("durable_records", "historical_memory_layers"),
            required_modes=(
                "cultural_historical_memory",
                "artifact_interpretation_mode",
            ),
            selectors=(
                "durable_record_evidence",
                "historical_memory_evidence",
            ),
            comparison_axis="descriptive_single_arm",
            non_goals=(
                _NULL_RESULT_NOTE,
                "Do not guarantee that any agent reads or understands the record.",
            ),
            capture_lanes=("objective_journal", "cultural_evidence"),
        ),
        _independent(
            request_number=7,
            scenario_id=V3_BENCH_07_FALSE_RECORD,
            title="A false written record preserves misinformation",
            required_specs=("durable_records", "historical_memory_layers"),
            required_modes=(
                "cultural_historical_memory",
                "artifact_interpretation_mode",
            ),
            selectors=(
                "durable_record_evidence",
                "historical_memory_evidence",
            ),
            comparison_axis="descriptive_single_arm",
            non_goals=(
                _NULL_RESULT_NOTE,
                "Do not leak an objective truth label into agent-visible state.",
            ),
            capture_lanes=("objective_journal", "cultural_evidence"),
        ),
        _independent(
            request_number=8,
            scenario_id=V3_BENCH_08_TECHNOLOGY_DISCOVERY,
            title="Technology discovery through experimentation and practice",
            required_specs=("knowledge_genealogy", "technique_lifecycle"),
            required_modes=("cultural_historical_memory",),
            selectors=(
                "knowledge_genealogy_evidence",
                "technique_lifecycle_evidence",
            ),
            comparison_axis="descriptive_single_arm",
            non_goals=(
                _NULL_RESULT_NOTE,
                "Do not install a global technique registry or a technology tree.",
            ),
            capture_lanes=("objective_journal", "lineage_snapshot"),
        ),
        _independent(
            request_number=9,
            scenario_id=V3_BENCH_09_TECHNOLOGY_DIFFUSION,
            title="Technology diffusion through valid learning channels",
            required_specs=("knowledge_genealogy", "mentorship"),
            required_modes=(
                "cultural_historical_memory",
                "teaching_interaction_mode",
            ),
            selectors=(
                "knowledge_genealogy_evidence",
                "mentorship_evidence",
            ),
            comparison_axis="descriptive_single_arm",
            non_goals=(
                _NULL_RESULT_NOTE,
                "Do not copy practical knowledge between owners without transmission.",
            ),
            capture_lanes=("objective_journal", "lineage_snapshot"),
        ),
        _independent(
            request_number=10,
            scenario_id=V3_BENCH_10_TECHNOLOGY_LOSS,
            title="Technology loss after all knowledge holders disappear",
            required_specs=("knowledge_genealogy", "knowledge_repositories"),
            required_modes=("cultural_historical_memory",),
            selectors=(
                "knowledge_genealogy_evidence",
                "technique_lifecycle_evidence",
            ),
            comparison_axis="descriptive_single_arm",
            non_goals=(
                _NULL_RESULT_NOTE,
                "Do not claim loss from censored or unavailable evidence.",
            ),
            capture_lanes=("objective_journal", "cultural_evidence"),
        ),
        _independent(
            request_number=11,
            scenario_id=V3_BENCH_11_TECHNOLOGY_REDISCOVERY,
            title="Independent technology rediscovery",
            required_specs=("knowledge_genealogy", "technique_lifecycle"),
            required_modes=("cultural_historical_memory",),
            selectors=(
                "technique_lifecycle_evidence",
                "knowledge_genealogy_evidence",
            ),
            comparison_axis="descriptive_single_arm",
            non_goals=(
                _NULL_RESULT_NOTE,
                "Do not treat rediscovery as a guaranteed post-loss outcome.",
            ),
            capture_lanes=("objective_journal", "lineage_snapshot"),
        ),
        _independent(
            request_number=12,
            scenario_id=V3_BENCH_12_INHERITANCE_PRACTICES,
            title="Emergent inheritance practices after a death",
            required_specs=("possession_succession",),
            required_modes=("generational_population",),
            selectors=("possession_succession_evidence", "objective_event_journal"),
            comparison_axis="descriptive_single_arm",
            non_goals=(
                _NULL_RESULT_NOTE,
                "Do not install an inheritance law or automatic transfer right.",
            ),
            capture_lanes=("objective_journal",),
        ),
        _independent(
            request_number=13,
            scenario_id=V3_BENCH_13_LONG_TERM_COMMITMENTS,
            title="Long-term promise and debt fulfillment or violation",
            required_specs=("structured_commitments",),
            required_modes=("generational_population",),
            selectors=("commitment_evidence", "objective_event_journal"),
            comparison_axis="descriptive_single_arm",
            non_goals=(
                _NULL_RESULT_NOTE,
                "Do not enforce debt collection or a binding obligation.",
            ),
            capture_lanes=("objective_journal",),
        ),
        _independent(
            request_number=14,
            scenario_id=V3_BENCH_14_SUBJECTIVE_BARTER,
            title="Negotiated barter with subjective valuations",
            required_specs=("subjective_exchange",),
            required_modes=("generational_population",),
            selectors=("subjective_exchange_evidence", "objective_event_journal"),
            comparison_axis="descriptive_single_arm",
            non_goals=(
                _NULL_RESULT_NOTE,
                "Do not expose one owner's reservation to another owner.",
            ),
            capture_lanes=("objective_journal",),
        ),
        _independent(
            request_number=15,
            scenario_id=V3_BENCH_15_CANDIDATE_EXCHANGE_MEDIUM,
            title="Candidate medium-of-exchange behavior without hard-coded money",
            required_specs=("resource_exchange_profile",),
            required_modes=("generational_population",),
            selectors=("exchange_function_evidence", "objective_event_journal"),
            comparison_axis="descriptive_single_arm",
            non_goals=(
                _NULL_RESULT_NOTE,
                "Do not declare money or a currency object.",
            ),
            capture_lanes=("objective_journal",),
        ),
        _independent(
            request_number=16,
            scenario_id=V3_BENCH_16_COLLECTIVE_PROJECT,
            title="Collective project coordination",
            required_specs=("collective_projects",),
            required_modes=("generational_population",),
            selectors=("collective_project_evidence", "objective_event_journal"),
            comparison_axis="descriptive_single_arm",
            non_goals=(
                _NULL_RESULT_NOTE,
                "Do not create a leader, quorum or binding resolution.",
            ),
            capture_lanes=("objective_journal",),
        ),
        _independent(
            request_number=17,
            scenario_id=V3_BENCH_17_PUBLIC_GOOD_PATTERNS,
            title="Public-good contribution and free-riding patterns",
            required_specs=("public_goods",),
            required_modes=("generational_population",),
            selectors=("public_goods_evidence", "objective_event_journal"),
            comparison_axis="descriptive_single_arm",
            non_goals=(
                _NULL_RESULT_NOTE,
                "Do not treat a benefit event as an access grant or moral role.",
            ),
            capture_lanes=("objective_journal",),
        ),
        _independent(
            request_number=18,
            scenario_id=V3_BENCH_18_REGIONAL_MIGRATION,
            title="Migration between regions through WorldEngine actions",
            required_specs=("regions_migration",),
            required_modes=("multi_polity_migration",),
            selectors=("migration_evidence", "objective_event_journal"),
            comparison_axis="descriptive_single_arm",
            non_goals=(
                _NULL_RESULT_NOTE,
                "Do not teleport agents or create borders/citizenship.",
            ),
            capture_lanes=("objective_journal",),
        ),
        _independent(
            request_number=19,
            scenario_id=V3_BENCH_19_ISOLATED_DIVERGENCE,
            title="Two isolated populations develop different cultural patterns",
            required_specs=("regions_migration", "cultural_contact"),
            required_modes=("multi_polity_migration",),
            selectors=(
                "migration_evidence",
                "cultural_contact_evidence",
                "cultural_feature_evidence",
            ),
            comparison_axis="descriptive_single_arm",
            non_goals=(
                _NULL_RESULT_NOTE,
                "Do not force divergence or install a global culture label.",
            ),
            capture_lanes=("objective_journal", "cultural_evidence"),
        ),
        _independent(
            request_number=20,
            scenario_id=V3_BENCH_20_RECONTACT_EXCHANGE,
            title="Re-contact and knowledge or cultural exchange",
            required_specs=("cultural_contact", "knowledge_genealogy"),
            required_modes=("multi_polity_migration",),
            selectors=(
                "cultural_contact_evidence",
                "knowledge_genealogy_evidence",
            ),
            comparison_axis="descriptive_single_arm",
            non_goals=(
                _NULL_RESULT_NOTE,
                "Do not synchronize knowledge merely because groups meet.",
            ),
            capture_lanes=("objective_journal", "cultural_evidence"),
        ),
        _independent(
            request_number=21,
            scenario_id=V3_BENCH_21_VOCABULARY_DIVERGENCE,
            title="Symbolic vocabulary divergence",
            required_specs=(
                "symbolic_language_mode",
                "translation_mode",
                "cultural_feature_provenance",
            ),
            required_modes=("symbolic_language_mode",),
            selectors=(
                "symbolic_language_evidence",
                "cultural_feature_evidence",
            ),
            comparison_axis="descriptive_single_arm",
            non_goals=(
                _NULL_RESULT_NOTE,
                "Do not create a world dictionary or shared vocabulary.",
            ),
            capture_lanes=(
                "objective_journal",
                "cultural_evidence",
                "lineage_snapshot",
            ),
        ),
        _independent(
            request_number=22,
            scenario_id=V3_BENCH_22_GENERATIONAL_SEMANTIC_DRIFT,
            title="Semantic drift across generations",
            required_specs=("symbolic_language_mode", "translation_mode"),
            required_modes=("symbolic_language_mode",),
            selectors=(
                "semantic_drift_evidence",
                "symbolic_language_evidence",
            ),
            comparison_axis="descriptive_single_arm",
            non_goals=(
                _NULL_RESULT_NOTE,
                "Do not assert that drift must occur in a complete window.",
            ),
            capture_lanes=(
                "objective_journal",
                "cultural_evidence",
                "lineage_snapshot",
            ),
        ),
        _independent(
            request_number=23,
            scenario_id=V3_BENCH_23_CROSS_CULTURAL_MISTRANSLATION,
            title="Cross-cultural mistranslation",
            required_specs=("translation_mode", "symbolic_language_mode"),
            required_modes=("translation_mode",),
            selectors=(
                "translation_evidence",
                "semantic_drift_evidence",
            ),
            comparison_axis="descriptive_single_arm",
            non_goals=(
                _NULL_RESULT_NOTE,
                "Do not guarantee mistranslation or shared meaning.",
            ),
            capture_lanes=("objective_journal", "cultural_evidence"),
        ),
        _independent(
            request_number=24,
            scenario_id=V3_BENCH_24_NARRATIVE_AFTER_WITNESSES,
            title="Historical narrative survives after eyewitness extinction",
            required_specs=(
                "population_lifecycle",
                "generational_narratives",
                "cultural_feature_provenance",
            ),
            required_modes=(
                "cultural_narrative_mode",
                "cultural_historical_memory",
            ),
            selectors=("generational_narrative_evidence",),
            comparison_axis="descriptive_single_arm",
            non_goals=(
                _NULL_RESULT_NOTE,
                "Do not add a narrative truth field or script a myth.",
            ),
            capture_lanes=("objective_journal", "cultural_evidence"),
        ),
        _independent(
            request_number=25,
            scenario_id=V3_BENCH_25_PERSISTENT_ROLE,
            title="Emergence of a persistent social role",
            required_specs=(
                "population_lifecycle",
                "new_agent_initialization",
                "institution_concept_mode",
            ),
            required_modes=("institution_concept_mode",),
            selectors=(
                "institution_concept_evidence",
                "objective_event_journal",
            ),
            comparison_axis="descriptive_single_arm",
            non_goals=(
                _NULL_RESULT_NOTE,
                "Do not create an objective office or institution type.",
            ),
            capture_lanes=("objective_journal", "lineage_snapshot"),
        ),
        _independent(
            request_number=26,
            scenario_id=V3_BENCH_26_OFFICE_SUCCESSION,
            title="Succession of an office after its occupant dies",
            required_specs=(
                "population_lifecycle",
                "new_agent_initialization",
                "office_succession_mode",
                "institution_concept_mode",
                "institutional_memory_mode",
            ),
            required_modes=(
                "office_succession_mode",
                "institutional_memory_mode",
            ),
            selectors=(
                "office_succession_evidence",
                "institutional_memory_evidence",
            ),
            comparison_axis="descriptive_single_arm",
            non_goals=(
                _NULL_RESULT_NOTE,
                "Do not install a global current-occupant registry.",
            ),
            capture_lanes=("objective_journal", "lineage_snapshot"),
        ),
        _independent(
            request_number=27,
            scenario_id=V3_BENCH_27_INSTITUTIONAL_PERSISTENCE,
            title="Institutional persistence across generations",
            required_specs=(
                "population_lifecycle",
                "new_agent_initialization",
                "office_succession_mode",
                "institution_concept_mode",
                "institutional_memory_mode",
            ),
            required_modes=(
                "office_succession_mode",
                "institutional_memory_mode",
            ),
            selectors=(
                "institution_concept_evidence",
                "institutional_memory_evidence",
            ),
            comparison_axis="descriptive_single_arm",
            non_goals=(
                _NULL_RESULT_NOTE,
                "Do not mandate institutional survival across generations.",
            ),
            capture_lanes=("objective_journal", "lineage_snapshot"),
        ),
        _independent(
            request_number=28,
            scenario_id=V3_BENCH_28_INSTITUTIONAL_DECAY,
            title="Institutional decay or disappearance",
            required_specs=(
                "population_lifecycle",
                "new_agent_initialization",
                "institutional_decay_mode",
                "institution_concept_mode",
                "office_succession_mode",
            ),
            required_modes=("institutional_decay_mode",),
            selectors=(
                "institutional_decay_evidence",
                "institution_concept_evidence",
            ),
            comparison_axis="descriptive_single_arm",
            non_goals=(
                _NULL_RESULT_NOTE,
                "Do not claim collapse from missing or censored evidence.",
            ),
            capture_lanes=("objective_journal", "lineage_snapshot"),
        ),
        _grouped(
            request_number=29,
            scenario_id=V3_BENCH_29_FOUNDER_CONTINGENCY,
            title="A small founder-event intervention creates divergent histories",
            required_specs=("generational_run", "cultural_feature_provenance"),
            required_modes=("generational_population",),
            selectors=(
                "path_dependence_outcome_evidence",
                "objective_event_journal",
            ),
            comparison_axis="founder_opportunity_vs_noop_twin",
            non_goals=(
                _NULL_RESULT_NOTE,
                "Do not claim single-run causality from one seed.",
                "Do not rewrite the sealed parent prefix.",
            ),
            capture_lanes=(
                "objective_journal",
                "path_dependence_artifacts",
                "cultural_evidence",
            ),
        ),
        _grouped(
            request_number=30,
            scenario_id=V3_BENCH_30_MULTIGENERATION_FORK,
            title="Multi-generation forked replay experiment",
            required_specs=("generational_run", "cultural_feature_provenance"),
            required_modes=("generational_population",),
            selectors=(
                "path_dependence_outcome_evidence",
                "objective_event_journal",
            ),
            comparison_axis="sealed_prefix_fork_vs_noop_twin",
            non_goals=(
                _NULL_RESULT_NOTE,
                "Do not promise durable subjective restart or recorded-LLM forks.",
            ),
            capture_lanes=(
                "objective_journal",
                "path_dependence_artifacts",
                "cultural_evidence",
            ),
            schedule_id=FAST_COHORT_SCHEDULE_ID,
            schedule_notes=(
                "cohort interval 2 ticks",
                "generation length 4 ticks",
                "sealed prefix 12 ticks",
            ),
        ),
    )
    registry: dict[str, V3BenchmarkSpec] = {}
    for spec in specs:
        if spec.scenario_id in registry:
            raise V3BenchmarkError(
                "duplicate_scenario_id",
                f"duplicate scenario_id={spec.scenario_id}",
            )
        registry[spec.scenario_id] = spec
    if len(registry) != V3_BENCHMARK_SCENARIO_COUNT:
        raise V3BenchmarkError(
            "scenario_count_mismatch",
            f"expected {V3_BENCHMARK_SCENARIO_COUNT} scenarios, got {len(registry)}",
        )
    missing = [item for item in V3_BENCHMARK_SCENARIO_IDS if item not in registry]
    if missing:
        raise V3BenchmarkError(
            "missing_scenario_ids", f"missing scenario_ids={','.join(missing)}"
        )
    extra = [item for item in registry if item not in V3_BENCHMARK_SCENARIO_IDS]
    if extra:
        raise V3BenchmarkError(
            "unexpected_scenario_ids",
            f"unexpected scenario_ids={','.join(sorted(extra))}",
        )
    requests = tuple(spec.request_number for spec in specs)
    if requests != tuple(range(1, V3_BENCHMARK_SCENARIO_COUNT + 1)):
        raise V3BenchmarkError(
            "request_coverage_mismatch",
            "scenario request numbers must be the ordered 1..30 sequence",
        )
    _LOG.info(
        "v3_benchmark_suite_registered suite_id=%s scenario_count=%s version=%s",
        V3_BENCHMARK_SUITE_ID,
        V3_BENCHMARK_SCENARIO_COUNT,
        V3_BENCHMARK_SUITE_VERSION,
    )
    return registry


_REGISTRY: Final[dict[str, V3BenchmarkSpec]] = _build_registry()


def registered_v3_benchmark_scenario_ids() -> tuple[str, ...]:
    """Return the locked ordered V3 benchmark scenario ids."""
    return V3_BENCHMARK_SCENARIO_IDS


def list_v3_benchmark_scenarios() -> tuple[V3BenchmarkSpec, ...]:
    """Return all registered specs in locked request order."""
    return tuple(_REGISTRY[item] for item in V3_BENCHMARK_SCENARIO_IDS)


def get_v3_benchmark_scenario(scenario_id: str) -> V3BenchmarkSpec:
    """Return one registered spec or raise a fail-closed benchmark error."""
    if type(scenario_id) is not str:
        raise V3BenchmarkError("unknown_scenario", "scenario_id must be a str")
    try:
        object_id = require_stable_id("scenario_id", scenario_id)
    except ValueError as exc:
        raise V3BenchmarkError("unknown_scenario", str(exc)) from exc
    if not object_id.startswith(V3_BENCHMARK_ID_PREFIX):
        raise V3BenchmarkError("unknown_scenario", f"unknown scenario_id={object_id}")
    try:
        return _REGISTRY[object_id]
    except KeyError as exc:
        _LOG.error(
            "v3_benchmark_unknown_scenario scenario_id=%s reason_code=unknown_scenario",
            object_id,
        )
        raise V3BenchmarkError(
            "unknown_scenario", f"unknown scenario_id={object_id}"
        ) from exc


def v3_benchmark_suite_registry() -> Mapping[str, V3BenchmarkSpec]:
    """Read-only view of the V3 benchmark registry."""
    return _REGISTRY


def v3_benchmark_scenario_id_for_request(request_number: int) -> str:
    """Resolve a 1-based request number to its locked scenario id."""
    if type(request_number) is not int or isinstance(request_number, bool):
        raise V3BenchmarkError("invalid_request_number", "request_number must be int")
    if request_number < 1 or request_number > V3_BENCHMARK_SCENARIO_COUNT:
        raise V3BenchmarkError("invalid_request_number", "request_number out of range")
    return V3_BENCHMARK_SCENARIO_IDS[request_number - 1]


__all__ = [
    "FAST_COHORT_SCHEDULE_ID",
    "RESEARCH_HORIZON_TICKS",
    "RESEARCH_SCHEDULE_ID",
    "RESEARCH_SEEDS",
    "SMOKE_HORIZON_TICKS",
    "SMOKE_SEED",
    "V3_BENCHMARK_SCENARIO_IDS",
    "get_v3_benchmark_scenario",
    "list_v3_benchmark_scenarios",
    "registered_v3_benchmark_scenario_ids",
    "v3_benchmark_scenario_id_for_request",
    "v3_benchmark_suite_registry",
]
