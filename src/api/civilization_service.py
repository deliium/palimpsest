"""Read-only objective map service, resolved once and bounded independently."""

from __future__ import annotations

import logging
from typing import Protocol, cast

from api.civilization_cursor import (
    CivilizationCursorCodec,
)
from api.civilization_schemas import (
    CivilizationAvailabilityReason,
    CivilizationCatalogueBoundaryOut,
    CivilizationCatalogueOut,
    CivilizationCatalogueScopeOut,
    CivilizationMapOut,
    CivilizationMarkersOut,
    CivilizationOverlayOut,
    civilization_map_out,
)
from api.errors import (
    ApiError,
    bad_request,
    conflict,
    gone,
    not_found,
    service_unavailable,
)
from simulation.civilization_models import (
    CivilizationCoverage,
    CivilizationCoverageState,
    CivilizationCursor,
    CivilizationError,
    CivilizationEvidenceClass,
    CivilizationLayer,
    CivilizationMarker,
    CivilizationPublicationRef,
    CivilizationScope,
    CivilizationSection,
    CivilizationSourceRef,
    CivilizationWindow,
)
from simulation.civilization_paging import select_civilization_rows
from simulation.civilization_ports import (
    CivilizationPage,
    CivilizationReadBudget,
    CivilizationReadPort,
)
from simulation.civilization_rows import CivilizationCapturedRow
from simulation.models import RunId
from simulation.observer_civilization import project_civilization_map
from simulation.persistence import RunManifest, SimulationRunRepository
from simulation.replay import FoldedObjectiveHistory

__all__ = [
    "ArtifactCivilizationApiService",
    "CivilizationApiService",
    "CivilizationHistoryResolver",
]

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


class ArtifactCivilizationApiService:
    """Bounded read-only catalogue/overlay/marker service over a read port.

    The service validates the persisted run identity, pins one committed
    publication, and maps every storage outcome to a closed API error. It never
    imports experiments, analysis, the publisher, or a live runtime.
    """

    __slots__ = ("_codec", "_reader", "_runs")

    def __init__(
        self,
        reader: CivilizationReadPort,
        codec: CivilizationCursorCodec,
        run_repository: SimulationRunRepository,
    ) -> None:
        self._reader = reader
        self._codec = codec
        self._runs = run_repository

    async def _manifest(self, run_id: str) -> RunManifest:
        try:
            identity = RunId(run_id)
        except (TypeError, ValueError):
            raise bad_request(code="invalid_civilization_query") from None
        try:
            manifest = await self._runs.get_run(identity)
        except Exception:
            _LOG.warning(
                "civilization_run_lookup_failed reason_code=storage_unavailable"
            )
            raise service_unavailable(code="civilization_storage_unavailable") from None
        if manifest is None:
            raise not_found(code="civilization_run_not_found", run_id=run_id)
        return manifest

    def _budget(self, limit: int) -> CivilizationReadBudget:
        budget = CivilizationReadBudget(limit=limit)
        # Reserve a conservative envelope before any row is selected.
        budget.reserve_response(8192)
        return budget

    async def _publication(
        self,
        run_id: str,
        *,
        requested: str | None,
        pinned: CivilizationPublicationRef | None,
        budget: CivilizationReadBudget,
    ) -> CivilizationPublicationRef | None:
        try:
            current = await self._reader.publication(run_id, budget=budget)
        except CivilizationError as exc:
            raise _storage_failure(exc) from None
        if pinned is not None and current != pinned:
            raise gone(code="civilization_publication_gone", run_id=run_id)
        if requested is not None:
            if current is None or current.publication_id != requested:
                raise gone(code="civilization_publication_gone", run_id=run_id)
        return current

    async def catalogue(
        self,
        run_id: str,
        *,
        evidence_class: str,
        owner_id: str | None,
        layer: str | None,
        limit: int,
        cursor: str | None,
    ) -> CivilizationCatalogueOut:
        evidence, selected_layer = _catalogue_scope(evidence_class, owner_id, layer)
        manifest = await self._manifest(run_id)
        world_id = manifest.world_id.value
        budget = self._budget(limit)
        continuation = None
        if cursor is not None:
            continuation = self._codec.decode_catalogue(
                cursor,
                run_id=run_id,
                evidence_class=evidence,
                owner_id=owner_id,
                layer=selected_layer,
                limit=limit,
            )
        publication = await self._publication(
            run_id,
            requested=None,
            pinned=None if continuation is None else continuation.publication,
            budget=budget,
        )
        scope = CivilizationCatalogueScopeOut(
            evidence_class=evidence, owner_id=owner_id, layer=selected_layer
        )
        if publication is None:
            return CivilizationCatalogueOut(
                run_id=run_id,
                world_id=world_id,
                scope=scope,
                publication=None,
                availability="unavailable",
                reason="publication_pending",
                coverage=CivilizationCoverage(
                    CivilizationCoverageState.UNAVAILABLE, "publication_pending"
                ),
                boundaries=(),
                next_cursor=None,
                truncated=False,
            )
        after = None if continuation is None else continuation.after_boundary
        try:
            page = await self._reader.catalogue(
                run_id,
                after_boundary=after,
                publication=publication,
                budget=budget,
            )
        except CivilizationError as exc:
            raise _storage_failure(exc) from None
        if page.world_id not in ("", world_id):
            _LOG.warning("civilization_identity_mismatch reason_code=world_mismatch")
            raise service_unavailable(code="civilization_identity_mismatch")
        boundaries = []
        allowed = _catalogue_layers(evidence, selected_layer)
        for ref in page.boundaries:
            layers = tuple(
                cast(CivilizationLayer, item.layer)
                for item in ref.scopes
                if item.evidence_class is evidence
                and item.owner_id == owner_id
                and item.layer in allowed
            )
            boundaries.append(
                CivilizationCatalogueBoundaryOut(
                    boundary_tick=cast(int, ref.cursor.boundary_tick),
                    revision=ref.cursor.revision,
                    coverage=ref.coverage,
                    layers=tuple(sorted(set(layers), key=lambda item: item.value)),
                )
            )
        next_cursor = None
        if page.next_cursor is not None and boundaries:
            next_cursor = self._codec.encode_catalogue(
                publication,
                run_id=run_id,
                evidence_class=evidence,
                owner_id=owner_id,
                layer=selected_layer,
                after_boundary=boundaries[-1].boundary_tick,
                limit=limit,
            )
        result = CivilizationCatalogueOut(
            run_id=run_id,
            world_id=world_id,
            scope=scope,
            publication=publication,
            availability="available",
            reason=None,
            coverage=CivilizationCoverage(CivilizationCoverageState.COMPLETE),
            boundaries=tuple(boundaries),
            next_cursor=next_cursor,
            truncated=next_cursor is not None,
        )
        _check_response_bytes(result)
        _LOG.debug(
            "civilization_catalogue_fetched ticks=%s returned=%s scanned=%s",
            len(boundaries),
            len(result.boundaries),
            budget.scanned_rows,
        )
        return result

    async def overlays(
        self,
        run_id: str,
        *,
        tick: int,
        layer: str,
        evidence_class: str,
        owner_id: str | None,
        location_id: str | None,
        region_id: str | None,
        entity_id: str | None,
        limit: int,
        cursor: str | None,
        publication_id: str | None,
    ) -> CivilizationOverlayOut:
        if location_id is not None and region_id is not None:
            raise bad_request(code="invalid_civilization_query")
        for value in (location_id, region_id, entity_id, publication_id):
            _optional_identifier(value)
        try:
            scope = CivilizationScope(
                CivilizationLayer(layer),
                CivilizationEvidenceClass(evidence_class),
                owner_id,
            )
        except (TypeError, ValueError):
            raise bad_request(code="invalid_civilization_scope") from None
        manifest = await self._manifest(run_id)
        world_id = manifest.world_id.value
        budget = self._budget(limit)
        continuation = None
        if cursor is not None:
            continuation = self._codec.decode_overlay(
                cursor,
                run_id=run_id,
                world_id=world_id,
                tick=tick,
                scope=scope,
                location_id=location_id,
                region_id=region_id,
                entity_id=entity_id,
                limit=limit,
            )
            if (
                publication_id is not None
                and publication_id != continuation.publication.publication_id
            ):
                raise bad_request(code="invalid_civilization_cursor")
        publication = await self._publication(
            run_id,
            requested=publication_id,
            pinned=None if continuation is None else continuation.publication,
            budget=budget,
        )
        if publication is None:
            return _overlay_unavailable(
                run_id,
                world_id,
                scope,
                tick,
                publication_id,
                reason="publication_pending",
            )
        probe = CivilizationCursor(run_id, world_id, tick, None, tick, 0)
        try:
            ref = await self._reader.exact_snapshot(
                probe, publication=publication, budget=budget
            )
        except CivilizationError as exc:
            if exc.code == "civilization_boundary_missing":
                return _overlay_unavailable(
                    run_id,
                    world_id,
                    scope,
                    tick,
                    publication.publication_id,
                    reason="boundary_not_captured",
                    publication=publication,
                )
            raise _storage_failure(exc) from None
        if scope not in ref.scopes:
            _LOG.debug(
                "civilization_overlay_channel_absent tick=%s layer=%s",
                tick,
                scope.layer.value,
            )
            return _overlay_unavailable(
                run_id,
                world_id,
                scope,
                tick,
                publication.publication_id,
                reason="channel_absent",
                publication=publication,
            )
        resolved = CivilizationCursor(
            run_id,
            world_id,
            ref.cursor.tick,
            None,
            tick,
            ref.cursor.revision,
        )
        if continuation is not None and continuation.cursor != resolved:
            raise gone(code="civilization_context_gone", run_id=run_id)
        after = None if continuation is None else continuation.after_key
        try:
            rows = await self._reader.rows(
                resolved,
                scope,
                publication=publication,
                after_key=after,
                entity_id=entity_id,
                location_id=location_id,
                region_id=region_id,
                budget=budget,
            )
        except CivilizationError as exc:
            if exc.code == "civilization_boundary_missing":
                raise gone(code="civilization_context_gone", run_id=run_id) from None
            raise _storage_failure(exc) from None
        next_cursor = None
        if rows.next_cursor is not None:
            if rows.next_cursor == after:
                raise service_unavailable(code="civilization_read_budget")
            next_cursor = self._codec.encode_overlay(
                publication,
                resolved,
                scope=scope,
                location_id=location_id,
                region_id=region_id,
                entity_id=entity_id,
                after_key=rows.next_cursor,
                limit=limit,
            )
        result = CivilizationOverlayOut(
            run_id=run_id,
            world_id=world_id,
            scope=scope,
            requested_tick=tick,
            requested_publication_id=publication_id,
            publication=publication,
            availability="available",
            reason=None,
            resolved_cursor=resolved,
            window=rows.window,
            coverage=rows.coverage,
            rows=cast(tuple[CivilizationCapturedRow, ...], rows.rows),
            next_cursor=next_cursor,
            truncated=next_cursor is not None,
            source_revision=resolved.revision,
        )
        _check_response_bytes(result)
        _LOG.debug(
            "civilization_overlay_fetched tick=%s layer=%s returned=%s scanned=%s",
            tick,
            scope.layer.value,
            len(result.rows),
            budget.scanned_rows,
        )
        return result

    async def markers(
        self,
        run_id: str,
        *,
        evidence_class: str,
        owner_id: str | None,
        layer: str | None,
        from_tick: int,
        to_tick: int,
        limit: int,
        cursor: str | None,
        publication_id: str | None,
    ) -> CivilizationMarkersOut:
        _optional_identifier(owner_id)
        _optional_identifier(publication_id)
        evidence, selected_layer = _catalogue_scope(evidence_class, owner_id, layer)
        if not 0 <= from_tick <= to_tick or to_tick - from_tick > 4096:
            raise bad_request(code="invalid_civilization_query")
        manifest = await self._manifest(run_id)
        world_id = manifest.world_id.value
        budget = self._budget(limit)
        continuation = None
        if cursor is not None:
            continuation = self._codec.decode_markers(
                cursor,
                run_id=run_id,
                evidence_class=evidence,
                owner_id=owner_id,
                layer=selected_layer,
                from_tick=from_tick,
                to_tick=to_tick,
                limit=limit,
            )
            if (
                publication_id is not None
                and publication_id != continuation.publication.publication_id
            ):
                raise bad_request(code="invalid_civilization_cursor")
        publication = await self._publication(
            run_id,
            requested=publication_id,
            pinned=None if continuation is None else continuation.publication,
            budget=budget,
        )
        scope = CivilizationCatalogueScopeOut(
            evidence_class=evidence, owner_id=owner_id, layer=selected_layer
        )
        window = CivilizationWindow(from_tick, to_tick)
        if publication is None:
            return CivilizationMarkersOut(
                run_id=run_id,
                world_id=world_id,
                scope=scope,
                requested_window=window,
                publication=None,
                availability="unavailable",
                reason="publication_pending",
                markers=(),
                missing_intervals=(),
                coverage=CivilizationCoverage(
                    CivilizationCoverageState.UNAVAILABLE, "publication_pending"
                ),
                next_cursor=None,
                truncated=False,
            )
        start = from_tick
        after_key = None
        if continuation is not None:
            start = continuation.after_tick
            after_key = continuation.after_key
            if after_key is None:
                start += 1
        try:
            page = await self._reader.catalogue(
                run_id,
                after_boundary=None if start == 0 else start - 1,
                publication=publication,
                budget=budget,
            )
        except CivilizationError as exc:
            raise _storage_failure(exc) from None
        if page.world_id not in ("", world_id):
            raise service_unavailable(code="civilization_identity_mismatch")
        markers: list[CivilizationMarker] = []
        processed: list[int] = []
        next_cursor = None
        truncated = False
        for ref in page.boundaries:
            boundary = cast(int, ref.cursor.boundary_tick)
            if boundary < from_tick or boundary >= to_tick:
                continue
            current_after = after_key if boundary == start else None
            remaining = limit - len(markers)
            if remaining <= 0:
                truncated = True
                break
            try:
                selection = await self._reader.markers_at(
                    ref,
                    publication=publication,
                    after_key=current_after,
                    evidence_class=evidence,
                    owner_id=owner_id,
                    layer=selected_layer,
                    limit=remaining,
                    budget=budget,
                )
            except CivilizationError as exc:
                if exc.code == "civilization_read_budget" and processed:
                    truncated = True
                    break
                raise _storage_failure(exc) from None
            markers.extend(selection.markers)
            processed.append(boundary)
            if selection.truncated:
                next_cursor = self._codec.encode_markers(
                    publication,
                    run_id=run_id,
                    evidence_class=evidence,
                    owner_id=owner_id,
                    layer=selected_layer,
                    from_tick=from_tick,
                    to_tick=to_tick,
                    after_tick=boundary,
                    after_key=selection.continuation_after,
                    limit=limit,
                )
                truncated = True
                break
            if len(markers) >= limit:
                last = markers[-1]
                next_cursor = self._codec.encode_markers(
                    publication,
                    run_id=run_id,
                    evidence_class=evidence,
                    owner_id=owner_id,
                    layer=selected_layer,
                    from_tick=from_tick,
                    to_tick=to_tick,
                    after_tick=last.seek_boundary,
                    after_key=last.marker_id,
                    limit=limit,
                )
                truncated = True
                break
            after_key = None
        if not truncated and page.next_cursor is not None:
            following = int(page.next_cursor)
            if following < to_tick:
                if not processed and not markers:
                    raise service_unavailable(code="civilization_read_budget")
                last_tick = processed[-1] if processed else start - 1
                next_cursor = self._codec.encode_markers(
                    publication,
                    run_id=run_id,
                    evidence_class=evidence,
                    owner_id=owner_id,
                    layer=selected_layer,
                    from_tick=from_tick,
                    to_tick=to_tick,
                    after_tick=last_tick,
                    after_key=None,
                    limit=limit,
                )
                truncated = True
        coverage, missing = _marker_coverage(
            from_tick=from_tick,
            to_tick=to_tick,
            scan_start=start,
            processed=tuple(processed),
            truncated=truncated,
        )
        result = CivilizationMarkersOut(
            run_id=run_id,
            world_id=world_id,
            scope=scope,
            requested_window=window,
            publication=publication,
            availability="available",
            reason=None,
            markers=tuple(markers),
            missing_intervals=missing,
            coverage=coverage,
            next_cursor=next_cursor,
            truncated=next_cursor is not None,
        )
        _check_response_bytes(result)
        _LOG.debug(
            "civilization_markers_fetched window=%s..%s returned=%s scanned=%s",
            from_tick,
            to_tick,
            len(result.markers),
            budget.scanned_rows,
        )
        return result


def _storage_failure(exc: CivilizationError) -> ApiError:
    if exc.code == "civilization_publication_gone":
        return gone(code="civilization_publication_gone")
    if exc.code == "civilization_boundary_missing":
        return gone(code="civilization_context_gone")
    if exc.code == "civilization_identity_conflict":
        return service_unavailable(code="civilization_identity_mismatch")
    if exc.code == "civilization_read_budget":
        return service_unavailable(code="civilization_read_budget")
    if exc.code == "civilization_response_budget":
        return service_unavailable(code="civilization_response_budget")
    if exc.code == "civilization_row_too_large":
        return service_unavailable(code="civilization_row_too_large")
    return service_unavailable(code="civilization_storage_unavailable")


def _catalogue_scope(
    evidence_raw: str, owner_id: str | None, layer_raw: str | None
) -> tuple[CivilizationEvidenceClass, CivilizationLayer | None]:
    _optional_identifier(owner_id)
    try:
        evidence = CivilizationEvidenceClass(evidence_raw)
        layer = None if layer_raw is None else CivilizationLayer(layer_raw)
    except (TypeError, ValueError):
        raise bad_request(code="invalid_civilization_scope") from None
    if (evidence is CivilizationEvidenceClass.SUBJECTIVE) != (owner_id is not None):
        raise bad_request(code="invalid_civilization_scope")
    if layer is not None and layer not in _catalogue_layers(evidence, None):
        raise bad_request(code="invalid_civilization_scope")
    return evidence, layer


def _optional_identifier(value: object) -> None:
    if value is None:
        return
    if (
        type(value) is not str
        or not 1 <= len(value) <= 512
        or value != value.strip()
        or any(ord(character) < 32 for character in value)
    ):
        raise bad_request(code="invalid_civilization_query")


def _catalogue_layers(
    evidence: CivilizationEvidenceClass, layer: CivilizationLayer | None
) -> set[CivilizationLayer]:
    if layer is not None:
        return {layer}
    if evidence is CivilizationEvidenceClass.OBJECTIVE:
        return {CivilizationLayer.MIGRATION}
    if evidence is CivilizationEvidenceClass.SUBJECTIVE:
        return {
            CivilizationLayer.TECHNOLOGY,
            CivilizationLayer.SOCIAL_GROUPS,
            CivilizationLayer.INSTITUTIONS,
        }
    return {
        CivilizationLayer.SETTLEMENTS,
        CivilizationLayer.TRADE,
        CivilizationLayer.CULTURE,
        CivilizationLayer.TECHNOLOGY,
        CivilizationLayer.SOCIAL_GROUPS,
        CivilizationLayer.INSTITUTIONS,
    }


def _overlay_unavailable(
    run_id: str,
    world_id: str,
    scope: CivilizationScope,
    tick: int,
    requested_publication_id: str | None,
    *,
    reason: str,
    publication: CivilizationPublicationRef | None = None,
) -> CivilizationOverlayOut:
    return CivilizationOverlayOut(
        run_id=run_id,
        world_id=world_id,
        scope=scope,
        requested_tick=tick,
        requested_publication_id=requested_publication_id,
        publication=publication,
        availability="unavailable",
        reason=cast(CivilizationAvailabilityReason, reason),
        resolved_cursor=None,
        window=None,
        coverage=CivilizationCoverage(
            CivilizationCoverageState.UNAVAILABLE,
            reason,
        ),
        rows=(),
        next_cursor=None,
        truncated=False,
        source_revision=None,
    )


def _marker_coverage(
    *,
    from_tick: int,
    to_tick: int,
    scan_start: int,
    processed: tuple[int, ...],
    truncated: bool,
) -> tuple[CivilizationCoverage, tuple[CivilizationWindow, ...]]:
    if scan_start >= to_tick:
        return CivilizationCoverage(CivilizationCoverageState.COMPLETE), ()
    end = to_tick if not truncated else (processed[-1] + 1 if processed else scan_start)
    if end <= scan_start:
        return (
            CivilizationCoverage(
                CivilizationCoverageState.PARTIAL,
                "capture_limit",
                capture_start=scan_start,
                capture_end=end,
            ),
            (),
        )
    expected = set(range(scan_start, end))
    observed = {tick for tick in processed if scan_start <= tick < end}
    missing = _coalesce_intervals(sorted(expected - observed))
    bounded_missing = missing[:200]
    if not missing and not truncated:
        return CivilizationCoverage(CivilizationCoverageState.COMPLETE), ()
    reason = "capture_gap" if missing else "capture_limit"
    return (
        CivilizationCoverage(
            CivilizationCoverageState.PARTIAL,
            reason,
            capture_start=scan_start,
            capture_end=end,
            missing_intervals=bounded_missing,
        ),
        bounded_missing,
    )


def _coalesce_intervals(ticks: list[int]) -> tuple[CivilizationWindow, ...]:
    intervals: list[CivilizationWindow] = []
    for tick in ticks:
        if intervals and intervals[-1].end_tick == tick:
            intervals[-1] = CivilizationWindow(intervals[-1].start_tick, tick + 1)
        else:
            intervals.append(CivilizationWindow(tick, tick + 1))
    return tuple(intervals)


def _check_response_bytes(model: object) -> None:
    dump = getattr(model, "model_dump_json", None)
    if dump is not None and len(dump().encode("utf-8")) > MAX_MAP_RESPONSE_BYTES:
        raise service_unavailable(code="civilization_response_budget")
