# mypy: ignore-errors
"""Compose and publish trade-network snapshots from analysis rows."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

from analysis.trade_networks_analysis import harvest_trade_networks_analysis
from analysis.trade_networks_contract import TradeCoverage
from analysis.trade_networks_rows import TradeLineageRow, TradeNetworkRow
from experiments.trade_networks_publication import (
    TradeNetworksHarvest,
    compose_trade_networks_snapshot,
    publish_trade_networks_snapshot,
    trade_networks_publication_document,
)
from persistence.trade_networks_filesystem import (
    create_trade_networks_publisher,
    create_trade_networks_reader,
)
from world.events import Given, ItemCrafted
from world.identifiers import EntityId, EventId, RecipeId


def _event(token: str, details: object, *, tick: int = 0, origin: str = "loc-a"):
    return SimpleNamespace(
        event_id=EventId(token),
        tick=tick,
        sequence=0,
        actor_id=EntityId("body-a"),
        details=details,
        occurrence=SimpleNamespace(origin_location_id=EntityId(origin)),
    )


def _analysis(*, trade_post: bool = False):
    events = (
        _event(
            "evt-c",
            ItemCrafted(
                recipe_id=RecipeId("cook_food"),
                created_item_id=EntityId("item-1"),
                resulting_holder_id=EntityId("body-a"),
                duration_ticks=1,
            ),
        ),
        _event(
            "evt-g",
            Given(recipient_id=EntityId("body-b"), item_id=EntityId("item-1")),
            tick=1,
            origin="loc-b",
        ),
    )
    return harvest_trade_networks_analysis(
        events=events,
        recipe_item_kinds={"cook_food": "food"},
        trade_post_locations=("loc-b",) if trade_post else (),
    )


def _network(token: str, window: int = 0) -> TradeNetworkRow:
    return TradeNetworkRow(
        network_token=token,
        window_index=window,
        corridor_tokens=(f"trd-cor-{int(token[-16:], 16):016x}",),
        location_tokens=("loc-a", "loc-b"),
        flow_counts=(("food", 1),),
        transfer_count=1,
    )


def _edge(
    *,
    network: str,
    previous: str,
    relation: str,
    rerouted: bool = False,
    sustained: bool = False,
    first: int = 0,
    last: int = 31,
):
    return TradeLineageRow(
        network_token=network,
        previous_token=previous,
        relation=relation,
        first_tick=first,
        last_tick=last,
        rerouted=rerouted,
        sustained=sustained,
    )


def _lineage_analysis():
    base = _analysis()
    networks = (
        _network("trd-net-0000000000000001"),
        _network("trd-net-0000000000000002"),
        _network("trd-net-0000000000000003"),
        _network("trd-net-0000000000000004"),
        _network("trd-net-0000000000000005"),
        _network("trd-net-0000000000000006"),
    )
    lineage = (
        _edge(
            network="trd-net-0000000000000001",
            previous="trd-net-0000000000000011",
            relation="continued",
            sustained=True,
        ),
        _edge(
            network="trd-net-0000000000000002",
            previous="trd-net-0000000000000012",
            relation="transformed",
            rerouted=True,
            sustained=True,
        ),
        _edge(
            network="trd-net-0000000000000013",
            previous="trd-net-0000000000000003",
            relation="split",
        ),
        _edge(
            network="trd-net-0000000000000014",
            previous="trd-net-0000000000000003",
            relation="split",
        ),
        _edge(
            network="trd-net-0000000000000004",
            previous="trd-net-0000000000000015",
            relation="merge",
        ),
        _edge(
            network="trd-net-0000000000000004",
            previous="trd-net-0000000000000016",
            relation="merge",
        ),
        _edge(
            network="trd-net-0000000000000005",
            previous="none",
            relation="emerged",
        ),
        _edge(
            network="none",
            previous="trd-net-0000000000000006",
            relation="dissolved",
        ),
    )
    return replace(
        base, networks=networks, lineage=lineage, network_count=len(networks)
    )


def test_compose_maps_every_analysis_row_family() -> None:
    analysis = _analysis(trade_post=True)
    snapshot = compose_trade_networks_snapshot(analysis, run_id="run-1")
    assert len(snapshot.corridors) == len(analysis.corridors)
    assert len(snapshot.flows) == len(analysis.flows)
    assert len(snapshot.locations) == len(analysis.locations)
    assert len(snapshot.dependence) == len(analysis.dependence)
    assert len(snapshot.networks) == len(analysis.networks)


def test_compose_maps_all_six_lineage_statuses() -> None:
    snapshot = compose_trade_networks_snapshot(_lineage_analysis(), run_id="run-1")
    statuses = {row.network_id: row.status for row in snapshot.networks}
    assert statuses == {
        "trd-net-0000000000000001": "continued",
        "trd-net-0000000000000002": "transformed",
        "trd-net-0000000000000003": "split",
        "trd-net-0000000000000004": "merge",
        "trd-net-0000000000000005": "emerged",
        "trd-net-0000000000000006": "dissolved",
    }


def test_compose_maps_sustained_and_venue_counts() -> None:
    snapshot = compose_trade_networks_snapshot(_lineage_analysis(), run_id="run-1")
    assert snapshot.summary.sustained_network_count == 2
    assert snapshot.summary.rerouted_count == 1
    assert snapshot.summary.emerged_count >= 1
    assert snapshot.summary.dissolved_count >= 1


def test_compose_maps_cross_society_anchors() -> None:
    candidates = (
        SimpleNamespace(
            society_id="msoc-aaaaaaaaaaaaaaaa",
            member_ids=("body-a",),
            window_tick=0,
        ),
        SimpleNamespace(
            society_id="msoc-bbbbbbbbbbbbbbbb",
            member_ids=("body-b",),
            window_tick=0,
        ),
    )
    from analysis.inter_society_relations_detection import (
        InterSocietyMacroCandidate,
    )

    analysis = harvest_trade_networks_analysis(
        events=_events_for_cross(),
        recipe_item_kinds={"cook_food": "food"},
        macro_candidates=tuple(
            InterSocietyMacroCandidate(
                society_id=item.society_id,
                member_ids=item.member_ids,
                window_tick=item.window_tick,
            )
            for item in candidates
        ),
    )
    snapshot = compose_trade_networks_snapshot(analysis, run_id="run-1")
    assert snapshot.cross_society[0].society_a_location_id == "loc-b"
    assert snapshot.cross_society[0].society_b_location_id == "loc-b"


def _events_for_cross():
    return (
        _event(
            "evt-c",
            ItemCrafted(
                recipe_id=RecipeId("cook_food"),
                created_item_id=EntityId("item-1"),
                resulting_holder_id=EntityId("body-a"),
                duration_ticks=1,
            ),
        ),
        _event(
            "evt-g",
            Given(recipient_id=EntityId("body-b"), item_id=EntityId("item-1")),
            tick=1,
            origin="loc-b",
        ),
    )


def test_missing_analysis_produces_missing_receipt() -> None:
    harvest = TradeNetworksHarvest(
        run_id="run-1", analysis=None, snapshot=None, coverage="missing"
    )
    receipt = publish_trade_networks_snapshot(harvest, object())
    assert receipt.stored is False
    assert receipt.reason_code == "trade_networks_publication_missing"


def test_partial_analysis_publishes_partial_snapshot(tmp_path: Path) -> None:
    analysis = _analysis()
    analysis = replace(
        analysis,
        notices=(*analysis.notices, "trade_networks_transfer_truncated"),
        coverage=TradeCoverage.PARTIAL,
    )
    snapshot = compose_trade_networks_snapshot(analysis, run_id="run-1")
    assert snapshot.summary.truncated is True
    assert snapshot.summary.coverage == "partial"


def test_publish_round_trip_through_store(tmp_path: Path) -> None:
    analysis = _analysis()
    snapshot = compose_trade_networks_snapshot(analysis, run_id="run-1")
    harvest = TradeNetworksHarvest(
        run_id="run-1",
        analysis=analysis,
        snapshot=snapshot,
        coverage=analysis.coverage.value,
    )
    publisher = create_trade_networks_publisher(tmp_path)
    receipt = publish_trade_networks_snapshot(harvest, publisher)
    assert receipt.stored is True
    stored = create_trade_networks_reader(tmp_path).read_snapshot("run-1")
    assert stored == snapshot


def test_publication_document_is_secret_free() -> None:
    analysis = _analysis()
    snapshot = compose_trade_networks_snapshot(analysis, run_id="run-1")
    harvest = TradeNetworksHarvest(
        run_id="run-1",
        analysis=analysis,
        snapshot=snapshot,
        coverage=analysis.coverage.value,
    )
    document = trade_networks_publication_document(harvest)
    assert document["run_id"] == "run-1"
    assert "secret" not in repr(document).lower()
    assert "token" not in repr(document).lower()


def test_publication_never_imported_by_api_or_simulation() -> None:
    for root in (Path("src/api"), Path("src/simulation")):
        for path in root.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            assert (
                "from experiments.trade_networks_publication" not in text
                and "import experiments.trade_networks_publication" not in text
            ), path
