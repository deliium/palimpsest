"""Dual representation: subjective cognition vs analytical traits."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.architecture

_ROOT = Path(__file__).resolve().parents[2]
_COGNITION = _ROOT / "src" / "agents" / "cognition" / "cultural_features.py"
_ANALYSIS_TRAITS = _ROOT / "src" / "analysis" / "cultural_traits.py"
_ANALYSIS_METRICS = _ROOT / "src" / "analysis" / "cultural_feature_metrics.py"


def _forbidden_analysis_imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    hits: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("analysis"):
                    hits.append(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            if node.module.startswith("analysis"):
                hits.append(node.module)
    return hits


def test_cognition_cultural_features_does_not_import_analysis() -> None:
    assert _forbidden_analysis_imports(_COGNITION) == []


def test_analysis_traits_does_not_import_cognition_belief_types() -> None:
    source = _ANALYSIS_TRAITS.read_text(encoding="utf-8")
    assert "agents.cognition.cultural_features" not in source
    assert "SubjectiveCulturalBelief" not in source


def test_analysis_metrics_does_not_import_subjective_ledger() -> None:
    source = _ANALYSIS_METRICS.read_text(encoding="utf-8")
    assert "SubjectiveCulturalBelief" not in source
    assert "CulturalFeatureLedger" not in source


def test_no_global_culture_type_in_world_package() -> None:
    world_dir = _ROOT / "src" / "world"
    for path in world_dir.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "class Culture(" not in text
        assert "class SocietyCulture(" not in text
