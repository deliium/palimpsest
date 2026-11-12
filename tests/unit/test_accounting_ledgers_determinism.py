"""Byte-level and digest-level accounting determinism."""

# mypy: ignore-errors

from __future__ import annotations

import os
import subprocess
import sys

from agents.cognition.accounting_ledgers import (
    ACCOUNTING_RECORD_PREDICATE,
    AccountingRecordIntegrity,
    AccountingRecordObservation,
    accounting_record_token,
    apply_accounting_ledger_update,
)
from agents.models import AgentId
from analysis.accounting_ledgers_analysis import (
    accounting_ledgers_analysis_digest,
    harvest_accounting_ledgers_analysis,
)
from experiments.accounting_ledgers_publication import (
    compose_accounting_ledgers_snapshot,
)
from simulation.accounting_ledgers_codec import (
    finalize_accounting_ledgers_snapshot,
)
from tests.unit.test_accounting_ledgers_events import _talked


def _ledger():
    observation = AccountingRecordObservation(
        record_token=accounting_record_token("artifact-1"),
        record_genre="agreement",
        integrity=AccountingRecordIntegrity.INTACT,
        content_revision=0,
        relations=(("xch_food", ACCOUNTING_RECORD_PREDICATE, "in2"),),
        tick=1,
    )
    return apply_accounting_ledger_update(
        owner_id=AgentId("owner-1"), tick=1, records=(observation,)
    )


def _run_under_hash_seed(seed: str) -> str:
    code = (
        "from agents.models import AgentId;"
        "from agents.cognition.accounting_ledgers import (" 
        "AccountingRecordObservation, AccountingRecordIntegrity,"
        "accounting_record_token, apply_accounting_ledger_update);"
        "obs=AccountingRecordObservation("
        "record_token=accounting_record_token('artifact-1'),"
        "record_genre='agreement',"
        "integrity=AccountingRecordIntegrity.INTACT,"
        "content_revision=0,"
        "relations=(('xch_food','acc_v1','in2'),),tick=1);"
        "ledger=apply_accounting_ledger_update("
        "owner_id=AgentId('owner-1'),tick=1,records=(obs,));"
        "print(repr(ledger))"
    )
    env = {**os.environ, "PYTHONHASHSEED": seed}
    return subprocess.check_output(
        [sys.executable, "-c", code], env=env, text=True
    )


def test_fold_is_byte_identical_across_hash_seeds() -> None:
    assert _run_under_hash_seed("0") == _run_under_hash_seed("1")


def test_analysis_and_snapshot_digests_are_stable() -> None:
    events = (_talked("ev-a", tick=1), _talked("ev-b", tick=2, sequence=1))
    first = harvest_accounting_ledgers_analysis(run_id="run-1", events=events)
    second = harvest_accounting_ledgers_analysis(
        run_id="run-1", events=tuple(reversed(events))
    )
    assert accounting_ledgers_analysis_digest(first) == (
        accounting_ledgers_analysis_digest(second)
    )
    first_snapshot = finalize_accounting_ledgers_snapshot(
        compose_accounting_ledgers_snapshot(first, run_id="run-1")
    )
    second_snapshot = finalize_accounting_ledgers_snapshot(
        compose_accounting_ledgers_snapshot(second, run_id="run-1")
    )
    assert first_snapshot.digest == second_snapshot.digest
