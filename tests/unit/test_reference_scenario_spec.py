"""Unit tests for the canonical five-agent reference scenario fixture."""

from __future__ import annotations

import logging

import pytest

from experiments.reference_scenario import (
    REFERENCE_DEATH_TICK,
    REFERENCE_DEFAULT_OVERRIDE_BUDGET,
    REFERENCE_MAX_TICKS,
    REFERENCE_SCENARIO_ID,
    REFERENCE_SCENARIO_VERSION,
    build_reference_scenario,
)
from simulation.runner_models import ImaginationMode, MemoryMode, MortalityMode
from tests.reference_scenario_helpers import (
    REFERENCE_AGENT_IDS,
    assert_reference_shape,
    make_reference_bundle,
)


def test_reference_scenario_shape_and_modes() -> None:
    bundle = make_reference_bundle()
    assert_reference_shape(bundle)
    assert bundle.scenario_id == REFERENCE_SCENARIO_ID
    assert bundle.scenario_version == REFERENCE_SCENARIO_VERSION
    assert bundle.config.stop_policy.max_ticks == REFERENCE_MAX_TICKS
    assert bundle.death_tick == REFERENCE_DEATH_TICK
    assert bundle.override_budget == REFERENCE_DEFAULT_OVERRIDE_BUDGET
    assert bundle.death_tick <= REFERENCE_MAX_TICKS // 2
    assert bundle.config.mortality_mode is MortalityMode.ENABLED
    for agent in bundle.config.agents:
        assert agent.cognition.memory_mode is MemoryMode.RECONSTRUCTIVE
        assert agent.cognition.imagination_mode is ImaginationMode.ENABLED
        assert agent.initial_goals
        assert agent.name is not None


def test_reference_scenario_map_resources_and_milestones() -> None:
    bundle = make_reference_bundle()
    scenario = bundle.config.scenario
    assert len(scenario.locations) == 4
    assert len(scenario.resources) == 2
    assert len(scenario.bodies) == 5
    assert all(body.life_status.value == "alive" for body in scenario.bodies)
    assert any(resource.regeneration_per_tick > 0.0 for resource in scenario.resources)
    assert any(resource.quantity > 0.0 for resource in scenario.resources)
    # Connected: every location has at least one neighbor.
    assert all(location.adjacent for location in scenario.locations)
    assert len(bundle.milestone_ids) == 6
    assert len(bundle.milestone_ids) < 20
    assert bundle.arbiter.override_budget_remaining == bundle.override_budget


def test_reference_scenario_agent_ids_stable() -> None:
    bundle = make_reference_bundle()
    ids = tuple(agent.agent_id.value for agent in bundle.config.agents)
    assert ids == REFERENCE_AGENT_IDS


def test_reference_scenario_rejects_late_death_tick() -> None:
    with pytest.raises(ValueError, match="first half"):
        build_reference_scenario(death_tick=30, max_ticks=48)


def test_reference_scenario_rejects_invalid_budget() -> None:
    with pytest.raises(ValueError, match="override_budget"):
        build_reference_scenario(override_budget=-1)


def test_reference_scenario_logs_are_metadata_only(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.INFO, logger="experiments.reference_scenario"):
        bundle = build_reference_scenario()
    text = caplog.text
    assert REFERENCE_SCENARIO_ID in text
    assert REFERENCE_SCENARIO_VERSION in text
    assert str(REFERENCE_MAX_TICKS) in text
    assert bundle.config_fingerprint[:12] in text or "fingerprint" in text.lower()
    # Forbidden payload fields must never appear in owned logs.
    for fragment in (
        "Mira",
        "secure-food",
        "spring-holds",
        "BerryBush",
        "loc-camp",
        str(bundle.config.seed),
    ):
        assert fragment not in text
