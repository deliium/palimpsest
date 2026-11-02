"""Bounded ``org_ca_v1`` collective-agency claims over Talk/Tell."""

from __future__ import annotations

from typing import cast

import pytest

from agents.cognition import (
    ORGANIZATION_AGENCY_COMMUNICATION_POLICY_VERSION,
    ORGANIZATION_AGENCY_FRAME_SUBJECT,
    ORGANIZATION_AGENCY_PREDICATES,
    OrganizationAgencyAct,
    OrganizationAgencyClaim,
    OrganizationAgencyConcept,
    OrganizationAgencyEffect,
    OrganizationAgencyError,
    OrganizationAgencyLedger,
    OrganizationAgencyProposalStatus,
    OrganizationAgencyReportKind,
    OrganizationOperationDomain,
    OrganizationStatus,
    encode_organization_agency_claim,
    organization_agency_claim_relation,
    organization_agency_communicate_utterance,
    parse_organization_agency_claim,
    parse_organization_agency_claim_relation,
)
from tests.unit.organization_agency_helpers import (
    OWNER,
    concept_id,
    concept_ledger,
    proposal,
)
from world.actions import Give, Talk, Tell, Wait
from world.communications import (
    CommunicationRelation,
    CommunicationSourceBasis,
    origin_utterance,
)
from world.identifiers import EntityId

pytestmark = pytest.mark.unit

_REF = "a" * 16
_TERMS = "b" * 16


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


def _claim(act: OrganizationAgencyAct) -> OrganizationAgencyClaim:
    if act is OrganizationAgencyAct.PROPOSE:
        return OrganizationAgencyClaim(
            act=act,
            proposal_ref=_REF,
            revision=1,
            domain=OrganizationOperationDomain.PROCEDURE_ACTION,
            effect=OrganizationAgencyEffect.NONE,
            terms_ref=_TERMS,
        )
    if act is OrganizationAgencyAct.AMEND:
        return OrganizationAgencyClaim(
            act=act,
            proposal_ref=_REF,
            revision=2,
            domain=OrganizationOperationDomain.PROCEDURE_ACTION,
            effect=OrganizationAgencyEffect.NONE,
            terms_ref=_TERMS,
        )
    if act is OrganizationAgencyAct.SUPPORT:
        return OrganizationAgencyClaim(
            act=act, proposal_ref=_REF, revision=1, stance="support"
        )
    if act is OrganizationAgencyAct.OPPOSE:
        return OrganizationAgencyClaim(
            act=act, proposal_ref=_REF, revision=1, stance="oppose"
        )
    if act is OrganizationAgencyAct.ABSTAIN:
        return OrganizationAgencyClaim(
            act=act, proposal_ref=_REF, revision=1, stance="abstain"
        )
    if act is OrganizationAgencyAct.WITHDRAW:
        return OrganizationAgencyClaim(
            act=act, proposal_ref=_REF, revision=1, stance="withdraw"
        )
    if act is OrganizationAgencyAct.RECOGNIZE:
        return OrganizationAgencyClaim(
            act=act,
            proposal_ref=_REF,
            revision=1,
            stance="recognized",
            procedure_ref="c" * 16,
        )
    if act is OrganizationAgencyAct.REFUSE:
        return OrganizationAgencyClaim(
            act=act, proposal_ref=_REF, revision=1, stance="refuse"
        )
    return OrganizationAgencyClaim(
        act=act,
        proposal_ref=_REF,
        revision=1,
        report_kind=OrganizationAgencyReportKind.IMPLEMENTED,
    )


def test_policy_subject_and_predicates_are_frozen() -> None:
    assert ORGANIZATION_AGENCY_COMMUNICATION_POLICY_VERSION == (
        "organization-agency-communication.v1"
    )
    assert ORGANIZATION_AGENCY_FRAME_SUBJECT == "org_ca_v1"
    assert tuple(ORGANIZATION_AGENCY_PREDICATES.values()) == (
        "org_ca_propose",
        "org_ca_support",
        "org_ca_oppose",
        "org_ca_abstain",
        "org_ca_amend",
        "org_ca_withdraw",
        "org_ca_recognize",
        "org_ca_refuse",
        "org_ca_report",
    )


@pytest.mark.parametrize("act", tuple(OrganizationAgencyAct))
def test_each_predicate_round_trips(act: OrganizationAgencyAct) -> None:
    claim = _claim(act)
    encoded = encode_organization_agency_claim(claim)
    assert len(encoded.split(":")) == 11
    assert parse_organization_agency_claim(encoded) == claim


@pytest.mark.parametrize(
    "frame",
    [
        "org_ca_v1:org_ca_support:" + ":".join([_REF] * 8),
        "org_ca_v1:org_ca_support:" + ":".join([_REF] * 10),
    ],
)
def test_wrong_field_count_is_rejected(frame: str) -> None:
    with pytest.raises(OrganizationAgencyError):
        parse_organization_agency_claim(frame)


def test_whitespace_control_and_length_are_bounded() -> None:
    for frame in (
        "org_ca_v1:org_ca_support: "
        + _REF
        + ":none:none:none:none:1:none:support:none",
        "org_ca_v1:org_ca_support:\x01"
        + _REF
        + ":none:none:none:none:1:none:support:none",
        "org_ca_v1:" + "x" * 400,
    ):
        with pytest.raises(OrganizationAgencyError):
            parse_organization_agency_claim(frame)


def test_bad_ref_revision_stance_and_report_are_rejected() -> None:
    with pytest.raises(OrganizationAgencyError):
        OrganizationAgencyClaim(
            act=OrganizationAgencyAct.SUPPORT,
            proposal_ref="zz",
            revision=1,
            stance="support",
        )
    with pytest.raises(OrganizationAgencyError):
        OrganizationAgencyClaim(
            act=OrganizationAgencyAct.SUPPORT,
            proposal_ref=_REF,
            revision=0,
            stance="support",
        )
    with pytest.raises(OrganizationAgencyError):
        OrganizationAgencyClaim(
            act=OrganizationAgencyAct.SUPPORT,
            proposal_ref=_REF,
            revision=1,
            stance="oppose",
        )
    with pytest.raises(OrganizationAgencyError):
        OrganizationAgencyClaim(
            act=OrganizationAgencyAct.REPORT,
            proposal_ref=_REF,
            revision=1,
            report_kind="unknown",  # type: ignore[arg-type]
        )


def test_effect_outside_domain_is_rejected() -> None:
    with pytest.raises(OrganizationAgencyError):
        OrganizationAgencyClaim(
            act=OrganizationAgencyAct.PROPOSE,
            proposal_ref=_REF,
            revision=1,
            terms_ref=_TERMS,
            domain=OrganizationOperationDomain.MEMBERSHIP_ADMISSION,
            effect=OrganizationAgencyEffect.GIVE,
        )


def test_relation_parser_ignores_other_frames_and_malformed_atoms() -> None:
    assert (
        parse_organization_agency_claim_relation(
            CommunicationRelation(
                subject="org_v1", predicate="organization_claim", object=_REF
            )
        )
        is None
    )
    assert (
        parse_organization_agency_claim_relation(
            CommunicationRelation(
                subject="org_op_v1", predicate="org_admit", object=_REF
            )
        )
        is None
    )
    assert (
        parse_organization_agency_claim_relation(
            CommunicationRelation(subject="unrelated", predicate="x", object="y")
        )
        is None
    )
    assert (
        parse_organization_agency_claim_relation(
            CommunicationRelation(
                subject="org_ca_v1", predicate="org_ca_support", object="broken"
            )
        )
        is None
    )


def test_relation_round_trips() -> None:
    claim = _claim(OrganizationAgencyAct.SUPPORT)
    relation = organization_agency_claim_relation(claim)
    assert relation.subject == "org_ca_v1"
    assert parse_organization_agency_claim_relation(relation) == claim


def _ledger_with_proposal() -> OrganizationAgencyLedger:
    concepts = concept_ledger()
    organization_id = concept_id(concepts)
    active = proposal(
        organization_id=organization_id,
        status=OrganizationAgencyProposalStatus.ACTIVE,
    )
    return OrganizationAgencyLedger(
        owner_id=OWNER,
        concepts=(
            OrganizationAgencyConcept(
                organization_id=organization_id,
                owner_id=OWNER,
                status=OrganizationStatus.RECOGNIZED,
                first_tick=1,
                last_tick=5,
                proposals=(active,),
            ),
        ),
    )


def test_communicate_preserves_command_and_adds_one_relation() -> None:
    command = _talk()
    updated = organization_agency_communicate_utterance(
        command, _ledger_with_proposal()
    )
    assert type(updated) is Talk
    assert updated.recipient_id == command.recipient_id
    assert updated.utterance.declared == command.utterance.declared
    assert updated.utterance.content.text == command.utterance.content.text
    relations = updated.utterance.content.relations
    assert len(relations) == 1
    assert relations[0].subject == "org_ca_v1"


def test_tell_is_preserved() -> None:
    tell = Tell(
        recipient_id=EntityId("body-ben"),
        utterance=origin_utterance(
            text="testimony",
            speaker_id=EntityId("body-ada"),
            communication_id="tell-1",
            source_basis=CommunicationSourceBasis.UNREFERENCED,
        ),
    )
    updated = cast(
        Tell, organization_agency_communicate_utterance(tell, _ledger_with_proposal())
    )
    assert type(updated) is Tell


def test_non_speech_commands_are_untouched() -> None:
    for command in (
        Wait(),
        Give(item_id=EntityId("item-1"), recipient_id=EntityId("body-ben")),
    ):
        assert (
            organization_agency_communicate_utterance(command, _ledger_with_proposal())
            is command
        )


def test_existing_agency_relation_blocks_decoration() -> None:
    claim = _claim(OrganizationAgencyAct.SUPPORT)
    command = _talk((organization_agency_claim_relation(claim),))
    updated = cast(
        Talk,
        organization_agency_communicate_utterance(command, _ledger_with_proposal()),
    )
    assert len(updated.utterance.content.relations) == 1


def test_relation_cap_fails_closed() -> None:
    relations = tuple(
        CommunicationRelation(subject=f"other-{index}", predicate="p", object="o")
        for index in range(32)
    )
    command = _talk(relations)
    updated = cast(
        Talk,
        organization_agency_communicate_utterance(command, _ledger_with_proposal()),
    )
    assert len(updated.utterance.content.relations) == 32


def test_encoded_frame_has_no_owner_or_local_ids() -> None:
    for act in OrganizationAgencyAct:
        encoded = encode_organization_agency_claim(_claim(act))
        assert OWNER.value not in encoded
        assert "orgc-" not in encoded
        assert "orgp-" not in encoded
        assert "body-" not in encoded
