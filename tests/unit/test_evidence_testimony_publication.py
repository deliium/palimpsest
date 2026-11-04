"""V4-08 completed-run snapshot composition and receipts."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

import pytest

from analysis.evidence_testimony_objective import (
    evidence_objective_anchor_rows_from_events,
)
from experiments.evidence_testimony_harvest import (
    build_completed_run_evidence_harvest,
)
from experiments.evidence_testimony_publication import (
    build_evidence_testimony_harvest_result,
    evidence_testimony_publication_document,
)
from simulation.evidence_testimony_codec import (
    decode_evidence_testimony_snapshot,
    encode_evidence_testimony_snapshot,
)
from tests.unit.evidence_testimony_helpers import make_parts

pytestmark = pytest.mark.unit
ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class _StopReason:
    value: str


@dataclass(frozen=True)
class _RunnerResult:
    evidence_ledgers: tuple[object, ...]
    run_id: str = "run-evidence-1"
    ticks_committed: int = 2
    stop_reason: _StopReason = _StopReason("completed")


def test_completed_run_composes_one_canonical_snapshot() -> None:
    parts = make_parts()
    harvest = build_completed_run_evidence_harvest(_RunnerResult((parts.ledger(),)))
    assert harvest.coverage == "partial"
    assert harvest.objective_rows == ()
    result = build_evidence_testimony_harvest_result(harvest)
    assert result.receipt["status"] == "published"
    assert result.published is True

    text = encode_evidence_testimony_snapshot(result.snapshot)
    decoded = decode_evidence_testimony_snapshot(text)
    assert decoded == result.snapshot
    assert encode_evidence_testimony_snapshot(decoded) == text
    assert decoded.publication_id.startswith("evid-pub-")

    document = evidence_testimony_publication_document(result)
    assert document["source_count"] == 1
    assert document["status"] == "published"


def test_empty_ledger_set_yields_empty_receipt() -> None:
    harvest = build_completed_run_evidence_harvest(_RunnerResult(()))
    result = build_evidence_testimony_harvest_result(harvest)
    assert result.receipt["status"] == "empty"
    assert result.published is False


def test_objective_events_produce_anchors() -> None:
    @dataclass(frozen=True)
    class _Entity:
        value: str

    @dataclass(frozen=True)
    class _Event:
        details: object
        tick: int
        event_id: _Entity

    class ArtifactCreated:
        artifact_id = "artifact-1"
        author_id = _Entity("agent-1")

    events = (_Event(ArtifactCreated(), 1, _Entity("event-1")),)
    harvest = build_completed_run_evidence_harvest(
        _RunnerResult((make_parts().ledger(),)), committed_events=events
    )
    assert harvest.objective_rows
    result = build_evidence_testimony_harvest_result(harvest)
    assert result.snapshot.objective_rows
    assert result.snapshot.objective_rows[0].kind == "artifact_created"


def test_composition_avoids_api_persistence_and_research_runner() -> None:
    path = ROOT / "src" / "experiments" / "evidence_testimony_publication.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.add(node.module.split(".")[0])
    assert imported.isdisjoint({"api", "persistence", "research_runner"})


def test_harvest_rejects_non_ledger_rows() -> None:
    with pytest.raises(ValueError):
        build_completed_run_evidence_harvest(_RunnerResult(("not-a-ledger",)))


def test_anchor_helpers_are_deterministic() -> None:
    @dataclass(frozen=True)
    class _Entity:
        value: str

    @dataclass(frozen=True)
    class _Event:
        details: object
        tick: int
        event_id: _Entity

    class Given:
        giver_id = _Entity("body-1")
        recipient_id = _Entity("body-2")
        item_id = "item-1"
        quantity = 1

    events = (_Event(Given(), 3, _Entity("event-2")),)
    first = evidence_objective_anchor_rows_from_events(events, {})
    second = evidence_objective_anchor_rows_from_events(events, {})
    assert first == second
