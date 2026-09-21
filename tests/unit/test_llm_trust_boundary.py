"""LLM structured results are untrusted and cannot enter engine submissions."""

from __future__ import annotations

import pytest

from agents.models import AgentId
from llm.models import (
    FinishReason,
    LLMResult,
    LLMResultMetadata,
    StructuredOutput,
    require_structured_output_type,
    validate_structured_output,
)
from simulation.actions import admit_agent_command
from simulation.clock import Tick
from simulation.lifecycle import ActionSubmission, TickToken, require_action_submission
from simulation.models import SimulationRunConfig
from world._operations import OperationRejected, RejectionCode, validate_action_request
from world._state import WorldState
from world.actions import (
    ActionRequest,
    Wait,
    accept_action_request,
    require_agent_command,
)
from world.identifiers import EntityId, ProposalId, RequestId, WorldId, WorldRevision


class _DecisionOutput(StructuredOutput):
    kind: str


class _Translator:
    def __init__(self, mapping: dict[AgentId, EntityId]) -> None:
        self._forward = mapping
        self._reverse = {entity: agent for agent, entity in mapping.items()}

    def to_entity_id(self, agent_id: AgentId) -> EntityId:
        return self._forward[agent_id]

    def to_agent_id(self, entity_id: EntityId) -> AgentId:
        return self._reverse[entity_id]


def _result() -> LLMResult[_DecisionOutput]:
    return LLMResult(
        output=_DecisionOutput(kind="speak"),
        metadata=LLMResultMetadata(
            provider_name="stub",
            model_name="scripted",
            finish_reason=FinishReason.STOP,
        ),
    )


def _untrusted_values() -> list[object]:
    output = _DecisionOutput(kind="wait")
    result = _result()
    return [
        result,
        output,
        output.model_dump(),
        output.model_dump_json(),
        '{"kind":"wait"}',
        {"kind": "wait"},
        {
            "request_id": "r-1",
            "proposal_id": "p-1",
            "world_id": "world-1",
            "actor_id": "body-1",
            "revision": 0,
            "command": {"kind": "wait"},
        },
        {
            "token": "tick-1",
            "agent_id": "agent-1",
            "command": {"kind": "wait"},
        },
    ]


def test_llm_result_is_rejected_as_action_submission() -> None:
    with pytest.raises(TypeError, match="ActionSubmission"):
        require_action_submission(_result())


def test_structured_output_is_rejected_as_agent_command() -> None:
    with pytest.raises(TypeError, match="unsupported agent command type"):
        require_agent_command(_DecisionOutput(kind="wait"))
    with pytest.raises(TypeError, match="raw mappings"):
        require_agent_command({"kind": "wait"})
    assert require_agent_command(Wait()) == Wait()


def test_provider_shaped_payloads_rejected_by_command_and_submission_gates() -> None:
    token = TickToken(value="tok-1", tick=Tick(0))
    for value in _untrusted_values():
        with pytest.raises(TypeError):
            require_agent_command(value)
        with pytest.raises(TypeError):
            require_action_submission(value)
        with pytest.raises(TypeError):
            ActionSubmission(token=token, agent_id=AgentId("agent-1"), command=value)  # type: ignore[arg-type]


def test_provider_shaped_payloads_rejected_by_admission() -> None:
    config = SimulationRunConfig(seed=9)
    agent_id = AgentId("agent-1")
    translator = _Translator({agent_id: EntityId("body-1")})
    for value in _untrusted_values():
        with pytest.raises(TypeError):
            admit_agent_command(
                config=config,
                agent_id=agent_id,
                command=value,
                translator=translator,
                world_id=WorldId("world-1"),
                revision=WorldRevision(0),
                keys=("llm-trust",),
            )


def test_provider_shaped_payloads_rejected_by_world_operation_boundary() -> None:
    for value in _untrusted_values():
        with pytest.raises(TypeError):
            accept_action_request(value)

    empty = WorldState(WorldRevision(0))
    for value in _untrusted_values():
        outcome = validate_action_request(
            world_id=WorldId("world-1"),
            state=empty,
            request=value,
        )
        assert isinstance(outcome, OperationRejected)
        assert outcome.code is RejectionCode.WRONG_TRUST_STAGE
        # Never log world or model payloads in authority trust proofs.


def test_action_request_still_required_for_gateway() -> None:
    request = ActionRequest(
        request_id=RequestId("r-1"),
        proposal_id=ProposalId("p-1"),
        world_id=WorldId("world-1"),
        actor_id=EntityId("body-1"),
        revision=WorldRevision(0),
        command=Wait(),
    )
    assert accept_action_request(request) is request


def test_structured_output_repr_hides_payload() -> None:
    output = _DecisionOutput(kind="secret-payload")
    assert "secret-payload" not in repr(output)
    assert "secret-payload" not in repr(_result())


def test_structured_output_rejects_instances_as_types() -> None:
    with pytest.raises(TypeError, match="class"):
        require_structured_output_type(_DecisionOutput(kind="x"))


def test_validate_structured_output_requires_exact_type() -> None:
    validated = validate_structured_output(_DecisionOutput, {"kind": "ok"})
    assert type(validated) is _DecisionOutput
    with pytest.raises(ValueError, match="schema validation"):
        validate_structured_output(_DecisionOutput, {"kind": 1})


def test_permissive_structured_output_subclass_is_rejected() -> None:
    with pytest.raises(TypeError, match="extra"):

        class _Loose(StructuredOutput):
            model_config = StructuredOutput.model_config.copy()
            model_config["extra"] = "allow"  # type: ignore[index]
            kind: str


def test_cognitive_artifacts_rejected_by_command_and_submission_gates() -> None:
    from agents.cognition.models import (
        ActionPlan,
        CognitiveLoopResult,
        ComponentBoundaryRecord,
        ComponentKind,
        ComponentStatus,
        DecisionMetadata,
        IntentionCode,
        InternalAgentState,
        MotivationCode,
        SelectedIntention,
    )

    agent = AgentId("agent-1")
    plan = ActionPlan(owner_id=agent, command=Wait(), confidence=1.0)
    intention = SelectedIntention(
        owner_id=agent,
        intention=IntentionCode.WAIT,
        source_motive=MotivationCode.WAIT,
        confidence=1.0,
    )
    record = ComponentBoundaryRecord(
        invocation_id="inv-1",
        component_kind=ComponentKind.PLANNING,
        component_version="v1",
        ordinal=7,
        status=ComponentStatus.COMPLETED,
        confidence=1.0,
        input_artifact=intention,
        output_artifact=plan,
        decision_metadata=DecisionMetadata(),
    )
    result = CognitiveLoopResult(
        invocation_id="inv-1",
        agent_id=agent,
        command=Wait(),
        boundary_records=(record,),
        memory_update_intents=(),
        final_confidence=1.0,
        internal_state=InternalAgentState(owner_id=agent),
    )
    token = TickToken(value="tok-cogs", tick=Tick(0))
    for value in (plan, intention, record, result, {"kind": "wait"}):
        with pytest.raises(TypeError):
            require_agent_command(value)
        with pytest.raises(TypeError):
            require_action_submission(value)
        with pytest.raises(TypeError):
            ActionSubmission(token=token, agent_id=agent, command=value)  # type: ignore[arg-type]
