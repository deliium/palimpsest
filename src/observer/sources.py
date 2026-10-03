"""Live and replay observer sources. Neither type calls the world engine."""

from __future__ import annotations

import logging
from collections.abc import Sequence

from observer.adapt import adapt_events
from observer.contracts import ObserverEvent, ObserverFrame, ObserverManifest
from observer.layout import ObserverLayoutCatalog
from observer.project import project_frame
from observer.version import OBSERVER_PROTOCOL_VERSION
from simulation.observer_facts import ObjectiveScene
from world.events import WorldEvent

_LOGGER = logging.getLogger("observer.sources")


def _build_manifest(
    *,
    layout: ObserverLayoutCatalog,
    event_schema_version: int,
    projector_version: str,
    run_id: str,
    parent_run_id: str | None,
    fork_tick: int | None,
    intervention_summary: str | None,
    branch_id: str | None,
) -> ObserverManifest:
    return ObserverManifest(
        protocol_version=OBSERVER_PROTOCOL_VERSION,
        layout_schema_version=layout.schema_version,
        layout_id=layout.layout_id,
        layout_hash=layout.content_hash(),
        event_schema_version=event_schema_version,
        projector_version=projector_version,
        run_id=run_id,
        parent_run_id=parent_run_id,
        fork_tick=fork_tick,
        intervention_summary=intervention_summary,
        branch_id=branch_id,
    )


class ReplayObserverSource:
    """Historical source over a folded scene and the events that built it."""

    __slots__ = (
        "_branch_id",
        "_events",
        "_fork_tick",
        "_intervention_summary",
        "_layout",
        "_parent_run_id",
        "_projector_version",
        "_run_id",
        "_scene",
        "_schema_version",
    )

    def __init__(
        self,
        *,
        scene: ObjectiveScene,
        events: Sequence[WorldEvent],
        layout: ObserverLayoutCatalog,
        event_schema_version: int,
        projector_version: str,
        run_id: str | None = None,
        parent_run_id: str | None = None,
        fork_tick: int | None = None,
        intervention_summary: str | None = None,
        branch_id: str | None = None,
    ) -> None:
        if type(scene) is not ObjectiveScene:
            raise TypeError("ReplayObserverSource requires ObjectiveScene")
        self._scene = scene
        self._events = tuple(events)
        self._layout = layout
        self._schema_version = event_schema_version
        self._projector_version = projector_version
        self._run_id = scene.run_id if run_id is None else run_id
        self._parent_run_id = parent_run_id
        self._fork_tick = fork_tick
        self._intervention_summary = intervention_summary
        self._branch_id = branch_id

    def manifest(self) -> ObserverManifest:
        return _build_manifest(
            layout=self._layout,
            event_schema_version=self._schema_version,
            projector_version=self._projector_version,
            run_id=self._run_id,
            parent_run_id=self._parent_run_id,
            fork_tick=self._fork_tick,
            intervention_summary=self._intervention_summary,
            branch_id=self._branch_id,
        )

    def frame(self) -> ObserverFrame:
        _LOGGER.debug(
            "observer_source_frame mode=%s tick=%s",
            "replay",
            self._scene.tick,
        )
        return project_frame(
            self._scene,
            self._layout,
            mode="replay",
            events=adapt_events(self._events),
        )

    def events_after(
        self, after_tick: int, after_sequence: int, limit: int
    ) -> tuple[ObserverEvent, ...]:
        selected = [
            event
            for event in adapt_events(self._events)
            if (event.tick, event.sequence) > (after_tick, after_sequence)
        ]
        return tuple(selected[:limit])


class LiveObserverSource:
    """Live source over the latest committed scene supplied by the caller."""

    __slots__ = (
        "_branch_id",
        "_events",
        "_fork_tick",
        "_intervention_summary",
        "_layout",
        "_parent_run_id",
        "_projector_version",
        "_run_id",
        "_scene",
        "_schema_version",
    )

    def __init__(
        self,
        *,
        scene: ObjectiveScene,
        events: Sequence[WorldEvent],
        layout: ObserverLayoutCatalog,
        event_schema_version: int,
        projector_version: str,
        run_id: str | None = None,
        parent_run_id: str | None = None,
        fork_tick: int | None = None,
        intervention_summary: str | None = None,
        branch_id: str | None = None,
    ) -> None:
        if type(scene) is not ObjectiveScene:
            raise TypeError("LiveObserverSource requires ObjectiveScene")
        self._scene = scene
        self._events = tuple(events)
        self._layout = layout
        self._schema_version = event_schema_version
        self._projector_version = projector_version
        self._run_id = scene.run_id if run_id is None else run_id
        self._parent_run_id = parent_run_id
        self._fork_tick = fork_tick
        self._intervention_summary = intervention_summary
        self._branch_id = branch_id

    def manifest(self) -> ObserverManifest:
        return _build_manifest(
            layout=self._layout,
            event_schema_version=self._schema_version,
            projector_version=self._projector_version,
            run_id=self._run_id,
            parent_run_id=self._parent_run_id,
            fork_tick=self._fork_tick,
            intervention_summary=self._intervention_summary,
            branch_id=self._branch_id,
        )

    def frame(self) -> ObserverFrame:
        _LOGGER.debug(
            "observer_source_frame mode=%s tick=%s",
            "live",
            self._scene.tick,
        )
        return project_frame(
            self._scene,
            self._layout,
            mode="live",
            events=adapt_events(self._events),
        )

    def events_after(
        self, after_tick: int, after_sequence: int, limit: int
    ) -> tuple[ObserverEvent, ...]:
        selected = [
            event
            for event in adapt_events(self._events)
            if (event.tick, event.sequence) > (after_tick, after_sequence)
        ]
        return tuple(selected[:limit])
