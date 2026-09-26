"""Contracts for subjective counterfactual scenarios."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from agents.cognition.configuration import CognitionCounterfactualMode
from agents.cognition.counterfactual import (
    COUNTERFACTUAL_POLICY_VERSION,
    CounterfactualAffect,
    CounterfactualAffectCode,
    CounterfactualPolicy,
    CounterfactualProvenanceKind,
    CounterfactualScenario,
    CounterfactualState,
    PredictedAlternativeOutcome,
    RememberedDecision,
    assemble_counterfactual_scenarios,
    communication_counterpart,
    decision_id_for,
    default_counterfactual_policy,
    direct_observation_memory_id,
    scenario_id_for,
)
from agents.cognition.models import ActionDirection
from agents.cognition.reflection import DecisionOutcomeCode
from agents.models import AgentId
from memory.models import MemorySourceKind
from world.models import PhysicalRules
from world.observations import ObservationSourceKind

_SOURCE = Path("src/agents/cognition/counterfactual.py")
_OWNER = AgentId("agent-owner")


def _decision(
    *,
    command_kind: str = "help",
    outcome_code: DecisionOutcomeCode = DecisionOutcomeCode.NO_PROGRESS,
    counterpart_id: str | None = "bob",
    memory_id: str | None = "memory-help",
    goal_ids: tuple[str, ...] = ("goal-help",),
    tick: int = 3,
    place_id: str | None = "place-a",
) -> RememberedDecision:
    decision_id = decision_id_for(
        owner_id=_OWNER,
        tick=tick,
        command_kind=command_kind,
        outcome_code=outcome_code,
        place_id=place_id,
        counterpart_id=counterpart_id,
        memory_id=memory_id,
        goal_ids=goal_ids,
    )
    return RememberedDecision(
        decision_id=decision_id,
        owner_id=_OWNER,
        tick=tick,
        command_kind=command_kind,
        outcome_code=outcome_code,
        place_id=place_id,
        counterpart_id=counterpart_id,
        memory_id=memory_id,
        goal_ids=goal_ids,
    )


def _scenario(
    decision: RememberedDecision | None = None,
    *,
    direction: ActionDirection = ActionDirection.WAIT,
    target_id: str | None = "bob",
    confidence: float = 0.75,
    magnitude: float = 0.2,
    provenance: object = CounterfactualProvenanceKind.IMAGINED_ALTERNATIVE,
) -> CounterfactualScenario:
    remembered = _decision() if decision is None else decision
    scenario_id = scenario_id_for(
        owner_id=remembered.owner_id,
        decision_id=remembered.decision_id,
        direction=direction,
        target_id=target_id,
    )
    return CounterfactualScenario(
        owner_id=remembered.owner_id,
        scenario_id=scenario_id,
        decision=remembered,
        alternative_direction=direction,
        target_id=target_id,
        predicted_outcome=PredictedAlternativeOutcome(
            direction=direction,
            value=0.0,
            magnitude=magnitude,
        ),
        confidence=confidence,
        goal_ids=remembered.goal_ids,
        emotional_impact=CounterfactualAffect(
            code=CounterfactualAffectCode.REGRET,
            magnitude=magnitude,
        ),
        provenance=provenance,  # type: ignore[arg-type]
    )


def test_mode_and_policy_default_closed(caplog: pytest.LogCaptureFixture) -> None:
    assert CognitionCounterfactualMode.DISABLED.value == "disabled"
    with caplog.at_level(logging.DEBUG, logger="agents.cognition.counterfactual"):
        policy = default_counterfactual_policy()
    assert policy.version == COUNTERFACTUAL_POLICY_VERSION
    assert policy.max_decisions == 4
    assert policy.min_confidence == 0.5
    assert policy.direction_bonus == 0.2
    assert policy.max_llm_calls == 1
    assert policy.max_tokens == 256
    assert policy.allow_provider is False
    assert any(
        "policy_version=counterfactual-v1" in record.message
        and "max_decisions=4" in record.message
        and "min_confidence=0.5" in record.message
        for record in caplog.records
    )


def test_policy_rejects_bad_caps_with_reason_codes(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.ERROR, logger="agents.cognition.counterfactual"):
        with pytest.raises(ValueError, match="max_decisions: not_positive"):
            CounterfactualPolicy(max_decisions=0)
        with pytest.raises(ValueError, match="max_llm_calls: not_nonnegative"):
            CounterfactualPolicy(max_llm_calls=-1)
        with pytest.raises(ValueError, match="min_confidence: not_unit_interval"):
            CounterfactualPolicy(min_confidence=1.5)
        with pytest.raises(ValueError, match="direction_bonus: not_unit_interval"):
            CounterfactualPolicy(direction_bonus=-0.1)
    assert any(
        record.levelno == logging.ERROR and "field=max_decisions" in record.message
        for record in caplog.records
    )
    assert CounterfactualPolicy(max_llm_calls=0, max_tokens=0).max_tokens == 0


def test_decision_construction_logs_owner_without_info_payload(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.DEBUG, logger="agents.cognition.counterfactual"):
        decision = _decision()
    assert decision.command_kind == "help"
    assert decision.outcome_code is DecisionOutcomeCode.NO_PROGRESS
    debug = [
        record
        for record in caplog.records
        if record.levelno == logging.DEBUG and "owner_id=agent-owner" in record.message
    ]
    assert debug
    assert "policy_version=counterfactual-v1" in debug[0].message
    assert "max_decisions=4" in debug[0].message
    assert "min_confidence=0.5" in debug[0].message
    info = [record for record in caplog.records if record.levelno == logging.INFO]
    assert info == []
    joined = " ".join(record.message for record in caplog.records)
    assert "bob" not in joined
    assert "goal-help" not in joined


def test_scenario_rejects_foreign_provenance_and_unit_breaches() -> None:
    decision = _decision()
    with pytest.raises(TypeError, match="provenance: invalid_provenance"):
        _scenario(decision, provenance=ObservationSourceKind.OCCURRENCE)
    with pytest.raises(TypeError, match="provenance: invalid_provenance"):
        _scenario(decision, provenance=MemorySourceKind.DIRECT_OBSERVATION)
    with pytest.raises(ValueError, match="confidence: not_unit_interval"):
        _scenario(decision, confidence=1.2)
    with pytest.raises(ValueError, match="magnitude: not_unit_interval"):
        _scenario(decision, magnitude=-0.1)


def test_objective_inputs_are_rejected_and_absent_from_source() -> None:
    text = _SOURCE.read_text(encoding="utf-8")
    assert "WorldEvent" not in text
    assert "WorldState" not in text
    assert "PhysicalRules" not in text
    assert "import llm" not in text
    assert "search_base_probability" not in text
    decision = _decision()
    with pytest.raises(TypeError, match="not a subjective input"):
        _scenario(decision, provenance=PhysicalRules())


def test_duplicate_scenario_ids_fail_closed() -> None:
    scenario = _scenario()
    assert scenario.provenance is CounterfactualProvenanceKind.IMAGINED_ALTERNATIVE
    with pytest.raises(ValueError, match="scenarios: duplicate_scenario_id"):
        assemble_counterfactual_scenarios((scenario, scenario))
    assert assemble_counterfactual_scenarios((scenario,)) == (scenario,)


def test_neutral_state_defaults_and_rejects_foreign_code() -> None:
    state = CounterfactualState()
    assert state.code is CounterfactualAffectCode.NEUTRAL
    assert state.magnitude == 0.0
    with pytest.raises(TypeError, match="code: invalid_affect"):
        CounterfactualState(code=DecisionOutcomeCode.UNKNOWN)  # type: ignore[arg-type]


def test_counterpart_and_memory_id_come_from_subjective_records() -> None:
    from types import SimpleNamespace

    from memory.models import MemorySourceKind

    talked = SimpleNamespace(
        kind="talked",
        actor_id=SimpleNamespace(value="alice"),
        other_entity_id=SimpleNamespace(value="body-1"),
    )
    assert communication_counterpart((talked,), "body-1") == "alice"
    asked = SimpleNamespace(
        kind="asked",
        actor_id=SimpleNamespace(value="body-1"),
        other_entity_id=SimpleNamespace(value="carol"),
    )
    assert communication_counterpart((asked,), "body-1") == "carol"
    assert communication_counterpart((), "body-1") is None
    trace = SimpleNamespace(
        provenance=SimpleNamespace(kind=MemorySourceKind.DIRECT_OBSERVATION),
        concepts=(SimpleNamespace(concept="help"),),
        memory_id=SimpleNamespace(value="memory-help"),
    )
    other = SimpleNamespace(
        provenance=SimpleNamespace(kind=MemorySourceKind.COMMUNICATED),
        concepts=(SimpleNamespace(concept="help"),),
        memory_id=SimpleNamespace(value="memory-other"),
    )
    assert direct_observation_memory_id((other, trace), "help") == "memory-help"
    assert direct_observation_memory_id((trace,), "wait") is None


@pytest.mark.asyncio
async def test_finalize_appends_one_remembered_decision(
    caplog: pytest.LogCaptureFixture,
) -> None:
    from agents.cognition.configuration import CognitionCounterfactualMode
    from agents.cognition.counterfactual import CounterfactualPolicy
    from simulation.run_control import AgentRuntimeCheckpoint
    from tests.unit.test_agent_runtime import _runtime, _self, _token
    from world.actions import Help
    from world.identifiers import EntityId

    runtime, _, _ = _runtime()
    runtime.start()
    runtime._loop._counterfactual_mode = CognitionCounterfactualMode.DETERMINISTIC
    runtime._loop._counterfactual_policy = CounterfactualPolicy(max_decisions=1)
    prepared = await runtime.prepare_observation(_self(tick=0), token=_token(0))
    pending = await runtime.bind_effective_command(
        prepared, effective_command=Help(target_id=EntityId("bob"))
    )
    with caplog.at_level(logging.DEBUG, logger="simulation.agent_runtime"):
        await runtime.finalize_pending(pending)
    assert runtime._decision_journal is None
    assert runtime._remembered_decisions is not None
    assert len(runtime._remembered_decisions) == 1
    decision = runtime._remembered_decisions[0]
    assert decision.command_kind == "help"
    assert decision.counterpart_id == "bob"
    assert decision.outcome_code is DecisionOutcomeCode.NO_PROGRESS
    assert decision.place_id == "loc-1"
    assert decision.memory_id is None
    debug = [
        record
        for record in caplog.records
        if record.levelno == logging.DEBUG
        and record.name == "simulation.agent_runtime"
        and "remembered_decision_appended" in record.message
    ]
    assert len(debug) == 1
    message = debug[0].message
    assert "owner_id=agent-1" in message
    assert "tick=0" in message
    assert "command_kind=help" in message
    assert "outcome_code=no_progress" in message
    assert "decision_count=1" in message
    assert "bob" not in message
    info = [
        record.getMessage()
        for record in caplog.records
        if record.levelno == logging.INFO
    ]
    assert all("bob" not in line and "success=" not in line for line in info)

    again = await runtime.prepare_observation(_self(tick=1), token=_token(1))
    second = await runtime.bind_effective_command(
        again, effective_command=Help(target_id=EntityId("bob"))
    )
    await runtime.finalize_pending(second)
    assert runtime._remembered_decisions is not None
    assert len(runtime._remembered_decisions) == 1
    assert runtime._remembered_decisions[0].tick == 1

    checkpoint = runtime.export_runtime_checkpoint()
    assert type(checkpoint) is AgentRuntimeCheckpoint
    restored, _, _ = _runtime()
    restored.restore_runtime_checkpoint(checkpoint)
    assert restored._remembered_decisions == runtime._remembered_decisions

    quiet, _, _ = _runtime()
    quiet.start()
    quiet_prepared = await quiet.prepare_observation(_self(tick=0), token=_token(0))
    quiet_pending = await quiet.bind_effective_command(quiet_prepared)
    caplog.clear()
    with caplog.at_level(logging.WARNING, logger="simulation.agent_runtime"):
        await quiet.finalize_pending(quiet_pending)
        quiet._append_remembered_decision(quiet_pending)
    assert quiet._remembered_decisions is None
    warnings = [
        record.getMessage()
        for record in caplog.records
        if record.levelno >= logging.WARNING
    ]
    assert any(
        "remembered_decision_skipped" in line and "reason_code=disabled" in line
        for line in warnings
    )
    assert sum("remembered_decision_skipped" in line for line in warnings) == 1
