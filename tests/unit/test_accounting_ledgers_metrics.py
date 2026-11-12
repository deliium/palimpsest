"""Four detached accounting metric documents."""

# mypy: ignore-errors

from __future__ import annotations

from analysis.accounting_ledgers_analysis import (
    empty_accounting_ledgers_analysis,
    harvest_accounting_ledgers_analysis,
)
from analysis.accounting_ledgers_metrics import (
    compute_accounting_entry_alignment,
    compute_accounting_flow_structure,
    compute_accounting_record_condition,
    compute_accounting_record_coverage,
)
from analysis.models import MetricAvailability
from tests.unit.test_accounting_ledgers_events import _talked, event
from world.artifacts import ArtifactKind
from world.events import ArtifactCreated
from world.identifiers import EntityId


def test_empty_analysis_yields_unknown_documents() -> None:
    analysis = empty_accounting_ledgers_analysis("run-1")
    documents = (
        compute_accounting_record_coverage(
            analysis, run_id="run-1", input_revision="rev-1"
        ),
        compute_accounting_entry_alignment(
            analysis, run_id="run-1", input_revision="rev-1"
        ),
        compute_accounting_record_condition(
            analysis, run_id="run-1", input_revision="rev-1"
        ),
        compute_accounting_flow_structure(
            analysis, run_id="run-1", input_revision="rev-1"
        ),
    )
    assert [document.metric_family for document in documents] == [
        "accounting_record_coverage",
        "accounting_entry_alignment",
        "accounting_record_condition",
        "accounting_flow_structure",
    ]
    assert all(
        document.availability is MetricAvailability.UNKNOWN
        for document in documents
    )
    assert all(document.values == {} for document in documents)


def test_present_analysis_emits_counts_and_milli_shares() -> None:
    created = event(
        "ev-created",
        ArtifactCreated(
            artifact_id=EntityId("artifact-1"),
            artifact_kind=ArtifactKind.RECORD,
            author_id=EntityId("body-a"),
            content_revision=0,
            resulting_location_id=EntityId("loc-a"),
        ),
    )
    analysis = harvest_accounting_ledgers_analysis(
        run_id="run-1", events=(created, _talked("ev-a", tick=1))
    )
    coverage = compute_accounting_record_coverage(
        analysis, run_id="run-1", input_revision="rev-1"
    )
    assert coverage.availability is not MetricAvailability.UNKNOWN
    assert coverage.values["entry_row_count"] == len(analysis.entries)
    assert coverage.values["coverage"] == "complete"

    alignment = compute_accounting_entry_alignment(
        analysis, run_id="run-1", input_revision="rev-1"
    )
    assert alignment.availability is MetricAvailability.UNKNOWN

    condition = compute_accounting_record_condition(
        analysis, run_id="run-1", input_revision="rev-1"
    )
    assert 0 <= condition.values["assessed_share_milli"] <= 1_000
    assert 0 <= condition.values["damaged_share_milli"] <= 1_000

    flow = compute_accounting_flow_structure(
        analysis, run_id="run-1", input_revision="rev-1"
    )
    assert flow.values["exchange_count"] == len(analysis.entries)


def test_documents_are_deterministic() -> None:
    analysis = harvest_accounting_ledgers_analysis(
        run_id="run-1", events=(_talked("ev-a", tick=1),)
    )
    first = compute_accounting_flow_structure(
        analysis, run_id="run-1", input_revision="rev-1"
    )
    second = compute_accounting_flow_structure(
        analysis, run_id="run-1", input_revision="rev-1"
    )
    assert first == second


def test_metric_service_emits_four_accounting_documents() -> None:
    from analysis.metric_service import (
        MetricComputationInputs,
        assemble_metric_documents,
    )

    analysis = harvest_accounting_ledgers_analysis(
        run_id="run-1", events=(_talked("ev-a", tick=1),)
    )
    inputs = MetricComputationInputs(
        run_id="run-1",
        input_revision="rev-1",
        window_end=1,
        accounting_ledgers_analysis=analysis,
    )
    bundle = assemble_metric_documents(inputs)
    accounting = [
        document
        for document in bundle.documents
        if document.metric_family.startswith("accounting_")
    ]
    assert len(accounting) == 4
