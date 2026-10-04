"""Unit tests for SQLAlchemy memory candidate-cap construction."""

from __future__ import annotations

import pytest

from agents.models import AgentId
from memory.models import (
    MemoryRunId,
    MemoryScope,
    MemoryScoreWeights,
    MemoryScoringPolicy,
)
from persistence.errors import PersistenceAdapterError
from persistence.memory_sqlalchemy import create_sqlalchemy_memory_service


def _policy() -> MemoryScoringPolicy:
    return MemoryScoringPolicy(
        policy_id="structured",
        version="1",
        weights=MemoryScoreWeights(recency=1.0),
    )


def test_create_memory_service_rejects_invalid_max_candidates() -> None:
    scope = MemoryScope(run_id=MemoryRunId("run-1"), owner_id=AgentId("agent-1"))
    policy = _policy()
    with pytest.raises(PersistenceAdapterError) as exc_info:
        create_sqlalchemy_memory_service(
            scope=scope,
            session_factory=object(),  # type: ignore[arg-type]
            scoring_policy=policy,
            max_candidates=0,
        )
    assert exc_info.value.code == "invalid_max_candidates"
    with pytest.raises(PersistenceAdapterError):
        create_sqlalchemy_memory_service(
            scope=scope,
            session_factory=object(),  # type: ignore[arg-type]
            scoring_policy=policy,
            max_candidates=True,  # type: ignore[arg-type]
        )
    with pytest.raises(PersistenceAdapterError):
        create_sqlalchemy_memory_service(
            scope=scope,
            session_factory=object(),  # type: ignore[arg-type]
            scoring_policy=policy,
            max_candidates=100_001,
        )
