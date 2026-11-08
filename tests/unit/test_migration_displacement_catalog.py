# mypy: ignore-errors
"""Catalog 176 -> 180: four appended migration families, first 176 unchanged."""

from __future__ import annotations

import hashlib
import json
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

MIGRATION_FAMILIES = (
    "migration_wave_structure",
    "migration_cause_evidence",
    "migration_cluster_cohesion",
    "migration_integration_outcome",
)
FIRST_176_DIGEST = "2c224ad34b8bcc995ef1e9965477b902cd7fef791430702e0b4da287fd263fdf"
FORBIDDEN_KEY_WORDS = ("score", "refugee", "forced", "wellbeing", "assimilation")


def _digest(specs) -> str:
    payload = [
        [
            spec.family_id.value,
            spec.algorithm_version,
            spec.schema_version,
            list(spec.value_keys),
            list(spec.formula_ids),
            sorted(spec.formulas.items()),
            spec.population,
            spec.denominator,
        ]
        for spec in specs
    ]
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def test_catalog_count_is_180() -> None:
    specs = all_metric_specifications()
    assert METRIC_FAMILY_COUNT == 180
    assert len(specs) == 180
    assert len(validate_metric_catalog()) == 180
    assert len({spec.family_id for spec in specs}) == 180


def test_four_migration_families_are_last() -> None:
    specs = all_metric_specifications()
    assert tuple(spec.family_id.value for spec in specs[-4:]) == MIGRATION_FAMILIES
    assert tuple(spec.family_id.value for spec in specs[176:180]) == MIGRATION_FAMILIES
    assert all(spec.family_id.value not in MIGRATION_FAMILIES for spec in specs[:176])
    assert tuple(spec.family_id.value for spec in specs[172:176]) == (
        "border_claim_structure",
        "border_overlap_contest",
        "border_agreement_recognition",
        "border_control_alignment",
    )
    for name in MIGRATION_FAMILIES:
        spec = metric_specification(name)
        assert spec.algorithm_version == "1"
        assert spec.value_keys
        assert MetricFamilyId(name).value == name
        for key in spec.value_keys:
            assert not any(word in key for word in FORBIDDEN_KEY_WORDS)


def test_first_176_ids_order_versions_and_keys_are_unchanged() -> None:
    specs = all_metric_specifications()
    assert _digest(specs[:176]) == FIRST_176_DIGEST
    # Migration-specific value keys are exactly the planned closed sets.
    keys = {spec.family_id.value: spec.value_keys for spec in specs[176:]}
    assert keys["migration_wave_structure"][:3] == (
        "wave_count",
        "participant_count",
        "distinct_origin_count",
    )
    assert "cause_count:resource_scarcity" in keys["migration_cause_evidence"]
    assert "cluster_size:5_to_8" in keys["migration_cluster_cohesion"]
    assert "outcome:settled" in keys["migration_integration_outcome"]


def test_no_current_pin_asserts_176() -> None:
    """No test pins the *current* catalog at 176; historical statements remain."""
    root = Path(__file__).resolve().parents[1]
    current_pin = re.compile(
        r"(METRIC_FAMILY_COUNT\s*==\s*176|len\([^)]*\)\s*==\s*176"
        r"|\"metric_family_count\":\s*176)"
    )
    offenders = []
    for path in sorted(root.rglob("test_*.py")):
        if path.name == Path(__file__).name:
            continue
        text = path.read_text(encoding="utf-8")
        if current_pin.search(text):
            offenders.append(path.name)
    assert offenders == []
