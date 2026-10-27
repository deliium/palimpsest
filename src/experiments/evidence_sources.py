"""Experiment-owned source interfaces over optional append-only evidence.

These adapters deliberately expose ordered iteration and exact boundary reads
instead of an all-history tuple accessor. The filesystem spool remains a byte
store; typed decoding and validation live in ``experiments.evidence_codecs``.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Final, Protocol

from experiments.evidence_codecs import (
    decode_civilization_boundary,
    decode_civilization_event_batch,
    decode_cultural_boundary,
)
from experiments.persistence import EvidenceSpool, EvidenceSpoolStatus
from simulation.civilization_boundaries import CivilizationBoundaryInput
from simulation.civilization_capture import CivilizationEventBatch
from simulation.cultural_evidence import (
    CulturalBoundaryExport,
    CulturalCaptureStatus,
)

__all__ = [
    "CIVILIZATION_BOUNDARY_SPOOL_LANE",
    "CIVILIZATION_EVENT_SPOOL_LANE",
    "CULTURAL_SPOOL_LANE",
    "CivilizationHistorySource",
    "CulturalCaptureSource",
    "MemoryCivilizationHistorySource",
    "MemoryCulturalCaptureSource",
    "SpooledCivilizationHistorySource",
    "SpooledCulturalCaptureSource",
    "boundary_identity",
    "event_identity",
]

CULTURAL_SPOOL_LANE: Final[str] = "cultural"
CIVILIZATION_BOUNDARY_SPOOL_LANE: Final[str] = "civilization_boundary"
CIVILIZATION_EVENT_SPOOL_LANE: Final[str] = "civilization_event"
_DEFAULT_PAGE: Final[int] = 512


def boundary_identity(tick: int) -> str:
    return f"b{tick:012d}"


def event_identity(tick: int) -> str:
    return f"e{tick:012d}"


class CulturalCaptureSource(Protocol):
    """Pinned cultural capture read interface."""

    @property
    def run_id(self) -> str: ...

    @property
    def source_revision(self) -> str: ...

    @property
    def capture_status(self) -> CulturalCaptureStatus: ...

    @property
    def gaps(self) -> tuple[str, ...]: ...

    @property
    def status(self) -> EvidenceSpoolStatus: ...

    def boundary_ticks(self) -> tuple[int, ...]: ...

    def iter_boundaries(
        self, *, after_boundary: int | None = None
    ) -> Iterator[CulturalBoundaryExport]: ...

    def read_boundary(self, tick: int) -> CulturalBoundaryExport | None: ...


class CivilizationHistorySource(Protocol):
    """Pinned civilization capture read interface."""

    @property
    def run_id(self) -> str: ...

    @property
    def world_id(self) -> str: ...

    @property
    def status(self) -> EvidenceSpoolStatus: ...

    def boundary_ticks(self) -> tuple[int, ...]: ...

    def event_ticks(self) -> tuple[int, ...]: ...

    def iter_boundaries(
        self, *, after_boundary: int | None = None
    ) -> Iterator[CivilizationBoundaryInput]: ...

    def read_boundary(self, tick: int) -> CivilizationBoundaryInput | None: ...

    def iter_event_batches(
        self,
        *,
        after_tick: int | None = None,
        through_tick: int | None = None,
    ) -> Iterator[CivilizationEventBatch]: ...

    def read_event_batch(self, tick: int) -> CivilizationEventBatch | None: ...


@dataclass(frozen=True, slots=True)
class MemoryCulturalCaptureSource:
    """Read-only source over an already materialized capture."""

    run_id_value: str
    source_revision: str
    frames: tuple[CulturalBoundaryExport, ...]
    gaps_value: tuple[str, ...]
    capture_status_value: CulturalCaptureStatus
    _by_tick: dict[int, CulturalBoundaryExport] = field(
        init=False, repr=False, compare=False
    )

    def __post_init__(self) -> None:
        by_tick: dict[int, CulturalBoundaryExport] = {}
        for frame in self.frames:
            if type(frame) is not CulturalBoundaryExport:
                raise TypeError("frames must contain CulturalBoundaryExport")
            if frame.run_id != self.run_id_value:
                raise ValueError("cultural_source_run_mismatch")
            if frame.boundary_tick in by_tick:
                raise ValueError("cultural_source_conflict")
            by_tick[frame.boundary_tick] = frame
        object.__setattr__(self, "_by_tick", by_tick)

    @property
    def run_id(self) -> str:
        return self.run_id_value

    @property
    def status(self) -> EvidenceSpoolStatus:
        ticks = sorted(self._by_tick)
        return EvidenceSpoolStatus(
            active=self.capture_status_value.active,
            failed=self.capture_status_value.failed,
            sealed=not self.capture_status_value.active,
            truncated="capture_truncated" in self.gaps_value,
            failure_code=self.capture_status_value.failure_code,
            record_count=len(self._by_tick),
            byte_count=0,
            first_boundary=ticks[0] if ticks else None,
            last_boundary=ticks[-1] if ticks else None,
        )

    @property
    def gaps(self) -> tuple[str, ...]:
        return self.gaps_value

    @property
    def capture_status(self) -> CulturalCaptureStatus:
        return self.capture_status_value

    def boundary_ticks(self) -> tuple[int, ...]:
        return tuple(sorted(self._by_tick))

    def iter_boundaries(
        self, *, after_boundary: int | None = None
    ) -> Iterator[CulturalBoundaryExport]:
        for tick in sorted(self._by_tick):
            if after_boundary is not None and tick <= after_boundary:
                continue
            yield self._by_tick[tick]

    def read_boundary(self, tick: int) -> CulturalBoundaryExport | None:
        return self._by_tick.get(tick)


class SpooledCulturalCaptureSource:
    """Read-only cultural source backed by an append-only spool lane."""

    __slots__ = (
        "_capture_status",
        "_gaps",
        "_lane",
        "_run_id",
        "_source_revision",
        "_spool",
        "_status",
    )

    def __init__(
        self,
        spool: EvidenceSpool,
        *,
        run_id: str,
        source_revision: str,
        capture_status: CulturalCaptureStatus,
        gaps: tuple[str, ...] = (),
        lane: str = CULTURAL_SPOOL_LANE,
    ) -> None:
        self._spool = spool
        self._run_id = run_id
        self._source_revision = source_revision
        self._capture_status = capture_status
        self._gaps = tuple(sorted(set(gaps)))
        self._lane = lane
        self._status = spool.lane_status(lane)

    @property
    def run_id(self) -> str:
        return self._run_id

    @property
    def source_revision(self) -> str:
        return self._source_revision

    @property
    def capture_status(self) -> CulturalCaptureStatus:
        return self._capture_status

    @property
    def gaps(self) -> tuple[str, ...]:
        return self._gaps

    @property
    def status(self) -> EvidenceSpoolStatus:
        lane = self._status
        return EvidenceSpoolStatus(
            active=self._capture_status.active and lane.active,
            failed=self._capture_status.failed,
            sealed=lane.sealed,
            truncated="capture_truncated" in self._gaps,
            failure_code=self._capture_status.failure_code,
            record_count=lane.record_count,
            byte_count=lane.byte_count,
            first_boundary=lane.first_boundary,
            last_boundary=lane.last_boundary,
        )

    def boundary_ticks(self) -> tuple[int, ...]:
        return tuple(frame.boundary_tick for frame in self.iter_boundaries())

    def iter_boundaries(
        self, *, after_boundary: int | None = None
    ) -> Iterator[CulturalBoundaryExport]:
        cursor = after_boundary
        through = self._status.last_boundary
        if through is None:
            return
        while True:
            payloads = self._spool.iter_lane(
                lane=self._lane,
                after_boundary=cursor,
                limit=_DEFAULT_PAGE,
            )
            if not payloads:
                return
            for payload in payloads:
                frame = decode_cultural_boundary(payload)
                if frame.boundary_tick > through:
                    return
                if frame.run_id != self._run_id:
                    raise ValueError("cultural_source_run_mismatch")
                if cursor is not None and frame.boundary_tick <= cursor:
                    raise ValueError("cultural_source_nonadvancing_boundary")
                cursor = frame.boundary_tick
                yield frame
            if len(payloads) < _DEFAULT_PAGE:
                return

    def read_boundary(self, tick: int) -> CulturalBoundaryExport | None:
        if self._status.last_boundary is None or tick > self._status.last_boundary:
            return None
        payload = self._spool.get(lane=self._lane, identity=boundary_identity(tick))
        if payload is None:
            return None
        frame = decode_cultural_boundary(payload)
        if frame.run_id != self._run_id or frame.boundary_tick != tick:
            raise ValueError("cultural_source_identity_mismatch")
        return frame


@dataclass(frozen=True, slots=True)
class MemoryCivilizationHistorySource:
    """Read-only source over an already materialized civilization history."""

    run_id_value: str
    world_id_value: str
    boundaries: tuple[CivilizationBoundaryInput, ...]
    event_batches: tuple[CivilizationEventBatch, ...]
    status: EvidenceSpoolStatus
    _by_boundary: dict[int, CivilizationBoundaryInput] = field(
        init=False, repr=False, compare=False
    )
    _by_event: dict[int, CivilizationEventBatch] = field(
        init=False, repr=False, compare=False
    )

    def __post_init__(self) -> None:
        boundaries: dict[int, CivilizationBoundaryInput] = {}
        for frame in self.boundaries:
            if type(frame) is not CivilizationBoundaryInput:
                raise TypeError("boundaries must contain CivilizationBoundaryInput")
            if (
                frame.cursor.run_id != self.run_id_value
                or frame.cursor.world_id != self.world_id_value
                or frame.cursor.boundary_tick is None
            ):
                raise ValueError("civilization_source_identity_mismatch")
            tick = frame.cursor.boundary_tick
            if tick in boundaries:
                raise ValueError("civilization_source_conflict")
            boundaries[tick] = frame
        batches: dict[int, CivilizationEventBatch] = {}
        for batch in self.event_batches:
            if type(batch) is not CivilizationEventBatch:
                raise TypeError("event_batches must contain CivilizationEventBatch")
            if batch.run_id != self.run_id_value:
                raise ValueError("civilization_source_identity_mismatch")
            if batch.tick in batches:
                raise ValueError("civilization_source_conflict")
            batches[batch.tick] = batch
        object.__setattr__(self, "_by_boundary", boundaries)
        object.__setattr__(self, "_by_event", batches)

    @property
    def run_id(self) -> str:
        return self.run_id_value

    @property
    def world_id(self) -> str:
        return self.world_id_value

    def boundary_ticks(self) -> tuple[int, ...]:
        return tuple(sorted(self._by_boundary))

    def event_ticks(self) -> tuple[int, ...]:
        return tuple(sorted(self._by_event))

    def iter_boundaries(
        self, *, after_boundary: int | None = None
    ) -> Iterator[CivilizationBoundaryInput]:
        for tick in sorted(self._by_boundary):
            if after_boundary is not None and tick <= after_boundary:
                continue
            yield self._by_boundary[tick]

    def read_boundary(self, tick: int) -> CivilizationBoundaryInput | None:
        return self._by_boundary.get(tick)

    def iter_event_batches(
        self,
        *,
        after_tick: int | None = None,
        through_tick: int | None = None,
    ) -> Iterator[CivilizationEventBatch]:
        for tick in sorted(self._by_event):
            if after_tick is not None and tick <= after_tick:
                continue
            if through_tick is not None and tick > through_tick:
                continue
            yield self._by_event[tick]

    def read_event_batch(self, tick: int) -> CivilizationEventBatch | None:
        return self._by_event.get(tick)


class SpooledCivilizationHistorySource:
    """Read-only civilization source over spool boundary/event lanes."""

    __slots__ = (
        "_boundary_lane",
        "_boundary_status",
        "_event_lane",
        "_event_status",
        "_run_id",
        "_spool",
        "_status",
        "_world_id",
    )

    def __init__(
        self,
        spool: EvidenceSpool,
        *,
        run_id: str,
        world_id: str,
        boundary_lane: str = CIVILIZATION_BOUNDARY_SPOOL_LANE,
        event_lane: str = CIVILIZATION_EVENT_SPOOL_LANE,
    ) -> None:
        self._spool = spool
        self._run_id = run_id
        self._world_id = world_id
        self._boundary_lane = boundary_lane
        self._event_lane = event_lane
        self._boundary_status = spool.lane_status(boundary_lane)
        self._event_status = spool.lane_status(event_lane)
        self._status = spool.status()

    @property
    def run_id(self) -> str:
        return self._run_id

    @property
    def world_id(self) -> str:
        return self._world_id

    @property
    def status(self) -> EvidenceSpoolStatus:
        return self._status

    def boundary_ticks(self) -> tuple[int, ...]:
        ticks: list[int] = []
        for frame in self.iter_boundaries():
            tick = frame.cursor.boundary_tick
            if tick is None:
                raise ValueError("civilization_source_identity_mismatch")
            ticks.append(tick)
        return tuple(ticks)

    def event_ticks(self) -> tuple[int, ...]:
        return tuple(batch.tick for batch in self.iter_event_batches())

    def iter_boundaries(
        self, *, after_boundary: int | None = None
    ) -> Iterator[CivilizationBoundaryInput]:
        cursor = after_boundary
        through = self._boundary_status.last_boundary
        if through is None:
            return
        while True:
            payloads = self._spool.iter_lane(
                lane=self._boundary_lane,
                after_boundary=cursor,
                limit=_DEFAULT_PAGE,
            )
            if not payloads:
                return
            for payload in payloads:
                frame = decode_civilization_boundary(payload)
                tick = frame.cursor.boundary_tick
                if tick is not None and tick > through:
                    return
                if (
                    frame.cursor.run_id != self._run_id
                    or frame.cursor.world_id != self._world_id
                    or tick is None
                ):
                    raise ValueError("civilization_source_identity_mismatch")
                if cursor is not None and tick <= cursor:
                    raise ValueError("civilization_source_nonadvancing_boundary")
                cursor = tick
                yield frame
            if len(payloads) < _DEFAULT_PAGE:
                return

    def read_boundary(self, tick: int) -> CivilizationBoundaryInput | None:
        through = self._boundary_status.last_boundary
        if through is None or tick > through:
            return None
        payload = self._spool.get(
            lane=self._boundary_lane, identity=boundary_identity(tick)
        )
        if payload is None:
            return None
        frame = decode_civilization_boundary(payload)
        if (
            frame.cursor.run_id != self._run_id
            or frame.cursor.world_id != self._world_id
            or frame.cursor.boundary_tick != tick
        ):
            raise ValueError("civilization_source_identity_mismatch")
        return frame

    def iter_event_batches(
        self,
        *,
        after_tick: int | None = None,
        through_tick: int | None = None,
    ) -> Iterator[CivilizationEventBatch]:
        cursor = after_tick
        pinned_through = self._event_status.last_boundary
        if pinned_through is None:
            return
        through_tick = (
            pinned_through
            if through_tick is None
            else min(pinned_through, through_tick)
        )
        while True:
            payloads = self._spool.iter_lane(
                lane=self._event_lane,
                after_boundary=cursor,
                limit=_DEFAULT_PAGE,
            )
            if not payloads:
                return
            for payload in payloads:
                batch = decode_civilization_event_batch(payload)
                if batch.run_id != self._run_id:
                    raise ValueError("civilization_source_identity_mismatch")
                if cursor is not None and batch.tick <= cursor:
                    raise ValueError("civilization_source_nonadvancing_boundary")
                if through_tick is not None and batch.tick > through_tick:
                    return
                cursor = batch.tick
                yield batch
            if len(payloads) < _DEFAULT_PAGE:
                return

    def read_event_batch(self, tick: int) -> CivilizationEventBatch | None:
        through = self._event_status.last_boundary
        if through is None or tick > through:
            return None
        payload = self._spool.get(lane=self._event_lane, identity=event_identity(tick))
        if payload is None:
            return None
        batch = decode_civilization_event_batch(payload)
        if batch.run_id != self._run_id or batch.tick != tick:
            raise ValueError("civilization_source_identity_mismatch")
        return batch
