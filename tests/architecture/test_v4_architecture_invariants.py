"""V4-01 scaffolding invariants: pins, authority, and read-only clients.

One executable gate that fails if V4-01 drifts into behavior, adds an unreserved
wire surface, grants a context authority it must not have, or lets a client gain
a write path.
"""

from __future__ import annotations

import ast
import re
from dataclasses import replace
from pathlib import Path

import pytest

import observer
from analysis.specifications import METRIC_FAMILY_COUNT
from experiments import BENCHMARK_SCENARIO_COUNT, V3_BENCHMARK_SCENARIO_COUNT
from observer.capabilities import SUPPORTED_OBSERVER_PROTOCOLS
from observer.version import SEMANTIC_EVENT_TYPES
from simulation.compatibility import ALEMBIC_HEAD_REVISION, V4_OWNED_CAPABILITY_FLAGS
from simulation.migration_plan import (
    V4_MIGRATION_SEQUENCE,
    next_revision,
    validate_migration_sequence,
)
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
    V4_CONTEXT_BY_ID,
    V4_CONTEXT_MAP_VERSION,
    V4_CONTEXTS,
    V4Authority,
    V4ContextId,
    validate_v4_contexts,
)
from simulation.versioning import (
    V4_EVENT_REUSING_CONTEXTS,
    V4_WRITE_PAIR_RESERVATIONS,
    validate_write_pair_reservations,
)
from world._rules import COMMAND_RULE_MATRIX
from world.events import EVENT_SCHEMA_REPLAY_V22

pytestmark = pytest.mark.architecture

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
DOC = ROOT / "docs" / "v4-architecture.md"

V4_MODULES = (
    SRC / "simulation" / "v4_architecture.py",
    SRC / "simulation" / "versioning.py",
    SRC / "simulation" / "migration_plan.py",
    SRC / "simulation" / "scale.py",
)

MAGIC_ACTOR_TOKENS = (
    "OrganizationActor",
    "WorldGovernment",
    "CentralBank",
    "GlobalOrganizationRegistry",
    "GlobalLawRegistry",
    "WarState",
    "CivilizationActor",
    "InstitutionActor",
)

ALLOWED_FLAG_REFERENCES = {
    "simulation/__init__.py",
    "simulation/compatibility.py",
    "simulation/runner.py",
    "simulation/runner_models.py",
    "simulation/runner_serialization.py",
    "simulation/v4_architecture.py",
    "experiments/catalog.py",
    "experiments/matrix_schema.py",
}


def _first_party_python_files() -> list[Path]:
    return [
        path for path in sorted(SRC.rglob("*.py")) if "__pycache__" not in path.parts
    ]


def _imported_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            roots.add(node.module.split(".", 1)[0])
        elif isinstance(node, ast.Import):
            roots.update(alias.name.split(".", 1)[0] for alias in node.names)
    return roots


def _imported_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.Name):
            names.add(node.id)
    return names


def test_runner_and_wire_pins_are_unchanged() -> None:
    assert RUNNER_SCHEMA_VERSION == "runner-config-v4"
    assert RUNNER_SCHEMA_VERSION_V55 == "runner-config-v55"
    assert RUNNER_SCHEMA_VERSION_V56 in SUPPORTED_RUNNER_SCHEMA_VERSIONS
    assert EVENT_SCHEMA_REPLAY_V22 == 22
    assert max(ACCEPTED_EVENT_SCHEMA_VERSIONS) == 22
    assert "v20" in ACCEPTED_PERSISTENCE_CODEC_VERSIONS
    assert "v21" not in ACCEPTED_PERSISTENCE_CODEC_VERSIONS
    assert METRIC_FAMILY_COUNT == 164
    assert BENCHMARK_SCENARIO_COUNT == 16
    assert V3_BENCHMARK_SCENARIO_COUNT == 30


def test_observer_pins_and_facade_identity() -> None:
    assert len(SEMANTIC_EVENT_TYPES) == 73
    assert observer.SEMANTIC_EVENT_TYPES is SEMANTIC_EVENT_TYPES
    assert observer.OBSERVER_PROTOCOL_VERSION == "observer-protocol-v1"
    assert SUPPORTED_OBSERVER_PROTOCOLS == ("observer-protocol-v1",)


def test_migration_head_stays_at_0017() -> None:
    assert ALEMBIC_HEAD_REVISION == "0017"
    assert sorted((ROOT / "alembic" / "versions").glob("0018_*.py")) == []
    assert next_revision() == "0018"
    validate_migration_sequence()


def test_closed_command_count_is_unchanged() -> None:
    assert len(COMMAND_RULE_MATRIX) == 43
    for module in V4_MODULES:
        source = module.read_text(encoding="utf-8")
        assert "AgentCommand" not in source, module
        assert not re.search(r"class\s+\w+Command\b", source), module


def test_context_registry_and_capability_ownership() -> None:
    validate_v4_contexts()
    assert set(V4_CONTEXT_BY_ID) == set(V4ContextId)
    assert len(V4_CAPABILITY_FLAGS) == 12
    assert V4_ANALYSIS_ONLY_CONTEXTS == frozenset(
        {V4ContextId.SOCIETAL_RESILIENCE, V4ContextId.MACRO_SOCIETY_IDENTITY}
    )
    for spec in V4_CONTEXTS:
        if spec.context_id in V4_ANALYSIS_ONLY_CONTEXTS:
            assert spec.capability_flag is None
            assert spec.authority is V4Authority.DETACHED_ANALYSIS
            assert spec.owner_packages == ("analysis",)
        else:
            assert spec.capability_flag is not None
            assert spec.authority is not V4Authority.DETACHED_ANALYSIS
    for name in V4_CAPABILITY_FLAGS:
        flags = V4CapabilityFlags(**{name: True})
        if name in {"organizations", "formal_rules", "legal_disputes", "diplomacy"}:
            assert flags.owned_enabled_names() == (name,)
            assert flags.unimplemented_enabled_names() == ()
        else:
            assert flags.unimplemented_enabled_names() == (name,)
            assert flags.owned_enabled_names() == ()


def test_v4_08_deepens_legal_disputes_without_new_schema() -> None:
    """V4-08 adds no context, flag, runner schema, or reserved surface."""

    assert V4_CONTEXT_MAP_VERSION == "v4-context-map-v2"
    assert len(V4_CONTEXTS) == 14
    assert len(V4_CAPABILITY_FLAGS) == 12
    assert V4_OWNED_CAPABILITY_FLAGS == frozenset(
        {"organizations", "formal_rules", "legal_disputes", "diplomacy"}
    )
    assert V4ContextId.LEGAL_DISPUTES in V4_CONTEXT_BY_ID
    assert V4_CONTEXT_BY_ID[V4ContextId.LEGAL_DISPUTES].authority is (
        V4Authority.OWNER_SCOPED
    )

    offenders = [
        str(path.relative_to(SRC))
        for path in _first_party_python_files()
        if "runner-config-v57" in path.read_text(encoding="utf-8")
    ]
    assert offenders == []


def test_reservations_and_prerequisite_graph() -> None:
    validate_write_pair_reservations()
    reserved = {item.context_id for item in V4_WRITE_PAIR_RESERVATIONS}
    assert not reserved & V4_EVENT_REUSING_CONTEXTS
    assert reserved | V4_EVENT_REUSING_CONTEXTS == set(V4ContextId)

    known = {spec.context_id for spec in V4_CONTEXTS}
    edges = {spec.context_id: set(spec.prerequisite_contexts) for spec in V4_CONTEXTS}
    for targets in edges.values():
        assert targets <= known
    visiting: set[V4ContextId] = set()
    settled: set[V4ContextId] = set()

    def visit(node: V4ContextId) -> None:
        assert node not in visiting, f"prerequisite cycle at {node}"
        if node in settled:
            return
        visiting.add(node)
        for target in edges[node]:
            visit(target)
        visiting.discard(node)
        settled.add(node)

    for node in edges:
        visit(node)


def test_v4_flags_are_only_referenced_by_the_declared_surface() -> None:
    hits = {
        str(path.relative_to(SRC))
        for path in _first_party_python_files()
        if "v4_capability_flags" in path.read_text(encoding="utf-8")
    }
    assert hits <= ALLOWED_FLAG_REFERENCES, hits - ALLOWED_FLAG_REFERENCES


def test_no_magic_actor_symbols_exist() -> None:
    hits: list[str] = []
    for path in _first_party_python_files():
        source = path.read_text(encoding="utf-8")
        for token in MAGIC_ACTOR_TOKENS:
            if token in source:
                hits.append(f"{path.relative_to(SRC)}:{token}")
    assert hits == []


def test_scaffolding_modules_hold_no_authority() -> None:
    forbidden_roots = {
        "experiments",
        "analysis",
        "api",
        "persistence",
        "infrastructure",
        "observer",
    }
    forbidden_names = {"WorldState", "WorldEngine", "ActionSubmission"}
    for module in V4_MODULES:
        assert _imported_roots(module) & forbidden_roots == set(), module
        assert _imported_names(module) & forbidden_names == set(), module


def test_godot_client_is_read_only() -> None:
    for path in sorted(
        (ROOT / "clients" / "godot-observer" / "scripts" / "net").glob("*.gd")
    ):
        source = path.read_text(encoding="utf-8")
        for method in ("METHOD_POST", "METHOD_PUT", "METHOD_PATCH", "METHOD_DELETE"):
            assert method not in source, path

    models = (
        ROOT / "clients" / "godot-observer" / "scripts" / "protocol" / "models.gd"
    ).read_text(encoding="utf-8")
    assert "const SUPPORTED_PROTOCOLS: Array[String] = [PROTOCOL_VERSION]" in models
    assert "observer-protocol-v2" in models  # declared reserved, not supported


def test_research_ui_has_no_new_write_path() -> None:
    """The only POST call site is the pre-existing V2 branch comparison."""
    sources = {
        path.relative_to(ROOT).as_posix(): path.read_text(encoding="utf-8")
        for path in sorted((ROOT / "clients" / "research-ui" / "src").rglob("*"))
        if path.suffix in {".ts", ".svelte"}
    }
    post_sites = [name for name, text in sources.items() if "method: 'POST'" in text]
    assert post_sites == ["clients/research-ui/src/api/client.ts"]

    client = sources["clients/research-ui/src/api/client.ts"]
    version_section = client.split("export async function getVersion", 1)[1]
    assert "credentialFor" not in version_section
    assert "x-palimpsest-token" not in version_section
    for name in (
        "clients/research-ui/src/api/versionSchema.ts",
        "clients/research-ui/src/components/research/ProtocolBadge.svelte",
    ):
        assert "method: 'POST'" not in sources[name], name


def test_document_declares_every_context_and_section() -> None:
    text = DOC.read_text(encoding="utf-8")
    for context_id in V4ContextId:
        assert context_id.value in text, context_id
    for section in (
        "## Status and scope",
        "## Authority model",
        "## Context map",
        "## Cross-context contracts",
        "## Scale model",
        "## Version surfaces",
        "## Compatibility and deprecation policy",
        "## Migration posture",
        "## Presentation policy",
        "## Non-goals",
        "## Downstream V4 plan checklist",
    ):
        assert section in text, section


def test_validators_reject_mutated_copies() -> None:
    with pytest.raises(ValueError, match="v4_context_duplicate"):
        validate_v4_contexts(
            tuple(
                replace(spec, context_id=V4ContextId.FORMAL_RULES)
                if spec.context_id is V4ContextId.ORGANIZATIONS
                else spec
                for spec in V4_CONTEXTS
            )
        )
    with pytest.raises(ValueError, match="v4_pair_duplicate_event"):
        validate_write_pair_reservations(
            tuple(
                replace(item, event_schema=23) if index == 1 else item
                for index, item in enumerate(V4_WRITE_PAIR_RESERVATIONS)
            )
        )
    with pytest.raises(ValueError, match="v4_migration_order"):
        validate_migration_sequence(
            stages=tuple(
                replace(stage, order=3) if index == 1 else stage
                for index, stage in enumerate(V4_MIGRATION_SEQUENCE)
            )
        )


def test_v4_09_deepens_organizations_without_new_schema() -> None:
    """V4-09 deepens organizations; it adds no context, flag, or schema."""

    assert V4_CONTEXT_MAP_VERSION == "v4-context-map-v2"
    assert len(V4_CONTEXTS) == 14
    assert len(V4_CAPABILITY_FLAGS) == 12
    assert V4_OWNED_CAPABILITY_FLAGS == frozenset(
        {"organizations", "formal_rules", "legal_disputes", "diplomacy"}
    )
    assert V4_CONTEXT_BY_ID[V4ContextId.ORGANIZATIONS].authority is (
        V4Authority.OWNER_SCOPED
    )
    assert (
        V4ContextId.ORGANIZATIONS
        in V4_CONTEXT_BY_ID[V4ContextId.DIPLOMACY].prerequisite_contexts
    )
    assert V4CapabilityFlags(organized_conflict=True).owned_enabled_names() == ()

    offenders = [
        str(path.relative_to(SRC))
        for path in _first_party_python_files()
        if "runner-config-v57" in path.read_text(encoding="utf-8")
    ]
    assert offenders == []
