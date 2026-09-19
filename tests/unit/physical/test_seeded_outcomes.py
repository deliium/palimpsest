"""Seeded determinism, stream scopes, and rules-fingerprint separation."""

from __future__ import annotations

import logging

import pytest
from hypothesis import given, settings

from agents.models import AgentId
from simulation.identifiers import derive_run_id
from simulation.lifecycle import ActionSubmission, EngineDiagnosticCode
from simulation.randomness import StreamScope, sample_stream
from tests.physical_helpers import (
    complete_fingerprint,
    make_engine,
    physical_config,
    run_wait_ticks,
    seeds,
    two_location_fixture,
)
from world.actions import Take, Wait
from world.identifiers import EntityId
from world.models import (
    PhysicalRules,
    default_physical_rules,
    physical_rules_fingerprint,
)

pytestmark = pytest.mark.unit

_ENGINE_LOGGER = "simulation.engine"


def test_same_seed_trajectories_are_byte_identical() -> None:
    fixture = two_location_fixture()
    left = make_engine(fixture, seed=77)
    right = make_engine(fixture, seed=77)
    for engine in (left, right):
        batch = engine.observe()
        engine.resolve_tick(
            (
                ActionSubmission(
                    batch.token, AgentId("agent-1"), Take(EntityId("item-1"))
                ),
                ActionSubmission(batch.token, AgentId("agent-2"), Wait()),
            )
        )
        run_wait_ticks(engine, 3)
    assert complete_fingerprint(left) == complete_fingerprint(right)


def test_golden_seed_pair_diverges() -> None:
    fixture = two_location_fixture()
    left = make_engine(fixture, seed=100)
    right = make_engine(fixture, seed=101)
    for engine in (left, right):
        batch = engine.observe()
        engine.resolve_tick(
            (
                ActionSubmission(
                    batch.token, AgentId("agent-1"), Take(EntityId("item-1"))
                ),
            )
        )
        run_wait_ticks(engine, 2)
    assert complete_fingerprint(left) != complete_fingerprint(right)


def test_rules_fingerprint_separates_equal_seeds() -> None:
    left_rules = default_physical_rules()
    right_rules = PhysicalRules(move_fatigue=6.0)
    assert physical_rules_fingerprint(left_rules) != physical_rules_fingerprint(
        right_rules
    )
    left = physical_config(42, rules=left_rules)
    right = physical_config(42, rules=right_rules)
    assert derive_run_id(left) != derive_run_id(right)
    scope = StreamScope(namespace="physical", names=("search", "req-1"))
    assert sample_stream(left, scope, 4) != sample_stream(right, scope, 4)


def test_distinct_stream_scopes_do_not_perturb() -> None:
    config = physical_config(9)
    search = StreamScope(
        namespace="action",
        names=("search", "tick-0", "ordinal-0"),
    )
    attack = StreamScope(
        namespace="action",
        names=("attack", "tick-0", "ordinal-0"),
    )
    weather = StreamScope(
        namespace="system",
        names=("weather", "tick-5", "loc-1"),
    )
    samples = {
        "search": sample_stream(config, search, 8),
        "attack": sample_stream(config, attack, 8),
        "weather": sample_stream(config, weather, 8),
    }
    assert len({samples["search"], samples["attack"], samples["weather"]}) == 3
    # Re-sampling search after other scopes is stable.
    assert sample_stream(config, search, 8) == samples["search"]


@given(seed=seeds)
@settings(max_examples=15, deadline=None)
def test_property_same_seed_engine_fingerprints(seed: int) -> None:
    fixture = two_location_fixture(item_on_ground=False)
    left = make_engine(fixture, seed=seed)
    right = make_engine(fixture, seed=seed)
    run_wait_ticks(left, 2)
    run_wait_ticks(right, 2)
    assert complete_fingerprint(left) == complete_fingerprint(right)


def test_diagnostics_codes_independent_of_seed_outcome(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger=_ENGINE_LOGGER)
    fixture = two_location_fixture(item_on_ground=False)
    for seed in (1, 2, 3):
        caplog.clear()
        engine = make_engine(fixture, seed=seed)
        engine.observe()
        engine.resolve_tick(())
        messages = " ".join(record.getMessage() for record in caplog.records)
        assert EngineDiagnosticCode.TICK_COMMITTED.value in messages
        assert "seed=" not in messages
        assert "WorldState" not in messages
