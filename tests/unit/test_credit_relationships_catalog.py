"""Append-only credit metric catalog positions and keys."""

from __future__ import annotations

import pytest

from analysis.specifications import (
    CREDIT_DISTRIBUTION_STRUCTURE_KEYS,
    CREDIT_RELATIONSHIP_FORMATION_KEYS,
    CREDIT_REPAYMENT_PERFORMANCE_KEYS,
    CREDIT_TERM_ALIGNMENT_KEYS,
    METRIC_FAMILY_COUNT,
    MetricFamilyId,
    all_metric_specifications,
    metric_specification,
)

pytestmark = pytest.mark.unit


def test_catalog_appends_exactly_four_families() -> None:
    specifications = all_metric_specifications()
    assert METRIC_FAMILY_COUNT == 216
    assert len(specifications) == 216
    assert [spec.family_id for spec in specifications[-4:]] == [
        MetricFamilyId.CREDIT_RELATIONSHIP_FORMATION,
        MetricFamilyId.CREDIT_REPAYMENT_PERFORMANCE,
        MetricFamilyId.CREDIT_TERM_ALIGNMENT,
        MetricFamilyId.CREDIT_DISTRIBUTION_STRUCTURE,
    ]
    assert specifications[-5].family_id is MetricFamilyId.MARKET_PRICE_CONVERGENCE


@pytest.mark.parametrize(
    ("family", "keys"),
    (
        (
            MetricFamilyId.CREDIT_RELATIONSHIP_FORMATION,
            CREDIT_RELATIONSHIP_FORMATION_KEYS,
        ),
        (
            MetricFamilyId.CREDIT_REPAYMENT_PERFORMANCE,
            CREDIT_REPAYMENT_PERFORMANCE_KEYS,
        ),
        (MetricFamilyId.CREDIT_TERM_ALIGNMENT, CREDIT_TERM_ALIGNMENT_KEYS),
        (
            MetricFamilyId.CREDIT_DISTRIBUTION_STRUCTURE,
            CREDIT_DISTRIBUTION_STRUCTURE_KEYS,
        ),
    ),
)
def test_credit_family_ids_versions_and_keys_are_exact(
    family: MetricFamilyId, keys: tuple[str, ...]
) -> None:
    specification = metric_specification(family)
    assert specification.family_id is family
    assert specification.algorithm_version == "1"
    assert specification.value_keys == keys
    assert specification.cohort_window == "credit_relationships_window_tick"
    assert specification.availability_behavior == (
        "explicit_unknown_without_credit_evidence"
    )


def test_lookup_works_for_both_enum_and_string() -> None:
    assert metric_specification(
        "credit_relationship_formation"
    ).family_id is MetricFamilyId.CREDIT_RELATIONSHIP_FORMATION
