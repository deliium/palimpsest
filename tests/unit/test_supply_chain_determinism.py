# mypy: ignore-errors

"""Supply-chain determinism, bounds, and leakage guards."""

from __future__ import annotations

import json

import pytest

from analysis.specifications import METRIC_FAMILY_COUNT
from analysis.supply_chain_analysis import harvest_supply_chain_analysis
from analysis.supply_chain_metrics import assemble_supply_chain_metrics
from analysis.supply_chain_policy import SupplyChainAnalysisPolicy
from api.routes.supply_chains import SUPPLY_CHAIN_ROUTE_COUNT
from observer.version import SEMANTIC_EVENT_TYPES
from simulation.compatibility import ALEMBIC_HEAD_REVISION
from tests.unit.test_supply_chain_graph import (
    _RECIPES,
    _craft_done,
    _craft_start,
    _harvest,
)

pytestmark = pytest.mark.unit


def _events():
    return [
        _harvest("harvest_grain", "item-grain", tick=0),
        _craft_start("mill_grain", ("item-grain",), tick=0, event_id="evt-s1"),
        _craft_done("mill_grain", "item-flour", tick=1, event_id="evt-d1"),
    ]


def test_analysis_is_deterministic() -> None:
    first = harvest_supply_chain_analysis(_events(), recipes=_RECIPES)
    second = harvest_supply_chain_analysis(tuple(reversed(_events())), recipes=_RECIPES)
    assert first == second


def test_metrics_are_deterministic() -> None:
    analysis = harvest_supply_chain_analysis(_events(), recipes=_RECIPES)
    first = assemble_supply_chain_metrics(
        analysis, run_id="run-1", input_revision="rev-1"
    )
    second = assemble_supply_chain_metrics(
        analysis, run_id="run-1", input_revision="rev-1"
    )
    assert first == second


def test_evidence_cap_retains_prefix_and_notice() -> None:
    events = [
        _harvest("harvest_grain", "item-grain", tick=index, event_id=f"evt-{index}")
        for index in range(5)
    ]
    analysis = harvest_supply_chain_analysis(
        events,
        recipes=_RECIPES,
        policy=SupplyChainAnalysisPolicy(max_evidence_rows=2),
    )
    assert analysis.stage_count == 2
    assert "evidence_truncated" in analysis.notices


def test_pins_are_unchanged() -> None:
    assert METRIC_FAMILY_COUNT == 220
    assert len(SEMANTIC_EVENT_TYPES) == 73
    assert SUPPLY_CHAIN_ROUTE_COUNT == 7
    assert ALEMBIC_HEAD_REVISION == "0017"


def test_analysis_and_snapshot_types_have_no_score_fields() -> None:
    from simulation.supply_chain_models import SupplyChainSnapshot

    for model in (SupplyChainSnapshot,):
        names = set(model.__dataclass_fields__)
        for forbidden in ("price", "score", "rank", "severity", "recommendation"):
            assert forbidden not in names
    assert json.dumps(["counts", "ratios"])


def test_independent_engines_produce_identical_events() -> None:
    from tests.unit.test_supply_chain_mechanics import _act, _engine, _fixture
    from world.actions import Craft, Harvest, Wait
    from world.identifiers import EntityId, RecipeId
    from world.production import example_production_catalog
    from world.supply_chain import supply_chain_production_catalog

    catalog = supply_chain_production_catalog(example_production_catalog())
    engines = [_engine(_fixture(), catalog=catalog, supply=True) for _ in range(2)]
    commands = [
        Harvest(RecipeId("harvest_grain"), EntityId("res-grain")),
        Craft(RecipeId("mill_grain")),
        Wait(),
        Craft(RecipeId("bake_bread")),
        Wait(),
    ]
    traces = []
    for engine in engines:
        trace = []
        for command in commands:
            result = _act(engine, "agent-1", command)
            trace.extend(
                (record.event.tick, record.event.details.kind, record.event.actor_id)
                for record in result.events
            )
        traces.append(trace)
    assert traces[0] == traces[1]


def test_metrics_are_stable_across_hash_seeds() -> None:
    import os
    import subprocess
    import sys

    script = """
import json
from tests.unit.test_supply_chain_determinism import _events
from tests.unit.test_supply_chain_graph import _RECIPES
from analysis.supply_chain_analysis import harvest_supply_chain_analysis
from analysis.supply_chain_metrics import assemble_supply_chain_metrics
analysis = harvest_supply_chain_analysis(_events(), recipes=_RECIPES)
docs = assemble_supply_chain_metrics(analysis, run_id="run-1", input_revision="rev-1")
print(json.dumps(
    [(doc.metric_family, dict(doc.values)) for doc in docs],
    sort_keys=True,
))
"""
    outputs = []
    for seed in ("1", "2"):
        env = dict(os.environ, PYTHONHASHSEED=seed)
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=str(__import__("pathlib").Path(__file__).resolve().parents[2]),
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )
        outputs.append(result.stdout)
    assert outputs[0] == outputs[1]
