"""Typed grouped-only discovery for historical-contingency experiments."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Final

from experiments.path_dependence_models import (
    PATH_DEPENDENCE_EXPERIMENT_ID,
    PathDependenceSpec,
)
from world.identifiers import require_stable_id

GROUPED_EXECUTION_KIND_PATH_DEPENDENCE: Final[str] = "path_dependence"


class GroupedExecutionRequired(ValueError):
    """Raised when a grouped experiment is routed through independent cells."""

    def __init__(self, experiment_id: str) -> None:
        self.code = "grouped_execution_required"
        self.experiment_id = experiment_id
        super().__init__(f"grouped_execution_required: {experiment_id}")


@dataclass(frozen=True, slots=True)
class GroupedExperimentRegistration:
    """Catalog metadata that never widens ``ExperimentDefinition``."""

    experiment_id: str
    label_code: str
    execution_kind: str = GROUPED_EXECUTION_KIND_PATH_DEPENDENCE

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "experiment_id",
            require_stable_id("experiment_id", self.experiment_id),
        )
        object.__setattr__(
            self, "label_code", require_stable_id("label_code", self.label_code)
        )
        if self.execution_kind != GROUPED_EXECUTION_KIND_PATH_DEPENDENCE:
            raise ValueError("unsupported grouped execution_kind")


BN_HISTORICAL_CONTINGENCY = GroupedExperimentRegistration(
    experiment_id=PATH_DEPENDENCE_EXPERIMENT_ID,
    label_code="BN",
)

GROUPED_EXPERIMENT_REGISTRY: Final[Mapping[str, GroupedExperimentRegistration]] = {
    PATH_DEPENDENCE_EXPERIMENT_ID: BN_HISTORICAL_CONTINGENCY,
}
GROUPED_EXPERIMENT_IDS: Final[frozenset[str]] = frozenset(
    GROUPED_EXPERIMENT_REGISTRY
)

PathDependenceBuilder = Callable[..., PathDependenceSpec]
PATH_DEPENDENCE_BUILDERS: dict[str, PathDependenceBuilder] = {}


def register_path_dependence_builder(
    experiment_id: str, builder: PathDependenceBuilder
) -> None:
    experiment_id = require_stable_id("experiment_id", experiment_id)
    if experiment_id not in GROUPED_EXPERIMENT_IDS:
        raise ValueError("unknown grouped experiment")
    if not callable(builder):
        raise TypeError("builder must be callable")
    PATH_DEPENDENCE_BUILDERS[experiment_id] = builder


def require_independent_execution(experiment_id: str) -> None:
    """Reject grouped experiments before independent assignment/write paths."""
    if type(experiment_id) is not str:
        raise TypeError("experiment_id must be str")
    if experiment_id in GROUPED_EXPERIMENT_IDS:
        raise GroupedExecutionRequired(experiment_id)


def grouped_experiment_id_from_matrix_base(base: object) -> str | None:
    """Return a grouped experiment id from a matrix base, if one is declared."""
    from experiments.matrix_models import MatrixCatalogBase, MatrixEmbeddedBase

    if isinstance(base, MatrixEmbeddedBase):
        experiment = base.runner_config.experiment
        return None if experiment is None else experiment.experiment_id
    if isinstance(base, MatrixCatalogBase):
        if base.builder_id in GROUPED_EXPERIMENT_IDS:
            return base.builder_id
        for key, value in base.params:
            if key == "experiment_id" and isinstance(value, str):
                return value
    return None


__all__ = [
    "BN_HISTORICAL_CONTINGENCY",
    "GROUPED_EXECUTION_KIND_PATH_DEPENDENCE",
    "GROUPED_EXPERIMENT_IDS",
    "GROUPED_EXPERIMENT_REGISTRY",
    "GroupedExecutionRequired",
    "GroupedExperimentRegistration",
    "PathDependenceBuilder",
    "grouped_experiment_id_from_matrix_base",
    "register_path_dependence_builder",
    "require_independent_execution",
]
