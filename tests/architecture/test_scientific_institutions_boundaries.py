"""V4-32 authority, import, and compatibility gates."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from analysis.specifications import (
    METRIC_FAMILY_COUNT,
    all_metric_specifications,
)
from persistence.scientific_institutions_filesystem import (
    SCIENTIFIC_INSTITUTIONS_STORE_VERSION,
)
from simulation import V4_CONTEXTS, V4CapabilityFlags
from simulation.scientific_institutions_models import (
    SCIENTIFIC_INSTITUTIONS_SNAPSHOT_VERSION,
)
from world._rules import COMMAND_RULE_MATRIX

pytestmark = pytest.mark.architecture

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                found.add(node.module.split(".")[0])
    return found


def test_analysis_does_not_import_outer_or_cognition_packages() -> None:
    forbidden = {
        "agents",
        "api",
        "experiments",
        "infrastructure",
        "observer",
        "persistence",
        "research_runner",
    }
    for path in (SRC / "analysis").glob("scientific_institutions*.py"):
        assert not (_imports(path) & forbidden), path.name


def test_api_route_uses_only_ports_and_adapters() -> None:
    path = SRC / "api" / "routes" / "scientific_institutions.py"
    imports = _imports(path)
    assert "analysis" not in imports
    assert "experiments" not in imports
    assert "persistence" not in imports


def test_clients_never_import_python_analysis() -> None:
    for path in (ROOT / "clients").glob("*/src/**/*"):
        if path.suffix not in {".ts", ".svelte", ".py", ".js"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        assert "from 'analysis" not in text
        assert 'from "analysis' not in text
        assert "import analysis" not in text


def test_no_predefined_university_or_academy_class() -> None:
    for path in SRC.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                lowered = node.name.lower()
                assert "university" not in lowered
                assert "academy" not in lowered


def test_catalog_and_command_pins_move_only_by_the_append() -> None:
    assert METRIC_FAMILY_COUNT == 275
    families = [spec.family_id.value for spec in all_metric_specifications()]
    assert families[268:271] == [
        "scientific_institution_practice",
        "scientific_institution_roles_and_carriers",
        "scientific_institution_lineage",
    ]
    assert len(COMMAND_RULE_MATRIX) == 45
    assert len(V4_CONTEXTS) == 17
    assert len(V4CapabilityFlags.__dataclass_fields__) == 12
    assert SCIENTIFIC_INSTITUTIONS_SNAPSHOT_VERSION == (
        "scientific-institutions-snapshot-v1"
    )
    assert SCIENTIFIC_INSTITUTIONS_STORE_VERSION == (
        "scientific-institutions-store-v1"
    )


def test_no_new_migration_or_version_surface() -> None:
    versions = SRC.parent / "alembic" / "versions"
    assert list(versions.glob("0018_*.py")) == []
    runner_models = (SRC / "simulation" / "runner_models.py").read_text(
        encoding="utf-8"
    )
    assert "runner-config-v59" not in runner_models
