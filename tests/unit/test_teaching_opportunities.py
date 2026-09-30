"""Demonstration and joint practice add a bonus without copying a hidden level."""

from __future__ import annotations

import logging
from dataclasses import replace

import pytest

from agents.models import AgentId
from simulation.engine import WorldEngine
from simulation.lifecycle import ActionSubmission
from tests.physical_helpers import physical_config, two_location_fixture
from tests.simulation_helpers import alive_body, make_location
from world._skills import SkillDomain, default_objective_skill_policy
from world._teaching import default_teaching_interaction_policy
from world.actions import Move, Search, Talk
from world.communications import CommunicationRelation, origin_utterance
from world.identifiers import EntityId
from world.models import PhysicalRules

pytestmark = pytest.mark.unit


def _quantize(value: float) -> float:
    return round(value / 1e-6) * 1e-6


def _engine(
    enabled: tuple[str, ...],
    *,
    teaching: tuple[str, ...] | None = None,
    seed: int = 3,
    visibility: float = 1.0,
    bystander: bool = False,
    rules: PhysicalRules | None = None,
    offer_window: int = 8,
) -> WorldEngine:
    fixture = two_location_fixture(item_on_ground=False)
    locations = (
        make_location(
            "loc-1",
            name="Camp",
            adjacent=("loc-2",),
            visibility_factor=visibility,
        ),
        fixture.locations[1],
    )
    bodies = fixture.bodies
    if bystander:
        bodies = (*bodies, alive_body("body-3", location_id="loc-1"))
    world = type(fixture)(
        world_id=fixture.world_id,
        locations=locations,
        bodies=bodies,
        items=fixture.items,
        resources=fixture.resources,
        weather=fixture.weather,
        registrations=fixture.registrations,
        revision=fixture.revision,
    )
    kwargs: dict[str, object] = {}
    if teaching is not None:
        kwargs["teaching_policy"] = replace(
            default_teaching_interaction_policy(),
            offer_window=offer_window,
        )
        kwargs["teaching_entity_ids"] = tuple(EntityId(entity) for entity in teaching)
    return WorldEngine(
        config=physical_config(seed, rules=rules),
        bootstrap=world.as_bootstrap(),
        skill_policy=default_objective_skill_policy(),
        skill_entity_ids=tuple(EntityId(entity) for entity in enabled),
        **kwargs,
    )


def _act(engine: WorldEngine, agent: str, command: object) -> None:
    batch = engine.observe()
    engine.resolve_tick((ActionSubmission(batch.token, AgentId(agent), command),))


def _both(engine: WorldEngine, first: object, second: object) -> None:
    batch = engine.observe()
    engine.resolve_tick(
        (
            ActionSubmission(batch.token, AgentId("agent-1"), first),
            ActionSubmission(batch.token, AgentId("agent-2"), second),
        )
    )


def _level(engine: WorldEngine, body: str, domain: SkillDomain) -> float:
    ledger = engine._skill_ledger
    assert ledger is not None
    return ledger.level(EntityId(body), domain)


def _talk(predicate: str, obj: str, *, communication_id: str) -> Talk:
    return Talk(
        EntityId("body-2"),
        origin_utterance(
            text="a public act",
            speaker_id=EntityId("body-1"),
            communication_id=communication_id,
            relations=(
                CommunicationRelation(subject="skill", predicate=predicate, object=obj),
            ),
        ),
    )


def test_disabled_policy_matches_skill_fold() -> None:
    rules = PhysicalRules(search_base_probability=1.0)
    plain = _engine(("body-1", "body-2"), rules=rules)
    taught = _engine(
        ("body-1", "body-2"),
        teaching=("body-1", "body-2"),
        rules=rules,
    )
    _act(plain, "agent-1", Search())
    _act(taught, "agent-1", Search())
    assert _level(taught, "body-1", SkillDomain.FORAGING) == _level(
        plain, "body-1", SkillDomain.FORAGING
    )
    assert _level(taught, "body-2", SkillDomain.FORAGING) == _level(
        plain, "body-2", SkillDomain.FORAGING
    )
    lesson = _engine(
        ("body-1", "body-2", "body-3"),
        teaching=("body-1", "body-2", "body-3"),
        bystander=True,
    )
    _act(
        lesson,
        "agent-1",
        Talk(
            EntityId("body-2"),
            origin_utterance(
                text="copy the motion",
                speaker_id=EntityId("body-1"),
                communication_id="comm-instruct",
                relations=(
                    CommunicationRelation(
                        subject="skill",
                        predicate="instruct",
                        object="foraging",
                    ),
                ),
            ),
        ),
    )
    assert _level(lesson, "body-2", SkillDomain.FORAGING) == 0.0
    assert _level(lesson, "body-1", SkillDomain.TEACHING) == _quantize(0.07)


def test_demonstrate_uses_start_level_not_the_folded_practice(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger="world._teaching")
    engine = _engine(
        ("body-1", "body-2", "body-3"),
        teaching=("body-1", "body-2"),
        bystander=True,
        rules=PhysicalRules(search_base_probability=1.0),
    )
    _act(engine, "agent-1", _talk("demonstrate", "foraging", communication_id="comm-d"))
    assert _level(engine, "body-2", SkillDomain.FORAGING) == 0.0
    assert "teaching_opportunity" not in caplog.text
    ledger = engine._skill_ledger
    assert ledger is not None
    engine._skill_ledger = ledger.apply_summed_deltas(
        {EntityId("body-2"): {SkillDomain.FORAGING: 0.5}}
    )
    _act(engine, "agent-1", Search())
    expected = _quantize(_quantize(0.5 + 0.01) + 0.02 * (1.0 - 0.5))
    assert _level(engine, "body-2", SkillDomain.FORAGING) == expected
    assert expected != _quantize(_quantize(0.5 + 0.01) + 0.02 * (1.0 - 0.51))
    assert _level(engine, "body-1", SkillDomain.FORAGING) == _quantize(0.07)
    assert _level(engine, "body-3", SkillDomain.FORAGING) == _quantize(0.01)
    assert "teaching_opportunity tick=" in caplog.text
    assert "entity_id=body-2" in caplog.text
    assert "act=demonstrate" in caplog.text
    assert "domain=foraging" in caplog.text


def test_success_consumes_the_offer_and_a_miss_does_not() -> None:
    rules = PhysicalRules(search_base_probability=1.0)
    engine = _engine(("body-1", "body-2"), teaching=("body-1", "body-2"), rules=rules)
    _act(engine, "agent-1", _talk("demonstrate", "foraging", communication_id="comm-d"))
    _act(engine, "agent-1", Search())
    after_first = _level(engine, "body-2", SkillDomain.FORAGING)
    assert after_first == _quantize(0.01 + 0.02)
    _act(engine, "agent-1", Search())
    after_second = _quantize(after_first + 0.01)
    assert _level(engine, "body-2", SkillDomain.FORAGING) == after_second

    missed = _engine(
        ("body-1", "body-2"),
        teaching=("body-1", "body-2"),
        rules=PhysicalRules(search_base_probability=0.0, search_visibility_weight=0.0),
    )
    _act(missed, "agent-1", _talk("demonstrate", "foraging", communication_id="comm-m"))
    _act(missed, "agent-1", Search())
    assert _level(missed, "body-2", SkillDomain.FORAGING) == 0.0
    from world._skills import SkillGrowthInput
    from world._teaching import fold_teaching_opportunities
    from world.events import Searched

    later = fold_teaching_opportunities(
        missed._skill_ledger,
        start_ledger=missed._skill_ledger,
        applied_actions=(
            SkillGrowthInput(
                actor_id=EntityId("body-1"),
                status="applied",
                action_kind="search",
                details=Searched(success=True),
                origin_location_id=EntityId("loc-1"),
                untargeted_search=True,
            ),
        ),
        prior_events=missed._snapshot.event_history,
        policy=missed._teaching_policy,
        teaching_entity_ids=missed._teaching_entity_ids,
        world_state=missed._snapshot.world.state,
        tick=missed._snapshot.tick.value,
        rules=missed._config.physical_rules,
    )
    assert later.level(EntityId("body-2"), SkillDomain.FORAGING) == _quantize(0.02)


def test_offer_expires_after_the_window() -> None:
    engine = _engine(
        ("body-1", "body-2"),
        teaching=("body-1", "body-2"),
        rules=PhysicalRules(search_base_probability=1.0),
        offer_window=1,
    )
    _act(engine, "agent-1", _talk("demonstrate", "foraging", communication_id="comm-w"))
    _act(
        engine,
        "agent-1",
        Talk(
            EntityId("body-2"),
            origin_utterance(
                text="still here",
                speaker_id=EntityId("body-1"),
                communication_id="comm-plain",
            ),
        ),
    )
    _act(engine, "agent-1", Search())
    assert _level(engine, "body-2", SkillDomain.FORAGING) == _quantize(0.01)


def test_practice_together_uses_each_start_level() -> None:
    engine = _engine(
        ("body-1", "body-2"),
        teaching=("body-1", "body-2"),
        rules=PhysicalRules(search_base_probability=1.0),
    )
    _act(
        engine,
        "agent-1",
        _talk("practice_together", "foraging", communication_id="comm-p"),
    )
    assert _level(engine, "body-1", SkillDomain.FORAGING) == 0.0
    assert _level(engine, "body-2", SkillDomain.FORAGING) == 0.0
    _both(engine, Search(), Search())
    own = _quantize(0.02 + 0.05)
    witnessed = _quantize(own + 0.01)
    assert _level(engine, "body-1", SkillDomain.FORAGING) == _quantize(
        witnessed + 0.02 * (1.0 - 0.0)
    )
    assert _level(engine, "body-2", SkillDomain.FORAGING) == _quantize(
        witnessed + 0.02 * (1.0 - 0.0)
    )


def test_explain_and_request_add_no_objective_delta() -> None:
    engine = _engine(("body-1", "body-2"), teaching=("body-1", "body-2"))
    _act(
        engine,
        "agent-1",
        _talk("explain", "foraging:high", communication_id="comm-e"),
    )
    _act(
        engine,
        "agent-1",
        _talk("request_instruction", "healing", communication_id="comm-r"),
    )
    assert _level(engine, "body-2", SkillDomain.FORAGING) == 0.0
    assert _level(engine, "body-2", SkillDomain.HEALING) == 0.0
    assert _level(engine, "body-1", SkillDomain.TEACHING) == 0.0


def test_missing_ledger_actor_is_logged_and_gains_nothing(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.ERROR, logger="world._teaching")
    engine = _engine(("body-1",), teaching=("body-1", "body-2"))
    _act(engine, "agent-2", Move(EntityId("loc-2")))
    assert EntityId("body-2") not in engine._skill_ledger.entity_ids()  # type: ignore[union-attr]
    assert "reason_code=missing_entity" in caplog.text
    assert "field=entity_id" in caplog.text
