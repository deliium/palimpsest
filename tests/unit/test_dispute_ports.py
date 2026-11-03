"""V4-07 bounded paging, cursor binding, and read-port contracts."""

from __future__ import annotations

import inspect
from typing import Any

import pytest

import simulation
from simulation import (
    DISPUTE_CURSOR_PURPOSES,
    DisputeCursor,
    DisputePortError,
    DisputePublicationPort,
    DisputeReadPort,
    dispute_cursor_matches,
    dispute_query_fingerprint,
    row_encoded_bytes,
    select_dispute_candidate_rows,
    select_dispute_claim_rows,
    select_dispute_lineage_rows,
    select_dispute_resolution_rows,
)
from tests.unit.test_dispute_snapshot import CANDIDATE, _snapshot

pytestmark = pytest.mark.unit

RUN = "run-1"
PUBLICATION = "disp-pub-0123456789abcdef"
DIGEST = "a" * 64


def _fingerprint(filters: tuple[tuple[str, str], ...] = ()) -> str:
    return dispute_query_fingerprint("claims", RUN, PUBLICATION, filters)


def test_six_cursor_purposes_are_exact() -> None:
    assert DISPUTE_CURSOR_PURPOSES == (
        "summary",
        "candidates",
        "candidate",
        "claims",
        "resolutions",
        "lineage",
    )
    with pytest.raises(DisputePortError) as excinfo:
        DisputeCursor(
            purpose="extra",
            run_id=RUN,
            publication_id=PUBLICATION,
            snapshot_digest=DIGEST,
            offset=0,
            query_fingerprint="b" * 64,
        )
    assert excinfo.value.code == "dispute_cursor_purpose"


def test_paging_is_deterministic_and_whole_row() -> None:
    snapshot = _snapshot()
    first = select_dispute_claim_rows(
        snapshot.claims,
        candidate_id=CANDIDATE,
        role=None,
        offset=0,
        limit=1,
    )
    second = select_dispute_claim_rows(
        snapshot.claims,
        candidate_id=CANDIDATE,
        role=None,
        offset=0,
        limit=1,
    )
    assert first == second
    assert first.truncated is True
    assert first.next_offset == 1
    assert first.items[0] is snapshot.claims[0]
    assert first.encoded_bytes == len(row_encoded_bytes(first.items[0]))
    tail = select_dispute_claim_rows(
        snapshot.claims,
        candidate_id=CANDIDATE,
        role=None,
        offset=1,
        limit=10,
    )
    assert tail.truncated is False
    assert tail.next_offset is None
    assert len(tail.items) == 1
    assert (
        select_dispute_candidate_rows(
            snapshot.candidates, status=None, offset=0, limit=1000
        ).items
        == snapshot.candidates
    )
    assert (
        select_dispute_resolution_rows(
            snapshot.resolutions,
            candidate_id=CANDIDATE,
            status="partially_accepted",
            offset=0,
            limit=10,
        ).items
        == snapshot.resolutions
    )
    assert (
        select_dispute_lineage_rows(
            snapshot.lineage, kind="emerged", offset=0, limit=10
        ).items
        == snapshot.lineage
    )


def test_cursor_binds_run_publication_digest_filter_and_offset() -> None:
    fingerprint = _fingerprint()
    cursor = DisputeCursor(
        purpose="claims",
        run_id=RUN,
        publication_id=PUBLICATION,
        snapshot_digest=DIGEST,
        offset=0,
        query_fingerprint=fingerprint,
    )
    assert dispute_cursor_matches(
        cursor,
        purpose="claims",
        run_id=RUN,
        publication_id=PUBLICATION,
        snapshot_digest=DIGEST,
        offset=0,
        fingerprint=fingerprint,
    )
    for changed in (
        {"purpose": "lineage"},
        {"run_id": "run-2"},
        {"publication_id": "disp-pub-fedcba9876543210"},
        {"snapshot_digest": "c" * 64},
        {"offset": 1},
        {"fingerprint": "d" * 64},
    ):
        arguments: dict[str, Any] = {
            "purpose": "claims",
            "run_id": RUN,
            "publication_id": PUBLICATION,
            "snapshot_digest": DIGEST,
            "offset": 0,
            "fingerprint": fingerprint,
            **changed,
        }
        assert not dispute_cursor_matches(cursor, **arguments)


def test_changed_filter_invalidates_cursor() -> None:
    first = _fingerprint((("role", "claim"),))
    second = _fingerprint((("role", "counterclaim"),))
    assert first != second
    cursor = DisputeCursor(
        purpose="claims",
        run_id=RUN,
        publication_id=PUBLICATION,
        snapshot_digest=DIGEST,
        offset=0,
        query_fingerprint=first,
    )
    assert dispute_cursor_matches(
        cursor,
        purpose="claims",
        run_id=RUN,
        publication_id=PUBLICATION,
        snapshot_digest=DIGEST,
        offset=0,
        fingerprint=first,
    )
    assert not dispute_cursor_matches(
        cursor,
        purpose="claims",
        run_id=RUN,
        publication_id=PUBLICATION,
        snapshot_digest=DIGEST,
        offset=0,
        fingerprint=second,
    )


def test_read_port_has_no_write_method() -> None:
    names = {
        name
        for name, value in DisputeReadPort.__dict__.items()
        if callable(value) and not name.startswith("_")
    }
    assert names == {
        "summary",
        "candidates",
        "candidate",
        "detail",
        "claims",
        "resolutions",
        "lineage",
    }
    assert "publish" not in names
    assert "publish" in DisputePublicationPort.__dict__


def test_port_is_run_id_filter_offset_based_without_session() -> None:
    summary = inspect.signature(DisputeReadPort.summary)
    assert list(summary.parameters) == ["self", "run_id"]
    detail = inspect.signature(DisputeReadPort.detail)
    assert list(detail.parameters) == ["self", "run_id", "candidate_id"]
    candidates = inspect.signature(DisputeReadPort.candidates)
    assert list(candidates.parameters) == [
        "self",
        "run_id",
        "status",
        "offset",
        "limit",
    ]
    claims = inspect.signature(DisputeReadPort.claims)
    assert list(claims.parameters) == [
        "self",
        "run_id",
        "candidate_id",
        "role",
        "offset",
        "limit",
    ]
    assert not hasattr(simulation, "DisputeReadSession")


def test_unknown_candidate_fails_closed() -> None:
    with pytest.raises(DisputePortError) as excinfo:
        simulation.require_known_dispute_candidate(None, "candidate_id")
    assert excinfo.value.code == "dispute_not_found"
    sentinel = object()
    assert (
        simulation.require_known_dispute_candidate(sentinel, "candidate_id") is sentinel
    )
