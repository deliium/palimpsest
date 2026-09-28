"""Prepare-time theory-of-mind updates and runtime commit."""

from __future__ import annotations

import logging

import pytest

from agents.cognition.configuration import (
    CognitionLoopConfig,
    CognitionTheoryOfMindMode,
    build_cognitive_loop,
)
from agents.cognition.theory_of_mind import TheoryOfMind
from agents.models import AgentId
from tests.cognition_helpers import build_loop_input, build_observation

_LOOP = "agents.cognition.loop"


@pytest.mark.asyncio
async def test_passthrough_leaves_the_model_unset() -> None:
    loop = build_cognitive_loop(CognitionLoopConfig())
    result = await loop.run(build_loop_input(build_observation()), invocation_id="off")
    assert result.theory_of_mind is None
    assert result.command is not None


@pytest.mark.asyncio
async def test_enabled_prepare_stores_a_model(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger=_LOOP)
    loop = build_cognitive_loop(
        CognitionLoopConfig(
            theory_of_mind_mode=CognitionTheoryOfMindMode.ENABLED,
        )
    )
    result = await loop.run(build_loop_input(build_observation()), invocation_id="on")
    assert type(result.theory_of_mind) is TheoryOfMind
    assert result.theory_of_mind.owner_id == AgentId("agent-1")
    assert any(
        "theory_of_mind_prepare" in record.getMessage()
        and "mode=enabled" in record.getMessage()
        for record in caplog.records
    )


def test_eat_bias_prefers_help_and_two_counters_stay_above_threshold() -> None:
    from agents.cognition.theory_of_mind import (
        MindAspect,
        MindSlot,
        cues_from_observation,
        default_theory_of_mind_policy,
        empty_theory_of_mind,
        mind_direction_deltas,
        update_theory_of_mind,
    )
    from tests.unit.test_theory_of_mind import _occurrence, _watch

    owner = AgentId("agent-alice")
    policy = default_theory_of_mind_policy()
    seen = _watch(
        tick=1,
        occurrences=(
            _occurrence(kind="eat", tick=1, actor="body-bob", event="evt-eat"),
        ),
    )
    model = update_theory_of_mind(
        empty_theory_of_mind(owner),
        cues_from_observation(seen, owner_id=owner, policy=policy),
        policy,
        owner_entity_id=seen.observer_id,
    )
    hunger = next(
        item
        for item in model.hypotheses
        if item.aspect is MindAspect.NEED
        and any(
            atom.slot is MindSlot.NEED_KIND and atom.value == "hunger"
            for atom in item.atoms
        )
    )
    assert hunger.confidence == pytest.approx(0.8)
    deltas, status, direction, _confidence, _hypothesis, aspect = mind_direction_deltas(
        model,
        candidates=(
            ("help-bob", "help", "body-bob"),
            ("wait", "wait", None),
        ),
        visible_destinations=frozenset(),
        visible_entities=frozenset({"body-bob"}),
    )
    assert status == "applied"
    assert direction == "help"
    assert aspect == "need"
    assert dict(deltas)["help-bob"] == pytest.approx(hunger.confidence)
