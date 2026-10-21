"""Runner-config-v54 institutional decay mode, exact keyset, and gates."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from experiments.institutionalization_scenario import institutionalization_scenario
from simulation.compatibility import COMPATIBILITY_MATRIX
from simulation.new_agent_initialization import (
    SPECIES_DEFAULT_INSTITUTIONAL_MEMORY_V1,
)
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION,
    RUNNER_SCHEMA_VERSION_V4,
    RUNNER_SCHEMA_VERSION_V53,
    RUNNER_SCHEMA_VERSION_V54,
    SUPPORTED_RUNNER_SCHEMA_VERSIONS,
    InstitutionalDecayMode,
    InstitutionalMemoryMode,
    InstitutionConceptMode,
    MediationMode,
    OfficeSuccessionMode,
    SimulationRunnerConfig,
)
from simulation.runner_serialization import (
    RunnerSerializationError,
    decode_runner_config,
    encode_runner_config,
    runner_config_fingerprint,
)


def _base(
    *,
    decay: bool = True,
    concepts: bool = True,
    offices: bool = False,
    memory: bool = True,
    schema_version: str = RUNNER_SCHEMA_VERSION_V54,
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
                institution_concept_mode=(
                    InstitutionConceptMode.DETERMINISTIC
                    if concepts
                    else InstitutionConceptMode.DISABLED
                ),
                office_succession_mode=(
                    OfficeSuccessionMode.DETERMINISTIC
                    if offices
                    else OfficeSuccessionMode.DISABLED
                ),
                institutional_memory_mode=(
                    InstitutionalMemoryMode.DETERMINISTIC
                    if memory
                    else InstitutionalMemoryMode.DISABLED
                ),
                institutional_decay_mode=(
                    InstitutionalDecayMode.DETERMINISTIC
                    if decay
                    else InstitutionalDecayMode.DISABLED
                ),
            ),
        )
        for agent in config.agents
    )
    return replace(config, schema_version=schema_version, agents=agents)


def test_v54_round_trips_with_concepts_only() -> None:
    config = _base(offices=False, memory=False)
    payload = encode_runner_config(config)
    document = json.loads(payload.decode("utf-8"))
    assert document["schema_version"] == RUNNER_SCHEMA_VERSION_V54
    cognition = document["agents"][0]["cognition"]
    assert cognition["institutional_decay_mode"] == "deterministic"
    assert cognition["institutional_memory_mode"] == "disabled"
    decoded = decode_runner_config(payload)
    assert decoded.schema_version == RUNNER_SCHEMA_VERSION_V54
    assert all(
        agent.cognition.institutional_decay_mode is InstitutionalDecayMode.DETERMINISTIC
        for agent in decoded.agents
    )
    assert runner_config_fingerprint(decoded) == runner_config_fingerprint(config)


@pytest.mark.parametrize(
    ("offices", "memory"),
    [
        (False, False),
        (True, False),
        (False, True),
        (True, True),
    ],
)
def test_v54_supported_combinations_round_trip(offices: bool, memory: bool) -> None:
    config = _base(concepts=True, offices=offices, memory=memory)
    decoded = decode_runner_config(encode_runner_config(config))
    assert all(
        agent.cognition.institutional_decay_mode is InstitutionalDecayMode.DETERMINISTIC
        for agent in decoded.agents
    )


def test_v54_cognition_keyset_is_exact() -> None:
    v53_payload = json.loads(
        encode_runner_config(
            _base(
                decay=False,
                memory=True,
                schema_version=RUNNER_SCHEMA_VERSION_V53,
            )
        ).decode("utf-8")
    )
    v54_payload = json.loads(encode_runner_config(_base()).decode("utf-8"))
    v53_keys = set(v53_payload["agents"][0]["cognition"])
    v54_keys = set(v54_payload["agents"][0]["cognition"])
    assert v54_keys == {*v53_keys, "institutional_decay_mode"}
    for agent in v53_payload["agents"]:
        assert "institutional_decay_mode" not in agent["cognition"]


def test_v54_keyset_rejects_missing_and_unknown_keys() -> None:
    payload = json.loads(encode_runner_config(_base()).decode("utf-8"))
    for agent in payload["agents"]:
        agent["cognition"].pop("institutional_decay_mode")
    with pytest.raises(RunnerSerializationError):
        decode_runner_config(json.dumps(payload).encode("utf-8"))

    payload = json.loads(encode_runner_config(_base()).decode("utf-8"))
    payload["agents"][0]["cognition"]["institutional_decay_policy"] = "custom"
    with pytest.raises(RunnerSerializationError):
        decode_runner_config(json.dumps(payload).encode("utf-8"))


def test_v54_unknown_enum_rejects() -> None:
    payload = json.loads(encode_runner_config(_base()).decode("utf-8"))
    payload["agents"][0]["cognition"]["institutional_decay_mode"] = "always"
    with pytest.raises(RunnerSerializationError):
        decode_runner_config(json.dumps(payload).encode("utf-8"))


def test_enabled_decay_rejects_old_schema() -> None:
    with pytest.raises(ValueError, match="institutional_decay_requires_v54"):
        _base(schema_version=RUNNER_SCHEMA_VERSION_V53, memory=True)


def test_v54_requires_an_enabled_decay_owner() -> None:
    with pytest.raises(ValueError, match="v54_requires_institutional_decay"):
        _base(decay=False)


def test_enabled_decay_requires_same_owner_concepts() -> None:
    with pytest.raises(ValueError, match="institutional_decay_requires_local_concepts"):
        _base(concepts=False)


def test_decay_prerequisite_is_per_owner() -> None:
    config = _base()
    agents = list(config.agents)
    agents[0] = replace(
        agents[0],
        cognition=replace(
            agents[0].cognition,
            institution_concept_mode=InstitutionConceptMode.DISABLED,
        ),
    )
    with pytest.raises(ValueError, match="institutional_decay_requires_local_concepts"):
        replace(config, agents=tuple(agents))


def test_v54_mixed_owners_round_trip() -> None:
    config = _base()
    agents = list(config.agents)
    agents[0] = replace(
        agents[0],
        cognition=replace(
            agents[0].cognition,
            institutional_decay_mode=InstitutionalDecayMode.DISABLED,
            institutional_memory_mode=InstitutionalMemoryMode.DISABLED,
        ),
    )
    config = replace(config, agents=tuple(agents))
    decoded = decode_runner_config(encode_runner_config(config))
    assert {agent.cognition.institutional_decay_mode for agent in decoded.agents} == {
        InstitutionalDecayMode.DETERMINISTIC,
        InstitutionalDecayMode.DISABLED,
    }


def test_v54_composes_with_mediation() -> None:
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
    assert decoded.schema_version == RUNNER_SCHEMA_VERSION_V54
    assert all(
        agent.cognition.mediation_mode is MediationMode.DETERMINISTIC
        for agent in decoded.agents
    )


def test_v53_institutional_memory_roundtrip_is_unchanged() -> None:
    config = _base(
        decay=False,
        memory=True,
        schema_version=RUNNER_SCHEMA_VERSION_V53,
    )
    decoded = decode_runner_config(encode_runner_config(config))
    assert decoded.schema_version == RUNNER_SCHEMA_VERSION_V53
    assert all(
        agent.cognition.institutional_memory_mode
        is InstitutionalMemoryMode.DETERMINISTIC
        for agent in decoded.agents
    )


def test_institutional_memory_profile_is_accepted_on_v53_and_v54() -> None:
    for schema_version in (
        RUNNER_SCHEMA_VERSION_V53,
        RUNNER_SCHEMA_VERSION_V54,
    ):
        config = _base(
            decay=schema_version == RUNNER_SCHEMA_VERSION_V54,
            memory=True,
            schema_version=schema_version,
        )
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


def test_default_write_version_is_unchanged() -> None:
    assert RUNNER_SCHEMA_VERSION == RUNNER_SCHEMA_VERSION_V4
    assert RUNNER_SCHEMA_VERSION_V54 in SUPPORTED_RUNNER_SCHEMA_VERSIONS
    entry = COMPATIBILITY_MATRIX["runner_config"]
    assert entry.write_version == RUNNER_SCHEMA_VERSION_V4
    assert RUNNER_SCHEMA_VERSION_V54 in entry.accepted_restore


def test_disabled_composition_keeps_fingerprint_unchanged() -> None:
    first = _base(decay=False, schema_version=RUNNER_SCHEMA_VERSION_V53)
    second = _base(decay=False, schema_version=RUNNER_SCHEMA_VERSION_V53)
    assert runner_config_fingerprint(first) == runner_config_fingerprint(second)
    with_decay = _base()
    assert runner_config_fingerprint(with_decay) != runner_config_fingerprint(first)


def test_direct_cognition_config_and_fingerprint_parity() -> None:
    from agents.cognition.configuration import (
        CognitionInstitutionalDecayMode,
        CognitionInstitutionConceptMode,
        CognitionLoopConfig,
    )
    from agents.cognition.institutional_decay import (
        default_institutional_decay_policy,
    )

    disabled = CognitionLoopConfig()
    assert disabled.institutional_decay_mode is (
        CognitionInstitutionalDecayMode.DISABLED
    )
    assert disabled.institutional_decay_policy is None
    material = disabled.condition_fingerprint_material()
    assert "institutional_decay_mode" not in material
    assert "institutional_decay_policy_version" not in material

    enabled = CognitionLoopConfig(
        institution_concept_mode=CognitionInstitutionConceptMode.DETERMINISTIC,
        institutional_decay_mode=CognitionInstitutionalDecayMode.DETERMINISTIC,
    )
    assert enabled.institutional_decay_policy is not None
    assert (
        enabled.institutional_decay_policy.version
        == default_institutional_decay_policy().version
    )
    enabled_material = enabled.condition_fingerprint_material()
    assert enabled_material["institutional_decay_mode"] == "deterministic"
    assert (
        enabled_material["institutional_decay_policy_version"]
        == default_institutional_decay_policy().version
    )

    with pytest.raises(TypeError):
        CognitionLoopConfig(
            institutional_decay_mode=InstitutionalDecayMode.DETERMINISTIC  # type: ignore[arg-type]
        )


def test_cognitive_loop_constructor_forwards_mode_and_policy() -> None:
    from agents.cognition.configuration import (
        CognitionInstitutionalDecayMode,
        CognitionInstitutionConceptMode,
        CognitionLoopConfig,
        build_cognitive_loop,
    )
    from agents.cognition.institutional_decay import (
        default_institutional_decay_policy,
    )

    loop = build_cognitive_loop(
        CognitionLoopConfig(
            institution_concept_mode=CognitionInstitutionConceptMode.DETERMINISTIC,
            institutional_decay_mode=CognitionInstitutionalDecayMode.DETERMINISTIC,
        )
    )
    assert (
        loop._institutional_decay_mode is CognitionInstitutionalDecayMode.DETERMINISTIC
    )
    policy = loop._institutional_decay_policy
    assert policy is not None
    assert policy.version == default_institutional_decay_policy().version


def test_cognitive_loop_constructor_rejects_decay_without_concepts() -> None:
    from agents.cognition.configuration import (
        CognitionInstitutionalDecayMode,
        CognitionLoopConfig,
    )

    with pytest.raises(ValueError, match="institutional_decay_requires_local_concepts"):
        CognitionLoopConfig(
            institutional_decay_mode=(CognitionInstitutionalDecayMode.DETERMINISTIC)
        )


def test_agent_cognition_spec_default_is_disabled() -> None:
    from agents.models import AgentId
    from simulation.runner_models import AgentCognitionSpec

    spec = AgentCognitionSpec(agent_id=AgentId("a"))
    assert spec.institutional_decay_mode is InstitutionalDecayMode.DISABLED
