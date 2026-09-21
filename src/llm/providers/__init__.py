"""Concrete LLM provider adapters (OpenAI-compatible V1).

Codec helpers live in :mod:`llm.providers.openai_compatible_codec` and remain
provider-private; they are not re-exported from :mod:`llm`.
"""

from llm.providers.openai_compatible import (
    CORRELATION_HEADER_NAME,
    OpenAICompatibleProvider,
)

__all__ = [
    "CORRELATION_HEADER_NAME",
    "OpenAICompatibleProvider",
]
