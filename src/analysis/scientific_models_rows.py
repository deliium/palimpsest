"""Detached predictive row kinds and analysis container."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from analysis.scientific_models_contract import (
    MAX_CALIBRATION_ROWS,
    MAX_COMPARISON_ROWS,
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
    "ModelCalibrationFact",
    "ModelComparisonFact",
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
    "calibration": MAX_CALIBRATION_ROWS,
    "comparisons": MAX_COMPARISON_ROWS,
}


class PredictiveRowKind(StrEnum):
    HYPOTHESIS = "hypothesis"
    MODEL = "model"
    PREDICTION = "prediction"
    OUTCOME = "outcome"
    REVISION = "revision"
    COVERAGE = "coverage"


@dataclass(frozen=True, slots=True)
class ModelCalibrationFact:
    group_token: str
    target_kind: str
    model_token: str
    scored_count: int
    brier_numerator_sum: int
    mean_brier_millionths: int
    calibration_gap_milli: int | None
    insufficient: bool

    def __post_init__(self) -> None:
        if not self.group_token or not self.model_token or not self.target_kind:
            raise ValueError("calibration: invalid_identity")
        for name in ("scored_count", "brier_numerator_sum", "mean_brier_millionths"):
            value = getattr(self, name)
            if isinstance(value, bool) or type(value) is not int or value < 0:
                raise ValueError(f"{name}: invalid_count")
        if self.calibration_gap_milli is not None and (
            isinstance(self.calibration_gap_milli, bool)
            or type(self.calibration_gap_milli) is not int
            or not 0 <= self.calibration_gap_milli <= 1000
        ):
            raise ValueError("calibration_gap_milli: invalid_range")


@dataclass(frozen=True, slots=True)
class ModelComparisonFact:
    group_token: str
    target_kind: str
    model_a_token: str
    model_b_token: str
    paired_count: int
    mean_brier_millionths_a: int
    mean_brier_millionths_b: int
    a_minus_b_millionths: int
    status: str

    def __post_init__(self) -> None:
        if not self.group_token or not self.model_a_token or not self.model_b_token:
            raise ValueError("comparison: invalid_identity")
        if self.model_a_token == self.model_b_token:
            raise ValueError("comparison: same_model")
        if self.status not in {
            "lower_loss_a",
            "lower_loss_b",
            "tied",
            "insufficient_samples",
        }:
            raise ValueError("comparison: invalid_status")
        for name in (
            "paired_count",
            "mean_brier_millionths_a",
            "mean_brier_millionths_b",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or type(value) is not int or value < 0:
                raise ValueError(f"{name}: invalid_count")
        if type(self.a_minus_b_millionths) is not int:
            raise ValueError("a_minus_b_millionths: invalid_type")


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
    calibration: tuple[ModelCalibrationFact, ...] = ()
    comparisons: tuple[ModelComparisonFact, ...] = ()

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
