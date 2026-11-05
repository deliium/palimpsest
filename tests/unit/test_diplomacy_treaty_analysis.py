# mypy: ignore-errors
"""V4-11 treaty harvest rows are detached, token-only, and ordered."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from agents.cognition import (
    TreatyAct,
    TreatyChangeKind,
    TreatyProvisionKind,
    TreatyRecollectionBasis,
    TreatyRecollectionStance,
    TreatySubjectKind,
    apply_diplomacy_update,
)
from agents.cognition.diplomacy_communication import TreatyFrame
from analysis.diplomacy_contract import DiplomacyCoverage
from analysis.diplomacy_layers import DiplomacySubjectiveRow
from analysis.diplomacy_rows import (
    DiplomacyHarvestRows,
    harvest_diplomacy_rows,
)

pytestmark = pytest.mark.unit

OWNER = "alice"
PEER = "bob"
OBS = SimpleNamespace(communications=(), occurrences=())


def _ledgers():
    propose = TreatyFrame(
        act=TreatyAct.TREATY_PROPOSE,
        participant_refs=(f"agent:{OWNER}", f"agent:{PEER}"),
        subject_kind=TreatySubjectKind.CEASEFIRE,
        change_kind=TreatyChangeKind.ORIGINAL,
        provision_kinds=(TreatyProvisionKind.NON_HOSTILITY,),
        terms_digest="a" * 64,
        record_refs=("record-1",),
        institutional_memory_refs=("b" * 64,),
        effective_tick=1,
        envoy_ref=OWNER,
    )
    first = apply_diplomacy_update(
        owner_id=OWNER, tick=1, observation=OBS, prior=None, frames=(propose,)
    )
    renewal = TreatyFrame(
        act=TreatyAct.TREATY_RENEW,
        treaty_ref=first.treaties[0].treaty_id,
        version_ref=first.treaty_versions[0].version_id,
        participant_refs=(f"agent:{OWNER}", f"agent:{PEER}"),
        subject_kind=TreatySubjectKind.CEASEFIRE,
        provision_kinds=(TreatyProvisionKind.NON_HOSTILITY,),
        terms_digest="b" * 64,
        effective_tick=2,
        envoy_ref=OWNER,
    )
    second = apply_diplomacy_update(
        owner_id=OWNER, tick=2, observation=OBS, prior=first, frames=(renewal,)
    )
    recollection = TreatyFrame(
        act=TreatyAct.TREATY_RECOLLECT,
        treaty_ref=first.treaties[0].treaty_id,
        version_ref=first.treaty_versions[0].version_id,
        subject_kind=TreatySubjectKind.CEASEFIRE,
        basis=TreatyRecollectionBasis.DURABLE_RECORD,
        stance=TreatyRecollectionStance.REMEMBER,
        confidence=0.5,
        envoy_ref=OWNER,
    )
    return apply_diplomacy_update(
        owner_id=OWNER, tick=3, observation=OBS, prior=second, frames=(recollection,)
    )


def test_harvest_produces_token_only_treaty_rows() -> None:
    rows = harvest_diplomacy_rows((_ledgers(),))
    assert rows.treaties
    assert rows.treaty_versions
    assert rows.treaty_declarations
    assert rows.treaty_recollections
    assert rows.treaty_anchors
    assert rows.treaty_lineage
    serialized = repr(rows)
    assert OWNER not in serialized
    assert PEER not in serialized
    assert "record-1" in serialized  # opaque anchor is retained, not content
    assert "ceasefire" not in serialized


def test_harvest_is_ordered_by_owner_and_tick() -> None:
    rows = harvest_diplomacy_rows((_ledgers(),))
    for collection in (rows.treaties, rows.treaty_versions):
        keys = [
            (
                row.owner_token,
                getattr(row, "opened_tick", getattr(row, "effective_tick", 0)),
            )
            for row in collection
        ]
        assert keys == sorted(keys)


def test_harvest_coverage_is_complete_without_notices() -> None:
    rows = harvest_diplomacy_rows((_ledgers(),))
    assert rows.coverage is DiplomacyCoverage.COMPLETE
    assert rows.has_any_rows() is True


def test_harvest_coverage_is_partial_with_notices() -> None:
    ledger = _ledgers()
    from dataclasses import replace

    rows = harvest_diplomacy_rows(
        (replace(ledger, notices=("treaty_unknown_treaty",)),)
    )
    assert rows.coverage is DiplomacyCoverage.PARTIAL


def test_existing_constructors_still_work() -> None:
    empty = DiplomacyHarvestRows()
    assert empty.treaties == ()
    assert empty.has_any_rows() is False
    subjective = DiplomacySubjectiveRow(
        owner_token="a" * 16,
        party_token=None,
        status_counts=(),
        lane_counts=(),
    )
    assert subjective.treaty_subject_counts == ()
