"""Known-answer and edge-case tests for Task 12 behavior metrics."""

from __future__ import annotations

from analysis.behavior_metrics import (
    compute_behavioral_specialization,
    compute_repeated_conventions,
    motif_token,
)
from analysis.models import AppliedActionRow, MetricAvailability
from analysis.numerical import quantize_float
from analysis.serialization import metric_document_fingerprint


def _q(value: float) -> float:
    return quantize_float(value)


def test_motif_token_is_lexicographic_and_neutral() -> None:
    token = motif_token("move", location_id="loc-a", target_id="tgt-b")
    assert token == "move|loc:loc-a|tgt:tgt-b"
    assert "leader" not in token
    assert "friend" not in token
    assert "culture" not in token


def test_repeated_conventions_known_answer_support() -> None:
    # Two agents each emit move>>wait twice -> motif support 4 for bigram.
    actions: list[AppliedActionRow] = []
    ordinal = 0
    for agent in ("a", "b"):
        for tick in (1, 3):
            actions.append(
                AppliedActionRow(
                    tick=tick, ordinal=ordinal, agent_id=agent, action_kind="move"
                )
            )
            ordinal += 1
            actions.append(
                AppliedActionRow(
                    tick=tick + 1, ordinal=ordinal, agent_id=agent, action_kind="wait"
                )
            )
            ordinal += 1
    doc = compute_repeated_conventions(
        actions, run_id="run-m", input_revision="rev-1", window_end=10
    )
    assert doc.availability is MetricAvailability.PRESENT
    assert doc.values["top_motif_support"] == 4
    assert doc.values["motif_count"] >= 1
    assert doc.values["ngram_order_max"] == 3
    coverage = doc.values["motif_opportunity_coverage"]
    assert type(coverage) is float and coverage > 0.0


def test_repeated_conventions_empty_unknown() -> None:
    doc = compute_repeated_conventions(
        [], run_id="run-m", input_revision="rev-1", window_end=5
    )
    assert doc.availability is MetricAvailability.UNKNOWN
    assert doc.values == {}


def test_repeated_conventions_input_permutation() -> None:
    actions = [
        AppliedActionRow(tick=1, ordinal=0, agent_id="a", action_kind="move"),
        AppliedActionRow(tick=2, ordinal=0, agent_id="a", action_kind="wait"),
        AppliedActionRow(tick=3, ordinal=0, agent_id="a", action_kind="move"),
        AppliedActionRow(tick=4, ordinal=0, agent_id="a", action_kind="wait"),
        AppliedActionRow(tick=1, ordinal=1, agent_id="b", action_kind="move"),
        AppliedActionRow(tick=2, ordinal=1, agent_id="b", action_kind="wait"),
        AppliedActionRow(tick=3, ordinal=1, agent_id="b", action_kind="move"),
        AppliedActionRow(tick=4, ordinal=1, agent_id="b", action_kind="wait"),
    ]
    first = compute_repeated_conventions(
        actions, run_id="run-m", input_revision="rev-1", window_end=10
    )
    second = compute_repeated_conventions(
        list(reversed(actions)),
        run_id="run-m",
        input_revision="rev-1",
        window_end=10,
    )
    assert first.values == second.values
    assert metric_document_fingerprint(first) == metric_document_fingerprint(second)


def test_behavioral_specialization_one_agent_js_unknown() -> None:
    actions = [
        AppliedActionRow(tick=1, ordinal=0, agent_id="solo", action_kind="move"),
        AppliedActionRow(tick=2, ordinal=0, agent_id="solo", action_kind="move"),
    ]
    doc = compute_behavioral_specialization(
        actions, run_id="run-b", input_revision="rev-1", window_end=5
    )
    assert doc.availability is MetricAvailability.PARTIAL
    assert doc.values["agents_scored"] == 1
    assert doc.values["mean_normalized_entropy"] == 0.0
    assert doc.values["mean_js_divergence"] is None


def test_behavioral_specialization_zero_action_unknown() -> None:
    doc = compute_behavioral_specialization(
        [], run_id="run-b", input_revision="rev-1", window_end=5
    )
    assert doc.availability is MetricAvailability.UNKNOWN


def test_behavioral_specialization_terminal_agent_excludes_post_death() -> None:
    actions = [
        AppliedActionRow(tick=1, ordinal=0, agent_id="alive", action_kind="move"),
        AppliedActionRow(tick=1, ordinal=1, agent_id="dead", action_kind="wait"),
        AppliedActionRow(tick=5, ordinal=0, agent_id="dead", action_kind="attack"),
        AppliedActionRow(tick=2, ordinal=0, agent_id="alive", action_kind="help"),
    ]
    doc = compute_behavioral_specialization(
        actions,
        run_id="run-b",
        input_revision="rev-1",
        window_end=10,
        death_ticks={"dead": 2},
    )
    assert doc.values["agents_scored"] == 2
    assert doc.availability is MetricAvailability.PRESENT
    assert type(doc.values["mean_js_divergence"]) is float


def test_behavioral_specialization_uniform_two_agents() -> None:
    actions = [
        AppliedActionRow(tick=1, ordinal=0, agent_id="a", action_kind="move"),
        AppliedActionRow(tick=1, ordinal=1, agent_id="b", action_kind="move"),
        AppliedActionRow(tick=2, ordinal=0, agent_id="a", action_kind="wait"),
        AppliedActionRow(tick=2, ordinal=1, agent_id="b", action_kind="wait"),
    ]
    doc = compute_behavioral_specialization(
        actions, run_id="run-b", input_revision="rev-1", window_end=5
    )
    assert doc.availability is MetricAvailability.PRESENT
    assert doc.values["agents_scored"] == 2
    # Identical mixtures -> JS divergence 0; normalized entropy 1 for two kinds.
    assert doc.values["mean_js_divergence"] == 0.0
    assert doc.values["mean_normalized_entropy"] == _q(1.0)
