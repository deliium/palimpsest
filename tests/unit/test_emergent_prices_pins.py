"""Pins for the V4-21 cognition contract."""

from __future__ import annotations

from pathlib import Path

import pytest

from agents.cognition.emergent_prices import (
    EMERGENT_PRICES_POLICY_VERSION,
    PRICE_BELIEF_PREFIX,
)

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"


def test_policy_token_and_prefix_are_pinned() -> None:
    assert EMERGENT_PRICES_POLICY_VERSION == "emergent-prices.v1"
    assert PRICE_BELIEF_PREFIX == "prcb-"


def test_price_modules_do_not_encode_a_runner_schema_bump() -> None:
    offenders = [
        str(path.relative_to(ROOT))
        for path in SRC.rglob("*.py")
        if "emergent_prices" in path.name
        and "runner-config-v57" in path.read_text(encoding="utf-8")
    ]
    assert offenders == []


def test_no_price_module_names_a_canonical_price_field() -> None:
    import ast

    offenders: list[str] = []
    for path in SRC.rglob("*emergent_prices*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for statement in node.body:
                    if isinstance(statement, ast.AnnAssign) and isinstance(
                        statement.target, ast.Name
                    ):
                        if statement.target.id in {"price", "canonical_price"}:
                            offenders.append(f"{path.name}:{node.name}")
    assert offenders == []


def test_final_v4_21_pins() -> None:
    from typing import get_args

    from analysis.specifications import METRIC_FAMILY_COUNT
    from observer.version import OBSERVER_PROTOCOL_VERSION, SEMANTIC_EVENT_TYPES
    from simulation.compatibility import (
        ALEMBIC_HEAD_REVISION,
        V4_OWNED_CAPABILITY_FLAGS,
    )
    from simulation.persistence import (
        ACCEPTED_EVENT_SCHEMA_VERSIONS,
        ACCEPTED_PERSISTENCE_CODEC_VERSIONS,
    )
    from simulation.v4_architecture import V4_CAPABILITY_FLAGS, V4_CONTEXTS
    from world._rules import COMMAND_RULE_MATRIX
    from world.actions import AgentCommand

    assert METRIC_FAMILY_COUNT == 220
    assert len(COMMAND_RULE_MATRIX) == 43
    assert len(get_args(AgentCommand)) == 43
    assert len(SEMANTIC_EVENT_TYPES) == 73
    assert len(V4_CONTEXTS) == 14
    assert len(V4_CAPABILITY_FLAGS) == 12
    assert len(V4_OWNED_CAPABILITY_FLAGS) == 8
    assert ALEMBIC_HEAD_REVISION == "0017"
    assert max(ACCEPTED_EVENT_SCHEMA_VERSIONS) == 27
    assert "v25" in ACCEPTED_PERSISTENCE_CODEC_VERSIONS
    assert OBSERVER_PROTOCOL_VERSION == "observer-protocol-v1"
    assert PRICE_BELIEF_PREFIX in "prcb-"
