# mypy: ignore-errors
"""Experiment-ledger export, checkpoint, blank-slate, and result validation."""

from __future__ import annotations

import pytest

from agents.cognition.configuration import CognitionScientificHypothesesMode
from agents.cognition.emotion import PassthroughEmotionalStateAppraiser
from agents.cognition.experimentation import (
    ExperimentCognitionBinding,
    admit_hypothesis,
    empty_experiment_ledger,
    formulate_hypothesis,
    require_owner_experiment_ledger,
)
from agents.cognition.goal_manager import PassthroughGoalManager
from agents.cognition.loop import CognitiveLoop
from agents.cognition.models import InternalAgentState
from agents.models import AgentId
from experiments.civilization_benchmark_evidence import (
    NOT_PERSISTED_STORES,
    STORE_PROBE_PATHS,
)
from simulation.agent_runtime import AgentRuntimeStatus
from simulation.models import RunId
from simulation.new_agent_initialization import (
    BlankSlateStoreCounts,
    assert_blank_slate_subjective_state,
)
from simulation.run_control import AgentRuntimeCheckpoint
from simulation.runner_models import SimulationRunnerResult
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
from world.experimentation import (
    ExperimentOperator,
    ExperimentOutcomeClass,
    ExperimentProcessToken,
)

pytestmark = pytest.mark.unit

OWNER = AgentId("agent-1")


def _binding() -> ExperimentCognitionBinding:
    return ExperimentCognitionBinding(
        max_hypotheses=8,
        max_trials_per_tick=1,
        repeat_threshold=2,
        learn_into_genealogy=False,
        allow_provider=False,
    )


def _ledger(owner: AgentId = OWNER, *, with_row: bool = False):
    ledger = empty_experiment_ledger(owner, _binding())
    if with_row:
        row = formulate_hypothesis(
            owner_id=owner,
            hypothesis_id="hyp:export",
            operator=ExperimentOperator.COMBINE,
            operand_a_id="item-material",
            operand_b_id="resource-material",
            process_token=ExperimentProcessToken.NONE,
            predicted_outcome=ExperimentOutcomeClass.SUCCESS,
        )
        ledger = admit_hypothesis(ledger, row)
    return ledger


def _checkpoint(**overrides):
    payload = {
        "agent_id": OWNER,
        "status": AgentRuntimeStatus.ACTIVE,
        "internal_state": InternalAgentState(owner_id=OWNER),
        "last_observation_key": None,
        "processed_invocation_count": 0,
        "finalized_hash_count": 0,
        "goals": (),
    }
    payload.update(overrides)
    return AgentRuntimeCheckpoint(**payload)


def test_require_owner_rejects_foreign_owner() -> None:
    ledger = _ledger(AgentId("agent-2"))
    with pytest.raises(ValueError, match="field: owner_mismatch"):
        require_owner_experiment_ledger(ledger, OWNER, field_name="field")


def test_checkpoint_round_trips_the_ledger() -> None:
    ledger = _ledger(with_row=True)
    checkpoint = _checkpoint(experiment_ledger=ledger)
    assert checkpoint.experiment_ledger == ledger
    with pytest.raises(ValueError, match="experiment_ledger: owner_mismatch"):
        _checkpoint(experiment_ledger=_ledger(AgentId("agent-2")))


def _loop() -> CognitiveLoop:
    return CognitiveLoop(
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


def test_ledger_if_present_is_none_until_the_channel_runs() -> None:
    loop = _loop()
    loop._bounded_experimentation_caps = _binding()
    assert loop.experiment_ledger_if_present() is None
    ledger = loop.experiment_ledger_for(OWNER)
    assert ledger is not None
    assert loop.experiment_ledger_if_present() is ledger


def test_restore_ledger_validates_owner_and_installs() -> None:
    loop = _loop()
    loop._bounded_experimentation_caps = _binding()
    ledger = _ledger(with_row=True)
    loop.restore_experiment_ledger(ledger, OWNER)
    assert loop.experiment_ledger_if_present() is ledger
    with pytest.raises(ValueError, match="owner_mismatch"):
        loop.restore_experiment_ledger(_ledger(AgentId("agent-2")), OWNER)
    loop.restore_experiment_ledger(None)
    assert loop.experiment_ledger_if_present() is None


def test_result_accepts_ordered_owner_ledgers() -> None:
    ledger = _ledger()
    result = SimulationRunnerResult(
        run_id=RunId("run-export"),
        ticks_committed=1,
        stop_reason=_stop_reason(),
        attempt_receipts=(),
        experiment_ledgers=(ledger,),
    )
    assert result.experiment_ledgers == (ledger,)


def test_result_rejects_unordered_or_duplicate_ledgers() -> None:
    ledger = _ledger()
    with pytest.raises(TypeError, match="experiment_ledgers must be ordered"):
        SimulationRunnerResult(
            run_id=RunId("run-export"),
            ticks_committed=1,
            stop_reason=_stop_reason(),
            attempt_receipts=(),
            experiment_ledgers={ledger},
        )
    with pytest.raises(TypeError, match="duplicate_owner"):
        SimulationRunnerResult(
            run_id=RunId("run-export"),
            ticks_committed=1,
            stop_reason=_stop_reason(),
            attempt_receipts=(),
            experiment_ledgers=(ledger, ledger),
        )


def _stop_reason():
    from simulation.runner_models import RunnerStopReasonCode

    return RunnerStopReasonCode.MAX_TICKS


def test_newborn_blank_slate_rejects_content_and_accepts_empty() -> None:
    assert_blank_slate_subjective_state(OWNER, BlankSlateStoreCounts())
    with pytest.raises(ValueError, match="subjective_copy_forbidden"):
        assert_blank_slate_subjective_state(
            OWNER, BlankSlateStoreCounts(experiment_ledger=1)
        )


def test_benchmark_reports_the_ledger_as_measurable() -> None:
    assert "experiment_ledger" not in NOT_PERSISTED_STORES
    assert STORE_PROBE_PATHS["experiment_ledger"] == (
        "runtime",
        "experiment_ledger",
    )


def test_export_has_no_rule_or_physics_fields() -> None:
    ledger = _ledger(with_row=True)
    row = ledger.hypotheses[0]
    for name in ("law", "rules", "probability", "delta", "product_id", "harm_band"):
        assert not hasattr(row, name)
