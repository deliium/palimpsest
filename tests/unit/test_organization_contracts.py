"""V4-03 organization belief records, concept, and ledger invariants."""

from __future__ import annotations

import hashlib
from collections.abc import Callable

import pytest

from agents.cognition import (
    FORBIDDEN_ORGANIZATION_FIELD_NAMES,
    ORGANIZATION_CONCEPT_POLICY_VERSION,
    ORGANIZATION_NOTICE_CODES,
    OrganizationCommitmentBelief,
    OrganizationCommitmentRole,
    OrganizationConcept,
    OrganizationConceptError,
    OrganizationConceptLedger,
    OrganizationConceptualization,
    OrganizationEvidence,
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
    OrganizationProcedureBelief,
    OrganizationProcedureKind,
    OrganizationRecordBelief,
    OrganizationRecordKind,
    OrganizationResourceBelief,
    OrganizationResourceKind,
    OrganizationRevisionKind,
    OrganizationRevisionRecord,
    OrganizationRoleBelief,
    OrganizationStatus,
    OrganizationTemporalScope,
    OrganizationWindowRecord,
    empty_organization_concept_ledger,
    organization_concept_digest,
    organization_concept_id,
    organization_lineage_id,
    require_owner_organization_concepts,
)
from agents.models import AgentId

pytestmark = pytest.mark.unit

OWNER = AgentId("agent-1")
OTHER = AgentId("agent-2")
TICK = 10
DIGEST = hashlib.sha256(b"concept").hexdigest()
EDGE_DIGEST = hashlib.sha256(b"edge").hexdigest()


def _member(
    member_id: str = "agent-2",
    *,
    status: OrganizationMembershipStatus = (OrganizationMembershipStatus.PERCEIVED),
    scope: OrganizationTemporalScope = OrganizationTemporalScope.ONGOING,
    expires_tick: int | None = None,
) -> OrganizationMemberBelief:
    return OrganizationMemberBelief(
        member_id=member_id,
        status=status,
        basis=OrganizationMembershipBasis.PARTICIPATION,
        temporal_scope=scope,
        first_tick=1,
        last_tick=TICK,
        strength=0.5,
        channels=(
            OrganizationEvidenceChannel.OBSERVED,
            OrganizationEvidenceChannel.COMMUNICATED,
        ),
        independently_evidenced=True,
        evidence_refs=(),
        expires_tick=expires_tick,
    )


def _role() -> OrganizationRoleBelief:
    return OrganizationRoleBelief(
        office_id="office-1",
        function="coordinator",
        context_key="site-1",
        occupant_ids=("agent-2",),
        status=OrganizationStatus.RECOGNIZED,
        first_tick=1,
        last_tick=TICK,
    )


def _goal() -> OrganizationGoalBelief:
    return OrganizationGoalBelief(
        anchor_kind=OrganizationGoalKind.COLLECTIVE_PROJECT,
        anchor_id="project-1",
        status=OrganizationStatus.RECOGNIZED,
        first_tick=1,
        last_tick=TICK,
    )


def _resource() -> OrganizationResourceBelief:
    return OrganizationResourceBelief(
        resource_kind=OrganizationResourceKind.REPOSITORY,
        anchor_id="repository-1",
        access_belief="shared",
        first_tick=1,
        last_tick=TICK,
    )


def _procedure() -> OrganizationProcedureBelief:
    return OrganizationProcedureBelief(
        procedure_kind=OrganizationProcedureKind.INSTITUTION_CONCEPT,
        anchor_id="concept-1",
        recurrence=3,
        status=OrganizationStatus.RECOGNIZED,
        first_tick=1,
        last_tick=TICK,
    )


def _record() -> OrganizationRecordBelief:
    return OrganizationRecordBelief(
        record_kind=OrganizationRecordKind.ARTIFACT,
        anchor_id="artifact-1",
        integrity=0.75,
        custody_belief="shared",
        first_tick=1,
        last_tick=TICK,
    )


def _commitment() -> OrganizationCommitmentBelief:
    return OrganizationCommitmentBelief(
        commitment_id="commitment-1",
        role=OrganizationCommitmentRole.DEBTOR,
        counterpart_id="agent-2",
        commitment_kind="deliver",
        status=OrganizationStatus.CANDIDATE,
        first_tick=1,
        last_tick=TICK,
        due_tick=20,
    )


def _identity() -> OrganizationIdentityBelief:
    return OrganizationIdentityBelief(
        label_token="water-carriers",
        conceptualization=OrganizationConceptualization.NAMED_CUSTOM,
        stance=OrganizationIdentityStance.MEMBER,
        first_tick=1,
        last_tick=TICK,
    )


def _snapshot(index: int = 0) -> OrganizationWindowRecord:
    return OrganizationWindowRecord(
        window_index=index,
        tick=TICK,
        status=OrganizationStatus.CANDIDATE,
        temporal_scope=OrganizationTemporalScope.ONGOING,
        member_ids=("agent-1",),
        role_anchor_ids=(),
        goal_anchor_ids=(),
        resource_anchor_ids=(),
        procedure_anchor_ids=(),
        record_anchor_ids=(),
        commitment_ids=(),
        structural_signature=DIGEST,
        evidence_count=1,
    )


def _revision(tick: int = TICK) -> OrganizationRevisionRecord:
    return OrganizationRevisionRecord(
        revision_id="revision-1",
        kind=OrganizationRevisionKind.MEMBERSHIP_REVISED,
        tick=tick,
        before_digest=DIGEST,
        after_digest=EDGE_DIGEST,
        reason_code="observed",
    )


def _lineage(
    organization_id: str, *, kind: OrganizationLineageKind
) -> OrganizationLineageRecord:
    return OrganizationLineageRecord(
        lineage_id=organization_lineage_id(
            OWNER.value, kind.value, TICK, (organization_id,), (organization_id,)
        ),
        kind=kind,
        tick=TICK,
        from_ids=(organization_id,),
        to_ids=(organization_id,),
        evidence_digest=EDGE_DIGEST,
    )


def _concept(
    *,
    owner: AgentId = OWNER,
    status: OrganizationStatus = OrganizationStatus.CANDIDATE,
    members: tuple[OrganizationMemberBelief, ...] | None = None,
    structural_channel_count: int = 2,
    lineage: tuple[OrganizationLineageRecord, ...] | None = None,
    goals: tuple[OrganizationGoalBelief, ...] | None = None,
) -> OrganizationConcept:
    members = (_member("agent-1"),) if members is None else members
    organization_id = organization_concept_id(
        owner.value, TICK, tuple(member.member_id for member in members), ("anchor-1",)
    )
    records = (
        (_lineage(organization_id, kind=OrganizationLineageKind.EMERGED),)
        if lineage is None
        else lineage
    )
    return OrganizationConcept(
        organization_id=organization_id,
        owner_id=owner,
        creation_tick=TICK,
        inception_digest=DIGEST,
        status=status,
        temporal_scope=OrganizationTemporalScope.ONGOING,
        strength=0.5,
        member_evidence_count=3,
        structural_channel_count=structural_channel_count,
        first_tick=1,
        last_tick=TICK,
        members=members,
        goals=() if goals is None else goals,
        lineage=records,
        revisions=(_revision(),),
        snapshots=(_snapshot(),),
    )


def test_every_aspect_record_accepts_a_representative_value() -> None:
    assert _role().office_id == "office-1"
    assert _goal().anchor_kind is OrganizationGoalKind.COLLECTIVE_PROJECT
    assert _resource().resource_kind is OrganizationResourceKind.REPOSITORY
    assert _procedure().procedure_kind is OrganizationProcedureKind.INSTITUTION_CONCEPT
    assert _record().record_kind is OrganizationRecordKind.ARTIFACT
    assert _commitment().role is OrganizationCommitmentRole.DEBTOR
    assert _identity().label_token == "water-carriers"
    assert _snapshot().window_index == 0
    assert _revision().kind is OrganizationRevisionKind.MEMBERSHIP_REVISED
    evidence = OrganizationEvidence(
        evidence_id="evidence-1",
        ordinal=0,
        channel=OrganizationEvidenceChannel.OBSERVED,
        ref="project-1",
        tick=TICK,
        anchor_digest=DIGEST,
    )
    assert evidence.channel is OrganizationEvidenceChannel.OBSERVED
    concept = _concept()
    assert concept.organization_id.startswith("orgc-")
    assert concept.owner_id == OWNER


@pytest.mark.parametrize(
    "factory",
    (
        lambda: _member(status="perceived"),  # type: ignore[arg-type]
        lambda: OrganizationRoleBelief(
            office_id="office-1",
            function="coordinator",
            context_key="site-1",
            occupant_ids=(),
            status="recognized",  # type: ignore[arg-type]
            first_tick=1,
            last_tick=TICK,
        ),
        lambda: _goal_with_kind("collective_project"),
        lambda: OrganizationResourceBelief(
            resource_kind="repository",  # type: ignore[arg-type]
            anchor_id="repository-1",
            access_belief="shared",
            first_tick=1,
            last_tick=TICK,
        ),
        lambda: OrganizationProcedureBelief(
            procedure_kind="institution_concept",  # type: ignore[arg-type]
            anchor_id="concept-1",
            recurrence=3,
            status=OrganizationStatus.RECOGNIZED,
            first_tick=1,
            last_tick=TICK,
        ),
        lambda: OrganizationRecordBelief(
            record_kind="artifact",  # type: ignore[arg-type]
            anchor_id="artifact-1",
            integrity=0.5,
            custody_belief="shared",
            first_tick=1,
            last_tick=TICK,
        ),
        lambda: OrganizationCommitmentBelief(
            commitment_id="commitment-1",
            role="debtor",  # type: ignore[arg-type]
            counterpart_id="agent-2",
            commitment_kind="deliver",
            status=OrganizationStatus.CANDIDATE,
            first_tick=1,
            last_tick=TICK,
        ),
        lambda: OrganizationIdentityBelief(
            label_token="water-carriers",
            conceptualization="named_custom",  # type: ignore[arg-type]
            stance=OrganizationIdentityStance.MEMBER,
            first_tick=1,
            last_tick=TICK,
        ),
    ),
)
def test_aspect_records_reject_string_statuses(factory: Callable[[], object]) -> None:
    with pytest.raises(OrganizationConceptError):
        factory()


def _goal_with_kind(kind: object) -> OrganizationGoalBelief:
    return OrganizationGoalBelief(
        anchor_kind=kind,  # type: ignore[arg-type]
        anchor_id="project-1",
        status=OrganizationStatus.RECOGNIZED,
        first_tick=1,
        last_tick=TICK,
    )


def test_members_must_be_sorted_and_unique() -> None:
    with pytest.raises(OrganizationConceptError) as excinfo:
        _concept(members=(_member("agent-3"), _member("agent-2")))
    assert excinfo.value.code == "organization_duplicate_member"

    with pytest.raises(OrganizationConceptError) as excinfo:
        _concept(members=(_member("agent-2"), _member("agent-2")))
    assert excinfo.value.code == "organization_duplicate_member"


def test_ticks_reject_regression_and_bool() -> None:
    with pytest.raises(OrganizationConceptError) as excinfo:
        OrganizationMemberBelief(
            member_id="agent-2",
            status=OrganizationMembershipStatus.PERCEIVED,
            basis=OrganizationMembershipBasis.PARTICIPATION,
            temporal_scope=OrganizationTemporalScope.ONGOING,
            first_tick=5,
            last_tick=4,
            strength=0.5,
            channels=(OrganizationEvidenceChannel.OBSERVED,),
            independently_evidenced=True,
        )
    assert excinfo.value.code == "organization_tick_regression"

    with pytest.raises(OrganizationConceptError) as excinfo:
        OrganizationRevisionRecord(
            revision_id="revision-1",
            kind=OrganizationRevisionKind.CONTINUED,
            tick=True,
            before_digest=DIGEST,
            after_digest=DIGEST,
            reason_code="observed",
        )
    assert excinfo.value.code == "organization_tick_regression"


def test_temporary_membership_requires_explicit_expiry() -> None:
    with pytest.raises(OrganizationConceptError) as excinfo:
        _member(scope=OrganizationTemporalScope.TEMPORARY)
    assert excinfo.value.code == "organization_invalid_temporal_scope"

    with pytest.raises(OrganizationConceptError) as excinfo:
        _member(scope=OrganizationTemporalScope.TEMPORARY, expires_tick=0)
    assert excinfo.value.code == "organization_invalid_temporal_scope"

    temporary = _member(scope=OrganizationTemporalScope.TEMPORARY, expires_tick=20)
    assert temporary.expires_tick == 20

    with pytest.raises(OrganizationConceptError) as excinfo:
        _member(scope=OrganizationTemporalScope.ONGOING, expires_tick=20)
    assert excinfo.value.code == "organization_invalid_temporal_scope"


def test_caps_reject_overflow() -> None:
    members = tuple(_member(f"agent-{index:03d}") for index in range(33))
    with pytest.raises(OrganizationConceptError) as excinfo:
        _concept(members=members)
    assert excinfo.value.code == "organization_cap_exceeded"


def test_foreign_owner_ledger_is_rejected() -> None:
    foreign = _concept(owner=OTHER)
    foreign_ledger = OrganizationConceptLedger(owner_id=OTHER, concepts=(foreign,))
    with pytest.raises(OrganizationConceptError) as excinfo:
        OrganizationConceptLedger(owner_id=OWNER, concepts=(foreign,))
    assert excinfo.value.code == "organization_foreign_ledger"

    with pytest.raises(OrganizationConceptError) as excinfo:
        require_owner_organization_concepts(
            foreign_ledger, OWNER, field_name="snapshot"
        )
    assert excinfo.value.code == "organization_foreign_ledger"


def test_none_versus_empty_ledger_is_distinct() -> None:
    require_owner_organization_concepts(None, OWNER, field_name="snapshot")
    empty = empty_organization_concept_ledger(OWNER)
    assert empty.owner_id == OWNER
    assert empty.concepts == ()
    assert empty.lineage == ()
    assert empty.policy_version == ORGANIZATION_CONCEPT_POLICY_VERSION
    require_owner_organization_concepts(empty, OWNER, field_name="snapshot")


def test_forbidden_labels_and_fields_are_rejected() -> None:
    with pytest.raises(OrganizationConceptError) as excinfo:
        _identity_token("government")
    assert excinfo.value.code == "organization_forbidden_label"

    with pytest.raises(OrganizationConceptError) as excinfo:
        _identity_token("Water Carrier")
    assert excinfo.value.code == "organization_forbidden_label"

    with pytest.raises(OrganizationConceptError) as excinfo:
        _identity_token("a" * 33)
    assert excinfo.value.code == "organization_forbidden_label"

    for name in ("treasury", "membership_roster", "global_registry"):
        assert name in FORBIDDEN_ORGANIZATION_FIELD_NAMES
    for record_type in (
        OrganizationConcept,
        OrganizationConceptLedger,
        OrganizationMemberBelief,
        OrganizationRoleBelief,
        OrganizationIdentityBelief,
        OrganizationWindowRecord,
    ):
        fields = set(record_type.__dataclass_fields__)
        assert fields & FORBIDDEN_ORGANIZATION_FIELD_NAMES == set()


def _identity_token(token: str) -> OrganizationIdentityBelief:
    return OrganizationIdentityBelief(
        label_token=token,
        conceptualization=OrganizationConceptualization.NAMED_CUSTOM,
        stance=OrganizationIdentityStance.MEMBER,
        first_tick=1,
        last_tick=TICK,
    )


def test_status_rules_match_membership_and_lineage() -> None:
    recognized = _concept(
        status=OrganizationStatus.RECOGNIZED,
        members=(_member("agent-1"), _member("agent-2")),
    )
    assert recognized.status is OrganizationStatus.RECOGNIZED

    with pytest.raises(OrganizationConceptError) as excinfo:
        _concept(status=OrganizationStatus.RECOGNIZED, structural_channel_count=1)
    assert excinfo.value.code == "organization_invalid_status"

    disputed_member = _member("agent-1", status=OrganizationMembershipStatus.DISPUTED)
    with pytest.raises(OrganizationConceptError) as excinfo:
        _concept(
            status=OrganizationStatus.RECOGNIZED,
            members=(disputed_member, _member("agent-2")),
        )
    assert excinfo.value.code == "organization_invalid_status"

    disputed = _concept(status=OrganizationStatus.DISPUTED, members=(disputed_member,))
    assert disputed.status is OrganizationStatus.DISPUTED

    active_goal = _goal()
    with pytest.raises(OrganizationConceptError) as excinfo:
        _concept(status=OrganizationStatus.DISSOLVED, goals=(active_goal,))
    assert excinfo.value.code == "organization_invalid_status"


def test_ledger_enforces_acyclic_forward_only_lineage() -> None:
    first = _concept()
    second = _concept(members=(_member("agent-9"),))
    forward = OrganizationLineageRecord(
        lineage_id=organization_lineage_id(
            OWNER.value,
            "continued",
            11,
            (first.organization_id,),
            (second.organization_id,),
        ),
        kind=OrganizationLineageKind.CONTINUED,
        tick=11,
        from_ids=(first.organization_id,),
        to_ids=(second.organization_id,),
        evidence_digest=EDGE_DIGEST,
    )
    backward = OrganizationLineageRecord(
        lineage_id=organization_lineage_id(
            OWNER.value,
            "continued",
            12,
            (second.organization_id,),
            (first.organization_id,),
        ),
        kind=OrganizationLineageKind.CONTINUED,
        tick=12,
        from_ids=(second.organization_id,),
        to_ids=(first.organization_id,),
        evidence_digest=EDGE_DIGEST,
    )
    with pytest.raises(OrganizationConceptError) as excinfo:
        OrganizationConceptLedger(
            owner_id=OWNER,
            concepts=(first, second),
            lineage=(forward, backward),
        )
    assert excinfo.value.code == "organization_lineage_cycle"


def test_notice_codes_are_closed() -> None:
    assert ORGANIZATION_NOTICE_CODES == frozenset(
        {
            "foreign_owner",
            "missing_institution",
            "missing_office",
            "unresolved_anchor",
            "history_truncated",
            "membership_conflict",
            "temporary_expired",
        }
    )
    with pytest.raises(OrganizationConceptError):
        _concept_with_notice("custom_notice")


def _concept_with_notice(notice: str) -> OrganizationConcept:
    base = _concept()
    return OrganizationConcept(
        organization_id=base.organization_id,
        owner_id=base.owner_id,
        creation_tick=base.creation_tick,
        inception_digest=base.inception_digest,
        status=base.status,
        temporal_scope=base.temporal_scope,
        strength=base.strength,
        member_evidence_count=base.member_evidence_count,
        structural_channel_count=base.structural_channel_count,
        first_tick=base.first_tick,
        last_tick=base.last_tick,
        members=base.members,
        lineage=base.lineage,
        revisions=base.revisions,
        snapshots=base.snapshots,
        notices=(notice,),
    )


def test_concept_digest_is_canonical_and_stable() -> None:
    concept = _concept()
    assert organization_concept_digest(concept) == organization_concept_digest(
        _concept()
    )
    assert len(organization_concept_digest(concept)) == 64
