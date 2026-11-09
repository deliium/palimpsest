"""Early ISR isolation smoke: analysis-only modules never feed live authority."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.architecture

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"

ISR_ANALYSIS = tuple(sorted((SRC / "analysis").glob("inter_society_relations_*.py")))
ISR_SIMULATION = tuple(
    sorted((SRC / "simulation").glob("inter_society_relations_*.py"))
)

FORBIDDEN_ANALYSIS_ROOTS = frozenset(
    {
        "simulation",
        "persistence",
        "api",
        "experiments",
        "observer",
        "infrastructure",
        "agents",
    }
)
FORBIDDEN_WORLD_AUTHORITY = (
    "WorldEngine",
    "WorldState",
    "ActionSubmission",
    "AgentCommand",
    "WorldEvent",
    "ActionRequest",
)
ISR_SYMBOLS = (
    "inter_society_relations",
    "InterSocietyRelationsAnalysis",
    "derive_inter_society_pair_id",
    "harvest_inter_society_relations",
    "inter_society_relation_structure",
)


def _import_roots(path: Path) -> set[str]:
    roots: set[str] = set()
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".", 1)[0])
        elif isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".", 1)[0])
    return roots


def test_isr_analysis_modules_exist_and_stay_detached() -> None:
    assert ISR_ANALYSIS
    for path in ISR_ANALYSIS:
        assert not _import_roots(path) & FORBIDDEN_ANALYSIS_ROOTS, path


def test_isr_simulation_modules_import_no_analysis_or_experiments() -> None:
    assert ISR_SIMULATION
    forbidden = {"analysis", "experiments", "api", "persistence", "observer"}
    for path in ISR_SIMULATION:
        assert not _import_roots(path) & forbidden, path


def test_isr_modules_never_mention_world_authority_types() -> None:
    for path in (*ISR_ANALYSIS, *ISR_SIMULATION):
        source = path.read_text(encoding="utf-8")
        for token in FORBIDDEN_WORLD_AUTHORITY:
            assert token not in source, (path, token)


def test_live_packages_never_import_isr_analysis() -> None:
    hits: list[str] = []
    for package in ("agents", "memory", "social", "world", "observer"):
        root = SRC / package
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            for symbol in ISR_SYMBOLS:
                if symbol in text:
                    hits.append(f"{path.relative_to(SRC)}:{symbol}")
            roots = _import_roots(path)
            if "analysis" in roots and "inter_society" in text:
                hits.append(f"{path.relative_to(SRC)}:analysis.inter_society")
    assert hits == []


def test_api_and_persistence_isr_modules_do_not_import_analysis() -> None:
    paths = (
        SRC / "persistence" / "inter_society_relations_filesystem.py",
        SRC / "api" / "routes" / "inter_society_relations.py",
        SRC / "api" / "inter_society_relations_cursor.py",
        SRC / "api" / "inter_society_relations_schemas.py",
    )
    for path in paths:
        assert path.is_file(), path
        assert "analysis" not in _import_roots(path), path
