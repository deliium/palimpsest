"""Type-check fixtures for generic LLMProvider result inference.

Positive cases must type-check. Negative cases live under invalid/.
"""

from __future__ import annotations

from llm.contracts import LLMProvider
from llm.models import (
    FinishReason,
    LLMMessage,
    LLMRequest,
    LLMRequestContext,
    LLMResult,
    LLMResultMetadata,
    MessageRole,
    StructuredOutput,
)


class DecisionOutput(StructuredOutput):
    """Example structured decision payload. Structure only — not a command."""

    kind: str


async def _generate_decision(provider: LLMProvider) -> DecisionOutput:
    request = LLMRequest.create(
        messages=(LLMMessage(role=MessageRole.USER, content="choose"),),
        response_model=DecisionOutput,
        context=LLMRequestContext(
            run_id="run-1",
            agent_id="agent-1",
            tick=0,
            llm_request_id="req-1",
        ),
    )
    result: LLMResult[DecisionOutput] = await provider.generate(request)
    output: DecisionOutput = result.output
    return output


def _metadata() -> LLMResultMetadata:
    return LLMResultMetadata(
        provider_name="stub",
        model_name="scripted",
        finish_reason=FinishReason.STOP,
    )
