# mypy: ignore-errors

"""Owner-local commons evidence fold and ``cgo_v1`` frame invariants."""

from __future__ import annotations

import pytest

from agents.cognition.commons_governance import (
    MAX_EVIDENCE_TICKS,
    MAX_TRANSITION_ROWS,
    CommonsEvidenceCode,
    CommonsQuantitySignal,
    CommonsStance,
    advance_commons_evidence,
    commons_proposal_id,
    empty_commons_ledger,
    stage_commons_outbound,
)
from agents.cognition.commons_governance_communication import (
    CGO_FRAME_SUBJECT,
    CommonsAct,
    CommonsFrame,
    CommonsFrameError,
    CommonsTopic,
    commons_frame_relation,
    encode_commons_frame,
    parse_commons_frame,
)
from agents.models import AgentId
from tests.simulation_helpers import alive_body
from world.communications import (
    CommunicationRelation,
    origin_utterance,
    retell_utterance,
)
from world.identifiers import EntityId, EventId, WorldId, WorldRevision
from world.observations import (
    Observation,
    ObservationProvenance,
    ObservationSourceKind,
    ObservedCommunication,
    ObservedResource,
    observed_self_from_body,
)
from world.values import ResourceKind

pytestmark = pytest.mark.unit

_OWNER = AgentId("agent-a")
_ENTITY = EntityId("body-a")
_PEER = EntityId("body-b")
_PEER_B = EntityId("body-c")
_WORLD = WorldId("world-commons-governance")
_STOCK_A = EntityId("stock-a")
_STOCK_B = EntityId("stock-b")
_STOCKS = (_STOCK_A,)


def _ledger():
    return empty_commons_ledger(_OWNER, _ENTITY)


def _resource(stock_id: EntityId, quantity: float) -> ObservedResource:
    return ObservedResource(
        entity_id=stock_id,
        name=stock_id.value,
        kind=ResourceKind.WATER,
        quantity=quantity,
        unit="L",
    )


def _observation(
    tick: int,
    *,
    resources: tuple[ObservedResource, ...] = (),
    communications: tuple[ObservedCommunication, ...] = (),
) -> Observation:
    body = alive_body("body-a", location_id="loc-a")
    return Observation(
        world_id=_WORLD,
        observer_id=_ENTITY,
        revision=WorldRevision(tick),
        tick=tick,
        self_body=observed_self_from_body(body),
        resources=resources,
        communications=communications,
    )


def _delivery(
    *,
    tick: int,
    event: str,
    frame: CommonsFrame,
    speaker: EntityId,
    listener: EntityId,
    action_kind: str = "tell",
) -> ObservedCommunication:
    relation = commons_frame_relation(frame)
    utterance = origin_utterance(
        text="commons",
        speaker_id=speaker,
        communication_id=f"comm-{event}",
        relations=(relation,),
    )
    return ObservedCommunication(
        provenance=ObservationProvenance(
            source_kind=ObservationSourceKind.COMMUNICATION,
            source_tick=tick,
            source_event_id=EventId(f"event-{event}"),
        ),
        speaker_id=speaker,
        listener_id=listener,
        utterance=utterance,
        action_kind=action_kind,  # type: ignore[arg-type]
    )


def test_first_sighting_is_baseline_only() -> None:
    ledger = advance_commons_evidence(
        _OWNER,
        _ledger(),
        _observation(1, resources=(_resource(_STOCK_A, 5.0),)),
        _STOCKS,
    )
    assert len(ledger.stocks) == 1
    stock = ledger.stocks[0]
    assert stock.stock_id == _STOCK_A
    assert stock.last_visible_tick == 1
    assert stock.last_quantity_tenths == 50
    codes = [row.code for row in ledger.transitions]
    assert CommonsEvidenceCode.STOCK_CHECKED in codes
    assert CommonsEvidenceCode.STOCK_DECLINED not in codes
    assert all(
        row.signal is CommonsQuantitySignal.BASELINE
        for row in ledger.transitions
        if row.code is CommonsEvidenceCode.STOCK_CHECKED
    )


def test_consecutive_decline_and_gap_resets_baseline() -> None:
    ledger = advance_commons_evidence(
        _OWNER,
        _ledger(),
        _observation(1, resources=(_resource(_STOCK_A, 5.0),)),
        _STOCKS,
    )
    ledger = advance_commons_evidence(
        _OWNER,
        ledger,
        _observation(2, resources=(_resource(_STOCK_A, 4.0),)),
        _STOCKS,
    )
    assert any(
        row.code is CommonsEvidenceCode.STOCK_DECLINED for row in ledger.transitions
    )
    # Gap: tick 4 without tick 3 visibility → new baseline, no decline.
    ledger = advance_commons_evidence(
        _OWNER,
        ledger,
        _observation(4, resources=(_resource(_STOCK_A, 3.0),)),
        _STOCKS,
    )
    declined_at_4 = [
        row
        for row in ledger.transitions
        if row.source_tick == 4 and row.code is CommonsEvidenceCode.STOCK_DECLINED
    ]
    assert declined_at_4 == []
    checked = [
        row
        for row in ledger.transitions
        if row.source_tick == 4 and row.code is CommonsEvidenceCode.STOCK_CHECKED
    ]
    assert checked[0].signal is CommonsQuantitySignal.BASELINE


def test_two_independent_stocks() -> None:
    stocks = (_STOCK_A, _STOCK_B)
    ledger = advance_commons_evidence(
        _OWNER,
        _ledger(),
        _observation(
            1,
            resources=(
                _resource(_STOCK_A, 5.0),
                _resource(_STOCK_B, 8.0),
            ),
        ),
        stocks,
    )
    ledger = advance_commons_evidence(
        _OWNER,
        ledger,
        _observation(
            2,
            resources=(
                _resource(_STOCK_A, 4.0),
                _resource(_STOCK_B, 8.0),
            ),
        ),
        stocks,
    )
    by_stock = {
        row.stock_id: row
        for row in ledger.transitions
        if row.code is CommonsEvidenceCode.STOCK_DECLINED
    }
    assert _STOCK_A in by_stock
    assert _STOCK_B not in by_stock
    nondecline = [
        row
        for row in ledger.transitions
        if row.stock_id == _STOCK_B
        and row.code is CommonsEvidenceCode.STOCK_NONDECLINE
    ]
    assert len(nondecline) == 1


def test_inbound_propose_support_and_unverified_report_use() -> None:
    ledger = advance_commons_evidence(
        _OWNER,
        _ledger(),
        _observation(1, resources=(_resource(_STOCK_A, 5.0),)),
        _STOCKS,
    )
    propose = CommonsFrame(
        act=CommonsAct.PROPOSE,
        topic=CommonsTopic.REST,
        stock_id=_STOCK_A,
    )
    proposal_id = commons_proposal_id(
        stock_id=_STOCK_A,
        proposer_id=_PEER,
        topic=CommonsTopic.REST.value,
        peer_id=None,
        origin_tick=1,
    )
    ledger = advance_commons_evidence(
        _OWNER,
        ledger,
        _observation(
            2,
            resources=(_resource(_STOCK_A, 5.0),),
            communications=(
                _delivery(
                    tick=1,
                    event="propose",
                    frame=propose,
                    speaker=_PEER,
                    listener=_ENTITY,
                ),
            ),
        ),
        _STOCKS,
    )
    assert ledger.stocks[0].proposals[0].proposal_id == proposal_id
    support = CommonsFrame(
        act=CommonsAct.SUPPORT,
        topic=CommonsTopic.REST,
        stock_id=_STOCK_A,
        proposal_id=proposal_id,
    )
    report = CommonsFrame(
        act=CommonsAct.REPORT_USE,
        topic=CommonsTopic.REST,
        stock_id=_STOCK_A,
        proposal_id=proposal_id,
        reported_tick=2,
    )
    ledger = advance_commons_evidence(
        _OWNER,
        ledger,
        _observation(
            3,
            resources=(_resource(_STOCK_A, 4.5),),
            communications=(
                _delivery(
                    tick=2,
                    event="support",
                    frame=support,
                    speaker=_PEER_B,
                    listener=_ENTITY,
                ),
                _delivery(
                    tick=2,
                    event="report",
                    frame=report,
                    speaker=_PEER,
                    listener=_ENTITY,
                ),
            ),
        ),
        _STOCKS,
    )
    proposal = ledger.stocks[0].proposals[0]
    contributors = {row.speaker_id: row for row in proposal.contributors}
    assert contributors[_PEER_B].stance is CommonsStance.SUPPORT
    assert contributors[_PEER].report_use_tick == 2
    assert any(row.code is CommonsEvidenceCode.REPORT_USE for row in ledger.transitions)


def test_competing_access_claims() -> None:
    ledger = advance_commons_evidence(
        _OWNER,
        _ledger(),
        _observation(1, resources=(_resource(_STOCK_A, 5.0),)),
        _STOCKS,
    )
    claim = CommonsFrame(
        act=CommonsAct.CLAIM_ACCESS,
        topic=CommonsTopic.ACCESS,
        stock_id=_STOCK_A,
    )
    ledger = advance_commons_evidence(
        _OWNER,
        ledger,
        _observation(
            2,
            resources=(_resource(_STOCK_A, 5.0),),
            communications=(
                _delivery(
                    tick=1,
                    event="claim-b",
                    frame=claim,
                    speaker=_PEER,
                    listener=_ENTITY,
                ),
                _delivery(
                    tick=1,
                    event="claim-c",
                    frame=claim,
                    speaker=_PEER_B,
                    listener=_ENTITY,
                ),
            ),
        ),
        _STOCKS,
    )
    speakers = {row.speaker_id for row in ledger.stocks[0].access_claims}
    assert speakers == {_PEER, _PEER_B}
    assert sum(
        1 for row in ledger.transitions if row.code is CommonsEvidenceCode.ACCESS_CLAIM
    ) == 2


def test_rejects_forgery_duplicate_malformed_and_relay() -> None:
    ledger = advance_commons_evidence(
        _OWNER,
        _ledger(),
        _observation(1, resources=(_resource(_STOCK_A, 5.0),)),
        _STOCKS,
    )
    propose = CommonsFrame(
        act=CommonsAct.PROPOSE,
        topic=CommonsTopic.REST,
        stock_id=_STOCK_A,
    )
    good = _delivery(
        tick=1,
        event="propose",
        frame=propose,
        speaker=_PEER,
        listener=_ENTITY,
    )
    ledger = advance_commons_evidence(
        _OWNER,
        ledger,
        _observation(
            2,
            resources=(_resource(_STOCK_A, 5.0),),
            communications=(good,),
        ),
        _STOCKS,
    )
    # Duplicate occurrence/root within speaker.
    ledger = advance_commons_evidence(
        _OWNER,
        ledger,
        _observation(
            3,
            resources=(_resource(_STOCK_A, 5.0),),
            communications=(good,),
        ),
        _STOCKS,
    )
    assert len(ledger.stocks[0].proposals) == 1
    # Malformed relation object.
    bad_utterance = origin_utterance(
        text="commons",
        speaker_id=_PEER,
        communication_id="comm-bad",
        relations=(
            CommunicationRelation(
                subject=CGO_FRAME_SUBJECT,
                predicate="cgo_propose",
                object="rest|stock-a|extra|none|none|none",
            ),
        ),
    )
    bad = ObservedCommunication(
        provenance=ObservationProvenance(
            source_kind=ObservationSourceKind.COMMUNICATION,
            source_tick=2,
            source_event_id=EventId("event-bad"),
        ),
        speaker_id=_PEER,
        listener_id=_ENTITY,
        utterance=bad_utterance,
        action_kind="tell",
    )
    propose_count = sum(
        1 for row in ledger.transitions if row.code is CommonsEvidenceCode.PROPOSE
    )
    ledger = advance_commons_evidence(
        _OWNER,
        ledger,
        _observation(
            4,
            resources=(_resource(_STOCK_A, 5.0),),
            communications=(bad,),
        ),
        _STOCKS,
    )
    assert (
        sum(1 for row in ledger.transitions if row.code is CommonsEvidenceCode.PROPOSE)
        == propose_count
    )
    # Relay forgery via third-party retell.
    prior = origin_utterance(
        text="commons",
        speaker_id=_PEER,
        communication_id="comm-origin-relay",
        relations=(commons_frame_relation(propose),),
    )
    relayed_utterance = retell_utterance(
        prior=prior,
        speaker_id=_PEER_B,
        communication_id="comm-relayed",
        relations=(commons_frame_relation(propose),),
    )
    relayed = ObservedCommunication(
        provenance=ObservationProvenance(
            source_kind=ObservationSourceKind.COMMUNICATION,
            source_tick=3,
            source_event_id=EventId("event-relayed"),
        ),
        speaker_id=_PEER_B,
        listener_id=_ENTITY,
        utterance=relayed_utterance,
        action_kind="tell",
    )
    proposals_before = len(ledger.stocks[0].proposals)
    ledger = advance_commons_evidence(
        _OWNER,
        ledger,
        _observation(
            5,
            resources=(_resource(_STOCK_A, 5.0),),
            communications=(relayed,),
        ),
        _STOCKS,
    )
    assert len(ledger.stocks[0].proposals) == proposals_before


def test_matched_outbound_support_wrong_listener_and_absent_delivery() -> None:
    ledger = advance_commons_evidence(
        _OWNER,
        _ledger(),
        _observation(1, resources=(_resource(_STOCK_A, 5.0),)),
        _STOCKS,
    )
    propose = CommonsFrame(
        act=CommonsAct.PROPOSE,
        topic=CommonsTopic.REST,
        stock_id=_STOCK_A,
    )
    proposal_id = commons_proposal_id(
        stock_id=_STOCK_A,
        proposer_id=_PEER,
        topic=CommonsTopic.REST.value,
        peer_id=None,
        origin_tick=1,
    )
    ledger = advance_commons_evidence(
        _OWNER,
        ledger,
        _observation(
            2,
            resources=(_resource(_STOCK_A, 5.0),),
            communications=(
                _delivery(
                    tick=1,
                    event="propose",
                    frame=propose,
                    speaker=_PEER,
                    listener=_ENTITY,
                ),
            ),
        ),
        _STOCKS,
    )
    support = CommonsFrame(
        act=CommonsAct.SUPPORT,
        topic=CommonsTopic.REST,
        stock_id=_STOCK_A,
        proposal_id=proposal_id,
    )
    encoded = encode_commons_frame(support)
    staged = stage_commons_outbound(
        ledger, send_tick=2, listener_id=_PEER, encoded_frame=encoded
    )
    # Wrong listener: delivery to someone else does not confirm.
    ledger = advance_commons_evidence(
        _OWNER,
        staged,
        _observation(
            3,
            resources=(_resource(_STOCK_A, 5.0),),
            communications=(
                _delivery(
                    tick=2,
                    event="support-wrong",
                    frame=support,
                    speaker=_ENTITY,
                    listener=_PEER_B,
                ),
            ),
        ),
        _STOCKS,
    )
    assert ledger.staged_outbound is None  # expired unmatched
    assert all(
        row.actor_id != _ENTITY or row.code is not CommonsEvidenceCode.STANCE
        for row in ledger.transitions
    )
    # Absent delivery expires the staged frame.
    staged = stage_commons_outbound(
        ledger, send_tick=3, listener_id=_PEER, encoded_frame=encoded
    )
    ledger = advance_commons_evidence(
        _OWNER,
        staged,
        _observation(4, resources=(_resource(_STOCK_A, 5.0),)),
        _STOCKS,
    )
    assert ledger.staged_outbound is None
    # Matched outbound support establishes own stance.
    staged = stage_commons_outbound(
        ledger, send_tick=4, listener_id=_PEER, encoded_frame=encoded
    )
    ledger = advance_commons_evidence(
        _OWNER,
        staged,
        _observation(
            5,
            resources=(_resource(_STOCK_A, 5.0),),
            communications=(
                _delivery(
                    tick=4,
                    event="support-self",
                    frame=support,
                    speaker=_ENTITY,
                    listener=_PEER,
                ),
            ),
        ),
        _STOCKS,
    )
    contributors = {
        row.speaker_id: row for row in ledger.stocks[0].proposals[0].contributors
    }
    assert contributors[_ENTITY].stance is CommonsStance.SUPPORT
    assert ledger.staged_outbound is None


def test_same_tick_origin_reply_rejected_independently() -> None:
    ledger = advance_commons_evidence(
        _OWNER,
        _ledger(),
        _observation(1, resources=(_resource(_STOCK_A, 5.0),)),
        _STOCKS,
    )
    propose = CommonsFrame(
        act=CommonsAct.PROPOSE,
        topic=CommonsTopic.REST,
        stock_id=_STOCK_A,
    )
    proposal_id = commons_proposal_id(
        stock_id=_STOCK_A,
        proposer_id=_PEER,
        topic=CommonsTopic.REST.value,
        peer_id=None,
        origin_tick=2,
    )
    support = CommonsFrame(
        act=CommonsAct.SUPPORT,
        topic=CommonsTopic.REST,
        stock_id=_STOCK_A,
        proposal_id=proposal_id,
    )
    # Propose and support share source_tick=2; support must not adopt.
    ledger = advance_commons_evidence(
        _OWNER,
        ledger,
        _observation(
            3,
            resources=(_resource(_STOCK_A, 5.0),),
            communications=(
                _delivery(
                    tick=2,
                    event="propose-same",
                    frame=propose,
                    speaker=_PEER,
                    listener=_ENTITY,
                ),
                _delivery(
                    tick=2,
                    event="support-same",
                    frame=support,
                    speaker=_PEER_B,
                    listener=_ENTITY,
                ),
            ),
        ),
        _STOCKS,
    )
    proposal = ledger.stocks[0].proposals[0]
    assert proposal.origin_tick == 2
    assert proposal.contributors == ()


def test_proposer_cannot_support_own_proposal() -> None:
    ledger = advance_commons_evidence(
        _OWNER,
        _ledger(),
        _observation(1, resources=(_resource(_STOCK_A, 5.0),)),
        _STOCKS,
    )
    propose = CommonsFrame(
        act=CommonsAct.PROPOSE,
        topic=CommonsTopic.REST,
        stock_id=_STOCK_A,
    )
    proposal_id = commons_proposal_id(
        stock_id=_STOCK_A,
        proposer_id=_PEER,
        topic=CommonsTopic.REST.value,
        peer_id=None,
        origin_tick=1,
    )
    ledger = advance_commons_evidence(
        _OWNER,
        ledger,
        _observation(
            2,
            resources=(_resource(_STOCK_A, 5.0),),
            communications=(
                _delivery(
                    tick=1,
                    event="propose",
                    frame=propose,
                    speaker=_PEER,
                    listener=_ENTITY,
                ),
            ),
        ),
        _STOCKS,
    )
    support = CommonsFrame(
        act=CommonsAct.SUPPORT,
        topic=CommonsTopic.REST,
        stock_id=_STOCK_A,
        proposal_id=proposal_id,
    )
    ledger = advance_commons_evidence(
        _OWNER,
        ledger,
        _observation(
            3,
            resources=(_resource(_STOCK_A, 5.0),),
            communications=(
                _delivery(
                    tick=2,
                    event="self-support",
                    frame=support,
                    speaker=_PEER,
                    listener=_ENTITY,
                ),
            ),
        ),
        _STOCKS,
    )
    assert ledger.stocks[0].proposals[0].contributors == ()


def test_frame_round_trip_and_reject_oversize_combinations() -> None:
    frame = CommonsFrame(
        act=CommonsAct.PROPOSE,
        topic=CommonsTopic.TURN,
        stock_id=_STOCK_A,
        peer_id=_PEER,
    )
    encoded = encode_commons_frame(frame)
    assert parse_commons_frame(encoded) == frame
    with pytest.raises(CommonsFrameError):
        CommonsFrame(
            act=CommonsAct.PROPOSE,
            topic=CommonsTopic.REST,
            stock_id=_STOCK_A,
            peer_id=_PEER,
        )
    with pytest.raises(CommonsFrameError):
        CommonsFrame(
            act=CommonsAct.SUPPORT,
            topic=CommonsTopic.REST,
            stock_id=_STOCK_A,
        )


def test_exact_repeat_noop_and_rewind_fails() -> None:
    observation = _observation(1, resources=(_resource(_STOCK_A, 5.0),))
    ledger = advance_commons_evidence(_OWNER, _ledger(), observation, _STOCKS)
    again = advance_commons_evidence(_OWNER, ledger, observation, _STOCKS)
    assert again is ledger
    with pytest.raises(ValueError, match="tick_rewind"):
        advance_commons_evidence(
            _OWNER,
            ledger,
            _observation(0, resources=(_resource(_STOCK_A, 5.0),)),
            _STOCKS,
        )
    with pytest.raises(ValueError, match="wrong_owner"):
        advance_commons_evidence(
            AgentId("agent-other"),
            ledger,
            observation,
            _STOCKS,
        )


def test_order_stability_and_eviction_bounds() -> None:
    ledger = _ledger()
    for tick in range(1, MAX_EVIDENCE_TICKS + 8):
        ledger = advance_commons_evidence(
            _OWNER,
            ledger,
            _observation(
                tick,
                resources=(_resource(_STOCK_A, float(10 - (tick % 5))),),
            ),
            _STOCKS,
        )
    assert len(ledger.transitions) <= MAX_TRANSITION_ROWS
    ticks = [row.source_tick for row in ledger.transitions]
    assert ticks == sorted(ticks)
    assert ledger.omission_count >= 0
    # Oldest evidence outside the window is gone.
    oldest = min(row.source_tick for row in ledger.transitions)
    assert oldest >= ledger.last_processed_tick - MAX_EVIDENCE_TICKS + 1


def test_turn_propose_requires_addressed_peer() -> None:
    ledger = advance_commons_evidence(
        _OWNER,
        _ledger(),
        _observation(1, resources=(_resource(_STOCK_A, 5.0),)),
        _STOCKS,
    )
    frame = CommonsFrame(
        act=CommonsAct.PROPOSE,
        topic=CommonsTopic.TURN,
        stock_id=_STOCK_A,
        peer_id=_PEER,
    )
    # Wrong listener rejects the turn proposal.
    ledger = advance_commons_evidence(
        _OWNER,
        ledger,
        _observation(
            2,
            resources=(_resource(_STOCK_A, 5.0),),
            communications=(
                _delivery(
                    tick=1,
                    event="turn-wrong",
                    frame=frame,
                    speaker=_PEER_B,
                    listener=_ENTITY,
                ),
            ),
        ),
        _STOCKS,
    )
    assert ledger.stocks[0].proposals == ()
    # Correct addressed peer accepts.
    ledger = advance_commons_evidence(
        _OWNER,
        ledger,
        _observation(
            3,
            resources=(_resource(_STOCK_A, 5.0),),
            communications=(
                _delivery(
                    tick=2,
                    event="turn-ok",
                    frame=frame,
                    speaker=_PEER_B,
                    listener=_PEER,
                ),
            ),
        ),
        _STOCKS,
    )
    # Inbound requires listener == self; delivery to peer is not inbound for us.
    assert ledger.stocks[0].proposals == ()
    ledger = advance_commons_evidence(
        _OWNER,
        ledger,
        _observation(
            4,
            resources=(_resource(_STOCK_A, 5.0),),
            communications=(
                _delivery(
                    tick=3,
                    event="turn-to-self",
                    frame=CommonsFrame(
                        act=CommonsAct.PROPOSE,
                        topic=CommonsTopic.TURN,
                        stock_id=_STOCK_A,
                        peer_id=_ENTITY,
                    ),
                    speaker=_PEER,
                    listener=_ENTITY,
                ),
            ),
        ),
        _STOCKS,
    )
    assert len(ledger.stocks[0].proposals) == 1
    assert ledger.stocks[0].proposals[0].peer_id == _ENTITY
