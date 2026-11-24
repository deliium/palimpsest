# mypy: ignore-errors

"""Voluntary commons social behavior: norms, rules, institutions, deferral, speech."""

from __future__ import annotations

from dataclasses import replace

import pytest

from agents.cognition.commons_governance import (
    CommonsConsiderationChoice,
    CommonsConsiderationOpportunity,
    CommonsContributor,
    CommonsProposalEvidence,
    CommonsStance,
    CommonsStockEvidence,
    advance_commons_evidence,
    commons_proposal_id,
    empty_commons_ledger,
    expected_turn_actor,
    proposal_is_contested,
    proposal_is_live,
    proposal_is_supported,
    rest_applies_on_tick,
)
from agents.cognition.commons_governance_actions import (
    CommonsNormCandidateKind,
    CommonsSpeechPriority,
    decorate_commons_speech,
    maybe_defer_commons_drink,
    select_commons_formal_rule_candidates,
    select_commons_institution_candidates,
    select_commons_norm_candidates,
    select_commons_proposal_origin,
    select_commons_speech,
    select_commons_stance,
)
from agents.cognition.commons_governance_communication import (
    CGO_FRAME_SUBJECT,
    CommonsAct,
    CommonsFrame,
    CommonsTopic,
    attach_commons_frame,
    commons_frame_relation,
    encode_commons_frame,
    parse_commons_frame,
)
from agents.cognition.configuration import CognitionSocialNormMode
from agents.cognition.formal_rules import (
    FormalRuleConstraintKind,
    FormalRuleScopeKind,
    FormalRuleStage,
    apply_formal_rule_update,
    empty_formal_rule_ledger,
    formal_rule_direction_preference,
    is_commons_lineage_rule,
)
from agents.cognition.institution_concepts import (
    InstitutionPatternChannel,
    apply_institution_concept_update,
    empty_institution_concept_ledger,
)
from agents.cognition.models import CounterpartBinding, OwnerSafeSocialIdentity
from agents.cognition.social_norms import evaluate_commons_norm_expectations
from agents.models import AgentId
from tests.simulation_helpers import alive_body
from world.actions import Drink, Talk, Wait
from world.communications import origin_utterance
from world.identifiers import EntityId, EventId, WorldId, WorldRevision
from world.models import LifeStatus
from world.observations import (
    CoarseHealth,
    Observation,
    ObservationAudienceRole,
    ObservationProvenance,
    ObservationSourceKind,
    ObservedCommunication,
    ObservedOccurrence,
    ObservedResource,
    VisibleBody,
    observed_self_from_body,
)
from world.values import ResourceKind, Thirst

pytestmark = pytest.mark.unit

_OWNER = AgentId("agent-a")
_ENTITY = EntityId("body-a")
_PEER = EntityId("body-b")
_PEER_C = EntityId("body-c")
_WORLD = WorldId("world-commons-behavior")
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


def _visible(*entity_ids: EntityId) -> tuple[VisibleBody, ...]:
    return tuple(
        VisibleBody(
            entity_id=entity_id,
            life_status=LifeStatus.ALIVE,
            coarse_health=CoarseHealth.STABLE,
        )
        for entity_id in entity_ids
    )


def _observation(
    tick: int,
    *,
    resources: tuple[ObservedResource, ...] = (),
    communications: tuple[ObservedCommunication, ...] = (),
    visible: tuple[VisibleBody, ...] = (),
    occurrences: tuple[ObservedOccurrence, ...] = (),
    thirst: float = 20.0,
) -> Observation:
    body = alive_body("body-a", location_id="loc-a")
    body = replace(body, thirst=Thirst(thirst))
    return Observation(
        world_id=_WORLD,
        observer_id=_ENTITY,
        revision=WorldRevision(tick),
        tick=tick,
        self_body=observed_self_from_body(body),
        resources=resources,
        communications=communications,
        visible_bodies=visible,
        occurrences=occurrences,
    )


def _delivery(
    *,
    tick: int,
    event: str,
    frame: CommonsFrame,
    speaker: EntityId,
    listener: EntityId,
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
        action_kind="tell",
    )


def _drink_occurrence(
    *,
    tick: int,
    event: str,
    stock_id: EntityId,
    actor: EntityId = _ENTITY,
) -> ObservedOccurrence:
    return ObservedOccurrence(
        provenance=ObservationProvenance(
            source_kind=ObservationSourceKind.OCCURRENCE,
            source_tick=tick,
            source_event_id=EventId(f"event-{event}"),
        ),
        kind="drink",
        audience_role=ObservationAudienceRole.ACTOR,
        actor_id=actor,
        other_entity_id=stock_id,
        success=True,
    )


def _seed_declines(
    ledger,
    *,
    end_tick: int,
    start_qty: float = 5.0,
    visible: tuple[VisibleBody, ...] = (),
):
    """Advance consecutive ticks with declining stock so end_tick has two declines."""

    qty = start_qty
    for tick in range(1, end_tick + 1):
        ledger = advance_commons_evidence(
            _OWNER,
            ledger,
            _observation(
                tick,
                resources=(_resource(_STOCK_A, qty),),
                visible=visible or _visible(_PEER),
            ),
            _STOCKS,
        )
        qty -= 0.5
    return ledger


def _identity() -> OwnerSafeSocialIdentity:
    return OwnerSafeSocialIdentity(
        owner_id=_OWNER,
        owner_entity_id=_ENTITY,
        counterparts=(
            CounterpartBinding(agent_id=AgentId("agent-b"), entity_id=_PEER),
        ),
    )


def _inject_supported_rest(
    ledger,
    *,
    origin_tick: int,
    support_tick: int,
    proposer: EntityId = _ENTITY,
    supporter: EntityId = _PEER,
):
    proposal_id = commons_proposal_id(
        stock_id=_STOCK_A,
        proposer_id=proposer,
        topic=CommonsTopic.REST.value,
        peer_id=None,
        origin_tick=origin_tick,
    )
    stock = (
        ledger.stocks[0]
        if ledger.stocks
        else CommonsStockEvidence(stock_id=_STOCK_A)
    )
    proposal = CommonsProposalEvidence(
        proposal_id=proposal_id,
        stock_id=_STOCK_A,
        topic=CommonsTopic.REST.value,
        proposer_id=proposer,
        peer_id=None,
        origin_tick=origin_tick,
        contributors=(
            CommonsContributor(
                speaker_id=supporter,
                stance=CommonsStance.SUPPORT,
                stance_tick=support_tick,
            ),
        ),
        eligible=True,
    )
    stock = replace(stock, proposals=(proposal,))
    return replace(ledger, stocks=(stock,)), proposal


def _inject_supported_turn(
    ledger,
    *,
    origin_tick: int,
    support_tick: int,
    proposer: EntityId = _ENTITY,
    peer: EntityId = _PEER,
):
    proposal_id = commons_proposal_id(
        stock_id=_STOCK_A,
        proposer_id=proposer,
        topic=CommonsTopic.TURN.value,
        peer_id=peer,
        origin_tick=origin_tick,
    )
    stock = (
        ledger.stocks[0]
        if ledger.stocks
        else CommonsStockEvidence(stock_id=_STOCK_A)
    )
    proposal = CommonsProposalEvidence(
        proposal_id=proposal_id,
        stock_id=_STOCK_A,
        topic=CommonsTopic.TURN.value,
        proposer_id=proposer,
        peer_id=peer,
        origin_tick=origin_tick,
        contributors=(
            CommonsContributor(
                speaker_id=peer,
                stance=CommonsStance.SUPPORT,
                stance_tick=support_tick,
            ),
        ),
        eligible=True,
    )
    stock = replace(stock, proposals=(proposal,))
    return replace(ledger, stocks=(stock,)), proposal


def test_lexical_first_originates_rest_after_consecutive_declines() -> None:
    ledger = _seed_declines(_ledger(), end_tick=3, visible=_visible(_PEER))
    origin = select_commons_proposal_origin(
        ledger,
        _observation(
            3,
            resources=(_resource(_STOCK_A, 3.5),),
            visible=_visible(_PEER),
        ),
    )
    assert origin is not None
    assert origin.topic is CommonsTopic.REST
    assert origin.recipient_id == _PEER
    assert origin.stock_id == _STOCK_A


def test_non_lexical_first_does_not_originate() -> None:
    # body-z sorts after body-a; add body-0 which sorts before body-a.
    early = EntityId("body-0")
    ledger = _seed_declines(_ledger(), end_tick=3, visible=_visible(early, _PEER))
    origin = select_commons_proposal_origin(
        ledger,
        _observation(
            3,
            resources=(_resource(_STOCK_A, 3.5),),
            visible=_visible(early, _PEER),
        ),
    )
    assert origin is None


def test_independent_support_activates_and_opposition_contests() -> None:
    ledger = _seed_declines(_ledger(), end_tick=2)
    ledger, proposal = _inject_supported_rest(
        ledger, origin_tick=1, support_tick=2, proposer=_PEER, supporter=_ENTITY
    )
    assert proposal_is_supported(proposal)
    assert proposal_is_live(proposal, 2)
    opposed = replace(
        proposal,
        contributors=(
            *proposal.contributors,
            CommonsContributor(
                speaker_id=_PEER_C,
                stance=CommonsStance.OPPOSE,
                stance_tick=2,
            ),
        ),
    )
    stock = replace(ledger.stocks[0], proposals=(opposed,))
    assert proposal_is_contested(opposed, stock, 2)


def test_proposal_expires_after_sixteen_ticks() -> None:
    ledger = _seed_declines(_ledger(), end_tick=2)
    ledger, proposal = _inject_supported_rest(
        ledger, origin_tick=1, support_tick=2
    )
    assert proposal_is_live(proposal, 16)
    assert not proposal_is_live(proposal, 17)


def test_turn_alternation_ignores_missing_slots() -> None:
    ledger = _seed_declines(_ledger(), end_tick=2)
    ledger, proposal = _inject_supported_turn(
        ledger, origin_tick=10, support_tick=11
    )
    assert expected_turn_actor(proposal, 10) == _ENTITY
    assert expected_turn_actor(proposal, 11) == _ENTITY
    assert expected_turn_actor(proposal, 12) == _PEER
    assert expected_turn_actor(proposal, 13) == _PEER
    assert expected_turn_actor(proposal, 14) == _ENTITY
    # Missing a peer turn does not shift later slots.
    assert expected_turn_actor(proposal, 16) == _PEER


def test_rest_parity_and_drink_deferral_with_consideration() -> None:
    ledger = _seed_declines(_ledger(), end_tick=2)
    ledger, proposal = _inject_supported_rest(
        ledger, origin_tick=2, support_tick=3
    )
    assert rest_applies_on_tick(proposal, 4)
    assert not rest_applies_on_tick(proposal, 5)
    result = maybe_defer_commons_drink(
        ledger,
        _observation(
            4,
            resources=(_resource(_STOCK_A, 3.0),),
            visible=_visible(_PEER),
            thirst=20.0,
        ),
        Drink(_STOCK_A),
    )
    assert result.deferred is True
    assert type(result.command) is Wait
    assert result.ledger.considerations[-1].opportunity is (
        CommonsConsiderationOpportunity.WAIT_EXPECTED
    )
    assert result.ledger.considerations[-1].choice is (
        CommonsConsiderationChoice.DEFERRED_DRAW
    )


def test_urgent_thirst_keeps_draw_and_opposes() -> None:
    ledger = _seed_declines(_ledger(), end_tick=2)
    ledger, _proposal = _inject_supported_rest(
        ledger, origin_tick=2, support_tick=3, proposer=_PEER, supporter=_ENTITY
    )
    result = maybe_defer_commons_drink(
        ledger,
        _observation(
            4,
            resources=(_resource(_STOCK_A, 3.0),),
            visible=_visible(_PEER),
            thirst=80.0,
        ),
        Drink(_STOCK_A),
    )
    assert result.deferred is False
    assert type(result.command) is Drink
    stance = select_commons_stance(
        ledger,
        _observation(4, resources=(_resource(_STOCK_A, 3.0),), visible=_visible(_PEER)),
        thirst=0.8,
    )
    assert stance is not None
    assert stance.stance is CommonsStance.OPPOSE


def test_out_of_turn_defers_own_turn_proceeds() -> None:
    ledger = _seed_declines(_ledger(), end_tick=2)
    ledger, _proposal = _inject_supported_turn(
        ledger, origin_tick=10, support_tick=11
    )
    # Tick 12-13: peer's turn -> owner defers.
    out = maybe_defer_commons_drink(
        ledger,
        _observation(
            12,
            resources=(_resource(_STOCK_A, 3.0),),
            visible=_visible(_PEER),
            thirst=20.0,
        ),
        Drink(_STOCK_A),
    )
    assert out.deferred is True
    # Tick 14-15: owner's turn -> proceed.
    own = maybe_defer_commons_drink(
        ledger,
        _observation(
            14,
            resources=(_resource(_STOCK_A, 3.0),),
            visible=_visible(_PEER),
            thirst=20.0,
        ),
        Drink(_STOCK_A),
    )
    assert own.deferred is False
    assert own.ledger.considerations[-1].opportunity is (
        CommonsConsiderationOpportunity.TURN_EXPECTED
    )


def test_formal_rule_commons_feed_excluded_from_generic_penalty() -> None:
    ledger = _seed_declines(_ledger(), end_tick=2)
    ledger, _proposal = _inject_supported_rest(
        ledger, origin_tick=1, support_tick=2
    )
    candidates = select_commons_formal_rule_candidates(ledger, 3)
    assert len(candidates) == 1
    assert candidates[0].lineage_ref.startswith("commons:")
    updated = apply_formal_rule_update(
        _OWNER,
        3,
        _observation(3, resources=(_resource(_STOCK_A, 3.0),)),
        empty_formal_rule_ledger(_OWNER),
        commons_candidates=candidates,
    )
    commons_rules = [rule for rule in updated.rules if is_commons_lineage_rule(rule)]
    assert len(commons_rules) == 1
    rule = commons_rules[0]
    assert rule.action_token == "feed"
    assert rule.constraint is FormalRuleConstraintKind.PROHIBITION
    assert rule.stage is FormalRuleStage.NORM
    assert rule.scope.kind is FormalRuleScopeKind.RESOURCE
    assert _STOCK_A.value in rule.scope.anchor_ids
    # Generic feed preference ignores the commons-tagged rule.
    assert formal_rule_direction_preference(updated, action_token="feed") == 0.0


def test_unrelated_stock_has_no_commons_restriction() -> None:
    ledger = _seed_declines(_ledger(), end_tick=2)
    ledger, _proposal = _inject_supported_rest(
        ledger, origin_tick=1, support_tick=2
    )
    candidates = select_commons_formal_rule_candidates(ledger, 3)
    updated = apply_formal_rule_update(
        _OWNER,
        3,
        _observation(
            3,
            resources=(
                _resource(_STOCK_A, 3.0),
                _resource(_STOCK_B, 9.0),
            ),
        ),
        empty_formal_rule_ledger(_OWNER),
        commons_candidates=candidates,
    )
    anchors = {
        anchor
        for rule in updated.rules
        if is_commons_lineage_rule(rule)
        for anchor in rule.scope.anchor_ids
    }
    assert anchors == {_STOCK_A.value}
    result = maybe_defer_commons_drink(
        ledger,
        _observation(
            4,
            resources=(_resource(_STOCK_B, 9.0),),
            visible=_visible(_PEER),
            thirst=20.0,
        ),
        Drink(_STOCK_B),
    )
    assert result.deferred is False


def test_institution_procedure_from_matched_turn_reports_only() -> None:
    ledger = _seed_declines(_ledger(), end_tick=2)
    ledger, proposal = _inject_supported_turn(
        ledger, origin_tick=10, support_tick=11
    )
    # After support at 11: peer slot 1 (ticks 12-13), then proposer slot 2 (14-15).
    peer_report = CommonsFrame(
        act=CommonsAct.REPORT_USE,
        topic=CommonsTopic.TURN,
        stock_id=_STOCK_A,
        proposal_id=proposal.proposal_id,
        reported_tick=12,
    )
    propose_report = CommonsFrame(
        act=CommonsAct.REPORT_USE,
        topic=CommonsTopic.TURN,
        stock_id=_STOCK_A,
        proposal_id=proposal.proposal_id,
        reported_tick=14,
    )
    from agents.cognition.commons_governance import stage_commons_outbound

    ledger = advance_commons_evidence(
        _OWNER,
        ledger,
        _observation(
            13,
            resources=(_resource(_STOCK_A, 2.5),),
            visible=_visible(_PEER),
            communications=(
                _delivery(
                    tick=12,
                    event="report-b",
                    frame=peer_report,
                    speaker=_PEER,
                    listener=_ENTITY,
                ),
            ),
        ),
        _STOCKS,
    )
    encoded = encode_commons_frame(propose_report)
    ledger = stage_commons_outbound(
        ledger, send_tick=14, listener_id=_PEER, encoded_frame=encoded
    )
    ledger = advance_commons_evidence(
        _OWNER,
        ledger,
        _observation(
            15,
            resources=(_resource(_STOCK_A, 2.0),),
            visible=_visible(_PEER),
            communications=(
                _delivery(
                    tick=14,
                    event="report-a",
                    frame=propose_report,
                    speaker=_ENTITY,
                    listener=_PEER,
                ),
            ),
        ),
        _STOCKS,
    )
    candidates = select_commons_institution_candidates(ledger, 15)
    assert candidates
    identity = _identity()
    prior = empty_institution_concept_ledger(_OWNER)
    updated = apply_institution_concept_update(
        _observation(
            15,
            resources=(_resource(_STOCK_A, 2.0),),
            visible=_visible(_PEER),
        ),
        identity,
        prior,
        commons_candidates=candidates,
    )
    assert updated is not None
    procedure = [
        concept
        for concept in updated.concepts
        if concept.strength_for(InstitutionPatternChannel.PROCEDURE_RECURRENCE) > 0.0
    ]
    assert procedure
    evidence_refs = {
        item.lineage_ref
        for concept in procedure
        for item in concept.evidence
        if item.pattern is InstitutionPatternChannel.PROCEDURE_RECURRENCE
    }
    assert len(evidence_refs) >= 1


def test_criticism_grounded_in_report_use_only() -> None:
    ledger = _seed_declines(_ledger(), end_tick=2)
    ledger, proposal = _inject_supported_rest(
        ledger, origin_tick=2, support_tick=3, proposer=_ENTITY, supporter=_PEER
    )
    # Peer reports a draw on a rest-parity tick after support.
    report = CommonsFrame(
        act=CommonsAct.REPORT_USE,
        topic=CommonsTopic.REST,
        stock_id=_STOCK_A,
        proposal_id=proposal.proposal_id,
        reported_tick=4,
    )
    ledger = advance_commons_evidence(
        _OWNER,
        ledger,
        _observation(
            5,
            resources=(_resource(_STOCK_A, 2.5),),
            visible=_visible(_PEER),
            communications=(
                _delivery(
                    tick=4,
                    event="bad-report",
                    frame=report,
                    speaker=_PEER,
                    listener=_ENTITY,
                ),
            ),
        ),
        _STOCKS,
    )
    candidates = select_commons_norm_candidates(
        ledger,
        _observation(5, resources=(_resource(_STOCK_A, 2.5),), visible=_visible(_PEER)),
    )
    criticism = [
        row for row in candidates if row.kind is CommonsNormCandidateKind.CRITICISM
    ]
    assert criticism
    assert criticism[0].recipient_id == _PEER
    assert criticism[0].reported_tick == 4
    expectations = evaluate_commons_norm_expectations(
        ledger,
        _observation(5, resources=(_resource(_STOCK_A, 2.5),), visible=_visible(_PEER)),
        mode=CognitionSocialNormMode.DETERMINISTIC,
    )
    assert any(row.kind == "criticism" for row in expectations)
    assert evaluate_commons_norm_expectations(
        ledger,
        _observation(5, resources=(_resource(_STOCK_A, 2.5),), visible=_visible(_PEER)),
        mode=CognitionSocialNormMode.DISABLED,
    ) == ()


def test_claim_access_when_no_supported_arrangement() -> None:
    ledger = _seed_declines(_ledger(), end_tick=3, visible=_visible(_PEER))
    observation = _observation(
        4,
        resources=(_resource(_STOCK_A, 3.0),),
        visible=_visible(_PEER),
        occurrences=(_drink_occurrence(tick=3, event="own-draw", stock_id=_STOCK_A),),
    )
    ledger = advance_commons_evidence(_OWNER, ledger, observation, _STOCKS)
    candidates = select_commons_norm_candidates(ledger, observation)
    claims = [
        row for row in candidates if row.kind is CommonsNormCandidateKind.CLAIM_ACCESS
    ]
    assert claims
    assert claims[0].stock_id == _STOCK_A


def test_speech_priority_and_ordinary_syntax() -> None:
    ledger = _seed_declines(_ledger(), end_tick=3, visible=_visible(_PEER))
    observation = _observation(
        3,
        resources=(_resource(_STOCK_A, 3.5),),
        visible=_visible(_PEER),
    )
    intent = select_commons_speech(ledger, observation)
    assert intent is not None
    assert intent.priority is CommonsSpeechPriority.PROPOSAL
    utterance = origin_utterance(
        text="hi",
        speaker_id=_ENTITY,
        communication_id="comm-speech",
        relations=(),
    )
    talk = Talk(recipient_id=_PEER, utterance=utterance)
    decorated, updated = decorate_commons_speech(ledger, observation, talk)
    assert type(decorated) is Talk
    relations = decorated.utterance.content.relations
    assert any(row.subject == CGO_FRAME_SUBJECT for row in relations)
    frame = parse_commons_frame(
        f"{CGO_FRAME_SUBJECT}|{relations[0].predicate}|{relations[0].object}"
    )
    assert frame.act is CommonsAct.PROPOSE
    assert updated.staged_outbound is not None
    assert updated.last_speech_tick == 3


def test_attach_frame_preserves_ordinary_admission_shape() -> None:
    frame = CommonsFrame(
        act=CommonsAct.CLAIM_ACCESS,
        topic=CommonsTopic.ACCESS,
        stock_id=_STOCK_A,
    )
    utterance = origin_utterance(
        text="claim",
        speaker_id=_ENTITY,
        communication_id="comm-claim",
        relations=(),
    )
    talk = Talk(recipient_id=_PEER, utterance=utterance)
    attached = attach_commons_frame(talk, frame)
    assert type(attached) is Talk
    assert attached.recipient_id == _PEER
    assert len(attached.utterance.content.relations) == 1


def test_override_suppresses_deferral_but_records_nothing_special() -> None:
    ledger = _seed_declines(_ledger(), end_tick=2)
    ledger, _proposal = _inject_supported_rest(
        ledger, origin_tick=2, support_tick=3
    )
    result = maybe_defer_commons_drink(
        ledger,
        _observation(
            4,
            resources=(_resource(_STOCK_A, 3.0),),
            visible=_visible(_PEER),
            thirst=20.0,
        ),
        Drink(_STOCK_A),
        overridden=True,
    )
    assert result.deferred is False
    assert type(result.command) is Drink
    assert result.ledger.considerations == ()
