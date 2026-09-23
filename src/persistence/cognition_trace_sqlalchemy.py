"""SQLAlchemy adapter for durable cognition execution traces.

Implements ``CognitionTraceRepository``. Stores codec bytes only — never
ad-hoc JSON. Never logs stage summaries, payloads, SQL, or DSNs.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from agents.models import AgentId
from infrastructure.database import session_scope
from infrastructure.logging import get_logger
from persistence.errors import PersistenceAdapterError, PersistenceConflictError
from persistence.orm import CognitionTraceInvocationOrm
from simulation.cognition_trace import (
    CognitionTraceConflictError,
    CognitionTraceInvocation,
    CognitionTracePage,
)
from simulation.cognition_trace_serialization import (
    decode_cognition_trace_invocation,
    encode_cognition_trace_invocation,
)
from simulation.models import RunId

_LOGGER = get_logger("persistence.cognition_trace_sqlalchemy")

__all__ = [
    "SqlAlchemyCognitionTraceRepository",
    "create_cognition_trace_repository",
]


def create_cognition_trace_repository(
    session_factory: async_sessionmaker[AsyncSession],
) -> SqlAlchemyCognitionTraceRepository:
    return SqlAlchemyCognitionTraceRepository(session_factory)


class SqlAlchemyCognitionTraceRepository:
    """PostgreSQL append-only cognition trace store."""

    __slots__ = ("_session_factory",)

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def append_invocation(self, invocation: CognitionTraceInvocation) -> None:
        if type(invocation) is not CognitionTraceInvocation:
            raise TypeError("append_invocation requires CognitionTraceInvocation")
        payload = encode_cognition_trace_invocation(invocation)
        fields = {
            "operation": "cognition_trace_append",
            "run_id": invocation.run_id.value,
            "agent_id": invocation.agent_id.value,
            "tick": invocation.tick,
            "invocation_id": invocation.invocation_id,
            "hash_prefix": invocation.content_hash[:12],
            "version": invocation.schema_version,
        }
        _LOGGER.debug("cognition_trace_append_started", **fields)
        try:
            async with session_scope(self._session_factory) as session:
                key = (
                    invocation.run_id.value,
                    invocation.agent_id.value,
                    invocation.tick,
                    invocation.invocation_id,
                )
                existing = await session.get(CognitionTraceInvocationOrm, key)
                if existing is not None:
                    if existing.content_hash == invocation.content_hash:
                        _LOGGER.warning("cognition_trace_identical_retry", **fields)
                        return
                    _LOGGER.error(
                        "cognition_trace_divergent_conflict",
                        **fields,
                        reason_code="divergent_content_hash",
                    )
                    raise PersistenceConflictError(
                        "divergent_content_hash",
                        operation="cognition_trace_append",
                    )
                session.add(
                    CognitionTraceInvocationOrm(
                        run_id=invocation.run_id.value,
                        agent_id=invocation.agent_id.value,
                        tick=invocation.tick,
                        invocation_id=invocation.invocation_id,
                        schema_version=invocation.schema_version,
                        content_hash=invocation.content_hash,
                        payload=payload,
                        command_kind=invocation.command_kind,
                        final_confidence=invocation.final_confidence,
                    )
                )
                await session.commit()
        except PersistenceAdapterError:
            raise
        except CognitionTraceConflictError as exc:
            raise PersistenceConflictError(
                exc.code, operation="cognition_trace_append"
            ) from exc
        except IntegrityError as exc:
            _LOGGER.error(
                "cognition_trace_integrity_conflict",
                **fields,
                reason_code="integrity_conflict",
            )
            raise PersistenceConflictError(
                "integrity_conflict", operation="cognition_trace_append"
            ) from exc
        _LOGGER.info("cognition_trace_committed", **fields)

    async def get_invocation(
        self,
        *,
        run_id: RunId,
        agent_id: AgentId,
        tick: int,
        invocation_id: str,
    ) -> CognitionTraceInvocation | None:
        async with session_scope(self._session_factory) as session:
            row = await session.get(
                CognitionTraceInvocationOrm,
                (run_id.value, agent_id.value, tick, invocation_id),
            )
            if row is None:
                return None
            return decode_cognition_trace_invocation(bytes(row.payload))

    async def list_invocations(
        self,
        *,
        run_id: RunId,
        agent_id: AgentId | None = None,
        tick_min: int | None = None,
        tick_max: int | None = None,
        after_cursor: str | None = None,
        limit: int = 50,
    ) -> CognitionTracePage:
        if limit < 1:
            raise ValueError("limit must be >= 1")
        async with session_scope(self._session_factory) as session:
            stmt = select(CognitionTraceInvocationOrm).where(
                CognitionTraceInvocationOrm.run_id == run_id.value
            )
            if agent_id is not None:
                stmt = stmt.where(
                    CognitionTraceInvocationOrm.agent_id == agent_id.value
                )
            if tick_min is not None:
                stmt = stmt.where(CognitionTraceInvocationOrm.tick >= tick_min)
            if tick_max is not None:
                stmt = stmt.where(CognitionTraceInvocationOrm.tick <= tick_max)
            stmt = stmt.order_by(
                CognitionTraceInvocationOrm.tick,
                CognitionTraceInvocationOrm.agent_id,
                CognitionTraceInvocationOrm.invocation_id,
            )
            rows = (await session.execute(stmt)).scalars().all()
            items: list[CognitionTraceInvocation] = []
            for row in rows:
                cursor = (
                    f"{row.tick:016d}:{row.agent_id}:{row.invocation_id}"
                )
                if after_cursor is not None and cursor <= after_cursor:
                    continue
                items.append(decode_cognition_trace_invocation(bytes(row.payload)))
                if len(items) > limit:
                    break
            page_items = tuple(items[:limit])
            next_cursor = None
            if len(items) > limit:
                last = page_items[-1]
                next_cursor = (
                    f"{last.tick:016d}:{last.agent_id.value}:{last.invocation_id}"
                )
            return CognitionTracePage(items=page_items, next_cursor=next_cursor)
