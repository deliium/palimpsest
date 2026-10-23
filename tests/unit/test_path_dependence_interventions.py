"""Scheduled child-only treatment arbiter and exposure ledger."""

from __future__ import annotations

import pytest

from agents.models import AgentId
from experiments.generational_comparison_base import generational_comparison_base
from experiments.path_dependence_interventions import (
    PathDependenceArbiter,
    TreatmentStatus,
)
from experiments.path_dependence_models import (
    GiveInterventionAction,
    PathDependenceValidationError,
    ScheduledCommandIntervention,
    WaitInterventionAction,
)
from simulation.clock import Tick
from simulation.lifecycle import (
    ActionResolution,
    ActionResolutionReason,
    ActionResolutionStatus,
)
from simulation.models import RunId
from simulation.runner import SimulationRunner
from world.actions import Give, Wait
from world.identifiers import EntityId, RequestId, WorldRevision

pytestmark = pytest.mark.unit

OWNER = AgentId("agent-1")
OTHER = AgentId("agent-2")


def _give(
    intervention_id: str = "share", tick: int = 4
) -> ScheduledCommandIntervention:
    return ScheduledCommandIntervention(
        intervention_id,
        OWNER,
        Tick(tick),
        GiveInterventionAction(EntityId("item-food"), EntityId("body-2")),
    )


def _wait(
    intervention_id: str = "withhold", tick: int = 4
) -> ScheduledCommandIntervention:
    return ScheduledCommandIntervention(
        intervention_id, OWNER, Tick(tick), WaitInterventionAction()
    )


def _resolution(
    status: ActionResolutionStatus,
    reason: ActionResolutionReason,
    *,
    tick: int = 4,
) -> ActionResolution:
    return ActionResolution(
        ordinal=0,
        agent_id=OWNER,
        command=Wait(),
        status=status,
        reason=reason,
        tick=Tick(tick),
        base_revision=WorldRevision(0),
        resulting_revision=WorldRevision(1),
        request_id=RequestId(f"req-{tick}"),
    )


def test_give_wait_and_untouched_schedules_are_distinct() -> None:
    give = PathDependenceArbiter((_give(),))
    decision = give.maybe_replace(tick=4, agent_id=OWNER, proposed_command=Wait())
    assert decision is not None
    assert type(decision.command) is Give
    assert decision.command.item_id == EntityId("item-food")
    assert decision.command.recipient_id == EntityId("body-2")
    assert give.maybe_replace(tick=3, agent_id=OWNER) is None
    assert give.maybe_replace(tick=4, agent_id=OTHER) is None

    wait = PathDependenceArbiter((_wait(),))
    wait_decision = wait.maybe_replace(tick=4, agent_id=OWNER)
    assert wait_decision is not None
    assert type(wait_decision.command) is Wait

    untouched = PathDependenceArbiter(())
    assert untouched.maybe_replace(tick=4, agent_id=OWNER) is None


def test_schedule_selects_once_and_records_committed_exposure() -> None:
    arbiter = PathDependenceArbiter((_give(),))
    decision = arbiter.maybe_replace(tick=4, agent_id=OWNER, proposed_command=Wait())
    assert decision is not None
    assert arbiter.maybe_replace(tick=4, agent_id=OWNER) is None
    arbiter.acknowledge_resolutions(
        (
            _resolution(
                ActionResolutionStatus.APPLIED, ActionResolutionReason.OCCURRENCE
            ),
        )
    )
    assert arbiter.maybe_replace(tick=4, agent_id=OWNER) is None
    assert arbiter.overrides_used == 1
    entry = arbiter.treatment_ledger[0]
    assert entry.status is TreatmentStatus.COMMITTED
    assert entry.proposed_command_kind == "wait"
    assert entry.effective_command_kind == "give"


def test_rejected_and_unreached_treatments_are_not_applied() -> None:
    rejected = PathDependenceArbiter((_give(),))
    assert rejected.maybe_replace(tick=4, agent_id=OWNER) is not None
    rejected.acknowledge_resolutions(
        (
            _resolution(
                ActionResolutionStatus.REJECTED,
                ActionResolutionReason.INVALID_TARGET,
            ),
        )
    )
    assert rejected.treatment_ledger[0].status is TreatmentStatus.REJECTED

    missed = PathDependenceArbiter((_wait(),))
    assert missed.maybe_replace(tick=4, agent_id=OWNER) is not None
    missed.finalize_unreached()
    assert missed.treatment_ledger[0].status is TreatmentStatus.MISSED


def test_duplicate_slots_and_budget_overflow_fail_closed() -> None:
    with pytest.raises(
        PathDependenceValidationError, match="duplicate_intervention"
    ):
        PathDependenceArbiter((_wait("a"), _wait("b")))
    with pytest.raises(
        PathDependenceValidationError, match="intervention_budget_exceeded"
    ):
        PathDependenceArbiter((_wait(),), override_budget=0)


def test_multiple_actions_and_independent_children() -> None:
    actions = (
        _give("share", 4),
        _wait("withhold-later", 5),
    )
    first = PathDependenceArbiter(actions, override_budget=2)
    second = PathDependenceArbiter(actions, override_budget=2)
    assert first.maybe_replace(tick=4, agent_id=OWNER) is not None
    assert first.maybe_replace(tick=5, agent_id=OWNER) is not None
    assert second.maybe_replace(tick=4, agent_id=OWNER) is not None
    first.acknowledge_resolutions(
        (
            _resolution(
                ActionResolutionStatus.APPLIED, ActionResolutionReason.OCCURRENCE
            ),
        )
    )
    assert first.overrides_used == 1
    assert second.overrides_used == 0
    assert len(second.treatment_ledger) == 2


@pytest.mark.asyncio
async def test_arbiter_treatment_flows_through_normal_admission() -> None:
    config = generational_comparison_base(seed=23, max_ticks=8)
    runner = await SimulationRunner.from_config(
        config, run_id=RunId("arbiter-run")
    )
    try:
        await runner.initialize_finalized_boundary()
        arbiter = PathDependenceArbiter(
            (
                ScheduledCommandIntervention(
                    "withhold",
                    AgentId("agent-origin"),
                    Tick(0),
                    WaitInterventionAction(),
                ),
            )
        )
        runner.set_intervention_arbiter(arbiter)
        await runner.run_tick()
        entry = arbiter.treatment_ledger[0]
        assert entry.status is TreatmentStatus.COMMITTED
        assert entry.resolution_status == "applied"
        assert arbiter.overrides_used == 1
    finally:
        await runner.aclose()
