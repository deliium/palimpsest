"""Canonical detached scientific-model snapshot contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

__all__ = [
    "MAX_SCIENTIFIC_MODELS_SECTION_ROWS",
    "MAX_SCIENTIFIC_MODELS_SNAPSHOT_BYTES",
    "SCIENTIFIC_MODELS_PUBLICATION_POLICY",
    "SCIENTIFIC_MODELS_SNAPSHOT_SCHEMA",
    "ScientificCalibrationRow",
    "ScientificComparisonRow",
    "ScientificCoverageRow",
    "ScientificModelRow",
    "ScientificModelsSnapshot",
    "ScientificOutcomeRow",
    "ScientificPredictionRow",
    "ScientificRevisionRow",
]

SCIENTIFIC_MODELS_SNAPSHOT_SCHEMA: Final[str] = "scientific-models-snapshot-v1"
SCIENTIFIC_MODELS_PUBLICATION_POLICY: Final[str] = "scientific-models-publication.v1"
MAX_SCIENTIFIC_MODELS_SECTION_ROWS: Final[int] = 8192
MAX_SCIENTIFIC_MODELS_SNAPSHOT_BYTES: Final[int] = 8 * 1024 * 1024

_LAYERS: Final[frozenset[str]] = frozenset(
    {
        "owner_prediction",
        "owner_observation",
        "owner_revision",
        "analytical_calibration",
        "analytical_comparison",
        "coverage",
    }
)


def _token(name: str, value: object) -> str:
    if type(value) is not str or not value or len(value) > 96:
        raise ValueError(f"{name}: invalid_token")
    return value


def _count(name: str, value: object) -> int:
    if isinstance(value, bool) or type(value) is not int or value < 0:
        raise ValueError(f"{name}: invalid_count")
    return value


@dataclass(frozen=True, slots=True)
class ScientificModelRow:
    owner_token: str
    model_token: str
    hypothesis_token: str
    target_kind: str
    unit_token: str
    horizon_ticks: int
    predictor_variant: str
    lifecycle: str
    revision_tokens: tuple[str, ...]
    layer: str = "owner_prediction"

    def __post_init__(self) -> None:
        for name in (
            "owner_token",
            "model_token",
            "hypothesis_token",
            "unit_token",
        ):
            _token(name, getattr(self, name))
        if not self.target_kind or not self.predictor_variant or not self.lifecycle:
            raise ValueError("model_row: invalid_enum")
        if _count("horizon_ticks", self.horizon_ticks) < 1:
            raise ValueError("horizon_ticks: invalid_range")
        if self.layer != "owner_prediction":
            raise ValueError("model_row: invalid_layer")
        for token in self.revision_tokens:
            _token("revision_tokens", token)


@dataclass(frozen=True, slots=True)
class ScientificPredictionRow:
    owner_token: str
    case_token: str
    prediction_token: str
    model_token: str
    target_kind: str
    target_token: str
    unit_token: str
    context_token: str
    horizon_ticks: int
    alphabet: tuple[str, ...]
    probabilities_milli: tuple[int, ...]
    predicted_class: str
    confidence_milli: int
    issued_tick: int
    committed_after_tick: int
    target_observation_tick: int
    receipt_tick: int
    window_index: int
    layer: str = "owner_prediction"

    def __post_init__(self) -> None:
        for name in (
            "owner_token",
            "case_token",
            "prediction_token",
            "model_token",
            "target_token",
            "unit_token",
            "context_token",
        ):
            _token(name, getattr(self, name))
        if not self.target_kind:
            raise ValueError("prediction_row: invalid_target")
        if self.layer != "owner_prediction":
            raise ValueError("prediction_row: invalid_layer")
        if not self.alphabet or len(set(self.alphabet)) != len(self.alphabet):
            raise ValueError("alphabet: invalid")
        if len(self.probabilities_milli) != len(self.alphabet):
            raise ValueError("probabilities_milli: invalid_alphabet")
        if sum(self.probabilities_milli) != 1000:
            raise ValueError("probabilities_milli: invalid_sum")
        if self.predicted_class not in self.alphabet:
            raise ValueError("predicted_class: invalid_class")
        if not 0 <= self.confidence_milli <= 1000:
            raise ValueError("confidence_milli: invalid_range")
        for name in (
            "horizon_ticks",
            "issued_tick",
            "committed_after_tick",
            "target_observation_tick",
            "receipt_tick",
            "window_index",
        ):
            _count(name, getattr(self, name))
        if self.committed_after_tick != self.issued_tick:
            raise ValueError("committed_after_tick: not_issuance")
        if self.target_observation_tick <= self.committed_after_tick:
            raise ValueError("target_observation_tick: before_commit")


@dataclass(frozen=True, slots=True)
class ScientificOutcomeRow:
    case_token: str
    owner_token: str
    target_kind: str
    target_token: str
    unit_token: str
    horizon_ticks: int
    state: str
    settlement_reason: str
    observed_class: str | None
    observed_tick: int | None
    outcome_token: str | None
    layer: str = "owner_observation"

    def __post_init__(self) -> None:
        _token("case_token", self.case_token)
        _token("owner_token", self.owner_token)
        _token("target_token", self.target_token)
        _token("unit_token", self.unit_token)
        _count("horizon_ticks", self.horizon_ticks)
        if not self.target_kind or not self.state or not self.settlement_reason:
            raise ValueError("outcome_row: invalid_enum")
        if self.layer != "owner_observation":
            raise ValueError("outcome_row: invalid_layer")
        if self.state == "scored":
            if self.observed_class is None or self.observed_tick is None:
                raise ValueError("outcome_row: missing_outcome")
            _token("outcome_token", self.outcome_token)
            _count("observed_tick", self.observed_tick)
        elif any(
            value is not None
            for value in (self.observed_class, self.observed_tick, self.outcome_token)
        ):
            raise ValueError("outcome_row: unexpected_outcome")


@dataclass(frozen=True, slots=True)
class ScientificCalibrationRow:
    group_token: str
    target_kind: str
    model_token: str
    scored_count: int
    brier_numerator_sum: int
    mean_brier_millionths: int
    calibration_gap_milli: int | None
    insufficient: bool
    layer: str = "analytical_calibration"

    def __post_init__(self) -> None:
        _token("group_token", self.group_token)
        _token("model_token", self.model_token)
        if not self.target_kind:
            raise ValueError("calibration_row: invalid_target")
        if self.layer != "analytical_calibration":
            raise ValueError("calibration_row: invalid_layer")
        for name in ("scored_count", "brier_numerator_sum", "mean_brier_millionths"):
            _count(name, getattr(self, name))


@dataclass(frozen=True, slots=True)
class ScientificRevisionRow:
    owner_token: str
    model_token: str
    revision_token: str
    revision_index: int
    tick: int
    kind: str
    reason: str
    layer: str = "owner_revision"

    def __post_init__(self) -> None:
        for name in ("owner_token", "model_token", "revision_token"):
            _token(name, getattr(self, name))
        _count("revision_index", self.revision_index)
        _count("tick", self.tick)
        if self.kind not in {"hypothesis", "model"} or not self.reason:
            raise ValueError("revision_row: invalid_enum")
        if self.layer != "owner_revision":
            raise ValueError("revision_row: invalid_layer")


@dataclass(frozen=True, slots=True)
class ScientificComparisonRow:
    group_token: str
    target_kind: str
    model_a_token: str
    model_b_token: str
    paired_count: int
    mean_brier_millionths_a: int
    mean_brier_millionths_b: int
    a_minus_b_millionths: int
    status: str
    layer: str = "analytical_comparison"

    def __post_init__(self) -> None:
        for name in ("group_token", "model_a_token", "model_b_token"):
            _token(name, getattr(self, name))
        if self.model_a_token == self.model_b_token or not self.target_kind:
            raise ValueError("comparison_row: invalid_identity")
        if self.status not in {
            "lower_loss_a",
            "lower_loss_b",
            "tied",
            "insufficient_samples",
        }:
            raise ValueError("comparison_row: invalid_status")
        if self.layer != "analytical_comparison":
            raise ValueError("comparison_row: invalid_layer")
        for name in (
            "paired_count",
            "mean_brier_millionths_a",
            "mean_brier_millionths_b",
        ):
            _count(name, getattr(self, name))


@dataclass(frozen=True, slots=True)
class ScientificCoverageRow:
    reason_code: str
    target_kind: str
    first_tick: int
    last_tick: int
    count: int
    layer: str = "coverage"

    def __post_init__(self) -> None:
        if not self.reason_code or not self.target_kind or self.layer != "coverage":
            raise ValueError("coverage_row: invalid_identity")
        _count("first_tick", self.first_tick)
        _count("last_tick", self.last_tick)
        if self.count < 1 or self.last_tick < self.first_tick:
            raise ValueError("coverage_row: invalid_range")


@dataclass(frozen=True, slots=True)
class ScientificModelsSnapshot:
    schema_version: str
    policy_version: str
    run_token: str
    publication_id: str
    finalized_through_tick: int
    coverage_status: str
    models: tuple[ScientificModelRow, ...] = ()
    predictions: tuple[ScientificPredictionRow, ...] = ()
    outcomes: tuple[ScientificOutcomeRow, ...] = ()
    calibration: tuple[ScientificCalibrationRow, ...] = ()
    revisions: tuple[ScientificRevisionRow, ...] = ()
    comparisons: tuple[ScientificComparisonRow, ...] = ()
    coverage: tuple[ScientificCoverageRow, ...] = ()
    notices: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.schema_version != SCIENTIFIC_MODELS_SNAPSHOT_SCHEMA:
            raise ValueError("snapshot: unsupported_schema")
        if self.policy_version != SCIENTIFIC_MODELS_PUBLICATION_POLICY:
            raise ValueError("snapshot: unsupported_policy")
        for name in ("run_token", "publication_id"):
            _token(name, getattr(self, name))
        _count("finalized_through_tick", self.finalized_through_tick)
        if self.coverage_status not in {"complete", "partial", "absent"}:
            raise ValueError("snapshot: invalid_status")
        for section in (
            "models",
            "predictions",
            "outcomes",
            "calibration",
            "revisions",
            "comparisons",
            "coverage",
            "notices",
        ):
            rows = getattr(self, section)
            if not isinstance(rows, tuple):
                raise ValueError(f"{section}: invalid_type")
            if len(rows) > MAX_SCIENTIFIC_MODELS_SECTION_ROWS:
                raise ValueError(f"{section}: cap_exceeded")
        model_tokens = {row.model_token for row in self.models}
        case_tokens = {row.case_token for row in self.outcomes}
        for prediction in self.predictions:
            if prediction.case_token not in case_tokens:
                raise ValueError("snapshot: orphan_prediction")
            if prediction.model_token not in model_tokens:
                raise ValueError("snapshot: unresolved_model")
        for revision_row in self.revisions:
            if revision_row.model_token not in model_tokens:
                raise ValueError("snapshot: unresolved_revision_model")
        for calibration_row in self.calibration:
            if calibration_row.model_token not in model_tokens:
                raise ValueError("snapshot: unresolved_calibration_model")
        for comparison_row in self.comparisons:
            if (
                comparison_row.model_a_token not in model_tokens
                or comparison_row.model_b_token not in model_tokens
            ):
                raise ValueError("snapshot: unresolved_comparison_model")
