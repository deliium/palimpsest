# mypy: ignore-errors
"""Intentional scientific tests: observation gating and Wait replacement."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

import pytest

from agents.cognition.configuration import CognitionScientificHypothesesMode
from agents.cognition.emotion import PassthroughEmotionalStateAppraiser
from agents.cognition.experimentation import (
    ExperimentCognitionBinding,
    ExperimentLedger,
    HypothesisCondition,
    HypothesisConditionSlot,
    HypothesisSourceKind,
    admit_hypothesis,
    compile_scientific_test,
    empty_experiment_ledger,
    formulate_hypothesis,
    observed_condition_tokens,
)
from agents.cognition.goal_manager import PassthroughGoalManager
from agents.cognition.loop import CognitiveLoop
from agents.cognition.models import (
    ActionPlan,
    CognitiveLoopInput,
    InternalAgentState,
)
from agents.cognition.world_model import (
    CausalAtom,
    CausalHypothesis,
    CausalOutcome,
    CausalProvenanceKind,
    CausalSlot,
    CausalWorldModel,
)
from agents.models import AgentId
from tests.typecheck.cognitive_loop import (
    ScriptedFutureImagination,
    ScriptedIntentionSelector,
    ScriptedMemoryRetriever,
    ScriptedMemoryUpdateHook,
    ScriptedMotivationEvaluator,
    ScriptedPerceptionInterpreter,
    ScriptedPlanner,
    ScriptedSelfStateProjector,
    ScriptedSituationModeler,
)
from world.actions import Experiment, Move, Wait
from world.environment import Season
from world.experimentation import (
    ExperimentOperator,
    ExperimentOutcomeClass,
    ExperimentProcessToken,
)
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import DayPhase
from world.observations import Observation

pytestmark = pytest.mark.unit

OWNER = AgentId("agent-1")


@dataclass(frozen=True, slots=True)
class _EntityValue:
    value: str


@dataclass(frozen=True, slots=True)
class _ObservedEntity:
    entity_id: _EntityValue


@dataclass(frozen=True, slots=True)
class FakeObservation:
    tick: int = 4
    location_id: str = "loc-1"
    day_phase: str = "day"
    weather: str = "clear"
    held_item_kind: str = "tool"
    counterpart: str = "agent-2"
    season: str = "spring"
    temperature_band: str = "mild"
    hazard: str = "none"
    action: str = "combine"
    concept: str = "fire"
    items: tuple[_ObservedEntity, ...] = (
        _ObservedEntity(_EntityValue("item:material")),
    )
    resources: tuple[_ObservedEntity, ...] = (
        _ObservedEntity(_EntityValue("resource:material")),
    )


def _binding(max_trials: int = 1) -> ExperimentCognitionBinding:
    return ExperimentCognitionBinding(
        max_hypotheses=8,
        max_trials_per_tick=max_trials,
        repeat_threshold=2,
        learn_into_genealogy=False,
        allow_provider=False,
    )


def _ledger(max_trials: int = 1) -> ExperimentLedger:
    return empty_experiment_ledger(OWNER, _binding(max_trials))


def _hypothesis(
    *,
    hypothesis_id: str = "hyp:science",
    prediction: ExperimentOutcomeClass | None = ExperimentOutcomeClass.SUCCESS,
    conditions: tuple[HypothesisCondition, ...] = (
        HypothesisCondition(HypothesisConditionSlot.LOCATION, "loc-1"),
    ),
):
    return formulate_hypothesis(
        owner_id=OWNER,
        hypothesis_id=hypothesis_id,
        operator=ExperimentOperator.COMBINE,
        operand_a_id="item:material",
        operand_b_id="resource:material",
        process_token=ExperimentProcessToken.NONE,
        predicted_outcome=prediction,
        conditions=conditions,
        created_tick=0,
    )


def _ledger_with(*rows) -> ExperimentLedger:
    ledger = _ledger()
    for row in rows:
        ledger = admit_hypothesis(ledger, row)
    return ledger


def test_observation_tokens_read_only_public_attributes() -> None:
    observed = observed_condition_tokens(FakeObservation())
    assert observed[HypothesisConditionSlot.LOCATION] == ("loc-1",)
    assert observed[HypothesisConditionSlot.DAY_PHASE] == ("day",)
    assert observed[HypothesisConditionSlot.HAZARD] == ("none",)


def test_matching_hypothesis_replaces_wait() -> None:
    ledger = _ledger_with(_hypothesis())
    compiled = compile_scientific_test(OWNER, ledger, FakeObservation())
    assert type(compiled.command) is Experiment
    assert compiled.command.hypothesis_id == "hyp:science"
    stored = compiled.ledger.hypotheses[0]
    assert stored.revisions[-1].reason.value == "test_formulated"


def test_conditions_mismatch_yields_no_command_or_revision() -> None:
    row = _hypothesis(
        conditions=(
            HypothesisCondition(HypothesisConditionSlot.LOCATION, "loc-9"),
        )
    )
    ledger = _ledger_with(row)
    compiled = compile_scientific_test(OWNER, ledger, FakeObservation())
    assert compiled.command is None
    assert compiled.reason == "scientific_hypothesis_untestable"
    assert compiled.ledger == ledger


def test_trial_cap_yields_no_command() -> None:
    from agents.cognition.experimentation import ExperimentTrial

    ledger = _ledger_with(_hypothesis())
    ledger = ExperimentLedger(
        owner_id=ledger.owner_id,
        max_hypotheses=ledger.max_hypotheses,
        max_trials_per_tick=ledger.max_trials_per_tick,
        repeat_threshold=ledger.repeat_threshold,
        learn_into_genealogy=ledger.learn_into_genealogy,
        hypotheses=ledger.hypotheses,
        trials=(
            ExperimentTrial(
                tick=4,
                event_id="evt:used",
                outcome_class="success",
                discovery_mode="deliberate",
                hypothesis_id="hyp:science",
            ),
        ),
    )
    compiled = compile_scientific_test(OWNER, ledger, FakeObservation())
    assert compiled.command is None
    assert compiled.reason == "experiment_trial_cap"


def test_new_formulation_uses_observed_conditions() -> None:
    ledger = _ledger()
    compiled = compile_scientific_test(
        OWNER,
        ledger,
        FakeObservation(),
        formulate_if_missing=True,
    )
    assert type(compiled.command) is Experiment
    stored = compiled.ledger.hypotheses[0]
    assert stored.source_kind is HypothesisSourceKind.OBSERVED
    assert stored.source_token == "observation"
    assert any(
        condition.slot is HypothesisConditionSlot.LOCATION
        for condition in stored.conditions
    )
    assert stored.revisions[0].reason.value == "formulated"
    assert stored.revisions[-1].reason.value == "test_formulated"


def test_untestable_active_hypothesis_does_not_create_another() -> None:
    row = _hypothesis(
        conditions=(
            HypothesisCondition(HypothesisConditionSlot.LOCATION, "loc-9"),
        )
    )
    ledger = _ledger_with(row)
    compiled = compile_scientific_test(
        OWNER,
        ledger,
        FakeObservation(),
        formulate_if_missing=True,
    )
    assert compiled.command is None
    assert len(compiled.ledger.hypotheses) == 1


def test_causal_match_attaches_link_and_source() -> None:
    model = CausalWorldModel(
        owner_id=OWNER,
        hypotheses=(
            CausalHypothesis(
                owner_id=OWNER,
                atoms=(CausalAtom(CausalSlot.LOCATION, "loc-1"),),
                outcome=CausalOutcome.HELP,
                support=2.0,
                counter=0.0,
                evidence_ids=("evt:1",),
                counter_evidence_ids=(),
                provenance_kind=CausalProvenanceKind.OBSERVATION,
            ),
        ),
    )
    compiled = compile_scientific_test(
        OWNER,
        _ledger_with(_hypothesis()),
        FakeObservation(),
        causal_model=model,
    )
    stored = compiled.ledger.hypotheses[0]
    assert stored.causal_hypothesis_id
    assert stored.source_kind is HypothesisSourceKind.OBSERVED


def test_no_causal_match_leaves_link_empty() -> None:
    model = CausalWorldModel(owner_id=OWNER, hypotheses=())
    compiled = compile_scientific_test(
        OWNER,
        _ledger_with(_hypothesis()),
        FakeObservation(),
        causal_model=model,
    )
    assert compiled.ledger.hypotheses[0].causal_hypothesis_id == ""


def test_foreign_owner_ledger_is_rejected() -> None:
    ledger = empty_experiment_ledger(AgentId("agent-2"), _binding())
    with pytest.raises(ValueError, match="ledger: owner_mismatch"):
        compile_scientific_test(OWNER, ledger, FakeObservation())


def test_foreign_causal_model_is_rejected() -> None:
    model = CausalWorldModel(owner_id=AgentId("agent-2"))
    with pytest.raises(ValueError, match="causal_model: owner_mismatch"):
        compile_scientific_test(
            OWNER,
            _ledger_with(_hypothesis()),
            FakeObservation(),
            causal_model=model,
        )


def test_loop_replaces_wait_but_not_meaningful_commands() -> None:
    loop = CognitiveLoop(
        perception=ScriptedPerceptionInterpreter(),
        memory=ScriptedMemoryRetriever(),
        situation=ScriptedSituationModeler(),
        self_state=ScriptedSelfStateProjector(),
        goal_manager=PassthroughGoalManager(),
        emotional_state=PassthroughEmotionalStateAppraiser(),
        futures=ScriptedFutureImagination(),
        motivation=ScriptedMotivationEvaluator(),
        intention=ScriptedIntentionSelector(),
        planner=ScriptedPlanner(),
        memory_updates=ScriptedMemoryUpdateHook(),
        scientific_hypotheses_mode=CognitionScientificHypothesesMode.DETERMINISTIC,
    )
    loop._bounded_experimentation_caps = _binding()
    observation = Observation(
        world_id=WorldId("world-1"),
        observer_id=EntityId("body-1"),
        revision=WorldRevision(0),
        tick=4,
        day_phase=DayPhase.DAY,
        season=Season.SPRING,
    )
    loop_input = CognitiveLoopInput(
        agent_id=OWNER,
        observation=observation,
        internal_state=InternalAgentState(owner_id=OWNER),
    )
    loop._experiment_ledger = _ledger_with(
        _hypothesis(
            conditions=(
                HypothesisCondition(HypothesisConditionSlot.DAY_PHASE, "day"),
            )
        )
    )
    result = asyncio.run(loop.run(loop_input, invocation_id="inv-science"))
    assert type(result.command) is Experiment
    assert result.command.hypothesis_id == "hyp:science"
    assert loop._experiment_ledger is not None
    assert loop._experiment_ledger.hypotheses[0].revisions[-1].reason.value == (
        "test_formulated"
    )


def test_loop_does_not_replace_a_meaningful_command() -> None:
    class MovingPlanner(ScriptedPlanner):
        async def plan(self, *args, **kwargs):
            loop_input = args[0]
            return ActionPlan(
                owner_id=loop_input.agent_id,
                command=Move(destination_id=EntityId("loc-2")),
                confidence=1.0,
            )

    loop = CognitiveLoop(
        perception=ScriptedPerceptionInterpreter(),
        memory=ScriptedMemoryRetriever(),
        situation=ScriptedSituationModeler(),
        self_state=ScriptedSelfStateProjector(),
        goal_manager=PassthroughGoalManager(),
        emotional_state=PassthroughEmotionalStateAppraiser(),
        futures=ScriptedFutureImagination(),
        motivation=ScriptedMotivationEvaluator(),
        intention=ScriptedIntentionSelector(),
        planner=MovingPlanner(),
        memory_updates=ScriptedMemoryUpdateHook(),
        scientific_hypotheses_mode=CognitionScientificHypothesesMode.DETERMINISTIC,
    )
    loop._bounded_experimentation_caps = _binding()
    loop._experiment_ledger = _ledger_with(_hypothesis())
    observation = Observation(
        world_id=WorldId("world-1"),
        observer_id=EntityId("body-1"),
        revision=WorldRevision(0),
        tick=4,
        day_phase=DayPhase.DAY,
    )
    loop_input = CognitiveLoopInput(
        agent_id=OWNER,
        observation=observation,
        internal_state=InternalAgentState(owner_id=OWNER),
    )
    result = asyncio.run(loop.run(loop_input, invocation_id="inv-science-move"))
    assert type(result.command) is Move


def test_experimentation_never_imports_objective_rules() -> None:
    import ast
    from pathlib import Path

    path = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "agents"
        / "cognition"
        / "experimentation.py"
    )
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
        elif isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
    assert "world._experiment_laws" not in modules
    assert "world._rules" not in modules
    assert not any(module.startswith("world._experiment_laws.") for module in modules)
    assert not any(module.startswith("world._rules.") for module in modules)


def test_science_off_is_passthrough() -> None:
    loop = CognitiveLoop(
        perception=ScriptedPerceptionInterpreter(),
        memory=ScriptedMemoryRetriever(),
        situation=ScriptedSituationModeler(),
        self_state=ScriptedSelfStateProjector(),
        goal_manager=PassthroughGoalManager(),
        emotional_state=PassthroughEmotionalStateAppraiser(),
        futures=ScriptedFutureImagination(),
        motivation=ScriptedMotivationEvaluator(),
        intention=ScriptedIntentionSelector(),
        planner=ScriptedPlanner(),
        memory_updates=ScriptedMemoryUpdateHook(),
    )
    loop._bounded_experimentation_caps = _binding()
    loop._experiment_ledger = _ledger_with(_hypothesis())
    observation = Observation(
        world_id=WorldId("world-1"),
        observer_id=EntityId("body-1"),
        revision=WorldRevision(0),
        tick=4,
        day_phase=DayPhase.DAY,
    )
    loop_input = CognitiveLoopInput(
        agent_id=OWNER,
        observation=observation,
        internal_state=InternalAgentState(owner_id=OWNER),
    )
    result = asyncio.run(loop.run(loop_input, invocation_id="inv-science-off"))
    assert type(result.command) is Wait
