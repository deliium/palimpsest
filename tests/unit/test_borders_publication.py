"""Border publication receipts stay outside scientific status."""

from __future__ import annotations

from types import SimpleNamespace

from experiments.borders_publication import (
    borders_publication_document,
    build_borders_harvest_result,
)


def test_incomplete_run_is_unavailable() -> None:
    runner = SimpleNamespace(
        stop_reason=SimpleNamespace(value="cancelled"),
        border_ledgers=(),
    )
    result = build_borders_harvest_result(runner, (), "run-1")
    assert result.snapshot is None
    assert result.receipt.status == "unavailable"


def test_missing_ledgers_is_disabled() -> None:
    runner = SimpleNamespace(
        stop_reason=SimpleNamespace(value="max_ticks"),
        border_ledgers=(),
    )
    result = build_borders_harvest_result(runner, (), "run-1")
    assert result.receipt.status == "disabled"
    document = borders_publication_document(result.receipt)
    assert "winner" not in document
    assert "score" not in document
