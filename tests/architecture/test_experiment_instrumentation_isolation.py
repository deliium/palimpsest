"""Architecture gate: experiment instrumentation stays outside domain packages."""

from __future__ import annotations

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src"

_FORBIDDEN_IMPORTS = ("import experiments", "from experiments")
_FORBIDDEN_SYMBOLS = (
    "StoryTruthSpec",
    "StoryInterventionArbiter",
    "ExperimentCoordinator",
    "CollectorMetricDocument",
    "collect_arm_summary",
    "ClaimTruthSpec",
    "EvidenceCompositionService",
)
_DOMAIN_ROOTS = (
    "world",
    "agents",
    "memory",
    "social",
    "simulation",
)


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules


def test_domain_and_simulation_never_import_experiments() -> None:
    for package in _DOMAIN_ROOTS:
        root = SRC / package
        for path in root.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            for marker in _FORBIDDEN_IMPORTS:
                assert marker not in text, f"{path}: {marker}"
            for symbol in _FORBIDDEN_SYMBOLS:
                assert symbol not in text, f"{path}: {symbol}"


def test_cognition_memory_social_never_reference_collectors() -> None:
    for package in ("agents/cognition", "memory", "social"):
        root = SRC / package
        for path in root.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            assert "StoryTruthSpec" not in text
            assert "ClaimTruthSpec" not in text
            assert "CollectorMetricDocument" not in text
            assert "collect_arm_summary" not in text
            assert "ExperimentCoordinator" not in text
            assert "EvidenceCompositionService" not in text


def test_composition_boundary_imports() -> None:
    composition = SRC / "experiments" / "composition.py"
    modules = _imported_modules(composition)
    assert any(m == "analysis" or m.startswith("analysis.") for m in modules)
    assert not any(m == "persistence" or m.startswith("persistence.") for m in modules)
    assert not any(m == "sqlalchemy" or m.startswith("sqlalchemy.") for m in modules)


def test_api_never_imports_analysis_or_composition() -> None:
    for path in (SRC / "api").rglob("*.py"):
        modules = _imported_modules(path)
        text = path.read_text(encoding="utf-8")
        assert not any(m == "analysis" or m.startswith("analysis.") for m in modules)
        assert "EvidenceCompositionService" not in text
        assert "ClaimTruthSpec" not in text
        assert "StoryTruthSpec" not in text


def test_persistence_analysis_loader_stays_analysis_free() -> None:
    path = SRC / "persistence" / "analysis_sqlalchemy.py"
    modules = _imported_modules(path)
    assert not any(m == "analysis" or m.startswith("analysis.") for m in modules)
    assert any(
        m == "experiments.persistence" or m.startswith("experiments.persistence")
        for m in modules
    )
