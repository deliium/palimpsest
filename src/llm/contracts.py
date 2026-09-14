"""Provider-neutral LLM ports. Implementations return untrusted response data only."""

from __future__ import annotations

from typing import Protocol

from llm.models import LLMResponse


class LLMClient(Protocol):
    def complete(self, prompt: str) -> LLMResponse:
        """Return a provider-valid response. The text is untrusted input."""
        ...
