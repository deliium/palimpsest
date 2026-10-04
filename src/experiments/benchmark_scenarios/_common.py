"""Shared helpers for thin benchmark scenario builders."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace

from experiments.models import (
    EXPERIMENT_SCHEMA_VERSION,
    ExperimentCondition,
    ExperimentDefinition,
    ExperimentSeedMatrix,
)


def filter_conditions(
    source: ExperimentDefinition,
    condition_ids: Sequence[str],
    *,
    experiment_id: str,
    paired_world_group: str | None = None,
    seed_matrix: ExperimentSeedMatrix | None = None,
) -> ExperimentDefinition:
    """Return a new definition keeping only the requested condition ids (ordered)."""
    by_id = {item.condition_id: item for item in source.conditions}
    missing = [item for item in condition_ids if item not in by_id]
    if missing:
        raise ValueError(f"missing_condition_ids:{','.join(missing)}")
    conditions: tuple[ExperimentCondition, ...] = tuple(
        by_id[item] for item in condition_ids
    )
    return ExperimentDefinition(
        experiment_id=experiment_id,
        schema_version=EXPERIMENT_SCHEMA_VERSION,
        seed_matrix=seed_matrix or source.seed_matrix,
        conditions=conditions,
        paired_world_group=paired_world_group or f"{experiment_id}-world",
    )


def with_seed_matrix(
    definition: ExperimentDefinition,
    seed_matrix: ExperimentSeedMatrix | None,
) -> ExperimentDefinition:
    if seed_matrix is None:
        return definition
    return replace(definition, seed_matrix=seed_matrix)
