"""Executable authority and compatibility claims for V4-04 operations."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from analysis.specifications import METRIC_FAMILY_COUNT
from observer.capabilities import SUPPORTED_OBSERVER_PROTOCOLS
from observer.version import SEMANTIC_EVENT_TYPES
from simulation.compatibility import ALEMBIC_HEAD_REVISION
from simulation.migration_plan import next_revision
from simulation.organization_models import (
    ORGANIZATION_OPERATION_ACTS,
    ORGANIZATION_OPERATION_ANCHOR_KINDS,
    ORGANIZATION_OPERATION_DOMAINS,
    ORGANIZATION_SNAPSHOT_SCHEMA_VERSION,
    ORGANIZATION_SNAPSHOT_SCHEMA_VERSION_V1,
    ORGANIZATION_SNAPSHOT_SCHEMA_VERSION_V2,
    SUPPORTED_ORGANIZATION_SNAPSHOT_SCHEMAS,
)
from simulation.persistence import (
    ACCEPTED_EVENT_SCHEMA_VERSIONS,
    ACCEPTED_PERSISTENCE_CODEC_VERSIONS,
)
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V56,
    SUPPORTED_RUNNER_SCHEMA_VERSIONS,
    V4CapabilityFlags,
)
from simulation.v4_architecture import (
    V4_CAPABILITY_FLAGS,
    V4_CONTEXTS,
    V4ContextId,
    validate_v4_contexts,
)
from simulation.versioning import V4_WRITE_PAIR_RESERVATIONS
from world._rules import COMMAND_RULE_MATRIX
from world.events import EVENT_SCHEMA_REPLAY_V22

pytestmark = pytest.mark.architecture

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"

COGNITION_MODULES = tuple(
    sorted((SRC / "agents" / "cognition").glob("organization_operation*.py"))
)
ANALYSIS_MODULES = tuple(
    sorted((SRC / "analysis").glob("organization_operation*.py"))
)
SIMULATION_MODULES = tuple(sorted((SRC / "simulation").glob("organization_*.py")))
PERSISTENCE_MODULES = (SRC / "persistence" / "organization_filesystem.py",)
API_MODULES = (
    SRC / "api" / "routes" / "organization.py",
    SRC / "api" / "organization_schemas.py",
    SRC / "api" / "organization_cursor.py",
)
BRIDGE_MODULES = (
    SRC / "experiments" / "organization_harvest.py",
    SRC / "experiments" / "organization_publication.py",
)
RUNNER_MODULES = (SRC / "research_runner" / "organization_composition.py",)

MAGIC_ACTOR_TOKENS = frozenset(
    {
        "OrganizationActor",
        "OrganizationTreasury",
        "OrganizationRegistry",
        "GlobalOrganizationRegistry",
        "ResourcePool",
        "CentralBank",
        "WorldGovernment",
        "Ministry",
    }
)
FORBIDDEN_AUTHORITY_SYMBOLS = frozenset(
    {
        "WorldState",
        "WorldEngine",
        "ActionSubmission",
        "TickToken",
        "EventStore",
        "PhysicalRules",
        "AgentCommand",
    }
)
FORBIDDEN_METHOD_NAMES = frozenset(
    {
        "teleport",
        "teleport_resources",
        "execute",
        "execute_action",
        "transfer_resources",
        "move_resources",
    }
)
OBJECTIVE_MODELS = {
    SRC / "world" / "models.py": {"Item", "Resource"},
    SRC / "world" / "production.py": {"Structure"},
    SRC / "world" / "artifacts.py": {"InformationArtifact"},
    SRC / "world" / "repositories.py": {"KnowledgeRepository"},
}


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


def _import_roots(path: Path) -> set[str]:
    roots: set[str] = set()
    for node in ast.walk(_tree(path)):
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            roots.add(node.module.split(".", 1)[0])
        elif isinstance(node, ast.Import):
            roots.update(alias.name.split(".", 1)[0] for alias in node.names)
    return roots


def _class_names(path: Path) -> set[str]:
    return {
        node.name for node in ast.walk(_tree(path)) if isinstance(node, ast.ClassDef)
    }


def _class_fields(path: Path, names: set[str]) -> set[str]:
    fields: set[str] = set()
    for node in ast.walk(_tree(path)):
        if not isinstance(node, ast.ClassDef) or node.name not in names:
            continue
        for statement in node.body:
            if isinstance(statement, ast.AnnAssign) and isinstance(
                statement.target, ast.Name
            ):
                fields.add(statement.target.id)
    return fields


@pytest.mark.parametrize("path", ANALYSIS_MODULES)
def test_analysis_operation_modules_are_detached(path: Path) -> None:
    assert _import_roots(path) & {
        "agents",
        "experiments",
        "api",
        "persistence",
        "infrastructure",
        "observer",
    } == set()


@pytest.mark.parametrize("path", SIMULATION_MODULES)
def test_simulation_operation_modules_are_detached(path: Path) -> None:
    forbidden = {
        "analysis",
        "api",
        "persistence",
        "infrastructure",
        "experiments",
        "observer",
    }
    # The explicit simulation bridge may re-export cognition id helpers.
    if path.name != "organization_agency_ids.py":
        forbidden.add("agents")
    assert _import_roots(path) & forbidden == set()


@pytest.mark.parametrize("path", PERSISTENCE_MODULES + API_MODULES)
def test_outer_surfaces_do_not_import_analysis(path: Path) -> None:
    roots = _import_roots(path)
    assert "analysis" not in roots
    assert "agents" not in roots


@pytest.mark.parametrize("path", BRIDGE_MODULES + RUNNER_MODULES)
def test_bridge_and_runner_do_not_import_api(path: Path) -> None:
    assert "api" not in _import_roots(path)


@pytest.mark.parametrize("path", COGNITION_MODULES + ANALYSIS_MODULES)
def test_no_magic_actor_or_authority_symbol(path: Path) -> None:
    referenced: set[str] = set()
    for node in ast.walk(_tree(path)):
        if isinstance(node, ast.Name):
            referenced.add(node.id)
        elif isinstance(node, ast.Attribute):
            referenced.add(node.attr)
    assert not (_class_names(path) & MAGIC_ACTOR_TOKENS)
    assert not (referenced & FORBIDDEN_AUTHORITY_SYMBOLS)
    for name in _class_names(path):
        assert not name.endswith(("Command", "Event")), name


@pytest.mark.parametrize("path", SIMULATION_MODULES + PERSISTENCE_MODULES)
def test_simulation_store_has_no_teleport_or_executor(path: Path) -> None:
    names = {
        node.name
        for node in ast.walk(_tree(path))
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert not (names & FORBIDDEN_METHOD_NAMES)


def test_update_reads_only_owner_inputs() -> None:
    import inspect

    from agents.cognition import apply_organization_operation_update

    parameters = set(
        inspect.signature(apply_organization_operation_update).parameters
    )
    for forbidden in (
        "peer",
        "other_owner",
        "all_ledgers",
        "runtimes",
        "world_state",
        "event_store",
    ):
        assert not any(forbidden in name for name in parameters)


def test_objective_models_have_no_organization_owner_field() -> None:
    for path, names in OBJECTIVE_MODELS.items():
        fields = _class_fields(path, names)
        for field in fields:
            lowered = field.lower()
            assert "organization" not in lowered, (path.name, field)
            assert lowered not in {"owner_id", "ownership"}, (path.name, field)
        source = path.read_text(encoding="utf-8")
        assert "organization_id" not in source, path.name
        assert "organization_owner" not in source, path.name


def test_objective_custody_fields_remain_the_only_placement() -> None:
    models = (SRC / "world" / "models.py").read_text()
    artifacts = (SRC / "world" / "artifacts.py").read_text()
    production = (SRC / "world" / "production.py").read_text()
    repositories = (SRC / "world" / "repositories.py").read_text()
    assert "holder_id" in models
    assert "location_id" in models
    assert "custodian_repository_id" in artifacts
    assert "stored_quantity" in production
    assert "location_id" in repositories
    for path in sorted((SRC / "world").rglob("*.py")):
        assert "organization_operation" not in path.read_text(encoding="utf-8"), path


def test_snapshot_accepts_three_schemas() -> None:
    assert SUPPORTED_ORGANIZATION_SNAPSHOT_SCHEMAS == (
        ORGANIZATION_SNAPSHOT_SCHEMA_VERSION_V1,
        ORGANIZATION_SNAPSHOT_SCHEMA_VERSION_V2,
        ORGANIZATION_SNAPSHOT_SCHEMA_VERSION,
    )
    assert ORGANIZATION_SNAPSHOT_SCHEMA_VERSION == "organization-snapshot-v3"
    assert len(ORGANIZATION_OPERATION_DOMAINS) == 8
    assert len(ORGANIZATION_OPERATION_ACTS) == 10
    assert len(ORGANIZATION_OPERATION_ANCHOR_KINDS) == 9


def test_compatibility_pins_are_unchanged() -> None:
    assert EVENT_SCHEMA_REPLAY_V22 == 22
    assert max(ACCEPTED_EVENT_SCHEMA_VERSIONS) == 22
    assert "v20" in ACCEPTED_PERSISTENCE_CODEC_VERSIONS
    assert "v21" not in ACCEPTED_PERSISTENCE_CODEC_VERSIONS
    assert len(COMMAND_RULE_MATRIX) == 43
    assert len(SEMANTIC_EVENT_TYPES) == 73
    assert METRIC_FAMILY_COUNT == 148
    assert ALEMBIC_HEAD_REVISION == "0017"
    assert sorted((ROOT / "alembic" / "versions").glob("0018_*.py")) == []
    assert next_revision() == "0018"
    assert RUNNER_SCHEMA_VERSION_V56 in SUPPORTED_RUNNER_SCHEMA_VERSIONS
    assert "runner-config-v57" not in SUPPORTED_RUNNER_SCHEMA_VERSIONS


def test_v4_registry_and_reservations_are_unchanged() -> None:
    validate_v4_contexts()
    assert len(V4_CONTEXTS) == 14
    assert len(V4_CAPABILITY_FLAGS) == 12
    assert len(V4_WRITE_PAIR_RESERVATIONS) == 4
    assert V4ContextId.ORGANIZATIONS in {
        context.context_id for context in V4_CONTEXTS
    }
    assert V4CapabilityFlags(organizations=True).owned_enabled_names() == (
        "organizations",
    )


def test_observer_protocol_is_unchanged() -> None:
    assert SUPPORTED_OBSERVER_PROTOCOLS == ("observer-protocol-v1",)


def test_organization_routes_are_five_get_only_routes() -> None:
    tree = _tree(SRC / "api" / "routes" / "organization.py")
    routes = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and any(
            isinstance(decorator, ast.Call)
            and isinstance(decorator.func, ast.Attribute)
            and decorator.func.attr == "get"
            for decorator in node.decorator_list
        )
    ]
    assert len(routes) == 6
    methods = {
        node.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and node.attr in {"get", "post", "put", "patch", "delete"}
    }
    assert methods == {"get"}


def test_research_ui_client_is_read_only() -> None:
    client = (
        ROOT / "clients" / "research-ui" / "src" / "api" / "organizations.ts"
    ).read_text()
    for verb in ("POST", "PUT", "PATCH", "DELETE"):
        assert verb not in client


def test_codec_and_models_have_no_analysis_dependency() -> None:
    for path in (
        SRC / "simulation" / "organization_models.py",
        SRC / "simulation" / "organization_codec.py",
        SRC / "simulation" / "organization_ports.py",
        SRC / "simulation" / "organization_paging.py",
    ):
        assert "analysis" not in _import_roots(path)
