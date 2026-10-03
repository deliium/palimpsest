"""SQLAlchemy adapter for research branch lineage (control plane).

Implements ``BranchLineageRepository``. Outside authoritative replay fold.
Never logs intervention payloads, belief text, or DSNs — ids/counts only.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from infrastructure.database import session_scope
from infrastructure.logging import get_logger
from persistence.errors import PersistenceAdapterError, PersistenceConflictError
from persistence.orm import SimulationBranchOrm
from simulation.branching import (
    BranchLineage,
    decode_branch_lineage,
    encode_branch_lineage,
)
from simulation.clock import require_exact_nonneg_int
from simulation.models import RunId

_LOGGER = get_logger("persistence.branch_lineage_sqlalchemy")

__all__ = [
    "SqlAlchemyBranchLineageRepository",
    "create_branch_lineage_repository",
]


def create_branch_lineage_repository(
    session_factory: async_sessionmaker[AsyncSession],
) -> SqlAlchemyBranchLineageRepository:
    return SqlAlchemyBranchLineageRepository(session_factory)


def _row_to_lineage(row: SimulationBranchOrm) -> BranchLineage:
    return decode_branch_lineage(
        {
            "child_run_id": row.child_run_id,
            "parent_run_id": row.parent_run_id,
            "fork_tick": row.fork_tick,
            "intervention_kind": row.intervention_kind,
            "intervention_fingerprint": row.intervention_fingerprint,
            "intervention_canonical": dict(row.intervention_canonical),
            "branch_id": row.branch_id,
            "created_as_of_parent_head": row.created_as_of_parent_head,
        }
    )


class SqlAlchemyBranchLineageRepository:
    """PostgreSQL control-plane store for research fork genealogy."""

    __slots__ = ("_session_factory",)

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def put_lineage(self, lineage: BranchLineage) -> BranchLineage:
        if type(lineage) is not BranchLineage:
            raise TypeError("put_lineage requires BranchLineage")
        document = encode_branch_lineage(lineage)
        fields = {
            "operation": "branch_lineage_put",
            "child_run_id": lineage.child_run_id.value,
            "parent_run_id": lineage.parent_run_id.value,
            "fork_tick": lineage.fork_tick,
            "branch_id": lineage.branch_id,
            "kind": lineage.intervention_kind.value,
            "fingerprint_prefix": lineage.intervention_fingerprint[:12],
        }
        _LOGGER.debug("branch_lineage_put_started", **fields)
        try:
            async with session_scope(self._session_factory) as session:
                existing = await session.get(
                    SimulationBranchOrm, lineage.child_run_id.value
                )
                if existing is not None:
                    decoded = _row_to_lineage(existing)
                    if (
                        decoded.intervention_fingerprint
                        == lineage.intervention_fingerprint
                        and decoded.parent_run_id == lineage.parent_run_id
                        and decoded.fork_tick == lineage.fork_tick
                    ):
                        _LOGGER.debug("branch_lineage_idempotent_hit", **fields)
                        return decoded
                    _LOGGER.error("branch_lineage_identity_conflict", **fields)
                    raise PersistenceConflictError(
                        "branch_identity_conflict",
                        operation="put_lineage",
                    )
                session.add(
                    SimulationBranchOrm(
                        child_run_id=document["child_run_id"],
                        parent_run_id=document["parent_run_id"],
                        fork_tick=document["fork_tick"],
                        intervention_kind=document["intervention_kind"],
                        intervention_fingerprint=document["intervention_fingerprint"],
                        intervention_canonical=document["intervention_canonical"],
                        branch_id=document["branch_id"],
                        created_as_of_parent_head=document[
                            "created_as_of_parent_head"
                        ],
                    )
                )
        except PersistenceConflictError:
            raise
        except IntegrityError as exc:
            _LOGGER.error("branch_lineage_integrity_conflict", **fields)
            raise PersistenceConflictError(
                "branch_identity_conflict",
                operation="put_lineage",
            ) from exc
        except Exception as exc:
            _LOGGER.error("branch_lineage_put_failed", **fields)
            raise PersistenceAdapterError(
                "branch_lineage_put_failed",
                operation="put_lineage",
            ) from exc
        _LOGGER.debug("branch_lineage_put_complete", **fields)
        return lineage

    async def get_lineage(self, *, child_run_id: RunId) -> BranchLineage | None:
        if type(child_run_id) is not RunId:
            raise TypeError("get_lineage requires RunId")
        async with session_scope(self._session_factory) as session:
            row = await session.get(SimulationBranchOrm, child_run_id.value)
            if row is None:
                _LOGGER.debug(
                    "branch_lineage_get_miss child_run_id=%s",
                    child_run_id.value,
                )
                return None
            lineage = _row_to_lineage(row)
            _LOGGER.debug(
                "branch_lineage_get_hit child_run_id=%s parent_run_id=%s",
                lineage.child_run_id.value,
                lineage.parent_run_id.value,
            )
            return lineage

    async def list_children(
        self,
        *,
        parent_run_id: RunId,
        after_child_run_id: str | None = None,
        limit: int = 100,
    ) -> tuple[BranchLineage, ...]:
        if type(parent_run_id) is not RunId:
            raise TypeError("list_children requires RunId")
        page_limit = require_exact_nonneg_int("limit", limit)
        if page_limit < 1:
            raise ValueError("limit must be >= 1")
        async with session_scope(self._session_factory) as session:
            stmt = (
                select(SimulationBranchOrm)
                .where(SimulationBranchOrm.parent_run_id == parent_run_id.value)
                .order_by(SimulationBranchOrm.child_run_id.asc())
                .limit(page_limit)
            )
            if after_child_run_id is not None:
                stmt = stmt.where(
                    SimulationBranchOrm.child_run_id > after_child_run_id
                )
            rows = (await session.execute(stmt)).scalars().all()
            result = tuple(_row_to_lineage(row) for row in rows)
            _LOGGER.debug(
                "branch_lineage_list parent_run_id=%s count=%s",
                parent_run_id.value,
                len(result),
            )
            return result
