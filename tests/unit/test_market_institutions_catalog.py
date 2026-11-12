"""Metric catalog append: 204 -> 212 with a stable leading block."""

from __future__ import annotations

import hashlib

import pytest

from analysis.specifications import (
    METRIC_FAMILY_COUNT,
    MetricFamilyId,
    all_metric_specifications,
    metric_specification,
    validate_metric_catalog,
)

pytestmark = pytest.mark.unit

_BASELINE_DIGEST = "7b830c00ace8a044c0d65a28dd81448642bbb13a328c837e08420886cd73dec2"


def test_catalog_has_212_families_and_validates() -> None:
    assert METRIC_FAMILY_COUNT == 216
    specs = validate_metric_catalog()
    assert len(specs) == 216


def test_first_204_specifications_are_unchanged() -> None:
    specs = all_metric_specifications()
    material = "\x1e".join(
        "\x1f".join(
            (spec.family_id.value, spec.algorithm_version, ",".join(spec.value_keys))
        )
        for spec in specs[:204]
    )
    assert hashlib.sha256(material.encode()).hexdigest() == _BASELINE_DIGEST


def test_market_families_append_in_locked_order() -> None:
    specs = all_metric_specifications()
    assert tuple(spec.family_id for spec in specs[204:208]) == (
        MetricFamilyId.MARKET_VENUE_RECURRENCE,
        MetricFamilyId.MARKET_VENUE_PERSISTENCE,
        MetricFamilyId.MARKET_EXPECTATION_STRUCTURE,
        MetricFamilyId.MARKET_ROLE_STRUCTURE,
    )
    assert metric_specification("market_venue_recurrence").family_id is (
        MetricFamilyId.MARKET_VENUE_RECURRENCE
    )


def test_price_families_append_after_the_market_block() -> None:
    specs = all_metric_specifications()
    assert tuple(spec.family_id for spec in specs[208:212]) == (
        MetricFamilyId.PRICE_EXPECTATION_STRUCTURE,
        MetricFamilyId.PRICE_DISTRIBUTION_DISPERSION,
        MetricFamilyId.PRICE_REFERENCE_UNIT_ALIGNMENT,
        MetricFamilyId.MARKET_PRICE_CONVERGENCE,
    )
