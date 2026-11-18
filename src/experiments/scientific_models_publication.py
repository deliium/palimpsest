"""Reference-closed snapshot selection and trusted publication composition."""

from __future__ import annotations

import logging
from dataclasses import replace
from typing import Final

from analysis.scientific_models_analysis import harvest_scientific_models_analysis
from analysis.scientific_models_contract import (
    ObservedModelOutcomeFact,
    PredictiveCoverageFact,
    PriorPredictionFact,
)
from analysis.scientific_models_rows import ScientificModelsAnalysis
from simulation.scientific_models_models import (
    MAX_SCIENTIFIC_MODELS_SECTION_ROWS,
    ScientificCalibrationRow,
    ScientificComparisonRow,
    ScientificCoverageRow,
    ScientificModelRow,
    ScientificModelsSnapshot,
    ScientificOutcomeRow,
    ScientificPredictionRow,
    ScientificRevisionRow,
)

__all__ = ["build_scientific_models_snapshot"]

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.scientific_models_publication"
)


def _fail(code: str) -> ValueError:
    return ValueError(code)


def _select_reference_closed(
    analysis: ScientificModelsAnalysis,
    *,
    max_rows: int,
) -> tuple[ScientificModelsAnalysis, int]:
    """Select whole case bundles in descending issuance order.

    Returns the filtered analysis and the number of omitted cases.
    """

    if max_rows < 1:
        raise _fail("scientific_models_invalid_max_rows")
    outcomes = {row.case_token: row for row in analysis.outcomes}
    models = {row.model_token: row for row in analysis.models}
    revisions = {row.revision_token: row for row in analysis.revisions}
    by_case: dict[tuple[int, str], list[PriorPredictionFact]] = {}
    for prediction in analysis.predictions:
        by_case.setdefault((prediction.issued_tick, prediction.case_token), []).append(
            prediction
        )
    ordered = sorted(by_case, reverse=True)
    selected_cases: set[str] = set()
    selected_predictions: list[PriorPredictionFact] = []
    selected_outcomes: list[ObservedModelOutcomeFact] = []
    selected_models: set[str] = set()
    selected_revisions: set[str] = set()
    omitted = 0
    for key in ordered:
        predictions = by_case[key]
        case_token = key[1]
        outcome = outcomes.get(case_token)
        if len(predictions) != 2 or outcome is None:
            omitted += 1
            continue
        model_tokens = {row.model_token for row in predictions}
        if not model_tokens <= set(models):
            omitted += 1
            continue
        revision_tokens: set[str] = set()
        resolvable = True
        for prediction in predictions:
            if prediction.model_revision_token not in revisions:
                resolvable = False
                break
            revision_tokens.add(prediction.model_revision_token)
        if not resolvable:
            omitted += 1
            continue
        if len(selected_predictions) + 2 > max_rows:
            omitted += 1
            continue
        if len(selected_outcomes) + 1 > max_rows:
            omitted += 1
            continue
        new_models = model_tokens - selected_models
        new_revisions = revision_tokens - selected_revisions
        if (
            len(selected_models) + len(new_models) > max_rows
            or len(selected_revisions) + len(new_revisions) > max_rows
        ):
            omitted += 1
            continue
        selected_cases.add(case_token)
        selected_predictions.extend(predictions)
        selected_outcomes.append(outcome)
        selected_models.update(new_models)
        selected_revisions.update(new_revisions)
    filtered = replace(
        analysis,
        predictions=tuple(selected_predictions),
        outcomes=tuple(selected_outcomes),
        models=tuple(
            row for row in analysis.models if row.model_token in selected_models
        ),
        revisions=tuple(
            row
            for row in analysis.revisions
            if row.revision_token in selected_revisions
        ),
        calibration=(),
        comparisons=(),
    )
    return filtered, omitted


def build_scientific_models_snapshot(
    analysis: object,
    *,
    run_token: str,
    publication_id: str,
    finalized_through_tick: int,
    max_rows: int = MAX_SCIENTIFIC_MODELS_SECTION_ROWS,
) -> ScientificModelsSnapshot:
    """Compose a bounded, reference-closed snapshot from detached facts."""

    if type(analysis) is not ScientificModelsAnalysis:
        raise _fail("scientific_models_invalid_analysis")
    if max_rows < 1 or max_rows > MAX_SCIENTIFIC_MODELS_SECTION_ROWS:
        raise _fail("scientific_models_invalid_max_rows")
    if not analysis.calibration and not analysis.comparisons:
        analysis = harvest_scientific_models_analysis(analysis)
    selected, omitted = _select_reference_closed(analysis, max_rows=max_rows)
    harvested = harvest_scientific_models_analysis(selected)
    coverage = list(harvested.coverage)
    if omitted:
        coverage.append(
            PredictiveCoverageFact(
                reason_code="retention_cap",
                target_kind="all",
                first_tick=0,
                last_tick=finalized_through_tick,
                count=omitted,
            )
        )
    model_rows = []
    revisions_by_model: dict[str, list[str]] = {}
    for row in harvested.revisions:
        if row.kind == "model":
            revisions_by_model.setdefault(row.model_token, []).append(
                row.revision_token
            )
    for model in harvested.models:
        model_rows.append(
            ScientificModelRow(
                owner_token=model.owner_token,
                model_token=model.model_token,
                hypothesis_token=model.hypothesis_token,
                target_kind=next(
                    (
                        hypothesis.target_kind
                        for hypothesis in harvested.hypotheses
                        if hypothesis.hypothesis_token == model.hypothesis_token
                    ),
                    "unknown",
                ),
                unit_token=next(
                    (
                        hypothesis.unit_token
                        for hypothesis in harvested.hypotheses
                        if hypothesis.hypothesis_token == model.hypothesis_token
                    ),
                    "unknown",
                ),
                horizon_ticks=next(
                    (
                        hypothesis.horizon_ticks
                        for hypothesis in harvested.hypotheses
                        if hypothesis.hypothesis_token == model.hypothesis_token
                    ),
                    1,
                ),
                predictor_variant=model.predictor_variant,
                lifecycle=model.lifecycle,
                revision_tokens=tuple(
                    sorted(revisions_by_model.get(model.model_token, ()))
                ),
            )
        )
    prediction_rows = tuple(
        ScientificPredictionRow(
            owner_token=row.owner_token,
            case_token=row.case_token,
            prediction_token=row.prediction_token,
            model_token=row.model_token,
            target_kind=row.target_kind,
            target_token=row.target_token,
            unit_token=row.unit_token,
            context_token=row.context_token,
            horizon_ticks=row.horizon_ticks,
            alphabet=row.alphabet,
            probabilities_milli=row.probabilities_milli,
            predicted_class=row.predicted_class,
            confidence_milli=row.confidence_milli,
            issued_tick=row.issued_tick,
            committed_after_tick=row.committed_after_tick,
            target_observation_tick=row.target_observation_tick,
            receipt_tick=row.receipt_tick,
            window_index=row.issued_tick // 32,
        )
        for row in harvested.predictions
    )
    outcome_rows = tuple(
        ScientificOutcomeRow(
            case_token=row.case_token,
            owner_token=row.owner_token,
            target_kind=row.target_kind,
            target_token=row.target_token,
            unit_token=row.unit_token,
            horizon_ticks=row.horizon_ticks,
            state=row.state,
            settlement_reason=row.settlement_reason,
            observed_class=row.observed_class,
            observed_tick=row.observed_tick,
            outcome_token=row.outcome_token,
        )
        for row in harvested.outcomes
    )
    calibration_rows = tuple(
        ScientificCalibrationRow(
            group_token=row.group_token,
            target_kind=row.target_kind,
            model_token=row.model_token,
            scored_count=row.scored_count,
            brier_numerator_sum=row.brier_numerator_sum,
            mean_brier_millionths=row.mean_brier_millionths,
            calibration_gap_milli=row.calibration_gap_milli,
            insufficient=row.insufficient,
        )
        for row in harvested.calibration
    )
    comparison_rows = tuple(
        ScientificComparisonRow(
            group_token=row.group_token,
            target_kind=row.target_kind,
            model_a_token=row.model_a_token,
            model_b_token=row.model_b_token,
            paired_count=row.paired_count,
            mean_brier_millionths_a=row.mean_brier_millionths_a,
            mean_brier_millionths_b=row.mean_brier_millionths_b,
            a_minus_b_millionths=row.a_minus_b_millionths,
            status=row.status,
        )
        for row in harvested.comparisons
    )
    revision_rows = tuple(
        ScientificRevisionRow(
            owner_token=row.owner_token,
            model_token=row.model_token,
            revision_token=row.revision_token,
            revision_index=row.revision_index,
            tick=row.tick,
            kind=row.kind,
            reason=row.reason,
        )
        for row in harvested.revisions
    )
    coverage_rows = tuple(
        ScientificCoverageRow(
            reason_code=row.reason_code,
            target_kind=row.target_kind,
            first_tick=row.first_tick,
            last_tick=row.last_tick,
            count=row.count,
        )
        for row in coverage
    )
    _LOG.debug(
        "scientific_models_snapshot_built prediction_count=%s omitted_cases=%s",
        len(prediction_rows),
        omitted,
    )
    return ScientificModelsSnapshot(
        schema_version="scientific-models-snapshot-v1",
        policy_version="scientific-models-publication.v1",
        run_token=run_token,
        publication_id=publication_id,
        finalized_through_tick=finalized_through_tick,
        coverage_status=harvested.export_status,
        models=tuple(model_rows),
        predictions=prediction_rows,
        outcomes=outcome_rows,
        calibration=calibration_rows,
        revisions=revision_rows,
        comparisons=comparison_rows,
        coverage=coverage_rows,
        notices=("retention_cap",) if omitted else (),
    )
