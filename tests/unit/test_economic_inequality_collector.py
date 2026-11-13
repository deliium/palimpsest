# mypy: ignore-errors
"""Collector injection of economic-inequality analysis is gated and contained."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from analysis.economic_inequality_analysis import (
    harvest_economic_inequality_analysis,
)
from analysis.economic_inequality_rows import EconomicPossessionRow
from analysis.metric_service import MetricComputationInputs

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]


def test_metric_inputs_accept_the_economic_analysis() -> None:
    analysis = harvest_economic_inequality_analysis(
        possession_rows=tuple(
            EconomicPossessionRow(
                owner_token=f"eio-{owner:016x}",
                tick=0,
                window_index=0,
                observed_item_count=owner,
                observed_tool_count=0,
            )
            for owner in range(4)
        )
    )
    inputs = MetricComputationInputs(
        run_id="run-1", input_revision="rev-1", window_end=0
    )
    updated = replace(inputs, economic_inequality_analysis=analysis)
    assert updated.economic_inequality_analysis is analysis


def test_collector_requires_events_and_an_economic_channel() -> None:
    source = (ROOT / "src" / "experiments" / "collectors.py").read_text(
        encoding="utf-8"
    )
    assert "build_completed_run_economic_inequality_analysis" in source
    assert "economic_inequality_completed_run" in source
    assert "economic_inequality_collector_injected" in source
    assert "economic_inequality_collector_failed" in source
    assert "economic_inequality_analysis=economic_analysis" in source
    for channel in (
        "organizations",
        "markets_credit",
        "infrastructure_networks",
        "supply_chains",
        "durable_records",
        "structured_commitments",
        "subjective_valuation",
    ):
        assert channel in source


def test_collector_failure_is_contained() -> None:
    source = (ROOT / "src" / "experiments" / "collectors.py").read_text(
        encoding="utf-8"
    )
    block = source.split("economic_enabled =", 1)[1].split("regions_spec =", 1)[0]
    assert "except Exception as exc:" in block
    assert 'getattr(exc, "reason_code", type(exc).__name__)' in block
    assert "_LOG.error" in block
