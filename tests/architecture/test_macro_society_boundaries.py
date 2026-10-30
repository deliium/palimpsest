"""Macro-society authority, import, and compatibility boundaries."""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from analysis.macro_society_contract import MacroSocietyLane
from analysis.macro_society_evidence import MacroSocietyEdge, MacroSocietyWindowEvidence
from experiments.macro_society_publication import (
    MacroSocietyHarvest,
    build_macro_society_harvest_result,
)
from simulation.macro_society_models import (
    MACRO_SOCIETY_SNAPSHOT_SCHEMA_VERSION,
    MacroSocietySnapshot,
)
from simulation.v4_architecture import V4ContextId
from simulation.runner_models import V4CapabilityFlags

ROOT = Path(__file__).resolve().parents[2]

ANALYSIS_MODULES = tuple(sorted((ROOT / "src" / "analysis").glob("macro_society_*.py")))
SIMULATION_MODULES = tuple(
    sorted((ROOT / "src" / "simulation").glob("macro_society_*.py"))
)
FORBIDDEN_ANALYSIS_ROOTS = {
    "simulation",
    "persistence",
    "api",
    "experiments",
    "observer",
    "infrastructure",
}
FORBIDDEN_WORLD_AUTHORITY = (
    "WorldEngine",
    "WorldState",
    "ActionSubmission",
    "AgentCommand",
    "WorldEvent",
    "ActionRequest",
)
MAGIC_ACTOR_PATTERN = re.compile(
    r"class\s+(Nation|Country|Civilization|Government|Society|Polity|Tribe|Empire|State)\b"
)


def _imports(path: Path) -> set[str]:
    roots: set[str] = set()
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".", 1)[0])
        elif isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".", 1)[0])
    return roots


def test_analysis_modules_import_only_the_analysis_layer() -> None:
    assert ANALYSIS_MODULES
    for path in ANALYSIS_MODULES:
        roots = _imports(path)
        assert not roots & FORBIDDEN_ANALYSIS_ROOTS, path


def test_simulation_modules_import_no_outer_layer() -> None:
    assert SIMULATION_MODULES
    forbidden = {"analysis", "experiments", "api", "persistence", "observer", "infrastructure"}
    for path in SIMULATION_MODULES:
        assert not _imports(path) & forbidden, path


def test_persistence_and_api_modules_respect_their_layers() -> None:
    persistence = ROOT / "src" / "persistence" / "macro_society_filesystem.py"
    api_route = ROOT / "src" / "api" / "routes" / "macro_society.py"
    api_cursor = ROOT / "src" / "api" / "macro_society_cursor.py"
    for path in (persistence,):
        assert not _imports(path) & {"analysis", "experiments", "api", "observer"}, path
    for path in (api_route, api_cursor):
        assert not _imports(path) & {"analysis", "experiments"}, path


def test_no_module_mentions_world_authority_types() -> None:
    for path in (*ANALYSIS_MODULES, *SIMULATION_MODULES):
        source = path.read_text(encoding="utf-8")
        for token in FORBIDDEN_WORLD_AUTHORITY:
            assert token not in source, (path, token)


def test_no_magic_actor_class_or_registry_exists() -> None:
    for directory in (ROOT / "src" / "analysis", ROOT / "src" / "simulation"):
        for path in directory.glob("macro_society_*.py"):
            source = path.read_text(encoding="utf-8")
            assert not MAGIC_ACTOR_PATTERN.search(source), path
            assert "society_registry" not in source, path
            assert "register_society" not in source, path


def test_no_capability_flag_or_runner_schema_is_referenced() -> None:
    for path in (*ANALYSIS_MODULES, *SIMULATION_MODULES):
        source = path.read_text(encoding="utf-8")
        assert "v4_capability_flags" not in source, path
        assert "V4CapabilityFlags" not in source, path
        assert "runner-config-v57" not in source, path
    assert V4CapabilityFlags().any_enabled() is False


def test_macro_context_is_analysis_only_and_unflagged() -> None:
    from simulation.v4_architecture import V4_ANALYSIS_ONLY_CONTEXTS, V4_CONTEXT_BY_ID

    spec = V4_CONTEXT_BY_ID[V4ContextId.MACRO_SOCIETY_IDENTITY]
    assert V4ContextId.MACRO_SOCIETY_IDENTITY in V4_ANALYSIS_ONLY_CONTEXTS
    assert spec.capability_flag is None
    assert spec.owner_packages == ("analysis",)


def test_observer_protocol_and_capabilities_are_unchanged() -> None:
    from observer.capabilities import (
        OBSERVER_CAPABILITIES,
        SUPPORTED_OBSERVER_PROTOCOLS,
    )
    from observer.version import OBSERVER_LAYOUT_SCHEMA_VERSION

    assert SUPPORTED_OBSERVER_PROTOCOLS == ("observer-protocol-v1",)
    assert OBSERVER_LAYOUT_SCHEMA_VERSION == "observer-layout-v1"
    assert len(OBSERVER_CAPABILITIES) == 4


def test_event_and_migration_pins_are_unchanged() -> None:
    from simulation.compatibility import ALEMBIC_HEAD_REVISION
    from world.events import EVENT_SCHEMA_REPLAY_V22

    assert EVENT_SCHEMA_REPLAY_V22 == 22
    assert ALEMBIC_HEAD_REVISION == "0017"
    assert not any(
        "0018" in path.name for path in (ROOT / "alembic" / "versions").glob("*.py")
    )


def test_route_module_is_get_only() -> None:
    path = ROOT / "src" / "api" / "routes" / "macro_society.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    methods = [
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "router"
    ]
    assert methods == ["get"] * 4


def test_snapshot_schema_is_versioned_and_independent() -> None:
    assert MACRO_SOCIETY_SNAPSHOT_SCHEMA_VERSION == "macro-society-snapshot-v1"
    assert "analysis" not in _imports(
        ROOT / "src" / "simulation" / "macro_society_models.py"
    )


def test_publication_uses_no_capability_flag_and_no_objective_authority() -> None:
    persons = tuple(f"person-{index}" for index in range(1, 9))
    edges = tuple(
        MacroSocietyEdge(MacroSocietyLane.INTERACTION, source, target, 0)
        for index, source in enumerate(persons[:4])
        for target in persons[:4][index + 1 :]
    )
    harvest = MacroSocietyHarvest(
        run_id="run-1",
        input_revision="rev-1",
        windows=(
            MacroSocietyWindowEvidence(
                window_index=0,
                tick_start=0,
                tick_end=9,
                person_ids=persons,
                edges=edges,
            ),
        ),
        generated_tick=9,
    )
    result = build_macro_society_harvest_result(harvest)
    assert isinstance(result.snapshot, MacroSocietySnapshot)
    assert result.snapshot.provenance_code == "ok"
    assert all(
        candidate.macro_society_id.startswith("msoc-")
        for candidate in result.snapshot.candidates
    )
