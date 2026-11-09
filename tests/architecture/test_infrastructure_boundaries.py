"""V4-16 infrastructure_networks ownership, isolation, and pin boundaries."""

from __future__ import annotations

import ast
from pathlib import Path

from analysis.specifications import METRIC_FAMILY_COUNT
from observer.version import SEMANTIC_EVENT_TYPES
from simulation.compatibility import (
    ALEMBIC_HEAD_REVISION,
)
from simulation.compatibility import (
    V4_OWNED_CAPABILITY_FLAGS as COMPAT_OWNED,
)
from simulation.persistence import (
    ACCEPTED_EVENT_SCHEMA_VERSIONS,
    ACCEPTED_PERSISTENCE_CODEC_VERSIONS,
)
from simulation.runner_models import _V4_OWNED_CAPABILITY_FLAGS as RUNNER_OWNED
from simulation.v4_architecture import V4_CAPABILITY_FLAGS
from world._rules import COMMAND_RULE_MATRIX
from world.collective_projects import (
    DRAW_PUBLIC_KINDS,
    PRESENCE_PUBLIC_KINDS,
    PUBLIC_GOOD_KINDS,
)
from world.events import EVENT_SCHEMA_REPLAY_V22, EVENT_SCHEMA_REPLAY_V23
from world.infrastructure import (
    INFRASTRUCTURE_CATALOG,
    INFRASTRUCTURE_FORBIDDEN_FIELDS,
)

ROOT = Path(__file__).resolve().parents[2]

INFRA_ANALYSIS = ROOT / "src" / "analysis" / "infrastructure_metrics.py"
INFRA_ANALYSIS_HARVEST = (
    ROOT / "src" / "analysis" / "infrastructure_networks_analysis.py"
)
INFRA_WORLD = ROOT / "src" / "world" / "infrastructure.py"
INFRA_WORLD_IMPL = ROOT / "src" / "world" / "_infrastructure.py"

FORBIDDEN_CLASSES = {
    "CivilizationScore",
    "InfrastructurePlanner",
    "AutoMaintainScheduler",
    "NationInfrastructure",
    "InfraActor",
    "GridPlanner",
}


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            roots.add(node.module.split(".", 1)[0])
        elif isinstance(node, ast.Import):
            roots.update(alias.name.split(".", 1)[0] for alias in node.names)
    return roots


def test_owned_flags_include_infrastructure_and_stay_equal() -> None:
    assert COMPAT_OWNED == RUNNER_OWNED
    assert len(COMPAT_OWNED) == 6
    assert "infrastructure_networks" in COMPAT_OWNED
    assert "supply_chains" not in COMPAT_OWNED
    unowned = set(V4_CAPABILITY_FLAGS) - set(COMPAT_OWNED)
    assert len(unowned) == 6
    assert "supply_chains" in unowned


def test_wire_pins_for_infrastructure_landing() -> None:
    assert METRIC_FAMILY_COUNT == 192
    assert EVENT_SCHEMA_REPLAY_V23 == 23
    assert EVENT_SCHEMA_REPLAY_V22 == 22
    assert EVENT_SCHEMA_REPLAY_V23 in ACCEPTED_EVENT_SCHEMA_VERSIONS
    assert max(ACCEPTED_EVENT_SCHEMA_VERSIONS) == 27
    assert "v21" in ACCEPTED_PERSISTENCE_CODEC_VERSIONS
    assert "v22" not in ACCEPTED_PERSISTENCE_CODEC_VERSIONS
    assert "v25" in ACCEPTED_PERSISTENCE_CODEC_VERSIONS
    assert len(COMMAND_RULE_MATRIX) == 43
    assert len(SEMANTIC_EVENT_TYPES) == 73
    assert ALEMBIC_HEAD_REVISION == "0017"
    assert not list((ROOT / "alembic" / "versions").glob("0018_*.py"))


def test_forbid_list_locked_on_world_contract() -> None:
    assert "score" in INFRASTRUCTURE_FORBIDDEN_FIELDS
    assert "civilization_score" in INFRASTRUCTURE_FORBIDDEN_FIELDS
    assert "auto_maintain" in INFRASTRUCTURE_FORBIDDEN_FIELDS
    assert "planner" in INFRASTRUCTURE_FORBIDDEN_FIELDS
    assert len(INFRASTRUCTURE_CATALOG) == 8


def test_analysis_modules_do_not_import_cognition() -> None:
    for path in (INFRA_ANALYSIS, INFRA_ANALYSIS_HARVEST):
        assert path.is_file(), path
        roots = _imports(path)
        assert "agents" not in roots
        assert "cognition" not in roots


def test_no_forbidden_class_names_in_infrastructure_modules() -> None:
    paths = [
        INFRA_WORLD,
        INFRA_WORLD_IMPL,
        INFRA_ANALYSIS,
        INFRA_ANALYSIS_HARVEST,
        ROOT / "src" / "simulation" / "infrastructure_models.py",
        ROOT / "src" / "api" / "routes" / "infrastructure_networks.py",
    ]
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        names = {
            node.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
        }
        assert names.isdisjoint(FORBIDDEN_CLASSES), (path, names & FORBIDDEN_CLASSES)


def test_no_auto_maintain_scheduler_string() -> None:
    for path in (INFRA_WORLD, INFRA_WORLD_IMPL):
        text = path.read_text(encoding="utf-8")
        assert "auto_maintain" not in text or "FORBIDDEN" in text
        assert "AutoMaintain" not in text
        assert "GridPlanner" not in text


def test_public_good_sets_exclude_infra_only_kinds() -> None:
    infra_only = frozenset({"road", "irrigation", "trade_post", "large_shelter"})
    public_values = frozenset(kind.value for kind in PUBLIC_GOOD_KINDS)
    draw_values = frozenset(kind.value for kind in DRAW_PUBLIC_KINDS)
    presence_values = frozenset(kind.value for kind in PRESENCE_PUBLIC_KINDS)
    assert public_values.isdisjoint(infra_only)
    assert draw_values.isdisjoint(infra_only)
    assert presence_values.isdisjoint(infra_only)
    # Pre-V4-16 public-good membership retained.
    assert "well" in public_values
    assert "warning_post" in public_values


def test_no_v2_api_surface_for_infrastructure() -> None:
    routes = (ROOT / "src" / "api" / "routes" / "infrastructure_networks.py").read_text(
        encoding="utf-8"
    )
    assert "/v2/" not in routes
    assert "infrastructure-networks" in routes
