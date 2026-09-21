"""Reusable test doubles for network-free unit tests."""

from tests.fakes.llm import (
    FakeCallRecord,
    FakeClock,
    FakeLLMFailureCode,
    FakeLLMProvider,
    FakeLLMProviderError,
    ScriptedFailure,
    ScriptedSuccess,
)

__all__ = [
    "FakeCallRecord",
    "FakeClock",
    "FakeLLMFailureCode",
    "FakeLLMProvider",
    "FakeLLMProviderError",
    "ScriptedFailure",
    "ScriptedSuccess",
]
