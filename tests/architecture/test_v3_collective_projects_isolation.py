"""Collective-project work stays objective and does not install a leader."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.architecture.test_analysis_isolation import _module_imports_forbidden
from world.collective_projects import CollectiveProject, ProjectContribution
from world.observations import ObservedCollectiveProject, ObservedProjectContribution

pytestmark = pytest.mark.architecture

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
_FORBIDDEN_FIELDS = frozenset(
    {
        "leader",
        "leader_id",
        "project_leader",
        "foreman",
        "chief",
        "manager",
        "coordinator_id",
        "crew_boss",
        "institution",
        "work_crew",
        "created_by",
    }
)


def test_agents_do_not_import_analysis() -> None:
    hits: list[str] = []
    for path in (SRC / "agents").rglob("*.py"):
        hits.extend(_module_imports_forbidden(path, ("analysis",)))
    assert hits == []


def test_project_types_have_no_leader_field() -> None:
    for model in (
        CollectiveProject,
        ProjectContribution,
        ObservedCollectiveProject,
        ObservedProjectContribution,
    ):
        assert _FORBIDDEN_FIELDS.isdisjoint(model.__slots__)


def test_new_modules_do_not_name_a_library_institution() -> None:
    paths = (
        SRC / "world" / "collective_projects.py",
        SRC / "agents" / "cognition" / "collective_projects.py",
        SRC / "analysis" / "collective_project_metrics.py",
    )
    for path in paths:
        text = path.read_text(encoding="utf-8")
        assert "LibraryInstitution" not in text
        assert "class LibraryInstitution" not in text
