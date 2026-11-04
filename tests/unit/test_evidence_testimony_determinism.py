"""V4-08 deterministic evidence output and identity."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from agents.cognition import (
    EvidenceContradictionKind,
    EvidenceCustodyRole,
    EvidenceInterpretationKind,
    EvidenceReferenceKind,
    EvidenceSourceKind,
    EvidenceTestimonyChannel,
    evidence_contradiction_id,
    evidence_custody_id,
    evidence_evaluation_id,
    evidence_item_id,
    evidence_ledger_digest,
    evidence_source_id,
    evidence_testimony_id,
)
from analysis.evidence_testimony_alignment import derive_evidence_lineage
from analysis.evidence_testimony_layers import project_evidence_layers
from analysis.evidence_testimony_rows import harvest_evidence_rows
from tests.unit.evidence_testimony_helpers import make_parts

pytestmark = pytest.mark.unit
ROOT = Path(__file__).resolve().parents[2]


def test_repeated_harvest_and_analysis_are_identical() -> None:
    ledger = make_parts().ledger()
    first = harvest_evidence_rows((ledger,))
    second = harvest_evidence_rows((ledger,))
    assert first == second

    first_analysis = derive_evidence_lineage(first)
    second_analysis = derive_evidence_lineage(second)
    assert first_analysis == second_analysis
    assert first_analysis.digest == second_analysis.digest

    first_layers = project_evidence_layers(
        first, first_analysis, first_analysis.summary
    )
    second_layers = project_evidence_layers(
        second, second_analysis, second_analysis.summary
    )
    assert first_layers == second_layers
    assert evidence_ledger_digest(ledger) == evidence_ledger_digest(
        make_parts().ledger()
    )


def test_id_minters_are_stable_across_calls() -> None:
    source = evidence_source_id(
        "agent-1",
        EvidenceSourceKind.ARTIFACT,
        EvidenceReferenceKind.ARTIFACT,
        "artifact-1",
        0,
    )
    assert source == evidence_source_id(
        "agent-1",
        EvidenceSourceKind.ARTIFACT,
        EvidenceReferenceKind.ARTIFACT,
        "artifact-1",
        0,
    )
    testimony = evidence_testimony_id(
        "agent-1", "agent-2", EvidenceTestimonyChannel.DIRECT, "-", 0
    )
    assert testimony == evidence_testimony_id(
        "agent-1", "agent-2", EvidenceTestimonyChannel.DIRECT, "-", 0
    )
    item = evidence_item_id("agent-1", source, EvidenceInterpretationKind.SUPPORTS, 0)
    assert item == evidence_item_id(
        "agent-1", source, EvidenceInterpretationKind.SUPPORTS, 0
    )
    custody = evidence_custody_id(
        "agent-1", source, 0, EvidenceCustodyRole.HOLDER, "x", 1
    )
    assert custody == evidence_custody_id(
        "agent-1", source, 0, EvidenceCustodyRole.HOLDER, "x", 1
    )
    contradiction = evidence_contradiction_id(
        "agent-1",
        source,
        item,
        EvidenceContradictionKind.INTERPRETATION_CONFLICT,
        0,
    )
    assert contradiction == evidence_contradiction_id(
        "agent-1",
        source,
        item,
        EvidenceContradictionKind.INTERPRETATION_CONFLICT,
        0,
    )
    evaluation = evidence_evaluation_id("agent-1", item, "direct_experience", 0)
    assert evaluation == evidence_evaluation_id("agent-1", item, "direct_experience", 0)


def test_evidence_modules_avoid_wall_clock_randomness_and_uuids() -> None:
    modules = [
        ROOT / "src" / "agents" / "cognition" / "evidence_testimony.py",
        ROOT / "src" / "agents" / "cognition" / "evidence_testimony_communication.py",
    ]
    modules.extend(sorted((ROOT / "src" / "analysis").glob("evidence_testimony_*.py")))
    modules.extend(
        sorted((ROOT / "src" / "simulation").glob("evidence_testimony_*.py"))
    )
    for path in modules:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        roots: set[str] = set()
        calls: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                roots.add(node.module.split(".")[0])
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                calls.add(node.func.id)
        assert roots.isdisjoint({"random", "secrets", "uuid", "time", "datetime"}), path
        assert "hash" not in calls, path
