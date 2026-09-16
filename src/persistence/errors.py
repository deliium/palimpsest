"""Stable persistence-adapter error types.

Construction is silent. Messages must not include DSNs, SQL parameters,
canonical blobs, JSON payloads, snapshots, configuration values, or seeds.
"""

from __future__ import annotations

__all__ = [
    "PersistenceAdapterError",
    "PersistenceConflictError",
    "PersistenceCorruptionError",
    "PersistenceNotFoundError",
]


class PersistenceAdapterError(Exception):
    """Base adapter failure with a stable operation/error name."""

    def __init__(self, code: str, *, operation: str | None = None) -> None:
        self.code = code
        self.operation = operation
        if operation is None:
            super().__init__(code)
        else:
            super().__init__(f"{operation}:{code}")


class PersistenceConflictError(PersistenceAdapterError):
    """Divergent idempotency key, stale predecessor, or concurrent writer."""


class PersistenceCorruptionError(PersistenceAdapterError):
    """Hash/version/continuity failure detected by the adapter."""


class PersistenceNotFoundError(PersistenceAdapterError):
    """Requested run, tick, snapshot, or experiment does not exist."""
