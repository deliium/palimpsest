"""Closed scalar outcome registry for historical-contingency experiments.

No new metric family or composite culture score is introduced. Each selector
delegates to an existing analysis algorithm and reports an explicit availability
instead of coercing missing evidence to zero.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import replace
from typing import Final

from analysis.cultural_evolution_evidence import CulturalAnalysisWindow
from analysis.cultural_narrative_survival import (
    compute_cultural_narrative_survival,
)
from analysis.cultural_technology_continuity import (
    compute_cultural_technology_continuity,
)
from analysis.institution_emergence import (
    InstitutionLane,
    compute_institution_candidates,
)
from analysis.institutional_persistence import (
    compute_institutional_persistence,
    compute_institutional_persistence_metric,
)
from analysis.models import (
    MetricAvailability,
    MetricDocument,
    RelationshipEdgeRow,
)
from analysis.numerical import quantize_float
from analysis.objective_metrics import (
    compute_cooperation,
    compute_resource_inequality,
)
from analysis.path_dependence_models import (
    SELECTOR_REGISTRY,
    OutcomeAvailability,
    OutcomeMeasurement,
    PathDependenceEvidence,
    PathDependenceOutcomeRow,
)
from analysis.relationship_metrics import compute_relationship_stability
from analysis.social_norm_metrics import (
    compute_emergent_social_norms,
    compute_norm_persistence,
)
from analysis.specifications import ResourceMeasureId
from experiments.path_dependence_models import (
    OutcomeSelector,
    OutcomeWindow,
    PathDependenceValidationError,
)

_LOG: Final[logging.Logger] = logging.getLogger(
    "analysis.path_dependence_outcomes"
)


def _availability(value: MetricAvailability) -> OutcomeAvailability:
    if value is MetricAvailability.PRESENT:
        return OutcomeAvailability.PRESENT
    if value is MetricAvailability.PARTIAL:
        return OutcomeAvailability.PARTIAL
    return OutcomeAvailability.UNKNOWN


def _number(document: MetricDocument, key: str) -> float | None:
    value = document.values.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return quantize_float(float(value))


def _row(
    *,
    selector: OutcomeSelector,
    value: float | None,
    availability: OutcomeAvailability,
    coverage: str,
    reason_code: str | None,
    evidence_refs: Sequence[str],
    censoring: str | None = None,
) -> PathDependenceOutcomeRow:
    if value is not None:
        value = quantize_float(float(value))
    if availability is OutcomeAvailability.KNOWN_ZERO and value != 0.0:
        raise PathDependenceValidationError(
            "outcome_basis_mismatch", "known zero requires zero value"
        )
    return PathDependenceOutcomeRow(
        selector_id=selector.selector_id,
        domain=selector.domain,
        window_id=selector.window_id,
        value=value,
        availability=availability,
        coverage=coverage,
        censoring=censoring,
        reason_code=reason_code,
        evidence_refs=tuple(evidence_refs),
    )


def _unknown(
    selector: OutcomeSelector,
    reason_code: str,
    *,
    coverage: str = "missing",
    censoring: str | None = None,
    refs: Sequence[str] = (),
) -> PathDependenceOutcomeRow:
    return _row(
        selector=selector,
        value=None,
        availability=OutcomeAvailability.UNKNOWN,
        coverage=coverage,
        censoring=censoring,
        reason_code=reason_code,
        evidence_refs=refs,
    )


def _norm_active(
    evidence: PathDependenceEvidence,
    selector: OutcomeSelector,
    window: OutcomeWindow,
) -> PathDependenceOutcomeRow:
    endpoint = window.end_tick.value
    if evidence.norm_rows is None:
        return _unknown(selector, "missing_norm_evidence", refs=(f"tick:{endpoint}",))
    document = compute_emergent_social_norms(
        evidence.norm_rows,
        run_id=evidence.run_id,
        input_revision=evidence.input_revision,
        tick=endpoint,
    )
    value = _number(document, "active_belief_count")
    refs = (f"algorithm:{document.algorithm_version}", f"tick:{endpoint}")
    if value is not None:
        return _row(
            selector=selector,
            value=value,
            availability=_availability(document.availability),
            coverage="complete" if document.coverage is not None else "missing",
            reason_code=None,
            evidence_refs=refs,
        )
    if (
        evidence.norm_coverage_complete
        and document.availability is MetricAvailability.ABSENT
    ):
        return _row(
            selector=selector,
            value=0.0,
            availability=OutcomeAvailability.KNOWN_ZERO,
            coverage="complete",
            reason_code="complete_empty_norm_ledger",
            evidence_refs=refs,
        )
    return _unknown(
        selector,
        "missing_norm_state",
        coverage="unknown",
        refs=refs,
    )


def _norm_persistence(
    evidence: PathDependenceEvidence,
    selector: OutcomeSelector,
    window: OutcomeWindow,
) -> PathDependenceOutcomeRow:
    document = compute_norm_persistence(
        evidence.norm_history,
        run_id=evidence.run_id,
        input_revision=evidence.input_revision,
        tick=window.end_tick.value,
    )
    value = _number(document, "belief_persistence")
    refs = (
        f"algorithm:{document.algorithm_version}",
        f"readings:{len(evidence.norm_history)}",
    )
    if value is not None:
        return _row(
            selector=selector,
            value=value,
            availability=_availability(document.availability),
            coverage="complete",
            reason_code=None,
            evidence_refs=refs,
        )
    return _unknown(
        selector,
        "insufficient_norm_readings"
        if len(evidence.norm_history) < 2
        else "missing_norm_persistence",
        refs=refs,
    )


def _relationship_delta(
    evidence: PathDependenceEvidence,
    selector: OutcomeSelector,
    window: OutcomeWindow,
) -> PathDependenceOutcomeRow:
    start = window.start_tick.value
    end = window.end_tick.value
    if end <= start:
        return _unknown(selector, "invalid_window")
    predecessors: dict[tuple[str, str], RelationshipEdgeRow] = {}
    in_window: list[RelationshipEdgeRow] = []
    for row in evidence.relationship_rows:
        tick = row.logical_tick
        if tick < start:
            key = (row.source_id, row.target_id)
            current = predecessors.get(key)
            if current is None or (
                tick,
                row.ordinal,
            ) > (current.logical_tick, current.ordinal):
                predecessors[key] = row
        elif tick < end:
            in_window.append(row)
    if not in_window:
        return _unknown(
            selector,
            "no_relationship_delta",
            refs=(f"window:{start}-{end}",),
        )
    selected = (*predecessors.values(), *in_window)
    document = compute_relationship_stability(
        selected,
        run_id=evidence.run_id,
        input_revision=evidence.input_revision,
        window_end=end - 1,
        death_ticks=dict(evidence.relationship_death_ticks),
    )
    value = _number(document, "mean_abs_delta")
    refs = (
        f"algorithm:{document.algorithm_version}",
        f"window:{start}-{end}",
    )
    if value is None:
        return _unknown(
            selector,
            "missing_relationship_delta",
            coverage="unknown",
            refs=refs,
        )
    return _row(
        selector=selector,
        value=value,
        availability=_availability(document.availability),
        coverage="complete" if document.coverage is not None else "missing",
        reason_code=None,
        evidence_refs=refs,
    )


def _institution_candidates(
    evidence: PathDependenceEvidence,
    selector: OutcomeSelector,
    window: OutcomeWindow,
) -> PathDependenceOutcomeRow:
    refs: tuple[str, ...] = (
        f"window:{window.start_tick.value}-{window.end_tick.value}",
    )
    if not evidence.institution_complete_search:
        return _unknown(
            selector,
            "incomplete_candidate_search",
            coverage="unknown",
            refs=refs,
        )
    lanes: dict[InstitutionLane, list[object]] = defaultdict(list)
    for row in evidence.institution_lane_rows:
        lanes[row.lane].append(row)
    result = compute_institution_candidates(
        role_rows=tuple(lanes[InstitutionLane.ROLE]),
        procedure_rows=tuple(lanes[InstitutionLane.PROCEDURE]),
        expectation_rows=tuple(lanes[InstitutionLane.EXPECTATION]),
        legitimacy_rows=tuple(lanes[InstitutionLane.LEGITIMACY]),
        succession_rows=tuple(lanes[InstitutionLane.SUCCESSION]),
        continuity_rows=tuple(lanes[InstitutionLane.CONTINUITY]),
        known_person_ids=evidence.institution_known_person_ids,
        tick=window.end_tick.value,
    )
    persistence = compute_institutional_persistence(result)
    document = compute_institutional_persistence_metric(
        persistence,
        run_id=evidence.run_id,
        input_revision=evidence.input_revision,
    )
    value = _number(document, "persistent_institution_like_count")
    candidate_count = _number(document, "candidate_count") or 0.0
    refs = (
        *refs,
        f"algorithm:{document.algorithm_version}",
        "witness:complete-empty-search",
    )
    if value is None:
        return _unknown(
            selector,
            "missing_institution_result",
            coverage="unknown",
            refs=refs,
        )
    if value == 0.0 and candidate_count == 0.0:
        return _row(
            selector=selector,
            value=0.0,
            availability=OutcomeAvailability.KNOWN_ZERO,
            coverage="complete",
            reason_code="complete_empty_candidate_search",
            evidence_refs=refs,
        )
    if value == 0.0:
        return _row(
            selector=selector,
            value=0.0,
            availability=OutcomeAvailability.PARTIAL,
            coverage="complete",
            reason_code="no_persistent_candidate",
            evidence_refs=refs,
        )
    return _row(
        selector=selector,
        value=value,
        availability=OutcomeAvailability.PRESENT,
        coverage="complete",
        reason_code=None,
        evidence_refs=refs,
    )


def _cultural_measurement(
    evidence: PathDependenceEvidence,
    selector: OutcomeSelector,
    window: OutcomeWindow,
    *,
    measurement_id: str,
    dimension: str,
    representation: str,
) -> PathDependenceOutcomeRow:
    inputs = evidence.cultural_inputs
    if inputs is None:
        return _unknown(selector, "missing_cultural_evidence")
    baseline = window.fork_tick.value
    endpoint = window.end_tick.value
    if endpoint <= baseline:
        return _unknown(selector, "invalid_cultural_window")
    scoped = replace(
        inputs,
        window=CulturalAnalysisWindow(
            baseline_boundary=baseline,
            end_boundary=endpoint,
        ),
    )
    calculator = (
        compute_cultural_narrative_survival
        if dimension == "narrative"
        else compute_cultural_technology_continuity
    )
    measurements = calculator(scoped)
    matches = tuple(
        measurement
        for measurement in measurements
        if measurement.measurement_id == measurement_id
        and measurement.dimension == dimension
        and measurement.representation == representation
        and measurement.scope == "global"
        and measurement.partition_id is None
        and not measurement.group_ids
        and measurement.trait_id is None
    )
    if len(matches) != 1:
        raise PathDependenceValidationError(
            "outcome_duplicate_measurement"
            if matches
            else "outcome_basis_mismatch",
            "cultural overall measurement selection is ambiguous",
        )
    measurement = matches[0]
    refs = (
        f"algorithm:{measurement.algorithm_version}",
        f"baseline:{baseline}",
        f"endpoint:{endpoint}",
    )
    if measurement.value is None:
        censoring = (
            "left" if measurement.left_censored else "right"
            if measurement.right_censored
            else None
        )
        return _unknown(
            selector,
            measurement.reason_code or "missing_cultural_measurement",
            coverage="unknown",
            censoring=censoring,
            refs=refs,
        )
    return _row(
        selector=selector,
        value=measurement.value,
        availability=_availability(measurement.availability),
        coverage=(
            "complete"
            if measurement.coverage_expected is not None
            and measurement.coverage_observed == measurement.coverage_expected
            else "partial"
        ),
        reason_code=None,
        evidence_refs=refs,
    )


def _resource(
    evidence: PathDependenceEvidence,
    selector: OutcomeSelector,
    window: OutcomeWindow,
    *,
    key: str,
) -> PathDependenceOutcomeRow:
    living = set(evidence.living_agent_ids)
    holdings = (
        tuple(row for row in evidence.resource_holdings if row.agent_id in living)
        if living
        else evidence.resource_holdings
    )
    if not holdings:
        return _unknown(selector, "empty_living_population")
    document = compute_resource_inequality(
        holdings,
        run_id=evidence.run_id,
        input_revision=evidence.input_revision,
        measure_id=ResourceMeasureId.INVENTORY_COUNT,
    )
    value = _number(document, key)
    refs = (
        f"algorithm:{document.algorithm_version}",
        f"endpoint:{window.end_tick.value}",
    )
    if value is None:
        return _unknown(
            selector,
            "missing_resource_measure",
            coverage="unknown",
            refs=refs,
        )
    return _row(
        selector=selector,
        value=value,
        availability=_availability(document.availability),
        coverage="complete" if document.coverage is not None else "missing",
        reason_code=None,
        evidence_refs=refs,
    )


def _cooperation(
    evidence: PathDependenceEvidence,
    selector: OutcomeSelector,
    window: OutcomeWindow,
) -> PathDependenceOutcomeRow:
    if not evidence.action_rows:
        return _unknown(selector, "no_applied_actions")
    agents = evidence.action_agent_ids or evidence.living_agent_ids
    if not agents:
        return _unknown(selector, "missing_action_population")
    document = compute_cooperation(
        evidence.action_rows,
        run_id=evidence.run_id,
        input_revision=evidence.input_revision,
        agent_ids=agents,
        window_start=window.start_tick.value,
        window_end=window.end_tick.value - 1,
        death_ticks=dict(evidence.action_death_ticks),
    )
    value = _number(document, "coop_occurrence_rate")
    refs = (
        f"algorithm:{document.algorithm_version}",
        f"window:{window.start_tick.value}-{window.end_tick.value}",
    )
    if value is None:
        return _unknown(
            selector,
            "missing_cooperation_measure",
            coverage="unknown",
            refs=refs,
        )
    return _row(
        selector=selector,
        value=value,
        availability=_availability(document.availability),
        coverage="complete" if document.coverage is not None else "missing",
        reason_code=None,
        evidence_refs=refs,
    )


def _compute_selector(
    evidence: PathDependenceEvidence,
    selector: OutcomeSelector,
    window: OutcomeWindow,
) -> PathDependenceOutcomeRow:
    selector_id = selector.selector_id
    if selector_id == "norms.active_beliefs":
        return _norm_active(evidence, selector, window)
    if selector_id == "norms.belief_persistence":
        return _norm_persistence(evidence, selector, window)
    if selector_id == "relationships.mean_abs_delta":
        return _relationship_delta(evidence, selector, window)
    if selector_id == "institutions.persistent_candidates":
        return _institution_candidates(evidence, selector, window)
    if selector_id == "technology.living_retention":
        return _cultural_measurement(
            evidence,
            selector,
            window,
            measurement_id="living_retention",
            dimension="technology",
            representation="practical_content_key",
        )
    if selector_id == "narratives.endpoint_persistence":
        return _cultural_measurement(
            evidence,
            selector,
            window,
            measurement_id="endpoint_persistence",
            dimension="narrative",
            representation="narrative_lineage",
        )
    if selector_id == "inequality.resource_gini":
        return _resource(evidence, selector, window, key="gini")
    if selector_id == "inequality.resource_theil":
        return _resource(evidence, selector, window, key="theil_t")
    if selector_id == "cooperation.applied_rate":
        return _cooperation(evidence, selector, window)
    raise PathDependenceValidationError(
        "unknown_outcome_selector", f"unknown selector {selector_id}"
    )


def compute_path_dependence_outcomes(
    evidence: PathDependenceEvidence,
    selectors: tuple[OutcomeSelector, ...],
    windows: tuple[OutcomeWindow, ...],
) -> tuple[PathDependenceOutcomeRow, ...]:
    """Compute every predeclared selector from detached evidence or an oracle."""
    if type(evidence) is not PathDependenceEvidence:
        raise TypeError("evidence must be PathDependenceEvidence")
    window_by_id = {window.window_id: window for window in windows}
    if len(window_by_id) != len(windows):
        raise PathDependenceValidationError(
            "invalid_window", "duplicate window id"
        )
    supplied: dict[tuple[str, str], OutcomeMeasurement] = {}
    for supplied_measurement in evidence.measurements:
        selector_id = supplied_measurement.selector_id
        if selector_id not in SELECTOR_REGISTRY:
            raise PathDependenceValidationError(
                "unknown_outcome_selector", f"unknown selector {selector_id}"
            )
        if supplied_measurement.window_id not in window_by_id:
            raise PathDependenceValidationError(
                "invalid_window", "measurement references unknown window"
            )
        key = (selector_id, supplied_measurement.window_id)
        if key in supplied:
            raise PathDependenceValidationError(
                "outcome_duplicate_measurement", "duplicate measurement"
            )
        supplied[key] = supplied_measurement
    rows: list[PathDependenceOutcomeRow] = []
    seen: set[tuple[str, str]] = set()
    for selector in selectors:
        expected_domain = SELECTOR_REGISTRY.get(selector.selector_id)
        if expected_domain is None:
            raise PathDependenceValidationError(
                "unknown_outcome_selector",
                f"unknown selector {selector.selector_id}",
            )
        if expected_domain is not selector.domain:
            raise PathDependenceValidationError(
                "outcome_basis_mismatch", "selector domain mismatch"
            )
        if selector.window_id not in window_by_id:
            raise PathDependenceValidationError(
                "invalid_window", "selector references unknown window"
            )
        key = (selector.selector_id, selector.window_id)
        if key in seen:
            raise PathDependenceValidationError(
                "outcome_duplicate_measurement", "duplicate selector row"
            )
        seen.add(key)
        measurement = supplied.get(key)
        if measurement is not None:
            rows.append(
                PathDependenceOutcomeRow(
                    selector_id=selector.selector_id,
                    domain=selector.domain,
                    window_id=selector.window_id,
                    value=measurement.value,
                    availability=measurement.availability,
                    coverage=measurement.coverage,
                    censoring=measurement.censoring,
                    reason_code=measurement.reason_code,
                    evidence_refs=measurement.evidence_refs,
                )
            )
            continue
        rows.append(
            _compute_selector(
                evidence, selector, window_by_id[selector.window_id]
            )
        )
    _LOG.info(
        "path_dependence_outcomes_computed selector_count=%s "
        "present=%s unknown=%s",
        len(rows),
        sum(
            1
            for row in rows
            if row.availability
            in (OutcomeAvailability.PRESENT, OutcomeAvailability.KNOWN_ZERO)
        ),
        sum(
            1
            for row in rows
            if row.availability is OutcomeAvailability.UNKNOWN
        ),
    )
    return tuple(rows)


__all__ = ["compute_path_dependence_outcomes"]
