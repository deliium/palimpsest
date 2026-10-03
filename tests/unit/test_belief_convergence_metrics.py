"""Belief convergence metric tests."""

from __future__ import annotations

from analysis.belief_convergence_metrics import (
    claim_overlap_token,
    compute_belief_convergence,
)
from analysis.models import BeliefClaimRow, MetricAvailability


def _claim(
    owner: str,
    claim_id: str,
    tick: int,
    *,
    categorical: str = "yes",
    active: bool = True,
) -> BeliefClaimRow:
    return BeliefClaimRow(
        owner_id=owner,
        belief_id=f"b-{owner}-{claim_id}",
        claim_id=claim_id,
        logical_tick=tick,
        activation_state="active" if active else "retired",
        confidence=0.8,
        value_kind="categorical",
        categorical_value=categorical,
    )


def test_overlap_token_ignores_inactive() -> None:
    row = _claim("a", "c1", 1, active=False)
    assert claim_overlap_token(row) is None


def test_empty_or_single_owner_absent() -> None:
    empty = compute_belief_convergence([], run_id="run-b", input_revision="rev-1")
    assert empty.availability is MetricAvailability.ABSENT
    one = compute_belief_convergence(
        [_claim("a", "c1", 1)], run_id="run-b", input_revision="rev-1"
    )
    assert one.availability is MetricAvailability.ABSENT


def test_convergence_jaccard_increases() -> None:
    rows = [
        _claim("a", "c1", 1, categorical="yes"),
        _claim("b", "c2", 1, categorical="no"),
        _claim("a", "c1", 2, categorical="yes"),
        _claim("b", "c1", 2, categorical="yes"),
        _claim("a", "c2", 2, categorical="no"),
        _claim("b", "c2", 2, categorical="no"),
    ]
    doc = compute_belief_convergence(rows, run_id="run-b", input_revision="rev-1")
    assert doc.availability is MetricAvailability.PRESENT
    assert doc.values["owner_count"] == 2
    assert doc.values["mean_pairwise_jaccard_final"] == 1.0
    assert float(doc.values["mean_pairwise_jaccard_delta"]) > 0.0
