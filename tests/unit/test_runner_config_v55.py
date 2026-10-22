"""Runner-config-v55 exact keyset, family selection, and legacy gates."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from experiments.institutionalization_scenario import institutionalization_scenario
from simulation.generational_models import (
    ExperimentCriterionSpec,
    GenerationalRunSpec,
    PopulationThresholdComparison,
    PopulationThresholdSpec,
)
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V54,
    RUNNER_SCHEMA_VERSION_V55,
    SUPPORTED_RUNNER_SCHEMA_VERSIONS,
    CollectiveDecisionMode,
    InstitutionalDecayMode,
    InstitutionalMemoryMode,
    InstitutionConceptMode,
    KinshipSpec,
    MediationMode,
    OfficeSuccessionMode,
    RunnerStopPolicy,
    SimulationRunnerConfig,
)
from simulation.runner_serialization import (
    RunnerSerializationError,
    decode_runner_config,
    encode_runner_config,
    runner_config_fingerprint,
)
from world import example_environmental_dynamics


def _base(
    *,
    generational_run: GenerationalRunSpec | None = None,
    schema_version: str = RUNNER_SCHEMA_VERSION_V55,
) -> SimulationRunnerConfig:
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
        schema_version=schema_version,
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
        stop_policy=RunnerStopPolicy(
            max_ticks=8, stop_on_all_agents_terminal=False
        ),
        generational_run=(
            generational_run
            if generational_run is not None
            else GenerationalRunSpec(max_generation_index=2)
        ),
    )


def test_v55_population_only_round_trips_with_all_institutional_modes_off() -> None:
    config = _base()
    payload = encode_runner_config(config)
    document = json.loads(payload.decode("utf-8"))
    assert document["schema_version"] == RUNNER_SCHEMA_VERSION_V55
    assert set(document["generational_run"]) == {
        "criterion_cadence_ticks",
        "experiment_criteria",
        "historical_checkpoint_cadence_ticks",
        "max_generation_index",
        "population_threshold",
        "sample_on_generation_change",
        "stop_on_extinction",
    }
    assert all(
        agent["cognition"]["institutional_decay_mode"] == "disabled"
        for agent in document["agents"]
    )
    decoded = decode_runner_config(payload)
    assert decoded.schema_version == RUNNER_SCHEMA_VERSION_V55
    assert decoded.generational_run == config.generational_run
    assert runner_config_fingerprint(decoded) == runner_config_fingerprint(config)


def test_v55_environmental_dynamics_round_trip() -> None:
    config = replace(_base(), environmental_dynamics=example_environmental_dynamics())
    decoded = decode_runner_config(encode_runner_config(config))
    assert decoded.environmental_dynamics is not None
    assert decoded.schema_version == RUNNER_SCHEMA_VERSION_V55
    assert decoded.generational_run == config.generational_run


def test_v55_optional_kinship_round_trip() -> None:
    config = replace(
        _base(),
        v3_capability_flags=replace(
            _base().v3_capability_flags, kinship_inheritance=True
        ),
        kinship=KinshipSpec(),
    )
    decoded = decode_runner_config(encode_runner_config(config))
    assert decoded.kinship is not None
    assert decoded.schema_version == RUNNER_SCHEMA_VERSION_V55


def test_v55_nested_stop_settings_round_trip() -> None:
    spec = GenerationalRunSpec(
        max_generation_index=None,
        stop_on_extinction=False,
        population_threshold=PopulationThresholdSpec(
            comparison=PopulationThresholdComparison.AT_LEAST, value=3
        ),
        experiment_criteria=(
            ExperimentCriterionSpec(
                criterion_id="stable_world",
                version="v1",
                params={"required_windows": 2, "allow_zero": False},
            ),
        ),
        criterion_cadence_ticks=4,
        sample_on_generation_change=False,
    )
    config = _base(generational_run=spec)
    decoded = decode_runner_config(encode_runner_config(config))
    assert decoded.generational_run == spec


def test_v55_rejects_missing_generational_run_key() -> None:
    payload = json.loads(encode_runner_config(_base()).decode("utf-8"))
    payload.pop("generational_run")
    with pytest.raises(RunnerSerializationError):
        decode_runner_config(json.dumps(payload).encode("utf-8"))


def test_v55_rejects_unknown_generational_run_key() -> None:
    payload = json.loads(encode_runner_config(_base()).decode("utf-8"))
    payload["generational_run"]["unknown"] = 1
    with pytest.raises(RunnerSerializationError):
        decode_runner_config(json.dumps(payload).encode("utf-8"))


def test_v55_rejects_null_old_optional_root_object() -> None:
    payload = json.loads(encode_runner_config(_base()).decode("utf-8"))
    payload["kinship"] = None
    with pytest.raises(RunnerSerializationError):
        decode_runner_config(json.dumps(payload).encode("utf-8"))


def test_legacy_schema_rejects_generational_run_sibling() -> None:
    payload = json.loads(encode_runner_config(_base()).decode("utf-8"))
    payload["schema_version"] = RUNNER_SCHEMA_VERSION_V54
    with pytest.raises(RunnerSerializationError):
        decode_runner_config(json.dumps(payload).encode("utf-8"))


def test_v55_is_in_accepted_versions() -> None:
    assert RUNNER_SCHEMA_VERSION_V55 in SUPPORTED_RUNNER_SCHEMA_VERSIONS
