"""V4-09 catalog append and stale metric-count pin guard."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from analysis.specifications import (
    METRIC_FAMILY_COUNT,
    MetricFamilyId,
    all_metric_specifications,
    metric_specification,
    validate_metric_catalog,
)

pytestmark = pytest.mark.unit

STRUCTURE_KEYS = (
    "mandate_count",
    "candidate_count",
    "principal_kind_histogram",
    "scope_kind_histogram",
    "duration_kind_histogram",
    "provenance_histogram",
    "status_histogram",
    "coverage",
)
RECOGNITION_KEYS = (
    "recognized_count",
    "contested_count",
    "rejected_count",
    "support_root_total",
    "opposition_root_total",
    "positioned_mandate_count",
    "recognition_ratio",
    "contestation_ratio",
    "rejection_ratio",
    "coverage",
)
ALIGNMENT_KEYS = (
    "consistent_count",
    "unresolved_count",
    "inconsistent_count",
    "not_applicable_count",
    "aligned_mandate_count",
    "consistency_ratio",
    "inconsistency_ratio",
    "coverage",
)


def test_catalog_is_164_with_diplomacy_last() -> None:
    specs = all_metric_specifications()
    assert METRIC_FAMILY_COUNT == 164
    assert len(specs) == 164
    assert len(validate_metric_catalog()) == 164
    assert [spec.family_id for spec in specs[-7:-4]] == [
        MetricFamilyId.REPRESENTATION_MANDATE_STRUCTURE,
        MetricFamilyId.REPRESENTATION_RECOGNITION_SUPPORT,
        MetricFamilyId.REPRESENTATION_SCOPE_ALIGNMENT,
    ]
    assert [spec.family_id for spec in specs[-4:]] == [
        MetricFamilyId.DIPLOMATIC_CONTACT_STRUCTURE,
        MetricFamilyId.DIPLOMATIC_INSTRUMENT_OUTCOMES,
        MetricFamilyId.DIPLOMATIC_ENVOY_ALIGNMENT,
        MetricFamilyId.INTER_SOCIETY_RELATION_LANES,
    ]


def test_representation_value_keys_are_exact() -> None:
    assert (
        tuple(
            metric_specification(
                MetricFamilyId.REPRESENTATION_MANDATE_STRUCTURE
            ).value_keys
        )
        == STRUCTURE_KEYS
    )
    assert (
        tuple(
            metric_specification(
                MetricFamilyId.REPRESENTATION_RECOGNITION_SUPPORT
            ).value_keys
        )
        == RECOGNITION_KEYS
    )
    assert (
        tuple(
            metric_specification(
                MetricFamilyId.REPRESENTATION_SCOPE_ALIGNMENT
            ).value_keys
        )
        == ALIGNMENT_KEYS
    )


def test_no_current_metric_count_assertion_still_uses_160() -> None:
    root = Path(__file__).resolve().parents[1]
    pattern = re.compile(
        r"(?:METRIC_FAMILY_COUNT\s*==\s*160|"
        r"len\((?:specs|families|all_metric_specifications\(\))\)\s*==\s*160)"
    )
    offenders: list[str] = []
    for path in sorted((root / "unit").rglob("*.py")) + sorted(
        (root / "architecture").rglob("*.py")
    ):
        text = path.read_text(encoding="utf-8")
        for line_number, line in enumerate(text.splitlines(), start=1):
            if pattern.search(line):
                offenders.append(f"{path.relative_to(root)}:{line_number}")
    assert offenders == []
