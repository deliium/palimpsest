# mypy: ignore-errors
"""Purpose-bound social-mobility cursor codec, TTL, and tamper rejection."""

from __future__ import annotations

import pytest

from api.social_mobility_cursor import (
    SOCIAL_MOBILITY_CURSOR_TTL_SECONDS,
    SocialMobilityCursorCodec,
    SocialMobilityCursorError,
)
from simulation.social_mobility_ports import social_mobility_query_fingerprint

pytestmark = pytest.mark.unit

SECRET = b"k" * 32


def _fingerprint(purpose: str = "domains", window_index: int | None = 0) -> str:
    return social_mobility_query_fingerprint(
        run_id="run-1",
        publication_id="socmob-pub-1",
        digest="sha256:abc",
        purpose=purpose,
        limit=100,
        window_index=window_index,
    )


def test_ttl_is_locked() -> None:
    assert SOCIAL_MOBILITY_CURSOR_TTL_SECONDS == 900


def test_cursor_round_trip_binds_purpose_and_query() -> None:
    codec = SocialMobilityCursorCodec(SECRET)
    token = codec.encode(
        purpose="domains",
        run_id="run-1",
        publication_id="socmob-pub-1",
        snapshot_digest="sha256:abc",
        query_fingerprint=_fingerprint(),
        after_key="000|resources",
    )
    payload = codec.decode(token, purpose="domains")
    assert payload["after_key"] == "000|resources"
    assert payload["query_fingerprint"] == _fingerprint()
    with pytest.raises(SocialMobilityCursorError):
        codec.decode(token, purpose="standing")


def test_tampered_cursor_is_rejected() -> None:
    codec = SocialMobilityCursorCodec(SECRET)
    token = codec.encode(
        purpose="domains",
        run_id="run-1",
        publication_id="socmob-pub-1",
        snapshot_digest="sha256:abc",
        query_fingerprint=_fingerprint(),
        after_key="000|resources",
    )
    with pytest.raises(SocialMobilityCursorError):
        codec.decode(token[:-2] + "xx", purpose="domains")


def test_fingerprint_changes_with_window_and_limit() -> None:
    assert _fingerprint(window_index=0) != _fingerprint(window_index=1)
    assert social_mobility_query_fingerprint(
        run_id="run-1",
        publication_id="socmob-pub-1",
        digest="sha256:abc",
        purpose="domains",
        limit=100,
        window_index=0,
    ) != social_mobility_query_fingerprint(
        run_id="run-1",
        publication_id="socmob-pub-1",
        digest="sha256:abc",
        purpose="domains",
        limit=50,
        window_index=0,
    )
