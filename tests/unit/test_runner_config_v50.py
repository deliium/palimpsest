"""Runner-config-v50 office mode, keysets, and initialization profile gates."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from experiments.institutionalization_scenario import institutionalization_scenario
from simulation.new_agent_initialization import (
    SPECIES_DEFAULT_OFFICES_V1,
    default_new_agent_initialization_spec,
)
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V4,
    RUNNER_SCHEMA_VERSION_V49,
    RUNNER_SCHEMA_VERSION_V50,
    CulturalNarrativeMode,
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


def _with_office(
    config: SimulationRunnerConfig,
    *,
    schema_version: str = RUNNER_SCHEMA_VERSION_V50,
) -> SimulationRunnerConfig:
    agents = tuple(
        replace(
            agent,
            cognition=replace(
                agent.cognition,
                office_succession_mode=OfficeSuccessionMode.DETERMINISTIC,
            ),
        )
        for agent in config.agents
    )
    return replace(config, schema_version=schema_version, agents=agents)


def test_v50_round_trips_and_includes_both_modes() -> None:
    config = _with_office(_base_v49())
    payload = encode_runner_config(config)
    document = json.loads(payload.decode("utf-8"))
    assert document["schema_version"] == RUNNER_SCHEMA_VERSION_V50
    cognition = document["agents"][0]["cognition"]
    assert cognition["institution_concept_mode"] == "deterministic"
    assert cognition["office_succession_mode"] == "deterministic"
    decoded = decode_runner_config(payload)
    assert decoded.schema_version == RUNNER_SCHEMA_VERSION_V50
    assert all(
        agent.cognition.office_succession_mode is OfficeSuccessionMode.DETERMINISTIC
        for agent in decoded.agents
    )
    assert runner_config_fingerprint(decoded) == runner_config_fingerprint(config)


def test_v50_composes_office_without_institution() -> None:
    config = _with_office(_base_v49())
    agents = tuple(
        replace(
            agent,
            cognition=replace(
                agent.cognition,
                institution_concept_mode=type(
                    agent.cognition.institution_concept_mode
                ).DISABLED,
            ),
        )
        for agent in config.agents
    )
    config = replace(config, agents=agents)
    decoded = decode_runner_config(encode_runner_config(config))
    assert all(
        agent.cognition.office_succession_mode is OfficeSuccessionMode.DETERMINISTIC
        for agent in decoded.agents
    )


def test_v49_with_office_key_rejects() -> None:
    with pytest.raises(ValueError, match="office_succession_requires_v50"):
        _with_office(_base_v49(), schema_version=RUNNER_SCHEMA_VERSION_V49)


def test_v50_without_office_mode_rejects() -> None:
    with pytest.raises(ValueError, match="v50_requires_office_succession"):
        replace(_base_v49(), schema_version=RUNNER_SCHEMA_VERSION_V50)


def test_v50_keyset_rejects_missing_office_mode() -> None:
    config = _with_office(_base_v49())
    payload = json.loads(encode_runner_config(config).decode("utf-8"))
    for agent in payload["agents"]:
        agent["cognition"].pop("office_succession_mode")
    with pytest.raises(RunnerSerializationError):
        decode_runner_config(json.dumps(payload).encode("utf-8"))


def test_offices_profile_round_trips_only_on_v50() -> None:
    config = _with_office(_base_v49())
    profile = replace(
        default_new_agent_initialization_spec(),
        species_defaults_id=SPECIES_DEFAULT_OFFICES_V1,
    )
    config = replace(config, new_agent_initialization=profile)
    decoded = decode_runner_config(encode_runner_config(config))
    assert (
        decoded.new_agent_initialization is not None
        and decoded.new_agent_initialization.species_defaults_id
        == SPECIES_DEFAULT_OFFICES_V1
    )
    with pytest.raises(ValueError, match="offices_profile_requires_v50"):
        replace(config, schema_version=RUNNER_SCHEMA_VERSION_V49)


def test_default_write_shape_remains_v4() -> None:
    assert RUNNER_SCHEMA_VERSION_V4 == "runner-config-v4"
    assert SimulationRunnerConfig.__dataclass_fields__["schema_version"].default == (
        RUNNER_SCHEMA_VERSION_V4
    )


def test_v50_composes_narrative_and_lifecycle_channels() -> None:
    config = _with_office(_base_v49())
    agents = tuple(
        replace(
            agent,
            cognition=replace(
                agent.cognition,
                cultural_narrative_mode=CulturalNarrativeMode.DETERMINISTIC,
            ),
        )
        for agent in config.agents
    )
    config = replace(config, agents=agents)
    assert config.population_lifecycle is not None
    decoded = decode_runner_config(encode_runner_config(config))
    assert decoded.schema_version == RUNNER_SCHEMA_VERSION_V50
    assert all(
        agent.cognition.cultural_narrative_mode is CulturalNarrativeMode.DETERMINISTIC
        for agent in decoded.agents
    )
    assert decoded.population_lifecycle is not None
