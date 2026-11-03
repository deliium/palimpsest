"""V4-06 owner-only isolation and foreign-ledger rejection."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from agents.cognition import (
    FormalRuleError,
    empty_formal_rule_ledger,
    require_owner_formal_rules,
)
from agents.models import AgentId

pytestmark = pytest.mark.unit

OWNER = AgentId("agent-1")
OTHER = AgentId("agent-2")
SRC = Path(__file__).resolve().parents[2] / "src"


def test_update_rejects_world_state_world_event_physical_rules_and_metrics() -> None:
    from agents.cognition import apply_formal_rule_update

    for name in ("WorldState", "WorldEvent", "PhysicalRules", "MetricDocument"):
        forbidden = type(name, (), {})()
        with pytest.raises(FormalRuleError) as excinfo:
            apply_formal_rule_update(OWNER, 1, forbidden, None)
        assert excinfo.value.code == "formal_rule_forbidden_input"


def test_update_rejects_foreign_owner_prior_ledger() -> None:
    from agents.cognition import apply_formal_rule_update

    prior = empty_formal_rule_ledger(OTHER)
    with pytest.raises(FormalRuleError) as excinfo:
        apply_formal_rule_update(
            OWNER,
            1,
            type(
                "ObservationOpaque",
                (),
                {"tick": 1, "artifacts": (), "communications": ()},
            )(),
            prior,
        )
    assert excinfo.value.code == "formal_rule_owner_mismatch"


def test_snapshot_checkpoint_and_result_reject_foreign_owner() -> None:
    ledger = empty_formal_rule_ledger(OWNER)
    with pytest.raises(FormalRuleError) as excinfo:
        require_owner_formal_rules(ledger, OTHER, field_name="snapshot")
    assert excinfo.value.code == "formal_rule_owner_mismatch"
    assert require_owner_formal_rules(ledger, OWNER, field_name="snapshot") is ledger


def test_owner_a_cannot_read_owner_b_ledger() -> None:
    first = empty_formal_rule_ledger(OWNER)
    second = empty_formal_rule_ledger(OTHER)
    assert first.owner_id != second.owner_id
    with pytest.raises(FormalRuleError):
        require_owner_formal_rules(second, OWNER, field_name="peer")


def test_analysis_never_reads_live_cognition() -> None:
    for path in sorted(SRC.glob("analysis/formal_rule*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module is not None:
                imported.add(node.module.split(".", 1)[0])
            elif isinstance(node, ast.Import):
                imported.update(alias.name.split(".", 1)[0] for alias in node.names)
        assert not imported & {
            "agents",
            "api",
            "experiments",
            "infrastructure",
            "observer",
            "persistence",
            "simulation",
            "world",
        }, path


def test_formal_rule_candidate_never_changes_organization_identity() -> None:
    for path in sorted(SRC.glob("analysis/formal_rule*.py")):
        source = path.read_text(encoding="utf-8")
        assert "organization_detection" not in source
        assert "organization_identity" not in source
