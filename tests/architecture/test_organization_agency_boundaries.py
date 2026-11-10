"""V4-05 authority boundaries and exact compatibility pins."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from agents.cognition.collective_decisions import COLLECTIVE_DECISION_POLICY_VERSION
from agents.cognition.organization_concepts import (
    ORGANIZATION_CONCEPT_ID_PREFIX,
    ORGANIZATION_CONCEPT_POLICY_VERSION,
)
from agents.cognition.organization_operations import (
    ORGANIZATION_OPERATION_POLICY_VERSION,
)
from analysis.specifications import METRIC_FAMILY_COUNT, all_metric_specifications
from api.routes.organization import router
from observer.capabilities import (
    RESERVED_OBSERVER_CAPABILITIES,
    SUPPORTED_OBSERVER_PROTOCOLS,
    ObserverCapability,
)
from observer.version import SEMANTIC_EVENT_TYPES
from simulation.compatibility import ALEMBIC_HEAD_REVISION
from simulation.migration_plan import next_revision
from simulation.organization_models import SUPPORTED_ORGANIZATION_SNAPSHOT_SCHEMAS
from simulation.organization_ports import ORGANIZATION_CURSOR_PURPOSES
from simulation.persistence import (
    ACCEPTED_EVENT_SCHEMA_VERSIONS,
    ACCEPTED_PERSISTENCE_CODEC_VERSIONS,
)
from simulation.runner_models import SUPPORTED_RUNNER_SCHEMA_VERSIONS
from simulation.v4_architecture import (
    V4_CAPABILITY_FLAGS,
    V4_CONTEXT_BY_ID,
    V4ContextId,
)
from simulation.versioning import V4_WRITE_PAIR_RESERVATIONS
from world._rules import COMMAND_RULE_MATRIX
from world.events import EVENT_SCHEMA_REPLAY_V22

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
AGENCY_MODULES = (
    ROOT / "src" / "agents" / "cognition" / "organization_agency.py",
    ROOT / "src" / "agents" / "cognition" / "organization_agency_actions.py",
    ROOT / "src" / "agents" / "cognition" / "organization_agency_communication.py",
    ROOT / "src" / "analysis" / "organization_agency.py",
)


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


def test_no_agency_module_constructs_a_command() -> None:
    for path in AGENCY_MODULES:
        tree = _tree(path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                name = getattr(func, "id", None) or getattr(func, "attr", None)
                assert name not in {"AgentCommand", "ActionSubmission"}, (
                    path,
                    name,
                )


def test_no_agency_module_imports_llm_or_prompts() -> None:
    for path in AGENCY_MODULES:
        tree = _tree(path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("llm"), (path, alias.name)
            elif isinstance(node, ast.ImportFrom) and node.module:
                assert not node.module.startswith("llm"), (path, node.module)
                assert not node.module.startswith("world._"), (path, node.module)
                assert not node.module.startswith("simulation.engine"), (
                    path,
                    node.module,
                )
                assert not node.module.startswith("persistence"), (path, node.module)
                assert not node.module.startswith("api"), (path, node.module)


def test_analysis_agency_module_imports_no_cognition() -> None:
    tree = _tree(ROOT / "src" / "analysis" / "organization_agency.py")
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            assert not node.module.startswith("agents"), node.module
        elif isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith("agents"), alias.name


def test_compatibility_pins_are_exact() -> None:
    assert METRIC_FAMILY_COUNT == 198
    families = all_metric_specifications()
    assert len(families) == 198
    assert families[146].family_id.value == "organization_collective_agency"
    assert families[147].family_id.value == "organization_collective_implementation"
    assert "runner-config-v57" not in SUPPORTED_RUNNER_SCHEMA_VERSIONS
    assert EVENT_SCHEMA_REPLAY_V22 == 22
    assert len(COMMAND_RULE_MATRIX) == 43
    assert len(SEMANTIC_EVENT_TYPES) == 73
    assert SUPPORTED_ORGANIZATION_SNAPSHOT_SCHEMAS == (
        "organization-snapshot-v1",
        "organization-snapshot-v2",
        "organization-snapshot-v3",
    )
    assert ORGANIZATION_CURSOR_PURPOSES[-1] == "organization_collective_agency"
    assert len(ORGANIZATION_CURSOR_PURPOSES) == 6


def test_registry_and_organizations_context_are_unchanged() -> None:
    assert len(V4ContextId) == 14
    assert len(V4_CONTEXT_BY_ID) == 14
    assert V4ContextId.ORGANIZATIONS in V4_CONTEXT_BY_ID
    spec = V4_CONTEXT_BY_ID[V4ContextId.ORGANIZATIONS]
    assert spec.authority.value == "owner_scoped"


def test_six_get_only_organization_routes() -> None:
    routes = [
        route
        for route in router.routes
        if getattr(route, "path", "").startswith("/v1/simulations")
    ]
    assert len(routes) == 6
    assert all("GET" in getattr(route, "methods", set()) for route in routes)


def test_alembic_head_has_no_v4_05_migration() -> None:
    versions = sorted(
        path.name for path in (ROOT / "alembic" / "versions").glob("0018_*.py")
    )
    assert versions == []


FORBIDDEN_CLASS_NAMES = {
    "OrganizationActor",
    "OrganizationAgent",
    "OrganizationLLM",
    "OrganizationRegistry",
    "GlobalRegistry",
    "Government",
    "Treasury",
    "Roster",
}


def test_no_magic_actor_or_registry_classes_exist() -> None:
    for path in sorted((ROOT / "src").rglob("*.py")):
        tree = _tree(path)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                assert node.name not in FORBIDDEN_CLASS_NAMES, (path, node.name)


def test_world_has_no_objective_organization_ownership_fields() -> None:
    forbidden = {"ownership", "organization_id", "collective_agency", "owner_id"}
    for path in sorted((ROOT / "src" / "world").rglob("*.py")):
        tree = _tree(path)
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            for statement in node.body:
                if isinstance(statement, ast.AnnAssign) and isinstance(
                    statement.target, ast.Name
                ):
                    assert statement.target.id not in forbidden, (
                        path,
                        node.name,
                        statement.target.id,
                    )


def test_metric_assembly_has_no_cognition_import() -> None:
    for path in (
        ROOT / "src" / "analysis" / "metric_service.py",
        ROOT / "src" / "experiments" / "collectors.py",
    ):
        tree = _tree(path)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert not node.module.startswith("agents"), (path, node.module)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("agents"), (path, alias.name)


def test_existing_organization_contracts_are_unchanged() -> None:
    assert COLLECTIVE_DECISION_POLICY_VERSION == "collective-decisions.v1"
    assert ORGANIZATION_CONCEPT_POLICY_VERSION == "organization-concepts.v1"
    assert ORGANIZATION_OPERATION_POLICY_VERSION == "organization-operations.v1"
    assert ORGANIZATION_CONCEPT_ID_PREFIX == "orgc-"


def test_v4_reservations_observer_and_migration_are_unchanged() -> None:
    assert len(V4_CAPABILITY_FLAGS) == 12
    assert len(V4_WRITE_PAIR_RESERVATIONS) == 4
    assert [item.codec_version for item in V4_WRITE_PAIR_RESERVATIONS] == [
        "v21",
        "v22",
        "v23",
        "v24",
    ]
    assert SUPPORTED_OBSERVER_PROTOCOLS == ("observer-protocol-v1",)
    assert ObserverCapability.ORGANIZATION_ROWS in RESERVED_OBSERVER_CAPABILITIES
    assert "v20" in ACCEPTED_PERSISTENCE_CODEC_VERSIONS
    assert "v21" in ACCEPTED_PERSISTENCE_CODEC_VERSIONS
    assert "v22" not in ACCEPTED_PERSISTENCE_CODEC_VERSIONS
    assert max(ACCEPTED_EVENT_SCHEMA_VERSIONS) == 27
    assert ALEMBIC_HEAD_REVISION == "0017"
    assert next_revision() == "0018"


def test_prepare_parallel_is_still_disabled() -> None:
    text = (ROOT / "src" / "simulation" / "runner.py").read_text(encoding="utf-8")
    assert "prepare_parallel enabled=%s" in text
    assert "False,\n            len(self._runtimes)" in text
