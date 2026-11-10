# mypy: ignore-errors

"""In-process supply chain: real engine, analysis, snapshot, and store."""

from __future__ import annotations

from pathlib import Path

import pytest

from analysis.supply_chain_analysis import harvest_supply_chain_analysis
from experiments.supply_chain_completed_run import supply_chain_recipe_specs
from experiments.supply_chain_publication import (
    SupplyChainHarvest,
    compose_supply_chain_snapshot,
    publish_supply_chain_snapshot,
)
from persistence.supply_chain_filesystem import (
    create_supply_chain_publisher,
    create_supply_chain_reader,
)
from tests.physical_helpers import make_resource
from tests.unit.test_supply_chain_mechanics import _act, _engine, _fixture
from world.actions import Craft, Harvest, Wait
from world.events import ItemCrafted, ResourceHarvested
from world.identifiers import EntityId, RecipeId
from world.production import example_production_catalog
from world.supply_chain import (
    supply_chain_production_catalog,
    validate_production_chain_catalog,
)
from world.values import ResourceKind

pytestmark = pytest.mark.unit


def _chain_fixture():
    import dataclasses

    base = _fixture()
    wood = make_resource(
        "res-wood",
        name="wood",
        kind=ResourceKind.MATERIAL,
        location_id="loc-1",
        quantity=2.0,
        maximum_quantity=5.0,
        regeneration_per_tick=0.0,
    )
    stone = make_resource(
        "res-stone",
        name="stone",
        kind=ResourceKind.MATERIAL,
        location_id="loc-1",
        quantity=2.0,
        maximum_quantity=5.0,
        regeneration_per_tick=0.0,
    )
    return dataclasses.replace(base, resources=(*base.resources, wood, stone))


def test_chain_publishes_and_reads(tmp_path: Path) -> None:
    catalog = supply_chain_production_catalog(example_production_catalog())
    engine = _engine(_chain_fixture(), catalog=catalog, supply=True)
    results = []

    def act(command: object):
        result = _act(engine, "agent-1", command)
        results.append(result)
        return result

    # grain → flour → bread
    act(
        Harvest(
            RecipeId("harvest_grain"),
            __import__("world.identifiers", fromlist=["EntityId"]).EntityId(
                "res-grain"
            ),
        )
    )
    act(Craft(RecipeId("mill_grain")))
    act(Wait())
    act(Craft(RecipeId("bake_bread")))
    act(Wait())
    # wood/stone → plank/tool_head → fine_tool
    act(
        Harvest(
            RecipeId("harvest_wood"),
            EntityId("res-wood"),
        )
    )
    act(
        Harvest(
            RecipeId("harvest_stone"),
            EntityId("res-stone"),
        )
    )
    act(Craft(RecipeId("craft_plank")))
    act(Wait())
    act(Craft(RecipeId("craft_tool_head")))
    act(Wait())
    act(Craft(RecipeId("assemble_tool")))
    act(Wait())

    events = tuple(record.event for result in results for record in result.events)
    assert any(type(record.details) is ResourceHarvested for record in events)
    assert any(type(record.details) is ItemCrafted for record in events)

    analysis = harvest_supply_chain_analysis(
        events,
        recipes=supply_chain_recipe_specs(
            __import__("types").SimpleNamespace(
                agents=(
                    __import__("types").SimpleNamespace(
                        cognition=__import__("types").SimpleNamespace(
                            production_catalog=catalog
                        )
                    ),
                )
            )
        ),
    )
    assert analysis.stage_count > 0
    assert analysis.edge_count >= 6
    assert analysis.chain_count >= 1
    assert analysis.max_depth >= 3
    assert validate_production_chain_catalog(catalog).max_depth >= 3

    snapshot = compose_supply_chain_snapshot(analysis, run_id="run-e2e-supply")
    harvest = SupplyChainHarvest(
        run_id="run-e2e-supply",
        analysis=analysis,
        snapshot=snapshot,
        coverage=analysis.coverage.value,
    )
    publisher = create_supply_chain_publisher(tmp_path / "store")
    receipt = publish_supply_chain_snapshot(harvest, publisher)
    assert receipt.stored is True
    reader = create_supply_chain_reader(tmp_path / "store")
    assert reader.read_snapshot("run-e2e-supply") == snapshot

    import asyncio

    from tests.unit.supply_chain_api_helpers import HEADERS, client

    async def read_api():
        async with client(tmp_path) as api:
            return await api.get(
                "/v1/simulations/run-e2e-supply/supply-chains", headers=HEADERS
            )

    response = asyncio.run(read_api())
    assert response.status_code == 200
    assert response.json()["stage_count"] == snapshot.summary.stage_count


def test_flag_off_skips_chain_validation_and_publication(tmp_path: Path) -> None:
    catalog = example_production_catalog()
    engine = _engine(_fixture(), catalog=catalog, supply=False)
    act = _act(
        engine,
        "agent-1",
        Harvest(RecipeId("harvest_wood"), EntityId("res-water")),
    )
    events = tuple(record.event for record in act.events)
    assert events

    analysis = harvest_supply_chain_analysis(events, recipes=())
    assert analysis.edge_count == 0
    publisher = create_supply_chain_publisher(tmp_path)
    receipt = publish_supply_chain_snapshot(None, publisher)
    assert receipt.stored is False
    assert receipt.reason == "supply_chain_publication_missing"
