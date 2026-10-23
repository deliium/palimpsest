"""Bounded outer-layer recorder for detached cultural boundary exports."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Final

from analysis.cultural_evolution_evidence import (
    ArchiveKnowledgeState,
    CulturalAnalysisWindow,
    CulturalEvolutionInputs,
    GroupMembership,
    normalize_cultural_frames,
)
from experiments.cultural_metric_artifacts import (
    CulturalCaptureOptions,
    cultural_capture_policy,
)
from simulation.cultural_evidence import (
    CulturalBoundaryExport,
    CulturalCaptureStatus,
)
from simulation.runner import SimulationRunner

_LOG: Final[logging.Logger] = logging.getLogger("experiments.cultural_evidence")

DEFAULT_MAX_CULTURAL_FRAMES: Final[int] = 10_000
DEFAULT_MAX_CULTURAL_ROWS: Final[int] = 1_000_000

__all__ = [
    "DEFAULT_MAX_CULTURAL_FRAMES",
    "DEFAULT_MAX_CULTURAL_ROWS",
    "CulturalEvidenceCapture",
    "CulturalEvidenceRecorder",
    "build_cultural_arm_fields",
    "cultural_evolution_inputs_from_capture",
    "install_cultural_recorder",
    "kinship_parent_child_edges",
]


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
    from analysis.cultural_evolution_metrics import (
        assemble_cultural_evolution_documents,
    )
    from experiments.cultural_evidence_serialization import evidence_digest

    capture = recorder.result()
    inputs = cultural_evolution_inputs_from_capture(
        capture,
        run_id=run_id,
        source_revision=source_revision,
        window=options.analysis_window,
        parent_child_edges=parent_child_edges,
    )
    digest = evidence_digest(
        inputs,
        config_fingerprint=config_fingerprint,
        capture_options=cultural_capture_policy(options),
        capture_status=capture.capture_status,
    )
    documents = assemble_cultural_evolution_documents(
        inputs,
        evidence_manifest_digest=digest,
    )
    return {
        "cultural_evolution_evidence": inputs,
        "cultural_evolution_evidence_digest": digest,
        "cultural_evolution_documents": documents,
        "cultural_evolution_capture_status": capture.capture_status,
    }


class CulturalEvidenceRecorder:
    """Store immutable frames without eviction or endpoint fabrication."""

    __slots__ = (
        "_frames",
        "_gaps",
        "_max_frames",
        "_max_rows",
        "_rows",
        "_status",
        "_truncated",
    )

    def __init__(
        self,
        *,
        max_frames: int = DEFAULT_MAX_CULTURAL_FRAMES,
        max_rows: int = DEFAULT_MAX_CULTURAL_ROWS,
    ) -> None:
        for name, value in (("max_frames", max_frames), ("max_rows", max_rows)):
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f"{name}: must_be_positive_integer")
        self._max_frames = max_frames
        self._max_rows = max_rows
        self._frames: list[CulturalBoundaryExport] = []
        self._gaps: list[str] = []
        self._rows = 0
        self._truncated = False
        self._status = CulturalCaptureStatus(active=True, failed=False)
        _LOG.debug(
            "cultural_recorder_created max_frames=%s max_rows=%s",
            max_frames,
            max_rows,
        )

    @property
    def frame_count(self) -> int:
        return len(self._frames)

    @property
    def truncated(self) -> bool:
        return self._truncated

    def capture(self, frame: CulturalBoundaryExport) -> None:
        """Retain one complete boundary or record an explicit truncation gap."""
        if type(frame) is not CulturalBoundaryExport:
            raise TypeError("frame must be CulturalBoundaryExport")
        if self._status.failed:
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
            self._truncated = True
            self._gaps.append("capture_truncated")
            _LOG.warning(
                "cultural_capture_truncated frame_count=%s row_count=%s reason_code=%s",
                len(self._frames),
                self._rows,
                "capture_truncated",
            )
            return
        self._frames.append(frame)
        self._rows += incoming_rows
        _LOG.debug(
            "cultural_frame_captured boundary_tick=%s owner_count=%s row_count=%s",
            frame.boundary_tick,
            len(frame.owners),
            self._rows,
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
            failed=status.failed,
            failure_boundary=status.failure_boundary,
            failure_code=status.failure_code,
            missing_prefix_through=missing,
        )
        if status.failed:
            _LOG.warning(
                "cultural_capture_failed failure_boundary=%s reason_code=%s",
                status.failure_boundary,
                status.failure_code,
            )

    def result(self) -> CulturalEvidenceCapture:
        """Return detached frames, gaps, and status."""
        return CulturalEvidenceCapture(
            frames=tuple(self._frames),
            gaps=tuple(sorted(set(self._gaps))),
            capture_status=self._status,
        )

    def __repr__(self) -> str:
        return (
            f"CulturalEvidenceRecorder(frame_count={len(self._frames)}, "
            f"row_count={self._rows}, truncated={self._truncated}, "
            f"failed={self._status.failed})"
        )
