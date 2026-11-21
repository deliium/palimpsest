# mypy: ignore-errors
"""Catalog append discipline for the six scientific-hypothesis families."""

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

_FIRST_244_DIGEST = (
    "222cca4267d7670390bcbf6db54206cf912e63efab8411512adb1e710b0a4077"
)

_APPENDED = (
    MetricFamilyId.SCIENTIFIC_HYPOTHESIS_STRUCTURE,
    MetricFamilyId.SCIENTIFIC_HYPOTHESIS_EVIDENCE,
    MetricFamilyId.SCIENTIFIC_HYPOTHESIS_TEST_ACTIVITY,
    MetricFamilyId.SCIENTIFIC_HYPOTHESIS_REVISIONS,
    MetricFamilyId.SCIENTIFIC_HYPOTHESIS_PROVENANCE,
    MetricFamilyId.SCIENTIFIC_HYPOTHESIS_PREDICTION_OUTCOMES,
)


def test_catalog_count_is_250_and_validates() -> None:
    validate_metric_catalog()
    specs = all_metric_specifications()
    assert METRIC_FAMILY_COUNT == 275
    assert len(specs) == 275
    assert len({spec.family_id for spec in specs}) == 275


def test_first_244_ids_are_byte_identical() -> None:
    specs = all_metric_specifications()
    material = json.dumps(
        [spec.family_id.value for spec in specs[:244]],
        separators=(",", ":"),
    )
    assert hashlib.sha256(material.encode()).hexdigest() == _FIRST_244_DIGEST


def test_appended_ids_are_exactly_the_six_new_families() -> None:
    specs = all_metric_specifications()
    assert tuple(spec.family_id for spec in specs[244:250]) == _APPENDED
    assert tuple(spec.family_id.value for spec in specs[250:256]) == (
        "scientific_replication_design_lineage",
        "scientific_replication_conditions",
        "scientific_replication_results",
        "scientific_replication_uncertainty",
        "scientific_replication_relationships",
        "scientific_replication_social_interpretation",
    )


def test_every_new_family_uses_the_science_window() -> None:
    for family in _APPENDED:
        spec = metric_specification(family)
        assert spec.cohort_window == "scientific_hypotheses_window_tick"
        assert spec.evidence_inputs
        assert spec.opportunity_vs_occurrence
        assert spec.value_keys
        assert spec.formulas


def test_no_family_is_a_truth_or_composite_score() -> None:
    forbidden = {
        "score",
        "accuracy",
        "calibration",
        "truth",
        "verified",
        "proven",
        "law",
        "rule",
        "severity",
        "rank",
        "merit",
    }
    for family in _APPENDED:
        spec = metric_specification(family)
        assert not (set(spec.value_keys) & forbidden)
        assert "score" not in spec.population
