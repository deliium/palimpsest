"""symbolic_social_distribution@1 reports descriptive divergence only."""

from __future__ import annotations

from types import SimpleNamespace

from analysis.models import MetricAvailability
from analysis.symbolic_language_metrics import (
    SymbolicAnalysisInputs,
    SymbolicCompositionRow,
    SymbolicMessageRow,
    compute_symbolic_social_distribution,
    compute_symbolic_social_distribution_metric,
    symbolic_surface_digest,
)


def _row(owner: str, token: str) -> SymbolicCompositionRow:
    other = "delta" if token == "gamma" else "beta"
    return SymbolicCompositionRow(
        owner_id=owner,
        composition_id=(owner + token) * 12,
        kind="relational",
        part_digests=(symbolic_surface_digest(token), symbolic_surface_digest(other)),
        referent_kind="location",
        status="active",
        strength_band="mid",
        usage_count=0,
        tick_range=(0, 1),
    )


def _community(community_id: str, people: tuple[str, ...]) -> object:
    return SimpleNamespace(community_id=community_id, person_ids=people)


def test_isolated_communities_show_divergence() -> None:
    inputs = SymbolicAnalysisInputs(
        compositions=(_row("a", "alpha"), _row("b", "gamma")),
        communities=(_community("c1", ("a",)), _community("c2", ("b",))),
    )
    result = compute_symbolic_social_distribution(inputs)
    assert result.community_count == 2
    assert result.pairwise_divergence == 1.0
    assert result.borrowed_digest_count == 0


def test_cross_community_delivery_counts_borrowing() -> None:
    inputs = SymbolicAnalysisInputs(
        compositions=(_row("a", "alpha"), _row("b", "alpha")),
        messages=(
            SymbolicMessageRow(
                message_id="m1",
                speaker_id="a",
                listener_id="b",
                tick=1,
                kind="relational",
                part_digests=(
                    symbolic_surface_digest("alpha"),
                    symbolic_surface_digest("beta"),
                ),
                parse_outcome="parsed",
                declared_confidence_band="mid",
            ),
        ),
        communities=(_community("c1", ("a",)), _community("c2", ("b",))),
    )
    result = compute_symbolic_social_distribution(inputs)
    assert result.borrowed_digest_count == 2
    assert result.availability is MetricAvailability.PRESENT


def test_missing_communities_is_absent_not_zero() -> None:
    inputs = SymbolicAnalysisInputs(compositions=(_row("a", "alpha"),))
    result = compute_symbolic_social_distribution(inputs)
    assert result.availability is MetricAvailability.ABSENT
    document = compute_symbolic_social_distribution_metric(
        result, run_id="run-1", input_revision="rev-1"
    )
    assert document.availability is MetricAvailability.ABSENT
