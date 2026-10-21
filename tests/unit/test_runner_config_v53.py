"""Runner-config-v53 institutional memory mode, exact keyset, and gates."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from agents.models import AgentId
from experiments.institutionalization_scenario import institutionalization_scenario
from simulation.new_agent_initialization import SPECIES_DEFAULT_OFFICES_V1
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V52,
    RUNNER_SCHEMA_VERSION_V53,
    AgentCognitionSpec,
    InstitutionalMemoryMode,
    InstitutionConceptMode,
    MediationMode,
    OfficeSuccessionMode,
    SimulationRunnerConfig,
    V3CapabilityFlags,
)
from simulation.runner_serialization import (
    RunnerSerializationError,
    decode_runner_config,
    encode_runner_config,
    runner_config_fingerprint,
)


def _base(
    *,
    role: bool = True,
    procedure: bool = False,
    institutional: bool = True,
    schema_version: str = RUNNER_SCHEMA_VERSION_V53,
) -> SimulationRunnerConfig:
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
                office_succession_mode=(
                    OfficeSuccessionMode.DETERMINISTIC
                    if role
                    else OfficeSuccessionMode.DISABLED
                ),
                institution_concept_mode=(
                    InstitutionConceptMode.DETERMINISTIC
                    if procedure
                    else InstitutionConceptMode.DISABLED
                ),
                institutional_memory_mode=(
                    InstitutionalMemoryMode.DETERMINISTIC
                    if institutional
                    else InstitutionalMemoryMode.DISABLED
                ),
            ),
        )
        for agent in config.agents
    )
    return replace(config, schema_version=schema_version, agents=agents)


def _v52() -> SimulationRunnerConfig:
    config = _base()
    agents = tuple(
        replace(
            agent,
            cognition=replace(
                agent.cognition,
                mediation_mode=MediationMode.DETERMINISTIC,
                institutional_memory_mode=InstitutionalMemoryMode.DISABLED,
            ),
        )
        for agent in config.agents
    )
    return replace(
        config,
        schema_version=RUNNER_SCHEMA_VERSION_V52,
        agents=agents,
    )


def test_v53_procedure_only_round_trips() -> None:
    config = _base(role=False, procedure=True)
    payload = encode_runner_config(config)
    document = json.loads(payload.decode("utf-8"))
    assert document["schema_version"] == RUNNER_SCHEMA_VERSION_V53
    cognition = document["agents"][0]["cognition"]
    assert cognition["institutional_memory_mode"] == "deterministic"
    decoded = decode_runner_config(payload)
    assert decoded.schema_version == RUNNER_SCHEMA_VERSION_V53
    assert all(
        agent.cognition.institutional_memory_mode
        is InstitutionalMemoryMode.DETERMINISTIC
        for agent in decoded.agents
    )
    assert runner_config_fingerprint(decoded) == runner_config_fingerprint(config)


def test_v53_role_only_round_trips() -> None:
    config = _base(role=True, procedure=False)
    decoded = decode_runner_config(encode_runner_config(config))
    assert all(
        agent.cognition.office_succession_mode is OfficeSuccessionMode.DETERMINISTIC
        for agent in decoded.agents
    )
    assert all(
        agent.cognition.institution_concept_mode is InstitutionConceptMode.DISABLED
        for agent in decoded.agents
    )


def test_v53_both_local_modes_and_mixed_owners() -> None:
    config = _base(role=True, procedure=True)
    agents = list(config.agents)
    agents[0] = replace(
        agents[0],
        cognition=replace(
            agents[0].cognition,
            institutional_memory_mode=InstitutionalMemoryMode.DISABLED,
        ),
    )
    config = replace(config, agents=tuple(agents))
    decoded = decode_runner_config(encode_runner_config(config))
    assert {agent.cognition.institutional_memory_mode for agent in decoded.agents} == {
        InstitutionalMemoryMode.DETERMINISTIC,
        InstitutionalMemoryMode.DISABLED,
    }


def test_v53_cognition_keyset_is_exact() -> None:
    v52_payload = json.loads(encode_runner_config(_v52()).decode("utf-8"))
    v53_payload = json.loads(encode_runner_config(_base()).decode("utf-8"))
    v52_keys = set(v52_payload["agents"][0]["cognition"])
    v53_keys = set(v53_payload["agents"][0]["cognition"])
    assert v53_keys == {*v52_keys, "institutional_memory_mode"}
    for agent in v52_payload["agents"]:
        assert "institutional_memory_mode" not in agent["cognition"]


def test_v53_keyset_rejects_missing_and_unknown_keys() -> None:
    payload = json.loads(encode_runner_config(_base()).decode("utf-8"))
    for agent in payload["agents"]:
        agent["cognition"].pop("institutional_memory_mode")
    with pytest.raises(RunnerSerializationError):
        decode_runner_config(json.dumps(payload).encode("utf-8"))

    payload = json.loads(encode_runner_config(_base()).decode("utf-8"))
    payload["agents"][0]["cognition"]["institutional_memory_policy"] = "custom"
    with pytest.raises(RunnerSerializationError):
        decode_runner_config(json.dumps(payload).encode("utf-8"))


def test_v53_unknown_enum_rejects() -> None:
    payload = json.loads(encode_runner_config(_base()).decode("utf-8"))
    payload["agents"][0]["cognition"]["institutional_memory_mode"] = "always"
    with pytest.raises(RunnerSerializationError):
        decode_runner_config(json.dumps(payload).encode("utf-8"))


def test_enabled_institutional_memory_rejects_old_schema() -> None:
    config = _v52()
    agents = tuple(
        replace(
            agent,
            cognition=replace(
                agent.cognition,
                institutional_memory_mode=InstitutionalMemoryMode.DETERMINISTIC,
            ),
        )
        for agent in config.agents
    )
    with pytest.raises(ValueError, match="institutional_memory_requires_v53"):
        replace(config, agents=agents)


def test_v53_requires_an_enabled_institutional_owner() -> None:
    with pytest.raises(ValueError, match="v53_requires_institutional_memory"):
        _base(institutional=False)


def test_enabled_owner_needs_its_own_local_mode() -> None:
    with pytest.raises(
        ValueError, match="institutional_memory_requires_local_role_or_procedure"
    ):
        _base(role=False, procedure=False)


def test_v53_composes_with_mediation() -> None:
    config = _base()
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
    config = replace(config, agents=agents)
    decoded = decode_runner_config(encode_runner_config(config))
    assert decoded.schema_version == RUNNER_SCHEMA_VERSION_V53
    assert all(
        agent.cognition.mediation_mode is MediationMode.DETERMINISTIC
        for agent in decoded.agents
    )


def test_v53_accepts_existing_office_profile() -> None:
    config = _base()
    assert config.new_agent_initialization is not None
    initialization = replace(
        config.new_agent_initialization,
        species_defaults_id=SPECIES_DEFAULT_OFFICES_V1,
    )
    updated = replace(config, new_agent_initialization=initialization)
    decoded = decode_runner_config(encode_runner_config(updated))
    assert (
        decoded.new_agent_initialization is not None
        and decoded.new_agent_initialization.species_defaults_id
        == SPECIES_DEFAULT_OFFICES_V1
    )


def test_enum_confusion_is_rejected() -> None:
    config = _base()
    agent = config.agents[0]
    with pytest.raises(TypeError):
        replace(
            agent.cognition,
            institutional_memory_mode=MediationMode.DETERMINISTIC,
        )


def test_unowned_flags_stay_unimplemented() -> None:
    flags = V3CapabilityFlags(institutional_economy=True)
    assert "institutional_economy" in flags.unimplemented_enabled_names()


def test_disabled_composition_keeps_historical_schema() -> None:
    definition = institutionalization_scenario(seed=23, max_ticks=2)
    config = next(
        condition.runner_config
        for condition in definition.conditions
        if condition.condition_id == "bf-institution-on"
    )
    assert config.schema_version == "runner-config-v49"
    assert all(
        agent.cognition.institutional_memory_mode is InstitutionalMemoryMode.DISABLED
        for agent in config.agents
    )


def test_direct_cognition_config_and_fingerprint_parity() -> None:
    from agents.cognition.configuration import (
        CognitionInstitutionalMemoryMode,
        CognitionLoopConfig,
    )
    from agents.cognition.institutional_memory import (
        default_institutional_memory_policy,
    )

    disabled = CognitionLoopConfig()
    assert (
        disabled.institutional_memory_mode is CognitionInstitutionalMemoryMode.DISABLED
    )
    assert disabled.institutional_memory_policy is None
    material = disabled.condition_fingerprint_material()
    assert "institutional_memory_mode" not in material
    assert "institutional_memory_policy_version" not in material

    enabled = CognitionLoopConfig(
        institutional_memory_mode=CognitionInstitutionalMemoryMode.DETERMINISTIC
    )
    assert enabled.institutional_memory_policy is not None
    assert (
        enabled.institutional_memory_policy.version
        == default_institutional_memory_policy().version
    )
    enabled_material = enabled.condition_fingerprint_material()
    assert enabled_material["institutional_memory_mode"] == "deterministic"
    assert (
        enabled_material["institutional_memory_policy_version"]
        == default_institutional_memory_policy().version
    )

    with pytest.raises(TypeError):
        CognitionLoopConfig(
            institutional_memory_mode=InstitutionalMemoryMode.DETERMINISTIC  # type: ignore[arg-type]
        )


def test_cognitive_loop_constructor_forwards_mode_and_policy() -> None:
    from agents.cognition.configuration import (
        CognitionInstitutionalMemoryMode,
        CognitionLoopConfig,
        build_cognitive_loop,
    )
    from agents.cognition.institutional_memory import (
        default_institutional_memory_policy,
    )

    loop = build_cognitive_loop(
        CognitionLoopConfig(
            institutional_memory_mode=CognitionInstitutionalMemoryMode.DETERMINISTIC
        )
    )
    assert (
        loop._institutional_memory_mode
        is CognitionInstitutionalMemoryMode.DETERMINISTIC
    )
    assert (
        loop._institutional_memory_policy.version
        == default_institutional_memory_policy().version
    )


def test_agent_cognition_spec_default_is_disabled() -> None:
    spec = AgentCognitionSpec(agent_id=AgentId("a"))
    assert spec.institutional_memory_mode is InstitutionalMemoryMode.DISABLED


def test_institutional_memory_profile_round_trips_on_v53() -> None:
    from simulation.new_agent_initialization import (
        SPECIES_DEFAULT_INSTITUTIONAL_MEMORY_V1,
    )

    config = _base()
    assert config.new_agent_initialization is not None
    initialization = replace(
        config.new_agent_initialization,
        species_defaults_id=SPECIES_DEFAULT_INSTITUTIONAL_MEMORY_V1,
    )
    updated = replace(config, new_agent_initialization=initialization)
    decoded = decode_runner_config(encode_runner_config(updated))
    assert (
        decoded.new_agent_initialization is not None
        and decoded.new_agent_initialization.species_defaults_id
        == SPECIES_DEFAULT_INSTITUTIONAL_MEMORY_V1
    )


def test_institutional_memory_profile_rejects_v52() -> None:
    from simulation.new_agent_initialization import (
        SPECIES_DEFAULT_INSTITUTIONAL_MEMORY_V1,
    )

    config = _v52()
    initialization = replace(
        config.new_agent_initialization,
        species_defaults_id=SPECIES_DEFAULT_INSTITUTIONAL_MEMORY_V1,
    )
    with pytest.raises(ValueError, match="institutional_memory_profile_requires_v53"):
        replace(config, new_agent_initialization=initialization)


def test_institutional_memory_profile_pack_is_empty_and_fresh() -> None:
    from agents.models import AgentId
    from simulation.new_agent_initialization import (
        SPECIES_DEFAULT_INSTITUTIONAL_MEMORY_V1,
        species_defaults_for,
    )

    first = species_defaults_for(
        SPECIES_DEFAULT_INSTITUTIONAL_MEMORY_V1, agent_id=AgentId("new-a")
    )
    second = species_defaults_for(
        SPECIES_DEFAULT_INSTITUTIONAL_MEMORY_V1, agent_id=AgentId("new-b")
    )
    assert first.cognition.agent_id != second.cognition.agent_id
    assert (
        first.cognition.institutional_memory_mode
        is InstitutionalMemoryMode.DETERMINISTIC
    )
    assert first.cognition.office_succession_mode is OfficeSuccessionMode.DETERMINISTIC
    assert first.cognition.artifact_interpretation_mode.value == "deterministic"
    assert first.cognition.teaching_interaction_mode.value == "deterministic"
    assert first.cognition.institution_concept_mode is InstitutionConceptMode.DISABLED
