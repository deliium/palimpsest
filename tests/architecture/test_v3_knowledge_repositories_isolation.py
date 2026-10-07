"""Knowledge-repository analysis must not bind cognition or private world authority."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.architecture.test_analysis_isolation import _module_imports_forbidden

pytestmark = pytest.mark.architecture

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"


def test_cognition_does_not_import_knowledge_repository_metrics() -> None:
    hits: list[str] = []
    for path in (SRC / "agents" / "cognition").rglob("*.py"):
        hits.extend(
            _module_imports_forbidden(
                path, ("analysis.knowledge_repository_metrics",)
            )
        )
    assert hits == []


def test_knowledge_repository_metrics_avoid_private_world_and_cognition() -> None:
    path = SRC / "analysis" / "knowledge_repository_metrics.py"
    text = path.read_text(encoding="utf-8")
    assert "agents.cognition" not in text
    assert "from world._" not in text
    assert "import world._" not in text
    assert "from world.repositories" not in text
    assert "LibraryInstitution" not in text
    hits = _module_imports_forbidden(
        path, ("agents.cognition", "world._operations", "world._state")
    )
    assert hits == []


def test_api_does_not_import_analysis_repository_metrics() -> None:
    hits: list[str] = []
    for path in (SRC / "api").rglob("*.py"):
        hits.extend(
            _module_imports_forbidden(
                path, ("analysis.knowledge_repository_metrics",)
            )
        )
    assert hits == []


def test_no_library_institution_controller_types() -> None:
    """Reject hard-coded institution controller types (deny-list strings OK)."""
    forbidden = (
        "class LibraryInstitution",
        "class GlobalArchive",
        "class SocietyLibrary",
    )
    hits: list[str] = []
    for path in (SRC / "world").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            if token in text:
                hits.append(f"{path.relative_to(ROOT)}:{token}")
    assert hits == []
