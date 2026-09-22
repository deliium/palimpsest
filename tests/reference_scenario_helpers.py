"""Shared helpers for reference-scenario unit tests (metadata-only assertions)."""

from __future__ import annotations

from experiments.reference_scenario import (
    AGENT_KAI,
    AGENT_MIRA,
    AGENT_NYX,
    AGENT_ROWAN,
    AGENT_SOREN,
    REFERENCE_DEATH_TICK,
    REFERENCE_DEFAULT_OVERRIDE_BUDGET,
    REFERENCE_MAX_TICKS,
    REFERENCE_SCENARIO_ID,
    REFERENCE_SCENARIO_VERSION,
    ReferenceScenarioBundle,
    build_reference_scenario,
)

REFERENCE_AGENT_IDS: tuple[str, ...] = (
    AGENT_MIRA,
    AGENT_KAI,
    AGENT_ROWAN,
    AGENT_SOREN,
    AGENT_NYX,
)


def make_reference_bundle(
    *,
    override_budget: int = REFERENCE_DEFAULT_OVERRIDE_BUDGET,
    death_tick: int = REFERENCE_DEATH_TICK,
    max_ticks: int = REFERENCE_MAX_TICKS,
) -> ReferenceScenarioBundle:
    """Build the canonical reference scenario for unit assertions."""
    return build_reference_scenario(
        override_budget=override_budget,
        death_tick=death_tick,
        max_ticks=max_ticks,
    )


def assert_reference_shape(bundle: ReferenceScenarioBundle) -> None:
    """Assert public scenario shape without inspecting payload content."""
    assert bundle.scenario_id == REFERENCE_SCENARIO_ID
    assert bundle.scenario_version == REFERENCE_SCENARIO_VERSION
    assert bundle.config.stop_policy.max_ticks == REFERENCE_MAX_TICKS or (
        bundle.config.stop_policy.max_ticks >= 1
    )
    assert len(bundle.config.agents) == 5
    assert {agent.agent_id.value for agent in bundle.config.agents} == set(
        REFERENCE_AGENT_IDS
    )
    assert len(bundle.config.scenario.locations) >= 2
    assert len(bundle.config.scenario.resources) >= 2
    assert bundle.death_tick <= bundle.config.stop_policy.max_ticks // 2
    assert bundle.override_budget == bundle.arbiter.override_budget
    assert len(bundle.milestone_ids) >= 1
    assert len(bundle.milestone_ids) <= bundle.override_budget
