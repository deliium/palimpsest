"""Committed-event reconstruction of credit claim and transfer evidence."""

# mypy: ignore-errors


from __future__ import annotations

import pytest

from analysis.credit_relationships_contract import (
    CreditClaimAct,
    CreditClaimDirection,
    CreditCoverage,
    CreditRelationshipAnalysisError,
)
from analysis.credit_relationships_events import (
    credit_evidence_digest,
    credit_evidence_rows_from_events,
)
from analysis.credit_relationships_policy import (
    CreditRelationshipsAnalysisPolicy,
)
from tests.unit.credit_relationships_analysis_helpers import (
    ANCHOR,
    RECIPIENT,
    completed,
    fed,
    frame,
    given,
    talked,
)
from world.communications import CommunicationRelation
from world.credit_relationships import CreditFrameAct, CreditFrameDirection
from world.events import Talked
from world.identifiers import EntityId, EventId

pytestmark = pytest.mark.unit


def test_valid_claim_is_reconstructed() -> None:
    harvest = credit_evidence_rows_from_events(
        [talked("evt-1", frame(), tick=2)]
    )
    assert harvest.coverage is CreditCoverage.COMPLETE
    row = harvest.claims[0]
    assert row.act is CreditClaimAct.PROPOSE
    assert row.direction is CreditClaimDirection.OWNER_DEBTOR
    assert row.anchor_token == ANCHOR
    assert row.principal_kind == "food"
    assert row.principal_quantity == 2
    assert row.repayment_kind == "water"
    assert row.repayment_quantity == 3
    assert row.actor_token == "body-a"
    assert row.counterparty_token == RECIPIENT


def test_told_is_also_evidence() -> None:
    harvest = credit_evidence_rows_from_events(
        [talked("evt-1", frame(), told=True)]
    )
    assert harvest.claim_count == 1


def test_two_relations_in_one_utterance_get_distinct_claims() -> None:
    harvest = credit_evidence_rows_from_events(
        [
            talked(
                "evt-1",
                frame(),
                frame(act=CreditFrameAct.ACCEPT),
            )
        ]
    )
    assert harvest.claim_count == 2
    assert len({row.claim_id for row in harvest.claims}) == 2


def test_unrelated_relation_is_ignored() -> None:
    from world.communications import origin_utterance

    relation = CommunicationRelation(
        subject="prc_v1", predicate="prc_quote", object="food:water"
    )
    event = SimpleTalk(
        "evt-1",
        origin_utterance(
            text="hello",
            speaker_id=EntityId("body-a"),
            relations=(relation,),
        ),
    )
    harvest = credit_evidence_rows_from_events([event])
    assert harvest.claims == ()
    assert harvest.coverage is CreditCoverage.MISSING


class SimpleTalk:
    def __init__(self, token: str, utterance: object) -> None:

        self.event_id = EventId(token)
        self.tick = 0
        self.sequence = 0
        self.actor_id = EntityId("body-a")
        self.target_id = None
        self.details = Talked(recipient_id=EntityId(RECIPIENT), utterance=utterance)
        self.occurrence = None


def _malformed_event(token: str, body: str) -> object:
    from types import SimpleNamespace

    from world.communications import origin_utterance

    relation = CommunicationRelation(
        subject="crd_v1", predicate="crd_propose", object=body
    )
    return SimpleNamespace(
        event_id=EventId(token),
        tick=0,
        sequence=0,
        actor_id=EntityId("body-a"),
        target_id=None,
        details=Talked(
            recipient_id=EntityId(RECIPIENT),
            utterance=origin_utterance(
                text="credit",
                speaker_id=EntityId("body-a"),
                relations=(relation,),
            ),
        ),
        occurrence=None,
    )


def test_malformed_frame_is_dropped_with_one_notice() -> None:
    harvest = credit_evidence_rows_from_events(
        [_malformed_event("evt-1", "not-a-frame")]
    )
    assert harvest.claims == ()
    assert "credit_claim_malformed" in harvest.notices
    assert harvest.coverage is CreditCoverage.MISSING


def test_oversize_frame_is_dropped() -> None:
    harvest = credit_evidence_rows_from_events(
        [_malformed_event("evt-1", "x" * 250)]
    )
    assert harvest.claims == ()
    assert "credit_claim_malformed" in harvest.notices


def test_duplicate_event_token_is_rejected() -> None:
    with pytest.raises(CreditRelationshipAnalysisError):
        credit_evidence_rows_from_events(
            [talked("evt-1", frame()), talked("evt-1", frame(), tick=1)]
        )


def test_ordering_is_deterministic() -> None:
    events = [
        talked("evt-2", frame(), tick=2, sequence=1),
        talked("evt-1", frame(), tick=1, sequence=2),
    ]
    harvest = credit_evidence_rows_from_events(events)
    assert [row.event_token for row in harvest.claims] == ["evt-1", "evt-2"]
    assert credit_evidence_digest(harvest) == credit_evidence_digest(
        credit_evidence_rows_from_events(list(reversed(events)))
    )


def test_transfer_kind_resolution_from_exchange_and_feed() -> None:
    harvest = credit_evidence_rows_from_events(
        [
            completed("evt-1", give_ids=("item-1",), give_kinds=("food",)),
            given("evt-2", item_id="item-1", tick=1, sequence=1),
            fed("evt-3", item_id="item-2", item_kind="water", tick=2),
            given("evt-4", item_id="item-2", tick=3, sequence=1),
        ]
    )
    assert [row.item_kind for row in harvest.transfers] == ["food", "water"]
    assert harvest.coverage is CreditCoverage.COMPLETE


def test_unresolved_transfer_kind_is_unknown_and_partial() -> None:
    harvest = credit_evidence_rows_from_events(
        [given("evt-1", item_id="item-unknown")]
    )
    assert harvest.transfers[0].item_kind == "unknown"
    assert harvest.transfers[0].coverage is CreditCoverage.PARTIAL
    assert harvest.coverage is CreditCoverage.PARTIAL


def test_empty_input_is_missing() -> None:
    harvest = credit_evidence_rows_from_events([])
    assert harvest.coverage is CreditCoverage.MISSING
    assert harvest.claims == ()
    assert harvest.transfers == ()
    assert harvest.notices == ()


def test_claim_cap_truncates_with_notice() -> None:
    policy = CreditRelationshipsAnalysisPolicy(max_claim_events=1)
    harvest = credit_evidence_rows_from_events(
        [talked("evt-1", frame()), talked("evt-2", frame(), tick=1)],
        policy=policy,
    )
    assert harvest.claim_count == 1
    assert "credit_evidence_truncated" in harvest.notices


def test_transfer_cap_truncates_with_notice() -> None:
    policy = CreditRelationshipsAnalysisPolicy(max_transfer_events=1)
    harvest = credit_evidence_rows_from_events(
        [
            given("evt-1", item_id="item-1"),
            given("evt-2", item_id="item-2", tick=1),
        ],
        policy=policy,
    )
    assert harvest.transfer_count == 1
    assert "credit_evidence_truncated" in harvest.notices


def test_digest_is_stable_across_repeats() -> None:
    events = [talked("evt-1", frame()), given("evt-2", item_id="item-1", tick=1)]
    first = credit_evidence_rows_from_events(events)
    second = credit_evidence_rows_from_events(events)
    assert credit_evidence_digest(first) == credit_evidence_digest(second)


def test_frame_direction_and_repayment_are_preserved() -> None:
    harvest = credit_evidence_rows_from_events(
        [
            talked(
                "evt-1",
                frame(
                    act=CreditFrameAct.REPAY,
                    direction=CreditFrameDirection.OWNER_CREDITOR,
                    paid_quantity=1,
                ),
            )
        ]
    )
    row = harvest.claims[0]
    assert row.direction is CreditClaimDirection.OWNER_CREDITOR
    assert row.paid_quantity == 1
