# mypy: ignore-errors
"""Locked economic-cascade policy and integer window arithmetic."""

from __future__ import annotations

import dataclasses

import pytest

from analysis.economic_cascades_contract import EconomicCascadesError
from analysis.economic_cascades_policy import (
    ECONOMIC_CASCADES_LOCKED_POLICY,
    EconomicCascadesPolicy,
    default_policy,
    policy_with,
    window_bounds,
    window_index,
    window_tick,
)

pytestmark = pytest.mark.unit


def test_defaults_match_the_locked_summary() -> None:
    policy = default_policy()
    assert policy.window_ticks == 32
    assert policy.max_windows == 512
    assert policy.max_events == 200_000
    assert policy.max_disruptions == 4_096
    assert policy.max_stages == 4_096
    assert policy.max_dependency_edges == 4_096
    assert policy.max_chains == 2_048
    assert policy.max_propagation_rows == 1_024
    assert policy.max_coverage_rows == 1_024
    assert policy.max_notices == 8
    assert policy.max_chain_depth == 6
    assert policy.max_propagation_lag_windows == 2
    assert policy.min_linked_chains == 3
    assert policy.shortfall_share_milli == 250
    assert ECONOMIC_CASCADES_LOCKED_POLICY["max_chains"] == 2_048


def test_policy_is_frozen() -> None:
    policy = default_policy()
    with pytest.raises(dataclasses.FrozenInstanceError):
        policy.max_chains = 1  # type: ignore[misc]


@pytest.mark.parametrize(
    "field,value",
    [
        ("window_ticks", 0),
        ("max_windows", 0),
        ("max_events", 0),
        ("max_chains", 0),
        ("shortfall_share_milli", 0),
        ("shortfall_share_milli", 1_001),
        ("max_chain_depth", 0),
        ("max_propagation_lag_windows", -1),
        ("min_linked_chains", 0),
    ],
)
def test_out_of_range_values_fail_closed(field: str, value: int) -> None:
    with pytest.raises(EconomicCascadesError):
        EconomicCascadesPolicy(**{field: value})


def test_bools_are_not_accepted_as_ints() -> None:
    with pytest.raises(EconomicCascadesError):
        EconomicCascadesPolicy(window_ticks=True)  # type: ignore[arg-type]


def test_policy_with_returns_a_validated_copy() -> None:
    policy = policy_with(max_chains=4)
    assert policy.max_chains == 4
    assert policy.window_ticks == 32
    with pytest.raises(EconomicCascadesError):
        policy_with(unknown_cap=1)  # type: ignore[call-arg]


def test_window_arithmetic_is_integer_only() -> None:
    policy = default_policy()
    assert policy.window_index(0) == 0
    assert policy.window_index(31) == 0
    assert policy.window_index(32) == 1
    assert policy.window_tick(3) == 96
    assert policy.window_bounds(65) == (64, 96)
    assert window_index(64) == 2
    assert window_tick(2) == 64
    assert window_bounds(64) == (64, 96)
    with pytest.raises(EconomicCascadesError):
        window_index(-1)
    with pytest.raises(EconomicCascadesError):
        window_tick(512)
    with pytest.raises(EconomicCascadesError):
        window_index(32 * 512)
