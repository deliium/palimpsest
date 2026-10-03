"""Registry and digest tests for cognitive architecture presets."""

from __future__ import annotations

import pytest

from agents.cognition.architectures import (
    ARCHITECTURES,
    ArchitectureCompatibilityError,
    ArchitectureDefinition,
    CapabilityDeclaration,
    StageSlot,
    architecture_definition_digest,
    get_architecture,
)

EXPECTED_IDS = (
    "full_v2_agent",
    "imagination_agent",
    "reactive_baseline",
    "reconstructive_memory_agent",
    "reflection_agent",
    "theory_of_mind_agent",
    "v1_memory_agent",
)


def test_seven_architectures_registered() -> None:
    assert sorted(ARCHITECTURES) == list(EXPECTED_IDS)


@pytest.mark.parametrize("architecture_id", EXPECTED_IDS)
def test_get_architecture_returns_preset(architecture_id: str) -> None:
    definition = get_architecture(architecture_id)
    assert definition.architecture_id == architecture_id
    assert frozenset(definition.implementation_keys) == frozenset(StageSlot)


def test_get_architecture_unknown() -> None:
    with pytest.raises(ArchitectureCompatibilityError) as exc:
        get_architecture("not_a_real_architecture")
    assert exc.value.reason_code == "architecture_unknown"


def test_digest_stable_across_calls() -> None:
    definition = get_architecture("v1_memory_agent")
    first = architecture_definition_digest(definition)
    second = architecture_definition_digest(get_architecture("v1_memory_agent"))
    assert first == second
    assert len(first) == 64


def test_digest_changes_when_binding_or_flag_changes() -> None:
    baseline = get_architecture("v1_memory_agent")
    base_digest = architecture_definition_digest(baseline)
    keys = dict(baseline.implementation_keys)
    keys[StageSlot.IMAGINATION] = "present_state"
    mutated_keys = ArchitectureDefinition(
        architecture_id=baseline.architecture_id,
        schema_version=baseline.schema_version,
        capabilities=CapabilityDeclaration(
            required_flags=baseline.capabilities.required_flags,
            forbidden_flags=baseline.capabilities.forbidden_flags,
            required_modes=baseline.capabilities.required_modes,
            forbidden_modes=baseline.capabilities.forbidden_modes,
            required_slots=baseline.capabilities.required_slots,
            implementation_keys=keys,
        ),
        implementation_keys=keys,
    )
    assert architecture_definition_digest(mutated_keys) != base_digest

    flag_mutated = ArchitectureDefinition(
        architecture_id=baseline.architecture_id,
        schema_version=baseline.schema_version,
        capabilities=CapabilityDeclaration(
            required_flags=frozenset({"advanced_social_inference"}),
            forbidden_flags=baseline.capabilities.forbidden_flags
            - frozenset({"advanced_social_inference"}),
            required_modes=baseline.capabilities.required_modes,
            forbidden_modes=baseline.capabilities.forbidden_modes,
            required_slots=baseline.capabilities.required_slots,
            implementation_keys=baseline.implementation_keys,
        ),
        implementation_keys=baseline.implementation_keys,
    )
    assert architecture_definition_digest(flag_mutated) != base_digest


def test_schema_versions_match_locked_table() -> None:
    expected = {
        "reactive_baseline": "runner-config-v4",
        "v1_memory_agent": "runner-config-v4",
        "reconstructive_memory_agent": "runner-config-v4",
        "imagination_agent": "runner-config-v7",
        "reflection_agent": "runner-config-v6",
        "theory_of_mind_agent": "runner-config-v4",
        "full_v2_agent": "runner-config-v6",
    }
    for architecture_id, schema in expected.items():
        assert get_architecture(architecture_id).schema_version == schema
