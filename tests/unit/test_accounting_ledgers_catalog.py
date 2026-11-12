"""Append-only accounting metric catalog positions and keys."""

# mypy: ignore-errors

from __future__ import annotations

import hashlib

import pytest

from analysis.specifications import (
    ACCOUNTING_ENTRY_ALIGNMENT_KEYS,
    ACCOUNTING_FLOW_STRUCTURE_KEYS,
    ACCOUNTING_RECORD_CONDITION_KEYS,
    ACCOUNTING_RECORD_COVERAGE_KEYS,
    METRIC_FAMILY_COUNT,
    MetricFamilyId,
    all_metric_specifications,
    metric_specification,
    validate_metric_catalog,
)

pytestmark = pytest.mark.unit


def test_catalog_appends_exactly_four_accounting_families() -> None:
    specifications = all_metric_specifications()
    assert METRIC_FAMILY_COUNT == 220
    assert len(specifications) == 220
    assert [spec.family_id for spec in specifications[-4:]] == [
        MetricFamilyId.ACCOUNTING_RECORD_COVERAGE,
        MetricFamilyId.ACCOUNTING_ENTRY_ALIGNMENT,
        MetricFamilyId.ACCOUNTING_RECORD_CONDITION,
        MetricFamilyId.ACCOUNTING_FLOW_STRUCTURE,
    ]
    assert (
        specifications[-5].family_id
        is MetricFamilyId.CREDIT_DISTRIBUTION_STRUCTURE
    )


def test_first_220_catalog_is_unchanged() -> None:
    specifications = all_metric_specifications()[:216]
    material = "\n".join(
        spec.family_id.value for spec in specifications
    ).encode("utf-8")
    assert hashlib.sha256(material).hexdigest() == (
        "e050842db2ff0ff8848f5132a168712e17f8ad960fdb7f156abe9157c81889a1"
    )


@pytest.mark.parametrize(
    ("family", "keys"),
    (
        (
            MetricFamilyId.ACCOUNTING_RECORD_COVERAGE,
            ACCOUNTING_RECORD_COVERAGE_KEYS,
        ),
        (
            MetricFamilyId.ACCOUNTING_ENTRY_ALIGNMENT,
            ACCOUNTING_ENTRY_ALIGNMENT_KEYS,
        ),
        (
            MetricFamilyId.ACCOUNTING_RECORD_CONDITION,
            ACCOUNTING_RECORD_CONDITION_KEYS,
        ),
        (
            MetricFamilyId.ACCOUNTING_FLOW_STRUCTURE,
            ACCOUNTING_FLOW_STRUCTURE_KEYS,
        ),
    ),
)
def test_accounting_family_ids_versions_and_keys_are_exact(
    family: MetricFamilyId, keys: tuple[str, ...]
) -> None:
    specification = metric_specification(family)
    assert specification.family_id is family
    assert specification.algorithm_version == "1"
    assert specification.value_keys == keys
    assert specification.cohort_window == "accounting_ledgers_window_tick"
    assert specification.availability_behavior == (
        "explicit_unknown_without_accounting_evidence"
    )
    assert keys[0] == "accounting_ledgers_window_tick"


def test_catalog_validates() -> None:
    assert len(validate_metric_catalog()) == 220


def test_lookup_works_for_both_enum_and_string() -> None:
    assert metric_specification(
        "accounting_record_coverage"
    ).family_id is MetricFamilyId.ACCOUNTING_RECORD_COVERAGE
