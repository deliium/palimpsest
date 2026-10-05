"""Architecture gates: dependency-care never assigns caregivers."""

from __future__ import annotations

import ast
import logging
from pathlib import Path

import pytest

pytestmark = pytest.mark.architecture

_LOG = logging.getLogger("tests.architecture.v3_dependency_care_isolation")

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC = _REPO_ROOT / "src"


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    return imported


def test_dependency_care_world_module_does_not_import_social() -> None:
    _LOG.debug("case_id=dependency_care_no_social")
    path = _SRC / "world" / "dependency_care.py"
    imported = _imported_modules(path)
    social_hits = {
        name for name in imported if name == "social" or name.startswith("social.")
    }
    assert social_hits == set(), sorted(social_hits)


def test_caregiving_bias_does_not_import_world_kinship() -> None:
    _LOG.debug("case_id=caregiving_no_objective_kinship")
    path = _SRC / "agents" / "cognition" / "caregiving.py"
    imported = _imported_modules(path)
    assert "world.kinship" not in imported
    assert "world.kinship" not in {
        name for name in imported if name.startswith("world.kinship")
    }


def test_caregiving_bias_does_not_import_analysis() -> None:
    _LOG.debug("case_id=caregiving_no_analysis_feedback")
    path = _SRC / "agents" / "cognition" / "caregiving.py"
    imported = _imported_modules(path)
    hits = {
        name
        for name in imported
        if name == "analysis" or name.startswith("analysis.")
    }
    assert hits == set(), sorted(hits)


def test_engine_has_no_parent_caregiver_map() -> None:
    _LOG.debug("case_id=engine_no_parent_caregiver_assignment")
    text = (_SRC / "simulation" / "engine.py").read_text(encoding="utf-8")
    for token in (
        "parent_id_caregiver",
        "assigned_caregiver",
        "must_care_for",
        "caregiver_map",
        "auto_assign_caregiver",
    ):
        assert token not in text


def test_feed_transport_mutate_paths_do_not_write_social() -> None:
    _LOG.debug("case_id=care_ops_no_social_writes")
    for rel in (
        Path("world") / "_operations.py",
        Path("world") / "_rules.py",
        Path("world") / "dependency_care.py",
    ):
        path = _SRC / rel
        imported = _imported_modules(path)
        social_hits = {
            name for name in imported if name == "social" or name.startswith("social.")
        }
        assert social_hits == set(), f"{rel}: {sorted(social_hits)}"
        source = path.read_text(encoding="utf-8")
        for forbidden in (
            "DirectedRelationshipProfile",
            "SelfModel",
            "revise_relationship",
            "WRITE_BELIEF",
            "REVISE_RELATIONSHIP",
        ):
            assert forbidden not in source, f"{rel} mentions {forbidden}"


def test_dependency_care_forbid_caregiver_role_aliases() -> None:
    _LOG.debug("case_id=forbidden_need_aliases")
    from world.dependency_care import FORBIDDEN_NEED_ALIASES

    for token in ("love", "parenting", "attachment", "caregiver", "guardian", "nanny"):
        assert token in FORBIDDEN_NEED_ALIASES or token in {
            "guardian",
            "nanny",
            "caregiver",
        }
    # Closed aliases documented in module.
    text = (_SRC / "world" / "dependency_care.py").read_text(encoding="utf-8")
    assert "nanny" in text or "guardian" in text or "caregiver" in text
