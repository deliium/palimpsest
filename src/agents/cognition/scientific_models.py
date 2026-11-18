"""Owner-scoped predictive models, prior forecasts, and predictive accounting.

A scientific model is one owner's revisable belief about an observable
regularity. Models never carry world authority: they do not create commands,
alter admission, or install objective truth. Forecasts are frozen before the
outcome they predict, and their probabilities are subjective estimates rather
than world chances.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Any, Final

from world.environment import Season
from world.experimentation import (
    ExperimentOperator,
    ExperimentOutcomeClass,
    ExperimentProcessToken,
)
from world.identifiers import AgentId, require_exact_nonneg_int, require_stable_id

__all__ = [
    "DISEASE_RISK_CAPABILITY",
    "MAX_CONDITIONS",
    "MAX_DERIVATION_SAMPLES",
    "MAX_EMPIRICAL_BINS",
    "MAX_EVIDENCE_REFS",
    "MAX_HYPOTHESES",
    "MAX_MODELS",
    "MAX_OUTCOME_REFS",
    "MAX_PAIR_COMPARISONS",
    "MAX_PENDING_CASES",
    "MAX_PERFORMANCE_SUMMARIES",
    "MAX_REVISION_RECORDS",
    "MAX_SOURCE_REFS",
    "MAX_TERMINAL_CASES",
    "PRODUCTION_CLASSES",
    "RESOURCE_CHANGE_CLASSES",
    "SCIENTIFIC_MODELS_POLICY_VERSION",
    "SEASON_CLASSES",
    "CalibrationBin",
    "DerivationSample",
    "EmpiricalContextBin",
    "ForecastCase",
    "ForecastCaseState",
    "ModelComparison",
    "ModelComparisonStatus",
    "ModelCondition",
    "ModelCoverageNotice",
    "ModelExecutionBinding",
    "ModelExecutionComparability",
    "ModelHypothesis",
    "ModelHypothesisRevision",
    "ModelLifecycle",
    "ModelObservedOutcome",
    "ModelOutcomeChannel",
    "ModelPerformanceSummary",
    "ModelPrediction",
    "ModelPredictorVariant",
    "ModelRevision",
    "ModelRevisionReason",
    "ModelSourceClaim",
    "ModelSourceKind",
    "ModelTargetKind",
    "PredictiveModel",
    "ScientificModelLedger",
    "ScientificModelPolicy",
    "bump_notice",
    "empty_scientific_model_ledger",
    "prune_terminal_cases",
    "scientific_case_id",
    "scientific_hypothesis_id",
    "scientific_model_id",
    "scientific_prediction_id",
    "target_alphabet",
]

_LOG: Final[logging.Logger] = logging.getLogger("agents.cognition.scientific_models")

SCIENTIFIC_MODELS_POLICY_VERSION: Final[str] = "scientific-models.v1"

MAX_HYPOTHESES: Final[int] = 32
MAX_MODELS: Final[int] = 64
MAX_PENDING_CASES: Final[int] = 128
MAX_TERMINAL_CASES: Final[int] = 512
MAX_REVISION_RECORDS: Final[int] = 512
MAX_DERIVATION_SAMPLES: Final[int] = 256
MAX_EMPIRICAL_BINS: Final[int] = 64
MAX_COVERAGE_NOTICES: Final[int] = 128
MAX_PERFORMANCE_SUMMARIES: Final[int] = 4096
MAX_PAIR_COMPARISONS: Final[int] = 2048

MAX_SOURCE_REFS: Final[int] = 8
MAX_CONDITIONS: Final[int] = 8
MAX_EVIDENCE_REFS: Final[int] = 64
MAX_TARGET_ALPHABET: Final[int] = 5
MAX_OUTCOME_REFS: Final[int] = 2
MAX_PREDICTIONS_PER_CASE: Final[int] = 2
MAX_HYPOTHESIS_REVISIONS: Final[int] = 32
MAX_MODEL_REVISIONS: Final[int] = 32

DISEASE_RISK_CAPABILITY: Final[str] = "unavailable_no_observable"


class ModelTargetKind(StrEnum):
    """Closed predictive target domains."""

    SEASON = "season"
    RESOURCE_REGENERATION = "resource_regeneration"
    PRODUCTION_OUTCOME = "production_outcome"
    DISEASE_RISK = "disease_risk"


@dataclass(frozen=True, slots=True)
class ModelSourceClaim:
    """One frozen categorical experimental claim used as a predictive source."""

    operator: ExperimentOperator
    operand_a_id: str
    operand_b_id: str | None
    process_token: ExperimentProcessToken

    def __post_init__(self) -> None:
        if type(self.operator) is not ExperimentOperator:
            raise _fail("operator", "invalid_type")
        require_stable_id("operand_a_id", self.operand_a_id)
        if self.operand_b_id is not None:
            require_stable_id("operand_b_id", self.operand_b_id)
        if type(self.process_token) is not ExperimentProcessToken:
            raise _fail("process_token", "invalid_type")
        if self.process_token is ExperimentProcessToken.NONE:
            raise _fail("process_token", "invalid_process")


class ModelSourceKind(StrEnum):
    """Where the owner's model hypothesis came from."""

    OBSERVED_REGULARITY = "observed_regularity"
    EXPERIMENT_HYPOTHESIS = "experiment_hypothesis"


class ModelLifecycle(StrEnum):
    """Owner-relative source/model lifecycle; never an objective status."""

    ACTIVE = "active"
    SUSPENDED = "suspended"
    RETIRED = "retired"


class ModelRevisionReason(StrEnum):
    """Closed reasons for one append-only model or hypothesis revision."""

    FORMULATED = "formulated"
    SOURCE_CHANGED = "source_changed"
    PARAMETER_UPDATED = "parameter_updated"
    RETIRED = "retired"
    SUSPENDED = "suspended"
    RESUMED = "resumed"


class ModelPredictorVariant(StrEnum):
    """The two candidate predictors every case carries."""

    HYPOTHESIS_BASELINE_V1 = "hypothesis_baseline_v1"
    EMPIRICAL_CONTEXT_V1 = "empirical_context_v1"


class ForecastCaseState(StrEnum):
    """Case lifecycle. Only ``pending`` can still settle."""

    PENDING = "pending"
    SCORED = "scored"
    NOT_ATTEMPTED = "not_attempted"
    NOT_COMPARABLE = "not_comparable"
    UNAVAILABLE = "unavailable"


class ModelOutcomeChannel(StrEnum):
    """Closed channels through which an owner may observe an outcome."""

    OBSERVATION = "observation"


class ModelExecutionComparability(StrEnum):
    """Whether one bound execution matches the forecast conditions."""

    COMPARABLE = "comparable"
    CHANGED_CONDITIONS = "changed_conditions"
    UNKNOWN_CONDITIONS = "unknown_conditions"


class ModelComparisonStatus(StrEnum):
    """Descriptive paired comparison outcome; never a ranking or truth claim."""

    LOWER_LOSS_A = "lower_loss_a"
    LOWER_LOSS_B = "lower_loss_b"
    TIED = "tied"
    INSUFFICIENT_SAMPLES = "insufficient_samples"


SEASON_CLASSES: Final[tuple[str, ...]] = tuple(item.value for item in Season)
RESOURCE_CHANGE_CLASSES: Final[tuple[str, ...]] = (
    "decrease",
    "unchanged",
    "increase",
)
PRODUCTION_CLASSES: Final[tuple[str, ...]] = tuple(
    item.value for item in ExperimentOutcomeClass
)

_ALPHABETS: Final[dict[ModelTargetKind, tuple[str, ...]]] = {
    ModelTargetKind.SEASON: SEASON_CLASSES,
    ModelTargetKind.RESOURCE_REGENERATION: RESOURCE_CHANGE_CLASSES,
    ModelTargetKind.PRODUCTION_OUTCOME: PRODUCTION_CLASSES,
    ModelTargetKind.DISEASE_RISK: (),
}

_CONDITION_SLOTS: Final[frozenset[str]] = frozenset(
    {"location", "season", "weather", "day_phase"}
)

_COVERAGE_REASON_CODES: Final[frozenset[str]] = frozenset(
    {
        "disease_unavailable_no_observable",
        "empirical_bin_cap",
        "hypothesis_cap",
        "model_cap",
        "not_comparable",
        "not_attempted",
        "no_comparable_outcome",
        "observation_source_missing",
        "pending_cap",
        "retention_cap",
        "sample_cap",
        "source_missing",
        "source_retired",
        "source_suspended",
        "summary_cap",
        "terminal_cap",
        "unavailable",
    }
)

_SETTLEMENT_REASONS: Final[frozenset[str]] = frozenset(
    {
        "observed",
        "missing_observation",
        "source_unavailable",
        "not_attempted",
        "ambiguous_execution",
        "changed_conditions",
        "unknown_conditions",
        "unit_mismatch",
        "occluded",
    }
)

_TERMINAL_STATES: Final[frozenset[ForecastCaseState]] = frozenset(
    {
        ForecastCaseState.SCORED,
        ForecastCaseState.NOT_ATTEMPTED,
        ForecastCaseState.NOT_COMPARABLE,
        ForecastCaseState.UNAVAILABLE,
    }
)


def _fail(field_name: str, reason: str) -> ValueError:
    return ValueError(f"{field_name}: {reason}")


def _require_text(field_name: str, value: object, *, max_length: int = 128) -> str:
    if not isinstance(value, str) or not value:
        raise _fail(field_name, "invalid_type")
    if len(value) > max_length or value != value.strip():
        raise _fail(field_name, "invalid_value")
    if any(ord(char) < 32 for char in value):
        raise _fail(field_name, "invalid_value")
    return value


def _require_int(
    field_name: str,
    value: object,
    *,
    minimum: int = 0,
    maximum: int | None = None,
) -> int:
    if isinstance(value, bool) or type(value) is not int:
        raise _fail(field_name, "invalid_type")
    if value < minimum:
        raise _fail(field_name, "invalid_range")
    if maximum is not None and value > maximum:
        raise _fail(field_name, "invalid_range")
    return value


def _require_tuple(field_name: str, value: object) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, tuple):
        raise _fail(field_name, "invalid_type")
    return value


def target_alphabet(kind: ModelTargetKind) -> tuple[str, ...]:
    """Return the closed categorical alphabet for one target kind."""

    if type(kind) is not ModelTargetKind:
        raise _fail("target_kind", "invalid_type")
    return _ALPHABETS[kind]


def _argmax(values: tuple[int, ...]) -> int:
    best = 0
    for index in range(1, len(values)):
        if values[index] > values[best]:
            best = index
    return best


def _digest(*parts: str) -> str:
    material = "|".join((SCIENTIFIC_MODELS_POLICY_VERSION, *parts))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def scientific_hypothesis_id(
    owner_id: AgentId,
    target_kind: ModelTargetKind,
    target_ref: str,
    unit_token: str,
    horizon_ticks: int,
    source_kind: ModelSourceKind,
) -> str:
    """Stable identity from owner, target and source kind. No RNG or clock."""

    if type(owner_id) is not AgentId:
        raise _fail("owner_id", "invalid_type")
    if type(target_kind) is not ModelTargetKind:
        raise _fail("target_kind", "invalid_type")
    if type(source_kind) is not ModelSourceKind:
        raise _fail("source_kind", "invalid_type")
    require_stable_id("target_ref", target_ref)
    require_stable_id("unit_token", unit_token)
    _require_int("horizon_ticks", horizon_ticks, minimum=1, maximum=64)
    return (
        "smh:"
        + _digest(
            owner_id.value,
            target_kind.value,
            target_ref,
            unit_token,
            str(horizon_ticks),
            source_kind.value,
        )[:32]
    )


def scientific_model_id(
    owner_id: AgentId,
    hypothesis_id: str,
    predictor_variant: ModelPredictorVariant,
    target_ref: str,
    unit_token: str,
    horizon_ticks: int,
) -> str:
    """Stable model identity; excludes growing evidence and performance."""

    if type(owner_id) is not AgentId:
        raise _fail("owner_id", "invalid_type")
    if type(predictor_variant) is not ModelPredictorVariant:
        raise _fail("predictor_variant", "invalid_type")
    require_stable_id("hypothesis_id", hypothesis_id)
    require_stable_id("target_ref", target_ref)
    require_stable_id("unit_token", unit_token)
    _require_int("horizon_ticks", horizon_ticks, minimum=1, maximum=64)
    return (
        "smm:"
        + _digest(
            owner_id.value,
            hypothesis_id,
            predictor_variant.value,
            target_ref,
            unit_token,
            str(horizon_ticks),
        )[:32]
    )


def scientific_case_id(owner_id: AgentId, observation_key: str) -> str:
    """Stable case identity from the owner and the issuing observation key."""

    if type(owner_id) is not AgentId:
        raise _fail("owner_id", "invalid_type")
    require_stable_id("observation_key", observation_key)
    return "smc:" + _digest(owner_id.value, observation_key)[:32]


def scientific_prediction_id(case_id: str, variant: ModelPredictorVariant) -> str:
    if type(variant) is not ModelPredictorVariant:
        raise _fail("predictor_variant", "invalid_type")
    require_stable_id("case_id", case_id)
    return "smp:" + _digest(case_id, variant.value)[:32]


@dataclass(frozen=True, slots=True)
class ScientificModelPolicy:
    """Locked caps and policy identity for one owner's predictive ledger."""

    policy_version: str = SCIENTIFIC_MODELS_POLICY_VERSION
    max_hypotheses: int = MAX_HYPOTHESES
    max_models: int = MAX_MODELS
    max_pending_cases: int = MAX_PENDING_CASES
    max_terminal_cases: int = MAX_TERMINAL_CASES
    max_revision_records: int = MAX_REVISION_RECORDS
    max_derivation_samples: int = MAX_DERIVATION_SAMPLES
    max_empirical_bins: int = MAX_EMPIRICAL_BINS
    max_coverage_notices: int = MAX_COVERAGE_NOTICES

    def __post_init__(self) -> None:
        if self.policy_version != SCIENTIFIC_MODELS_POLICY_VERSION:
            raise _fail("policy_version", "unsupported_policy")
        locked = (
            ("max_hypotheses", MAX_HYPOTHESES),
            ("max_models", MAX_MODELS),
            ("max_pending_cases", MAX_PENDING_CASES),
            ("max_terminal_cases", MAX_TERMINAL_CASES),
            ("max_revision_records", MAX_REVISION_RECORDS),
            ("max_derivation_samples", MAX_DERIVATION_SAMPLES),
            ("max_empirical_bins", MAX_EMPIRICAL_BINS),
            ("max_coverage_notices", MAX_COVERAGE_NOTICES),
        )
        for name, expected in locked:
            if _require_int(name, getattr(self, name), minimum=1) != expected:
                raise _fail(name, "policy_mismatch")


@dataclass(frozen=True, slots=True)
class ModelCondition:
    """One closed owner-visible condition slot and its stable token."""

    slot: str
    value_token: str

    def __post_init__(self) -> None:
        if self.slot not in _CONDITION_SLOTS:
            raise _fail("slot", "invalid_slot")
        _require_text("value_token", self.value_token, max_length=128)
        if "|" in self.value_token or "=" in self.value_token:
            raise _fail("value_token", "invalid_separator")


def _validated_conditions(
    field_name: str, conditions: object
) -> tuple[ModelCondition, ...]:
    rows = _require_tuple(field_name, conditions)
    if len(rows) > MAX_CONDITIONS:
        raise _fail(field_name, "invalid_cap")
    seen: set[str] = set()
    for row in rows:
        if type(row) is not ModelCondition:
            raise _fail(field_name, "invalid_type")
        if row.slot in seen:
            raise _fail(field_name, "duplicate_slot")
        seen.add(row.slot)
    return rows


@dataclass(frozen=True, slots=True)
class ModelHypothesisRevision:
    """One append-only revision of an owner's predictive hypothesis."""

    revision_index: int
    tick: int
    reason: ModelRevisionReason
    conditions: tuple[ModelCondition, ...] = ()
    predicted_class: str | None = None
    source_revision_ref: str = ""
    support_refs: tuple[str, ...] = ()
    contradiction_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_int("revision_index", self.revision_index)
        _require_int("tick", self.tick)
        if type(self.reason) is not ModelRevisionReason:
            raise _fail("reason", "invalid_type")
        object.__setattr__(
            self, "conditions", _validated_conditions("conditions", self.conditions)
        )
        if self.predicted_class is not None:
            _require_text("predicted_class", self.predicted_class, max_length=64)
        if self.source_revision_ref:
            require_stable_id("source_revision_ref", self.source_revision_ref)
        for field_name in ("support_refs", "contradiction_refs"):
            refs = _require_tuple(field_name, getattr(self, field_name))
            if len(refs) > MAX_EVIDENCE_REFS:
                raise _fail(field_name, "invalid_cap")
            for ref in refs:
                require_stable_id(field_name, ref)


@dataclass(frozen=True, slots=True)
class ModelHypothesis:
    """An owner belief about an observable regularity. Never a world law."""

    owner_id: AgentId
    hypothesis_id: str
    target_kind: ModelTargetKind
    target_ref: str
    unit_token: str
    horizon_ticks: int
    source_kind: ModelSourceKind
    source_refs: tuple[str, ...] = ()
    source_claim: ModelSourceClaim | None = None
    revisions: tuple[ModelHypothesisRevision, ...] = ()
    lifecycle: ModelLifecycle = ModelLifecycle.ACTIVE
    created_tick: int = 0
    sequence: int = 0
    causal_link_ref: str = ""

    def __post_init__(self) -> None:
        if type(self.owner_id) is not AgentId:
            raise _fail("owner_id", "invalid_type")
        require_stable_id("hypothesis_id", self.hypothesis_id)
        if type(self.target_kind) is not ModelTargetKind:
            raise _fail("target_kind", "invalid_type")
        if self.target_kind is ModelTargetKind.DISEASE_RISK:
            raise _fail("target_kind", "disease_unavailable")
        require_stable_id("target_ref", self.target_ref)
        require_stable_id("unit_token", self.unit_token)
        _require_int("horizon_ticks", self.horizon_ticks, minimum=1, maximum=64)
        if type(self.source_kind) is not ModelSourceKind:
            raise _fail("source_kind", "invalid_type")
        refs = _require_tuple("source_refs", self.source_refs)
        if len(refs) > MAX_SOURCE_REFS:
            raise _fail("source_refs", "invalid_cap")
        for ref in refs:
            require_stable_id("source_refs", ref)
        if type(self.lifecycle) is not ModelLifecycle:
            raise _fail("lifecycle", "invalid_type")
        _require_int("created_tick", self.created_tick)
        _require_int("sequence", self.sequence)
        if self.causal_link_ref:
            require_stable_id("causal_link_ref", self.causal_link_ref)
        if self.source_claim is not None and (
            type(self.source_claim) is not ModelSourceClaim
        ):
            raise _fail("source_claim", "invalid_type")
        if self.target_kind is ModelTargetKind.PRODUCTION_OUTCOME:
            if self.source_claim is None:
                raise _fail("source_claim", "missing")
        elif self.source_claim is not None:
            raise _fail("source_claim", "unexpected")
        revisions = _require_tuple("revisions", self.revisions)
        if not revisions:
            raise _fail("revisions", "empty")
        if len(revisions) > MAX_HYPOTHESIS_REVISIONS:
            raise _fail("revisions", "invalid_cap")
        previous = -1
        alphabet = target_alphabet(self.target_kind)
        for position, revision in enumerate(revisions):
            if type(revision) is not ModelHypothesisRevision:
                raise _fail("revisions", "invalid_type")
            if revision.revision_index <= previous:
                raise _fail("revisions", "out_of_order")
            previous = revision.revision_index
            if revision.revision_index != position:
                raise _fail("revisions", "invalid_index_sequence")
            if revision.predicted_class is None:
                raise _fail("revisions", "missing_class")
            if revision.predicted_class not in alphabet:
                raise _fail("revisions", "invalid_class")

    @property
    def current_revision(self) -> ModelHypothesisRevision:
        return self.revisions[-1]

    @property
    def predicted_class(self) -> str | None:
        return self.current_revision.predicted_class

    @property
    def revision_ref(self) -> str:
        return f"{self.hypothesis_id}#{self.current_revision.revision_index}"


@dataclass(frozen=True, slots=True)
class EmpiricalContextBin:
    """One bounded empirical context with per-class resolution counts."""

    context_digest: str
    counts: tuple[int, ...]
    last_tick: int

    def __post_init__(self) -> None:
        require_stable_id("context_digest", self.context_digest)
        counts = _require_tuple("counts", self.counts)
        if not counts or len(counts) > MAX_TARGET_ALPHABET:
            raise _fail("counts", "invalid_cap")
        for count in counts:
            _require_int("counts", count)
        _require_int("last_tick", self.last_tick)


@dataclass(frozen=True, slots=True)
class ModelRevision:
    """One append-only model revision. Prior cases pin older revisions."""

    revision_index: int
    tick: int
    reason: ModelRevisionReason
    source_revision_ref: str
    parameter_digest: str
    conditions: tuple[ModelCondition, ...] = ()
    predicted_class: str | None = None

    def __post_init__(self) -> None:
        _require_int("revision_index", self.revision_index)
        _require_int("tick", self.tick)
        if type(self.reason) is not ModelRevisionReason:
            raise _fail("reason", "invalid_type")
        require_stable_id("source_revision_ref", self.source_revision_ref)
        require_stable_id("parameter_digest", self.parameter_digest)
        object.__setattr__(
            self, "conditions", _validated_conditions("conditions", self.conditions)
        )
        if self.predicted_class is not None:
            _require_text("predicted_class", self.predicted_class, max_length=64)


@dataclass(frozen=True, slots=True)
class PredictiveModel:
    """One candidate predictor for an owner's model hypothesis."""

    owner_id: AgentId
    model_id: str
    hypothesis_id: str
    target_kind: ModelTargetKind
    target_ref: str
    unit_token: str
    horizon_ticks: int
    predictor_variant: ModelPredictorVariant
    source_revision_ref: str
    parameter_digest: str
    lifecycle: ModelLifecycle
    revisions: tuple[ModelRevision, ...] = ()
    empirical_bins: tuple[EmpiricalContextBin, ...] = ()
    created_tick: int = 0
    sequence: int = 0

    def __post_init__(self) -> None:
        if type(self.owner_id) is not AgentId:
            raise _fail("owner_id", "invalid_type")
        require_stable_id("model_id", self.model_id)
        require_stable_id("hypothesis_id", self.hypothesis_id)
        if type(self.target_kind) is not ModelTargetKind:
            raise _fail("target_kind", "invalid_type")
        if self.target_kind is ModelTargetKind.DISEASE_RISK:
            raise _fail("target_kind", "disease_unavailable")
        require_stable_id("target_ref", self.target_ref)
        require_stable_id("unit_token", self.unit_token)
        _require_int("horizon_ticks", self.horizon_ticks, minimum=1, maximum=64)
        if type(self.predictor_variant) is not ModelPredictorVariant:
            raise _fail("predictor_variant", "invalid_type")
        require_stable_id("source_revision_ref", self.source_revision_ref)
        require_stable_id("parameter_digest", self.parameter_digest)
        if type(self.lifecycle) is not ModelLifecycle:
            raise _fail("lifecycle", "invalid_type")
        _require_int("created_tick", self.created_tick)
        _require_int("sequence", self.sequence)
        revisions = _require_tuple("revisions", self.revisions)
        if not revisions:
            raise _fail("revisions", "empty")
        if len(revisions) > MAX_MODEL_REVISIONS:
            raise _fail("revisions", "invalid_cap")
        alphabet = target_alphabet(self.target_kind)
        previous = -1
        for revision in revisions:
            if type(revision) is not ModelRevision:
                raise _fail("revisions", "invalid_type")
            if revision.revision_index <= previous:
                raise _fail("revisions", "out_of_order")
            previous = revision.revision_index
            if revision.predicted_class is not None and (
                revision.predicted_class not in alphabet
            ):
                raise _fail("revisions", "invalid_class")
        bins = _require_tuple("empirical_bins", self.empirical_bins)
        if len(bins) > MAX_EMPIRICAL_BINS:
            raise _fail("empirical_bins", "invalid_cap")
        seen: set[str] = set()
        for bin_row in bins:
            if type(bin_row) is not EmpiricalContextBin:
                raise _fail("empirical_bins", "invalid_type")
            if bin_row.context_digest in seen:
                raise _fail("empirical_bins", "duplicate_context")
            if len(bin_row.counts) != len(alphabet):
                raise _fail("empirical_bins", "invalid_alphabet")
            seen.add(bin_row.context_digest)

    @property
    def current_revision(self) -> ModelRevision:
        return self.revisions[-1]


@dataclass(frozen=True, slots=True)
class ModelPrediction:
    """One frozen candidate distribution for a single forecast case."""

    prediction_id: str
    model_id: str
    hypothesis_id: str
    predictor_variant: ModelPredictorVariant
    alphabet: tuple[str, ...]
    probabilities_milli: tuple[int, ...]
    predicted_class: str
    confidence_milli: int
    model_revision_ref: str
    source_revision_ref: str
    parameter_digest: str

    def __post_init__(self) -> None:
        require_stable_id("prediction_id", self.prediction_id)
        require_stable_id("model_id", self.model_id)
        require_stable_id("hypothesis_id", self.hypothesis_id)
        if type(self.predictor_variant) is not ModelPredictorVariant:
            raise _fail("predictor_variant", "invalid_type")
        alphabet = _require_tuple("alphabet", self.alphabet)
        if not alphabet or len(alphabet) > MAX_TARGET_ALPHABET:
            raise _fail("alphabet", "invalid_cap")
        if len(set(alphabet)) != len(alphabet):
            raise _fail("alphabet", "duplicate_class")
        probabilities = _require_tuple("probabilities_milli", self.probabilities_milli)
        if len(probabilities) != len(alphabet):
            raise _fail("probabilities_milli", "invalid_alphabet")
        total = 0
        for value in probabilities:
            _require_int("probabilities_milli", value)
            total += value
        if total != 1000:
            raise _fail("probabilities_milli", "invalid_sum")
        if self.predicted_class not in alphabet:
            raise _fail("predicted_class", "invalid_class")
        if self.predicted_class != alphabet[_argmax(probabilities)]:
            raise _fail("predicted_class", "not_argmax")
        _require_int("confidence_milli", self.confidence_milli, maximum=1000)
        if self.confidence_milli != probabilities[alphabet.index(self.predicted_class)]:
            raise _fail("confidence_milli", "not_predicted_probability")
        require_stable_id("model_revision_ref", self.model_revision_ref)
        require_stable_id("source_revision_ref", self.source_revision_ref)
        require_stable_id("parameter_digest", self.parameter_digest)

    @property
    def brier_numerator(self) -> int:
        """Integer multiclass Brier numerator against the predicted class."""
        target = self.alphabet.index(self.predicted_class)
        return sum(
            (value - (1000 if index == target else 0)) ** 2
            for index, value in enumerate(self.probabilities_milli)
        )


@dataclass(frozen=True, slots=True)
class ModelObservedOutcome:
    """One actual owner observation that settles a forecast."""

    observed_class: str
    observed_tick: int
    outcome_ref: str
    channel: ModelOutcomeChannel = ModelOutcomeChannel.OBSERVATION

    def __post_init__(self) -> None:
        _require_text("observed_class", self.observed_class, max_length=64)
        _require_int("observed_tick", self.observed_tick)
        require_stable_id("outcome_ref", self.outcome_ref)
        if type(self.channel) is not ModelOutcomeChannel:
            raise _fail("channel", "invalid_type")


@dataclass(frozen=True, slots=True)
class ForecastCase:
    """One frozen prior forecast shared by exactly two candidate models."""

    case_id: str
    owner_id: AgentId
    target_kind: ModelTargetKind
    target_ref: str
    unit_token: str
    horizon_ticks: int
    alphabet: tuple[str, ...]
    conditions: tuple[ModelCondition, ...]
    predictions: tuple[ModelPrediction, ...]
    issued_observation_tick: int
    issued_observation_key: str
    committed_after_tick: int
    target_observation_tick: int
    training_high_water_tick: int
    state: ForecastCaseState = ForecastCaseState.PENDING
    observed: ModelObservedOutcome | None = None
    outcome_refs: tuple[str, ...] = ()
    source_claim: ModelSourceClaim | None = None
    reference_quantity_milli: int | None = None
    reference_resource_kind: str | None = None
    settlement_reason: str = ""
    outcome_start_milli: int | None = None
    outcome_end_milli: int | None = None

    def __post_init__(self) -> None:
        require_stable_id("case_id", self.case_id)
        if type(self.owner_id) is not AgentId:
            raise _fail("owner_id", "invalid_type")
        if type(self.target_kind) is not ModelTargetKind:
            raise _fail("target_kind", "invalid_type")
        if self.target_kind is ModelTargetKind.DISEASE_RISK:
            raise _fail("target_kind", "disease_unavailable")
        require_stable_id("target_ref", self.target_ref)
        require_stable_id("unit_token", self.unit_token)
        _require_int("horizon_ticks", self.horizon_ticks, minimum=1, maximum=64)
        alphabet = _require_tuple("alphabet", self.alphabet)
        if alphabet != target_alphabet(self.target_kind):
            raise _fail("alphabet", "invalid_alphabet")
        object.__setattr__(
            self, "conditions", _validated_conditions("conditions", self.conditions)
        )
        predictions = _require_tuple("predictions", self.predictions)
        if len(predictions) != MAX_PREDICTIONS_PER_CASE:
            raise _fail("predictions", "invalid_count")
        variants: set[ModelPredictorVariant] = set()
        model_ids: set[str] = set()
        for prediction in predictions:
            if type(prediction) is not ModelPrediction:
                raise _fail("predictions", "invalid_type")
            if prediction.alphabet != alphabet:
                raise _fail("predictions", "invalid_alphabet")
            if prediction.predictor_variant in variants:
                raise _fail("predictions", "duplicate_variant")
            if prediction.model_id in model_ids:
                raise _fail("predictions", "duplicate_model")
            variants.add(prediction.predictor_variant)
            model_ids.add(prediction.model_id)
        _require_int("issued_observation_tick", self.issued_observation_tick)
        require_stable_id("issued_observation_key", self.issued_observation_key)
        _require_int("committed_after_tick", self.committed_after_tick)
        _require_int("target_observation_tick", self.target_observation_tick)
        _require_int("training_high_water_tick", self.training_high_water_tick)
        if self.committed_after_tick != self.issued_observation_tick:
            raise _fail("committed_after_tick", "not_issuance_tick")
        if self.target_observation_tick != (
            self.issued_observation_tick + self.horizon_ticks
        ):
            raise _fail("target_observation_tick", "invalid_horizon")
        if self.training_high_water_tick > self.issued_observation_tick:
            raise _fail("training_high_water_tick", "trained_on_target")
        if type(self.state) is not ForecastCaseState:
            raise _fail("state", "invalid_type")
        if (
            self.observed is not None
            and type(self.observed) is not ModelObservedOutcome
        ):
            raise _fail("observed", "invalid_type")
        if self.state is ForecastCaseState.PENDING:
            if self.observed is not None:
                raise _fail("state", "pending_with_outcome")
        elif self.state is ForecastCaseState.SCORED:
            if self.observed is None:
                raise _fail("state", "scored_without_outcome")
        elif self.observed is not None:
            raise _fail("state", "unscored_with_outcome")
        if self.observed is not None:
            if self.observed.observed_class not in alphabet:
                raise _fail("observed", "invalid_class")
            if self.observed.observed_tick != self.target_observation_tick:
                raise _fail("observed", "invalid_tick")
        refs = _require_tuple("outcome_refs", self.outcome_refs)
        if len(refs) > MAX_OUTCOME_REFS:
            raise _fail("outcome_refs", "invalid_cap")
        for ref in refs:
            require_stable_id("outcome_refs", ref)
        if self.source_claim is not None and (
            type(self.source_claim) is not ModelSourceClaim
        ):
            raise _fail("source_claim", "invalid_type")
        if self.target_kind is ModelTargetKind.PRODUCTION_OUTCOME:
            if self.source_claim is None:
                raise _fail("source_claim", "missing")
        elif self.source_claim is not None:
            raise _fail("source_claim", "unexpected")
        if self.state is ForecastCaseState.PENDING:
            if self.settlement_reason:
                raise _fail("settlement_reason", "unexpected")
        elif self.settlement_reason and (
            self.settlement_reason not in _SETTLEMENT_REASONS
        ):
            raise _fail("settlement_reason", "unknown_reason")
        if self.outcome_start_milli is not None:
            _require_int("outcome_start_milli", self.outcome_start_milli)
        if self.outcome_end_milli is not None:
            _require_int("outcome_end_milli", self.outcome_end_milli)
        if (
            self.outcome_start_milli is not None
            or self.outcome_end_milli is not None
        ) and self.target_kind is not ModelTargetKind.RESOURCE_REGENERATION:
            raise _fail("outcome_start_milli", "unexpected")
        if self.target_kind is ModelTargetKind.RESOURCE_REGENERATION:
            if self.reference_quantity_milli is None:
                raise _fail("reference_quantity_milli", "missing")
            _require_int(
                "reference_quantity_milli", self.reference_quantity_milli
            )
            _require_text(
                "reference_resource_kind",
                self.reference_resource_kind,
                max_length=64,
            )
        elif (
            self.reference_quantity_milli is not None
            or self.reference_resource_kind is not None
        ):
            raise _fail("reference_quantity_milli", "unexpected")

    @property
    def is_pending(self) -> bool:
        return self.state is ForecastCaseState.PENDING


@dataclass(frozen=True, slots=True)
class ModelExecutionBinding:
    """One exact owner action bound to a production forecast case."""

    binding_id: str
    owner_id: AgentId
    case_id: str
    tick: int
    command_ref: str
    target_ref: str
    conditions: tuple[ModelCondition, ...]
    comparability: ModelExecutionComparability

    def __post_init__(self) -> None:
        require_stable_id("binding_id", self.binding_id)
        if type(self.owner_id) is not AgentId:
            raise _fail("owner_id", "invalid_type")
        require_stable_id("case_id", self.case_id)
        _require_int("tick", self.tick)
        require_stable_id("command_ref", self.command_ref)
        require_stable_id("target_ref", self.target_ref)
        object.__setattr__(
            self, "conditions", _validated_conditions("conditions", self.conditions)
        )
        if type(self.comparability) is not ModelExecutionComparability:
            raise _fail("comparability", "invalid_type")


@dataclass(frozen=True, slots=True)
class DerivationSample:
    """One bounded owner observation retained for model derivation."""

    sample_id: str
    target_kind: ModelTargetKind
    target_ref: str
    unit_token: str
    observed_tick: int
    observation_key: str
    location_ref: str
    observed_class: str | None = None
    quantity_milli: int | None = None
    kind_token: str = ""
    conditions: tuple[ModelCondition, ...] = ()

    def __post_init__(self) -> None:
        require_stable_id("sample_id", self.sample_id)
        if type(self.target_kind) is not ModelTargetKind:
            raise _fail("target_kind", "invalid_type")
        require_stable_id("target_ref", self.target_ref)
        require_stable_id("unit_token", self.unit_token)
        _require_int("observed_tick", self.observed_tick)
        require_stable_id("observation_key", self.observation_key)
        require_stable_id("location_ref", self.location_ref)
        if self.observed_class is not None:
            _require_text("observed_class", self.observed_class, max_length=64)
        if self.quantity_milli is not None:
            _require_int("quantity_milli", self.quantity_milli)
        if self.kind_token:
            _require_text("kind_token", self.kind_token, max_length=64)
        object.__setattr__(
            self, "conditions", _validated_conditions("conditions", self.conditions)
        )
        if self.observed_class is None and self.quantity_milli is None:
            raise _fail("observed_class", "missing_value")


@dataclass(frozen=True, slots=True)
class CalibrationBin:
    """One of ten confidence bins over retained scored cases."""

    bin_index: int
    count: int
    confidence_sum_milli: int
    hit_count: int

    def __post_init__(self) -> None:
        _require_int("bin_index", self.bin_index, maximum=9)
        _require_int("count", self.count)
        _require_int("confidence_sum_milli", self.confidence_sum_milli)
        _require_int("hit_count", self.hit_count)
        if self.hit_count > self.count:
            raise _fail("hit_count", "invalid_count")


@dataclass(frozen=True, slots=True)
class ModelPerformanceSummary:
    """Retained-cohort descriptive performance for one model and cohort."""

    summary_id: str
    owner_id: AgentId
    model_id: str
    target_kind: ModelTargetKind
    target_ref: str
    unit_token: str
    horizon_ticks: int
    context_digest: str
    alphabet: tuple[str, ...]
    scored_count: int
    hit_count: int
    hit_share_milli: int
    brier_numerator_sum: int
    mean_brier_millionths: int
    calibration_gap_milli: int | None = None
    calibration_bins: tuple[CalibrationBin, ...] = ()
    evicted_count: int = 0
    missing_count: int = 0
    pending_count: int = 0
    unavailable_count: int = 0
    not_attempted_count: int = 0
    not_comparable_count: int = 0
    retained_floor_tick: int = 0

    def __post_init__(self) -> None:
        require_stable_id("summary_id", self.summary_id)
        if type(self.owner_id) is not AgentId:
            raise _fail("owner_id", "invalid_type")
        require_stable_id("model_id", self.model_id)
        if type(self.target_kind) is not ModelTargetKind:
            raise _fail("target_kind", "invalid_type")
        require_stable_id("target_ref", self.target_ref)
        require_stable_id("unit_token", self.unit_token)
        _require_int("horizon_ticks", self.horizon_ticks, minimum=1, maximum=64)
        require_stable_id("context_digest", self.context_digest)
        alphabet = _require_tuple("alphabet", self.alphabet)
        if alphabet != target_alphabet(self.target_kind):
            raise _fail("alphabet", "invalid_alphabet")
        for name in (
            "scored_count",
            "hit_count",
            "hit_share_milli",
            "brier_numerator_sum",
            "mean_brier_millionths",
            "evicted_count",
            "missing_count",
            "pending_count",
            "unavailable_count",
            "not_attempted_count",
            "not_comparable_count",
            "retained_floor_tick",
        ):
            _require_int(name, getattr(self, name))
        if self.scored_count == 0:
            raise _fail("scored_count", "empty_cohort")
        if self.hit_count > self.scored_count:
            raise _fail("hit_count", "invalid_count")
        if self.hit_share_milli > 1000:
            raise _fail("hit_share_milli", "invalid_range")
        if self.mean_brier_millionths > 2_000_000:
            raise _fail("mean_brier_millionths", "invalid_range")
        if self.calibration_gap_milli is not None:
            _require_int("calibration_gap_milli", self.calibration_gap_milli)
            if self.calibration_gap_milli > 1000:
                raise _fail("calibration_gap_milli", "invalid_range")
        bins = _require_tuple("calibration_bins", self.calibration_bins)
        if len(bins) > 10:
            raise _fail("calibration_bins", "invalid_cap")
        previous = -1
        for bin_row in bins:
            if type(bin_row) is not CalibrationBin:
                raise _fail("calibration_bins", "invalid_type")
            if bin_row.bin_index <= previous:
                raise _fail("calibration_bins", "out_of_order")
            previous = bin_row.bin_index


@dataclass(frozen=True, slots=True)
class ModelComparison:
    """Descriptive paired loss comparison on identical retained cases."""

    comparison_id: str
    owner_id: AgentId
    target_kind: ModelTargetKind
    target_ref: str
    unit_token: str
    horizon_ticks: int
    context_digest: str
    model_a_id: str
    model_b_id: str
    paired_count: int
    excluded_count: int
    mean_brier_millionths_a: int
    mean_brier_millionths_b: int
    a_minus_b_millionths: int
    status: ModelComparisonStatus

    def __post_init__(self) -> None:
        require_stable_id("comparison_id", self.comparison_id)
        if type(self.owner_id) is not AgentId:
            raise _fail("owner_id", "invalid_type")
        if type(self.target_kind) is not ModelTargetKind:
            raise _fail("target_kind", "invalid_type")
        require_stable_id("target_ref", self.target_ref)
        require_stable_id("unit_token", self.unit_token)
        _require_int("horizon_ticks", self.horizon_ticks, minimum=1, maximum=64)
        require_stable_id("context_digest", self.context_digest)
        require_stable_id("model_a_id", self.model_a_id)
        require_stable_id("model_b_id", self.model_b_id)
        if self.model_a_id == self.model_b_id:
            raise _fail("model_b_id", "same_model")
        for name in (
            "paired_count",
            "excluded_count",
            "mean_brier_millionths_a",
            "mean_brier_millionths_b",
        ):
            _require_int(name, getattr(self, name), maximum=2_000_000)
        if (
            isinstance(self.a_minus_b_millionths, bool)
            or type(self.a_minus_b_millionths) is not int
        ):
            raise _fail("a_minus_b_millionths", "invalid_type")
        if self.a_minus_b_millionths != (
            self.mean_brier_millionths_a - self.mean_brier_millionths_b
        ):
            raise _fail("a_minus_b_millionths", "inconsistent")
        if type(self.status) is not ModelComparisonStatus:
            raise _fail("status", "invalid_type")
        if self.paired_count < 3 and (
            self.status is not ModelComparisonStatus.INSUFFICIENT_SAMPLES
        ):
            raise _fail("status", "insufficient_samples")


@dataclass(frozen=True, slots=True)
class ModelCoverageNotice:
    """Aggregated coverage notice. Repeats increment counts, never append."""

    reason_code: str
    target_kind: ModelTargetKind
    first_tick: int
    last_tick: int
    count: int

    def __post_init__(self) -> None:
        if self.reason_code not in _COVERAGE_REASON_CODES:
            raise _fail("reason_code", "unknown_reason")
        if type(self.target_kind) is not ModelTargetKind:
            raise _fail("target_kind", "invalid_type")
        _require_int("first_tick", self.first_tick)
        _require_int("last_tick", self.last_tick)
        _require_int("count", self.count, minimum=1)
        if self.last_tick < self.first_tick:
            raise _fail("last_tick", "before_first_tick")


@dataclass(frozen=True, slots=True)
class ScientificModelLedger:
    """Bounded owner-local predictive state. Outside the objective fold."""

    owner_id: AgentId
    policy_version: str = SCIENTIFIC_MODELS_POLICY_VERSION
    hypotheses: tuple[ModelHypothesis, ...] = ()
    models: tuple[PredictiveModel, ...] = ()
    cases: tuple[ForecastCase, ...] = ()
    bindings: tuple[ModelExecutionBinding, ...] = ()
    samples: tuple[DerivationSample, ...] = ()
    summaries: tuple[ModelPerformanceSummary, ...] = ()
    comparisons: tuple[ModelComparison, ...] = ()
    notices: tuple[ModelCoverageNotice, ...] = ()
    issued_observation_keys: tuple[str, ...] = ()
    cursor: int = 0
    sequence: int = 0
    hypothesis_sequence: int = 0
    model_sequence: int = 0
    case_sequence: int = 0
    revision_sequence: int = 0
    evicted_cases: int = 0
    evicted_revisions: int = 0
    first_retained_tick: int | None = None
    last_observation_key: str = ""
    last_observation_tick: int = 0
    last_issued_tick: int = -1

    def __post_init__(self) -> None:
        if type(self.owner_id) is not AgentId:
            raise _fail("owner_id", "invalid_type")
        if self.policy_version != SCIENTIFIC_MODELS_POLICY_VERSION:
            raise _fail("policy_version", "unsupported_policy")
        for name in (
            "hypotheses",
            "models",
            "cases",
            "bindings",
            "samples",
            "summaries",
            "comparisons",
            "notices",
            "issued_observation_keys",
        ):
            _require_tuple(name, getattr(self, name))
        if len(self.hypotheses) > MAX_HYPOTHESES:
            raise _fail("hypotheses", "cap_exceeded")
        if len(self.models) > MAX_MODELS:
            raise _fail("models", "cap_exceeded")
        pending = [row for row in self.cases if row.is_pending]
        terminal = [row for row in self.cases if not row.is_pending]
        if len(pending) > MAX_PENDING_CASES:
            raise _fail("cases", "pending_cap_exceeded")
        if len(terminal) > MAX_TERMINAL_CASES:
            raise _fail("cases", "terminal_cap_exceeded")
        if len(self.bindings) > MAX_PENDING_CASES:
            raise _fail("bindings", "cap_exceeded")
        if len(self.samples) > MAX_DERIVATION_SAMPLES:
            raise _fail("samples", "cap_exceeded")
        if len(self.summaries) > MAX_PERFORMANCE_SUMMARIES:
            raise _fail("summaries", "cap_exceeded")
        if len(self.comparisons) > MAX_PAIR_COMPARISONS:
            raise _fail("comparisons", "cap_exceeded")
        if len(self.notices) > MAX_COVERAGE_NOTICES:
            raise _fail("notices", "cap_exceeded")
        if len(self.issued_observation_keys) > (MAX_PENDING_CASES + MAX_TERMINAL_CASES):
            raise _fail("issued_observation_keys", "cap_exceeded")
        if self.revision_records > MAX_REVISION_RECORDS:
            raise _fail("revisions", "cap_exceeded")

        hypothesis_ids: set[str] = set()
        for hypothesis in self.hypotheses:
            if type(hypothesis) is not ModelHypothesis:
                raise _fail("hypotheses", "invalid_type")
            if hypothesis.owner_id != self.owner_id:
                raise _fail("hypotheses", "owner_mismatch")
            if hypothesis.hypothesis_id in hypothesis_ids:
                raise _fail("hypotheses", "duplicate_id")
            hypothesis_ids.add(hypothesis.hypothesis_id)

        model_ids: set[str] = set()
        for model in self.models:
            if type(model) is not PredictiveModel:
                raise _fail("models", "invalid_type")
            if model.owner_id != self.owner_id:
                raise _fail("models", "owner_mismatch")
            if model.model_id in model_ids:
                raise _fail("models", "duplicate_id")
            if model.hypothesis_id not in hypothesis_ids:
                raise _fail("models", "unknown_hypothesis")
            model_ids.add(model.model_id)

        case_ids: set[str] = set()
        for case in self.cases:
            if type(case) is not ForecastCase:
                raise _fail("cases", "invalid_type")
            if case.owner_id != self.owner_id:
                raise _fail("cases", "owner_mismatch")
            if case.case_id in case_ids:
                raise _fail("cases", "duplicate_id")
            for prediction in case.predictions:
                if prediction.model_id not in model_ids:
                    raise _fail("cases", "unknown_model")
            case_ids.add(case.case_id)

        binding_ids: set[str] = set()
        for binding in self.bindings:
            if type(binding) is not ModelExecutionBinding:
                raise _fail("bindings", "invalid_type")
            if binding.owner_id != self.owner_id:
                raise _fail("bindings", "owner_mismatch")
            if binding.binding_id in binding_ids:
                raise _fail("bindings", "duplicate_id")
            if binding.case_id not in case_ids:
                raise _fail("bindings", "unknown_case")
            binding_ids.add(binding.binding_id)

        sample_ids: set[str] = set()
        for sample in self.samples:
            if type(sample) is not DerivationSample:
                raise _fail("samples", "invalid_type")
            if sample.sample_id in sample_ids:
                raise _fail("samples", "duplicate_id")
            sample_ids.add(sample.sample_id)

        summary_ids: set[str] = set()
        for summary in self.summaries:
            if type(summary) is not ModelPerformanceSummary:
                raise _fail("summaries", "invalid_type")
            if summary.owner_id != self.owner_id:
                raise _fail("summaries", "owner_mismatch")
            if summary.summary_id in summary_ids:
                raise _fail("summaries", "duplicate_id")
            if summary.model_id not in model_ids:
                raise _fail("summaries", "unknown_model")
            summary_ids.add(summary.summary_id)

        comparison_ids: set[str] = set()
        for comparison in self.comparisons:
            if type(comparison) is not ModelComparison:
                raise _fail("comparisons", "invalid_type")
            if comparison.owner_id != self.owner_id:
                raise _fail("comparisons", "owner_mismatch")
            if comparison.comparison_id in comparison_ids:
                raise _fail("comparisons", "duplicate_id")
            if (
                comparison.model_a_id not in model_ids
                or comparison.model_b_id not in model_ids
            ):
                raise _fail("comparisons", "unknown_model")
            comparison_ids.add(comparison.comparison_id)

        notice_keys: set[tuple[str, ModelTargetKind]] = set()
        for notice in self.notices:
            if type(notice) is not ModelCoverageNotice:
                raise _fail("notices", "invalid_type")
            key = (notice.reason_code, notice.target_kind)
            if key in notice_keys:
                raise _fail("notices", "duplicate_key")
            notice_keys.add(key)

        issued_keys = self.issued_observation_keys
        if len(set(issued_keys)) != len(issued_keys):
            raise _fail("issued_observation_keys", "duplicate_id")
        for issued_key in issued_keys:
            require_stable_id("issued_observation_keys", issued_key)

        for name in (
            "cursor",
            "sequence",
            "hypothesis_sequence",
            "model_sequence",
            "case_sequence",
            "revision_sequence",
            "evicted_cases",
            "evicted_revisions",
        ):
            require_exact_nonneg_int(name, getattr(self, name))
        if self.first_retained_tick is not None:
            _require_int("first_retained_tick", self.first_retained_tick)
        if self.last_observation_key:
            require_stable_id("last_observation_key", self.last_observation_key)
        _require_int("last_observation_tick", self.last_observation_tick)
        if (
            isinstance(self.last_issued_tick, bool)
            or type(self.last_issued_tick) is not int
            or self.last_issued_tick < -1
        ):
            raise _fail("last_issued_tick", "invalid_type")

    @property
    def revision_records(self) -> int:
        return sum(len(row.revisions) for row in self.hypotheses) + sum(
            len(row.revisions) for row in self.models
        )

    @property
    def pending_cases(self) -> tuple[ForecastCase, ...]:
        return tuple(row for row in self.cases if row.is_pending)

    @property
    def terminal_cases(self) -> tuple[ForecastCase, ...]:
        return tuple(row for row in self.cases if not row.is_pending)


def empty_scientific_model_ledger(owner_id: AgentId) -> ScientificModelLedger:
    """Construct an empty owner ledger. No content is copied from elsewhere."""

    if type(owner_id) is not AgentId:
        raise _fail("owner_id", "invalid_type")
    ledger = ScientificModelLedger(owner_id=owner_id)
    _LOG.debug(
        "scientific_model_ledger_constructed owner_id=%s hypothesis_count=%s "
        "model_count=%s case_count=%s",
        owner_id.value,
        0,
        0,
        0,
    )
    return ledger


def prune_terminal_cases(
    cases: tuple[ForecastCase, ...],
    *,
    pinned_case_ids: frozenset[str] = frozenset(),
    max_terminal: int = MAX_TERMINAL_CASES,
) -> tuple[tuple[ForecastCase, ...], int, int | None]:
    """Drop the oldest unpinned terminal cases. Pending cases are never dropped.

    Returns ``(kept_cases, evicted_count, first_retained_tick)``.
    """

    if not isinstance(cases, tuple):
        raise _fail("cases", "invalid_type")
    _require_int("max_terminal", max_terminal, minimum=0)
    terminal = [row for row in cases if not row.is_pending]
    if len(terminal) <= max_terminal:
        retained = list(cases)
    else:
        removable = sorted(
            (row for row in terminal if row.case_id not in pinned_case_ids),
            key=lambda row: (row.issued_observation_tick, row.case_id),
        )
        excess = len(terminal) - max_terminal
        if len(removable) < excess:
            raise _fail("cases", "retention_cap")
        removed = {row.case_id for row in removable[:excess]}
        retained = [row for row in cases if row.case_id not in removed]
    evicted = len(cases) - len(retained)
    floor = min((row.issued_observation_tick for row in retained), default=None)
    return tuple(retained), evicted, floor


def bump_notice(
    notices: tuple[ModelCoverageNotice, ...],
    *,
    reason_code: str,
    target_kind: ModelTargetKind,
    tick: int,
) -> tuple[ModelCoverageNotice, ...]:
    """Aggregate one coverage occurrence, never appending duplicate keys."""

    if reason_code not in _COVERAGE_REASON_CODES:
        raise _fail("reason_code", "unknown_reason")
    if type(target_kind) is not ModelTargetKind:
        raise _fail("target_kind", "invalid_type")
    _require_int("tick", tick)
    for index, notice in enumerate(notices):
        if notice.reason_code == reason_code and notice.target_kind is target_kind:
            updated = replace(
                notice,
                first_tick=min(notice.first_tick, tick),
                last_tick=max(notice.last_tick, tick),
                count=notice.count + 1,
            )
            rows = list(notices)
            rows[index] = updated
            return tuple(rows)
    if len(notices) >= MAX_COVERAGE_NOTICES:
        return notices
    return (
        *notices,
        ModelCoverageNotice(
            reason_code=reason_code,
            target_kind=target_kind,
            first_tick=tick,
            last_tick=tick,
            count=1,
        ),
    )
