"""Four-layer projection of one detached emergent-price analysis."""

from __future__ import annotations

from dataclasses import dataclass

from analysis.emergent_prices_analysis import EmergentPricesAnalysis
from analysis.emergent_prices_contract import (
    EmergentPriceAnalysisError,
    PriceLayer,
)
from analysis.emergent_prices_detection import assert_price_layer_separation
from analysis.emergent_prices_rows import (
    ExchangePriceEvidenceRow,
    OwnerPriceExpectationRow,
    OwnerPriceQuoteRow,
    PriceDistributionRow,
    PriceMarketRow,
    PriceQuoteEvidenceRow,
    PriceRelationRow,
    PriceUnitRow,
)

__all__ = ["PriceLayerView", "project_price_layers"]


@dataclass(frozen=True, slots=True)
class PriceLayerView:
    """Layer-separated row groups; values never cross layers."""

    objective_exchange: tuple[ExchangePriceEvidenceRow | PriceQuoteEvidenceRow, ...]
    owner_expectation: tuple[
        OwnerPriceExpectationRow | OwnerPriceQuoteRow | PriceUnitRow, ...
    ]
    analytical_distribution: tuple[PriceDistributionRow | PriceMarketRow, ...]
    comparison_view: tuple[PriceRelationRow, ...]


def project_price_layers(analysis: EmergentPricesAnalysis) -> PriceLayerView:
    """Project one analysis into four strictly separated views."""

    if type(analysis) is not EmergentPricesAnalysis:
        raise EmergentPriceAnalysisError("price_analysis_invalid_row")
    view = PriceLayerView(
        objective_exchange=analysis.evidence,
        owner_expectation=(*analysis.expectations, *analysis.quotes, *analysis.units),
        analytical_distribution=(*analysis.distributions, *analysis.markets),
        comparison_view=analysis.relations,
    )
    assert_price_layer_separation(
        {
            PriceLayer.OBJECTIVE_EXCHANGE: view.objective_exchange,
            PriceLayer.OWNER_EXPECTATION: view.owner_expectation,
            PriceLayer.ANALYTICAL_DISTRIBUTION: tuple(
                row
                for row in view.analytical_distribution
                if type(row) is PriceDistributionRow
            ),
            PriceLayer.COMPARISON_VIEW: view.comparison_view,
        }
    )
    return view
