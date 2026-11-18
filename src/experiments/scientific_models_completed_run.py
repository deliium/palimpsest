"""Trusted completed-run bridge from frozen owner ledgers to detached facts."""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Sequence
from typing import Any, Final

from analysis.scientific_models_contract import (
    MAX_PREDICTIVE_ROWS,
    ModelHypothesisFact,
    ObservedModelOutcomeFact,
    PredictiveCoverageFact,
    PredictiveModelFact,
    PredictiveRevisionFact,
    PriorPredictionFact,
)
from analysis.scientific_models_rows import ScientificModelsAnalysis

__all__ = [
    "build_completed_run_scientific_models_analysis",
    "scientific_model_facts",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.scientific_models_completed_run"
)

_COVERAGE_REASONS: Final[frozenset[str]] = frozenset(
    {
        "retention_cap",
        "partial_owner_export",
        "outcome_missing",
        "condition_unknown",
        "not_comparable",
        "unavailable_no_observable",
    }
)


def _token(run_token: str, kind: str, raw: str) -> str:
    digest = hashlib.sha256(f"{run_token}|{kind}|{raw}".encode()).hexdigest()
    return digest[:32]


def _condition_text(conditions: Sequence[object]) -> str:
    return "|".join(
        f"{getattr(row, 'slot', '')}={getattr(row, 'value_token', '')}"
        for row in conditions
    )


def _add(destination: dict[str, Any], token: str, value: Any) -> None:
    existing = destination.get(token)
    if existing is not None and existing != value:
        raise ValueError("scientific_model_facts_conflict")
    destination[token] = value


def scientific_model_facts(
    result: object,
    *,
    run_token: str,
    expected_owner_count: int | None = None,
) -> ScientificModelsAnalysis:
    """Read only the completed result's validated owner ledgers."""

    if type(run_token) is not str or not run_token:
        raise ValueError("run_token: invalid")
    ledgers = getattr(result, "scientific_model_ledgers", None)
    if ledgers is None or isinstance(ledgers, (str, bytes)):
        raise ValueError("result: missing_scientific_model_ledgers")
    if not isinstance(ledgers, tuple):
        raise ValueError("result: invalid_scientific_model_ledgers")
    expected = len(ledgers) if expected_owner_count is None else expected_owner_count
    if isinstance(expected, bool) or type(expected) is not int or expected < 0:
        raise ValueError("expected_owner_count: invalid")

    hypotheses: dict[str, ModelHypothesisFact] = {}
    models: dict[str, PredictiveModelFact] = {}
    predictions: dict[str, PriorPredictionFact] = {}
    outcomes: dict[str, ObservedModelOutcomeFact] = {}
    revisions: dict[str, PredictiveRevisionFact] = {}
    coverage: dict[tuple[str, str], PredictiveCoverageFact] = {}
    seen_owners: set[str] = set()

    for ledger in ledgers:
        owner_token = _token(run_token, "owner", ledger.owner_id.value)
        if owner_token in seen_owners:
            raise ValueError("scientific_model_facts_conflict")
        seen_owners.add(owner_token)
        hypothesis_tokens = {
            row.hypothesis_id: _token(run_token, "hypothesis", row.hypothesis_id)
            for row in ledger.hypotheses
        }
        model_tokens = {
            row.model_id: _token(run_token, "model", row.model_id)
            for row in ledger.models
        }
        for hypothesis in ledger.hypotheses:
            _add(
                hypotheses,
                hypothesis_tokens[hypothesis.hypothesis_id],
                ModelHypothesisFact(
                    hypothesis_token=hypothesis_tokens[hypothesis.hypothesis_id],
                    owner_token=owner_token,
                    target_kind=hypothesis.target_kind.value,
                    unit_token=_token(run_token, "unit", hypothesis.unit_token),
                    horizon_ticks=hypothesis.horizon_ticks,
                    source_kind=hypothesis.source_kind.value,
                    lifecycle=hypothesis.lifecycle.value,
                    revision_count=len(hypothesis.revisions),
                ),
            )
            for revision in hypothesis.revisions:
                revision_token = _token(
                    run_token,
                    "hyprev",
                    f"{hypothesis.hypothesis_id}#{revision.revision_index}",
                )
                _add(
                    revisions,
                    revision_token,
                    PredictiveRevisionFact(
                        owner_token=owner_token,
                        model_token=hypothesis_tokens[hypothesis.hypothesis_id],
                        revision_token=revision_token,
                        revision_index=revision.revision_index,
                        tick=revision.tick,
                        kind="hypothesis",
                        reason=revision.reason.value,
                    ),
                )
        for model in ledger.models:
            model_token = model_tokens[model.model_id]
            source_token = _token(
                run_token,
                "hyprev",
                f"{model.hypothesis_id}#{model.source_revision_ref.rsplit('#', 1)[-1]}",
            )
            context_token = _token(
                run_token,
                "context",
                "|".join(
                    (
                        model.target_kind.value,
                        model.target_ref,
                        model.unit_token,
                        str(model.horizon_ticks),
                        _condition_text(model.current_revision.conditions),
                    )
                ),
            )
            _add(
                models,
                model_token,
                PredictiveModelFact(
                    model_token=model_token,
                    hypothesis_token=hypothesis_tokens[model.hypothesis_id],
                    owner_token=owner_token,
                    predictor_variant=model.predictor_variant.value,
                    lifecycle=model.lifecycle.value,
                    revision_count=len(model.revisions),
                    source_revision_token=source_token,
                    context_token=context_token,
                ),
            )
            for revision in model.revisions:
                revision_token = _token(
                    run_token,
                    "modrev",
                    f"{model.model_id}#{revision.revision_index}",
                )
                _add(
                    revisions,
                    revision_token,
                    PredictiveRevisionFact(
                        owner_token=owner_token,
                        model_token=model_token,
                        revision_token=revision_token,
                        revision_index=revision.revision_index,
                        tick=revision.tick,
                        kind="model",
                        reason=revision.reason.value,
                    ),
                )
        for case in ledger.cases:
            case_token = _token(run_token, "case", case.case_id)
            target_token = _token(run_token, "target", case.target_ref)
            unit_token = _token(run_token, "unit", case.unit_token)
            context_token = _token(
                run_token,
                "context",
                "|".join(
                    (
                        case.target_kind.value,
                        case.target_ref,
                        case.unit_token,
                        str(case.horizon_ticks),
                        _condition_text(case.conditions),
                    )
                ),
            )
            for prediction in case.predictions:
                prediction_token = _token(
                    run_token, "prediction", prediction.prediction_id
                )
                source_token = _token(
                    run_token,
                    "hyprev",
                    prediction.source_revision_ref,
                )
                model_revision_token = _token(
                    run_token, "modrev", prediction.model_revision_ref
                )
                _add(
                    predictions,
                    prediction_token,
                    PriorPredictionFact(
                        prediction_token=prediction_token,
                        case_token=case_token,
                        model_token=model_tokens[prediction.model_id],
                        owner_token=owner_token,
                        target_kind=case.target_kind.value,
                        target_token=target_token,
                        unit_token=unit_token,
                        context_token=context_token,
                        horizon_ticks=case.horizon_ticks,
                        alphabet=prediction.alphabet,
                        probabilities_milli=prediction.probabilities_milli,
                        predicted_class=prediction.predicted_class,
                        confidence_milli=prediction.confidence_milli,
                        issued_tick=case.issued_observation_tick,
                        committed_after_tick=case.committed_after_tick,
                        target_observation_tick=case.target_observation_tick,
                        training_high_water_tick=case.training_high_water_tick,
                        source_revision_token=source_token,
                        model_revision_token=model_revision_token,
                        receipt_tick=case.issued_observation_tick,
                        channel="observation",
                    ),
                )
            outcome_token = (
                None
                if case.observed is None
                else _token(run_token, "outcome", case.observed.outcome_ref)
            )
            _add(
                outcomes,
                case_token,
                ObservedModelOutcomeFact(
                    case_token=case_token,
                    owner_token=owner_token,
                    target_kind=case.target_kind.value,
                    target_token=target_token,
                    unit_token=unit_token,
                    horizon_ticks=case.horizon_ticks,
                    state="scored" if case.observed is not None else case.state.value,
                    settlement_reason=case.settlement_reason or case.state.value,
                    observed_class=(
                        None if case.observed is None else case.observed.observed_class
                    ),
                    observed_tick=(
                        None if case.observed is None else case.observed.observed_tick
                    ),
                    outcome_token=outcome_token,
                    start_milli=case.outcome_start_milli,
                    end_milli=case.outcome_end_milli,
                ),
            )
        for notice in ledger.notices:
            if notice.reason_code not in _COVERAGE_REASONS:
                continue
            key = (notice.reason_code, notice.target_kind.value)
            existing = coverage.get(key)
            if existing is None:
                coverage[key] = PredictiveCoverageFact(
                    reason_code=notice.reason_code,
                    target_kind=notice.target_kind.value,
                    first_tick=notice.first_tick,
                    last_tick=notice.last_tick,
                    count=notice.count,
                )
            else:
                coverage[key] = PredictiveCoverageFact(
                    reason_code=existing.reason_code,
                    target_kind=existing.target_kind,
                    first_tick=min(existing.first_tick, notice.first_tick),
                    last_tick=max(existing.last_tick, notice.last_tick),
                    count=existing.count + notice.count,
                )

    status = (
        "absent"
        if expected == 0 and not ledgers
        else ("complete" if len(ledgers) >= expected else "partial")
    )
    if status == "partial":
        coverage[("partial_owner_export", "all")] = PredictiveCoverageFact(
            reason_code="partial_owner_export",
            target_kind="all",
            first_tick=0,
            last_tick=0,
            count=1,
        )
    if len(predictions) > MAX_PREDICTIVE_ROWS:
        keep = sorted(predictions)[:MAX_PREDICTIVE_ROWS]
        predictions = {token: predictions[token] for token in keep}
        coverage[("retention_cap", "all")] = PredictiveCoverageFact(
            reason_code="retention_cap",
            target_kind="all",
            first_tick=0,
            last_tick=0,
            count=1,
        )
    analysis = ScientificModelsAnalysis(
        version="scientific-models-analysis-v1",
        export_status=status,
        owner_count=len(seen_owners),
        expected_owner_count=expected,
        hypotheses=tuple(
            sorted(hypotheses.values(), key=lambda row: row.hypothesis_token)
        ),
        models=tuple(sorted(models.values(), key=lambda row: row.model_token)),
        predictions=tuple(
            sorted(predictions.values(), key=lambda row: row.prediction_token)
        ),
        outcomes=tuple(sorted(outcomes.values(), key=lambda row: row.case_token)),
        revisions=tuple(
            sorted(
                revisions.values(),
                key=lambda row: (
                    row.owner_token,
                    row.model_token,
                    row.kind,
                    row.revision_index,
                ),
            )
        ),
        coverage=tuple(
            sorted(
                coverage.values(), key=lambda row: (row.reason_code, row.target_kind)
            )
        ),
    )
    _LOG.debug(
        "scientific_model_facts status=%s owner_count=%s prediction_count=%s",
        status,
        analysis.owner_count,
        len(analysis.predictions),
    )
    return analysis


def build_completed_run_scientific_models_analysis(
    result: object,
    *,
    run_token: str,
    expected_owner_count: int | None = None,
) -> ScientificModelsAnalysis:
    """Neutral completed-run builder used by the trusted experiment layer."""

    return scientific_model_facts(
        result,
        run_token=run_token,
        expected_owner_count=expected_owner_count,
    )
