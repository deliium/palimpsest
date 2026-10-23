"""Grouped-only discovery and independent-execution rejection."""

from __future__ import annotations

import pytest

from experiments.coordinator import ExperimentCoordinator
from experiments.generational_comparison_base import generational_comparison_base
from experiments.matrix_models import MatrixEmbeddedBase
from experiments.models import (
    ExperimentCondition,
    ExperimentDefinition,
    ExperimentSeedMatrix,
)
from experiments.path_dependence_catalog import (
    GROUPED_EXPERIMENT_IDS,
    GroupedExecutionRequired,
    grouped_experiment_id_from_matrix_base,
    require_independent_execution,
)
from experiments.path_dependence_models import PATH_DEPENDENCE_EXPERIMENT_ID
from simulation.runner_models import ExperimentAssignmentRef

pytestmark = pytest.mark.unit


def test_grouped_ids_are_typed_and_rejected_independently() -> None:
    assert PATH_DEPENDENCE_EXPERIMENT_ID in GROUPED_EXPERIMENT_IDS
    with pytest.raises(GroupedExecutionRequired) as exc:
        require_independent_execution(PATH_DEPENDENCE_EXPERIMENT_ID)
    assert exc.value.code == "grouped_execution_required"
    require_independent_execution("reference-v1")


def test_matrix_base_grouped_identity_is_detected() -> None:
    config = generational_comparison_base(seed=23, max_ticks=8)
    config = config.__class__(
        **{
            **{
                field: getattr(config, field)
                for field in config.__dataclass_fields__
            },
            "experiment": ExperimentAssignmentRef(
                experiment_id=PATH_DEPENDENCE_EXPERIMENT_ID,
                condition_id="share",
            ),
        }
    )
    base = MatrixEmbeddedBase(config)
    assert grouped_experiment_id_from_matrix_base(base) == (
        PATH_DEPENDENCE_EXPERIMENT_ID
    )


@pytest.mark.asyncio
async def test_coordinator_rejects_grouped_definition_before_assignments() -> None:
    config = generational_comparison_base(seed=23, max_ticks=8)
    definition = ExperimentDefinition(
        experiment_id=PATH_DEPENDENCE_EXPERIMENT_ID,
        schema_version="experiment-definition-v1",
        seed_matrix=ExperimentSeedMatrix(seeds=(23,)),
        conditions=(
            ExperimentCondition("share", "SHARE", config),
            ExperimentCondition("withhold", "WITHHOLD", config),
        ),
        paired_world_group="bn-pair",
    )
    coordinator = ExperimentCoordinator(definition)
    with pytest.raises(GroupedExecutionRequired):
        await coordinator.run_all()
