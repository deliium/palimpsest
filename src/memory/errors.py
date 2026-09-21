"""Stable memory-service error codes (metadata-only)."""

from __future__ import annotations

from enum import StrEnum

__all__ = [
    "BeliefServiceError",
    "BeliefServiceErrorCode",
    "MemoryServiceError",
    "MemoryServiceErrorCode",
]


class MemoryServiceErrorCode(StrEnum):
    """Stable ERROR/WARN reason codes for the memory application boundary."""

    CONFLICT = "conflict"
    OWNERSHIP = "ownership"
    NOT_FOUND = "not_found"
    INVALID_BATCH = "invalid_batch"
    INVALID_REQUEST = "invalid_request"


class MemoryServiceError(ValueError):
    """Fail-closed service error with a stable reason code only."""

    def __init__(self, code: MemoryServiceErrorCode) -> None:
        self.code = code
        super().__init__(code.value)


class BeliefServiceErrorCode(StrEnum):
    """Stable ERROR/WARN reason codes for semantic belief revisions."""

    CONFLICT = "conflict"
    OWNERSHIP = "ownership"
    NOT_FOUND = "not_found"
    INVALID_REQUEST = "invalid_request"
    CHRONOLOGY = "chronology"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"


class BeliefServiceError(ValueError):
    """Fail-closed belief-service error with a stable reason code only."""

    def __init__(self, code: BeliefServiceErrorCode) -> None:
        self.code = code
        super().__init__(code.value)
