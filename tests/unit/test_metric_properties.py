"""Hypothesis invariants for objective metric numerical policy (Task 11)."""

from __future__ import annotations

import math

from hypothesis import given, settings
from hypothesis import strategies as st

from analysis.models import MetricAvailability, ResourceHoldingRow, SurvivalAgentRow
from analysis.numerical import quantize_float
from analysis.objective_metrics import compute_resource_inequality, compute_survival
from analysis.serialization import metric_document_fingerprint


@given(
    values=st.lists(
        st.floats(
            min_value=0.0,
            max_value=1_000.0,
            allow_nan=False,
            allow_infinity=False,
            allow_subnormal=False,
        ),
        min_size=1,
        max_size=12,
    )
)
@settings(max_examples=40, deadline=None)
def test_resource_inequality_finite_and_bounded(values: list[float]) -> None:
    holdings = [
        ResourceHoldingRow(agent_id=f"agent-{index:02d}", value=float(value))
        for index, value in enumerate(sorted(values))
    ]
    permuted = list(reversed(holdings))
    first = compute_resource_inequality(
        holdings, run_id="run-h", input_revision="rev-h"
    )
    second = compute_resource_inequality(
        permuted, run_id="run-h", input_revision="rev-h"
    )
    assert first.availability in {
        MetricAvailability.PRESENT,
        MetricAvailability.PARTIAL,
    }
    assert metric_document_fingerprint(first) == metric_document_fingerprint(second)
    gini = first.values["gini"]
    theil = first.values["theil_t"]
    share = first.values["share_top_1"]
    atkinson = first.values["atkinson_eps_1"]
    assert type(gini) is float and math.isfinite(gini)
    assert type(theil) is float and math.isfinite(theil)
    assert type(share) is float and math.isfinite(share)
    assert type(atkinson) is float and math.isfinite(atkinson)
    assert 0.0 <= gini <= 1.0 + 1e-9
    assert theil >= 0.0
    assert 0.0 <= share <= 1.0 + 1e-9
    assert 0.0 <= atkinson <= 1.0 + 1e-9
    assert first.values["population_size"] == len(values)


@given(
    n=st.integers(min_value=1, max_value=8),
    death_count=st.integers(min_value=0, max_value=8),
)
@settings(max_examples=30, deadline=None)
def test_survival_rate_matches_censor_count(n: int, death_count: int) -> None:
    deaths = min(n, death_count)
    agents = [
        SurvivalAgentRow(
            agent_id=f"a{index}",
            death_tick=(index + 1) if index < deaths else None,
        )
        for index in range(n)
    ]
    doc = compute_survival(
        agents, run_id="run-s", input_revision="rev-s", final_tick=100
    )
    assert doc.values["deaths"] == deaths
    assert doc.values["censored_alive"] == n - deaths
    assert doc.values["survival_rate_at_T"] == quantize_float(
        float(n - deaths) / float(n)
    )
    rate = doc.values["survival_rate_at_T"]
    assert type(rate) is float and math.isfinite(rate)
