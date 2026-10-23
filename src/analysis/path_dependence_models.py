"""Detached seven-domain outcome rows for historical-contingency comparisons."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from analysis.cultural_evolution_evidence import CulturalEvolutionInputs
from analysis.institution_emergence import InstitutionLaneRow
from analysis.models import AppliedActionRow, RelationshipEdgeRow, ResourceHoldingRow
from analysis.path_dependence_contracts import (
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
    """Detached inputs for the closed outcome selectors.

    ``measurements`` carries caller-supplied oracle values. Every other field is
    raw detached evidence used only when the matching measurement is absent.
    """

    measurements: tuple[OutcomeMeasurement, ...] = ()
    run_id: str = "path-dependence-evidence"
    input_revision: str = "revision-0"
    norm_rows: Mapping[str, object] | None = None
    norm_history: tuple[object, ...] = ()
    norm_coverage_complete: bool = False
    relationship_rows: tuple[RelationshipEdgeRow, ...] = ()
    relationship_death_ticks: tuple[tuple[str, int], ...] = ()
    institution_lane_rows: tuple[InstitutionLaneRow, ...] = ()
    institution_known_person_ids: tuple[str, ...] = ()
    institution_complete_search: bool = False
    cultural_inputs: CulturalEvolutionInputs | None = None
    resource_holdings: tuple[ResourceHoldingRow, ...] = ()
    living_agent_ids: tuple[str, ...] = ()
    action_rows: tuple[AppliedActionRow, ...] = ()
    action_agent_ids: tuple[str, ...] = ()
    action_death_ticks: tuple[tuple[str, int], ...] = ()

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
        for name in ("run_id", "input_revision"):
            value = getattr(self, name)
            if type(value) is not str or not value:
                raise PathDependenceValidationError(
                    "outcome_basis_mismatch", f"invalid {name}"
                )
        if type(self.norm_coverage_complete) is not bool:
            raise PathDependenceValidationError(
                "outcome_basis_mismatch", "invalid norm coverage"
            )
        if type(self.institution_complete_search) is not bool:
            raise PathDependenceValidationError(
                "outcome_basis_mismatch", "invalid institution search flag"
            )
        for name, model in (
            ("relationship_rows", RelationshipEdgeRow),
            ("institution_lane_rows", InstitutionLaneRow),
            ("resource_holdings", ResourceHoldingRow),
            ("action_rows", AppliedActionRow),
        ):
            values = tuple(getattr(self, name))
            for value in values:
                if type(value) is not model:
                    raise PathDependenceValidationError(
                        "outcome_basis_mismatch", f"invalid {name}"
                    )
            object.__setattr__(self, name, values)
        for name in (
            "norm_history",
            "institution_known_person_ids",
            "living_agent_ids",
            "action_agent_ids",
        ):
            object.__setattr__(self, name, tuple(getattr(self, name)))
        for name in ("relationship_death_ticks", "action_death_ticks"):
            rows: list[tuple[str, int]] = []
            for entry in getattr(self, name):
                if not isinstance(entry, tuple) or len(entry) != 2:
                    raise PathDependenceValidationError(
                        "outcome_basis_mismatch", f"invalid {name}"
                    )
                agent_id, tick = entry
                if (
                    type(agent_id) is not str
                    or not agent_id
                    or isinstance(tick, bool)
                    or type(tick) is not int
                    or tick < 0
                ):
                    raise PathDependenceValidationError(
                        "outcome_basis_mismatch", f"invalid {name}"
                    )
                rows.append((agent_id, tick))
            object.__setattr__(self, name, tuple(rows))
        if self.cultural_inputs is not None and (
            type(self.cultural_inputs) is not CulturalEvolutionInputs
        ):
            raise PathDependenceValidationError(
                "outcome_basis_mismatch", "invalid cultural inputs"
            )


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
    """Project every requested selector to a scalar row or explicit unknown.

    Implementation lives in ``analysis.path_dependence_outcomes`` to keep this
    module limited to detached row contracts. Imported lazily to avoid a module
    cycle with the calculator registry.
    """
    from analysis.path_dependence_outcomes import (
        compute_path_dependence_outcomes as _compute,
    )

    return _compute(evidence, selectors, windows)


__all__ = [
    "OUTCOME_SCHEMA_VERSION",
    "SELECTOR_REGISTRY",
    "OutcomeAvailability",
    "OutcomeMeasurement",
    "PathDependenceEvidence",
    "PathDependenceOutcomeRow",
    "compute_path_dependence_outcomes",
]
