# mypy: ignore-errors

"""Canonical competing-theory snapshot and atomic filesystem store."""

from __future__ import annotations

import dataclasses

import pytest

import experiments.competing_theories_publication as publication
from analysis.competing_theories_analysis import harvest_competing_theories_analysis
from experiments.competing_theories_publication import (
    compose_competing_theories_snapshot,
)
from persistence.competing_theories_filesystem import (
    FilesystemCompetingTheoriesStore,
)
from simulation.competing_theories_codec import (
    canonical_competing_theories_json,
    decode_competing_theories_snapshot,
    encode_competing_theories_snapshot,
)
from simulation.competing_theories_paging import page_theory_rows
from tests.unit.test_competing_theories_analysis import _facts

pytestmark = pytest.mark.unit


def _snapshot():
    analysis = harvest_competing_theories_analysis(_facts())
    return compose_competing_theories_snapshot(
        analysis, run_id="run-1", publication_id="pub-1"
    )


def test_snapshot_round_trips_canonically() -> None:
    snapshot = _snapshot()
    payload = encode_competing_theories_snapshot(snapshot)
    decoded = decode_competing_theories_snapshot(payload)
    assert decoded == snapshot
    assert canonical_competing_theories_json(decoded) == (
        canonical_competing_theories_json(snapshot)
    )
    page = page_theory_rows(snapshot, section="support", limit=2)
    assert len(page.rows) <= 2
    with pytest.raises(ValueError, match="unsupported"):
        page_theory_rows(snapshot, section="coverage", theory_id="x")


def test_store_is_read_only_idempotent_and_corruption_aware(tmp_path) -> None:
    snapshot = _snapshot()
    store = FilesystemCompetingTheoriesStore(tmp_path)
    first = store.publish(snapshot)
    second = store.publish(snapshot)
    assert first.status == "published"
    assert second.digest == first.digest
    assert store.read("run-1", "pub-1") == snapshot
    assert store.read("run-1") == snapshot
    assert store.read("missing") is None
    path = tmp_path / "run-1" / "pub-1" / "snapshot.json"
    path.write_bytes(b"{}")
    with pytest.raises(ValueError, match="corrupt"):
        store.read("run-1", "pub-1")


def test_conflicting_publication_id_is_rejected(tmp_path) -> None:
    snapshot = _snapshot()
    store = FilesystemCompetingTheoriesStore(tmp_path)
    assert store.publish(snapshot).status == "published"
    conflicting = dataclasses.replace(snapshot, summary=(("claim_count", 99),))
    with pytest.raises(ValueError, match="conflicting"):
        store.publish(conflicting)


def test_cumulative_quota_returns_a_receipt_not_a_partial_write(
    tmp_path, monkeypatch
) -> None:
    import persistence.competing_theories_filesystem as filesystem

    snapshot = _snapshot()
    monkeypatch.setattr(filesystem, "_MAX_TOTAL_BYTES", 10)
    store = FilesystemCompetingTheoriesStore(tmp_path)
    receipt = store.publish(snapshot)
    assert receipt.status == "quota_exceeded"
    assert not (tmp_path / "run-1" / "pub-1" / "manifest.json").exists()


def test_canonical_bytes_are_independent_of_input_order() -> None:
    facts = _facts()
    reordered = dataclasses.replace(
        facts,
        stances=tuple(reversed(facts.stances)),
        citations=tuple(reversed(facts.citations)),
        receipts=tuple(reversed(facts.receipts)),
        owner_last_ticks=tuple(reversed(facts.owner_last_ticks)),
    )
    first = compose_competing_theories_snapshot(
        harvest_competing_theories_analysis(facts),
        run_id="run-1",
        publication_id="pub-1",
    )
    second = compose_competing_theories_snapshot(
        harvest_competing_theories_analysis(reordered),
        run_id="run-1",
        publication_id="pub-1",
    )
    assert canonical_competing_theories_json(first) == (
        canonical_competing_theories_json(second)
    )


def test_case_rows_carry_frozen_vectors_and_only_observed_misses() -> None:
    snapshot = _snapshot()
    predictions = [
        row
        for row in snapshot.predictions
        if row.row_key.startswith("predictions:")
    ]
    assert predictions
    assert all(
        "," in dict(row.fields)["probabilities_milli"] for row in predictions
    )
    failures = [row for row in snapshot.failures if row.row_key.startswith("failures:")]
    assert failures
    assert {dict(row.fields)["observed_category"] for row in failures} == {"summer"}
    assert all(dict(row.fields)["failure_count"] == 1 for row in failures)


def test_snapshot_keeps_newest_whole_windows_and_reports_omission(monkeypatch) -> None:
    facts = _facts()
    shifted = dataclasses.replace(
        facts,
        stances=tuple(
            dataclasses.replace(row, tick=40) for row in facts.stances
        ),
        receipts=tuple(
            dataclasses.replace(row, tick=40) for row in facts.receipts
        ),
        forecasts=tuple(
            dataclasses.replace(
                row,
                issued_tick=40,
                target_tick=42,
                rows=tuple(row.rows),
            )
            for row in facts.forecasts
        ),
        owner_last_ticks=tuple((token, 40) for token, _ in facts.owner_last_ticks),
    )
    analysis = harvest_competing_theories_analysis(shifted)
    full = compose_competing_theories_snapshot(
        analysis, run_id="run-1", publication_id="pub-1"
    )
    assert full.first_retained_window == 0
    assert full.omitted_windows == 0
    newest_rows = tuple(
        row for row in full.theories + full.support + full.citations
        + full.predictions + full.failures + full.transmission + full.coverage
        if row.window_start == 32
        or (row.section == "theories" and row.theory_id in {
            item.theory_id for item in full.predictions if item.window_start == 32
        })
    )
    newest = publication._snapshot(
        run_id="run-1",
        publication_id="pub-1",
        analysis=analysis,
        admitted=(32,),
        rows=newest_rows,
        omitted_windows=1,
    )
    newest_bytes = len(canonical_competing_theories_json(newest))
    monkeypatch.setattr(publication, "MAX_SNAPSHOT_BYTES", newest_bytes + 10)
    truncated = compose_competing_theories_snapshot(
        analysis, run_id="run-1", publication_id="pub-1"
    )
    assert truncated.first_retained_window == 32
    assert truncated.omitted_windows == 1
    monkeypatch.setattr(publication, "MAX_SNAPSHOT_BYTES", newest_bytes - 1)
    with pytest.raises(publication.TheorySnapshotOverflow):
        compose_competing_theories_snapshot(
            analysis, run_id="run-1", publication_id="pub-1"
        )
