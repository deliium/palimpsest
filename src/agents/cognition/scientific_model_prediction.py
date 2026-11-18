"""Immutable prior forecasts with deterministic predictive distributions.

Forecasts are frozen before the observation they predict. The two candidate
distributions are subjective estimates derived from an owner's model hypothesis
and past resolved cases; source support ratios are never used as probabilities.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import replace
from typing import Final

from agents.cognition.scientific_models import (
    MAX_MODEL_REVISIONS,
    MAX_MODELS,
    MAX_PENDING_CASES,
    ForecastCase,
    ModelCondition,
    ModelHypothesis,
    ModelLifecycle,
    ModelPrediction,
    ModelPredictorVariant,
    ModelRevision,
    ModelRevisionReason,
    ModelTargetKind,
    PredictiveModel,
    ScientificModelLedger,
    bump_notice,
    scientific_case_id,
    scientific_model_id,
    scientific_prediction_id,
    target_alphabet,
)

__all__ = [
    "BASELINE_CLAIM_WEIGHT",
    "BASELINE_OTHER_WEIGHT",
    "baseline_distribution",
    "empirical_distribution",
    "issue_model_forecasts",
    "largest_remainder",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "agents.cognition.scientific_model_prediction"
)

BASELINE_CLAIM_WEIGHT: Final[int] = 2
BASELINE_OTHER_WEIGHT: Final[int] = 1


def _digest(*parts: str) -> str:
    material = "|".join(parts)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:32]


def _fail(field_name: str, reason: str) -> ValueError:
    return ValueError(f"{field_name}: {reason}")


def largest_remainder(
    weights: tuple[int, ...], *, total: int = 1000
) -> tuple[int, ...]:
    """Allocate ``total`` integer units by largest remainder, ties by index."""

    if not weights:
        raise _fail("weights", "empty")
    for weight in weights:
        if isinstance(weight, bool) or type(weight) is not int or weight < 0:
            raise _fail("weights", "invalid_weight")
    grand = sum(weights)
    if grand == 0:
        base = [total // len(weights)] * len(weights)
        for index in range(total - sum(base)):
            base[index] += 1
        return tuple(base)
    base = [weight * total // grand for weight in weights]
    remaining = total - sum(base)
    order = sorted(
        range(len(weights)),
        key=lambda index: (-(weights[index] * total % grand), index),
    )
    for index in order[:remaining]:
        base[index] += 1
    return tuple(base)


def baseline_distribution(
    alphabet: tuple[str, ...], predicted_class: str
) -> tuple[int, ...]:
    """Weight the source claim twice every other class, then normalize."""

    if predicted_class not in alphabet:
        raise _fail("predicted_class", "invalid_class")
    weights = tuple(
        BASELINE_CLAIM_WEIGHT if name == predicted_class else BASELINE_OTHER_WEIGHT
        for name in alphabet
    )
    return largest_remainder(weights)


def empirical_distribution(
    alphabet: tuple[str, ...], counts: tuple[int, ...]
) -> tuple[int, ...]:
    """Laplace-smoothed exact-context counts; no samples yield uniform."""

    if len(counts) != len(alphabet):
        raise _fail("counts", "invalid_alphabet")
    for count in counts:
        if isinstance(count, bool) or type(count) is not int or count < 0:
            raise _fail("counts", "invalid_count")
    return largest_remainder(tuple(count + 1 for count in counts))


def _conditions_satisfied(
    conditions: tuple[ModelCondition, ...], observation: object
) -> bool:
    current: dict[str, str] = {}
    for name in ("season", "weather_condition", "day_phase"):
        value = getattr(observation, name, None)
        if value is not None:
            token = getattr(value, "value", value)
            if isinstance(token, str):
                current[name] = token
    self_body = getattr(observation, "self_body", None)
    location_id = getattr(self_body, "location_id", None)
    if location_id is not None:
        current["location"] = str(getattr(location_id, "value", location_id))
    for condition in conditions:
        if current.get(condition.slot) != condition.value_token:
            return False
    return True


def _condition_text(conditions: tuple[ModelCondition, ...]) -> str:
    return "|".join(f"{row.slot}={row.value_token}" for row in conditions)


def _context_digest(hypothesis: ModelHypothesis) -> str:
    return "ctx:" + _digest(
        hypothesis.target_kind.value,
        hypothesis.target_ref,
        hypothesis.unit_token,
        str(hypothesis.horizon_ticks),
        _condition_text(hypothesis.current_revision.conditions),
    )


def _parameter_digest(
    model_id: str,
    variant: ModelPredictorVariant,
    hypothesis: ModelHypothesis,
    context_digest: str,
) -> str:
    return "par:" + _digest(
        model_id,
        variant.value,
        hypothesis.revision_ref,
        context_digest,
    )


def _new_model(
    ledger: ScientificModelLedger,
    hypothesis: ModelHypothesis,
    variant: ModelPredictorVariant,
    *,
    tick: int,
    context_digest: str,
) -> PredictiveModel:
    current = hypothesis.current_revision
    assert current.predicted_class is not None
    model_id = scientific_model_id(
        ledger.owner_id,
        hypothesis.hypothesis_id,
        variant,
        hypothesis.target_ref,
        hypothesis.unit_token,
        hypothesis.horizon_ticks,
    )
    parameter_digest = _parameter_digest(model_id, variant, hypothesis, context_digest)
    return PredictiveModel(
        owner_id=ledger.owner_id,
        model_id=model_id,
        hypothesis_id=hypothesis.hypothesis_id,
        target_kind=hypothesis.target_kind,
        target_ref=hypothesis.target_ref,
        unit_token=hypothesis.unit_token,
        horizon_ticks=hypothesis.horizon_ticks,
        predictor_variant=variant,
        source_revision_ref=hypothesis.revision_ref,
        parameter_digest=parameter_digest,
        lifecycle=ModelLifecycle.ACTIVE,
        revisions=(
            ModelRevision(
                revision_index=0,
                tick=tick,
                reason=ModelRevisionReason.FORMULATED,
                source_revision_ref=hypothesis.revision_ref,
                parameter_digest=parameter_digest,
                conditions=current.conditions,
                predicted_class=current.predicted_class,
            ),
        ),
        created_tick=tick,
        sequence=ledger.model_sequence,
    )


def _refresh_model(
    model: PredictiveModel,
    hypothesis: ModelHypothesis,
    *,
    tick: int,
    context_digest: str,
) -> PredictiveModel:
    if model.source_revision_ref == hypothesis.revision_ref:
        return model
    current = hypothesis.current_revision
    assert current.predicted_class is not None
    latest = model.current_revision
    parameter_digest = _parameter_digest(
        model.model_id, model.predictor_variant, hypothesis, context_digest
    )
    if len(model.revisions) >= MAX_MODEL_REVISIONS:
        revision_rows = model.revisions
    else:
        revision_rows = (
            *model.revisions,
            ModelRevision(
                revision_index=latest.revision_index + 1,
                tick=tick,
                reason=ModelRevisionReason.SOURCE_CHANGED,
                source_revision_ref=hypothesis.revision_ref,
                parameter_digest=parameter_digest,
                conditions=current.conditions,
                predicted_class=current.predicted_class,
            ),
        )
    return replace(
        model,
        source_revision_ref=hypothesis.revision_ref,
        parameter_digest=parameter_digest,
        lifecycle=ModelLifecycle.ACTIVE,
        revisions=revision_rows,
    )


def _ensure_models(
    ledger: ScientificModelLedger,
    hypothesis: ModelHypothesis,
    *,
    tick: int,
    context_digest: str,
) -> tuple[ScientificModelLedger, tuple[PredictiveModel, PredictiveModel]] | None:
    rows = list(ledger.models)
    selected: list[PredictiveModel] = []
    sequence = ledger.model_sequence
    for variant in (
        ModelPredictorVariant.HYPOTHESIS_BASELINE_V1,
        ModelPredictorVariant.EMPIRICAL_CONTEXT_V1,
    ):
        model_id = scientific_model_id(
            ledger.owner_id,
            hypothesis.hypothesis_id,
            variant,
            hypothesis.target_ref,
            hypothesis.unit_token,
            hypothesis.horizon_ticks,
        )
        position = next(
            (index for index, row in enumerate(rows) if row.model_id == model_id),
            None,
        )
        if position is None:
            if len(rows) >= MAX_MODELS:
                return None
            model = _new_model(
                replace(ledger, model_sequence=sequence),
                hypothesis,
                variant,
                tick=tick,
                context_digest=context_digest,
            )
            rows.append(model)
            sequence += 1
        else:
            model = _refresh_model(
                rows[position],
                hypothesis,
                tick=tick,
                context_digest=context_digest,
            )
            rows[position] = model
        selected.append(model)
    updated = replace(
        ledger,
        models=tuple(rows),
        model_sequence=sequence,
        sequence=ledger.sequence + 1,
    )
    return updated, (selected[0], selected[1])


def _empirical_counts(
    ledger: ScientificModelLedger,
    model: PredictiveModel,
    *,
    context_digest: str,
) -> tuple[int, ...]:
    alphabet = target_alphabet(model.target_kind)
    counts = [0] * len(alphabet)
    for case in ledger.cases:
        if case.observed is None:
            continue
        if not any(
            prediction.model_id == model.model_id for prediction in case.predictions
        ):
            continue
        if case.target_kind is not model.target_kind:
            continue
        if case.target_ref != model.target_ref or case.unit_token != model.unit_token:
            continue
        if case.horizon_ticks != model.horizon_ticks:
            continue
        case_context = "ctx:" + _digest(
            case.target_kind.value,
            case.target_ref,
            case.unit_token,
            str(case.horizon_ticks),
            _condition_text(case.conditions),
        )
        if case_context != context_digest:
            continue
        if case.observed.observed_class not in alphabet:
            continue
        counts[alphabet.index(case.observed.observed_class)] += 1
    return tuple(counts)


def _prediction_for(
    ledger: ScientificModelLedger,
    model: PredictiveModel,
    hypothesis: ModelHypothesis,
    *,
    case_id: str,
    context_digest: str,
) -> ModelPrediction:
    alphabet = target_alphabet(hypothesis.target_kind)
    current = hypothesis.current_revision
    assert current.predicted_class is not None
    if model.predictor_variant is ModelPredictorVariant.HYPOTHESIS_BASELINE_V1:
        probabilities = baseline_distribution(alphabet, current.predicted_class)
    else:
        probabilities = empirical_distribution(
            alphabet,
            _empirical_counts(ledger, model, context_digest=context_digest),
        )
    predicted = alphabet[
        max(
            range(len(probabilities)),
            key=lambda index: (probabilities[index], -index),
        )
    ]
    return ModelPrediction(
        prediction_id=scientific_prediction_id(case_id, model.predictor_variant),
        model_id=model.model_id,
        hypothesis_id=hypothesis.hypothesis_id,
        predictor_variant=model.predictor_variant,
        alphabet=alphabet,
        probabilities_milli=probabilities,
        predicted_class=predicted,
        confidence_milli=probabilities[alphabet.index(predicted)],
        model_revision_ref=(
            f"{model.model_id}#{model.current_revision.revision_index}"
        ),
        source_revision_ref=hypothesis.revision_ref,
        parameter_digest=model.parameter_digest,
    )


def issue_model_forecasts(
    ledger: ScientificModelLedger, observation: object
) -> ScientificModelLedger:
    """Issue at most one shared two-candidate case for this owner and tick."""

    if type(ledger) is not ScientificModelLedger:
        raise _fail("ledger", "invalid_type")
    # The trusted loop supplies only this owner's detached observation.
    tick = getattr(observation, "tick", None)
    if isinstance(tick, bool) or type(tick) is not int or tick < 0:
        raise _fail("observation", "invalid_tick")
    if ledger.last_issued_tick >= 0 and tick <= ledger.last_issued_tick:
        _LOG.debug(
            "forecast_suppressed owner_id=%s tick=%s reason=same_or_older_tick",
            ledger.owner_id.value,
            tick,
        )
        return ledger
    observation_key = f"tick:{tick}"
    if observation_key in ledger.issued_observation_keys:
        return ledger

    eligible = sorted(
        (
            hypothesis
            for hypothesis in ledger.hypotheses
            if hypothesis.lifecycle is ModelLifecycle.ACTIVE
            and _conditions_satisfied(
                hypothesis.current_revision.conditions, observation
            )
        ),
        key=lambda row: row.hypothesis_id,
    )
    if not eligible:
        return replace(ledger, last_issued_tick=tick)
    if len(ledger.pending_cases) >= MAX_PENDING_CASES:
        return replace(
            ledger,
            last_issued_tick=tick,
            notices=bump_notice(
                ledger.notices,
                reason_code="pending_cap",
                target_kind=eligible[0].target_kind,
                tick=tick,
            ),
        )
    index = ledger.cursor % len(eligible)
    hypothesis = eligible[index]
    context_digest = _context_digest(hypothesis)
    prepared = _ensure_models(
        ledger, hypothesis, tick=tick, context_digest=context_digest
    )
    if prepared is None:
        return replace(
            ledger,
            last_issued_tick=tick,
            notices=bump_notice(
                ledger.notices,
                reason_code="model_cap",
                target_kind=hypothesis.target_kind,
                tick=tick,
            ),
        )
    updated, models = prepared
    case_id = scientific_case_id(ledger.owner_id, observation_key)
    if any(case.case_id == case_id for case in ledger.cases):
        return ledger
    reference_quantity: int | None = None
    reference_kind: str | None = None
    if hypothesis.target_kind is ModelTargetKind.RESOURCE_REGENERATION:
        samples = [
            row
            for row in ledger.samples
            if row.target_kind is ModelTargetKind.RESOURCE_REGENERATION
            and row.quantity_milli is not None
            and f"{row.target_ref}:{row.location_ref}" == hypothesis.target_ref
            and row.observed_tick <= tick
        ]
        if not samples:
            return replace(ledger, last_issued_tick=tick)
        latest = max(
            samples, key=lambda row: (row.observed_tick, row.sample_id)
        )
        reference_quantity = latest.quantity_milli
        reference_kind = latest.kind_token or None
    predictions = tuple(
        _prediction_for(
            updated,
            model,
            hypothesis,
            case_id=case_id,
            context_digest=context_digest,
        )
        for model in models
    )
    case = ForecastCase(
        case_id=case_id,
        owner_id=ledger.owner_id,
        target_kind=hypothesis.target_kind,
        target_ref=hypothesis.target_ref,
        unit_token=hypothesis.unit_token,
        horizon_ticks=hypothesis.horizon_ticks,
        alphabet=target_alphabet(hypothesis.target_kind),
        conditions=hypothesis.current_revision.conditions,
        predictions=predictions,
        issued_observation_tick=tick,
        issued_observation_key=observation_key,
        committed_after_tick=tick,
        target_observation_tick=tick + hypothesis.horizon_ticks,
        training_high_water_tick=max(0, tick - 1),
        source_claim=hypothesis.source_claim,
        reference_quantity_milli=reference_quantity,
        reference_resource_kind=reference_kind,
    )
    updated = replace(
        updated,
        cases=(*updated.cases, case),
        issued_observation_keys=(
            *updated.issued_observation_keys,
            observation_key,
        ),
        cursor=(index + 1) % len(eligible),
        last_issued_tick=tick,
        case_sequence=updated.case_sequence + 1,
    )
    _LOG.debug(
        "forecast_issued owner_id=%s tick=%s target_kind=%s horizon_ticks=%s",
        ledger.owner_id.value,
        tick,
        hypothesis.target_kind.value,
        hypothesis.horizon_ticks,
    )
    return updated
