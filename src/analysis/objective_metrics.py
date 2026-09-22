"""Objective outcome metrics from immutable events and detached receipts.

Implements Task 11 families: resource inequality, cooperation, conflict,
survival, goal completion, plus shared ActionResolution rates.
Missing evidence is ``unknown`` — never silent zero/false.
"""

from __future__ import annotations

import logging
import math
import time
from collections.abc import Mapping, Sequence
from typing import Final

import numpy as np
import pandas as pd

from analysis.evidence import EvidenceStage
from analysis.models import (
    ACTION_RESOLUTION_RATES_FAMILY,
    METRIC_DOCUMENT_SCHEMA_VERSION,
    ActionResolutionRow,
    AppliedActionRow,
    GoalTransitionRow,
    MetricAvailability,
    MetricCoverage,
    MetricDocument,
    MetricProvenance,
    ResourceHoldingRow,
    SurvivalAgentRow,
)
from analysis.numerical import (
    NumericalPolicyError,
    library_versions,
    quantize_float,
    require_finite,
)
from analysis.specifications import (
    ACTION_VOCABULARY_V1,
    CONFLICT_ACTION_KINDS,
    COOPERATION_ACTION_KINDS,
    MetricFamilyId,
    ResourceMeasureId,
    action_resolution_rate_spec,
    metric_specification,
)
from world.events import WorldEvent
from world.identifiers import require_exact_nonneg_int, require_stable_id

__all__ = [
    "ACTION_RESOLUTION_RATES_FAMILY",
    "applied_actions_from_world_events",
    "compute_action_resolution_rates",
    "compute_conflict",
    "compute_cooperation",
    "compute_goal_completion",
    "compute_resource_inequality",
    "compute_survival",
    "living_agent_ticks",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.objective_metrics")

_APPLIED_STATUS: Final[str] = "applied"
_CONFLICTED_STATUS: Final[str] = "conflicted"
_REJECTED_STATUSES: Final[frozenset[str]] = frozenset(
    {"rejected", "dead_actor", "duplicate", "deferred_policy"}
)
_GOAL_COMPLETED: Final[str] = "completed"
_GOAL_ABANDONED: Final[str] = "abandoned"
_GOAL_DEATH: Final[str] = "death"
_GOAL_RUN_END: Final[str] = "run_end"
_VOCAB: Final[frozenset[str]] = frozenset(ACTION_VOCABULARY_V1)


def living_agent_ticks(
    agent_ids: Sequence[str],
    *,
    window_start: int,
    window_end: int,
    death_ticks: Mapping[str, int],
) -> int:
    """Sum inclusive alive agent-ticks; exclude ticks strictly after death."""
    window_start = require_exact_nonneg_int("window_start", window_start)
    window_end = require_exact_nonneg_int("window_end", window_end)
    if window_end < window_start:
        raise ValueError("window_end_before_start")
    total = 0
    for agent_id in sorted(agent_ids):
        require_stable_id("agent_id", agent_id)
        death = death_ticks.get(agent_id)
        for tick in range(window_start, window_end + 1):
            if death is not None and tick > death:
                continue
            total += 1
    return total


def applied_actions_from_world_events(
    events: Sequence[WorldEvent],
    *,
    entity_to_agent: Mapping[str, str] | None = None,
) -> tuple[AppliedActionRow, ...]:
    """Project vocabulary-kind WorldEvents into sorted AppliedActionRow values.

    Environmental / non-vocabulary details are dropped. ``entity_to_agent`` maps
    actor entity IDs to registered agent IDs when they differ.
    """
    mapping = dict(entity_to_agent or {})
    rows: list[AppliedActionRow] = []
    for event in events:
        kind = getattr(event.details, "kind", None)
        if not isinstance(kind, str) or kind not in _VOCAB:
            continue
        if event.actor_id is None:
            continue
        actor_raw = event.actor_id.value
        agent_id = mapping.get(actor_raw, actor_raw)
        target_id: str | None = None
        if event.target_id is not None:
            target_raw = event.target_id.value
            target_id = mapping.get(target_raw, target_raw)
        location_id: str | None = None
        occurrence = event.occurrence
        if occurrence is not None and occurrence.origin_location_id is not None:
            location_id = occurrence.origin_location_id.value
        rows.append(
            AppliedActionRow(
                tick=event.tick,
                ordinal=event.sequence,
                agent_id=agent_id,
                action_kind=kind,
                location_id=location_id,
                target_id=target_id,
            )
        )
    rows.sort(key=lambda row: (row.tick, row.ordinal, row.agent_id, row.action_kind))
    return tuple(rows)


def _document(
    *,
    family: str,
    algorithm_version: str,
    run_id: str,
    input_revision: str,
    evidence_stages: frozenset[EvidenceStage],
    population: str,
    denominator: str,
    availability: MetricAvailability,
    values: Mapping[str, object],
    coverage: MetricCoverage | None,
    notes_code: str,
    source_ids: tuple[str, ...] = (),
) -> MetricDocument:
    return MetricDocument(
        schema_version=METRIC_DOCUMENT_SCHEMA_VERSION,
        metric_family=family,
        algorithm_version=algorithm_version,
        library_versions=library_versions(),
        run_id=run_id,
        input_revision=input_revision,
        evidence_stages=evidence_stages,
        population=population,
        denominator=denominator,
        coverage=coverage,
        availability=availability,
        values=dict(values),
        provenance=MetricProvenance(
            source_kind="objective_metrics",
            source_ids=source_ids,
            notes_code=notes_code,
        ),
    )


def _q(value: float) -> float:
    return quantize_float(require_finite(float(value)))


def _gini(values: np.ndarray) -> float:
    n = int(values.size)
    if n == 0:
        raise NumericalPolicyError("empty_gini")
    if n == 1:
        return 0.0
    ordered = np.sort(values.astype(np.float64, copy=False))
    total = float(ordered.sum())
    if total == 0.0:
        return 0.0
    index = np.arange(1, n + 1, dtype=np.float64)
    numerator = 2.0 * float(np.dot(index, ordered)) - (n + 1) * total
    return numerator / (n * total)


def _theil_t(values: np.ndarray) -> float:
    n = int(values.size)
    if n == 0:
        raise NumericalPolicyError("empty_theil")
    if n == 1:
        return 0.0
    total = float(values.sum())
    mu = total / float(n)
    if mu == 0.0:
        return 0.0
    contrib = 0.0
    for raw in values:
        x = float(raw)
        if x <= 0.0:
            continue
        ratio = x / mu
        contrib += ratio * math.log(ratio)
    return contrib / float(n)


def _atkinson_eps_1(values: np.ndarray) -> float:
    n = int(values.size)
    if n == 0:
        raise NumericalPolicyError("empty_atkinson")
    if n == 1:
        return 0.0
    if float(np.min(values)) <= 0.0:
        return 1.0
    mu = float(values.mean())
    if mu == 0.0:
        return 1.0
    geo = math.exp(float(np.mean(np.log(values.astype(np.float64)))))
    return 1.0 - (geo / mu)


def compute_resource_inequality(
    holdings: Sequence[ResourceHoldingRow],
    *,
    run_id: str,
    input_revision: str,
    measure_id: ResourceMeasureId | str = ResourceMeasureId.INVENTORY_COUNT,
) -> MetricDocument:
    """Distributional inequality over one named resource measure."""
    started = time.perf_counter()
    spec = metric_specification(MetricFamilyId.RESOURCE_INEQUALITY)
    run_id = require_stable_id("run_id", run_id)
    input_revision = require_stable_id("input_revision", input_revision)
    if type(measure_id) is ResourceMeasureId:
        measure_value = measure_id.value
    else:
        measure_value = require_stable_id("measure_id", measure_id)
        try:
            ResourceMeasureId(measure_value)
        except ValueError:
            _LOG.error(
                "resource_inequality_invalid_measure",
                extra={
                    "metric_family": spec.family_id.value,
                    "algorithm_version": spec.algorithm_version,
                    "code": "invalid_measure_id",
                },
            )
            raise ValueError("invalid_measure_id") from None

    ordered = sorted(holdings, key=lambda row: row.agent_id)
    observed = [row for row in ordered if row.value is not None]
    unknown_count = len(ordered) - len(observed)
    _LOG.debug(
        "resource_inequality_start",
        extra={
            "metric_family": spec.family_id.value,
            "algorithm_version": spec.algorithm_version,
            "run_id": run_id,
            "input_count": len(ordered),
            "observed_count": len(observed),
            "unknown_count": unknown_count,
            "measure_id": measure_value,
        },
    )

    if not observed:
        doc = _document(
            family=spec.family_id.value,
            algorithm_version=spec.algorithm_version,
            run_id=run_id,
            input_revision=input_revision,
            evidence_stages=spec.evidence_inputs,
            population=spec.population,
            denominator=spec.denominator,
            availability=MetricAvailability.UNKNOWN,
            values={},
            coverage=MetricCoverage(observed=0, expected=len(ordered), ratio=None)
            if ordered
            else None,
            notes_code="empty_or_all_unknown_holdings",
        )
        _LOG.warning(
            "resource_inequality_insufficient",
            extra={
                "metric_family": spec.family_id.value,
                "algorithm_version": spec.algorithm_version,
                "code": "insufficient_holdings",
                "availability": doc.availability.value,
            },
        )
        return doc

    vector = np.asarray([float(row.value) for row in observed], dtype=np.float64)  # type: ignore[arg-type]
    try:
        gini = _q(_gini(vector))
        theil = _q(_theil_t(vector))
        atkinson = _q(_atkinson_eps_1(vector))
        total = float(vector.sum())
        share = _q(float(np.max(vector)) / total) if total > 0.0 else 0.0
    except NumericalPolicyError as exc:
        _LOG.error(
            "resource_inequality_non_finite",
            extra={
                "metric_family": spec.family_id.value,
                "algorithm_version": spec.algorithm_version,
                "code": exc.code,
            },
        )
        raise

    availability = (
        MetricAvailability.PARTIAL
        if unknown_count > 0
        else MetricAvailability.PRESENT
    )
    coverage = MetricCoverage(
        observed=len(observed),
        expected=len(ordered) if ordered else len(observed),
        ratio=_q(len(observed) / float(len(ordered))) if ordered else 1.0,
    )
    doc = _document(
        family=spec.family_id.value,
        algorithm_version=spec.algorithm_version,
        run_id=run_id,
        input_revision=input_revision,
        evidence_stages=spec.evidence_inputs,
        population=spec.population,
        denominator=spec.denominator,
        availability=availability,
        values={
            "gini": gini,
            "theil_t": theil,
            "atkinson_eps_1": atkinson,
            "share_top_1": share,
            "population_size": len(observed),
            "measure_id": measure_value,
        },
        coverage=coverage,
        notes_code="resource_inequality_ok",
    )
    _LOG.debug(
        "resource_inequality_done",
        extra={
            "metric_family": spec.family_id.value,
            "algorithm_version": spec.algorithm_version,
            "run_id": run_id,
            "population_size": len(observed),
            "availability": availability.value,
            "duration_ms": int((time.perf_counter() - started) * 1000),
        },
    )
    return doc


def _filter_window(
    actions: Sequence[AppliedActionRow],
    *,
    window_start: int,
    window_end: int,
) -> list[AppliedActionRow]:
    return [
        row
        for row in sorted(
            actions, key=lambda item: (item.tick, item.ordinal, item.agent_id)
        )
        if window_start <= row.tick <= window_end
    ]


def _is_coop_event(row: AppliedActionRow) -> bool:
    if row.action_kind not in COOPERATION_ACTION_KINDS:
        return False
    if row.action_kind in {"help", "give"} and row.target_id == row.agent_id:
        return False
    return True


def compute_cooperation(
    actions: Sequence[AppliedActionRow],
    *,
    run_id: str,
    input_revision: str,
    agent_ids: Sequence[str],
    window_start: int = 0,
    window_end: int,
    death_ticks: Mapping[str, int] | None = None,
) -> MetricDocument:
    """Cooperation occurrence and opportunity rates; kinds stay distinguished."""
    started = time.perf_counter()
    spec = metric_specification(MetricFamilyId.COOPERATION)
    run_id = require_stable_id("run_id", run_id)
    input_revision = require_stable_id("input_revision", input_revision)
    window_end = require_exact_nonneg_int("window_end", window_end)
    deaths = dict(death_ticks or {})
    agents = tuple(sorted(require_stable_id("agent_id", a) for a in agent_ids))
    windowed = _filter_window(actions, window_start=window_start, window_end=window_end)
    applied = [row for row in windowed if row.action_kind in _VOCAB]
    coop = [row for row in applied if _is_coop_event(row)]
    opportunity = living_agent_ticks(
        agents,
        window_start=window_start,
        window_end=window_end,
        death_ticks=deaths,
    )
    _LOG.debug(
        "cooperation_start",
        extra={
            "metric_family": spec.family_id.value,
            "algorithm_version": spec.algorithm_version,
            "run_id": run_id,
            "action_count": len(applied),
            "coop_count": len(coop),
            "opportunity_agent_ticks": opportunity,
            "population_size": len(agents),
        },
    )
    if not applied:
        _LOG.warning(
            "cooperation_no_events",
            extra={
                "metric_family": spec.family_id.value,
                "algorithm_version": spec.algorithm_version,
                "code": "no_applied_events",
            },
        )
        return _document(
            family=spec.family_id.value,
            algorithm_version=spec.algorithm_version,
            run_id=run_id,
            input_revision=input_revision,
            evidence_stages=spec.evidence_inputs,
            population=spec.population,
            denominator=spec.denominator,
            availability=MetricAvailability.UNKNOWN,
            values={},
            coverage=None,
            notes_code="no_applied_events",
        )

    occurrence = _q(len(coop) / float(len(applied)))
    opportunity_rate = (
        _q(len(coop) / float(opportunity)) if opportunity > 0 else None
    )
    availability = (
        MetricAvailability.PRESENT
        if opportunity_rate is not None
        else MetricAvailability.PARTIAL
    )
    values: dict[str, object] = {
        "coop_occurrence_rate": occurrence,
        "coop_event_count": len(coop),
        "opportunity_agent_ticks": opportunity,
    }
    if opportunity_rate is not None:
        values["coop_opportunity_rate"] = opportunity_rate
    else:
        values["coop_opportunity_rate"] = None
    doc = _document(
        family=spec.family_id.value,
        algorithm_version=spec.algorithm_version,
        run_id=run_id,
        input_revision=input_revision,
        evidence_stages=spec.evidence_inputs,
        population=spec.population,
        denominator=spec.denominator,
        availability=availability,
        values=values,
        coverage=MetricCoverage(
            observed=len(applied), expected=max(len(applied), 1), ratio=1.0
        ),
        notes_code="cooperation_ok",
    )
    _LOG.debug(
        "cooperation_done",
        extra={
            "metric_family": spec.family_id.value,
            "algorithm_version": spec.algorithm_version,
            "run_id": run_id,
            "availability": availability.value,
            "duration_ms": int((time.perf_counter() - started) * 1000),
        },
    )
    return doc


def compute_conflict(
    actions: Sequence[AppliedActionRow],
    *,
    run_id: str,
    input_revision: str,
    agent_ids: Sequence[str],
    window_start: int = 0,
    window_end: int,
    death_ticks: Mapping[str, int] | None = None,
) -> MetricDocument:
    """Conflict rates with attack and flee kept separate."""
    started = time.perf_counter()
    spec = metric_specification(MetricFamilyId.CONFLICT)
    run_id = require_stable_id("run_id", run_id)
    input_revision = require_stable_id("input_revision", input_revision)
    window_end = require_exact_nonneg_int("window_end", window_end)
    deaths = dict(death_ticks or {})
    agents = tuple(sorted(require_stable_id("agent_id", a) for a in agent_ids))
    windowed = _filter_window(actions, window_start=window_start, window_end=window_end)
    applied = [row for row in windowed if row.action_kind in _VOCAB]
    attacks = [row for row in applied if row.action_kind == "attack"]
    flees = [row for row in applied if row.action_kind == "flee"]
    conflict_rows = [row for row in applied if row.action_kind in CONFLICT_ACTION_KINDS]
    opportunity = living_agent_ticks(
        agents,
        window_start=window_start,
        window_end=window_end,
        death_ticks=deaths,
    )
    _LOG.debug(
        "conflict_start",
        extra={
            "metric_family": spec.family_id.value,
            "algorithm_version": spec.algorithm_version,
            "run_id": run_id,
            "action_count": len(applied),
            "conflict_count": len(conflict_rows),
            "attack_count": len(attacks),
            "flee_count": len(flees),
            "opportunity_agent_ticks": opportunity,
        },
    )
    if not applied:
        _LOG.warning(
            "conflict_no_events",
            extra={
                "metric_family": spec.family_id.value,
                "algorithm_version": spec.algorithm_version,
                "code": "no_applied_events",
            },
        )
        return _document(
            family=spec.family_id.value,
            algorithm_version=spec.algorithm_version,
            run_id=run_id,
            input_revision=input_revision,
            evidence_stages=spec.evidence_inputs,
            population=spec.population,
            denominator=spec.denominator,
            availability=MetricAvailability.UNKNOWN,
            values={},
            coverage=None,
            notes_code="no_applied_events",
        )

    denom = float(len(applied))
    values: dict[str, object] = {
        "conflict_occurrence_rate": _q(len(conflict_rows) / denom),
        "attack_occurrence_rate": _q(len(attacks) / denom),
        "flee_occurrence_rate": _q(len(flees) / denom),
        "conflict_event_count": len(conflict_rows),
    }
    if opportunity > 0:
        values["conflict_opportunity_rate"] = _q(
            len(conflict_rows) / float(opportunity)
        )
        availability = MetricAvailability.PRESENT
    else:
        values["conflict_opportunity_rate"] = None
        availability = MetricAvailability.PARTIAL
    doc = _document(
        family=spec.family_id.value,
        algorithm_version=spec.algorithm_version,
        run_id=run_id,
        input_revision=input_revision,
        evidence_stages=spec.evidence_inputs,
        population=spec.population,
        denominator=spec.denominator,
        availability=availability,
        values=values,
        coverage=MetricCoverage(
            observed=len(applied), expected=max(len(applied), 1), ratio=1.0
        ),
        notes_code="conflict_ok",
    )
    _LOG.debug(
        "conflict_done",
        extra={
            "metric_family": spec.family_id.value,
            "algorithm_version": spec.algorithm_version,
            "run_id": run_id,
            "availability": availability.value,
            "duration_ms": int((time.perf_counter() - started) * 1000),
        },
    )
    return doc


def _kaplan_meier_median(
    death_ticks: Sequence[int], *, n_registered: int
) -> int | None:
    if n_registered <= 0 or not death_ticks:
        return None
    table = (
        pd.DataFrame({"tick": list(death_ticks)})
        .groupby("tick", sort=True)
        .size()
        .rename("deaths")
        .reset_index()
    )
    at_risk = float(n_registered)
    survival = 1.0
    for _, row in table.iterrows():
        deaths = float(row["deaths"])
        if at_risk <= 0.0:
            break
        survival *= 1.0 - (deaths / at_risk)
        at_risk -= deaths
        if survival <= 0.5:
            return int(row["tick"])
    return None


def compute_survival(
    agents: Sequence[SurvivalAgentRow],
    *,
    run_id: str,
    input_revision: str,
    final_tick: int,
) -> MetricDocument:
    """Survival rate, death counts, and Kaplan-Meier median (or partial)."""
    started = time.perf_counter()
    spec = metric_specification(MetricFamilyId.SURVIVAL)
    run_id = require_stable_id("run_id", run_id)
    input_revision = require_stable_id("input_revision", input_revision)
    final_tick = require_exact_nonneg_int("final_tick", final_tick)
    ordered = sorted(agents, key=lambda row: row.agent_id)
    _LOG.debug(
        "survival_start",
        extra={
            "metric_family": spec.family_id.value,
            "algorithm_version": spec.algorithm_version,
            "run_id": run_id,
            "population_size": len(ordered),
            "final_tick": final_tick,
        },
    )
    if not ordered:
        _LOG.warning(
            "survival_empty",
            extra={
                "metric_family": spec.family_id.value,
                "algorithm_version": spec.algorithm_version,
                "code": "empty_population",
            },
        )
        return _document(
            family=spec.family_id.value,
            algorithm_version=spec.algorithm_version,
            run_id=run_id,
            input_revision=input_revision,
            evidence_stages=spec.evidence_inputs,
            population=spec.population,
            denominator=spec.denominator,
            availability=MetricAvailability.UNKNOWN,
            values={},
            coverage=None,
            notes_code="empty_population",
        )

    deaths = [
        row.death_tick
        for row in ordered
        if row.death_tick is not None and row.death_tick <= final_tick
    ]
    death_count = len(deaths)
    censored = len(ordered) - death_count
    survival_rate = _q(float(censored) / float(len(ordered)))
    median = _kaplan_meier_median(sorted(deaths), n_registered=len(ordered))
    availability = (
        MetricAvailability.PARTIAL
        if death_count < (len(ordered) / 2.0) or median is None
        else MetricAvailability.PRESENT
    )
    # Spec: median None with partial when fewer than half died.
    if death_count < (len(ordered) / 2.0):
        median = None
        availability = MetricAvailability.PARTIAL
    values: dict[str, object] = {
        "survival_rate_at_T": survival_rate,
        "deaths": death_count,
        "censored_alive": censored,
        "median_survival_tick": median,
        "population_size": len(ordered),
    }
    doc = _document(
        family=spec.family_id.value,
        algorithm_version=spec.algorithm_version,
        run_id=run_id,
        input_revision=input_revision,
        evidence_stages=spec.evidence_inputs,
        population=spec.population,
        denominator=spec.denominator,
        availability=availability,
        values=values,
        coverage=MetricCoverage(
            observed=len(ordered), expected=len(ordered), ratio=1.0
        ),
        notes_code="survival_ok",
    )
    _LOG.debug(
        "survival_done",
        extra={
            "metric_family": spec.family_id.value,
            "algorithm_version": spec.algorithm_version,
            "run_id": run_id,
            "deaths": death_count,
            "availability": availability.value,
            "duration_ms": int((time.perf_counter() - started) * 1000),
        },
    )
    return doc


def compute_goal_completion(
    transitions: Sequence[GoalTransitionRow],
    *,
    run_id: str,
    input_revision: str,
    legacy_unavailable: bool = False,
) -> MetricDocument:
    """Goal completion / abandonment / death-interrupt rates from receipts."""
    started = time.perf_counter()
    spec = metric_specification(MetricFamilyId.GOAL_COMPLETION)
    run_id = require_stable_id("run_id", run_id)
    input_revision = require_stable_id("input_revision", input_revision)
    _LOG.debug(
        "goal_completion_start",
        extra={
            "metric_family": spec.family_id.value,
            "algorithm_version": spec.algorithm_version,
            "run_id": run_id,
            "transition_count": len(transitions),
            "legacy_unavailable": legacy_unavailable,
        },
    )
    if legacy_unavailable:
        _LOG.warning(
            "goal_completion_legacy",
            extra={
                "metric_family": spec.family_id.value,
                "algorithm_version": spec.algorithm_version,
                "code": "legacy_unavailable",
            },
        )
        return _document(
            family=spec.family_id.value,
            algorithm_version=spec.algorithm_version,
            run_id=run_id,
            input_revision=input_revision,
            evidence_stages=spec.evidence_inputs,
            population=spec.population,
            denominator=spec.denominator,
            availability=MetricAvailability.UNKNOWN,
            values={},
            coverage=None,
            notes_code="legacy_unavailable",
        )

    ordered = sorted(
        transitions, key=lambda row: (row.tick, row.goal_id, row.owner_id)
    )
    if not ordered:
        return _document(
            family=spec.family_id.value,
            algorithm_version=spec.algorithm_version,
            run_id=run_id,
            input_revision=input_revision,
            evidence_stages=spec.evidence_inputs,
            population=spec.population,
            denominator=spec.denominator,
            availability=MetricAvailability.ABSENT,
            values={"goals_total": 0},
            coverage=MetricCoverage(observed=0, expected=0, ratio=None),
            notes_code="no_goal_receipts",
        )

    # Latest transition per goal determines terminal/censored outcome.
    latest: dict[str, GoalTransitionRow] = {}
    for row in ordered:
        latest[row.goal_id] = row
    terminals = list(latest.values())
    n_completed = sum(1 for row in terminals if row.reason_code == _GOAL_COMPLETED)
    n_abandoned = sum(1 for row in terminals if row.reason_code == _GOAL_ABANDONED)
    n_death = sum(1 for row in terminals if row.reason_code == _GOAL_DEATH)
    n_run_end = sum(1 for row in terminals if row.reason_code == _GOAL_RUN_END)
    denom = n_completed + n_abandoned + n_death + n_run_end
    if denom == 0:
        _LOG.warning(
            "goal_completion_degenerate",
            extra={
                "metric_family": spec.family_id.value,
                "algorithm_version": spec.algorithm_version,
                "code": "no_terminal_outcomes",
            },
        )
        return _document(
            family=spec.family_id.value,
            algorithm_version=spec.algorithm_version,
            run_id=run_id,
            input_revision=input_revision,
            evidence_stages=spec.evidence_inputs,
            population=spec.population,
            denominator=spec.denominator,
            availability=MetricAvailability.UNKNOWN,
            values={"goals_total": len(terminals)},
            coverage=None,
            notes_code="no_terminal_outcomes",
        )

    values: dict[str, object] = {
        "completion_rate": _q(n_completed / float(denom)),
        "abandonment_rate": _q(n_abandoned / float(denom)),
        "death_interrupt_rate": _q(n_death / float(denom)),
        "goals_total": len(terminals),
        "goals_censored_run_end": n_run_end,
    }
    doc = _document(
        family=spec.family_id.value,
        algorithm_version=spec.algorithm_version,
        run_id=run_id,
        input_revision=input_revision,
        evidence_stages=spec.evidence_inputs,
        population=spec.population,
        denominator=spec.denominator,
        availability=MetricAvailability.PRESENT,
        values=values,
        coverage=MetricCoverage(
            observed=len(terminals), expected=len(terminals), ratio=1.0
        ),
        notes_code="goal_completion_ok",
    )
    _LOG.debug(
        "goal_completion_done",
        extra={
            "metric_family": spec.family_id.value,
            "algorithm_version": spec.algorithm_version,
            "run_id": run_id,
            "goals_total": len(terminals),
            "availability": MetricAvailability.PRESENT.value,
            "duration_ms": int((time.perf_counter() - started) * 1000),
        },
    )
    return doc


def compute_action_resolution_rates(
    resolutions: Sequence[ActionResolutionRow],
    *,
    run_id: str,
    input_revision: str,
    legacy_unavailable: bool = False,
    evidence_complete: bool = True,
) -> MetricDocument:
    """Attempted/applied/rejected/conflicted rates from ActionResolution only."""
    started = time.perf_counter()
    shared = action_resolution_rate_spec()
    run_id = require_stable_id("run_id", run_id)
    input_revision = require_stable_id("input_revision", input_revision)
    _LOG.debug(
        "action_resolution_rates_start",
        extra={
            "metric_family": ACTION_RESOLUTION_RATES_FAMILY,
            "algorithm_version": shared.algorithm_version,
            "run_id": run_id,
            "resolution_count": len(resolutions),
            "legacy_unavailable": legacy_unavailable,
        },
    )
    if legacy_unavailable:
        _LOG.warning(
            "action_resolution_legacy",
            extra={
                "metric_family": ACTION_RESOLUTION_RATES_FAMILY,
                "algorithm_version": shared.algorithm_version,
                "code": "legacy_unavailable",
            },
        )
        return _document(
            family=ACTION_RESOLUTION_RATES_FAMILY,
            algorithm_version=shared.algorithm_version,
            run_id=run_id,
            input_revision=input_revision,
            evidence_stages=shared.evidence_inputs,
            population=shared.population,
            denominator=shared.denominator,
            availability=MetricAvailability.UNKNOWN,
            values={},
            coverage=None,
            notes_code="legacy_unavailable",
        )

    ordered = sorted(
        resolutions, key=lambda row: (row.tick, row.ordinal, row.agent_id)
    )
    if not ordered:
        return _document(
            family=ACTION_RESOLUTION_RATES_FAMILY,
            algorithm_version=shared.algorithm_version,
            run_id=run_id,
            input_revision=input_revision,
            evidence_stages=shared.evidence_inputs,
            population=shared.population,
            denominator=shared.denominator,
            availability=MetricAvailability.ABSENT,
            values={},
            coverage=MetricCoverage(observed=0, expected=0, ratio=None),
            notes_code="no_action_resolution_rows",
        )

    attempt_count = len(ordered)
    applied = sum(1 for row in ordered if row.status == _APPLIED_STATUS)
    conflicted = sum(1 for row in ordered if row.status == _CONFLICTED_STATUS)
    rejected = sum(1 for row in ordered if row.status in _REJECTED_STATUSES)
    denom = float(attempt_count)
    values: dict[str, object] = {
        "attempt_count": attempt_count,
        "applied_rate": _q(applied / denom),
        "rejected_rate": _q(rejected / denom),
        "conflicted_rate": _q(conflicted / denom),
    }
    availability = (
        MetricAvailability.PRESENT
        if evidence_complete
        else MetricAvailability.PARTIAL
    )
    doc = _document(
        family=ACTION_RESOLUTION_RATES_FAMILY,
        algorithm_version=shared.algorithm_version,
        run_id=run_id,
        input_revision=input_revision,
        evidence_stages=shared.evidence_inputs,
        population=shared.population,
        denominator=shared.denominator,
        availability=availability,
        values=values,
        coverage=MetricCoverage(
            observed=attempt_count, expected=attempt_count, ratio=1.0
        ),
        notes_code="action_resolution_rates_ok",
    )
    _LOG.debug(
        "action_resolution_rates_done",
        extra={
            "metric_family": ACTION_RESOLUTION_RATES_FAMILY,
            "algorithm_version": shared.algorithm_version,
            "run_id": run_id,
            "attempt_count": attempt_count,
            "availability": availability.value,
            "duration_ms": int((time.perf_counter() - started) * 1000),
        },
    )
    return doc
