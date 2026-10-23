"""Detached seven-domain outcome rows for historical-contingency comparisons."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from experiments.path_dependence_models import (
    OutcomeDomain,
    OutcomeSelector,
    OutcomeWindow,
    PathDependenceValidationError,
)

OUTCOME_SCHEMA_VERSION: Final[str] = "path-dependence-outcome-row-v1"


class OutcomeAvailability(StrEnum):
    PRESENT = "present"
    KNOWN_ZERO = "known_zero"
    UNKNOWN = "unknown"
    PARTIAL = "partial"
    CENSORED = "censored"


@dataclass(frozen=True, slots=True)
class OutcomeMeasurement:
    """One already-computed scalar with explicit coverage/evidence identity."""

    selector_id: str
    window_id: str
    value: float | None
    availability: OutcomeAvailability
    evidence_refs: tuple[str, ...] = ()
    coverage: str = "complete"
    censoring: str | None = None
    reason_code: str | None = None

    def __post_init__(self) -> None:
        if type(self.selector_id) is not str or not self.selector_id:
            raise PathDependenceValidationError(
                "unknown_outcome_selector", "invalid selector_id"
            )
        if type(self.window_id) is not str or not self.window_id:
            raise PathDependenceValidationError(
                "invalid_window", "invalid window_id"
            )
        if type(self.availability) is not OutcomeAvailability:
            raise PathDependenceValidationError(
                "outcome_basis_mismatch", "invalid availability"
            )
        if self.value is not None:
            if isinstance(self.value, bool) or not isinstance(
                self.value, (int, float)
            ):
                raise PathDependenceValidationError(
                    "outcome_nonfinite", "invalid value"
                )
            value = float(self.value)
            if not math.isfinite(value):
                raise PathDependenceValidationError(
                    "outcome_nonfinite", "non-finite value"
                )
            object.__setattr__(self, "value", value)
        if self.availability is OutcomeAvailability.KNOWN_ZERO and self.value != 0.0:
            raise PathDependenceValidationError(
                "outcome_basis_mismatch", "known zero requires value zero"
            )
        if self.availability is OutcomeAvailability.PRESENT and self.value is None:
            raise PathDependenceValidationError(
                "outcome_basis_mismatch", "present requires a value"
            )
        if isinstance(self.evidence_refs, (set, frozenset, Mapping)) or not isinstance(
            self.evidence_refs, Sequence
        ):
            raise PathDependenceValidationError(
                "outcome_basis_mismatch", "evidence_refs must be ordered"
            )
        refs = tuple(self.evidence_refs)
        if any(type(ref) is not str or not ref for ref in refs):
            raise PathDependenceValidationError(
                "outcome_basis_mismatch", "invalid evidence ref"
            )
        object.__setattr__(self, "evidence_refs", refs)


@dataclass(frozen=True, slots=True)
class PathDependenceEvidence:
    measurements: tuple[OutcomeMeasurement, ...] = ()

    def __post_init__(self) -> None:
        if isinstance(self.measurements, (set, frozenset, Mapping)) or not isinstance(
            self.measurements, Sequence
        ):
            raise PathDependenceValidationError(
                "outcome_basis_mismatch", "measurements must be ordered"
            )
        measurements = tuple(self.measurements)
        for measurement in measurements:
            if type(measurement) is not OutcomeMeasurement:
                raise PathDependenceValidationError(
                    "outcome_basis_mismatch", "invalid measurement"
                )
        object.__setattr__(self, "measurements", measurements)


@dataclass(frozen=True, slots=True)
class PathDependenceOutcomeRow:
    selector_id: str
    domain: OutcomeDomain
    window_id: str
    value: float | None
    availability: OutcomeAvailability
    coverage: str
    censoring: str | None
    reason_code: str | None
    evidence_refs: tuple[str, ...]
    schema_version: str = OUTCOME_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if type(self.domain) is not OutcomeDomain:
            raise PathDependenceValidationError(
                "outcome_basis_mismatch", "invalid domain"
            )


SELECTOR_REGISTRY: Final[Mapping[str, OutcomeDomain]] = {
    "norms.active_beliefs": OutcomeDomain.NORMS,
    "norms.belief_persistence": OutcomeDomain.NORMS,
    "relationships.mean_abs_delta": OutcomeDomain.RELATIONSHIPS,
    "institutions.persistent_candidates": OutcomeDomain.INSTITUTIONS,
    "technology.living_retention": OutcomeDomain.TECHNOLOGY,
    "narratives.endpoint_persistence": OutcomeDomain.CULTURAL_NARRATIVES,
    "inequality.resource_gini": OutcomeDomain.INEQUALITY,
    "inequality.resource_theil": OutcomeDomain.INEQUALITY,
    "cooperation.applied_rate": OutcomeDomain.COOPERATION,
}


def compute_path_dependence_outcomes(
    evidence: PathDependenceEvidence,
    selectors: tuple[OutcomeSelector, ...],
    windows: tuple[OutcomeWindow, ...],
) -> tuple[PathDependenceOutcomeRow, ...]:
    """Project every requested selector to a scalar row or explicit unknown."""
    if type(evidence) is not PathDependenceEvidence:
        raise TypeError("evidence must be PathDependenceEvidence")
    window_ids = {window.window_id for window in windows}
    measurements: dict[tuple[str, str], OutcomeMeasurement] = {}
    for measurement in evidence.measurements:
        selector_id = measurement.selector_id
        if selector_id not in SELECTOR_REGISTRY:
            raise PathDependenceValidationError(
                "unknown_outcome_selector", f"unknown selector {selector_id}"
            )
        if measurement.window_id not in window_ids:
            raise PathDependenceValidationError(
                "invalid_window", "measurement references unknown window"
            )
        key = (selector_id, measurement.window_id)
        if key in measurements:
            raise PathDependenceValidationError(
                "outcome_duplicate_measurement", "duplicate measurement"
            )
        measurements[key] = measurement
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
        if selector.window_id not in window_ids:
            raise PathDependenceValidationError(
                "invalid_window", "selector references unknown window"
            )
        key = (selector.selector_id, selector.window_id)
        if key in seen:
            raise PathDependenceValidationError(
                "outcome_duplicate_measurement", "duplicate selector row"
            )
        seen.add(key)
        selected_measurement = measurements.get(key)
        if selected_measurement is None:
            rows.append(
                PathDependenceOutcomeRow(
                    selector_id=selector.selector_id,
                    domain=selector.domain,
                    window_id=selector.window_id,
                    value=None,
                    availability=OutcomeAvailability.UNKNOWN,
                    coverage="missing",
                    censoring=None,
                    reason_code="missing_measurement",
                    evidence_refs=(),
                )
            )
            continue
        rows.append(
            PathDependenceOutcomeRow(
                selector_id=selector.selector_id,
                domain=selector.domain,
                window_id=selector.window_id,
                value=selected_measurement.value,
                availability=selected_measurement.availability,
                coverage=selected_measurement.coverage,
                censoring=selected_measurement.censoring,
                reason_code=selected_measurement.reason_code,
                evidence_refs=selected_measurement.evidence_refs,
            )
        )
    return tuple(rows)


__all__ = [
    "OUTCOME_SCHEMA_VERSION",
    "SELECTOR_REGISTRY",
    "OutcomeAvailability",
    "OutcomeMeasurement",
    "PathDependenceEvidence",
    "PathDependenceOutcomeRow",
    "compute_path_dependence_outcomes",
]
