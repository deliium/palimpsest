"""Stable memory-service error codes (metadata-only)."""

from __future__ import annotations

from enum import StrEnum

__all__ = [
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
