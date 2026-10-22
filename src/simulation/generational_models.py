"""Immutable contracts for opt-in multi-generation run orchestration.

These values describe an experimental generation calendar, stopping evidence,
and detached population progress. They do not add objective institution,
pedigree, or social authority. Generation indices are admission labels, not
genealogy or community identity.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from world.identifiers import (
    require_exact_nonneg_int,
    require_stable_id,
)

_LOGGER: Final[logging.Logger] = logging.getLogger("simulation.generational_models")

GENERATIONAL_RUN_POLICY_VERSION: Final[str] = "generational-run-v1"

_CRITERION_STATUS_VALUES: Final[frozenset[str]] = frozenset(
    {
        "not_due",
        "evaluated",
        "skipped_builtin_stop",
        "failed",
        "not_configured",
    }
)


class PopulationThresholdComparison(StrEnum):
    """Closed inclusive population-threshold comparators."""

    AT_MOST = "at_most"
    AT_LEAST = "at_least"


class ExperimentCriterionEvaluationStatus(StrEnum):
    """Closed custom-criterion evaluation status for stop evidence."""

    NOT_DUE = "not_due"
    EVALUATED = "evaluated"
    SKIPPED_BUILTIN_STOP = "skipped_builtin_stop"
    FAILED = "failed"
    NOT_CONFIGURED = "not_configured"


def _require_bool(name: str, value: object) -> bool:
    if type(value) is not bool:
        raise TypeError(f"{name} must be bool")
    return value


def _require_positive_int(name: str, value: object) -> int:
    if isinstance(value, bool) or type(value) is not int or value < 1:
        raise ValueError(f"{name} must be a positive integer")
    return value


def freeze_json_value(name: str, value: object) -> object:
    """Recursively freeze a JSON-compatible value in declaration order.

    Accepted leaves are ``None``, exact ``bool``, exact ``int``, finite
    ``float``, and exact ``str``. Mappings become read-only mappings with
    string keys; sequences become tuples. Executable or opaque objects fail
    closed instead of being silently stringified.
    """
    if value is None or type(value) is bool:
        return value
    if type(value) is int:
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError(f"{name} must not contain non-finite numbers")
        return value
    if type(value) is str:
        return value
    if isinstance(value, Mapping):
        frozen: dict[str, object] = {}
        for key, item in value.items():
            if type(key) is not str:
                raise TypeError(f"{name} keys must be str")
            frozen[key] = freeze_json_value(f"{name}.{key}", item)
        return MappingProxyType(frozen)
    if isinstance(value, (list, tuple)):
        return tuple(
            freeze_json_value(f"{name}[{index}]", item)
            for index, item in enumerate(value)
        )
    raise TypeError(
        f"{name} must contain only JSON values, got {type(value).__name__}"
    )


@dataclass(frozen=True, slots=True)
class PopulationThresholdSpec:
    """Inclusive living-population termination threshold."""

    comparison: PopulationThresholdComparison
    value: int

    def __post_init__(self) -> None:
        if type(self.comparison) is not PopulationThresholdComparison:
            raise TypeError("comparison must be PopulationThresholdComparison")
        object.__setattr__(
            self,
            "value",
            require_exact_nonneg_int("PopulationThresholdSpec.value", self.value),
        )


@dataclass(frozen=True, slots=True)
class ExperimentCriterionSpec:
    """Trusted experiment criterion identity plus frozen JSON parameters."""

    criterion_id: str
    version: str
    params: Mapping[str, object] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "criterion_id",
            require_stable_id(
                "ExperimentCriterionSpec.criterion_id", self.criterion_id
            ),
        )
        object.__setattr__(
            self,
            "version",
            require_stable_id("ExperimentCriterionSpec.version", self.version),
        )
        if isinstance(self.params, (str, bytes)) or not isinstance(
            self.params, Mapping
        ):
            raise TypeError("ExperimentCriterionSpec.params must be a mapping")
        frozen = freeze_json_value("ExperimentCriterionSpec.params", self.params)
        if not isinstance(frozen, Mapping):
            raise TypeError("ExperimentCriterionSpec.params must be a mapping")
        object.__setattr__(self, "params", frozen)

    @property
    def identity(self) -> tuple[str, str]:
        return (self.criterion_id, self.version)


@dataclass(frozen=True, slots=True)
class ExperimentCriterionIdentity:
    """Stable identity retained in stop evidence (no executable callback)."""

    criterion_id: str
    version: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "criterion_id",
            require_stable_id(
                "ExperimentCriterionIdentity.criterion_id", self.criterion_id
            ),
        )
        object.__setattr__(
            self,
            "version",
            require_stable_id("ExperimentCriterionIdentity.version", self.version),
        )

    @property
    def identity(self) -> tuple[str, str]:
        return (self.criterion_id, self.version)


@dataclass(frozen=True, slots=True)
class CohortPopulationRow:
    """One admitted cohort's objective population totals."""

    generation_index: int
    entry_tick: int
    cohort_id: str
    admitted: int
    living: int
    dead: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "generation_index",
            require_exact_nonneg_int(
                "CohortPopulationRow.generation_index", self.generation_index
            ),
        )
        object.__setattr__(
            self,
            "entry_tick",
            require_exact_nonneg_int(
                "CohortPopulationRow.entry_tick", self.entry_tick
            ),
        )
        object.__setattr__(
            self,
            "cohort_id",
            require_stable_id("CohortPopulationRow.cohort_id", self.cohort_id),
        )
        for name in ("admitted", "living", "dead"):
            object.__setattr__(
                self,
                name,
                require_exact_nonneg_int(
                    f"CohortPopulationRow.{name}", getattr(self, name)
                ),
            )
        if self.living + self.dead != self.admitted:
            raise ValueError(
                "cohort living+dead must equal admitted "
                "(code=cohort_population_inconsistent)"
            )


@dataclass(frozen=True, slots=True)
class GenerationPopulationRow:
    """One generation label's objective population totals."""

    generation_index: int
    admitted: int
    living: int
    dead: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "generation_index",
            require_exact_nonneg_int(
                "GenerationPopulationRow.generation_index", self.generation_index
            ),
        )
        for name in ("admitted", "living", "dead"):
            object.__setattr__(
                self,
                name,
                require_exact_nonneg_int(
                    f"GenerationPopulationRow.{name}", getattr(self, name)
                ),
            )
        if self.living + self.dead != self.admitted:
            raise ValueError(
                "generation living+dead must equal admitted "
                "(code=generation_population_inconsistent)"
            )


@dataclass(frozen=True, slots=True)
class PopulationProgress:
    """Detached post-finalization population progress at a boundary."""

    boundary_tick: int
    living_population: int
    total_admitted: int
    total_deaths: int
    max_generation_index_seen: int
    cohorts: tuple[CohortPopulationRow, ...] = ()
    generations: tuple[GenerationPopulationRow, ...] = ()

    def __post_init__(self) -> None:
        for name in (
            "boundary_tick",
            "living_population",
            "total_admitted",
            "total_deaths",
            "max_generation_index_seen",
        ):
            object.__setattr__(
                self,
                name,
                require_exact_nonneg_int(
                    f"PopulationProgress.{name}", getattr(self, name)
                ),
            )
        if isinstance(self.cohorts, (set, frozenset)):
            raise TypeError("PopulationProgress.cohorts must be ordered")
        cohorts = tuple(self.cohorts)
        for cohort_row in cohorts:
            if type(cohort_row) is not CohortPopulationRow:
                raise TypeError("cohorts entries must be CohortPopulationRow")
        ordered_cohorts = tuple(
            sorted(
                cohorts,
                key=lambda item: (
                    item.generation_index,
                    item.entry_tick,
                    item.cohort_id,
                ),
            )
        )
        if len({row.cohort_id for row in ordered_cohorts}) != len(
            ordered_cohorts
        ):
            raise ValueError("cohort_id values must be unique")
        object.__setattr__(self, "cohorts", ordered_cohorts)
        if isinstance(self.generations, (set, frozenset)):
            raise TypeError("PopulationProgress.generations must be ordered")
        generations = tuple(self.generations)
        for generation_row in generations:
            if type(generation_row) is not GenerationPopulationRow:
                raise TypeError(
                    "generations entries must be GenerationPopulationRow"
                )
        ordered_generations = tuple(
            sorted(generations, key=lambda item: item.generation_index)
        )
        if len({row.generation_index for row in ordered_generations}) != len(
            ordered_generations
        ):
            raise ValueError("generation_index values must be unique")
        object.__setattr__(self, "generations", ordered_generations)
        if ordered_generations:
            expected = (
                sum(row.admitted for row in ordered_generations),
                sum(row.living for row in ordered_generations),
                sum(row.dead for row in ordered_generations),
            )
            actual = (self.total_admitted, self.living_population, self.total_deaths)
            if expected != actual:
                raise ValueError(
                    "generation totals mismatch population progress "
                    "(code=population_progress_inconsistent)"
                )
        if ordered_cohorts:
            expected = (
                sum(row.admitted for row in ordered_cohorts),
                sum(row.living for row in ordered_cohorts),
                sum(row.dead for row in ordered_cohorts),
            )
            actual = (self.total_admitted, self.living_population, self.total_deaths)
            if expected != actual:
                raise ValueError(
                    "cohort totals mismatch population progress "
                    "(code=population_progress_inconsistent)"
                )
        if self.living_population + self.total_deaths != self.total_admitted:
            raise ValueError(
                "living+dead must equal total_admitted "
                "(code=population_progress_inconsistent)"
            )


@dataclass(frozen=True, slots=True)
class BoundaryEventFact:
    """One public detached objective event fact at a completed boundary."""

    event_id: str
    kind: str
    tick: int
    actor_id: str | None = None
    target_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "event_id",
            require_stable_id("BoundaryEventFact.event_id", self.event_id),
        )
        object.__setattr__(
            self,
            "kind",
            require_stable_id("BoundaryEventFact.kind", self.kind),
        )
        object.__setattr__(
            self,
            "tick",
            require_exact_nonneg_int("BoundaryEventFact.tick", self.tick),
        )
        if self.actor_id is not None:
            object.__setattr__(
                self,
                "actor_id",
                require_stable_id("BoundaryEventFact.actor_id", self.actor_id),
            )
        if self.target_id is not None:
            object.__setattr__(
                self,
                "target_id",
                require_stable_id(
                    "BoundaryEventFact.target_id", self.target_id
                ),
            )


@dataclass(frozen=True, slots=True)
class GenerationalBoundary:
    """Committed/finalized boundary identity used by stop evidence."""

    progress: PopulationProgress
    objective_revision: int
    last_completed_tick: int | None = None
    objective_commit_id: str | None = None
    event_facts: tuple[BoundaryEventFact, ...] = ()

    def __post_init__(self) -> None:
        if type(self.progress) is not PopulationProgress:
            raise TypeError("progress must be PopulationProgress")
        object.__setattr__(
            self,
            "objective_revision",
            require_exact_nonneg_int(
                "GenerationalBoundary.objective_revision", self.objective_revision
            ),
        )
        if self.progress.boundary_tick == 0:
            if self.last_completed_tick is not None:
                raise ValueError(
                    "boundary_tick 0 forbids last_completed_tick "
                    "(code=boundary_tick_inconsistent)"
                )
        else:
            expected_tick = self.progress.boundary_tick - 1
            if self.last_completed_tick != expected_tick:
                raise ValueError(
                    "last_completed_tick must equal boundary_tick-1 "
                    "(code=boundary_tick_inconsistent)"
                )
        if self.objective_commit_id is not None:
            object.__setattr__(
                self,
                "objective_commit_id",
                require_stable_id(
                    "GenerationalBoundary.objective_commit_id",
                    self.objective_commit_id,
                ),
            )
        if isinstance(self.event_facts, (set, frozenset)):
            raise TypeError("event_facts must be ordered")
        facts = tuple(self.event_facts)
        for fact in facts:
            if type(fact) is not BoundaryEventFact:
                raise TypeError("event_facts entries must be BoundaryEventFact")
        if facts and self.last_completed_tick is None:
            raise ValueError(
                "event facts require a completed tick "
                "(code=boundary_tick_inconsistent)"
            )
        if any(fact.tick != self.last_completed_tick for fact in facts):
            raise ValueError(
                "event facts must match the last completed tick "
                "(code=boundary_tick_inconsistent)"
            )
        ordered_facts = tuple(sorted(facts, key=lambda item: item.event_id))
        if len({fact.event_id for fact in ordered_facts}) != len(ordered_facts):
            raise ValueError("event_id values must be unique")
        object.__setattr__(self, "event_facts", ordered_facts)


@dataclass(frozen=True, slots=True)
class StopEvidence:
    """Ordered stop/criterion evidence retained outside objective replay."""

    boundary: GenerationalBoundary
    matched_condition_codes: tuple[str, ...] = ()
    primary_condition_code: str = ""
    matched_criteria: tuple[ExperimentCriterionIdentity, ...] = ()
    criterion_evaluation_status: ExperimentCriterionEvaluationStatus = (
        ExperimentCriterionEvaluationStatus.NOT_CONFIGURED
    )
    failed_stage: str | None = None
    failure_reason_code: str | None = None
    measurements: Mapping[str, object] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        if type(self.boundary) is not GenerationalBoundary:
            raise TypeError("boundary must be GenerationalBoundary")
        if isinstance(self.matched_condition_codes, (str, bytes)) or not isinstance(
            self.matched_condition_codes, Sequence
        ):
            raise TypeError("matched_condition_codes must be a sequence")
        codes = tuple(
            require_stable_id("matched_condition_code", code)
            for code in self.matched_condition_codes
        )
        if len(set(codes)) != len(codes):
            raise ValueError(
                "matched_condition_codes must be unique "
                "(code=stop_evidence_inconsistent)"
            )
        object.__setattr__(self, "matched_condition_codes", codes)
        primary = require_stable_id(
            "StopEvidence.primary_condition_code", self.primary_condition_code
        )
        if codes and primary not in codes:
            raise ValueError(
                "primary_condition_code must be among matched condition codes "
                "(code=stop_evidence_inconsistent)"
            )
        object.__setattr__(self, "primary_condition_code", primary)
        if type(self.criterion_evaluation_status) is not (
            ExperimentCriterionEvaluationStatus
        ):
            raise TypeError(
                "criterion_evaluation_status must be "
                "ExperimentCriterionEvaluationStatus"
            )
        if isinstance(self.matched_criteria, (set, frozenset)):
            raise TypeError("matched_criteria must be ordered")
        criteria = tuple(self.matched_criteria)
        for item in criteria:
            if type(item) is not ExperimentCriterionIdentity:
                raise TypeError(
                    "matched_criteria entries must be ExperimentCriterionIdentity"
                )
        ordered = tuple(sorted(criteria, key=lambda item: item.identity))
        if len({item.identity for item in ordered}) != len(ordered):
            raise ValueError(
                "matched_criteria identities must be unique "
                "(code=stop_evidence_inconsistent)"
            )
        object.__setattr__(self, "matched_criteria", ordered)
        if self.failed_stage is not None:
            object.__setattr__(
                self,
                "failed_stage",
                require_stable_id("StopEvidence.failed_stage", self.failed_stage),
            )
        if self.failure_reason_code is not None:
            object.__setattr__(
                self,
                "failure_reason_code",
                require_stable_id(
                    "StopEvidence.failure_reason_code", self.failure_reason_code
                ),
            )
        if isinstance(self.measurements, (str, bytes)) or not isinstance(
            self.measurements, Mapping
        ):
            raise TypeError("measurements must be a mapping")
        measurements: dict[str, object] = {}
        for key, value in self.measurements.items():
            require_stable_id("StopEvidence.measurements key", key)
            if type(value) not in (bool, int, float):
                raise TypeError(
                    "StopEvidence.measurements values must be finite numbers or bool"
                )
            if type(value) is float and not math.isfinite(value):
                raise ValueError(
                    "StopEvidence.measurements values must be finite "
                    "(code=stop_evidence_inconsistent)"
                )
            measurements[key] = value
        object.__setattr__(self, "measurements", MappingProxyType(measurements))
        _LOGGER.debug(
            "stop_evidence_validated boundary_tick=%s primary_condition_code=%s "
            "matched_condition_count=%s matched_criterion_count=%s "
            "criterion_status=%s failed_stage=%s",
            self.boundary.progress.boundary_tick,
            primary,
            len(codes),
            len(ordered),
            self.criterion_evaluation_status.value,
            self.failed_stage,
        )


@dataclass(frozen=True, slots=True)
class GenerationalRunSpec:
    """Closed opt-in multi-generation run configuration."""

    max_generation_index: int | None = None
    stop_on_extinction: bool = True
    population_threshold: PopulationThresholdSpec | None = None
    experiment_criteria: tuple[ExperimentCriterionSpec, ...] = ()
    criterion_cadence_ticks: int = 1
    historical_checkpoint_cadence_ticks: int | None = None
    sample_on_generation_change: bool = True

    def __post_init__(self) -> None:
        if self.max_generation_index is not None:
            object.__setattr__(
                self,
                "max_generation_index",
                _require_positive_int(
                    "GenerationalRunSpec.max_generation_index",
                    self.max_generation_index,
                ),
            )
        object.__setattr__(
            self,
            "stop_on_extinction",
            _require_bool(
                "GenerationalRunSpec.stop_on_extinction", self.stop_on_extinction
            ),
        )
        if self.population_threshold is not None and (
            type(self.population_threshold) is not PopulationThresholdSpec
        ):
            raise TypeError(
                "population_threshold must be PopulationThresholdSpec or None"
            )
        if isinstance(self.experiment_criteria, (set, frozenset)):
            raise TypeError("experiment_criteria must be ordered")
        criteria = tuple(self.experiment_criteria)
        for criterion in criteria:
            if type(criterion) is not ExperimentCriterionSpec:
                raise TypeError(
                    "experiment_criteria entries must be ExperimentCriterionSpec"
                )
        identities = [criterion.identity for criterion in criteria]
        if len(set(identities)) != len(identities):
            raise ValueError(
                "experiment criterion identities must be unique "
                "(code=experiment_criteria_duplicate_id)"
            )
        object.__setattr__(self, "experiment_criteria", criteria)
        object.__setattr__(
            self,
            "criterion_cadence_ticks",
            _require_positive_int(
                "GenerationalRunSpec.criterion_cadence_ticks",
                self.criterion_cadence_ticks,
            ),
        )
        if self.historical_checkpoint_cadence_ticks is not None:
            object.__setattr__(
                self,
                "historical_checkpoint_cadence_ticks",
                _require_positive_int(
                    "GenerationalRunSpec.historical_checkpoint_cadence_ticks",
                    self.historical_checkpoint_cadence_ticks,
                ),
            )
        object.__setattr__(
            self,
            "sample_on_generation_change",
            _require_bool(
                "GenerationalRunSpec.sample_on_generation_change",
                self.sample_on_generation_change,
            ),
        )
        _LOGGER.debug(
            "generational_run_spec_validated policy_version=%s "
            "max_generation_index=%s stop_on_extinction=%s "
            "criterion_count=%s criterion_cadence_ticks=%s "
            "historical_checkpoint_cadence_ticks=%s "
            "sample_on_generation_change=%s",
            GENERATIONAL_RUN_POLICY_VERSION,
            self.max_generation_index,
            self.stop_on_extinction,
            len(criteria),
            self.criterion_cadence_ticks,
            self.historical_checkpoint_cadence_ticks,
            self.sample_on_generation_change,
        )


def criterion_status_value(value: object) -> str:
    """Validate a serialized custom-criterion status token."""
    if type(value) is not str or value not in _CRITERION_STATUS_VALUES:
        raise ValueError("unknown criterion evaluation status")
    return value


__all__ = [
    "GENERATIONAL_RUN_POLICY_VERSION",
    "BoundaryEventFact",
    "CohortPopulationRow",
    "ExperimentCriterionEvaluationStatus",
    "ExperimentCriterionIdentity",
    "ExperimentCriterionSpec",
    "GenerationPopulationRow",
    "GenerationalBoundary",
    "GenerationalRunSpec",
    "PopulationProgress",
    "PopulationThresholdComparison",
    "PopulationThresholdSpec",
    "StopEvidence",
    "criterion_status_value",
    "freeze_json_value",
]
