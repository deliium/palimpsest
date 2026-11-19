# mypy: ignore-errors
"""Economic-inequality metric catalog append discipline (historical 220 -> 228)."""

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
    "resource_possession_inequality",
    "productive_tool_access_inequality",
    "infrastructure_access_inequality",
    "storage_access_inequality",
    "credit_relationship_inequality",
    "organizational_resource_control_inequality",
    "economic_inequality_cohorts",
    "economic_inequality_society_comparison",
)


def test_catalog_count_is_244() -> None:
    assert METRIC_FAMILY_COUNT == 262
    specs = all_metric_specifications()
    assert len(specs) == 262
    validate_metric_catalog()


def test_first_228_are_unchanged() -> None:
    specs = all_metric_specifications()
    material = "\n".join(
        f"{spec.family_id.value}@{spec.algorithm_version}|{','.join(spec.value_keys)}"
        for spec in specs[:228]
    )
    assert hashlib.sha256(material.encode()).hexdigest() == _FIRST_228_DIGEST


def test_eight_economic_families_append_at_220_through_227() -> None:
    specs = all_metric_specifications()
    assert tuple(spec.family_id.value for spec in specs[220:228]) == _APPENDED_IDS
    assert {
        MetricFamilyId.RESOURCE_POSSESSION_INEQUALITY,
        MetricFamilyId.PRODUCTIVE_TOOL_ACCESS_INEQUALITY,
        MetricFamilyId.INFRASTRUCTURE_ACCESS_INEQUALITY,
        MetricFamilyId.STORAGE_ACCESS_INEQUALITY,
        MetricFamilyId.CREDIT_RELATIONSHIP_INEQUALITY,
        MetricFamilyId.ORGANIZATIONAL_RESOURCE_CONTROL_INEQUALITY,
        MetricFamilyId.ECONOMIC_INEQUALITY_COHORTS,
        MetricFamilyId.ECONOMIC_INEQUALITY_SOCIETY_COMPARISON,
    } <= set(MetricFamilyId)


def test_appended_specs_use_the_locked_cases() -> None:
    specs = all_metric_specifications()[220:228]
    for spec in specs:
        assert spec.cohort_window == "economic_inequality_window_tick"
        assert spec.deceased_policy == "exclude_owners_strictly_after_death"
        assert spec.zero_holding_policy == ("observed_zero_included_unobserved_unknown")
        assert spec.self_edge_policy == "not_applicable"
        assert spec.censoring_policy == "insufficient_samples_remain_explicit"
        assert spec.empty_case == "unavailable_unknown"
        assert spec.one_case == "insufficient_samples"
        assert spec.all_zero_case == "emit_zero"
        assert spec.unknown_case == "unavailable_unknown"
        assert spec.availability_behavior == (
            "explicit_unknown_without_economic_evidence"
        )
        assert spec.formulas
        assert spec.value_keys


def test_organizational_control_declares_claim_stages() -> None:
    spec = next(
        spec
        for spec in all_metric_specifications()
        if spec.family_id is MetricFamilyId.ORGANIZATIONAL_RESOURCE_CONTROL_INEQUALITY
    )
    assert {stage.value for stage in spec.evidence_inputs} == {
        "objective_event_state",
        "agent_visible_projection",
        "belief_revision_testimony",
    }
