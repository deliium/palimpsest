# mypy: ignore-errors
"""Canonical trade-network snapshot models, codec, and paging."""

from __future__ import annotations

import json

import pytest
from hypothesis import given
from hypothesis import strategies as st

from simulation.trade_networks_codec import (
    compute_trade_networks_publication_id,
    decode_trade_networks_snapshot,
    encode_trade_networks_snapshot,
    finalize_trade_networks_snapshot,
    trade_networks_digest,
)
from simulation.trade_networks_models import (
    MAX_TRADE_SNAPSHOT_LINEAGE_EDGES,
    MAX_TRADE_SNAPSHOT_WINDOWS,
    CrossSocietyTradeRecord,
    TradeCorridorRecord,
    TradeDependenceRecord,
    TradeFlowCountRecord,
    TradeFlowRecord,
    TradeLocationRecord,
    TradeNetworkRecord,
    TradeNetworksArtifactError,
    TradeNetworksSnapshot,
    TradeNetworksSummaryRecord,
    empty_trade_networks_snapshot,
)
from simulation.trade_networks_paging import (
    CrossSocietyTradeRowSelection,
    TradeCorridorRowSelection,
    page_cross_society_trades,
    page_trade_corridors,
)
from simulation.trade_networks_ports import (
    TradeNetworksCursor,
    trade_networks_cursor_matches,
    trade_networks_query_fingerprint,
)

CORRIDOR = "trd-cor-0000000000000001"
NETWORK = "trd-net-0000000000000001"
PAIR = "trd-pair-0000000000000001"


def _summary(**kwargs):
    values = dict(
        window_tick=64,
        corridor_count=1,
        flow_count=1,
        location_count=2,
        major_location_count=1,
        trade_post_location_count=1,
        network_count=1,
        cross_society_pair_count=1,
        transfer_count=2,
        emerged_count=0,
        continued_count=1,
        transformed_count=0,
        split_count=0,
        merge_count=0,
        dissolved_count=0,
        rerouted_count=0,
        sustained_network_count=1,
        lineage_edge_count=1,
        coverage="complete",
        truncated=False,
    )
    values.update(kwargs)
    return TradeNetworksSummaryRecord(**values)


def _flows():
    return (TradeFlowCountRecord(flow_class="food", count=2),)


def _snapshot() -> TradeNetworksSnapshot:
    return finalize_trade_networks_snapshot(
        TradeNetworksSnapshot(
            run_id="run-1",
            schema_version="trade-networks-snapshot-v1",
            policy_version="trade-networks.v1",
            summary=_summary(),
            corridors=(
                TradeCorridorRecord(
                    corridor_id=CORRIDOR,
                    window_index=1,
                    from_location_id="loc-a",
                    to_location_id="loc-b",
                    flow_counts=_flows(),
                    transfer_count=2,
                    coverage="complete",
                ),
            ),
            flows=(
                TradeFlowRecord(
                    window_index=1,
                    flow_class="food",
                    transfer_count=2,
                    cross_location_count=2,
                    imported_count=2,
                    exported_count=2,
                    local_count=0,
                    coverage="complete",
                ),
            ),
            locations=(
                TradeLocationRecord(
                    location_id="loc-b",
                    window_index=1,
                    inflow_count=2,
                    outflow_count=0,
                    local_count=0,
                    corridor_degree=1,
                    is_major=True,
                    trade_post_present=True,
                    flow_counts=_flows(),
                    coverage="complete",
                ),
            ),
            dependence=(
                TradeDependenceRecord(
                    location_id="loc-b",
                    window_index=1,
                    flow_class="food",
                    imported_count=2,
                    locally_originated_count=0,
                    dependence_milli=1_000,
                    high_dependence=True,
                    coverage="complete",
                ),
            ),
            cross_society=(
                CrossSocietyTradeRecord(
                    pair_id=PAIR,
                    window_index=1,
                    society_a="msoc-aaaaaaaaaaaaaaaa",
                    society_b="msoc-bbbbbbbbbbbbbbbb",
                    society_a_location_id="loc-a",
                    society_b_location_id="loc-b",
                    overlap_member_count=0,
                    flow_counts=_flows(),
                    transfer_count=2,
                    society_a_to_b_count=2,
                    society_b_to_a_count=0,
                    coverage="complete",
                ),
            ),
            networks=(
                TradeNetworkRecord(
                    network_id=NETWORK,
                    window_index=1,
                    corridor_ids=(CORRIDOR,),
                    location_ids=("loc-a", "loc-b"),
                    flow_counts=_flows(),
                    transfer_count=2,
                    status="continued",
                    previous_network_ids=("trd-net-0000000000000000",),
                    next_network_ids=(),
                    rerouted=False,
                    sustained=True,
                    coverage="complete",
                ),
            ),
        )
    )


def test_empty_snapshot_is_canonical() -> None:
    snapshot = finalize_trade_networks_snapshot(empty_trade_networks_snapshot("run-1"))
    encoded = encode_trade_networks_snapshot(snapshot)
    decoded = decode_trade_networks_snapshot(encoded, run_id="run-1")
    assert decoded == snapshot
    assert snapshot.summary.coverage == "missing"


def test_snapshot_round_trips_exactly() -> None:
    snapshot = _snapshot()
    encoded = encode_trade_networks_snapshot(snapshot)
    assert decode_trade_networks_snapshot(encoded, run_id="run-1") == snapshot


def test_digest_and_publication_id_change_with_rows() -> None:
    snapshot = _snapshot()
    empty = finalize_trade_networks_snapshot(empty_trade_networks_snapshot("run-1"))
    assert trade_networks_digest(snapshot) != trade_networks_digest(empty)
    assert snapshot.publication_id == compute_trade_networks_publication_id(
        run_id="run-1", digest=snapshot.digest
    )


def test_unknown_field_and_duplicate_key_rejected() -> None:
    snapshot = _snapshot()
    payload = json.loads(encode_trade_networks_snapshot(snapshot))
    payload["unknown"] = 1
    with pytest.raises(TradeNetworksArtifactError):
        decode_trade_networks_snapshot(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode() + b"\n"
        )
    duplicate = (
        b'{"run_id":"run-1","run_id":"run-1","schema_version":'
        b'"trade-networks-snapshot-v1"}'
    )
    with pytest.raises(TradeNetworksArtifactError):
        decode_trade_networks_snapshot(duplicate)


def test_wrong_run_id_rejected() -> None:
    snapshot = _snapshot()
    encoded = encode_trade_networks_snapshot(snapshot)
    with pytest.raises(TradeNetworksArtifactError):
        decode_trade_networks_snapshot(encoded, run_id="run-2")


def test_caps_are_enforced() -> None:
    with pytest.raises(TradeNetworksArtifactError):
        TradeNetworksSnapshot(
            run_id="run-1",
            schema_version="trade-networks-snapshot-v1",
            policy_version="trade-networks.v1",
            summary=_summary(lineage_edge_count=MAX_TRADE_SNAPSHOT_LINEAGE_EDGES + 1),
        )


def test_window_index_is_bounded() -> None:
    with pytest.raises(TradeNetworksArtifactError):
        TradeCorridorRecord(
            corridor_id=CORRIDOR,
            window_index=MAX_TRADE_SNAPSHOT_WINDOWS,
            from_location_id="loc-a",
            to_location_id="loc-b",
            flow_counts=_flows(),
            transfer_count=1,
            coverage="complete",
        )
    with pytest.raises(ValueError, match="trade_networks_cursor_invalid"):
        page_trade_corridors(
            _snapshot(),
            TradeCorridorRowSelection(
                purpose="corridors",
                after_key=None,
                limit=10,
                window_index=MAX_TRADE_SNAPSHOT_WINDOWS,
            ),
        )


def test_network_lineage_status_fields_round_trip() -> None:
    snapshot = _snapshot()
    decoded = decode_trade_networks_snapshot(encode_trade_networks_snapshot(snapshot))
    network = decoded.networks[0]
    assert network.status == "continued"
    assert network.previous_network_ids == ("trd-net-0000000000000000",)
    assert network.sustained is True and network.rerouted is False


def test_cross_society_anchor_fields_round_trip() -> None:
    decoded = decode_trade_networks_snapshot(
        encode_trade_networks_snapshot(_snapshot())
    )
    pair = decoded.cross_society[0]
    assert pair.society_a_location_id == "loc-a"
    assert pair.society_b_location_id == "loc-b"
    assert pair.society_a_to_b_count == 2


def test_trade_post_and_cross_location_fields_round_trip() -> None:
    decoded = decode_trade_networks_snapshot(
        encode_trade_networks_snapshot(_snapshot())
    )
    location = decoded.locations[0]
    assert location.trade_post_present is True
    assert location.is_major is True
    assert decoded.flows[0].cross_location_count == 2


def test_window_filter_and_cursor_fingerprint() -> None:
    snapshot = _snapshot()
    page = page_trade_corridors(
        snapshot,
        TradeCorridorRowSelection(
            purpose="corridors", after_key=None, limit=10, window_index=1
        ),
    )
    assert len(page.rows) == 1
    empty = page_trade_corridors(
        snapshot,
        TradeCorridorRowSelection(
            purpose="corridors", after_key=None, limit=10, window_index=0
        ),
    )
    assert empty.rows == ()
    first = trade_networks_query_fingerprint(
        run_id="run-1",
        publication_id=snapshot.publication_id,
        digest=snapshot.digest,
        purpose="corridors",
        filters={"window_index": 1},
        after_key=None,
        limit=10,
    )
    second = trade_networks_query_fingerprint(
        run_id="run-1",
        publication_id=snapshot.publication_id,
        digest=snapshot.digest,
        purpose="corridors",
        filters={"window_index": 0},
        after_key=None,
        limit=10,
    )
    assert first != second
    cursor = TradeNetworksCursor(
        purpose="corridors", after_key=None, limit=10, fingerprint=first
    )
    assert trade_networks_cursor_matches(cursor, first)
    assert not trade_networks_cursor_matches(cursor, second)


def test_cross_society_page_uses_purpose() -> None:
    snapshot = _snapshot()
    page = page_cross_society_trades(
        snapshot,
        CrossSocietyTradeRowSelection(
            purpose="cross-society", after_key=None, limit=10
        ),
    )
    assert len(page.rows) == 1
    with pytest.raises(ValueError):
        page_cross_society_trades(
            snapshot,
            CrossSocietyTradeRowSelection(
                purpose="corridors", after_key=None, limit=10
            ),
        )


@given(counts=st.lists(st.integers(min_value=0, max_value=100), max_size=4))
def test_codec_round_trip_preserves_snapshot(counts) -> None:
    corridors = tuple(
        TradeCorridorRecord(
            corridor_id=f"trd-cor-{index:016x}",
            window_index=index,
            from_location_id="loc-a",
            to_location_id="loc-b",
            flow_counts=(TradeFlowCountRecord(flow_class="food", count=count),),
            transfer_count=count,
            coverage="complete",
        )
        for index, count in enumerate(counts)
    )
    snapshot = finalize_trade_networks_snapshot(
        TradeNetworksSnapshot(
            run_id="run-1",
            schema_version="trade-networks-snapshot-v1",
            policy_version="trade-networks.v1",
            summary=_summary(corridor_count=len(corridors)),
            corridors=corridors,
        )
    )
    assert (
        decode_trade_networks_snapshot(encode_trade_networks_snapshot(snapshot))
        == snapshot
    )
