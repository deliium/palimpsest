"""Four-layer projection for market-like institution analysis."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Final

from analysis.market_institutions_analysis import MarketInstitutionsAnalysis
from analysis.market_institutions_contract import (
    MarketInstitutionsError,
    MarketLayer,
)
from analysis.market_institutions_detection import (
    assert_market_layer_separation,
)

__all__ = ["MarketLayerView", "project_market_layers"]

_LOG: Final[logging.Logger] = logging.getLogger(
    "analysis.market_institutions.layers"
)


@dataclass(frozen=True, slots=True)
class MarketLayerView:
    """Strictly separated objective, owner, analytical, and comparison rows."""

    objective: tuple[object, ...]
    owner: tuple[object, ...]
    analytical: tuple[object, ...]
    comparison: tuple[object, ...]

    def __post_init__(self) -> None:
        for name in ("objective", "owner", "analytical", "comparison"):
            values = getattr(self, name)
            if type(values) is not tuple:
                raise MarketInstitutionsError("market_institutions_invalid_input")


def project_market_layers(
    analysis: MarketInstitutionsAnalysis,
) -> MarketLayerView:
    """Project one analysis into the four separated layers."""

    if type(analysis) is not MarketInstitutionsAnalysis:
        raise MarketInstitutionsError("market_institutions_invalid_input")
    view = MarketLayerView(
        objective=(),
        owner=(
            *analysis.expectations,
            *analysis.roles,
            *analysis.records,
        ),
        analytical=(
            *analysis.venues,
            *analysis.gatherings,
            *analysis.participation,
            *analysis.markets,
            *analysis.lineage,
        ),
        comparison=(),
    )
    assert_market_layer_separation(
        {
            MarketLayer.OBJECTIVE_EXCHANGE: view.objective,
            MarketLayer.OWNER_EXPECTATION: view.owner,
            MarketLayer.ANALYTICAL_MARKET: view.analytical,
            MarketLayer.COMPARISON_VIEW: view.comparison,
        }
    )
    return view
