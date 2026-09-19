"""Effect-complete event records and projection without rules/RNG."""

from __future__ import annotations

import pytest

from agents.models import AgentId
from simulation.lifecycle import ActionResolutionStatus, ActionSubmission
from tests.physical_helpers import (
    checkpoint_restore,
    make_engine,
    objective_fingerprint,
    restore_from_fixture_events,
    run_wait_ticks,
    snapshot_from_engine,
    two_location_fixture,
)
from world.actions import Attack, Take, Wait
from world.events import Attacked, Died, Taken
from world.identifiers import EntityId
from world.models import LifeStatus, copy_body
from world.values import Health

pytestmark = pytest.mark.unit


def test_replay_with_rng_and_rules_patched_to_fail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = two_location_fixture()
    live = make_engine(fixture, seed=55)
    batch = live.observe()
    live.resolve_tick(
        (
            ActionSubmission(
                batch.token, AgentId("agent-1"), Take(EntityId("item-1"))
            ),
            ActionSubmission(batch.token, AgentId("agent-2"), Wait()),
        )
    )
    run_wait_ticks(live, 2)
    events = tuple(live.export_events().events)
    live_fp = objective_fingerprint(live)

    def _boom(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("RNG must not be called during replay projection")

    def _rules_boom(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("physical rules must not run during replay")

    monkeypatch.setattr("simulation.randomness.create_named_stream", _boom)
    monkeypatch.setattr("simulation.randomness.sample_stream", _boom)
    monkeypatch.setattr(
        "world._physical.apply_autonomous_physical_step", _rules_boom
    )

    restored = restore_from_fixture_events(fixture, seed=55, events=events)
    assert objective_fingerprint(restored) == live_fp
    assert restored._snapshot.world.state.items[EntityId("item-1")].holder_id == (
        EntityId("body-1")
    )


def test_live_bootstrap_and_checkpoint_fingerprints_agree() -> None:
    fixture = two_location_fixture()
    live = make_engine(fixture, seed=56)
    batch = live.observe()
    live.resolve_tick(
        (
            ActionSubmission(
                batch.token, AgentId("agent-1"), Take(EntityId("item-1"))
            ),
        )
    )
    run_wait_ticks(live, 1)
    events = tuple(live.export_events().events)
    live_fp = objective_fingerprint(live)

    bootstrap = restore_from_fixture_events(fixture, seed=56, events=events)
    assert objective_fingerprint(bootstrap) == live_fp

    # Checkpoint at head (no further events) matches live objective state.
    checkpoint = checkpoint_restore(live)
    assert (
        checkpoint.tick.value,
        checkpoint.revision.value,
    ) == (live.tick.value, live.revision.value)
    from tests.unit.determinism_helpers import project_world_state

    assert project_world_state(checkpoint._snapshot.world.state) == project_world_state(
        live._snapshot.world.state
    )


def test_attack_events_are_effect_complete_for_projection() -> None:
    fixture = two_location_fixture(item_on_ground=False)
    frail = copy_body(fixture.bodies[1], health=Health(5))
    world = type(fixture)(
        world_id=fixture.world_id,
        locations=fixture.locations,
        bodies=(fixture.bodies[0], frail),
        items=(),
        resources=fixture.resources,
        weather=fixture.weather,
        registrations=fixture.registrations,
        revision=fixture.revision,
    )
    for seed in range(40, 140):
        live = make_engine(world, seed=seed)
        batch = live.observe()
        result = live.resolve_tick(
            (
                ActionSubmission(
                    batch.token, AgentId("agent-1"), Attack(EntityId("body-2"))
                ),
            )
        )
        assert result.resolutions[0].status is ActionResolutionStatus.APPLIED
        attacked = [
            record.event
            for record in result.events
            if type(record.event.details) is Attacked
        ]
        if not attacked or not attacked[0].details.hit:
            continue
        if attacked[0].details.resulting_target_health != 0.0:
            continue
        died = [
            record.event
            for record in result.events
            if type(record.event.details) is Died
        ]
        assert len(died) == 1
        events = tuple(live.export_events().events)
        restored = restore_from_fixture_events(world, seed=seed, events=events)
        assert (
            restored._snapshot.world.state.bodies[EntityId("body-2")].life_status
            is LifeStatus.DEAD
        )
        assert objective_fingerprint(restored) == objective_fingerprint(live)
        return
    pytest.fail("no lethal attack found for effect-complete check")


def test_taken_event_carries_resulting_holder() -> None:
    fixture = two_location_fixture()
    engine = make_engine(fixture, seed=57)
    batch = engine.observe()
    result = engine.resolve_tick(
        (
            ActionSubmission(
                batch.token, AgentId("agent-1"), Take(EntityId("item-1"))
            ),
        )
    )
    taken = next(
        record.event
        for record in result.events
        if type(record.event.details) is Taken
    )
    assert taken.details.resulting_holder_id == EntityId("body-1")
    assert snapshot_from_engine(engine).integrity_hash.value
