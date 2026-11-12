"""Canonical price snapshot round-trip, caps, and strict decoding."""

# mypy: ignore-errors


from __future__ import annotations

import json

import pytest

from analysis.emergent_prices_analysis import harvest_emergent_prices_analysis
from analysis.emergent_prices_contract import PriceCoverage, PriceUnitSource
from analysis.emergent_prices_rows import PriceOwnerExpectationInput
from experiments.emergent_prices_publication import (
    compose_emergent_prices_snapshot,
)
from simulation import (
    EMERGENT_PRICES_SNAPSHOT_VERSION,
    EmergentPricesSnapshot,
    decode_emergent_prices_snapshot,
    encode_emergent_prices_snapshot,
    finalize_emergent_prices_snapshot,
)
from tests.unit.emergent_prices_analysis_helpers import completed

pytestmark = pytest.mark.unit


def _analysis():
    return harvest_emergent_prices_analysis(
        committed_events=[
            completed(f"event-{index}", tick=index) for index in range(4)
        ],
        expectation_inputs=(
            PriceOwnerExpectationInput(
                owner_token="owner-1",
                window_index=0,
                item_kind="food",
                unit_kind="water",
                unit_source=PriceUnitSource.EXCHANGE_COUNTERPART,
                expected_ratio_milli=1_000,
                confidence_milli=600,
                level="expected",
                valuation_reservation=1,
                observation_count=4,
                quote_count=0,
                first_tick=0,
                last_tick=3,
                coverage=PriceCoverage.COMPLETE,
            ),
        ),
    )


def test_round_trip_is_canonical_and_stable() -> None:
    snapshot = compose_emergent_prices_snapshot(_analysis(), run_id="run-1")
    payload = encode_emergent_prices_snapshot(snapshot)
    decoded = decode_emergent_prices_snapshot(payload, run_id="run-1")
    assert decoded == snapshot
    assert encode_emergent_prices_snapshot(decoded) == payload
    assert snapshot.schema_version == EMERGENT_PRICES_SNAPSHOT_VERSION
    assert snapshot.publication_id.startswith("prc-pub-")
    assert snapshot.digest.startswith("sha256:")


def test_distribution_fields_round_trip() -> None:
    snapshot = compose_emergent_prices_snapshot(_analysis(), run_id="run-1")
    assert snapshot.distributions
    row = snapshot.distributions[0]
    assert row.sample_source in {"completed", "quoted"}
    assert len(row.bin_shares_milli) == 5
    assert sum(row.bin_shares_milli) == 1_000
    assert "created_at" not in snapshot.summary.__dataclass_fields__
    assert "created_at" not in type(snapshot).__dataclass_fields__


def test_duplicate_key_and_unknown_key_are_rejected() -> None:
    snapshot = compose_emergent_prices_snapshot(_analysis(), run_id="run-1")
    payload = encode_emergent_prices_snapshot(snapshot)
    duplicate = payload.replace(
        b'{"digest"', b'{"digest":"x","digest"', 1
    )
    with pytest.raises(ValueError):
        decode_emergent_prices_snapshot(duplicate)
    parsed = json.loads(payload)
    parsed["unknown"] = True
    with pytest.raises(ValueError):
        decode_emergent_prices_snapshot(
            (json.dumps(parsed, sort_keys=True, separators=(",", ":")) + "\n").encode()
        )


def test_noncanonical_and_oversize_are_rejected() -> None:
    snapshot = compose_emergent_prices_snapshot(_analysis(), run_id="run-1")
    payload = encode_emergent_prices_snapshot(snapshot)
    with pytest.raises(ValueError):
        decode_emergent_prices_snapshot(payload + b"\n")
    from simulation.emergent_prices_models import EMERGENT_PRICES_ARTIFACT_MAX_BYTES

    with pytest.raises(ValueError):
        decode_emergent_prices_snapshot(b"x" * (EMERGENT_PRICES_ARTIFACT_MAX_BYTES + 1))


def test_finalize_is_idempotent() -> None:
    snapshot = compose_emergent_prices_snapshot(_analysis(), run_id="run-1")
    assert finalize_emergent_prices_snapshot(snapshot) == snapshot


def test_public_symbols_import_from_simulation() -> None:
    assert EmergentPricesSnapshot.__module__.startswith("simulation")
