"""Phenomenon indicator panel builder tests."""

from __future__ import annotations

from analysis.models import (
    METRIC_DOCUMENT_SCHEMA_VERSION,
    MetricAvailability,
    MetricDocument,
    MetricProvenance,
)
from analysis.numerical import library_versions
from analysis.phenomenon_models import SupportBand
from analysis.phenomenon_panel import build_phenomenon_indicator_panel
from analysis.evidence import EvidenceStage


def _doc(family: str, values: dict[str, object]) -> MetricDocument:
    return MetricDocument(
        schema_version=METRIC_DOCUMENT_SCHEMA_VERSION,
        metric_family=family,
        algorithm_version="1",
        library_versions=library_versions(),
        run_id="run-p",
        input_revision="rev-1",
        evidence_stages=frozenset({EvidenceStage.OBJECTIVE_EVENT_STATE}),
        population="test",
        denominator="test",
        coverage=None,
        availability=MetricAvailability.PRESENT,
        values=values,
        provenance=MetricProvenance(
            source_kind="test", source_ids=(), notes_code="ok"
        ),
    )


def test_panel_missing_families_absent() -> None:
    panel = build_phenomenon_indicator_panel(
        [], run_id="run-p", input_revision="rev-1"
    )
    assert len(panel.readings) == 18
    assert all(reading.support_band is SupportBand.ABSENT for reading in panel.readings)


def test_panel_reciprocity_unary_weak() -> None:
    docs = [_doc("trust_network_structure", {"reciprocity": 0.9})]
    panel = build_phenomenon_indicator_panel(
        docs, run_id="run-p", input_revision="rev-1"
    )
    reciprocity = next(
        reading
        for reading in panel.readings
        if reading.phenomenon_id.value == "reciprocity"
    )
    assert reciprocity.support_band is SupportBand.WEAK
    assert reciprocity.present_indicator_count == 1
