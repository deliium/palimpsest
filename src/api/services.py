"""Injectable API service facades (kept separate to avoid route cycles)."""

from __future__ import annotations

from typing import Literal

from api.errors import forbidden, gone, not_found
from api.schemas import (
    AgentVisibleOut,
    AvailabilityOut,
    CausalTraceOut,
    DebuggerInvocationPageOut,
    DebuggerLineageOut,
    EventCursorIn,
    EventPageOut,
    ExperimentalStateOut,
    MetricCatalogOut,
    MetricDocumentOut,
    ObjectiveWorldOut,
    ReplayRequest,
    ReplayResultOut,
    SubjectiveGraphSummaryOut,
    SubjectivePageOut,
)


class InspectionService:
    """Injectable inspection facade used by routes (unit-test friendly)."""

    async def objective_world(self, run_id: str) -> ObjectiveWorldOut:
        raise not_found(code="run_not_found", run_id=run_id)

    async def events_page(
        self,
        run_id: str,
        *,
        after: EventCursorIn | None,
        limit: int,
    ) -> EventPageOut:
        raise not_found(code="run_not_found", run_id=run_id)

    async def agent_visible(self, run_id: str, agent_id: str) -> AgentVisibleOut:
        raise not_found(code="run_not_found", run_id=run_id)

    async def experimental_state(self, run_id: str) -> ExperimentalStateOut:
        return ExperimentalStateOut(
            run_id=run_id,
            availability=AvailabilityOut.UNAVAILABLE,
        )

    async def subjective_page(
        self,
        run_id: str,
        owner_id: str,
        *,
        kind: Literal["memories", "beliefs", "relationships"],
        after: str | None,
        limit: int,
    ) -> SubjectivePageOut:
        raise forbidden(code="debug_disabled")

    async def graph_summary_page(
        self,
        run_id: str,
        owner_id: str,
        *,
        kind: Literal["memories", "beliefs"],
        after: str | None,
        limit: int,
    ) -> SubjectiveGraphSummaryOut:
        del after
        return SubjectiveGraphSummaryOut(
            run_id=run_id,
            owner_id=owner_id,
            kind=kind,
            availability=AvailabilityOut.UNAVAILABLE,
            limit=limit,
            count=0,
            items=(),
        )


class MetricReadService:
    """Injectable metric catalog/document reader (persistence-backed)."""

    async def catalog(self, run_id: str) -> MetricCatalogOut:
        return MetricCatalogOut(
            run_id=run_id,
            items=(),
            count=0,
            availability=AvailabilityOut.UNAVAILABLE,
        )

    async def document(
        self, run_id: str, metric_set_id: str, metric_family: str
    ) -> MetricDocumentOut:
        raise gone(code="metric_unavailable", run_id=run_id)


class ReplayApiService:
    """Injectable replay facade (never returns live engines)."""

    async def replay_to_tick(
        self, run_id: str, body: ReplayRequest
    ) -> ReplayResultOut:
        raise not_found(code="run_not_found", run_id=run_id)


class CausalDebuggerApiService:
    """Injectable read-only causal debugger facade (subjective_debug)."""

    async def causal_trace(
        self,
        run_id: str,
        *,
        event_id: str | None,
        tick: int | None,
        sequence: int | None,
    ) -> CausalTraceOut:
        raise not_found(code="run_not_found", run_id=run_id)

    async def list_invocations(
        self,
        run_id: str,
        agent_id: str,
        *,
        tick: int | None,
    ) -> DebuggerInvocationPageOut:
        raise not_found(code="run_not_found", run_id=run_id)

    async def lineage(
        self,
        run_id: str,
        *,
        kind: str,
        subject_id: str,
        owner_id: str,
    ) -> DebuggerLineageOut:
        raise not_found(code="run_not_found", run_id=run_id)
