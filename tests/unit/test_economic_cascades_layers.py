# mypy: ignore-errors
"""Hard separation between objective, dependency, and analytical rows."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from analysis.economic_cascades_contract import (
    CascadeChainState,
    CascadeCoverage,
    CascadeDependencyKind,
    CascadeDisruptionKind,
    CascadeLayer,
    EconomicCascadesError,
    assert_economic_cascade_layer_separation,
    mint_chain_token,
)
from analysis.economic_cascades_rows import (
    CascadeChainRow,
    CascadeDependencyEdgeRow,
    CascadeDisruptionRow,
)

pytestmark = pytest.mark.unit


def _disruption() -> CascadeDisruptionRow:
    return CascadeDisruptionRow(
        window_index=0,
        window_tick=0,
        sequence=1,
        kind=CascadeDisruptionKind.RESOURCE_LOSS,
        subject_token="harvest_grain",
        magnitude_count=1,
        evidence_event_token="evt-1",
        coverage=CascadeCoverage.COMPLETE,
    )


def _edge() -> CascadeDependencyEdgeRow:
    return CascadeDependencyEdgeRow(
        window_index=0,
        window_tick=0,
        upstream_token="harvest_grain",
        downstream_recipe_id="mill_grain",
        kind=CascadeDependencyKind.ITEM_INPUT,
        depth=1,
        evidence_count=1,
    )


def _chain() -> CascadeChainRow:
    return CascadeChainRow(
        chain_token=mint_chain_token(
            disruption_kind=CascadeDisruptionKind.RESOURCE_LOSS,
            upstream_token="harvest_grain",
            downstream_recipe_id="mill_grain",
            depth=1,
            lag_windows=0,
            window_index=0,
            evidence_tokens=("evt-1",),
        ),
        window_index=0,
        window_tick=0,
        disruption_kind=CascadeDisruptionKind.RESOURCE_LOSS,
        upstream_token="harvest_grain",
        downstream_recipe_id="mill_grain",
        depth=1,
        lag_windows=0,
        shortfall_share_milli=500,
        state=CascadeChainState.LINKED,
        coverage=CascadeCoverage.COMPLETE,
    )


def test_clean_three_layer_input_is_accepted() -> None:
    assert_economic_cascade_layer_separation(
        objective_rows=[_disruption()],
        dependency_rows=[_edge()],
        analytical_rows=[_chain()],
    )


def test_objective_row_carrying_a_chain_token_is_rejected() -> None:
    @dataclass(frozen=True, slots=True)
    class BadObjective:
        subject_token: str
        chain_token: str

        @property
        def source_layers(self) -> tuple[CascadeLayer, ...]:
            return (CascadeLayer.OBJECTIVE_DISRUPTION,)

    with pytest.raises(EconomicCascadesError):
        assert_economic_cascade_layer_separation(
            objective_rows=[BadObjective("harvest_grain", "casc-1234")]
        )


def test_analytical_row_carrying_an_owner_token_is_rejected() -> None:
    @dataclass(frozen=True, slots=True)
    class BadAnalytical:
        chain_token: str
        owner_token: str

        @property
        def source_layers(self) -> tuple[CascadeLayer, ...]:
            return (CascadeLayer.ANALYTICAL_CHAIN,)

    with pytest.raises(EconomicCascadesError):
        assert_economic_cascade_layer_separation(
            analytical_rows=[BadAnalytical("casc-1", "owner-1")]
        )


def test_forbidden_key_in_any_layer_is_rejected() -> None:
    @dataclass(frozen=True, slots=True)
    class BadAnalytical:
        chain_token: str
        severity: int

        @property
        def source_layers(self) -> tuple[CascadeLayer, ...]:
            return (CascadeLayer.ANALYTICAL_CHAIN,)

    with pytest.raises(EconomicCascadesError):
        assert_economic_cascade_layer_separation(
            analytical_rows=[BadAnalytical("casc-1", 3)]
        )


def test_analytical_token_in_an_objective_row_is_rejected() -> None:
    @dataclass(frozen=True, slots=True)
    class BadObjective:
        subject_token: str
        evidence_event_token: str

        @property
        def source_layers(self) -> tuple[CascadeLayer, ...]:
            return (CascadeLayer.OBJECTIVE_DISRUPTION,)

    chain = _chain()
    with pytest.raises(EconomicCascadesError):
        assert_economic_cascade_layer_separation(
            objective_rows=[BadObjective(chain.chain_token, "evt-1")],
            analytical_rows=[chain],
        )
