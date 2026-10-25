"""Compose replay folds into read-only observer responses. Drops every engine."""

from __future__ import annotations

import logging
from typing import NoReturn, Protocol

from api.errors import (
    ApiError,
    bad_request,
    conflict,
    internal,
    not_found,
    service_unavailable,
)
from api.observer_demographic_schemas import (
    DemographicAgentRowOut,
    DemographicCohortRowOut,
    DemographicGenerationRowOut,
    DemographicPopulationOut,
    DemographicStageRowOut,
    GenerationMarkerRowOut,
    ObserverDemographicsOut,
    ObserverGenerationMarkersOut,
)
from api.observer_replay_context import (
    ObserverReplayContextError,
    ObserverReplayContextSource,
)
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
from observer.strategy_audit import StrategyAuditOverlay, project_strategy_audit_overlay
from observer.version import DEFAULT_LAYOUT_ID, OBSERVER_PROTOCOL_VERSION
from simulation.branching import BranchLineage
from simulation.clock import Tick
from simulation.models import RunId
from simulation.observer_demographics import (
    DemographicsError,
    decode_group_cursor,
    encode_group_cursor,
    project_demographics,
    project_generation_markers,
)
from simulation.persistence import BranchLineageRepository, ReplayStatus
from simulation.replay import (
    FoldedObjectiveHistory,
    ObserverHistoryError,
    ObserverReplayContext,
    ReplayService,
    scene_at_tick,
    scene_through_event,
)

_LOGGER = logging.getLogger("api.observer")
_MAX_DEMOGRAPHIC_RESPONSE_BYTES = 1_048_576


class RelationshipScoreSource(Protocol):
    async def read_relationship_dimension_values(
        self, run_id: str, owner_id: str
    ) -> tuple[tuple[str, str, str, float], ...]: ...


class ObserverReadService:
    """Read-only observer queries. Route handlers must not advance a tick."""

    __slots__ = ("_lineage", "_relationships", "_replay", "_replay_context")

    def __init__(
        self,
        replay: ReplayService,
        relationships: RelationshipScoreSource | None = None,
        lineage: BranchLineageRepository | None = None,
        replay_context: ObserverReplayContextSource | None = None,
    ) -> None:
        if type(replay) is not ReplayService:
            raise TypeError("ObserverReadService requires ReplayService")
        self._replay = replay
        self._relationships = relationships
        self._lineage = lineage
        self._replay_context = replay_context

    @property
    def replay(self) -> ReplayService:
        return self._replay

    async def resolve_objective_history(
        self, run_id: str, *, tick: int | None, through_sequence: int | None
    ) -> FoldedObjectiveHistory:
        """Public detached resolver for independent, cursor-pinned sidecars.

        Preserve trusted replay-context injection and all restoration policy in
        the existing observer path. No live-manager metadata is joined here.
        """
        try:
            return await self._demographic_history(
                run_id, tick=tick, through_sequence=through_sequence
            )
        except ApiError as exc:
            if exc.code != "target_unreachable" or tick is None:
                raise
            # The legacy replay status conflates an unknown run and an ahead
            # target. Disambiguate only this failure path using the same trusted
            # resolver; never use the head as a substitute historical scene.
            head = await self._history(run_id, target_tick=None)
            if tick > head.scene.tick:
                raise conflict(
                    code="cursor_ahead_of_high_water", run_id=run_id
                ) from None
            raise service_unavailable(code="civilization_replay_unavailable") from None

    async def _branch_fields(self, run_id: str) -> dict[str, object]:
        if self._lineage is None:
            return {
                "run_id": run_id,
                "parent_run_id": None,
                "fork_tick": None,
                "intervention_summary": None,
                "branch_id": None,
            }
        loaded = await self._lineage.get_lineage(child_run_id=RunId(run_id))
        if loaded is None or type(loaded) is not BranchLineage:
            return {
                "run_id": run_id,
                "parent_run_id": None,
                "fork_tick": None,
                "intervention_summary": None,
                "branch_id": None,
            }
        summary = (
            f"{loaded.intervention_kind.value}:{loaded.intervention_fingerprint[:12]}"
        )
        return {
            "run_id": run_id,
            "parent_run_id": loaded.parent_run_id.value,
            "fork_tick": loaded.fork_tick,
            "intervention_summary": summary,
            "branch_id": loaded.branch_id,
        }

    async def manifest(self, run_id: str, *, layout_id: str) -> ObserverManifestOut:
        history = await self._history(run_id, target_tick=None)
        layout = _layout(layout_id)
        branch = await self._branch_fields(run_id)
        source = _source(history, layout, mode="live", branch=branch)
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
        branch = await self._branch_fields(run_id)
        source = _source(history, layout, mode=mode, branch=branch)
        return _frame_out(source.frame())

    async def demographics(
        self,
        run_id: str,
        *,
        tick: int | None,
        through_sequence: int | None,
        section: str,
        agent_id: str | None = None,
        after_agent_id: str | None = None,
        after_group_key: str | None = None,
        limit: int = 100,
    ) -> ObserverDemographicsOut:
        """Bounded demographic rows with exact full-population scalar totals."""
        if section not in {"agents", "cohorts", "generations"}:
            raise bad_request(code="demographics_unknown_section", run_id=run_id)
        if tick is None and (after_agent_id is not None or after_group_key is not None):
            raise bad_request(code="incomplete_demographic_cursor", run_id=run_id)
        history = await self._demographic_history(
            run_id, tick=tick, through_sequence=through_sequence
        )
        requested_tick = history.scene.tick if tick is None else tick
        decoded_group_key: str | None = None
        if after_group_key is not None:
            try:
                decoded_group_key = decode_group_cursor(
                    after_group_key,
                    section=section,
                    tick=requested_tick,
                    sequence=through_sequence,
                )
            except DemographicsError as exc:
                raise bad_request(code=exc.reason_code, run_id=run_id) from exc
        try:
            projection = project_demographics(
                history.scene,
                requested_tick=requested_tick,
                through_sequence=through_sequence,
                section=section,
                agent_id=agent_id,
                after_agent_id=after_agent_id,
                after_group_key=decoded_group_key,
                limit=limit,
            )
        except DemographicsError as exc:
            raise bad_request(code=exc.reason_code, run_id=run_id) from exc
        next_after_group_key = None
        if projection.next_after_group_key is not None:
            next_after_group_key = encode_group_cursor(
                section=section,
                tick=requested_tick,
                sequence=through_sequence,
                key=projection.next_after_group_key,
            )
        population = projection.population
        response = ObserverDemographicsOut(
            run_id=history.scene.run_id,
            requested_tick=requested_tick,
            requested_through_sequence=through_sequence,
            resolved_tick=history.scene.tick,
            revision=history.scene.revision,
            availability=projection.availability,  # type: ignore[arg-type]
            reason_code=projection.reason_code,  # type: ignore[arg-type]
            section=projection.section,  # type: ignore[arg-type]
            selection_state=projection.selection_state,  # type: ignore[arg-type]
            population=(
                None
                if population is None
                else DemographicPopulationOut(
                    living=population.living,
                    admitted=population.admitted,
                    dead=population.dead,
                    max_generation_index=population.max_generation_index,
                )
            ),
            stage_rows=tuple(
                DemographicStageRowOut(
                    stage=row.stage,
                    life_status=row.life_status,  # type: ignore[arg-type]
                    count=row.count,
                )
                for row in projection.stage_rows
            ),
            stage_counts_truncated=projection.stage_counts_truncated,
            agents=tuple(
                DemographicAgentRowOut(
                    agent_id=row.agent_id,
                    entity_id=row.entity_id,
                    entry_tick=row.entry_tick,
                    generation_index=row.generation_index,
                    cohort_id=row.cohort_id,
                    stage=row.stage,
                    dependency_status=row.dependency_status,  # type: ignore[arg-type]
                    life_status=row.life_status,  # type: ignore[arg-type]
                    age_ticks=row.age_ticks,
                    age_reason_code=row.age_reason_code,  # type: ignore[arg-type]
                )
                for row in projection.agents
            ),
            cohorts=tuple(
                DemographicCohortRowOut(
                    generation_index=row.generation_index,
                    entry_tick=row.entry_tick,
                    cohort_id=row.cohort_id,
                    admitted=row.admitted,
                    living=row.living,
                    dead=row.dead,
                )
                for row in projection.cohorts
            ),
            generations=tuple(
                DemographicGenerationRowOut(
                    generation_index=row.generation_index,
                    admitted=row.admitted,
                    living=row.living,
                    dead=row.dead,
                )
                for row in projection.generations
            ),
            next_after_agent_id=projection.next_after_agent_id,
            next_after_group_key=next_after_group_key,
            limit=projection.limit,
        )
        _enforce_response_ceiling(response, run_id=run_id)
        _LOGGER.debug(
            "demographics_fetched run_id=%s section=%s tick=%s through_sequence=%s "
            "selection_state=%s availability=%s",
            run_id,
            section,
            requested_tick,
            None if through_sequence is None else through_sequence,
            projection.selection_state,
            projection.availability,
        )
        return response

    async def generation_markers(
        self,
        run_id: str,
        *,
        tick: int,
        from_tick: int | None = None,
        to_tick: int | None = None,
        after_generation_index: int | None = None,
        limit: int = 100,
    ) -> ObserverGenerationMarkersOut:
        """Admitted-generation markers at one sealed full boundary."""
        if tick < 0:
            raise bad_request(code="invalid_marker_tick", run_id=run_id)
        history = await self._history(run_id, target_tick=Tick(tick))
        try:
            projection = project_generation_markers(
                history.scene,
                requested_tick=tick,
                from_tick=from_tick,
                to_tick=to_tick,
                after_generation_index=after_generation_index,
                limit=limit,
            )
        except DemographicsError as exc:
            raise bad_request(code=exc.reason_code, run_id=run_id) from exc
        response = ObserverGenerationMarkersOut(
            run_id=history.scene.run_id,
            requested_tick=tick,
            resolved_tick=history.scene.tick,
            revision=history.scene.revision,
            availability=projection.availability,  # type: ignore[arg-type]
            reason_code=projection.reason_code,  # type: ignore[arg-type]
            markers=tuple(
                GenerationMarkerRowOut(
                    generation_index=row.generation_index,
                    first_entry_tick=row.first_entry_tick,
                    seek_tick=row.seek_tick,
                    admitted_count=row.admitted_count,
                    label_code=row.label_code,  # type: ignore[arg-type]
                )
                for row in projection.markers
            ),
            next_after_generation_index=projection.next_after_generation_index,
            limit=projection.limit,
        )
        _enforce_response_ceiling(response, run_id=run_id)
        _LOGGER.debug(
            "generation_markers_fetched run_id=%s tick=%s count=%s availability=%s",
            run_id,
            tick,
            len(response.markers),
            projection.availability,
        )
        return response

    async def _demographic_history(
        self, run_id: str, *, tick: int | None, through_sequence: int | None
    ) -> FoldedObjectiveHistory:
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
            return await self._history_through_event(
                run_id, tick=tick, through_sequence=through_sequence
            )
        return await self._history(
            run_id, target_tick=None if tick is None else Tick(tick)
        )

    async def events(
        self,
        run_id: str,
        *,
        after_tick: int | None,
        after_sequence: int | None,
        limit: int,
        layout_id: str,
        agent_id: str | None = None,
        event_type: str | None = None,
        location_id: str | None = None,
        catch_up: bool = False,
    ) -> ObserverEventPageOut:
        """Page adapted observer events with optional presentation filters.

        ``agent_id`` matches adapted ``actor_id`` **or** ``target_id`` (no
        protocol bump). Journal keyset filtering uses the same actor|target
        semantics when supported.
        """
        _layout(layout_id)
        typed = _run_id(run_id)
        history = await self._history(run_id, target_tick=None)
        _reject_ahead(history.scene.tick, after_tick, after_sequence, run_id=run_id)
        cursor_tick = 0 if after_tick is None else after_tick
        cursor_sequence = -1 if after_sequence is None else after_sequence
        filter_codes: list[str] = []
        if agent_id is not None:
            filter_codes.append("agent_id")
            _LOGGER.debug(
                "[api.observer] agent_match_mode=actor_or_target run_id=%s",
                run_id,
            )
        if event_type is not None:
            filter_codes.append("event_type")
        if location_id is not None:
            filter_codes.append("location_id")

        adapted: list[ObserverEvent] = []
        pages = 0
        needs_scan = (
            catch_up
            or location_id is not None
            or event_type is not None
            or agent_id is not None
        )
        max_pages = 64 if needs_scan else 1
        domain_event_type = _domain_event_type_filter(event_type)
        while pages < max_pages and len(adapted) < limit:
            page = await self._replay.read_event_keyset_page(
                typed,
                after_tick=cursor_tick,
                after_sequence=cursor_sequence,
                limit=limit,
                actor_id=agent_id,
                event_type=domain_event_type,
            )
            pages += 1
            if not page.events:
                break
            for event in page.events:
                item = adapt_event(event)
                if event_type is not None and not _event_matches_type(item, event_type):
                    continue
                if location_id is not None and not _event_matches_location(
                    item, location_id
                ):
                    continue
                if agent_id is not None and not _event_matches_agent(item, agent_id):
                    continue
                adapted.append(item)
                if len(adapted) >= limit:
                    break
            last = page.events[-1]
            cursor_tick = last.tick
            cursor_sequence = last.sequence
            if len(page.events) < limit and not needs_scan:
                break
            if not needs_scan:
                break

        if catch_up:
            _LOGGER.info(
                "[api.observer] reconnect_catchup run_id=%s pages=%s events=%s",
                run_id,
                pages,
                len(adapted),
            )
        if filter_codes:
            _LOGGER.debug(
                "[api.observer] events_filtered run_id=%s limit=%s "
                "filter_codes=%s result_count=%s",
                run_id,
                limit,
                ",".join(filter_codes),
                len(adapted),
            )
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
        limit: int = 100,
    ) -> ObserverTickPageOut:
        if to_tick < from_tick:
            raise bad_request(code="invalid_tick_range", run_id=run_id)
        if limit < 1:
            raise bad_request(code="invalid_page_limit", run_id=run_id)
        typed = _run_id(run_id)
        page = await self._replay.read_event_page(
            typed,
            from_tick=Tick(from_tick),
            to_tick=Tick(to_tick),
            limit=limit,
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
        branch = await self._branch_fields(run_id)
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
            parent_run_id=branch["parent_run_id"],  # type: ignore[arg-type]
            fork_tick=branch["fork_tick"],  # type: ignore[arg-type]
            intervention_summary=branch["intervention_summary"],  # type: ignore[arg-type]
            branch_id=branch["branch_id"],  # type: ignore[arg-type]
        )

    async def strategy_audit_overlay(
        self,
        run_id: str,
        *,
        audits: tuple[object, ...],
        agent_entity_ids: dict[str, str] | None = None,
    ) -> StrategyAuditOverlay:
        """Project ANALYTICAL per-event strategy categories from committed events."""
        history = await self._history(run_id, target_tick=None)
        overlay = project_strategy_audit_overlay(
            audits,
            history.events,
            agent_entity_ids=agent_entity_ids,
        )
        _LOGGER.debug(
            "strategy_audit_projected count=%s run_id=%s",
            overlay.count,
            run_id,
        )
        return overlay

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
        context, context_error = await self._resolve_replay_context(run_id)
        try:
            history = await scene_at_tick(
                self._replay, typed, target_tick=target_tick, context=context
            )
        except ObserverHistoryError as exc:
            _LOGGER.error("observer_replay_failed reason_code=%s", exc.reason_code)
            _raise_context_or_history(
                context_error,
                exc,
                run_id=run_id,
            )
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
        context, context_error = await self._resolve_replay_context(run_id)
        try:
            history = await scene_through_event(
                self._replay,
                typed,
                tick=Tick(tick),
                through_sequence=through_sequence,
                context=context,
            )
        except ObserverHistoryError as exc:
            _LOGGER.error("observer_replay_failed reason_code=%s", exc.reason_code)
            if exc.reason_code == "observer_event_not_found":
                raise not_found(code="observer_event_not_found", run_id=run_id) from exc
            if exc.reason_code == "target_unreachable":
                raise conflict(
                    code="cursor_ahead_of_high_water", run_id=run_id
                ) from exc
            _raise_context_or_history(
                context_error,
                exc,
                run_id=run_id,
            )
        self._log_loaded(
            run_id,
            history,
            target_tick=Tick(tick),
            through_sequence=through_sequence,
        )
        if hasattr(history, "engine"):
            raise RuntimeError("observer history retained an engine")
        return history

    async def _resolve_replay_context(
        self, run_id: str
    ) -> tuple[ObserverReplayContext | None, ObserverReplayContextError | None]:
        if self._replay_context is None:
            return None, None
        try:
            context = await self._replay_context.read_context(run_id)
        except ObserverReplayContextError as exc:
            _LOGGER.warning(
                "observer_replay_context_rejected run_id=%s reason_code=%s",
                run_id,
                exc.reason_code,
            )
            return None, exc
        if context is None:
            return None, ObserverReplayContextError(
                "observer_replay_context_unavailable"
            )
        return context, None

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


def _raise_context_or_history(
    context_error: ObserverReplayContextError | None,
    history_error: ObserverHistoryError,
    *,
    run_id: str,
) -> NoReturn:
    """Map a restore failure to the stored-context problem when relevant."""
    if (
        context_error is not None
        and history_error.result.status is ReplayStatus.STREAM_DISCONTINUITY
    ):
        raise service_unavailable(code=context_error.reason_code) from history_error
    raise not_found(code=history_error.reason_code, run_id=run_id) from history_error


def _enforce_response_ceiling(response: object, *, run_id: str) -> None:
    payload = response.model_dump_json()  # type: ignore[attr-defined]
    if len(payload.encode("utf-8")) > _MAX_DEMOGRAPHIC_RESPONSE_BYTES:
        _LOGGER.warning(
            "observer_projection_response_too_large run_id=%s bytes=%s",
            run_id,
            len(payload.encode("utf-8")),
        )
        raise internal(code="observer_demographics_response_too_large")


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
    branch: dict[str, object] | None = None,
) -> LiveObserverSource | ReplayObserverSource:
    fields = branch or {"run_id": history.scene.run_id}
    common = {
        "scene": history.scene,
        "events": history.events,
        "layout": layout,
        "event_schema_version": history.result.event_schema_version,
        "projector_version": history.result.projector_version,
        "run_id": str(fields.get("run_id") or history.scene.run_id),
        "parent_run_id": fields.get("parent_run_id"),
        "fork_tick": fields.get("fork_tick"),
        "intervention_summary": fields.get("intervention_summary"),
        "branch_id": fields.get("branch_id"),
    }
    if mode == "live":
        return LiveObserverSource(**common)  # type: ignore[arg-type]
    return ReplayObserverSource(**common)  # type: ignore[arg-type]


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


def _presentation_mapping(presentation: object | None) -> dict[str, str | None] | None:
    from observer.presentation import EntityPresentation

    if type(presentation) is not EntityPresentation:
        return None
    payload: dict[str, str | None] = {
        "visual_category": presentation.visual_category,
        "icon_key": presentation.icon_key,
        "size_category": presentation.size_category,
    }
    if presentation.display_label is not None:
        payload["display_label"] = presentation.display_label
    return payload


def _domain_event_type_filter(event_type: str | None) -> str | None:
    """Map observer semantic types to indexed domain ``event_type`` when possible."""
    if event_type is None:
        return None
    from observer.version import SEMANTIC_TYPE_BY_KIND

    for domain_kind, semantic in SEMANTIC_TYPE_BY_KIND.items():
        if event_type == semantic or event_type == domain_kind:
            return domain_kind
    return event_type


def _event_matches_type(event: ObserverEvent, event_type: str) -> bool:
    return event_type in {event.type, event.domain_kind}


def _event_matches_location(event: ObserverEvent, location_id: str) -> bool:
    return location_id in {
        event.origin_location_id,
        event.destination_location_id,
    }


def _event_matches_agent(event: ObserverEvent, agent_id: str) -> bool:
    """Presentation filter: entity id equals adapted actor **or** target."""
    return agent_id in {event.actor_id, event.target_id}


def _event_out(event: ObserverEvent) -> ObserverEventOut:
    return ObserverEventOut.model_validate(event.public_mapping())


def _frame_out(frame: ObserverFrame) -> ObserverFrameOut:
    from dataclasses import asdict

    world = frame.world
    payload: dict[str, object] = {
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
                    **(
                        {"region_id": item.region_id, "region_label": item.region_label}
                        if item.region_id is not None
                        else {}
                    ),
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
                    **(
                        {"journey": asdict(item.journey)}
                        if item.journey is not None
                        else {}
                    ),
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
            "artifacts": [
                {
                    "artifact_id": item.artifact_id,
                    "kind": item.kind,
                    "author_id": item.author_id,
                    "created_tick": item.created_tick,
                    "content_revision": item.content_revision,
                    "location_id": item.location_id,
                    "holder_id": item.holder_id,
                    "marks": list(item.marks),
                    "presentation": _presentation_mapping(item.presentation),
                }
                for item in world.artifacts
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
    if world.season is not None:
        world_payload = payload["world"]
        assert isinstance(world_payload, dict)
        world_payload["season"] = world.season
        world_payload["temperature_bands"] = [
            {"location_id": item.location_id, "band": item.band}
            for item in world.temperature_bands
        ]
        world_payload["hazards"] = [
            {
                "location_id": item.location_id,
                "hazard_kind": item.hazard_kind,
                "remaining_ticks": item.remaining_ticks,
            }
            for item in world.hazards
        ]
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
        run_id=manifest.run_id,
        parent_run_id=manifest.parent_run_id,
        fork_tick=manifest.fork_tick,
        intervention_summary=manifest.intervention_summary,
        branch_id=manifest.branch_id,
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
