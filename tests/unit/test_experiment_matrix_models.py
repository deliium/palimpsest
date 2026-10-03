"""Unit tests for experiment-matrix-v1 contracts."""

from __future__ import annotations

import pytest

from agents.models import AgentId
from experiments.catalog import base_runner_config_from_scenario
from experiments.matrix_models import (
    DEFAULT_SUCCESS_STOP_REASONS,
    EXPERIMENT_MATRIX_SCHEMA_VERSION,
    ExperimentMatrixSpec,
    GroupRole,
    MatrixCell,
    MatrixConstraints,
    MatrixEmbeddedBase,
    MatrixExcludeCombo,
    MatrixExecutionPolicy,
    MatrixFactor,
    MatrixFactorId,
    MatrixFactorLevel,
    MatrixValidationError,
    RetryPolicy,
    RunVersionIdentity,
    cell_factor_fingerprint,
    matrix_spec_fingerprint,
)
from experiments.models import ExperimentSeedMatrix
from simulation.runner_models import (
    AgentCognitionSpec,
    AgentRunnerSpec,
    RunnerStopReasonCode,
    WorldScenarioSpec,
)
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.identifiers import WorldId, WorldRevision
from world.models import default_physical_rules


def _base_config():
    body = alive_body("body-1")
    agent_id = AgentId("agent-1")
    return base_runner_config_from_scenario(
        seed=7,
        stochastic_identity="cmp-matrix",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-1"),
            revision=WorldRevision(0),
            physical_rules=default_physical_rules(),
            locations=(make_location(),),
            bodies=(body,),
            weather=(make_weather(),),
        ),
        agents=(
            AgentRunnerSpec(
                agent_id=agent_id,
                entity_id=body.entity_id,
                cognition=AgentCognitionSpec(agent_id=agent_id),
            ),
        ),
        max_ticks=2,
    )


def _minimal_spec(**overrides: object) -> ExperimentMatrixSpec:
    kwargs: dict[str, object] = {
        "matrix_id": "matrix-demo",
        "schema_version": EXPERIMENT_MATRIX_SCHEMA_VERSION,
        "base": MatrixEmbeddedBase(runner_config=_base_config()),
        "factors": (
            MatrixFactor(
                factor_id=MatrixFactorId.MEMORY_TYPE,
                levels=(
                    MatrixFactorLevel(
                        level_id="reference",
                        label_code="mem_ref",
                        group_role=GroupRole.CONTROL,
                    ),
                    MatrixFactorLevel(
                        level_id="reconstructive",
                        label_code="mem_recon",
                        group_role=GroupRole.TREATMENT,
                    ),
                ),
            ),
            MatrixFactor(
                factor_id=MatrixFactorId.MORTALITY,
                levels=(
                    MatrixFactorLevel(
                        level_id="disabled",
                        label_code="mort_off",
                        group_role=GroupRole.CONTROL,
                    ),
                    MatrixFactorLevel(
                        level_id="enabled",
                        label_code="mort_on",
                        group_role=GroupRole.TREATMENT,
                    ),
                ),
            ),
        ),
        "seed_matrix": ExperimentSeedMatrix(seeds=(7,)),
        "constraints": MatrixConstraints(),
        "execution": MatrixExecutionPolicy(),
        "groups": (),
    }
    kwargs.update(overrides)
    return ExperimentMatrixSpec(**kwargs)  # type: ignore[arg-type]


def test_default_success_stop_set() -> None:
    assert DEFAULT_SUCCESS_STOP_REASONS == (
        RunnerStopReasonCode.MAX_TICKS,
        RunnerStopReasonCode.ALL_AGENTS_TERMINAL,
        RunnerStopReasonCode.INJECTED_STOP,
    )


def test_matrix_spec_accepts_valid_grid() -> None:
    spec = _minimal_spec()
    assert spec.schema_version == EXPERIMENT_MATRIX_SCHEMA_VERSION
    assert len(spec.factors) == 2
    digest = matrix_spec_fingerprint(spec)
    assert len(digest) == 64
    assert matrix_spec_fingerprint(spec) == digest


def test_rejects_unknown_schema_version() -> None:
    with pytest.raises(MatrixValidationError) as exc:
        _minimal_spec(schema_version="experiment-matrix-v0")
    assert exc.value.code == "unsupported_matrix_schema"


def test_rejects_duplicate_factor_ids() -> None:
    factor = MatrixFactor(
        factor_id=MatrixFactorId.TOM,
        levels=(
            MatrixFactorLevel(level_id="off", label_code="tom_off"),
            MatrixFactorLevel(level_id="on", label_code="tom_on"),
        ),
    )
    with pytest.raises(MatrixValidationError) as exc:
        _minimal_spec(factors=(factor, factor))
    assert exc.value.code == "duplicate_factor_id"


def test_rejects_unknown_level_id() -> None:
    with pytest.raises(MatrixValidationError) as exc:
        MatrixFactor(
            factor_id=MatrixFactorId.TOM,
            levels=(MatrixFactorLevel(level_id="maybe", label_code="tom_maybe"),),
        )
    assert exc.value.code == "unknown_level_id"


def test_rejects_empty_factors() -> None:
    with pytest.raises(MatrixValidationError) as exc:
        _minimal_spec(factors=())
    assert exc.value.code == "empty_factors"


def test_rejects_non_positive_concurrency() -> None:
    with pytest.raises(MatrixValidationError) as exc:
        MatrixExecutionPolicy(max_concurrency=0)
    assert exc.value.code == "invalid_max_concurrency"


def test_rejects_unknown_constraint_factor() -> None:
    with pytest.raises(MatrixValidationError) as exc:
        MatrixExcludeCombo(levels=(("not_a_factor", "on"),))
    assert exc.value.code == "unknown_constraint_factor"


def test_cell_and_version_identity() -> None:
    levels = (("memory_type", "reference"), ("mortality", "disabled"))
    cell_fp = cell_factor_fingerprint(
        condition_id="memory_type-reference__mortality-disabled",
        factor_levels=levels,
        group_role=GroupRole.CONTROL,
    )
    cell = MatrixCell(
        cell_id="cell-0",
        condition_id="memory_type-reference__mortality-disabled",
        factor_levels=levels,
        group_role=GroupRole.CONTROL,
        seed=7,
        seed_ordinal=0,
        replicate_index=0,
        cell_fingerprint=cell_fp,
        config_fingerprint="a" * 64,
    )
    assert cell.group_role is GroupRole.CONTROL
    identity = RunVersionIdentity(
        package_version="0.0.0",
        runner_schema_version="runner-config-v4",
        experiment_schema_version="experiment-definition-v1",
        matrix_schema_version=EXPERIMENT_MATRIX_SCHEMA_VERSION,
        derivation_version="derivation-v1",
        matrix_fingerprint="b" * 64,
        cell_fingerprint=cell_fp,
        config_fingerprint="a" * 64,
        code_revision="",
    )
    assert identity.code_revision == ""


def test_retry_policy_rejects_duplicates() -> None:
    with pytest.raises(MatrixValidationError) as exc:
        RetryPolicy(transient_reason_codes=("timeout", "timeout"))
    assert exc.value.code == "duplicate_transient_code"
