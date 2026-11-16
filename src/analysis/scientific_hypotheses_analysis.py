"""Bounded detached composition of owner testable hypotheses and trials."""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Final

from analysis.scientific_hypotheses_contract import (
    NONE_TOKEN,
    SCIENTIFIC_HYPOTHESES_POLICY_VERSION,
    ScientificHypothesesError,
    ScientificHypothesisAvailability,
    ScientificHypothesisConditionSlot,
    ScientificHypothesisCoverage,
    ScientificHypothesisLayer,
    assert_scientific_hypothesis_layer_separation,
)
from analysis.scientific_hypotheses_policy import (
    ScientificHypothesesPolicy,
    default_policy,
    window_bounds,
    window_index,
)
from analysis.scientific_hypotheses_rows import (
    HypothesisFact,
    ScientificCoverageRow,
    ScientificHypothesisRow,
    ScientificObjectiveEvidenceRow,
    ScientificOutcomeRow,
    ScientificRevisionRow,
    ScientificSourceRow,
    ScientificTrialRow,
)
from world.events import ExperimentResolved, WorldEvent
from world.experimentation import (
    DiscoveryMode,
    ExperimentOperator,
    ExperimentOutcomeClass,
)

__all__ = [
    "ScientificHypothesesAnalysis",
    "empty_scientific_hypotheses_analysis",
    "harvest_scientific_hypotheses_analysis",
    "scientific_hypotheses_analysis_digest",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "analysis.scientific_hypotheses.analysis"
)

_OUTCOME_ORDER: Final[tuple[ExperimentOutcomeClass, ...]] = tuple(
    ExperimentOutcomeClass
)


@dataclass(frozen=True, slots=True)
class ScientificHypothesesAnalysis:
    """Detached analysis value with three strictly separated layers."""

    objective_rows: tuple[ScientificObjectiveEvidenceRow, ...] = ()
    hypothesis_rows: tuple[ScientificHypothesisRow, ...] = ()
    revision_rows: tuple[ScientificRevisionRow, ...] = ()
    trial_rows: tuple[ScientificTrialRow, ...] = ()
    source_rows: tuple[ScientificSourceRow, ...] = ()
    outcome_rows: tuple[ScientificOutcomeRow, ...] = ()
    coverage_rows: tuple[ScientificCoverageRow, ...] = ()
    notices: tuple[str, ...] = ()
    policy_version: str = SCIENTIFIC_HYPOTHESES_POLICY_VERSION

    @property
    def row_count(self) -> int:
        """Total row count across every family."""

        return (
            len(self.objective_rows)
            + len(self.hypothesis_rows)
            + len(self.revision_rows)
            + len(self.trial_rows)
            + len(self.source_rows)
            + len(self.outcome_rows)
            + len(self.coverage_rows)
        )

    @property
    def source_layers(self) -> tuple[ScientificHypothesisLayer, ...]:
        """Layers that actually contributed at least one row."""

        layers: list[ScientificHypothesisLayer] = []
        if self.objective_rows:
            layers.append(ScientificHypothesisLayer.OBJECTIVE_EVIDENCE)
        if self.hypothesis_rows or self.revision_rows:
            layers.append(ScientificHypothesisLayer.OWNER_HYPOTHESIS)
        if (
            self.trial_rows
            or self.source_rows
            or self.outcome_rows
            or self.coverage_rows
        ):
            layers.append(ScientificHypothesisLayer.ANALYTICAL_SUMMARY)
        return tuple(layers)


def empty_scientific_hypotheses_analysis(
    policy: ScientificHypothesesPolicy | None = None,
) -> ScientificHypothesesAnalysis:
    """Return the explicit missing analysis; no fabricated zero rows."""

    coverage = ScientificCoverageRow(
        window_index=0,
        window_tick=0,
        window_count=0,
        event_count=0,
        owner_count=0,
        hypothesis_count=0,
        condition_count=0,
        revision_count=0,
        trial_count=0,
        truncated=False,
        coverage=ScientificHypothesisCoverage.MISSING,
        availability=ScientificHypothesisAvailability.UNAVAILABLE,
    )
    analysis = ScientificHypothesesAnalysis(
        coverage_rows=(coverage,),
        policy_version=active_version(),
    )
    _assert_layers(analysis)
    return analysis


def active_version() -> str:
    return SCIENTIFIC_HYPOTHESES_POLICY_VERSION


def scientific_hypotheses_analysis_digest(
    analysis: ScientificHypothesesAnalysis,
) -> str:
    """Digest counts, ordering, coverage, and notices only."""

    if type(analysis) is not ScientificHypothesesAnalysis:
        raise ScientificHypothesesError("scientific_hypotheses_invalid_hypothesis")
    parts = [
        analysis.policy_version,
        str(len(analysis.objective_rows)),
        str(len(analysis.hypothesis_rows)),
        str(len(analysis.revision_rows)),
        str(len(analysis.trial_rows)),
        str(len(analysis.source_rows)),
        str(len(analysis.outcome_rows)),
        str(len(analysis.coverage_rows)),
        "|".join(analysis.notices),
        "|".join(
            f"{row.window_index}:{row.window_tick}:{row.coverage.value}:"
            f"{row.availability.value}"
            for row in analysis.coverage_rows
        ),
    ]
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:32]


def _assert_layers(analysis: ScientificHypothesesAnalysis) -> None:
    assert_scientific_hypothesis_layer_separation(
        analysis.objective_rows,
        (*analysis.hypothesis_rows, *analysis.revision_rows),
        (
            *analysis.trial_rows,
            *analysis.source_rows,
            *analysis.outcome_rows,
            *analysis.coverage_rows,
        ),
    )


def _cap[T](rows: list[T], limit: int) -> tuple[list[T], bool]:
    if len(rows) <= limit:
        return rows, False
    return rows[:limit], True


def _safe_objective_rows(
    events: Sequence[WorldEvent], policy: ScientificHypothesesPolicy
) -> tuple[list[ScientificObjectiveEvidenceRow], bool]:
    candidates: list[tuple[int, int, str, ScientificObjectiveEvidenceRow]] = []
    for event in events:
        details = getattr(event, "details", None)
        if type(details) is not ExperimentResolved:
            continue
        tick = int(event.tick)
        event_token = f"evt:{event.event_id.value}"
        coverage = ScientificHypothesisCoverage.COMPLETE
        row = ScientificObjectiveEvidenceRow(
            window_index=window_index(tick, policy),
            window_tick=window_bounds(tick, policy)[0],
            sequence=int(event.sequence),
            event_token=event_token,
            operator=ExperimentOperator(details.operator),
            outcome_class=ExperimentOutcomeClass(details.outcome_class),
            discovery_mode=DiscoveryMode(details.discovery_mode),
            coverage=coverage,
        )
        candidates.append((row.window_index, row.sequence, event_token, row))
    candidates.sort(key=lambda item: (item[0], item[1], item[2]))
    rows = [item[3] for item in candidates]
    capped, truncated = _cap(rows, policy.max_events)
    return capped, truncated


def _condition_pairs(fact: HypothesisFact) -> tuple[
    tuple[ScientificHypothesisConditionSlot, str], ...
]:
    return tuple(
        (
            ScientificHypothesisConditionSlot(condition.slot.value),
            condition.value_token,
        )
        for condition in fact.conditions
    )


def _prediction(value: str | None) -> str:
    return NONE_TOKEN if value is None else value


def _hypothesis_row(
    fact: HypothesisFact,
    *,
    policy: ScientificHypothesesPolicy,
    coverage: ScientificHypothesisCoverage,
) -> ScientificHypothesisRow:
    tick = fact.created_tick
    return ScientificHypothesisRow(
        window_index=window_index(tick, policy),
        window_tick=window_bounds(tick, policy)[0],
        owner_token=fact.owner_token,
        hypothesis_token=fact.hypothesis_token,
        claim_token=fact.claim_token,
        causal_hypothesis_token=fact.causal_hypothesis_token,
        status=fact.status,
        predicted_outcome=_prediction(fact.predicted_outcome),
        confidence_milli=fact.confidence_milli,
        condition_count=len(fact.conditions),
        condition_pairs=_condition_pairs(fact),
        support_count=len(
            [trial for trial in fact.trials if trial.matched]
        ),
        contradiction_count=len(
            [
                trial
                for trial in fact.trials
                if not trial.matched and trial.predicted_outcome != NONE_TOKEN
            ]
        ),
        revision_count=len(fact.revisions),
        source_kind=fact.source_kind,
        active=fact.active,
        created_tick=tick,
        coverage=coverage,
    )


def _revision_rows(
    fact: HypothesisFact,
    *,
    policy: ScientificHypothesesPolicy,
    coverage: ScientificHypothesisCoverage,
) -> list[ScientificRevisionRow]:
    rows: list[ScientificRevisionRow] = []
    for revision in fact.revisions:
        rows.append(
            ScientificRevisionRow(
                window_index=window_index(revision.tick, policy),
                window_tick=window_bounds(revision.tick, policy)[0],
                hypothesis_token=fact.hypothesis_token,
                revision_index=revision.revision_index,
                revision_tick=revision.tick,
                reason=revision.reason,
                claim_token=revision.claim_token,
                predicted_outcome=_prediction(revision.predicted_outcome),
                condition_pairs=revision.condition_pairs,
                confidence_milli=revision.confidence_milli,
                coverage=coverage,
            )
        )
    return rows


def _trial_row(
    fact: HypothesisFact,
    *,
    policy: ScientificHypothesesPolicy,
    coverage: ScientificHypothesisCoverage,
) -> ScientificTrialRow:
    matched = sum(1 for trial in fact.trials if trial.matched)
    inconclusive = sum(
        1 for trial in fact.trials if trial.predicted_outcome == NONE_TOKEN
    )
    mismatched = len(fact.trials) - matched - inconclusive
    last_tick = max((trial.tick for trial in fact.trials), default=0)
    return ScientificTrialRow(
        window_index=window_index(last_tick, policy),
        window_tick=window_bounds(last_tick, policy)[0],
        hypothesis_token=fact.hypothesis_token,
        trial_count=len(fact.trials),
        matched_count=matched,
        mismatched_count=mismatched,
        inconclusive_count=inconclusive,
        last_trial_tick=last_tick,
        coverage=coverage,
        deliberate_count=sum(
            1
            for trial in fact.trials
            if trial.discovery_mode is DiscoveryMode.DELIBERATE
        ),
        accidental_count=sum(
            1
            for trial in fact.trials
            if trial.discovery_mode is DiscoveryMode.ACCIDENTAL
        ),
    )


def _availability(
    hypothesis_count: int, trial_count: int, policy: ScientificHypothesesPolicy
) -> ScientificHypothesisAvailability:
    if hypothesis_count < policy.min_samples or trial_count < policy.min_samples:
        return ScientificHypothesisAvailability.INSUFFICIENT_SAMPLES
    return ScientificHypothesisAvailability.AVAILABLE


def harvest_scientific_hypotheses_analysis(
    *,
    events: Sequence[WorldEvent],
    facts: Sequence[HypothesisFact],
    policy: ScientificHypothesesPolicy | None = None,
    window_end: int | None = None,
) -> ScientificHypothesesAnalysis:
    """Compose bounded objective, owner, and analytical rows."""

    if isinstance(events, (str, bytes)) or not isinstance(events, Sequence):
        raise ScientificHypothesesError("scientific_hypotheses_invalid_hypothesis")
    if isinstance(facts, (str, bytes)) or not isinstance(facts, Sequence):
        raise ScientificHypothesesError("scientific_hypotheses_invalid_hypothesis")
    active = default_policy() if policy is None else policy
    if type(active) is not ScientificHypothesesPolicy:
        raise ScientificHypothesesError("scientific_hypotheses_invalid_policy")
    if window_end is not None and (
        isinstance(window_end, bool)
        or type(window_end) is not int
        or window_end < 0
    ):
        raise ScientificHypothesesError("scientific_hypotheses_invalid_policy")
    filtered_events = [
        event
        for event in events
        if type(event) is WorldEvent
        and (window_end is None or event.tick <= window_end)
    ]
    filtered_facts = [
        fact
        for fact in facts
        if type(fact) is HypothesisFact
        and (window_end is None or fact.created_tick <= window_end)
    ]
    if not filtered_events and not filtered_facts:
        return empty_scientific_hypotheses_analysis(active)

    notices: list[str] = []
    objective_rows, objective_truncated = _safe_objective_rows(
        filtered_events, active
    )
    if objective_truncated:
        notices.append("objective_events")

    facts_sorted = sorted(
        filtered_facts,
        key=lambda fact: (fact.created_tick, fact.owner_token, fact.hypothesis_token),
    )
    owners = sorted({fact.owner_token for fact in facts_sorted})
    if len(owners) > active.max_owners:
        owners = owners[: active.max_owners]
        notices.append("owners")
    allowed_owners = set(owners)
    facts_sorted = [fact for fact in facts_sorted if fact.owner_token in allowed_owners]

    hypothesis_rows = [
        _hypothesis_row(
            fact, policy=active, coverage=ScientificHypothesisCoverage.COMPLETE
        )
        for fact in facts_sorted
    ]
    hypothesis_rows, hypothesis_truncated = _cap(
        hypothesis_rows, active.max_hypotheses
    )
    if hypothesis_truncated:
        notices.append("hypotheses")

    condition_count = sum(row.condition_count for row in hypothesis_rows)
    if condition_count > active.max_conditions:
        notices.append("conditions")

    revision_rows = []
    for fact in facts_sorted:
        revision_rows.extend(
            _revision_rows(
                fact, policy=active, coverage=ScientificHypothesisCoverage.COMPLETE
            )
        )
    revision_rows.sort(
        key=lambda row: (
            row.window_index,
            row.revision_tick,
            row.hypothesis_token,
            row.revision_index,
        )
    )
    revision_rows, revision_truncated = _cap(revision_rows, active.max_revisions)
    if revision_truncated:
        notices.append("revisions")

    trial_rows = [
        _trial_row(
            fact, policy=active, coverage=ScientificHypothesisCoverage.COMPLETE
        )
        for fact in facts_sorted
    ]
    trial_rows.sort(
        key=lambda row: (
            row.window_index,
            row.last_trial_tick,
            row.hypothesis_token,
        )
    )
    trial_rows, trial_truncated = _cap(trial_rows, active.max_trials)
    if trial_truncated:
        notices.append("trials")

    safe_tokens = {row.event_token for row in objective_rows}
    unlinked = 0
    for fact in facts_sorted:
        for trial in fact.trials:
            if trial.event_token not in safe_tokens:
                unlinked += 1
    if unlinked:
        _LOG.warning("scientific_hypotheses_unlinked_trial count=%s", unlinked)
        notices.append("unlinked_trials")

    source_rows = _source_rows(hypothesis_rows, active)
    source_rows, source_truncated = _cap(source_rows, active.max_summary_rows)
    if source_truncated:
        notices.append("sources")

    outcome_rows = _outcome_rows(facts_sorted, trial_rows, active)
    outcome_rows, outcome_truncated = _cap(outcome_rows, active.max_summary_rows)
    if outcome_truncated:
        notices.append("outcomes")

    coverage_rows = _coverage_rows(
        objective_rows, hypothesis_rows, revision_rows, trial_rows, active
    )
    coverage_rows, coverage_truncated = _cap(coverage_rows, active.max_summary_rows)
    if coverage_truncated:
        notices.append("coverage")

    notices = notices[: active.max_notices]
    truncated = any(
        (
            objective_truncated,
            hypothesis_truncated,
            revision_truncated,
            trial_truncated,
            source_truncated,
            outcome_truncated,
            coverage_truncated,
        )
    )
    coverage_value = (
        ScientificHypothesisCoverage.PARTIAL
        if truncated
        else ScientificHypothesisCoverage.COMPLETE
    )
    if truncated:
        objective_rows = [
            _with_coverage(row, coverage_value) for row in objective_rows
        ]
        hypothesis_rows = [
            _with_coverage(row, coverage_value) for row in hypothesis_rows
        ]
        revision_rows = [
            _with_coverage(row, coverage_value) for row in revision_rows
        ]
        trial_rows = [_with_coverage(row, coverage_value) for row in trial_rows]
        source_rows = [_with_coverage(row, coverage_value) for row in source_rows]
        outcome_rows = [_with_coverage(row, coverage_value) for row in outcome_rows]
        coverage_rows = [
            _with_coverage(row, coverage_value) for row in coverage_rows
        ]
        _LOG.warning("scientific_hypotheses_truncated family=bounded_harvest")

    analysis = ScientificHypothesesAnalysis(
        objective_rows=tuple(objective_rows),
        hypothesis_rows=tuple(hypothesis_rows),
        revision_rows=tuple(revision_rows),
        trial_rows=tuple(trial_rows),
        source_rows=tuple(source_rows),
        outcome_rows=tuple(outcome_rows),
        coverage_rows=tuple(coverage_rows),
        notices=tuple(notices),
        policy_version=active_version(),
    )
    _assert_layers(analysis)
    return analysis


def _with_coverage(row: Any, coverage: ScientificHypothesisCoverage) -> Any:
    from dataclasses import replace

    return replace(row, coverage=coverage)


def _source_rows(
    hypothesis_rows: Sequence[ScientificHypothesisRow],
    policy: ScientificHypothesesPolicy,
) -> list[ScientificSourceRow]:
    grouped: dict[tuple[int, int, str], list[ScientificHypothesisRow]] = {}
    for row in hypothesis_rows:
        grouped.setdefault(
            (row.window_index, row.window_tick, row.source_kind.value), []
        ).append(row)
    rows: list[ScientificSourceRow] = []
    for (window, tick, _source_kind), members in sorted(grouped.items()):
        rows.append(
            ScientificSourceRow(
                window_index=window,
                window_tick=tick,
                source_kind=members[0].source_kind,
                hypothesis_count=len(members),
                adopted_count=sum(
                    1
                    for member in members
                    if member.source_kind.value == "communicated"
                ),
                coverage=ScientificHypothesisCoverage.COMPLETE,
            )
        )
    return rows


def _outcome_rows(
    facts: Sequence[HypothesisFact],
    trial_rows: Sequence[ScientificTrialRow],
    policy: ScientificHypothesesPolicy,
) -> list[ScientificOutcomeRow]:
    counts: dict[tuple[int, int, ExperimentOutcomeClass], dict[str, int]] = {}
    for fact in facts:
        for trial in fact.trials:
            window = window_index(trial.tick, policy)
            tick = window_bounds(trial.tick, policy)[0]
            key = (window, tick, trial.outcome_class)
            bucket = counts.setdefault(
                key, {"trial": 0, "matched": 0, "mismatched": 0}
            )
            bucket["trial"] += 1
            if trial.predicted_outcome == NONE_TOKEN:
                continue
            if trial.matched:
                bucket["matched"] += 1
            else:
                bucket["mismatched"] += 1
    rows: list[ScientificOutcomeRow] = []
    for (window, tick, outcome_class), bucket in sorted(
        counts.items(), key=lambda item: (item[0][0], item[0][1], item[0][2].value)
    ):
        trial_count = bucket["trial"]
        rows.append(
            ScientificOutcomeRow(
                window_index=window,
                window_tick=tick,
                outcome_class=outcome_class,
                trial_count=trial_count,
                matched_count=bucket["matched"],
                mismatched_count=bucket["mismatched"],
                share_milli=(
                    0
                    if trial_count == 0
                    else (bucket["matched"] * 1_000) // trial_count
                ),
                coverage=ScientificHypothesisCoverage.COMPLETE,
                availability=(
                    ScientificHypothesisAvailability.AVAILABLE
                    if trial_count >= policy.min_samples
                    else ScientificHypothesisAvailability.INSUFFICIENT_SAMPLES
                ),
            )
        )
    return rows


def _window_totals(
    facts: Sequence[HypothesisFact], policy: ScientificHypothesesPolicy
) -> dict[tuple[int, int], dict[str, int]]:
    totals: dict[tuple[int, int], dict[str, int]] = {}
    for fact in facts:
        window = window_index(fact.created_tick, policy)
        tick = window_bounds(fact.created_tick, policy)[0]
        bucket = totals.setdefault(
            (window, tick),
            {
                "hypotheses": 0,
                "conditions": 0,
                "revisions": 0,
                "trials": 0,
            },
        )
        bucket["hypotheses"] += 1
        bucket["conditions"] += len(fact.conditions)
        bucket["revisions"] += len(fact.revisions)
        bucket["trials"] += len(fact.trials)
    return totals


def _coverage_rows(
    objective_rows: Sequence[ScientificObjectiveEvidenceRow],
    hypothesis_rows: Sequence[ScientificHypothesisRow],
    revision_rows: Sequence[ScientificRevisionRow],
    trial_rows: Sequence[ScientificTrialRow],
    policy: ScientificHypothesesPolicy,
) -> list[ScientificCoverageRow]:
    events: dict[tuple[int, int], int] = {}
    for row in objective_rows:
        key = (row.window_index, row.window_tick)
        events[key] = events.get(key, 0) + 1
    hypotheses = _window_totals_from_rows(hypothesis_rows, revision_rows, trial_rows)
    keys = sorted(set(events) | set(hypotheses))
    rows: list[ScientificCoverageRow] = []
    for key in keys:
        window, tick = key
        hypothesis_count = hypotheses.get(key, {}).get("hypotheses", 0)
        trial_count = hypotheses.get(key, {}).get("trials", 0)
        rows.append(
            ScientificCoverageRow(
                window_index=window,
                window_tick=tick,
                window_count=1,
                event_count=events.get(key, 0),
                owner_count=len(
                    {
                        row.owner_token
                        for row in hypothesis_rows
                        if (row.window_index, row.window_tick) == key
                    }
                ),
                hypothesis_count=hypothesis_count,
                condition_count=hypotheses.get(key, {}).get("conditions", 0),
                revision_count=hypotheses.get(key, {}).get("revisions", 0),
                trial_count=trial_count,
                truncated=False,
                coverage=ScientificHypothesisCoverage.COMPLETE,
                availability=(
                    ScientificHypothesisAvailability.UNAVAILABLE
                    if hypothesis_count == 0
                    else _availability(hypothesis_count, trial_count, policy)
                ),
            )
        )
    return rows


def _window_totals_from_rows(
    hypothesis_rows: Sequence[ScientificHypothesisRow],
    revision_rows: Sequence[ScientificRevisionRow],
    trial_rows: Sequence[ScientificTrialRow],
) -> dict[tuple[int, int], dict[str, int]]:
    totals: dict[tuple[int, int], dict[str, int]] = {}
    for hypothesis_row in hypothesis_rows:
        bucket = totals.setdefault(
            (hypothesis_row.window_index, hypothesis_row.window_tick),
            {"hypotheses": 0, "conditions": 0, "revisions": 0, "trials": 0},
        )
        bucket["hypotheses"] += 1
        bucket["conditions"] += hypothesis_row.condition_count
    for revision_row in revision_rows:
        bucket = totals.setdefault(
            (revision_row.window_index, revision_row.window_tick),
            {"hypotheses": 0, "conditions": 0, "revisions": 0, "trials": 0},
        )
        bucket["revisions"] += 1
    for trial_row in trial_rows:
        bucket = totals.setdefault(
            (trial_row.window_index, trial_row.window_tick),
            {"hypotheses": 0, "conditions": 0, "revisions": 0, "trials": 0},
        )
        bucket["trials"] += trial_row.trial_count
    return totals
