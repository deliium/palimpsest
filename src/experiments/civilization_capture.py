"""Bounded civilization evidence retention outside simulation authority.

The continuous event lane is independent of sampled physical boundaries.
Private owner inventories and grounding remain explicitly unavailable until
their dedicated metadata-only exports are installed.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass

from experiments.evidence_codecs import (
    decode_civilization_boundary,
    decode_civilization_event_batch,
    encode_civilization_boundary,
    encode_civilization_event_batch,
)
from experiments.evidence_sources import (
    CIVILIZATION_BOUNDARY_SPOOL_LANE,
    CIVILIZATION_EVENT_SPOOL_LANE,
    CivilizationHistorySource,
    MemoryCivilizationHistorySource,
    SpooledCivilizationHistorySource,
    boundary_identity,
    event_identity,
)
from experiments.persistence import EvidenceSpool, EvidenceSpoolStatus
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
    "CivilizationEvidenceAccounting",
    "CivilizationEvidenceRecorder",
    "CivilizationPublicationReceipt",
]

_RESUME_PAGE = 256

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


@dataclass(frozen=True, slots=True)
class CivilizationEvidenceAccounting:
    """Logical quota accounting separated from physical spool storage."""

    logical_rows: int
    logical_bytes: int
    physical_records: int
    physical_bytes: int
    event_records: int
    boundary_records: int
    spooled: bool


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
        "_last_boundary_tick",
        "_last_event_tick",
        "_options",
        "_resumed",
        "_retained_bytes",
        "_retained_rows",
        "_run_id",
        "_spool",
        "_spool_factory",
        "_world_id",
    )

    def __init__(
        self,
        options: CivilizationCaptureOptions | None = None,
        *,
        spool: EvidenceSpool | Callable[[str], EvidenceSpool] | None = None,
    ) -> None:
        if options is not None and type(options) is not CivilizationCaptureOptions:
            raise CivilizationError()
        self._options = options or CivilizationCaptureOptions()
        self._batches: dict[int, CivilizationEventBatch] = {}
        self._boundaries: dict[int, CivilizationBoundaryInput] = {}
        self._failure_boundary: int | None = None
        self._failure_code: str | None = None
        self._retained_bytes = self._retained_rows = 0
        self._run_id: str | None = None
        self._world_id: str | None = None
        if spool is not None and callable(spool):
            self._spool_factory: Callable[[str], EvidenceSpool] | None = spool
            self._spool: EvidenceSpool | None = None
        else:
            self._spool_factory = None
            self._spool = spool
        self._resumed = False
        self._last_event_tick: int | None = None
        self._last_boundary_tick: int | None = None

    @property
    def status(self) -> CivilizationCaptureStatus:
        if self._spool is not None:
            events = self._spool.lane_status(CIVILIZATION_EVENT_SPOOL_LANE)
            boundaries = self._spool.lane_status(CIVILIZATION_BOUNDARY_SPOOL_LANE)
            return CivilizationCaptureStatus(
                self._options.enabled and self._failure_code is None,
                self._failure_code is not None,
                self._failure_boundary,
                self._failure_code,
                self._retained_rows,
                self._retained_bytes,
                events.first_boundary,
                events.last_boundary,
                boundaries.first_boundary,
                boundaries.last_boundary,
            )
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
    def accounting(self) -> CivilizationEvidenceAccounting:
        """Report logical quota counts separately from physical spool bytes."""
        if self._spool is None:
            return CivilizationEvidenceAccounting(
                logical_rows=self._retained_rows,
                logical_bytes=self._retained_bytes,
                physical_records=len(self._batches) + len(self._boundaries),
                physical_bytes=0,
                event_records=len(self._batches),
                boundary_records=len(self._boundaries),
                spooled=False,
            )
        events = self._spool.lane_status(CIVILIZATION_EVENT_SPOOL_LANE)
        boundaries = self._spool.lane_status(CIVILIZATION_BOUNDARY_SPOOL_LANE)
        return CivilizationEvidenceAccounting(
            logical_rows=self._retained_rows,
            logical_bytes=self._retained_bytes,
            physical_records=events.record_count + boundaries.record_count,
            physical_bytes=events.byte_count + boundaries.byte_count,
            event_records=events.record_count,
            boundary_records=boundaries.record_count,
            spooled=True,
        )

    def _resolve_spool(self, run_id: str, boundary: int) -> bool:
        """Resolve a composition-provided per-run spool factory once."""
        if self._spool is not None:
            return True
        if self._spool_factory is None:
            return False
        try:
            self._spool = self._spool_factory(run_id)
        except Exception:
            self._fail(boundary, "capture_build_failed")
            return False
        return True

    def _resume_spooled(self) -> None:
        """Rebuild exact logical accounting from a committed spool prefix."""
        if self._resumed:
            return
        self._resumed = True
        assert self._spool is not None
        run_id: str | None = None
        world_id: str | None = None
        rows = 0
        logical_bytes = 0
        last_event: int | None = None
        last_boundary: int | None = None
        cursor: int | None = None
        while True:
            payloads = self._spool.iter_lane(
                lane=CIVILIZATION_EVENT_SPOOL_LANE,
                after_boundary=cursor,
                limit=_RESUME_PAGE,
            )
            if not payloads:
                break
            for payload in payloads:
                batch = decode_civilization_event_batch(payload)
                if run_id is not None and batch.run_id != run_id:
                    raise ValueError("capture_conflict")
                run_id = batch.run_id
                if last_event is not None and batch.tick <= last_event:
                    raise ValueError("capture_conflict")
                last_event = batch.tick
                cursor = last_event
                rows += 1 + sum(1 + len(receipt.items) for receipt in batch.receipts)
                logical_bytes += len(civilization_event_bytes(batch))
            if len(payloads) < _RESUME_PAGE:
                break
        cursor = None
        while True:
            payloads = self._spool.iter_lane(
                lane=CIVILIZATION_BOUNDARY_SPOOL_LANE,
                after_boundary=cursor,
                limit=_RESUME_PAGE,
            )
            if not payloads:
                break
            for payload in payloads:
                frame = decode_civilization_boundary(payload)
                tick = frame.cursor.boundary_tick
                if tick is None:
                    raise ValueError("capture_conflict")
                if run_id is not None and frame.cursor.run_id != run_id:
                    raise ValueError("capture_conflict")
                if world_id is not None and frame.cursor.world_id != world_id:
                    raise ValueError("capture_conflict")
                if last_boundary is not None and tick <= last_boundary:
                    raise ValueError("capture_conflict")
                run_id = frame.cursor.run_id
                world_id = frame.cursor.world_id
                last_boundary = tick
                cursor = tick
                rows += civilization_boundary_rows(frame)
                logical_bytes += len(civilization_boundary_bytes(frame))
            if len(payloads) < _RESUME_PAGE:
                break
        self._run_id = run_id
        self._world_id = world_id
        self._last_event_tick = last_event
        self._last_boundary_tick = last_boundary
        self._retained_rows = rows
        self._retained_bytes = logical_bytes
        _LOG.info(
            "civilization_evidence_resumed rows=%s logical_bytes=%s "
            "last_event_tick=%s last_boundary=%s",
            rows,
            logical_bytes,
            last_event,
            last_boundary,
        )

    @property
    def event_batches(self) -> tuple[CivilizationEventBatch, ...]:
        if self._spool is not None:
            return tuple(self.source().iter_event_batches())
        return tuple(self._batches[tick] for tick in sorted(self._batches))

    @property
    def boundaries(self) -> tuple[CivilizationBoundaryInput, ...]:
        if self._spool is not None:
            return tuple(self.source().iter_boundaries())
        return tuple(self._boundaries[tick] for tick in sorted(self._boundaries))

    def source(self) -> CivilizationHistorySource:
        if not self._options.enabled:
            return MemoryCivilizationHistorySource(
                run_id_value=self._run_id or "",
                world_id_value=self._world_id or "",
                boundaries=(),
                event_batches=(),
                status=EvidenceSpoolStatus(
                    active=False,
                    failed=False,
                    sealed=False,
                    truncated=False,
                    failure_code=None,
                    record_count=0,
                    byte_count=0,
                    first_boundary=None,
                    last_boundary=None,
                ),
            )
        if self._spool is not None:
            return SpooledCivilizationHistorySource(
                self._spool,
                run_id=self._run_id or "",
                world_id=self._world_id or "",
            )
        ticks = sorted(self._boundaries)
        return MemoryCivilizationHistorySource(
            run_id_value=self._run_id or "",
            world_id_value=self._world_id or "",
            boundaries=tuple(self._boundaries[tick] for tick in ticks),
            event_batches=tuple(self._batches[tick] for tick in sorted(self._batches)),
            status=EvidenceSpoolStatus(
                active=self._options.enabled and self._failure_code is None,
                failed=self._failure_code is not None,
                sealed=False,
                truncated=False,
                failure_code=self._failure_code,
                record_count=len(self._batches) + len(self._boundaries),
                byte_count=self._retained_bytes,
                first_boundary=(
                    min(
                        (
                            value
                            for value in (
                                min(self._batches, default=None),
                                min(self._boundaries, default=None),
                            )
                            if value is not None
                        ),
                        default=None,
                    )
                ),
                last_boundary=(
                    max(
                        (
                            value
                            for value in (
                                max(self._batches, default=None),
                                max(self._boundaries, default=None),
                            )
                            if value is not None
                        ),
                        default=None,
                    )
                ),
            ),
        )

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
            self._fail(
                (self._last_event_tick if self._last_event_tick is not None else -1)
                + 2,
                "capture_build_failed",
            )
            return False
        boundary = batch.tick + 1
        if self._spool is not None or self._spool_factory is not None:
            if not self._resolve_spool(batch.run_id, boundary):
                return False
            return self._capture_events_spooled(batch, boundary)
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
            self._last_event_tick = batch.tick
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

    def _capture_events_spooled(
        self, batch: CivilizationEventBatch, boundary: int
    ) -> bool:
        assert self._spool is not None
        try:
            self._resume_spooled()
        except ValueError:
            self._fail(boundary, "capture_conflict")
            return False
        try:
            if self._run_id is not None and batch.run_id != self._run_id:
                self._fail(boundary, "capture_conflict")
                return False
            payload = encode_civilization_event_batch(batch)
            previous = self._spool.get(
                lane=CIVILIZATION_EVENT_SPOOL_LANE,
                identity=event_identity(batch.tick),
            )
            if previous is not None:
                if previous != payload:
                    self._fail(boundary, "capture_conflict")
                    return False
                return True
            if self._last_event_tick is not None and batch.tick < self._last_event_tick:
                self._fail(boundary, "capture_conflict")
                return False
            encoded = civilization_event_bytes(batch)
            rows = 1 + sum(1 + len(receipt.items) for receipt in batch.receipts)
            if self._retained_rows + rows > self._options.max_rows:
                self._fail(boundary, "capture_row_limit")
                return False
            if self._retained_bytes + len(encoded) > self._options.max_bytes:
                self._fail(boundary, "capture_byte_limit")
                return False
            self._spool.append(
                lane=CIVILIZATION_EVENT_SPOOL_LANE,
                boundary_tick=batch.tick,
                identity=event_identity(batch.tick),
                payload=payload,
            )
            self._run_id = batch.run_id
            if self._last_event_tick is None or batch.tick > self._last_event_tick:
                self._last_event_tick = batch.tick
                self._retained_rows += rows
                self._retained_bytes += len(encoded)
            _LOG.debug(
                "civilization_events_spooled tick=%s receipt_count=%s byte_count=%s",
                batch.tick,
                len(batch.receipts),
                len(encoded),
            )
            return True
        except ValueError as exc:
            code = getattr(exc, "code", None)
            if code == "evidence_spool_conflict":
                self._fail(boundary, "capture_conflict")
            elif code == "evidence_spool_full":
                self._fail(boundary, "capture_byte_limit")
            else:
                self._fail(boundary, "capture_build_failed")
            return False
        except Exception:
            self._fail(boundary, "capture_build_failed")
            return False

    def capture_boundary(self, frame: CivilizationBoundaryInput) -> bool:
        if not self.wants_events():
            return False
        if type(frame) is not CivilizationBoundaryInput:
            self._fail(
                (
                    self._last_boundary_tick
                    if self._last_boundary_tick is not None
                    else -1
                )
                + 1,
                "capture_build_failed",
            )
            return False
        boundary = frame.cursor.tick
        if not self.wants_boundary(boundary):
            return False
        if self._spool is not None or self._spool_factory is not None:
            if not self._resolve_spool(frame.cursor.run_id, boundary):
                return False
            return self._capture_boundary_spooled(frame, boundary)
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
            self._world_id = frame.cursor.world_id
            self._last_boundary_tick = boundary
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

    def _capture_boundary_spooled(
        self, frame: CivilizationBoundaryInput, boundary: int
    ) -> bool:
        assert self._spool is not None
        try:
            self._resume_spooled()
        except ValueError:
            self._fail(boundary, "capture_conflict")
            return False
        try:
            if self._run_id is not None and frame.cursor.run_id != self._run_id:
                self._fail(boundary, "capture_conflict")
                return False
            if self._world_id is not None and frame.cursor.world_id != self._world_id:
                self._fail(boundary, "capture_conflict")
                return False
            payload = encode_civilization_boundary(frame)
            previous = self._spool.get(
                lane=CIVILIZATION_BOUNDARY_SPOOL_LANE,
                identity=boundary_identity(boundary),
            )
            if previous is not None:
                if previous != payload:
                    self._fail(boundary, "capture_conflict")
                    return False
                return True
            if (
                self._last_boundary_tick is not None
                and boundary < self._last_boundary_tick
            ):
                self._fail(boundary, "capture_conflict")
                return False
            if (
                self._spool.lane_status(CIVILIZATION_BOUNDARY_SPOOL_LANE).record_count
                >= self._options.max_boundaries
            ):
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
            self._spool.append(
                lane=CIVILIZATION_BOUNDARY_SPOOL_LANE,
                boundary_tick=boundary,
                identity=boundary_identity(boundary),
                payload=payload,
            )
            self._run_id = frame.cursor.run_id
            self._world_id = frame.cursor.world_id
            if self._last_boundary_tick is None or boundary > self._last_boundary_tick:
                self._last_boundary_tick = boundary
                self._retained_rows += rows
                self._retained_bytes += len(encoded)
            _LOG.debug(
                "civilization_boundary_spooled boundary_tick=%s "
                "row_count=%s byte_count=%s",
                boundary,
                rows,
                len(encoded),
            )
            return True
        except ValueError as exc:
            code = getattr(exc, "code", None)
            if code == "evidence_spool_conflict":
                self._fail(boundary, "capture_conflict")
            elif code == "evidence_spool_full":
                self._fail(boundary, "capture_byte_limit")
            else:
                self._fail(boundary, "capture_build_failed")
            return False
        except Exception:
            self._fail(boundary, "capture_build_failed")
            return False
