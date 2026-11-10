# mypy: ignore-errors

"""Supply-chain snapshot codec, paging, and facade pins."""

from __future__ import annotations

import dataclasses

import pytest

import simulation
from simulation.supply_chain_codec import (
    decode_supply_chain_snapshot,
    encode_supply_chain_snapshot,
    finalize_supply_chain_snapshot,
)
from simulation.supply_chain_models import (
    SupplyChainSnapshotError,
    SupplyLocationRecord,
    empty_supply_chain_snapshot,
)
from simulation.supply_chain_paging import page_locations, page_stages

pytestmark = pytest.mark.unit


def _finalized():
    return finalize_supply_chain_snapshot(empty_supply_chain_snapshot("run-1"))


def test_round_trip_is_canonical() -> None:
    snapshot = _finalized()
    assert (
        decode_supply_chain_snapshot(encode_supply_chain_snapshot(snapshot)) == snapshot
    )


def test_digest_is_stable() -> None:
    assert _finalized().digest == _finalized().digest
    assert len(_finalized().digest) == 64


def test_snapshot_has_no_wall_clock_field() -> None:
    fields = {field.name for field in dataclasses.fields(_finalized())}
    for forbidden in ("created_at", "created_tick", "wall_clock", "timestamp"):
        assert forbidden not in fields


def test_decode_rejects_digest_mismatch() -> None:
    snapshot = _finalized()
    tampered = dataclasses.replace(snapshot, digest="0" * 64)
    with pytest.raises(SupplyChainSnapshotError):
        decode_supply_chain_snapshot(encode_supply_chain_snapshot(tampered))


def test_decode_rejects_unknown_version() -> None:
    import json

    snapshot = _finalized()
    payload = json.loads(encode_supply_chain_snapshot(snapshot))
    payload["schema_version"] = "supply-chains-snapshot-v2"
    with pytest.raises(SupplyChainSnapshotError):
        decode_supply_chain_snapshot(
            (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode()
        )


def test_empty_snapshot_is_valid() -> None:
    snapshot = _finalized()
    assert snapshot.summary.stage_count == 0
    assert snapshot.summary.coverage == "missing"


def test_page_without_filter() -> None:
    rows = tuple(
        SupplyLocationRecord(
            location_token=f"loc-{index}",
            window_index=index,
            observed_count=1,
            completed_count=1,
            coverage="complete",
        )
        for index in range(5)
    )
    selected, next_key = page_locations(rows, limit=2)
    assert len(selected) == 2
    assert next_key is not None


def test_page_with_window_filter() -> None:
    rows = tuple(
        SupplyLocationRecord(
            location_token=f"loc-{index}",
            window_index=index,
            observed_count=1,
            completed_count=1,
            coverage="complete",
        )
        for index in range(5)
    )
    selected, next_key = page_locations(rows, limit=10, window_index=3)
    assert [row.window_index for row in selected] == [3]
    assert next_key is None


def test_paging_stages_is_empty_safe() -> None:
    assert page_stages((), limit=10) == ((), None)


def test_simulation_facade_exports() -> None:
    for name in (
        "SupplyChainSnapshot",
        "SupplyChainSummaryRecord",
        "SupplyStageRecord",
        "empty_supply_chain_snapshot",
    ):
        assert name in simulation.__all__
        assert hasattr(simulation, name)


def test_cursor_binds_window() -> None:
    from simulation.supply_chain_ports import supply_chain_query_fingerprint

    common = dict(
        run_id="run-1",
        publication_id="pub-1",
        digest="digest-1",
        purpose="stages",
        limit=100,
    )
    first = supply_chain_query_fingerprint(
        **common, filters={"window_index": 0}
    )
    second = supply_chain_query_fingerprint(
        **common, filters={"window_index": 1}
    )
    assert first != second


def test_cursor_rejects_other_window() -> None:
    from simulation.supply_chain_ports import (
        SupplyChainCursor,
        supply_chain_cursor_matches,
        supply_chain_query_fingerprint,
    )

    fingerprint = supply_chain_query_fingerprint(
        run_id="run-1",
        publication_id="pub-1",
        digest="digest-1",
        purpose="stages",
        filters={"window_index": 1},
        limit=100,
    )
    cursor = SupplyChainCursor(
        purpose="stages",
        after_key=None,
        limit=100,
        fingerprint=fingerprint,
        window_index=1,
    )
    assert supply_chain_cursor_matches(cursor, fingerprint) is True
    other = supply_chain_query_fingerprint(
        run_id="run-1",
        publication_id="pub-1",
        digest="digest-1",
        purpose="stages",
        filters={"window_index": 0},
        limit=100,
    )
    assert supply_chain_cursor_matches(cursor, other) is False


def test_paging_is_pure() -> None:
    from simulation.supply_chain_paging import page_stages

    rows = ()
    first = page_stages(rows, limit=1, window_index=0)
    second = page_stages(rows, limit=1, window_index=0)
    assert first == second == ((), None)


def test_records_reject_forbidden_keys() -> None:
    import dataclasses

    from simulation import supply_chain_models
    from simulation.supply_chain_models import SUPPLY_SNAPSHOT_FORBIDDEN_KEYS

    for value in vars(supply_chain_models).values():
        if not dataclasses.is_dataclass(value):
            continue
        names = {field.name for field in dataclasses.fields(value)}
        assert not names & SUPPLY_SNAPSHOT_FORBIDDEN_KEYS
