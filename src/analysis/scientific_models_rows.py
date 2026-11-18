"""Detached predictive row kinds and analysis container."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from analysis.scientific_models_contract import (
    MAX_PREDICTIVE_ROWS,
    SCIENTIFIC_MODELS_ANALYSIS_VERSION,
    ModelHypothesisFact,
    ObservedModelOutcomeFact,
    PredictiveCoverageFact,
    PredictiveModelFact,
    PredictiveRevisionFact,
    PriorPredictionFact,
)

__all__ = [
    "SCIENTIFIC_MODELS_ANALYSIS_VERSION",
    "PredictiveRowKind",
    "ScientificModelsAnalysis",
    "empty_scientific_models_analysis",
]

_ROW_CAPS: Final[dict[str, int]] = {
    "hypotheses": MAX_PREDICTIVE_ROWS,
    "models": MAX_PREDICTIVE_ROWS,
    "predictions": MAX_PREDICTIVE_ROWS,
    "outcomes": MAX_PREDICTIVE_ROWS,
    "revisions": MAX_PREDICTIVE_ROWS,
    "coverage": MAX_PREDICTIVE_ROWS,
}


class PredictiveRowKind(StrEnum):
    HYPOTHESIS = "hypothesis"
    MODEL = "model"
    PREDICTION = "prediction"
    OUTCOME = "outcome"
    REVISION = "revision"
    COVERAGE = "coverage"


@dataclass(frozen=True, slots=True)
class ScientificModelsAnalysis:
    version: str
    export_status: str
    owner_count: int
    expected_owner_count: int
    hypotheses: tuple[ModelHypothesisFact, ...] = ()
    models: tuple[PredictiveModelFact, ...] = ()
    predictions: tuple[PriorPredictionFact, ...] = ()
    outcomes: tuple[ObservedModelOutcomeFact, ...] = ()
    revisions: tuple[PredictiveRevisionFact, ...] = ()
    coverage: tuple[PredictiveCoverageFact, ...] = ()

    def __post_init__(self) -> None:
        if self.version != SCIENTIFIC_MODELS_ANALYSIS_VERSION:
            raise ValueError("analysis: unsupported_version")
        if self.export_status not in {"complete", "partial", "absent"}:
            raise ValueError("analysis: invalid_status")
        for name, cap in _ROW_CAPS.items():
            rows = getattr(self, name)
            if isinstance(rows, (str, bytes)) or not isinstance(rows, tuple):
                raise ValueError(f"{name}: invalid_type")
            if len(rows) > cap:
                raise ValueError(f"{name}: cap_exceeded")
        if self.owner_count < 0 or self.expected_owner_count < 0:
            raise ValueError("analysis: invalid_owner_count")


def empty_scientific_models_analysis(
    *, expected_owner_count: int = 0
) -> ScientificModelsAnalysis:
    return ScientificModelsAnalysis(
        version=SCIENTIFIC_MODELS_ANALYSIS_VERSION,
        export_status="complete" if expected_owner_count == 0 else "partial",
        owner_count=0,
        expected_owner_count=expected_owner_count,
    )
