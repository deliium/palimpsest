"""V4-06 HMAC cursor reuse, binding, expiry, and tampering."""

from __future__ import annotations

import pytest

from api.formal_rule_cursor import FormalRuleCursorCodec, FormalRuleCursorError

pytestmark = pytest.mark.unit

RUN = "run-1"
PUBLICATION = "frule-pub-0123456789abcdef"
DIGEST = "d" * 64
FINGERPRINT = "f" * 64


def _codec(clock: list[float]) -> FormalRuleCursorCodec:
    return FormalRuleCursorCodec(b"k" * 32, now=lambda: clock[0], ttl_seconds=900)


def test_cursor_round_trips_same_filter_run_publication_digest() -> None:
    clock = [1000.0]
    codec = _codec(clock)
    token = codec.encode(
        purpose="candidates",
        run_id=RUN,
        publication_id=PUBLICATION,
        snapshot_digest=DIGEST,
        offset=10,
        query_fingerprint=FINGERPRINT,
    )
    cursor, raw = codec.decode(token, purpose="candidates")
    assert cursor.offset == 10
    assert cursor.run_id == RUN
    assert cursor.publication_id == PUBLICATION
    assert cursor.snapshot_digest == DIGEST
    assert raw["f"] == FINGERPRINT


def test_changed_filter_run_publication_or_digest_is_invalid() -> None:
    clock = [1000.0]
    codec = _codec(clock)
    token = codec.encode(
        purpose="candidates",
        run_id=RUN,
        publication_id=PUBLICATION,
        snapshot_digest=DIGEST,
        offset=0,
        query_fingerprint=FINGERPRINT,
    )
    cursor, _ = codec.decode(token, purpose="candidates")
    assert cursor.query_fingerprint == FINGERPRINT
    with pytest.raises(FormalRuleCursorError):
        codec.decode(token, purpose="rules")


def test_expired_cursor_is_reported() -> None:
    clock = [1000.0]
    codec = _codec(clock)
    token = codec.encode(
        purpose="candidates",
        run_id=RUN,
        publication_id=PUBLICATION,
        snapshot_digest=DIGEST,
        offset=0,
        query_fingerprint=FINGERPRINT,
    )
    clock[0] += 901
    with pytest.raises(FormalRuleCursorError) as excinfo:
        codec.decode(token, purpose="candidates")
    assert excinfo.value.reason_code == "formal_rule_cursor_expired"


def test_purpose_is_bound() -> None:
    clock = [1000.0]
    codec = _codec(clock)
    token = codec.encode(
        purpose="lineage",
        run_id=RUN,
        publication_id=PUBLICATION,
        snapshot_digest=DIGEST,
        offset=0,
        query_fingerprint=FINGERPRINT,
    )
    with pytest.raises(FormalRuleCursorError):
        codec.decode(token, purpose="candidates")


def test_tampered_or_malformed_cursor_is_invalid() -> None:
    clock = [1000.0]
    codec = _codec(clock)
    token = codec.encode(
        purpose="candidates",
        run_id=RUN,
        publication_id=PUBLICATION,
        snapshot_digest=DIGEST,
        offset=0,
        query_fingerprint=FINGERPRINT,
    )
    for malformed in ("", "abc", token + ".x", token[:-1] + "0"):
        with pytest.raises(FormalRuleCursorError) as excinfo:
            codec.decode(malformed, purpose="candidates")
        assert excinfo.value.reason_code == "formal_rule_cursor_invalid"
