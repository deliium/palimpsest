"""Deterministic WorldEngine replay proofs."""

from __future__ import annotations

import random
from collections.abc import Callable, Sequence

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from agents.models import AgentId
from simulation.bootstrap import AgentRegistration, WorldBootstrap
from simulation.engine import WorldEngine
from simulation.lifecycle import (
    ActionResolution,
    ActionResolutionStatus,
    ActionSubmission,
    TickResult,
    TickToken,
)
from simulation.models import SimulationRunConfig
from simulation.serialization import encode_domain
from tests.unit.determinism_helpers import project_world_state
from world.actions import Drop, Give, Move, Take, Wait
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import AgentBody, Item, LifeStatus, Location
from world.values import Fatigue, Health, Hunger, TemperatureCelsius, Thirst

SubmissionFactory = Callable[[TickToken], Sequence[ActionSubmission]]


def _body(
    entity_id: str,
    *,
    inventory: tuple[EntityId, ...] = (),
    life_status: LifeStatus = LifeStatus.ALIVE,
) -> AgentBody:
    health = Health(0) if life_status is LifeStatus.DEAD else Health(100)
    return AgentBody(
        entity_id=EntityId(entity_id),
        location_id=EntityId("loc-1"),
        health=health,
        hunger=Hunger(0),
        thirst=Thirst(0),
        fatigue=Fatigue(0),
        temperature=TemperatureCelsius(36.5),
        inventory=inventory,
        life_status=life_status,
    )


def _bootstrap(
    *,
    bodies: tuple[AgentBody, ...] | None = None,
    items: tuple[Item, ...] | None = None,
) -> WorldBootstrap:
    if bodies is None:
        bodies = (_body("body-1"), _body("body-2"))
    if items is None:
        items = (
            Item(
                entity_id=EntityId("item-1"),
                name="Rock",
                location_id=EntityId("loc-1"),
            ),
        )
    return WorldBootstrap(
        world_id=WorldId("world-1"),
        revision=WorldRevision(0),
        locations=(Location(entity_id=EntityId("loc-1"), name="Camp"),),
        items=items,
        bodies=bodies,
        registrations=(
            AgentRegistration(AgentId("agent-1"), EntityId("body-1")),
            AgentRegistration(AgentId("agent-2"), EntityId("body-2")),
        ),
    )


def _engine(seed: int = 7, bootstrap: WorldBootstrap | None = None) -> WorldEngine:
    return WorldEngine(
        config=SimulationRunConfig(seed=seed),
        bootstrap=bootstrap if bootstrap is not None else _bootstrap(),
    )


def _fingerprint(
    engine: WorldEngine, result_events: tuple[object, ...] | None = None
) -> tuple[object, ...]:
    export_bytes = encode_domain(engine.export_events())
    return (
        project_world_state(engine._snapshot.world.state),
        engine.tick.value,
        engine.revision.value,
        result_events,
        export_bytes,
    )


def _resolution_tuple(result: TickResult) -> tuple[tuple[object, ...], ...]:
    return tuple(
        (
            item.ordinal,
            item.agent_id.value,
            item.status.value,
            item.reason.value,
            item.request_id.value,
            item.base_revision.value,
            item.resulting_revision.value,
        )
        for item in result.resolutions
    )


def _event_tuple(result: TickResult) -> tuple[tuple[object, ...], ...]:
    return tuple(
        (
            record.sequence,
            record.event.event_id.value,
            record.event.request_id.value,
            record.event.revision.value,
            record.event.details.kind,
        )
        for record in result.events
    )


def _run_once(
    seed: int,
    submissions_factory: SubmissionFactory,
    *,
    bootstrap: WorldBootstrap | None = None,
) -> tuple[
    tuple[object, ...],
    tuple[tuple[object, ...], ...],
    tuple[tuple[object, ...], ...],
]:
    engine = _engine(seed, bootstrap)
    batch = engine.observe()
    result = engine.resolve_tick(submissions_factory(batch.token))
    return (
        _fingerprint(engine, _event_tuple(result)),
        _resolution_tuple(result),
        _event_tuple(result),
    )


def test_fixed_trace_replays_identically_despite_global_rng() -> None:
    def submissions(token: TickToken) -> Sequence[ActionSubmission]:
        return (
            ActionSubmission(token, AgentId("agent-1"), Take(EntityId("item-1"))),
            ActionSubmission(token, AgentId("agent-2"), Wait()),
        )

    random.seed(12345)
    first = _run_once(7, submissions)
    random.seed(99999)
    _ = random.random()
    second = _run_once(7, submissions)
    assert first == second
    assert random.getstate() is not None


@given(
    seed=st.integers(min_value=0, max_value=10_000),
    include_take=st.booleans(),
)
@settings(max_examples=20, deadline=None)
def test_property_short_traces_replay(seed: int, include_take: bool) -> None:
    def submissions(token: TickToken) -> Sequence[ActionSubmission]:
        if include_take:
            return (
                ActionSubmission(token, AgentId("agent-1"), Take(EntityId("item-1"))),
                ActionSubmission(token, AgentId("agent-2"), Wait()),
            )
        return (
            ActionSubmission(token, AgentId("agent-1"), Wait()),
            ActionSubmission(token, AgentId("agent-2"), Wait()),
        )

    assert _run_once(seed, submissions) == _run_once(seed, submissions)


def test_empty_and_event_only_ticks_are_deterministic() -> None:
    empty = _run_once(3, lambda _token: ())
    assert empty == _run_once(3, lambda _token: ())

    def waits(token: TickToken) -> Sequence[ActionSubmission]:
        return (ActionSubmission(token, AgentId("agent-1"), Wait()),)

    assert _run_once(4, waits) == _run_once(4, waits)
    _, _, events = _run_once(4, waits)
    assert events[0][3] == 0  # event-only retains starting revision


def test_take_drop_give_conflict_and_deferred_are_deterministic() -> None:
    def take_conflict(token: TickToken) -> Sequence[ActionSubmission]:
        return (
            ActionSubmission(token, AgentId("agent-1"), Take(EntityId("item-1"))),
            ActionSubmission(token, AgentId("agent-2"), Take(EntityId("item-1"))),
        )

    assert _run_once(5, take_conflict) == _run_once(5, take_conflict)
    (_, resolutions, _) = _run_once(5, take_conflict)
    assert resolutions[0][2] == ActionResolutionStatus.APPLIED.value
    assert resolutions[1][2] == ActionResolutionStatus.CONFLICTED.value

    owned = _bootstrap(
        bodies=(_body("body-1", inventory=(EntityId("item-1"),)), _body("body-2")),
        items=(
            Item(
                entity_id=EntityId("item-1"),
                name="Rock",
                holder_id=EntityId("body-1"),
            ),
        ),
    )

    def give_then_drop(token: TickToken) -> Sequence[ActionSubmission]:
        return (
            ActionSubmission(
                token,
                AgentId("agent-1"),
                Give(EntityId("body-2"), EntityId("item-1")),
            ),
            ActionSubmission(token, AgentId("agent-2"), Drop(EntityId("item-1"))),
        )

    assert _run_once(6, give_then_drop, bootstrap=owned) == _run_once(
        6, give_then_drop, bootstrap=owned
    )

    def deferred(token: TickToken) -> Sequence[ActionSubmission]:
        return (ActionSubmission(token, AgentId("agent-1"), Move(EntityId("loc-1"))),)

    (_, resolutions, events) = _run_once(8, deferred)
    assert resolutions[0][2] == ActionResolutionStatus.DEFERRED_POLICY.value
    assert events == ()


def test_duplicate_omitted_dead_invalid_and_stale_are_deterministic() -> None:
    def duplicate(token: TickToken) -> Sequence[ActionSubmission]:
        return (
            ActionSubmission(token, AgentId("agent-1"), Wait()),
            ActionSubmission(token, AgentId("agent-1"), Wait()),
        )

    assert _run_once(9, duplicate) == _run_once(9, duplicate)

    dead = _bootstrap(
        bodies=(
            _body("body-1", life_status=LifeStatus.DEAD),
            _body("body-2"),
        )
    )

    def dead_actor(token: TickToken) -> Sequence[ActionSubmission]:
        return (ActionSubmission(token, AgentId("agent-1"), Wait()),)

    (_, resolutions, events) = _run_once(10, dead_actor, bootstrap=dead)
    assert resolutions[0][2] == ActionResolutionStatus.DEAD_ACTOR.value
    assert events == ()

    def invalid_target(token: TickToken) -> Sequence[ActionSubmission]:
        return (
            ActionSubmission(token, AgentId("agent-1"), Take(EntityId("missing"))),
        )

    assert _run_once(11, invalid_target) == _run_once(11, invalid_target)

    engine = _engine(12)
    first_token = engine.observe().token
    engine.resolve_tick((ActionSubmission(first_token, AgentId("agent-1"), Wait()),))
    second_token = engine.observe().token
    before = project_world_state(engine._snapshot.world.state)
    tick_before = engine.tick.value
    with pytest.raises(ValueError, match=r"stale|mismatch"):
        engine.resolve_tick(
            (ActionSubmission(first_token, AgentId("agent-2"), Wait()),)
        )
    assert project_world_state(engine._snapshot.world.state) == before
    assert engine.tick.value == tick_before
    # Current token still usable after rejected stale submission.
    engine.resolve_tick((ActionSubmission(second_token, AgentId("agent-2"), Wait()),))


def test_failed_candidate_preserves_snapshot_and_retries_deterministically() -> None:
    engine = _engine(13)
    token = engine.observe().token
    before = _fingerprint(engine)
    with pytest.raises(TypeError):
        engine.resolve_tick(object())  # type: ignore[arg-type]
    assert _fingerprint(engine) == before
    result = engine.resolve_tick(
        (ActionSubmission(token, AgentId("agent-1"), Wait()),)
    )
    fresh = _engine(13)
    fresh_token = fresh.observe().token
    fresh_result = fresh.resolve_tick(
        (ActionSubmission(fresh_token, AgentId("agent-1"), Wait()),)
    )
    assert _resolution_tuple(result) == _resolution_tuple(fresh_result)
    assert _event_tuple(result) == _event_tuple(fresh_result)
    assert project_world_state(engine._snapshot.world.state) == project_world_state(
        fresh._snapshot.world.state
    )
    assert isinstance(result.resolutions[0], ActionResolution)
