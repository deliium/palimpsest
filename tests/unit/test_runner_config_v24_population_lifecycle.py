"""runner-config-v24 population lifecycle encode/decode and schema gates."""

from __future__ import annotations

import logging
from dataclasses import replace

import pytest

from agents.models import AgentId
from experiments.catalog import base_runner_config_from_scenario
from simulation.models import RunId
from simulation.runner import (
    RunnerConstructionError,
    RunnerConstructionErrorCode,
    SimulationRunner,
)
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V4,
    RUNNER_SCHEMA_VERSION_V23,
    RUNNER_SCHEMA_VERSION_V24,
    AgentCognitionSpec,
    AgentRunnerSpec,
    PopulationLifecycleSpec,
    V3CapabilityFlags,
    WorldScenarioSpec,
    example_population_lifecycle_spec,
)
from simulation.runner_serialization import (
    RunnerSerializationError,
    decode_runner_config,
    encode_runner_config,
    runner_config_fingerprint,
)
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.identifiers import WorldId, WorldRevision
from world.lifecycle import LifecycleStageId, LifecycleStageThreshold
from world.models import default_physical_rules

_LOG = logging.getLogger("tests.runner_config_v24_population_lifecycle")


def _base():
    body = alive_body("body-1")
    agent_id = AgentId("agent-1")
    return base_runner_config_from_scenario(
        seed=24,
        stochastic_identity="cmp-v24-lifecycle",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-v24"),
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


def test_default_write_stays_v4_when_v3_flags_off() -> None:
    _LOG.debug("case_id=default_write_v4")
    config = _base()
    assert config.schema_version == RUNNER_SCHEMA_VERSION_V4
    assert config.population_lifecycle is None
    assert config.v3_capability_flags == V3CapabilityFlags()


def test_all_off_v24_round_trip() -> None:
    _LOG.debug("case_id=all_off_v24_round_trip")
    lifecycle = example_population_lifecycle_spec()
    config = replace(
        _base(),
        schema_version=RUNNER_SCHEMA_VERSION_V24,
        population_lifecycle=lifecycle,
        v3_capability_flags=V3CapabilityFlags(),
    )
    encoded = encode_runner_config(config)
    decoded = decode_runner_config(encoded)
    assert decoded.schema_version == RUNNER_SCHEMA_VERSION_V24
    assert decoded.v3_capability_flags == V3CapabilityFlags()
    assert decoded.population_lifecycle is not None
    assert (
        decoded.population_lifecycle.demographic_policy_id
        == lifecycle.demographic_policy_id
    )
    assert runner_config_fingerprint(decoded) == runner_config_fingerprint(config)


def test_generational_population_requires_v24() -> None:
    _LOG.debug("case_id=generational_requires_v24")
    with pytest.raises(ValueError, match="generational_population_requires_v24"):
        replace(
            _base(),
            schema_version=RUNNER_SCHEMA_VERSION_V23,
            v3_capability_flags=V3CapabilityFlags(generational_population=True),
            population_lifecycle=example_population_lifecycle_spec(),
        )


def test_v24_requires_population_lifecycle() -> None:
    _LOG.debug("case_id=v24_requires_lifecycle")
    with pytest.raises(ValueError, match="v24_requires_population_lifecycle"):
        replace(
            _base(),
            schema_version=RUNNER_SCHEMA_VERSION_V24,
            population_lifecycle=None,
        )


def test_other_v3_flag_still_requires_v23() -> None:
    _LOG.debug("case_id=other_v3_requires_v23")
    with pytest.raises(ValueError, match="v3_capability_requires_v23"):
        replace(
            _base(),
            schema_version=RUNNER_SCHEMA_VERSION_V4,
            v3_capability_flags=V3CapabilityFlags(kinship_inheritance=True),
        )


def test_legacy_decode_synthesizes_absent_lifecycle() -> None:
    _LOG.debug("case_id=legacy_synthesize_lifecycle")
    encoded = encode_runner_config(_base())
    decoded = decode_runner_config(encoded)
    assert decoded.population_lifecycle is None


def test_fixed_interval_policy_params_round_trip() -> None:
    _LOG.debug("case_id=fixed_interval_params")
    lifecycle = example_population_lifecycle_spec(policy_id="fixed_interval_entry")
    config = replace(
        _base(),
        schema_version=RUNNER_SCHEMA_VERSION_V24,
        v3_capability_flags=V3CapabilityFlags(generational_population=True),
        population_lifecycle=lifecycle,
    )
    decoded = decode_runner_config(encode_runner_config(config))
    assert decoded.v3_capability_flags.generational_population is True
    assert decoded.population_lifecycle is not None
    assert (
        decoded.population_lifecycle.demographic_policy_params["interval_ticks"] == 5
    )


def test_unknown_policy_id_fails_closed() -> None:
    _LOG.debug("case_id=unknown_policy")
    with pytest.raises(ValueError, match="unknown_demographic_policy_id"):
        PopulationLifecycleSpec(
            lifespan_ticks=10,
            stage_thresholds=(
                LifecycleStageThreshold(LifecycleStageId("infant"), 2),
                LifecycleStageThreshold(LifecycleStageId("adult"), 9),
            ),
            dependent_until_stage=LifecycleStageId("adult"),
            demographic_policy_id="mating",
            demographic_policy_params={},
            max_population=4,
            natural_death_on_lifespan=True,
        )


def test_biology_keys_forbidden_in_params() -> None:
    _LOG.debug("case_id=biology_forbidden")
    with pytest.raises(ValueError, match="lifecycle_biology_forbidden"):
        PopulationLifecycleSpec(
            lifespan_ticks=10,
            stage_thresholds=(
                LifecycleStageThreshold(LifecycleStageId("infant"), 2),
                LifecycleStageThreshold(LifecycleStageId("adult"), 9),
            ),
            dependent_until_stage=LifecycleStageId("adult"),
            demographic_policy_id="disabled",
            demographic_policy_params={"sex": "x"},
            max_population=4,
            natural_death_on_lifespan=False,
        )


@pytest.mark.asyncio
async def test_owned_generational_flag_does_not_fail_closed_at_from_config() -> None:
    _LOG.debug("case_id=owned_flag_from_config")
    config = replace(
        _base(),
        schema_version=RUNNER_SCHEMA_VERSION_V24,
        v3_capability_flags=V3CapabilityFlags(generational_population=True),
        population_lifecycle=example_population_lifecycle_spec(),
    )
    runner = await SimulationRunner.from_config(
        config, run_id=RunId("run-v24-owned-generational")
    )
    assert runner is not None


@pytest.mark.asyncio
async def test_unowned_v3_flag_still_fails_closed() -> None:
    _LOG.debug("case_id=unowned_flag_fail_closed")
    config = replace(
        _base(),
        schema_version=RUNNER_SCHEMA_VERSION_V23,
        v3_capability_flags=V3CapabilityFlags(kinship_inheritance=True),
    )
    with pytest.raises(RunnerConstructionError) as exc_info:
        await SimulationRunner.from_config(
            config, run_id=RunId("run-v23-kinship")
        )
    assert exc_info.value.code is RunnerConstructionErrorCode.CAPABILITY_UNIMPLEMENTED


def test_v24_decode_rejects_missing_lifecycle_key() -> None:
    _LOG.debug("case_id=v24_missing_lifecycle_key")
    config = replace(
        _base(),
        schema_version=RUNNER_SCHEMA_VERSION_V24,
        population_lifecycle=example_population_lifecycle_spec(),
    )
    document = decode_runner_config(encode_runner_config(config))
    # Re-encode then strip key via raw JSON mutation is covered by root key gate:
    raw = encode_runner_config(document)
    import json

    parsed = json.loads(raw.decode("utf-8"))
    del parsed["population_lifecycle"]
    mangled = json.dumps(parsed, separators=(",", ":"), sort_keys=True).encode("utf-8")
    with pytest.raises(RunnerSerializationError):
        decode_runner_config(mangled)
