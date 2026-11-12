"""V4-21 structural, authority, and version invariants."""

from __future__ import annotations

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
from world._rules import COMMAND_RULE_MATRIX
from world.actions import AgentCommand

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
TESTS = ROOT / "tests"
BASELINE_212 = "87fd875c1b53e588e19af116ca6c974515a5e8fa4b878901def526c096eb496e"


def test_markets_credit_seam_is_unchanged() -> None:
    spec = V4_CONTEXT_BY_ID[V4ContextId.MARKETS_CREDIT]
    assert spec.authority is V4Authority.OWNER_SCOPED
    assert spec.owner_packages == ("agents.cognition", "simulation")
    assert spec.uses_existing_events is True
    assert spec.prerequisite_contexts == (
        V4ContextId.SUPPLY_CHAINS,
        V4ContextId.ORGANIZATIONS,
    )
    assert "price index" in " ".join(spec.non_goals)


def test_context_and_flag_counts_stay_owned() -> None:
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


def test_no_price_context_flag_or_schema_bump() -> None:
    assert "emergent_prices" not in {
        context.context_id.value for context in V4_CONTEXTS
    }
    assert "emergent_prices" not in V4_CAPABILITY_FLAGS
    token = "runner-config-" + "v57"
    assert token not in SUPPORTED_RUNNER_SCHEMA_VERSIONS
    for path in SRC.rglob("*emergent_prices*.py"):
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


def test_catalog_and_prefix_digest() -> None:
    assert METRIC_FAMILY_COUNT == 216
    specs = all_metric_specifications()
    material = "\x1e".join(
        "\x1f".join(
            (spec.family_id.value, spec.algorithm_version, ",".join(spec.value_keys))
        )
        for spec in specs[:212]
    )
    assert hashlib.sha256(material.encode()).hexdigest() == BASELINE_212


def test_no_global_price_field_in_price_modules() -> None:
    import ast

    forbidden = {
        "price",
        "canonical_price",
        "price_index",
        "clearing_price",
        "money",
        "currency",
        "numeraire",
        "bid",
        "ask",
        "spread",
        "fee",
        "commission",
        "tax",
        "debt",
        "credit_limit",
        "market_score",
        "ranking",
        "severity",
        "recommendation",
        "allocation",
        "quota",
        "central_planner",
    }
    offenders: list[str] = []
    for path in (*SRC.rglob("*emergent_prices*.py"),):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for statement in node.body:
                    if isinstance(statement, ast.AnnAssign) and isinstance(
                        statement.target, ast.Name
                    ):
                        if statement.target.id in forbidden:
                            offenders.append(f"{path.name}:{node.name}")
    assert offenders == []


def test_analysis_and_snapshot_rows_hold_no_private_types() -> None:
    from agents.models import AgentId
    from analysis.emergent_prices_analysis import EmergentPricesAnalysis
    from simulation.emergent_prices_models import EmergentPricesSnapshot
    from world.identifiers import EntityId

    for cls in (EmergentPricesAnalysis, EmergentPricesSnapshot):
        for name in cls.__dataclass_fields__:
            value = getattr(cls.__dataclass_fields__[name], "type", None)
            text = str(value)
            assert "AgentId" not in text
            assert "EntityId" not in text
            assert "WorldState" not in text
            assert "WorldEvent" not in text
    assert AgentId is not None and EntityId is not None


def test_no_market_identity_minting_in_price_modules() -> None:
    import re

    offenders: list[str] = []
    pattern = re.compile(r'return f"[^"]*mktc-')
    for path in SRC.rglob("*emergent_prices*.py"):
        if pattern.search(path.read_text(encoding="utf-8")):
            offenders.append(path.name)
    assert offenders == []


def test_off_gate_experiment_membership() -> None:
    from experiments.catalog import (
        EXPERIMENT_A_V1_CONDITION_IDS,
        OFF_GATE_MATRIX_EXPERIMENT_IDS,
    )

    assert "emergent_prices@1" in OFF_GATE_MATRIX_EXPERIMENT_IDS
    assert "emergent_prices@1" not in EXPERIMENT_A_V1_CONDITION_IDS
