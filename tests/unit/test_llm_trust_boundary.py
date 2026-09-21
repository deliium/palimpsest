"""LLM structured results are untrusted and cannot enter engine submissions."""

from __future__ import annotations

import pytest

from llm.models import (
    FinishReason,
    LLMResult,
    LLMResultMetadata,
    StructuredOutput,
    require_structured_output_type,
    validate_structured_output,
)
from simulation.lifecycle import require_action_submission
from world.actions import Wait, require_agent_command


class _DecisionOutput(StructuredOutput):
    kind: str


def _result() -> LLMResult[_DecisionOutput]:
    return LLMResult(
        output=_DecisionOutput(kind="speak"),
        metadata=LLMResultMetadata(
            provider_name="stub",
            model_name="scripted",
            finish_reason=FinishReason.STOP,
        ),
    )


def test_llm_result_is_rejected_as_action_submission() -> None:
    with pytest.raises(TypeError, match="ActionSubmission"):
        require_action_submission(_result())


def test_structured_output_is_rejected_as_agent_command() -> None:
    with pytest.raises(TypeError, match="unsupported agent command type"):
        require_agent_command(_DecisionOutput(kind="wait"))
    with pytest.raises(TypeError, match="raw mappings"):
        require_agent_command({"kind": "wait"})
    assert require_agent_command(Wait()) == Wait()


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
