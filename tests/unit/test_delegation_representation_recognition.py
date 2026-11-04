"""V4-09 principal resolution and derived recognition precedence."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

import pytest

from agents.cognition import (
    RepresentationDurationKind,
    RepresentationPrincipalKind,
    RepresentationProvenance,
    RepresentationRecognitionBasis,
    RepresentationScopeKind,
    RepresentationStatus,
    default_representation_policy,
)
from agents.cognition.delegation_representation import (
    RepresentationLedger,
    RepresentationPosition,
    RepresentationPositionStance,
    apply_representation_update,
    appraise_representation_recognition,
    enforce_representation_limits,
    representation_ledger_digest,
    representation_standing_summary,
    require_owner_representation,
    resolve_representation_principal,
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
        prior=prior if prior is not None else None,
        frames=frames,
        organization_concepts=kwargs.get("organization_concepts"),
        collective_decisions=kwargs.get("collective_decisions"),
        offices=kwargs.get("offices"),
        formal_rules=kwargs.get("formal_rules"),
        policy=default_representation_policy(),
    )


def _claim_with_positions(
    *stances: tuple[str, RepresentationPositionStance],
) -> RepresentationLedger:
    ledger = _apply(None, _frame(RepresentationAct.CLAIM), tick=1)
    mandate_id = ledger.mandates[0].mandate_id
    tick = 2
    for actor, stance in stances:
        act = {
            RepresentationPositionStance.SUPPORT: RepresentationAct.SUPPORT,
            RepresentationPositionStance.OPPOSE: RepresentationAct.OPPOSE,
            RepresentationPositionStance.ABSTAIN: RepresentationAct.ABSTAIN,
        }[stance]
        ledger = _apply(
            ledger,
            _frame(act, mandate_ref=mandate_id, actor_ref=actor),
            tick=tick,
        )
        tick += 1
    return ledger


def test_self_claim_alone_stays_claimed() -> None:
    ledger = _apply(None, _frame(RepresentationAct.CLAIM), tick=1)
    assert ledger.mandates[0].status is RepresentationStatus.CLAIMED


def test_two_independent_supporters_recognize() -> None:
    ledger = _claim_with_positions(
        ("agent-c", RepresentationPositionStance.SUPPORT),
        ("agent-d", RepresentationPositionStance.SUPPORT),
    )
    assert ledger.mandates[0].status is RepresentationStatus.RECOGNIZED
    assert ledger.mandates[0].recognition_basis is (
        RepresentationRecognitionBasis.INDEPENDENT_SUPPORT
    )


def test_same_root_supporters_count_once() -> None:
    ledger = _apply(None, _frame(RepresentationAct.CLAIM), tick=1)
    mandate_id = ledger.mandates[0].mandate_id
    base = ledger
    for actor, tick in (("agent-c", 2), ("agent-d", 3)):
        position = RepresentationPosition(
            position_id="rmp-" + f"{tick:016x}",
            mandate_id=mandate_id,
            actor_id=actor,
            stance=RepresentationPositionStance.SUPPORT,
            root_ref="root-shared",
            provenance=RepresentationProvenance.COMMUNICATED,
            tick=tick,
            active=True,
        )
        base = RepresentationLedger(
            owner_id=_OWNER,
            mandates=base.mandates,
            positions=(*base.positions, position),
            first_tick=0,
            last_tick=4,
        )
    assert base.mandates[0].status is RepresentationStatus.CLAIMED


def test_owner_self_support_is_excluded() -> None:
    ledger = _claim_with_positions(
        (_OWNER, RepresentationPositionStance.SUPPORT),
        ("agent-c", RepresentationPositionStance.SUPPORT),
    )
    assert ledger.mandates[0].status is RepresentationStatus.CLAIMED


def test_opposition_majority_rejects_and_mixed_contests() -> None:
    rejected = _claim_with_positions(
        ("agent-c", RepresentationPositionStance.SUPPORT),
        ("agent-d", RepresentationPositionStance.OPPOSE),
        ("agent-e", RepresentationPositionStance.OPPOSE),
    )
    assert rejected.mandates[0].status is RepresentationStatus.REJECTED

    contested = _claim_with_positions(
        ("agent-c", RepresentationPositionStance.SUPPORT),
        ("agent-d", RepresentationPositionStance.OPPOSE),
    )
    assert contested.mandates[0].status is RepresentationStatus.CONTESTED


def test_unresolved_org_and_settlement_stay_claimed() -> None:
    collective = "orgc-" + "1" * 16
    org = _apply(
        None,
        _frame(
            RepresentationAct.CLAIM,
            principal_kind=RepresentationPrincipalKind.ORGANIZATION,
            principal_ref=collective,
        ),
        tick=1,
        organization_concepts=SimpleNamespace(concepts=()),
    )
    assert org.mandates[0].status is RepresentationStatus.CLAIMED
    assert org.mandates[0].principal_resolved is False

    settlement = _apply(
        None,
        _frame(
            RepresentationAct.CLAIM,
            principal_kind=RepresentationPrincipalKind.SETTLEMENT,
            principal_ref="region-missing",
        ),
        tick=1,
    )
    assert settlement.mandates[0].status is RepresentationStatus.CLAIMED
    assert settlement.mandates[0].principal_resolved is False


def test_unknown_principal_is_unknown() -> None:
    ledger = _apply(
        None,
        _frame(
            RepresentationAct.CLAIM,
            principal_kind=RepresentationPrincipalKind.UNKNOWN,
            principal_ref=None,
        ),
        tick=1,
    )
    assert ledger.mandates[0].status is RepresentationStatus.UNKNOWN


def test_principal_resolution_uses_owner_anchors_only() -> None:
    collective = "orgc-" + "1" * 16
    mandate = _apply(
        None,
        _frame(
            RepresentationAct.CLAIM,
            principal_kind=RepresentationPrincipalKind.ORGANIZATION,
            principal_ref=collective,
        ),
        tick=1,
    ).mandates[0]
    assert resolve_representation_principal(
        mandate=mandate,
        organization_concepts=SimpleNamespace(
            concepts=(SimpleNamespace(organization_id=collective),)
        ),
        region_anchors=(),
    )
    assert not resolve_representation_principal(
        mandate=mandate,
        organization_concepts=SimpleNamespace(concepts=()),
        region_anchors=(),
    )


def _support_once() -> RepresentationLedger:
    ledger = _apply(None, _frame(RepresentationAct.CLAIM), tick=1)
    mandate_id = ledger.mandates[0].mandate_id
    return _apply(
        ledger,
        _frame(
            RepresentationAct.SUPPORT,
            mandate_ref=mandate_id,
            actor_ref="agent-c",
        ),
        tick=2,
    )


def test_office_basis_requires_an_independent_root() -> None:
    office_id = "a" * 64
    offices = SimpleNamespace(
        offices=(
            SimpleNamespace(
                office_id=office_id,
                occupants=(
                    SimpleNamespace(
                        occupant_id=SimpleNamespace(value=_REP),
                        status=SimpleNamespace(value="preferred"),
                    ),
                ),
            ),
        )
    )
    without_support = _apply(
        None, _frame(RepresentationAct.CLAIM), tick=1, offices=offices
    )
    assert without_support.mandates[0].status is RepresentationStatus.CLAIMED

    with_support = _apply(
        _support_once(),
        _frame(
            RepresentationAct.SUPPORT,
            mandate_ref=_support_once().mandates[0].mandate_id,
            actor_ref="agent-d",
        ),
        tick=3,
        offices=offices,
    )
    assert with_support.mandates[0].status is RepresentationStatus.RECOGNIZED
    assert with_support.mandates[0].office_basis is True


def test_decision_and_written_bases_are_owner_read_only() -> None:
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
            SimpleNamespace(
                proposal_ref=proposal_ref,
                actor_id=SimpleNamespace(value=_REP),
                stance=SimpleNamespace(value="support"),
            ),
        ),
        outcomes=(),
    )
    with_decision = _apply(
        _support_once(),
        _frame(
            RepresentationAct.SUPPORT,
            mandate_ref=_support_once().mandates[0].mandate_id,
            actor_ref="agent-d",
        ),
        tick=3,
        collective_decisions=decisions,
    )
    assert with_decision.mandates[0].decision_basis is True
    assert with_decision.mandates[0].status is RepresentationStatus.RECOGNIZED

    rule_id = "frl-" + "c" * 16
    rules = SimpleNamespace(
        rules=(
            SimpleNamespace(
                rule_id=rule_id,
                action_token="border",
                status=SimpleNamespace(value="documented"),
                versions=(
                    SimpleNamespace(
                        written=SimpleNamespace(status=SimpleNamespace(value="intact"))
                    ),
                ),
            ),
        )
    )
    with_written = _apply(
        _support_once(),
        _frame(
            RepresentationAct.SUPPORT,
            mandate_ref=_support_once().mandates[0].mandate_id,
            actor_ref="agent-d",
        ),
        tick=3,
        formal_rules=rules,
    )
    assert with_written.mandates[0].written_basis is True
    assert with_written.mandates[0].status is RepresentationStatus.RECOGNIZED


def test_recognition_precedence_table() -> None:
    cases = [
        (dict(principal_resolved=False), RepresentationStatus.CLAIMED),
        (
            dict(principal_declared=True),
            RepresentationStatus.RECOGNIZED,
        ),
        (
            dict(office_basis=True, support_roots=("a",)),
            RepresentationStatus.RECOGNIZED,
        ),
        (
            dict(decision_basis=True, support_roots=("a",)),
            RepresentationStatus.RECOGNIZED,
        ),
        (
            dict(written_basis=True, support_roots=("a",)),
            RepresentationStatus.RECOGNIZED,
        ),
        (
            dict(support_roots=("a", "b")),
            RepresentationStatus.RECOGNIZED,
        ),
        (
            dict(opposition_roots=("a",)),
            RepresentationStatus.REJECTED,
        ),
        (
            dict(support_roots=("a",), opposition_roots=("b",)),
            RepresentationStatus.CONTESTED,
        ),
    ]
    for overrides, expected in cases:
        values = {
            "principal_kind": RepresentationPrincipalKind.AGENT,
            "principal_resolved": True,
            "principal_declared": False,
            "support_roots": (),
            "opposition_roots": (),
            "office_basis": False,
            "decision_basis": False,
            "written_basis": False,
            "revoked": False,
            "expired": False,
            "superseded": False,
        }
        values.update(cast(Any, overrides))
        status, _ = appraise_representation_recognition(**cast(Any, values))
        assert status is expected


def test_terminal_states_dominate() -> None:
    base = dict(
        principal_kind=RepresentationPrincipalKind.AGENT,
        principal_resolved=True,
        principal_declared=True,
        support_roots=("a",),
        opposition_roots=(),
        office_basis=False,
        decision_basis=False,
        written_basis=False,
    )
    assert (
        appraise_representation_recognition(
            **cast(Any, base), revoked=True, expired=False, superseded=False
        )[0]
        is RepresentationStatus.REVOKED
    )
    assert (
        appraise_representation_recognition(
            **cast(Any, base), revoked=False, expired=True, superseded=False
        )[0]
        is RepresentationStatus.EXPIRED
    )
    assert (
        appraise_representation_recognition(
            **cast(Any, base), revoked=False, expired=False, superseded=True
        )[0]
        is RepresentationStatus.SUPERSEDED
    )


def test_standing_summary_is_read_only_and_excludes_revoked() -> None:
    ledger = _claim_with_positions(
        ("agent-c", RepresentationPositionStance.SUPPORT),
        ("agent-d", RepresentationPositionStance.SUPPORT),
    )
    summary = representation_standing_summary(
        ledger,
        principal_kind=RepresentationPrincipalKind.AGENT,
        principal_ref=_PRINCIPAL,
    )
    assert summary.recognized_representatives == (_REP,)
    assert summary.contested_representatives == ()
    assert summary.revoked_count == 0
    assert summary.coverage == "complete"
    assert not hasattr(summary, "authorized")


def test_owner_guard_and_limits_are_stable() -> None:
    ledger = enforce_representation_limits(_claim_with_positions())
    require_owner_representation(ledger, _OWNER)
    assert representation_ledger_digest(ledger) != representation_ledger_digest(
        _claim_with_positions(("agent-c", RepresentationPositionStance.OPPOSE))
    )
