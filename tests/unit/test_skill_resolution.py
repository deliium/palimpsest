"""Objective skill modifiers stay inside WorldEngine resolution."""

from __future__ import annotations

import logging

import pytest

from agents.cognition.competence import empty_competence_model
from agents.models import AgentId
from simulation.engine import WorldEngine
from simulation.lifecycle import ActionResolutionStatus, ActionSubmission
from tests.physical_helpers import make_engine, physical_config, two_location_fixture
from world._skills import (
    ObjectiveSkillLedger,
    SkillDomain,
    default_objective_skill_policy,
)
from world.actions import Help, Move, Search
from world.events import Helped, Searched
from world.identifiers import EntityId
from world.models import copy_body
from world.values import Health

pytestmark = pytest.mark.unit


def _ledger(*pairs: tuple[str, SkillDomain, float]) -> ObjectiveSkillLedger:
    entities = tuple(
        dict.fromkeys(EntityId(entity) for entity, _domain, _level in pairs)
    )
    ledger = ObjectiveSkillLedger.bootstrap(entities or (EntityId("body-1"),))
    additions: dict[EntityId, dict[SkillDomain, float]] = {}
    for entity, domain, level in pairs:
        additions.setdefault(EntityId(entity), {})[domain] = level
    return ledger.apply_summed_deltas(additions)


def _engine(
    seed: int,
    *,
    policy: object | None = None,
    enabled: tuple[str, ...] = (),
    ledger: ObjectiveSkillLedger | None = None,
    wounded: bool = False,
) -> WorldEngine:
    fixture = two_location_fixture(item_on_ground=False)
    if wounded:
        bodies = list(fixture.bodies)
        bodies[1] = copy_body(bodies[1], health=Health(40.0))
        fixture = type(fixture)(
            world_id=fixture.world_id,
            locations=fixture.locations,
            bodies=tuple(bodies),
            items=fixture.items,
            resources=fixture.resources,
            weather=fixture.weather,
            registrations=fixture.registrations,
            revision=fixture.revision,
        )
    kwargs: dict[str, object] = {}
    if policy is not None:
        kwargs["skill_policy"] = policy
        kwargs["skill_entity_ids"] = tuple(EntityId(entity) for entity in enabled)
        if ledger is not None:
            kwargs["skill_ledger"] = ledger
    return WorldEngine(
        config=physical_config(seed),
        bootstrap=fixture.as_bootstrap(),
        **kwargs,
    )


def _search_bit(engine: WorldEngine, agent: str) -> bool:
    batch = engine.observe()
    result = engine.resolve_tick(
        (ActionSubmission(batch.token, AgentId(agent), Search()),)
    )
    searched = next(
        record.event.details
        for record in result.events
        if type(record.event.details) is Searched
        and record.event.actor_id
        == EntityId("body-1" if agent == "agent-1" else "body-2")
    )
    assert type(searched) is Searched
    assert type(searched.success) is bool
    return searched.success


def test_enabled_runs_match_and_zero_matches_disabled_search() -> None:
    policy = default_objective_skill_policy()
    ledger = _ledger(("body-1", SkillDomain.FORAGING, 1.0))
    first = _search_bit(
        _engine(41, policy=policy, enabled=("body-1",), ledger=ledger),
        "agent-1",
    )
    second = _search_bit(
        _engine(41, policy=policy, enabled=("body-1",), ledger=ledger),
        "agent-1",
    )
    assert first is second
    disabled = _search_bit(
        make_engine(two_location_fixture(item_on_ground=False), seed=41),
        "agent-1",
    )
    zeros = _search_bit(
        _engine(
            41,
            policy=policy,
            enabled=("body-1",),
            ledger=ObjectiveSkillLedger.bootstrap((EntityId("body-1"),)),
        ),
        "agent-1",
    )
    assert zeros is disabled


def test_navigation_and_healing_match_across_seeds_and_zero_is_identity() -> None:
    policy = default_objective_skill_policy()
    ledger = _ledger(
        ("body-1", SkillDomain.NAVIGATION, 1.0),
        ("body-1", SkillDomain.HEALING, 1.0),
    )

    def run(seed_engine: WorldEngine) -> tuple[float, float]:
        batch = seed_engine.observe()
        helped = seed_engine.resolve_tick(
            (
                ActionSubmission(
                    batch.token,
                    AgentId("agent-1"),
                    Help(EntityId("body-2")),
                ),
            )
        )
        health_delta = next(
            record.event.details.health_delta
            for record in helped.events
            if type(record.event.details) is Helped
        )
        batch = seed_engine.observe()
        moved = seed_engine.resolve_tick(
            (
                ActionSubmission(
                    batch.token, AgentId("agent-1"), Move(EntityId("loc-2"))
                ),
            )
        )
        assert moved.resolutions[0].status is ActionResolutionStatus.APPLIED
        actor = seed_engine._snapshot.world.state.bodies[EntityId("body-1")]
        fatigue = actor.fatigue.value
        return fatigue, health_delta

    left = run(
        _engine(7, policy=policy, enabled=("body-1",), ledger=ledger, wounded=True)
    )
    right = run(
        _engine(7, policy=policy, enabled=("body-1",), ledger=ledger, wounded=True)
    )
    assert left == right
    off = run(_engine(7, wounded=True))
    zero = run(
        _engine(
            7,
            policy=policy,
            enabled=("body-1",),
            ledger=ObjectiveSkillLedger.bootstrap(
                (EntityId("body-1"), EntityId("body-2"))
            ),
            wounded=True,
        )
    )
    assert zero == off
    assert left[1] != off[1]


def test_mixed_run_adjusts_only_the_enabled_actor() -> None:
    policy = default_objective_skill_policy()
    ledger = _ledger(("body-1", SkillDomain.NAVIGATION, 1.0))
    enabled = _engine(9, policy=policy, enabled=("body-1",), ledger=ledger)
    disabled = make_engine(two_location_fixture(item_on_ground=False), seed=9)

    def fatigue_after_move(engine: WorldEngine, agent: str, body: str) -> float:
        batch = engine.observe()
        engine.resolve_tick(
            (ActionSubmission(batch.token, AgentId(agent), Move(EntityId("loc-2"))),)
        )
        return engine._snapshot.world.state.bodies[EntityId(body)].fatigue.value

    assert fatigue_after_move(enabled, "agent-1", "body-1") != fatigue_after_move(
        disabled, "agent-1", "body-1"
    )
    other_on = _engine(11, policy=policy, enabled=("body-1",), ledger=ledger)
    other_off = make_engine(two_location_fixture(item_on_ground=False), seed=11)
    assert fatigue_after_move(other_on, "agent-2", "body-2") == fatigue_after_move(
        other_off, "agent-2", "body-2"
    )


def test_search_resolver_rejects_competence_model() -> None:
    engine = make_engine(two_location_fixture(item_on_ground=False), seed=3)
    with pytest.raises(TypeError):
        engine._resolve_search_effect(
            snap=engine._snapshot,
            request=None,  # type: ignore[arg-type]
            request_ordinals={},
            rules=None,
            starting_state=None,
            skill_ledger=empty_competence_model(AgentId("agent-1")),
        )


def test_skill_modifier_logs_and_missing_domain_fails_closed(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger="simulation.engine")
    policy = default_objective_skill_policy()
    ledger = _ledger(("body-1", SkillDomain.NAVIGATION, 1.0))
    engine = _engine(5, policy=policy, enabled=("body-1",), ledger=ledger)
    batch = engine.observe()
    engine.resolve_tick(
        (ActionSubmission(batch.token, AgentId("agent-1"), Move(EntityId("loc-2"))),)
    )
    messages = [
        record.getMessage()
        for record in caplog.records
        if record.name == "simulation.engine"
        and "skill_modifier " in record.getMessage()
    ]
    assert messages
    assert any(
        "domain=navigation" in line and "outcome=efficiency" in line
        for line in messages
    )
    assert any("level=" in line for line in messages)
    assert all("seed" not in line for line in messages)
    broken = _engine(
        6,
        policy=policy,
        enabled=("body-1",),
        ledger=ObjectiveSkillLedger.bootstrap((EntityId("body-9"),)),
    )
    batch = broken.observe()
    with pytest.raises(ValueError, match="missing_domain"):
        broken.resolve_tick(
            (
                ActionSubmission(
                    batch.token, AgentId("agent-1"), Move(EntityId("loc-2"))
                ),
            )
        )
    assert "reason_code=missing_domain" in caplog.text
    assert broken._skill_ledger is not None
    assert broken._skill_ledger.entity_ids() == (EntityId("body-9"),)


def test_aborted_prepare_keeps_the_previous_ledger() -> None:
    policy = default_objective_skill_policy()
    ledger = _ledger(("body-1", SkillDomain.NAVIGATION, 1.0))
    engine = _engine(8, policy=policy, enabled=("body-1",), ledger=ledger)
    before = engine._skill_ledger
    batch = engine.observe()
    with pytest.raises(TypeError):
        engine.resolve_tick(("not-a-submission",))  # type: ignore[arg-type]
    assert engine._skill_ledger is before
    engine.resolve_tick(
        (ActionSubmission(batch.token, AgentId("agent-1"), Move(EntityId("loc-2"))),)
    )
    assert engine._skill_ledger is not before
