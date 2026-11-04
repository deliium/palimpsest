"""V4-09 representation records, ordering, truncation, and digests."""

from __future__ import annotations

from dataclasses import replace

import pytest

from agents.cognition import (
    REPRESENTATION_POLICY_VERSION,
    RepresentationConflict,
    RepresentationConflictKind,
    RepresentationDurationKind,
    RepresentationError,
    RepresentationLedger,
    RepresentationMandate,
    RepresentationPolicy,
    RepresentationPosition,
    RepresentationPositionStance,
    RepresentationPrincipalKind,
    RepresentationProvenance,
    RepresentationRecognitionBasis,
    RepresentationRevocation,
    RepresentationRevocationKind,
    RepresentationScopeKind,
    RepresentationStatus,
)
from agents.cognition.delegation_representation import (
    default_representation_policy,
    empty_representation_ledger,
    enforce_representation_limits,
    representation_conflict_id,
    representation_ledger_digest,
    representation_mandate_id,
    representation_position_id,
    representation_revocation_id,
    require_owner_representation,
)

pytestmark = pytest.mark.unit

_OWNER = "agent-owner"


def _mandate(
    *,
    owner: str = _OWNER,
    tick: int = 1,
    principal_kind: RepresentationPrincipalKind = RepresentationPrincipalKind.AGENT,
    principal_ref: str | None = "agent-principal",
    representative: str = "agent-representative",
    scope_kind: RepresentationScopeKind = RepresentationScopeKind.SPEAK_FOR,
    scope_subject: str | None = "border",
    duration: RepresentationDurationKind = RepresentationDurationKind.UNTIL_REVOKED,
    end_tick: int | None = None,
    status: RepresentationStatus = RepresentationStatus.CLAIMED,
    basis: RepresentationRecognitionBasis = RepresentationRecognitionBasis.NONE,
    principal_resolved: bool = True,
    principal_declared: bool = False,
    revoked: bool = False,
    expired: bool = False,
    superseded: bool = False,
) -> RepresentationMandate:
    mandate_id = representation_mandate_id(
        owner,
        tick,
        principal_kind,
        principal_ref,
        representative,
        scope_kind,
        scope_subject,
        duration,
    )
    return RepresentationMandate(
        mandate_id=mandate_id,
        principal_kind=principal_kind,
        principal_ref=principal_ref,
        representative_id=representative,
        scope_kind=scope_kind,
        scope_subject=scope_subject,
        duration_kind=duration,
        start_tick=tick,
        end_tick=end_tick,
        provenance=RepresentationProvenance.SELF_DECLARED,
        attributed_actor_id=representative,
        evidence_refs=(),
        decision_refs=(),
        office_refs=(),
        rule_refs=(),
        confidence=0.5,
        principal_resolved=principal_resolved,
        principal_declared=principal_declared,
        office_basis=False,
        decision_basis=False,
        written_basis=False,
        revoked=revoked,
        expired=expired,
        superseded=superseded,
        status=status,
        recognition_basis=basis,
        revision=0,
    )


def _position(
    mandate: RepresentationMandate,
    *,
    actor: str = "agent-supporter",
    stance: RepresentationPositionStance = RepresentationPositionStance.SUPPORT,
    tick: int = 2,
    ordinal: int = 0,
) -> RepresentationPosition:
    return RepresentationPosition(
        position_id=representation_position_id(
            _OWNER, mandate.mandate_id, actor, tick, stance, ordinal
        ),
        mandate_id=mandate.mandate_id,
        actor_id=actor,
        stance=stance,
        root_ref=None,
        provenance=RepresentationProvenance.COMMUNICATED,
        tick=tick,
        active=True,
    )


def _revocation(
    mandate: RepresentationMandate,
    *,
    actor: str = "agent-principal",
    kind: RepresentationRevocationKind = RepresentationRevocationKind.PRINCIPAL_REVOKED,
) -> RepresentationRevocation:
    return RepresentationRevocation(
        revocation_id=representation_revocation_id(
            _OWNER, mandate.mandate_id, actor, 3, kind, 0
        ),
        mandate_id=mandate.mandate_id,
        actor_id=actor,
        kind=kind,
        provenance=RepresentationProvenance.PRINCIPAL_DECLARED,
        tick=3,
        contested=False,
    )


def _conflict(
    first: RepresentationMandate,
    second: RepresentationMandate,
    *,
    kind: RepresentationConflictKind = RepresentationConflictKind.DUPLICATE_MANDATE,
) -> RepresentationConflict:
    mandate_ids = tuple(sorted((first.mandate_id, second.mandate_id)))
    return RepresentationConflict(
        conflict_id=representation_conflict_id(_OWNER, mandate_ids, kind, 4),
        mandate_ids=mandate_ids,
        kind=kind,
        status="unresolved",
        tick=4,
    )


def _ledger(
    *,
    mandates: tuple[RepresentationMandate, ...] = (),
    positions: tuple[RepresentationPosition, ...] = (),
    revocations: tuple[RepresentationRevocation, ...] = (),
    conflicts: tuple[RepresentationConflict, ...] = (),
    first_tick: int = 0,
    last_tick: int = 5,
    region_anchors: tuple[str, ...] = (),
) -> RepresentationLedger:
    return RepresentationLedger(
        owner_id=_OWNER,
        mandates=mandates,
        positions=positions,
        revocations=revocations,
        conflicts=conflicts,
        region_anchors=region_anchors,
        first_tick=first_tick,
        last_tick=last_tick,
    )


def test_policy_version_is_locked() -> None:
    assert REPRESENTATION_POLICY_VERSION == "delegation-representation.v1"
    assert default_representation_policy() == RepresentationPolicy()


def test_duration_validation_matrix() -> None:
    assert (
        _mandate(duration=RepresentationDurationKind.SINGLE_ACT, end_tick=1).end_tick
        == 1
    )
    assert (
        _mandate(duration=RepresentationDurationKind.OCCASION, end_tick=4).end_tick == 4
    )
    assert (
        _mandate(duration=RepresentationDurationKind.UNTIL_TICK, end_tick=9).end_tick
        == 9
    )
    assert _mandate(duration=RepresentationDurationKind.UNTIL_REVOKED).end_tick is None
    assert _mandate(duration=RepresentationDurationKind.UNKNOWN).end_tick is None

    for duration, end_tick in (
        (RepresentationDurationKind.SINGLE_ACT, None),
        (RepresentationDurationKind.SINGLE_ACT, 2),
        (RepresentationDurationKind.OCCASION, None),
        (RepresentationDurationKind.UNTIL_TICK, None),
        (RepresentationDurationKind.UNTIL_REVOKED, 4),
        (RepresentationDurationKind.UNKNOWN, 4),
    ):
        with pytest.raises(RepresentationError) as excinfo:
            _mandate(duration=duration, end_tick=end_tick)
        assert excinfo.value.code == "representation_invalid_duration"


def test_principal_validation_matrix() -> None:
    collective = "orgc-" + "1" * 16
    assert (
        _mandate(
            principal_kind=RepresentationPrincipalKind.ORGANIZATION,
            principal_ref=collective,
        ).principal_ref
        == collective
    )
    assert (
        _mandate(
            principal_kind=RepresentationPrincipalKind.COALITION,
            principal_ref=collective,
        ).principal_ref
        == collective
    )
    assert (
        _mandate(
            principal_kind=RepresentationPrincipalKind.SETTLEMENT,
            principal_ref="region-1",
        ).principal_ref
        == "region-1"
    )
    assert (
        _mandate(
            principal_kind=RepresentationPrincipalKind.UNKNOWN,
            principal_ref=None,
            principal_resolved=False,
        ).principal_ref
        is None
    )

    with pytest.raises(RepresentationError, match="representation_invalid_principal"):
        _mandate(
            principal_kind=RepresentationPrincipalKind.AGENT,
            principal_ref="agent-representative",
        )
    with pytest.raises(RepresentationError, match="representation_invalid_principal"):
        _mandate(
            principal_kind=RepresentationPrincipalKind.ORGANIZATION,
            principal_ref="not-a-concept",
        )
    with pytest.raises(RepresentationError, match="representation_invalid_principal"):
        _mandate(
            principal_kind=RepresentationPrincipalKind.UNKNOWN,
            principal_ref=None,
            principal_resolved=True,
        )


def test_ordering_is_permutation_independent_and_digest_stable() -> None:
    first = _mandate(tick=1)
    second = _mandate(tick=2, representative="agent-other")
    first_position = _position(first, tick=3)
    second_position = _position(second, actor="agent-other", tick=2)
    forward = _ledger(
        mandates=(first, second),
        positions=(first_position, second_position),
    )
    backward = _ledger(
        mandates=(second, first),
        positions=(second_position, first_position),
    )
    assert forward.mandates == backward.mandates
    assert forward.positions == backward.positions
    assert representation_ledger_digest(forward) == representation_ledger_digest(
        backward
    )


def test_duplicate_and_unknown_references_fail_closed() -> None:
    mandate = _mandate()
    with pytest.raises(RepresentationError, match="representation_duplicate_id"):
        _ledger(mandates=(mandate, mandate))
    orphan = replace(_position(mandate), mandate_id="rmd-" + "0" * 16)
    with pytest.raises(RepresentationError, match="representation_unknown_reference"):
        _ledger(mandates=(mandate,), positions=(orphan,))


def test_tick_regression_fails_closed() -> None:
    with pytest.raises(RepresentationError, match="representation_tick_regression"):
        _ledger(mandates=(_mandate(tick=5),), first_tick=0, last_tick=4)
    with pytest.raises(RepresentationError, match="representation_tick_regression"):
        _ledger(first_tick=6, last_tick=5)


def test_truncation_is_explicit_and_never_deletes_recognized() -> None:
    claimed = tuple(
        _mandate(tick=index, representative=f"agent-{index}") for index in range(33)
    )
    limited = enforce_representation_limits(_ledger(mandates=claimed, last_tick=40))
    assert len(limited.mandates) == 32
    assert limited.pruned_mandates == 1
    assert limited.coverage == "partial"
    assert "representation_truncated" in limited.notices

    recognized = tuple(
        _mandate(
            tick=index,
            representative=f"agent-{index}",
            principal_declared=True,
            status=RepresentationStatus.RECOGNIZED,
            basis=RepresentationRecognitionBasis.PRINCIPAL_DECLARATION,
        )
        for index in range(33)
    )
    capped = enforce_representation_limits(_ledger(mandates=recognized, last_tick=40))
    assert len(capped.mandates) == 33
    assert capped.pruned_mandates == 0
    assert "representation_capacity_reached" in capped.notices


def test_owner_guard_accepts_same_owner_and_rejects_foreign() -> None:
    ledger = empty_representation_ledger(_OWNER)
    require_owner_representation(ledger, _OWNER)
    require_owner_representation(ledger, type("Owner", (), {"value": _OWNER})())
    with pytest.raises(RepresentationError, match="representation_invalid_owner"):
        require_owner_representation(ledger, "agent-other")
    with pytest.raises(TypeError, match="RepresentationLedger"):
        require_owner_representation(object(), _OWNER)


def test_revocations_and_conflicts_are_retained_and_ordered() -> None:
    first = _mandate(tick=1)
    second = _mandate(tick=2, representative="agent-other")
    revocation = _revocation(first)
    conflict = _conflict(first, second)
    ledger = _ledger(
        mandates=(second, first),
        revocations=(revocation,),
        conflicts=(conflict,),
    )
    assert len(ledger.revocations) == 1
    assert len(ledger.conflicts) == 1
    assert ledger.conflicts[0].mandate_ids == tuple(
        sorted((first.mandate_id, second.mandate_id))
    )
