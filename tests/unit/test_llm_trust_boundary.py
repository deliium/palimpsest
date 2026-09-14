"""LLM output is untrusted and cannot enter the world gateway."""

from __future__ import annotations

import pytest

from llm.models import LLMResponse
from world.actions import accept_action_request


def test_llm_response_is_rejected_by_world_gateway() -> None:
    response = LLMResponse(provider="stub", model="scripted", text='{"kind": "speak"}')
    with pytest.raises(TypeError, match="ActionRequest"):
        accept_action_request(response)


def test_llm_response_is_frozen() -> None:
    response = LLMResponse(provider="stub", model="scripted", text="ok", token_count=4)
    with pytest.raises(AttributeError):
        response.text = "mutated"  # type: ignore[misc]


def test_llm_token_count_rejects_booleans() -> None:
    with pytest.raises(ValueError, match="non-negative integer"):
        LLMResponse(provider="stub", model="scripted", text="ok", token_count=True)
