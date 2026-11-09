"""V4-06 metric catalog append, updated by later appends to 160 families."""

from __future__ import annotations

import pytest

from analysis.specifications import (
    METRIC_FAMILY_COUNT,
    MetricFamilyId,
    all_metric_specifications,
    metric_specification,
    validate_metric_catalog,
)

pytestmark = pytest.mark.unit

NEW_FAMILIES = (
    MetricFamilyId.FORMAL_RULE_DEVELOPMENT,
    MetricFamilyId.FORMAL_RULE_AUTHORITY,
    MetricFamilyId.FORMAL_RULE_RESPONSE,
)

EXPECTED_KEYS = {
    MetricFamilyId.FORMAL_RULE_DEVELOPMENT: {
        "candidate_count",
        "active_count",
        "documented_count",
        "recognized_enforcement_count",
        "stage_histogram",
        "constraint_histogram",
        "written_representation_count",
        "mean_version_count",
        "coverage",
    },
    MetricFamilyId.FORMAL_RULE_AUTHORITY: {
        "system_count",
        "proponent_count",
        "recognized_authority_count",
        "authority_histogram",
        "competing_system_count",
        "contested_system_count",
        "coverage",
    },
    MetricFamilyId.FORMAL_RULE_RESPONSE: {
        "follow_count",
        "violate_count",
        "challenge_count",
        "reinterpret_count",
        "ignore_count",
        "response_histogram",
        "expected_sanction_histogram",
        "exception_count",
        "coverage",
    },
}


def test_catalog_validates_at_160() -> None:
    specs = validate_metric_catalog()
    assert METRIC_FAMILY_COUNT == 188
    assert len(specs) == 188
    assert len({spec.family_id for spec in specs}) == 188


def test_first_151_families_are_unchanged() -> None:
    specs = all_metric_specifications()
    assert len(specs[:151]) == 151
    assert specs[150].family_id is MetricFamilyId.FORMAL_RULE_RESPONSE
    assert specs[147].family_id is MetricFamilyId.ORGANIZATION_COLLECTIVE_IMPLEMENTATION
    assert not any(spec.family_id.value.startswith("dispute_") for spec in specs[:151])


def test_three_formal_rule_families_precede_later_appends() -> None:
    specs = all_metric_specifications()
    assert tuple(spec.family_id for spec in specs[148:151]) == NEW_FAMILIES


def test_each_family_has_exact_value_keys() -> None:
    for family, expected in EXPECTED_KEYS.items():
        spec = metric_specification(family)
        assert set(spec.value_keys) == expected
        assert spec.version_identifier.endswith("@1")
        assert tuple(spec.value_keys) == tuple(sorted(expected))


def test_version_identifiers_are_id_at_1() -> None:
    assert (
        metric_specification(MetricFamilyId.FORMAL_RULE_DEVELOPMENT).version_identifier
        == "formal_rule_development@1"
    )
    assert (
        metric_specification(MetricFamilyId.FORMAL_RULE_AUTHORITY).version_identifier
        == "formal_rule_authority@1"
    )
    assert (
        metric_specification(MetricFamilyId.FORMAL_RULE_RESPONSE).version_identifier
        == "formal_rule_response@1"
    )
