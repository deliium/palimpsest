# mypy: ignore-errors

"""Detached arithmetic, absence semantics and layer separation."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from agents.cognition.scientific_model_lifecycle import advance_scientific_models
from analysis.models import MetricAvailability
from analysis.scientific_models_analysis import harvest_scientific_models_analysis
from analysis.scientific_models_metrics import (
    compute_scientific_model_calibration,
    compute_scientific_model_comparison,
    compute_scientific_model_structure,
)
from experiments.scientific_models_completed_run import scientific_model_facts
from tests.unit.test_scientific_models_lifecycle import (
    _experiment_ledger,
    _observation,
    _season_ledger,
)
from world.environment import Season

pytestmark = pytest.mark.unit


def _scored_result():
    ledger = _season_ledger()
    ledger = advance_scientific_models(
        ledger,
        _observation(12, season=Season.SUMMER),
        experiment_ledger=_experiment_ledger(),
    )
    return SimpleNamespace(scientific_model_ledgers=(ledger,))


def test_harvest_recomputes_calibration_and_pair_comparison() -> None:
    facts = scientific_model_facts(
        _scored_result(), run_token="run-analysis", expected_owner_count=1
    )
    assert facts.outcomes
    harvested = harvest_scientific_models_analysis(facts)
    assert harvested.calibration
    assert harvested.comparisons
    scored = [row for row in harvested.outcomes if row.state == "scored"]
    assert scored
    for row in harvested.calibration:
        assert 0 <= row.mean_brier_millionths <= 2_000_000
        assert (
            row.calibration_gap_milli is None or 0 <= row.calibration_gap_milli <= 1000
        )
    for row in harvested.comparisons:
        assert row.status in {
            "lower_loss_a",
            "lower_loss_b",
            "tied",
            "insufficient_samples",
        }
        assert row.a_minus_b_millionths == (
            row.mean_brier_millionths_a - row.mean_brier_millionths_b
        )


def test_metrics_emit_counts_and_absent_is_unknown() -> None:
    facts = scientific_model_facts(
        _scored_result(), run_token="run-analysis", expected_owner_count=1
    )
    harvested = harvest_scientific_models_analysis(facts)
    structure = compute_scientific_model_structure(
        harvested, run_id="run", input_revision="rev"
    )
    calibration = compute_scientific_model_calibration(
        harvested, run_id="run", input_revision="rev"
    )
    comparison = compute_scientific_model_comparison(
        harvested, run_id="run", input_revision="rev"
    )
    assert structure.availability is MetricAvailability.PRESENT
    assert structure.values["model_count"] >= 2
    assert calibration.values["scored_prediction_count"] >= 1
    assert comparison.values["comparison_count"] >= 1

    absent = scientific_model_facts(
        SimpleNamespace(scientific_model_ledgers=()),
        run_token="run",
        expected_owner_count=0,
    )
    absent_doc = compute_scientific_model_structure(
        harvest_scientific_models_analysis(absent),
        run_id="run",
        input_revision="rev",
    )
    assert absent_doc.availability is MetricAvailability.UNKNOWN
    assert absent_doc.values == {}


def test_analysis_does_not_import_cognition_or_world() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[2] / "src" / "analysis"
    for name in ("scientific_models_analysis.py", "scientific_models_metrics.py"):
        text = (root / name).read_text(encoding="utf-8")
        for forbidden in ("agents.cognition", "world.", "simulation"):
            assert forbidden not in text
