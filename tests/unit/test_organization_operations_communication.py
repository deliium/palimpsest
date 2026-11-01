"""Bounded ``org_op_v1`` claims inside existing Talk/Tell speech."""

from __future__ import annotations

import pytest

from agents.cognition import (
    ORGANIZATION_OPERATION_COMMUNICATION_POLICY_VERSION,
    ORGANIZATION_OPERATION_FRAME_SUBJECT,
    ORGANIZATION_OPERATION_PREDICATES,
    OrganizationAdmissionBelief,
    OrganizationAdmissionStance,
    OrganizationAuthorityBasis,
    OrganizationClaim,
    OrganizationControlBelief,
    OrganizationControlStance,
    OrganizationIdentityStance,
    OrganizationOperationAct,
    OrganizationOperationalConcept,
    OrganizationOperationalStatus,
    OrganizationOperationClaim,
    OrganizationOperationDomain,
    OrganizationOperationError,
    OrganizationOperationLedger,
    OrganizationTemporalScope,
    encode_organization_operation_claim,
    organization_operation_claim_relation,
    organization_operation_communicate_utterance,
    parse_organization_claim_relation,
    parse_organization_operation_claim,
    parse_organization_operation_claim_relation,
)
from agents.models import AgentId
from world.actions import Talk, Tell, Wait
from world.communications import (
    CommunicationRelation,
    CommunicationSourceBasis,
    origin_utterance,
)
from world.identifiers import EntityId

pytestmark = pytest.mark.unit

OWNER = AgentId("ada")
ORG = f"orgc-{'a' * 16}"
REF = "b" * 16

_ACT_STANCES = (
    (OrganizationOperationAct.ADMIT, "admitted", 4),
    (OrganizationOperationAct.DEPART, "resigned", None),
    (OrganizationOperationAct.ASSIGN, "assigned", None),
    (OrganizationOperationAct.REMOVE, "removed", None),
    (OrganizationOperationAct.AUTHORIZE_CONTROL, "recognized", None),
    (OrganizationOperationAct.REVOKE_CONTROL, "former", None),
    (OrganizationOperationAct.INVOKE_PROCEDURE, "recognized", None),
    (OrganizationOperationAct.DECLARE_COMMITMENT, "declared", None),
    (OrganizationOperationAct.FULFILL_COMMITMENT, "fulfilled", None),
    (OrganizationOperationAct.RECORD_DECISION, "claimed", None),
)


def _claim(
    act: OrganizationOperationAct,
    stance: str,
    expires: int | None = None,
) -> OrganizationOperationClaim:
    return OrganizationOperationClaim(
        act=act,
        stance=stance,
        target_ref=REF,
        anchor_kind="member",
        anchor_ref=REF,
        authority_ref=REF,
        expires_tick=expires,
    )


def _control() -> OrganizationControlBelief:
    return OrganizationControlBelief(
        domain=OrganizationOperationDomain.RESOURCE_CONTROL,
        anchor_kind="repository",
        anchor_id="repository-beta",
        stance=OrganizationControlStance.RECOGNIZED,
        authority_basis=OrganizationAuthorityBasis.OBSERVATION,
        legitimacy_doctrine="shared_use",
        decision_ref=None,
        role_ref=None,
        first_tick=1,
        last_tick=4,
        owner_support_count=1,
        contest_count=0,
        evidence_refs=("ev-1",),
    )


def _admission(
    stance: OrganizationAdmissionStance = OrganizationAdmissionStance.CLAIMED,
) -> OrganizationAdmissionBelief:
    return OrganizationAdmissionBelief(
        member_id="body-ben",
        stance=stance,
        authority_basis=OrganizationAuthorityBasis.SELF_AUTHORED,
        role_ref=None,
        decision_ref=None,
        temporal_scope=OrganizationTemporalScope.ONGOING,
        expires_tick=None,
        first_tick=1,
        last_tick=4,
        owner_support_count=1,
        contest_count=0,
        evidence_refs=("ev-1",),
    )


def _ledger(
    *,
    controls: tuple[OrganizationControlBelief, ...] = (),
    admissions: tuple[OrganizationAdmissionBelief, ...] = (),
) -> OrganizationOperationLedger:
    concept = OrganizationOperationalConcept(
        organization_id=ORG,
        owner_id=OWNER,
        status=OrganizationOperationalStatus.ACTIVE,
        first_tick=1,
        last_tick=4,
        controls=controls,
        admissions=admissions,
    )
    return OrganizationOperationLedger(owner_id=OWNER, concepts=(concept,))


def _talk(relations: tuple[CommunicationRelation, ...] = ()) -> Talk:
    return Talk(
        recipient_id=EntityId("body-ben"),
        utterance=origin_utterance(
            text="hello",
            speaker_id=EntityId("body-ada"),
            communication_id="talk-op-1",
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
            communication_id="tell-op-1",
            relations=relations,
            source_basis=CommunicationSourceBasis.UNREFERENCED,
        ),
    )


def test_policy_version_and_predicates_are_frozen() -> None:
    assert (
        ORGANIZATION_OPERATION_COMMUNICATION_POLICY_VERSION
        == "organization-operations-communication.v1"
    )
    assert ORGANIZATION_OPERATION_FRAME_SUBJECT == "org_op_v1"
    assert ORGANIZATION_OPERATION_PREDICATES == {
        OrganizationOperationAct.ADMIT: "org_admit",
        OrganizationOperationAct.DEPART: "org_depart",
        OrganizationOperationAct.ASSIGN: "org_assign",
        OrganizationOperationAct.REMOVE: "org_remove",
        OrganizationOperationAct.AUTHORIZE_CONTROL: "org_authorize",
        OrganizationOperationAct.REVOKE_CONTROL: "org_revoke",
        OrganizationOperationAct.INVOKE_PROCEDURE: "org_invoke",
        OrganizationOperationAct.DECLARE_COMMITMENT: "org_commit",
        OrganizationOperationAct.FULFILL_COMMITMENT: "org_fulfill",
        OrganizationOperationAct.RECORD_DECISION: "org_record",
    }


@pytest.mark.parametrize(("act", "stance", "expires"), _ACT_STANCES)
def test_every_act_stance_round_trips(
    act: OrganizationOperationAct, stance: str, expires: int | None
) -> None:
    claim = _claim(act, stance, expires)
    frame = encode_organization_operation_claim(claim)
    assert frame.count(":") == 8
    assert frame.startswith(f"{ORGANIZATION_OPERATION_FRAME_SUBJECT}:")
    assert parse_organization_operation_claim(frame) == claim

    relation = organization_operation_claim_relation(claim)
    assert parse_organization_operation_claim_relation(relation) == claim


def test_malformed_frames_fail_closed() -> None:
    good = encode_organization_operation_claim(
        _claim(OrganizationOperationAct.ADMIT, "admitted", 4)
    )
    malformed = (
        good.replace(ORGANIZATION_OPERATION_FRAME_SUBJECT, "org_v1", 1),
        good.replace(":org_admit:", ":org_unknown:", 1),
        good.rsplit(":", 1)[0],
        good + ":extra",
        good.replace(":admitted:", ":resigned:", 1),
        "x" * 257,
        good.replace(":admitted:", ":admitted :", 1),
        good.replace(REF, "NOTHEX", 1),
        good.replace(":4", ":negative"),
    )
    for frame in malformed:
        with pytest.raises(OrganizationOperationError):
            parse_organization_operation_claim(frame)


def test_expiry_is_legal_only_for_admission() -> None:
    with pytest.raises(OrganizationOperationError):
        OrganizationOperationClaim(
            act=OrganizationOperationAct.DEPART,
            stance="resigned",
            target_ref=REF,
            anchor_kind="member",
            anchor_ref=REF,
            expires_tick=4,
        )

    with pytest.raises(OrganizationOperationError):
        parse_organization_operation_claim(
            "org_op_v1:org_depart:none:none:unknown:none:none:resigned:4"
        )


def test_wrong_act_family_stance_fails_closed() -> None:
    with pytest.raises(OrganizationOperationError):
        OrganizationOperationClaim(
            act=OrganizationOperationAct.ADMIT,
            stance="resigned",
            target_ref=REF,
            anchor_kind="member",
            anchor_ref=REF,
        )

    with pytest.raises(OrganizationOperationError):
        OrganizationOperationClaim(
            act=OrganizationOperationAct.RECORD_DECISION,
            stance="admitted",
            anchor_kind="unknown",
        )


def test_unknown_anchor_forbids_anchor_ref() -> None:
    with pytest.raises(OrganizationOperationError):
        OrganizationOperationClaim(
            act=OrganizationOperationAct.INVOKE_PROCEDURE,
            stance="recognized",
            anchor_kind="unknown",
            anchor_ref=REF,
        )

    with pytest.raises(OrganizationOperationError):
        OrganizationOperationClaim(
            act=OrganizationOperationAct.INVOKE_PROCEDURE,
            stance="recognized",
            anchor_kind="repository",
            anchor_ref=None,
        )


def test_unrelated_relations_return_none() -> None:
    unrelated = CommunicationRelation(
        subject="ordinary", predicate="greeting", object="hello"
    )
    assert parse_organization_operation_claim_relation(unrelated) is None
    assert parse_organization_claim_relation(unrelated) is None

    operation = organization_operation_claim_relation(
        _claim(OrganizationOperationAct.INVOKE_PROCEDURE, "recognized")
    )
    assert parse_organization_claim_relation(operation) is None

    concept_claim = OrganizationClaim(
        predicate="organization_claim",
        stance=OrganizationIdentityStance.MEMBER,
    )
    org_relation = CommunicationRelation(
        subject="org_v1",
        predicate=concept_claim.predicate,
        object="none:member:none",
    )
    assert parse_organization_operation_claim_relation(org_relation) is None
    assert (
        parse_organization_claim_relation(
            CommunicationRelation(
                subject="org_v1",
                predicate="organization_claim",
                object="broken",
            )
        )
        is None
    )


def test_decorator_preserves_class_recipient_and_existing_relations() -> None:
    existing = CommunicationRelation(subject="a", predicate="b", object="c")
    for command in (_talk((existing,)), _tell((existing,))):
        decorated = organization_operation_communicate_utterance(
            command, _ledger(controls=(_control(),))
        )
        assert type(decorated) is type(command)
        assert decorated.recipient_id == command.recipient_id
        assert len(decorated.utterance.content.relations) == 2
        assert decorated.utterance.content.relations[0] == existing
        assert (
            decorated.utterance.content.relations[1].subject
            == ORGANIZATION_OPERATION_FRAME_SUBJECT
        )


def test_decorator_is_a_noop_for_wait_and_disabled_ledgers() -> None:
    wait = Wait()
    assert organization_operation_communicate_utterance(wait, _ledger()) is wait
    talk = _talk()
    assert organization_operation_communicate_utterance(talk, None) is talk
    assert organization_operation_communicate_utterance(talk, object()) is talk


def test_existing_operation_relation_prevents_a_second_one() -> None:
    relation = organization_operation_claim_relation(
        _claim(OrganizationOperationAct.INVOKE_PROCEDURE, "recognized")
    )
    command = _talk((relation,))
    decorated = organization_operation_communicate_utterance(
        command, _ledger(controls=(_control(),))
    )
    assert decorated is command


def test_relation_cap_prevents_attachment() -> None:
    relations = tuple(
        CommunicationRelation(subject="a", predicate=f"p{index}", object="c")
        for index in range(32)
    )
    command = _talk(relations)
    decorated = organization_operation_communicate_utterance(
        command, _ledger(controls=(_control(),))
    )
    assert decorated is command


def test_selector_prefers_disputed_then_unresolved() -> None:
    disputed = _ledger(
        admissions=(
            _admission(OrganizationAdmissionStance.DISPUTED),
            _admission(OrganizationAdmissionStance.CLAIMED),
        )
    )
    relation = organization_operation_claim_relation(
        _claim(OrganizationOperationAct.ADMIT, "admitted", 4)
    )
    command = _talk((relation,))
    assert organization_operation_communicate_utterance(command, disputed) is command

    unresolved = _ledger(admissions=(_admission(),))
    decorated = organization_operation_communicate_utterance(_talk(), unresolved)
    claim = parse_organization_operation_claim_relation(
        decorated.utterance.content.relations[-1]
    )
    assert claim is not None
    assert claim.act is OrganizationOperationAct.ADMIT
    assert claim.stance == "claimed"


def test_no_claim_returns_command_unchanged() -> None:
    command = _talk()
    assert (
        organization_operation_communicate_utterance(command, _ledger()) is command
    )
