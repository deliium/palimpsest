"""Detached, tokenized predictive facts. Never cognition ledgers or truth."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal

__all__ = [
    "MAX_PREDICTIVE_ROWS",
    "MAX_PREDICTIVE_WINDOWS",
    "SCIENTIFIC_MODELS_ANALYSIS_VERSION",
    "ModelHypothesisFact",
    "ObservedModelOutcomeFact",
    "PredictiveCoverageFact",
    "PredictiveModelFact",
    "PredictiveRevisionFact",
    "PriorPredictionFact",
    "require_predictive_token",
]

SCIENTIFIC_MODELS_ANALYSIS_VERSION: Final[str] = "scientific-models-analysis-v1"
MAX_PREDICTIVE_WINDOWS: Final[int] = 512
MAX_PREDICTIVE_ROWS: Final[int] = 8192


def _nonneg(name: str, value: object) -> int:
    if isinstance(value, bool) or type(value) is not int or value < 0:
        raise ValueError(f"{name}: invalid_count")
    return value


def require_predictive_token(name: str, value: object) -> str:
    """Detached identifiers are lowercase digest tokens, never raw payloads."""

    if type(value) is not str or not value:
        raise ValueError(f"{name}: invalid_token")
    if len(value) > 96 or not all(char in "0123456789abcdef:" for char in value):
        raise ValueError(f"{name}: invalid_token")
    return value


@dataclass(frozen=True, slots=True)
class ModelHypothesisFact:
    hypothesis_token: str
    owner_token: str
    target_kind: str
    unit_token: str
    horizon_ticks: int
    source_kind: str
    lifecycle: str
    revision_count: int

    def __post_init__(self) -> None:
        require_predictive_token("hypothesis_token", self.hypothesis_token)
        require_predictive_token("owner_token", self.owner_token)
        require_predictive_token("unit_token", self.unit_token)
        if not self.target_kind or not self.source_kind or not self.lifecycle:
            raise ValueError("hypothesis: invalid_enum")
        if self.horizon_ticks < 1:
            raise ValueError("horizon_ticks: invalid_range")
        _nonneg("revision_count", self.revision_count)


@dataclass(frozen=True, slots=True)
class PredictiveModelFact:
    model_token: str
    hypothesis_token: str
    owner_token: str
    predictor_variant: str
    lifecycle: str
    revision_count: int
    source_revision_token: str
    context_token: str

    def __post_init__(self) -> None:
        for name in (
            "model_token",
            "hypothesis_token",
            "owner_token",
            "source_revision_token",
            "context_token",
        ):
            require_predictive_token(name, getattr(self, name))
        if not self.predictor_variant or not self.lifecycle:
            raise ValueError("model: invalid_enum")
        _nonneg("revision_count", self.revision_count)


@dataclass(frozen=True, slots=True)
class PriorPredictionFact:
    prediction_token: str
    case_token: str
    model_token: str
    owner_token: str
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
    training_high_water_tick: int
    source_revision_token: str
    model_revision_token: str
    receipt_tick: int
    channel: str

    def __post_init__(self) -> None:
        for name in (
            "prediction_token",
            "case_token",
            "model_token",
            "owner_token",
            "target_token",
            "unit_token",
            "context_token",
            "source_revision_token",
            "model_revision_token",
        ):
            require_predictive_token(name, getattr(self, name))
        if not self.target_kind or not self.channel:
            raise ValueError("prediction: invalid_enum")
        _nonneg("horizon_ticks", self.horizon_ticks)
        if not self.alphabet or any(
            type(name) is not str or not name for name in self.alphabet
        ):
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
            "issued_tick",
            "committed_after_tick",
            "target_observation_tick",
            "training_high_water_tick",
            "receipt_tick",
        ):
            _nonneg(name, getattr(self, name))
        if self.committed_after_tick != self.issued_tick:
            raise ValueError("committed_after_tick: not_issuance")
        if self.target_observation_tick <= self.committed_after_tick:
            raise ValueError("target_observation_tick: before_commit")
        if self.training_high_water_tick > self.issued_tick:
            raise ValueError("training_high_water_tick: trained_on_target")


@dataclass(frozen=True, slots=True)
class ObservedModelOutcomeFact:
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
    start_milli: int | None
    end_milli: int | None

    def __post_init__(self) -> None:
        require_predictive_token("case_token", self.case_token)
        require_predictive_token("owner_token", self.owner_token)
        require_predictive_token("target_token", self.target_token)
        require_predictive_token("unit_token", self.unit_token)
        _nonneg("horizon_ticks", self.horizon_ticks)
        if not self.target_kind or not self.state or not self.settlement_reason:
            raise ValueError("outcome: invalid_enum")
        if self.state == "scored":
            if self.observed_class is None or self.observed_tick is None:
                raise ValueError("scored: missing_outcome")
            if self.outcome_token is None:
                raise ValueError("scored: missing_outcome_token")
            require_predictive_token("outcome_token", self.outcome_token)
            _nonneg("observed_tick", self.observed_tick)
        elif any(
            value is not None
            for value in (self.observed_class, self.observed_tick, self.outcome_token)
        ):
            raise ValueError("unscored: unexpected_outcome")
        for name in ("start_milli", "end_milli"):
            value = getattr(self, name)
            if value is not None:
                _nonneg(name, value)


@dataclass(frozen=True, slots=True)
class PredictiveRevisionFact:
    owner_token: str
    model_token: str
    revision_index: int
    tick: int
    kind: Literal["hypothesis", "model"]
    reason: str

    def __post_init__(self) -> None:
        require_predictive_token("owner_token", self.owner_token)
        require_predictive_token("model_token", self.model_token)
        _nonneg("revision_index", self.revision_index)
        _nonneg("tick", self.tick)
        if self.kind not in {"hypothesis", "model"} or not self.reason:
            raise ValueError("revision: invalid_enum")


@dataclass(frozen=True, slots=True)
class PredictiveCoverageFact:
    reason_code: str
    target_kind: str
    first_tick: int
    last_tick: int
    count: int

    def __post_init__(self) -> None:
        if self.reason_code not in {
            "retention_cap",
            "partial_owner_export",
            "outcome_missing",
            "condition_unknown",
            "not_comparable",
            "unavailable_no_observable",
        }:
            raise ValueError("coverage: unknown_reason")
        if not self.target_kind:
            raise ValueError("coverage: invalid_target")
        _nonneg("first_tick", self.first_tick)
        _nonneg("last_tick", self.last_tick)
        if self.count < 1 or self.last_tick < self.first_tick:
            raise ValueError("coverage: invalid_range")
