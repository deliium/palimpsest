"""V4-10 runtime carry, checkpoint, export, and determinism tests."""

from __future__ import annotations

import ast
from dataclasses import fields
from pathlib import Path
from types import SimpleNamespace

import pytest

from agents.cognition import empty_diplomacy_ledger, require_owner_diplomacy
from agents.cognition.configuration import (
    CognitionLoopConfig,
    build_cognitive_loop,
)
from agents.cognition.contracts import Perspective
from agents.cognition.models import SubjectiveSnapshot
from agents.models import AgentId
from simulation.models import RunId
from simulation.run_control import AgentRuntimeCheckpoint
from simulation.runner_models import (
    CognitionCounters,
    RunnerStopReasonCode,
    SimulationRunnerResult,
    SimulationRunnerResultDocument,
)

pytestmark = pytest.mark.unit

OWNER = "owner-a"
_SRC = Path(__file__).resolve().parents[2] / "src"


def test_perspective_snapshot_carries_the_owner_ledger() -> None:
    ledger = empty_diplomacy_ledger(OWNER, tick=2)
    snapshot = SubjectiveSnapshot(
        owner_id=AgentId(OWNER),
        revision=0,
        memories=(),
        legacy_beliefs=(),
        semantic_beliefs=(),
        relationships=(),
        goals=(),
        diplomacy=ledger,
    )
    assert snapshot.diplomacy is ledger
    assert "diplomacy" in {field.name for field in fields(Perspective)}


def test_snapshot_rejects_a_foreign_diplomacy_ledger() -> None:
    foreign = empty_diplomacy_ledger("owner-z", tick=0)
    with pytest.raises(ValueError, match="diplomacy_owner_mismatch"):
        SubjectiveSnapshot(
            owner_id=AgentId(OWNER),
            revision=0,
            memories=(),
            legacy_beliefs=(),
            semantic_beliefs=(),
            relationships=(),
            goals=(),
            diplomacy=foreign,
        )
    require_owner_diplomacy(None, OWNER)
    with pytest.raises(TypeError):
        require_owner_diplomacy(object(), OWNER)


def test_checkpoint_declares_the_diplomacy_slot() -> None:
    names = {field.name for field in fields(AgentRuntimeCheckpoint)}
    assert "diplomacy" in names


def test_disabled_mode_prepares_nothing() -> None:
    loop = build_cognitive_loop(CognitionLoopConfig())
    assert (
        loop._prepare_diplomacy(
            SimpleNamespace(),  # type: ignore[arg-type]
            representation=None,
            organization_concepts=None,
            collective_decisions=None,
            structured_commitments=None,
            disputes=None,
            evidence=None,
        )
        is None
    )
    assert loop._prepared_diplomacy is None


def _result(**overrides: object) -> SimulationRunnerResult:
    values: dict[str, object] = {
        "run_id": RunId("run-diplomacy-runtime"),
        "ticks_committed": 1,
        "stop_reason": RunnerStopReasonCode.MAX_TICKS,
        "attempt_receipts": (),
        "cognition_counters": CognitionCounters(),
    }
    values.update(overrides)
    return SimulationRunnerResult(**values)  # type: ignore[arg-type]


def test_result_accepts_owner_ordered_diplomacy_ledgers() -> None:
    ledgers = (
        empty_diplomacy_ledger("owner-a", tick=1),
        empty_diplomacy_ledger("owner-b", tick=1),
    )
    result = _result(diplomacy_ledgers=ledgers)
    assert result.diplomacy_ledgers == ledgers


def test_result_rejects_foreign_duplicate_and_misordered_ledgers() -> None:
    with pytest.raises(TypeError, match="diplomacy_ledgers"):
        _result(diplomacy_ledgers=(object(),))

    duplicate = (
        empty_diplomacy_ledger("owner-a", tick=1),
        empty_diplomacy_ledger("owner-a", tick=2),
    )
    with pytest.raises(ValueError, match="invalid_order"):
        _result(diplomacy_ledgers=duplicate)

    misordered = (
        empty_diplomacy_ledger("owner-b", tick=1),
        empty_diplomacy_ledger("owner-a", tick=1),
    )
    with pytest.raises(ValueError, match="invalid_order"):
        _result(diplomacy_ledgers=misordered)


def test_result_document_schema_is_unchanged() -> None:
    names = {field.name for field in fields(SimulationRunnerResultDocument)}
    assert "diplomacy" not in names
    assert "diplomacy_ledgers" not in names


def test_diplomacy_modules_are_deterministic_by_construction() -> None:
    forbidden_calls = {"uuid4", "uuid1", "now", "utcnow", "time", "hash"}
    for name in ("diplomacy.py", "diplomacy_communication.py"):
        path = _SRC / "agents" / "cognition" / name
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                text = (
                    func.id
                    if isinstance(func, ast.Name)
                    else func.attr
                    if isinstance(func, ast.Attribute)
                    else ""
                )
                assert text not in forbidden_calls, (name, text)
        assert "random" not in source
        assert "uuid" not in source
        assert "datetime" not in source
