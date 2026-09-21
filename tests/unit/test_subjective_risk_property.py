"""Hypothesis/property tests for subjective risk deliberation invariants."""

from __future__ import annotations

import math
from dataclasses import replace

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from agents.cognition.imagination import ImaginationEngine
from agents.cognition.models import ActionDirection, SituationClaimCode
from agents.cognition.motivation import MotivationAppraisal
from tests.cognition_helpers import (
    build_belief,
    build_loop_input,
    build_observation,
    build_reconstruction,
    build_self_model,
    build_situation,
    memory_context,
    run_deliberation,
)
from world.actions import Search, Wait

pytestmark = pytest.mark.unit

_CONFIDENCE = st.floats(
    min_value=0.15, max_value=0.99, allow_nan=False, allow_infinity=False
)


@given(
    confidences=st.lists(_CONFIDENCE, min_size=2, max_size=4),
    data=st.data(),
)
@settings(max_examples=25, deadline=None)
def test_belief_order_permutation_invariance(confidences: list[float], data) -> None:  # type: ignore[no-untyped-def]
    beliefs = tuple(
        build_belief(
            predicate="is_dangerous",
            confidence=confidence,
            belief_id=f"belief-{index}",
        )
        for index, confidence in enumerate(confidences)
    )
    permuted = data.draw(st.permutations(list(beliefs)))
    observation = build_observation(with_threat=True, with_exit=True)

    async def _run() -> None:
        _, _, intention_a, plan_a = await run_deliberation(
            build_loop_input(observation, beliefs=beliefs)
        )
        _, _, intention_b, plan_b = await run_deliberation(
            build_loop_input(observation, beliefs=tuple(permuted))
        )
        assert intention_a.direction is intention_b.direction
        assert intention_a.selected_future_id == intention_b.selected_future_id
        assert type(plan_a.command) is type(plan_b.command)

    __import__("asyncio").run(_run())


@given(
    concepts=st.lists(
        st.sampled_from(["harm", "danger", "safety", "shelter", "threat"]),
        min_size=1,
        max_size=3,
        unique=True,
    ),
    data=st.data(),
)
@settings(max_examples=20, deadline=None)
def test_memory_order_permutation_invariance(concepts: list[str], data) -> None:  # type: ignore[no-untyped-def]
    recons = tuple(
        build_reconstruction(
            concepts=(concept,),
            reconstruction_id=f"recon-{index}",
            memory_id=f"mem-{index}",
        )
        for index, concept in enumerate(concepts)
    )
    permuted = data.draw(st.permutations(list(recons)))
    observation = build_observation(with_threat=True, with_water=True)

    async def _run() -> None:
        _, _, intention_a, plan_a = await run_deliberation(
            build_loop_input(observation),
            memory=memory_context(reconstructions=recons),
        )
        _, _, intention_b, plan_b = await run_deliberation(
            build_loop_input(observation),
            memory=memory_context(reconstructions=tuple(permuted)),
        )
        assert intention_a.selected_future_id == intention_b.selected_future_id
        assert type(plan_a.command) is type(plan_b.command)

    __import__("asyncio").run(_run())


@pytest.mark.asyncio
async def test_repeatability_same_inputs_same_command() -> None:
    observation = build_observation(
        with_water=True, with_threat=True, with_exit=True, thirst=30.0
    )
    beliefs = (
        build_belief(predicate="is_dangerous", confidence=0.7, belief_id="belief-1"),
        build_belief(predicate="is_safe", confidence=0.4, belief_id="belief-2"),
    )
    loop_input = build_loop_input(observation, beliefs=beliefs)
    first = await run_deliberation(loop_input)
    second = await run_deliberation(loop_input)
    assert [f.future_id for f in first[0].futures] == [
        f.future_id for f in second[0].futures
    ]
    assert first[2].selected_future_id == second[2].selected_future_id
    assert type(first[3].command) is type(second[3].command)
    assert first[3].command == second[3].command


@given(confidence=_CONFIDENCE)
@settings(max_examples=20, deadline=None)
def test_finite_bounds_on_appraisals_and_mortality(confidence: float) -> None:
    observation = build_observation(with_threat=True, with_exit=True)
    beliefs = (
        build_belief(
            predicate="is_dangerous", confidence=confidence, belief_id="belief-1"
        ),
    )

    async def _run() -> None:
        futures, motivation, _, _ = await run_deliberation(
            build_loop_input(observation, beliefs=beliefs)
        )
        for future in futures.futures:
            assert math.isfinite(future.confidence)
            assert 0.0 <= future.confidence <= 1.0
            for risk in future.risks:
                assert math.isfinite(risk.severity)
                assert math.isfinite(risk.likelihood)
                assert 0.0 <= risk.severity <= 1.0
                assert 0.0 <= risk.likelihood <= 1.0
        for appraisal in motivation.appraisals:
            if appraisal.mortality is not None:
                mort = appraisal.mortality
                for value in (
                    mort.death_probability,
                    mort.outstanding_goal_value,
                    mort.attachment_loss,
                    mort.safety_activation,
                    mort.autonomy_loss,
                    mort.option_space.foreclosed_ratio,
                    mort.composite,
                ):
                    assert math.isfinite(value)
                    assert 0.0 <= value <= 1.0
            for effect in appraisal.drive_effects:
                assert math.isfinite(effect.delta)
                assert -1.0 <= effect.delta <= 1.0

    __import__("asyncio").run(_run())


@pytest.mark.asyncio
async def test_monotonic_danger_confidence_on_wait_mortality_or_harm() -> None:
    observation = build_observation(with_threat=True, with_exit=True)
    lows: list[float] = []
    highs: list[float] = []
    for confidence in (0.2, 0.4, 0.6, 0.8, 0.95):
        futures, motivation, _, _ = await run_deliberation(
            build_loop_input(
                observation,
                beliefs=(
                    build_belief(
                        predicate="is_dangerous",
                        confidence=confidence,
                        belief_id="belief-1",
                    ),
                ),
            )
        )
        wait_future = next(
            item for item in futures.futures if item.direction is ActionDirection.WAIT
        )
        wait_appraisal = next(
            item for item in motivation.appraisals if item.future_id == "wait"
        )
        harm = sum(
            risk.likelihood * risk.severity
            for risk in wait_future.risks
            if risk.kind.value == "physical_harm"
        )
        mortality = (
            0.0
            if wait_appraisal.mortality is None
            else wait_appraisal.mortality.death_probability
        )
        lows.append(harm)
        highs.append(mortality)
    assert lows == sorted(lows)
    assert highs == sorted(highs)


@pytest.mark.asyncio
async def test_owner_isolation_foreign_belief_ignored() -> None:
    observation = build_observation(
        with_water=True, with_threat=True, with_exit=True
    )
    owned = build_belief(
        predicate="is_dangerous",
        confidence=0.9,
        belief_id="belief-owned",
        owner="agent-1",
    )
    foreign = build_belief(
        predicate="is_dangerous",
        confidence=0.9,
        belief_id="belief-foreign",
        owner="agent-2",
    )
    # Boundary contracts reject foreign-owned beliefs at construction.
    with pytest.raises(ValueError, match=r"ownership|owner mismatch"):
        memory_context(beliefs=(foreign,))
    with pytest.raises(ValueError, match="ownership"):
        build_loop_input(observation, beliefs=(foreign,))

    _, _, intention_owned, plan_owned = await run_deliberation(
        build_loop_input(observation),
        memory=memory_context(beliefs=(owned,)),
    )
    _, _, intention_empty, plan_empty = await run_deliberation(
        build_loop_input(observation),
        memory=memory_context(),
    )
    assert (intention_owned.direction, type(plan_owned.command)) != (
        intention_empty.direction,
        type(plan_empty.command),
    )
    assert type(plan_owned.command) is Search


@pytest.mark.asyncio
async def test_irrelevant_evidence_neutrality() -> None:
    observation = build_observation(with_threat=True, with_exit=True)
    baseline = await run_deliberation(build_loop_input(observation))
    irrelevant = (
        build_belief(
            predicate="is_blue", confidence=0.99, belief_id="belief-color"
        ),
        build_belief(
            predicate="likes_music", confidence=0.99, belief_id="belief-music"
        ),
    )
    with_noise = await run_deliberation(
        build_loop_input(observation, beliefs=irrelevant)
    )
    assert baseline[2].selected_future_id == with_noise[2].selected_future_id
    assert type(baseline[3].command) is type(with_noise[3].command)
    assert baseline[3].command == with_noise[3].command


@pytest.mark.asyncio
async def test_source_trace_immutability() -> None:
    observation = build_observation(with_threat=True)
    beliefs = (
        build_belief(predicate="is_dangerous", confidence=0.8, belief_id="belief-1"),
    )
    futures, _, _, _ = await run_deliberation(
        build_loop_input(observation, beliefs=beliefs)
    )
    wait = next(
        item for item in futures.futures if item.direction is ActionDirection.WAIT
    )
    assert wait.source_refs.belief_ids == ("belief-1",)
    with pytest.raises(AttributeError):
        wait.source_refs.belief_ids = ("tampered",)  # type: ignore[misc]
    with pytest.raises(AttributeError):
        wait.future_id = "tampered"  # type: ignore[misc]
    # replace yields a new frozen object; original remains unchanged.
    altered = replace(wait.source_refs, belief_ids=("tampered",))
    assert wait.source_refs.belief_ids == ("belief-1",)
    assert altered.belief_ids == ("tampered",)


@pytest.mark.asyncio
async def test_stable_fallback_empty_and_terminal_wait() -> None:
    terminal = build_situation(SituationClaimCode.TERMINAL_SELF, tick=1)
    empty_observation = build_observation()
    futures = await ImaginationEngine().imagine(
        build_loop_input(empty_observation),
        terminal,
        build_self_model(),
        memory_context(),
    )
    assert len(futures.futures) == 1
    assert futures.futures[0].direction is ActionDirection.WAIT

    motivation = await MotivationAppraisal().evaluate(
        build_loop_input(empty_observation),
        terminal,
        build_self_model(),
        futures,
    )
    from agents.cognition.deliberation import (
        CommandPlanner,
        MultiCriteriaIntentionSelector,
    )

    intention = await MultiCriteriaIntentionSelector().select(
        build_loop_input(empty_observation), motivation, futures
    )
    plan = await CommandPlanner().plan(
        build_loop_input(empty_observation), intention, futures
    )
    assert intention.direction is ActionDirection.WAIT
    assert type(plan.command) is Wait
