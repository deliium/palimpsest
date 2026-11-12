"""Regression checks for the V4-23 verification fixes."""

# mypy: ignore-errors

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from agents.cognition import build_cognitive_loop
from agents.cognition.accounting_ledgers import (
    AccountingRecordIntegrity,
    AccountingRecordObservation,
    accounting_record_token,
    apply_accounting_ledger_update,
)
from agents.cognition.configuration import (
    CognitionAccountingLedgerMode,
    CognitionEvidenceMode,
    CognitionLoopConfig,
)
from agents.cognition.evidence_testimony import (
    EvidencePriorAgreement,
    EvidenceSourceKind,
)
from agents.cognition.subjective_value import SubjectiveValuationLedger, ValuationRow
from agents.models import AgentId
from analysis.accounting_ledgers_contract import (
    AccountingCoverage,
    AccountingEntryDirection,
    AccountingEntryKindToken,
    AccountingRecordAssessmentToken,
)
from analysis.accounting_ledgers_detection import (
    detect_accounting_entries,
    detect_record_conditions,
)
from analysis.accounting_ledgers_events import accounting_evidence_rows_from_events
from analysis.accounting_ledgers_rows import (
    AccountingClaimEvidenceRow,
    AccountingEvidenceHarvest,
    AnalyticalAccountingEntryRow,
)
from experiments.accounting_ledgers_completed_run import (
    accounting_owner_rows_from_result,
)
from persistence.accounting_ledgers_filesystem import (
    AccountingLedgersPublisherOptions,
    create_accounting_ledgers_publisher,
)
from simulation.accounting_ledgers_codec import (
    decode_accounting_ledgers_snapshot,
    encode_accounting_ledgers_snapshot,
    finalize_accounting_ledgers_snapshot,
)
from simulation.accounting_ledgers_models import (
    AccountingLedgersSnapshot,
    AccountingLedgersSummary,
    AccountingSnapshotEntry,
    empty_accounting_ledgers_snapshot,
)
from simulation.accounting_ledgers_paging import page_accounting_ledgers
from tests.unit.test_accounting_ledgers_events import event
from world.artifacts import ArtifactKind
from world.events import ArtifactAnnotated, ArtifactModified
from world.identifiers import EntityId
from world.values import ItemKind

OWNER = AgentId("agent-owner")
OTHER = AgentId("agent-other")


def _entry(index: int, *, window: int = 0, assessment: str = "consistent"):
    return AnalyticalAccountingEntryRow(
        entry_token=f"acce-{index:016x}",
        record_token=f"accrec-{index:016x}",
        entry_kind=AccountingEntryKindToken.EXCHANGE,
        direction=AccountingEntryDirection.INFLOW,
        item_kind="food",
        quantity=1,
        assessment=AccountingRecordAssessmentToken(assessment),
        confidence_milli=500,
        first_tick=window * 32,
        last_tick=window * 32,
        window_index=window,
    )


def _claim(index: int) -> AccountingClaimEvidenceRow:
    return AccountingClaimEvidenceRow(
        claim_token=f"accc-{index:016x}",
        record_token=f"accrec-{index:016x}",
        entry_kind=AccountingEntryKindToken.EXCHANGE,
        direction=AccountingEntryDirection.INFLOW,
        item_kind="food",
        quantity=1,
        assessment=AccountingRecordAssessmentToken.CONSISTENT,
        confidence_milli=500,
        speaker_token="body-a",
        tick=0,
        event_ordinal=index,
    )


def test_paging_across_windows_does_not_skip_rows() -> None:
    rows = (
        AccountingSnapshotEntry(
            entry_token="acce-ffffffffffffffff",
            record_token="accrec-0000000000000001",
            entry_kind="exchange",
            direction="inflow",
            item_kind="food",
            quantity=1,
            assessment="consistent",
            confidence_milli=500,
            first_tick=0,
            last_tick=0,
            window_index=0,
        ),
        AccountingSnapshotEntry(
            entry_token="acce-0000000000000001",
            record_token="accrec-0000000000000002",
            entry_kind="exchange",
            direction="inflow",
            item_kind="food",
            quantity=1,
            assessment="consistent",
            confidence_milli=500,
            first_tick=32,
            last_tick=32,
            window_index=1,
        ),
    )
    first, key = page_accounting_ledgers(rows, purpose="entries", limit=1)
    second, _ = page_accounting_ledgers(
        rows, purpose="entries", limit=1, after_key=key
    )
    assert len(first) == 1
    assert len(second) == 1


def test_condition_shares_are_condition_share_of_window_total() -> None:
    entries = (
        _entry(1, assessment="consistent"),
        _entry(2, assessment="consistent"),
        _entry(3, assessment="consistent"),
        _entry(4, assessment="damaged"),
    )
    conditions = detect_record_conditions(entries)
    by_name = {row.condition: row for row in conditions}
    assert by_name["consistent"].share_milli == 750
    assert by_name["damaged"].share_milli == 250
    assert all(row.availability == "available" for row in conditions)
    insufficient = detect_record_conditions(entries[:3])
    assert all(row.availability == "insufficient_samples" for row in insufficient)


def test_record_lifecycle_includes_modified_and_annotated() -> None:
    events = (
        event(
            "ev-modified",
            ArtifactModified(
                artifact_id=EntityId("artifact-1"),
                artifact_kind=ArtifactKind.RECORD,
                content_revision=1,
                resulting_location_id=EntityId("loc-a"),
            ),
            tick=1,
            sequence=1,
        ),
        event(
            "ev-annotated",
            ArtifactAnnotated(
                artifact_id=EntityId("artifact-1"),
                annotation_revisions=1,
                content_revision=2,
                integrity="damaged",
            ),
            tick=2,
            sequence=2,
        ),
    )
    harvest = accounting_evidence_rows_from_events(events, run_id="run-1")
    assert len(harvest.records) == 2
    assert harvest.records[0].content_revision == 1
    assert harvest.records[1].observed_integrity.value == "damaged"


def test_store_enforces_cumulative_byte_quota(tmp_path: Path) -> None:
    first = finalize_accounting_ledgers_snapshot(
        empty_accounting_ledgers_snapshot("run-1")
    )
    first_payload = encode_accounting_ledgers_snapshot(first)
    second = finalize_accounting_ledgers_snapshot(
        AccountingLedgersSnapshot(
            run_id="run-1",
            schema_version="accounting-ledgers-snapshot-v1",
            policy_version="accounting-ledgers.v1",
            summary=AccountingLedgersSummary(
                entry_count=1,
                record_count=0,
                condition_count=0,
                flow_count=0,
                counterparty_count=0,
                alignment_count=0,
                window_count=1,
                entry_coverage="complete",
                record_coverage="missing",
                alignment_coverage="missing",
                truncated=False,
            ),
            entries=(
                AccountingSnapshotEntry(
                    entry_token="acce-0000000000000001",
                    record_token="accrec-0000000000000001",
                    entry_kind="exchange",
                    direction="inflow",
                    item_kind="food",
                    quantity=1,
                    assessment="consistent",
                    confidence_milli=500,
                    first_tick=0,
                    last_tick=0,
                    window_index=0,
                ),
            ),
        )
    )
    second_payload = encode_accounting_ledgers_snapshot(second)
    publisher = create_accounting_ledgers_publisher(
        tmp_path,
        options=AccountingLedgersPublisherOptions(
            max_bytes=max(len(first_payload), len(second_payload)) + 1
        ),
    )
    publisher.publish(first)
    with pytest.raises(ValueError) as quota:
        publisher.publish(second)
    assert "quota" in str(quota.value)


def test_owner_rows_are_exported_from_a_runner_result() -> None:
    observation = AccountingRecordObservation(
        record_token=accounting_record_token("artifact-1"),
        record_genre="agreement",
        integrity=AccountingRecordIntegrity.INTACT,
        content_revision=0,
        relations=(("xch_food", "acc_v1", "in2"),),
        tick=1,
    )
    ledger = apply_accounting_ledger_update(
        owner_id=OWNER, tick=1, records=(observation,)
    )
    result = SimpleNamespace(accounting_ledgers=(ledger,))
    rows = accounting_owner_rows_from_result(result)
    assert len(rows) == 1
    assert rows[0].owner_token.startswith("acco-")
    assert rows[0].entry_token.startswith("acce-")


def test_prepare_evidence_routes_prior_agreement_candidates() -> None:
    loop = build_cognitive_loop(
        CognitionLoopConfig(evidence_mode=CognitionEvidenceMode.DETERMINISTIC)
    )
    observation = SimpleNamespace(
        tick=2,
        artifacts=(),
        repositories=(),
        occurrences=(),
        communications=(),
    )
    loop_input = SimpleNamespace(
        agent_id=OWNER,
        observation=observation,
        snapshot=None,
    )
    candidate = EvidencePriorAgreement(
        local_ref=EvidenceSourceKind.PRIOR_AGREEMENT.value,
        parties=(OWNER.value, OTHER.value),
        kind="commitment",
        tick=1,
        confidence=0.5,
        ordinal=0,
        owner_id=OWNER.value,
    )
    ledger = loop._prepare_evidence(
        loop_input, None, accounting_candidates=(candidate,)
    )
    assert ledger is not None


def test_detected_entries_use_the_entry_prefix() -> None:
    harvest = AccountingEvidenceHarvest(
        claims=(_claim(1),),
        coverage=AccountingCoverage.COMPLETE,
    )
    entries = detect_accounting_entries(harvest)
    assert entries[0].entry_token.startswith("acce-")


def test_accounting_valuations_use_the_real_valuation_ledger_rows() -> None:
    loop = build_cognitive_loop(
        CognitionLoopConfig(
            accounting_ledger_mode=CognitionAccountingLedgerMode.DETERMINISTIC
        )
    )
    observation = SimpleNamespace(
        tick=2,
        observer_id=OWNER,
        artifacts=(
            SimpleNamespace(
                entity_id=EntityId("artifact-1"),
                record_genre=SimpleNamespace(value="agreement"),
                integrity=SimpleNamespace(value="intact"),
                content_revision=0,
                content=SimpleNamespace(
                    relations=(
                        SimpleNamespace(
                            subject="xch_food",
                            predicate="acc_v1",
                            object="in2",
                        ),
                    )
                ),
            ),
        ),
        collective_projects=(),
    )
    loop_input = SimpleNamespace(
        agent_id=OWNER,
        observation=observation,
        snapshot=None,
    )
    valuations = SubjectiveValuationLedger(
        owner_id=OWNER,
        kind_rows=(
            ValuationRow(
                ItemKind.FOOD,
                ItemKind.GENERIC,
                2,
                (),
                1,
            ),
        ),
    )
    ledger = loop._prepare_accounting_ledgers(
        loop_input,
        structured_commitments=None,
        subjective_valuations=valuations,
        organizations=None,
    )
    assert ledger is not None
    assert ledger.entries[0].terms.valuation_milli == 2_000


def test_snapshot_decode_rejects_a_tampered_truncated_flag() -> None:
    snapshot = AccountingLedgersSnapshot(
        run_id="run-1",
        schema_version="accounting-ledgers-snapshot-v1",
        policy_version="accounting-ledgers.v1",
        summary=AccountingLedgersSummary(
            entry_count=0,
            record_count=0,
            condition_count=0,
            flow_count=0,
            counterparty_count=0,
            alignment_count=0,
            window_count=0,
            entry_coverage="missing",
            record_coverage="missing",
            alignment_coverage="missing",
            truncated=True,
        ),
    )
    finalized = finalize_accounting_ledgers_snapshot(snapshot)
    with pytest.raises(ValueError):
        decode_accounting_ledgers_snapshot(
            encode_accounting_ledgers_snapshot(finalized)
        )
