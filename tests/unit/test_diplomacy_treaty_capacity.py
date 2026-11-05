# mypy: ignore-errors
"""V4-11 treaty caps, truncation, and protected rows."""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest

from agents.cognition import (
    DiplomacyError,
    DiplomaticProvenance,
    DiplomaticTreaty,
    DiplomaticTreatyRecollection,
    TreatyAct,
    TreatyChangeKind,
    TreatyProvisionKind,
    TreatyRecollectionBasis,
    TreatyRecollectionStance,
    TreatySubjectKind,
    apply_diplomacy_update,
    default_diplomacy_policy,
    default_treaty_policy,
    diplomacy_treaty_recollection_id,
    enforce_diplomacy_limits,
)
from agents.cognition.diplomacy_communication import TreatyFrame

pytestmark = pytest.mark.unit

OWNER = "alice"
PEER = "bob"
OBS = SimpleNamespace(communications=(), occurrences=())


def _ledger():
    frame = TreatyFrame(
        act=TreatyAct.TREATY_PROPOSE,
        participant_refs=(f"agent:{OWNER}", f"agent:{PEER}"),
        subject_kind=TreatySubjectKind.CEASEFIRE,
        change_kind=TreatyChangeKind.ORIGINAL,
        provision_kinds=(TreatyProvisionKind.NON_HOSTILITY,),
        terms_digest="a" * 64,
        effective_tick=1,
        envoy_ref=OWNER,
    )
    return apply_diplomacy_update(
        owner_id=OWNER, tick=1, observation=OBS, prior=None, frames=(frame,)
    )


def _recollections(count: int) -> tuple[DiplomaticTreatyRecollection, ...]:
    rows = []
    for index in range(count):
        row_id = diplomacy_treaty_recollection_id(
            OWNER,
            "dpg-" + f"{index:016x}",
            "dpv-" + f"{index:016x}",
            TreatyRecollectionBasis.DURABLE_RECORD,
            TreatyRecollectionStance.REMEMBER,
            index + 1,
        )
        rows.append(
            DiplomaticTreatyRecollection(
                recollection_id=row_id,
                treaty_ref="dpg-" + f"{index:016x}",
                version_ref="dpv-" + f"{index:016x}",
                subject_kind=TreatySubjectKind.CEASEFIRE,
                basis=TreatyRecollectionBasis.DURABLE_RECORD,
                stance=TreatyRecollectionStance.REMEMBER,
                claimed_terms_digest="a" * 64,
                confidence=0.5,
                first_tick=index + 1,
                last_tick=index + 1,
                independence_ref=None,
                provenance=DiplomaticProvenance.COMMUNICATED,
                revision=0,
            )
        )
    return tuple(rows)


def test_truncation_drops_only_the_oldest_recollections() -> None:
    ledger = _ledger()
    rows = _recollections(65)
    ledger = replace(ledger, tick=70, treaty_recollections=rows)
    limited = enforce_diplomacy_limits(
        ledger,
        policy=default_diplomacy_policy(),
        treaty_policy=default_treaty_policy(),
    )
    assert len(limited.treaty_recollections) == (
        default_treaty_policy().max_treaty_recollections
    )
    assert "diplomacy_truncated:treaty_recollections" in limited.notices
    assert limited.treaties == ledger.treaties
    assert limited.treaty_versions == ledger.treaty_versions


def test_treaty_and_version_rows_are_never_age_dropped() -> None:
    ledger = _ledger()
    rows = _recollections(65)
    ledger = replace(
        ledger,
        tick=70,
        treaty_recollections=rows,
        notices=("diplomacy_truncated:treaty_recollections",),
    )
    limited = enforce_diplomacy_limits(
        ledger,
        policy=default_diplomacy_policy(),
        treaty_policy=default_treaty_policy(),
    )
    assert len(limited.treaties) == 1
    assert len(limited.treaty_versions) == 1
    assert len(limited.treaty_declarations) == 1


def test_participant_cap_fails_with_treaty_capacity_code() -> None:
    participants = tuple(f"agent-{index:02d}" for index in range(33))
    with pytest.raises(DiplomacyError, match="treaty_capacity_reached"):
        DiplomaticTreaty(
            treaty_id="dpg-" + "0" * 16,
            relation_id="dpl-" + "0" * 16,
            participant_party_ids=participants,
            subject_kind=TreatySubjectKind.CEASEFIRE,
            current_version_id="dpv-" + "0" * 16,
            opened_tick=1,
            last_tick=1,
            provenance=DiplomaticProvenance.SELF_DECLARED,
            revision=0,
        )


def test_policy_is_locked_and_not_runtime_tunable() -> None:
    policy = default_treaty_policy()
    assert policy.max_treaty_recollections == 64
    with pytest.raises(DiplomacyError):
        replace(policy, max_treaty_recollections=65)
