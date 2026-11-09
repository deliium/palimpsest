# mypy: ignore-errors
"""V4-13 border authority, import, route, and pin boundaries."""

from __future__ import annotations

import ast
from pathlib import Path

from analysis.specifications import METRIC_FAMILY_COUNT
from observer.version import SEMANTIC_EVENT_TYPES
from simulation.borders_ports import BORDERS_CURSOR_PURPOSES
from simulation.compatibility import (
    ALEMBIC_HEAD_REVISION,
    V4_OWNED_CAPABILITY_FLAGS,
)
from simulation.persistence import ACCEPTED_PERSISTENCE_CODEC_VERSIONS
from simulation.v4_architecture import V4_CAPABILITY_FLAGS, V4_CONTEXTS
from world._rules import COMMAND_RULE_MATRIX
from world.events import EVENT_SCHEMA_REPLAY_V22

ROOT = Path(__file__).resolve().parents[2]

BORDER_PATHS = tuple(
    sorted(
        path
        for pattern in (
            "src/agents/cognition/borders*.py",
            "src/analysis/borders*.py",
            "src/simulation/borders*.py",
            "src/experiments/borders*.py",
            "src/persistence/borders_filesystem.py",
            "src/research_runner/borders_composition.py",
            "src/api/routes/borders.py",
            "src/api/borders_schemas.py",
            "src/api/borders_cursor.py",
        )
        for path in ROOT.glob(pattern)
    )
)

FORBIDDEN_CLASSES = {
    "Border",
    "CountryOwner",
    "Sovereignty",
    "TerritoryRegistry",
    "BorderRegistry",
    "BorderAuthority",
    "BorderExecutor",
    "WarState",
    "LegitimacyOracle",
    "TruthEngine",
    "WinnerOracle",
}

COMMAND_CONSTRUCTORS = {
    "Attack",
    "Move",
    "Take",
    "Give",
    "Flee",
    "Help",
    "Feed",
    "Transport",
    "Wait",
    "Seize",
    "Defend",
    "Guard",
    "Protect",
    "Block",
    "Enforce",
    "Claim",
}


def _tree(path: Path) -> ast.AST:
    return ast.parse(path.read_text(encoding="utf-8"))


def test_border_paths_exist() -> None:
    names = {path.name for path in BORDER_PATHS}
    expected = {
        "borders.py",
        "borders_communication.py",
        "borders_models.py",
        "borders_codec.py",
        "borders_ports.py",
        "borders_paging.py",
        "borders_filesystem.py",
    }
    assert expected <= names
    assert len(BORDER_PATHS) >= 20


def test_no_objective_border_or_owner_field_exists() -> None:
    forbidden = {
        "country_owner",
        "sovereign",
        "territory_owner",
        "controller",
        "border_owner",
        "ownership",
    }
    for path in (ROOT / "src" / "world").rglob("*.py"):
        tree = _tree(path)
        names = {
            node.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Name)
        } | {
            node.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Attribute)
        }
        assert names.isdisjoint(forbidden), (path, names & forbidden)


def test_no_authority_or_registry_class_exists() -> None:
    for path in BORDER_PATHS:
        tree = _tree(path)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                assert node.name not in FORBIDDEN_CLASSES, (path, node.name)


def test_no_command_construction_or_resolution() -> None:
    for path in BORDER_PATHS:
        tree = _tree(path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = getattr(node.func, "id", None) or getattr(
                    node.func, "attr", None
                )
                assert name not in COMMAND_CONSTRUCTORS, (path, name)
                assert name not in {"submit", "resolve", "admit"}, (path, name)


def test_no_score_or_oracle_result_field() -> None:
    forbidden = {
        "winner",
        "loser",
        "score",
        "composite",
        "sovereignty",
        "legitimacy",
        "country_owner",
        "ownership",
        "refugee",
        "forced",
        "wellbeing",
        "assimilation",
        "enforcement",
    }
    for path in BORDER_PATHS:
        tree = _tree(path)
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            for item in node.body:
                targets: list[ast.expr] = []
                if isinstance(item, ast.AnnAssign):
                    targets = [item.target]
                elif isinstance(item, ast.Assign):
                    targets = list(item.targets)
                for target in targets:
                    if isinstance(target, ast.Name):
                        assert target.id not in forbidden, (path, node.name, target.id)


def test_world_and_perception_never_read_border_ledgers() -> None:
    for path in (
        *(ROOT / "src" / "world").rglob("*.py"),
        *(ROOT / "src" / "observer").rglob("*.py"),
    ):
        text = path.read_text(encoding="utf-8")
        assert "borders" not in text
        assert "BorderLedger" not in text
    for path in (
        ROOT / "src" / "simulation" / "perception.py",
        ROOT / "src" / "simulation" / "engine.py",
    ):
        text = path.read_text(encoding="utf-8")
        assert "BorderLedger" not in text
        assert "from agents.cognition.borders" not in text


def test_analysis_modules_are_detached() -> None:
    forbidden = (
        "agents.cognition",
        "experiments",
        "api",
        "persistence",
        "observer",
        "simulation.runner",
    )
    for path in (ROOT / "src" / "analysis").glob("borders_*.py"):
        tree = _tree(path)
        for node in ast.walk(tree):
            modules: list[str] = []
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules = [node.module]
            for module in modules:
                for prefix in forbidden:
                    assert not module.startswith(prefix), (path, module)


def test_no_peer_ledger_read_in_update_pipeline() -> None:
    source = (ROOT / "src" / "agents" / "cognition" / "borders.py").read_text(
        encoding="utf-8"
    )
    tree = ast.parse(source)
    function = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "apply_borders_update"
    )
    arguments = {
        argument.arg for argument in function.args.args + function.args.kwonlyargs
    }
    assert "territorial_claims" in arguments
    assert not any(
        name.endswith("_ledger") or name in {"peer", "other_owner", "foreign"}
        for name in arguments
    )


def test_snapshot_and_api_do_not_rebuild_analysis() -> None:
    for path in (
        *(ROOT / "src" / "simulation").glob("borders_*.py"),
        ROOT / "src" / "api" / "routes" / "borders.py",
    ):
        tree = _tree(path)
        for node in ast.walk(tree):
            modules: list[str] = []
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules = [node.module]
            for module in modules:
                assert not module.startswith("analysis"), (path, module)
                assert not module.startswith("experiments"), (path, module)
                assert not module.startswith("agents.cognition"), (path, module)


def test_exactly_six_get_routes() -> None:
    source = (ROOT / "src" / "api" / "routes" / "borders.py").read_text(
        encoding="utf-8"
    )
    assert source.count("@router.get(") == 6
    for verb in ("@router.post", "@router.put", "@router.patch", "@router.delete"):
        assert verb not in source


def test_no_v2_route_or_protocol() -> None:
    for path in BORDER_PATHS:
        text = path.read_text(encoding="utf-8")
        assert "/v2" not in text
        assert "observer-protocol-v2" not in text


def test_pins_are_unchanged() -> None:
    assert len(COMMAND_RULE_MATRIX) == 43
    assert len(SEMANTIC_EVENT_TYPES) == 73
    assert EVENT_SCHEMA_REPLAY_V22 == 22
    assert "v20" in ACCEPTED_PERSISTENCE_CODEC_VERSIONS
    assert "v21" not in ACCEPTED_PERSISTENCE_CODEC_VERSIONS
    assert len(V4_CONTEXTS) == 14
    assert len(V4_CAPABILITY_FLAGS) == 12
    assert METRIC_FAMILY_COUNT == 184
    assert ALEMBIC_HEAD_REVISION == "0017"
    assert len(V4_OWNED_CAPABILITY_FLAGS) == 5
    assert BORDERS_CURSOR_PURPOSES == {
        "summary",
        "claims",
        "claim",
        "agreements",
        "agreement",
        "control",
    }


def test_godot_and_ui_are_read_only() -> None:
    ui = (ROOT / "clients/research-ui/src/api/borders.ts").read_text(
        encoding="utf-8"
    )
    for verb in (
        "method: 'POST'",
        "method: 'PUT'",
        "method: 'PATCH'",
        "method: 'DELETE'",
    ):
        assert verb not in ui
    session = (
        ROOT / "clients/godot-observer/scripts/net/session.gd"
    ).read_text(encoding="utf-8")
    assert "request_border_summary" in session
    assert "_request_path" in session


def test_no_raw_ids_in_publication_types() -> None:
    for path in (
        ROOT / "src" / "simulation" / "borders_models.py",
        ROOT / "src" / "api" / "borders_schemas.py",
    ):
        text = path.read_text(encoding="utf-8")
        for token in ("AgentId", "EntityId", "EventId", "RunId"):
            assert token not in text, (path, token)


def test_snapshot_summary_and_candidate_refs_resolve() -> None:
    from simulation.borders_codec import finalize_borders_snapshot
    from simulation.borders_models import (
        BordersCandidateRow,
        BordersLineageRow,
        empty_borders_snapshot,
    )

    snapshot = finalize_borders_snapshot(
        empty_borders_snapshot(
            "run-1", publication_id="bd-pub-pending", digest="0" * 64
        )
    )
    assert snapshot.summary.candidate_count == len(snapshot.candidates) == 0
    candidate = BordersCandidateRow(
        "bord-0000000000000001", ("bloc-1",), (), "claimed", 1, 0, 0
    )
    edge = BordersLineageRow(
        "bord-edge-1",
        "bord-start-0000000000000001",
        candidate.candidate_token,
        "emerged",
        0,
        0,
    )
    assert edge.child_token == candidate.candidate_token
