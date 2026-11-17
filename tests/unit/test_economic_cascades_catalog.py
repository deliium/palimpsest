# mypy: ignore-errors
"""Catalog append discipline for the eight economic-cascade families."""

from __future__ import annotations

import hashlib
import json

from analysis.specifications import (
    METRIC_FAMILY_COUNT,
    MetricFamilyId,
    all_metric_specifications,
    metric_specification,
    validate_metric_catalog,
)

_FIRST_236_DIGEST = (
    "68f7d685370818246eb03ed4c8cac961a941095f30e465c5204cc5abd226d671"
)

_APPENDED = (
    MetricFamilyId.RESOURCE_LOSS_CASCADE,
    MetricFamilyId.ROUTE_CLOSURE_CASCADE,
    MetricFamilyId.INFRASTRUCTURE_DESTRUCTION_CASCADE,
    MetricFamilyId.POPULATION_LOSS_CASCADE,
    MetricFamilyId.TOOL_SHORTAGE_CASCADE,
    MetricFamilyId.CASCADE_DEPENDENCY_STRUCTURE,
    MetricFamilyId.CASCADE_PROPAGATION,
    MetricFamilyId.CASCADE_COVERAGE,
)


def test_catalog_count_is_244_and_validates() -> None:
    validate_metric_catalog()
    specs = all_metric_specifications()
    assert METRIC_FAMILY_COUNT == 256
    assert len(specs) == 256
    assert len({spec.family_id for spec in specs}) == 256


def test_first_236_ids_are_byte_identical() -> None:
    specs = all_metric_specifications()
    material = json.dumps(
        [spec.family_id.value for spec in specs[:236]],
        separators=(",", ":"),
    )
    assert hashlib.sha256(material.encode()).hexdigest() == _FIRST_236_DIGEST


def test_appended_ids_are_exactly_the_eight_new_families() -> None:
    specs = all_metric_specifications()
    assert tuple(spec.family_id for spec in specs[236:244]) == _APPENDED


def test_every_new_family_uses_the_cascade_window() -> None:
    for family in _APPENDED:
        spec = metric_specification(family)
        assert spec.cohort_window == "cascade_window_tick"
        assert spec.evidence_inputs
        assert spec.opportunity_vs_occurrence
        assert spec.value_keys
        assert spec.formulas


def test_no_family_is_a_composite_score() -> None:
    forbidden = {
        "severity",
        "criticality",
        "priority",
        "impact_score",
        "cascade_score",
        "risk_score",
        "blame",
        "root_cause",
    }
    for family in _APPENDED:
        spec = metric_specification(family)
        assert not (set(spec.value_keys) & forbidden)
        assert "score" not in spec.population
