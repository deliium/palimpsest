"""V4-06 authority, boundary, and compatibility invariants."""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from agents.cognition import FormalRuleConstraintKind
from analysis.specifications import METRIC_FAMILY_COUNT
from api.routes.formal_rule import router as formal_rule_router
from api.routes.organization import router as organization_router
from observer import SUPPORTED_OBSERVER_PROTOCOLS
from observer.version import SEMANTIC_EVENT_TYPES
from simulation import (
    ALEMBIC_HEAD_REVISION,
    OBSERVER_LAYOUT_SCHEMA_VERSION,
    OBSERVER_PROTOCOL_VERSION,
    V4_ANALYSIS_ONLY_CONTEXTS,
    V4_CAPABILITY_FLAGS,
    V4_CONTEXT_BY_ID,
    V4_WRITE_PAIR_RESERVATIONS,
    V4CapabilityFlags,
    V4ContextId,
    V4ContextSpec,
    validate_v4_contexts,
)
from simulation.formal_rule_models import (
    FORMAL_RULE_SNAPSHOT_POLICY_VERSION,
    FORMAL_RULE_SNAPSHOT_SCHEMA,
)
from simulation.formal_rule_ports import FORMAL_RULE_CURSOR_PURPOSES
from simulation.persistence import ACCEPTED_EVENT_SCHEMA_VERSIONS
from simulation.runner_models import SUPPORTED_RUNNER_SCHEMA_VERSIONS
from world._rules import COMMAND_RULE_MATRIX
from world.events import EVENT_SCHEMA_REPLAY_V22

pytestmark = pytest.mark.architecture

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"

FORMAL_RULE_MODULES = (
    *SRC.glob("agents/cognition/formal_rule*.py"),
    *SRC.glob("analysis/formal_rule*.py"),
    *SRC.glob("simulation/formal_rule*.py"),
    *SRC.glob("experiments/formal_rule*.py"),
    *SRC.glob("persistence/formal_rule*.py"),
    SRC / "api" / "routes" / "formal_rule.py",
    *SRC.glob("api/formal_rule_*.py"),
    SRC / "research_runner" / "formal_rule_composition.py",
)

FORBIDDEN_CLASSES = (
    "Law",
    "Statute",
    "LegalCode",
    "Court",
    "Judge",
    "Police",
    "Government",
    "Jurisdiction",
    "RuleEngine",
    "SanctionEngine",
    "PolicyEngine",
    "GlobalRuleRegistry",
    "WorldRule",
)


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


def _imports(path: Path) -> set[str]:
    tree = _tree(path)
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            roots.add(node.module)
            roots.add(node.module.split(".", 1)[0])
        elif isinstance(node, ast.Import):
            roots.update(alias.name for alias in node.names)
    return roots


def test_formal_rule_modules_import_no_world_engine_state_or_commands() -> None:
    forbidden = {
        "world._state",
        "world.events",
        "simulation.engine",
        "simulation.actions",
    }
    forbidden_names = {"WorldState", "WorldEvent", "PhysicalRules", "AgentCommand"}
    for path in FORMAL_RULE_MODULES:
        imports = _imports(path)
        assert not imports & forbidden, path
        names = {
            node.id for node in ast.walk(_tree(path)) if isinstance(node, ast.Name)
        }
        assert not names & forbidden_names, path


def test_no_world_law_magic_actor_classes_exist() -> None:
    offenders: list[tuple[Path, str]] = []
    for path in sorted(SRC.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        for name in FORBIDDEN_CLASSES:
            if re.search(rf"class\s+{name}\b", text):
                offenders.append((path, name))
    assert offenders == []


def test_world_engine_perception_and_admission_do_not_reference_formal_rules() -> None:
    for path in (
        SRC / "world" / "_rules.py",
        SRC / "world" / "_operations.py",
        SRC / "world" / "_perception.py",
        SRC / "simulation" / "engine.py",
        SRC / "simulation" / "actions.py",
    ):
        assert "formal_rule" not in path.read_text(encoding="utf-8").lower(), path


def test_no_command_construction_or_dispatch() -> None:
    for path in FORMAL_RULE_MODULES:
        text = path.read_text(encoding="utf-8")
        for token in (
            "Give(",
            "Attack(",
            "Inscribe(",
            "ActionSubmission(",
            "AgentCommand(",
        ):
            assert token not in text, (path, token)


def test_no_objective_law_or_jurisdiction_fields() -> None:
    forbidden = {
        "jurisdiction",
        "law_id",
        "enforced_by_world",
        "objective_rule",
        "binding",
    }
    for path in FORMAL_RULE_MODULES:
        tree = _tree(path)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                names = {
                    item.target.id
                    for item in node.body
                    if isinstance(item, ast.AnnAssign)
                    and isinstance(item.target, ast.Name)
                }
                assert not names & forbidden, (path, node.name)


def test_six_get_only_formal_rule_routes() -> None:
    routes = [
        route
        for route in formal_rule_router.routes
        if getattr(route, "methods", None) is not None
    ]
    assert len(routes) == 6
    assert all(getattr(route, "methods", None) == {"GET"} for route in routes)


def test_six_organization_routes_are_unchanged() -> None:
    routes = [
        route
        for route in organization_router.routes
        if getattr(route, "methods", None) is not None
    ]
    assert len(routes) == 6
    assert all(getattr(route, "methods", None) == {"GET"} for route in routes)


def test_six_formal_rule_cursor_purposes() -> None:
    assert FORMAL_RULE_CURSOR_PURPOSES == (
        "summary",
        "candidates",
        "candidate",
        "rules",
        "versions",
        "lineage",
    )


def test_snapshot_schema_and_store_schema_are_v1() -> None:
    assert FORMAL_RULE_SNAPSHOT_SCHEMA == "formal-rule-snapshot-v1"
    assert FORMAL_RULE_SNAPSHOT_POLICY_VERSION == "formal-rule-analysis.v1"
    store = (SRC / "persistence" / "formal_rule_filesystem.py").read_text(
        encoding="utf-8"
    )
    assert "formal-rule-store-v1" in store


def test_compatibility_pins_are_exact() -> None:
    assert METRIC_FAMILY_COUNT == 157
    assert len(COMMAND_RULE_MATRIX) == 43
    assert EVENT_SCHEMA_REPLAY_V22 == 22
    assert ALEMBIC_HEAD_REVISION == "0017"
    assert OBSERVER_PROTOCOL_VERSION == "observer-protocol-v1"
    assert OBSERVER_LAYOUT_SCHEMA_VERSION == "observer-layout-v1"
    assert SUPPORTED_OBSERVER_PROTOCOLS == ("observer-protocol-v1",)
    assert "runner-config-v57" not in SUPPORTED_RUNNER_SCHEMA_VERSIONS
    assert "runner-config-v56" in SUPPORTED_RUNNER_SCHEMA_VERSIONS


def test_v4_registry_has_fourteen_contexts_twelve_flags_two_owned() -> None:
    validate_v4_contexts()
    assert len(V4_CONTEXT_BY_ID) == 14
    assert len(V4_CAPABILITY_FLAGS) == 12
    assert V4_ANALYSIS_ONLY_CONTEXTS == frozenset(
        {V4ContextId.SOCIETAL_RESILIENCE, V4ContextId.MACRO_SOCIETY_IDENTITY}
    )
    assert V4CapabilityFlags(organizations=True).owned_enabled_names() == (
        "organizations",
    )
    assert V4CapabilityFlags(formal_rules=True).owned_enabled_names() == (
        "formal_rules",
    )
    assert V4CapabilityFlags(legal_disputes=True).owned_enabled_names() == (
        "legal_disputes",
    )


def test_reserved_write_pairs_are_unchanged() -> None:
    assert len(V4_WRITE_PAIR_RESERVATIONS) == 4
    assert "formal_rules" not in {
        item.context_id.value for item in V4_WRITE_PAIR_RESERVATIONS
    }


def test_formal_rules_reuses_existing_events_and_has_no_reservation() -> None:
    spec = V4_CONTEXT_BY_ID[V4ContextId.FORMAL_RULES]
    assert isinstance(spec, V4ContextSpec)
    assert spec.uses_existing_events is True
    assert spec.prerequisite_contexts == ()
    assert spec.authority.value == "owner_scoped"


def test_no_physical_constraint_member_exists() -> None:
    assert tuple(kind.value for kind in FormalRuleConstraintKind) == (
        "prohibition",
        "obligation",
        "permission",
    )


_MUTABLE_CONSTRUCTORS = frozenset(
    {
        "dict",
        "list",
        "set",
        "defaultdict",
        "Counter",
        "WeakKeyDictionary",
        "WeakValueDictionary",
    }
)


_MUTATING_METHODS = frozenset(
    {
        "add",
        "append",
        "clear",
        "discard",
        "extend",
        "pop",
        "popitem",
        "setdefault",
        "update",
    }
)


def test_no_global_rule_registry_or_cross_owner_store() -> None:
    for path in FORMAL_RULE_MODULES:
        tree = _tree(path)
        containers: set[str] = set()
        for node in tree.body:
            if isinstance(node, ast.AnnAssign):
                value = node.value
                targets: list[ast.expr] = [node.target]
            elif isinstance(node, ast.Assign):
                value = node.value
                targets = list(node.targets)
            else:
                continue
            names = {target.id for target in targets if isinstance(target, ast.Name)}
            if "__all__" in names:
                continue
            mutable = isinstance(value, (ast.Dict, ast.List, ast.Set)) or (
                isinstance(value, ast.Call)
                and isinstance(value.func, ast.Name)
                and value.func.id in _MUTABLE_CONSTRUCTORS
            )
            if mutable:
                containers.update(names - {"__all__"})

        for child in ast.walk(tree):
            if isinstance(child, ast.Subscript):
                base = child.value
                if isinstance(base, ast.Name) and base.id in containers:
                    if isinstance(child.ctx, (ast.Store, ast.Del)):
                        raise AssertionError((path, base.id))
            if (
                isinstance(child, ast.Call)
                and isinstance(child.func, ast.Attribute)
                and child.func.attr in _MUTATING_METHODS
                and isinstance(child.func.value, ast.Name)
                and child.func.value.id in containers
            ):
                raise AssertionError((path, child.func.value.id))
            if isinstance(child, ast.ClassDef):
                assert not child.name.endswith("Registry"), (path, child.name)


def test_settings_never_imports_or_reads_a_formal_rule_ledger() -> None:
    text = (SRC / "infrastructure" / "settings.py").read_text(encoding="utf-8")
    assert "FormalRuleLedger" not in text
    assert "formal_rule_ledger" not in text
    assert "agents.cognition.formal_rules" not in text
    assert "formal_rule_root" in text
    assert "formal_rule_cursor_key" in text


def test_app_wiring_imports_only_api_and_persistence() -> None:
    forbidden_roots = {"analysis", "experiments", "research_runner"}
    for name in ("app.py", "dependencies.py"):
        imports = _imports(SRC / "api" / name)
        assert not imports & forbidden_roots, (name, sorted(imports & forbidden_roots))
    app_source = (SRC / "api" / "app.py").read_text(encoding="utf-8")
    assert "persistence.formal_rule_filesystem" in app_source


def test_no_new_event_command_observer_semantic_or_migration() -> None:
    assert EVENT_SCHEMA_REPLAY_V22 == 22
    assert max(ACCEPTED_EVENT_SCHEMA_VERSIONS) == 22
    assert len(SEMANTIC_EVENT_TYPES) == 73
    assert len(COMMAND_RULE_MATRIX) == 43
    assert ALEMBIC_HEAD_REVISION == "0017"
    assert not sorted((ROOT / "alembic" / "versions").glob("0018_*.py"))
    spec = V4_CONTEXT_BY_ID[V4ContextId.FORMAL_RULES]
    assert spec.uses_existing_events is True
    assert "formal_rules" not in {
        item.context_id.value for item in V4_WRITE_PAIR_RESERVATIONS
    }
