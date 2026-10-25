"""Bounded civilization evidence retention outside simulation authority.

The continuous event lane is independent of sampled physical boundaries.
Private owner inventories and grounding remain explicitly unavailable until
their dedicated metadata-only exports are installed.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from simulation.civilization_boundaries import (
    CivilizationBoundaryInput,
    civilization_boundary_bytes,
    civilization_boundary_rows,
)
from simulation.civilization_capture import (
    CivilizationCaptureOptions,
    CivilizationEventBatch,
    civilization_event_bytes,
)
from simulation.civilization_models import (
    CivilizationCoverageState,
    CivilizationError,
    CivilizationPublicationRef,
    CivilizationWindow,
)

__all__ = [
    "CivilizationCaptureStatus",
    "CivilizationEvidenceRecorder",
    "CivilizationPublicationReceipt",
]

_LOG = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class CivilizationPublicationReceipt:
    """Operational publication readiness, never scientific completion."""

    run_id: str
    boundary_tick: int
    publication: CivilizationPublicationRef | None
    published_boundaries: int
    failure_code: str | None

    def __post_init__(self) -> None:
        if type(self.run_id) is not str or not self.run_id:
            raise CivilizationError()
        if type(self.boundary_tick) is not int or self.boundary_tick < 0:
            raise CivilizationError()
        if type(self.published_boundaries) is not int or self.published_boundaries < 0:
            raise CivilizationError()
        if self.failure_code is not None and self.failure_code not in {
            "civilization_capture_unavailable",
            "civilization_publication_failed",
        }:
            raise CivilizationError()


@dataclass(frozen=True, slots=True)
class CivilizationCaptureStatus:
    active: bool
    failed: bool
    failure_boundary: int | None
    failure_code: str | None
    retained_rows: int
    retained_bytes: int
    first_event_tick: int | None
    last_event_tick: int | None
    first_boundary: int | None
    last_boundary: int | None


class CivilizationEvidenceRecorder:
    """Atomic, idempotent, append-only retention; failures latch, never evict.

    Event batches are retained every tick, even when boundary cadence is >1.
    Never accepts WorldEvent/checkpoints/ledger objects or arbitrary mappings.
    """

    __slots__ = (
        "_batches",
        "_boundaries",
        "_failure_boundary",
        "_failure_code",
        "_options",
        "_retained_bytes",
        "_retained_rows",
        "_run_id",
    )

    def __init__(self, options: CivilizationCaptureOptions | None = None) -> None:
        if options is not None and type(options) is not CivilizationCaptureOptions:
            raise CivilizationError()
        self._options = options or CivilizationCaptureOptions()
        self._batches: dict[int, CivilizationEventBatch] = {}
        self._boundaries: dict[int, CivilizationBoundaryInput] = {}
        self._failure_boundary: int | None = None
        self._failure_code: str | None = None
        self._retained_bytes = self._retained_rows = 0
        self._run_id: str | None = None

    @property
    def status(self) -> CivilizationCaptureStatus:
        return CivilizationCaptureStatus(
            self._options.enabled and self._failure_code is None,
            self._failure_code is not None,
            self._failure_boundary,
            self._failure_code,
            self._retained_rows,
            self._retained_bytes,
            min(self._batches, default=None),
            max(self._batches, default=None),
            min(self._boundaries, default=None),
            max(self._boundaries, default=None),
        )

    @property
    def event_batches(self) -> tuple[CivilizationEventBatch, ...]:
        return tuple(self._batches[tick] for tick in sorted(self._batches))

    @property
    def boundaries(self) -> tuple[CivilizationBoundaryInput, ...]:
        return tuple(self._boundaries[tick] for tick in sorted(self._boundaries))

    def wants_events(self) -> bool:
        return self._options.enabled and self._failure_code is None

    def wants_boundary(self, boundary_tick: int) -> bool:
        return self.wants_events() and boundary_tick % self._options.cadence == 0

    @property
    def covered_event_intervals(self) -> tuple[CivilizationWindow, ...]:
        """Only independently proven contiguous tick intervals, never gap repair."""
        intervals: list[CivilizationWindow] = []
        for batch in self.event_batches:
            if batch.coverage.state is not CivilizationCoverageState.COMPLETE:
                continue
            if intervals and intervals[-1].end_tick == batch.tick:
                intervals[-1] = CivilizationWindow(
                    intervals[-1].start_tick, batch.tick + 1
                )
            else:
                intervals.append(CivilizationWindow(batch.tick, batch.tick + 1))
        return tuple(intervals)

    def _fail(self, boundary: int, code: str) -> None:
        if self._failure_code is not None:
            return
        self._failure_boundary, self._failure_code = boundary, code
        _LOG.warning(
            "civilization_capture_stopped boundary_tick=%s reason_code=%s",
            boundary,
            code,
        )

    def capture_events(self, batch: CivilizationEventBatch) -> bool:
        if not self._options.enabled or self._failure_code is not None:
            return False
        if type(batch) is not CivilizationEventBatch:
            self._fail(max(self._batches, default=-1) + 2, "capture_build_failed")
            return False
        boundary = batch.tick + 1
        try:
            if self._run_id is not None and batch.run_id != self._run_id:
                self._fail(boundary, "capture_conflict")
                return False
            previous = self._batches.get(batch.tick)
            if previous is not None:
                if previous != batch:
                    self._fail(boundary, "capture_conflict")
                    return False
                return True
            if self._batches and batch.tick < max(self._batches):
                self._fail(boundary, "capture_conflict")
                return False
            encoded = civilization_event_bytes(batch)
            # Account for headers and nested items as retained rows too, so an
            # empty-source run or large nested details cannot evade the quota.
            rows = 1 + sum(1 + len(receipt.items) for receipt in batch.receipts)
            if self._retained_rows + rows > self._options.max_rows:
                self._fail(boundary, "capture_row_limit")
                return False
            if self._retained_bytes + len(encoded) > self._options.max_bytes:
                self._fail(boundary, "capture_byte_limit")
                return False
            self._batches[batch.tick] = batch
            self._run_id = batch.run_id
            self._retained_rows += rows
            self._retained_bytes += len(encoded)
            _LOG.debug(
                "civilization_events_retained tick=%s receipt_count=%s byte_count=%s",
                batch.tick,
                len(batch.receipts),
                len(encoded),
            )
            return True
        except Exception:
            self._fail(boundary, "capture_build_failed")
            return False

    def capture_boundary(self, frame: CivilizationBoundaryInput) -> bool:
        if not self.wants_events():
            return False
        if type(frame) is not CivilizationBoundaryInput:
            self._fail(max(self._boundaries, default=-1) + 1, "capture_build_failed")
            return False
        boundary = frame.cursor.tick
        if not self.wants_boundary(boundary):
            return False
        try:
            if self._run_id is not None and frame.cursor.run_id != self._run_id:
                self._fail(boundary, "capture_conflict")
                return False
            previous = self._boundaries.get(boundary)
            if previous is not None:
                if previous != frame:
                    self._fail(boundary, "capture_conflict")
                    return False
                return True
            if self._boundaries and boundary < max(self._boundaries):
                self._fail(boundary, "capture_conflict")
                return False
            if len(self._boundaries) >= self._options.max_boundaries:
                self._fail(boundary, "capture_boundary_limit")
                return False
            encoded = civilization_boundary_bytes(frame)
            rows = civilization_boundary_rows(frame)
            if self._retained_rows + rows > self._options.max_rows:
                self._fail(boundary, "capture_row_limit")
                return False
            if self._retained_bytes + len(encoded) > self._options.max_bytes:
                self._fail(boundary, "capture_byte_limit")
                return False
            self._boundaries[boundary] = frame
            self._run_id = frame.cursor.run_id
            self._retained_rows += rows
            self._retained_bytes += len(encoded)
            _LOG.debug(
                "civilization_boundary_retained boundary_tick=%s "
                "row_count=%s byte_count=%s",
                boundary,
                rows,
                len(encoded),
            )
            return True
        except Exception:
            self._fail(boundary, "capture_build_failed")
            return False
