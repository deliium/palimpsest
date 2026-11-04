"""V4-09 revocation, expiry, supersession, and retained conflicts."""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest

from agents.cognition import (
    RepresentationConflictKind,
    RepresentationDurationKind,
    RepresentationPrincipalKind,
    RepresentationProvenance,
    RepresentationRevocationKind,
    RepresentationScopeKind,
    RepresentationStatus,
    default_representation_policy,
)
from agents.cognition.delegation_representation import (
    RepresentationLedger,
    apply_representation_revocation,
    apply_representation_update,
    detect_representation_conflicts,
    expire_representation_mandates,
)
from agents.cognition.delegation_representation_communication import (
    RepresentationAct,
    RepresentationFrame,
)

pytestmark = pytest.mark.unit

_OWNER = "agent-owner"
_PRINCIPAL = "agent-principal"
_REP = "agent-representative"


def _frame(
    act: RepresentationAct,
    *,
    mandate_ref: str | None = None,
    principal_kind: RepresentationPrincipalKind = RepresentationPrincipalKind.AGENT,
    principal_ref: str | None = _PRINCIPAL,
    representative_ref: str = _REP,
    scope_kind: RepresentationScopeKind = RepresentationScopeKind.SPEAK_FOR,
    scope_subject: str | None = "border",
    duration_kind: RepresentationDurationKind = (
        RepresentationDurationKind.UNTIL_REVOKED
    ),
    end_tick: int | None = None,
    actor_ref: str | None = _REP,
) -> RepresentationFrame:
    if act in {RepresentationAct.CLAIM, RepresentationAct.DELEGATE}:
        mandate_ref = None
    elif mandate_ref is None:
        mandate_ref = "rmd-" + "1" * 16
    return RepresentationFrame(
        act=act,
        mandate_ref=mandate_ref,
        principal_kind=principal_kind,
        principal_ref=principal_ref,
        representative_ref=representative_ref,
        scope_kind=scope_kind,
        scope_subject=scope_subject,
        duration_kind=duration_kind,
        end_tick=end_tick,
        provenance=RepresentationProvenance.SELF_DECLARED,
        actor_ref=actor_ref,
    )


def _apply(
    prior: RepresentationLedger | None,
    *frames: RepresentationFrame,
    tick: int,
    **kwargs: object,
) -> RepresentationLedger:
    return apply_representation_update(
        owner_id=_OWNER,
        tick=tick,
        observation=None,
        prior=prior,
        frames=frames,
        organization_concepts=kwargs.get("organization_concepts"),
        collective_decisions=kwargs.get("collective_decisions"),
        offices=kwargs.get("offices"),
        formal_rules=kwargs.get("formal_rules"),
        policy=default_representation_policy(),
    )


def _claimed(
    duration: RepresentationDurationKind = RepresentationDurationKind.UNTIL_REVOKED,
    end_tick: int | None = None,
) -> RepresentationLedger:
    return _apply(
        None,
        _frame(RepresentationAct.CLAIM, duration_kind=duration, end_tick=end_tick),
        tick=1,
    )


def test_principal_revocation_is_authorized_and_retained() -> None:
    ledger = _claimed()
    mandate_id = ledger.mandates[0].mandate_id
    revoked = _apply(
        ledger,
        _frame(RepresentationAct.REVOKE, mandate_ref=mandate_id, actor_ref=_PRINCIPAL),
        tick=2,
    )
    assert revoked.mandates[0].status is RepresentationStatus.REVOKED
    assert len(revoked.revocations) == 1
    assert revoked.revocations[0].kind is (
        RepresentationRevocationKind.PRINCIPAL_REVOKED
    )
    assert revoked.revocations[0].contested is False


def test_representative_resignation_is_authorized() -> None:
    ledger = _claimed()
    mandate_id = ledger.mandates[0].mandate_id
    resigned = _apply(
        ledger,
        _frame(RepresentationAct.RESIGN, mandate_ref=mandate_id, actor_ref=_REP),
        tick=2,
    )
    assert resigned.mandates[0].status is RepresentationStatus.REVOKED
    assert resigned.revocations[0].kind is (
        RepresentationRevocationKind.REPRESENTATIVE_RESIGNED
    )


def test_unauthorized_revocation_is_contested_and_retains_mandate() -> None:
    ledger = _claimed()
    mandate_id = ledger.mandates[0].mandate_id
    contested = _apply(
        ledger,
        _frame(
            RepresentationAct.REVOKE,
            mandate_ref=mandate_id,
            actor_ref="agent-third-party",
        ),
        tick=2,
    )
    assert contested.mandates[0].status is RepresentationStatus.CLAIMED
    assert contested.revocations[0].contested is True
    assert any(
        conflict.kind is RepresentationConflictKind.REVOCATION_DISPUTE
        for conflict in contested.conflicts
    )


def test_collective_decision_and_office_loss_revocations() -> None:
    proposal_ref = "f" * 32
    proposal_id = "b" * 64
    decisions = SimpleNamespace(
        proposals=(
            SimpleNamespace(proposal_id=proposal_id, proposal_ref=proposal_ref),
        ),
        positions=(
            SimpleNamespace(
                proposal_ref=proposal_ref,
                actor_id=SimpleNamespace(value=_PRINCIPAL),
                stance=SimpleNamespace(value="support"),
            ),
        ),
        outcomes=(),
    )
    ledger = _apply(
        None,
        _frame(RepresentationAct.CLAIM),
        tick=1,
        collective_decisions=decisions,
    )
    mandate_id = ledger.mandates[0].mandate_id
    mandate = replace(ledger.mandates[0], decision_refs=(proposal_id,))
    ledger = replace(ledger, mandates=(mandate,))

    revoked = apply_representation_revocation(
        ledger,
        tick=2,
        mandate_id=mandate_id,
        actor_id="agent-member",
        kind=RepresentationRevocationKind.COLLECTIVE_DECISION_REVOKED,
        provenance=RepresentationProvenance.COLLECTIVE_DECISION,
        collective_decisions=decisions,
    )
    assert revoked.mandates[0].status is RepresentationStatus.REVOKED

    office_id = "a" * 64
    office_mandate = replace(
        ledger.mandates[0],
        office_refs=(office_id,),
        decision_refs=(),
    )
    ledger = replace(ledger, mandates=(office_mandate,))
    lost = apply_representation_revocation(
        ledger,
        tick=2,
        mandate_id=mandate_id,
        actor_id="agent-member",
        kind=RepresentationRevocationKind.OFFICE_LOST,
        provenance=RepresentationProvenance.OFFICE_BELIEF,
        offices=SimpleNamespace(offices=()),
    )
    assert lost.mandates[0].status is RepresentationStatus.REVOKED


def test_expiry_at_boundary_tick_and_until_revoked_persistence() -> None:
    finite = _claimed(duration=RepresentationDurationKind.UNTIL_TICK, end_tick=3)
    expired = expire_representation_mandates(finite, tick=3)
    assert expired.mandates[0].status is RepresentationStatus.EXPIRED
    assert "representation_expired" in expired.notices

    eternal = _claimed()
    still = expire_representation_mandates(eternal, tick=99)
    assert still.mandates[0].status is RepresentationStatus.CLAIMED


def test_supersession_of_claimed_mandate() -> None:
    ledger = _claimed()
    delegated = _apply(
        ledger,
        _frame(
            RepresentationAct.DELEGATE,
            representative_ref="agent-c",
            actor_ref=_PRINCIPAL,
        ),
        tick=2,
    )
    assert len(delegated.mandates) == 2
    statuses = {row.representative_id: row.status for row in delegated.mandates}
    assert statuses[_REP] is RepresentationStatus.SUPERSEDED
    assert statuses["agent-c"] is RepresentationStatus.RECOGNIZED


def test_two_recognized_mandates_coexist_with_duplicate_conflict() -> None:
    ledger = _apply(
        None,
        _frame(
            RepresentationAct.DELEGATE,
            representative_ref=_REP,
            actor_ref=_PRINCIPAL,
        ),
        tick=1,
    )
    both = _apply(
        ledger,
        _frame(
            RepresentationAct.DELEGATE,
            representative_ref="agent-c",
            actor_ref=_PRINCIPAL,
        ),
        tick=2,
    )
    assert len(both.mandates) == 2
    assert {row.status for row in both.mandates} == {RepresentationStatus.RECOGNIZED}
    assert any(
        conflict.kind is RepresentationConflictKind.DUPLICATE_MANDATE
        for conflict in both.conflicts
    )


def test_all_conflict_kinds_are_retained() -> None:
    first = _apply(None, _frame(RepresentationAct.CLAIM), tick=1)
    second = _apply(
        first,
        _frame(
            RepresentationAct.CLAIM,
            representative_ref="agent-c",
            actor_ref="agent-c",
        ),
        tick=2,
    )
    assert any(
        conflict.kind is RepresentationConflictKind.DUPLICATE_MANDATE
        for conflict in second.conflicts
    )

    contradictory = _apply(
        second,
        _frame(
            RepresentationAct.CLAIM,
            principal_kind=RepresentationPrincipalKind.AGENT,
            principal_ref="agent-other",
        ),
        tick=3,
    )
    kinds = {conflict.kind for conflict in contradictory.conflicts}
    assert RepresentationConflictKind.CONFLICTING_PRINCIPAL in kinds

    ledger = _claimed()
    mandate_id = ledger.mandates[0].mandate_id
    dispute = _apply(
        ledger,
        _frame(
            RepresentationAct.REVOKE,
            mandate_ref=mandate_id,
            actor_ref="agent-third-party",
        ),
        tick=2,
    )
    assert any(
        conflict.kind is RepresentationConflictKind.REVOCATION_DISPUTE
        for conflict in dispute.conflicts
    )
    assert detect_representation_conflicts(dispute) == dispute.conflicts


def test_contradictory_scope_conflict_is_retained() -> None:
    ledger = _apply(
        None,
        _frame(RepresentationAct.CLAIM, scope_subject=None),
        tick=1,
    )
    ledger = _apply(
        ledger,
        _frame(RepresentationAct.CLAIM, scope_subject="border"),
        tick=2,
    )
    assert len(ledger.mandates) == 2
    assert any(
        conflict.kind is RepresentationConflictKind.CONTRADICTORY_SCOPE
        for conflict in ledger.conflicts
    )
    assert detect_representation_conflicts(ledger) == ledger.conflicts


def test_retention_after_every_transition() -> None:
    ledger = _claimed()
    mandate_id = ledger.mandates[0].mandate_id
    revoked = _apply(
        ledger,
        _frame(RepresentationAct.REVOKE, mandate_ref=mandate_id, actor_ref=_PRINCIPAL),
        tick=2,
    )
    assert revoked.mandates
    assert revoked.revocations
    assert revoked.positions == ledger.positions
