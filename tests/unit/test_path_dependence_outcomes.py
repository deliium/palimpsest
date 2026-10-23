"""Closed seven-domain scalar outcome projection."""

from __future__ import annotations

import pytest

from analysis.institution_emergence import InstitutionLane, InstitutionLaneRow
from analysis.models import (
    AppliedActionRow,
    RelationshipEdgeRow,
    ResourceHoldingRow,
)
from analysis.objective_metrics import compute_cooperation, compute_resource_inequality
from analysis.path_dependence_models import (
    OutcomeAvailability,
    OutcomeMeasurement,
    PathDependenceEvidence,
    compute_path_dependence_outcomes,
)
from analysis.relationship_metrics import compute_relationship_stability
from analysis.social_norm_metrics import (
    compute_emergent_social_norms,
    compute_norm_persistence,
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
    OutcomeSelector("norms.belief_persistence", OutcomeDomain.NORMS, "win"),
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
    assert len(rows) == 9
    assert {row.domain for row in rows} == set(OutcomeDomain)
    assert all(row.availability is OutcomeAvailability.UNKNOWN for row in rows)
    assert all(row.reason_code for row in rows)
    assert {row.reason_code for row in rows} >= {
        "missing_norm_evidence",
        "insufficient_norm_readings",
        "no_relationship_delta",
        "incomplete_candidate_search",
        "missing_cultural_evidence",
        "empty_living_population",
        "no_applied_actions",
    }


def test_present_known_zero_and_witness_survive_projection() -> None:
    evidence = PathDependenceEvidence(
        (
            _measurement("norms.active_beliefs", 3.5, OutcomeAvailability.PRESENT),
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
        for row in compute_path_dependence_outcomes(evidence, SELECTORS, (WINDOW,))
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
        _measurement("norms.active_beliefs", float("nan"), OutcomeAvailability.PRESENT)
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


def _selector(selector_id: str, domain: OutcomeDomain) -> OutcomeSelector:
    return OutcomeSelector(selector_id, domain, "win")


def test_norm_active_beliefs_matches_direct_calculator_and_known_empty() -> None:
    belief_rows = (
        {
            "tick": 8,
            "owner_id": "agent-a",
            "pattern": "share_food",
            "status": "active",
            "confidence": 0.9,
        },
        {
            "tick": 8,
            "owner_id": "agent-b",
            "pattern": "share_food",
            "status": "candidate",
            "confidence": 0.5,
        },
    )
    evidence = PathDependenceEvidence(
        norm_rows={"belief_rows": belief_rows},
        norm_coverage_complete=True,
    )
    (row,) = compute_path_dependence_outcomes(
        evidence,
        (_selector("norms.active_beliefs", OutcomeDomain.NORMS),),
        (WINDOW,),
    )
    oracle = compute_emergent_social_norms(
        {"belief_rows": belief_rows},
        run_id=evidence.run_id,
        input_revision=evidence.input_revision,
        tick=8,
    )
    assert row.value == oracle.values["active_belief_count"]
    assert row.availability is OutcomeAvailability.PRESENT

    empty = PathDependenceEvidence(
        norm_rows={"belief_rows": ()},
        norm_coverage_complete=True,
    )
    (zero,) = compute_path_dependence_outcomes(
        empty,
        (_selector("norms.active_beliefs", OutcomeDomain.NORMS),),
        (WINDOW,),
    )
    assert zero.value == 0.0
    assert zero.availability is OutcomeAvailability.KNOWN_ZERO


def test_norm_belief_persistence_matches_direct_calculator() -> None:
    active = {
        "status": "active",
        "confidence": 0.9,
        "owner_id": "agent-a",
        "pattern": "share_food",
    }
    history = (
        {"rates": {}, "beliefs": (active,)},
        {"rates": {}, "beliefs": (active,)},
    )
    evidence = PathDependenceEvidence(norm_history=history)
    (row,) = compute_path_dependence_outcomes(
        evidence,
        (_selector("norms.belief_persistence", OutcomeDomain.NORMS),),
        (WINDOW,),
    )
    oracle = compute_norm_persistence(
        history,
        run_id=evidence.run_id,
        input_revision=evidence.input_revision,
        tick=WINDOW.end_tick.value,
    )
    assert row.value == oracle.values["belief_persistence"]
    assert row.availability is OutcomeAvailability.PRESENT
    assert row.evidence_refs == (
        f"algorithm:{oracle.algorithm_version}",
        "readings:2",
    )

    (unknown,) = compute_path_dependence_outcomes(
        PathDependenceEvidence(norm_history=(history[0],)),
        (_selector("norms.belief_persistence", OutcomeDomain.NORMS),),
        (WINDOW,),
    )
    assert unknown.availability is OutcomeAvailability.UNKNOWN
    assert unknown.reason_code == "insufficient_norm_readings"


def test_relationship_predecessor_and_window_boundaries_match_direct_call() -> None:
    rows = (
        RelationshipEdgeRow("agent-a", "agent-b", 2, "active", trust=0.0),
        RelationshipEdgeRow("agent-a", "agent-b", 4, "active", trust=0.5),
        RelationshipEdgeRow("agent-a", "agent-b", 6, "active", trust=1.0),
        RelationshipEdgeRow("agent-a", "agent-b", 8, "active", trust=-1.0),
    )
    window = OutcomeWindow("win", Tick(4), Tick(4), Tick(8))
    evidence = PathDependenceEvidence(relationship_rows=rows)
    (row,) = compute_path_dependence_outcomes(
        evidence,
        (_selector("relationships.mean_abs_delta", OutcomeDomain.RELATIONSHIPS),),
        (window,),
    )
    oracle = compute_relationship_stability(
        rows[:3],
        run_id=evidence.run_id,
        input_revision=evidence.input_revision,
        window_end=7,
    )
    assert row.value == oracle.values["mean_abs_delta"]
    assert row.availability is OutcomeAvailability.PRESENT


def test_relationship_without_in_window_revision_is_unknown() -> None:
    rows = (RelationshipEdgeRow("agent-a", "agent-b", 2, "active", trust=0.0),)
    (row,) = compute_path_dependence_outcomes(
        PathDependenceEvidence(relationship_rows=rows),
        (_selector("relationships.mean_abs_delta", OutcomeDomain.RELATIONSHIPS),),
        (WINDOW,),
    )
    assert row.value is None
    assert row.availability is OutcomeAvailability.UNKNOWN
    assert row.reason_code == "no_relationship_delta"


def test_institution_search_witness_controls_known_zero() -> None:
    selector = _selector(
        "institutions.persistent_candidates", OutcomeDomain.INSTITUTIONS
    )
    (missing,) = compute_path_dependence_outcomes(
        PathDependenceEvidence(institution_complete_search=False),
        (selector,),
        (WINDOW,),
    )
    assert missing.availability is OutcomeAvailability.UNKNOWN
    assert missing.reason_code == "incomplete_candidate_search"

    witness = PathDependenceEvidence(
        institution_complete_search=True,
        institution_lane_rows=(
            InstitutionLaneRow(
                lane=InstitutionLane.ROLE,
                subject_digest="a" * 16,
                evidence_digest="b" * 16,
                tick_start=4,
                tick_end=4,
            ),
        ),
    )
    (partial,) = compute_path_dependence_outcomes(witness, (selector,), (WINDOW,))
    assert partial.availability is OutcomeAvailability.PARTIAL
    assert partial.value == 0.0

    (zero,) = compute_path_dependence_outcomes(
        PathDependenceEvidence(institution_complete_search=True),
        (selector,),
        (WINDOW,),
    )
    assert zero.availability is OutcomeAvailability.KNOWN_ZERO
    assert zero.value == 0.0


def test_resource_and_cooperation_projections_match_direct_calculators() -> None:
    holdings = (
        ResourceHoldingRow("agent-a", 0.0),
        ResourceHoldingRow("agent-b", 3.0),
        ResourceHoldingRow("agent-c", None),
    )
    evidence = PathDependenceEvidence(
        resource_holdings=holdings,
        living_agent_ids=("agent-a", "agent-b", "agent-c"),
        action_rows=(
            AppliedActionRow(4, 0, "agent-a", "give", target_id="agent-b"),
            AppliedActionRow(5, 0, "agent-a", "wait"),
        ),
        action_agent_ids=("agent-a", "agent-b"),
    )
    rows = {
        row.selector_id: row
        for row in compute_path_dependence_outcomes(
            evidence,
            (
                _selector("inequality.resource_gini", OutcomeDomain.INEQUALITY),
                _selector("cooperation.applied_rate", OutcomeDomain.COOPERATION),
            ),
            (WINDOW,),
        )
    }
    resource_oracle = compute_resource_inequality(
        holdings,
        run_id=evidence.run_id,
        input_revision=evidence.input_revision,
    )
    cooperation_oracle = compute_cooperation(
        evidence.action_rows,
        run_id=evidence.run_id,
        input_revision=evidence.input_revision,
        agent_ids=("agent-a", "agent-b"),
        window_start=4,
        window_end=7,
    )
    assert rows["inequality.resource_gini"].value == resource_oracle.values["gini"]
    assert (
        rows["cooperation.applied_rate"].value
        == cooperation_oracle.values["coop_occurrence_rate"]
    )


def test_cooperation_without_actions_is_unknown_not_zero() -> None:
    (row,) = compute_path_dependence_outcomes(
        PathDependenceEvidence(),
        (_selector("cooperation.applied_rate", OutcomeDomain.COOPERATION),),
        (WINDOW,),
    )
    assert row.value is None
    assert row.availability is OutcomeAvailability.UNKNOWN
    assert row.reason_code == "no_applied_actions"
