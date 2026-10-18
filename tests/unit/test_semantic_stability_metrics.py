"""semantic_stability@1 counts retention without forcing convergence."""

from __future__ import annotations

from analysis.models import MetricAvailability
from analysis.semantic_drift_metrics import (
    SemanticAnalysisInputs,
    SemanticSenseRow,
    compute_semantic_stability,
    compute_semantic_stability_metric,
)


def _row(
    *,
    owner: str = "owner-a",
    term: str = "term-a",
    referent: str | None = "ref-a",
    associated: tuple[str, ...] = ("assoc-a",),
    tick: int = 1,
    revision: int = 0,
    trigger: str = "promoted",
) -> SemanticSenseRow:
    return SemanticSenseRow(
        owner_id=owner,
        term_digest=term,
        term_source="label",
        referent_kind="location",
        referent_digest=referent,
        associated_digests=associated,
        tick=tick,
        sense_revision=revision,
        trigger=trigger,
    )


def test_zero_transitions_report_full_stability_where_defined() -> None:
    inputs = SemanticAnalysisInputs(
        senses=(_row(tick=1), _row(tick=2, revision=1)), expected_owner_count=1
    )
    result = compute_semantic_stability(inputs)
    assert result.transition_count == 1
    assert result.stable_referent_count == 1
    assert result.stable_association_count == 1
    assert result.retained_transition_count == 1
    assert result.availability is MetricAvailability.PRESENT
    assert result.coverage.ratio == 1.0


def test_referent_switch_lowers_only_referent_stability() -> None:
    inputs = SemanticAnalysisInputs(
        senses=(
            _row(tick=1, referent="ref-a"),
            _row(tick=2, referent="ref-b", trigger="shifted", revision=1),
        )
    )
    result = compute_semantic_stability(inputs)
    assert result.stable_referent_count == 0
    assert result.stable_association_count == 1
    assert result.retained_transition_count == 0


def test_terms_with_one_sense_do_not_enter_stability_denominators() -> None:
    inputs = SemanticAnalysisInputs(senses=(_row(),))
    result = compute_semantic_stability(inputs)
    assert result.term_count == 1
    assert result.availability is MetricAvailability.ABSENT


def test_missing_generation_data_leaves_generation_measure_absent() -> None:
    inputs = SemanticAnalysisInputs(
        senses=(_row(tick=1), _row(tick=2, revision=1))
    )
    result = compute_semantic_stability(inputs)
    assert result.cross_generation_term_count == 0
    assert result.cross_generation_stable_count == 0
    document = compute_semantic_stability_metric(
        result, run_id="run-a", input_revision="rev-a"
    )
    assert "cross_generation_stability_rate" not in document.values


def test_cross_generation_stability_uses_real_generation_map() -> None:
    inputs = SemanticAnalysisInputs(
        senses=(
            _row(owner="owner-a", tick=1),
            _row(owner="owner-b", tick=2),
        ),
        generation_index_by_owner={"owner-a": 0, "owner-b": 1},
    )
    result = compute_semantic_stability(inputs)
    assert result.cross_generation_term_count == 1
    assert result.cross_generation_stable_count == 1
    document = compute_semantic_stability_metric(
        result, run_id="run-a", input_revision="rev-a"
    )
    assert document.values["cross_generation_stability_rate"] == 1.0


def test_identical_inputs_produce_identical_documents() -> None:
    inputs = SemanticAnalysisInputs(
        senses=(_row(tick=1), _row(tick=2, revision=1))
    )
    first = compute_semantic_stability_metric(
        compute_semantic_stability(inputs), run_id="run-a", input_revision="rev-a"
    )
    second = compute_semantic_stability_metric(
        compute_semantic_stability(inputs), run_id="run-a", input_revision="rev-a"
    )
    assert first == second
