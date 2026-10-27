"""Trusted composition of retained civilization evidence into publications.

This module is the only bridge from capture to analysis. Simulation, API and
persistence never import it, and publication never feeds live cognition.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import cast

from analysis.civilization_overlays import (
    compose_culture_rows,
    compose_group_rows,
    compose_institution_rows,
    compose_markers,
    compose_migration_rows,
    compose_settlement_rows,
    compose_technology_rows,
    compose_trade_rows,
)
from experiments.evidence_sources import CivilizationHistorySource
from simulation.civilization_boundaries import CivilizationBoundaryInput
from simulation.civilization_capture import CivilizationEventBatch
from simulation.civilization_models import (
    CivilizationCursor,
    CivilizationError,
    CivilizationScope,
)
from simulation.civilization_ports import CivilizationBoundaryPublication
from simulation.civilization_rows import CivilizationCapturedRow

__all__ = [
    "CivilizationCapturedHistory",
    "CivilizationPublicationError",
    "compose_civilization_boundary",
    "compose_civilization_boundary_from_source",
    "compose_civilization_history",
]


class CivilizationPublicationError(ValueError):
    """Closed failure codes only; never payload content or exception reprs."""

    def __init__(self, code: str = "publication_failed") -> None:
        if code not in {
            "publication_failed",
            "source_conflict",
            "identity_mismatch",
            "boundary_missing",
        }:
            code = "publication_failed"
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class CivilizationCapturedHistory:
    """Complete captured evidence for one run, ordered by finalized boundary."""

    run_id: str
    world_id: str
    boundaries: tuple[CivilizationBoundaryInput, ...]
    event_batches: tuple[CivilizationEventBatch, ...]

    def __post_init__(self) -> None:
        boundaries = tuple(self.boundaries)
        batches = tuple(self.event_batches)
        for value in (self.run_id, self.world_id):
            if type(value) is not str or not value or value != value.strip():
                raise CivilizationPublicationError("identity_mismatch")
        ticks: list[int] = []
        for boundary in boundaries:
            if type(boundary) is not CivilizationBoundaryInput:
                raise CivilizationPublicationError("publication_failed")
            if (
                boundary.cursor.run_id != self.run_id
                or boundary.cursor.world_id != self.world_id
                or boundary.cursor.boundary_tick is None
            ):
                raise CivilizationPublicationError("identity_mismatch")
            ticks.append(boundary.cursor.boundary_tick)
        if ticks != sorted(set(ticks)):
            raise CivilizationPublicationError("publication_failed")
        for batch in batches:
            if type(batch) is not CivilizationEventBatch:
                raise CivilizationPublicationError("publication_failed")
            if batch.run_id != self.run_id:
                raise CivilizationPublicationError("identity_mismatch")
        if len({batch.tick for batch in batches}) != len(batches):
            raise CivilizationPublicationError("source_conflict")
        object.__setattr__(self, "boundaries", boundaries)
        object.__setattr__(self, "event_batches", batches)
        object.__setattr__(
            self, "event_batches", tuple(sorted(batches, key=lambda item: item.tick))
        )

    @property
    def boundary_ticks(self) -> tuple[int, ...]:
        return tuple(
            sorted(
                boundary.cursor.boundary_tick
                for boundary in self.boundaries
                if boundary.cursor.boundary_tick is not None
            )
        )

    def boundary(self, tick: int) -> CivilizationBoundaryInput:
        for boundary in self.boundaries:
            if boundary.cursor.boundary_tick == tick:
                return boundary
        raise CivilizationPublicationError("boundary_missing")


def compose_civilization_boundary(
    history: CivilizationCapturedHistory, boundary_tick: int
) -> CivilizationBoundaryPublication:
    """Compose exactly one finalized boundary; never substitute a nearest one."""
    if type(history) is not CivilizationCapturedHistory:
        raise CivilizationPublicationError("publication_failed")
    if boundary_tick not in history.boundary_ticks:
        raise CivilizationPublicationError("boundary_missing")
    boundary = history.boundary(boundary_tick)
    prefix = tuple(
        item for item in history.boundaries if item.cursor.tick <= boundary_tick
    )
    try:
        settlements = compose_settlement_rows(prefix, boundary_tick=boundary_tick)
        migration = compose_migration_rows(
            history.event_batches, boundary_tick=boundary_tick
        )
        trade = compose_trade_rows(history.event_batches, boundary_tick=boundary_tick)
        culture = compose_culture_rows(boundary)
        technology = compose_technology_rows(boundary)
        groups = compose_group_rows(boundary)
        institutions = compose_institution_rows(boundary)
        markers = compose_markers(
            prefix, history.event_batches, boundary_tick=boundary_tick
        )
    except CivilizationError:
        raise
    except ValueError as exc:
        code = str(exc)
        raise CivilizationPublicationError(
            "source_conflict" if code == "source_conflict" else "publication_failed"
        ) from None
    rows: tuple[CivilizationCapturedRow, ...] = (
        *settlements,
        *migration,
        *trade,
        *culture,
        *technology,
        *groups,
        *institutions,
    )
    scopes: dict[CivilizationScope, None] = {}
    for row in rows:
        scopes[row.history.scope] = None
    for marker in markers:
        scopes[
            CivilizationScope(marker.layer, marker.evidence_class, marker.owner_id)
        ] = None
    cursor: CivilizationCursor = boundary.cursor
    return CivilizationBoundaryPublication(
        cursor,
        tuple(
            sorted(
                scopes,
                key=lambda scope: (
                    scope.layer.value,
                    scope.evidence_class.value,
                    scope.owner_id or "",
                ),
            )
        ),
        tuple(
            sorted(
                rows,
                key=lambda row: (row.history.scope.layer.value, row.context.row_id),
            )
        ),
        markers,
    )


class _BoundaryPrefix:
    """Re-iterable prefix view that never materializes all captured frames."""

    __slots__ = ("_source", "_through")

    def __init__(self, source: CivilizationHistorySource, through: int) -> None:
        self._source = source
        self._through = through

    def __iter__(self) -> Iterator[CivilizationBoundaryInput]:
        for frame in self._source.iter_boundaries():
            if frame.cursor.tick <= self._through:
                yield frame


class _EventThrough:
    __slots__ = ("_source", "_through")

    def __init__(self, source: CivilizationHistorySource, through: int) -> None:
        self._source = source
        self._through = through

    def __iter__(self) -> Iterator[CivilizationEventBatch]:
        yield from self._source.iter_event_batches(through_tick=self._through)


def compose_civilization_boundary_from_source(
    source: CivilizationHistorySource, boundary_tick: int
) -> CivilizationBoundaryPublication:
    """Compose one exact boundary from ordered source iteration."""
    boundary = source.read_boundary(boundary_tick)
    if boundary is None:
        raise CivilizationPublicationError("boundary_missing")
    if (
        boundary.cursor.run_id != source.run_id
        or boundary.cursor.world_id != source.world_id
        or boundary.cursor.boundary_tick != boundary_tick
    ):
        raise CivilizationPublicationError("identity_mismatch")
    prefix = cast(
        tuple[CivilizationBoundaryInput, ...], _BoundaryPrefix(source, boundary_tick)
    )
    batches = cast(
        tuple[CivilizationEventBatch, ...], _EventThrough(source, boundary_tick)
    )
    try:
        settlements = compose_settlement_rows(prefix, boundary_tick=boundary_tick)
        migration = compose_migration_rows(batches, boundary_tick=boundary_tick)
        trade = compose_trade_rows(batches, boundary_tick=boundary_tick)
        culture = compose_culture_rows(boundary)
        technology = compose_technology_rows(boundary)
        groups = compose_group_rows(boundary)
        institutions = compose_institution_rows(boundary)
        markers = compose_markers(prefix, batches, boundary_tick=boundary_tick)
    except CivilizationError:
        raise
    except ValueError as exc:
        code = str(exc)
        raise CivilizationPublicationError(
            "source_conflict" if code == "source_conflict" else "publication_failed"
        ) from None
    rows: tuple[CivilizationCapturedRow, ...] = (
        *settlements,
        *migration,
        *trade,
        *culture,
        *technology,
        *groups,
        *institutions,
    )
    scopes: dict[CivilizationScope, None] = {}
    for row in rows:
        scopes[row.history.scope] = None
    for marker in markers:
        scopes[
            CivilizationScope(marker.layer, marker.evidence_class, marker.owner_id)
        ] = None
    return CivilizationBoundaryPublication(
        boundary.cursor,
        tuple(
            sorted(
                scopes,
                key=lambda scope: (
                    scope.layer.value,
                    scope.evidence_class.value,
                    scope.owner_id or "",
                ),
            )
        ),
        tuple(
            sorted(
                rows,
                key=lambda row: (row.history.scope.layer.value, row.context.row_id),
            )
        ),
        markers,
    )


def compose_civilization_history(
    history: CivilizationCapturedHistory,
) -> tuple[CivilizationBoundaryPublication, ...]:
    if type(history) is not CivilizationCapturedHistory:
        raise CivilizationPublicationError("publication_failed")
    return tuple(
        compose_civilization_boundary(history, tick) for tick in history.boundary_ticks
    )
