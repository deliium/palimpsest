# mypy: ignore-errors

"""Bounded supply-chain analysis composition and layer separation."""

from __future__ import annotations

import dataclasses

import pytest

import analysis
from analysis.supply_chain_analysis import (
    SupplyChainAnalysis,
    empty_supply_chain_analysis,
    harvest_supply_chain_analysis,
)
from analysis.supply_chain_contract import SupplyChainError, SupplyCoverage
from analysis.supply_chain_layers import (
    SupplyChainLayerView,
    assert_supply_chain_layer_separation,
)
from tests.unit.test_supply_chain_graph import (
    _RECIPES,
    _craft_done,
    _craft_start,
    _harvest,
)


def _two_window_events():
    return [
        _harvest("harvest_grain", "item-grain", tick=0, event_id="evt-h1"),
        _craft_start("mill_grain", ("item-grain",), tick=0, event_id="evt-s1"),
        _craft_done("mill_grain", "item-flour", tick=1, event_id="evt-d1"),
        _harvest("harvest_grain", "item-grain", tick=32, event_id="evt-h2"),
        _craft_start("mill_grain", ("item-grain",), tick=32, event_id="evt-s2"),
        _craft_done("mill_grain", "item-flour", tick=33, event_id="evt-d2"),
    ]


def test_empty_analysis_is_missing() -> None:
    analysis = empty_supply_chain_analysis()
    assert analysis.coverage is SupplyCoverage.MISSING
    assert analysis.stage_count == 0
    assert analysis.chain_count == 0


def test_counts_match_rows() -> None:
    result = harvest_supply_chain_analysis(_two_window_events(), recipes=_RECIPES)
    assert result.stage_count == len(result.stages)
    assert result.edge_count == len(result.edges)
    assert result.chain_count == len(result.chains)
    assert result.bottleneck_count == len(result.bottlenecks)
    assert result.location_count == len(result.locations)
    assert result.organization_count == len(result.organizations)


def test_partial_dimension_sets_partial_aggregate() -> None:
    result = harvest_supply_chain_analysis(_two_window_events(), recipes=_RECIPES)
    assert result.coverage is SupplyCoverage.PARTIAL


def test_lineage_coverage_requires_two_windows() -> None:
    single = harvest_supply_chain_analysis(
        [_harvest("harvest_grain", "item-grain")], recipes=_RECIPES
    )
    assert single.lineage_coverage is SupplyCoverage.MISSING
    multi = harvest_supply_chain_analysis(_two_window_events(), recipes=_RECIPES)
    assert multi.lineage_coverage is not SupplyCoverage.MISSING


def test_sustained_chain_count() -> None:
    result = harvest_supply_chain_analysis(_two_window_events(), recipes=_RECIPES)
    assert result.sustained_chain_count >= 0


def test_layers_project_rows() -> None:
    result = harvest_supply_chain_analysis(_two_window_events(), recipes=_RECIPES)
    total = (
        len(result.layers.objective_derived)
        + len(result.layers.analytical)
        + len(result.layers.owner_claims)
    )
    assert total == (
        len(result.stages)
        + len(result.edges)
        + len(result.locations)
        + len(result.chains)
        + len(result.lineage)
        + len(result.bottlenecks)
        + len(result.organizations)
    )


def test_layer_leak_raises() -> None:
    with pytest.raises(SupplyChainError) as excinfo:
        assert_supply_chain_layer_separation(
            SupplyChainLayerView(objective_derived=(object(),))
        )
    assert excinfo.value.reason_code == "supply_chain_layer_leak"


def test_rejects_foreign_input() -> None:
    with pytest.raises(SupplyChainError):
        harvest_supply_chain_analysis(
            _two_window_events(),
            recipes=(object(),),  # type: ignore[arg-type]
        )
    with pytest.raises(SupplyChainError):
        harvest_supply_chain_analysis(
            _two_window_events(),
            recipes=_RECIPES,
            policy=object(),  # type: ignore[arg-type]
        )


def test_analysis_is_frozen() -> None:
    result = empty_supply_chain_analysis()
    assert isinstance(result, SupplyChainAnalysis)
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.stage_count = 1  # type: ignore[misc]


def test_analysis_facade_exports() -> None:
    for name in (
        "SupplyChainAnalysis",
        "harvest_supply_chain_analysis",
        "empty_supply_chain_analysis",
        "assemble_supply_chain_metrics",
        "SupplyChainAnalysisPolicy",
    ):
        assert name in analysis.__all__
        assert hasattr(analysis, name)
