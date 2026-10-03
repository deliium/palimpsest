"""Expand experiment-matrix-v1 specs into ExperimentDefinition + MatrixCell."""

from __future__ import annotations

import hashlib
import itertools
import logging
from typing import Final

from experiments.matrix_factors import apply_factor_levels
from experiments.matrix_models import (
    EXPERIMENT_MATRIX_SCHEMA_VERSION,
    ExperimentMatrixSpec,
    GroupRole,
    MatrixCatalogBase,
    MatrixCell,
    MatrixEmbeddedBase,
    MatrixValidationError,
    cell_factor_fingerprint,
    config_fingerprint_for_cell,
    matrix_spec_fingerprint,
)
from experiments.matrix_schema import finalize_matrix_cell_config
from experiments.models import (
    EXPERIMENT_SCHEMA_VERSION,
    ExperimentCondition,
    ExperimentDefinition,
)
from simulation.runner_models import SimulationRunnerConfig
from world.identifiers import require_stable_id

_LOG: Final[logging.Logger] = logging.getLogger("experiments.matrix_expand")

_CONDITION_ID_MAX = 128


def _resolve_base(spec: ExperimentMatrixSpec) -> SimulationRunnerConfig:
    if type(spec.base) is MatrixEmbeddedBase:
        return spec.base.runner_config
    if type(spec.base) is MatrixCatalogBase:
        raise MatrixValidationError(
            "catalog_base_unresolved",
            "catalog base builders are not resolved in expand_matrix; "
            "embed a SimulationRunnerConfig instead",
        )
    raise TypeError("unsupported matrix base")


def _combo_excluded(
    levels: tuple[tuple[str, str], ...],
    exclude: tuple[tuple[str, str], ...],
) -> bool:
    selected = dict(levels)
    return all(selected.get(factor_id) == level_id for factor_id, level_id in exclude)


def _compose_group_role(
    spec: ExperimentMatrixSpec,
    levels: tuple[tuple[str, str], ...],
    level_roles: tuple[GroupRole, ...],
) -> GroupRole:
    selected = dict(levels)
    for overlay in spec.groups:
        match = dict(overlay.level_match)
        if all(selected.get(fid) == lid for fid, lid in match.items()):
            return overlay.group_role
    if any(role is GroupRole.TREATMENT for role in level_roles):
        return GroupRole.TREATMENT
    if any(role is GroupRole.CONTROL for role in level_roles):
        return GroupRole.CONTROL
    return GroupRole.NEUTRAL


def _condition_id_for(levels: tuple[tuple[str, str], ...]) -> str:
    raw = "__".join(f"{factor_id}-{level_id}" for factor_id, level_id in levels)
    if len(raw) <= _CONDITION_ID_MAX:
        try:
            return require_stable_id("condition_id", raw)
        except ValueError:
            pass
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
    shortened = f"cond-{digest}"
    _LOG.warning(
        "matrix_condition_id_hash_fallback",
        extra={
            "experiment": {
                "condition_id_prefix": shortened,
                "raw_length": len(raw),
            }
        },
    )
    return require_stable_id("condition_id", shortened)


def expand_matrix(
    spec: ExperimentMatrixSpec,
) -> tuple[ExperimentDefinition, tuple[MatrixCell, ...]]:
    """Expand factors x seeds x replicates into definition + cells."""
    if type(spec) is not ExperimentMatrixSpec:
        raise TypeError("spec must be ExperimentMatrixSpec")
    if spec.schema_version != EXPERIMENT_MATRIX_SCHEMA_VERSION:
        raise MatrixValidationError(
            "unsupported_matrix_schema",
            "unsupported experiment matrix schema_version",
        )

    base = _resolve_base(spec)
    factor_level_lists: list[list[tuple[str, str, GroupRole]]] = []
    for factor in spec.factors:
        factor_level_lists.append(
            [
                (factor.factor_id.value, level.level_id, level.group_role)
                for level in factor.levels
            ]
        )

    raw_combos = list(itertools.product(*factor_level_lists))
    conditions_data: list[
        tuple[str, GroupRole, tuple[tuple[str, str], ...], SimulationRunnerConfig]
    ] = []
    for combo in raw_combos:
        levels = tuple((factor_id, level_id) for factor_id, level_id, _role in combo)
        excluded = any(
            _combo_excluded(levels, exclude.levels)
            for exclude in spec.constraints.exclude_combos
        )
        if excluded:
            continue
        roles = tuple(role for _fid, _lid, role in combo)
        group_role = _compose_group_role(spec, levels, roles)
        applied = apply_factor_levels(base, levels)
        finalized = finalize_matrix_cell_config(applied)
        condition_id = _condition_id_for(levels)
        conditions_data.append((condition_id, group_role, levels, finalized))

    if len(conditions_data) < 2:
        _LOG.error(
            "matrix_expand_too_few_conditions",
            extra={
                "experiment": {
                    "matrix_id": spec.matrix_id,
                    "condition_count": len(conditions_data),
                    "reason_code": "fewer_than_two_conditions",
                }
            },
        )
        raise MatrixValidationError(
            "fewer_than_two_conditions",
            "matrix expansion requires at least two conditions after constraints",
        )

    # Deduplicate condition ids fail closed.
    seen_ids: set[str] = set()
    for condition_id, _role, _levels, _cfg in conditions_data:
        if condition_id in seen_ids:
            raise MatrixValidationError(
                "duplicate_condition_id",
                f"duplicate condition_id after expansion: {condition_id}",
            )
        seen_ids.add(condition_id)

    definition = ExperimentDefinition(
        experiment_id=spec.matrix_id,
        schema_version=EXPERIMENT_SCHEMA_VERSION,
        seed_matrix=spec.seed_matrix,
        conditions=tuple(
            ExperimentCondition(
                condition_id=condition_id,
                label_code=condition_id,
                runner_config=config,
            )
            for condition_id, _role, _levels, config in conditions_data
        ),
        paired_world_group=f"{spec.matrix_id}-world",
    )

    matrix_fp = matrix_spec_fingerprint(spec)
    cells: list[MatrixCell] = []
    ordinal = 0
    for condition_id, group_role, levels, config in conditions_data:
        cell_fp = cell_factor_fingerprint(
            condition_id=condition_id,
            factor_levels=levels,
            group_role=group_role,
        )
        cfg_fp = config_fingerprint_for_cell(config)
        for seed_ordinal, seed in enumerate(spec.seed_matrix.seeds):
            for replicate_index in range(spec.seed_matrix.replicates_per_seed):
                cell_id = (
                    f"{spec.matrix_id}-{condition_id}"
                    f"-s{seed_ordinal}-r{replicate_index}"
                )
                if len(cell_id) > 128:
                    digest = hashlib.sha256(cell_id.encode("utf-8")).hexdigest()[:16]
                    cell_id = f"cell-{digest}"
                cells.append(
                    MatrixCell(
                        cell_id=cell_id,
                        condition_id=condition_id,
                        factor_levels=levels,
                        group_role=group_role,
                        seed=seed,
                        seed_ordinal=seed_ordinal,
                        replicate_index=replicate_index,
                        cell_fingerprint=cell_fp,
                        config_fingerprint=cfg_fp,
                    )
                )
                _LOG.debug(
                    "matrix_cell_expanded",
                    extra={
                        "experiment": {
                            "matrix_id": spec.matrix_id,
                            "ordinal": ordinal,
                            "condition_id_prefix": condition_id[:32],
                            "matrix_fingerprint_prefix": matrix_fp[:12],
                        }
                    },
                )
                ordinal += 1

    _LOG.info(
        "matrix_expanded",
        extra={
            "experiment": {
                "matrix_id": spec.matrix_id,
                "condition_count": len(conditions_data),
                "cell_count": len(cells),
                "factor_count": len(spec.factors),
            }
        },
    )
    return definition, tuple(cells)


__all__ = ["expand_matrix"]
