"""Fail-closed subjective clone for forks made before any owner state exists.

Full durable owner-state cloning is intentionally unsupported by the V3-44
benchmark plan. This adapter only admits a fork whose prefix contains no
persisted memory, belief, relationship, or goal rows for the parent run. It
returns a zero-count receipt; any non-empty prefix fails closed with
``subjective_clone_incomplete`` instead of fabricating owner state.
"""

from __future__ import annotations

from typing import Final

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from simulation.branch_service import SubjectiveCloneResult
from simulation.branching import BranchError
from simulation.models import RunId

_STORE_QUERIES: Final[tuple[str, ...]] = (
    "SELECT 1 FROM memory_traces WHERE run_id = :run_id "
    "AND created_tick <= :fork_tick AND source_tick <= :fork_tick LIMIT 1",
    "SELECT 1 FROM semantic_beliefs WHERE run_id = :run_id "
    "AND updated_tick <= :fork_tick LIMIT 1",
    "SELECT 1 FROM directed_relationships WHERE run_id = :run_id LIMIT 1",
    "SELECT 1 FROM goal_revisions WHERE run_id = :run_id "
    "AND tick <= :fork_tick LIMIT 1",
)


class EmptyBoundarySubjectiveClone:
    """Clone port that permits only owner-state-empty fork boundaries."""

    __slots__ = ("_session_factory",)

    def __init__(
        self, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        self._session_factory = session_factory

    async def clone_as_of(
        self,
        *,
        parent_run_id: RunId,
        child_run_id: RunId,
        fork_tick: int,
    ) -> SubjectiveCloneResult:
        if type(parent_run_id) is not RunId or type(child_run_id) is not RunId:
            raise TypeError("clone_as_of requires RunId")
        async with self._session_factory() as session:
            for query in _STORE_QUERIES:
                present = await session.scalar(
                    text(query),
                    {"run_id": parent_run_id.value, "fork_tick": fork_tick},
                )
                if present is not None:
                    raise BranchError("subjective_clone_incomplete")
        return SubjectiveCloneResult(
            parent_run_id=parent_run_id,
            child_run_id=child_run_id,
            fork_tick=fork_tick,
            owner_count=0,
            memory_rows=0,
            belief_rows=0,
            relationship_rows=0,
            goal_rows=0,
        )


__all__ = ["EmptyBoundarySubjectiveClone"]
