"""Known-answer and edge-case tests for Task 11 objective metrics."""

from __future__ import annotations

import math

import pytest

from analysis.models import (
    ACTION_RESOLUTION_RATES_FAMILY,
    ActionResolutionRow,
    AppliedActionRow,
    GoalTransitionRow,
    MetricAvailability,
    ResourceHoldingRow,
    SurvivalAgentRow,
)
from analysis.numerical import quantize_float
from analysis.objective_metrics import (
    compute_action_resolution_rates,
    compute_conflict,
    compute_cooperation,
    compute_goal_completion,
    compute_resource_inequality,
    compute_survival,
    living_agent_ticks,
)
from analysis.serialization import (
    decode_metric_document,
    encode_metric_document,
    metric_document_fingerprint,
)
from analysis.specifications import (
    MetricFamilyId,
    ResourceMeasureId,
    metric_specification,
)
from tests.unit.metric_fixtures import all_known_answer_fixtures


def _q(value: float) -> float:
    return quantize_float(value)


def test_resource_inequality_known_answers_from_fixtures() -> None:
    for fixture in all_known_answer_fixtures():
        if fixture.family_id is not MetricFamilyId.RESOURCE_INEQUALITY:
            continue
        if fixture.fixture_id == "deg-resource-empty-population":
            doc = compute_resource_inequality(
                [],
                run_id="run-ri",
                input_revision="rev-1",
                measure_id=ResourceMeasureId.INVENTORY_COUNT,
            )
            assert doc.availability is MetricAvailability.UNKNOWN
            assert doc.values == {}
            continue
        if fixture.fixture_id == "deg-resource-one-agent":
            holdings = [ResourceHoldingRow(agent_id="a1", value=7.0)]
        elif fixture.fixture_id == "deg-resource-all-zero":
            holdings = [
                ResourceHoldingRow(agent_id=f"a{i}", value=0.0) for i in range(3)
            ]
        elif fixture.fixture_id == "deg-resource-two-agent-gini":
            holdings = [
                ResourceHoldingRow(agent_id="a", value=0.0),
                ResourceHoldingRow(agent_id="b", value=10.0),
            ]
        elif fixture.fixture_id == "ref-resource-inequality-inventory-skew":
            holdings = [
                ResourceHoldingRow(agent_id=f"agent-{i}", value=0.0) for i in range(4)
            ] + [ResourceHoldingRow(agent_id="agent-4", value=1.0)]
        else:
            continue
        doc = compute_resource_inequality(
            holdings,
            run_id="run-ri",
            input_revision="rev-1",
            measure_id=ResourceMeasureId.INVENTORY_COUNT,
        )
        assert doc.availability is fixture.availability
        for key, expected in fixture.expected_values.items():
            assert doc.values[key] == expected


def test_resource_inequality_unknown_holdings_not_zero() -> None:
    holdings = [
        ResourceHoldingRow(agent_id="a", value=1.0),
        ResourceHoldingRow(agent_id="b", value=None),
    ]
    doc = compute_resource_inequality(
        holdings, run_id="run-ri", input_revision="rev-1"
    )
    assert doc.availability is MetricAvailability.PARTIAL
    assert doc.values["population_size"] == 1
    assert "wealth" not in repr(doc).lower()


def test_resource_inequality_permutation_determinism() -> None:
    holdings_a = [
        ResourceHoldingRow(agent_id="z", value=4.0),
        ResourceHoldingRow(agent_id="a", value=1.0),
        ResourceHoldingRow(agent_id="m", value=2.0),
    ]
    holdings_b = list(reversed(holdings_a))
    first = compute_resource_inequality(
        holdings_a, run_id="run-ri", input_revision="rev-1"
    )
    second = compute_resource_inequality(
        holdings_b, run_id="run-ri", input_revision="rev-1"
    )
    assert first.values == second.values
    assert metric_document_fingerprint(first) == metric_document_fingerprint(second)


def test_cooperation_and_conflict_distinguish_kinds() -> None:
    actions = [
        AppliedActionRow(
            tick=1, ordinal=0, agent_id="a", action_kind="help", target_id="b"
        ),
        AppliedActionRow(
            tick=1, ordinal=1, agent_id="a", action_kind="give", target_id="b"
        ),
        AppliedActionRow(
            tick=1, ordinal=2, agent_id="a", action_kind="talk", target_id="b"
        ),
        AppliedActionRow(
            tick=2, ordinal=0, agent_id="a", action_kind="attack", target_id="b"
        ),
        AppliedActionRow(tick=2, ordinal=1, agent_id="a", action_kind="flee"),
        AppliedActionRow(tick=3, ordinal=0, agent_id="a", action_kind="move"),
    ]
    coop = compute_cooperation(
        actions,
        run_id="run-c",
        input_revision="rev-1",
        agent_ids=["a", "b"],
        window_end=3,
    )
    conflict = compute_conflict(
        actions,
        run_id="run-c",
        input_revision="rev-1",
        agent_ids=["a", "b"],
        window_end=3,
    )
    assert coop.availability is MetricAvailability.PRESENT
    assert conflict.availability is MetricAvailability.PRESENT
    assert coop.values["coop_event_count"] == 3
    assert conflict.values["conflict_event_count"] == 2
    assert conflict.values["attack_occurrence_rate"] == _q(1.0 / 6.0)
    assert conflict.values["flee_occurrence_rate"] == _q(1.0 / 6.0)
    self_give = [
        *actions,
        AppliedActionRow(
            tick=4, ordinal=0, agent_id="a", action_kind="give", target_id="a"
        ),
    ]
    coop_self = compute_cooperation(
        self_give,
        run_id="run-c",
        input_revision="rev-1",
        agent_ids=["a", "b"],
        window_end=4,
    )
    assert coop_self.values["coop_event_count"] == 3


def test_cooperation_no_events_unknown() -> None:
    doc = compute_cooperation(
        [],
        run_id="run-c",
        input_revision="rev-1",
        agent_ids=["a"],
        window_end=5,
    )
    assert doc.availability is MetricAvailability.UNKNOWN
    assert doc.values == {}


def test_action_resolution_rates_never_infer_from_absence() -> None:
    empty = compute_action_resolution_rates(
        [], run_id="run-ar", input_revision="rev-1"
    )
    assert empty.metric_family == ACTION_RESOLUTION_RATES_FAMILY
    assert empty.availability is MetricAvailability.ABSENT

    legacy = compute_action_resolution_rates(
        [], run_id="run-ar", input_revision="rev-1", legacy_unavailable=True
    )
    assert legacy.availability is MetricAvailability.UNKNOWN

    rows = [
        ActionResolutionRow(
            tick=1, ordinal=0, agent_id="a", command_kind="move", status="applied"
        ),
        ActionResolutionRow(
            tick=1, ordinal=1, agent_id="b", command_kind="attack", status="applied"
        ),
        ActionResolutionRow(
            tick=1, ordinal=2, agent_id="c", command_kind="help", status="rejected"
        ),
        ActionResolutionRow(
            tick=1, ordinal=3, agent_id="d", command_kind="flee", status="conflicted"
        ),
    ]
    doc = compute_action_resolution_rates(
        list(reversed(rows)), run_id="run-ar", input_revision="rev-1"
    )
    assert doc.availability is MetricAvailability.PRESENT
    assert doc.values["attempt_count"] == 4
    assert doc.values["applied_rate"] == _q(0.5)
    assert doc.values["rejected_rate"] == _q(0.25)
    assert doc.values["conflicted_rate"] == _q(0.25)


def test_survival_reference_and_censoring() -> None:
    agents = [
        SurvivalAgentRow(agent_id="a1", death_tick=10),
        SurvivalAgentRow(agent_id="a2"),
        SurvivalAgentRow(agent_id="a3"),
        SurvivalAgentRow(agent_id="a4"),
        SurvivalAgentRow(agent_id="a5"),
    ]
    doc = compute_survival(
        list(reversed(agents)),
        run_id="run-s",
        input_revision="rev-1",
        final_tick=48,
    )
    assert doc.values["survival_rate_at_T"] == _q(4.0 / 5.0)
    assert doc.values["deaths"] == 1
    assert doc.values["censored_alive"] == 4
    assert doc.values["median_survival_tick"] is None
    assert doc.availability is MetricAvailability.PARTIAL


def test_survival_empty_unknown() -> None:
    doc = compute_survival([], run_id="run-s", input_revision="rev-1", final_tick=10)
    assert doc.availability is MetricAvailability.UNKNOWN


def test_goal_completion_rates_and_legacy() -> None:
    transitions = [
        GoalTransitionRow(
            goal_id="g1",
            owner_id="a",
            tick=1,
            reason_code="completed",
            to_status="completed",
        ),
        GoalTransitionRow(
            goal_id="g2",
            owner_id="b",
            tick=2,
            reason_code="abandoned",
            to_status="abandoned",
        ),
        GoalTransitionRow(
            goal_id="g3",
            owner_id="c",
            tick=3,
            reason_code="death",
            to_status="abandoned",
        ),
        GoalTransitionRow(
            goal_id="g4",
            owner_id="d",
            tick=4,
            reason_code="run_end",
            to_status="active",
        ),
    ]
    doc = compute_goal_completion(
        transitions, run_id="run-g", input_revision="rev-1"
    )
    assert doc.availability is MetricAvailability.PRESENT
    assert doc.values["completion_rate"] == _q(0.25)
    assert doc.values["abandonment_rate"] == _q(0.25)
    assert doc.values["death_interrupt_rate"] == _q(0.25)
    assert doc.values["goals_censored_run_end"] == 1

    empty = compute_goal_completion([], run_id="run-g", input_revision="rev-1")
    assert empty.availability is MetricAvailability.ABSENT
    assert empty.values["goals_total"] == 0

    legacy = compute_goal_completion(
        [], run_id="run-g", input_revision="rev-1", legacy_unavailable=True
    )
    assert legacy.availability is MetricAvailability.UNKNOWN


def test_living_agent_ticks_excludes_post_death() -> None:
    ticks = living_agent_ticks(
        ["a", "b"],
        window_start=0,
        window_end=2,
        death_ticks={"a": 1},
    )
    # a: ticks 0,1 (not 2); b: 0,1,2 -> 5
    assert ticks == 5


def test_objective_documents_round_trip_and_are_finite() -> None:
    holdings = [
        ResourceHoldingRow(agent_id="a", value=0.0),
        ResourceHoldingRow(agent_id="b", value=10.0),
    ]
    doc = compute_resource_inequality(
        holdings, run_id="run-rt", input_revision="rev-1"
    )
    encoded = encode_metric_document(doc)
    decoded = decode_metric_document(encoded)
    assert decoded.values == doc.values
    for value in doc.values.values():
        if type(value) is float:
            assert math.isfinite(value)


@pytest.mark.parametrize(
    "family",
    [
        MetricFamilyId.RESOURCE_INEQUALITY,
        MetricFamilyId.COOPERATION,
        MetricFamilyId.CONFLICT,
        MetricFamilyId.SURVIVAL,
        MetricFamilyId.GOAL_COMPLETION,
    ],
)
def test_objective_families_match_spec_versions(family: MetricFamilyId) -> None:
    spec = metric_specification(family)
    assert spec.algorithm_version == "1"
    assert "wealth" not in spec.population.lower()
