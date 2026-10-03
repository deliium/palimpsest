"""Unit tests for experiment-matrix-v1 canonical JSON codecs."""

from __future__ import annotations

import json

import pytest

from agents.models import AgentId
from experiments.catalog import base_runner_config_from_scenario
from experiments.matrix_models import (
    EXPERIMENT_MATRIX_SCHEMA_VERSION,
    ExperimentMatrixSpec,
    GroupRole,
    MatrixConstraints,
    MatrixEmbeddedBase,
    MatrixExcludeCombo,
    MatrixExecutionPolicy,
    MatrixFactor,
    MatrixFactorId,
    MatrixFactorLevel,
    RetryPolicy,
    RunVersionIdentity,
    matrix_spec_fingerprint,
)
from experiments.matrix_serialization import (
    MatrixSerializationError,
    decode_matrix_spec,
    decode_run_version_identity,
    encode_matrix_spec,
    encode_run_version_identity,
)
from experiments.models import ExperimentSeedMatrix
from simulation.runner_models import (
    AgentCognitionSpec,
    AgentRunnerSpec,
    WorldScenarioSpec,
)
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.identifiers import WorldId, WorldRevision
from world.models import default_physical_rules


def _base_config():
    body = alive_body("body-1")
    agent_id = AgentId("agent-1")
    return base_runner_config_from_scenario(
        seed=11,
        stochastic_identity="cmp-matrix-ser",
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


def _spec() -> ExperimentMatrixSpec:
    return ExperimentMatrixSpec(
        matrix_id="matrix-ser",
        schema_version=EXPERIMENT_MATRIX_SCHEMA_VERSION,
        base=MatrixEmbeddedBase(runner_config=_base_config()),
        factors=(
            MatrixFactor(
                factor_id=MatrixFactorId.TOM,
                levels=(
                    MatrixFactorLevel(
                        level_id="off",
                        label_code="tom_off",
                        group_role=GroupRole.CONTROL,
                    ),
                    MatrixFactorLevel(
                        level_id="on",
                        label_code="tom_on",
                        group_role=GroupRole.TREATMENT,
                    ),
                ),
            ),
            MatrixFactor(
                factor_id=MatrixFactorId.REFLECTION,
                levels=(
                    MatrixFactorLevel(
                        level_id="disabled",
                        label_code="refl_off",
                        group_role=GroupRole.CONTROL,
                    ),
                    MatrixFactorLevel(
                        level_id="deterministic",
                        label_code="refl_on",
                        group_role=GroupRole.TREATMENT,
                    ),
                ),
            ),
        ),
        seed_matrix=ExperimentSeedMatrix(seeds=(11,), replicates_per_seed=1),
        constraints=MatrixConstraints(
            exclude_combos=(
                MatrixExcludeCombo(levels=(("tom", "on"), ("reflection", "disabled"))),
            )
        ),
        execution=MatrixExecutionPolicy(
            max_concurrency=1,
            retry_policy=RetryPolicy(
                max_attempts=2,
                transient_reason_codes=("timeout",),
            ),
            stop_on_first_error=False,
        ),
        groups=(),
    )


def test_round_trip_matrix_spec() -> None:
    spec = _spec()
    payload = encode_matrix_spec(spec)
    restored = decode_matrix_spec(payload)
    assert restored.matrix_id == spec.matrix_id
    assert restored.factors[0].factor_id is MatrixFactorId.TOM
    assert set(restored.constraints.exclude_combos[0].levels) == {
        ("tom", "on"),
        ("reflection", "disabled"),
    }
    assert matrix_spec_fingerprint(restored) == matrix_spec_fingerprint(spec)
    assert encode_matrix_spec(restored) == payload


def test_rejects_unknown_fields() -> None:
    spec = _spec()
    document = json.loads(encode_matrix_spec(spec).decode("utf-8"))
    document["extra_field"] = True
    payload = json.dumps(document, separators=(",", ":"), sort_keys=True).encode()
    with pytest.raises(MatrixSerializationError) as exc:
        decode_matrix_spec(payload)
    assert exc.value.code == "invalid_fields"


def test_rejects_unknown_constraint_ops() -> None:
    spec = _spec()
    document = json.loads(encode_matrix_spec(spec).decode("utf-8"))
    document["constraints"] = {"exclude_combos": [], "include_combos": []}
    payload = json.dumps(document, separators=(",", ":"), sort_keys=True).encode()
    with pytest.raises(MatrixSerializationError) as exc:
        decode_matrix_spec(payload)
    assert exc.value.code == "unknown_constraint_ops"


def test_rejects_unsupported_schema() -> None:
    spec = _spec()
    document = json.loads(encode_matrix_spec(spec).decode("utf-8"))
    document["schema_version"] = "experiment-matrix-v0"
    payload = json.dumps(document, separators=(",", ":"), sort_keys=True).encode()
    with pytest.raises(MatrixSerializationError) as exc:
        decode_matrix_spec(payload)
    assert exc.value.code == "unsupported_matrix_schema"


def test_run_version_identity_round_trip() -> None:
    identity = RunVersionIdentity(
        package_version="1.2.3",
        runner_schema_version="runner-config-v4",
        experiment_schema_version="experiment-definition-v1",
        matrix_schema_version=EXPERIMENT_MATRIX_SCHEMA_VERSION,
        derivation_version="derivation-v1",
        matrix_fingerprint="a" * 64,
        cell_fingerprint="b" * 64,
        config_fingerprint="c" * 64,
        code_revision="deadbeef",
    )
    payload = encode_run_version_identity(identity)
    restored = decode_run_version_identity(payload)
    assert restored == identity
    assert encode_run_version_identity(restored) == payload
