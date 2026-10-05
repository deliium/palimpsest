"""runner-config-v26 developmental stage encode/decode and schema gates."""

from __future__ import annotations

import logging
from dataclasses import replace

import pytest

from agents.models import AgentId
from experiments.catalog import base_runner_config_from_scenario
from experiments.matrix_schema import finalize_matrix_cell_config
from simulation.new_agent_initialization import default_new_agent_initialization_spec
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V4,
    RUNNER_SCHEMA_VERSION_V24,
    RUNNER_SCHEMA_VERSION_V25,
    RUNNER_SCHEMA_VERSION_V26,
    AgentCognitionSpec,
    AgentRunnerSpec,
    GradualAgingSpec,
    LifespanDistributionSpec,
    V3CapabilityFlags,
    WorldScenarioSpec,
    example_population_lifecycle_spec,
)
from simulation.runner_serialization import (
    decode_runner_config,
    encode_runner_config,
    runner_config_fingerprint,
)
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.identifiers import WorldId, WorldRevision
from world.lifecycle import LifecycleStageId
from world.lifecycle_effects import StageCapabilityEffect
from world.models import default_physical_rules

_LOG = logging.getLogger("tests.runner_config_v26_developmental_stages")


def _base():
    body = alive_body("body-1")
    agent_id = AgentId("agent-1")
    return base_runner_config_from_scenario(
        seed=26,
        stochastic_identity="cmp-v26-dev",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-v26"),
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


def _developmental_lifecycle():
    base = example_population_lifecycle_spec(lifespan_ticks=20)
    effects = (
        StageCapabilityEffect(
            stage_id=LifecycleStageId("infant"),
            physical_capacity_factor=0.5,
            learning_rate_factor=0.8,
            fatigue_accrual_factor=1.2,
            denied_command_kinds=("attack",),
        ),
        StageCapabilityEffect(
            stage_id=LifecycleStageId("juvenile"),
            physical_capacity_factor=0.8,
            learning_rate_factor=1.2,
            fatigue_accrual_factor=1.0,
            denied_command_kinds=(),
        ),
        StageCapabilityEffect(
            stage_id=LifecycleStageId("adult"),
            physical_capacity_factor=1.0,
            learning_rate_factor=1.0,
            fatigue_accrual_factor=1.0,
            denied_command_kinds=(),
        ),
    )
    return replace(
        base,
        stage_capability_effects=effects,
        gradual_aging=GradualAgingSpec(intra_stage_interpolation=True),
        lifespan_distribution=LifespanDistributionSpec(
            distribution_id="uniform_int",
            params={"min_ticks": 10, "max_ticks": 20},
        ),
    )


def test_default_write_stays_v4_when_v3_flags_off() -> None:
    _LOG.debug("case_id=default_write_v4")
    config = _base()
    assert config.schema_version == RUNNER_SCHEMA_VERSION_V4


def test_v24_decode_synthesizes_developmental_passthrough() -> None:
    _LOG.debug("case_id=v24_synthesize_developmental")
    config = replace(
        _base(),
        schema_version=RUNNER_SCHEMA_VERSION_V24,
        population_lifecycle=example_population_lifecycle_spec(),
        v3_capability_flags=V3CapabilityFlags(generational_population=True),
    )
    decoded = decode_runner_config(encode_runner_config(config))
    assert decoded.population_lifecycle is not None
    assert decoded.population_lifecycle.gradual_aging.intra_stage_interpolation is False
    assert (
        decoded.population_lifecycle.lifespan_distribution.distribution_id == "fixed"
    )
    assert decoded.population_lifecycle.stage_capability_effects == ()
    assert not decoded.population_lifecycle.has_developmental_extensions()


def test_v26_round_trip_developmental_extensions() -> None:
    _LOG.debug("case_id=v26_round_trip")
    lifecycle = _developmental_lifecycle()
    config = replace(
        _base(),
        schema_version=RUNNER_SCHEMA_VERSION_V26,
        population_lifecycle=lifecycle,
        new_agent_initialization=default_new_agent_initialization_spec(),
        v3_capability_flags=V3CapabilityFlags(generational_population=True),
    )
    encoded = encode_runner_config(config)
    decoded = decode_runner_config(encoded)
    assert decoded.schema_version == RUNNER_SCHEMA_VERSION_V26
    assert decoded.population_lifecycle is not None
    assert decoded.population_lifecycle.has_developmental_extensions()
    assert (
        decoded.population_lifecycle.gradual_aging.intra_stage_interpolation is True
    )
    assert (
        decoded.population_lifecycle.lifespan_distribution.distribution_id
        == "uniform_int"
    )
    assert len(decoded.population_lifecycle.stage_capability_effects) == 3
    assert runner_config_fingerprint(decoded) == runner_config_fingerprint(config)


def test_developmental_extensions_require_v26() -> None:
    _LOG.debug("case_id=developmental_require_v26")
    with pytest.raises(ValueError, match="developmental_stages_require_v26"):
        replace(
            _base(),
            schema_version=RUNNER_SCHEMA_VERSION_V24,
            population_lifecycle=_developmental_lifecycle(),
            v3_capability_flags=V3CapabilityFlags(generational_population=True),
        )


def test_matrix_finalize_selects_v26_for_developmental() -> None:
    _LOG.debug("case_id=matrix_finalize_v26")
    # Construct via fields bypass: start from a valid v26-shaped config, then
    # reset schema to v4-equivalent inputs through finalize's field copy.
    from dataclasses import fields as dc_fields

    valid = replace(
        _base(),
        schema_version=RUNNER_SCHEMA_VERSION_V26,
        population_lifecycle=_developmental_lifecycle(),
        new_agent_initialization=default_new_agent_initialization_spec(),
        v3_capability_flags=V3CapabilityFlags(generational_population=True),
    )
    payload = {field.name: getattr(valid, field.name) for field in dc_fields(valid)}
    payload["schema_version"] = RUNNER_SCHEMA_VERSION_V4
    # Rebuild without __post_init__ gates by using object.__new__ pattern via
    # finalize which sets schema then validates.
    from simulation.runner_models import SimulationRunnerConfig

    draft = SimulationRunnerConfig.__new__(SimulationRunnerConfig)
    for name, value in payload.items():
        object.__setattr__(draft, name, value)
    finalized = finalize_matrix_cell_config(draft)
    assert finalized.schema_version == RUNNER_SCHEMA_VERSION_V26


def test_matrix_finalize_keeps_ae_v24_and_af_v25() -> None:
    _LOG.debug("case_id=matrix_finalize_ae_af")
    from simulation.runner_models import SimulationRunnerConfig

    ae_valid = replace(
        _base(),
        schema_version=RUNNER_SCHEMA_VERSION_V24,
        population_lifecycle=example_population_lifecycle_spec(),
        v3_capability_flags=V3CapabilityFlags(generational_population=True),
    )
    ae_draft = SimulationRunnerConfig.__new__(SimulationRunnerConfig)
    for field in ae_valid.__dataclass_fields__:
        object.__setattr__(ae_draft, field, getattr(ae_valid, field))
    object.__setattr__(ae_draft, "schema_version", RUNNER_SCHEMA_VERSION_V4)
    assert finalize_matrix_cell_config(ae_draft).schema_version == (
        RUNNER_SCHEMA_VERSION_V24
    )
    af_valid = replace(
        ae_valid,
        schema_version=RUNNER_SCHEMA_VERSION_V25,
        new_agent_initialization=default_new_agent_initialization_spec(),
    )
    af_draft = SimulationRunnerConfig.__new__(SimulationRunnerConfig)
    for field in af_valid.__dataclass_fields__:
        object.__setattr__(af_draft, field, getattr(af_valid, field))
    object.__setattr__(af_draft, "schema_version", RUNNER_SCHEMA_VERSION_V4)
    assert finalize_matrix_cell_config(af_draft).schema_version == (
        RUNNER_SCHEMA_VERSION_V25
    )


def test_v26_passthrough_round_trip() -> None:
    _LOG.debug("case_id=v26_passthrough")
    config = replace(
        _base(),
        schema_version=RUNNER_SCHEMA_VERSION_V26,
        population_lifecycle=example_population_lifecycle_spec(),
        new_agent_initialization=default_new_agent_initialization_spec(),
        v3_capability_flags=V3CapabilityFlags(generational_population=True),
    )
    decoded = decode_runner_config(encode_runner_config(config))
    assert decoded.schema_version == RUNNER_SCHEMA_VERSION_V26
    assert not decoded.population_lifecycle.has_developmental_extensions()  # type: ignore[union-attr]
