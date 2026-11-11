"""Canonical snapshot codec, finalization, and purpose-bound paging."""

from __future__ import annotations

import json

import pytest

from simulation.market_institutions_codec import (
    decode_market_institutions_snapshot,
    encode_market_institutions_snapshot,
    finalize_market_institutions_snapshot,
)
from simulation.market_institutions_models import (
    MarketInstitutionsSnapshot,
    empty_market_institutions_snapshot,
)
from simulation.market_institutions_paging import (
    MARKET_INSTITUTIONS_PAGE_MAX,
    page_market_institutions,
)

pytestmark = pytest.mark.unit


def _snapshot() -> MarketInstitutionsSnapshot:
    return finalize_market_institutions_snapshot(
        empty_market_institutions_snapshot("run-1")
    )


def test_round_trip_is_byte_identical() -> None:
    first = _snapshot()
    encoded = encode_market_institutions_snapshot(first)
    assert encode_market_institutions_snapshot(first) == encoded
    decoded = decode_market_institutions_snapshot(encoded, run_id="run-1")
    assert decoded == first


def test_digest_and_publication_id_are_stable() -> None:
    first = _snapshot()
    assert first.digest == _snapshot().digest
    assert first.publication_id.startswith("mkt-pub-")
    assert len(first.publication_id) == len("mkt-pub-") + 32


def test_unknown_and_missing_keys_fail_closed() -> None:
    encoded = encode_market_institutions_snapshot(_snapshot())
    payload = json.loads(encoded)
    payload["extra"] = 1
    with pytest.raises(ValueError):
        decode_market_institutions_snapshot(json.dumps(payload).encode() + b"\n")
    payload = json.loads(encoded)
    payload.pop("summary")
    with pytest.raises(ValueError):
        decode_market_institutions_snapshot(json.dumps(payload).encode() + b"\n")


def test_run_mismatch_and_digest_mismatch_fail() -> None:
    encoded = encode_market_institutions_snapshot(_snapshot())
    with pytest.raises(ValueError):
        decode_market_institutions_snapshot(encoded, run_id="run-2")
    payload = json.loads(encoded)
    payload["digest"] = "0" * 64
    with pytest.raises(ValueError):
        decode_market_institutions_snapshot(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode() + b"\n"
        )


def test_no_wall_clock_or_owner_belief_ids() -> None:
    encoded = encode_market_institutions_snapshot(_snapshot()).decode()
    assert "mktb-" not in encoded
    for key in ("created_at", "timestamp", "host", "request_id"):
        assert key not in encoded


def test_paging_window_filter_and_cursor() -> None:
    from analysis.market_institutions_contract import MarketCoverage
    from simulation.market_institutions_models import MarketVenueRecord

    rows = tuple(
        MarketVenueRecord(
            venue_id=f"mkt-ven-{index:016x}",
            window_index=index,
            location_id=f"loc-{index}",
            exchange_count=1,
            proposal_count=0,
            withdrawn_count=0,
            distinct_party_count=2,
            distinct_actor_count=1,
            active_window_count=1,
            recurrence_milli=1_000,
            status="single_gathering",
            market_like=False,
            coverage=MarketCoverage.COMPLETE,
        )
        for index in range(3)
    )
    page = page_market_institutions(rows, purpose="venues", window_index=1)
    assert tuple(row.window_index for row in page) == (1,)
    after = page_market_institutions(
        rows, purpose="venues", after_key=(1, rows[1].venue_id)
    )
    assert tuple(row.window_index for row in after) == (2,)


def test_paging_rejects_bad_purpose_limit_and_window() -> None:
    with pytest.raises(ValueError):
        page_market_institutions((), purpose="summary")
    with pytest.raises(ValueError):
        page_market_institutions((), purpose="venues", limit=0)
    with pytest.raises(ValueError):
        page_market_institutions(
            (), purpose="venues", limit=MARKET_INSTITUTIONS_PAGE_MAX + 1
        )
    with pytest.raises(ValueError):
        page_market_institutions((), purpose="venues", window_index=512)
