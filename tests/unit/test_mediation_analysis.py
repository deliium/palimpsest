"""Detached mediation harvesting, alignment, and partial-coverage behavior."""

from __future__ import annotations

from typing import Any

from agents.cognition.mediation import (
    MediationCase,
    MediationCaseStatus,
    MediationEvidence,
    MediationEvidenceChannel,
    MediationLedger,
    mediation_case_id,
    mediation_evidence_id,
)
from agents.models import AgentId
from analysis.mediation import (
    MediationCaseRow,
    MediationSnapshot,
    compute_conflict_mediation,
    harvest_mediation_rows,
    harvest_mediation_snapshot,
)

_CASE_A = "a" * 64
_CASE_B = "b" * 64
_CONTEXT = "c" * 16


def _case_row(
    ref: str,
    *,
    owner: str = "ada",
    status: str = "unresolved",
    tick: int = 2,
    root_ref: str = "",
) -> MediationCaseRow:
    return MediationCaseRow(
        owner_id=owner,
        case_ref=ref,
        subject_token="item_share",
        context_key=_CONTEXT,
        status=status,
        origin_id="bob",
        party_ids=("bob", "dave"),
        evidence_count=1,
        pruned_evidence_count=0,
        first_tick=1,
        last_tick=tick,
        window_first_tick=1,
        window_last_tick=8,
        evidence_coverage="complete",
        root_ref=root_ref,
    )


def _snapshot(*, owner: str = "ada", **kwargs: Any) -> MediationSnapshot:
    base: dict[str, Any] = dict(
        owner_id=owner,
        enabled=True,
        coverage="complete",
        first_observed_tick=1,
        last_observed_tick=2,
        observation_count=2,
    )
    base.update(kwargs)
    return MediationSnapshot(**base)


def test_same_root_repetition_counts_as_one_distinct_case() -> None:
    left = _snapshot(cases=(_case_row(_CASE_A), _case_row(_CASE_A, tick=3)))
    right = _snapshot(owner="bea", cases=(_case_row(_CASE_A, owner="bea"),))
    document = compute_conflict_mediation(
        (left, right), run_id="run-1", input_revision="rev-1", tick=4
    )
    assert document.values["distinct_case_count"] == 1


def test_duplicate_observer_reports_are_not_multiplied() -> None:
    left = _snapshot(cases=(_case_row(_CASE_A),))
    right = _snapshot(owner="bea", cases=(_case_row(_CASE_A, owner="bea"),))
    document = compute_conflict_mediation(
        (left, right), run_id="run-2", input_revision="rev-1", tick=4
    )
    assert document.values["distinct_case_count"] == 1
    assert document.values["enabled_owner_count"] == 2


def test_distinct_owner_refs_with_one_root_count_once() -> None:
    left = _snapshot(cases=(_case_row(_CASE_A, root_ref="shared-root"),))
    right = _snapshot(
        owner="bea", cases=(_case_row(_CASE_B, owner="bea", root_ref="shared-root"),)
    )
    document = compute_conflict_mediation(
        (left, right), run_id="run-root", input_revision="rev-1", tick=4
    )
    assert document.values["distinct_case_count"] == 1
    assert document.values["enabled_owner_count"] == 2


def test_disputed_alignment_stays_distinct_from_apparent_settlement() -> None:
    snapshot = _snapshot(
        cases=(
            _case_row(_CASE_A, status="disputed"),
            _case_row(_CASE_B, status="apparently_settled"),
        )
    )
    document = compute_conflict_mediation(
        (snapshot,), run_id="run-3", input_revision="rev-1", tick=4
    )
    assert document.values["disputed_case_count"] == 1
    assert document.values["apparently_settled_case_count"] == 1


def test_partial_history_is_published_as_partial() -> None:
    snapshot = _snapshot(
        cases=(_case_row(_CASE_A),),
        coverage="partial",
        pruned_case_count=1,
    )
    document = compute_conflict_mediation(
        (snapshot,), run_id="run-4", input_revision="rev-1", tick=4
    )
    assert document.availability.value == "partial"
    assert document.values["partial_coverage"] is True


def test_harvest_real_ledger_rows() -> None:
    evidence = MediationEvidence(
        evidence_id=mediation_evidence_id(
            _CASE_A, 0, MediationEvidenceChannel.OBSERVED, "lineage"
        ),
        ordinal=0,
        channel=MediationEvidenceChannel.OBSERVED,
        lineage_ref="lineage",
        root_ref="root",
        tick=1,
    )
    case = MediationCase(
        case_id=mediation_case_id(AgentId("ada"), _CASE_A),
        owner_id=AgentId("ada"),
        case_ref=_CASE_A,
        subject_token="item_share",
        context_key=_CONTEXT,
        status=MediationCaseStatus.UNRESOLVED,
        first_tick=1,
        last_tick=1,
        window_first_tick=1,
        window_last_tick=8,
        origin_id=AgentId("bob"),
        party_ids=(AgentId("bob"), AgentId("dave")),
        evidence=(evidence,),
    )
    ledger = MediationLedger(owner_id=AgentId("ada"), cases=(case,))
    snapshots = harvest_mediation_rows((ledger,))
    assert snapshots[0].cases[0].case_ref == _CASE_A
    with_duplicate = harvest_mediation_snapshot(ledger)
    assert with_duplicate.owner_id == "ada"


def test_committed_give_events_project_to_effect_rows() -> None:
    from types import SimpleNamespace

    from analysis.mediation import mediation_effect_rows_from_events
    from world.identifiers import EntityId

    event = SimpleNamespace(
        tick=3,
        actor_id=EntityId("body-ada"),
        details=SimpleNamespace(
            kind="give",
            recipient_id=EntityId("body-bob"),
            item_id=EntityId("bread"),
        ),
    )
    ignored = SimpleNamespace(
        tick=3,
        actor_id=EntityId("body-ada"),
        details=SimpleNamespace(kind="wait"),
    )
    rows = mediation_effect_rows_from_events(
        (event, ignored),
        entity_to_agent={"body-ada": "ada", "body-bob": "bob"},
    )
    assert len(rows) == 1
    assert rows[0].actor_id == "ada"
    assert rows[0].recipient_id == "bob"
    assert rows[0].item_token == "bread"
