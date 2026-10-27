"""Bounded outer-layer recorder for detached cultural boundary exports."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Final

from analysis.cultural_evolution_evidence import (
    ArchiveKnowledgeState,
    CulturalAnalysisWindow,
    CulturalEvolutionInputs,
    GroupMembership,
    normalize_cultural_frame_source,
    normalize_cultural_frames,
)
from experiments.cultural_metric_artifacts import (
    CulturalCaptureOptions,
    cultural_capture_policy,
)
from experiments.evidence_codecs import (
    decode_cultural_boundary,
    encode_cultural_boundary,
)
from experiments.evidence_sources import (
    CULTURAL_SPOOL_LANE,
    CulturalCaptureSource,
    MemoryCulturalCaptureSource,
    SpooledCulturalCaptureSource,
    boundary_identity,
)
from experiments.persistence import EvidenceSpool, EvidenceSpoolStatus
from simulation.cultural_evidence import (
    CulturalBoundaryExport,
    CulturalCaptureStatus,
)
from simulation.runner import SimulationRunner

_LOG: Final[logging.Logger] = logging.getLogger("experiments.cultural_evidence")

DEFAULT_MAX_CULTURAL_FRAMES: Final[int] = 10_000
DEFAULT_MAX_CULTURAL_ROWS: Final[int] = 1_000_000
_RESUME_PAGE: Final[int] = 256

__all__ = [
    "DEFAULT_MAX_CULTURAL_FRAMES",
    "DEFAULT_MAX_CULTURAL_ROWS",
    "CulturalEvidenceAccounting",
    "CulturalEvidenceBatchError",
    "CulturalEvidenceCapture",
    "CulturalEvidenceRecorder",
    "SourceBackedCulturalEvidence",
    "build_cultural_arm_fields",
    "build_cultural_arm_fields_from_source",
    "cultural_evidence_source",
    "cultural_evolution_inputs_from_capture",
    "cultural_evolution_inputs_from_source",
    "install_cultural_recorder",
    "kinship_parent_child_edges",
    "materialize_cultural_evidence",
]


class CulturalEvidenceBatchError(ValueError):
    """Payload-free exact-batch failure with a stable safe code."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class SourceBackedCulturalEvidence:
    """Tagged, pinned source for streamed artifacts and exact batch stages.

    This is an internal composition value. It is never a runner, result or API
    wire field, and it never grants analytical or world authority.
    """

    source: CulturalCaptureSource
    run_id: str
    source_revision: str
    window: CulturalAnalysisWindow
    config_fingerprint: str
    capture_options: dict[str, object]
    capture_status: CulturalCaptureStatus
    status: EvidenceSpoolStatus
    digest: str
    gaps: tuple[str, ...]
    parent_child_edges: tuple[tuple[str, str], ...]
    boundary_count: int
    trait_row_count: int

    def __post_init__(self) -> None:
        if type(self.window) is not CulturalAnalysisWindow:
            raise TypeError("window must be CulturalAnalysisWindow")
        if type(self.capture_status) is not CulturalCaptureStatus:
            raise TypeError("capture_status must be CulturalCaptureStatus")
        if type(self.status) is not EvidenceSpoolStatus:
            raise TypeError("status must be EvidenceSpoolStatus")
        if type(self.run_id) is not str or not self.run_id:
            raise ValueError("run_id must be a non-empty str")
        if self.source.run_id != self.run_id:
            raise ValueError("cultural_source_run_mismatch")
        if len(self.digest) != 64 or any(
            char not in "0123456789abcdef" for char in self.digest
        ):
            raise ValueError("digest must be a lowercase sha256 hex digest")
        for name in ("boundary_count", "trait_row_count"):
            value = getattr(self, name)
            if type(value) is not int or value < 0:
                raise ValueError(f"{name} must be a non-negative int")
        if type(self.gaps) is not tuple:
            raise TypeError("gaps must be a tuple")
        if type(self.parent_child_edges) is not tuple:
            raise TypeError("parent_child_edges must be a tuple")
        if not isinstance(self.capture_options, dict):
            raise TypeError("capture_options must be a dict")

    def __repr__(self) -> str:
        return (
            f"SourceBackedCulturalEvidence(run_id={self.run_id!r}, "
            f"boundary_count={self.boundary_count}, "
            f"trait_row_count={self.trait_row_count}, "
            f"digest={self.digest[:12]!r}, "
            f"sealed={self.status.sealed})"
        )


@dataclass(frozen=True, slots=True)
class CulturalEvidenceAccounting:
    """Separate logical quota accounting from physical spool storage."""

    logical_frames: int
    logical_rows: int
    physical_records: int
    physical_bytes: int
    truncated: bool
    spooled: bool

    def __repr__(self) -> str:
        return (
            f"CulturalEvidenceAccounting(logical_frames={self.logical_frames}, "
            f"logical_rows={self.logical_rows}, "
            f"physical_records={self.physical_records}, "
            f"physical_bytes={self.physical_bytes}, "
            f"truncated={self.truncated}, spooled={self.spooled})"
        )


def kinship_parent_child_edges(graph: object) -> tuple[tuple[str, str], ...]:
    """Copy detached objective parent→child identities from a kinship graph."""
    rows: set[tuple[str, str]] = set()
    for edge in getattr(graph, "edges", ()):
        parent = getattr(getattr(edge, "parent_agent_id", None), "value", None)
        child = getattr(getattr(edge, "child_agent_id", None), "value", None)
        if isinstance(parent, str) and isinstance(child, str):
            rows.add((parent, child))
    return tuple(sorted(rows))


def _ledger_entry_count(frame: CulturalBoundaryExport) -> int:
    total = 0
    for owner in frame.owners:
        for channel in owner.channels:
            ledger = channel.ledger
            if ledger is None:
                continue
            total += len(getattr(ledger, "beliefs", ()))
            total += len(getattr(ledger, "bindings", ()))
            total += len(getattr(ledger, "variants", ()))
            total += len(getattr(ledger, "entries", ()))
    return total


@dataclass(frozen=True, slots=True)
class CulturalEvidenceCapture:
    """Detached recorder result merged with runner-owned capture status."""

    frames: tuple[CulturalBoundaryExport, ...]
    gaps: tuple[str, ...]
    capture_status: CulturalCaptureStatus

    def __repr__(self) -> str:
        return (
            f"CulturalEvidenceCapture(frame_count={len(self.frames)}, "
            f"gap_count={len(self.gaps)}, "
            f"failed={self.capture_status.failed}, "
            f"missing_prefix_through="
            f"{self.capture_status.missing_prefix_through})"
        )


def cultural_evolution_inputs_from_capture(
    capture: CulturalEvidenceCapture | tuple[CulturalBoundaryExport, ...],
    *,
    run_id: str,
    source_revision: str,
    window: CulturalAnalysisWindow,
    committed_events: tuple[object, ...] = (),
    parent_child_edges: tuple[tuple[str, str], ...] = (),
    group_memberships: tuple[GroupMembership, ...] = (),
    archive_states: tuple[ArchiveKnowledgeState, ...] = (),
) -> CulturalEvolutionInputs:
    """Normalize captured frames after execution; never called live."""
    _ = committed_events
    if type(capture) is CulturalEvidenceCapture:
        frames = capture.frames
        gaps = capture.gaps
    elif isinstance(capture, tuple):
        frames = capture
        gaps = ()
    else:
        raise TypeError("capture must be CulturalEvidenceCapture or tuple")
    return normalize_cultural_frames(
        frames,
        run_id=run_id,
        source_revision=source_revision,
        window=window,
        parent_child_edges=parent_child_edges,
        group_memberships=group_memberships,
        archive_states=archive_states,
        gaps=gaps,
    )


def cultural_evidence_source(
    recorder: CulturalEvidenceRecorder,
) -> CulturalCaptureSource:
    """Return a pinned read source without materializing all frames."""
    return recorder.source()


def cultural_evolution_inputs_from_source(
    source: CulturalCaptureSource,
    *,
    run_id: str,
    source_revision: str,
    window: CulturalAnalysisWindow,
    parent_child_edges: tuple[tuple[str, str], ...] = (),
    group_memberships: tuple[GroupMembership, ...] = (),
    archive_states: tuple[ArchiveKnowledgeState, ...] = (),
) -> CulturalEvolutionInputs:
    """Normalize source-backed frames in repeatable ordered passes.

    Raw decoded frames are never accumulated and no ``tuple(all_frames)``
    accessor is used; each pass re-reads the pinned source in order.
    """
    return normalize_cultural_frame_source(
        source.iter_boundaries,
        run_id=run_id,
        source_revision=source_revision,
        window=window,
        parent_child_edges=parent_child_edges,
        group_memberships=group_memberships,
        archive_states=archive_states,
        gaps=source.gaps,
    )


def materialize_cultural_evidence(
    evidence: SourceBackedCulturalEvidence,
    *,
    stage: str = "metric",
    max_boundaries: int = DEFAULT_MAX_CULTURAL_FRAMES,
    max_rows: int = DEFAULT_MAX_CULTURAL_ROWS,
) -> CulturalEvolutionInputs:
    """Run the exact global batch stage under an explicit capture-derived budget.

    This is the only place where a source-backed capture becomes the complete
    normalized analyst input. The digest is re-derived from the pinned source;
    a mismatch fails closed instead of publishing altered evidence.
    """
    if type(evidence) is not SourceBackedCulturalEvidence:
        raise TypeError("evidence must be SourceBackedCulturalEvidence")
    from experiments.cultural_evidence_serialization import (
        evidence_digest_from_inputs,
    )

    inputs = cultural_evolution_inputs_from_source(
        evidence.source,
        run_id=evidence.run_id,
        source_revision=evidence.source_revision,
        window=evidence.window,
        parent_child_edges=evidence.parent_child_edges,
    )
    row_count = sum(len(boundary.entries) for boundary in inputs.boundaries)
    if len(inputs.boundaries) > max_boundaries or row_count > max_rows:
        _LOG.error(
            "cultural_evidence_batch_budget_exceeded stage=%s run_id=%s "
            "boundary_count=%s trait_row_count=%s max_boundaries=%s max_rows=%s",
            stage,
            evidence.run_id,
            len(inputs.boundaries),
            row_count,
            max_boundaries,
            max_rows,
        )
        raise CulturalEvidenceBatchError("cultural_batch_budget_exceeded")
    digest = evidence_digest_from_inputs(
        inputs,
        config_fingerprint=evidence.config_fingerprint,
        capture_options=evidence.capture_options,
        capture_status=evidence.capture_status,
    )
    if digest != evidence.digest:
        _LOG.error(
            "cultural_evidence_digest_mismatch stage=%s run_id=%s",
            stage,
            evidence.run_id,
        )
        raise CulturalEvidenceBatchError("cultural_evidence_digest_mismatch")
    _LOG.info(
        "cultural_evidence_batch_materialized stage=%s run_id=%s "
        "boundary_count=%s trait_row_count=%s edge_count=%s physical_bytes=%s",
        stage,
        evidence.run_id,
        len(inputs.boundaries),
        row_count,
        len(inputs.transmission_edges),
        evidence.status.byte_count,
    )
    return inputs


def install_cultural_recorder(
    runner: SimulationRunner,
    options: CulturalCaptureOptions | None,
) -> CulturalEvidenceRecorder | None:
    """Install one fresh recorder for this run when capture is enabled."""
    if options is None or not options.enabled:
        return None
    recorder = CulturalEvidenceRecorder(
        max_frames=options.max_frames,
        max_rows=options.max_rows,
        spool=options.spool,  # type: ignore[arg-type]
    )
    runner.set_cultural_boundary_sink(recorder)
    _LOG.debug(
        "cultural_capture_installed run_id=%s max_frames=%s max_rows=%s",
        getattr(runner, "run_id", "unknown"),
        options.max_frames,
        options.max_rows,
    )
    return recorder


def build_cultural_arm_fields(
    recorder: CulturalEvidenceRecorder,
    *,
    run_id: str,
    config_fingerprint: str,
    options: CulturalCaptureOptions,
    source_revision: str,
    parent_child_edges: tuple[tuple[str, str], ...] = (),
) -> dict[str, object]:
    """Normalize captured frames and bind six documents to the evidence digest."""
    return build_cultural_arm_fields_from_source(
        cultural_evidence_source(recorder),
        run_id=run_id,
        config_fingerprint=config_fingerprint,
        options=options,
        source_revision=source_revision,
        parent_child_edges=parent_child_edges,
    )


def build_cultural_arm_fields_from_source(
    source: CulturalCaptureSource,
    *,
    run_id: str,
    config_fingerprint: str,
    options: CulturalCaptureOptions,
    source_revision: str,
    parent_child_edges: tuple[tuple[str, str], ...] = (),
) -> dict[str, object]:
    """Normalize a source-backed capture and bind exact evidence documents.

    The arm receives a pinned :class:`SourceBackedCulturalEvidence` tag. The
    canonical digest comes from the streamed section order, while complete
    metric documents remain an explicit exact batch stage.
    """
    from analysis.cultural_evolution_metrics import (
        assemble_cultural_evolution_documents,
    )
    from experiments.cultural_evidence_serialization import (
        evidence_digest_from_inputs,
    )

    inputs = cultural_evolution_inputs_from_source(
        source,
        run_id=run_id,
        source_revision=source_revision,
        window=options.analysis_window,
        parent_child_edges=parent_child_edges,
    )
    policy = cultural_capture_policy(options)
    capture_status = source.capture_status
    digest = evidence_digest_from_inputs(
        inputs,
        config_fingerprint=config_fingerprint,
        capture_options=policy,
        capture_status=capture_status,
    )
    documents = assemble_cultural_evolution_documents(
        inputs,
        evidence_manifest_digest=digest,
    )
    evidence = SourceBackedCulturalEvidence(
        source=source,
        run_id=run_id,
        source_revision=source_revision,
        window=options.analysis_window,
        config_fingerprint=config_fingerprint,
        capture_options=policy,
        capture_status=capture_status,
        status=source.status,
        digest=digest,
        gaps=tuple(inputs.gaps),
        parent_child_edges=parent_child_edges,
        boundary_count=len(inputs.boundaries),
        trait_row_count=sum(len(boundary.entries) for boundary in inputs.boundaries),
    )
    _LOG.info(
        "cultural_arm_fields_built run_id=%s boundary_count=%s "
        "trait_row_count=%s document_count=%s spooled=%s",
        run_id,
        evidence.boundary_count,
        evidence.trait_row_count,
        len(documents),
        evidence.status.record_count > 0,
    )
    return {
        "cultural_evolution_evidence": evidence,
        "cultural_evolution_evidence_digest": digest,
        "cultural_evolution_documents": documents,
        "cultural_evolution_capture_status": capture_status,
    }


class CulturalEvidenceRecorder:
    """Store immutable frames without eviction or endpoint fabrication.

    The default strategy keeps frames in memory. An explicit composition-only
    ``spool`` stores verified bytes instead and exposes a pinned source; logical
    quotas still count every logical row even when physical storage deduplicates.
    """

    __slots__ = (
        "_baseline_boundary",
        "_frames",
        "_gaps",
        "_max_frames",
        "_max_rows",
        "_resumed",
        "_rows",
        "_run_id",
        "_source_revision",
        "_spool",
        "_spool_factory",
        "_status",
        "_truncated",
    )

    def __init__(
        self,
        *,
        max_frames: int = DEFAULT_MAX_CULTURAL_FRAMES,
        max_rows: int = DEFAULT_MAX_CULTURAL_ROWS,
        spool: EvidenceSpool | Callable[[str], EvidenceSpool] | None = None,
        source_revision: str = "cultural-evidence-v1",
    ) -> None:
        for name, value in (("max_frames", max_frames), ("max_rows", max_rows)):
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f"{name}: must_be_positive_integer")
        self._max_frames = max_frames
        self._max_rows = max_rows
        self._baseline_boundary: int | None = None
        self._frames: list[CulturalBoundaryExport] = []
        self._gaps: list[str] = []
        self._resumed = False
        self._rows = 0
        self._run_id: str | None = None
        self._truncated = False
        self._source_revision = source_revision
        self._status = CulturalCaptureStatus(active=True, failed=False)
        if spool is not None and callable(spool):
            self._spool_factory: Callable[[str], EvidenceSpool] | None = spool
            self._spool: EvidenceSpool | None = None
        else:
            self._spool_factory = None
            self._spool = spool
        _LOG.debug(
            "cultural_recorder_created max_frames=%s max_rows=%s spooled=%s",
            max_frames,
            max_rows,
            self._spool is not None or self._spool_factory is not None,
        )

    @property
    def source_revision(self) -> str:
        return self._source_revision

    def _ensure_resumed(self) -> None:
        """Reconstruct committed accounting before any read accessor."""
        if self._resumed or self._spool is None:
            return
        self._resume_spooled()

    @property
    def frame_count(self) -> int:
        self._ensure_resumed()
        if self._spool is not None:
            return self._spool.lane_status(CULTURAL_SPOOL_LANE).record_count
        return len(self._frames)

    @property
    def accounting(self) -> CulturalEvidenceAccounting:
        """Report logical capture accounting separately from physical bytes."""
        self._ensure_resumed()
        if self._spool is None:
            return CulturalEvidenceAccounting(
                logical_frames=len(self._frames),
                logical_rows=self._rows,
                physical_records=0,
                physical_bytes=0,
                truncated=self._truncated,
                spooled=False,
            )
        status = self._spool.lane_status(CULTURAL_SPOOL_LANE)
        return CulturalEvidenceAccounting(
            logical_frames=self.frame_count,
            logical_rows=self._rows,
            physical_records=status.record_count,
            physical_bytes=status.byte_count,
            truncated=self._truncated,
            spooled=True,
        )

    @property
    def truncated(self) -> bool:
        return self._truncated

    def start_at_boundary(self, boundary_tick: int) -> None:
        """Declare the first allowed capture after restoring a fork boundary."""
        if isinstance(boundary_tick, bool) or type(boundary_tick) is not int:
            raise TypeError("boundary_tick must be an int")
        if boundary_tick < 0:
            raise ValueError("boundary_tick must be non-negative")
        if self.frame_count:
            raise ValueError("cultural_evidence_baseline_after_capture")
        if self._baseline_boundary is not None:
            raise ValueError("cultural_evidence_baseline_already_set")
        self._baseline_boundary = boundary_tick
        _LOG.info(
            "cultural_evidence_baseline_start boundary_tick=%s",
            boundary_tick,
        )

    def capture(self, frame: CulturalBoundaryExport) -> None:
        """Retain one complete boundary or record an explicit truncation gap."""
        if type(frame) is not CulturalBoundaryExport:
            raise TypeError("frame must be CulturalBoundaryExport")
        if self._status.failed:
            return
        if (
            self._baseline_boundary is not None
            and frame.boundary_tick < self._baseline_boundary
        ):
            raise ValueError("cultural_evidence_before_baseline")
        if self._spool is not None or self._spool_factory is not None:
            self._capture_spooled(frame)
            return
        for existing in self._frames:
            if existing.boundary_tick != frame.boundary_tick:
                continue
            if existing == frame:
                return
            raise ValueError("cultural_evidence_conflict")
        if self._truncated:
            return
        incoming_rows = _ledger_entry_count(frame)
        if (
            len(self._frames) >= self._max_frames
            or self._rows + incoming_rows > self._max_rows
        ):
            self._truncate(frame.boundary_tick)
            return
        self._frames.append(frame)
        self._rows += incoming_rows
        _LOG.debug(
            "cultural_frame_captured boundary_tick=%s owner_count=%s row_count=%s",
            frame.boundary_tick,
            len(frame.owners),
            self._rows,
        )

    def _capture_spooled(self, frame: CulturalBoundaryExport) -> None:
        if self._spool is None:
            if self._spool_factory is None:
                return
            try:
                self._spool = self._spool_factory(frame.run_id)
            except Exception:
                self._fail_spool(frame.boundary_tick)
                return
        assert self._spool is not None
        try:
            if not self._resumed:
                self._resume_spooled()
        except ValueError:
            self._status = CulturalCaptureStatus(
                active=True,
                failed=True,
                failure_boundary=frame.boundary_tick,
                failure_code="cultural_capture_resume_failed",
                missing_prefix_through=self._status.missing_prefix_through,
            )
            _LOG.error(
                "cultural_capture_resume_failed boundary_tick=%s reason_code=%s",
                frame.boundary_tick,
                "cultural_capture_resume_failed",
            )
            return
        if self._run_id is not None and frame.run_id != self._run_id:
            raise ValueError("cultural_evidence_conflict")
        incoming_rows = _ledger_entry_count(frame)
        try:
            payload = encode_cultural_boundary(frame)
            existing = self._spool.get(
                lane=CULTURAL_SPOOL_LANE,
                identity=boundary_identity(frame.boundary_tick),
            )
            if existing is not None:
                if existing == payload:
                    return
                raise ValueError("cultural_evidence_conflict")
            last = self._spool.lane_status(CULTURAL_SPOOL_LANE).last_boundary
            if last is not None and frame.boundary_tick < last:
                raise ValueError("cultural_evidence_conflict")
            if self._truncated:
                return
            if (
                self.frame_count >= self._max_frames
                or self._rows + incoming_rows > self._max_rows
            ):
                self._truncate(frame.boundary_tick)
                return
            added = self._spool.append(
                lane=CULTURAL_SPOOL_LANE,
                boundary_tick=frame.boundary_tick,
                identity=boundary_identity(frame.boundary_tick),
                payload=payload,
            )
        except ValueError as exc:
            if str(exc) == "cultural_evidence_conflict":
                raise
            code = getattr(exc, "code", None)
            if code == "evidence_spool_full":
                self._truncate(frame.boundary_tick)
                return
            if code == "evidence_spool_conflict":
                raise ValueError("cultural_evidence_conflict") from None
            self._fail_spool(frame.boundary_tick)
            return
        except OSError:
            self._fail_spool(frame.boundary_tick)
            return
        self._run_id = frame.run_id
        if added:
            self._rows += incoming_rows
        _LOG.debug(
            "cultural_frame_spooled boundary_tick=%s owner_count=%s row_count=%s",
            frame.boundary_tick,
            len(frame.owners),
            self._rows,
        )

    def _resume_spooled(self) -> None:
        """Reconstruct logical accounting from a supported committed prefix.

        Bounded and explicit: the existing lane is read once in pages, decoded
        with the same codec, and only counts/identities are retained. Missing
        capture is never synthesized and a foreign run fails closed.
        """
        self._resumed = True
        assert self._spool is not None
        status = self._spool.lane_status(CULTURAL_SPOOL_LANE)
        if status.record_count == 0:
            return
        frames = 0
        rows = 0
        cursor: int | None = None
        run_id: str | None = None
        while True:
            payloads = self._spool.iter_lane(
                lane=CULTURAL_SPOOL_LANE,
                after_boundary=cursor,
                limit=_RESUME_PAGE,
            )
            if not payloads:
                break
            for payload in payloads:
                frame = decode_cultural_boundary(payload)
                if run_id is None:
                    run_id = frame.run_id
                elif frame.run_id != run_id:
                    raise ValueError("cultural_evidence_conflict")
                if cursor is not None and frame.boundary_tick <= cursor:
                    raise ValueError("cultural_source_nonadvancing_boundary")
                cursor = frame.boundary_tick
                frames += 1
                rows += _ledger_entry_count(frame)
            if len(payloads) < _RESUME_PAGE:
                break
        self._run_id = run_id
        self._rows = rows
        if frames >= self._max_frames or rows > self._max_rows:
            self._truncated = True
            if "capture_truncated" not in self._gaps:
                self._gaps.append("capture_truncated")
        _LOG.info(
            "cultural_evidence_resumed frames=%s logical_rows=%s "
            "physical_records=%s physical_bytes=%s truncated=%s",
            frames,
            rows,
            status.record_count,
            status.byte_count,
            self._truncated,
        )

    def seal(self) -> None:
        """Seal the optional spool after capture; committed evidence stays."""
        if self._spool is None:
            return
        try:
            status = self._spool.seal()
        except OSError:
            last = self._spool.lane_status(CULTURAL_SPOOL_LANE).last_boundary
            self._fail_spool(
                0 if last is None else last, code="cultural_capture_seal_failed"
            )
            return
        _LOG.info(
            "cultural_evidence_sealed logical_rows=%s physical_records=%s "
            "physical_bytes=%s truncated=%s",
            self._rows,
            status.record_count,
            status.byte_count,
            self._truncated,
        )

    def _fail_spool(
        self, boundary_tick: int, *, code: str = "cultural_capture_spool_failed"
    ) -> None:
        self._status = CulturalCaptureStatus(
            active=True,
            failed=True,
            failure_boundary=boundary_tick,
            failure_code=code,
            missing_prefix_through=self._status.missing_prefix_through,
        )
        _LOG.warning(
            "cultural_capture_spool_failed boundary_tick=%s reason_code=%s",
            boundary_tick,
            code,
        )

    def _truncate(self, boundary_tick: int) -> None:
        self._truncated = True
        if "capture_truncated" not in self._gaps:
            self._gaps.append("capture_truncated")
        _LOG.warning(
            "cultural_capture_truncated boundary_tick=%s frame_count=%s "
            "row_count=%s reason_code=%s",
            boundary_tick,
            self.frame_count,
            self._rows,
            "capture_truncated",
        )

    def merge_capture_status(self, status: CulturalCaptureStatus) -> None:
        """Merge runner-owned failure and missing-prefix facts."""
        if type(status) is not CulturalCaptureStatus:
            raise TypeError("status must be CulturalCaptureStatus")
        missing = self._status.missing_prefix_through
        if status.missing_prefix_through is not None and (
            missing is None or status.missing_prefix_through > missing
        ):
            missing = status.missing_prefix_through
        self._status = CulturalCaptureStatus(
            active=status.active,
            failed=self._status.failed or status.failed,
            failure_boundary=(
                self._status.failure_boundary
                if self._status.failed
                else status.failure_boundary
            ),
            failure_code=(
                self._status.failure_code
                if self._status.failed
                else status.failure_code
            ),
            missing_prefix_through=missing,
        )
        if status.failed:
            _LOG.warning(
                "cultural_capture_failed failure_boundary=%s reason_code=%s",
                status.failure_boundary,
                status.failure_code,
            )

    def source(self) -> CulturalCaptureSource:
        self._ensure_resumed()
        gaps = tuple(sorted(set(self._gaps)))
        if self._spool is not None:
            _LOG.debug(
                "cultural_evidence_source_pinned logical_rows=%s "
                "physical_records=%s physical_bytes=%s",
                self._rows,
                self._spool.lane_status(CULTURAL_SPOOL_LANE).record_count,
                self._spool.lane_status(CULTURAL_SPOOL_LANE).byte_count,
            )
            return SpooledCulturalCaptureSource(
                self._spool,
                run_id=self._run_id or "",
                source_revision=self._source_revision,
                capture_status=self._status,
                gaps=gaps,
            )
        run_id = self._frames[0].run_id if self._frames else ""
        return MemoryCulturalCaptureSource(
            run_id,
            self._source_revision,
            tuple(self._frames),
            gaps,
            self._status,
        )

    def result(self) -> CulturalEvidenceCapture:
        """Return detached frames, gaps, and status.

        Legacy explicit callers only. Scalable consumers use :meth:`source`.
        """
        self._ensure_resumed()
        if self._spool is not None:
            frames = tuple(self.source().iter_boundaries())
            return CulturalEvidenceCapture(
                frames=frames,
                gaps=tuple(sorted(set(self._gaps))),
                capture_status=self._status,
            )
        return CulturalEvidenceCapture(
            frames=tuple(self._frames),
            gaps=tuple(sorted(set(self._gaps))),
            capture_status=self._status,
        )

    def __repr__(self) -> str:
        return (
            f"CulturalEvidenceRecorder(frame_count={self.frame_count}, "
            f"row_count={self._rows}, truncated={self._truncated}, "
            f"spooled={self._spool is not None}, failed={self._status.failed})"
        )
