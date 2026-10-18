"""semantic_drift@1 describes recorded changes and usage contexts."""

from __future__ import annotations

from analysis.models import MetricAvailability
from analysis.semantic_drift_metrics import (
    SemanticAnalysisInputs,
    SemanticSenseRow,
    SemanticUsageRow,
    compute_semantic_drift,
    compute_semantic_drift_metric,
)


def _sense(
    *,
    referent: str | None = "ref-a",
    associated: tuple[str, ...] = ("assoc-a",),
    tick: int = 1,
    revision: int = 0,
    trigger: str = "promoted",
) -> SemanticSenseRow:
    return SemanticSenseRow(
        owner_id="owner-a",
        term_digest="term-a",
        term_source="label",
        referent_kind="location",
        referent_digest=referent,
        associated_digests=associated,
        tick=tick,
        sense_revision=revision,
        trigger=trigger,
    )


def _usage(tick: int, channel: str = "observed") -> SemanticUsageRow:
    return SemanticUsageRow(
        owner_id="owner-a",
        term_digest="term-a",
        term_source="label",
        tick=tick,
        channel=channel,
        actor_digest=None,
        referent_digest=None,
    )


def test_shifted_trigger_increments_transition_and_referent_switch() -> None:
    inputs = SemanticAnalysisInputs(
        senses=(
            _sense(tick=1, referent="ref-a"),
            _sense(tick=2, referent="ref-b", trigger="shifted", revision=1),
        )
    )
    result = compute_semantic_drift(inputs)
    assert result.transition_count == 1
    assert result.referent_switch_count == 1
    assert result.drift_rate == 1.0
    assert result.revision_count == 1


def test_association_only_change_does_not_count_as_referent_switch() -> None:
    inputs = SemanticAnalysisInputs(
        senses=(
            _sense(tick=1, associated=("assoc-a",)),
            _sense(tick=2, associated=("assoc-b",), trigger="merged"),
        )
    )
    result = compute_semantic_drift(inputs)
    assert result.transition_count == 1
    assert result.referent_switch_count == 0
    assert result.association_change_count == 1
    assert result.drift_rate == 0.0
    assert result.mean_jaccard_distance == 1.0


def test_usage_rows_do_not_double_count_transitions() -> None:
    inputs = SemanticAnalysisInputs(
        senses=(
            _sense(tick=1),
            _sense(tick=2, revision=1),
        ),
        usages=(
            _usage(1, "observed"),
            _usage(2, "communicated"),
            _usage(2, "communicated"),
        ),
    )
    result = compute_semantic_drift(inputs)
    assert result.transition_count == 1
    assert result.usage_context_count == 3
    assert dict(result.channel_counts) == {"communicated": 2, "observed": 1}


def test_zero_transitions_produce_zero_counts_and_no_rate() -> None:
    inputs = SemanticAnalysisInputs(senses=(_sense(),))
    result = compute_semantic_drift(inputs)
    assert result.transition_count == 0
    assert result.referent_switch_count == 0
    assert result.drift_rate is None
    assert result.availability is MetricAvailability.PRESENT
    document = compute_semantic_drift_metric(
        result, run_id="run-a", input_revision="rev-a"
    )
    assert "drift_rate" not in document.values


def test_empty_input_yields_absent() -> None:
    result = compute_semantic_drift(SemanticAnalysisInputs())
    assert result.availability is MetricAvailability.ABSENT
    assert result.transition_count == 0


def test_multiple_referents_are_counted_once_per_term() -> None:
    inputs = SemanticAnalysisInputs(
        senses=(
            _sense(tick=1, referent="ref-a"),
            _sense(tick=2, referent="ref-b", trigger="shifted"),
            _sense(tick=3, referent="ref-c", trigger="shifted"),
        )
    )
    result = compute_semantic_drift(inputs)
    assert result.multi_referent_term_count == 1
    assert result.transition_count == 2
