"""Predictive layers keep authority, import and client boundaries."""

from __future__ import annotations

from pathlib import Path

import pytest

import agents.cognition as cognition
from agents.cognition import scientific_model_lifecycle as lifecycle
from agents.cognition import scientific_model_observation as observation
from agents.cognition import scientific_model_prediction as prediction
from agents.cognition import scientific_model_scoring as scoring
from agents.cognition import scientific_models as contracts

pytestmark = pytest.mark.architecture

_SRC = Path(__file__).resolve().parents[2] / "src"


def _text(relative: str) -> str:
    return (_SRC / relative).read_text(encoding="utf-8")


def test_cognition_predictive_modules_import_no_authority() -> None:
    for module in (contracts, lifecycle, observation, prediction, scoring):
        source = Path(module.__file__).read_text(encoding="utf-8")
        for forbidden in (
            "world._",
            "simulation",
            "analysis",
            "persistence",
            "infrastructure",
            "api",
        ):
            assert forbidden not in source, (module.__name__, forbidden)


def test_analysis_predictive_modules_import_no_live_layers() -> None:
    for relative in (
        "analysis/scientific_models_contract.py",
        "analysis/scientific_models_rows.py",
        "analysis/scientific_models_analysis.py",
        "analysis/scientific_models_metrics.py",
    ):
        source = _text(relative)
        for forbidden in (
            "agents.cognition",
            "world.",
            "simulation",
            "experiments",
            "persistence",
            "infrastructure",
        ):
            assert forbidden not in source, (relative, forbidden)


def test_simulation_snapshot_modules_stay_independent() -> None:
    for relative in (
        "simulation/scientific_models_models.py",
        "simulation/scientific_models_codec.py",
        "simulation/scientific_models_ports.py",
        "simulation/scientific_models_paging.py",
    ):
        source = _text(relative)
        for forbidden in (
            "analysis",
            "experiments",
            "infrastructure",
            "persistence",
            "api",
        ):
            assert forbidden not in source, (relative, forbidden)


def test_persistence_and_api_do_not_import_analysis() -> None:
    for relative in (
        "persistence/scientific_models_filesystem.py",
        "api/routes/scientific_models.py",
        "api/scientific_models_cursor.py",
    ):
        source = _text(relative)
        assert "analysis" not in source, relative
    assert "experiments" not in _text("persistence/scientific_models_filesystem.py")


def test_clients_are_never_imported_by_python() -> None:
    for relative in (
        "api/routes/scientific_models.py",
        "api/app.py",
        "experiments/scientific_models_publication.py",
    ):
        source = _text(relative)
        assert "clients/" not in source
        assert "clients." not in source


def test_contracts_expose_only_owner_safe_values() -> None:
    assert "WorldState" not in cognition.__all__
    assert "ScientificModelLedger" in cognition.__all__
    assert "ModelTargetKind" in cognition.__all__
    assert "scientific_model_content_count" in cognition.__all__
