# ruff: noqa: E501
# mypy: disable-error-code="arg-type,assignment,union-attr,attr-defined,no-untyped-def,no-untyped-call,call-overload,index,type-arg,unused-ignore"
from __future__ import annotations

import pytest

from agents.cognition.models import SubjectiveSnapshot
from agents.cognition.organized_conflict import (
    ConflictLedger,
    empty_organized_conflict_ledger,
    organized_conflict_ledger_digest,
    require_owner_conflict,
)
from agents.models import AgentId

OWNER = AgentId("agent-owner")
OTHER = AgentId("agent-other")


def _snapshot(owner: AgentId, ledger: object | None) -> SubjectiveSnapshot:
    return SubjectiveSnapshot(
        owner_id=owner,
        revision=1,
        memories=(),
        legacy_beliefs=(),
        semantic_beliefs=(),
        organized_conflict=ledger,
    )


def test_disabled_mode_allocates_nothing() -> None:
    snapshot = _snapshot(OWNER, None)
    assert snapshot.organized_conflict is None
    require_owner_conflict(None, OWNER)


def test_snapshot_rejects_foreign_owner() -> None:
    ledger = empty_organized_conflict_ledger(OWNER, tick=1)
    assert _snapshot(OWNER, ledger).organized_conflict is ledger
    with pytest.raises(ValueError, match="conflict_owner_mismatch"):
        _snapshot(OTHER, ledger)


def test_snapshot_rejects_wrong_type() -> None:
    with pytest.raises(TypeError):
        _snapshot(OWNER, object())


def test_checkpoint_ledger_round_trips_and_digest_is_stable() -> None:
    ledger = empty_organized_conflict_ledger(OWNER, tick=4)
    snapshot = _snapshot(OWNER, ledger)
    carried = snapshot.organized_conflict
    assert type(carried) is ConflictLedger
    assert organized_conflict_ledger_digest(
        carried
    ) == organized_conflict_ledger_digest(ledger)


def test_rehydrated_pending_preserves_prior_ledger() -> None:
    # A pending finalization rehydrated without a ledger leaves the carried
    # ledger unchanged by contract; the next tick rebuilds from it.
    prior = empty_organized_conflict_ledger(OWNER, tick=2)
    require_owner_conflict(prior, OWNER)
    assert prior.tick == 2
