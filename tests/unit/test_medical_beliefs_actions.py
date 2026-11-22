# mypy: ignore-errors

"""Ordinary intervention compilation from owner-scoped medical beliefs."""

from __future__ import annotations

from dataclasses import replace

import pytest

from agents.cognition.medical_beliefs import (
    MedicalBeliefLedger,
    MedicalCause,
    MedicalPractice,
    advance,
    begin_attempt,
)
from agents.cognition.medical_beliefs_actions import (
    MEDICAL_RETRY_COOLDOWN_TICKS,
    default_practice_for,
    select_medical_intervention,
)
from tests.unit.test_medical_beliefs_ledger import (
    _delivery,
    _ledger,
    _observation,
    _root,
)
from world.actions import Move, Sleep, Wait
from world.identifiers import EntityId
from world.observations import VisibleExit

pytestmark = pytest.mark.unit


def _supported_ledger(
    cause: MedicalCause = MedicalCause.CONTACT,
    practice: MedicalPractice = MedicalPractice.LEAVE,
) -> MedicalBeliefLedger:
    root = _root(41)
    return advance(
        _ledger(),
        _observation(
            1,
            cue=False,
            communications=(
                _delivery(
                    tick=0,
                    event="a",
                    object_value=f"{cause.value}|{practice.value}|uncertain|{root}|0",
                ),
            ),
        ),
    )


def _with_exits(observation: object, exits: tuple[VisibleExit, ...]) -> object:
    return replace(observation, exits=exits)


def test_default_practice_mapping_is_declared() -> None:
    assert default_practice_for(MedicalCause.CONTACT) is MedicalPractice.LEAVE
    assert default_practice_for(MedicalCause.LOCATION) is MedicalPractice.LEAVE
    assert default_practice_for(MedicalCause.FOOD) is MedicalPractice.REST
    assert default_practice_for(MedicalCause.WEATHER) is MedicalPractice.REST
    assert default_practice_for(MedicalCause.CULTURAL) is MedicalPractice.RITUAL_PAUSE


def test_leave_uses_first_visible_exit_by_destination_id() -> None:
    ledger = _supported_ledger()
    observation = _with_exits(
        _observation(2, cue=True),
        (
            VisibleExit(destination_id=EntityId("loc-z"), name="Z"),
            VisibleExit(destination_id=EntityId("loc-b"), name="B"),
            VisibleExit(destination_id=EntityId("loc-c"), name="C"),
        ),
    )
    selected = select_medical_intervention(observation, ledger, tick=2)
    assert selected is not None
    assert type(selected.command) is Move
    assert selected.command.destination_id == EntityId("loc-b")
    assert selected.cause is MedicalCause.CONTACT
    assert selected.practice is MedicalPractice.LEAVE


def test_leave_without_exit_is_a_legal_null() -> None:
    ledger = _supported_ledger()
    assert (
        select_medical_intervention(_observation(2, cue=True), ledger, tick=2)
        is None
    )


def test_rest_and_ritual_compile_ordinary_commands() -> None:
    rest = _supported_ledger(MedicalCause.FOOD, MedicalPractice.REST)
    selected = select_medical_intervention(
        _observation(2, cue=True), rest, tick=2
    )
    assert selected is not None and type(selected.command) is Sleep
    ritual = _supported_ledger(MedicalCause.CULTURAL, MedicalPractice.RITUAL_PAUSE)
    selected = select_medical_intervention(
        _observation(2, cue=True), ritual, tick=2
    )
    assert selected is not None and type(selected.command) is Wait


def test_no_cue_no_active_cause_or_journey_blocks_intervention() -> None:
    ledger = _supported_ledger()
    assert (
        select_medical_intervention(_observation(2, cue=False), ledger, tick=2)
        is None
    )
    assert (
        select_medical_intervention(_observation(2, cue=True), _ledger(), tick=2)
        is None
    )


def test_cooldown_blocks_same_pair_until_three_ticks() -> None:
    ledger = _supported_ledger()
    ledger = begin_attempt(
        ledger,
        tick=2,
        cause=MedicalCause.CONTACT,
        practice=MedicalPractice.LEAVE,
    )
    observation = _with_exits(
        _observation(2, cue=True),
        (VisibleExit(destination_id=EntityId("loc-b"), name="B"),),
    )
    assert (
        select_medical_intervention(
            observation, ledger, tick=2 + MEDICAL_RETRY_COOLDOWN_TICKS - 1
        )
        is None
    )
    later = _with_exits(
        _observation(5, cue=True),
        (VisibleExit(destination_id=EntityId("loc-b"), name="B"),),
    )
    assert (
        select_medical_intervention(
            later, ledger, tick=2 + MEDICAL_RETRY_COOLDOWN_TICKS
        )
        is not None
    )


def test_default_practice_used_below_threshold_when_cause_is_active() -> None:
    ledger = advance(_ledger(), _observation(0, cue=False, peer=True))
    ledger = advance(ledger, _observation(1, cue=True))
    assert dict(ledger.cause_scores)[MedicalCause.CONTACT] == 2
    ledger = replace(
        ledger,
        practice_scores=tuple(
            (cause, practice, 0)
            for cause, practice, _score in ledger.practice_scores
        ),
    )
    observation = _with_exits(
        _observation(2, cue=True),
        (VisibleExit(destination_id=EntityId("loc-b"), name="B"),),
    )
    selected = select_medical_intervention(observation, ledger, tick=2)
    assert selected is not None
    assert selected.practice is MedicalPractice.LEAVE


@pytest.mark.asyncio
async def test_command_override_suppresses_attempt_but_keeps_evidence() -> None:
    from dataclasses import replace as _replace

    from agents.models import AgentId
    from tests.simulation_helpers import alive_body
    from tests.unit.test_cognitive_loop import _loop, _loop_input
    from world.identifiers import EntityId
    from world.observations import observed_self_from_body

    ledger = _supported_ledger(MedicalCause.CONTACT, MedicalPractice.LEAVE)
    loop = _loop(medical_beliefs_enabled=True)
    loop.restore_medical_belief_ledger(ledger, AgentId("agent-a"))
    base = _loop_input("agent-a")
    body = _replace(
        observed_self_from_body(alive_body("body-a")), symptom_cue="unwell"
    )
    observation = _replace(
        base.observation,
        observer_id=EntityId("body-a"),
        tick=5,
        self_body=body,
        exits=(VisibleExit(destination_id=EntityId("loc-b"), name="B"),),
    )
    loop_input = _replace(base, observation=observation)

    proposal = await loop.prepare(loop_input, invocation_id="inv-override")
    overridden = await loop.complete(
        proposal, effective_command=Wait(), command_override=True
    )
    assert type(overridden.command) is Wait
    assert not any(
        getattr(row, "kind", None) == "attempt"
        for row in overridden.medical_belief_ledger.rows
    )

    proposal = await loop.prepare(loop_input, invocation_id="inv-normal")
    normal = await loop.complete(proposal, effective_command=Wait())
    assert type(normal.command) is Move
    assert any(
        getattr(row, "kind", None) == "attempt"
        for row in normal.medical_belief_ledger.rows
    )


@pytest.mark.asyncio
async def test_unmarked_wait_stays_wait_without_a_supported_belief() -> None:
    from dataclasses import replace as _replace

    from agents.models import AgentId
    from tests.simulation_helpers import alive_body
    from tests.unit.test_cognitive_loop import _loop, _loop_input
    from world.identifiers import EntityId
    from world.observations import observed_self_from_body

    loop = _loop(medical_beliefs_enabled=True)
    loop.restore_medical_belief_ledger(_ledger(), AgentId("agent-a"))
    base = _loop_input("agent-a")
    body = _replace(
        observed_self_from_body(alive_body("body-a")), symptom_cue="unwell"
    )
    observation = _replace(
        base.observation,
        observer_id=EntityId("body-a"),
        tick=5,
        self_body=body,
    )
    loop_input = _replace(base, observation=observation)
    proposal = await loop.prepare(loop_input, invocation_id="inv-unmarked")
    result = await loop.complete(proposal, effective_command=Wait())
    assert type(result.command) is Wait
    assert not any(
        getattr(row, "kind", None) == "attempt"
        for row in result.medical_belief_ledger.rows
    )


@pytest.mark.asyncio
async def test_non_wait_command_is_never_replaced() -> None:
    from dataclasses import replace as _replace

    from agents.models import AgentId
    from tests.simulation_helpers import alive_body
    from tests.unit.test_cognitive_loop import _loop, _loop_input
    from world.identifiers import EntityId
    from world.observations import observed_self_from_body

    ledger = _supported_ledger(MedicalCause.CONTACT, MedicalPractice.LEAVE)
    loop = _loop(medical_beliefs_enabled=True)
    loop.restore_medical_belief_ledger(ledger, AgentId("agent-a"))
    base = _loop_input("agent-a")
    body = _replace(
        observed_self_from_body(alive_body("body-a")), symptom_cue="unwell"
    )
    observation = _replace(
        base.observation,
        observer_id=EntityId("body-a"),
        tick=5,
        self_body=body,
        exits=(VisibleExit(destination_id=EntityId("loc-b"), name="B"),),
    )
    loop_input = _replace(base, observation=observation)
    proposal = await loop.prepare(loop_input, invocation_id="inv-move")
    result = await loop.complete(
        proposal, effective_command=Move(destination_id=EntityId("loc-c"))
    )
    assert type(result.command) is Move
    assert result.command.destination_id == EntityId("loc-c")
    assert not any(
        getattr(row, "kind", None) == "attempt"
        for row in result.medical_belief_ledger.rows
    )
