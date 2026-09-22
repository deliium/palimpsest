"""Unit tests for Experiment E and milestone arbitration."""

from __future__ import annotations

import logging

import pytest

from agents.models import AgentId
from experiments.interventions import (
    DEFAULT_OVERRIDE_BUDGET,
    ArbiterOverrideDecision,
    MilestoneInterventionArbiter,
    MilestoneOverride,
    MilestoneStatus,
    StoryInterventionArbiter,
    make_false_story_intervention,
    unwrap_arbiter_command,
)
from simulation.clock import Tick
from simulation.lifecycle import (
    ActionResolution,
    ActionResolutionReason,
    ActionResolutionStatus,
)
from world.actions import Attack, Search, Tell, Wait
from world.identifiers import EntityId, RequestId, WorldRevision


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
    command = arbiter.maybe_replace(
        tick=3,
        agent_id=AgentId("agent-1"),
        proposed_command=Wait(),
    )
    assert isinstance(command, Tell)
    assert command.recipient_id.value == "body-2"
    assert arbiter.consumed is False
    arbiter.mark_committed(accepted=True)
    assert arbiter.consumed is True
    assert arbiter.maybe_replace(tick=3, agent_id=AgentId("agent-1")) is None


def test_story_arbiter_acknowledges_from_action_resolution() -> None:
    intervention = make_false_story_intervention(
        intervention_id="e-ack",
        tick=1,
        source_agent_id=AgentId("agent-1"),
        source_entity_id=EntityId("body-1"),
        recipient_entity_id=EntityId("body-2"),
        text="signal",
        concepts=("signal",),
    )
    arbiter = StoryInterventionArbiter(intervention)
    assert arbiter.maybe_replace(tick=1, agent_id=AgentId("agent-1")) is not None
    resolution = ActionResolution(
        ordinal=0,
        agent_id=AgentId("agent-1"),
        command=Tell(
            recipient_id=EntityId("body-2"),
            utterance=intervention.utterance,
        ),
        status=ActionResolutionStatus.REJECTED,
        reason=ActionResolutionReason.STRUCTURAL_REJECTION,
        tick=Tick(1),
        base_revision=WorldRevision(0),
        resulting_revision=WorldRevision(0),
        request_id=RequestId("req-1"),
    )
    arbiter.acknowledge_resolutions((resolution,))
    assert arbiter.consumed is True


def _resolution(
    *,
    tick: int,
    agent_id: str,
    command: object,
    status: ActionResolutionStatus = ActionResolutionStatus.APPLIED,
) -> ActionResolution:
    return ActionResolution(
        ordinal=0,
        agent_id=AgentId(agent_id),
        command=command,  # type: ignore[arg-type]
        status=status,
        reason=(
            ActionResolutionReason.OCCURRENCE
            if status is ActionResolutionStatus.APPLIED
            else ActionResolutionReason.STRUCTURAL_REJECTION
        ),
        tick=Tick(tick),
        base_revision=WorldRevision(0),
        resulting_revision=WorldRevision(
            1 if status is ActionResolutionStatus.APPLIED else 0
        ),
        request_id=RequestId(f"req-{agent_id}-{tick}"),
    )


def test_milestone_arbiter_returns_decision_and_records_metadata() -> None:
    milestone = MilestoneOverride(
        milestone_id="ms-search",
        tick=2,
        agent_id=AgentId("agent-kai"),
        build_command=lambda: Search(target_id=EntityId("res-water")),
    )
    arbiter = MilestoneInterventionArbiter((milestone,), override_budget=4)
    assert arbiter.override_budget == 4
    assert arbiter.override_budget_remaining == 4
    assert arbiter.maybe_replace(tick=1, agent_id=AgentId("agent-kai")) is None
    decision = arbiter.maybe_replace(
        tick=2,
        agent_id=AgentId("agent-kai"),
        proposed_command=Wait(),
    )
    assert isinstance(decision, ArbiterOverrideDecision)
    assert decision.milestone_id == "ms-search"
    assert isinstance(decision.command, Search)
    assert unwrap_arbiter_command(decision) is decision.command
    assert arbiter.milestone_status("ms-search") is MilestoneStatus.SELECTED
    records = arbiter.proposed_versus_effective
    assert len(records) == 1
    assert records[0].proposed_command_kind == "wait"
    assert records[0].effective_command_kind == "search"
    assert records[0].resolution_status is None

    arbiter.acknowledge_resolutions(
        (
            _resolution(
                tick=2,
                agent_id="agent-kai",
                command=decision.command,
            ),
        )
    )
    assert arbiter.overrides_used == 1
    assert arbiter.override_budget_remaining == 3
    assert arbiter.milestone_status("ms-search") is MilestoneStatus.APPLIED
    assert arbiter.proposed_versus_effective[0].resolution_status == "applied"
    assert arbiter.maybe_replace(tick=2, agent_id=AgentId("agent-kai")) is None


def test_milestone_arbiter_respects_override_budget() -> None:
    milestones = tuple(
        MilestoneOverride(
            milestone_id=f"ms-{index}",
            tick=index,
            agent_id=AgentId("agent-1"),
            build_command=lambda: Wait(),
        )
        for index in range(3)
    )
    arbiter = MilestoneInterventionArbiter(milestones, override_budget=1)
    first = arbiter.maybe_replace(tick=0, agent_id=AgentId("agent-1"))
    assert first is not None
    arbiter.acknowledge_resolutions(
        (_resolution(tick=0, agent_id="agent-1", command=Wait()),)
    )
    second = arbiter.maybe_replace(tick=1, agent_id=AgentId("agent-1"))
    assert second is None
    assert arbiter.milestone_status("ms-1") is MilestoneStatus.BUDGET_EXHAUSTED


def test_milestone_arbiter_fresh_tell_communication_ids() -> None:
    calls: list[str] = []

    def _build_tell() -> Tell:
        intervention = make_false_story_intervention(
            intervention_id=f"tell-{len(calls)}",
            tick=4,
            source_agent_id=AgentId("agent-1"),
            source_entity_id=EntityId("body-1"),
            recipient_entity_id=EntityId("body-2"),
            text="ping",
            concepts=("ping",),
        )
        calls.append(intervention.utterance.declared.communication_id.value)
        return intervention.as_tell()

    milestone = MilestoneOverride(
        milestone_id="ms-tell",
        tick=4,
        agent_id=AgentId("agent-1"),
        build_command=_build_tell,
    )
    arbiter = MilestoneInterventionArbiter((milestone,), override_budget=2)
    first = arbiter.maybe_replace(tick=4, agent_id=AgentId("agent-1"))
    assert isinstance(first, ArbiterOverrideDecision)
    arbiter.acknowledge_resolutions(
        (
            _resolution(
                tick=4,
                agent_id="agent-1",
                command=first.command,
                status=ActionResolutionStatus.REJECTED,
            ),
        )
    )
    # Consumed one-shot even when rejected; no second selection.
    assert arbiter.maybe_replace(tick=4, agent_id=AgentId("agent-1")) is None
    assert len(calls) == 1


def test_milestone_arbiter_default_budget_is_sparse() -> None:
    assert DEFAULT_OVERRIDE_BUDGET < 20
    assert DEFAULT_OVERRIDE_BUDGET > 0


def test_milestone_arbiter_logs_metadata_only(
    caplog: pytest.LogCaptureFixture,
) -> None:
    milestone = MilestoneOverride(
        milestone_id="ms-attack",
        tick=5,
        agent_id=AgentId("agent-soren"),
        build_command=lambda: Attack(target_id=EntityId("body-nyx")),
    )
    with caplog.at_level(logging.DEBUG, logger="experiments.interventions"):
        arbiter = MilestoneInterventionArbiter((milestone,), override_budget=2)
        decision = arbiter.maybe_replace(
            tick=5,
            agent_id=AgentId("agent-soren"),
            proposed_command=Wait(),
        )
        assert decision is not None
        arbiter.acknowledge_resolutions(
            (_resolution(tick=5, agent_id="agent-soren", command=decision.command),)
        )
    text = caplog.text
    assert "ms-attack" in text
    assert "body-nyx" not in text
    assert "Attack(" not in text
    assert "target_id" not in text
