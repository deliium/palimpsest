"""Unit tests for architecture capability validation reason codes."""

from __future__ import annotations

import logging

import pytest

from agents.cognition.architectures import (
    ArchitectureCompatibilityError,
    ArchitectureDefinition,
    ArchitectureModeSnapshot,
    CapabilityDeclaration,
    StageSlot,
    get_architecture,
    snapshot_from_definition,
    validate_architecture_compatibility,
)


def _base_keys() -> dict[StageSlot, str]:
    return {
        StageSlot.PERCEPTION: "literal",
        StageSlot.RETRIEVAL: "reconstructive",
        StageSlot.RECONSTRUCTION: "deterministic",
        StageSlot.BELIEFS: "subjective_revision",
        StageSlot.WORLD_MODEL: "passthrough",
        StageSlot.REFLECTION: "disabled",
        StageSlot.IMAGINATION: "imagination_engine",
        StageSlot.MOTIVATION: "motivation_appraisal",
        StageSlot.THEORY_OF_MIND: "passthrough",
        StageSlot.PLANNING: "command_planner",
    }


def test_validate_succeeds_for_registry_presets() -> None:
    for architecture_id in (
        "reactive_baseline",
        "v1_memory_agent",
        "full_v2_agent",
        "theory_of_mind_agent",
    ):
        definition = get_architecture(architecture_id)
        validate_architecture_compatibility(
            definition, snapshot_from_definition(definition)
        )


def test_architecture_missing_flag(caplog: pytest.LogCaptureFixture) -> None:
    definition = get_architecture("theory_of_mind_agent")
    snapshot = snapshot_from_definition(definition)
    broken = ArchitectureModeSnapshot(
        flags={**snapshot.flags, "advanced_social_inference": False},
        modes=snapshot.modes,
    )
    with caplog.at_level(logging.ERROR, logger="agents.cognition.architectures"):
        with pytest.raises(ArchitectureCompatibilityError) as exc:
            validate_architecture_compatibility(definition, broken)
    assert exc.value.reason_code == "architecture_missing_flag"
    assert "architecture_missing_flag" in caplog.text


def test_architecture_forbidden_flag() -> None:
    definition = get_architecture("reactive_baseline")
    snapshot = snapshot_from_definition(definition)
    broken = ArchitectureModeSnapshot(
        flags={**snapshot.flags, "extended_self_model": True},
        modes=snapshot.modes,
    )
    with pytest.raises(ArchitectureCompatibilityError) as exc:
        validate_architecture_compatibility(definition, broken)
    assert exc.value.reason_code == "architecture_forbidden_flag"


def test_architecture_mode_mismatch() -> None:
    definition = get_architecture("v1_memory_agent")
    snapshot = snapshot_from_definition(definition)
    broken = ArchitectureModeSnapshot(
        flags=snapshot.flags,
        modes={**snapshot.modes, "memory_mode": "reference"},
    )
    with pytest.raises(ArchitectureCompatibilityError) as exc:
        validate_architecture_compatibility(definition, broken)
    assert exc.value.reason_code == "architecture_mode_mismatch"


def test_architecture_slot_unbound() -> None:
    keys = _base_keys()
    del keys[StageSlot.PLANNING]
    definition = ArchitectureDefinition(
        architecture_id="forged_unbound",
        schema_version="runner-config-v4",
        capabilities=CapabilityDeclaration(
            required_slots=frozenset(StageSlot),
            required_modes={
                "memory_mode": "reconstructive",
                "imagination_mode": "enabled",
                "reflection_mode": "disabled",
                "prospective_mode": "disabled",
                "mortality_appraisal": "enabled",
            },
            implementation_keys=keys,
        ),
        implementation_keys=keys,
    )
    with pytest.raises(ArchitectureCompatibilityError) as exc:
        validate_architecture_compatibility(
            definition, snapshot_from_definition(definition)
        )
    assert exc.value.reason_code == "architecture_slot_unbound"


def test_architecture_unknown_impl() -> None:
    keys = _base_keys()
    keys[StageSlot.PERCEPTION] = "not_a_real_impl"
    definition = ArchitectureDefinition(
        architecture_id="forged_unknown_impl",
        schema_version="runner-config-v4",
        capabilities=CapabilityDeclaration(
            required_slots=frozenset(StageSlot),
            required_modes={
                "memory_mode": "reconstructive",
                "imagination_mode": "enabled",
                "reflection_mode": "disabled",
                "prospective_mode": "disabled",
                "mortality_appraisal": "enabled",
            },
            implementation_keys=keys,
        ),
        implementation_keys=keys,
    )
    with pytest.raises(ArchitectureCompatibilityError) as exc:
        validate_architecture_compatibility(
            definition, snapshot_from_definition(definition)
        )
    assert exc.value.reason_code == "architecture_unknown_impl"


def test_architecture_unimplemented_flag_when_required() -> None:
    keys = _base_keys()
    definition = ArchitectureDefinition(
        architecture_id="forged_multi_hop",
        schema_version="runner-config-v4",
        capabilities=CapabilityDeclaration(
            required_flags=frozenset({"multi_hop_testimony_tracking"}),
            required_slots=frozenset(StageSlot),
            required_modes={
                "memory_mode": "reconstructive",
                "imagination_mode": "enabled",
                "reflection_mode": "disabled",
                "prospective_mode": "disabled",
                "mortality_appraisal": "enabled",
            },
            implementation_keys=keys,
        ),
        implementation_keys=keys,
    )
    with pytest.raises(ArchitectureCompatibilityError) as exc:
        validate_architecture_compatibility(
            definition, snapshot_from_definition(definition)
        )
    assert exc.value.reason_code == "architecture_unimplemented_flag"


def test_full_v2_fails_closed_when_multi_hop_forced_on() -> None:
    definition = get_architecture("full_v2_agent")
    snapshot = snapshot_from_definition(
        definition,
        extra_flags={"multi_hop_testimony_tracking": True},
    )
    with pytest.raises(ArchitectureCompatibilityError) as exc:
        validate_architecture_compatibility(definition, snapshot)
    assert exc.value.reason_code == "capability_unimplemented"


def test_full_v2_enables_all_owned_flags() -> None:
    definition = get_architecture("full_v2_agent")
    assert definition.capabilities.required_flags == frozenset(
        {
            "advanced_social_inference",
            "predictive_world_model",
            "extended_self_model",
            "short_term_emotional_state",
        }
    )
    assert "multi_hop_testimony_tracking" not in definition.capabilities.required_flags
    assert definition.capabilities.required_modes["prospective_mode"] == "disabled"
