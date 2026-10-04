"""Run-scoped cognitive execution trace ports and DTOs.

Scientific observability only. Never imported by ``WorldEngine``, admission,
perception, or live cognition inputs. Trace data is **not** part of
``EvidenceManifest`` / objective high-water / authoritative replay.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final, Protocol

from agents.cognition.trace import (
    CognitionTraceStageSummary,
    project_cognition_trace_stages,
    stage_summaries_content_hash,
)
from agents.models import AgentId
from simulation.models import RunId
from simulation.runner_models import CognitionTraceSpec
from world.identifiers import require_exact_nonneg_int, require_stable_id

_LOG: Final[logging.Logger] = logging.getLogger("simulation.cognition_trace")

__all__ = [
    "COGNITION_TRACE_SCHEMA_VERSION",
    "AgentId",
    "CognitionTraceConflictError",
    "CognitionTraceInvocation",
    "CognitionTracePage",
    "CognitionTraceRepository",
    "CognitionTraceStageRecord",
    "InMemoryCognitionTraceRepository",
    "NullCognitionTraceRepository",
    "SoftCapCognitionTraceRepository",
    "build_cognition_trace_invocation",
    "export_cognition_trace_invocations",
    "maybe_append_cognition_trace",
    "select_cognition_trace_repository",
    "wrap_cognition_trace_soft_caps",
]

COGNITION_TRACE_SCHEMA_VERSION: Final[str] = "cognition-trace-v1"


class CognitionTraceConflictError(ValueError):
    """Divergent content_hash for an identical invocation key."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class CognitionTraceStageRecord:
    """Run-scoped wrapper around one cognition stage summary."""

    run_id: RunId
    agent_id: AgentId
    tick: int
    invocation_id: str
    ordinal: int
    summary: CognitionTraceStageSummary

    def __post_init__(self) -> None:
        if type(self.run_id) is not RunId:
            raise TypeError("CognitionTraceStageRecord.run_id must be RunId")
        if type(self.agent_id) is not AgentId:
            raise TypeError("CognitionTraceStageRecord.agent_id must be AgentId")
        object.__setattr__(
            self,
            "tick",
            require_exact_nonneg_int("CognitionTraceStageRecord.tick", self.tick),
        )
        object.__setattr__(
            self,
            "invocation_id",
            require_stable_id(
                "CognitionTraceStageRecord.invocation_id", self.invocation_id
            ),
        )
        object.__setattr__(
            self,
            "ordinal",
            require_exact_nonneg_int(
                "CognitionTraceStageRecord.ordinal", self.ordinal
            ),
        )
        if type(self.summary) is not CognitionTraceStageSummary:
            raise TypeError(
                "CognitionTraceStageRecord.summary must be CognitionTraceStageSummary"
            )
        if self.summary.ordinal != self.ordinal:
            raise ValueError("stage record ordinal must match summary.ordinal")

    def __repr__(self) -> str:
        return (
            f"CognitionTraceStageRecord(run_id={self.run_id.value!r}, "
            f"agent_id={self.agent_id.value!r}, tick={self.tick}, "
            f"ordinal={self.ordinal}, stage_kind={self.summary.stage_kind.value!r})"
        )


@dataclass(frozen=True, slots=True)
class CognitionTraceInvocation:
    """One cognition bind's ordered stage envelope (run-scoped)."""

    run_id: RunId
    agent_id: AgentId
    tick: int
    invocation_id: str
    stages: tuple[CognitionTraceStageRecord, ...]
    command_kind: str | None
    final_confidence: float | None
    content_hash: str
    schema_version: str = COGNITION_TRACE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if type(self.run_id) is not RunId:
            raise TypeError("CognitionTraceInvocation.run_id must be RunId")
        if type(self.agent_id) is not AgentId:
            raise TypeError("CognitionTraceInvocation.agent_id must be AgentId")
        object.__setattr__(
            self,
            "tick",
            require_exact_nonneg_int("CognitionTraceInvocation.tick", self.tick),
        )
        object.__setattr__(
            self,
            "invocation_id",
            require_stable_id(
                "CognitionTraceInvocation.invocation_id", self.invocation_id
            ),
        )
        if not isinstance(self.stages, tuple):
            raise TypeError("CognitionTraceInvocation.stages must be a tuple")
        for stage in self.stages:
            if type(stage) is not CognitionTraceStageRecord:
                raise TypeError(
                    "stages entries must be CognitionTraceStageRecord"
                )
            if stage.run_id != self.run_id:
                raise ValueError("stage run_id mismatch")
            if stage.agent_id != self.agent_id:
                raise ValueError("stage agent_id mismatch")
            if stage.tick != self.tick:
                raise ValueError("stage tick mismatch")
            if stage.invocation_id != self.invocation_id:
                raise ValueError("stage invocation_id mismatch")
        if self.command_kind is not None:
            object.__setattr__(
                self,
                "command_kind",
                require_stable_id(
                    "CognitionTraceInvocation.command_kind", self.command_kind
                ),
            )
        if self.final_confidence is not None:
            if isinstance(self.final_confidence, bool) or not isinstance(
                self.final_confidence, (int, float)
            ):
                raise TypeError("final_confidence must be float or None")
            number = float(self.final_confidence)
            if number < 0.0 or number > 1.0:
                raise ValueError("final_confidence must be in [0.0, 1.0]")
            object.__setattr__(self, "final_confidence", number)
        object.__setattr__(
            self,
            "content_hash",
            require_stable_id(
                "CognitionTraceInvocation.content_hash", self.content_hash
            ),
        )
        object.__setattr__(
            self,
            "schema_version",
            require_stable_id(
                "CognitionTraceInvocation.schema_version", self.schema_version
            ),
        )
        if self.schema_version != COGNITION_TRACE_SCHEMA_VERSION:
            raise ValueError(
                f"schema_version must be {COGNITION_TRACE_SCHEMA_VERSION!r}"
            )

    def __repr__(self) -> str:
        return (
            f"CognitionTraceInvocation(run_id={self.run_id.value!r}, "
            f"agent_id={self.agent_id.value!r}, tick={self.tick}, "
            f"invocation_id={self.invocation_id!r}, "
            f"stage_count={len(self.stages)}, "
            f"content_hash={self.content_hash[:12]!r})"
        )


@dataclass(frozen=True, slots=True)
class CognitionTracePage:
    """Keyset page of invocations ordered by (tick, agent_id, invocation_id)."""

    items: tuple[CognitionTraceInvocation, ...]
    next_cursor: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.items, tuple):
            raise TypeError("CognitionTracePage.items must be a tuple")
        for item in self.items:
            if type(item) is not CognitionTraceInvocation:
                raise TypeError("page items must be CognitionTraceInvocation")
        if self.next_cursor is not None:
            object.__setattr__(
                self,
                "next_cursor",
                require_stable_id("CognitionTracePage.next_cursor", self.next_cursor),
            )


def build_cognition_trace_invocation(
    *,
    run_id: RunId,
    agent_id: AgentId,
    tick: int,
    invocation_id: str,
    stage_summaries: Sequence[CognitionTraceStageSummary],
    command_kind: str | None = None,
    final_confidence: float | None = None,
    content_hash: str | None = None,
) -> CognitionTraceInvocation:
    """Attach ``run_id`` to cognition stage summaries and build an invocation."""
    if type(run_id) is not RunId:
        raise TypeError("run_id must be RunId")
    if type(agent_id) is not AgentId:
        raise TypeError("agent_id must be AgentId")
    summaries = tuple(stage_summaries)
    for summary in summaries:
        if type(summary) is not CognitionTraceStageSummary:
            raise TypeError(
                "stage_summaries entries must be CognitionTraceStageSummary"
            )
    stages = tuple(
        CognitionTraceStageRecord(
            run_id=run_id,
            agent_id=agent_id,
            tick=tick,
            invocation_id=invocation_id,
            ordinal=summary.ordinal,
            summary=summary,
        )
        for summary in summaries
    )
    digest = (
        content_hash
        if content_hash is not None
        else stage_summaries_content_hash(summaries)
    )
    invocation = CognitionTraceInvocation(
        run_id=run_id,
        agent_id=agent_id,
        tick=tick,
        invocation_id=invocation_id,
        stages=stages,
        command_kind=command_kind,
        final_confidence=final_confidence,
        content_hash=digest,
    )
    _LOG.debug(
        "cognition_trace_invocation_built",
        extra={
            "run_id": run_id.value,
            "agent_id": agent_id.value,
            "tick": tick,
            "invocation_id": invocation_id,
            "stage_count": len(stages),
            "hash_prefix": digest[:12],
        },
    )
    return invocation


class CognitionTraceRepository(Protocol):
    """Append-only cognition trace store (debugger/experiment read surface)."""

    async def append_invocation(self, invocation: CognitionTraceInvocation) -> None:
        """Append one invocation. Identical hash is idempotent; divergent raises."""

    async def get_invocation(
        self,
        *,
        run_id: RunId,
        agent_id: AgentId,
        tick: int,
        invocation_id: str,
    ) -> CognitionTraceInvocation | None: ...

    async def list_invocations(
        self,
        *,
        run_id: RunId,
        agent_id: AgentId | None = None,
        tick_min: int | None = None,
        tick_max: int | None = None,
        after_cursor: str | None = None,
        limit: int = 50,
    ) -> CognitionTracePage: ...


class InMemoryCognitionTraceRepository:
    """Copy-on-write in-memory repository with identical-retry semantics."""

    __slots__ = ("_items",)

    def __init__(self) -> None:
        self._items: dict[
            tuple[str, str, int, str], CognitionTraceInvocation
        ] = {}

    async def append_invocation(self, invocation: CognitionTraceInvocation) -> None:
        if type(invocation) is not CognitionTraceInvocation:
            raise TypeError("append_invocation requires CognitionTraceInvocation")
        key = (
            invocation.run_id.value,
            invocation.agent_id.value,
            invocation.tick,
            invocation.invocation_id,
        )
        _LOG.debug(
            "cognition_trace_append_started",
            extra={
                "run_id": invocation.run_id.value,
                "agent_id": invocation.agent_id.value,
                "tick": invocation.tick,
                "invocation_id": invocation.invocation_id,
                "hash_prefix": invocation.content_hash[:12],
            },
        )
        existing = self._items.get(key)
        if existing is not None:
            if existing.content_hash == invocation.content_hash:
                _LOG.warning(
                    "cognition_trace_identical_retry",
                    extra={
                        "run_id": invocation.run_id.value,
                        "agent_id": invocation.agent_id.value,
                        "tick": invocation.tick,
                        "invocation_id": invocation.invocation_id,
                        "hash_prefix": invocation.content_hash[:12],
                    },
                )
                return
            _LOG.error(
                "cognition_trace_divergent_conflict",
                extra={
                    "run_id": invocation.run_id.value,
                    "agent_id": invocation.agent_id.value,
                    "tick": invocation.tick,
                    "invocation_id": invocation.invocation_id,
                    "reason_code": "divergent_content_hash",
                },
            )
            raise CognitionTraceConflictError(
                "divergent_content_hash",
                "cognition trace invocation content_hash conflict",
            )
        self._items[key] = invocation
        _LOG.debug(
            "cognition_trace_append_complete",
            extra={
                "run_id": invocation.run_id.value,
                "agent_id": invocation.agent_id.value,
                "tick": invocation.tick,
                "invocation_id": invocation.invocation_id,
                "hash_prefix": invocation.content_hash[:12],
            },
        )

    async def get_invocation(
        self,
        *,
        run_id: RunId,
        agent_id: AgentId,
        tick: int,
        invocation_id: str,
    ) -> CognitionTraceInvocation | None:
        return self._items.get(
            (run_id.value, agent_id.value, tick, invocation_id)
        )

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
        limit = require_exact_nonneg_int("limit", limit)
        if limit < 1:
            raise ValueError("limit must be >= 1")
        items = [
            item
            for item in self._items.values()
            if item.run_id == run_id
            and (agent_id is None or item.agent_id == agent_id)
            and (tick_min is None or item.tick >= tick_min)
            and (tick_max is None or item.tick <= tick_max)
        ]
        items.sort(
            key=lambda item: (
                item.tick,
                item.agent_id.value,
                item.invocation_id,
            )
        )
        if after_cursor is not None:
            cursor = after_cursor
            items = [
                item
                for item in items
                if _cursor_for(item) > cursor
            ]
        page_items = items[:limit]
        next_cursor = None
        if len(items) > limit:
            next_cursor = _cursor_for(page_items[-1])
        return CognitionTracePage(items=tuple(page_items), next_cursor=next_cursor)


class NullCognitionTraceRepository:
    """No-op repository: zero durable state; appends/queries succeed as empty."""

    async def append_invocation(self, invocation: CognitionTraceInvocation) -> None:
        if type(invocation) is not CognitionTraceInvocation:
            raise TypeError("append_invocation requires CognitionTraceInvocation")
        # Silent at INFO+; optional DEBUG only for verbose sink tests.
        _LOG.debug(
            "cognition_trace_null_append",
            extra={
                "run_id": invocation.run_id.value,
                "agent_id": invocation.agent_id.value,
                "tick": invocation.tick,
                "invocation_id": invocation.invocation_id,
            },
        )

    async def get_invocation(
        self,
        *,
        run_id: RunId,
        agent_id: AgentId,
        tick: int,
        invocation_id: str,
    ) -> CognitionTraceInvocation | None:
        return None

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
        return CognitionTracePage(items=())


def select_cognition_trace_repository(
    *,
    enabled: bool,
    durable: CognitionTraceRepository | None = None,
    in_memory: CognitionTraceRepository | None = None,
) -> CognitionTraceRepository:
    """Composition helper: Null when disabled; prefer durable else in-memory."""
    if not enabled:
        return NullCognitionTraceRepository()
    if durable is not None:
        return durable
    if in_memory is not None:
        return in_memory
    return InMemoryCognitionTraceRepository()


class SoftCapCognitionTraceRepository:
    """Fail-soft stop-append wrapper. Never deletes prior rows."""

    __slots__ = (
        "_bytes_appended",
        "_inner",
        "_invocations_appended",
        "_max_bytes",
        "_max_invocations",
        "_stopped_reason",
    )

    def __init__(
        self,
        inner: CognitionTraceRepository,
        *,
        max_invocations: int | None = None,
        max_bytes: int | None = None,
    ) -> None:
        if max_invocations is not None and (
            isinstance(max_invocations, bool)
            or type(max_invocations) is not int
            or max_invocations < 1
        ):
            raise ValueError("max_invocations must be >= 1 when set")
        if max_bytes is not None and (
            isinstance(max_bytes, bool) or type(max_bytes) is not int or max_bytes < 1
        ):
            raise ValueError("max_bytes must be >= 1 when set")
        self._inner = inner
        self._max_invocations = max_invocations
        self._max_bytes = max_bytes
        self._invocations_appended = 0
        self._bytes_appended = 0
        self._stopped_reason: str | None = None

    @property
    def stopped_reason(self) -> str | None:
        return self._stopped_reason

    async def append_invocation(self, invocation: CognitionTraceInvocation) -> None:
        if type(invocation) is not CognitionTraceInvocation:
            raise TypeError("append_invocation requires CognitionTraceInvocation")
        if self._stopped_reason is not None:
            _LOG.debug(
                "[cognition_trace] soft_cap_skip run_id=%s reason_code=%s count=%s",
                invocation.run_id.value,
                self._stopped_reason,
                self._invocations_appended,
            )
            return
        approx_bytes = len(invocation.content_hash) + 64 * max(1, len(invocation.stages))
        if (
            self._max_invocations is not None
            and self._invocations_appended >= self._max_invocations
        ):
            self._stopped_reason = "soft_cap_invocations"
            _LOG.warning(
                "[cognition_trace] soft_cap_reached run_id=%s reason_code=%s count=%s",
                invocation.run_id.value,
                self._stopped_reason,
                self._invocations_appended,
            )
            return
        if (
            self._max_bytes is not None
            and self._bytes_appended + approx_bytes > self._max_bytes
        ):
            self._stopped_reason = "soft_cap_bytes"
            _LOG.warning(
                "[cognition_trace] soft_cap_reached run_id=%s reason_code=%s count=%s",
                invocation.run_id.value,
                self._stopped_reason,
                self._invocations_appended,
            )
            return
        await self._inner.append_invocation(invocation)
        self._invocations_appended += 1
        self._bytes_appended += approx_bytes

    async def get_invocation(
        self,
        *,
        run_id: RunId,
        agent_id: AgentId,
        tick: int,
        invocation_id: str,
    ) -> CognitionTraceInvocation | None:
        return await self._inner.get_invocation(
            run_id=run_id,
            agent_id=agent_id,
            tick=tick,
            invocation_id=invocation_id,
        )

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
        return await self._inner.list_invocations(
            run_id=run_id,
            agent_id=agent_id,
            tick_min=tick_min,
            tick_max=tick_max,
            after_cursor=after_cursor,
            limit=limit,
        )


def wrap_cognition_trace_soft_caps(
    repository: CognitionTraceRepository,
    *,
    max_invocations: int | None = None,
    max_bytes: int | None = None,
) -> CognitionTraceRepository:
    """Apply optional soft stop-append caps (default-off when both None)."""
    if max_invocations is None and max_bytes is None:
        return repository
    return SoftCapCognitionTraceRepository(
        repository,
        max_invocations=max_invocations,
        max_bytes=max_bytes,
    )


async def export_cognition_trace_invocations(
    repository: CognitionTraceRepository,
    *,
    run_id: RunId,
    agent_id: AgentId | None = None,
    limit: int = 1000,
) -> tuple[CognitionTraceInvocation, ...]:
    """Read-only export copy for offline archival. Does not delete live rows."""
    collected: list[CognitionTraceInvocation] = []
    after_cursor: str | None = None
    pages = 0
    while len(collected) < limit and pages < 10_000:
        page = await repository.list_invocations(
            run_id=run_id,
            agent_id=agent_id,
            after_cursor=after_cursor,
            limit=min(100, limit - len(collected)),
        )
        pages += 1
        if not page.items:
            break
        collected.extend(page.items)
        after_cursor = page.next_cursor
        if after_cursor is None:
            break
    _LOG.debug(
        "[cognition_trace] export_copy run_id=%s count=%s pages=%s",
        run_id.value,
        len(collected),
        pages,
    )
    return tuple(collected)


async def maybe_append_cognition_trace(
    *,
    repository: CognitionTraceRepository,
    spec: CognitionTraceSpec,
    run_id: RunId,
    agent_id: AgentId,
    tick: int,
    invocation_id: str,
    loop_result: object | None = None,
    loop_failure: object | None = None,
    loop_input: object | None = None,
    command_kind: str | None = None,
    final_confidence: float | None = None,
    budget_audit: object | None = None,
) -> bool:
    """Project and soft-append a cognition trace when enabled.

    Returns True when an append was attempted successfully (including identical
    retry). Returns False when skipped or soft-failed. Never raises into the
    cognition/admission path for sink errors.
    """
    if not spec.enabled:
        return False
    if spec.sample_every_n_ticks is not None:
        # tick 0 always sampled; then every N ticks.
        if tick != 0 and (tick % spec.sample_every_n_ticks) != 0:
            _LOG.debug(
                "cognition_trace_skipped",
                extra={
                    "reason_code": "sample_skip",
                    "run_id": run_id.value,
                    "agent_id": agent_id.value,
                    "tick": tick,
                    "invocation_id": invocation_id,
                },
            )
            return False
    try:
        stages = project_cognition_trace_stages(
            loop_result=loop_result,  # type: ignore[arg-type]
            loop_failure=loop_failure,  # type: ignore[arg-type]
            loop_input=loop_input,  # type: ignore[arg-type]
            agent_id=agent_id.value,
            tick=tick,
            invocation_id=invocation_id,
            budget_audit=budget_audit,
        )
        if spec.max_bytes_per_invocation is not None:
            stages = _truncate_stages_to_budget(
                stages, max_bytes=spec.max_bytes_per_invocation
            )
        invocation = build_cognition_trace_invocation(
            run_id=run_id,
            agent_id=agent_id,
            tick=tick,
            invocation_id=invocation_id,
            stage_summaries=stages,
            command_kind=command_kind,
            final_confidence=final_confidence,
        )
        # Prefer durable codec hash when serialization is available.
        try:
            from simulation.cognition_trace_serialization import (
                cognition_trace_content_hash,
            )

            digest = cognition_trace_content_hash(invocation)
            invocation = build_cognition_trace_invocation(
                run_id=run_id,
                agent_id=agent_id,
                tick=tick,
                invocation_id=invocation_id,
                stage_summaries=stages,
                command_kind=command_kind,
                final_confidence=final_confidence,
                content_hash=digest,
            )
        except Exception:  # pragma: no cover - codec always present in-tree
            pass
        await repository.append_invocation(invocation)
        _LOG.debug(
            "cognition_trace_appended",
            extra={
                "run_id": run_id.value,
                "agent_id": agent_id.value,
                "tick": tick,
                "invocation_id": invocation_id,
                "stage_count": len(stages),
                "hash_prefix": invocation.content_hash[:12],
            },
        )
        return True
    except Exception as exc:
        _LOG.warning(
            "cognition_trace_sink_failed",
            extra={
                "reason_code": type(exc).__name__,
                "run_id": run_id.value,
                "agent_id": agent_id.value,
                "tick": tick,
                "invocation_id": invocation_id,
            },
        )
        return False


def _truncate_stages_to_budget(
    stages: tuple[CognitionTraceStageSummary, ...],
    *,
    max_bytes: int,
) -> tuple[CognitionTraceStageSummary, ...]:
    """Soft-truncate trailing stages when serialized summaries exceed budget."""
    # Keep prefixes; mark last kept stage as truncated via a WARN only.
    from agents.cognition.trace import CognitionTraceStageStatus

    kept: list[CognitionTraceStageSummary] = []
    for stage in stages:
        candidate = (*kept, stage)
        # Approximate size via content hash input length.
        size = len(stage_summaries_content_hash(candidate).encode("utf-8")) * 32
        # Use a rough estimate: number of refs/codes as proxy if needed.
        approx = sum(
            64
            + len(item.selection_codes) * 16
            + len(item.id_refs) * 24
            + (0 if item.counts is None else len(item.counts) * 16)
            for item in candidate
        )
        if approx > max_bytes and kept:
            _LOG.warning(
                "cognition_trace_truncated",
                extra={
                    "reason_code": "max_bytes_per_invocation",
                    "kept_stage_count": len(kept),
                    "dropped_stage_count": len(stages) - len(kept),
                    "max_bytes": max_bytes,
                },
            )
            # Flip last kept status to TRUNCATED if completed.
            last = kept[-1]
            if last.status is CognitionTraceStageStatus.COMPLETED:
                kept[-1] = CognitionTraceStageSummary(
                    stage_kind=last.stage_kind,
                    status=CognitionTraceStageStatus.TRUNCATED,
                    ordinal=last.ordinal,
                    confidence=last.confidence,
                    uncertainty_band=last.uncertainty_band,
                    selection_codes=last.selection_codes,
                    id_refs=last.id_refs,
                    counts=last.counts,
                    reason_code="max_bytes_per_invocation",
                    decision_metadata=last.decision_metadata,
                    command_kind=last.command_kind,
                    intention_code=last.intention_code,
                    llm_meta=last.llm_meta,
                )
            return tuple(kept)
        _ = size  # keep estimate path referenced for future codec sizing
        kept.append(stage)
    return tuple(kept)


def _cursor_for(item: CognitionTraceInvocation) -> str:
    return f"{item.tick:016d}:{item.agent_id.value}:{item.invocation_id}"
