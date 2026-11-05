# mypy: ignore-errors
"""V4-11 treaty composition into diplomacy-snapshot-v2."""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest

from agents.cognition import (
    TreatyAct,
    TreatyChangeKind,
    TreatyProvisionKind,
    TreatySubjectKind,
    apply_diplomacy_update,
)
from agents.cognition.diplomacy_communication import TreatyFrame
from experiments.diplomacy_harvest import build_completed_run_diplomacy_harvest
from experiments.diplomacy_publication import (
    build_diplomacy_harvest_result,
    diplomacy_publication_document,
)
from simulation.diplomacy_models import DIPLOMACY_SNAPSHOT_SCHEMA_VERSION_V2

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


def _result():
    ledger = _ledger()
    return build_completed_run_diplomacy_harvest(
        SimpleNamespace(
            run_id=SimpleNamespace(value="run-1"),
            ticks_committed=1,
            diplomacy_ledgers=(ledger,),
        )
    )


def test_completed_harvest_composes_v2_treaty_rows() -> None:
    harvest = _result()
    built = build_diplomacy_harvest_result(
        harvest, run_id="run-1", revision="rev-1", window_end=1
    )
    assert built.snapshot is not None
    snapshot = built.snapshot
    assert snapshot.schema_version == DIPLOMACY_SNAPSHOT_SCHEMA_VERSION_V2
    assert len(snapshot.treaties) == 1
    assert len(snapshot.treaty_versions) == 1
    assert len(snapshot.treaty_declarations) == 1
    assert snapshot.treaties[0].status == "proposed"
    assert (
        snapshot.treaties[0].subject_kind == snapshot.treaties[0].subject_kind.lower()
    )
    assert snapshot.treaty_versions[0].status == "proposed"


def test_receipt_counts_are_additive_and_metadata_only() -> None:
    harvest = _result()
    built = build_diplomacy_harvest_result(
        harvest, run_id="run-1", revision="rev-1", window_end=1
    )
    receipt = built.receipt
    assert receipt["treaties"] == 1
    assert receipt["treaty_versions"] == 1
    assert receipt["treaty_recollections"] == 0
    for value in receipt.values():
        if isinstance(value, str):
            assert OWNER not in value
            assert PEER not in value
    document = diplomacy_publication_document(receipt)
    assert document["treaties"] == 1


def _accept(ledger, party: str, *, tick: int, envoy: str | None = None):
    frame = TreatyFrame(
        act=TreatyAct.TREATY_ACCEPT,
        treaty_ref=ledger.treaties[0].treaty_id,
        version_ref=ledger.treaty_versions[-1].version_id,
        party_ref=party,
        envoy_ref=envoy or party,
        actor_ref=envoy or party,
        participant_refs=(f"agent:{OWNER}", f"agent:{PEER}"),
    )
    return apply_diplomacy_update(
        owner_id=OWNER, tick=tick, observation=OBS, prior=ledger, frames=(frame,)
    )


def _renew(ledger, *, tick: int):
    frame = TreatyFrame(
        act=TreatyAct.TREATY_RENEW,
        treaty_ref=ledger.treaties[0].treaty_id,
        version_ref=ledger.treaty_versions[-1].version_id,
        participant_refs=(f"agent:{OWNER}", f"agent:{PEER}"),
        subject_kind=TreatySubjectKind.CEASEFIRE,
        provision_kinds=(TreatyProvisionKind.NON_HOSTILITY,),
        terms_digest="b" * 64,
        effective_tick=tick,
        envoy_ref=OWNER,
    )
    return apply_diplomacy_update(
        owner_id=OWNER, tick=tick, observation=OBS, prior=ledger, frames=(frame,)
    )


def _compose(ledger, *, tick: int):
    harvest = build_completed_run_diplomacy_harvest(
        SimpleNamespace(
            run_id=SimpleNamespace(value="run-1"),
            ticks_committed=tick,
            diplomacy_ledgers=(ledger,),
        )
    )
    return build_diplomacy_harvest_result(
        harvest, run_id="run-1", revision="rev-1", window_end=tick
    )


def test_publication_status_matches_representative_aware_cognition() -> None:
    ledger = _ledger()
    ledger = _accept(ledger, OWNER, tick=2)
    ledger = _accept(ledger, PEER, tick=3, envoy="unrecognized-envoy")
    built = _compose(ledger, tick=3)
    assert built.snapshot is not None
    assert built.snapshot.treaty_versions[0].status == "proposed"
    assert built.snapshot.treaties[0].status == "proposed"

    ledger = _accept(ledger, PEER, tick=4)
    built = _compose(ledger, tick=4)
    assert built.snapshot is not None
    assert built.snapshot.treaty_versions[0].status == "apparently_accepted"


def test_publication_preserves_supersession_labels() -> None:
    ledger = _ledger()
    ledger = _accept(ledger, OWNER, tick=2)
    ledger = _accept(ledger, PEER, tick=3)
    ledger = _renew(ledger, tick=4)
    ledger = _accept(ledger, OWNER, tick=5)
    ledger = _accept(ledger, PEER, tick=6)
    built = _compose(ledger, tick=6)
    assert built.snapshot is not None
    by_index = {
        row.version_index: row.status for row in built.snapshot.treaty_versions
    }
    assert by_index == {1: "superseded", 2: "apparently_accepted"}
    assert built.snapshot.treaties[0].status == "apparently_accepted"
    assert built.receipt["treaty_accepted"] == 1


def test_zero_treaty_diplomacy_run_records_all_four_treaty_families() -> None:
    ledger = replace(
        _ledger(),
        treaties=(),
        treaty_versions=(),
        treaty_declarations=(),
        treaty_recollections=(),
        treaty_misrepresentations=(),
    )
    built = _compose(ledger, tick=1)
    assert built.snapshot is not None
    assert built.snapshot.treaties == ()
    for family in (
        "treaty_structure",
        "treaty_version_lineage",
        "treaty_recollection",
        "treaty_anchor_coverage",
    ):
        assert family in built.snapshot.metric_families


def test_incomplete_run_is_unavailable() -> None:
    built = build_diplomacy_harvest_result(
        _result(),
        run_id="run-1",
        revision="rev-1",
        window_end=1,
        stop_reason="cancelled",
    )
    assert built.receipt["status"] == "unavailable"
    assert built.snapshot is None


def test_no_diplomacy_rows_is_disabled() -> None:
    built = build_diplomacy_harvest_result(
        None, run_id="run-1", revision="rev-1", window_end=1
    )
    assert built.receipt["status"] == "disabled"


def test_treaty_metric_families_are_recorded_when_present() -> None:
    built = build_diplomacy_harvest_result(
        _result(), run_id="run-1", revision="rev-1", window_end=1
    )
    assert built.snapshot is not None
    assert "treaty_structure" in built.snapshot.metric_families
    assert "treaty_version_lineage" in built.snapshot.metric_families
