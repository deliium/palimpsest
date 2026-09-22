"""Experiment-specific persistence ports (framework-free).

Concrete SQLAlchemy adapters live in ``persistence`` and may import these
contracts. The ``experiments`` package never imports SQLAlchemy.
"""

from __future__ import annotations

from typing import Protocol


class ExperimentRecordRepository(Protocol):
    """Append-only experiment definition/result record port."""

    async def append_definition(self, *, experiment_id: str, payload_hash: str) -> None:
        ...

    async def append_result(self, *, run_id: str, payload_hash: str) -> None: ...
