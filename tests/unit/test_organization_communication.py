"""Bounded ``org_v1`` claims over existing Talk/Tell speech."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from agents.cognition import (
    ORGANIZATION_COMMUNICATION_POLICY_VERSION,
    ORGANIZATION_FRAME_SUBJECT,
    ORGANIZATION_PREDICATES,
    OrganizationClaim,
    OrganizationClaimError,
    OrganizationConceptLedger,
    OrganizationConceptualization,
    OrganizationEvidenceChannel,
    OrganizationGoalBelief,
    OrganizationGoalKind,
    OrganizationIdentityBelief,
    OrganizationIdentityStance,
    OrganizationLineageKind,
    OrganizationLineageRecord,
    OrganizationMemberBelief,
    OrganizationMembershipBasis,
    OrganizationMembershipStatus,
    OrganizationStatus,
    OrganizationTemporalScope,
    encode_organization_claim,
    organization_claim_relation,
    organization_communicate_utterance,
    organization_concept_id,
    organization_lineage_id,
    parse_organization_claim,
    parse_organization_claim_relation,
)
from agents.models import AgentId
from world.actions import Give, Talk, Tell, Wait
from world.communications import (
    CommunicationRelation,
    CommunicationSourceBasis,
    origin_utterance,
)
from world.identifiers import EntityId

pytestmark = pytest.mark.unit

OWNER = AgentId("ada")
TICK = 7
DIGEST = hashlib.sha256(b"comm").hexdigest()
EDGE_DIGEST = hashlib.sha256(b"comm-edge").hexdigest()


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


def _tell(relations: tuple[CommunicationRelation, ...] = ()) -> Tell:
    return Tell(
        recipient_id=EntityId("body-ben"),
        utterance=origin_utterance(
            text="testimony",
            speaker_id=EntityId("body-ada"),
            communication_id="tell-1",
            relations=relations,
            source_basis=CommunicationSourceBasis.UNREFERENCED,
        ),
    )


def _identity(
    *,
    stance: OrganizationIdentityStance = OrganizationIdentityStance.MEMBER,
    token: str | None = "water-carriers",
    status: OrganizationStatus = OrganizationStatus.CANDIDATE,
) -> OrganizationConceptLedger:
    member = OrganizationMemberBelief(
        member_id="ada",
        status=(
            OrganizationMembershipStatus.DISPUTED
            if status is OrganizationStatus.DISPUTED
            else OrganizationMembershipStatus.EXPLICIT
        ),
        basis=OrganizationMembershipBasis.SELF_IDENTIFICATION,
        temporal_scope=OrganizationTemporalScope.ONGOING,
        first_tick=1,
        last_tick=TICK,
        strength=0.6,
        channels=(OrganizationEvidenceChannel.COMMUNICATED,),
        independently_evidenced=True,
    )
    organization_id = organization_concept_id(
        OWNER.value, 1, (member.member_id,), ("anchor-1",)
    )
    lineage = OrganizationLineageRecord(
        lineage_id=organization_lineage_id(
            OWNER.value, "emerged", 1, (organization_id,), (organization_id,)
        ),
        kind=OrganizationLineageKind.EMERGED,
        tick=1,
        from_ids=(organization_id,),
        to_ids=(organization_id,),
        evidence_digest=EDGE_DIGEST,
    )
    from agents.cognition import OrganizationConcept

    concept = OrganizationConcept(
        organization_id=organization_id,
        owner_id=OWNER,
        creation_tick=1,
        inception_digest=DIGEST,
        status=status,
        temporal_scope=OrganizationTemporalScope.ONGOING,
        strength=0.6,
        member_evidence_count=3,
        structural_channel_count=2,
        first_tick=1,
        last_tick=TICK,
        members=(member,),
        goals=(
            OrganizationGoalBelief(
                anchor_kind=OrganizationGoalKind.COLLECTIVE_PROJECT,
                anchor_id="project-1",
                status=OrganizationStatus.RECOGNIZED,
                first_tick=1,
                last_tick=TICK,
            ),
        ),
        identities=(
            OrganizationIdentityBelief(
                label_token=token,
                conceptualization=(
                    OrganizationConceptualization.NONE
                    if token is None
                    else OrganizationConceptualization.NAMED_CUSTOM
                ),
                stance=stance,
                first_tick=1,
                last_tick=TICK,
            ),
        ),
        lineage=(lineage,),
    )
    return OrganizationConceptLedger(owner_id=OWNER, concepts=(concept,))


def test_policy_and_predicates_are_frozen() -> None:
    assert ORGANIZATION_COMMUNICATION_POLICY_VERSION == (
        "organization-communication.v1"
    )
    assert ORGANIZATION_FRAME_SUBJECT == "org_v1"
    assert ORGANIZATION_PREDICATES == (
        "organization_claim",
        "organization_affirm",
        "organization_dispute",
        "organization_leave",
    )


@pytest.mark.parametrize("predicate", ORGANIZATION_PREDICATES)
@pytest.mark.parametrize(
    "stance",
    (
        OrganizationIdentityStance.MEMBER,
        OrganizationIdentityStance.AFFILIATED,
        OrganizationIdentityStance.OUTSIDE,
        OrganizationIdentityStance.UNKNOWN,
    ),
)
def test_encode_parse_round_trip(
    predicate: str, stance: OrganizationIdentityStance
) -> None:
    claim = OrganizationClaim(
        predicate=predicate,
        stance=stance,
        label_token="water-carriers",
        expires_tick=None if stance is OrganizationIdentityStance.OUTSIDE else 40,
    )
    frame = encode_organization_claim(claim)
    assert frame.startswith("org_v1:")
    parsed = parse_organization_claim(frame)
    assert parsed == claim

    relation = organization_claim_relation(claim)
    assert relation.subject == ORGANIZATION_FRAME_SUBJECT
    assert relation.predicate == predicate
    assert parse_organization_claim_relation(relation) == claim


def test_claim_accepts_none_tokens() -> None:
    claim = OrganizationClaim(
        predicate="organization_affirm",
        stance=OrganizationIdentityStance.UNKNOWN,
    )
    frame = encode_organization_claim(claim)
    assert frame == "org_v1:organization_affirm:none:unknown:none"
    assert parse_organization_claim(frame) == claim


@pytest.mark.parametrize(
    "text",
    (
        "",
        "org_v1:organization_claim:none:member",
        "org_v2:organization_claim:none:member:none",
        "org_v1:organization_unknown:none:member:none",
        "org_v1:organization_claim:none:leader:none",
        "org_v1:organization_claim:none:member:soon",
        "org_v1:organization_claim:none:member:-1",
        "org_v1:organization_claim:Water Carriers:member:none",
        "org_v1:organization_claim:government:member:none",
        "org_v1:organization_claim:" + "a" * 33 + ":member:none",
        "org_v1:organization_claim:none:member:none\nextra",
        "org_v1:organization_claim:none:member:none:extra",
        "organization_claim:none:member:none",
    ),
)
def test_malformed_frames_fail_closed(text: str) -> None:
    with pytest.raises(OrganizationClaimError) as excinfo:
        parse_organization_claim(text)
    assert excinfo.value.code == "organization_invalid_claim"
    assert str(excinfo.value) == "organization_invalid_claim"


def test_claim_rejects_invalid_values() -> None:
    with pytest.raises(OrganizationClaimError):
        OrganizationClaim(
            predicate="organization_unknown", stance=(OrganizationIdentityStance.MEMBER)
        )
    with pytest.raises(OrganizationClaimError):
        OrganizationClaim(
            predicate="organization_claim",
            stance=OrganizationIdentityStance.OUTSIDE,
            expires_tick=10,
        )
    with pytest.raises(OrganizationClaimError):
        OrganizationClaim(
            predicate="organization_claim",
            stance="member",  # type: ignore[arg-type]
        )


def test_unrelated_relations_are_ignored() -> None:
    relation = CommunicationRelation(
        subject="elsewhere", predicate="unrelated", object="value"
    )
    assert parse_organization_claim_relation(relation) is None
    assert organization_communicate_utterance(_talk(), None) == _talk()
    assert (
        organization_communicate_utterance(
            _talk(), OrganizationConceptLedger(owner_id=OWNER)
        )
        == _talk()
    )


def test_utterance_decoration_preserves_command_and_existing_relations() -> None:
    existing = CommunicationRelation(
        subject="weather", predicate="raining", object="light"
    )
    command = _talk((existing,))
    decorated = organization_communicate_utterance(command, _identity())
    assert type(decorated) is Talk
    assert decorated.recipient_id == command.recipient_id
    relations = decorated.utterance.content.relations
    assert existing in relations
    claims = [
        parse_organization_claim_relation(relation)
        for relation in relations
        if relation.subject == ORGANIZATION_FRAME_SUBJECT
    ]
    assert len(claims) == 1
    assert claims[0] is not None
    assert claims[0].predicate == "organization_claim"
    assert claims[0].stance is OrganizationIdentityStance.MEMBER
    assert decorated.utterance.content.text == command.utterance.content.text
    assert decorated.utterance.declared == command.utterance.declared

    # At most one organization relation is ever attached.
    again = organization_communicate_utterance(decorated, _identity())
    assert again == decorated


def test_tell_is_decorated_and_other_commands_are_untouched() -> None:
    assert organization_communicate_utterance(_tell(), _identity()) != _tell()

    wait = Wait()
    assert organization_communicate_utterance(wait, _identity()) == wait

    give = Give(
        recipient_id=EntityId("body-ben"),
        item_id=EntityId("item-1"),
    )
    assert organization_communicate_utterance(give, _identity()) == give


def test_dispute_and_leave_predicates_are_selected() -> None:
    disputed = organization_communicate_utterance(
        _talk(), _identity(status=OrganizationStatus.DISPUTED)
    )
    dispute_claims = [
        parse_organization_claim_relation(relation)
        for relation in disputed.utterance.content.relations
    ]
    assert dispute_claims[0] is not None
    assert dispute_claims[0].predicate == "organization_dispute"

    leaving = organization_communicate_utterance(
        _talk(), _identity(stance=OrganizationIdentityStance.OUTSIDE)
    )
    leave_claims = [
        parse_organization_claim_relation(relation)
        for relation in leaving.utterance.content.relations
    ]
    assert leave_claims[0] is not None
    assert leave_claims[0].predicate == "organization_leave"
    assert leave_claims[0].stance is OrganizationIdentityStance.OUTSIDE


def test_no_new_command_class_exists() -> None:
    from agents.cognition import organization_communication

    source = Path(organization_communication.__file__).read_text(encoding="utf-8")
    assert "class OrganizationCommand" not in source
    assert "AgentCommand" not in source
