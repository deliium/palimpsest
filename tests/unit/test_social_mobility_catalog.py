# mypy: ignore-errors
"""Social-mobility metric catalog append discipline (228 -> 244)."""

from __future__ import annotations

import hashlib

from analysis.specifications import (
    METRIC_FAMILY_COUNT,
    MetricFamilyId,
    all_metric_specifications,
    validate_metric_catalog,
)

_FIRST_228_DIGEST = "c8ac976ec9ae568d337835d4b0879850c4864040e4d338e663a3c13a83dc3dff"

_APPENDED_IDS = (
    "resource_mobility",
    "skill_mobility",
    "social_influence_mobility",
    "organization_role_mobility",
    "educational_access_mobility",
    "productive_asset_mobility",
    "social_mobility_generation_lag",
    "social_mobility_coverage",
)


def test_catalog_count_is_244() -> None:
    assert METRIC_FAMILY_COUNT == 271
    specs = all_metric_specifications()
    assert len(specs) == 271
    validate_metric_catalog()


def test_first_228_are_unchanged() -> None:
    specs = all_metric_specifications()
    material = "\n".join(
        f"{spec.family_id.value}@{spec.algorithm_version}|{','.join(spec.value_keys)}"
        for spec in specs[:228]
    )
    assert hashlib.sha256(material.encode()).hexdigest() == _FIRST_228_DIGEST


def test_eight_families_append_at_228_through_235() -> None:
    specs = all_metric_specifications()
    assert tuple(spec.family_id.value for spec in specs[228:236]) == _APPENDED_IDS
    assert {
        MetricFamilyId.RESOURCE_MOBILITY,
        MetricFamilyId.SKILL_MOBILITY,
        MetricFamilyId.SOCIAL_INFLUENCE_MOBILITY,
        MetricFamilyId.ORGANIZATION_ROLE_MOBILITY,
        MetricFamilyId.EDUCATIONAL_ACCESS_MOBILITY,
        MetricFamilyId.PRODUCTIVE_ASSET_MOBILITY,
        MetricFamilyId.SOCIAL_MOBILITY_GENERATION_LAG,
        MetricFamilyId.SOCIAL_MOBILITY_COVERAGE,
    } <= set(MetricFamilyId)


def test_appended_specs_use_the_locked_cases() -> None:
    for spec in all_metric_specifications()[228:236]:
        assert spec.cohort_window == "social_mobility_window_tick"
        assert spec.empty_case == "unavailable_unknown"
        assert spec.one_case == "insufficient_samples"
        assert spec.unknown_case == "unavailable_unknown"
        assert spec.availability_behavior == (
            "explicit_unknown_without_genealogy_or_outcome_evidence"
        )
        assert spec.formulas
        assert spec.value_keys


def test_influence_role_and_education_declare_owner_stages() -> None:
    for family in (
        MetricFamilyId.SOCIAL_INFLUENCE_MOBILITY,
        MetricFamilyId.ORGANIZATION_ROLE_MOBILITY,
        MetricFamilyId.EDUCATIONAL_ACCESS_MOBILITY,
    ):
        spec = next(
            item for item in all_metric_specifications() if item.family_id is family
        )
        assert {stage.value for stage in spec.evidence_inputs} == {
            "objective_event_state",
            "agent_visible_projection",
            "belief_revision_testimony",
        }


def test_no_family_pools_multiple_domains() -> None:
    from analysis.specifications import (
        SOCIAL_MOBILITY_COVERAGE_KEYS,
        SOCIAL_MOBILITY_DOMAIN_KEYS,
        SOCIAL_MOBILITY_GENERATION_KEYS,
    )

    domain_families = set(_APPENDED_IDS[:6])
    for spec in all_metric_specifications()[228:236]:
        assert spec.value_keys[0] == "social_mobility_window_tick"
        if spec.family_id.value in domain_families:
            assert spec.value_keys == SOCIAL_MOBILITY_DOMAIN_KEYS
        elif spec.family_id is MetricFamilyId.SOCIAL_MOBILITY_GENERATION_LAG:
            assert spec.value_keys == SOCIAL_MOBILITY_GENERATION_KEYS
        else:
            assert spec.value_keys == SOCIAL_MOBILITY_COVERAGE_KEYS
