"""Immutable contracts for the V3 generational civilization benchmark.

Composition-only metadata: these contracts never grant world authority, mutate a
runner schema, install research outcomes into cognition, or parse English
scenario narration. They keep execution, invariants, mechanism coverage,
measurement, phenomenon, publication and comparison as separate fields so a
null or unavailable result can never be reported as a passing invariant.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from world.identifiers import require_stable_id

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.civilization_benchmark_models"
)

V3_BENCHMARK_SUITE_ID: Final[str] = "v3-generational-civilization-benchmark-v1"
V3_BENCHMARK_SUITE_VERSION: Final[int] = 1
V3_BENCHMARK_SCENARIO_COUNT: Final[int] = 30

V3_BENCHMARK_ID_PREFIX: Final[str] = "v3-bench-"
V3_VISUAL_BENCHMARK_ID: Final[str] = "v3-visual-integration-v1"


class V3BenchmarkError(ValueError):
    """Fail-closed benchmark contract validation with a stable code."""

    def __init__(self, code: str, message: str = "") -> None:
        self.code = code
        detail = message or code
        super().__init__(detail)
        _LOG.error("v3_benchmark_invalid reason_code=%s", code)


class V3BenchmarkProfile(StrEnum):
    """Predeclared bounded fixture budgets."""

    SMOKE = "smoke"
    RESEARCH = "research"
    VISUAL = "visual"


class V3BenchmarkExecutionKind(StrEnum):
    """Independent mechanism/research case versus a grouped fork protocol."""

    INDEPENDENT = "independent"
    GROUPED = "grouped"


class V3BenchmarkLane(StrEnum):
    """Controlled mechanism lane versus autonomous research lane."""

    MECHANISM = "mechanism"
    RESEARCH = "research"


class V3BenchmarkExecutionStatus(StrEnum):
    """Execution outcome, independent from scientific interpretation."""

    COMPLETED = "completed"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    NOT_RUN = "not_run"


class V3BenchmarkCoverage(StrEnum):
    """Whether a declared mechanism was actually exercised."""

    EXERCISED = "exercised"
    NOT_EXERCISED = "not_exercised"
    NOT_APPLICABLE = "not_applicable"


class V3BenchmarkEvidenceAvailability(StrEnum):
    """Completeness of the retained source evidence."""

    COMPLETE = "complete"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"


class V3BenchmarkPhenomenon(StrEnum):
    """Observed phenomenon state; absence remains a valid research outcome."""

    DETECTED = "detected"
    NOT_DETECTED = "not_detected"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"


class V3BenchmarkCheckStatus(StrEnum):
    """Invariant check outcome."""

    PASS = "pass"
    FAIL = "fail"
    UNEXECUTED = "unexecuted"


class V3BenchmarkSourceKind(StrEnum):
    """Qualified evidence channel backing a check."""

    OBJECTIVE_INSPECTION = "objective_inspection"
    SUBJECTIVE_DEBUG = "subjective_debug"
    ANALYSIS_FAMILY = "analysis_family"
    CAPTURE = "capture"


class V3BenchmarkTreatmentScope(StrEnum):
    """Declared scope of a controlled contrast."""

    NONE = "none"
    RUN_OPPORTUNITY = "run_opportunity"
    FOUNDER_ROSTER = "founder_roster"
    INITIALIZER_PROFILE = "initializer_profile"


class V3BenchmarkContrastKind(StrEnum):
    """Whether a contrast isolates one factor or a composite profile."""

    NONE = "none"
    SINGLE_FACTOR = "single_factor"
    COMPOSITE_PROFILE = "composite_profile"


# Closed selector registry. A selector identifies the retained evidence channel
# a scenario requires; it is not a claim that a phenomenon must occur.
EVIDENCE_SELECTOR_VERSIONS: Final[Mapping[str, int]] = {
    "population_lifecycle_evidence": 1,
    "new_agent_initialization_evidence": 1,
    "dependency_care_evidence": 1,
    "developmental_learning_evidence": 1,
    "mentorship_evidence": 1,
    "cultural_feature_evidence": 1,
    "historical_memory_evidence": 1,
    "durable_record_evidence": 1,
    "knowledge_repository_evidence": 1,
    "knowledge_genealogy_evidence": 1,
    "technique_lifecycle_evidence": 1,
    "possession_succession_evidence": 1,
    "commitment_evidence": 1,
    "subjective_exchange_evidence": 1,
    "exchange_function_evidence": 1,
    "collective_project_evidence": 1,
    "public_goods_evidence": 1,
    "migration_evidence": 1,
    "cultural_contact_evidence": 1,
    "symbolic_language_evidence": 1,
    "semantic_drift_evidence": 1,
    "translation_evidence": 1,
    "generational_narrative_evidence": 1,
    "institution_concept_evidence": 1,
    "office_succession_evidence": 1,
    "institutional_memory_evidence": 1,
    "institutional_decay_evidence": 1,
    "lineage_genealogy_evidence": 1,
    "path_dependence_outcome_evidence": 1,
    "objective_event_journal": 1,
    "recording_replay_evidence": 1,
    "mechanism_intervention_evidence": 1,
}

# Closed run-level specification IDs a recipe may declare as prerequisites.
KNOWN_SPEC_IDS: Final[frozenset[str]] = frozenset(
    {
        "population_lifecycle",
        "new_agent_initialization",
        "generational_run",
        "dependency_care",
        "developmental_learning",
        "mentorship",
        "cultural_feature_provenance",
        "historical_memory_layers",
        "durable_records",
        "knowledge_repositories",
        "knowledge_genealogy",
        "technique_lifecycle",
        "possession_succession",
        "structured_commitments",
        "subjective_exchange",
        "resource_exchange_profile",
        "collective_projects",
        "public_goods",
        "regions_migration",
        "cultural_contact",
        "generational_narratives",
        "institution_concept_mode",
        "office_succession_mode",
        "institutional_memory_mode",
        "institutional_decay_mode",
        "symbolic_language_mode",
        "translation_mode",
    }
)

# Closed capability-flag and per-agent cognition mode IDs.
KNOWN_MODE_IDS: Final[frozenset[str]] = frozenset(
    {
        "generational_population",
        "kinship_inheritance",
        "cultural_historical_memory",
        "multi_polity_migration",
        "skill_learning_mode",
        "teaching_interaction_mode",
        "semantic_naming_mode",
        "cultural_narrative_mode",
        "artifact_interpretation_mode",
        "symbolic_language_mode",
        "translation_mode",
        "institution_concept_mode",
        "office_succession_mode",
        "institutional_memory_mode",
        "institutional_decay_mode",
        "social_norm_mode",
        "social_convention_mode",
    }
)

PUBLICATION_STATUSES: Final[frozenset[str]] = frozenset(
    {"not_requested", "published", "failed", "unavailable"}
)

CAPTURE_LANE_IDS: Final[frozenset[str]] = frozenset(
    {
        "objective_journal",
        "cultural_evidence",
        "lineage_snapshot",
        "path_dependence_artifacts",
        "recording_replay",
        "visual_fixture",
    }
)


def _require_bool(name: str, value: object) -> bool:
    if type(value) is not bool:
        raise V3BenchmarkError("invalid_boolean", f"{name} must be bool")
    return value


def _require_non_negative_int(name: str, value: object) -> int:
    if type(value) is not int or isinstance(value, bool):
        raise V3BenchmarkError("invalid_integer", f"{name} must be int")
    if value < 0:
        raise V3BenchmarkError("invalid_integer", f"{name} must be >= 0")
    return value


def _require_positive_int(name: str, value: object) -> int:
    number = _require_non_negative_int(name, value)
    if number < 1:
        raise V3BenchmarkError("invalid_integer", f"{name} must be >= 1")
    return number


def _ordered_str_tuple(
    name: str, value: object, *, allow_empty: bool = False
) -> tuple[str, ...]:
    if isinstance(value, (set, frozenset)):
        raise V3BenchmarkError(f"unordered_{name}", f"{name} must be ordered")
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise V3BenchmarkError(f"invalid_{name}", f"{name} must be a sequence")
    items = tuple(value)
    if not items and not allow_empty:
        raise V3BenchmarkError(f"empty_{name}", f"{name} must be non-empty")
    for item in items:
        if type(item) is not str or not item.strip():
            raise V3BenchmarkError(
                f"invalid_{name}_entry", f"{name} entries must be non-empty str"
            )
        require_stable_id(name, item)
    if len(set(items)) != len(items):
        raise V3BenchmarkError(f"duplicate_{name}", f"{name} entries must be unique")
    return items


def _ordered_typed_tuple[T](
    name: str, value: object, enum_type: type[T], *, allow_empty: bool = False
) -> tuple[T, ...]:
    if isinstance(value, (set, frozenset)):
        raise V3BenchmarkError(f"unordered_{name}", f"{name} must be ordered")
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise V3BenchmarkError(f"invalid_{name}", f"{name} must be a sequence")
    items = tuple(value)
    if not items and not allow_empty:
        raise V3BenchmarkError(f"empty_{name}", f"{name} must be non-empty")
    resolved: list[T] = []
    for item in items:
        if type(item) is not enum_type:
            raise V3BenchmarkError(
                f"invalid_{name}_entry", f"{name} entries must be {enum_type.__name__}"
            )
        resolved.append(item)
    if len(set(resolved)) != len(resolved):
        raise V3BenchmarkError(f"duplicate_{name}", f"{name} entries must be unique")
    return tuple(resolved)


def _require_known_selector(selector_id: str, selector_version: int) -> None:
    known_version = EVIDENCE_SELECTOR_VERSIONS.get(selector_id)
    if known_version is None:
        raise V3BenchmarkError(
            "unknown_selector", f"unknown evidence selector {selector_id!r}"
        )
    if known_version != selector_version:
        raise V3BenchmarkError(
            "unknown_selector_version",
            f"selector {selector_id!r} version {selector_version} is unsupported",
        )


@dataclass(frozen=True, slots=True)
class V3BenchmarkSourceReference:
    """Qualified, bounded reference to retained source evidence."""

    source_kind: V3BenchmarkSourceKind
    reference_id: str
    owner_id: str | None = None
    tick: int | None = None

    def __post_init__(self) -> None:
        if type(self.source_kind) is not V3BenchmarkSourceKind:
            raise V3BenchmarkError(
                "invalid_source_kind", "source_kind must be V3BenchmarkSourceKind"
            )
        object.__setattr__(
            self, "reference_id", require_stable_id("reference_id", self.reference_id)
        )
        if self.owner_id is not None:
            object.__setattr__(
                self, "owner_id", require_stable_id("owner_id", self.owner_id)
            )
        if self.tick is not None:
            object.__setattr__(
                self, "tick", _require_non_negative_int("tick", self.tick)
            )


@dataclass(frozen=True, slots=True)
class V3BenchmarkEvidenceSelector:
    """Closed evidence selector declared by one scenario."""

    selector_id: str
    selector_version: int
    required: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "selector_id", require_stable_id("selector_id", self.selector_id)
        )
        object.__setattr__(
            self,
            "selector_version",
            _require_positive_int("selector_version", self.selector_version),
        )
        _require_known_selector(self.selector_id, self.selector_version)
        object.__setattr__(self, "required", _require_bool("required", self.required))


@dataclass(frozen=True, slots=True)
class V3BenchmarkRecipe:
    """Bounded fixture recipe metadata (never stored inside runner JSON)."""

    profile: V3BenchmarkProfile
    schedule_id: str
    schedule_version: int
    horizon_ticks: int
    seeds: tuple[int, ...]
    arm_count: int
    treatment_scope: V3BenchmarkTreatmentScope = V3BenchmarkTreatmentScope.NONE
    contrast_kind: V3BenchmarkContrastKind = V3BenchmarkContrastKind.NONE
    schedule_notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if type(self.profile) is not V3BenchmarkProfile:
            raise V3BenchmarkError("invalid_profile", "profile must be a known profile")
        object.__setattr__(
            self, "schedule_id", require_stable_id("schedule_id", self.schedule_id)
        )
        object.__setattr__(
            self,
            "schedule_version",
            _require_positive_int("schedule_version", self.schedule_version),
        )
        object.__setattr__(
            self,
            "horizon_ticks",
            _require_positive_int("horizon_ticks", self.horizon_ticks),
        )
        if isinstance(self.seeds, (set, frozenset)):
            raise V3BenchmarkError("unordered_seeds", "seeds must be ordered")
        if isinstance(self.seeds, (str, bytes)) or not isinstance(
            self.seeds, Sequence
        ):
            raise V3BenchmarkError("invalid_seeds", "seeds must be a sequence")
        seeds = tuple(_require_positive_int("seed", item) for item in self.seeds)
        if not seeds:
            raise V3BenchmarkError("empty_seeds", "seeds must be non-empty")
        if len(set(seeds)) != len(seeds):
            raise V3BenchmarkError("duplicate_seed", "seeds must be unique")
        object.__setattr__(self, "seeds", seeds)
        object.__setattr__(
            self, "arm_count", _require_positive_int("arm_count", self.arm_count)
        )
        if type(self.treatment_scope) is not V3BenchmarkTreatmentScope:
            raise V3BenchmarkError(
                "invalid_treatment_scope",
                "treatment_scope must be V3BenchmarkTreatmentScope",
            )
        if type(self.contrast_kind) is not V3BenchmarkContrastKind:
            raise V3BenchmarkError(
                "invalid_contrast_kind",
                "contrast_kind must be V3BenchmarkContrastKind",
            )
        if self.treatment_scope is V3BenchmarkTreatmentScope.INITIALIZER_PROFILE:
            if self.contrast_kind is not V3BenchmarkContrastKind.COMPOSITE_PROFILE:
                raise V3BenchmarkError(
                    "contrast_scope_mismatch",
                    "initializer_profile contrasts are composite_profile",
                )
        elif self.treatment_scope is V3BenchmarkTreatmentScope.NONE:
            if self.contrast_kind is not V3BenchmarkContrastKind.NONE:
                raise V3BenchmarkError(
                    "contrast_scope_mismatch",
                    "no treatment scope requires no contrast kind",
                )
        elif self.contrast_kind is not V3BenchmarkContrastKind.SINGLE_FACTOR:
            raise V3BenchmarkError(
                "contrast_scope_mismatch",
                "opportunity/founder_roster contrasts are single_factor",
            )
        notes = _ordered_str_tuple(
            "schedule_notes", self.schedule_notes, allow_empty=True
        )
        object.__setattr__(self, "schedule_notes", notes)


@dataclass(frozen=True, slots=True)
class V3BenchmarkSpec:
    """Mandatory per-scenario contract for the V3 benchmark suite."""

    request_number: int
    scenario_id: str
    title: str
    execution_kind: V3BenchmarkExecutionKind
    lanes: tuple[V3BenchmarkLane, ...]
    recipe: V3BenchmarkRecipe
    required_specs: tuple[str, ...]
    required_modes: tuple[str, ...]
    evidence_selectors: tuple[V3BenchmarkEvidenceSelector, ...]
    comparison_axis: str
    non_goals: tuple[str, ...]
    required_capture_lanes: tuple[str, ...]
    off_v1_gate: bool = True

    def __post_init__(self) -> None:
        request_number = _require_positive_int("request_number", self.request_number)
        if request_number > V3_BENCHMARK_SCENARIO_COUNT:
            raise V3BenchmarkError(
                "invalid_request_number", "request_number exceeds scenario count"
            )
        object.__setattr__(self, "request_number", request_number)
        scenario_id = require_stable_id("scenario_id", self.scenario_id)
        if (
            not scenario_id.startswith(V3_BENCHMARK_ID_PREFIX)
            and scenario_id != V3_VISUAL_BENCHMARK_ID
        ):
            raise V3BenchmarkError(
                "invalid_scenario_id", "scenario_id must use the v3-bench- prefix"
            )
        object.__setattr__(self, "scenario_id", scenario_id)
        if type(self.title) is not str or not self.title.strip():
            raise V3BenchmarkError("invalid_title", "title must be non-empty str")
        if type(self.execution_kind) is not V3BenchmarkExecutionKind:
            raise V3BenchmarkError(
                "unsupported_execution_kind",
                "execution_kind must be V3BenchmarkExecutionKind",
            )
        lanes = _ordered_typed_tuple("lanes", self.lanes, V3BenchmarkLane)
        expected_lanes = (V3BenchmarkLane.MECHANISM, V3BenchmarkLane.RESEARCH)
        if lanes != expected_lanes:
            raise V3BenchmarkError(
                "unsupported_lane_combination",
                "scenarios require exactly the mechanism and research lanes",
            )
        object.__setattr__(self, "lanes", lanes)
        if type(self.recipe) is not V3BenchmarkRecipe:
            raise V3BenchmarkError("invalid_recipe", "recipe must be a recipe")
        specs = _ordered_str_tuple("required_specs", self.required_specs)
        unknown_specs = [item for item in specs if item not in KNOWN_SPEC_IDS]
        if unknown_specs:
            raise V3BenchmarkError(
                "unknown_spec", f"unknown specs={','.join(unknown_specs)}"
            )
        object.__setattr__(self, "required_specs", specs)
        modes = _ordered_str_tuple("required_modes", self.required_modes)
        unknown_modes = [item for item in modes if item not in KNOWN_MODE_IDS]
        if unknown_modes:
            raise V3BenchmarkError(
                "unknown_mode", f"unknown modes={','.join(unknown_modes)}"
            )
        object.__setattr__(self, "required_modes", modes)
        selectors = _ordered_typed_tuple(
            "evidence_selectors", self.evidence_selectors, V3BenchmarkEvidenceSelector
        )
        selector_ids = [selector.selector_id for selector in selectors]
        if len(set(selector_ids)) != len(selector_ids):
            raise V3BenchmarkError(
                "duplicate_selector", "evidence selectors must be unique"
            )
        if not any(selector.required for selector in selectors):
            raise V3BenchmarkError(
                "missing_selector", "at least one required selector is mandatory"
            )
        object.__setattr__(self, "evidence_selectors", selectors)
        if type(self.comparison_axis) is not str or not self.comparison_axis.strip():
            raise V3BenchmarkError(
                "invalid_comparison_axis", "comparison_axis must be non-empty str"
            )
        object.__setattr__(
            self, "non_goals", _ordered_str_tuple("non_goals", self.non_goals)
        )
        object.__setattr__(
            self,
            "required_capture_lanes",
            _ordered_str_tuple("required_capture_lanes", self.required_capture_lanes),
        )
        unknown_lanes = [
            item
            for item in self.required_capture_lanes
            if item not in CAPTURE_LANE_IDS
        ]
        if unknown_lanes:
            raise V3BenchmarkError(
                "unknown_capture_lane", f"unknown capture lanes={unknown_lanes!r}"
            )
        object.__setattr__(
            self, "off_v1_gate", _require_bool("off_v1_gate", self.off_v1_gate)
        )
        if self.off_v1_gate is not True:
            raise V3BenchmarkError(
                "off_v1_gate_required", "V3 benchmark scenarios are off the V1 gate"
            )
        if self.execution_kind is V3BenchmarkExecutionKind.INDEPENDENT:
            if (
                self.recipe.treatment_scope is not V3BenchmarkTreatmentScope.NONE
                or self.recipe.arm_count != 1
            ):
                raise V3BenchmarkError(
                    "unsupported_lane_combination",
                    "independent cases have one arm and no treatment scope",
                )
        else:
            if self.recipe.arm_count < 2:
                raise V3BenchmarkError(
                    "unsupported_lane_combination",
                    "grouped cases require at least two arms",
                )
            if self.recipe.treatment_scope is V3BenchmarkTreatmentScope.NONE:
                raise V3BenchmarkError(
                    "unsupported_lane_combination",
                    "grouped research lanes are intervention based",
                )


@dataclass(frozen=True, slots=True)
class V3BenchmarkCheck:
    """One invariant/mechanism check with qualified source coverage."""

    selector_id: str
    selector_version: int
    status: V3BenchmarkCheckStatus
    reason_code: str
    evidence: V3BenchmarkEvidenceAvailability
    coverage: V3BenchmarkCoverage
    source_references: tuple[V3BenchmarkSourceReference, ...]
    boundary_start_tick: int | None = None
    boundary_end_tick: int | None = None
    numerator: int | None = None
    denominator: int | None = None

    def __post_init__(self) -> None:
        selector_id = require_stable_id("selector_id", self.selector_id)
        selector_version = _require_positive_int(
            "selector_version", self.selector_version
        )
        _require_known_selector(selector_id, selector_version)
        object.__setattr__(self, "selector_id", selector_id)
        object.__setattr__(self, "selector_version", selector_version)
        if type(self.status) is not V3BenchmarkCheckStatus:
            raise V3BenchmarkError("invalid_check_status", "status must be known")
        if type(self.evidence) is not V3BenchmarkEvidenceAvailability:
            raise V3BenchmarkError("invalid_evidence", "evidence must be known")
        if type(self.coverage) is not V3BenchmarkCoverage:
            raise V3BenchmarkError("invalid_coverage", "coverage must be known")
        object.__setattr__(
            self, "reason_code", require_stable_id("reason_code", self.reason_code)
        )
        references = _ordered_typed_tuple(
            "source_references",
            self.source_references,
            V3BenchmarkSourceReference,
            allow_empty=True,
        )
        object.__setattr__(self, "source_references", references)
        if (self.boundary_start_tick is None) != (self.boundary_end_tick is None):
            raise V3BenchmarkError(
                "invalid_boundary", "boundary start and end must both be set"
            )
        if self.boundary_start_tick is not None:
            start_value = self.boundary_start_tick
            end_value = self.boundary_end_tick
            assert end_value is not None
            start = _require_non_negative_int("boundary_start_tick", start_value)
            end = _require_non_negative_int("boundary_end_tick", end_value)
            if end < start:
                raise V3BenchmarkError(
                    "invalid_boundary", "boundary end must not precede start"
                )
            object.__setattr__(self, "boundary_start_tick", start)
            object.__setattr__(self, "boundary_end_tick", end)
        if (self.numerator is None) != (self.denominator is None):
            raise V3BenchmarkError(
                "invalid_ratio", "numerator and denominator must both be set"
            )
        if self.numerator is not None:
            numerator_value = self.numerator
            denominator_value = self.denominator
            assert denominator_value is not None
            numerator = _require_non_negative_int("numerator", numerator_value)
            denominator = _require_non_negative_int("denominator", denominator_value)
            if numerator > denominator:
                raise V3BenchmarkError(
                    "invalid_ratio", "numerator must not exceed denominator"
                )
            object.__setattr__(self, "numerator", numerator)
            object.__setattr__(self, "denominator", denominator)
        if self.status is V3BenchmarkCheckStatus.PASS:
            if self.evidence is not V3BenchmarkEvidenceAvailability.COMPLETE:
                raise V3BenchmarkError(
                    "pass_requires_complete_evidence",
                    "a passing check requires complete source evidence",
                )
            if self.coverage is not V3BenchmarkCoverage.EXERCISED:
                raise V3BenchmarkError(
                    "pass_requires_exercised_coverage",
                    "a passing check requires exercised mechanism coverage",
                )
            if not references:
                raise V3BenchmarkError(
                    "pass_requires_sources",
                    "a passing check requires at least one qualified source",
                )


@dataclass(frozen=True, slots=True)
class V3BenchmarkInterventionReceipt:
    """Applied/rejected acknowledgement of one declared mechanism action."""

    milestone_id: str
    status: str
    proposed_command_kind: str
    effective_command_kind: str
    resolution_status: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "milestone_id", require_stable_id("milestone_id", self.milestone_id)
        )
        object.__setattr__(self, "status", require_stable_id("status", self.status))
        object.__setattr__(
            self,
            "proposed_command_kind",
            require_stable_id("proposed_command_kind", self.proposed_command_kind),
        )
        object.__setattr__(
            self,
            "effective_command_kind",
            require_stable_id("effective_command_kind", self.effective_command_kind),
        )
        if self.resolution_status is not None:
            object.__setattr__(
                self,
                "resolution_status",
                require_stable_id("resolution_status", self.resolution_status),
            )


@dataclass(frozen=True, slots=True)
class V3BenchmarkRunResult:
    """Separated execution, evidence, phenomenon and publication state."""

    scenario_id: str
    lane: V3BenchmarkLane
    execution_status: V3BenchmarkExecutionStatus
    declared_horizon: int
    ticks_committed: int
    coverage: V3BenchmarkCoverage
    evidence: V3BenchmarkEvidenceAvailability
    phenomenon: V3BenchmarkPhenomenon
    checks: tuple[V3BenchmarkCheck, ...]
    publication_status: str = "not_requested"
    comparison_id: str | None = None
    intervention_receipts: tuple[V3BenchmarkInterventionReceipt, ...] = ()

    def __post_init__(self) -> None:
        scenario_id = require_stable_id("scenario_id", self.scenario_id)
        if (
            not scenario_id.startswith(V3_BENCHMARK_ID_PREFIX)
            and scenario_id != V3_VISUAL_BENCHMARK_ID
        ):
            raise V3BenchmarkError(
                "invalid_scenario_id", "scenario_id must use the v3-bench- prefix"
            )
        object.__setattr__(self, "scenario_id", scenario_id)
        if type(self.lane) is not V3BenchmarkLane:
            raise V3BenchmarkError("invalid_lane", "lane must be a known lane")
        if type(self.execution_status) is not V3BenchmarkExecutionStatus:
            raise V3BenchmarkError(
                "invalid_execution_status", "execution_status must be known"
            )
        if type(self.coverage) is not V3BenchmarkCoverage:
            raise V3BenchmarkError("invalid_coverage", "coverage must be known")
        if type(self.evidence) is not V3BenchmarkEvidenceAvailability:
            raise V3BenchmarkError("invalid_evidence", "evidence must be known")
        if type(self.phenomenon) is not V3BenchmarkPhenomenon:
            raise V3BenchmarkError("invalid_phenomenon", "phenomenon must be known")
        declared = _require_positive_int("declared_horizon", self.declared_horizon)
        committed = _require_non_negative_int("ticks_committed", self.ticks_committed)
        if committed > declared:
            raise V3BenchmarkError(
                "invalid_horizon", "ticks_committed must not exceed declared_horizon"
            )
        object.__setattr__(self, "declared_horizon", declared)
        object.__setattr__(self, "ticks_committed", committed)
        checks = _ordered_typed_tuple(
            "checks", self.checks, V3BenchmarkCheck, allow_empty=True
        )
        selectors = [check.selector_id for check in checks]
        if len(set(selectors)) != len(selectors):
            raise V3BenchmarkError(
                "duplicate_check_selector", "checks must reference unique selectors"
            )
        object.__setattr__(self, "checks", checks)
        receipts = _ordered_typed_tuple(
            "intervention_receipt",
            self.intervention_receipts,
            V3BenchmarkInterventionReceipt,
            allow_empty=True,
        )
        if len({item.milestone_id for item in receipts}) != len(receipts):
            raise V3BenchmarkError(
                "duplicate_intervention_receipt",
                "intervention receipts must be unique per milestone",
            )
        object.__setattr__(self, "intervention_receipts", receipts)
        if type(self.publication_status) is not str:
            raise V3BenchmarkError(
                "invalid_publication_status", "publication_status must be str"
            )
        if self.publication_status not in PUBLICATION_STATUSES:
            raise V3BenchmarkError(
                "invalid_publication_status",
                f"unsupported publication status {self.publication_status!r}",
            )
        if self.comparison_id is not None:
            object.__setattr__(
                self,
                "comparison_id",
                require_stable_id("comparison_id", self.comparison_id),
            )
        if self.evidence is V3BenchmarkEvidenceAvailability.COMPLETE:
            if self.execution_status is not V3BenchmarkExecutionStatus.COMPLETED:
                raise V3BenchmarkError(
                    "complete_evidence_requires_completion",
                    "complete evidence requires a completed execution",
                )
            if committed != declared:
                raise V3BenchmarkError(
                    "incomplete_horizon",
                    "complete evidence requires the full declared horizon",
                )
        if self.phenomenon in (
            V3BenchmarkPhenomenon.DETECTED,
            V3BenchmarkPhenomenon.NOT_DETECTED,
        ):
            if self.evidence is not V3BenchmarkEvidenceAvailability.COMPLETE:
                raise V3BenchmarkError(
                    "phenomenon_requires_complete_evidence",
                    "detected/not_detected require complete evidence",
                )


@dataclass(frozen=True, slots=True)
class V3BenchmarkSuiteResult:
    """Ordered lane results for one benchmark profile."""

    profile: V3BenchmarkProfile
    runs: tuple[V3BenchmarkRunResult, ...]

    def __post_init__(self) -> None:
        if type(self.profile) is not V3BenchmarkProfile:
            raise V3BenchmarkError("invalid_profile", "profile must be known")
        runs = _ordered_typed_tuple("run", self.runs, V3BenchmarkRunResult)
        identities = [(run.scenario_id, run.lane) for run in runs]
        if len(set(identities)) != len(identities):
            raise V3BenchmarkError(
                "duplicate_run", "suite runs must have unique scenario/lane pairs"
            )
        object.__setattr__(self, "runs", runs)

    def scenario_ids(self) -> tuple[str, ...]:
        """Return scenario ids in retained order, without duplicates."""
        seen: list[str] = []
        for run in self.runs:
            if run.scenario_id not in seen:
                seen.append(run.scenario_id)
        return tuple(seen)


__all__ = [
    "CAPTURE_LANE_IDS",
    "EVIDENCE_SELECTOR_VERSIONS",
    "KNOWN_MODE_IDS",
    "KNOWN_SPEC_IDS",
    "PUBLICATION_STATUSES",
    "V3_BENCHMARK_ID_PREFIX",
    "V3_BENCHMARK_SCENARIO_COUNT",
    "V3_BENCHMARK_SUITE_ID",
    "V3_BENCHMARK_SUITE_VERSION",
    "V3_VISUAL_BENCHMARK_ID",
    "V3BenchmarkCheck",
    "V3BenchmarkCheckStatus",
    "V3BenchmarkContrastKind",
    "V3BenchmarkCoverage",
    "V3BenchmarkError",
    "V3BenchmarkEvidenceAvailability",
    "V3BenchmarkEvidenceSelector",
    "V3BenchmarkExecutionKind",
    "V3BenchmarkExecutionStatus",
    "V3BenchmarkInterventionReceipt",
    "V3BenchmarkLane",
    "V3BenchmarkPhenomenon",
    "V3BenchmarkProfile",
    "V3BenchmarkRecipe",
    "V3BenchmarkRunResult",
    "V3BenchmarkSourceKind",
    "V3BenchmarkSourceReference",
    "V3BenchmarkSpec",
    "V3BenchmarkSuiteResult",
    "V3BenchmarkTreatmentScope",
]
