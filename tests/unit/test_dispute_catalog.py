"""V4-07 metric catalog append: 154 families with an unchanged first 151."""

from __future__ import annotations

import hashlib

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
    MetricFamilyId.DISPUTE_CLAIM_STRUCTURE,
    MetricFamilyId.DISPUTE_TESTIMONY_INDEPENDENCE,
    MetricFamilyId.DISPUTE_RESOLUTION_ALIGNMENT,
)

# Digest of the first 151 families as (family@version:value_keys), recorded when
# V4-07 appended its three families. Any id, order, version, or key drift fails.
FIRST_151_DIGEST = "c34a7267643ad175955db4c4fb0e5e3ebbd048c75212ee7235ac33dc694a9eac"


def test_metric_catalog_count_is_154() -> None:
    specs = validate_metric_catalog()
    assert METRIC_FAMILY_COUNT == 154
    assert len(specs) == 154
    assert len({spec.family_id for spec in specs}) == 154
    assert len(all_metric_specifications()) == 154


def test_first_151_families_are_unchanged() -> None:
    specs = all_metric_specifications()
    assert len(specs[:151]) == 151
    assert specs[150].family_id is MetricFamilyId.FORMAL_RULE_RESPONSE
    assert not any(spec.family_id in NEW_FAMILIES for spec in specs[:151])
    material = "\x1f".join(
        f"{spec.family_id.value}@{spec.algorithm_version}:{','.join(spec.value_keys)}"
        for spec in specs[:151]
    )
    assert hashlib.sha256(material.encode("utf-8")).hexdigest() == FIRST_151_DIGEST


def test_three_dispute_families_are_last_and_versioned_at_1() -> None:
    specs = all_metric_specifications()
    assert tuple(spec.family_id for spec in specs[-3:]) == NEW_FAMILIES
    assert tuple(spec.family_id for spec in specs[-6:-3]) == (
        MetricFamilyId.FORMAL_RULE_DEVELOPMENT,
        MetricFamilyId.FORMAL_RULE_AUTHORITY,
        MetricFamilyId.FORMAL_RULE_RESPONSE,
    )
    assert [spec.version_identifier for spec in specs[-3:]] == [
        "dispute_claim_structure@1",
        "dispute_testimony_independence@1",
        "dispute_resolution_alignment@1",
    ]


def test_dispute_value_keys_are_exact() -> None:
    assert metric_specification(MetricFamilyId.DISPUTE_CLAIM_STRUCTURE).value_keys == (
        "candidate_count",
        "case_count",
        "claim_count",
        "claim_kind_histogram",
        "counterclaim_count",
        "counterclaim_ratio",
        "evidence_backed_claim_ratio",
        "multi_party_case_ratio",
        "polarity_histogram",
        "rule_referenced_case_ratio",
        "unresolved_case_ratio",
    )
    assert metric_specification(
        MetricFamilyId.DISPUTE_TESTIMONY_INDEPENDENCE
    ).value_keys == (
        "claim_without_testimony_ratio",
        "communicated_testimony_ratio",
        "contradictory_testimony_ratio",
        "direct_testimony_ratio",
        "distinct_root_count",
        "independently_evidenced_ratio",
        "shared_root_duplicate_ratio",
        "testimony_count",
    )
    assert metric_specification(
        MetricFamilyId.DISPUTE_RESOLUTION_ALIGNMENT
    ).value_keys == (
        "accepted_party_ratio",
        "agreement_alignment_ratio",
        "apparently_accepted_resolution_count",
        "contested_resolution_count",
        "mediation_linked_resolution_ratio",
        "objective_inconsistent_claim_ratio",
        "objective_supported_claim_ratio",
        "objective_unresolved_claim_ratio",
        "proposed_resolution_count",
        "rejected_party_ratio",
        "resolution_count",
    )
