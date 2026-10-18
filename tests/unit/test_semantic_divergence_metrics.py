"""semantic_divergence@1 compares distributions without a correctness claim."""

from __future__ import annotations

from types import SimpleNamespace

from analysis.models import MetricAvailability
from analysis.semantic_drift_metrics import (
    SemanticAnalysisInputs,
    SemanticSenseRow,
    compute_semantic_divergence,
    compute_semantic_divergence_metric,
)


def _row(
    owner: str,
    referent: str | None,
    *,
    term: str = "term-a",
    tick: int = 1,
) -> SemanticSenseRow:
    return SemanticSenseRow(
        owner_id=owner,
        term_digest=term,
        term_source="label",
        referent_kind="location",
        referent_digest=referent,
        associated_digests=(),
        tick=tick,
        sense_revision=0,
        trigger="promoted",
    )


def _community(community_id: str, *owners: str) -> SimpleNamespace:
    return SimpleNamespace(
        community_id=community_id, person_ids=tuple(owners)
    )


def test_two_groups_with_disjoint_referents_show_maximum_divergence() -> None:
    inputs = SemanticAnalysisInputs(
        senses=(
            _row("owner-a", "ref-a"),
            _row("owner-b", "ref-b"),
        ),
        communities=(
            _community("c1", "owner-a"),
            _community("c2", "owner-b"),
        ),
    )
    result = compute_semantic_divergence(inputs)
    assert result.group_count == 2
    assert result.between_group_divergence is not None
    assert result.between_group_divergence > 0.6
    assert result.availability is MetricAvailability.PRESENT


def test_one_group_yields_no_pairwise_value() -> None:
    inputs = SemanticAnalysisInputs(
        senses=(_row("owner-a", "ref-a"), _row("owner-b", "ref-a")),
        communities=(_community("c1", "owner-a", "owner-b"),),
    )
    result = compute_semantic_divergence(inputs)
    assert result.between_group_divergence is None
    assert result.pairwise_divergence == 0.0
    assert result.within_group_divergence == 0.0


def test_absent_groups_and_generations_yield_absent_not_zero() -> None:
    inputs = SemanticAnalysisInputs(senses=(_row("owner-a", "ref-a"),))
    result = compute_semantic_divergence(inputs)
    assert result.availability is MetricAvailability.ABSENT
    assert result.between_group_divergence is None
    assert result.pairwise_divergence is None


def test_unknown_referents_do_not_create_a_shared_unknown_bucket() -> None:
    inputs = SemanticAnalysisInputs(
        senses=(_row("owner-a", None), _row("owner-b", None)),
        communities=(
            _community("c1", "owner-a"),
            _community("c2", "owner-b"),
        ),
    )
    result = compute_semantic_divergence(inputs)
    assert result.unknown_referent_count == 2
    assert result.between_group_divergence is None


def test_term_absent_from_a_generation_is_excluded_from_continuity() -> None:
    inputs = SemanticAnalysisInputs(
        senses=(
            _row("owner-a", "ref-a", term="term-a"),
            _row("owner-b", "ref-b", term="term-b"),
        ),
        generation_index_by_owner={"owner-a": 0, "owner-b": 1},
    )
    result = compute_semantic_divergence(inputs)
    assert result.generation_count == 2
    assert result.cross_generation_continuity is None


def test_cross_generation_continuity_compares_shared_terms() -> None:
    inputs = SemanticAnalysisInputs(
        senses=(
            _row("owner-a", "ref-a", term="term-a"),
            _row("owner-b", "ref-a", term="term-a"),
        ),
        generation_index_by_owner={"owner-a": 0, "owner-b": 1},
    )
    result = compute_semantic_divergence(inputs)
    assert result.cross_generation_continuity == 1.0
    assert result.between_generation_divergence is not None


def test_identical_rows_produce_identical_documents() -> None:
    inputs = SemanticAnalysisInputs(
        senses=(_row("owner-a", "ref-a"), _row("owner-b", "ref-b")),
        communities=(
            _community("c1", "owner-a"),
            _community("c2", "owner-b"),
        ),
    )
    first = compute_semantic_divergence_metric(
        compute_semantic_divergence(inputs),
        run_id="run-a",
        input_revision="rev-a",
    )
    second = compute_semantic_divergence_metric(
        compute_semantic_divergence(inputs),
        run_id="run-a",
        input_revision="rev-a",
    )
    assert first == second
