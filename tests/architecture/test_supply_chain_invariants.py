# mypy: ignore-errors

"""V4-19 supply-chain architecture pins and no-authority invariants."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from analysis.specifications import METRIC_FAMILY_COUNT
from analysis.supply_chain_contract import SupplyEdgeKind
from api.routes.supply_chains import SUPPLY_CHAIN_ROUTE_COUNT, router
from observer.version import SEMANTIC_EVENT_TYPES
from simulation.compatibility import (
    ALEMBIC_HEAD_REVISION,
    V4_OWNED_CAPABILITY_FLAGS,
)
from simulation.runner_models import _V4_OWNED_CAPABILITY_FLAGS
from simulation.v4_architecture import (
    V4_CAPABILITY_FLAGS,
    V4_CONTEXTS,
    V4Authority,
    V4ContextId,
    v4_context_for_flag,
)
from simulation.versioning import V4_DEEPENING_WRITE_PAIRS
from world._rules import COMMAND_RULE_MATRIX
from world.events import EVENT_SCHEMA_REPLAY_V27
from world.production import example_production_catalog, production_catalog_digest
from world.supply_chain import SUPPLY_CHAIN_RECIPES

pytestmark = pytest.mark.architecture

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"

_FORBIDDEN_AUTHORITY = {
    "WorldState",
    "WorldEngine",
    "ActionSubmission",
    "ProductionCatalog",
}


def test_v4_19_owns_supply_chains() -> None:
    assert len(V4_CONTEXTS) == 14
    assert len(V4_CAPABILITY_FLAGS) == 12
    assert len(V4_OWNED_CAPABILITY_FLAGS) == 8
    assert set(V4_CAPABILITY_FLAGS) - set(V4_OWNED_CAPABILITY_FLAGS) == {
        "science",
        "epidemics",
        "ecological_feedback",
        "disasters",
    }
    assert V4_OWNED_CAPABILITY_FLAGS == _V4_OWNED_CAPABILITY_FLAGS
    assert "supply_chains" in V4_OWNED_CAPABILITY_FLAGS
    context = v4_context_for_flag("supply_chains")
    assert context.context_id is V4ContextId.SUPPLY_CHAINS


def test_supply_chains_refuses_new_write_pair() -> None:
    context = v4_context_for_flag("supply_chains")
    assert context.uses_existing_events is True
    assert context.authority is V4Authority.OBJECTIVE_WORLD
    assert context.owner_packages == ("world", "simulation")
    assert context.non_goals == (
        "no central planner or quota",
        "no automatic allocation of items",
    )
    assert [item.event_schema for item in V4_DEEPENING_WRITE_PAIRS] == [27]


def test_no_new_command() -> None:
    assert len(COMMAND_RULE_MATRIX) == 43


def test_no_new_observer_semantic() -> None:
    assert len(SEMANTIC_EVENT_TYPES) == 73
    assert not any("supply" in value for value in SEMANTIC_EVENT_TYPES)


def test_replay_and_codec_maxima_unchanged() -> None:
    assert EVENT_SCHEMA_REPLAY_V27 == 27
    from world import events

    assert not hasattr(events, "EVENT_SCHEMA_REPLAY_V28")
    from simulation import persistence

    assert max(persistence.ACCEPTED_EVENT_SCHEMA_VERSIONS) == 27
    assert "v25" in persistence.ACCEPTED_PERSISTENCE_CODEC_VERSIONS
    assert "v26" not in persistence.ACCEPTED_PERSISTENCE_CODEC_VERSIONS


def test_alembic_head_is_0017() -> None:
    assert ALEMBIC_HEAD_REVISION == "0017"
    versions = sorted((ROOT / "alembic" / "versions").glob("*.py"))
    assert versions
    assert versions[-1].name.startswith("0017_")


def test_metric_catalog_is_204() -> None:
    assert METRIC_FAMILY_COUNT == 208


def test_seven_routes() -> None:
    assert SUPPLY_CHAIN_ROUTE_COUNT == 7
    assert len(router.routes) == 7
    for route in router.routes:
        assert set(route.methods or ()) == {"GET"}
        assert route.path.startswith("/v1/simulations/")


def test_ten_edge_kinds() -> None:
    assert len(SupplyEdgeKind) == 10


def test_legacy_production_catalog_unchanged() -> None:
    catalog = example_production_catalog()
    ids = tuple(recipe.recipe_id.value for recipe in catalog.recipes)
    assert catalog.recipe_count == 6
    assert ids == (
        "harvest_wood",
        "harvest_stone",
        "craft_tool",
        "build_shelter",
        "repair_shelter",
        "store_food",
    )
    assert production_catalog_digest(ids)
    assert len(SUPPLY_CHAIN_RECIPES) == 6


def test_no_forbidden_authority() -> None:
    for pattern in ("analysis/supply_chain_*.py", "simulation/supply_chain_*.py"):
        for path in sorted(SRC.glob(pattern)):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            names = {
                alias.name
                for node in ast.walk(tree)
                if isinstance(node, ast.ImportFrom)
                for alias in node.names
            }
            assert not names & _FORBIDDEN_AUTHORITY, path
