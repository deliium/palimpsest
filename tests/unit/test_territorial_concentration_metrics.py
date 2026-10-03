"""Territorial concentration metric tests."""

from __future__ import annotations

from analysis.models import MetricAvailability
from analysis.territorial_concentration_metrics import (
    TerritorialConcentrationRow,
    compute_territorial_concentration,
)


def test_empty_rows_absent() -> None:
    doc = compute_territorial_concentration(
        (), control_rows=(), run_id="run-t", input_revision="rev-1"
    )
    assert doc.availability is MetricAvailability.ABSENT
    assert doc.values == {}


def test_presence_hhi_and_top_shares() -> None:
    presence = [
        TerritorialConcentrationRow(location_id="loc-a", tick=1, agent_id="a"),
        TerritorialConcentrationRow(location_id="loc-a", tick=2, agent_id="b"),
        TerritorialConcentrationRow(location_id="loc-b", tick=1, agent_id="c"),
    ]
    doc = compute_territorial_concentration(
        presence, run_id="run-t", input_revision="rev-1"
    )
    assert doc.availability is MetricAvailability.PARTIAL
    assert doc.values["presence_location_count"] == 2
    # Shares 2/3 and 1/3 → HHI = (2/3)^2 + (1/3)^2
    expected_hhi = (2.0 / 3.0) ** 2 + (1.0 / 3.0) ** 2
    assert abs(float(doc.values["presence_hhi"]) - expected_hhi) < 1e-12
    assert abs(float(doc.values["presence_top1_share"]) - (2.0 / 3.0)) < 1e-12
    assert "control_hhi" not in doc.values


def test_both_channels_present() -> None:
    presence = [TerritorialConcentrationRow(location_id="loc-a", tick=1)]
    control = [
        TerritorialConcentrationRow(location_id="loc-a", tick=1),
        TerritorialConcentrationRow(location_id="loc-b", tick=1),
    ]
    doc = compute_territorial_concentration(
        presence, control, run_id="run-t", input_revision="rev-1"
    )
    assert doc.availability is MetricAvailability.PRESENT
    assert doc.values["presence_hhi"] == 1.0
    assert doc.values["control_top1_share"] == 0.5
