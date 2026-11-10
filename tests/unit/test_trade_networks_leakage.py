# mypy: ignore-errors
"""Trade-network layer, vocabulary, and authority leakage guards."""

from __future__ import annotations

import ast
from pathlib import Path

from analysis.trade_networks_contract import TradeFlowClass
from analysis.trade_networks_events import TradeTransferRow
from analysis.trade_networks_layers import (
    project_trade_layers,
)
from analysis.trade_networks_rows import TradeNetworkRow

FORBIDDEN_WORDS = (
    "price",
    "money",
    "currency",
    "central_planner",
    "route_plan",
    "quota",
    "allocation",
    "score",
    "ranking",
)


def _module_paths(pattern: str) -> tuple[Path, ...]:
    return tuple(sorted(Path("src").glob(pattern)))


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            names.add(node.module)
    return names


def test_objective_layer_has_no_analytical_ids() -> None:
    transfer = TradeTransferRow(
        entity_kind="item",
        entity_token="item-1",
        flow_class=TradeFlowClass.FOOD,
        tick=0,
        event_token="evt-1",
        location_token="loc-a",
        previous_location_token="loc-b",
        origin_location_token="loc-b",
        actor_token="body-a",
        counterparty_token="body-b",
        direction="give",
        source_kind="gift",
        consumed=False,
    )
    view = project_trade_layers((transfer,), (), (), ())
    assert view.objective_transfers
    strings = " ".join(
        value
        for row in view.objective_transfers
        for value in (
            row.entity_token,
            row.event_token,
            row.location_token,
            row.previous_location_token,
        )
    )
    assert "trd-cor-" not in strings
    assert "trd-net-" not in strings
    assert "trd-pair-" not in strings


def test_network_layer_has_no_raw_event_tokens() -> None:
    network = TradeNetworkRow(
        network_token="trd-net-0000000000000001",
        window_index=0,
        corridor_tokens=("trd-cor-0000000000000001",),
        location_tokens=("loc-a", "loc-b"),
        flow_counts=(("food", 1),),
        transfer_count=1,
    )
    assert "evt-" not in repr(network)


def test_snapshot_api_ui_and_fixture_have_no_forbidden_vocabulary() -> None:
    paths = [
        *_module_paths("simulation/trade_networks_*.py"),
        *_module_paths("api/trade_networks_*.py"),
        *tuple(Path("src/api").glob("trade_networks_*.py")),
        Path("clients/research-ui/src/api/tradeNetworks.ts"),
        Path("clients/research-ui/src/views/TradeNetworksPanel.svelte"),
        Path("clients/godot-observer/fixtures/protocol/civilization/overlay_trade.json"),
    ]
    for path in paths:
        lowered = path.read_text(encoding="utf-8").lower()
        for word in FORBIDDEN_WORDS:
            assert word not in lowered, (path, word)


def test_trade_modules_do_not_import_authority_or_outer_layers() -> None:
    forbidden = {
        "world._state",
        "world._perception",
        "simulation.engine",
        "simulation.bootstrap",
        "experiments",
        "api",
        "persistence",
        "observer",
    }
    for path in (
        *_module_paths("analysis/trade_networks_*.py"),
        *_module_paths("simulation/trade_networks_*.py"),
        Path("src/api/routes/trade_networks.py"),
        *_module_paths("experiments/trade_networks_*.py"),
    ):
        imports = _imports(path)
        for name in imports:
            assert name not in forbidden, (path, name)
            assert not name.startswith("world._"), (path, name)
    for path in _module_paths("simulation/trade_networks_*.py"):
        assert "analysis" not in _imports(path), path
