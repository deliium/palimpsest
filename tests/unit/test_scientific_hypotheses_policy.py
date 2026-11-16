# mypy: ignore-errors
"""Locked scientific-hypothesis analysis policy defaults and bounds."""

from __future__ import annotations

import pytest

from analysis.scientific_hypotheses_contract import ScientificHypothesesError
from analysis.scientific_hypotheses_policy import (
    SCIENTIFIC_HYPOTHESES_LOCKED_POLICY,
    ScientificHypothesesPolicy,
    default_policy,
    policy_with,
    window_bounds,
    window_index,
    window_tick,
)

pytestmark = pytest.mark.unit


def test_defaults_are_locked() -> None:
    policy = default_policy()
    assert policy.window_ticks == 32
    assert policy.max_windows == 512
    assert policy.max_events == 200_000
    assert policy.max_owners == 64
    assert policy.max_hypotheses == 4_096
    assert policy.max_conditions == 8_192
    assert policy.max_revisions == 8_192
    assert policy.max_trials == 4_096
    assert policy.max_summary_rows == 1_024
    assert policy.max_notices == 8
    assert policy.min_samples == 3
    assert policy.confidence_prior == 1
    assert SCIENTIFIC_HYPOTHESES_LOCKED_POLICY["window_ticks"] == 32


def test_frozen_and_validated() -> None:
    policy = default_policy()
    with pytest.raises((AttributeError, TypeError)):
        policy.window_ticks = 64  # type: ignore[misc]
    with pytest.raises(ScientificHypothesesError):
        ScientificHypothesesPolicy(window_ticks=0)
    with pytest.raises(ScientificHypothesesError):
        ScientificHypothesesPolicy(window_ticks=True)  # type: ignore[arg-type]
    with pytest.raises(ScientificHypothesesError):
        ScientificHypothesesPolicy(confidence_prior=0)


def test_window_arithmetic_is_integer() -> None:
    policy = default_policy()
    assert window_index(0) == 0
    assert window_index(31) == 0
    assert window_index(32) == 1
    assert window_tick(2) == 64
    assert window_bounds(33) == (32, 64)
    assert policy.window_index(65) == 2
    assert policy.window_tick(2) == 64
    assert policy.window_bounds(65) == (64, 96)


def test_policy_with_overrides_and_rejects_unknown() -> None:
    policy = policy_with(min_samples=5)
    assert policy.min_samples == 5
    assert default_policy().min_samples == 3
    with pytest.raises(ScientificHypothesesError):
        policy_with(unknown=1)  # type: ignore[call-arg]
    with pytest.raises(ScientificHypothesesError):
        policy_with(window_ticks=0)


def test_window_rejects_out_of_range_and_bool() -> None:
    with pytest.raises(ScientificHypothesesError):
        window_index(-1)
    with pytest.raises(ScientificHypothesesError):
        window_index(True)  # type: ignore[arg-type]
    with pytest.raises(ScientificHypothesesError):
        window_tick(512)
    with pytest.raises(ScientificHypothesesError):
        window_index(512 * 32)
