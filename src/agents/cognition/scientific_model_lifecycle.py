"""Ordered predictive transition: settle, score, revise, derive, issue, retain.

The transition is pure and owner-local. It never creates, replaces, or submits
an ``AgentCommand`` and never reads global or hidden world state.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import replace
from typing import Final

from agents.cognition.experimentation import ExperimentLedger
from agents.cognition.scientific_model_derivation import derive_model_hypotheses
from agents.cognition.scientific_model_observation import resolve_due_model_cases
from agents.cognition.scientific_model_prediction import issue_model_forecasts
from agents.cognition.scientific_model_scoring import recompute_model_accounting
from agents.cognition.scientific_models import (
    MAX_MODEL_REVISIONS,
    MAX_TERMINAL_CASES,
    ForecastCase,
    ModelRevision,
    ModelRevisionReason,
    PredictiveModel,
    ScientificModelLedger,
    prune_terminal_cases,
    target_alphabet,
)

__all__ = ["advance_scientific_models"]

_LOG: Final[logging.Logger] = logging.getLogger(
    "agents.cognition.scientific_model_lifecycle"
)


def _fail(field_name: str, reason: str) -> ValueError:
    return ValueError(f"{field_name}: {reason}")


def _digest(*parts: str) -> str:
    material = "|".join(parts)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:32]


def _observed_counts(
    cases: tuple[ForecastCase, ...],
    model: PredictiveModel,
    *,
    condition_text: str,
) -> tuple[int, ...]:
    alphabet = target_alphabet(model.target_kind)
    counts = [0] * len(alphabet)
    for case in cases:
        if case.observed is None:
            continue
        if not any(row.model_id == model.model_id for row in case.predictions):
            continue
        if (
            case.target_kind is not model.target_kind
            or case.target_ref != model.target_ref
            or case.unit_token != model.unit_token
            or case.horizon_ticks != model.horizon_ticks
            or "|".join(f"{row.slot}={row.value_token}" for row in case.conditions)
            != condition_text
        ):
            continue
        if case.observed.observed_class in alphabet:
            counts[alphabet.index(case.observed.observed_class)] += 1
    return tuple(counts)


def _refresh_empirical_parameters(
    ledger: ScientificModelLedger,
    *,
    newly_scored: frozenset[str],
    tick: int,
) -> ScientificModelLedger:
    if not newly_scored:
        return ledger
    touched = {
        prediction.model_id
        for case in ledger.cases
        if case.case_id in newly_scored
        for prediction in case.predictions
    }
    rows: list[PredictiveModel] = []
    for model in ledger.models:
        if model.model_id not in touched:
            rows.append(model)
            continue
        condition_text = "|".join(
            f"{row.slot}={row.value_token}" for row in model.current_revision.conditions
        )
        counts = _observed_counts(ledger.cases, model, condition_text=condition_text)
        parameter_digest = "par:" + _digest(
            model.model_id,
            model.predictor_variant.value,
            model.source_revision_ref,
            condition_text,
            ",".join(str(count) for count in counts),
        )
        if model.parameter_digest == parameter_digest:
            rows.append(model)
            continue
        if len(model.revisions) >= MAX_MODEL_REVISIONS:
            rows.append(replace(model, parameter_digest=parameter_digest))
            continue
        revision = ModelRevision(
            revision_index=model.current_revision.revision_index + 1,
            tick=tick,
            reason=ModelRevisionReason.PARAMETER_UPDATED,
            source_revision_ref=model.source_revision_ref,
            parameter_digest=parameter_digest,
            conditions=model.current_revision.conditions,
            predicted_class=model.current_revision.predicted_class,
        )
        rows.append(
            replace(
                model,
                parameter_digest=parameter_digest,
                revisions=(*model.revisions, revision),
            )
        )
    return replace(ledger, models=tuple(rows))


def _retain(
    ledger: ScientificModelLedger,
) -> ScientificModelLedger:
    pending_ids = frozenset(row.case_id for row in ledger.pending_cases)
    kept, evicted, floor = prune_terminal_cases(
        ledger.cases,
        pinned_case_ids=pending_ids,
        max_terminal=MAX_TERMINAL_CASES,
    )
    if evicted == 0:
        return ledger
    return replace(
        ledger,
        cases=kept,
        evicted_cases=ledger.evicted_cases + evicted,
        first_retained_tick=(
            floor if floor is not None else ledger.first_retained_tick
        ),
    )


def advance_scientific_models(
    ledger: ScientificModelLedger,
    observation: object,
    *,
    experiment_ledger: ExperimentLedger,
    causal_world_model: object | None = None,
) -> ScientificModelLedger:
    """Apply the ordered predictive transition for one owner observation."""

    if type(ledger) is not ScientificModelLedger:
        raise _fail("ledger", "invalid_type")
    if type(experiment_ledger) is not ExperimentLedger:
        raise _fail("experiment_ledger", "invalid_type")
    if experiment_ledger.owner_id != ledger.owner_id:
        raise _fail("experiment_ledger", "owner_mismatch")
    # The trusted loop supplies only this owner's detached observation.
    tick = getattr(observation, "tick", None)
    if isinstance(tick, bool) or type(tick) is not int or tick < 0:
        raise _fail("observation", "invalid_tick")

    pending_before = {row.case_id for row in ledger.pending_cases}
    settled = resolve_due_model_cases(ledger, observation)
    newly_scored = frozenset(
        row.case_id
        for row in settled.cases
        if row.case_id in pending_before
        and row.observed is not None
        and row.observed.observed_tick == row.target_observation_tick
    )
    revised = _refresh_empirical_parameters(
        settled, newly_scored=newly_scored, tick=tick
    )
    accounted = recompute_model_accounting(revised, evaluated_tick=tick)
    derived = derive_model_hypotheses(
        accounted,
        observation,
        experiment_ledger=experiment_ledger,
        causal_world_model=causal_world_model,
    )
    issued = issue_model_forecasts(derived, observation)
    retained = _retain(issued)
    _LOG.debug(
        "scientific_model_transition owner_id=%s tick=%s newly_scored=%s "
        "case_count=%s pending_count=%s model_count=%s",
        ledger.owner_id.value,
        tick,
        len(newly_scored),
        len(retained.cases),
        len(retained.pending_cases),
        len(retained.models),
    )
    return retained
