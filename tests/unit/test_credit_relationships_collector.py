"""Collector injection of credit analysis is gated and contained."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from analysis.credit_relationships_analysis import (
    harvest_credit_relationships_analysis,
)
from analysis.metric_service import MetricComputationInputs
from tests.unit.credit_relationships_analysis_helpers import frame, talked

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]


def test_metric_inputs_accept_the_credit_analysis() -> None:
    analysis = harvest_credit_relationships_analysis(
        committed_events=[talked("evt-1", frame())]
    )
    inputs = MetricComputationInputs(
        run_id="run-1", input_revision="rev-1", window_end=0
    )
    updated = replace(inputs, credit_relationships_analysis=analysis)
    assert updated.credit_relationships_analysis is analysis


def test_collector_requires_events_flag_and_commitments() -> None:
    source = (ROOT / "src" / "experiments" / "collectors.py").read_text(
        encoding="utf-8"
    )
    assert "build_completed_run_credit_relationships_analysis" in source
    assert "markets_credit" in source
    assert "structured_commitments" in source
    assert "credit_relationships_collector_failed" in source
    assert "credit_relationships_analysis=credit_analysis" in source
