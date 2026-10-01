"""runner-config-v14 is emitted only when environmental dynamics are set."""

from __future__ import annotations

import json
import logging

import pytest

from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION,
    RUNNER_SCHEMA_VERSION_V13,
    RUNNER_SCHEMA_VERSION_V14,
    SimulationRunnerConfig,
)
from simulation.runner_serialization import (
    RunnerSerializationError,
    decode_runner_config,
    encode_runner_config,
)
from tests.unit.test_production_runner import _with_cognition
from tests.unit.test_runner_serialization import _configured
from world.environment import example_environmental_dynamics
from world.production import example_production_catalog


def test_default_write_stays_v4() -> None:
    document = json.loads(
        encode_runner_config(
            _configured(schema_version=RUNNER_SCHEMA_VERSION)
        ).decode("utf-8")
    )
    assert document["schema_version"] == "runner-config-v4"
    assert "environmental_dynamics" not in document
    assert RUNNER_SCHEMA_VERSION == "runner-config-v4"


def test_catalog_without_dynamics_stays_v13() -> None:
    base = _configured(schema_version=RUNNER_SCHEMA_VERSION)
    agent = base.agents[0]
    config = _with_cognition(
        base,
        type(agent.cognition)(
            agent_id=agent.agent_id,
            memory_mode=agent.cognition.memory_mode,
            drive_overrides=agent.cognition.drive_overrides,
            production_catalog=example_production_catalog(),
        ),
        schema_version=RUNNER_SCHEMA_VERSION_V13,
    )
    document = json.loads(encode_runner_config(config).decode("utf-8"))
    assert document["schema_version"] == "runner-config-v13"
    assert "environmental_dynamics" not in document


def test_spec_round_trips_only_on_v14(
    caplog: pytest.LogCaptureFixture,
) -> None:
    spec = example_environmental_dynamics()
    base = _configured(schema_version=RUNNER_SCHEMA_VERSION)
    with caplog.at_level(logging.DEBUG, logger="simulation.runner"):
        config = SimulationRunnerConfig(
            seed=base.seed,
            stochastic_identity=base.stochastic_identity,
            scenario=base.scenario,
            agents=base.agents,
            stop_policy=base.stop_policy,
            schema_version=RUNNER_SCHEMA_VERSION_V14,
            environmental_dynamics=spec,
        )
        encoded = encode_runner_config(config)
    document = json.loads(encoded.decode("utf-8"))
    assert document["schema_version"] == "runner-config-v14"
    assert document["environmental_dynamics"]["season_length_ticks"] == 48
    cognition = document["agents"][0]["cognition"]
    assert "production_catalog" in cognition
    assert "skill_learning_mode" in cognition
    assert "teaching_interaction_mode" in cognition
    assert decode_runner_config(encoded) == config
    assert any(
        record.levelno == logging.INFO
        and record.message
        == "environment_config schema_version=runner-config-v14 "
        "season_length=48 hazard_rule_count=2"
        for record in caplog.records
    )
    assert any(
        record.levelno == logging.DEBUG and spec.digest in record.message
        for record in caplog.records
    )


def test_v14_without_spec_is_rejected(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.ERROR, logger="simulation.runner"):
        with pytest.raises(ValueError, match="environment_spec_mismatch"):
            _configured(schema_version=RUNNER_SCHEMA_VERSION_V14)
    assert any(
        "environment_spec_mismatch schema_version=runner-config-v14 "
        "reason_code=environment_spec_mismatch" in record.message
        for record in caplog.records
    )


def test_earlier_schema_rejects_the_spec() -> None:
    base = _configured(schema_version=RUNNER_SCHEMA_VERSION)
    with pytest.raises(ValueError, match="environment_spec_mismatch"):
        SimulationRunnerConfig(
            seed=base.seed,
            stochastic_identity=base.stochastic_identity,
            scenario=base.scenario,
            agents=base.agents,
            stop_policy=base.stop_policy,
            schema_version=RUNNER_SCHEMA_VERSION,
            environmental_dynamics=example_environmental_dynamics(),
        )


def test_v13_document_rejects_the_dynamics_key() -> None:
    base = _configured(schema_version=RUNNER_SCHEMA_VERSION)
    agent = base.agents[0]
    config = _with_cognition(
        base,
        type(agent.cognition)(
            agent_id=agent.agent_id,
            memory_mode=agent.cognition.memory_mode,
            drive_overrides=agent.cognition.drive_overrides,
            production_catalog=example_production_catalog(),
        ),
        schema_version=RUNNER_SCHEMA_VERSION_V13,
    )
    document = json.loads(encode_runner_config(config).decode("utf-8"))
    document["environmental_dynamics"] = {"season_length_ticks": 48}
    payload = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    with pytest.raises(RunnerSerializationError):
        decode_runner_config(payload)
