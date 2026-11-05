"""Catalog registration for the four macro-society families."""

from __future__ import annotations

from analysis.serialization import is_supported_metric_family
from analysis.specifications import (
    METRIC_FAMILY_COUNT,
    MetricFamilyId,
    all_metric_specifications,
    metric_specification,
    validate_metric_catalog,
)

MACRO_FAMILIES = (
    MetricFamilyId.MACRO_SOCIETY_STRUCTURE,
    MetricFamilyId.MACRO_SOCIETY_IDENTITY_ALIGNMENT,
    MetricFamilyId.MACRO_SOCIETY_LINEAGE,
    MetricFamilyId.MACRO_SOCIETY_MEMBERSHIP_DISPUTE,
)
ORGANIZATION_FAMILIES = (
    MetricFamilyId.ORGANIZATION_FORMATION,
    MetricFamilyId.ORGANIZATION_MEMBERSHIP,
    MetricFamilyId.ORGANIZATION_STRUCTURE,
    MetricFamilyId.ORGANIZATION_LINEAGE,
)


def test_catalog_validates_at_154_and_appends_macro_families() -> None:
    specs = validate_metric_catalog()
    assert METRIC_FAMILY_COUNT == 168
    assert len(specs) == 168
    assert tuple(spec.family_id for spec in specs[-32:-28]) == MACRO_FAMILIES
    assert tuple(spec.family_id for spec in specs[-28:-24]) == ORGANIZATION_FAMILIES
    assert len({spec.family_id for spec in all_metric_specifications()}) == 168


def test_macro_specs_declare_their_value_keys() -> None:
    expected = {
        MetricFamilyId.MACRO_SOCIETY_STRUCTURE: {
            "candidate_count",
            "covered_person_count",
            "fragment_person_count",
            "lane_presence_count",
            "largest_candidate_share",
            "mean_candidate_members",
            "overlap_person_count",
        },
        MetricFamilyId.MACRO_SOCIETY_IDENTITY_ALIGNMENT: {
            "candidates_with_self_identification",
            "layer_disagreement_count",
            "self_identified_member_share",
            "territory_alignment_share",
            "territory_supported_candidate_count",
            "unrecognized_self_identified_group_count",
        },
        MetricFamilyId.MACRO_SOCIETY_LINEAGE: {
            "continuation_count",
            "dissolution_count",
            "emergence_count",
            "lineage_window_count",
            "mean_continuation_jaccard",
            "merge_count",
            "split_count",
            "transform_count",
        },
        MetricFamilyId.MACRO_SOCIETY_MEMBERSHIP_DISPUTE: {
            "contested_candidate_count",
            "contested_share",
            "disputed_candidate_count",
            "disputed_member_count",
            "overlap_member_count",
            "unresolved_fragment_count",
        },
    }
    for family, keys in expected.items():
        spec = metric_specification(family)
        assert spec.family_id is family
        assert set(spec.value_keys) == keys
        assert spec.algorithm_version == "1"
        assert spec.family_id.value.startswith("macro_society_")
        assert "unknown" in spec.unknown_case


def test_macro_families_are_serializable_and_closed() -> None:
    for family in MACRO_FAMILIES:
        assert is_supported_metric_family(family.value)
    assert not is_supported_metric_family("macro_society_unknown")
