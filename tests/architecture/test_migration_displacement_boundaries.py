# mypy: ignore-errors
"""V4-14 migration-displacement authority, import, route, and pin boundaries."""

from __future__ import annotations

import ast
from pathlib import Path

from analysis.migration_displacement_layers import (
    AnalyticalWaveLayer,
    IntegrationOutcomeLayer,
    MigrationLayerLeakError,
    MigrationLayers,
    ObjectiveMovementLayer,
    SubjectiveCauseLayer,
    assert_migration_layer_separation,
)
from analysis.specifications import METRIC_FAMILY_COUNT, all_metric_specifications
from api.routes.migration_displacement import (
    MIGRATION_DISPLACEMENT_ROUTE_COUNT,
    router,
)
from observer.version import SEMANTIC_EVENT_TYPES
from simulation.compatibility import (
    ALEMBIC_HEAD_REVISION,
    V4_OWNED_CAPABILITY_FLAGS,
)
from simulation.migration_displacement_ports import (
    MIGRATION_DISPLACEMENT_CURSOR_PURPOSES,
)
from simulation.persistence import ACCEPTED_PERSISTENCE_CODEC_VERSIONS
from simulation.v4_architecture import V4_CAPABILITY_FLAGS, V4_CONTEXTS
from world._rules import COMMAND_RULE_MATRIX
from world.events import EVENT_SCHEMA_REPLAY_V22

ROOT = Path(__file__).resolve().parents[2]

MIGRATION_PATHS = tuple(
    sorted(
        path
        for pattern in (
            "src/agents/cognition/migration_displacement*.py",
            "src/analysis/migration_displacement_*.py",
            "src/simulation/migration_displacement_*.py",
            "src/experiments/migration_displacement_*.py",
            "src/persistence/migration_displacement_filesystem.py",
            "src/research_runner/migration_displacement_composition.py",
            "src/api/routes/migration_displacement.py",
            "src/api/migration_displacement_schemas.py",
            "src/api/migration_displacement_cursor.py",
        )
        for path in ROOT.glob(pattern)
    )
)

FORBIDDEN_CLASSES = {
    "Refugee",
    "RefugeeStatus",
    "AsylumSeeker",
    "DisplacedPerson",
    "RefugeeCamp",
    "ResettlementAuthority",
    "MigrationRegistry",
    "WaveRegistry",
    "MigrationWave",
    "CauseOracle",
    "IntegrationOracle",
    "AssimilationScore",
    "WellbeingScore",
    "ForcedMigrationClassifier",
    "MigrationAuthority",
    "MigrationExecutor",
    "CountryOwner",
    "Border",
    "TerritoryRegistry",
}

FORBIDDEN_COMMANDS = {
    "Migrate",
    "Evacuate",
    "Resettle",
    "Deport",
    "Expel",
    "Admit",
    "Integrate",
    "FleeTo",
    "Defend",
    "Guard",
    "Protect",
    "Block",
    "Seize",
    "Enforce",
    "Claim",
}

COMMAND_CONSTRUCTORS = FORBIDDEN_COMMANDS | {
    "Attack",
    "Move",
    "Take",
    "Give",
    "Flee",
    "Help",
    "Feed",
    "Transport",
    "Wait",
}

FORBIDDEN_OWNERSHIP_FIELDS = {
    "region_to_border",
    "country_owner",
    "sovereign",
    "controller",
    "territory_owner",
    "ownership",
}

FORBIDDEN_GEOMETRY_NAMES = {
    "region_to_border",
    "polygon",
    "grid_cell",
    "latitude",
    "longitude",
    "coordinate_to_region",
    "area_sq",
    "geometry",
}

MIGRATION_FAMILIES = (
    "migration_wave_structure",
    "migration_cause_evidence",
    "migration_cluster_cohesion",
    "migration_integration_outcome",
)


def _tree(path: Path) -> ast.AST:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _imported_modules(path: Path) -> list[str]:
    tree = _tree(path)
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.append(node.module)
    return modules


def test_migration_paths_exist() -> None:
    assert MIGRATION_PATHS, "expected migration-displacement modules"
    names = {path.name for path in MIGRATION_PATHS}
    expected = {
        "migration_displacement.py",
        "migration_displacement_communication.py",
        "migration_displacement_codec.py",
        "migration_displacement_ports.py",
        "migration_displacement_paging.py",
        "migration_displacement_filesystem.py",
        "migration_displacement_composition.py",
        "migration_displacement_schemas.py",
        "migration_displacement_cursor.py",
    }
    assert expected <= names
    assert len(MIGRATION_PATHS) >= 20


def test_no_forbidden_class_or_command_name() -> None:
    for path in MIGRATION_PATHS:
        tree = _tree(path)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                assert node.name not in FORBIDDEN_CLASSES, (path, node.name)
            if isinstance(node, ast.FunctionDef):
                assert node.name not in FORBIDDEN_COMMANDS, (path, node.name)


def test_cognition_modules_forbid_world_authority_and_peer_ledgers() -> None:
    forbidden_prefixes = (
        "world._state",
        "world._perception",
        "simulation.engine",
        "simulation.bootstrap",
    )
    forbidden_names = {
        "AgentCommand",
        "ActionSubmission",
        "WorldEvent",
        "peer_ledger",
        "other_owner_ledger",
        "foreign_ledger",
    }
    for path in (ROOT / "src" / "agents" / "cognition").glob(
        "migration_displacement*.py"
    ):
        modules = _imported_modules(path)
        for module in modules:
            for prefix in forbidden_prefixes:
                assert not (
                    module == prefix or module.startswith(f"{prefix}.")
                ), (path, module)
            assert not module.endswith("_ledger") or module.startswith(
                "agents.cognition"
            ), (path, module)
        tree = _tree(path)
        names = {
            node.id for node in ast.walk(tree) if isinstance(node, ast.Name)
        } | {
            node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
        }
        assert names.isdisjoint(forbidden_names), (path, names & forbidden_names)


def test_analysis_modules_are_detached() -> None:
    forbidden = (
        "agents.cognition",
        "experiments",
        "api",
        "persistence",
        "observer",
    )
    for path in (ROOT / "src" / "analysis").glob("migration_displacement_*.py"):
        for module in _imported_modules(path):
            for prefix in forbidden:
                assert not (
                    module == prefix or module.startswith(f"{prefix}.")
                ), (path, module)


def test_simulation_modules_are_detached() -> None:
    forbidden = (
        "analysis",
        "api",
        "experiments",
        "infrastructure",
        "persistence",
        "observer",
    )
    for path in (ROOT / "src" / "simulation").glob("migration_displacement_*.py"):
        for module in _imported_modules(path):
            for prefix in forbidden:
                assert not (
                    module == prefix or module.startswith(f"{prefix}.")
                ), (path, module)


def test_api_route_imports_no_analysis() -> None:
    path = ROOT / "src" / "api" / "routes" / "migration_displacement.py"
    for module in _imported_modules(path):
        assert not module.startswith("analysis"), (path, module)


def test_no_hash_uuid_or_wall_clock() -> None:
    for path in MIGRATION_PATHS:
        text = path.read_text(encoding="utf-8")
        assert "import uuid" not in text, path
        assert "from uuid" not in text, path
        assert "datetime.now" not in text, path
        assert "time.time" not in text, path
        tree = _tree(path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name) and func.id == "hash":
                    raise AssertionError(f"{path}: bare hash()")


def test_no_geometry_or_ownership_fields() -> None:
    for path in MIGRATION_PATHS:
        tree = _tree(path)
        names = {
            node.id for node in ast.walk(tree) if isinstance(node, ast.Name)
        } | {
            node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
        }
        assert names.isdisjoint(FORBIDDEN_OWNERSHIP_FIELDS), (
            path,
            names & FORBIDDEN_OWNERSHIP_FIELDS,
        )
        assert names.isdisjoint(FORBIDDEN_GEOMETRY_NAMES), (
            path,
            names & FORBIDDEN_GEOMETRY_NAMES,
        )
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
                        assert target.id not in FORBIDDEN_OWNERSHIP_FIELDS, (
                            path,
                            node.name,
                            target.id,
                        )


def test_world_engine_never_reads_migration_ledger() -> None:
    for path in (
        *(ROOT / "src" / "world").rglob("*.py"),
        ROOT / "src" / "simulation" / "engine.py",
        ROOT / "src" / "simulation" / "perception.py",
    ):
        text = path.read_text(encoding="utf-8")
        assert "MigrationDisplacementLedger" not in text, path
        assert "from agents.cognition.migration_displacement" not in text, path
        assert "migration_displacement_ledgers" not in text, path


def test_no_command_construction_or_executor_calls() -> None:
    for path in MIGRATION_PATHS:
        tree = _tree(path)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
            assert name not in COMMAND_CONSTRUCTORS, (path, name)
            assert name not in {"submit", "resolve", "admit", "execute"}, (path, name)


def test_bias_helper_returns_mapping_not_command() -> None:
    import inspect

    from agents.cognition.migration_displacement import (
        migration_displacement_action_biases,
    )

    hints = migration_displacement_action_biases.__annotations__
    return_hint = str(hints.get("return", ""))
    assert "Mapping" in return_hint or "dict" in return_hint.lower()
    source = inspect.getsource(migration_displacement_action_biases)
    for command in ("Move(", "Flee(", "Transport(", "AgentCommand", "ActionSubmission"):
        assert command not in source


def test_four_layer_leakage_guard() -> None:
    leaky = MigrationLayers(
        ObjectiveMovementLayer(movements=(object(),)),  # type: ignore[arg-type]
        SubjectiveCauseLayer(),
        AnalyticalWaveLayer(),
        IntegrationOutcomeLayer(),
    )
    try:
        assert_migration_layer_separation(leaky)
    except MigrationLayerLeakError as exc:
        assert "objective_movement" in str(exc)
    else:  # pragma: no cover - must fail
        raise AssertionError("expected MigrationLayerLeakError")
    layers_source = (
        ROOT / "src" / "analysis" / "migration_displacement_layers.py"
    ).read_text(encoding="utf-8")
    for name in (
        "ObjectiveMovementLayer",
        "SubjectiveCauseLayer",
        "AnalyticalWaveLayer",
        "IntegrationOutcomeLayer",
        "assert_migration_layer_separation",
    ):
        assert name in layers_source


def test_exactly_six_get_routes_require_subjective_debug() -> None:
    source = (ROOT / "src" / "api" / "routes" / "migration_displacement.py").read_text(
        encoding="utf-8"
    )
    assert source.count("@router.get(") == 6
    assert MIGRATION_DISPLACEMENT_ROUTE_COUNT == 6
    routes = [
        route for route in router.routes if getattr(route, "methods", None) is not None
    ]
    assert len(routes) == 6
    assert all(route.methods == {"GET"} for route in routes)
    for verb in ("@router.post", "@router.put", "@router.patch", "@router.delete"):
        assert verb not in source
    assert "SUBJECTIVE_DEBUG" in source
    assert "ApiCapability.SUBJECTIVE_DEBUG" in source
    assert "/v2" not in source


def test_no_new_flag_context_or_v57() -> None:
    assert len(V4_CONTEXTS) == 14
    assert len(V4_CAPABILITY_FLAGS) == 12
    assert len(V4_OWNED_CAPABILITY_FLAGS) == 7
    assert V4_OWNED_CAPABILITY_FLAGS == frozenset(
        {
            "organizations",
            "formal_rules",
            "legal_disputes",
            "diplomacy",
            "organized_conflict",
            "infrastructure_networks",
        "supply_chains",
        }
    )
    offenders = [
        str(path.relative_to(ROOT / "src"))
        for path in sorted((ROOT / "src").rglob("*.py"))
        if "__pycache__" not in path.parts
        and "runner-config-v57" in path.read_text(encoding="utf-8")
    ]
    assert offenders == []
    for path in MIGRATION_PATHS:
        assert "runner-config-v57" not in path.read_text(encoding="utf-8")


def test_pins_are_unchanged() -> None:
    assert METRIC_FAMILY_COUNT == 204
    specs = all_metric_specifications()
    assert len(specs) == 204
    assert tuple(spec.family_id.value for spec in specs[176:180]) == MIGRATION_FAMILIES
    assert len(COMMAND_RULE_MATRIX) == 43
    assert len(SEMANTIC_EVENT_TYPES) == 73
    assert EVENT_SCHEMA_REPLAY_V22 == 22
    assert "v20" in ACCEPTED_PERSISTENCE_CODEC_VERSIONS
    assert "v21" in ACCEPTED_PERSISTENCE_CODEC_VERSIONS
    assert "v22" not in ACCEPTED_PERSISTENCE_CODEC_VERSIONS
    assert ALEMBIC_HEAD_REVISION == "0017"
    assert sorted((ROOT / "alembic" / "versions").glob("0018_*.py")) == []
    assert MIGRATION_DISPLACEMENT_CURSOR_PURPOSES == (
        "summary",
        "waves",
        "wave",
        "routes",
        "causes",
        "outcomes",
    )
    assert len(MIGRATION_DISPLACEMENT_CURSOR_PURPOSES) == 6
