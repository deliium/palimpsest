# mypy: ignore-errors
"""Atomic filesystem store for trade-network snapshots."""

from __future__ import annotations

from pathlib import Path

import pytest

from persistence.trade_networks_filesystem import (
    TradeNetworksPublisherOptions,
    create_trade_networks_publisher,
    create_trade_networks_reader,
)
from simulation.trade_networks_codec import finalize_trade_networks_snapshot
from simulation.trade_networks_models import (
    TradeCorridorRecord,
    TradeFlowCountRecord,
    TradeNetworksSnapshot,
    TradeNetworksSummaryRecord,
)


def _summary(**kwargs):
    values = dict(
        window_tick=0,
        corridor_count=0,
        flow_count=0,
        location_count=0,
        major_location_count=0,
        trade_post_location_count=0,
        network_count=0,
        cross_society_pair_count=0,
        transfer_count=0,
        emerged_count=0,
        continued_count=0,
        transformed_count=0,
        split_count=0,
        merge_count=0,
        dissolved_count=0,
        rerouted_count=0,
        sustained_network_count=0,
        lineage_edge_count=0,
        coverage="complete",
        truncated=False,
    )
    values.update(kwargs)
    return TradeNetworksSummaryRecord(**values)


def _snapshot(token: int = 1) -> TradeNetworksSnapshot:
    return finalize_trade_networks_snapshot(
        TradeNetworksSnapshot(
            run_id="run-1",
            schema_version="trade-networks-snapshot-v1",
            policy_version="trade-networks.v1",
            summary=_summary(corridor_count=1),
            corridors=(
                TradeCorridorRecord(
                    corridor_id=f"trd-cor-{token:016x}",
                    window_index=0,
                    from_location_id="loc-a",
                    to_location_id="loc-b",
                    flow_counts=(TradeFlowCountRecord(flow_class="food", count=1),),
                    transfer_count=1,
                    coverage="complete",
                ),
            ),
        )
    )


def test_publish_and_read_round_trip(tmp_path: Path) -> None:
    snapshot = _snapshot()
    publisher = create_trade_networks_publisher(tmp_path)
    publisher.publish(snapshot)
    reader = create_trade_networks_reader(tmp_path)
    assert reader.read_snapshot("run-1") == snapshot
    summary = reader.read_summary("run-1")
    assert summary is not None
    assert summary.corridor_count == 1


def test_duplicate_publication_rejected(tmp_path: Path) -> None:
    snapshot = _snapshot()
    publisher = create_trade_networks_publisher(tmp_path)
    publisher.publish(snapshot)
    altered = TradeNetworksSnapshot(
        run_id=snapshot.run_id,
        schema_version=snapshot.schema_version,
        policy_version=snapshot.policy_version,
        summary=snapshot.summary,
        corridors=snapshot.corridors,
        digest=snapshot.digest,
        publication_id=snapshot.publication_id,
    )
    altered = finalize_trade_networks_snapshot(
        TradeNetworksSnapshot(
            run_id=altered.run_id,
            schema_version=altered.schema_version,
            policy_version=altered.policy_version,
            summary=_summary(corridor_count=0),
        )
    )
    object.__setattr__(altered, "publication_id", snapshot.publication_id)
    with pytest.raises(ValueError, match="trade_networks_publication_exists"):
        publisher.publish(altered)


def test_publication_count_quota(tmp_path: Path) -> None:
    publisher = create_trade_networks_publisher(
        tmp_path, TradeNetworksPublisherOptions(max_publications=1)
    )
    publisher.publish(_snapshot(1))
    second = _snapshot(2)
    second = finalize_trade_networks_snapshot(
        TradeNetworksSnapshot(
            run_id=second.run_id,
            schema_version=second.schema_version,
            policy_version=second.policy_version,
            summary=second.summary,
            corridors=second.corridors,
        )
    )
    with pytest.raises(ValueError, match="trade_networks_store_quota_exceeded"):
        publisher.publish(second)


def test_byte_quota(tmp_path: Path) -> None:
    publisher = create_trade_networks_publisher(
        tmp_path, TradeNetworksPublisherOptions(max_bytes=1)
    )
    with pytest.raises(ValueError, match="trade_networks_store_quota_exceeded"):
        publisher.publish(_snapshot())


def test_corrupt_payload_rejected(tmp_path: Path) -> None:
    snapshot = _snapshot()
    publisher = create_trade_networks_publisher(tmp_path)
    publisher.publish(snapshot)
    path = tmp_path / "run-1" / f"{snapshot.publication_id}.json"
    path.write_text("{not-json", encoding="utf-8")
    with pytest.raises(ValueError, match="trade_networks_store_corrupt"):
        create_trade_networks_reader(tmp_path).read_snapshot("run-1")


def test_reader_missing_run_returns_none(tmp_path: Path) -> None:
    reader = create_trade_networks_reader(tmp_path)
    assert reader.read_snapshot("run-missing") is None
    assert reader.read_summary("run-missing") is None
    assert reader.list_publications("run-missing") == ()
