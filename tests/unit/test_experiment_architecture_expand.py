"""Expand architectures to runner configs under schema exclusivity rules."""

from __future__ import annotations

import pytest

from agents.cognition.architectures import ARCHITECTURES, get_architecture
from experiments.architectures import (
    expand_architecture,
    mode_snapshot_from_runner_config,
)
from simulation.runner_models import (
    ImaginationMode,
    MemoryMode,
    MortalityMode,
    ProspectiveImaginationMode,
    ReflectionMode,
    V2CapabilityFlags,
)
from tests.unit.test_runner_models import _config


@pytest.mark.parametrize("architecture_id", sorted(ARCHITECTURES))
def test_expand_constructs_without_schema_reason_codes(architecture_id: str) -> None:
    base = _config()
    expanded = expand_architecture(base, architecture_id)
    definition = get_architecture(architecture_id)
    assert expanded.schema_version == definition.schema_version
    # Construction already validated exclusivity (v6 reflection / v7 prospective).
    cognition = expanded.agents[0].cognition
    modes = definition.capabilities.required_modes
    assert cognition.memory_mode is MemoryMode(modes["memory_mode"])
    assert cognition.imagination_mode is ImaginationMode(modes["imagination_mode"])
    assert cognition.reflection_mode is ReflectionMode(modes["reflection_mode"])
    assert cognition.prospective_mode is ProspectiveImaginationMode(
        modes["prospective_mode"]
    )
    assert expanded.mortality_mode is MortalityMode(modes["mortality_appraisal"])


def test_expand_sets_capability_flags_for_tom_and_full_v2() -> None:
    base = _config()
    tom = expand_architecture(base, "theory_of_mind_agent")
    assert tom.capability_flags == V2CapabilityFlags(advanced_social_inference=True)
    full = expand_architecture(base, "full_v2_agent")
    assert full.capability_flags == V2CapabilityFlags(
        advanced_social_inference=True,
        predictive_world_model=True,
        extended_self_model=True,
        short_term_emotional_state=True,
    )
    assert full.capability_flags.multi_hop_testimony_tracking is False


def test_expand_preserves_seed_scenario_identity() -> None:
    base = _config(seed=42)
    expanded = expand_architecture(base, "reflection_agent")
    assert expanded.seed == base.seed
    assert expanded.scenario == base.scenario
    assert expanded.stochastic_identity == base.stochastic_identity
    assert expanded.cognition_trace.enabled is False


def test_mode_snapshot_round_trip() -> None:
    base = _config()
    expanded = expand_architecture(base, "imagination_agent")
    snapshot = mode_snapshot_from_runner_config(expanded)
    assert snapshot.modes["prospective_mode"] == "deterministic"
    assert snapshot.modes["memory_mode"] == "reconstructive"
