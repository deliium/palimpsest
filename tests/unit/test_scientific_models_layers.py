"""Detached predictive layers stay separate from cognition and world truth."""

from __future__ import annotations

from pathlib import Path

import pytest

from analysis.scientific_models_contract import (
    ModelHypothesisFact,
    ObservedModelOutcomeFact,
    PriorPredictionFact,
)
from analysis.scientific_models_rows import ScientificModelsAnalysis
from experiments.scientific_models_completed_run import scientific_model_facts
from tests.unit.test_scientific_models_lifecycle import _season_ledger

pytestmark = pytest.mark.unit


def test_analysis_modules_import_no_cognition_or_world_authority() -> None:
    root = Path(__file__).resolve().parents[2] / "src" / "analysis"
    for name in (
        "scientific_models_contract.py",
        "scientific_models_rows.py",
    ):
        source = (root / name).read_text(encoding="utf-8")
        for forbidden in (
            "agents.cognition",
            "simulation",
            "world._",
            "experiments",
        ):
            assert forbidden not in source


def test_prediction_and_outcome_rows_are_distinct() -> None:
    from types import SimpleNamespace

    analysis = scientific_model_facts(
        SimpleNamespace(scientific_model_ledgers=(_season_ledger(),)),
        run_token="run-layers",
        expected_owner_count=1,
    )
    assert analysis.predictions
    assert analysis.outcomes
    for row in analysis.predictions:
        assert type(row) is PriorPredictionFact
        assert not hasattr(row, "observed_class")
    for row in analysis.outcomes:
        assert type(row) is ObservedModelOutcomeFact
        assert not hasattr(row, "probabilities_milli")


def test_analysis_carries_no_truth_or_quality_score_fields() -> None:
    assert not any(
        "score" in field or "truth" in field or "accuracy" in field
        for field in ScientificModelsAnalysis.__dataclass_fields__
    )
    for cls in (
        ModelHypothesisFact,
        PriorPredictionFact,
        ObservedModelOutcomeFact,
    ):
        assert not any(
            "score" in field or "truth" in field or "accuracy" in field
            for field in cls.__dataclass_fields__
        )
