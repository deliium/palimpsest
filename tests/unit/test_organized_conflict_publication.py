# ruff: noqa: E501
# mypy: disable-error-code="arg-type,assignment,union-attr,attr-defined,no-untyped-def,no-untyped-call,call-overload,index,type-arg,unused-ignore"
from __future__ import annotations

from types import SimpleNamespace

from agents.cognition.organized_conflict import empty_organized_conflict_ledger
from agents.models import AgentId
from experiments.organized_conflict_publication import (
    build_organized_conflict_harvest_result,
    organized_conflict_publication_document,
    publish_organized_conflict_snapshot,
)
from simulation.runner_models import RunnerStopReasonCode

RUN_ID = "run-conflict-publication"


class _FailingPublisher:
    def publish(self, snapshot):
        raise RuntimeError("boom")


def _result(stop=RunnerStopReasonCode.MAX_TICKS, ledgers=()):
    return SimpleNamespace(
        stop_reason=stop,
        organized_conflict_ledgers=ledgers,
    )


def _ledger():
    return empty_organized_conflict_ledger(AgentId("agent-owner"), tick=3)


def test_incomplete_run_is_unavailable() -> None:
    result = build_organized_conflict_harvest_result(
        _result(stop=RunnerStopReasonCode.CANCELLED, ledgers=(_ledger(),)),
        (),
        run_id=RUN_ID,
    )
    assert result.receipt.status == "unavailable"
    assert result.receipt.reason == "incomplete_run"
    assert result.snapshot is None


def test_no_ledger_is_disabled() -> None:
    result = build_organized_conflict_harvest_result(_result(), (), run_id=RUN_ID)
    assert result.receipt.status == "disabled"
    assert result.receipt.reason == "no_rows"


def test_ready_receipt_counts_match_snapshot() -> None:
    result = build_organized_conflict_harvest_result(
        _result(ledgers=(_ledger(),)), (), run_id=RUN_ID
    )
    assert result.receipt.status == "ready"
    assert result.snapshot is not None
    assert result.receipt.episodes == len(result.snapshot.episodes)
    assert result.receipt.plans == len(result.snapshot.plans)
    assert result.receipt.interpretations == len(result.snapshot.interpretations)
    assert result.snapshot.metric_provenance


def test_publication_failure_does_not_change_result() -> None:
    result = build_organized_conflict_harvest_result(
        _result(ledgers=(_ledger(),)), (), run_id=RUN_ID
    )
    failed = publish_organized_conflict_snapshot(result, _FailingPublisher())
    assert failed.receipt.status == "failed"
    assert failed.receipt.reason == "publication_failed"
    assert failed.snapshot == result.snapshot


def test_receipt_is_metadata_only() -> None:
    result = build_organized_conflict_harvest_result(
        _result(ledgers=(_ledger(),)), (), run_id=RUN_ID
    )
    document = organized_conflict_publication_document(result)
    assert set(document) == {
        "status",
        "reason",
        "publication_id",
        "digest",
        "episodes",
        "plans",
        "interpretations",
        "coverage",
    }
    assert "payload" not in document
