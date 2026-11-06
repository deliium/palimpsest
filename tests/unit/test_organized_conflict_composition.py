# ruff: noqa: E501
# mypy: disable-error-code="arg-type,assignment,union-attr,attr-defined,no-untyped-def,no-untyped-call,call-overload,index,type-arg,unused-ignore"
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from research_runner.organized_conflict_composition import (
    OrganizedConflictProducerOptions,
    publish_organized_conflict_harvest,
    write_organized_conflict_receipt,
)


def _result() -> SimpleNamespace:
    return SimpleNamespace(
        stop_reason=SimpleNamespace(value="max_ticks"),
        organized_conflict_ledgers=(),
    )


def test_unset_root_disables_producer() -> None:
    receipt = publish_organized_conflict_harvest(
        _result(),
        OrganizedConflictProducerOptions(),
        committed_events=(),
        run_id="run-conflict-composition",
    )
    assert receipt["status"] == "disabled"
    assert receipt["reason"] == "root_unset"


def test_receipt_is_metadata_only_and_atomic(tmp_path: Path) -> None:
    receipt = publish_organized_conflict_harvest(
        _result(),
        OrganizedConflictProducerOptions(root=tmp_path / "store"),
        committed_events=(),
        run_id="run-conflict-composition",
    )
    write_organized_conflict_receipt(tmp_path, "run-conflict-composition", receipt)
    path = tmp_path / "organized-conflict-publication-run-conflict-composition.json"
    stored = json.loads(path.read_text(encoding="utf-8"))
    assert stored["status"] == "disabled"
    assert stored["reason"] == "no_rows"
    assert "prompt" not in stored
    assert "payload" not in stored
