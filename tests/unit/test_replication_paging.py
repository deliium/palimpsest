# mypy: ignore-errors
"""V4-28 keyset paging is complete, stable, signed, and query-bound."""

from __future__ import annotations

import pytest

from simulation.replication_paging import (
    PAGE_LIMIT_MAX,
    ReplicationPage,
    page_replication_rows,
)
from simulation.replication_ports import ReplicationPublicationError

pytestmark = pytest.mark.unit

KEY = b"k" * 32
RUN = "run-1"
PUBLICATION = "srep-1"
QUERY = "q" * 32


def _rows(count: int) -> tuple[dict[str, object], ...]:
    return tuple(
        {
            "row_token": f"rrow-{index:04d}",
            "window_index": index // 100,
            "row_kind": "report" if index % 2 else "execution",
            "layer": "owner_scoped" if index % 2 else "objective",
        }
        for index in range(count)
    )


def _page(
    rows,
    *,
    limit=100,
    cursor=None,
    query=QUERY,
    run_id=RUN,
    publication=PUBLICATION,
):
    return page_replication_rows(
        rows,
        run_id=run_id,
        publication_id=publication,
        query_fingerprint=query,
        limit=limit,
        cursor=cursor,
        cursor_key=KEY,
    )


def test_pages_cover_every_row_once_in_stable_order() -> None:
    rows = tuple(reversed(_rows(501)))
    collected: list[dict[str, object]] = []
    cursor = None
    pages = 0
    while True:
        page = _page(rows, limit=100, cursor=cursor)
        assert isinstance(page, ReplicationPage)
        collected.extend(page.rows)
        pages += 1
        if page.next_cursor is None:
            break
        cursor = page.next_cursor
    assert pages == 6
    tokens = [row["row_token"] for row in collected]
    assert len(tokens) == 501
    assert len(set(tokens)) == 501
    assert tokens == sorted(tokens)


def test_both_result_variants_survive_paging_without_collision() -> None:
    rows = _rows(4)
    page = _page(rows, limit=10)
    kinds = [row["row_kind"] for row in page.rows]
    assert kinds.count("execution") == 2
    assert kinds.count("report") == 2
    assert page.truncated is False


def test_limit_is_bounded_and_validated() -> None:
    rows = _rows(3)
    for invalid in (0, -1, True, "5", 1.5):
        with pytest.raises(ReplicationPublicationError) as excinfo:
            _page(rows, limit=invalid)  # type: ignore[arg-type]
        assert excinfo.value.code == "replication_paging_invalid_limit"
    assert PAGE_LIMIT_MAX == 500
    assert len(_page(_rows(600), limit=PAGE_LIMIT_MAX).rows) == PAGE_LIMIT_MAX


def test_cursor_is_bound_to_run_publication_and_query() -> None:
    rows = _rows(5)
    cursor = _page(rows, limit=2).next_cursor
    assert cursor is not None
    for kwargs in (
        {"run_id": "run-2"},
        {"publication": "srep-2"},
        {"query": "z" * 32},
    ):
        with pytest.raises(ReplicationPublicationError) as excinfo:
            _page(rows, limit=2, cursor=cursor, **kwargs)  # type: ignore[arg-type]
        assert excinfo.value.code == "replication_paging_invalid_cursor"


def test_tampered_or_foreign_cursor_fails_closed() -> None:
    rows = _rows(5)
    cursor = _page(rows, limit=2).next_cursor
    assert cursor is not None
    with pytest.raises(ReplicationPublicationError):
        _page(rows, limit=2, cursor=cursor[:-1] + "0")
    with pytest.raises(ReplicationPublicationError):
        page_replication_rows(
            rows,
            run_id=RUN,
            publication_id=PUBLICATION,
            query_fingerprint=QUERY,
            limit=2,
            cursor=cursor,
            cursor_key=b"z" * 32,
        )
