"""Six mediation acts, responses, and role expressions over existing speech."""

from __future__ import annotations

import pytest

from agents.cognition.mediation import (
    MediationAct,
    MediationCase,
    MediationCaseStatus,
    MediationEvidence,
    MediationEvidenceChannel,
    MediationLedger,
    MediationRecommendation,
    MediationResponseKind,
    MediationRoleExpressionKind,
    mediation_case_id,
    mediation_context_key,
    mediation_evidence_id,
    mediation_recommendation_id,
)
from agents.cognition.mediation_communication import (
    MEDIATION_PREDICATES,
    ParsedMediationRelation,
    encode_mediation_relation,
    mediation_communicate_utterance,
    parse_mediation_relation,
    policy_marker_relation,
)
from agents.cognition.models import CounterpartBinding, OwnerSafeSocialIdentity
from agents.models import AgentId
from world.actions import Talk, Wait
from world.communications import (
    CommunicationRelation,
    CommunicationSourceBasis,
    origin_utterance,
)
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import LifeStatus
from world.observations import Observation, ObservedSelf
from world.values import (
    CarryCapacity,
    Fatigue,
    Health,
    Hunger,
    TemperatureCelsius,
    Thirst,
)

_OWNER = AgentId("ada")
_BEN = AgentId("ben")
_CAROL = AgentId("carol")
_CASE = "f" * 64
_CONTEXT = "a" * 16


def _identity() -> OwnerSafeSocialIdentity:
    return OwnerSafeSocialIdentity(
        owner_id=_OWNER,
        owner_entity_id=EntityId("body-ada"),
        counterparts=(
            CounterpartBinding(agent_id=_BEN, entity_id=EntityId("body-ben")),
            CounterpartBinding(agent_id=_CAROL, entity_id=EntityId("body-carol")),
        ),
    )


def _observation(*, tick: int = 1) -> Observation:
    return Observation(
        world_id=WorldId("world-w"),
        observer_id=EntityId("body-ada"),
        revision=WorldRevision(1),
        tick=tick,
        self_body=ObservedSelf(
            entity_id=EntityId("body-ada"),
            location_id=EntityId("clearing"),
            health=Health(100),
            hunger=Hunger(0),
            thirst=Thirst(0),
            fatigue=Fatigue(0),
            temperature=TemperatureCelsius(36.5),
            inventory=(),
            life_status=LifeStatus.ALIVE,
            carry_capacity=CarryCapacity(10),
        ),
    )


def _talk(relations: tuple[CommunicationRelation, ...] = ()) -> Talk:
    return Talk(
        recipient_id=EntityId("body-ben"),
        utterance=origin_utterance(
            text="hello",
            speaker_id=EntityId("body-ada"),
            communication_id="talk-1",
            relations=relations,
            source_basis=CommunicationSourceBasis.UNREFERENCED,
        ),
    )


def _evidence() -> MediationEvidence:
    return MediationEvidence(
        evidence_id=mediation_evidence_id(
            _CASE, 0, MediationEvidenceChannel.OBSERVED, "lineage"
        ),
        ordinal=0,
        channel=MediationEvidenceChannel.OBSERVED,
        lineage_ref="lineage",
        root_ref="root",
        tick=1,
    )


def _ledger(*, with_recommendation: bool = False) -> MediationLedger:
    case = MediationCase(
        case_id=mediation_case_id(_OWNER, _CASE),
        owner_id=_OWNER,
        case_ref=_CASE,
        subject_token="item_share",
        context_key=_CONTEXT,
        status=MediationCaseStatus.UNRESOLVED,
        first_tick=1,
        last_tick=1,
        window_first_tick=1,
        window_last_tick=8,
        origin_id=_BEN,
        party_ids=(_BEN, _CAROL),
        evidence=(_evidence(),),
    )
    recommendations: tuple[MediationRecommendation, ...] = ()
    if with_recommendation:
        recommendations = (
            MediationRecommendation(
                recommendation_id=mediation_recommendation_id(_OWNER, _CASE, 0),
                owner_id=_OWNER,
                case_ref=_CASE,
                revision=0,
                proposed_actor_id=_BEN,
                action_token="give",
                first_tick=1,
                last_tick=1,
                window_first_tick=1,
                window_last_tick=8,
                target_ids=(_CAROL,),
                item_token="bread",
                terms=("return_item",),
            ),
        )
    return MediationLedger(
        owner_id=_OWNER,
        cases=(case,),
        recommendations=recommendations,
        first_observed_tick=1,
        last_observed_tick=1,
        observation_count=1,
    )


def test_every_primary_act_encodes_and_parses() -> None:
    assert len(MEDIATION_PREDICATES) == 6
    for act in MediationAct:
        relation = encode_mediation_relation(
            act=act,
            case_ref=_CASE,
            revision=0,
            subject_token="item_share",
            action_token="give"
            if act
            in {
                MediationAct.PROPOSE_COMPROMISE,
                MediationAct.RECOMMEND_RESTITUTION,
            }
            else None,
            proposed_entity=EntityId("body-ben")
            if act
            in {
                MediationAct.PROPOSE_COMPROMISE,
                MediationAct.RECOMMEND_RESTITUTION,
            }
            else None,
            item_token="bread"
            if act
            in {
                MediationAct.PROPOSE_COMPROMISE,
                MediationAct.RECOMMEND_RESTITUTION,
            }
            else None,
            terms=("return_item",)
            if act
            in {
                MediationAct.PROPOSE_COMPROMISE,
                MediationAct.RECOMMEND_RESTITUTION,
            }
            else (),
            window_first_tick=1,
            window_last_tick=8,
            target_entity=EntityId("body-carol") if act is MediationAct.VOUCH else None,
            claim_token="endorsed" if act is MediationAct.VOUCH else None,
        )
        parsed = parse_mediation_relation(relation)
        assert parsed is not None
        assert parsed.act is act
        assert parsed.case_ref == _CASE


def test_every_response_kind_encodes_and_parses() -> None:
    for kind in MediationResponseKind:
        relation = encode_mediation_relation(
            response_kind=kind,
            case_ref=_CASE,
            revision=0,
            recommendation_ref=_CASE
            if kind is not MediationResponseKind.ACCOUNT
            else None,
            recommendation_revision=0
            if kind is not MediationResponseKind.ACCOUNT
            else None,
            undertaking_token="give_bread",
            terms=("order",) if kind is MediationResponseKind.COUNTERPROPOSE else (),
            accepted_terms=("return_item",)
            if kind is MediationResponseKind.ACCEPT
            else (),
            withdraws_id=_CASE if kind is MediationResponseKind.WITHDRAW else None,
        )
        parsed = parse_mediation_relation(relation)
        assert parsed is not None
        assert parsed.response_kind is kind


def test_every_role_expression_encodes_and_parses() -> None:
    for kind in MediationRoleExpressionKind:
        relation = encode_mediation_relation(
            role_kind=kind,
            case_ref=_CASE,
            revision=0,
            function_token="conflict_mediation",
            context_key=_CONTEXT,
            withdraws_id="e" * 64
            if kind is MediationRoleExpressionKind.WITHDRAW_ROLE_ENDORSEMENT
            else None,
        )
        parsed = parse_mediation_relation(relation)
        assert parsed is not None
        assert parsed.role_kind is kind


def test_actor_is_not_claimable_from_payload() -> None:
    relation = encode_mediation_relation(
        act=MediationAct.MEDIATE, case_ref=_CASE, revision=0
    )
    assert "actor" not in relation.object
    parsed = parse_mediation_relation(relation)
    assert parsed is not None
    assert not hasattr(parsed, "actor_id")


def test_hostile_and_oversized_recipes_are_rejected() -> None:
    with pytest.raises(ValueError):
        encode_mediation_relation(
            act=MediationAct.HEAR_DISPUTE, case_ref="short", revision=0
        )
    with pytest.raises(ValueError):
        encode_mediation_relation(
            act=MediationAct.PROPOSE_COMPROMISE,
            case_ref=_CASE,
            revision=0,
            action_token="give",
            terms=tuple(f"term_{index}" for index in range(4)),
        )
    long_item = "x" * 200
    with pytest.raises(ValueError, match="capacity"):
        encode_mediation_relation(
            act=MediationAct.PROPOSE_COMPROMISE,
            case_ref=_CASE,
            revision=0,
            action_token="give",
            proposed_entity=EntityId("body-ben"),
            item_token=long_item,
            window_first_tick=1,
            window_last_tick=8,
        )
    malformed = CommunicationRelation(
        subject="item_share", predicate="mediation_hear", object="bad"
    )
    assert parse_mediation_relation(malformed) is None


def test_unrelated_conversation_passes_through() -> None:
    command = _talk()
    identical = mediation_communicate_utterance(
        command,
        owner_id=_OWNER,
        tick=1,
        observation=_observation(),
        identity=_identity(),
        ledger=_ledger(),
        mode=object(),
    )
    assert identical is command
    wait = Wait()
    assert (
        mediation_communicate_utterance(
            wait,
            owner_id=_OWNER,
            tick=1,
            observation=_observation(),
            identity=_identity(),
            ledger=_ledger(),
            mode=type("M", (), {"value": "deterministic"})(),
        )
        is wait
    )


def test_marker_relation_is_namespaced() -> None:
    marker = policy_marker_relation()
    assert marker.subject == "mediation"
    assert marker.object == "mediation.v1"


def test_selected_speech_preserves_existing_relations() -> None:
    existing = CommunicationRelation(subject="tool", predicate="name", object="knife")
    command = _talk((existing,))
    decorated = mediation_communicate_utterance(
        command,
        owner_id=_OWNER,
        tick=1,
        observation=_observation(),
        identity=_identity(),
        ledger=_ledger(with_recommendation=True),
        mode=type("M", (), {"value": "deterministic"})(),
    )
    assert isinstance(decorated, Talk)
    assert decorated is not command
    relations = decorated.utterance.content.relations
    assert relations[0] == existing
    assert parse_mediation_relation(relations[1]) is not None
    assert relations[2] == policy_marker_relation()


def test_relation_capacity_returns_command_unchanged() -> None:
    filler = tuple(
        CommunicationRelation(subject="tool", predicate="name", object=f"n{index}")
        for index in range(31)
    )
    command = _talk(filler)
    decorated = mediation_communicate_utterance(
        command,
        owner_id=_OWNER,
        tick=1,
        observation=_observation(),
        identity=_identity(),
        ledger=_ledger(),
        mode=type("M", (), {"value": "deterministic"})(),
    )
    assert decorated is command


def test_explicit_response_recipe_is_selected() -> None:
    parsed = ParsedMediationRelation(
        response_kind=MediationResponseKind.REFUSE,
        case_ref=_CASE,
        revision=0,
    )
    decorated = mediation_communicate_utterance(
        _talk(),
        owner_id=_OWNER,
        tick=1,
        observation=_observation(),
        identity=_identity(),
        ledger=_ledger(),
        mode=type("M", (), {"value": "deterministic"})(),
        parsed=parsed,
    )
    assert isinstance(decorated, Talk)
    assert decorated is not _talk()
    parsed_back = parse_mediation_relation(decorated.utterance.content.relations[0])
    assert parsed_back is not None
    assert parsed_back.response_kind is MediationResponseKind.REFUSE


def test_case_context_key_is_observable_only() -> None:
    assert len(mediation_context_key(_observation())) == 16


def _owner_directed_ledger() -> MediationLedger:
    from dataclasses import replace

    ledger = _ledger(with_recommendation=True)
    recommendation = replace(
        ledger.recommendations[0],
        proposed_actor_id=_OWNER,
        originator_id=_CAROL,
        target_ids=(_BEN,),
    )
    return replace(ledger, recommendations=(recommendation,))


def _appraisal(strength: float) -> object:
    from agents.cognition.mediation import (
        MediationAuthorityAppraisal,
        MediationAuthorityChannel,
        MediationAuthorityComponent,
    )

    return MediationAuthorityAppraisal(
        owner_id=_OWNER,
        mediator_id=_CAROL,
        context_key=_CONTEXT,
        components=(
            MediationAuthorityComponent(
                channel=MediationAuthorityChannel.RELATIONSHIP,
                available=True,
                strength=strength,
                uncertainty=0.1,
            ),
        ),
    )


def _selected_response(
    authority: tuple[object, ...],
) -> ParsedMediationRelation:
    from agents.cognition.configuration import CognitionMediationMode

    command = mediation_communicate_utterance(
        _talk(),
        owner_id=_OWNER,
        tick=1,
        observation=_observation(),
        identity=_identity(),
        ledger=_owner_directed_ledger(),
        mode=CognitionMediationMode.DETERMINISTIC,
        authority=authority,
    )
    assert isinstance(command, Talk)
    relations = command.utterance.content.relations
    parsed = parse_mediation_relation(relations[-2])
    assert parsed is not None
    return parsed


def test_recipient_authority_drives_revision_specific_response() -> None:
    accepted = _selected_response((_appraisal(0.9),))
    assert accepted.response_kind is MediationResponseKind.ACCEPT
    assert accepted.recommendation_revision == 0
    deferred = _selected_response(())
    assert deferred.response_kind is MediationResponseKind.DEFER
    refused = _selected_response((_appraisal(0.1),))
    assert refused.response_kind is MediationResponseKind.REFUSE
    countered = _selected_response((_appraisal(0.4),))
    assert countered.response_kind is MediationResponseKind.COUNTERPROPOSE
    assert countered.terms == ("partial_terms",)


def test_fresh_evidence_selects_hear_request_and_vouch_acts() -> None:
    from dataclasses import replace

    from agents.cognition.configuration import CognitionMediationMode
    from agents.cognition.mediation import MediationAccount

    def select(ledger: MediationLedger) -> ParsedMediationRelation | None:
        command = mediation_communicate_utterance(
            _talk(),
            owner_id=_OWNER,
            tick=1,
            observation=_observation(),
            identity=_identity(),
            ledger=ledger,
            mode=CognitionMediationMode.DETERMINISTIC,
            authority=(_appraisal(0.9),),
        )
        assert isinstance(command, Talk)
        return parse_mediation_relation(command.utterance.content.relations[-2])

    empty_accounts = _ledger()
    heard = select(empty_accounts)
    assert heard is not None and heard.act is MediationAct.HEAR_DISPUTE

    account = MediationAccount(
        account_id="a" * 64,
        owner_id=_OWNER,
        actor_id=_BEN,
        case_ref=_CASE,
        subject_token="item_share",
        claim_token="ben_claim",
        direct=True,
        channel=MediationEvidenceChannel.OBSERVED,
        root_ref="root-ben",
        first_tick=1,
        last_tick=1,
        evidence_id="b" * 64,
    )
    one_account = replace(_ledger(), accounts=(account,))
    requested = select(one_account)
    assert requested is not None and requested.act is MediationAct.REQUEST_ACCOUNTS

    second = replace(
        account, account_id="c" * 64, actor_id=_CAROL, root_ref="root-carol"
    )
    two_accounts = replace(_ledger(), accounts=(account, second))
    vouched = select(two_accounts)
    assert vouched is not None and vouched.act is MediationAct.VOUCH
