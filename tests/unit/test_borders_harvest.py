# mypy: ignore-errors
"""Completed-run border harvest and publication receipts."""

from __future__ import annotations

from types import SimpleNamespace

from agents.cognition.borders import (
    BorderLedger,
    DomainClaimStatus,
    TerritorialDomainClaim,
    domain_claim_id,
)
from agents.models import AgentId
from analysis.borders_policy import default_borders_analysis_policy
from analysis.borders_rows import harvest_border_rows
from experiments.borders_harvest import build_completed_run_borders_harvest
from experiments.borders_publication import (
    borders_publication_document,
    build_borders_harvest_result,
)
from world.identifiers import EntityId, EventId

OWNER = AgentId("agent-1")
LOC_A = EntityId("loc-a")


def _ledger() -> BorderLedger:
    domain = TerritorialDomainClaim(
        domain_id=domain_claim_id(OWNER, (LOC_A,)),
        owner_id=OWNER,
        location_ids=(LOC_A,),
        boundary_edges=(),
        anchor_kind=None,
        anchor_ref=None,
        status=DomainClaimStatus.CLAIMED,
        strength=0.8,
        first_tick=1,
        last_tick=1,
    )
    return BorderLedger(owner_id=OWNER, domains=(domain,))


def _event() -> SimpleNamespace:
    return SimpleNamespace(
        event_id=EventId("event-1"),
        tick=1,
        actor_id=EntityId("body-1"),
        details=SimpleNamespace(kind="sleep"),
        occurrence=SimpleNamespace(
            origin_location_id=LOC_A, destination_location_id=None
        ),
    )


def _runner_result(*, ledger: BorderLedger | None = None, stop: str = "max_ticks"):
    return SimpleNamespace(
        stop_reason=SimpleNamespace(value=stop),
        border_ledgers=() if ledger is None else (ledger,),
        organization_candidates=(),
        macro_society_analysis=None,
    )


def test_harvest_order_and_inactive_paths() -> None:
    harvest = build_completed_run_borders_harvest(
        _runner_result(ledger=_ledger()), (_event(),)
    )
    assert harvest.has_ledger is True
    assert len(harvest.rows.claims) == 1
    assert len(harvest.rows.physical) == 1
    assert harvest.patterns
    assert harvest.candidates
    assert harvest.alignment
    assert harvest.summary.claim_count == 1
    assert harvest.layers.claims == harvest.rows.claims


def test_no_ledgers_yields_disabled() -> None:
    result = build_borders_harvest_result(_runner_result(), (), "run-1")
    assert result.receipt.status == "disabled"
    assert result.snapshot is None


def test_incomplete_stop_is_unavailable() -> None:
    result = build_borders_harvest_result(
        _runner_result(ledger=_ledger(), stop="cancelled"), (), "run-1"
    )
    assert result.receipt.status == "unavailable"
    assert result.receipt.reason == "cancelled"


def test_complete_run_publishes_all_four_families() -> None:
    result = build_borders_harvest_result(
        _runner_result(ledger=_ledger()), (_event(),), "run-1"
    )
    assert result.receipt.status == "published"
    assert result.snapshot is not None
    assert result.snapshot.publication_id.startswith("bd-pub-")
    assert {row.family for row in result.snapshot.metric_provenance} == {
        "border_claim_structure",
        "border_overlap_contest",
        "border_agreement_recognition",
        "border_control_alignment",
    }
    assert result.snapshot.summary.claim_count == 1
    document = borders_publication_document(result.receipt)
    assert document["status"] == "published"
    assert document["publication_id"] == result.receipt.publication_id


def test_harvest_does_not_mutate_the_result() -> None:
    ledger = _ledger()
    runner = _runner_result(ledger=ledger)
    build_completed_run_borders_harvest(runner, (_event(),))
    assert runner.border_ledgers == (ledger,)
    assert ledger == _ledger()


def test_org_and_macro_joins_are_read_only() -> None:
    org = SimpleNamespace(organization_id="org-1", border_domain_tokens=())
    runner = _runner_result(ledger=_ledger())
    runner.organization_candidates = (org,)
    build_completed_run_borders_harvest(runner, (_event(),))
    assert org.organization_id == "org-1"


def test_harvest_rows_without_physical_are_partial() -> None:
    rows = harvest_border_rows(
        (),
        (),
        policy=default_borders_analysis_policy(),
    )
    assert rows.coverage == "not_applicable"
    assert rows.physical == ()
