"""Border read-port cursors and bounded detail selection."""

from __future__ import annotations

import pytest

from simulation.borders_ports import (
    BORDERS_CURSOR_PURPOSES,
    BordersCursor,
    borders_cursor_matches,
    borders_query_fingerprint,
    bounded_border_detail_rows,
)


def _fingerprint(purpose: str = "summary") -> str:
    return borders_query_fingerprint(
        run_id="run-1",
        publication_id="bd-pub-1",
        digest="0" * 64,
        purpose=purpose,
    )


def test_six_cursor_purposes_are_closed() -> None:
    assert BORDERS_CURSOR_PURPOSES == {
        "summary",
        "claims",
        "claim",
        "agreements",
        "agreement",
        "control",
    }


def test_cursor_matches_only_the_same_fingerprint() -> None:
    fingerprint = _fingerprint()
    cursor = BordersCursor(purpose="summary", fingerprint=fingerprint)
    assert borders_cursor_matches(cursor, fingerprint)
    assert not borders_cursor_matches(cursor, _fingerprint("claims"))


def test_detail_rows_are_bounded_and_sorted() -> None:
    rows = ("c", "a", "b")
    assert bounded_border_detail_rows(rows, limit=2) == (("a", "b"), True)
    with pytest.raises(ValueError, match="borders_page_limit"):
        bounded_border_detail_rows(rows, limit=0)
