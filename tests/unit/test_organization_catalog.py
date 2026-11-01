"""Organization catalog registration: 144 families, append-only order."""

from __future__ import annotations

import pytest

from analysis import (
    MetricAvailability,
    all_metric_specifications,
    metric_specification,
    validate_metric_catalog,
)
from analysis.specifications import METRIC_FAMILY_COUNT, MetricFamilyId

pytestmark = pytest.mark.unit

ORGANIZATION_FAMILIES = (
    MetricFamilyId.ORGANIZATION_FORMATION,
    MetricFamilyId.ORGANIZATION_MEMBERSHIP,
    MetricFamilyId.ORGANIZATION_STRUCTURE,
    MetricFamilyId.ORGANIZATION_LINEAGE,
)


def test_catalog_validates_at_146() -> None:
    specs = validate_metric_catalog()
    assert METRIC_FAMILY_COUNT == 146
    assert len(specs) == 146
    assert len({spec.family_id for spec in specs}) == 146
    assert tuple(spec.family_id for spec in specs[-6:-2]) == ORGANIZATION_FAMILIES
    assert tuple(spec.family_id for spec in specs[-10:-6]) == (
        MetricFamilyId.MACRO_SOCIETY_STRUCTURE,
        MetricFamilyId.MACRO_SOCIETY_IDENTITY_ALIGNMENT,
        MetricFamilyId.MACRO_SOCIETY_LINEAGE,
        MetricFamilyId.MACRO_SOCIETY_MEMBERSHIP_DISPUTE,
    )


def test_organization_families_are_exact() -> None:
    expected = {
        MetricFamilyId.ORGANIZATION_FORMATION: {
            "as_of_tick",
            "candidate_count",
            "coverage_ratio",
            "mean_structural_channels",
            "multi_channel_candidate_count",
            "recognized_count",
            "temporary_count",
            "window_count",
        },
        MetricFamilyId.ORGANIZATION_MEMBERSHIP: {
            "as_of_tick",
            "disputed_count",
            "explicit_count",
            "former_count",
            "member_belief_count",
            "overlap_member_count",
            "perceived_count",
            "temporary_member_count",
            "unknown_count",
            "unresolved_member_count",
        },
        MetricFamilyId.ORGANIZATION_STRUCTURE: {
            "as_of_tick",
            "candidates_with_goals",
            "candidates_with_records",
            "candidates_with_roles",
            "commitment_count",
            "goal_count",
            "identity_count",
            "mean_structural_channels",
            "procedure_count",
            "record_count",
            "resource_count",
            "role_count",
        },
        MetricFamilyId.ORGANIZATION_LINEAGE: {
            "as_of_tick",
            "continuation_count",
            "dissolution_count",
            "emergence_count",
            "lineage_window_count",
            "mean_continuation_jaccard",
            "merge_count",
            "split_count",
            "transform_count",
        },
    }
    for family, keys in expected.items():
        spec = metric_specification(family)
        assert set(spec.value_keys) == keys
        assert spec.version_identifier.endswith("@1")
        assert MetricAvailability.ABSENT.value == "absent"
        assert spec.empty_case
        assert spec.unknown_case

    versions = [spec.version_identifier for spec in all_metric_specifications()]
    assert versions[-6:-2] == [
        "organization_formation@1",
        "organization_membership@1",
        "organization_structure@1",
        "organization_lineage@1",
    ]


def test_no_composite_organization_score_exists() -> None:
    ids = {spec.family_id.value for spec in all_metric_specifications()}
    assert not any(
        "organization_score" in family or "organization_capacity" in family
        for family in ids
    )
