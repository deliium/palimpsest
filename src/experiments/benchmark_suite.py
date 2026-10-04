"""V2 benchmark suite scenario registry and immutable contracts.

Composition-only: specs reference existing catalog condition ids and modes.
Builders live under ``experiments.benchmark_scenarios`` (Task 2+). This module
does **not** parse English invariant phrases at runtime — mandate-language
deny-lists belong in unit tests only.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from experiments.architectures import registered_architecture_ids
from world.identifiers import require_stable_id

_LOG: Final[logging.Logger] = logging.getLogger("experiments.benchmark_suite")

BENCHMARK_SUITE_ID: Final[str] = "v2-benchmark-suite"
BENCHMARK_SCENARIO_COUNT: Final[int] = 16

BENCH_01_SEASONAL_PLANNING: Final[str] = "bench-01-seasonal-planning"
BENCH_02_MEMORY_INTERFERENCE: Final[str] = "bench-02-memory-interference"
BENCH_03_REFLECTION_REVISION: Final[str] = "bench-03-reflection-revision"
BENCH_04_TOM_SOCIAL_FAILURE: Final[str] = "bench-04-tom-social-failure"
BENCH_05_TOM_COOPERATION: Final[str] = "bench-05-tom-cooperation"
BENCH_06_DECEPTION_REPUTATION: Final[str] = "bench-06-deception-reputation"
BENCH_07_SKILL_SPECIALIZATION: Final[str] = "bench-07-skill-specialization"
BENCH_08_TERRITORIAL: Final[str] = "bench-08-territorial"
BENCH_09_SOCIAL_CLUSTERS: Final[str] = "bench-09-social-clusters"
BENCH_10_NORMS: Final[str] = "bench-10-norms"
BENCH_11_CONVENTIONS: Final[str] = "bench-11-conventions"
BENCH_12_ARTIFACTS: Final[str] = "bench-12-artifacts"
BENCH_13_NAMING_DRIFT: Final[str] = "bench-13-naming-drift"
BENCH_14_RUMOR_NARRATIVE: Final[str] = "bench-14-rumor-narrative"
BENCH_15_ARCHITECTURE_MATRIX: Final[str] = "bench-15-architecture-matrix"
BENCH_16_FORKED_INTERVENTION: Final[str] = "bench-16-forked-intervention"

BENCHMARK_SCENARIO_IDS: Final[tuple[str, ...]] = (
    BENCH_01_SEASONAL_PLANNING,
    BENCH_02_MEMORY_INTERFERENCE,
    BENCH_03_REFLECTION_REVISION,
    BENCH_04_TOM_SOCIAL_FAILURE,
    BENCH_05_TOM_COOPERATION,
    BENCH_06_DECEPTION_REPUTATION,
    BENCH_07_SKILL_SPECIALIZATION,
    BENCH_08_TERRITORIAL,
    BENCH_09_SOCIAL_CLUSTERS,
    BENCH_10_NORMS,
    BENCH_11_CONVENTIONS,
    BENCH_12_ARTIFACTS,
    BENCH_13_NAMING_DRIFT,
    BENCH_14_RUMOR_NARRATIVE,
    BENCH_15_ARCHITECTURE_MATRIX,
    BENCH_16_FORKED_INTERVENTION,
)


class BenchmarkSpecError(ValueError):
    """Fail-closed structural validation for benchmark scenario specs."""

    def __init__(self, code: str, message: str = "") -> None:
        self.code = code
        detail = message or code
        super().__init__(detail)
        _LOG.error("benchmark_spec_invalid reason_code=%s", code)


@dataclass(frozen=True, slots=True)
class BenchmarkConfiguration:
    """Locked condition refs and required mode tokens for one scenario."""

    condition_ids: tuple[str, ...]
    required_modes: tuple[str, ...] = ()
    composition_notes: str = ""

    def __post_init__(self) -> None:
        if isinstance(self.condition_ids, (set, frozenset)):
            raise BenchmarkSpecError(
                "unordered_condition_ids", "condition_ids must be ordered"
            )
        if isinstance(self.condition_ids, (str, bytes)) or not isinstance(
            self.condition_ids, Sequence
        ):
            raise BenchmarkSpecError(
                "invalid_condition_ids", "condition_ids must be a sequence"
            )
        ids = tuple(self.condition_ids)
        if not ids:
            raise BenchmarkSpecError(
                "empty_condition_ids", "condition_ids must be non-empty"
            )
        seen: set[str] = set()
        for item in ids:
            require_stable_id("condition_id", item)
            if item in seen:
                raise BenchmarkSpecError(
                    "duplicate_condition_id",
                    f"duplicate condition_id={item}",
                )
            seen.add(item)
        object.__setattr__(self, "condition_ids", ids)
        if isinstance(self.required_modes, (set, frozenset)):
            raise BenchmarkSpecError(
                "unordered_required_modes", "required_modes must be ordered"
            )
        if isinstance(self.required_modes, (str, bytes)) or not isinstance(
            self.required_modes, Sequence
        ):
            raise BenchmarkSpecError(
                "invalid_required_modes", "required_modes must be a sequence"
            )
        modes = tuple(self.required_modes)
        for mode in modes:
            if type(mode) is not str or not mode:
                raise BenchmarkSpecError(
                    "invalid_required_mode", "required_modes entries must be non-empty str"
                )
        object.__setattr__(self, "required_modes", modes)
        if type(self.composition_notes) is not str:
            raise BenchmarkSpecError(
                "invalid_composition_notes", "composition_notes must be str"
            )


@dataclass(frozen=True, slots=True)
class BenchmarkScenarioSpec:
    """Mandatory per-scenario contract for the V2 benchmark suite."""

    scenario_id: str
    title: str
    configuration: BenchmarkConfiguration
    seed_strategy: str
    expected_invariants: tuple[str, ...]
    measurable_outputs: tuple[str, ...]
    non_goals: tuple[str, ...]
    statistical_comparison: str
    max_ticks: int
    off_v1_gate: bool = True

    def __post_init__(self) -> None:
        require_stable_id("scenario_id", self.scenario_id)
        if type(self.title) is not str or not self.title.strip():
            raise BenchmarkSpecError("invalid_title", "title must be non-empty str")
        if type(self.configuration) is not BenchmarkConfiguration:
            raise BenchmarkSpecError(
                "invalid_configuration",
                "configuration must be BenchmarkConfiguration",
            )
        if type(self.seed_strategy) is not str or not self.seed_strategy.strip():
            raise BenchmarkSpecError(
                "invalid_seed_strategy", "seed_strategy must be non-empty str"
            )
        object.__setattr__(
            self, "expected_invariants", _require_str_tuple("expected_invariants", self.expected_invariants)
        )
        object.__setattr__(
            self,
            "measurable_outputs",
            _require_str_tuple("measurable_outputs", self.measurable_outputs),
        )
        object.__setattr__(
            self, "non_goals", _require_str_tuple("non_goals", self.non_goals)
        )
        if type(self.statistical_comparison) is not str or not self.statistical_comparison.strip():
            raise BenchmarkSpecError(
                "invalid_statistical_comparison",
                "statistical_comparison must be non-empty str",
            )
        if type(self.max_ticks) is not int or isinstance(self.max_ticks, bool):
            raise BenchmarkSpecError("invalid_max_ticks", "max_ticks must be int")
        if self.max_ticks < 1:
            raise BenchmarkSpecError("invalid_max_ticks", "max_ticks must be >= 1")
        if self.off_v1_gate is not True:
            raise BenchmarkSpecError(
                "off_v1_gate_required",
                "benchmark scenarios must set off_v1_gate=True",
            )


def _require_str_tuple(name: str, value: object) -> tuple[str, ...]:
    if isinstance(value, (set, frozenset)):
        raise BenchmarkSpecError(f"unordered_{name}", f"{name} must be ordered")
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise BenchmarkSpecError(f"invalid_{name}", f"{name} must be a sequence")
    items = tuple(value)
    if not items:
        raise BenchmarkSpecError(f"empty_{name}", f"{name} must be non-empty")
    for item in items:
        if type(item) is not str or not item.strip():
            raise BenchmarkSpecError(
                f"invalid_{name}_entry",
                f"{name} entries must be non-empty str",
            )
    return items


def _spec(
    *,
    scenario_id: str,
    title: str,
    condition_ids: tuple[str, ...],
    required_modes: tuple[str, ...] = (),
    composition_notes: str = "",
    seed_strategy: str,
    expected_invariants: tuple[str, ...],
    measurable_outputs: tuple[str, ...],
    non_goals: tuple[str, ...],
    statistical_comparison: str,
    max_ticks: int,
) -> BenchmarkScenarioSpec:
    _LOG.debug(
        "benchmark_spec_load scenario_id=%s condition_count=%s max_ticks=%s",
        scenario_id,
        len(condition_ids),
        max_ticks,
    )
    return BenchmarkScenarioSpec(
        scenario_id=scenario_id,
        title=title,
        configuration=BenchmarkConfiguration(
            condition_ids=condition_ids,
            required_modes=required_modes,
            composition_notes=composition_notes,
        ),
        seed_strategy=seed_strategy,
        expected_invariants=expected_invariants,
        measurable_outputs=measurable_outputs,
        non_goals=non_goals,
        statistical_comparison=statistical_comparison,
        max_ticks=max_ticks,
        off_v1_gate=True,
    )


def _build_registry() -> dict[str, BenchmarkScenarioSpec]:
    specs = (
        _spec(
            scenario_id=BENCH_01_SEASONAL_PLANNING,
            title="Long-term planning under seasonal scarcity",
            condition_ids=("u-learned", "u-naive"),
            required_modes=("EnvironmentalDynamicsSpec", "initial_goals LONG_TERM"),
            composition_notes="Experiment U; predictive world model vs naive",
            seed_strategy="matrix: multi-seed; shared scenario + stochastic identity across arms",
            expected_invariants=(
                "When Experiment U arms run, environmental_dynamics@1 and goal_completion@1 are assemblable.",
                "LONG_TERM initial_goals remain on both u-learned and u-naive without a second goal system.",
                "Capability flags stay opt-in; suite does not enable multi_hop_testimony_tracking.",
            ),
            measurable_outputs=(
                "goal lifecycle counts",
                "harvest/stockpile actions by season",
                "environmental_dynamics@1",
                "goal_completion@1",
            ),
            non_goals=(
                "Do not assert that agents always stockpile before winter.",
                "Do not invent a second goal system beyond Experiment U initial_goals.",
            ),
            statistical_comparison="multi-seed matrix; planning-ahead action-rate distribution",
            max_ticks=64,
        ),
        _spec(
            scenario_id=BENCH_02_MEMORY_INTERFERENCE,
            title="Memory interference changing behavior",
            condition_ids=("a-reconstructive-v2", "a-reconstructive"),
            required_modes=("MemoryMode.RECONSTRUCTIVE_V2", "MemoryMode.RECONSTRUCTIVE"),
            composition_notes="Experiment A reconstructive-V2 vs reconstructive; shared seed",
            seed_strategy="paired: shared seed; identical scenario and stochastic identity",
            expected_invariants=(
                "When reconstructive-V2 is enabled, memory_dynamics@1 interference/source-confusion fields are assemblable.",
                "Paired arms share seed and scenario fingerprint.",
            ),
            measurable_outputs=(
                "memory_dynamics@1 interference/source-confusion",
                "action-class delta",
            ),
            non_goals=(
                "Do not assert interference must change every seed's actions.",
            ),
            statistical_comparison="paired arms same seed",
            max_ticks=64,
        ),
        _spec(
            scenario_id=BENCH_03_REFLECTION_REVISION,
            title="Reflection revising a false belief",
            condition_ids=("g-deterministic", "g-disabled"),
            required_modes=("ReflectionMode.DETERMINISTIC", "ReflectionMode.DISABLED"),
            composition_notes="Experiment G; planted false belief uses analysis truth only",
            seed_strategy="paired: on/off reflection; shared seed",
            expected_invariants=(
                "When ReflectionMode=DETERMINISTIC, reflection audits are emitted and belief revision events are countable in analysis.",
                "Planted false belief is analysis-truth only — never agent-visible is_false.",
            ),
            measurable_outputs=(
                "reflection audits",
                "belief revision events",
                "confidence-band change (analysis truth only)",
            ),
            non_goals=(
                "Do not assert every seed revises the planted belief.",
                "Do not expose is_false to agent-visible observation.",
            ),
            statistical_comparison="on/off reflection; revision rate after contradictory evidence",
            max_ticks=64,
        ),
        _spec(
            scenario_id=BENCH_04_TOM_SOCIAL_FAILURE,
            title="Incorrect ToM measurable social failure when mismatch occurs",
            condition_ids=("l-enabled", "l-disabled"),
            required_modes=("advanced_social_inference",),
            composition_notes="Experiment L (+ optional M ledger); shared seed with bench-05; not a new wrong/corrected catalog arm",
            seed_strategy="matrix: multi-seed shared with bench-05; same world/seed matrix",
            expected_invariants=(
                "When advanced_social_inference is on, theory_of_mind@1 mismatch indicators are assemblable.",
                "Failed cooperation/ask rates are reported when present — absence is a valid outcome.",
            ),
            measurable_outputs=(
                "theory_of_mind@1 mismatch indicators",
                "failed cooperation/ask rates when present",
            ),
            non_goals=(
                "Do not assert social failure on every seed.",
                "Do not add wrong-vs-corrected Experiment L catalog arms.",
            ),
            statistical_comparison="multi-seed support/detectability — never failure-must-occur",
            max_ticks=64,
        ),
        _spec(
            scenario_id=BENCH_05_TOM_COOPERATION,
            title="Successful cooperation using ToM when hypotheses help",
            condition_ids=("l-enabled", "l-disabled"),
            required_modes=("advanced_social_inference",),
            composition_notes="Experiment L; same world/seed matrix as bench-04",
            seed_strategy="matrix: multi-seed shared with bench-04; same world/seed matrix",
            expected_invariants=(
                "When advanced_social_inference is on, cooperation@1 is assemblable.",
                "Handoff success and ToM support for partner goal are reported when present.",
            ),
            measurable_outputs=(
                "cooperation@1",
                "handoff success when present",
                "ToM support for partner goal",
            ),
            non_goals=(
                "Do not assert cooperation on every seed.",
                "Do not add wrong-vs-corrected Experiment L catalog arms.",
            ),
            statistical_comparison="multi-seed success-rate CI; no mandated cooperation",
            max_ticks=64,
        ),
        _spec(
            scenario_id=BENCH_06_DECEPTION_REPUTATION,
            title="Strategic deception and reputation consequences",
            condition_ids=("o-strategy-reputation", "q-disabled", "o-strategy-only"),
            required_modes=(
                "CommunicationStrategyMode.DETERMINISTIC",
                "ReputationMode.DETERMINISTIC",
            ),
            composition_notes=(
                "Custom shared-seed arm on runner-config-v10 with strategy+reputation; "
                "q-disabled / strategy-only controls as needed"
            ),
            seed_strategy="matrix: multi-seed; shared scenario + stochastic identity",
            expected_invariants=(
                "When CommunicationStrategyMode and ReputationMode are DETERMINISTIC, "
                "communication_strategy@1 and distributed_reputation@1 are assemblable.",
                "o-enabled alone is not treated as carrying reputation.",
            ),
            measurable_outputs=(
                "communication_strategy@1 categories",
                "distributed_reputation@1 divergence",
            ),
            non_goals=(
                "Do not invent a second LLM recording stack.",
                "Do not log utterance text.",
            ),
            statistical_comparison="multi-seed; reputation shift after observed deception vs control",
            max_ticks=64,
        ),
        _spec(
            scenario_id=BENCH_07_SKILL_SPECIALIZATION,
            title="Skill learning and specialization",
            condition_ids=("r-enabled", "t-enabled", "r-disabled", "t-disabled"),
            required_modes=(
                "SkillLearningMode.DETERMINISTIC",
                "TeachingInteractionMode.DETERMINISTIC",
            ),
            composition_notes="Experiments R + T vs disabled peers",
            seed_strategy="paired/matrix: shared-seed specialization vs uniform",
            expected_invariants=(
                "When skill/teaching modes are DETERMINISTIC, skill_learning@1 and "
                "behavioral_specialization@1 are assemblable.",
            ),
            measurable_outputs=(
                "skill_learning@1",
                "behavioral_specialization@1",
                "craft success rates",
            ),
            non_goals=(
                "Do not assert every agent specializes on every seed.",
            ),
            statistical_comparison="shared-seed specialization vs uniform",
            max_ticks=64,
        ),
        _spec(
            scenario_id=BENCH_08_TERRITORIAL,
            title="Emergent territorial behavior",
            condition_ids=("v-scarce", "v-abundant"),
            required_modes=("TerritorialClaimMode.DETERMINISTIC",),
            composition_notes="Experiment V paired-world contract",
            seed_strategy="paired: existing V scarce vs abundant world contract",
            expected_invariants=(
                "When TerritorialClaimMode=DETERMINISTIC, claim ledger updates are owner-scoped "
                "and analysis spatial_control@1 is assemblable.",
            ),
            measurable_outputs=(
                "claim ledger activity",
                "spatial_control@1",
                "territorial_concentration@1",
            ),
            non_goals=(
                "Do not require territorial claims on every seed.",
            ),
            statistical_comparison="existing V paired-world contract",
            max_ticks=64,
        ),
        _spec(
            scenario_id=BENCH_09_SOCIAL_CLUSTERS,
            title="Formation and dissolution of social clusters",
            condition_ids=("w-enabled", "w-disabled"),
            required_modes=("GroupFormationMode.DETERMINISTIC",),
            composition_notes="Experiment W; measure churn when present; no scripted shock",
            seed_strategy="matrix: multi-seed support_band distribution",
            expected_invariants=(
                "When GroupFormationMode=DETERMINISTIC, group ledger churn metrics and "
                "support_band machinery run without boolean group-formed labels.",
                "Membership decay/retire churn is reported when present.",
            ),
            measurable_outputs=(
                "group ledger churn",
                "modularity/persistence when present",
                "decay/retire churn when present",
            ),
            non_goals=(
                "Do not invent a scripted world shock to force dissolution.",
                "Do not require boolean group-formation outcomes.",
            ),
            statistical_comparison="multi-seed support_band distribution — never boolean group formed",
            max_ticks=64,
        ),
        _spec(
            scenario_id=BENCH_10_NORMS,
            title="Norm formation and violation",
            condition_ids=("x-enabled", "x-disabled"),
            required_modes=("SocialNormMode.DETERMINISTIC",),
            composition_notes="Experiment X on/off",
            seed_strategy="paired: on/off mode; shared seed",
            expected_invariants=(
                "When SocialNormMode=DETERMINISTIC, norm ledger entries and violation "
                "observations are countable; sanction/talk responses reported when ledger non-empty.",
            ),
            measurable_outputs=(
                "norm ledger entries",
                "violation observations",
                "sanction/talk responses when ledger non-empty",
            ),
            non_goals=(
                "Do not require norm ledger entries on every seed.",
            ),
            statistical_comparison="on/off mode; response rate conditional on ledger",
            max_ticks=64,
        ),
        _spec(
            scenario_id=BENCH_11_CONVENTIONS,
            title="Persistent convention/tradition",
            condition_ids=("y-enabled", "y-disabled"),
            required_modes=("SocialConventionMode.DETERMINISTIC",),
            composition_notes="Experiment Y on/off",
            seed_strategy="matrix: multi-seed persistence distribution",
            expected_invariants=(
                "When SocialConventionMode=DETERMINISTIC, persistent_social_conventions@1 is assemblable.",
            ),
            measurable_outputs=(
                "persistent_social_conventions@1",
                "situation→action regularity",
            ),
            non_goals=(
                "Do not assert a tradition must persist on every seed.",
            ),
            statistical_comparison="multi-seed persistence distribution",
            max_ticks=64,
        ),
        _spec(
            scenario_id=BENCH_12_ARTIFACTS,
            title="External artifacts preserving information",
            condition_ids=("artifact_channel", "memory_only"),
            required_modes=("ArtifactInterpretationMode.DETERMINISTIC",),
            composition_notes="Experiment Z present vs absent artifact channel",
            seed_strategy="paired: present vs absent arms; shared seed",
            expected_invariants=(
                "When artifact channel is active, external_artifact_memory@1 is assemblable.",
                "Later use after author absence/death is reported when a terminal event occurs.",
            ),
            measurable_outputs=(
                "external_artifact_memory@1",
                "later use after author absence/death when terminal occurs",
            ),
            non_goals=(
                "Do not assert every seed produces post-death artifact reuse.",
            ),
            statistical_comparison="present vs absent arms",
            max_ticks=64,
        ),
        _spec(
            scenario_id=BENCH_13_NAMING_DRIFT,
            title="Vocabulary/naming drift",
            condition_ids=("aa-enabled", "aa-disabled"),
            required_modes=("SemanticNamingMode.DETERMINISTIC",),
            composition_notes="Experiment AA on/off",
            seed_strategy="matrix: multi-seed drift vs convergence indicators",
            expected_invariants=(
                "When SemanticNamingMode=DETERMINISTIC, emergent_semantic_naming@1 is assemblable.",
            ),
            measurable_outputs=(
                "emergent_semantic_naming@1",
                "invent/adopt/compete/forget counts",
            ),
            non_goals=(
                "Do not assert naming drift must occur on every seed.",
            ),
            statistical_comparison="multi-seed drift vs convergence indicators",
            max_ticks=64,
        ),
        _spec(
            scenario_id=BENCH_14_RUMOR_NARRATIVE,
            title="Rumor to persistent inaccurate narrative",
            condition_ids=("ab-enabled", "ab-disabled"),
            required_modes=("CulturalNarrativeMode.DETERMINISTIC",),
            composition_notes="Experiment AB (+ E/P stimulus patterns only as needed)",
            seed_strategy="matrix: multi-seed support when inaccurate persistent variant occurs",
            expected_invariants=(
                "When CulturalNarrativeMode=DETERMINISTIC, cultural_narrative_lineage@1 and "
                "rumor_distortion@1 are assemblable.",
                "If narrative lineage rows exist, cultural_narrative_lineage@1 reports "
                "support_band that is not a coding error or ABSENT for wrong reasons.",
            ),
            measurable_outputs=(
                "cultural_narrative_lineage@1",
                "rumor_distortion@1",
                "uplift gates",
            ),
            non_goals=(
                "Do not script a myth.",
                "Do not assert an inaccurate narrative must persist on every seed.",
            ),
            statistical_comparison="multi-seed support when inaccurate persistent variant occurs",
            max_ticks=64,
        ),
        _spec(
            scenario_id=BENCH_15_ARCHITECTURE_MATRIX,
            title="Identical world, different cognitive architectures",
            condition_ids=tuple(
                f"ac-{architecture_id}"
                for architecture_id in registered_architecture_ids()
            ),
            required_modes=("architecture_expand",),
            composition_notes="Experiment AC ac-<architecture_id> arms; shared scenario fingerprint",
            seed_strategy="matrix: shared-seed architecture factor",
            expected_invariants=(
                "Architecture arms share scenario fingerprint and seed; each produces valid closed commands.",
                "Architecture digests are diagnostics only — never fed into cognition.",
            ),
            measurable_outputs=(
                "shared scenario fingerprint",
                "valid closed commands",
                "audit/metric availability diffs",
            ),
            non_goals=(
                "Do not treat architecture digests as world truth.",
            ),
            statistical_comparison="shared-seed architecture factor",
            max_ticks=64,
        ),
        _spec(
            scenario_id=BENCH_16_FORKED_INTERVENTION,
            title="Forked replay after one controlled intervention",
            condition_ids=("fork-communication-remove",),
            required_modes=("ResearchInterventionKind.COMMUNICATION_REMOVE",),
            composition_notes=(
                "One ResearchIntervention(kind=COMMUNICATION_REMOVE); "
                "parent immutable; child post-fork hash diverges"
            ),
            seed_strategy="n/a: single deterministic intervention (not a culture matrix)",
            expected_invariants=(
                "Parent history remains immutable after COMMUNICATION_REMOVE fork.",
                "Child prefix equals parent prefix; post-fork trajectory hash diverges.",
                "branch_compare document is assemblable for parent/child run ids.",
            ),
            measurable_outputs=(
                "lineage",
                "prefix equality",
                "branch_compare document",
            ),
            non_goals=(
                "Do not use a culture matrix for this scenario.",
                "Do not rewrite parent event history.",
            ),
            statistical_comparison="n/a: single deterministic intervention (not a culture matrix)",
            max_ticks=64,
        ),
    )
    registry: dict[str, BenchmarkScenarioSpec] = {}
    for spec in specs:
        if spec.scenario_id in registry:
            raise BenchmarkSpecError(
                "duplicate_scenario_id",
                f"duplicate scenario_id={spec.scenario_id}",
            )
        registry[spec.scenario_id] = spec
    if len(registry) != BENCHMARK_SCENARIO_COUNT:
        raise BenchmarkSpecError(
            "scenario_count_mismatch",
            f"expected {BENCHMARK_SCENARIO_COUNT} scenarios, got {len(registry)}",
        )
    missing = [item for item in BENCHMARK_SCENARIO_IDS if item not in registry]
    if missing:
        raise BenchmarkSpecError(
            "missing_scenario_ids",
            f"missing scenario_ids={','.join(missing)}",
        )
    extra = [item for item in registry if item not in BENCHMARK_SCENARIO_IDS]
    if extra:
        raise BenchmarkSpecError(
            "unexpected_scenario_ids",
            f"unexpected scenario_ids={','.join(sorted(extra))}",
        )
    _LOG.info(
        "benchmark_suite_registered scenario_count=%s",
        BENCHMARK_SCENARIO_COUNT,
    )
    return registry


_REGISTRY: Final[dict[str, BenchmarkScenarioSpec]] = _build_registry()


def registered_benchmark_scenario_ids() -> tuple[str, ...]:
    """Return the locked ordered suite scenario ids."""
    return BENCHMARK_SCENARIO_IDS


def list_benchmark_scenarios() -> tuple[BenchmarkScenarioSpec, ...]:
    """Return all registered specs in locked catalog order."""
    return tuple(_REGISTRY[item] for item in BENCHMARK_SCENARIO_IDS)


def get_benchmark_scenario(scenario_id: str) -> BenchmarkScenarioSpec:
    """Return one registered spec or raise BenchmarkSpecError."""
    require_stable_id("scenario_id", scenario_id)
    try:
        return _REGISTRY[scenario_id]
    except KeyError as exc:
        raise BenchmarkSpecError(
            "unknown_scenario_id",
            f"unknown scenario_id={scenario_id}",
        ) from exc


def benchmark_suite_registry() -> Mapping[str, BenchmarkScenarioSpec]:
    """Read-only view of the scenario registry."""
    return _REGISTRY
