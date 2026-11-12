"""Accounting evidence reconstruction from committed events only."""

# mypy: ignore-errors

from __future__ import annotations

from types import SimpleNamespace

from agents.cognition.accounting_ledgers import accounting_record_token
from analysis.accounting_ledgers_contract import (
    AccountingCoverage,
    accounting_record_evidence_token,
)
from analysis.accounting_ledgers_events import (
    accounting_evidence_digest,
    accounting_evidence_rows_from_events,
)
from analysis.accounting_ledgers_policy import AccountingLedgersAnalysisPolicy
from world.accounting_ledgers import (
    AccountingEntryFrame,
    AccountingFrameAct,
    AccountingFrameAssessment,
    AccountingFrameDirection,
    AccountingFrameEntryKind,
    AccountingFrameIntegrity,
    accounting_entry_relation,
)
from world.artifacts import ArtifactKind
from world.communications import origin_utterance
from world.events import (
    ArtifactCreated,
    ArtifactDamaged,
    ArtifactDestroyed,
    ExchangeCompleted,
    Given,
    ProjectContributed,
    PublicGoodBenefit,
    Talked,
)
from world.identifiers import EntityId, EventId


def event(
    token: str,
    details: object,
    *,
    tick: int = 0,
    sequence: int = 0,
    actor: str = "body-a",
):
    return SimpleNamespace(
        event_id=EventId(token),
        tick=tick,
        sequence=sequence,
        actor_id=EntityId(actor),
        target_id=None,
        details=details,
        occurrence=None,
    )


def _claim_frame(*, tick: int = 3) -> AccountingEntryFrame:
    return AccountingEntryFrame(
        act=AccountingFrameAct.DECLARE_ENTRY,
        entry_anchor="acct-0123456789abcdef",
        record_token=accounting_record_token("artifact-1"),
        entry_kind=AccountingFrameEntryKind.EXCHANGE,
        direction=AccountingFrameDirection.INFLOW,
        item_kind="food",
        quantity=2,
        organization_token=None,
        counterparty_token=None,
        assessment=AccountingFrameAssessment.CONSISTENT,
        integrity=AccountingFrameIntegrity.INTACT,
        confidence_milli=700,
        tick=tick,
        revision=0,
        record_genre="agreement",
    )


def _talked(token: str, *, tick: int = 3, sequence: int = 0) -> SimpleNamespace:
    relation = accounting_entry_relation(_claim_frame(tick=tick))
    utterance = origin_utterance(
        text="account",
        speaker_id=EntityId("body-a"),
        relations=(relation,),
    )

    return event(
        token,
        Talked(recipient_id=EntityId("body-b"), utterance=utterance),
        tick=tick,
        sequence=sequence,
    )


def test_record_lifecycle_reconstruction_including_tombstone() -> None:
    events = (
        event(
            "ev-created",
            ArtifactCreated(
                artifact_id=EntityId("artifact-1"),
                artifact_kind=ArtifactKind.RECORD,
                author_id=EntityId("body-a"),
                content_revision=0,
                resulting_location_id=EntityId("loc-a"),
            ),
        ),
        event(
            "ev-damaged",
            ArtifactDamaged(
                artifact_id=EntityId("artifact-1"),
                prior_integrity="intact",
                next_integrity="damaged",
                lost_mark_count_delta=1,
                content_revision=1,
            ),
            tick=1,
            sequence=1,
        ),
        event(
            "ev-destroyed",
            ArtifactDestroyed(
                artifact_id=EntityId("artifact-1"),
                artifact_kind=ArtifactKind.RECORD,
                content_revision=2,
                tombstone=True,
            ),
            tick=2,
            sequence=2,
        ),
    )
    harvest = accounting_evidence_rows_from_events(events, run_id="run-1")
    assert len(harvest.records) == 3
    assert harvest.records[-1].tombstoned is True
    assert harvest.records[-1].observed_integrity.value == "unknown"
    assert harvest.records[1].observed_integrity.value == "damaged"


def test_transfer_and_contribution_extraction() -> None:
    events = (
        event(
            "ev-give",
            Given(recipient_id=EntityId("body-b"), item_id=EntityId("item-1")),
        ),
        event(
            "ev-exchange",
            ExchangeCompleted(
                actor_id=EntityId("body-a"),
                counterparty_id=EntityId("body-b"),
                act="accept",
                give_item_ids=(EntityId("i1"), EntityId("i2")),
                take_item_ids=(EntityId("i3"),),
                give_item_kinds=("food", "food"),
                take_item_kinds=("water",),
            ),
            tick=1,
            sequence=1,
        ),
        event(
            "ev-contrib",
            ProjectContributed(
                project_id=EntityId("project-1"),
                actor_id=EntityId("body-a"),
                accepted=True,
                labor_done=1,
                materials_done=0,
            ),
            tick=2,
            sequence=2,
        ),
        event(
            "ev-benefit",
            PublicGoodBenefit(
                project_id=EntityId("project-1"),
                actor_id=EntityId("body-b"),
                project_kind="well",
                benefit_code="draw",
                source="command",
                integrity_millis=1_000,
                resulting_hunger=0.5,
            ),
            tick=3,
            sequence=3,
        ),
    )
    harvest = accounting_evidence_rows_from_events(events, run_id="run-1")
    assert len(harvest.transfers) == 3
    assert {row.item_kind for row in harvest.transfers} == {
        "food",
        "water",
        "unknown",
    }
    assert len(harvest.contributions) == 2
    assert harvest.contributions[0].accepted is True


def test_claim_speech_parsing_ignores_unrelated_and_malformed() -> None:
    from world.communications import CommunicationRelation

    unrelated = origin_utterance(
        text="hello",
        speaker_id=EntityId("body-a"),
        relations=(CommunicationRelation(subject="x", predicate="y", object="z"),),
    )

    events = (
        _talked("ev-claim"),
        event(
            "ev-unrelated",
            Talked(recipient_id=EntityId("body-b"), utterance=unrelated),
            tick=4,
            sequence=1,
        ),
    )
    harvest = accounting_evidence_rows_from_events(events, run_id="run-1")
    assert len(harvest.claims) == 1
    assert harvest.claims[0].record_token == accounting_record_token("artifact-1")
    assert harvest.claims[0].quantity == 2
    assert harvest.malformed_claims == 0


def test_digest_is_order_independent_for_committed_events() -> None:
    first = accounting_evidence_rows_from_events(
        (_talked("ev-a", tick=1), _talked("ev-b", tick=2, sequence=1)),
        run_id="run-1",
    )
    second = accounting_evidence_rows_from_events(
        (_talked("ev-b", tick=2, sequence=1), _talked("ev-a", tick=1)),
        run_id="run-1",
    )
    assert accounting_evidence_digest(first) == accounting_evidence_digest(second)


def test_token_parity_with_cognition() -> None:
    assert accounting_record_evidence_token("artifact-1") == accounting_record_token(
        "artifact-1"
    )


def test_coverage_states_and_truncation() -> None:
    empty = accounting_evidence_rows_from_events((), run_id="run-1")
    assert empty.coverage is AccountingCoverage.MISSING
    policy = AccountingLedgersAnalysisPolicy(max_claim_events=1)
    harvest = accounting_evidence_rows_from_events(
        (_talked("ev-a", tick=1), _talked("ev-b", tick=2, sequence=1)),
        run_id="run-1",
        policy=policy,
    )
    assert harvest.coverage is AccountingCoverage.PARTIAL
    assert len(harvest.claims) == 1
    assert "accounting_claim_truncated" in harvest.notices
