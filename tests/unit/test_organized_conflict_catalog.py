# ruff: noqa: E501
# mypy: disable-error-code="arg-type,assignment,union-attr,attr-defined,no-untyped-def,no-untyped-call,call-overload,index,type-arg,unused-ignore"
from __future__ import annotations

import hashlib
import json

from analysis.specifications import (
    METRIC_FAMILY_COUNT,
    MetricFamilyId,
    all_metric_specifications,
    validate_metric_catalog,
)

LAST_FOUR = (
    "border_claim_structure",
    "border_overlap_contest",
    "border_agreement_recognition",
    "border_control_alignment",
)
V4_12_FAMILIES = (
    "organized_conflict_participation",
    "organized_conflict_persistence",
    "organized_conflict_outcomes",
    "organized_conflict_interpretation",
)


def test_catalog_is_exactly_176_with_four_appended() -> None:
    specs = validate_metric_catalog()
    assert METRIC_FAMILY_COUNT == 204
    assert len(specs) == 204
    assert tuple(spec.family_id.value for spec in specs[172:176]) == LAST_FOUR
    assert tuple(item.value for item in tuple(MetricFamilyId)[172:176]) == LAST_FOUR
    assert (
        tuple(spec.family_id.value for spec in specs[168:172]) == V4_12_FAMILIES
    )


def test_first_168_keep_their_order_versions_and_value_keys() -> None:
    specs = all_metric_specifications()[:168]
    payload = [
        [spec.family_id.value, spec.algorithm_version, list(spec.value_keys)]
        for spec in specs
    ]
    digest = hashlib.sha256(
        json.dumps(payload, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    assert digest == "63294c8c22b4c1060491ad5212b2641bd7f0f67aceeb248d127cc43d84cc995f"
    assert all(spec.algorithm_version == "1" for spec in specs)
