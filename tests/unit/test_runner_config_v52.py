"""Runner-config-v52 mediation mode, exact keyset, and gates."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from experiments.institutionalization_scenario import institutionalization_scenario
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V49,
    RUNNER_SCHEMA_VERSION_V51,
    RUNNER_SCHEMA_VERSION_V52,
    CollectiveDecisionMode,
    MediationMode,
    SimulationRunnerConfig,
)
from simulation.runner_serialization import (
    RunnerSerializationError,
    decode_runner_config,
    encode_runner_config,
    runner_config_fingerprint,
)


def _base() -> SimulationRunnerConfig:
    definition = institutionalization_scenario(seed=23, max_ticks=2)
    config = next(
        condition.runner_config
        for condition in definition.conditions
        if condition.condition_id == "bf-institution-on"
    )
    agents = tuple(
        replace(
            agent,
            cognition=replace(
                agent.cognition,
                mediation_mode=MediationMode.DETERMINISTIC,
            ),
        )
        for agent in config.agents
    )
    return replace(config, schema_version=RUNNER_SCHEMA_VERSION_V52, agents=agents)


def test_v52_round_trips_and_includes_mediation() -> None:
    config = _base()
    payload = encode_runner_config(config)
    document = json.loads(payload.decode("utf-8"))
    assert document["schema_version"] == RUNNER_SCHEMA_VERSION_V52
    cognition = document["agents"][0]["cognition"]
    assert cognition["mediation_mode"] == "deterministic"
    decoded = decode_runner_config(payload)
    assert decoded.schema_version == RUNNER_SCHEMA_VERSION_V52
    assert all(
        agent.cognition.mediation_mode is MediationMode.DETERMINISTIC
        for agent in decoded.agents
    )
    assert runner_config_fingerprint(decoded) == runner_config_fingerprint(config)


def test_v52_composes_collective_decisions() -> None:
    config = _base()
    agents = tuple(
        replace(
            agent,
            cognition=replace(
                agent.cognition,
                collective_decision_mode=CollectiveDecisionMode.DETERMINISTIC,
            ),
        )
        for agent in config.agents
    )
    config = replace(config, agents=agents)
    decoded = decode_runner_config(encode_runner_config(config))
    assert decoded.schema_version == RUNNER_SCHEMA_VERSION_V52
    assert all(
        agent.cognition.collective_decision_mode is CollectiveDecisionMode.DETERMINISTIC
        for agent in decoded.agents
    )


def test_historical_schema_rejects_mediation_mode() -> None:
    config = _base()
    agents = tuple(
        replace(
            agent,
            cognition=replace(
                agent.cognition,
                collective_decision_mode=CollectiveDecisionMode.DETERMINISTIC,
            ),
        )
        for agent in config.agents
    )
    with pytest.raises(ValueError, match="mediation_requires_v52"):
        replace(
            config,
            schema_version=RUNNER_SCHEMA_VERSION_V51,
            agents=agents,
        )


def test_v52_requires_an_enabled_mediation_agent() -> None:
    config = _base()
    agents = tuple(
        replace(
            agent,
            cognition=replace(
                agent.cognition,
                mediation_mode=MediationMode.DISABLED,
            ),
        )
        for agent in config.agents
    )
    with pytest.raises(ValueError, match="v52_requires_mediation"):
        replace(config, agents=agents)


def test_v52_keyset_rejects_missing_and_unknown_keys() -> None:
    payload = json.loads(encode_runner_config(_base()).decode("utf-8"))
    for agent in payload["agents"]:
        agent["cognition"].pop("mediation_mode")
    with pytest.raises(RunnerSerializationError):
        decode_runner_config(json.dumps(payload).encode("utf-8"))

    payload = json.loads(encode_runner_config(_base()).decode("utf-8"))
    payload["agents"][0]["cognition"]["mediation_policy"] = "custom"
    with pytest.raises(RunnerSerializationError):
        decode_runner_config(json.dumps(payload).encode("utf-8"))


def test_v52_unknown_enum_rejects() -> None:
    payload = json.loads(encode_runner_config(_base()).decode("utf-8"))
    payload["agents"][0]["cognition"]["mediation_mode"] = "always"
    with pytest.raises(RunnerSerializationError):
        decode_runner_config(json.dumps(payload).encode("utf-8"))


def test_v52_mixed_owners_round_trip() -> None:
    config = _base()
    agents = list(config.agents)
    agents[0] = replace(
        agents[0],
        cognition=replace(
            agents[0].cognition,
            mediation_mode=MediationMode.DISABLED,
        ),
    )
    config = replace(config, agents=tuple(agents))
    decoded = decode_runner_config(encode_runner_config(config))
    assert {agent.cognition.mediation_mode for agent in decoded.agents} == {
        MediationMode.DETERMINISTIC,
        MediationMode.DISABLED,
    }


def test_disabled_composition_keeps_historical_schema() -> None:
    definition = institutionalization_scenario(seed=23, max_ticks=2)
    config = next(
        condition.runner_config
        for condition in definition.conditions
        if condition.condition_id == "bf-institution-on"
    )
    assert config.schema_version == RUNNER_SCHEMA_VERSION_V49
    assert all(
        agent.cognition.mediation_mode is MediationMode.DISABLED
        for agent in config.agents
    )


def test_cognition_config_direct_composition_and_fingerprint() -> None:
    from agents.cognition.configuration import (
        CognitionLoopConfig,
        CognitionMediationMode,
    )
    from agents.cognition.mediation import default_mediation_policy

    disabled = CognitionLoopConfig()
    assert disabled.mediation_mode is CognitionMediationMode.DISABLED
    assert disabled.mediation_policy is None
    enabled = CognitionLoopConfig(mediation_mode=CognitionMediationMode.DETERMINISTIC)
    assert enabled.mediation_policy is not None
    assert enabled.mediation_policy.version == default_mediation_policy().version
    assert enabled.condition_fingerprint_material()["mediation_mode"] == "deterministic"
    with pytest.raises(TypeError):
        CognitionLoopConfig(
            mediation_mode=MediationMode.DETERMINISTIC  # type: ignore[arg-type]
        )
