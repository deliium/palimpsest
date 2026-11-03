"""Runner-config-v56 exact keyset, legacy synthesis, and fail-closed V4 gate."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from agents.models import AgentId
from experiments.catalog import base_runner_config_from_scenario
from experiments.institutionalization_scenario import institutionalization_scenario
from experiments.matrix_models import MatrixValidationError
from experiments.matrix_schema import finalize_matrix_cell_config
from simulation.generational_models import GenerationalRunSpec
from simulation.models import RunId
from simulation.runner import (
    RunnerConstructionError,
    RunnerConstructionErrorCode,
    SimulationRunner,
)
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION,
    RUNNER_SCHEMA_VERSION_V4,
    RUNNER_SCHEMA_VERSION_V23,
    RUNNER_SCHEMA_VERSION_V55,
    RUNNER_SCHEMA_VERSION_V56,
    SUPPORTED_RUNNER_SCHEMA_VERSIONS,
    AgentCognitionSpec,
    AgentRunnerSpec,
    CollectiveDecisionMode,
    InstitutionalDecayMode,
    InstitutionalMemoryMode,
    InstitutionConceptMode,
    MediationMode,
    OfficeSuccessionMode,
    RunnerStopPolicy,
    SimulationRunnerConfig,
    V4CapabilityFlags,
    WorldScenarioSpec,
)
from simulation.runner_serialization import (
    RunnerSerializationError,
    decode_runner_config,
    encode_runner_config,
)
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.identifiers import WorldId, WorldRevision
from world.models import default_physical_rules

pytestmark = pytest.mark.unit


def _base() -> SimulationRunnerConfig:
    body = alive_body("body-1")
    agent_id = AgentId("agent-1")
    return base_runner_config_from_scenario(
        seed=11,
        stochastic_identity="cmp-v4-scaffolding",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-v4-scaffolding"),
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


def _generational_v55() -> SimulationRunnerConfig:
    """A valid v55 generational config with every institutional mode off."""
    definition = institutionalization_scenario(seed=23, max_ticks=8)
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
                institution_concept_mode=InstitutionConceptMode.DISABLED,
                office_succession_mode=OfficeSuccessionMode.DISABLED,
                institutional_memory_mode=InstitutionalMemoryMode.DISABLED,
                institutional_decay_mode=InstitutionalDecayMode.DISABLED,
                collective_decision_mode=CollectiveDecisionMode.DISABLED,
                mediation_mode=MediationMode.DISABLED,
            ),
        )
        for agent in config.agents
    )
    return replace(
        config,
        schema_version=RUNNER_SCHEMA_VERSION_V55,
        agents=agents,
        v3_capability_flags=replace(
            config.v3_capability_flags,
            kinship_inheritance=False,
            cultural_historical_memory=False,
        ),
        mentorship=None,
        developmental_learning=None,
        dependency_care=None,
        kinship=None,
        cultural_feature_provenance=None,
        collective_projects=None,
        public_goods=None,
        structured_commitments=None,
        subjective_valuation=None,
        resource_exchange_profile=None,
        generational_narratives=None,
        stop_policy=RunnerStopPolicy(max_ticks=8, stop_on_all_agents_terminal=False),
        generational_run=GenerationalRunSpec(max_generation_index=2),
    )


def test_v56_is_accepted_and_never_the_default() -> None:
    assert RUNNER_SCHEMA_VERSION_V56 == "runner-config-v56"
    assert RUNNER_SCHEMA_VERSION_V56 in SUPPORTED_RUNNER_SCHEMA_VERSIONS
    assert "runner-config-v57" not in SUPPORTED_RUNNER_SCHEMA_VERSIONS
    assert RUNNER_SCHEMA_VERSION == RUNNER_SCHEMA_VERSION_V4 == "runner-config-v4"


def test_v56_all_flags_off_round_trips_byte_identically() -> None:
    config = replace(_base(), schema_version=RUNNER_SCHEMA_VERSION_V56)
    payload = encode_runner_config(config)
    document = json.loads(payload)
    assert document["schema_version"] == RUNNER_SCHEMA_VERSION_V56
    flags = document["v4_capability_flags"]
    assert len(flags) == 12
    assert set(flags.values()) == {False}

    decoded = decode_runner_config(payload)
    assert decoded.schema_version == RUNNER_SCHEMA_VERSION_V56
    assert decoded.v4_capability_flags == V4CapabilityFlags()
    assert encode_runner_config(decoded) == payload


def test_v56_generational_config_round_trips() -> None:
    config = replace(_generational_v55(), schema_version=RUNNER_SCHEMA_VERSION_V56)
    payload = encode_runner_config(config)
    decoded = decode_runner_config(payload)
    assert decoded.schema_version == RUNNER_SCHEMA_VERSION_V56
    assert decoded.generational_run == config.generational_run
    assert encode_runner_config(decoded) == payload


def test_v55_payload_rejects_the_v4_flag_sibling() -> None:
    payload = encode_runner_config(_generational_v55())
    document = json.loads(payload)
    assert "v4_capability_flags" not in document
    document["v4_capability_flags"] = json.loads(
        encode_runner_config(replace(_base(), schema_version=RUNNER_SCHEMA_VERSION_V56))
    )["v4_capability_flags"]
    with pytest.raises(RunnerSerializationError) as excinfo:
        decode_runner_config(json.dumps(document).encode())
    assert excinfo.value.code == "invalid_fields"
    assert excinfo.value.path == "$"


def test_v56_requires_the_root_flag_sibling() -> None:
    document = json.loads(
        encode_runner_config(replace(_base(), schema_version=RUNNER_SCHEMA_VERSION_V56))
    )
    document.pop("v4_capability_flags")
    with pytest.raises(RunnerSerializationError) as excinfo:
        decode_runner_config(json.dumps(document).encode())
    assert excinfo.value.code == "missing_field"


def test_v56_flag_sibling_is_exactly_the_twelve_keys() -> None:
    document = json.loads(
        encode_runner_config(replace(_base(), schema_version=RUNNER_SCHEMA_VERSION_V56))
    )
    extra = dict(document)
    extra["v4_capability_flags"] = {**document["v4_capability_flags"], "extra": False}
    with pytest.raises(RunnerSerializationError) as excinfo:
        decode_runner_config(json.dumps(extra).encode())
    assert excinfo.value.code == "invalid_fields"
    assert excinfo.value.path == "$.v4_capability_flags"

    missing = dict(document)
    inner = dict(document["v4_capability_flags"])
    inner.pop("science")
    missing["v4_capability_flags"] = inner
    with pytest.raises(RunnerSerializationError) as excinfo:
        decode_runner_config(json.dumps(missing).encode())
    assert excinfo.value.code == "missing_field"

    non_bool = dict(document)
    non_bool["v4_capability_flags"] = {
        **document["v4_capability_flags"],
        "science": "yes",
    }
    with pytest.raises(RunnerSerializationError) as excinfo:
        decode_runner_config(json.dumps(non_bool).encode())
    assert excinfo.value.code == "invalid_bool"


def test_legacy_payloads_synthesize_all_flags_off() -> None:
    for schema_version in (
        RUNNER_SCHEMA_VERSION_V4,
        RUNNER_SCHEMA_VERSION_V23,
        RUNNER_SCHEMA_VERSION_V55,
    ):
        config = (
            _generational_v55()
            if schema_version == RUNNER_SCHEMA_VERSION_V55
            else replace(_base(), schema_version=schema_version)
        )
        payload = encode_runner_config(config)
        assert "v4_capability_flags" not in json.loads(payload)
        decoded = decode_runner_config(payload)
        assert decoded.v4_capability_flags == V4CapabilityFlags()
        assert decoded.v4_capability_flags.any_enabled() is False


def test_matrix_finalize_preserves_explicit_v56_only() -> None:
    explicit = replace(_base(), schema_version=RUNNER_SCHEMA_VERSION_V56)
    assert finalize_matrix_cell_config(explicit).schema_version == (
        RUNNER_SCHEMA_VERSION_V56
    )

    plain = _base()
    assert finalize_matrix_cell_config(plain).schema_version == RUNNER_SCHEMA_VERSION_V4


def test_matrix_finalize_rejects_v56_with_an_enabled_v4_flag() -> None:
    config = replace(
        _base(),
        schema_version=RUNNER_SCHEMA_VERSION_V56,
        v4_capability_flags=V4CapabilityFlags(science=True),
    )
    with pytest.raises(MatrixValidationError) as excinfo:
        finalize_matrix_cell_config(config)
    assert excinfo.value.code == "finalize_validation_failed"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "flag_name",
    (
        "legal_disputes",
        "diplomacy",
        "organized_conflict",
        "infrastructure_networks",
        "supply_chains",
        "markets_credit",
        "science",
        "epidemics",
        "ecological_feedback",
        "disasters",
    ),
)
async def test_unowned_v4_flag_fails_closed_after_encode_decode(
    flag_name: str,
) -> None:
    config = replace(
        _base(),
        schema_version=RUNNER_SCHEMA_VERSION_V56,
        v4_capability_flags=V4CapabilityFlags(**{flag_name: True}),
    )
    decoded = decode_runner_config(encode_runner_config(config))
    assert getattr(decoded.v4_capability_flags, flag_name) is True

    with pytest.raises(RunnerConstructionError) as excinfo:
        await SimulationRunner.from_config(
            config, run_id=RunId(f"run-v4-gate-{flag_name}")
        )
    assert excinfo.value.code is RunnerConstructionErrorCode.CAPABILITY_UNIMPLEMENTED
    assert excinfo.value.stage == "v4_capability_flags"


@pytest.mark.asyncio
@pytest.mark.parametrize("flag_name", ("organizations", "formal_rules"))
async def test_owned_v4_flag_constructs_after_encode_decode(flag_name: str) -> None:
    config = replace(
        _base(),
        schema_version=RUNNER_SCHEMA_VERSION_V56,
        v4_capability_flags=V4CapabilityFlags(**{flag_name: True}),
    )
    decoded = decode_runner_config(encode_runner_config(config))
    assert getattr(decoded.v4_capability_flags, flag_name) is True

    runner = await SimulationRunner.from_config(
        config, run_id=RunId(f"run-v4-gate-{flag_name}")
    )
    assert runner.config.v4_capability_flags.owned_enabled_names() == (flag_name,)
    assert runner.config.v4_capability_flags.unimplemented_enabled_names() == ()
