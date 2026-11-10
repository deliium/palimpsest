"""Executable authority, compatibility, and read-only claims for V4-03."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any, cast

import pytest

import observer
from analysis.specifications import METRIC_FAMILY_COUNT
from experiments import BENCHMARK_SCENARIO_COUNT, V3_BENCHMARK_SCENARIO_COUNT
from observer.capabilities import SUPPORTED_OBSERVER_PROTOCOLS
from observer.version import SEMANTIC_EVENT_TYPES
from simulation.compatibility import ALEMBIC_HEAD_REVISION
from simulation.migration_plan import next_revision
from simulation.persistence import (
    ACCEPTED_EVENT_SCHEMA_VERSIONS,
    ACCEPTED_PERSISTENCE_CODEC_VERSIONS,
)
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION,
    RUNNER_SCHEMA_VERSION_V55,
    RUNNER_SCHEMA_VERSION_V56,
    SUPPORTED_RUNNER_SCHEMA_VERSIONS,
    V4CapabilityFlags,
)
from simulation.v4_architecture import (
    V4_ANALYSIS_ONLY_CONTEXTS,
    V4_CAPABILITY_FLAGS,
    V4_CONTEXTS,
    V4ContextId,
    validate_v4_contexts,
)
from simulation.versioning import (
    V4_EVENT_REUSING_CONTEXTS,
    V4_WRITE_PAIR_RESERVATIONS,
)
from world._rules import COMMAND_RULE_MATRIX
from world.events import EVENT_SCHEMA_REPLAY_V22

pytestmark = pytest.mark.architecture

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"

ANALYSIS_MODULES = tuple(sorted((SRC / "analysis").glob("organization*.py")))
SIMULATION_MODULES = tuple(sorted((SRC / "simulation").glob("organization_*.py")))
COGNITION_MODULES = tuple(
    sorted((SRC / "agents" / "cognition").glob("organization_*.py"))
)
PERSISTENCE_MODULES = (SRC / "persistence" / "organization_filesystem.py",)
API_MODULES = (
    SRC / "api" / "routes" / "organization.py",
    SRC / "api" / "organization_schemas.py",
    SRC / "api" / "organization_cursor.py",
)
RUNNER_MODULES = (SRC / "research_runner" / "organization_composition.py",)
BRIDGE_MODULES = (
    SRC / "experiments" / "organization_harvest.py",
    SRC / "experiments" / "organization_publication.py",
)

MAGIC_ACTOR_TOKENS = (
    "OrganizationActor",
    "GlobalOrganizationRegistry",
    "OrganizationRegistry",
    "WorldGovernment",
    "CentralBank",
    "Treasury",
    "Ministry",
    "InstitutionActor",
    "CivilizationActor",
    "Country",
    "Nation",
    "Empire",
    "Polity",
    "Tribe",
)

FORBIDDEN_WORLD_SYMBOLS = (
    "WorldState",
    "WorldEngine",
    "ActionSubmission",
    "TickToken",
    "EventStore",
    "PhysicalRules",
    "AgentCommand",
)


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


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


@pytest.mark.parametrize("path", ANALYSIS_MODULES)
def test_analysis_modules_are_read_only(path: Path) -> None:
    roots = _import_roots(path)
    assert (
        roots
        & {
            "agents",
            "experiments",
            "api",
            "persistence",
            "infrastructure",
            "observer",
        }
        == set()
    )


@pytest.mark.parametrize("path", SIMULATION_MODULES)
def test_simulation_modules_are_independent(path: Path) -> None:
    roots = _import_roots(path)
    assert (
        roots
        & {
            "analysis",
            "experiments",
            "api",
            "persistence",
            "infrastructure",
            "observer",
        }
        == set()
    )


@pytest.mark.parametrize("path", PERSISTENCE_MODULES)
def test_persistence_store_is_filesystem_only(path: Path) -> None:
    roots = _import_roots(path)
    assert roots & {"analysis", "experiments", "api", "observer", "agents"} == set()
    assert roots & {"sqlalchemy", "alembic", "asyncpg"} == set()


@pytest.mark.parametrize("path", API_MODULES)
def test_api_modules_are_read_only_presentation(path: Path) -> None:
    roots = _import_roots(path)
    assert roots & {"analysis", "experiments", "agents"} == set()


@pytest.mark.parametrize("path", RUNNER_MODULES)
def test_runner_modules_do_not_import_api(path: Path) -> None:
    assert "api" not in _import_roots(path)


@pytest.mark.parametrize("path", BRIDGE_MODULES)
def test_bridge_does_not_import_outer_layers(path: Path) -> None:
    roots = _import_roots(path)
    assert roots & {"api", "persistence", "observer", "infrastructure"} == set()


def test_no_magic_actor_or_registry_class_exists() -> None:
    hits: list[str] = []
    for path in SRC.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        hits.extend(
            f"{path.relative_to(SRC)}:{name}"
            for name in _class_names(path) & set(MAGIC_ACTOR_TOKENS)
        )
    assert hits == []


@pytest.mark.parametrize("path", COGNITION_MODULES + ANALYSIS_MODULES)
def test_no_world_authority_or_command_symbol(path: Path) -> None:
    referenced: set[str] = set()
    for node in ast.walk(_tree(path)):
        if isinstance(node, ast.Name):
            referenced.add(node.id)
        elif isinstance(node, ast.Attribute):
            referenced.add(node.attr)
    for symbol in FORBIDDEN_WORLD_SYMBOLS:
        assert symbol not in referenced, (path.name, symbol)
    for name in _class_names(path):
        assert not name.endswith(("Command", "Event")), name


def test_organization_update_reads_only_owner_inputs() -> None:
    import inspect

    from agents.cognition import apply_organization_concept_update

    parameters = set(inspect.signature(apply_organization_concept_update).parameters)
    for forbidden in ("peer", "other_owner", "all_ledgers", "runtimes", "world_state"):
        assert not any(forbidden in name for name in parameters)


def test_objective_layers_do_not_read_organization_ledgers() -> None:
    for module in sorted((SRC / "world").rglob("*.py")):
        assert "organization_concept" not in _source(module), module
    perception = _source(SRC / "simulation" / "perception.py")
    assert "organization_concepts" in perception
    assert "organization_concept_ledger" not in perception


def test_v4_flag_literal_stays_inside_the_allowlist() -> None:
    from tests.architecture.test_v4_architecture_invariants import (
        ALLOWED_FLAG_REFERENCES,
    )

    hits = {
        str(path.relative_to(SRC))
        for path in SRC.rglob("*.py")
        if "__pycache__" not in path.parts and "v4_capability_flags" in _source(path)
    }
    assert hits <= ALLOWED_FLAG_REFERENCES, hits - ALLOWED_FLAG_REFERENCES


def test_compatibility_pins_are_unchanged() -> None:
    assert EVENT_SCHEMA_REPLAY_V22 == 22
    assert max(ACCEPTED_EVENT_SCHEMA_VERSIONS) == 27
    assert "v20" in ACCEPTED_PERSISTENCE_CODEC_VERSIONS
    assert "v21" in ACCEPTED_PERSISTENCE_CODEC_VERSIONS
    assert "v22" not in ACCEPTED_PERSISTENCE_CODEC_VERSIONS
    assert len(COMMAND_RULE_MATRIX) == 43
    assert len(SEMANTIC_EVENT_TYPES) == 73
    assert METRIC_FAMILY_COUNT == 198
    assert BENCHMARK_SCENARIO_COUNT == 16
    assert V3_BENCHMARK_SCENARIO_COUNT == 30
    assert ALEMBIC_HEAD_REVISION == "0017"
    assert sorted((ROOT / "alembic" / "versions").glob("0018_*.py")) == []
    assert next_revision() == "0018"
    assert RUNNER_SCHEMA_VERSION == "runner-config-v4"
    assert RUNNER_SCHEMA_VERSION_V55 == "runner-config-v55"
    assert RUNNER_SCHEMA_VERSION_V56 in SUPPORTED_RUNNER_SCHEMA_VERSIONS
    assert "runner-config-v57" not in SUPPORTED_RUNNER_SCHEMA_VERSIONS


def test_v4_registry_keeps_fourteen_contexts_and_ownership_split() -> None:
    validate_v4_contexts()
    assert len(V4_CONTEXTS) == 14
    assert len(V4_CAPABILITY_FLAGS) == 12
    assert V4_ANALYSIS_ONLY_CONTEXTS == frozenset(
        {V4ContextId.SOCIETAL_RESILIENCE, V4ContextId.MACRO_SOCIETY_IDENTITY}
    )
    assert V4ContextId.ORGANIZATIONS in V4_EVENT_REUSING_CONTEXTS
    assert len(V4_WRITE_PAIR_RESERVATIONS) == 4
    assert "organizations" not in {
        reservation.context_id.value for reservation in V4_WRITE_PAIR_RESERVATIONS
    }
    assert V4CapabilityFlags(organizations=True).owned_enabled_names() == (
        "organizations",
    )
    assert V4CapabilityFlags(formal_rules=True).owned_enabled_names() == (
        "formal_rules",
    )
    for name in V4_CAPABILITY_FLAGS:
        if name in {
            "organizations",
            "formal_rules",
            "legal_disputes",
            "diplomacy",
            "organized_conflict",
            "infrastructure_networks",
        }:
            continue
        flags = V4CapabilityFlags(**{name: True})
        assert flags.owned_enabled_names() == ()
        assert flags.unimplemented_enabled_names() == (name,)


def test_observer_protocol_and_reserved_rows_are_unchanged() -> None:
    from observer.capabilities import observer_capability_payload

    assert SUPPORTED_OBSERVER_PROTOCOLS == ("observer-protocol-v1",)
    payload = observer_capability_payload()
    capabilities = cast(dict[str, Any], payload)
    assert "organization_rows" not in capabilities["capabilities"]
    assert "organization_rows" in capabilities["reserved_capabilities"]
    assert len(cast(list[str], capabilities["capabilities"])) == 4
    assert len(cast(list[str], capabilities["reserved_capabilities"])) == 6
    assert observer.OBSERVER_PROTOCOL_VERSION == "observer-protocol-v1"


def test_organization_routes_are_get_only() -> None:
    tree = _tree(SRC / "api" / "routes" / "organization.py")
    methods = {
        node.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and node.attr in {"get", "post", "put", "patch", "delete"}
    }
    assert methods == {"get"}


def test_research_ui_organization_client_has_no_write_calls() -> None:
    client = (
        ROOT / "clients" / "research-ui" / "src" / "api" / "organizations.ts"
    ).read_text()
    for verb in ("POST", "PUT", "PATCH", "DELETE"):
        assert verb not in client


def test_snapshot_codec_has_no_analysis_dependency() -> None:
    for path in (
        SRC / "simulation" / "organization_models.py",
        SRC / "simulation" / "organization_codec.py",
    ):
        assert "analysis" not in _import_roots(path)
    from simulation.organization_codec import encode_organization_snapshot
    from tests.unit.organization_artifact_helpers import example_snapshot

    assert "orgc-" not in encode_organization_snapshot(example_snapshot()).decode()
