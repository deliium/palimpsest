"""Standalone LLM provider factory (no infrastructure / no network)."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from llm.errors import LLMError, LLMErrorCode
from llm.factory import (
    DisabledLLMProvider,
    ProviderAdapterKind,
    ProviderFactoryConfig,
    create_llm_provider,
)
from llm.models import (
    LLMMessage,
    LLMRequest,
    LLMRequestContext,
    MessageRole,
    StructuredOutput,
    StructuredOutputMode,
)
from llm.providers.openai_compatible import OpenAICompatibleProvider

pytestmark = pytest.mark.unit


class _Decision(StructuredOutput):
    kind: str


class _Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def monotonic(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.now += seconds


def _request() -> LLMRequest[_Decision]:
    return LLMRequest.create(
        messages=(LLMMessage(role=MessageRole.USER, content="decide"),),
        response_model=_Decision,
        context=LLMRequestContext(
            run_id="run-1",
            agent_id="agent-1",
            tick=0,
            llm_request_id="req-1",
        ),
    )


def test_factory_defaults_to_disabled_provider() -> None:
    clock = _Clock()
    provider = create_llm_provider(
        ProviderFactoryConfig(),
        sleep=clock.sleep,
        monotonic=clock.monotonic,
    )
    assert isinstance(provider, DisabledLLMProvider)


@pytest.mark.asyncio
async def test_disabled_provider_fails_with_configuration_error() -> None:
    provider = DisabledLLMProvider()
    with pytest.raises(LLMError) as exc_info:
        await provider.generate(_request())
    assert exc_info.value.code is LLMErrorCode.CONFIGURATION
    assert exc_info.value.retryable is False
    await provider.close()


def test_factory_builds_openai_compatible_without_network(
    caplog: pytest.LogCaptureFixture,
) -> None:
    clock = _Clock()
    config = ProviderFactoryConfig(
        adapter_kind=ProviderAdapterKind.OPENAI_COMPATIBLE,
        model="llama3.2",
        base_url="http://127.0.0.1:11434/v1",
        api_key="sk-test-secret",
        mode=StructuredOutputMode.JSON_OBJECT,
        temperature=0.0,
        max_attempts=2,
        send_correlation_header=True,
    )
    with caplog.at_level(logging.DEBUG, logger="llm.factory"):
        provider = create_llm_provider(
            config,
            sleep=clock.sleep,
            monotonic=clock.monotonic,
        )
    assert isinstance(provider, OpenAICompatibleProvider)
    assert provider.closed is False
    assert "sk-test-secret" not in caplog.text
    assert "127.0.0.1" not in caplog.text
    assert "11434" not in caplog.text
    assert "adapter_kind=openai_compatible" in caplog.text
    assert "model=llama3.2" in caplog.text
    assert "has_api_key=True" in caplog.text
    assert "http://127.0.0.1" not in repr(config)
    assert "sk-test-secret" not in repr(config)


def test_factory_rejects_enabled_config_missing_required_fields() -> None:
    clock = _Clock()
    with pytest.raises(LLMError) as exc_info:
        create_llm_provider(
            ProviderFactoryConfig(
                adapter_kind=ProviderAdapterKind.OPENAI_COMPATIBLE,
                model="llama3.2",
            ),
            sleep=clock.sleep,
            monotonic=clock.monotonic,
        )
    assert exc_info.value.code is LLMErrorCode.CONFIGURATION


def test_factory_does_not_import_infrastructure() -> None:
    import ast

    import llm.factory as factory_module

    assert factory_module.__file__ is not None
    source = Path(factory_module.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.add(node.module.split(".", 1)[0])
    assert "infrastructure" not in imported
    assert "os" not in imported
