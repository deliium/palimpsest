"""LLM output is untrusted and cannot enter engine submissions."""

from __future__ import annotations

import pytest

from llm.models import LLMResponse
from simulation.lifecycle import require_action_submission
from world.actions import Wait, require_agent_command


def test_llm_response_is_rejected_as_action_submission() -> None:
    response = LLMResponse(provider="stub", model="scripted", text='{"kind": "speak"}')
    with pytest.raises(TypeError, match="ActionSubmission"):
        require_action_submission(response)


def test_provider_shaped_mappings_are_not_commands() -> None:
    with pytest.raises(TypeError, match="raw mappings"):
        require_agent_command({"kind": "wait"})
    assert require_agent_command(Wait()) == Wait()


def test_llm_response_is_frozen() -> None:
    response = LLMResponse(provider="stub", model="scripted", text="ok", token_count=4)
    with pytest.raises(AttributeError):
        response.text = "mutated"  # type: ignore[misc]


def test_llm_token_count_rejects_booleans() -> None:
    with pytest.raises(ValueError, match="non-negative integer"):
        LLMResponse(provider="stub", model="scripted", text="ok", token_count=True)
