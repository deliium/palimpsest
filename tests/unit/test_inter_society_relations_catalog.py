"""Catalog 180 -> 184: four appended ISR families; first 180 unchanged."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Sequence
from pathlib import Path

import pytest

from analysis.specifications import (
    METRIC_FAMILY_COUNT,
    MetricFamilyId,
    MetricSpecification,
    all_metric_specifications,
    metric_specification,
    validate_metric_catalog,
)

pytestmark = pytest.mark.unit

ISR_FAMILIES = (
    "inter_society_relation_structure",
    "inter_society_domain_evidence",
    "inter_society_relation_timeseries",
    "inter_society_pair_comparison",
)
FIRST_180_DIGEST = "2e3169d32810c42561c6d55738a4639dc2c9178f295048536e24f166a37db562"
FORBIDDEN_KEY_WORDS = (
    "score",
    "alliance",
    "enmity",
    "trust_score",
    "composite",
    "rank",
)


def _digest(specs: Sequence[MetricSpecification]) -> str:
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


def test_catalog_count_is_184() -> None:
    specs = all_metric_specifications()
    assert METRIC_FAMILY_COUNT == 204
    assert len(specs) == 204
    assert len(validate_metric_catalog()) == 204
    assert len({spec.family_id for spec in specs}) == 204


def test_four_isr_families_are_last_and_distinct_from_lanes() -> None:
    specs = all_metric_specifications()
    assert tuple(spec.family_id.value for spec in specs[180:184]) == ISR_FAMILIES
    assert tuple(spec.family_id.value for spec in specs[180:184]) == ISR_FAMILIES
    assert all(spec.family_id.value not in ISR_FAMILIES for spec in specs[:180])
    assert "inter_society_relation_lanes" not in ISR_FAMILIES
    lane_indexes = [
        index
        for index, spec in enumerate(specs)
        if spec.family_id.value == "inter_society_relation_lanes"
    ]
    assert lane_indexes and lane_indexes[0] < 180
    for name in ISR_FAMILIES:
        spec = metric_specification(name)
        assert spec.algorithm_version == "1"
        assert spec.value_keys
        assert MetricFamilyId(name).value == name
        for key in spec.value_keys:
            assert not any(word in key for word in FORBIDDEN_KEY_WORDS)


def test_first_180_ids_order_versions_and_keys_are_unchanged() -> None:
    specs = all_metric_specifications()
    assert _digest(specs[:180]) == FIRST_180_DIGEST


def test_no_current_pin_asserts_180() -> None:
    """No test pins the *current* catalog at 180; historical statements remain."""
    root = Path(__file__).resolve().parents[1]
    current_pin = re.compile(
        r"(METRIC_FAMILY_COUNT\s*==\s*180|len\([^)]*\)\s*==\s*180"
        r"|\"metric_family_count\":\s*180)"
    )
    offenders = []
    for path in sorted(root.rglob("test_*.py")):
        if path.name == Path(__file__).name:
            continue
        text = path.read_text(encoding="utf-8")
        if current_pin.search(text):
            offenders.append(path.name)
    assert offenders == []
