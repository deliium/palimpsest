# ruff: noqa: E501
# mypy: disable-error-code="arg-type,assignment,union-attr,attr-defined,no-untyped-def,no-untyped-call,call-overload,index,type-arg,unused-ignore"
"""Architecture boundaries for V4-12 organized conflict.

Phase 1 pins capability ownership. Later phases extend the authority,
determinism, and no-new-wire-surface assertions.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from simulation.compatibility import V4_OWNED_CAPABILITY_FLAGS
from simulation.runner_models import V4CapabilityFlags
from simulation.v4_architecture import (
    V4_CAPABILITY_FLAGS,
    V4_CONTEXT_BY_ID,
    V4_CONTEXT_MAP_VERSION,
    V4_CONTEXTS,
    V4Authority,
    V4ContextId,
)

_SRC = Path(__file__).resolve().parents[2] / "src"


def next_revision() -> str:
    from simulation.migration_plan import next_revision as _next

    return _next()


def test_v4_12_owns_organized_conflict_without_new_context() -> None:
    assert V4_CONTEXT_MAP_VERSION == "v4-context-map-v2"
    assert len(V4_CONTEXTS) == 14
    assert len(V4_CAPABILITY_FLAGS) == 12
    assert V4_OWNED_CAPABILITY_FLAGS == frozenset(
        {
            "organizations",
            "formal_rules",
            "legal_disputes",
            "diplomacy",
            "organized_conflict",
            "infrastructure_networks",
        }
    )
    spec = V4_CONTEXT_BY_ID[V4ContextId.ORGANIZED_CONFLICT]
    assert spec.authority is V4Authority.OBJECTIVE_WORLD
    assert spec.capability_flag == "organized_conflict"
    assert spec.prerequisite_contexts == (V4ContextId.DIPLOMACY,)
    assert spec.uses_existing_events is True

    assert V4CapabilityFlags(organized_conflict=True).owned_enabled_names() == (
        "organized_conflict",
    )
    assert (
        V4CapabilityFlags(organized_conflict=True).unimplemented_enabled_names() == ()
    )


def test_v4_12_adds_no_runner_schema_or_war_state() -> None:
    offenders = [
        str(path.relative_to(_SRC))
        for path in sorted(_SRC.rglob("*.py"))
        if "__pycache__" not in path.parts
        and "runner-config-v57" in path.read_text(encoding="utf-8")
    ]
    assert offenders == []


@pytest.mark.parametrize(
    "forbidden",
    (
        "class ConflictRegistry",
        "class ArmyActor",
        "class WarState",
        "class VictoryOracle",
        "class Battle",
        "at_war:",
        "war_state:",
    ),
)
def test_no_war_state_object_exists_in_conflict_modules(forbidden: str) -> None:
    for name in ("organized_conflict.py", "organized_conflict_contract.py"):
        for path in _SRC.rglob(name):
            assert forbidden not in path.read_text(encoding="utf-8")


def test_conflict_analysis_and_publication_never_construct_commands() -> None:
    offenders = []
    for path in sorted(_SRC.rglob("organized_conflict*.py")):
        if "__pycache__" in path.parts:
            continue
        if path.name in {
            "organized_conflict_actions.py",
            "organized_conflict.py",
            "organized_conflict_communication.py",
        }:
            continue
        text = path.read_text(encoding="utf-8")
        if "AgentCommand" in text or "ActionSubmission" in text:
            offenders.append(str(path.relative_to(_SRC)))
    api_route = _SRC / "api" / "routes" / "organized_conflict.py"
    assert "AgentCommand" not in api_route.read_text(encoding="utf-8")
    assert offenders == []


def test_world_and_engine_never_read_the_conflict_ledger() -> None:
    for relative in ("world", "simulation/engine.py", "simulation/perception.py"):
        path = _SRC / relative
        files = [path] if path.is_file() else sorted(path.rglob("*.py"))
        for item in files:
            if item.name == "perception.py":
                continue
            assert "organized_conflict" not in item.read_text(encoding="utf-8"), item


def test_closed_pins_remain_unchanged() -> None:
    from simulation.compatibility import (
        ALEMBIC_HEAD_REVISION,
        OBSERVER_PROTOCOL_VERSION,
    )
    from simulation.versioning import EVENT_SCHEMA_REPLAY_V22
    from world._rules import COMMAND_RULE_MATRIX

    assert ALEMBIC_HEAD_REVISION == "0017"
    assert next_revision() == "0018"
    assert EVENT_SCHEMA_REPLAY_V22 == 22
    assert len(COMMAND_RULE_MATRIX) == 43
    assert OBSERVER_PROTOCOL_VERSION == "observer-protocol-v1"
    assert sorted((_SRC.parent / "alembic" / "versions").glob("0018_*.py")) == []


def test_exactly_six_conflict_routes_and_no_v2() -> None:
    from api.routes.organized_conflict import router

    routes = [route for route in router.routes if getattr(route, "methods", None)]
    assert len(routes) == 6
    assert all(route.methods == {"GET"} for route in routes)
    assert all("/v2/" not in route.path for route in routes)


def test_conflict_modules_do_not_import_or_call_world_authority() -> None:
    import ast

    forbidden_calls = {"submit", "admit", "resolve_tick", "execute"}
    forbidden_modules = (
        "world._",
        "simulation.engine",
        "simulation.persistence",
        "persistence",
        "api",
    )
    paths = [
        *sorted((_SRC / "agents" / "cognition").glob("organized_conflict*.py")),
        *sorted((_SRC / "analysis").glob("organized_conflict_*.py")),
        *sorted((_SRC / "simulation").glob("organized_conflict_*.py")),
        *sorted((_SRC / "experiments").glob("organized_conflict_*.py")),
        *sorted((_SRC / "persistence").glob("organized_conflict_*.py")),
    ]
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert not node.module.startswith(forbidden_modules), (path, node.module)
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith(forbidden_modules), (path, alias.name)
            if isinstance(node, ast.Call):
                name = getattr(node.func, "id", None) or getattr(
                    node.func, "attr", None
                )
                assert name not in forbidden_calls, (path, name)


def test_conflict_identity_never_mutates_org_or_msoc() -> None:
    path = _SRC / "analysis" / "organized_conflict_identity.py"
    text = path.read_text(encoding="utf-8")
    for operation in ("mint(", "rename(", "split(", "merge(", "dissolve("):
        assert operation not in text


def test_conflict_snapshot_store_and_cursor_pins() -> None:
    from persistence.organized_conflict_filesystem import (
        ORGANIZED_CONFLICT_STORE_SCHEMA,
    )
    from simulation.organized_conflict_models import ORGANIZED_CONFLICT_SNAPSHOT_SCHEMA
    from simulation.organized_conflict_ports import (
        ORGANIZED_CONFLICT_CURSOR_PURPOSES,
    )

    assert ORGANIZED_CONFLICT_SNAPSHOT_SCHEMA == "organized-conflict-snapshot-v1"
    assert ORGANIZED_CONFLICT_STORE_SCHEMA == "organized-conflict-store-v1"
    assert ORGANIZED_CONFLICT_CURSOR_PURPOSES == frozenset(
        {"summary", "episodes", "episode", "plans", "plan", "interpretations"}
    )


def test_conflict_metric_catalog_and_reserved_write_pairs() -> None:
    from analysis.specifications import METRIC_FAMILY_COUNT
    from simulation.versioning import V4_WRITE_PAIR_RESERVATIONS

    assert METRIC_FAMILY_COUNT == 192
    assert len(V4_WRITE_PAIR_RESERVATIONS) == 4


def test_conflict_modules_have_no_wall_clock_or_unordered_identity() -> None:
    for path in sorted(_SRC.rglob("organized_conflict*.py")):
        if "__pycache__" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        for forbidden in (
            "time.time(",
            "datetime.now(",
            "uuid4(",
            "uuid.uuid",
            "hash(",
        ):
            assert forbidden not in text, (path, forbidden)
