"""Metric catalog append: 208 -> 212 with a stable leading block."""

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

_BASELINE_208_DIGEST = (
    "addd1dc350b8c0f7588132845138951f48f5595891e2bd136094a381cf734fed"
)


def test_catalog_has_212_families_and_validates() -> None:
    assert METRIC_FAMILY_COUNT == 216
    specs = validate_metric_catalog()
    assert len(specs) == 216


def test_first_208_specifications_are_unchanged() -> None:
    specs = all_metric_specifications()
    material = "\x1e".join(
        "\x1f".join(
            (spec.family_id.value, spec.algorithm_version, ",".join(spec.value_keys))
        )
        for spec in specs[:208]
    )
    assert hashlib.sha256(material.encode()).hexdigest() == _BASELINE_208_DIGEST


def test_price_families_append_in_locked_order() -> None:
    specs = all_metric_specifications()
    assert tuple(spec.family_id for spec in specs[208:212]) == (
        MetricFamilyId.PRICE_EXPECTATION_STRUCTURE,
        MetricFamilyId.PRICE_DISTRIBUTION_DISPERSION,
        MetricFamilyId.PRICE_REFERENCE_UNIT_ALIGNMENT,
        MetricFamilyId.MARKET_PRICE_CONVERGENCE,
    )
    assert metric_specification("price_expectation_structure").family_id is (
        MetricFamilyId.PRICE_EXPECTATION_STRUCTURE
    )


def test_price_specs_match_locked_triples() -> None:
    expected = {
        "price_expectation_structure": (
            "owner_scoped_price_expectations",
            "observed_expectation_rows",
            "evaluable_claims",
        ),
        "price_distribution_dispersion": (
            "analytical_price_distributions",
            "observed_distribution_samples",
            "active_edges",
        ),
        "price_reference_unit_alignment": (
            "owner_scoped_price_units",
            "observed_unit_rows",
            "evaluable_claims",
        ),
        "market_price_convergence": (
            "analytical_price_relations",
            "observed_relation_pairs",
            "active_edges",
        ),
    }
    for family, (population, denominator, kind) in expected.items():
        spec = metric_specification(family)
        assert spec.population == population
        assert spec.denominator == denominator
        assert spec.denominator_kind.value == kind


def test_no_price_family_value_key_is_forbidden() -> None:
    for spec in all_metric_specifications()[208:212]:
        assert "price" not in spec.value_keys
        assert "canonical_price" not in spec.value_keys
