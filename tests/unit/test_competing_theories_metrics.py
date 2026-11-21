# mypy: ignore-errors

"""Competing-theory metric catalog append and optional-input behavior."""

from __future__ import annotations

import pytest

from analysis.competing_theories_analysis import harvest_competing_theories_analysis
from analysis.metric_service import MetricComputationInputs, assemble_metric_documents
from analysis.specifications import METRIC_FAMILY_COUNT, all_metric_specifications
from tests.unit.test_competing_theories_analysis import _facts

pytestmark = pytest.mark.unit

_FAMILIES = (
    "competing_theory_structure",
    "competing_theory_support_network",
    "competing_theory_citations",
    "competing_theory_predictions",
    "competing_theory_failures",
    "competing_theory_transmission",
)

_KEYS = {
    "competing_theory_structure": {"claim_count", "rival_pair_count"},
    "competing_theory_support_network": {"support_edge_count", "community_count"},
    "competing_theory_citations": {"citation_count", "verified_root_count"},
    "competing_theory_predictions": {"prediction_count", "scored_count"},
    "competing_theory_failures": {"failure_count", "unscored_count"},
    "competing_theory_transmission": {"delivered_count", "teaching_count"},
}


def test_six_families_append_without_moving_the_prior_tail() -> None:
    specs = all_metric_specifications()
    assert len(specs) == METRIC_FAMILY_COUNT == 275
    assert tuple(spec.family_id.value for spec in specs[-9:-3]) == _FAMILIES
    assert not {
        spec.family_id.value for spec in specs[:262]
    } & set(_FAMILIES)
    assert specs[256].family_id.value == "scientific_model_structure"
    assert specs[261].family_id.value == "scientific_model_comparison"


def test_absent_input_emits_no_competing_family() -> None:
    bundle = assemble_metric_documents(
        MetricComputationInputs(run_id="run-1", input_revision="rev-1", window_end=0)
    )
    assert not {
        document.metric_family for document in bundle.documents
    } & set(_FAMILIES)


def test_present_input_emits_six_families_with_exact_keys() -> None:
    analysis = harvest_competing_theories_analysis(_facts())
    bundle = assemble_metric_documents(
        MetricComputationInputs(
            run_id="run-1",
            input_revision="rev-1",
            window_end=0,
            competing_theories_analysis=analysis,
        )
    )
    by_family = {document.metric_family: document for document in bundle.documents}
    for family in _FAMILIES:
        assert by_family[family].values.keys() == _KEYS[family]
