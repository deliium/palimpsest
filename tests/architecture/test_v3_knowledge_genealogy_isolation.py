"""Knowledge-genealogy cognition/analysis isolation guards."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.architecture.test_analysis_isolation import _module_imports_forbidden

pytestmark = pytest.mark.architecture

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"


def test_cognition_does_not_import_analysis_knowledge_genealogy() -> None:
    hits: list[str] = []
    for path in (SRC / "agents" / "cognition").rglob("*.py"):
        hits.extend(
            _module_imports_forbidden(
                path,
                (
                    "analysis.knowledge_genealogy",
                    "analysis.knowledge_genealogy_metrics",
                ),
            )
        )
    assert hits == []


def test_cognition_practical_knowledge_avoids_world_skills() -> None:
    path = SRC / "agents" / "cognition" / "practical_knowledge.py"
    hits = _module_imports_forbidden(
        path, ("world._skills", "analysis", "analysis.knowledge_genealogy")
    )
    assert hits == []
    text = path.read_text(encoding="utf-8")
    assert "from world._" not in text
    assert "import world._" not in text


def test_api_does_not_import_analysis_knowledge_genealogy() -> None:
    hits: list[str] = []
    for path in (SRC / "api").rglob("*.py"):
        hits.extend(
            _module_imports_forbidden(
                path,
                (
                    "analysis.knowledge_genealogy",
                    "analysis.knowledge_genealogy_metrics",
                ),
            )
        )
    assert hits == []


def test_no_global_technique_registry_under_world() -> None:
    forbidden = (
        "class GlobalTechniqueRegistry",
        "class GlobalKnowledge",
        "class TechniqueRegistry",
        "class SocietyEncyclopedia",
    )
    hits: list[str] = []
    for path in (SRC / "world").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            if token in text:
                hits.append(f"{path.relative_to(ROOT)}:{token}")
    assert hits == []
