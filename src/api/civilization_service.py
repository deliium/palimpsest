"""Read-only objective map service, resolved once and bounded independently."""

from __future__ import annotations

import logging
from typing import Protocol

from api.civilization_cursor import CivilizationCursorCodec
from api.civilization_schemas import CivilizationMapOut, civilization_map_out
from api.errors import (
    ApiError,
    bad_request,
    conflict,
    gone,
    not_found,
    service_unavailable,
)
from simulation.civilization_models import (
    CivilizationCursor,
    CivilizationError,
    CivilizationEvidenceClass,
    CivilizationScope,
    CivilizationSection,
    CivilizationSourceRef,
)
from simulation.civilization_paging import select_civilization_rows
from simulation.civilization_ports import CivilizationPage, CivilizationReadBudget
from simulation.models import RunId
from simulation.observer_civilization import project_civilization_map
from simulation.replay import FoldedObjectiveHistory

__all__ = ["CivilizationApiService", "CivilizationHistoryResolver"]

_LOG = logging.getLogger(__name__)
MAX_MAP_RESPONSE_BYTES = 1024 * 1024


class CivilizationHistoryResolver(Protocol):
    async def resolve_objective_history(
        self, run_id: str, *, tick: int | None, through_sequence: int | None
    ) -> FoldedObjectiveHistory: ...


class CivilizationApiService:
    __slots__ = ("_codec", "_history")

    def __init__(
        self, history: CivilizationHistoryResolver, codec: CivilizationCursorCodec
    ) -> None:
        self._history = history
        self._codec = codec

    async def map(
        self,
        run_id: str,
        *,
        section: str = "locations",
        tick: int | None = None,
        through_sequence: int | None = None,
        entity_id: str | None = None,
        limit: int = 100,
        cursor: str | None = None,
    ) -> CivilizationMapOut:
        try:
            RunId(run_id)
            selected = CivilizationSection(section)
            for value in (tick, through_sequence):
                if value is not None and (type(value) is not int or value < 0):
                    raise ValueError()
            if through_sequence is not None and tick is None:
                raise ValueError()
            if entity_id is not None:
                # Route identities are pairs of native IDs and can exceed128.
                CivilizationSourceRef("scene", entity_id, 0)
            budget = CivilizationReadBudget(limit=limit)
        except (TypeError, ValueError):
            raise bad_request(code="invalid_civilization_query") from None
        continuation = (
            None
            if cursor is None
            else self._codec.decode(
                cursor,
                run_id=run_id,
                section=selected,
                entity_id=entity_id,
                limit=limit,
                tick=tick,
                through_sequence=through_sequence,
            )
        )
        try:
            history = await self._history.resolve_objective_history(
                run_id, tick=tick, through_sequence=through_sequence
            )
        except ApiError as exc:
            if continuation is not None and exc.status == 404:
                raise gone(code="civilization_context_gone") from None
            if exc.code == "observer_event_not_found":
                raise conflict(code="cursor_ahead_of_high_water") from None
            if exc.code in {
                "stream_discontinuity",
                "snapshot_corrupt",
                "schema_unsupported",
            }:
                raise service_unavailable(
                    code="civilization_replay_unavailable"
                ) from None
            raise
        except Exception:
            _LOG.warning("civilization_replay_failed reason_code=storage_unavailable")
            raise service_unavailable(code="civilization_replay_unavailable") from None
        scene = history.scene
        if tick is not None:
            supported_ticks = {tick} if through_sequence is None else {tick, tick + 1}
            if scene.tick not in supported_ticks:
                raise service_unavailable(code="civilization_replay_unavailable")
        # A complete event prefix advances world.tick to T+1. It is now a full
        # boundary, not an incomplete private snapshot merely because the input
        # had a last-event resume pair.
        complete = through_sequence is None or (tick is not None and scene.tick > tick)
        resolved = CivilizationCursor(
            run_id,
            scene.world_id,
            scene.tick,
            None if complete else through_sequence,
            scene.tick if complete else None,
            scene.revision,
        )
        if continuation is not None and continuation.cursor != resolved:
            raise gone(code="civilization_context_gone")
        scope = CivilizationScope(selected, CivilizationEvidenceClass.OBJECTIVE)
        after = None if continuation is None else continuation.after_key
        try:
            projection = project_civilization_map(
                scene,
                cursor=resolved,
                section=selected.value,
                entity_id=entity_id,
                after_key=after,
                source_limit=min(2000, limit + 1),
            )
            if entity_id is not None and not projection.rows and after is None:
                if projection.coverage.state.value in {"complete", "partial"}:
                    raise not_found(code="civilization_entity_not_found")
            empty = CivilizationPage(
                resolved,
                resolved,
                scope,
                projection.coverage,
                (),
                None,
                False,
                resolved.revision,
            )
            envelope = civilization_map_out(
                empty, tick=tick, through_sequence=through_sequence
            )
            # Include the largest permitted signed continuation and punctuation.
            # Storage row encodings are conservative relative to HTTP (they also
            # carry type tags); the final serialized envelope is checked below.
            budget.reserve_response(
                len(envelope.model_dump_json().encode("utf-8")) + 8192
            )
            budget.reserve_scan(len(projection.rows))
            selection = select_civilization_rows(
                projection.rows, budget=budget, after_key=after
            )
            truncated = selection.truncated or projection.source_has_more
            last = selection.continuation_after
            if truncated and last is None and selection.rows:
                last = selection.rows[-1].context.row_id
            next_cursor = None
            if truncated:
                if last is None or last == after:
                    raise CivilizationError("civilization_response_budget")
                next_cursor = self._codec.encode(
                    resolved,
                    section=selected,
                    entity_id=entity_id,
                    limit=limit,
                    after_key=last,
                )
            page = CivilizationPage(
                resolved,
                resolved,
                scope,
                projection.coverage,
                selection.rows,
                next_cursor,
                truncated,
                resolved.revision,
            )
            result = civilization_map_out(
                page, tick=tick, through_sequence=through_sequence
            )
            if len(result.model_dump_json().encode("utf-8")) > MAX_MAP_RESPONSE_BYTES:
                raise CivilizationError("civilization_response_budget")
        except CivilizationError as exc:
            _LOG.warning("civilization_map_failed reason_code=%s", exc.code)
            raise service_unavailable(code=exc.code) from None
        except (TypeError, ValueError):
            _LOG.warning(
                "civilization_map_failed reason_code=invalid_civilization_contract"
            )
            raise service_unavailable(code="invalid_civilization_contract") from None
        _LOG.debug(
            "civilization_map_fetched tick=%s section=%s scanned=%s returned=%s",
            scene.tick,
            selected.value,
            budget.scanned_rows,
            len(result.rows),
        )
        return result
