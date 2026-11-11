"""Metric catalog append-only registration for the operation families."""

from __future__ import annotations

import pytest

from analysis import metric_specification
from analysis.specifications import (
    METRIC_FAMILY_COUNT,
    MetricFamilyId,
    MetricSpecificationError,
    all_metric_specifications,
    validate_metric_catalog,
)

pytestmark = pytest.mark.unit

V4_03_FAMILIES = (
    "organization_formation",
    "organization_membership",
    "organization_structure",
    "organization_lineage",
)


def test_catalog_is_exactly_154() -> None:
    assert METRIC_FAMILY_COUNT == 208
    specs = all_metric_specifications()
    assert len(specs) == 208
    assert len(validate_metric_catalog()) == 208


def test_new_families_are_appended_last() -> None:
    specs = all_metric_specifications()
    assert [spec.family_id.value for spec in specs[140:154]] == [
        *V4_03_FAMILIES,
        "organization_operations",
        "organization_operation_authority",
        "organization_collective_agency",
        "organization_collective_implementation",
        "formal_rule_development",
        "formal_rule_authority",
        "formal_rule_response",
        "dispute_claim_structure",
        "dispute_testimony_independence",
        "dispute_resolution_alignment",
    ]
    assert [spec.family_id.value for spec in specs[154:157]] == [
        "evidence_source_structure",
        "evidence_provenance_continuity",
        "evidence_objective_alignment",
    ]
    assert [spec.family_id.value for spec in specs[157:160]] == [
        "representation_mandate_structure",
        "representation_recognition_support",
        "representation_scope_alignment",
    ]
    assert specs[153].family_id is MetricFamilyId.DISPUTE_RESOLUTION_ALIGNMENT
    assert specs[152].family_id is MetricFamilyId.DISPUTE_TESTIMONY_INDEPENDENCE
    assert specs[151].family_id is MetricFamilyId.DISPUTE_CLAIM_STRUCTURE
    assert specs[150].family_id is MetricFamilyId.FORMAL_RULE_RESPONSE
    assert specs[149].family_id is MetricFamilyId.FORMAL_RULE_AUTHORITY
    assert specs[148].family_id is MetricFamilyId.FORMAL_RULE_DEVELOPMENT
    assert specs[147].family_id is MetricFamilyId.ORGANIZATION_COLLECTIVE_IMPLEMENTATION
    assert specs[146].family_id is MetricFamilyId.ORGANIZATION_COLLECTIVE_AGENCY
    assert specs[145].family_id is MetricFamilyId.ORGANIZATION_OPERATION_AUTHORITY
    assert specs[144].family_id is MetricFamilyId.ORGANIZATION_OPERATIONS

def test_existing_families_keep_identity_and_order() -> None:
    specs = all_metric_specifications()
    first = specs[:144]
    identifiers = [spec.family_id.value for spec in first]
    assert len(set(identifiers)) == 144
    assert "organization_operations" not in identifiers
    assert "organization_operation_authority" not in identifiers
    assert identifiers[-4:] == list(V4_03_FAMILIES)
    for spec in first:
        assert spec.algorithm_version == "1"


def test_lookup_is_exact_and_fail_closed() -> None:
    for family in (
        MetricFamilyId.ORGANIZATION_OPERATIONS,
        MetricFamilyId.ORGANIZATION_OPERATION_AUTHORITY,
    ):
        spec = metric_specification(family)
        assert spec.family_id is family
        assert spec.value_keys
    with pytest.raises(MetricSpecificationError):
        metric_specification("organization_operations_v2")
