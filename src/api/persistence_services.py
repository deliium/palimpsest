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
    EventCursorIn,
    EventPageOut,
    EventSummaryOut,
    ExperimentalStateOut,
    MetricCatalogItemOut,
    MetricCatalogOut,
    MetricDocumentOut,
    ObjectiveWorldOut,
    ReplayRequest,
    ReplayResultOut,
    SubjectivePageOut,
)
from api.services import InspectionService, MetricReadService, ReplayApiService
from infrastructure.logging import get_logger
from persistence.errors import PersistenceNotFoundError
from simulation.clock import Tick
from simulation.inspection import (
    EventKeysetCursor,
    InspectionAvailability,
    InspectionError,
    InspectionReplayProjection,
    MemoryKeysetCursor,
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
