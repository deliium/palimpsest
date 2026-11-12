"""Collector injection of the price analysis is gated and contained."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from analysis.emergent_prices_analysis import harvest_emergent_prices_analysis
from analysis.metric_service import MetricComputationInputs
from tests.unit.emergent_prices_analysis_helpers import completed

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]


def test_metric_inputs_accept_the_price_analysis() -> None:
    analysis = harvest_emergent_prices_analysis(
        committed_events=[completed("event-1")]
    )
    inputs = MetricComputationInputs(
        run_id="run-1", input_revision="rev-1", window_end=0
    )
    updated = replace(inputs, emergent_prices_analysis=analysis)
    assert updated.emergent_prices_analysis is analysis


def test_collector_requires_events_flag_and_valuation() -> None:
    source = (ROOT / "src" / "experiments" / "collectors.py").read_text(
        encoding="utf-8"
    )
    assert "build_completed_run_emergent_prices_analysis" in source
    assert "markets_credit" in source
    assert "subjective_valuation" in source
    assert "emergent_prices_collector_failed" in source
    assert "emergent_prices_analysis=price_analysis" in source
