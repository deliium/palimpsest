# mypy: ignore-errors
"""Border cursors, fingerprints, and bounded paging."""

from __future__ import annotations

import pytest

from simulation.borders_paging import (
    BorderRowSelection,
    page_border_detail,
    page_border_rows,
)
from simulation.borders_ports import (
    BORDERS_CURSOR_PURPOSES,
    BordersCursor,
    borders_cursor_matches,
    borders_query_fingerprint,
)


def test_exactly_six_cursor_purposes() -> None:
    assert BORDERS_CURSOR_PURPOSES == frozenset(
        {"summary", "claims", "claim", "agreements", "agreement", "control"}
    )


def test_fingerprint_binds_run_publication_digest_purpose_filters() -> None:
    base = dict(
        run_id="run-1",
        publication_id="bd-pub-1",
        digest="a" * 64,
        purpose="claims",
        filters={"layer": "all"},
    )
    fingerprint = borders_query_fingerprint(**base)
    assert len(fingerprint) == 64
    for change in (
        {"run_id": "run-2"},
        {"publication_id": "bd-pub-2"},
        {"digest": "b" * 64},
        {"purpose": "agreements"},
        {"filters": {"layer": "physical"}},
    ):
        values = dict(base)
        values.update(change)
        assert borders_query_fingerprint(**values) != fingerprint


def test_cursor_match_rejects_any_changed_binding() -> None:
    fingerprint = borders_query_fingerprint(
        run_id="run-1",
        publication_id="bd-pub-1",
        digest="a" * 64,
        purpose="summary",
    )
    cursor = BordersCursor("summary", fingerprint)
    assert borders_cursor_matches(cursor, fingerprint)
    assert not borders_cursor_matches(cursor, fingerprint + "x")
    assert not borders_cursor_matches(object(), fingerprint)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        BordersCursor("unknown", fingerprint)
    with pytest.raises(ValueError):
        BordersCursor("summary", "")


def test_detail_cap() -> None:
    with pytest.raises(ValueError):
        borders_query_fingerprint(
            run_id="run-1",
            publication_id="bd-pub-1",
            digest="a" * 64,
            purpose="unknown",
        )


def test_first_next_last_and_empty_pages() -> None:
    rows = (("c",), ("a",), ("b",))
    first = page_border_rows(rows, after_key=None, limit=2, key=lambda row: row[0])
    assert first.rows == (("a",), ("b",))
    assert first.next_key == "b"
    last = page_border_rows(
        rows, after_key=first.next_key, limit=2, key=lambda row: row[0]
    )
    assert last.rows == (("c",),)
    assert last.next_key is None
    empty = page_border_rows((), after_key=None, limit=2)
    assert empty == BorderRowSelection(())


def test_page_limit_bounds_and_invalid_limit() -> None:
    with pytest.raises(ValueError):
        page_border_rows((), after_key=None, limit=0)
    with pytest.raises(ValueError):
        page_border_rows((), after_key=None, limit=501)


def test_paging_is_stable_and_non_mutating() -> None:
    rows = [("b",), ("a",)]
    first = page_border_rows(rows, after_key=None, limit=10, key=lambda row: row[0])
    second = page_border_rows(rows, after_key=None, limit=10, key=lambda row: row[0])
    assert first == second
    assert rows == [("b",), ("a",)]


def test_detail_page_cap() -> None:
    rows = tuple((str(index),) for index in range(600))
    selection = page_border_detail(rows, limit=10, key=lambda row: row[0])
    assert len(selection.rows) == 10
    with pytest.raises(ValueError):
        page_border_detail(rows, limit=501)
