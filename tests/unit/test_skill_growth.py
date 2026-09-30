"""Objective skill growth is a fold of committed tick facts."""

from __future__ import annotations

import logging

import pytest

from agents.models import AgentId
from simulation.engine import WorldEngine
from simulation.lifecycle import ActionSubmission
from tests.physical_helpers import physical_config, two_location_fixture
from tests.simulation_helpers import alive_body, make_location
from world._skills import SkillDomain, default_objective_skill_policy
from world.actions import Attack, Help, Move, Search, Talk
from world.communications import CommunicationRelation, origin_utterance
from world.identifiers import EntityId
from world.models import PhysicalRules

pytestmark = pytest.mark.unit


def _quantize(value: float) -> float:
    return round(value / 1e-6) * 1e-6


def _fixture(*, visibility: float = 1.0, bystander: bool = False):
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
    return type(fixture)(
        world_id=fixture.world_id,
        locations=locations,
        bodies=bodies,
        items=fixture.items,
        resources=fixture.resources,
        weather=fixture.weather,
        registrations=fixture.registrations,
        revision=fixture.revision,
    )


def _engine(
    enabled: tuple[str, ...],
    *,
    seed: int = 3,
    visibility: float = 1.0,
    bystander: bool = False,
    rules: PhysicalRules | None = None,
) -> WorldEngine:
    fixture = _fixture(visibility=visibility, bystander=bystander)
    return WorldEngine(
        config=physical_config(seed, rules=rules),
        bootstrap=fixture.as_bootstrap(),
        skill_policy=default_objective_skill_policy(),
        skill_entity_ids=tuple(EntityId(entity) for entity in enabled),
    )


def _act(engine: WorldEngine, agent: str, command: object) -> None:
    batch = engine.observe()
    engine.resolve_tick((ActionSubmission(batch.token, AgentId(agent), command),))


def _level(engine: WorldEngine, body: str, domain: SkillDomain) -> float:
    ledger = engine._skill_ledger
    assert ledger is not None
    return ledger.level(EntityId(body), domain)


def test_search_help_and_move_quantized_growth() -> None:
    engine = _engine(
        ("body-1", "body-2"),
        rules=PhysicalRules(search_base_probability=1.0),
    )
    _act(engine, "agent-1", Search())
    assert _level(engine, "body-1", SkillDomain.FORAGING) == _quantize(0.07)
    missed = _engine(
        ("body-1",),
        rules=PhysicalRules(
            search_base_probability=0.0,
            search_visibility_weight=0.0,
        ),
    )
    _act(missed, "agent-1", Search(EntityId("res-food")))
    assert _level(missed, "body-1", SkillDomain.RESOURCE_DETECTION) == _quantize(0.03)
    healer = _engine(("body-1",))
    _act(healer, "agent-1", Help(EntityId("body-2")))
    assert _level(healer, "body-1", SkillDomain.HEALING) == _quantize(0.07)
    mover = _engine(("body-1",))
    _act(mover, "agent-1", Move(EntityId("loc-2")))
    assert _level(mover, "body-1", SkillDomain.NAVIGATION) == _quantize(0.07)


def test_plain_talk_and_zero_teacher_instruction(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger="world._skills")
    speaker = EntityId("body-1")
    plain = _engine(("body-1", "body-2", "body-3"), bystander=True)
    _act(
        plain,
        "agent-1",
        Talk(
            EntityId("body-2"),
            origin_utterance(text="hello", speaker_id=speaker),
        ),
    )
    assert _level(plain, "body-1", SkillDomain.COMMUNICATION) == _quantize(0.07)
    assert _level(plain, "body-1", SkillDomain.TEACHING) == 0.0
    assert _level(plain, "body-3", SkillDomain.COMMUNICATION) == 0.0
    lesson = _engine(("body-1", "body-2", "body-3"), bystander=True)
    _act(
        lesson,
        "agent-1",
        Talk(
            EntityId("body-2"),
            origin_utterance(
                text="forage like this",
                speaker_id=speaker,
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
    assert _level(lesson, "body-1", SkillDomain.TEACHING) == _quantize(0.07)
    assert _level(lesson, "body-2", SkillDomain.FORAGING) == 0.0
    assert _level(lesson, "body-3", SkillDomain.FORAGING) == 0.0
    assert "reason_code=not_instruction" in caplog.text
    assert "reason_code=private_utterance" in caplog.text
    assert "forage like this" not in caplog.text
    assert "hello" not in caplog.text


def test_witness_visibility_disabled_rejected_and_attack(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger="world._skills")
    visible = _engine(("body-1", "body-2"))
    batch = visible.observe()
    visible.resolve_tick(
        (
            ActionSubmission(
                batch.token, AgentId("agent-1"), Move(EntityId("loc-2"))
            ),
            ActionSubmission(
                batch.token, AgentId("agent-2"), Move(EntityId("loc-2"))
            ),
        )
    )
    assert _level(visible, "body-2", SkillDomain.NAVIGATION) == _quantize(
        0.02 + 0.05 + 0.01
    )
    hidden = _engine(("body-1", "body-2"), visibility=0.4)
    _act(hidden, "agent-1", Move(EntityId("loc-2")))
    assert _level(hidden, "body-2", SkillDomain.NAVIGATION) == 0.0
    assert "reason_code=not_visible" in caplog.text
    disabled = _engine(("body-1",))
    _act(disabled, "agent-2", Move(EntityId("loc-2")))
    assert disabled._skill_ledger is not None
    assert EntityId("body-2") not in disabled._skill_ledger.entity_ids()
    assert _level(disabled, "body-1", SkillDomain.NAVIGATION) == _quantize(0.01)
    assert "reason_code=actor_disabled" in caplog.text
    rejected = _engine(("body-1",))
    _act(rejected, "agent-1", Move(EntityId("loc-9")))
    assert _level(rejected, "body-1", SkillDomain.NAVIGATION) == 0.0
    assert "reason_code=rejected" in caplog.text
    attacker = _engine(("body-1",))
    _act(attacker, "agent-1", Attack(EntityId("body-2")))
    assert all(
        _level(attacker, "body-1", domain) == 0.0 for domain in SkillDomain
    )
    messages = [
        record.getMessage()
        for record in caplog.records
        if record.name == "world._skills"
        and record.getMessage().startswith("skill_growth ")
    ]
    assert messages
    assert any("channel=observation" in line for line in messages)
    assert any("channel=practice" in line for line in messages)


def test_unknown_domain_is_dropped(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG, logger="world._skills")
    engine = _engine(("body-1", "body-2"))
    _act(
        engine,
        "agent-1",
        Talk(
            EntityId("body-2"),
            origin_utterance(
                text="unknown",
                speaker_id=EntityId("body-1"),
                relations=(
                    CommunicationRelation(
                        subject="skill",
                        predicate="instruct",
                        object="wizardry",
                    ),
                ),
            ),
        ),
    )
    assert _level(engine, "body-2", SkillDomain.TEACHING) == 0.0
    assert "reason_code=unknown_domain" in caplog.text
    assert "wizardry" not in caplog.text
