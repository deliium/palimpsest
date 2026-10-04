"""Persistence-backed API service adapters (composition root helpers).

Maps simulation/persistence DTOs to public Pydantic schemas. Never imports
``analysis`` or ``experiments``. Never returns live ``WorldEngine`` or private
world state through schemas.
"""

from __future__ import annotations

import base64
from collections.abc import Awaitable, Callable
from typing import Literal, Protocol

from api.errors import bad_request, forbidden, gone, not_found, unprocessable
from api.schemas import (
    AgentVisibleOut,
    AvailabilityOut,
    CausalTraceNodeOut,
    CausalTraceOut,
    DebuggerAddressOut,
    DebuggerAvailabilityOut,
    DebuggerFocusOut,
    DebuggerInvocationPageOut,
    DebuggerInvocationSummaryOut,
    DebuggerLineageEntryOut,
    DebuggerLineageOut,
    DebuggerNodeStatusOut,
    EventCursorIn,
    EventPageOut,
    EventSummaryOut,
    ExperimentalStateOut,
    GraphNodeSummaryOut,
    MetricCatalogItemOut,
    MetricCatalogOut,
    MetricDocumentOut,
    ObjectiveWorldOut,
    ReplayRequest,
    ReplayResultOut,
    SubjectiveGraphSummaryOut,
    SubjectivePageOut,
)
from api.services import (
    CausalDebuggerApiService,
    InspectionService,
    MetricReadService,
    ReplayApiService,
)
from infrastructure.logging import get_logger
from persistence.errors import PersistenceNotFoundError
from simulation.clock import Tick
from simulation.inspection import (
    EventKeysetCursor,
    InspectionAvailability,
    InspectionError,
    InspectionReplayProjection,
    MemoryKeysetCursor,
    SubjectiveGraphSummaryPage,
)
from simulation.models import RunId
from simulation.persistence import (
    ReplayRequest as SimulationReplayRequest,
)
from simulation.persistence import (
    SimulationRunRepository,
)
from simulation.replay import ReplayService

_LOGGER = get_logger("api.persistence_services")


class ObjectiveEvidenceLoaderPort(Protocol):
    async def load_events_page(
        self,
        *,
        run_id: str,
        after: EventKeysetCursor | None = None,
        limit: int = 100,
        manifest: object | None = None,
    ) -> object: ...


class SubjectiveEvidenceLoaderPort(Protocol):
    async def load_traces_page(
        self,
        *,
        run_id: str,
        owner_id: str,
        after: MemoryKeysetCursor | None = None,
        limit: int = 100,
        manifest: object | None = None,
    ) -> object: ...

    async def load_beliefs_page(
        self,
        *,
        run_id: str,
        owner_id: str,
        after: MemoryKeysetCursor | None = None,
        limit: int = 100,
        manifest: object | None = None,
    ) -> object: ...

    async def load_relationships_page(
        self,
        *,
        run_id: str,
        owner_id: str,
        after: MemoryKeysetCursor | None = None,
        limit: int = 100,
        manifest: object | None = None,
    ) -> object: ...

    async def load_graph_summary_page(
        self,
        *,
        run_id: str,
        owner_id: str,
        kind: Literal["memories", "beliefs"],
        after: MemoryKeysetCursor | None = None,
        limit: int = 100,
    ) -> object: ...


class InspectionEvidenceLoaderPort(Protocol):
    @property
    def objective(self) -> ObjectiveEvidenceLoaderPort: ...

    @property
    def subjective(self) -> SubjectiveEvidenceLoaderPort: ...


class MetricDocumentRepositoryPort(Protocol):
    async def list_metric_documents(
        self, *, run_id: str, metric_set_id: str | None = None
    ) -> tuple[object, ...]: ...

    async def get_metric_document(
        self, *, run_id: str, metric_set_id: str, metric_family: str
    ) -> object | None: ...


class MetricSetRepositoryPort(Protocol):
    async def get_metric_set(
        self, *, run_id: str, metric_set_id: str
    ) -> object | None: ...


def _map_availability(value: object) -> AvailabilityOut:
    if isinstance(value, InspectionAvailability):
        return AvailabilityOut(value.value)
    text = getattr(value, "value", None)
    if isinstance(text, str):
        return AvailabilityOut(text)
    return AvailabilityOut(str(value))


def _event_summaries(events: tuple[object, ...]) -> tuple[EventSummaryOut, ...]:
    summaries: list[EventSummaryOut] = []
    for event in events:
        tick = int(getattr(event, "tick", 0))
        sequence = int(getattr(event, "sequence", 0))
        kind_obj = getattr(event, "kind", None)
        kind = getattr(kind_obj, "value", None) or str(kind_obj or "unknown")
        summaries.append(EventSummaryOut(tick=tick, sequence=sequence, kind=str(kind)))
    return tuple(summaries)


def _objective_out(
    *, run_id: str, projection: object | None, availability: AvailabilityOut
) -> ObjectiveWorldOut | None:
    if projection is None:
        return None
    bodies = getattr(projection, "bodies", ())
    body_count = len(bodies)
    location_ids = {
        getattr(getattr(body, "location_id", None), "value", None)
        or str(getattr(body, "location_id", ""))
        for body in bodies
    }
    location_ids.discard("")
    location_ids.discard(None)
    return ObjectiveWorldOut(
        run_id=run_id,
        tick=int(getattr(projection, "tick", 0)),
        revision=int(getattr(projection, "revision", 0)),
        availability=availability,
        body_count=body_count,
        location_count=len(location_ids),
    )


def _agent_visible_out(
    *, run_id: str, view: object | None, availability: AvailabilityOut
) -> AgentVisibleOut | None:
    if view is None:
        return None
    observation = getattr(view, "observation", None)
    occurrence_count = len(getattr(observation, "occurrences", ()) or ())
    communication_count = len(getattr(observation, "communications", ()) or ())
    return AgentVisibleOut(
        run_id=run_id,
        tick=int(getattr(view, "tick", 0)),
        agent_id=str(getattr(view, "agent_id", "")),
        entity_id=str(getattr(view, "entity_id", "")),
        availability=availability,
        occurrence_count=occurrence_count,
        communication_count=communication_count,
    )


def _encode_memory_cursor(cursor: MemoryKeysetCursor | None) -> str | None:
    if cursor is None:
        return None
    return f"{cursor.created_tick}:{cursor.row_id}"


def _parse_memory_cursor(after: str | None) -> MemoryKeysetCursor | None:
    if after is None or after == "":
        return None
    tick_s, sep, row_id = after.partition(":")
    if not sep or not tick_s or not row_id:
        raise bad_request(code="invalid_memory_cursor")
    try:
        tick = int(tick_s)
    except ValueError as exc:
        raise bad_request(code="invalid_memory_cursor") from exc
    if tick < 0:
        raise bad_request(code="invalid_memory_cursor")
    return MemoryKeysetCursor(created_tick=tick, row_id=row_id)


def _translate_inspection_error(exc: InspectionError, *, run_id: str) -> None:
    if exc.code in {"unknown_agent", "run_not_found"}:
        raise not_found(code=exc.code, run_id=run_id) from exc
    if exc.code in {"projection_unavailable", "replay_unavailable"}:
        raise gone(code=exc.code, run_id=run_id) from exc
    if exc.code in {
        "invalid_page_limit",
        "page_limit_exceeded",
        "invalid_memory_cursor",
    }:
        raise bad_request(code=exc.code, run_id=run_id) from exc
    if exc.code in {"subjective_requires_debug_surface"}:
        raise forbidden(code=exc.code) from exc
    raise unprocessable(code=exc.code, run_id=run_id) from exc


class PersistenceInspectionService(InspectionService):
    """Inspection facade backed by evidence loaders + detached replay."""

    def __init__(
        self,
        *,
        evidence: InspectionEvidenceLoaderPort,
        runs: SimulationRunRepository,
        replay: ReplayService,
    ) -> None:
        self._evidence = evidence
        self._runs = runs
        self._replay = replay

    async def objective_world(self, run_id: str) -> ObjectiveWorldOut:
        _LOGGER.info(
            "[FIX] inspection_objective_world",
            run_id=run_id,
            operation="objective_world",
        )
        try:
            projection = await self._inspect(run_id, agent_id=None)
        except PersistenceNotFoundError as exc:
            raise not_found(code=exc.code, run_id=run_id) from exc
        except InspectionError as exc:
            _translate_inspection_error(exc, run_id=run_id)
            raise
        availability = _map_availability(projection.availability)
        objective = _objective_out(
            run_id=run_id,
            projection=projection.objective,
            availability=availability,
        )
        if objective is None:
            raise not_found(code="run_not_found", run_id=run_id)
        _LOGGER.info(
            "[FIX] inspection_objective_world_ok",
            run_id=run_id,
            availability=availability.value,
            body_count=objective.body_count,
        )
        return objective

    async def events_page(
        self,
        run_id: str,
        *,
        after: EventCursorIn | None,
        limit: int,
    ) -> EventPageOut:
        cursor = (
            None
            if after is None
            else EventKeysetCursor(tick=after.tick, sequence=after.sequence)
        )
        _LOGGER.info(
            "[FIX] inspection_events_page",
            run_id=run_id,
            limit=limit,
            has_cursor=after is not None,
        )
        try:
            page = await self._evidence.objective.load_events_page(
                run_id=run_id, after=cursor, limit=limit
            )
        except PersistenceNotFoundError as exc:
            raise not_found(code=exc.code, run_id=run_id) from exc
        except InspectionError as exc:
            _translate_inspection_error(exc, run_id=run_id)
            raise
        events = tuple(getattr(page, "events", ()) or ())
        next_raw = getattr(page, "next_cursor", None)
        next_cursor = (
            None
            if next_raw is None
            else EventCursorIn(
                tick=int(getattr(next_raw, "tick", 0)),
                sequence=int(getattr(next_raw, "sequence", 0)),
            )
        )
        availability = _map_availability(getattr(page, "availability", "unavailable"))
        result = EventPageOut(
            run_id=run_id,
            limit=int(getattr(page, "limit", limit)),
            count=len(events),
            next_cursor=next_cursor,
            availability=availability,
            manifest_hash=getattr(page, "manifest_hash", None),
            events=_event_summaries(events),
        )
        _LOGGER.info(
            "[FIX] inspection_events_page_ok",
            run_id=run_id,
            count=result.count,
            availability=result.availability.value,
        )
        return result

    async def agent_visible(self, run_id: str, agent_id: str) -> AgentVisibleOut:
        _LOGGER.info(
            "[FIX] inspection_agent_visible",
            run_id=run_id,
            agent_id=agent_id,
        )
        try:
            projection = await self._inspect(run_id, agent_id=agent_id)
        except PersistenceNotFoundError as exc:
            raise not_found(code=exc.code, run_id=run_id) from exc
        except InspectionError as exc:
            _translate_inspection_error(exc, run_id=run_id)
            raise
        availability = _map_availability(projection.availability)
        view = _agent_visible_out(
            run_id=run_id,
            view=projection.agent_visible,
            availability=availability,
        )
        if view is None:
            raise not_found(code="unknown_agent", run_id=run_id)
        return view

    async def experimental_state(self, run_id: str) -> ExperimentalStateOut:
        manifest = await self._runs.get_run(RunId(run_id))
        if manifest is None:
            raise not_found(code="run_not_found", run_id=run_id)
        assignment = getattr(manifest, "experiment_assignment", None)
        if assignment is None:
            _LOGGER.info(
                "[FIX] inspection_experimental_unavailable",
                run_id=run_id,
                availability=AvailabilityOut.UNAVAILABLE.value,
            )
            return ExperimentalStateOut(
                run_id=run_id,
                availability=AvailabilityOut.UNAVAILABLE,
            )
        experiment_obj = getattr(assignment, "experiment_id", None)
        experiment_id = getattr(experiment_obj, "value", None)
        if experiment_id is None:
            experiment_id = str(experiment_obj or "") or None
        return ExperimentalStateOut(
            run_id=run_id,
            experiment_id=experiment_id,
            membership_source="assignment",
            has_assignment=True,
            availability=AvailabilityOut.AVAILABLE,
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
        cursor = _parse_memory_cursor(after)
        loader = self._evidence.subjective
        loaders: dict[
            str,
            Callable[..., Awaitable[object]],
        ] = {
            "memories": loader.load_traces_page,
            "beliefs": loader.load_beliefs_page,
            "relationships": loader.load_relationships_page,
        }
        load = loaders[kind]
        _LOGGER.info(
            "[FIX] inspection_subjective_page",
            run_id=run_id,
            owner_id=owner_id,
            kind=kind,
            limit=limit,
        )
        try:
            page = await load(
                run_id=run_id, owner_id=owner_id, after=cursor, limit=limit
            )
        except PersistenceNotFoundError as exc:
            raise not_found(code=exc.code, run_id=run_id) from exc
        except InspectionError as exc:
            _translate_inspection_error(exc, run_id=run_id)
            raise
        next_raw = getattr(page, "next_cursor", None)
        next_cursor = (
            _encode_memory_cursor(next_raw)
            if isinstance(next_raw, MemoryKeysetCursor)
            else None
        )
        return SubjectivePageOut(
            run_id=run_id,
            owner_id=owner_id,
            limit=int(getattr(page, "limit", limit)),
            item_count=int(getattr(page, "item_count", 0)),
            next_cursor=next_cursor,
            availability=_map_availability(
                getattr(page, "availability", InspectionAvailability.UNAVAILABLE)
            ),
            content_available=bool(getattr(page, "content_available", False)),
            kind=kind,
        )

    async def graph_summary_page(
        self,
        run_id: str,
        owner_id: str,
        *,
        kind: Literal["memories", "beliefs"],
        after: str | None,
        limit: int,
    ) -> SubjectiveGraphSummaryOut:
        cursor = _parse_memory_cursor(after)
        loader = self._evidence.subjective
        _LOGGER.info(
            "[FIX] inspection_graph_summary",
            run_id=run_id,
            owner_id=owner_id,
            kind=kind,
            limit=limit,
        )
        try:
            page = await loader.load_graph_summary_page(
                run_id=run_id,
                owner_id=owner_id,
                kind=kind,
                after=cursor,
                limit=limit,
            )
        except PersistenceNotFoundError as exc:
            raise not_found(code=exc.code, run_id=run_id) from exc
        except InspectionError as exc:
            _translate_inspection_error(exc, run_id=run_id)
            raise
        if type(page) is not SubjectiveGraphSummaryPage:
            raise TypeError("load_graph_summary_page must return SubjectiveGraphSummaryPage")
        next_raw = page.next_cursor
        next_cursor = (
            _encode_memory_cursor(next_raw)
            if isinstance(next_raw, MemoryKeysetCursor)
            else None
        )
        items = tuple(
            GraphNodeSummaryOut(
                node_id=item.node_id,
                created_tick=item.created_tick,
                source_kind=item.source_kind,
                strength=item.strength,
                target_id=item.target_id,
                lineage_ref_ids=item.lineage_ref_ids,
            )
            for item in page.items
        )
        _LOGGER.debug(
            "[FIX] inspection_graph_summary_page_size",
            run_id=run_id,
            owner_id=owner_id,
            kind=kind,
            count=len(items),
        )
        return SubjectiveGraphSummaryOut(
            run_id=run_id,
            owner_id=owner_id,
            kind=kind,
            availability=_map_availability(page.availability),
            limit=page.limit,
            count=len(items),
            next_cursor=next_cursor,
            items=items,
        )

    async def _inspect(
        self, run_id: str, *, agent_id: str | None
    ) -> InspectionReplayProjection:
        request = SimulationReplayRequest(
            run_id=RunId(run_id),
            target_tick=None,
        )
        projected = await self._replay.inspect_at_tick(request, agent_id=agent_id)
        if type(projected) is not InspectionReplayProjection:
            raise TypeError("inspect_at_tick must return InspectionReplayProjection")
        return projected


class PersistenceMetricReadService(MetricReadService):
    """Metric catalog/document reader over opaque persistence envelopes."""

    def __init__(
        self,
        *,
        documents: MetricDocumentRepositoryPort,
        metric_sets: MetricSetRepositoryPort,
        runs: SimulationRunRepository,
    ) -> None:
        self._documents = documents
        self._metric_sets = metric_sets
        self._runs = runs

    async def catalog(self, run_id: str) -> MetricCatalogOut:
        if await self._runs.get_run(RunId(run_id)) is None:
            raise not_found(code="run_not_found", run_id=run_id)
        records = await self._documents.list_metric_documents(run_id=run_id)
        items: list[MetricCatalogItemOut] = []
        for record in records:
            envelope = getattr(record, "envelope", None)
            content_hash = str(getattr(envelope, "content_hash", "") or "")
            items.append(
                MetricCatalogItemOut(
                    metric_set_id=str(getattr(record, "metric_set_id", "")),
                    metric_family=str(getattr(record, "metric_family", "")),
                    evidence_manifest_hash=str(
                        getattr(record, "evidence_manifest_hash", "")
                    ),
                    schema_version=str(getattr(envelope, "schema_version", "") or ""),
                    content_hash_prefix=(content_hash[:12] or "unavailable")[:16],
                )
            )
        _LOGGER.info(
            "[FIX] metric_catalog",
            run_id=run_id,
            count=len(items),
        )
        return MetricCatalogOut(
            run_id=run_id,
            items=tuple(items),
            count=len(items),
            availability=AvailabilityOut.AVAILABLE,
        )

    async def document(
        self, run_id: str, metric_set_id: str, metric_family: str
    ) -> MetricDocumentOut:
        if await self._runs.get_run(RunId(run_id)) is None:
            raise not_found(code="run_not_found", run_id=run_id)
        # Touch metric-set portal so wiring is exercised without experiments types.
        await self._metric_sets.get_metric_set(
            run_id=run_id, metric_set_id=metric_set_id
        )
        record = await self._documents.get_metric_document(
            run_id=run_id,
            metric_set_id=metric_set_id,
            metric_family=metric_family,
        )
        if record is None:
            raise gone(code="metric_unavailable", run_id=run_id)
        envelope = getattr(record, "envelope", None)
        payload = bytes(getattr(envelope, "payload", b"") or b"")
        content_hash = str(getattr(envelope, "content_hash", "") or "")
        _LOGGER.info(
            "[FIX] metric_document",
            run_id=run_id,
            metric_set_id=metric_set_id,
            metric_family=metric_family,
            payload_bytes=len(payload),
        )
        return MetricDocumentOut(
            run_id=run_id,
            metric_set_id=metric_set_id,
            metric_family=metric_family,
            evidence_manifest_hash=str(
                getattr(record, "evidence_manifest_hash", "")
            ),
            schema_version=str(getattr(envelope, "schema_version", "") or ""),
            content_hash=content_hash,
            payload_b64=base64.b64encode(payload).decode("ascii"),
            availability=AvailabilityOut.AVAILABLE,
        )


class PersistenceReplayApiService(ReplayApiService):
    """Replay facade: ReplayService + project_replay_for_inspection only."""

    def __init__(self, *, replay: ReplayService) -> None:
        self._replay = replay

    async def replay_to_tick(
        self, run_id: str, body: ReplayRequest
    ) -> ReplayResultOut:
        _LOGGER.info(
            "[FIX] replay_to_tick",
            run_id=run_id,
            to_tick=body.to_tick,
            has_agent=body.agent_id is not None,
        )
        request = SimulationReplayRequest(
            run_id=RunId(run_id),
            target_tick=Tick(body.to_tick),
        )
        try:
            projected = await self._replay.inspect_at_tick(
                request, agent_id=body.agent_id
            )
        except PersistenceNotFoundError as exc:
            raise not_found(code=exc.code, run_id=run_id) from exc
        except InspectionError as exc:
            _translate_inspection_error(exc, run_id=run_id)
            raise
        if type(projected) is not InspectionReplayProjection:
            raise TypeError("inspect_at_tick must return InspectionReplayProjection")
        result = projected.result
        availability = _map_availability(projected.availability)
        status = getattr(getattr(result, "status", None), "value", None) or str(
            getattr(result, "status", "unknown")
        )
        target = getattr(result, "target_tick", None)
        if target is not None and hasattr(target, "value"):
            ticks_replayed = int(target.value)
        else:
            ticks_replayed = int(getattr(result, "events_applied", 0) or 0)
        out = ReplayResultOut(
            run_id=run_id,
            status=status,
            availability=availability,
            ticks_replayed=ticks_replayed,
            objective=_objective_out(
                run_id=run_id,
                projection=projected.objective,
                availability=availability,
            ),
            agent_visible=_agent_visible_out(
                run_id=run_id,
                view=projected.agent_visible,
                availability=availability,
            ),
            reason_code=None if status == "ok" else status,
        )
        _LOGGER.info(
            "[FIX] replay_to_tick_ok",
            run_id=run_id,
            status=status,
            availability=availability.value,
            ticks_replayed=ticks_replayed,
        )
        return out


def _focus_out(handle: object) -> DebuggerFocusOut:
    return DebuggerFocusOut(
        run_id=str(getattr(getattr(handle, "run_id", None), "value", "")),
        tick=int(getattr(handle, "tick", 0)),
        sequence=getattr(handle, "sequence", None),
        event_id=getattr(handle, "event_id", None),
    )


def _node_out(node: object) -> CausalTraceNodeOut:
    status_raw = getattr(getattr(node, "status", None), "value", "unavailable")
    return CausalTraceNodeOut(
        stage_code=str(getattr(node, "stage_code", "")),
        status=DebuggerNodeStatusOut(status_raw),
        reason_code=getattr(node, "reason_code", None),
        confidence=getattr(node, "confidence", None),
        uncertainty_band=getattr(node, "uncertainty_band", None),
        selection_codes=tuple(getattr(node, "selection_codes", ()) or ()),
        id_refs=tuple(getattr(node, "id_refs", ()) or ()),
        counts=(
            None
            if getattr(node, "counts", None) is None
            else dict(node.counts)
        ),
        command_kind=getattr(node, "command_kind", None),
        intention_code=getattr(node, "intention_code", None),
        observer_focus=tuple(
            _focus_out(item) for item in (getattr(node, "focus_handles", ()) or ())
        ),
        secondary=bool(getattr(node, "secondary", False)),
    )


def _address_out(address: object) -> DebuggerAddressOut:
    agent = getattr(address, "agent_id", None)
    return DebuggerAddressOut(
        run_id=str(getattr(getattr(address, "run_id", None), "value", "")),
        tick=int(getattr(address, "tick", 0)),
        event_id=getattr(address, "event_id", None),
        sequence=getattr(address, "sequence", None),
        agent_id=None if agent is None else str(getattr(agent, "value", agent)),
    )


def _causal_trace_out(trace: object) -> CausalTraceOut:
    availability = DebuggerAvailabilityOut(
        getattr(getattr(trace, "availability", None), "value", "unavailable")
    )
    return CausalTraceOut(
        address=_address_out(trace.address),
        availability=availability,
        nodes=tuple(_node_out(node) for node in getattr(trace, "nodes", ())),
        invocation_id=getattr(trace, "invocation_id", None),
        ambiguity=bool(getattr(trace, "ambiguity", False)),
        reason_code=getattr(trace, "reason_code", None),
        command_kind=getattr(trace, "command_kind", None),
        supporting_nodes=tuple(
            _node_out(node) for node in getattr(trace, "supporting_nodes", ())
        ),
    )


class PersistenceCausalDebuggerService(CausalDebuggerApiService):
    """Compose cognition-trace repo + event/lineage ports into debugger GETs."""

    def __init__(
        self,
        *,
        traces: object,
        events: object,
        lineage_ports: dict[str, object],
        runs: SimulationRunRepository,
    ) -> None:
        self._traces = traces
        self._events = events
        self._lineage_ports = lineage_ports
        self._runs = runs

    async def causal_trace(
        self,
        run_id: str,
        *,
        event_id: str | None,
        tick: int | None,
        sequence: int | None,
    ) -> CausalTraceOut:
        from simulation.causal_debugger import (
            CausalTrace,
            CausalTraceAvailability,
            assemble_causal_trace,
            resolve_invocation_for_event,
        )
        from simulation.models import RunId

        typed_run = RunId(run_id)
        if await self._runs.get_run(typed_run) is None:
            raise not_found(code="run_not_found", run_id=run_id)
        _LOGGER.debug(
            "debugger_causal_trace",
            run_id=run_id,
            event_id=event_id,
            tick=tick,
            sequence=sequence,
        )
        resolved = await resolve_invocation_for_event(
            run_id=typed_run,
            traces=self._traces,
            events=self._events,
            event_id=event_id,
            tick=tick,
            sequence=sequence,
        )
        if resolved.reason_code == "event_not_found":
            raise not_found(code="event_not_found", run_id=run_id)
        if resolved.availability is not CausalTraceAvailability.AVAILABLE:
            empty = CausalTrace(
                address=resolved.address,
                availability=resolved.availability,
                nodes=(),
                reason_code=resolved.reason_code,
                ambiguity=resolved.ambiguity,
                command_kind=resolved.command_kind,
            )
            return _causal_trace_out(empty)
        assert resolved.invocation_id is not None
        assert resolved.address.agent_id is not None
        invocation = await self._traces.get_invocation(
            run_id=typed_run,
            agent_id=resolved.address.agent_id,
            tick=resolved.address.tick,
            invocation_id=resolved.invocation_id,
        )
        if invocation is None:
            empty = CausalTrace(
                address=resolved.address,
                availability=CausalTraceAvailability.UNAVAILABLE,
                nodes=(),
                reason_code="cognition_trace_missing",
            )
            return _causal_trace_out(empty)
        assembled = assemble_causal_trace(
            invocation,
            address=resolved.address,
            ambiguity=resolved.ambiguity,
            ambiguity_reason=resolved.reason_code,
        )
        return _causal_trace_out(assembled)

    async def list_invocations(
        self,
        run_id: str,
        agent_id: str,
        *,
        tick: int | None,
    ) -> DebuggerInvocationPageOut:
        from simulation.cognition_trace import AgentId
        from simulation.models import RunId

        typed_run = RunId(run_id)
        if await self._runs.get_run(typed_run) is None:
            raise not_found(code="run_not_found", run_id=run_id)
        page = await self._traces.list_invocations(
            run_id=typed_run,
            agent_id=AgentId(agent_id),
            tick_min=tick,
            tick_max=tick,
            limit=100,
        )
        items = tuple(
            DebuggerInvocationSummaryOut(
                invocation_id=item.invocation_id,
                agent_id=item.agent_id.value,
                tick=item.tick,
                command_kind=item.command_kind,
                content_hash_prefix=item.content_hash[:12],
            )
            for item in page.items
        )
        availability = (
            DebuggerAvailabilityOut.AVAILABLE
            if items
            else DebuggerAvailabilityOut.UNAVAILABLE
        )
        return DebuggerInvocationPageOut(
            run_id=run_id,
            agent_id=agent_id,
            tick=tick,
            items=items,
            count=len(items),
            availability=availability,
        )

    async def lineage(
        self,
        run_id: str,
        *,
        kind: str,
        subject_id: str,
        owner_id: str,
    ) -> DebuggerLineageOut:
        from simulation.cognition_trace import AgentId
        from simulation.models import RunId

        typed_run = RunId(run_id)
        if await self._runs.get_run(typed_run) is None:
            raise not_found(code="run_not_found", run_id=run_id)
        port = self._lineage_ports.get(kind)
        if port is None:
            raise bad_request(code="invalid_kind")
        owner = AgentId(owner_id)
        if kind == "belief_evidence":
            response = await port.belief_evidence(  # type: ignore[attr-defined]
                run_id=typed_run, owner_id=owner, subject_id=subject_id
            )
        elif kind == "memory_derivation":
            response = await port.memory_derivation(  # type: ignore[attr-defined]
                run_id=typed_run, owner_id=owner, subject_id=subject_id
            )
        elif kind == "communication":
            response = await port.communication_lineage(  # type: ignore[attr-defined]
                run_id=typed_run, owner_id=owner, subject_id=subject_id
            )
        elif kind == "narrative":
            response = await port.narrative_lineage(  # type: ignore[attr-defined]
                run_id=typed_run, owner_id=owner, subject_id=subject_id
            )
        elif kind == "goal_ancestry":
            response = await port.goal_ancestry(  # type: ignore[attr-defined]
                run_id=typed_run, owner_id=owner, subject_id=subject_id
            )
        elif kind == "prediction":
            response = await port.prediction_provenance(  # type: ignore[attr-defined]
                run_id=typed_run, owner_id=owner, subject_id=subject_id
            )
        else:
            raise bad_request(code="invalid_kind")
        return DebuggerLineageOut(
            run_id=run_id,
            owner_id=owner_id,
            kind=kind,
            subject_id=subject_id,
            availability=DebuggerAvailabilityOut(response.availability.value),
            entries=tuple(
                DebuggerLineageEntryOut(
                    entry_id=entry.entry_id,
                    kind=entry.kind.value,
                    related_ids=entry.related_ids,
                    reason_codes=entry.reason_codes,
                    counts=None if entry.counts is None else dict(entry.counts),
                    observer_focus=tuple(
                        _focus_out(item) for item in entry.focus_handles
                    ),
                    parent_ids=entry.parent_ids,
                    status_code=entry.status_code,
                )
                for entry in response.entries
            ),
            reason_code=response.reason_code,
        )
