"""Separate read, publication and finalized-capture ports and hard budgets.

Read reservations happen before opening/decoding files. Cache hits still charge
decoded/scanned rows. No HTTP-controlled producer budget exists.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol, TypeVar

from simulation.civilization_models import (
    CivilizationCoverage,
    CivilizationCursor,
    CivilizationError,
    CivilizationEvidenceClass,
    CivilizationLayer,
    CivilizationMarker,
    CivilizationPublicationRef,
    CivilizationScope,
    CivilizationSection,
    CivilizationWindow,
    _count,
)
from simulation.civilization_rows import (
    CivilizationCapturedRow,
    CivilizationMapRow,
    _map_section,
)

__all__ = [
    "CIVILIZATION_MAX_BOUNDARIES",
    "CIVILIZATION_MAX_BOUNDARY_BYTES",
    "CIVILIZATION_MAX_CAPTURE_BYTES",
    "CIVILIZATION_MAX_METADATA_BYTES",
    "CIVILIZATION_MAX_RETAINED_ROWS",
    "CIVILIZATION_MAX_SHARD_BYTES",
    "CIVILIZATION_MAX_SHARD_ROWS",
    "CivilizationBoundaryPublication",
    "CivilizationBoundaryRef",
    "CivilizationBoundarySink",
    "CivilizationCataloguePage",
    "CivilizationFinalizedInput",
    "CivilizationMarkerSelection",
    "CivilizationPage",
    "CivilizationPublicationPort",
    "CivilizationReadBudget",
    "CivilizationReadPort",
    "CivilizationReadReservation",
]

_LOG = logging.getLogger(__name__)
CIVILIZATION_MAX_BOUNDARIES = 10_000
CIVILIZATION_MAX_RETAINED_ROWS = 1_000_000
CIVILIZATION_MAX_CAPTURE_BYTES = 256 * 1024 * 1024
CIVILIZATION_MAX_BOUNDARY_BYTES = 64 * 1024 * 1024
CIVILIZATION_MAX_METADATA_BYTES = 64 * 1024
CIVILIZATION_MAX_SHARD_BYTES = 1024 * 1024
CIVILIZATION_MAX_SHARD_ROWS = 200


@dataclass(frozen=True, slots=True)
class CivilizationReadReservation:
    source_bytes: int

    def __post_init__(self) -> None:
        _count(self.source_bytes)

    def require_actual_bytes(self, actual: int) -> None:
        if _count(actual) > self.source_bytes:
            raise CivilizationError("civilization_storage_corrupt")


class CivilizationReadBudget:
    """Hard per-request physical, decoded and serialized allowances."""

    __slots__ = (
        "_limit",
        "_physical_bytes",
        "_physical_files",
        "_response_bytes",
        "_returned_rows",
        "_scanned_rows",
    )

    def __init__(self, *, limit: int = 100) -> None:
        if not 1 <= _count(limit) <= 200:
            raise CivilizationError()
        self._limit = limit
        self._physical_files = self._physical_bytes = self._scanned_rows = 0
        self._response_bytes = self._returned_rows = 0

    @property
    def limit(self) -> int:
        return self._limit

    @property
    def physical_files(self) -> int:
        return self._physical_files

    @property
    def physical_bytes(self) -> int:
        return self._physical_bytes

    @property
    def scanned_rows(self) -> int:
        return self._scanned_rows

    @property
    def response_bytes(self) -> int:
        return self._response_bytes

    @property
    def returned_rows(self) -> int:
        return self._returned_rows

    def reserve_file(
        self, source_bytes: int, *, metadata: bool = False
    ) -> CivilizationReadReservation:
        size = _count(source_bytes)
        if type(metadata) is not bool:
            raise CivilizationError()
        file_cap = (
            CIVILIZATION_MAX_METADATA_BYTES
            if metadata
            else CIVILIZATION_MAX_SHARD_BYTES
        )
        if size > file_cap:
            raise CivilizationError("civilization_storage_corrupt")
        if self._physical_files == 16 or self._physical_bytes + size > 12 * 1024 * 1024:
            raise CivilizationError("civilization_read_budget")
        self._physical_files += 1
        self._physical_bytes += size
        _LOG.debug(
            "civilization_read_reserved files=%s byte_count=%s",
            self._physical_files,
            self._physical_bytes,
        )
        return CivilizationReadReservation(size)

    def reserve_scan(self, row_count: int) -> None:
        """Called before decoding, including previously cached row objects."""
        count = _count(row_count)
        if self._scanned_rows + count > 2_000:
            raise CivilizationError("civilization_read_budget")
        self._scanned_rows += count

    def reserve_response(self, byte_count: int, *, rows: int = 0) -> None:
        """Charge envelope first; charge a row before advancing its key."""
        size, count = _count(byte_count), _count(rows)
        if (
            self._response_bytes + size > 1024 * 1024
            or self._returned_rows + count > self._limit
        ):
            raise CivilizationError("civilization_response_budget")
        self._response_bytes += size
        self._returned_rows += count


@dataclass(frozen=True, slots=True)
class CivilizationBoundaryRef:
    cursor: CivilizationCursor
    manifest_digest: str
    scopes: tuple[CivilizationScope, ...]
    coverage: CivilizationCoverage

    def __post_init__(self) -> None:
        from simulation.civilization_codec import validate_civilization_value

        validate_civilization_value(self)
        CivilizationPublicationRef("validation", self.manifest_digest, "validation")
        if self.cursor.boundary_tick is None:
            raise CivilizationError()


@dataclass(frozen=True, slots=True)
class CivilizationPage:
    requested_cursor: CivilizationCursor
    resolved_cursor: CivilizationCursor
    scope: CivilizationScope
    coverage: CivilizationCoverage
    rows: tuple[CivilizationMapRow | CivilizationCapturedRow | CivilizationMarker, ...]
    next_cursor: str | None
    truncated: bool
    source_revision: int
    publication: CivilizationPublicationRef | None = None
    window: CivilizationWindow | None = None

    def __post_init__(self) -> None:
        from simulation.civilization_codec import validate_civilization_value

        validate_civilization_value(self)
        if (
            self.requested_cursor.run_id != self.resolved_cursor.run_id
            or self.requested_cursor.world_id != self.resolved_cursor.world_id
            or self.source_revision != self.resolved_cursor.revision
            or self.truncated != (self.next_cursor is not None)
        ):
            raise CivilizationError()
        if (
            self.publication is None
            and type(self.scope.layer) is not CivilizationSection
        ):
            raise CivilizationError()
        if type(self.scope.layer) is not CivilizationSection:
            if (
                self.window is None
                or self.resolved_cursor.boundary_tick is None
                or self.window.end_tick > self.resolved_cursor.boundary_tick
            ):
                raise CivilizationError()
        keys: list[str] = []
        for row in self.rows:
            if isinstance(row, CivilizationMarker):
                keys.append(row.marker_id)
                if (
                    self.resolved_cursor.boundary_tick is None
                    or row.seek_boundary > self.resolved_cursor.boundary_tick
                ):
                    raise CivilizationError()
                if (
                    CivilizationScope(row.layer, row.evidence_class, row.owner_id)
                    != self.scope
                ):
                    raise CivilizationError()
            else:
                keys.append(row.context.row_id)
                if hasattr(row, "history"):
                    if (
                        row.history.scope != self.scope
                        or row.history.boundary_tick
                        != self.resolved_cursor.boundary_tick
                        or row.history.window != self.window
                    ):
                        raise CivilizationError()
                elif _map_section(row) is not self.scope.layer:
                    raise CivilizationError("invalid_civilization_scope")
        if keys != sorted(set(keys)):
            raise CivilizationError()


@dataclass(frozen=True, slots=True)
class CivilizationMarkerSelection:
    """One boundary's keyset page; keys are local marker IDs in tick order."""

    markers: tuple[CivilizationMarker, ...]
    continuation_after: str | None
    truncated: bool

    def __post_init__(self) -> None:
        markers = tuple(self.markers)
        if any(type(marker) is not CivilizationMarker for marker in markers):
            raise CivilizationError()
        keys = [marker.marker_id for marker in markers]
        if keys != sorted(set(keys)):
            raise CivilizationError()
        if self.continuation_after is not None and (
            type(self.continuation_after) is not str
            or not 1 <= len(self.continuation_after) <= 512
        ):
            raise CivilizationError()
        if type(self.truncated) is not bool or self.truncated != (
            self.continuation_after is not None
        ):
            raise CivilizationError()
        object.__setattr__(self, "markers", markers)


@dataclass(frozen=True, slots=True)
class CivilizationCataloguePage:
    run_id: str
    world_id: str
    publication: CivilizationPublicationRef
    boundaries: tuple[CivilizationBoundaryRef, ...]
    next_cursor: str | None
    truncated: bool

    def __post_init__(self) -> None:
        from simulation.civilization_codec import validate_civilization_value

        validate_civilization_value(self)
        ticks = [_count(boundary.cursor.boundary_tick) for boundary in self.boundaries]
        if (
            ticks != sorted(set(ticks))
            or self.truncated != (self.next_cursor is not None)
            or any(
                boundary.cursor.run_id != self.run_id
                or boundary.cursor.world_id != self.world_id
                for boundary in self.boundaries
            )
        ):
            raise CivilizationError()


@dataclass(frozen=True, slots=True)
class CivilizationBoundaryPublication:
    cursor: CivilizationCursor
    scopes: tuple[CivilizationScope, ...]
    rows: tuple[CivilizationCapturedRow, ...]
    markers: tuple[CivilizationMarker, ...]

    def __post_init__(self) -> None:
        if (
            type(self.cursor) is not CivilizationCursor
            or self.cursor.boundary_tick is None
        ):
            raise CivilizationError()
        scopes, rows, markers = (
            tuple(self.scopes),
            tuple(self.rows),
            tuple(self.markers),
        )
        if any(type(scope) is not CivilizationScope for scope in scopes):
            raise CivilizationError()
        if len(set(scopes)) != len(scopes):
            raise CivilizationError()
        keys: set[tuple[CivilizationScope, str]] = set()
        for row in rows:
            if (
                row.history.scope not in scopes
                or row.history.boundary_tick != self.cursor.boundary_tick
                or (row.history.scope, row.context.row_id) in keys
            ):
                raise CivilizationError()
            keys.add((row.history.scope, row.context.row_id))
        if len({marker.marker_id for marker in markers}) != len(markers):
            raise CivilizationError()
        if any(marker.seek_boundary != self.cursor.boundary_tick for marker in markers):
            raise CivilizationError()
        object.__setattr__(self, "scopes", scopes)
        object.__setattr__(self, "rows", rows)
        object.__setattr__(self, "markers", markers)


class CivilizationReadPort(Protocol):
    """Read-only consumers cannot publish, repair or seal artifacts."""

    async def publication(
        self, run_id: str, *, budget: CivilizationReadBudget
    ) -> CivilizationPublicationRef | None: ...

    async def catalogue(
        self,
        run_id: str,
        *,
        after_boundary: int | None,
        publication: CivilizationPublicationRef | None,
        budget: CivilizationReadBudget,
    ) -> CivilizationCataloguePage: ...

    async def exact_snapshot(
        self,
        cursor: CivilizationCursor,
        *,
        publication: CivilizationPublicationRef,
        budget: CivilizationReadBudget,
    ) -> CivilizationBoundaryRef: ...

    async def rows(
        self,
        cursor: CivilizationCursor,
        scope: CivilizationScope,
        *,
        publication: CivilizationPublicationRef,
        after_key: str | None,
        entity_id: str | None,
        location_id: str | None = None,
        region_id: str | None = None,
        budget: CivilizationReadBudget,
    ) -> CivilizationPage: ...

    async def markers_at(
        self,
        ref: CivilizationBoundaryRef,
        *,
        publication: CivilizationPublicationRef,
        after_key: str | None,
        evidence_class: CivilizationEvidenceClass,
        owner_id: str | None,
        layer: CivilizationLayer | None,
        limit: int,
        budget: CivilizationReadBudget,
    ) -> CivilizationMarkerSelection: ...


class CivilizationPublicationPort(Protocol):
    async def publish_boundary(
        self, publication_id: str, boundary: CivilizationBoundaryPublication
    ) -> None: ...

    async def seal_catalogue(
        self, run_id: str, publication_id: str
    ) -> CivilizationPublicationRef: ...


class CivilizationFinalizedInput(Protocol):
    """Concrete whitelisted capture input is owned by the capture module."""

    @property
    def cursor(self) -> CivilizationCursor: ...


_Input = TypeVar("_Input", bound=CivilizationFinalizedInput, contravariant=True)


class CivilizationBoundarySink(Protocol[_Input]):
    """Accept only finalized detached inputs, never a live engine."""

    def capture_boundary(self, boundary: _Input) -> bool:
        """Acknowledge retention; refusal is not successful publication."""
        ...
