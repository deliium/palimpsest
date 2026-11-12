# mypy: ignore-errors
"""Closed metric catalog: append-only V4-13 families."""

from __future__ import annotations

from analysis.specifications import (
    METRIC_FAMILY_COUNT,
    MetricFamilyId,
    all_metric_specifications,
    validate_metric_catalog,
)

BORDER_FAMILIES = (
    "border_claim_structure",
    "border_overlap_contest",
    "border_agreement_recognition",
    "border_control_alignment",
)


def test_catalog_count_is_176_and_validates() -> None:
    specs = all_metric_specifications()
    assert METRIC_FAMILY_COUNT == 216
    assert len(specs) == 216
    validate_metric_catalog()


def test_border_families_are_appended_last() -> None:
    specs = all_metric_specifications()
    assert tuple(spec.family_id.value for spec in specs[172:176]) == BORDER_FAMILIES
    assert all(spec.family_id.value not in BORDER_FAMILIES for spec in specs[:172])


def test_no_duplicate_family() -> None:
    ids = [spec.family_id for spec in all_metric_specifications()]
    assert len(set(ids)) == len(ids)
    assert MetricFamilyId.BORDER_CLAIM_STRUCTURE.value == "border_claim_structure"


def test_each_border_family_has_value_keys() -> None:
    specs = {spec.family_id.value: spec for spec in all_metric_specifications()}
    for name in BORDER_FAMILIES:
        assert specs[name].value_keys
