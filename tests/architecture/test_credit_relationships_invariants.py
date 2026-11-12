"""V4-22 structural, authority, and append-only catalog invariants."""

from __future__ import annotations

import ast
import hashlib
from pathlib import Path
from typing import get_args

import pytest

from analysis.specifications import METRIC_FAMILY_COUNT, all_metric_specifications
from observer.version import SEMANTIC_EVENT_TYPES
from simulation.compatibility import (
    ALEMBIC_HEAD_REVISION,
    V4_OWNED_CAPABILITY_FLAGS,
)
from simulation.persistence import (
    ACCEPTED_EVENT_SCHEMA_VERSIONS,
    ACCEPTED_PERSISTENCE_CODEC_VERSIONS,
)
from simulation.runner_models import SUPPORTED_RUNNER_SCHEMA_VERSIONS
from simulation.v4_architecture import (
    V4_CAPABILITY_FLAGS,
    V4_CONTEXT_BY_ID,
    V4_CONTEXTS,
    V4Authority,
    V4ContextId,
)
from simulation.versioning import V4_WRITE_PAIR_RESERVATIONS
from world._rules import COMMAND_RULE_MATRIX
from world.actions import AgentCommand

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
TESTS = ROOT / "tests"
BASELINE_212 = "87fd875c1b53e588e19af116ca6c974515a5e8fa4b878901def526c096eb496e"
CREDIT_FAMILIES = (
    "credit_relationship_formation",
    "credit_repayment_performance",
    "credit_term_alignment",
    "credit_distribution_structure",
)


def test_catalog_appends_four_credit_families_after_212() -> None:
    assert METRIC_FAMILY_COUNT == 216
    specs = all_metric_specifications()
    assert len(specs) == 216
    assert tuple(spec.family_id.value for spec in specs[212:216]) == CREDIT_FAMILIES
    assert all(spec.algorithm_version == "1" for spec in specs[212:216])


def test_first_212_catalog_entries_are_byte_identical() -> None:
    specs = all_metric_specifications()[:212]
    material = "\x1e".join(
        "\x1f".join(
            (spec.family_id.value, spec.algorithm_version, ",".join(spec.value_keys))
        )
        for spec in specs
    )
    assert hashlib.sha256(material.encode()).hexdigest() == BASELINE_212


def test_no_credit_context_flag_or_schema_bump() -> None:
    assert "credit_relationships" not in {
        context.context_id.value for context in V4_CONTEXTS
    }
    assert "credit_relationships" not in V4_CAPABILITY_FLAGS
    assert len(V4_CONTEXTS) == 14
    assert len(V4_CAPABILITY_FLAGS) == 12
    assert len(V4_OWNED_CAPABILITY_FLAGS) == 8
    assert V4_OWNED_CAPABILITY_FLAGS == frozenset(
        {
            "organizations",
            "formal_rules",
            "legal_disputes",
            "diplomacy",
            "organized_conflict",
            "infrastructure_networks",
            "supply_chains",
            "markets_credit",
        }
    )
    token = "runner-config-" + "v57"
    assert token not in SUPPORTED_RUNNER_SCHEMA_VERSIONS
    for path in SRC.rglob("*credit_relationships*.py"):
        assert token not in path.read_text(encoding="utf-8", errors="ignore")


def test_version_pins_are_unchanged() -> None:
    assert ALEMBIC_HEAD_REVISION == "0017"
    assert not list((ROOT / "alembic" / "versions").glob("0018*"))
    assert len(COMMAND_RULE_MATRIX) == 43
    assert len(get_args(AgentCommand)) == 43
    assert len(SEMANTIC_EVENT_TYPES) == 73
    assert max(ACCEPTED_EVENT_SCHEMA_VERSIONS) == 27
    assert "v25" in ACCEPTED_PERSISTENCE_CODEC_VERSIONS
    assert "v22" not in ACCEPTED_PERSISTENCE_CODEC_VERSIONS


def test_markets_credit_context_stays_owner_scoped() -> None:
    spec = V4_CONTEXT_BY_ID[V4ContextId.MARKETS_CREDIT]
    assert spec.authority is V4Authority.OWNER_SCOPED
    assert spec.owner_packages == ("agents.cognition", "simulation")
    assert spec.uses_existing_events is True
    assert spec.prerequisite_contexts == (
        V4ContextId.SUPPLY_CHAINS,
        V4ContextId.ORGANIZATIONS,
    )
    assert "central bank" in " ".join(spec.non_goals)


def test_no_new_write_pair_is_claimed() -> None:
    assert {reservation.event_schema for reservation in V4_WRITE_PAIR_RESERVATIONS} == {
        23,
        24,
        25,
        26,
    }
    assert {
        reservation.codec_version for reservation in V4_WRITE_PAIR_RESERVATIONS
    } == {
        "v21",
        "v22",
        "v23",
        "v24",
    }


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
    return found


def test_credit_cognition_stays_inside_the_owner_layer() -> None:
    forbidden = (
        "simulation",
        "analysis",
        "experiments",
        "persistence",
        "api",
        "observer",
    )
    for path in SRC.rglob("*credit_relationships*.py"):
        if path.parts[-2] != "cognition":
            continue
        for module in _imports(path):
            assert not module.startswith(forbidden), f"{path.name}: {module}"


def test_credit_analysis_has_no_live_authority_imports() -> None:
    forbidden = (
        "agents",
        "simulation",
        "experiments",
        "persistence",
        "api",
        "observer",
    )
    for path in SRC.rglob("credit_relationships_*.py"):
        if path.parts[-2] != "analysis":
            continue
        for module in _imports(path):
            assert not module.startswith(forbidden), f"{path.name}: {module}"


def test_snapshot_tokens_stay_out_of_scientific_schemas() -> None:
    forbidden = (
        "credit-relationships-snapshot-v1",
        "credit-relationships-store-v1",
    )
    for path in (
        SRC / "simulation" / "runner_models.py",
        SRC / "simulation" / "runner.py",
        SRC / "simulation" / "persistence.py",
    ):
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in text, f"{path.name}: {token}"
    for path in (ROOT / "alembic" / "versions").glob("*.py"):
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in text, f"{path.name}: {token}"


def test_credit_modules_do_not_add_v2_routes_or_extra_events() -> None:
    for path in SRC.rglob("*credit_relationship*.py"):
        text = path.read_text(encoding="utf-8")
        assert "/v2" not in text, path.name
        assert "runner-config-v57" not in text, path.name


def test_credit_routes_are_get_only() -> None:
    from api.routes.credit_relationships import (
        CREDIT_RELATIONSHIPS_ROUTE_COUNT,
        router,
    )

    methods = {
        method
        for route in router.routes
        for method in getattr(route, "methods", set())
    }
    assert CREDIT_RELATIONSHIPS_ROUTE_COUNT == 7
    assert methods == {"GET"}
    text = (SRC / "api" / "routes" / "credit_relationships.py").read_text(
        encoding="utf-8"
    )
    for verb in ("@router.post", "@router.put", "@router.patch", "@router.delete"):
        assert verb not in text


def test_no_test_expects_markets_credit_unowned() -> None:
    offenders: list[str] = []
    for path in TESTS.rglob("*.py"):
        if "__pycache__" in path.parts or path == Path(__file__):
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if "markets_credit" in line and "unowned" in line:
                offenders.append(str(path.relative_to(ROOT)))
                break
    assert offenders == []
