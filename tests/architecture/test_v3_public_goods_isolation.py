"""Public goods do not create access, moral, or leadership roles."""

from __future__ import annotations

from pathlib import Path

import pytest

from simulation.runner_models import PublicGoodsSpec
from tests.architecture.test_analysis_isolation import _module_imports_forbidden
from world.actions import MaintainPublicGood, OpposePublicGood, UsePublicGood
from world.collective_projects import CollectiveProject, PublicGoodAct
from world.events import PublicGoodBenefit, PublicGoodMaintained, PublicGoodOpposed
from world.observations import ObservedCollectiveProject

pytestmark = pytest.mark.architecture

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
_FORBIDDEN_FIELDS = frozenset(
    {
        "free_rider",
        "freerider",
        "free_rider_id",
        "cheater",
        "selfish",
        "guilty",
        "fair",
        "unfair",
        "deserved",
        "sanction",
        "punish",
        "punishment",
        "exclude",
        "exclusion",
        "toll",
        "wage",
        "membership",
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
        "archive",
        "library",
    }
)


def test_agents_do_not_import_analysis() -> None:
    hits: list[str] = []
    for path in (SRC / "agents").rglob("*.py"):
        hits.extend(_module_imports_forbidden(path, ("analysis",)))
    assert hits == []


def test_public_good_types_have_no_forbidden_role_fields() -> None:
    for model in (
        PublicGoodsSpec,
        PublicGoodAct,
        CollectiveProject,
        ObservedCollectiveProject,
        UsePublicGood,
        MaintainPublicGood,
        OpposePublicGood,
        PublicGoodBenefit,
        PublicGoodMaintained,
        PublicGoodOpposed,
    ):
        assert _FORBIDDEN_FIELDS.isdisjoint(model.__slots__)


def test_public_good_modules_do_not_name_a_library_institution() -> None:
    paths = (
        SRC / "world" / "collective_projects.py",
        SRC / "agents" / "cognition" / "collective_projects.py",
        SRC / "analysis" / "public_good_metrics.py",
    )
    for path in paths:
        assert "LibraryInstitution" not in path.read_text(encoding="utf-8")
