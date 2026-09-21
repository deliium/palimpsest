"""Scenario unit tests: subjective inputs diverge decisions under fixed observation."""

from __future__ import annotations

import logging

import pytest

from agents.cognition.models import (
    ActionDirection,
    MotivationEvaluation,
    SelectedIntention,
)
from agents.models import (
    REQUIRED_DRIVE_KINDS,
    AgentId,
    DriveKind,
    GoalOutcome,
    GoalOutcomeKind,
)
from memory.beliefs import BeliefActivationState
from tests.cognition_helpers import (
    FixedMemoryRetriever,
    build_belief,
    build_drive_profile,
    build_goal,
    build_loop_input,
    build_observation,
    build_reconstruction,
    build_relationship,
    memory_context,
    production_cognitive_loop,
    run_deliberation,
)
from world.actions import Drink, Help, Move, Search, Talk, Wait

pytestmark = pytest.mark.unit


def _harm_on_wait(futures) -> float:  # type: ignore[no-untyped-def]
    wait = next(
        item for item in futures.futures if item.direction is ActionDirection.WAIT
    )
    return sum(
        risk.likelihood for risk in wait.risks if risk.kind.value == "physical_harm"
    )


@pytest.mark.asyncio
async def test_safe_versus_dangerous_beliefs_diverge(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG)
    observation = build_observation(with_water=True, with_threat=True, with_exit=True)
    danger = build_belief(
        predicate="is_dangerous", confidence=0.9, belief_id="belief-danger"
    )
    safety = build_belief(
        predicate="is_safe", confidence=0.9, belief_id="belief-safe"
    )

    futures_d, motivation_d, intention_d, plan_d = await run_deliberation(
        build_loop_input(observation, beliefs=(danger,))
    )
    futures_s, _motivation_s, intention_s, plan_s = await run_deliberation(
        build_loop_input(observation, beliefs=(safety,))
    )

    assert _harm_on_wait(futures_d) > _harm_on_wait(futures_s)
    assert (intention_d.direction, type(plan_d.command)) != (
        intention_s.direction,
        type(plan_s.command),
    )
    assert type(plan_d.command) is Search
    assert type(plan_s.command) is Move
    assert len(futures_d.futures) >= 3
    assert set(motivation_d.active_drive_kinds) == set(REQUIRED_DRIVE_KINDS)

    messages = " ".join(record.getMessage() for record in caplog.records)
    assert any(record.levelno == logging.DEBUG for record in caplog.records)
    assert "imagination_complete" in messages or "deliberation_complete" in messages
    assert "is_dangerous" not in messages
    assert "is_safe" not in messages
    assert "subjective-episode" not in messages


@pytest.mark.asyncio
async def test_remembered_harm_versus_safety_diverges() -> None:
    observation = build_observation(with_water=True, with_threat=True, with_exit=True)
    harm = build_reconstruction(
        concepts=("harm", "danger"),
        reconstruction_id="recon-harm",
        memory_id="mem-harm",
        narrative="subjective-episode",
    )
    safety = build_reconstruction(
        concepts=("safety", "shelter"),
        reconstruction_id="recon-safe",
        memory_id="mem-safe",
        narrative="subjective-episode",
    )
    futures_h, _, intention_h, plan_h = await run_deliberation(
        build_loop_input(observation),
        memory=memory_context(reconstructions=(harm,)),
    )
    futures_s, _, intention_s, plan_s = await run_deliberation(
        build_loop_input(observation),
        memory=memory_context(reconstructions=(safety,)),
    )
    assert _harm_on_wait(futures_h) > _harm_on_wait(futures_s)
    assert (intention_h.direction, type(plan_h.command)) != (
        intention_s.direction,
        type(plan_s.command),
    )
    assert type(plan_h.command) is Search
    assert type(plan_s.command) is Talk


@pytest.mark.asyncio
async def test_urgent_thirst_with_danger_prefers_drink() -> None:
    """Critical thirst + water: Drink wins even with high danger belief."""
    observation = build_observation(thirst=90.0, with_water=True, with_threat=True)
    danger = build_belief(
        predicate="is_dangerous", confidence=0.95, belief_id="belief-d"
    )
    _, _, intention, plan = await run_deliberation(
        build_loop_input(observation, beliefs=(danger,))
    )
    assert intention.direction is ActionDirection.DRINK
    assert type(plan.command) is Drink


@pytest.mark.asyncio
async def test_belonging_versus_autonomy_diverges() -> None:
    observation = build_observation(with_threat=True, with_exit=True)
    belonging = build_drive_profile(
        boosts={
            DriveKind.BELONGING: (0.95, 0.95),
            DriveKind.AUTONOMY: (0.05, 0.05),
            DriveKind.SAFETY: (0.2, 0.2),
        }
    )
    autonomy = build_drive_profile(
        boosts={
            DriveKind.AUTONOMY: (0.95, 0.95),
            DriveKind.BELONGING: (0.05, 0.05),
            DriveKind.SAFETY: (0.2, 0.2),
        }
    )
    goal_belong = build_goal(
        goal_id="goal-belong",
        description="secret-belong",
        outcome=GoalOutcome(
            kind=GoalOutcomeKind.RELATE_TO_AGENT, counterpart_id=AgentId("agent-2")
        ),
    )
    goal_auto = build_goal(
        goal_id="goal-auto",
        description="secret-auto",
        outcome=GoalOutcome(kind=GoalOutcomeKind.REACH_PLACE, place_id="loc-2"),
    )
    rel = build_relationship(affection=0.9, dependency=0.5)
    _, _, intention_b, plan_b = await run_deliberation(
        build_loop_input(
            observation,
            drives=belonging,
            goals=(goal_belong,),
            relationships=(rel,),
            counterpart_agent="agent-2",
        )
    )
    _, _, intention_a, plan_a = await run_deliberation(
        build_loop_input(
            observation,
            drives=autonomy,
            goals=(goal_auto,),
            counterpart_agent="agent-2",
        )
    )
    assert type(plan_b.command) is Help
    assert type(plan_a.command) is Move
    assert intention_b.direction is not intention_a.direction


@pytest.mark.asyncio
async def test_novelty_versus_predictability_diverges() -> None:
    observation = build_observation(with_water=True, with_exit=True)
    novelty = build_drive_profile(
        boosts={
            DriveKind.NOVELTY: (0.95, 0.95),
            DriveKind.CURIOSITY: (0.95, 0.95),
            DriveKind.PREDICTABILITY: (0.05, 0.05),
            DriveKind.THIRST: (0.05, 0.05),
        }
    )
    predictability = build_drive_profile(
        boosts={
            DriveKind.PREDICTABILITY: (0.95, 0.95),
            DriveKind.NOVELTY: (0.05, 0.05),
            DriveKind.CURIOSITY: (0.05, 0.05),
            DriveKind.THIRST: (0.05, 0.05),
        }
    )
    _, _, intention_n, plan_n = await run_deliberation(
        build_loop_input(observation, drives=novelty)
    )
    _, _, intention_p, plan_p = await run_deliberation(
        build_loop_input(observation, drives=predictability)
    )
    assert type(plan_n.command) is Search
    assert type(plan_p.command) is Wait
    assert intention_n.direction is ActionDirection.SEARCH
    assert intention_p.direction is ActionDirection.WAIT


@pytest.mark.asyncio
async def test_competence_status_versus_risk_diverges() -> None:
    observation = build_observation(with_threat=True)
    danger = build_belief(
        predicate="is_dangerous", confidence=0.9, belief_id="belief-d"
    )
    status = build_drive_profile(
        boosts={
            DriveKind.STATUS: (0.95, 0.95),
            DriveKind.COMPETENCE: (0.95, 0.95),
            DriveKind.SAFETY: (0.1, 0.1),
        }
    )
    safety = build_drive_profile(
        boosts={
            DriveKind.SAFETY: (0.95, 0.95),
            DriveKind.STATUS: (0.1, 0.1),
            DriveKind.COMPETENCE: (0.1, 0.1),
        }
    )
    _, _, intention_st, plan_st = await run_deliberation(
        build_loop_input(
            observation,
            drives=status,
            beliefs=(danger,),
            counterpart_agent="agent-2",
            goals=(
                build_goal(
                    goal_id="goal-status",
                    description="secret-status",
                    outcome=GoalOutcome(
                        kind=GoalOutcomeKind.ACHIEVE_CODE, outcome_code="status-up"
                    ),
                ),
            ),
        )
    )
    _, _, intention_sf, plan_sf = await run_deliberation(
        build_loop_input(
            observation,
            drives=safety,
            beliefs=(danger,),
            counterpart_agent="agent-2",
        )
    )
    assert type(plan_st.command) is Help
    assert type(plan_sf.command) is Talk
    assert intention_st.direction != intention_sf.direction


@pytest.mark.asyncio
async def test_high_versus_low_opportunity_foreclosure_fear_of_death() -> None:
    observation = build_observation(with_threat=True, with_exit=True)
    danger = build_belief(
        predicate="is_dangerous", confidence=0.95, belief_id="belief-d"
    )
    high_goal = build_goal(
        goal_id="goal-life",
        description="secret-life",
        priority=1.0,
        outcome=GoalOutcome(kind=GoalOutcomeKind.PRESERVE_LIFE),
    )
    low_goal = build_goal(
        goal_id="goal-info",
        description="secret-goal",
        priority=0.1,
        outcome=GoalOutcome(
            kind=GoalOutcomeKind.GATHER_INFORMATION, outcome_code="look-around"
        ),
    )
    high_rel = build_relationship(dependency=0.95, affection=0.9)
    low_rel = build_relationship(dependency=0.05, affection=0.05)

    _, motivation_h, _, plan_h = await run_deliberation(
        build_loop_input(
            observation,
            beliefs=(danger,),
            goals=(high_goal,),
            relationships=(high_rel,),
        )
    )
    _, motivation_l, _, plan_l = await run_deliberation(
        build_loop_input(
            observation,
            beliefs=(danger,),
            goals=(low_goal,),
            relationships=(low_rel,),
        )
    )
    wait_h = next(item for item in motivation_h.appraisals if item.future_id == "wait")
    wait_l = next(item for item in motivation_l.appraisals if item.future_id == "wait")
    assert wait_h.mortality is not None and wait_l.mortality is not None
    assert wait_h.mortality.composite > wait_l.mortality.composite
    assert not hasattr(wait_h.mortality, "death_penalty")
    assert "death_penalty" not in MotivationEvaluation.__dataclass_fields__
    assert type(plan_h.command) is not type(plan_l.command)


@pytest.mark.asyncio
async def test_several_futures_and_all_eleven_drives_in_appraisals() -> None:
    observation = build_observation(
        with_water=True, with_threat=True, with_exit=True, thirst=40.0
    )
    futures, motivation, _, _ = await run_deliberation(
        build_loop_input(
            observation,
            beliefs=(
                build_belief(predicate="is_dangerous", confidence=0.6, belief_id="b1"),
            ),
        )
    )
    assert len(futures.futures) >= 4
    directions = {item.direction for item in futures.futures}
    assert ActionDirection.WAIT in directions
    assert ActionDirection.DRINK in directions
    assert ActionDirection.FLEE in directions
    assert set(motivation.active_drive_kinds) == set(REQUIRED_DRIVE_KINDS)
    for appraisal in motivation.appraisals:
        kinds = {effect.kind for effect in appraisal.drive_effects}
        assert kinds == set(REQUIRED_DRIVE_KINDS)


@pytest.mark.asyncio
async def test_no_permanent_reward_scalar_on_evaluation_or_intention() -> None:
    observation = build_observation(with_water=True)
    _, motivation, intention, _ = await run_deliberation(build_loop_input(observation))
    for name in ("reward", "total_reward", "death_penalty"):
        assert name not in MotivationEvaluation.__dataclass_fields__
        assert name not in SelectedIntention.__dataclass_fields__
        assert not hasattr(motivation, name)
        assert not hasattr(intention, name)
    assert motivation.appraisals
    assert intention.selected_future_id is not None


@pytest.mark.asyncio
async def test_caplog_excludes_semantic_payloads(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG)
    observation = build_observation(with_water=True, with_threat=True)
    danger = build_belief(
        predicate="is_dangerous", confidence=0.88, belief_id="belief-d"
    )
    recon = build_reconstruction(
        concepts=("harm",), narrative="subjective-episode", memory_id="mem-1"
    )
    goal = build_goal(description="secret-goal")
    rel = build_relationship(dependency=0.77, affection=0.66, fear=0.55)
    loop = production_cognitive_loop(
        memory=FixedMemoryRetriever(beliefs=(danger,), reconstructions=(recon,))
    )
    loop_input = build_loop_input(
        observation, beliefs=(danger,), goals=(goal,), relationships=(rel,)
    )
    result = await loop.run(loop_input, invocation_id="inv-risk-1")
    assert result.command is not None
    messages = " ".join(record.getMessage() for record in caplog.records)
    assert any(record.levelno == logging.DEBUG for record in caplog.records)
    assert "is_dangerous" not in messages
    assert "subjective-episode" not in messages
    assert "secret-goal" not in messages
    assert "0.77" not in messages
    assert "0.66" not in messages
    assert "0.55" not in messages


@pytest.mark.asyncio
async def test_inactive_belief_does_not_match_active_danger_path() -> None:
    observation = build_observation(
        with_water=True, with_threat=True, with_exit=True
    )
    active = build_belief(
        predicate="is_dangerous", confidence=0.9, belief_id="belief-active"
    )
    inactive = build_belief(
        predicate="is_dangerous",
        confidence=0.9,
        belief_id="belief-inactive",
        activation=BeliefActivationState.RETIRED,
    )
    futures_a, _, intention_a, plan_a = await run_deliberation(
        build_loop_input(observation, beliefs=(active,))
    )
    futures_i, _, intention_i, plan_i = await run_deliberation(
        build_loop_input(observation, beliefs=(inactive,))
    )
    assert _harm_on_wait(futures_a) > _harm_on_wait(futures_i)
    assert (intention_a.direction, type(plan_a.command)) != (
        intention_i.direction,
        type(plan_i.command),
    )
    assert type(plan_a.command) is Search
    assert type(plan_i.command) is Help
