"""Determinism proofs for behavior metrics under input permutation (Task 12)."""

from __future__ import annotations

from analysis.behavior_metrics import (
    compute_behavioral_specialization,
    compute_repeated_conventions,
)
from analysis.models import AppliedActionRow
from analysis.serialization import (
    encode_metric_document,
    metric_document_fingerprint,
)


def _sample_actions() -> list[AppliedActionRow]:
    rows: list[AppliedActionRow] = []
    kinds = ("move", "wait", "help", "attack", "talk")
    ordinal = 0
    for agent_index, agent in enumerate(("alpha", "beta", "gamma")):
        for tick in range(1, 7):
            kind = kinds[(tick + agent_index) % len(kinds)]
            rows.append(
                AppliedActionRow(
                    tick=tick,
                    ordinal=ordinal,
                    agent_id=agent,
                    action_kind=kind,
                    location_id=f"loc-{tick % 2}",
                    target_id="gamma" if kind in {"help", "attack", "talk"} else None,
                )
            )
            ordinal += 1
    return rows


def test_behavior_metrics_permutation_invariant_fingerprints() -> None:
    actions = _sample_actions()
    permuted = list(reversed(actions))
    conv_a = compute_repeated_conventions(
        actions, run_id="run-d", input_revision="rev-d", window_end=20
    )
    conv_b = compute_repeated_conventions(
        permuted, run_id="run-d", input_revision="rev-d", window_end=20
    )
    spec_a = compute_behavioral_specialization(
        actions, run_id="run-d", input_revision="rev-d", window_end=20
    )
    spec_b = compute_behavioral_specialization(
        permuted, run_id="run-d", input_revision="rev-d", window_end=20
    )
    assert metric_document_fingerprint(conv_a) == metric_document_fingerprint(conv_b)
    assert metric_document_fingerprint(spec_a) == metric_document_fingerprint(spec_b)
    assert encode_metric_document(conv_a) == encode_metric_document(conv_b)
    assert encode_metric_document(spec_a) == encode_metric_document(spec_b)


def test_behavior_metrics_terminal_and_zero_action_stable() -> None:
    empty_conv = compute_repeated_conventions(
        [], run_id="run-d", input_revision="rev-d", window_end=3
    )
    empty_spec = compute_behavioral_specialization(
        [], run_id="run-d", input_revision="rev-d", window_end=3
    )
    assert encode_metric_document(empty_conv) == encode_metric_document(
        compute_repeated_conventions(
            [], run_id="run-d", input_revision="rev-d", window_end=3
        )
    )
    assert encode_metric_document(empty_spec) == encode_metric_document(
        compute_behavioral_specialization(
            [], run_id="run-d", input_revision="rev-d", window_end=3
        )
    )

    actions = [
        AppliedActionRow(tick=1, ordinal=0, agent_id="a", action_kind="move"),
        AppliedActionRow(tick=2, ordinal=0, agent_id="a", action_kind="wait"),
        AppliedActionRow(tick=9, ordinal=0, agent_id="a", action_kind="attack"),
    ]
    with_death = compute_behavioral_specialization(
        actions,
        run_id="run-d",
        input_revision="rev-d",
        window_end=10,
        death_ticks={"a": 2},
    )
    again = compute_behavioral_specialization(
        list(reversed(actions)),
        run_id="run-d",
        input_revision="rev-d",
        window_end=10,
        death_ticks={"a": 2},
    )
    assert metric_document_fingerprint(with_death) == metric_document_fingerprint(again)
    assert with_death.values["agents_scored"] == 1


def test_network_and_relationship_permutation_invariant() -> None:
    from analysis.models import RelationshipEdgeRow
    from analysis.network_metrics import compute_trust_network_structure
    from analysis.relationship_metrics import compute_relationship_stability

    rows = [
        RelationshipEdgeRow(
            source_id="a", target_id="b", logical_tick=1, activation_state="active", trust=0.5
        ),
        RelationshipEdgeRow(
            source_id="b", target_id="a", logical_tick=2, activation_state="active", trust=-0.2
        ),
        RelationshipEdgeRow(
            source_id="a", target_id="b", logical_tick=4, activation_state="active", trust=0.9
        ),
    ]
    rel_a = compute_relationship_stability(
        rows, run_id="run-d", input_revision="rev-d", window_end=10
    )
    rel_b = compute_relationship_stability(
        list(reversed(rows)), run_id="run-d", input_revision="rev-d", window_end=10
    )
    net_a = compute_trust_network_structure(
        rows, run_id="run-d", input_revision="rev-d", agent_ids=("a", "b")
    )
    net_b = compute_trust_network_structure(
        list(reversed(rows)), run_id="run-d", input_revision="rev-d", agent_ids=("b", "a")
    )
    assert metric_document_fingerprint(rel_a) == metric_document_fingerprint(rel_b)
    assert metric_document_fingerprint(net_a) == metric_document_fingerprint(net_b)
