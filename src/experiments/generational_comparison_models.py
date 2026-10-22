"""Closed generational-comparison axis and level contracts.

These contracts are experiment metadata only. They never grant world
authority, mutate a runner schema, or install a comparison into cognition.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from experiments.models import ExperimentSeedMatrix
from simulation.runner_models import SimulationRunnerConfig
from world.identifiers import require_stable_id

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.generational_comparison_models"
)


class GenerationalComparisonAxis(StrEnum):
    """Closed population-level comparison axes."""

    LIFESPAN = "lifespan"
    LEARNING_MODEL = "learning_model"
    TEACHING_FREQUENCY = "teaching_frequency"
    RECORD_AVAILABILITY = "record_availability"
    MEMORY_ARCHITECTURE = "memory_architecture"
    INNOVATION_RATE = "innovation_rate"
    MIGRATION = "migration"
    RESOURCE_SCARCITY = "resource_scarcity"
    POPULATION_SIZE = "population_size"
    INSTITUTION_SUPPORT = "institution_support"
    COGNITIVE_ARCHITECTURE = "cognitive_architecture"


AXIS_LEVEL_IDS: Final[Mapping[GenerationalComparisonAxis, frozenset[str]]] = {
    GenerationalComparisonAxis.LIFESPAN: frozenset({"short", "long"}),
    GenerationalComparisonAxis.LEARNING_MODEL: frozenset(
        {"practice_only", "teaching_supported"}
    ),
    GenerationalComparisonAxis.TEACHING_FREQUENCY: frozenset({"low", "high"}),
    GenerationalComparisonAxis.RECORD_AVAILABILITY: frozenset({"absent", "present"}),
    GenerationalComparisonAxis.MEMORY_ARCHITECTURE: frozenset(
        {"reference", "reconstructive"}
    ),
    GenerationalComparisonAxis.INNOVATION_RATE: frozenset({"low", "high"}),
    GenerationalComparisonAxis.MIGRATION: frozenset({"isolated", "connected"}),
    GenerationalComparisonAxis.RESOURCE_SCARCITY: frozenset({"scarce", "abundant"}),
    GenerationalComparisonAxis.POPULATION_SIZE: frozenset({"small", "large"}),
    GenerationalComparisonAxis.INSTITUTION_SUPPORT: frozenset({"off", "on"}),
    GenerationalComparisonAxis.COGNITIVE_ARCHITECTURE: frozenset(
        {"v1_memory", "full_v2"}
    ),
}


class GenerationalComparisonError(ValueError):
    """Fail-closed generational comparison validation with a stable code."""

    def __init__(self, code: str, message: str = "") -> None:
        self.code = code
        detail = message or code
        super().__init__(detail)
        _LOG.warning(
            "generational_comparison_invalid",
            extra={"experiment": {"reason_code": code}},
        )


def require_comparison_axis(value: object) -> GenerationalComparisonAxis:
    """Resolve a closed axis from its enum or string value."""
    if type(value) is GenerationalComparisonAxis:
        return value
    if type(value) is str:
        try:
            return GenerationalComparisonAxis(value)
        except ValueError as exc:
            raise GenerationalComparisonError(
                "unknown_axis", f"unknown comparison axis: {value}"
            ) from exc
    raise GenerationalComparisonError("invalid_type", "axis must be an enum or str")


def _require_level(axis: GenerationalComparisonAxis, level_id: object) -> str:
    if type(level_id) is not str:
        raise GenerationalComparisonError("invalid_type", "level_id must be str")
    if level_id not in AXIS_LEVEL_IDS[axis]:
        raise GenerationalComparisonError(
            "unknown_level", f"unknown level {level_id!r} for axis {axis.value}"
        )
    return require_stable_id("level_id", level_id)


def _require_label(value: object) -> str:
    if type(value) is not str:
        raise GenerationalComparisonError("invalid_type", "label_code must be str")
    return require_stable_id("label_code", value)


@dataclass(frozen=True, slots=True)
class GenerationalAxisLevel:
    """One declared level on a closed comparison axis."""

    axis: GenerationalComparisonAxis
    level_id: str
    label_code: str

    def __post_init__(self) -> None:
        axis = require_comparison_axis(self.axis)
        object.__setattr__(self, "axis", axis)
        object.__setattr__(self, "level_id", _require_level(axis, self.level_id))
        object.__setattr__(self, "label_code", _require_label(self.label_code))


@dataclass(frozen=True, slots=True)
class GenerationalComparison:
    """One control/treatment pair over a single closed axis."""

    comparison_id: str
    axis: GenerationalComparisonAxis
    control_level_id: str
    treatment_level_id: str
    label_code: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "comparison_id",
            require_stable_id("comparison_id", self.comparison_id),
        )
        axis = require_comparison_axis(self.axis)
        object.__setattr__(self, "axis", axis)
        control = _require_level(axis, self.control_level_id)
        treatment = _require_level(axis, self.treatment_level_id)
        if control == treatment:
            raise GenerationalComparisonError(
                "identical_levels", "control and treatment levels must differ"
            )
        object.__setattr__(self, "control_level_id", control)
        object.__setattr__(self, "treatment_level_id", treatment)
        object.__setattr__(self, "label_code", _require_label(self.label_code))


@dataclass(frozen=True, slots=True)
class GenerationalComparisonSpec:
    """Ordered independent comparison pairs over one shared v55 base."""

    experiment_id: str
    base: SimulationRunnerConfig
    comparisons: tuple[GenerationalComparison, ...]
    seed_matrix: ExperimentSeedMatrix
    max_ticks: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "experiment_id",
            require_stable_id("experiment_id", self.experiment_id),
        )
        if type(self.base) is not SimulationRunnerConfig:
            raise GenerationalComparisonError(
                "invalid_type", "base must be SimulationRunnerConfig"
            )
        if type(self.seed_matrix) is not ExperimentSeedMatrix:
            raise GenerationalComparisonError(
                "invalid_type", "seed_matrix must be ExperimentSeedMatrix"
            )
        if (
            type(self.max_ticks) is not int
            or isinstance(self.max_ticks, bool)
            or self.max_ticks <= 0
        ):
            raise GenerationalComparisonError(
                "invalid_max_ticks", "max_ticks must be a positive int"
            )
        if isinstance(self.comparisons, (set, frozenset)):
            raise GenerationalComparisonError(
                "invalid_type", "comparisons must be ordered"
            )
        if isinstance(self.comparisons, (str, bytes)) or not isinstance(
            self.comparisons, Sequence
        ):
            raise GenerationalComparisonError(
                "invalid_type", "comparisons must be an ordered sequence"
            )
        comparisons = tuple(self.comparisons)
        if not comparisons:
            raise GenerationalComparisonError(
                "invalid_type", "comparisons must be non-empty"
            )
        seen_ids: set[str] = set()
        seen_axes: set[GenerationalComparisonAxis] = set()
        for comparison in comparisons:
            if type(comparison) is not GenerationalComparison:
                raise GenerationalComparisonError(
                    "invalid_type", "comparisons entries must be GenerationalComparison"
                )
            if comparison.comparison_id in seen_ids:
                raise GenerationalComparisonError(
                    "duplicate_comparison_id",
                    f"duplicate comparison_id: {comparison.comparison_id}",
                )
            seen_ids.add(comparison.comparison_id)
            if comparison.axis in seen_axes:
                raise GenerationalComparisonError(
                    "duplicate_axis", f"duplicate axis: {comparison.axis.value}"
                )
            seen_axes.add(comparison.axis)
        object.__setattr__(self, "comparisons", comparisons)
        _LOG.info(
            "generational_comparison_spec_built experiment_id=%s comparison_count=%s "
            "axis_count=%s max_ticks=%s",
            self.experiment_id,
            len(comparisons),
            len(seen_axes),
            self.max_ticks,
        )


__all__ = [
    "AXIS_LEVEL_IDS",
    "GenerationalAxisLevel",
    "GenerationalComparison",
    "GenerationalComparisonAxis",
    "GenerationalComparisonError",
    "GenerationalComparisonSpec",
    "require_comparison_axis",
]
