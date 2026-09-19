"""Target world scale: 5/10 and 10/20 agents/locations with fingerprints."""

from __future__ import annotations

import logging

import pytest

from agents.models import AgentId
from simulation.lifecycle import ActionSubmission, EngineDiagnosticCode
from tests.physical_helpers import (
    checkpoint_restore,
    complete_fingerprint,
    make_engine,
    objective_fingerprint,
    restore_from_fixture_events,
    run_autonomous_ticks,
    run_wait_ticks,
    scaled_fixture,
)
from world.actions import Move, Search, Take, Wait
from world.identifiers import EntityId

pytestmark = pytest.mark.unit

_ENGINE_LOGGER = "simulation.engine"


def _mixed_scenario(engine, *, agents: int, locations: int) -> None:
    """Run a mixed movement/search/take/wait/autonomous sequence."""
    batch = engine.observe()
    submissions: list[ActionSubmission] = []
    # First agent takes local item if present.
    submissions.append(
        ActionSubmission(
            batch.token,
            AgentId("agent-00"),
            Take(EntityId("item-00")),
        )
    )
    if agents > 1:
        submissions.append(
            ActionSubmission(batch.token, AgentId("agent-01"), Search())
        )
    if agents > 2 and locations > 1:
        submissions.append(
            ActionSubmission(
                batch.token,
                AgentId("agent-02"),
                Move(EntityId("loc-01")),
            )
        )
    for index in range(3, min(agents, 5)):
        submissions.append(
            ActionSubmission(
                batch.token, AgentId(f"agent-{index:02d}"), Wait()
            )
        )
    engine.resolve_tick(tuple(submissions))
    run_wait_ticks(engine, 2)
    run_autonomous_ticks(engine, 1)


@pytest.mark.parametrize(
    ("agents", "locations"),
    [
        (5, 10),
        (10, 20),
    ],
)
def test_scaled_world_same_seed_fingerprints(
    agents: int, locations: int, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG, logger=_ENGINE_LOGGER)
    fixture = scaled_fixture(agents=agents, locations=locations)
    left = make_engine(fixture, seed=2026)
    right = make_engine(fixture, seed=2026)
    _mixed_scenario(left, agents=agents, locations=locations)
    _mixed_scenario(right, agents=agents, locations=locations)
    assert complete_fingerprint(left) == complete_fingerprint(right)

    events = tuple(left.export_events().events)
    bootstrap = restore_from_fixture_events(fixture, seed=2026, events=events)
    assert objective_fingerprint(bootstrap) == objective_fingerprint(left)

    checkpoint = checkpoint_restore(left)
    assert objective_fingerprint(checkpoint)[:2] == (
        left.tick.value,
        left.revision.value,
    )
    from tests.unit.determinism_helpers import project_world_state

    assert project_world_state(checkpoint._snapshot.world.state) == project_world_state(
        left._snapshot.world.state
    )

    messages = " ".join(record.getMessage() for record in caplog.records)
    assert EngineDiagnosticCode.TICK_COMMITTED.value in messages
    assert "seed=" not in messages
    assert "inventory" not in messages


def test_scaled_divergent_seeds_differ() -> None:
    fixture = scaled_fixture(agents=5, locations=10)
    left = make_engine(fixture, seed=1)
    right = make_engine(fixture, seed=2)
    _mixed_scenario(left, agents=5, locations=10)
    _mixed_scenario(right, agents=5, locations=10)
    assert complete_fingerprint(left) != complete_fingerprint(right)
