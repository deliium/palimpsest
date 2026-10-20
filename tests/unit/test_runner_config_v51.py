"""Runner-config-v51 collective-decision mode, keysets, and gates."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from experiments.institutionalization_scenario import institutionalization_scenario
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V49,
    RUNNER_SCHEMA_VERSION_V50,
    RUNNER_SCHEMA_VERSION_V51,
    CollectiveDecisionMode,
    InstitutionConceptMode,
    OfficeSuccessionMode,
    SimulationRunnerConfig,
)
from simulation.runner_serialization import (
    RunnerSerializationError,
    decode_runner_config,
    encode_runner_config,
    runner_config_fingerprint,
)


def _base_v49() -> SimulationRunnerConfig:
    definition = institutionalization_scenario(seed=23, max_ticks=2)
    return next(
        condition.runner_config
        for condition in definition.conditions
        if condition.condition_id == "bf-institution-on"
    )


def _with_decisions(
    config: SimulationRunnerConfig,
    *,
    schema_version: str = RUNNER_SCHEMA_VERSION_V51,
    offices: bool = False,
) -> SimulationRunnerConfig:
    agents = tuple(
        replace(
            agent,
            cognition=replace(
                agent.cognition,
                collective_decision_mode=CollectiveDecisionMode.DETERMINISTIC,
                office_succession_mode=(
                    OfficeSuccessionMode.DETERMINISTIC
                    if offices
                    else OfficeSuccessionMode.DISABLED
                ),
            ),
        )
        for agent in config.agents
    )
    return replace(config, schema_version=schema_version, agents=agents)


def _decisions_only_base() -> SimulationRunnerConfig:
    config = _with_decisions(_base_v49())
    agents = tuple(
        replace(
            agent,
            cognition=replace(
                agent.cognition,
                institution_concept_mode=InstitutionConceptMode.DISABLED,
            ),
        )
        for agent in config.agents
    )
    return replace(config, agents=agents)


def test_v51_round_trips_and_includes_decisions() -> None:
    config = _with_decisions(_decisions_only_base())
    payload = encode_runner_config(config)
    document = json.loads(payload.decode("utf-8"))
    assert document["schema_version"] == RUNNER_SCHEMA_VERSION_V51
    cognition = document["agents"][0]["cognition"]
    assert cognition["collective_decision_mode"] == "deterministic"
    assert cognition["office_succession_mode"] == "disabled"
    assert cognition["institution_concept_mode"] == "disabled"
    decoded = decode_runner_config(payload)
    assert decoded.schema_version == RUNNER_SCHEMA_VERSION_V51
    assert all(
        agent.cognition.collective_decision_mode is CollectiveDecisionMode.DETERMINISTIC
        for agent in decoded.agents
    )
    assert runner_config_fingerprint(decoded) == runner_config_fingerprint(config)


def test_v51_composes_offices_and_institutions() -> None:
    config = _with_decisions(_base_v49(), offices=True)
    assert config.agents[0].cognition.institution_concept_mode is (
        InstitutionConceptMode.DETERMINISTIC
    )
    decoded = decode_runner_config(encode_runner_config(config))
    assert decoded.schema_version == RUNNER_SCHEMA_VERSION_V51
    assert all(
        agent.cognition.collective_decision_mode is CollectiveDecisionMode.DETERMINISTIC
        for agent in decoded.agents
    )
    assert all(
        agent.cognition.office_succession_mode is OfficeSuccessionMode.DETERMINISTIC
        for agent in decoded.agents
    )


def test_v50_with_collective_key_rejects() -> None:
    with pytest.raises(ValueError, match="collective_decision_requires_v51"):
        _with_decisions(
            _base_v49(),
            schema_version=RUNNER_SCHEMA_VERSION_V50,
            offices=True,
        )


def test_v49_with_collective_mode_rejects() -> None:
    with pytest.raises(ValueError, match="collective_decision_requires_v51"):
        _with_decisions(
            _base_v49(),
            schema_version=RUNNER_SCHEMA_VERSION_V49,
        )


def test_v51_requires_an_enabled_decision_agent() -> None:
    config = _with_decisions(_decisions_only_base())
    agents = tuple(
        replace(
            agent,
            cognition=replace(
                agent.cognition,
                collective_decision_mode=CollectiveDecisionMode.DISABLED,
            ),
        )
        for agent in config.agents
    )
    with pytest.raises(ValueError, match="v51_requires_collective_decision"):
        replace(config, agents=agents)


def test_v51_keyset_rejects_missing_decision_mode() -> None:
    config = _with_decisions(_decisions_only_base())
    payload = json.loads(encode_runner_config(config).decode("utf-8"))
    for agent in payload["agents"]:
        agent["cognition"].pop("collective_decision_mode")
    with pytest.raises(RunnerSerializationError):
        decode_runner_config(json.dumps(payload).encode("utf-8"))


def test_v51_keyset_rejects_unknown_decision_key() -> None:
    config = _with_decisions(_decisions_only_base())
    payload = json.loads(encode_runner_config(config).decode("utf-8"))
    payload["agents"][0]["cognition"]["collective_decision_policy"] = "custom"
    with pytest.raises(RunnerSerializationError):
        decode_runner_config(json.dumps(payload).encode("utf-8"))


def test_v51_mixed_enabled_and_disabled_owners_round_trip() -> None:
    config = _with_decisions(_decisions_only_base())
    agents = list(config.agents)
    agents[0] = replace(
        agents[0],
        cognition=replace(
            agents[0].cognition,
            collective_decision_mode=CollectiveDecisionMode.DISABLED,
        ),
    )
    config = replace(config, agents=tuple(agents))
    decoded = decode_runner_config(encode_runner_config(config))
    modes = {agent.cognition.collective_decision_mode for agent in decoded.agents}
    assert modes == {
        CollectiveDecisionMode.DETERMINISTIC,
        CollectiveDecisionMode.DISABLED,
    }


def test_v51_unknown_enum_value_rejects() -> None:
    config = _with_decisions(_decisions_only_base())
    payload = json.loads(encode_runner_config(config).decode("utf-8"))
    payload["agents"][0]["cognition"]["collective_decision_mode"] = "always"
    with pytest.raises(RunnerSerializationError):
        decode_runner_config(json.dumps(payload).encode("utf-8"))


def test_cognition_config_direct_composition_and_fingerprint() -> None:
    from agents.cognition.collective_decisions import default_collective_decision_policy
    from agents.cognition.configuration import (
        CognitionCollectiveDecisionMode,
        CognitionLoopConfig,
    )

    disabled = CognitionLoopConfig()
    assert disabled.collective_decision_mode is CognitionCollectiveDecisionMode.DISABLED
    assert disabled.collective_decision_policy is None
    enabled = CognitionLoopConfig(
        collective_decision_mode=CognitionCollectiveDecisionMode.DETERMINISTIC
    )
    assert enabled.collective_decision_policy is not None
    assert (
        enabled.collective_decision_policy.version
        == default_collective_decision_policy().version
    )
    assert (
        enabled.condition_fingerprint_material()["collective_decision_mode"]
        == "deterministic"
    )
    assert (
        disabled.condition_fingerprint_material()["collective_decision_mode"]
        == "disabled"
    )
    with pytest.raises(TypeError):
        CognitionLoopConfig(
            collective_decision_mode=CollectiveDecisionMode.DETERMINISTIC  # type: ignore[arg-type]
        )
    with pytest.raises(TypeError):
        CognitionLoopConfig(
            collective_decision_mode=CognitionCollectiveDecisionMode.DETERMINISTIC,
            collective_decision_policy=object(),  # type: ignore[arg-type]
        )
