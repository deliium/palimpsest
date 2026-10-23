"""Boundary-qualified cultural evidence capture."""

from __future__ import annotations

import pytest

from experiments.cultural_evidence import CulturalEvidenceRecorder
from simulation.cultural_evidence import CulturalBoundaryExport

pytestmark = pytest.mark.unit


def _frame(tick: int) -> CulturalBoundaryExport:
    return CulturalBoundaryExport(run_id="run", boundary_tick=tick, owners=())


def test_baseline_rejects_earlier_and_duplicate_initialization() -> None:
    recorder = CulturalEvidenceRecorder()
    recorder.start_at_boundary(4)
    with pytest.raises(ValueError, match="cultural_evidence_baseline_already_set"):
        recorder.start_at_boundary(4)
    with pytest.raises(ValueError, match="cultural_evidence_before_baseline"):
        recorder.capture(_frame(3))
    recorder.capture(_frame(4))
    recorder.capture(_frame(4))
    assert [frame.boundary_tick for frame in recorder.result().frames] == [4]
    with pytest.raises(ValueError, match="cultural_evidence_baseline_after_capture"):
        recorder.start_at_boundary(5)


def test_no_baseline_preserves_default_tick_zero_behavior() -> None:
    recorder = CulturalEvidenceRecorder()
    recorder.capture(_frame(0))
    recorder.capture(_frame(1))
    assert [frame.boundary_tick for frame in recorder.result().frames] == [0, 1]
