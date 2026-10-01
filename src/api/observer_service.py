"""Compose replay folds into read-only observer responses. Drops every engine."""

from __future__ import annotations

import logging
from typing import Protocol

from api.errors import bad_request, conflict, not_found
from api.observer_schemas import (
    ObserverDimensionScoreOut,
    ObserverEventOut,
    ObserverEventPageOut,
    ObserverFrameOut,
    ObserverManifestOut,
    ObserverRelationshipPageOut,
    ObserverRelationshipSummaryOut,
    ObserverRunOut,
    ObserverTickPageOut,
    ObserverTickSummaryOut,
)
from observer.adapt import adapt_event
from observer.contracts import (
    ObserverEvent,
    ObserverFrame,
    ObserverManifest,
    ObserverPresentation,
    ObserverRelationshipSummary,
    ScreenPoint,
    VisualBounds,
)
from observer.layout import ObserverLayoutCatalog, ObserverLayoutError, load_layout
from observer.relationships import project_relationship_summaries
from observer.sources import LiveObserverSource, ReplayObserverSource
from observer.version import DEFAULT_LAYOUT_ID, OBSERVER_PROTOCOL_VERSION
from simulation.clock import Tick
from simulation.models import RunId
from simulation.replay import (
    FoldedObjectiveHistory,
    ObserverHistoryError,
    ReplayService,
    scene_at_tick,
    scene_through_event,
)

_LOGGER = logging.getLogger("api.observer")


class RelationshipScoreSource(Protocol):
    async def read_relationship_dimension_values(
        self, run_id: str, owner_id: str
    ) -> tuple[tuple[str, str, str, float], ...]: ...


class ObserverReadService:
    """Read-only observer queries. Route handlers must not advance a tick."""

    __slots__ = ("_relationships", "_replay")

    def __init__(
        self,
        replay: ReplayService,
        relationships: RelationshipScoreSource | None = None,
    ) -> None:
        if type(replay) is not ReplayService:
            raise TypeError("ObserverReadService requires ReplayService")
        self._replay = replay
        self._relationships = relationships

    @property
    def replay(self) -> ReplayService:
        return self._replay

    async def manifest(self, run_id: str, *, layout_id: str) -> ObserverManifestOut:
        history = await self._history(run_id, target_tick=None)
        layout = _layout(layout_id)
        source = _source(history, layout, mode="live")
        return _manifest_out(source.manifest())

    async def state(
        self,
        run_id: str,
        *,
        tick: int | None,
        layout_id: str,
        through_sequence: int | None = None,
    ) -> ObserverFrameOut:
        if through_sequence is not None and tick is None:
            raise bad_request(code="incomplete_event_cursor", run_id=run_id)
        if through_sequence is not None and (
            isinstance(through_sequence, bool)
            or type(through_sequence) is not int
            or through_sequence < 0
        ):
            raise bad_request(code="incomplete_event_cursor", run_id=run_id)
        if through_sequence is not None:
            assert tick is not None
            history = await self._history_through_event(
                run_id, tick=tick, through_sequence=through_sequence
            )
        else:
            target = None if tick is None else Tick(tick)
            history = await self._history(run_id, target_tick=target)
        layout = _layout(layout_id)
        mode = "replay" if tick is not None or through_sequence is not None else "live"
        source = _source(history, layout, mode=mode)
        return _frame_out(source.frame())

    async def events(
        self,
        run_id: str,
        *,
        after_tick: int | None,
        after_sequence: int | None,
        limit: int,
        layout_id: str,
    ) -> ObserverEventPageOut:
        _layout(layout_id)
        typed = _run_id(run_id)
        history = await self._history(run_id, target_tick=None)
        _reject_ahead(history.scene.tick, after_tick, after_sequence, run_id=run_id)
        page = await self._replay.read_event_keyset_page(
            typed,
            after_tick=0 if after_tick is None else after_tick,
            after_sequence=-1 if after_sequence is None else after_sequence,
            limit=limit,
        )
        adapted = tuple(adapt_event(event) for event in page.events)
        return ObserverEventPageOut(
            run_id=run_id,
            count=len(adapted),
            events=tuple(_event_out(item) for item in adapted),
            limit=limit,
        )

    async def ticks(
        self,
        run_id: str,
        *,
        from_tick: int,
        to_tick: int,
    ) -> ObserverTickPageOut:
        if to_tick < from_tick:
            raise bad_request(code="invalid_tick_range", run_id=run_id)
        typed = _run_id(run_id)
        page = await self._replay.read_event_page(
            typed,
            from_tick=Tick(from_tick),
            to_tick=Tick(to_tick),
            limit=1000,
        )
        grouped: dict[int, list[int]] = {}
        for event in page.events:
            grouped.setdefault(event.tick, []).append(event.sequence)
        summaries = tuple(
            ObserverTickSummaryOut(
                tick=tick,
                event_count=len(sequences),
                first_sequence=min(sequences),
                last_sequence=max(sequences),
            )
            for tick, sequences in sorted(grouped.items())
        )
        return ObserverTickPageOut(run_id=run_id, count=len(summaries), ticks=summaries)

    async def event(self, run_id: str, event_id: str) -> ObserverEventOut:
        typed = _run_id(run_id)
        after_tick = 0
        after_sequence = -1
        for _ in range(100):
            page = await self._replay.read_event_keyset_page(
                typed,
                after_tick=after_tick,
                after_sequence=after_sequence,
                limit=100,
            )
            if not page.events:
                break
            for item in page.events:
                if item.event_id.value == event_id:
                    return _event_out(adapt_event(item))
            last = page.events[-1]
            after_tick = last.tick
            after_sequence = last.sequence
            if page.next_offset is None and len(page.events) < page.limit:
                break
        raise not_found(code="observer_event_not_found", run_id=run_id)

    async def run(self, run_id: str) -> ObserverRunOut:
        history = await self._history(run_id, target_tick=None)
        latest_tick = None
        latest_sequence = None
        if history.events:
            latest_tick = history.events[-1].tick
            latest_sequence = history.events[-1].sequence
        return ObserverRunOut(
            run_id=history.scene.run_id,
            world_id=history.scene.world_id,
            availability="available",
            protocol_version=OBSERVER_PROTOCOL_VERSION,
            event_schema_version=history.result.event_schema_version,
            projector_version=history.result.projector_version,
            tick=history.scene.tick,
            latest_tick=latest_tick,
            latest_sequence=latest_sequence,
        )

    async def relationships(
        self, run_id: str, owner_id: str
    ) -> ObserverRelationshipPageOut:
        if self._relationships is None:
            raise not_found(code="observer_relationships_unavailable", run_id=run_id)
        rows = await self._relationships.read_relationship_dimension_values(
            run_id, owner_id
        )
        summaries = project_relationship_summaries(rows)
        return ObserverRelationshipPageOut(
            run_id=run_id,
            owner_id=owner_id,
            count=len(summaries),
            items=tuple(_relationship_out(item) for item in summaries),
        )

    async def _history(
        self, run_id: str, *, target_tick: Tick | None
    ) -> FoldedObjectiveHistory:
        typed = _run_id(run_id)
        try:
            history = await scene_at_tick(self._replay, typed, target_tick=target_tick)
        except ObserverHistoryError as exc:
            _LOGGER.error("observer_replay_failed reason_code=%s", exc.reason_code)
            raise not_found(code=exc.reason_code, run_id=run_id) from exc
        self._log_loaded(
            run_id, history, target_tick=target_tick, through_sequence=None
        )
        if hasattr(history, "engine"):
            raise RuntimeError("observer history retained an engine")
        return history

    async def _history_through_event(
        self, run_id: str, *, tick: int, through_sequence: int
    ) -> FoldedObjectiveHistory:
        typed = _run_id(run_id)
        live = await self._history(run_id, target_tick=None)
        if tick >= live.scene.tick:
            raise conflict(code="cursor_ahead_of_high_water", run_id=run_id)
        try:
            history = await scene_through_event(
                self._replay,
                typed,
                tick=Tick(tick),
                through_sequence=through_sequence,
            )
        except ObserverHistoryError as exc:
            _LOGGER.error("observer_replay_failed reason_code=%s", exc.reason_code)
            if exc.reason_code == "observer_event_not_found":
                raise not_found(code="observer_event_not_found", run_id=run_id) from exc
            if exc.reason_code == "target_unreachable":
                raise conflict(
                    code="cursor_ahead_of_high_water", run_id=run_id
                ) from exc
            raise not_found(code=exc.reason_code, run_id=run_id) from exc
        self._log_loaded(
            run_id,
            history,
            target_tick=Tick(tick),
            through_sequence=through_sequence,
        )
        if hasattr(history, "engine"):
            raise RuntimeError("observer history retained an engine")
        return history

    def _log_loaded(
        self,
        run_id: str,
        history: FoldedObjectiveHistory,
        *,
        target_tick: Tick | None,
        through_sequence: int | None,
    ) -> None:
        snapshot_tick = (
            None
            if history.result.snapshot_next_tick is None
            else history.result.snapshot_next_tick.value
        )
        _LOGGER.debug(
            "observer_replay_loaded run_id=%s target_tick=%s "
            "snapshot_next_tick=%s event_count=%s through_sequence=%s",
            run_id,
            None if target_tick is None else target_tick.value,
            snapshot_tick,
            len(history.events),
            "-" if through_sequence is None else through_sequence,
        )


def _run_id(run_id: str) -> RunId:
    try:
        return RunId(run_id)
    except (TypeError, ValueError) as exc:
        raise not_found(code="run_not_found", run_id=run_id) from exc


def _layout(layout_id: str) -> ObserverLayoutCatalog:
    try:
        return load_layout(layout_id or DEFAULT_LAYOUT_ID)
    except ObserverLayoutError as exc:
        raise bad_request(code=exc.reason_code) from exc


def _source(
    history: FoldedObjectiveHistory,
    layout: ObserverLayoutCatalog,
    *,
    mode: str,
) -> LiveObserverSource | ReplayObserverSource:
    if mode == "live":
        return LiveObserverSource(
            scene=history.scene,
            events=history.events,
            layout=layout,
            event_schema_version=history.result.event_schema_version,
            projector_version=history.result.projector_version,
        )
    return ReplayObserverSource(
        scene=history.scene,
        events=history.events,
        layout=layout,
        event_schema_version=history.result.event_schema_version,
        projector_version=history.result.projector_version,
    )


def _reject_ahead(
    head_tick: int,
    after_tick: int | None,
    after_sequence: int | None,
    *,
    run_id: str,
) -> None:
    if after_tick is None:
        return
    if after_tick >= head_tick:
        raise conflict(code="cursor_ahead_of_high_water", run_id=run_id)
    del after_sequence


def _point(point: ScreenPoint | None) -> dict[str, float] | None:
    if point is None:
        return None
    return {"x": point.x, "y": point.y}


def _bounds(bounds: VisualBounds | None) -> dict[str, float] | None:
    if bounds is None:
        return None
    return {
        "x": bounds.x,
        "y": bounds.y,
        "width": bounds.width,
        "height": bounds.height,
    }


def _presentation(block: ObserverPresentation | None) -> dict[str, object] | None:
    if block is None:
        return None
    return {
        "screen_position": _point(block.screen_position),
        "visual_bounds": _bounds(block.visual_bounds),
        "theme": block.theme,
        "icon_ref": block.icon_ref,
        "background_ref": block.background_ref,
        "connection_anchors": [
            (neighbor, _point(point)) for neighbor, point in block.connection_anchors
        ],
        "slot_anchors": [_point(point) for point in block.slot_anchors],
    }


def _presentation_mapping(presentation: object | None) -> dict[str, str] | None:
    from observer.presentation import EntityPresentation

    if type(presentation) is not EntityPresentation:
        return None
    return {
        "visual_category": presentation.visual_category,
        "icon_key": presentation.icon_key,
        "size_category": presentation.size_category,
    }


def _event_out(event: ObserverEvent) -> ObserverEventOut:
    return ObserverEventOut.model_validate(event.public_mapping())


def _frame_out(frame: ObserverFrame) -> ObserverFrameOut:
    world = frame.world
    payload = {
        "protocol_version": frame.protocol_version,
        "cursor": {
            "run_id": frame.cursor.run_id,
            "mode": frame.cursor.mode,
            "tick": frame.cursor.tick,
            "protocol_version": frame.cursor.protocol_version,
            "sequence": frame.cursor.sequence,
            "after_tick": frame.cursor.after_tick,
            "after_sequence": frame.cursor.after_sequence,
        },
        "world": {
            "tick": world.tick,
            "revision": world.revision,
            "locations": [
                {
                    "location_id": item.location_id,
                    "name": item.name,
                    "display_name": item.display_name,
                    "neighbor_ids": list(item.neighbor_ids),
                    "presentation": _presentation(item.presentation),
                }
                for item in world.locations
            ],
            "agents": [
                {
                    "entity_id": item.entity_id,
                    "location_id": item.location_id,
                    "life_status": item.life_status,
                    "inventory_ids": list(item.inventory_ids),
                    "measures": {
                        "health": item.measures.health,
                        "hunger": item.measures.hunger,
                        "thirst": item.measures.thirst,
                        "fatigue": item.measures.fatigue,
                        "temperature": item.measures.temperature,
                    },
                    "agent_id": item.agent_id,
                    "presentation_slot": (
                        None
                        if item.presentation_slot is None
                        else {
                            "slot_index": item.presentation_slot.slot_index,
                            "local_x": item.presentation_slot.local_x,
                            "local_y": item.presentation_slot.local_y,
                        }
                    ),
                }
                for item in world.agents
            ],
            "items": [
                {
                    "item_id": item.item_id,
                    "name": item.name,
                    "kind": item.kind,
                    "location_id": item.location_id,
                    "holder_id": item.holder_id,
                    "presentation": _presentation_mapping(item.presentation),
                }
                for item in world.items
            ],
            "resources": [
                {
                    "resource_id": item.resource_id,
                    "name": item.name,
                    "kind": item.kind,
                    "location_id": item.location_id,
                    "quantity": item.quantity,
                    "unit": item.unit,
                    "presentation": _presentation_mapping(item.presentation),
                }
                for item in world.resources
            ],
            "structures": [
                {
                    "structure_id": item.structure_id,
                    "location_id": item.location_id,
                    "kind": item.kind,
                    "integrity": item.integrity,
                    "stored_quantity": item.stored_quantity,
                    "presentation": _presentation_mapping(item.presentation),
                }
                for item in world.structures
            ],
            "weather": [
                {"location_id": item.location_id, "condition": item.condition}
                for item in world.weather
            ],
        },
        "events": None
        if frame.events is None
        else [item.public_mapping() for item in frame.events],
    }
    return ObserverFrameOut.model_validate(payload)


def _manifest_out(manifest: ObserverManifest) -> ObserverManifestOut:
    return ObserverManifestOut(
        protocol_version=manifest.protocol_version,
        layout_schema_version=manifest.layout_schema_version,
        layout_id=manifest.layout_id,
        layout_hash=manifest.layout_hash,
        ordering=manifest.ordering,
        read_only=True,
        event_types=manifest.event_types,
        event_schema_version=manifest.event_schema_version,
        projector_version=manifest.projector_version,
    )


def _relationship_out(
    summary: ObserverRelationshipSummary,
) -> ObserverRelationshipSummaryOut:
    return ObserverRelationshipSummaryOut(
        owner_id=summary.owner_id,
        target_id=summary.target_id,
        protocol_version=summary.protocol_version,
        dimensions=tuple(
            ObserverDimensionScoreOut(dimension=item.dimension, value=item.value)
            for item in summary.dimensions
        ),
    )


__all__ = ["ObserverReadService", "RelationshipScoreSource"]
