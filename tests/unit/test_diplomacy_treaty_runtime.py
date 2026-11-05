# mypy: ignore-errors
"""V4-11 treaty rows travel inside the existing diplomacy ledger and result."""

from __future__ import annotations

from dataclasses import fields
from types import SimpleNamespace

import pytest

from agents.cognition import (
    DiplomacyError,
    TreatyAct,
    TreatyChangeKind,
    TreatyProvisionKind,
    TreatySubjectKind,
    apply_diplomacy_update,
    diplomacy_ledger_digest,
    require_owner_diplomacy,
)
from agents.cognition.diplomacy_communication import TreatyFrame
from simulation.runner_models import SimulationRunnerResult

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


def test_digest_is_stable_for_equal_treaty_rows() -> None:
    first = _ledger()
    second = _ledger()
    assert diplomacy_ledger_digest(first) == diplomacy_ledger_digest(second)
    assert len(first.treaties) == 1
    assert len(first.treaty_versions) == 1
    assert len(first.treaty_declarations) == 1


def test_owner_mismatch_still_fails_closed() -> None:
    ledger = _ledger()
    require_owner_diplomacy(ledger, OWNER)
    with pytest.raises(DiplomacyError, match="diplomacy_owner_mismatch"):
        require_owner_diplomacy(ledger, "mallory")


def test_result_document_field_set_is_unchanged() -> None:
    names = {field.name for field in fields(SimulationRunnerResult)}
    assert "diplomacy_ledgers" in names
    assert "treaty_ledgers" not in names
    assert "treaties" not in names


def test_diplomacy_ledgers_remains_ordered_tuple() -> None:
    field = next(
        field
        for field in fields(SimulationRunnerResult)
        if field.name == "diplomacy_ledgers"
    )
    assert field.default == ()
