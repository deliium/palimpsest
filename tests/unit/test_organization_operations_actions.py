"""Closed command classification and commitment follow-through recognition."""

from __future__ import annotations

import pytest

from agents.cognition import (
    ORGANIZATION_DOMAIN_COMMANDS,
    OrganizationAdmissionBelief,
    OrganizationAdmissionStance,
    OrganizationAuthorityBasis,
    OrganizationCommitmentOperationBelief,
    OrganizationCommitmentRole,
    OrganizationCommitmentStance,
    OrganizationConcept,
    OrganizationConceptLedger,
    OrganizationConceptualization,
    OrganizationControlBelief,
    OrganizationControlStance,
    OrganizationIdentityBelief,
    OrganizationIdentityStance,
    OrganizationOperationAct,
    OrganizationOperationalConcept,
    OrganizationOperationalStatus,
    OrganizationOperationClaim,
    OrganizationOperationDomain,
    OrganizationOperationLedger,
    OrganizationOperationOutcome,
    OrganizationProcedureActionBelief,
    OrganizationStatus,
    OrganizationTemporalScope,
    organization_commitment_follow_through,
    organization_communicate_utterance,
    organization_domain_allows,
    organization_operation_claim_relation,
    organization_operation_command_support,
    organization_operation_communicate_utterance,
    parse_organization_claim_relation,
    parse_organization_operation_claim_relation,
)
from agents.models import AgentId
from tests.unit.test_organization_operations_communication import _talk
from world._rules import COMMAND_RULE_MATRIX
from world.actions import (
    Amend,
    AnnotateRecord,
    Build,
    ContributeCollectiveProject,
    CopyRecord,
    DepositRecord,
    Drop,
    EstablishRepository,
    Give,
    Help,
    Inscribe,
    MaintainPublicGood,
    MaintainRepository,
    Repair,
    RetrieveRecord,
    Store,
    Take,
    Talk,
    TransferArtifact,
    Wait,
)
from world.identifiers import EntityId

pytestmark = pytest.mark.unit

OWNER = AgentId("agent-1")
OWNER_ENTITY = "body-owner"
ORG = f"orgc-{'a' * 16}"


def _control(
    domain: OrganizationOperationDomain = (
        OrganizationOperationDomain.RESOURCE_CONTROL
    ),
    anchor_id: str = "item-1",
) -> OrganizationControlBelief:
    return OrganizationControlBelief(
        domain=domain,
        anchor_kind="item",
        anchor_id=anchor_id,
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


def _admission(member_id: str = "body-peer") -> OrganizationAdmissionBelief:
    return OrganizationAdmissionBelief(
        member_id=member_id,
        stance=OrganizationAdmissionStance.ADMITTED,
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


def _procedure() -> OrganizationProcedureActionBelief:
    return OrganizationProcedureActionBelief(
        procedure_ref="procedure-1",
        command_kind="maintain_repository",
        actor_id=OWNER_ENTITY,
        outcome=OrganizationOperationOutcome.COMPLETED,
        authority_basis=OrganizationAuthorityBasis.PROCEDURE_BELIEF,
        decision_ref=None,
        first_tick=1,
        last_tick=4,
        owner_support_count=1,
        contest_count=0,
        evidence_refs=("ev-1",),
    )


def _commitment(
    counterpart_id: str = "body-peer",
    stance: OrganizationCommitmentStance = OrganizationCommitmentStance.DECLARED,
) -> OrganizationCommitmentOperationBelief:
    return OrganizationCommitmentOperationBelief(
        commitment_id="commitment-1",
        role=OrganizationCommitmentRole.DEBTOR,
        counterpart_id=counterpart_id,
        stance=stance,
        authority_basis=OrganizationAuthorityBasis.UNKNOWN,
        decision_ref=None,
        due_tick=None,
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
    procedures: tuple[OrganizationProcedureActionBelief, ...] = (),
    commitments: tuple[OrganizationCommitmentOperationBelief, ...] = (),
) -> OrganizationOperationLedger:
    concept = OrganizationOperationalConcept(
        organization_id=ORG,
        owner_id=OWNER,
        status=OrganizationOperationalStatus.ACTIVE,
        first_tick=1,
        last_tick=4,
        controls=controls,
        admissions=admissions,
        procedures=procedures,
        commitments=commitments,
    )
    return OrganizationOperationLedger(owner_id=OWNER, concepts=(concept,))


def test_every_domain_maps_only_to_existing_world_actions() -> None:
    import world.actions as actions_module

    assert len(COMMAND_RULE_MATRIX) == 43
    referenced: set[type] = set()
    for domain, commands in ORGANIZATION_DOMAIN_COMMANDS.items():
        assert type(domain) is OrganizationOperationDomain
        for command in commands:
            assert getattr(actions_module, command.__name__, None) is command
            referenced.add(command)
    assert len(referenced) <= 43


def test_domain_allowlist_is_closed() -> None:
    controls = ORGANIZATION_DOMAIN_COMMANDS[
        OrganizationOperationDomain.RESOURCE_CONTROL
    ]
    assert controls == (
        Give,
        Take,
        Drop,
        Store,
    )
    assert ORGANIZATION_DOMAIN_COMMANDS[OrganizationOperationDomain.STORAGE] == (
        Store,
        Take,
        DepositRecord,
        RetrieveRecord,
    )
    record_keeping = ORGANIZATION_DOMAIN_COMMANDS[
        OrganizationOperationDomain.RECORD_KEEPING
    ]
    assert record_keeping == (
        Inscribe,
        Amend,
        CopyRecord,
        AnnotateRecord,
        TransferArtifact,
        DepositRecord,
    )
    procedure_actions = ORGANIZATION_DOMAIN_COMMANDS[
        OrganizationOperationDomain.PROCEDURE_ACTION
    ]
    assert procedure_actions == (
        Help,
        ContributeCollectiveProject,
        MaintainPublicGood,
        MaintainRepository,
        EstablishRepository,
        Build,
        Repair,
    )
    assert organization_domain_allows(
        OrganizationOperationDomain.PROCEDURE_ACTION, Help(EntityId("body-peer"))
    )
    assert not organization_domain_allows(
        OrganizationOperationDomain.PROCEDURE_ACTION, Wait()
    )
    assert organization_domain_allows(
        OrganizationOperationDomain.MEMBERSHIP_ADMISSION, _talk()
    )
    assert organization_domain_allows(
        OrganizationOperationDomain.RESOURCE_CONTROL, Give(
            recipient_id=EntityId("body-peer"), item_id=EntityId("item-1")
        )
    )


def test_domain_allows_rejects_unknown_domain() -> None:
    with pytest.raises(TypeError):
        organization_domain_allows("resource_control", Wait())  # type: ignore[arg-type]


def test_command_support_returns_active_domains() -> None:
    ledger = _ledger(
        controls=(
            _control(OrganizationOperationDomain.RESOURCE_CONTROL, "item-1"),
            _control(OrganizationOperationDomain.STORAGE, "structure-1"),
            _control(OrganizationOperationDomain.RECORD_KEEPING, "artifact-1"),
        ),
        admissions=(_admission("body-ben"),),
        procedures=(_procedure(),),
        commitments=(_commitment(),),
    )
    give = Give(recipient_id=EntityId("body-peer"), item_id=EntityId("item-1"))
    store = object.__new__(Store)
    inscribe = object.__new__(Inscribe)
    wait = Wait()

    give_domains = organization_operation_command_support(ledger, give)
    assert OrganizationOperationDomain.RESOURCE_CONTROL in give_domains
    assert OrganizationOperationDomain.INTERNAL_COMMITMENT in give_domains
    assert OrganizationOperationDomain.STORAGE in (
        organization_operation_command_support(ledger, store)
    )
    assert OrganizationOperationDomain.RECORD_KEEPING in (
        organization_operation_command_support(ledger, inscribe)
    )
    assert OrganizationOperationDomain.MEMBERSHIP_ADMISSION in (
        organization_operation_command_support(ledger, _talk())
    )
    assert organization_operation_command_support(ledger, wait) == ()
    assert organization_operation_command_support(None, give) == ()


def test_command_support_ignores_records_for_other_targets() -> None:
    ledger = _ledger(
        admissions=(_admission("body-other"),),
        procedures=(_procedure(),),
    )
    talk = _talk()
    assert OrganizationOperationDomain.MEMBERSHIP_ADMISSION not in (
        organization_operation_command_support(ledger, talk)
    )
    assert OrganizationOperationDomain.PROCEDURE_ACTION in (
        organization_operation_command_support(ledger, Help(EntityId("body-peer")))
    )


def test_commitment_follow_through_requires_an_exact_target() -> None:
    ledger = _ledger(commitments=(_commitment(),))
    match = Give(
        recipient_id=EntityId("body-peer"), item_id=EntityId("item-1")
    )
    wrong_recipient = Give(
        recipient_id=EntityId("body-other"), item_id=EntityId("item-1")
    )
    assert organization_commitment_follow_through(ledger, match) == "commitment-1"
    assert organization_commitment_follow_through(ledger, wrong_recipient) is None
    assert organization_commitment_follow_through(ledger, Wait()) is None

    project = ContributeCollectiveProject(project_id=EntityId("project-1"))
    project_ledger = _ledger(commitments=(_commitment("project-1"),))
    assert (
        organization_commitment_follow_through(project_ledger, project)
        == "commitment-1"
    )

    repository = DepositRecord(
        repository_id=EntityId("repository-1"),
        artifact_id=EntityId("artifact-1"),
    )
    repository_ledger = _ledger(commitments=(_commitment("repository-1"),))
    assert (
        organization_commitment_follow_through(repository_ledger, repository)
        == "commitment-1"
    )


def test_fulfilled_commitment_is_not_recognized_again() -> None:
    ledger = _ledger(
        commitments=(
            _commitment(stance=OrganizationCommitmentStance.FULFILLED),
        )
    )
    command = Give(
        recipient_id=EntityId("body-peer"), item_id=EntityId("item-1")
    )
    assert organization_commitment_follow_through(ledger, command) is None


def test_helpers_do_not_mutate_the_command() -> None:
    command = Give(
        recipient_id=EntityId("body-peer"), item_id=EntityId("item-1")
    )
    before = repr(command)
    ledger = _ledger(controls=(_control(),), commitments=(_commitment(),))
    organization_operation_command_support(ledger, command)
    organization_commitment_follow_through(ledger, command)
    assert repr(command) == before


def test_deliberation_seam_attaches_both_frames() -> None:
    identity = OrganizationIdentityBelief(
        label_token="club",
        conceptualization=OrganizationConceptualization.NAMED_CUSTOM,
        stance=OrganizationIdentityStance.MEMBER,
        first_tick=1,
        last_tick=4,
    )
    concept_ledger = OrganizationConceptLedger(
        owner_id=OWNER,
        concepts=(
            OrganizationConcept(
                organization_id=ORG,
                owner_id=OWNER,
                creation_tick=1,
                inception_digest="a" * 64,
                status=OrganizationStatus.CANDIDATE,
                temporal_scope=OrganizationTemporalScope.ONGOING,
                strength=0.5,
                member_evidence_count=0,
                structural_channel_count=0,
                first_tick=1,
                last_tick=4,
                identities=(identity,),
            ),
        ),
    )
    operation_ledger = _ledger(admissions=(_admission(),))
    command = _talk()
    command = organization_communicate_utterance(command, concept_ledger)
    command = organization_operation_communicate_utterance(command, operation_ledger)
    assert type(command) is Talk
    relations = command.utterance.content.relations
    assert len(relations) == 2
    assert {relation.subject for relation in relations} == {"org_v1", "org_op_v1"}
    assert any(
        parse_organization_claim_relation(relation) is not None
        for relation in relations
    )
    operation_relation = next(
        relation for relation in relations if relation.subject == "org_op_v1"
    )
    parsed = parse_organization_operation_claim_relation(operation_relation)
    assert parsed is not None
    assert parsed.act is OrganizationOperationAct.ADMIT
    assert isinstance(parsed, OrganizationOperationClaim)
    assert organization_operation_claim_relation(parsed) == operation_relation


def test_wait_is_unchanged_by_the_deliberation_seam() -> None:
    wait = Wait()
    assert organization_communicate_utterance(wait, None) is wait
    assert organization_operation_communicate_utterance(wait, None) is wait
