"""V4-08 catalog append: 154 -> 160 with the first 154 unchanged."""

from __future__ import annotations

import hashlib
import json

import pytest

from analysis.specifications import (
    METRIC_FAMILY_COUNT,
    MetricFamilyId,
    all_metric_specifications,
    validate_metric_catalog,
)

pytestmark = pytest.mark.unit

FIRST_154_DIGEST = "71c0925dc37943888827b8f82ef4b448227d760e56f9bd6389f16da2441ceec7"
FIRST_157_DIGEST = "22d2f317370e09f25667d3191e7fc72c577f9cf9bb1cfe2fa8b60d931db6c438"

SOURCE_KEYS = (
    "candidate_count",
    "source_count",
    "source_kind_histogram",
    "testimony_count",
    "item_count",
    "interpretation_histogram",
    "confidence_band_histogram",
    "multi_owner_candidate_ratio",
    "uncorroborated_item_ratio",
)
PROVENANCE_KEYS = (
    "provenance_channel_histogram",
    "independent_root_ratio",
    "communicated_testimony_ratio",
    "custody_link_count",
    "custody_complete_ratio",
    "custody_incomplete_count",
    "custody_conflicting_count",
    "missing_provenance_ratio",
)
ALIGNMENT_KEYS = (
    "aligned_item_count",
    "consistent_count",
    "unresolved_count",
    "inconsistent_count",
    "not_applicable_count",
    "consistency_ratio",
    "custody_match_count",
    "custody_mismatch_count",
    "custody_unknown_count",
)


def test_catalog_is_160_unique_and_validated() -> None:
    specs = all_metric_specifications()
    assert METRIC_FAMILY_COUNT == 176
    assert len(specs) == 176
    assert len({spec.family_id for spec in specs}) == 176
    assert len(validate_metric_catalog()) == 176


def test_evidence_families_are_retained_before_representation() -> None:
    specs = all_metric_specifications()
    assert [spec.family_id for spec in specs[-22:-19]] == [
        MetricFamilyId.EVIDENCE_SOURCE_STRUCTURE,
        MetricFamilyId.EVIDENCE_PROVENANCE_CONTINUITY,
        MetricFamilyId.EVIDENCE_OBJECTIVE_ALIGNMENT,
    ]
    assert [spec.family_id for spec in specs[-19:-16]] == [
        MetricFamilyId.REPRESENTATION_MANDATE_STRUCTURE,
        MetricFamilyId.REPRESENTATION_RECOGNITION_SUPPORT,
        MetricFamilyId.REPRESENTATION_SCOPE_ALIGNMENT,
    ]
    for spec in specs[-19:-12]:
        assert spec.algorithm_version == "1"
        assert set(spec.formula_ids) == set(spec.value_keys)


def test_first_157_catalog_is_unchanged() -> None:
    specs = all_metric_specifications()[:157]
    material = [
        (spec.family_id.value, spec.algorithm_version, tuple(spec.value_keys))
        for spec in specs
    ]
    payload = json.dumps(material, separators=(",", ":"))
    assert hashlib.sha256(payload.encode("utf-8")).hexdigest() == FIRST_157_DIGEST


def test_first_154_catalog_is_unchanged() -> None:
    specs = all_metric_specifications()[:154]
    material = [
        (spec.family_id.value, spec.algorithm_version, tuple(spec.value_keys))
        for spec in specs
    ]
    payload = json.dumps(material, separators=(",", ":"))
    assert hashlib.sha256(payload.encode("utf-8")).hexdigest() == FIRST_154_DIGEST


def test_value_keys_are_exact() -> None:
    specs = {spec.family_id: spec for spec in all_metric_specifications()}
    assert tuple(specs[MetricFamilyId.EVIDENCE_SOURCE_STRUCTURE].value_keys) == (
        SOURCE_KEYS
    )
    assert tuple(specs[MetricFamilyId.EVIDENCE_PROVENANCE_CONTINUITY].value_keys) == (
        PROVENANCE_KEYS
    )
    assert tuple(specs[MetricFamilyId.EVIDENCE_OBJECTIVE_ALIGNMENT].value_keys) == (
        ALIGNMENT_KEYS
    )
