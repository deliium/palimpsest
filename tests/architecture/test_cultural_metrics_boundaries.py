"""Architecture boundaries for cultural evidence and metric analysis."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.architecture

_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "src"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            names.add(node.module)
    return names


def test_simulation_export_does_not_import_outer_layers() -> None:
    path = _SRC / "simulation" / "cultural_evidence.py"
    for name in _imports(path):
        assert not name.startswith(("analysis", "experiments", "api", "persistence"))


def test_new_analysis_modules_do_not_import_world_mutation_authority() -> None:
    modules = (
        "cultural_metric_comparison.py",
        "cultural_evolution_metrics.py",
        "cultural_trait_dynamics.py",
        "cultural_evolution_transmission.py",
        "cultural_population_structure.py",
        "cultural_narrative_survival.py",
        "cultural_vocabulary_differentiation.py",
        "cultural_technology_continuity.py",
    )
    forbidden = (
        "world._",
        "simulation.engine",
        "simulation.bootstrap",
        "experiments",
        "persistence",
        "api",
    )
    for module in modules:
        for name in _imports(_SRC / "analysis" / module):
            assert not name.startswith(forbidden), (module, name)


def test_no_composite_culture_score_shortcut() -> None:
    for path in (_SRC / "analysis").glob("cultural_*.py"):
        text = path.read_text(encoding="utf-8").lower()
        assert "culture_score" not in text
        assert "culture-index" not in text


def test_capture_evidence_is_not_exposed_to_cognition_or_presentation() -> None:
    forbidden_roots = (
        _SRC / "agents",
        _SRC / "observer",
        _SRC / "api",
    )
    for root in forbidden_roots:
        for path in root.rglob("*.py"):
            for name in _imports(path):
                assert not name.startswith(
                    (
                        "simulation.cultural_evidence",
                        "analysis.cultural_evolution_evidence",
                    )
                ), path
