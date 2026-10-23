"""Closed seven-domain scalar outcome projection."""

from __future__ import annotations

import pytest

from analysis.path_dependence_models import (
    OutcomeAvailability,
    OutcomeMeasurement,
    PathDependenceEvidence,
    compute_path_dependence_outcomes,
)
from experiments.path_dependence_models import (
    OutcomeDomain,
    OutcomeSelector,
    OutcomeWindow,
    PathDependenceValidationError,
)
from simulation.clock import Tick

pytestmark = pytest.mark.unit

WINDOW = OutcomeWindow("win", Tick(4), Tick(4), Tick(36))
SELECTORS = (
    OutcomeSelector("norms.active_beliefs", OutcomeDomain.NORMS, "win"),
    OutcomeSelector("relationships.mean_abs_delta", OutcomeDomain.RELATIONSHIPS, "win"),
    OutcomeSelector(
        "institutions.persistent_candidates", OutcomeDomain.INSTITUTIONS, "win"
    ),
    OutcomeSelector("technology.living_retention", OutcomeDomain.TECHNOLOGY, "win"),
    OutcomeSelector(
        "narratives.endpoint_persistence", OutcomeDomain.CULTURAL_NARRATIVES, "win"
    ),
    OutcomeSelector("inequality.resource_gini", OutcomeDomain.INEQUALITY, "win"),
    OutcomeSelector("inequality.resource_theil", OutcomeDomain.INEQUALITY, "win"),
    OutcomeSelector("cooperation.applied_rate", OutcomeDomain.COOPERATION, "win"),
)


def _measurement(
    selector_id: str,
    value: float | None,
    availability: OutcomeAvailability,
    *,
    refs: tuple[str, ...] = (),
) -> OutcomeMeasurement:
    return OutcomeMeasurement(
        selector_id=selector_id,
        window_id="win",
        value=value,
        availability=availability,
        evidence_refs=refs,
    )


def test_all_seven_domains_emit_explicit_rows() -> None:
    rows = compute_path_dependence_outcomes(
        PathDependenceEvidence(()), SELECTORS, (WINDOW,)
    )
    assert len(rows) == 8
    assert {row.domain for row in rows} == set(OutcomeDomain)
    assert all(row.availability is OutcomeAvailability.UNKNOWN for row in rows)
    assert all(row.reason_code == "missing_measurement" for row in rows)


def test_present_known_zero_and_witness_survive_projection() -> None:
    evidence = PathDependenceEvidence(
        (
            _measurement(
                "norms.active_beliefs", 3.5, OutcomeAvailability.PRESENT
            ),
            _measurement(
                "institutions.persistent_candidates",
                0.0,
                OutcomeAvailability.KNOWN_ZERO,
                refs=("complete-empty-search",),
            ),
        )
    )
    rows = {
        row.selector_id: row
        for row in compute_path_dependence_outcomes(
            evidence, SELECTORS, (WINDOW,)
        )
    }
    assert rows["norms.active_beliefs"].value == 3.5
    assert rows["norms.active_beliefs"].availability is OutcomeAvailability.PRESENT
    zero = rows["institutions.persistent_candidates"]
    assert zero.availability is OutcomeAvailability.KNOWN_ZERO
    assert zero.value == 0.0
    assert zero.evidence_refs == ("complete-empty-search",)


def test_unknown_selector_duplicate_and_nonfinite_fail_closed() -> None:
    with pytest.raises(PathDependenceValidationError, match="unknown_outcome_selector"):
        compute_path_dependence_outcomes(
            PathDependenceEvidence(()),
            (OutcomeSelector("norms.unknown", OutcomeDomain.NORMS, "win"),),
            (WINDOW,),
        )
    duplicate = PathDependenceEvidence(
        (
            _measurement("norms.active_beliefs", 1.0, OutcomeAvailability.PRESENT),
            _measurement("norms.active_beliefs", 2.0, OutcomeAvailability.PRESENT),
        )
    )
    with pytest.raises(
        PathDependenceValidationError, match="outcome_duplicate_measurement"
    ):
        compute_path_dependence_outcomes(duplicate, SELECTORS, (WINDOW,))
    with pytest.raises(PathDependenceValidationError, match="outcome_nonfinite"):
        _measurement(
            "norms.active_beliefs", float("nan"), OutcomeAvailability.PRESENT
        )
    with pytest.raises(PathDependenceValidationError, match="outcome_basis_mismatch"):
        _measurement(
            "institutions.persistent_candidates",
            1.0,
            OutcomeAvailability.KNOWN_ZERO,
            refs=("witness",),
        )


def test_domain_mismatch_is_rejected() -> None:
    with pytest.raises(PathDependenceValidationError, match="outcome_basis_mismatch"):
        compute_path_dependence_outcomes(
            PathDependenceEvidence(()),
            (
                OutcomeSelector(
                    "norms.active_beliefs",
                    OutcomeDomain.TECHNOLOGY,
                    "win",
                ),
            ),
            (WINDOW,),
        )
