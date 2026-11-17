# mypy: ignore-errors
"""V4-28 replication cursors are purpose-bound, signed, and short-lived."""

from __future__ import annotations

import pytest

from api.replication_cursor import (
    REPLICATION_CURSOR_TTL_SECONDS,
    ReplicationCursorCodec,
    ReplicationCursorError,
)

pytestmark = pytest.mark.unit

KEY = b"k" * 32
PURPOSE = "scientific-replication:designs"


def _encode(codec: ReplicationCursorCodec, *, after: str = "row-1") -> str:
    return codec.encode(
        purpose=PURPOSE,
        run_id="run-1",
        publication_id="srep-1",
        snapshot_digest="d" * 64,
        query_fingerprint="q" * 32,
        after_key=after,
    )


def test_round_trips_every_bound_identity_field() -> None:
    codec = ReplicationCursorCodec(KEY, now=lambda: 1000.0)
    payload = codec.decode(_encode(codec), purpose=PURPOSE)
    assert payload["run_id"] == "run-1"
    assert payload["publication_id"] == "srep-1"
    assert payload["snapshot_digest"] == "d" * 64
    assert payload["query_fingerprint"] == "q" * 32
    assert payload["after_key"] == "row-1"


def test_rejects_keys_shorter_than_32_bytes() -> None:
    with pytest.raises(ValueError):
        ReplicationCursorCodec(b"short")


def test_rejects_foreign_purpose_key_and_tampering() -> None:
    codec = ReplicationCursorCodec(KEY, now=lambda: 1000.0)
    token = _encode(codec)
    with pytest.raises(ReplicationCursorError):
        codec.decode(token, purpose="scientific-replication:results")
    with pytest.raises(ReplicationCursorError):
        ReplicationCursorCodec(b"z" * 32, now=lambda: 1000.0).decode(
            token, purpose=PURPOSE
        )
    tampered = token[:-1] + ("0" if token[-1] != "0" else "1")
    with pytest.raises(ReplicationCursorError):
        codec.decode(tampered, purpose=PURPOSE)
    with pytest.raises(ReplicationCursorError):
        codec.decode("not-a-cursor", purpose=PURPOSE)


def test_expiry_is_distinct_from_invalidity() -> None:
    clock = [1000.0]
    codec = ReplicationCursorCodec(KEY, now=lambda: clock[0])
    token = _encode(codec)
    clock[0] += REPLICATION_CURSOR_TTL_SECONDS - 1
    assert codec.decode(token, purpose=PURPOSE)["after_key"] == "row-1"
    clock[0] += 1
    with pytest.raises(ReplicationCursorError) as excinfo:
        codec.decode(token, purpose=PURPOSE)
    assert excinfo.value.reason_code == "diplomacy_cursor_expired"


def test_oversize_cursor_input_fails_closed() -> None:
    codec = ReplicationCursorCodec(KEY, now=lambda: 1000.0)
    with pytest.raises(ReplicationCursorError):
        codec.decode("a" * 9000, purpose=PURPOSE)


def test_ttl_constant_matches_the_documented_window() -> None:
    assert REPLICATION_CURSOR_TTL_SECONDS == 900
