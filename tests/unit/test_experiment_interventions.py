"""Unit tests for Experiment E false-story intervention."""

from __future__ import annotations

from agents.models import AgentId
from experiments.interventions import (
    StoryInterventionArbiter,
    make_false_story_intervention,
)
from world.actions import Tell
from world.identifiers import EntityId


def test_intervention_replaces_only_matching_tick_and_agent() -> None:
    intervention = make_false_story_intervention(
        intervention_id="e-1",
        tick=3,
        source_agent_id=AgentId("agent-1"),
        source_entity_id=EntityId("body-1"),
        recipient_entity_id=EntityId("body-2"),
        text="the well is poisoned",
        concepts=("well", "poison"),
    )
    assert not hasattr(intervention.utterance, "is_false")
    assert intervention.truth.is_false is True
    arbiter = StoryInterventionArbiter(intervention)
    assert arbiter.maybe_replace(tick=2, agent_id=AgentId("agent-1")) is None
    assert arbiter.maybe_replace(tick=3, agent_id=AgentId("agent-2")) is None
    command = arbiter.maybe_replace(tick=3, agent_id=AgentId("agent-1"))
    assert isinstance(command, Tell)
    assert command.recipient_id.value == "body-2"
    assert arbiter.consumed is False
    arbiter.mark_committed(accepted=True)
    assert arbiter.consumed is True
    assert arbiter.maybe_replace(tick=3, agent_id=AgentId("agent-1")) is None
