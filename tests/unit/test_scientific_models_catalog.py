# mypy: ignore-errors

"""Catalog pins: exactly six appended families with locked keysets."""

from __future__ import annotations

import pytest

from analysis.specifications import all_metric_specifications

pytestmark = pytest.mark.unit

_TAIL = [
    "scientific_model_structure",
    "scientific_model_predictions",
    "scientific_model_observed_outcomes",
    "scientific_model_calibration",
    "scientific_model_revisions",
    "scientific_model_comparison",
]


def test_catalog_appends_exactly_six_families() -> None:
    specs = all_metric_specifications()
    assert len(specs) == 275
    ids = [spec.family_id.value for spec in specs]
    assert ids[255] == "scientific_replication_social_interpretation"
    assert ids[256:262] == _TAIL


def test_new_keysets_are_locked() -> None:
    specs = {spec.family_id.value: spec for spec in all_metric_specifications()}
    assert specs["scientific_model_structure"].value_keys == (
        "model_count",
        "hypothesis_count",
        "target_kind_count",
    )
    assert specs["scientific_model_predictions"].value_keys == (
        "prediction_count",
        "case_count",
        "pending_case_count",
    )
    assert specs["scientific_model_observed_outcomes"].value_keys == (
        "observed_case_count",
        "unavailable_case_count",
        "not_attempted_case_count",
        "not_comparable_case_count",
        "evicted_case_count",
    )
    assert specs["scientific_model_calibration"].value_keys == (
        "scored_prediction_count",
        "calibration_group_count",
        "insufficient_group_count",
    )
    assert specs["scientific_model_revisions"].value_keys == (
        "revision_count",
        "source_revision_count",
        "parameter_revision_count",
    )
    assert specs["scientific_model_comparison"].value_keys == (
        "comparison_count",
        "paired_case_count",
        "lower_loss_a_count",
        "lower_loss_b_count",
        "tie_count",
        "insufficient_comparison_count",
    )


def test_hypothesis_forbidden_keys_remain_forbidden() -> None:
    from analysis import scientific_hypotheses_contract as contract

    forbidden = next(
        value
        for name, value in vars(contract).items()
        if "FORBIDDEN" in name and isinstance(value, frozenset)
    )
    for key in ("truth", "calibration", "score", "accuracy"):
        assert key in forbidden
