"""V4-08 evidence metric documents and availability semantics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from agents.cognition import empty_evidence_ledger
from analysis.evidence_testimony_alignment import derive_evidence_lineage
from analysis.evidence_testimony_layers import project_evidence_layers
from analysis.evidence_testimony_metrics import (
    compute_evidence_objective_alignment,
    compute_evidence_provenance_continuity,
    compute_evidence_source_structure,
)
from analysis.evidence_testimony_objective import (
    EvidenceObjectiveAnchorKind,
    evidence_objective_anchor_rows_from_events,
)
from analysis.evidence_testimony_rows import (
    EvidenceHarvestRows,
    harvest_evidence_rows,
)
from analysis.models import MetricAvailability
from tests.unit.evidence_testimony_helpers import OWNER, make_parts

pytestmark = pytest.mark.unit


def _documents(rows: EvidenceHarvestRows | None) -> tuple[Any, Any, Any]:
    if rows is None:
        return (
            compute_evidence_source_structure(
                None, None, None, None, run_id="run-1", input_revision="r1"
            ),
            compute_evidence_provenance_continuity(
                None, None, None, None, run_id="run-1", input_revision="r1"
            ),
            compute_evidence_objective_alignment(
                None, None, None, None, run_id="run-1", input_revision="r1"
            ),
        )
    analysis = derive_evidence_lineage(rows, objective_rows=())
    layers = project_evidence_layers(rows, analysis, analysis.summary)
    return (
        compute_evidence_source_structure(
            rows,
            analysis,
            analysis.summary,
            layers,
            run_id="run-1",
            input_revision="r1",
        ),
        compute_evidence_provenance_continuity(
            rows,
            analysis,
            analysis.summary,
            layers,
            run_id="run-1",
            input_revision="r1",
        ),
        compute_evidence_objective_alignment(
            rows,
            analysis,
            analysis.summary,
            layers,
            run_id="run-1",
            input_revision="r1",
        ),
    )


def test_absent_inputs_are_absent() -> None:
    for document in _documents(None):
        assert document.availability is MetricAvailability.ABSENT
        assert document.values == {}


def test_enabled_empty_ledger_is_present_with_zero_counts() -> None:
    rows = harvest_evidence_rows((empty_evidence_ledger(OWNER),))
    for document in _documents(rows):
        assert document.availability is MetricAvailability.PRESENT
        assert document.values
        assert document.coverage.observed == 0


def test_source_structure_values_and_denominators() -> None:
    parts = make_parts()
    rows = harvest_evidence_rows((parts.ledger(),))
    documents = _documents(rows)
    structure = documents[0]
    assert structure.metric_family == "evidence_source_structure"
    assert structure.values["source_count"] == 1
    assert structure.values["testimony_count"] == 1
    assert structure.values["item_count"] == 1
    assert isinstance(structure.values["source_kind_histogram"], str)
    assert structure.values["multi_owner_candidate_ratio"] == 0.0
    assert structure.values["uncorroborated_item_ratio"] == 0.0

    provenance = documents[1]
    assert provenance.values["custody_link_count"] == 1
    assert provenance.values["custody_complete_ratio"] == 1.0
    assert provenance.values["communicated_testimony_ratio"] == 1.0


def test_alignment_counts_and_not_applicable_exclusion() -> None:
    @dataclass
    class _Entity:
        value: str

    @dataclass
    class _Event:
        details: object
        tick: int
        event_id: _Entity

    def event(name: str, **attributes: object) -> _Event:
        return _Event(type(name, (), attributes)(), 1, _Entity("event-1"))

    anchors = evidence_objective_anchor_rows_from_events(
        (
            event(
                "ArtifactCreated",
                artifact_id="artifact-1",
                author_id=_Entity("agent-1"),
            ),
        ),
        {},
    )
    parts = make_parts()
    rows = harvest_evidence_rows((parts.ledger(),))
    analysis = derive_evidence_lineage(rows, objective_rows=anchors)
    layers = project_evidence_layers(
        rows, analysis, analysis.summary, objective_rows=anchors
    )
    document = compute_evidence_objective_alignment(
        rows,
        analysis,
        analysis.summary,
        layers,
        run_id="run-1",
        input_revision="r1",
    )
    assert document.metric_family == "evidence_objective_alignment"
    assert document.values["consistent_count"] == 1
    assert document.values["not_applicable_count"] == 0
    assert document.values["consistency_ratio"] == 1.0
    assert document.values["aligned_item_count"] == 1
    assert EvidenceObjectiveAnchorKind.ARTIFACT_CREATED.value == "artifact_created"
