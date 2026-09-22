"""Bounded Hypothesis properties for reference-scenario topology/seed/order."""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from experiments.reference_scenario import (
    REFERENCE_DEATH_TICK,
    REFERENCE_MAX_TICKS,
    build_reference_scenario,
)
from simulation.runner_serialization import runner_config_fingerprint
from tests.reference_scenario_helpers import (
    REFERENCE_AGENT_IDS,
    day_night_phases,
    make_reference_bundle,
)
from world.models import DayPhase

pytestmark = pytest.mark.unit


@given(seed=st.integers(min_value=1, max_value=10_000))
@settings(max_examples=12, deadline=None)
def test_seed_changes_config_fingerprint(seed: int) -> None:
    left = build_reference_scenario(seed=seed)
    right = build_reference_scenario(seed=seed + 1)
    assert runner_config_fingerprint(left.config) != runner_config_fingerprint(
        right.config
    )
    # Topology (locations/resources/bodies) is seed-invariant.
    assert len(left.config.scenario.locations) == len(right.config.scenario.locations)
    assert len(left.config.scenario.resources) == len(right.config.scenario.resources)
    assert len(left.config.scenario.bodies) == len(right.config.scenario.bodies)


@given(
    death_tick=st.integers(min_value=10, max_value=REFERENCE_MAX_TICKS // 2),
)
@settings(max_examples=8, deadline=None)
def test_death_tick_stays_in_first_half(death_tick: int) -> None:
    bundle = build_reference_scenario(death_tick=death_tick)
    assert bundle.death_tick == death_tick
    assert bundle.death_tick <= bundle.config.stop_policy.max_ticks // 2
    assert len(bundle.milestone_ids) >= 1


@given(data=st.data())
@settings(max_examples=10, deadline=None)
def test_agent_order_permutation_preserves_id_set(data: st.DataObject) -> None:
    bundle = make_reference_bundle()
    agents = list(bundle.config.agents)
    shuffled = data.draw(st.permutations(agents))
    assert {agent.agent_id.value for agent in shuffled} == set(REFERENCE_AGENT_IDS)
    assert len(shuffled) == 5


def test_topology_connected_and_day_night_cover() -> None:
    bundle = make_reference_bundle()
    locations = bundle.config.scenario.locations
    assert all(location.adjacent for location in locations)
    # Undirected adjacency: every edge has a reverse.
    adj = {
        location.entity_id.value: {item.value for item in location.adjacent}
        for location in locations
    }
    for source, neighbors in adj.items():
        for neighbor in neighbors:
            assert source in adj[neighbor]
    phases = day_night_phases(bundle)
    assert DayPhase.DAY in phases and DayPhase.NIGHT in phases
    assert bundle.death_tick == REFERENCE_DEATH_TICK
