# mypy: ignore-errors
"""V4-11 treaty boundaries: no authority, registry, score, or command path."""

from __future__ import annotations

import ast
from pathlib import Path

from analysis.specifications import METRIC_FAMILY_COUNT
from api.routes.diplomacy import router as diplomacy_router
from simulation.compatibility import V4_OWNED_CAPABILITY_FLAGS
from simulation.diplomacy_models import (
    DIPLOMACY_SNAPSHOT_SCHEMA,
    SUPPORTED_DIPLOMACY_SNAPSHOT_SCHEMAS,
)
from simulation.v4_architecture import V4_CONTEXTS

ROOT = Path(__file__).resolve().parents[2]


def _treaty_paths() -> list[Path]:
    patterns = (
        "src/agents/cognition/diplomacy*.py",
        "src/analysis/diplomacy*.py",
        "src/simulation/diplomacy*.py",
        "src/experiments/diplomacy*.py",
        "src/persistence/diplomacy*.py",
        "src/research_runner/diplomacy*.py",
        "src/api/routes/diplomacy.py",
        "src/api/diplomacy*.py",
    )
    return [path for pattern in patterns for path in ROOT.glob(pattern)]


def test_no_authority_or_registry_class_exists() -> None:
    forbidden = {
        "TreatyStore",
        "TreatyAuthority",
        "TreatyRegistry",
        "TreatyExecutor",
        "CeasefireState",
        "WarState",
        "ArmyActor",
        "Polity",
        "Border",
        "Citizenship",
        "RelationScore",
        "DiplomacyScore",
        "LegitimacyOracle",
        "TruthEngine",
    }
    for path in _treaty_paths():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        classes = {
            node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)
        }
        assert forbidden.isdisjoint(classes), (path.name, forbidden & classes)


def test_no_forbidden_result_field_exists() -> None:
    forbidden = {
        "binding",
        "enforced",
        "enforcement",
        "legitimate",
        "truth",
        "misremembered",
        "false_belief",
        "winner",
        "score",
        "rank",
        "trust",
        "valence",
        "composite",
        "overall_relation",
    }
    for path in _treaty_paths():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        names = {
            node.target.id
            for node in ast.walk(tree)
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
        }
        assert forbidden.isdisjoint(names), (path.name, forbidden & names)


def test_catalog_and_context_pins_are_unchanged() -> None:
    assert METRIC_FAMILY_COUNT == 188
    assert len(V4_CONTEXTS) == 14
    assert len(V4_OWNED_CAPABILITY_FLAGS) == 6


def test_snapshot_v2_and_v1_are_supported() -> None:
    assert DIPLOMACY_SNAPSHOT_SCHEMA == "diplomacy-snapshot-v2"
    assert set(SUPPORTED_DIPLOMACY_SNAPSHOT_SCHEMAS) == {
        "diplomacy-snapshot-v1",
        "diplomacy-snapshot-v2",
    }


def test_exactly_eight_get_diplomacy_routes() -> None:
    routes = [
        route
        for route in diplomacy_router.routes
        if getattr(route, "methods", None) is not None
    ]
    assert len(routes) == 8
    assert all(route.methods == {"GET"} for route in routes)


def test_world_and_engine_never_read_treaties() -> None:
    for path in (
        *(ROOT / "src" / "world").glob("*.py"),
        ROOT / "src" / "simulation" / "engine.py",
        ROOT / "src" / "simulation" / "perception.py",
    ):
        source = path.read_text(encoding="utf-8")
        assert "agents.cognition.diplomacy" not in source
        assert "DiplomacyLedger" not in source
        assert "treaty_id" not in source


def test_treaty_command_paths_are_absent() -> None:
    forbidden_calls = {"submit", "admit", "submit_command", "resolve_command"}
    for path in _treaty_paths():
        source = path.read_text(encoding="utf-8")
        assert "AgentCommand" not in source, path
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                name = (
                    func.id
                    if isinstance(func, ast.Name)
                    else func.attr
                    if isinstance(func, ast.Attribute)
                    else ""
                )
                assert name not in forbidden_calls, (path.name, name)


def test_analysis_treaty_modules_are_detached() -> None:
    for path in sorted((ROOT / "src" / "analysis").glob("diplomacy*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module)
        for forbidden in (
            "analysis.experiments",
            "analysis.persistence",
            "analysis.api",
            "agents.cognition",
            "experiments",
            "persistence",
            "api",
        ):
            assert not any(
                item == forbidden or item.startswith(f"{forbidden}.")
                for item in imports
            ), (path.name, forbidden)


def test_treaty_analysis_never_calls_identity_mutation_helpers() -> None:
    forbidden = ("mint", "rename", "split", "merge", "dissolve")
    for path in sorted((ROOT / "src" / "analysis").glob("diplomacy*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                name = (
                    func.id
                    if isinstance(func, ast.Name)
                    else func.attr
                    if isinstance(func, ast.Attribute)
                    else ""
                )
                lowered = name.lower()
                assert not any(part in lowered for part in forbidden), (
                    path.name,
                    name,
                )


def test_treaty_frame_and_snapshot_bounds_are_exact() -> None:
    from agents.cognition.diplomacy_communication import (
        DIPLOMACY_FRAME_FIELD_COUNT,
        DIPLOMACY_FRAME_MAX_CHARS,
        TREATY_CHUNK_MAX_CHARS,
        TREATY_FRAME_FIELD_COUNT,
        TREATY_FRAME_MAX_CHARS,
        TREATY_MAX_CHUNKS,
    )
    from persistence.diplomacy_filesystem import DIPLOMACY_STORE_SCHEMA

    assert DIPLOMACY_FRAME_FIELD_COUNT == 15
    assert DIPLOMACY_FRAME_MAX_CHARS == 320
    assert TREATY_FRAME_FIELD_COUNT == 22
    assert TREATY_FRAME_MAX_CHARS == 832
    assert TREATY_CHUNK_MAX_CHARS == 240
    assert TREATY_MAX_CHUNKS == 4
    assert DIPLOMACY_STORE_SCHEMA == "diplomacy-store-v1"


def test_no_v2_route_or_observer_protocol_v2() -> None:
    from observer.version import OBSERVER_PROTOCOL_VERSION

    assert OBSERVER_PROTOCOL_VERSION == "observer-protocol-v1"
    for route in diplomacy_router.routes:
        path = getattr(route, "path", "")
        assert "/v2" not in path
        assert path.startswith("/v1/simulations")


def test_observer_and_godot_never_read_treaty_ledgers() -> None:
    for path in sorted((ROOT / "src" / "observer").glob("*.py")):
        source = path.read_text(encoding="utf-8")
        assert "treaty" not in source.lower(), path
        assert "DiplomacyLedger" not in source, path
    for path in sorted((ROOT / "clients" / "godot-observer").rglob("*.gd")):
        source = path.read_text(encoding="utf-8")
        assert "treaty" not in source.lower(), path
        assert "DiplomacyLedger" not in source, path
