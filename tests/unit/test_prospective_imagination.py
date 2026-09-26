"""Contracts and deterministic scoring for bounded prospective imagination."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from agents.cognition.configuration import CognitionProspectiveMode
from agents.cognition.models import (
    ActionDirection,
    CognitiveLoopInput,
    GoalBoard,
    InternalAgentState,
    RetrievedMemoryContext,
    SelfModel,
    SituationClaimCode,
    SituationModel,
    SubjectiveUncertainty,
    UncertaintyBand,
)
from agents.cognition.prospective import (
    PROSPECTIVE_POLICY_VERSION,
    ImaginedTransition,
    ProspectivePolicy,
    ProspectivePruneReason,
    ProspectiveRollout,
    choose_path,
    default_prospective_policy,
    path_value,
    rollout_prospective,
    transition_id_for,
)
from agents.cognition.world_model import (
    CausalAtom,
    CausalHypothesis,
    CausalOutcome,
    CausalProvenanceKind,
    CausalSlot,
    CausalWorldModel,
    confidence_from_masses,
)
from agents.models import (
    AgentId,
    Goal,
    GoalHorizon,
    GoalId,
    GoalOutcome,
    GoalOutcomeKind,
    GoalStatus,
)
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import LifeStatus, PhysicalRules
from world.observations import (
    Observation,
    ObservedItem,
    ObservedItemPlacement,
    ObservedSelf,
    VisibleExit,
)
from world.values import (
    CarryCapacity,
    Fatigue,
    Health,
    Hunger,
    ItemKind,
    ItemLoad,
    TemperatureCelsius,
    Thirst,
)

_OWNER = AgentId("agent-1")
_SOURCE = (
    Path(__file__).resolve().parents[2] / "src/agents/cognition/prospective.py"
)


def _self() -> ObservedSelf:
    return ObservedSelf(
        entity_id=EntityId("body-1"),
        location_id=EntityId("here"),
        health=Health(100),
        hunger=Hunger(0),
        thirst=Thirst(0),
        fatigue=Fatigue(0),
        temperature=TemperatureCelsius(36.5),
        inventory=(),
        life_status=LifeStatus.ALIVE,
        carry_capacity=CarryCapacity(10),
    )


def _observation() -> Observation:
    return Observation(
        world_id=WorldId("world-1"),
        observer_id=EntityId("body-1"),
        revision=WorldRevision(0),
        tick=3,
        self_body=_self(),
        items=(
            ObservedItem(
                entity_id=EntityId("stone-1"),
                name="stone",
                kind=ItemKind.MATERIAL,
                load=ItemLoad(1),
                placement=ObservedItemPlacement.GROUND_HERE,
            ),
        ),
        exits=(VisibleExit(destination_id=EntityId("D"), name="path"),),
    )


def _loop_input() -> CognitiveLoopInput:
    return CognitiveLoopInput(
        agent_id=_OWNER,
        observation=_observation(),
        internal_state=InternalAgentState(owner_id=_OWNER),
    )


def _situation() -> SituationModel:
    return SituationModel(
        owner_id=_OWNER,
        tick=3,
        claim_codes=(SituationClaimCode.LOCAL_SCENE,),
        confidence=1.0,
    )


def _self_model() -> SelfModel:
    return SelfModel(
        owner_id=_OWNER,
        policy_id="self-model-projection",
        policy_version="1",
        life_status=LifeStatus.ALIVE,
        beliefs=(),
        goal_ids=(),
        confidence=1.0,
        candidate_count=0,
    )


def _memory() -> RetrievedMemoryContext:
    return RetrievedMemoryContext(
        owner_id=_OWNER,
        memory_ids=(),
        belief_ids=(),
        confidence=1.0,
    )


def _board() -> GoalBoard:
    reach = Goal(
        goal_id=GoalId("reach-d"),
        owner_id=_OWNER,
        description="reach the far place",
        priority=0.5,
        status=GoalStatus.ACTIVE,
        horizon=GoalHorizon.MEDIUM_TERM,
        outcome=GoalOutcome(kind=GoalOutcomeKind.REACH_PLACE, place_id="D"),
        created_tick=1,
    )
    gather = Goal(
        goal_id=GoalId("gather-info"),
        owner_id=_OWNER,
        description="search once there",
        priority=0.8,
        status=GoalStatus.ACTIVE,
        horizon=GoalHorizon.CURRENT_INTENTION,
        outcome=GoalOutcome(
            kind=GoalOutcomeKind.GATHER_INFORMATION, outcome_code="survey"
        ),
        created_tick=1,
    )
    return GoalBoard(
        owner_id=_OWNER,
        tick=3,
        goals=(reach, gather),
        foci_ids=(gather.goal_id,),
        transition_intents=(),
        confidence=1.0,
        policy_version="goals.v1",
    )


def _rollout(**policy_kwargs: object) -> object:
    defaults: dict[str, object] = {"horizon": 3, "max_depth": 3}
    defaults.update(policy_kwargs)
    policy = ProspectivePolicy(**defaults)  # type: ignore[arg-type]
    return rollout_prospective(
        _loop_input(),
        _situation(),
        _self_model(),
        _memory(),
        policy,
        goal_board=_board(),
    )


def test_mode_defaults_disabled_and_policy_keeps_provider_off() -> None:
    assert CognitionProspectiveMode.DISABLED.value == "disabled"
    policy = default_prospective_policy()
    assert policy.version == PROSPECTIVE_POLICY_VERSION
    assert policy.horizon == 3
    assert policy.branching_factor == 3
    assert policy.max_branches == 16
    assert policy.max_depth == 3
    assert policy.max_llm_calls == 1
    assert policy.max_tokens == 256
    assert policy.timeout_seconds == 0.05
    assert policy.allow_provider is False
    assert policy.clock is None
    assisted = default_prospective_policy(allow_provider=True)
    assert assisted.allow_provider is True


def test_policy_rejects_horizon_above_depth_and_bad_caps(caplog) -> None:
    caplog.set_level(logging.ERROR, logger="agents.cognition.prospective")
    with pytest.raises(ValueError, match="horizon_exceeds_max_depth"):
        ProspectivePolicy(horizon=4, max_depth=3)
    with pytest.raises(ValueError, match="not_positive"):
        ProspectivePolicy(branching_factor=0)
    with pytest.raises(ValueError, match="not_finite"):
        ProspectivePolicy(timeout_seconds=float("nan"))
    zero_calls = ProspectivePolicy(max_llm_calls=0, max_tokens=0)
    assert zero_calls.max_llm_calls == 0
    assert zero_calls.max_tokens == 0
    assert "horizon_exceeds_max_depth" in caplog.text
    assert "field=horizon" in caplog.text


def test_rollout_rejects_duplicate_ids_and_unit_interval_breaches() -> None:
    transition_id = transition_id_for(
        owner_id=_OWNER,
        parent_id=None,
        depth=1,
        direction=ActionDirection.WAIT,
        target_id=None,
    )
    transition = ImaginedTransition(
        owner_id=_OWNER,
        transition_id=transition_id,
        parent_id=None,
        depth=1,
        direction=ActionDirection.WAIT,
        target_id=None,
        confidence=1.0,
        uncertainty=SubjectiveUncertainty(
            epistemic=0.4, aleatory=0.1, band=UncertaintyBand.MEDIUM
        ),
        value=0.0,
    )
    with pytest.raises(ValueError, match="duplicate_transition_id"):
        ProspectiveRollout(
            owner_id=_OWNER,
            root_situation_atom_count=1,
            transitions=(transition, transition),
        )
    with pytest.raises(ValueError, match="not_unit_interval"):
        ImaginedTransition(
            owner_id=_OWNER,
            transition_id=transition_id,
            parent_id=None,
            depth=1,
            direction=ActionDirection.WAIT,
            target_id=None,
            confidence=1.2,
            uncertainty=SubjectiveUncertainty(),
            value=0.0,
        )


def test_locked_fixture_winning_path_moves_toward_d_then_searches() -> None:
    rollout = _rollout()
    assert type(rollout) is ProspectiveRollout
    path = choose_path(rollout)
    assert path is not None
    assert path[0].direction is ActionDirection.MOVE
    assert path[0].target_id == "D"
    assert path_value(path) == pytest.approx(0.3 - 0.024 + 0.4 - 0.041)
    assert any(
        step.direction is ActionDirection.SEARCH and step.depth >= 2 for step in path
    )


def test_effective_depth_one_stores_only_first_steps() -> None:
    rollout = _rollout(horizon=1, max_depth=1)
    assert type(rollout) is ProspectiveRollout
    assert rollout.transitions
    assert {item.depth for item in rollout.transitions} == {1}
    assert ProspectivePruneReason.BUDGET_DEPTH in rollout.budgets_exhausted


def test_max_branches_one_expands_only_the_root() -> None:
    rollout = _rollout(max_branches=1)
    assert type(rollout) is ProspectiveRollout
    assert rollout.expanded_count == 1
    assert ProspectivePruneReason.BUDGET_BRANCHES in rollout.budgets_exhausted
    assert all(item.depth == 1 for item in rollout.transitions)


def test_scripted_clock_stops_with_timeout() -> None:
    samples = iter((0.0, 1.0))
    rollout = _rollout(clock=lambda: next(samples), timeout_seconds=0.05)
    assert type(rollout) is ProspectiveRollout
    assert ProspectivePruneReason.BUDGET_TIMEOUT in rollout.budgets_exhausted
    assert rollout.timeout_hit is True
    assert rollout.expanded_count == 0


def test_physical_rules_are_rejected_and_absent_from_source() -> None:
    text = _SOURCE.read_text(encoding="utf-8")
    assert "search_base_probability" not in text
    assert "PhysicalRules" not in text
    assert "WorldState" not in text
    assert "time.monotonic" not in text
    assert "import llm" not in text
    with pytest.raises(TypeError):
        rollout_prospective(
            _loop_input(),
            _situation(),
            _self_model(),
            _memory(),
            default_prospective_policy(),
            physical_rules=PhysicalRules(),
        )


def test_danger_hypothesis_makes_move_then_search_negative() -> None:
    atoms = (CausalAtom(slot=CausalSlot.LOCATION, value="D"),)
    confidence = confidence_from_masses(4.0, 0.0, prior=1.0)
    assert confidence == 0.8
    hypothesis = CausalHypothesis(
        owner_id=_OWNER,
        atoms=atoms,
        outcome=CausalOutcome.DANGER,
        support=4.0,
        counter=0.0,
        evidence_ids=("evidence-1",),
        counter_evidence_ids=(),
        provenance_kind=CausalProvenanceKind.OBSERVATION,
    )
    model = CausalWorldModel(owner_id=_OWNER, hypotheses=(hypothesis,))
    rollout = rollout_prospective(
        _loop_input(),
        _situation(),
        _self_model(),
        _memory(),
        ProspectivePolicy(horizon=2, max_depth=2),
        goal_board=_board(),
        causal_world_model=model,
    )
    path = choose_path(rollout)
    assert path is not None
    assert path[0].direction is ActionDirection.WAIT
    assert path_value(path) <= 0.0
    assert model.hypotheses[0].confidence == 0.8


@pytest.mark.asyncio
async def test_imagine_keeps_one_step_search_and_collapses_deeper_move() -> None:
    from agents.cognition.deliberation import (
        CommandPlanner,
        MultiCriteriaIntentionSelector,
    )
    from agents.cognition.imagination import ImaginationEngine
    from agents.cognition.motivation import MotivationAppraisal
    from world.actions import Move, Search, Wait

    engine = ImaginationEngine()
    loop_input = _loop_input()
    situation = _situation()
    self_state = _self_model()
    memory = _memory()
    board = _board()
    shallow = await engine.imagine(
        loop_input, situation, self_state, memory, board
    )
    assert engine.last_prospective_audit() is None
    assert len(shallow.futures) > 1
    assert all(item.horizon_ticks == 1 for item in shallow.futures)
    appraisal = await MotivationAppraisal(mortality_appraisal_enabled=False).evaluate(
        loop_input, situation, self_state, shallow, board
    )
    chosen = await MultiCriteriaIntentionSelector().select(
        loop_input, appraisal, shallow, board, self_state=self_state
    )
    assert chosen.direction is ActionDirection.SEARCH
    planned = await CommandPlanner().plan(loop_input, chosen, shallow, memory, board)
    assert type(planned.command) is Search

    policy = ProspectivePolicy(horizon=3, max_depth=3)
    deep = await engine.imagine(
        loop_input,
        situation,
        self_state,
        memory,
        board,
        prospective_policy=policy,
    )
    assert len(deep.futures) == 1
    winner = deep.futures[0]
    assert winner.direction is ActionDirection.MOVE
    assert winner.target_entity_id == "D"
    assert winner.horizon_ticks >= 2
    gather = next(
        effect
        for effect in winner.goal_effects
        if effect.goal_id.value == "gather-info"
    )
    assert gather.progress_delta == 0.4
    assert gather.confidence == 0.7
    deep_appraisal = await MotivationAppraisal(
        mortality_appraisal_enabled=False
    ).evaluate(loop_input, situation, self_state, deep, board)
    assert len(deep_appraisal.appraisals) == 1
    deep_choice = await MultiCriteriaIntentionSelector().select(
        loop_input, deep_appraisal, deep, board, self_state=self_state
    )
    deep_plan = await CommandPlanner().plan(
        loop_input, deep_choice, deep, memory, board
    )
    assert type(deep_plan.command) is Move
    assert deep_plan.command.destination_id == EntityId("D")
    audit = engine.last_prospective_audit()
    assert audit is not None
    assert audit.direction_code == "move"

    atoms = (CausalAtom(slot=CausalSlot.LOCATION, value="D"),)
    model = CausalWorldModel(
        owner_id=_OWNER,
        hypotheses=(
            CausalHypothesis(
                owner_id=_OWNER,
                atoms=atoms,
                outcome=CausalOutcome.DANGER,
                support=4.0,
                counter=0.0,
                evidence_ids=("evidence-1",),
                counter_evidence_ids=(),
                provenance_kind=CausalProvenanceKind.OBSERVATION,
            ),
        ),
    )
    feared = await engine.imagine(
        loop_input,
        situation,
        self_state,
        memory,
        board,
        prospective_policy=ProspectivePolicy(horizon=2, max_depth=2),
        causal_world_model=model,
    )
    assert len(feared.futures) == 1
    assert feared.futures[0].direction is ActionDirection.WAIT
    feared_plan = await CommandPlanner().plan(
        loop_input,
        await MultiCriteriaIntentionSelector().select(
            loop_input,
            await MotivationAppraisal(mortality_appraisal_enabled=False).evaluate(
                loop_input, situation, self_state, feared, board
            ),
            feared,
            board,
            self_state=self_state,
        ),
        feared,
        memory,
        board,
    )
    assert type(feared_plan.command) is Wait
    assert model.hypotheses[0].confidence == 0.8


def test_depth_three_uncertainty_stays_in_range_and_rises() -> None:
    rollout = _rollout(horizon=3, max_depth=3)
    assert type(rollout) is ProspectiveRollout
    by_id = {item.transition_id: item for item in rollout.transitions}
    for item in rollout.transitions:
        assert 0.0 <= item.confidence <= 1.0
        assert 0.0 <= item.uncertainty.epistemic <= 1.0
        assert 0.0 <= item.uncertainty.aleatory <= 1.0
        assert item.uncertainty.band in {
            UncertaintyBand.LOW,
            UncertaintyBand.MEDIUM,
            UncertaintyBand.HIGH,
        }
        if item.depth == 2 and item.parent_id is not None:
            parent = by_id[item.parent_id]
            assert item.uncertainty.epistemic > parent.uncertainty.epistemic


def test_source_keeps_provider_import_in_selection_module() -> None:
    root = Path(__file__).resolve().parents[2]
    selection = (root / "src/agents/cognition/prospective_selection.py").read_text(
        encoding="utf-8"
    )
    rollout = (root / "src/agents/cognition/prospective.py").read_text(encoding="utf-8")
    imagination = (root / "src/agents/cognition/imagination.py").read_text(
        encoding="utf-8"
    )
    assert "from llm import" in selection
    assert "import llm" not in rollout
    assert "import llm" not in imagination
    assert "search_base_probability" not in rollout


def test_rollout_debug_names_direction_without_objective_terms(caplog) -> None:
    caplog.set_level(logging.DEBUG, logger="agents.cognition.prospective")
    rollout = _rollout(horizon=2, max_depth=2, max_branches=1)
    assert type(rollout) is ProspectiveRollout
    messages = " ".join(record.getMessage() for record in caplog.records)
    assert "direction=move" in messages
    assert "reason_code=budget_branches" in messages
    assert "search_base_probability" not in messages
    assert "candidate_json" not in messages


@pytest.mark.asyncio
async def test_each_budget_still_yields_one_command(caplog) -> None:
    from agents.cognition.deliberation import (
        CommandPlanner,
        MultiCriteriaIntentionSelector,
    )
    from agents.cognition.imagination import ImaginationEngine
    from agents.cognition.motivation import MotivationAppraisal
    from world.actions import Move, Search, Wait

    caplog.set_level(logging.DEBUG, logger="agents.cognition.prospective_selection")
    loop_input = _loop_input()
    situation = _situation()
    self_state = _self_model()
    memory = _memory()
    board = _board()

    async def one_command(
        policy: ProspectivePolicy,
    ) -> tuple[type[object], object]:
        engine = ImaginationEngine()
        futures = await engine.imagine(
            loop_input,
            situation,
            self_state,
            memory,
            board,
            prospective_policy=policy,
        )
        assert len(futures.futures) == 1
        choice = await MultiCriteriaIntentionSelector().select(
            loop_input,
            await MotivationAppraisal(mortality_appraisal_enabled=False).evaluate(
                loop_input, situation, self_state, futures, board
            ),
            futures,
            board,
            self_state=self_state,
        )
        plan = await CommandPlanner().plan(
            loop_input, choice, futures, memory, board
        )
        assert type(plan.command) in {Move, Search, Wait}
        audit = engine.last_prospective_audit()
        assert audit is not None
        return type(plan.command), audit

    samples = iter((0.0, 1.0))
    cases = (
        (
            ProspectivePolicy(horizon=1, max_depth=1),
            ProspectivePruneReason.BUDGET_DEPTH,
        ),
        (
            ProspectivePolicy(horizon=2, max_depth=2, max_branches=1),
            ProspectivePruneReason.BUDGET_BRANCHES,
        ),
        (
            ProspectivePolicy(
                horizon=2, max_depth=2, allow_provider=True, max_llm_calls=0
            ),
            ProspectivePruneReason.BUDGET_LLM,
        ),
        (
            ProspectivePolicy(
                horizon=2, max_depth=2, allow_provider=True, max_tokens=0
            ),
            ProspectivePruneReason.BUDGET_TOKENS,
        ),
        (
            ProspectivePolicy(
                horizon=2,
                max_depth=2,
                clock=lambda: next(samples),
                timeout_seconds=0.05,
            ),
            ProspectivePruneReason.BUDGET_TIMEOUT,
        ),
    )
    for policy, reason in cases:
        _command, audit = await one_command(policy)
        if reason is ProspectivePruneReason.BUDGET_TIMEOUT:
            assert audit.timeout_hit is True
            continue
        if policy.allow_provider:
            assert audit.fallback_used is True
            assert reason.value in {"budget_llm", "budget_tokens"}
            continue
        rollout = rollout_prospective(
            loop_input,
            situation,
            self_state,
            memory,
            policy,
            goal_board=board,
        )
        assert reason in rollout.budgets_exhausted
    warnings = " ".join(
        record.getMessage()
        for record in caplog.records
        if record.levelno == logging.WARNING
        and record.name == "agents.cognition.prospective_selection"
    )
    assert "reason_code=budget_llm" in warnings
    assert "reason_code=budget_tokens" in warnings
    debug = " ".join(
        record.getMessage()
        for record in caplog.records
        if record.levelno == logging.DEBUG
        and record.name == "agents.cognition.prospective_selection"
    )
    assert "selected_count=0" in debug
    assert "token_count=0" in debug
    assert "candidate_json" not in debug


@pytest.mark.asyncio
async def test_provider_ranks_known_ids_and_rejects_foreign_ids(caplog) -> None:
    from agents.cognition.imagination import ImaginationEngine
    from agents.cognition.prospective_selection import ProspectiveSelectionOutput
    from tests.fakes.llm import FakeLLMProvider, ScriptedSuccess

    caplog.set_level(logging.DEBUG, logger="agents.cognition.prospective_selection")

    class Boom:
        async def generate(self, request: object) -> object:
            raise AssertionError(request)

    engine = ImaginationEngine()
    loop_input = _loop_input()
    quiet = await engine.imagine(
        loop_input,
        _situation(),
        _self_model(),
        _memory(),
        _board(),
        prospective_policy=ProspectivePolicy(horizon=2, max_depth=2),
        llm_provider=Boom(),
    )
    assert quiet.futures[0].direction is ActionDirection.MOVE
    ranked = rollout_prospective(
        loop_input,
        _situation(),
        _self_model(),
        _memory(),
        ProspectivePolicy(horizon=2, max_depth=2, allow_provider=True),
        goal_board=_board(),
    )
    wait_id = next(
        item.transition_id
        for item in ranked.transitions
        if item.direction is ActionDirection.WAIT and item.depth == 1
    )
    provider = FakeLLMProvider()
    provider.enqueue(
        "prospective-3-agent-1",
        ScriptedSuccess(output=ProspectiveSelectionOutput(selected_ids=(wait_id,))),
    )
    assisted = ImaginationEngine()
    chosen = await assisted.imagine(
        loop_input,
        _situation(),
        _self_model(),
        _memory(),
        _board(),
        prospective_policy=ProspectivePolicy(
            horizon=2, max_depth=2, allow_provider=True
        ),
        llm_provider=provider,
    )
    assert chosen.futures[0].direction is ActionDirection.WAIT
    audit = assisted.last_prospective_audit()
    assert audit is not None
    assert audit.fallback_used is False
    assert audit.llm_call_count == 1
    selected_logs = [
        record.getMessage()
        for record in caplog.records
        if record.name == "agents.cognition.prospective_selection"
        and "selected_count=1" in record.getMessage()
    ]
    assert selected_logs
    assert "token_count=64" in selected_logs[0]
    assert "candidate_json" not in selected_logs[0]
    foreign = FakeLLMProvider()
    foreign.enqueue(
        "prospective-3-agent-1",
        ScriptedSuccess(
            output=ProspectiveSelectionOutput(selected_ids=("not-a-transition",))
        ),
    )
    kept = ImaginationEngine()
    fallback = await kept.imagine(
        loop_input,
        _situation(),
        _self_model(),
        _memory(),
        _board(),
        prospective_policy=ProspectivePolicy(
            horizon=2, max_depth=2, allow_provider=True
        ),
        llm_provider=foreign,
    )
    assert fallback.futures[0].direction is ActionDirection.MOVE
    fallback_audit = kept.last_prospective_audit()
    assert fallback_audit is not None
    assert fallback_audit.fallback_used is True
    warnings = [
        record.getMessage()
        for record in caplog.records
        if record.levelno == logging.WARNING
        and record.name == "agents.cognition.prospective_selection"
    ]
    assert any("reason_code=foreign_id" in message for message in warnings)
