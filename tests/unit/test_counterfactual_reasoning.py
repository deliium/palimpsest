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
    alternative_for,
    assemble_counterfactual_scenarios,
    communication_counterpart,
    consider_counterfactuals,
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
    selection = Path("src/agents/cognition/counterfactual_selection.py").read_text(
        encoding="utf-8"
    )
    assert "llm.models" not in selection
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


def _input(*, tick: int = 3, exits: tuple[object, ...] = ()):
    from dataclasses import replace

    from agents.cognition.models import CognitiveLoopInput, InternalAgentState
    from tests.unit.test_agent_runtime import _self

    return CognitiveLoopInput(
        agent_id=_OWNER,
        observation=replace(_self(tick=tick), exits=exits),
        internal_state=InternalAgentState(owner_id=_OWNER),
    )


def _messages(caplog: pytest.LogCaptureFixture, level: int) -> list[str]:
    return [
        record.getMessage()
        for record in caplog.records
        if record.name == "agents.cognition.counterfactual" and record.levelno == level
    ]


def test_help_without_progress_imagines_waiting(
    caplog: pytest.LogCaptureFixture,
) -> None:
    decision = _decision(command_kind="help", counterpart_id="bob")
    with caplog.at_level(logging.DEBUG, logger="agents.cognition.counterfactual"):
        scenarios = consider_counterfactuals(
            _input(), (decision,), policy=default_counterfactual_policy()
        )
    assert len(scenarios) == 1
    scenario = scenarios[0]
    assert scenario.alternative_direction is ActionDirection.WAIT
    assert scenario.target_id == "bob"
    assert scenario.emotional_impact.code is CounterfactualAffectCode.REGRET
    assert scenario.emotional_impact.magnitude == 0.2
    assert scenario.predicted_outcome.value == 0.0
    assert scenario.predicted_outcome.magnitude == 0.2
    assert scenario.confidence == 0.75
    assert scenario.provenance is CounterfactualProvenanceKind.IMAGINED_ALTERNATIVE
    assert scenario.goal_ids == ("goal-help",)
    debug = _messages(caplog, logging.DEBUG)
    assert any(
        "counterfactual_scenario" in line
        and "direction_code=wait" in line
        and "affect_code=regret" in line
        and "provenance_code=imagined_alternative" in line
        and "confidence_band=high" in line
        and "owner_id=agent-owner" in line
        and "tick=3" in line
        for line in debug
    )
    assert all("bob" not in line for line in _messages(caplog, logging.INFO))
    assert any(
        "counterfactual_considered kept_count=1 skipped_count=0" in line
        for line in _messages(caplog, logging.INFO)
    )


def test_perceived_change_is_not_salient(caplog: pytest.LogCaptureFixture) -> None:
    decision = _decision(outcome_code=DecisionOutcomeCode.PERCEIVED_CHANGE)
    with caplog.at_level(logging.WARNING, logger="agents.cognition.counterfactual"):
        scenarios = consider_counterfactuals(
            _input(), (decision,), policy=default_counterfactual_policy()
        )
    assert scenarios == ()
    assert any(
        "counterfactual_skipped reason_code=not_salient" in line
        for line in _messages(caplog, logging.WARNING)
    )


def test_search_without_progress_moves_toward_another_exit() -> None:
    from world.identifiers import EntityId
    from world.observations import VisibleExit

    decision = _decision(
        command_kind="search",
        counterpart_id=None,
        place_id="place-a",
        memory_id=None,
        goal_ids=(),
    )
    exits = (VisibleExit(destination_id=EntityId("loc-b"), name="path"),)
    scenarios = consider_counterfactuals(
        _input(exits=exits),
        (decision,),
        policy=default_counterfactual_policy(),
    )
    assert len(scenarios) == 1
    scenario = scenarios[0]
    assert scenario.alternative_direction is ActionDirection.MOVE
    assert scenario.target_id == "loc-b"
    assert scenario.emotional_impact.code is CounterfactualAffectCode.REGRET
    assert scenario.emotional_impact.magnitude == 0.5
    assert scenario.confidence == 0.6
    blocked = _decision(
        command_kind="search",
        counterpart_id=None,
        place_id="loc-b",
        tick=4,
        memory_id=None,
        goal_ids=(),
    )
    assert consider_counterfactuals(
        _input(tick=4, exits=exits),
        (blocked,),
        policy=default_counterfactual_policy(),
    ) == ()


def test_wait_with_stored_counterpart_imagines_communication() -> None:
    from social.relationships import (
        DirectedRelationshipProfile,
        RelationshipActivationState,
        RelationshipConfidence,
        RelationshipDimension,
        RelationshipDimensionState,
        RelationshipId,
        RelationshipPolicyRef,
        RelationshipRevisionId,
    )

    decision = _decision(
        command_kind="wait",
        counterpart_id="alice",
        place_id="place-a",
        memory_id="memory-wait",
        goal_ids=("goal-wait",),
    )
    policy = RelationshipPolicyRef(policy_id="rel-v1", version="1")
    confidence = RelationshipConfidence(
        confidence=0.9, support_mass=0.9, contradiction_mass=0.0
    )
    profile = DirectedRelationshipProfile(
        relationship_id=RelationshipId("rel-1"),
        source_id=_OWNER,
        target_id=AgentId("alice"),
        dimensions=(
            RelationshipDimensionState(
                dimension=RelationshipDimension.TRUST,
                value=0.8,
                confidence=confidence,
                evidence=(),
                logical_tick=1,
                policy=policy,
            ),
        ),
        activation_state=RelationshipActivationState.ACTIVE,
        current_revision_id=RelationshipRevisionId("rrev-1"),
        revision_ordinal=1,
        created_tick=1,
        updated_tick=1,
        policy=policy,
    )
    scenarios = consider_counterfactuals(
        _input(),
        (decision,),
        policy=default_counterfactual_policy(),
        relationships=(profile,),
    )
    assert len(scenarios) == 1
    scenario = scenarios[0]
    assert scenario.alternative_direction is ActionDirection.COMMUNICATE
    assert scenario.target_id == "alice"
    assert scenario.confidence == 0.9
    assert scenario.emotional_impact.code is CounterfactualAffectCode.REGRET
    assert scenario.emotional_impact.magnitude == 0.45


def test_missing_decision_and_objective_model_fail_closed(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING, logger="agents.cognition.counterfactual"):
        assert (
            consider_counterfactuals(
                _input(), policy=default_counterfactual_policy()
            )
            == ()
        )
    assert any(
        "counterfactual_skipped reason_code=no_remembered_decision" in line
        for line in _messages(caplog, logging.WARNING)
    )
    assert consider_counterfactuals(_input(), (_decision(),)) == ()
    with pytest.raises(TypeError, match="not a subjective input"):
        consider_counterfactuals(
            _input(),
            (_decision(),),
            policy=default_counterfactual_policy(),
            causal_world_model=PhysicalRules(),
        )
    foreign = _decision(tick=9)
    object.__setattr__(foreign, "owner_id", AgentId("other-owner"))
    with pytest.raises(ValueError, match="owner_mismatch"):
        consider_counterfactuals(
            _input(), (foreign,), policy=default_counterfactual_policy()
        )
    talk = _decision(command_kind="talk", counterpart_id=None, memory_id=None)
    with caplog.at_level(logging.WARNING, logger="agents.cognition.counterfactual"):
        assert (
            consider_counterfactuals(
                _input(), (talk,), policy=default_counterfactual_policy()
            )
            == ()
        )
    assert any(
        "counterfactual_skipped reason_code=no_alternative" in line
        for line in _messages(caplog, logging.WARNING)
    )
    assert alternative_for(talk, _input().observation) is None


@pytest.mark.asyncio
async def test_disabled_prepare_keeps_the_same_command() -> None:
    from dataclasses import replace

    from agents.cognition.configuration import (
        CognitionLoopConfig,
        build_cognitive_loop,
    )

    decision = _decision()
    loop_input = _input()
    disabled = build_cognitive_loop(CognitionLoopConfig())
    enabled = build_cognitive_loop(
        replace(
            CognitionLoopConfig(),
            counterfactual_mode=CognitionCounterfactualMode.DETERMINISTIC,
        )
    )
    quiet = await disabled.prepare(
        loop_input,
        invocation_id="inv-off",
        remembered_decisions=(decision,),
    )
    loud = await enabled.prepare(
        loop_input,
        invocation_id="inv-on",
        remembered_decisions=(decision,),
    )
    assert disabled.last_counterfactual_scenarios() == ()
    kept = enabled.last_counterfactual_scenarios()
    assert len(kept) == 1
    assert kept[0].scenario_id not in repr(loud.futures)
    assert kept[0].scenario_id not in repr(quiet.futures)
    assert type(quiet.proposed_command) is type(loud.proposed_command)
    assert quiet.proposed_command == loud.proposed_command


def _help_scenario(*, memory_id: str | None = "memory-help"):
    decision = _decision(memory_id=memory_id, counterpart_id="bob")
    scenarios = consider_counterfactuals(
        _input(), (decision,), policy=default_counterfactual_policy()
    )
    assert len(scenarios) == 1
    return scenarios[0]


def test_conclusions_revise_belief_without_an_alternative_trace(
    caplog: pytest.LogCaptureFixture,
) -> None:
    from agents.cognition.counterfactual import counterfactual_belief_requests
    from memory.belief_formation import extract_evidence_candidates

    scenario = _help_scenario()
    with caplog.at_level(logging.DEBUG, logger="agents.cognition.counterfactual"):
        requests = counterfactual_belief_requests(
            (scenario,),
            policy=default_counterfactual_policy(),
            owner_id=_OWNER,
            tick=3,
        )
    assert len(requests) == 1
    claim = requests[0].claim
    assert claim.predicate == "counterfactual_alternative"
    assert claim.subject.concept == scenario.decision.decision_id
    assert claim.value.text_value == "wait"
    assert requests[0].evidence.supporting[0].memory_id.value == "memory-help"
    assert any(
        "counterfactual_effect" in line
        and "effect_code=belief" in line
        and "reason_code=applied" in line
        and "owner_id=agent-owner" in line
        and "tick=3" in line
        for line in _messages(caplog, logging.DEBUG)
    )
    formation = Path("src/memory/belief_formation.py").read_text(encoding="utf-8")
    service = Path("src/memory/belief_service.py").read_text(encoding="utf-8")
    assert "counterfactual_alternative" not in formation
    assert "counterfactual_alternative" not in service
    assert "counterfactual_alternative" not in (
        extract_evidence_candidates.__doc__ or ""
    )
    missing = _help_scenario(memory_id=None)
    skipped = counterfactual_belief_requests(
        (missing,),
        policy=default_counterfactual_policy(),
        owner_id=_OWNER,
        tick=3,
    )
    assert skipped == ()


@pytest.mark.asyncio
async def test_alternative_direction_wins_one_vote() -> None:
    from agents.cognition.deliberation import (
        CommandPlanner,
        MultiCriteriaIntentionSelector,
        _pairwise_compare,
    )
    from agents.cognition.models import PossibleFutures
    from agents.models import DriveKind
    from tests.unit.test_intention_selection import (
        _appraisal,
        _future,
        _loop_input,
        _motivation,
    )

    futures = (
        _future("flee", ActionDirection.FLEE),
        _future("wait", ActionDirection.WAIT),
    )
    motivation = _motivation(futures, active_drives=(DriveKind.AUTONOMY,))
    possible = PossibleFutures(
        owner_id=AgentId("agent-1"), futures=futures, confidence=1.0
    )
    by_id = {item.future_id: item for item in futures}
    left = _appraisal(futures[0])
    right = _appraisal(futures[1])
    assert _pairwise_compare(left, right, by_id, motivation) == 0
    biased = _pairwise_compare(
        left,
        right,
        by_id,
        motivation,
        counterfactual_bias={"wait": 0.2, "flee": 0.0},
    )
    assert biased == -1
    assert type(biased) is int
    selector = MultiCriteriaIntentionSelector()
    previous = await selector.select(_loop_input(), motivation, possible)
    chosen = await selector.select(
        _loop_input(),
        motivation,
        possible,
        counterfactual_bias={"wait": 0.2, "flee": 0.0},
    )
    assert previous.direction is ActionDirection.FLEE
    assert chosen.direction is ActionDirection.WAIT
    assert chosen.decision_metadata.tie_break_applied is False
    plan = await CommandPlanner().plan(_loop_input(), chosen, possible)
    assert plan.command.kind == "wait"


def test_relationship_revision_lowers_trust_without_help_given(
    caplog: pytest.LogCaptureFixture,
) -> None:
    from agents.cognition.counterfactual import counterfactual_relationship_requests
    from social.relationships import (
        RelationshipDimension,
        RelationshipSignalKind,
        signals_to_dimension_deltas,
    )
    from world.identifiers import EntityId

    scenario = _help_scenario()

    def resolve(entity_id: EntityId) -> AgentId | None:
        if entity_id.value == "bob":
            return AgentId("agent-bob")
        return None

    with caplog.at_level(logging.DEBUG, logger="simulation.agent_runtime"):
        requests = counterfactual_relationship_requests(
            (scenario,),
            policy=default_counterfactual_policy(),
            owner_id=_OWNER,
            tick=3,
            resolve_counterpart=resolve,
        )
    assert len(requests) == 1
    signal = requests[0].signals[0]
    assert signal.kind is RelationshipSignalKind.COUNTERFACTUAL_TRUST_DOWN
    assert signal.strength == scenario.confidence
    assert signal.memory_ref == "memory-help"
    deltas = signals_to_dimension_deltas(requests[0].signals)
    assert deltas[RelationshipDimension.TRUST][0] == pytest.approx(-0.075)
    assert RelationshipSignalKind.HELP_GIVEN not in {
        item.kind for item in requests[0].signals
    }
    messages = [
        record.getMessage()
        for record in caplog.records
        if record.name == "simulation.agent_runtime"
    ]
    assert any(
        "counterfactual_effect" in line
        and "effect_code=relationship" in line
        and "reason_code=applied" in line
        and "bob" not in line
        for line in messages
    )
    unresolved = counterfactual_relationship_requests(
        (scenario,),
        policy=default_counterfactual_policy(),
        owner_id=_OWNER,
        tick=3,
        resolve_counterpart=lambda _entity: None,
    )
    assert unresolved == ()


@pytest.mark.asyncio
async def test_loop_identity_mode_gates_the_self_belief() -> None:
    from dataclasses import replace

    from agents.cognition.configuration import (
        CognitionIdentityMode,
        CognitionLoopConfig,
        build_cognitive_loop,
    )
    from world.actions import Wait

    decision = _decision()
    loop_input = _input()
    passthrough = build_cognitive_loop(
        replace(
            CognitionLoopConfig(),
            counterfactual_mode=CognitionCounterfactualMode.DETERMINISTIC,
        )
    )
    enabled = build_cognitive_loop(
        replace(
            CognitionLoopConfig(),
            counterfactual_mode=CognitionCounterfactualMode.DETERMINISTIC,
            identity_mode=CognitionIdentityMode.ENABLED,
        )
    )
    quiet_proposal = await passthrough.prepare(
        loop_input, invocation_id="inv-pass", remembered_decisions=(decision,)
    )
    enabled_proposal = await enabled.prepare(
        loop_input, invocation_id="inv-on", remembered_decisions=(decision,)
    )
    quiet = await passthrough.complete(
        quiet_proposal, effective_command=Wait()
    )
    loud = await enabled.complete(enabled_proposal, effective_command=Wait())
    quiet_predicates = _revision_predicates(quiet.identity_revisions)
    loud_predicates = _revision_predicates(loud.identity_revisions)
    assert "identity.weakness.own_choice.counterfactual_regret" not in quiet_predicates
    assert "identity.weakness.own_choice.counterfactual_regret" in loud_predicates
    belief_predicates = [
        intent.belief_revision.claim.predicate
        for intent in loud.memory_update_intents
        if getattr(intent, "belief_revision", None) is not None
    ]
    assert "counterfactual_alternative" in belief_predicates
    concepts = [
        concept.concept
        for intent in loud.memory_update_intents
        if getattr(intent, "memory", None) is not None
        for concept in intent.memory.concepts
    ]
    assert "wait" not in concepts


def _revision_predicates(requests: tuple[object, ...]) -> set[str]:
    predicates: set[str] = set()
    for request in requests:
        claim = getattr(request, "claim", None)
        predicate = getattr(claim, "predicate", None)
        if isinstance(predicate, str):
            predicates.add(predicate)
    return predicates


def test_identity_passthrough_is_quiet_and_enabled_records_regret(
    caplog: pytest.LogCaptureFixture,
) -> None:
    from agents.cognition.configuration import CognitionIdentityMode
    from agents.cognition.identity import counterfactual_regret_request

    scenario = _help_scenario()
    with caplog.at_level(logging.DEBUG, logger="agents.cognition.identity"):
        request = counterfactual_regret_request(
            scenario, owner_id=_OWNER, tick=3
        )
    assert CognitionIdentityMode.PASSTHROUGH.value == "passthrough"
    assert request is not None
    assert (
        request.claim.predicate
        == "identity.weakness.own_choice.counterfactual_regret"
    )
    assert request.claim.value.bool_value is True
    assert request.evidence.supporting[0].memory_id.value == "memory-help"
    assert any(
        "counterfactual_effect" in line
        and "effect_code=identity" in line
        and "reason_code=applied" in line
        for line in [
            record.getMessage()
            for record in caplog.records
            if record.name == "agents.cognition.identity"
        ]
    )


@pytest.mark.asyncio
async def test_enabled_emotion_adds_sadness_and_passthrough_does_not() -> None:
    from agents.cognition.emotion import (
        EmotionalStateEngine,
        PassthroughEmotionalStateAppraiser,
    )
    from agents.cognition.models import EmotionDriverCode, EmotionKind
    from tests.unit.test_emotional_state_engine import (
        _board,
        _loop_input,
        _memory,
        _perception,
        _self_model,
        _situation,
    )

    scenario = _help_scenario()
    engine = EmotionalStateEngine()
    loop_input = _loop_input()
    enabled = await engine.appraise(
        loop_input,
        _perception(),
        _situation(),
        _memory(),
        _self_model(),
        _board(),
        counterfactual_scenarios=(scenario,),
    )
    assert EmotionKind.SADNESS in {item.kind for item in enabled.state.intensities}
    sadness = enabled.state.get(EmotionKind.SADNESS)
    assert sadness == pytest.approx(0.05)
    assert EmotionDriverCode.COUNTERFACTUAL in enabled.driver_codes
    passthrough = PassthroughEmotionalStateAppraiser()
    quiet = await passthrough.appraise(
        loop_input,
        _perception(),
        _situation(),
        _memory(),
        _self_model(),
        _board(),
        counterfactual_scenarios=(scenario,),
    )
    assert quiet.state.get(EmotionKind.SADNESS) == 0.0


@pytest.mark.asyncio
async def test_provider_ranks_known_ids_and_falls_back(
    caplog: pytest.LogCaptureFixture,
) -> None:
    from agents.cognition.counterfactual import CounterfactualPolicy
    from agents.cognition.counterfactual_selection import (
        CounterfactualSelectionOutput,
        rank_counterfactual_scenarios,
    )
    from tests.fakes.llm import FakeLLMProvider, ScriptedSuccess

    schema = CounterfactualSelectionOutput.model_json_schema()["properties"]
    assert "probability" not in schema
    scenario = _help_scenario()
    other = _help_scenario()
    policy = CounterfactualPolicy(allow_provider=True)
    calls = {"count": 0}

    class Spy:
        async def generate(self, request: object) -> object:
            calls["count"] += 1
            raise AssertionError(request)

    quiet_policy = default_counterfactual_policy()
    quiet = await rank_counterfactual_scenarios(
        (scenario,),
        quiet_policy,
        provider=Spy(),
        owner_id=_OWNER.value,
        tick=3,
    )
    assert calls["count"] == 0
    assert quiet.fallback_used is False
    missing = await rank_counterfactual_scenarios(
        (scenario,),
        policy,
        provider=None,
        owner_id=_OWNER.value,
        tick=3,
    )
    assert missing.fallback_used is True
    assert missing.selected_ids == (scenario.scenario_id,)
    provider = FakeLLMProvider()
    provider.enqueue(
        f"counterfactual-3-{_OWNER.value}",
        ScriptedSuccess(
            output=CounterfactualSelectionOutput(selected_ids=(scenario.scenario_id,))
        ),
    )
    with caplog.at_level(
        logging.DEBUG, logger="agents.cognition.counterfactual_selection"
    ):
        ranked = await rank_counterfactual_scenarios(
            (scenario, other),
            policy,
            provider=provider,
            owner_id=_OWNER.value,
            tick=3,
        )
    assert ranked.selected_ids == (scenario.scenario_id,)
    assert ranked.fallback_used is False
    debug = [
        record.getMessage()
        for record in caplog.records
        if record.name == "agents.cognition.counterfactual_selection"
        and record.levelno == logging.DEBUG
    ]
    assert any(
        "counterfactual_llm_selection" in line
        and f"owner_id={_OWNER.value}" in line
        and "tick=3" in line
        and "candidate_count=2" in line
        and "selected_count=1" in line
        and "token_count=256" in line
        and "fallback_used=False" in line
        and "candidate_json" not in line
        for line in debug
    )
    foreign = FakeLLMProvider()
    foreign.enqueue(
        f"counterfactual-3-{_OWNER.value}",
        ScriptedSuccess(
            output=CounterfactualSelectionOutput(selected_ids=("not-a-scenario",))
        ),
    )
    caplog.clear()
    with caplog.at_level(
        logging.WARNING, logger="agents.cognition.counterfactual_selection"
    ):
        rejected = await rank_counterfactual_scenarios(
            (scenario,),
            policy,
            provider=foreign,
            owner_id=_OWNER.value,
            tick=3,
        )
    assert rejected.fallback_used is True
    assert rejected.selected_ids == (scenario.scenario_id,)
    warnings = [
        record.getMessage()
        for record in caplog.records
        if record.levelno == logging.WARNING
    ]
    assert any("reason_code=foreign_id" in line for line in warnings)
    budget = await rank_counterfactual_scenarios(
        (scenario,),
        CounterfactualPolicy(allow_provider=True, max_llm_calls=0),
        provider=Spy(),
        owner_id=_OWNER.value,
        tick=3,
    )
    assert budget.reason_code == "budget_llm"
    assert calls["count"] == 0


@pytest.mark.asyncio
async def test_disabled_audits_stay_empty() -> None:
    from agents.cognition.counterfactual import CounterfactualProvenanceKind
    from tests.unit.test_agent_runtime import _runtime, _self, _token

    quiet, _, _ = _runtime()
    quiet.start()
    prepared = await quiet.prepare_observation(_self(tick=0), token=_token(0))
    pending = await quiet.bind_effective_command(prepared)
    await quiet.finalize_pending(pending)
    assert quiet.export_counterfactual_audits() == ()

    runtime, _, _ = _runtime()
    runtime.start()
    runtime._loop._counterfactual_mode = CognitionCounterfactualMode.DETERMINISTIC
    runtime._loop._counterfactual_policy = default_counterfactual_policy()
    prepared = await runtime.prepare_observation(_self(tick=0), token=_token(0))
    pending = await runtime.bind_effective_command(prepared)
    await runtime.finalize_pending(pending)
    audits = runtime.export_counterfactual_audits()
    assert len(audits) == 1
    provenance = CounterfactualProvenanceKind.IMAGINED_ALTERNATIVE.value
    assert audits[0].provenance_code == provenance
    assert audits[0].fallback_used is False
    assert audits[0].llm_call_count == 0
