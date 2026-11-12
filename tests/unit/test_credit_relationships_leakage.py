"""Leakage guards for credit cognition, analysis, and export rows."""

# mypy: ignore-errors


from __future__ import annotations

import ast
from pathlib import Path

import pytest

from agents.cognition.credit_relationships import (
    CREDIT_FORBIDDEN_FIELD_NAMES,
    apply_credit_relationship_update,
)
from analysis.credit_relationships_contract import (
    CREDIT_ANALYSIS_FORBIDDEN_KEYS,
)
from simulation.credit_relationships_export import credit_owner_export
from tests.unit.test_credit_relationships_helpers import OWNER, claim

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"


def _credit_modules():
    return tuple(SRC.rglob("*credit_relationship*.py"))


def test_no_forbidden_field_names_outside_declared_constants() -> None:
    forbidden = CREDIT_FORBIDDEN_FIELD_NAMES | CREDIT_ANALYSIS_FORBIDDEN_KEYS
    offenders: list[str] = []
    for path in _credit_modules():
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


def test_analysis_rows_have_no_live_authority_fields() -> None:
    from analysis.credit_relationships_analysis import (
        CreditRelationshipsAnalysis,
    )

    for name in CreditRelationshipsAnalysis.__dataclass_fields__:
        text = str(
            CreditRelationshipsAnalysis.__dataclass_fields__[name].type
        )
        assert "WorldState" not in text
        assert "AgentCommand" not in text
        assert "WorldEvent" not in text
        assert "EntityId" not in text
        assert "Memory" not in text


def test_owner_export_contains_no_counterparty_ids_or_raw_items() -> None:
    ledger = apply_credit_relationship_update(
        owner_id=OWNER, tick=2, claims=(claim(),)
    )
    rows = credit_owner_export((ledger,))
    material = repr(rows)
    assert "agent-2" not in material
    assert "body-" not in material
    assert "item-" not in material


def test_credit_relations_never_attach_to_non_speech_commands() -> None:
    from agents.cognition.credit_relationships_communication import (
        credit_communicate_utterance,
    )
    from tests.unit.test_credit_relationships_helpers import PEER
    from world.actions import Give, Move, NegotiateExchange, Wait
    from world.identifiers import EntityId

    ledger = apply_credit_relationship_update(
        owner_id=OWNER, tick=2, claims=(claim(),)
    )
    for command in (
        Wait(),
        Move(destination_id=EntityId("loc-b")),
        Give(recipient_id=PEER, item_id=EntityId("item-1")),
        NegotiateExchange(
            counterparty_id=PEER,
            act="offer",
            give_item_ids=(EntityId("item-1"),),
            take_item_ids=(EntityId("item-2"),),
        ),
    ):
        assert (
            credit_communicate_utterance(
                command, owner_id=OWNER, ledger=ledger, tick=3
            )
            is command
        )


def test_cognition_modules_do_not_import_analysis_or_simulation() -> None:
    forbidden = (
        "simulation",
        "analysis",
        "experiments",
        "persistence",
        "api",
        "observer",
    )
    for path in SRC.rglob("*credit_relationship*.py"):
        if path.parts[-2] != "cognition":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert not node.module.startswith(forbidden), (path.name, node.module)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith(forbidden), (path.name, alias.name)
