# mypy: ignore-errors

"""Supply-chain publication bridge stays opt-in and bounded."""

from __future__ import annotations

from pathlib import Path

import pytest

from analysis.supply_chain_analysis import (
    empty_supply_chain_analysis,
    harvest_supply_chain_analysis,
)
from experiments.supply_chain_publication import (
    SupplyChainHarvest,
    compose_supply_chain_snapshot,
    publish_supply_chain_snapshot,
    supply_chain_publication_document,
)
from persistence.supply_chain_filesystem import create_supply_chain_publisher
from tests.unit.test_supply_chain_graph import (
    _RECIPES,
    _craft_done,
    _craft_start,
    _harvest,
)

pytestmark = pytest.mark.unit


def _analysis():
    return harvest_supply_chain_analysis(
        [
            _harvest("harvest_grain", "item-grain", tick=0),
            _craft_start("mill_grain", ("item-grain",), tick=0, event_id="evt-s1"),
            _craft_done("mill_grain", "item-flour", tick=1, event_id="evt-d1"),
        ],
        recipes=_RECIPES,
    )


def _harvest_result(analysis) -> SupplyChainHarvest:
    return SupplyChainHarvest(
        run_id="run-1",
        analysis=analysis,
        snapshot=compose_supply_chain_snapshot(analysis, run_id="run-1"),
        coverage=analysis.coverage.value,
    )


def test_compose_requires_analysis() -> None:
    with pytest.raises(TypeError):
        compose_supply_chain_snapshot(object(), run_id="run-1")  # type: ignore[arg-type]


def test_compose_maps_all_row_families() -> None:
    harvest = _harvest_result(_analysis())
    assert harvest.snapshot.stages
    assert harvest.snapshot.edges
    assert harvest.snapshot.summary.stage_count == len(harvest.snapshot.stages)


def test_empty_harvest_is_not_stored(tmp_path: Path) -> None:
    harvest = _harvest_result(empty_supply_chain_analysis(window_tick=0))
    publisher = create_supply_chain_publisher(tmp_path)
    receipt = publish_supply_chain_snapshot(harvest, publisher)
    assert receipt.stored is False
    assert receipt.reason == "supply_chain_publication_missing"


def test_publish_stores_snapshot(tmp_path: Path) -> None:
    harvest = _harvest_result(_analysis())
    publisher = create_supply_chain_publisher(tmp_path)
    receipt = publish_supply_chain_snapshot(harvest, publisher)
    assert receipt.stored is True
    assert receipt.reason == "published"


def test_document_has_bounded_fields() -> None:
    document = supply_chain_publication_document(_harvest_result(_analysis()))
    assert set(document) == {
        "run_id",
        "coverage",
        "stage_count",
        "edge_count",
        "chain_count",
        "bottleneck_count",
        "publication_id",
        "digest",
    }


def test_none_harvest_is_not_stored() -> None:
    receipt = publish_supply_chain_snapshot(None, object())
    assert receipt.stored is False
    assert receipt.reason == "supply_chain_publication_missing"


def test_publish_is_idempotent(tmp_path: Path) -> None:
    harvest = _harvest_result(_analysis())
    publisher = create_supply_chain_publisher(tmp_path)
    first = publish_supply_chain_snapshot(harvest, publisher)
    second = publish_supply_chain_snapshot(harvest, publisher)
    assert first == second
    assert publisher.list_publications("run-1") == (first.publication_id,)


def test_store_error_propagates() -> None:
    class Boom:
        def publish(self, snapshot):
            raise RuntimeError("store failed")

    with pytest.raises(RuntimeError, match="store failed"):
        publish_supply_chain_snapshot(_harvest_result(_analysis()), Boom())


def test_no_api_import() -> None:
    import ast

    root = Path(__file__).resolve().parents[2]
    for path in (
        root / "src" / "experiments" / "supply_chain_publication.py",
        root / "src" / "research_runner" / "supply_chain_composition.py",
    ):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        modules = {
            node.module or ""
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        }
        assert not any(
            module == "api" or module.startswith("api.") for module in modules
        )


def test_cli_flag_defaults_off() -> None:
    from types import SimpleNamespace

    from research_runner.supply_chain_composition import (
        supply_chain_producer_options_from_args,
    )

    options = supply_chain_producer_options_from_args(SimpleNamespace())
    assert options.enabled is False
