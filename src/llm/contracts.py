"""Provider-neutral LLM ports.

Implementations return structurally validated, semantically untrusted output.
"""

from __future__ import annotations

from typing import Protocol

from llm.models import LLMRequest, LLMResult, StructuredOutput


class LLMProvider(Protocol):
    """Async provider boundary for structured generation.

    ``generate`` returns only a :class:`~llm.models.LLMResult` whose ``output``
    is a project-owned :class:`~llm.models.StructuredOutput` instance. That
    value is structurally validated and remains non-authoritative: it is not an
    agent command, action request, or world mutation.
    """

    async def generate[T: StructuredOutput](
        self, request: LLMRequest[T]
    ) -> LLMResult[T]:
        """Generate and locally validate structured output for ``request``."""
        ...
