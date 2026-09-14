"""Provider-valid but untrusted LLM response data."""

from __future__ import annotations

from dataclasses import dataclass


def _require_non_empty(name: str, value: str) -> str:
    if not value:
        raise ValueError(f"{name} must be a non-empty string")
    return value


@dataclass(frozen=True, slots=True)
class LLMResponse:
    """Validated transport payload. Not an action request and not world-trusted."""

    provider: str
    model: str
    text: str
    token_count: int | None = None

    def __post_init__(self) -> None:
        _require_non_empty("LLMResponse.provider", self.provider)
        _require_non_empty("LLMResponse.model", self.model)
        if self.token_count is not None and (
            isinstance(self.token_count, bool) or self.token_count < 0
        ):
            raise ValueError("LLMResponse.token_count must be a non-negative integer")
