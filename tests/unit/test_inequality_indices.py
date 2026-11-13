# mypy: ignore-errors
"""Quantized inequality index and distribution-summary tests."""

from __future__ import annotations

import pytest

from analysis.economic_inequality_contract import (
    EconomicInequalityAvailability,
    EconomicInequalityError,
)
from analysis.inequality_indices import (
    inequality_bin_shares_milli,
    inequality_distribution_summary,
    quantized_atkinson_eps_1,
    quantized_gini,
    quantized_theil_t,
    quantized_top_share,
)


def test_equal_values_have_zero_indices() -> None:
    values = (2, 2, 2, 2)
    assert quantized_gini(values) == 0
    assert quantized_theil_t(values) == 0
    assert quantized_atkinson_eps_1(values) == 0
    assert quantized_top_share(values) == 250


def test_all_zero_values_have_zero_indices_and_shares() -> None:
    values = (0, 0, 0, 0)
    assert quantized_gini(values) == 0
    assert quantized_theil_t(values) == 0
    assert quantized_atkinson_eps_1(values) == 0
    assert quantized_top_share(values) == 0
    summary = inequality_distribution_summary(values)
    assert summary.status is EconomicInequalityAvailability.AVAILABLE
    assert summary.bin_shares_milli == (0, 0, 0, 0, 0)


def test_gini_matches_the_shared_quantized_formula() -> None:
    assert quantized_gini((0, 0, 0, 4)) == 750
    assert quantized_gini((1, 2, 3, 4)) > 0


def test_atkinson_is_bounded() -> None:
    assert quantized_atkinson_eps_1((0, 1, 2, 3)) == 1_000
    assert 0 <= quantized_atkinson_eps_1((1, 2, 3, 4)) <= 1_000


def test_top_share_is_bounded() -> None:
    assert quantized_top_share((1, 1, 1, 1)) == 250
    assert quantized_top_share((1, 2, 3, 4)) == 400
    assert quantized_top_share((0, 0, 0, 1)) == 1_000


@pytest.mark.parametrize(
    "values",
    [(), (1,), (1, 2), (1, 2, 3)],
)
def test_short_vectors_are_insufficient(
    values: tuple[int, ...],
) -> None:
    summary = inequality_distribution_summary(values)
    if not values:
        assert summary.status is EconomicInequalityAvailability.UNAVAILABLE
        assert summary.sample_count == 0
    else:
        assert summary.status is EconomicInequalityAvailability.INSUFFICIENT_SAMPLES
        assert summary.sample_count == len(values)
        assert summary.median is None
        assert summary.bin_shares_milli == (0, 0, 0, 0, 0)


def test_summary_uses_nearest_rank_and_sums_to_one_thousand() -> None:
    summary = inequality_distribution_summary((0, 1, 2, 3, 4))
    assert summary.status is EconomicInequalityAvailability.AVAILABLE
    assert summary.minimum == 0
    assert summary.p25 == 1
    assert summary.median == 2
    assert summary.p75 == 3
    assert summary.maximum == 4
    assert summary.iqr == 2
    assert summary.dispersion == 4
    assert sum(summary.bin_shares_milli) == 1_000


def test_bin_shares_are_deterministic_and_bounded() -> None:
    assert inequality_bin_shares_milli((0, 0, 0, 0)) == (0, 0, 0, 0, 0)
    assert inequality_bin_shares_milli((5, 5, 5, 5)) == (1_000, 0, 0, 0, 0)
    assert sum(inequality_bin_shares_milli((0, 1, 2, 3, 4, 5, 6))) == 1_000


def test_invalid_inputs_fail_closed() -> None:
    with pytest.raises(EconomicInequalityError):
        quantized_gini(())
    with pytest.raises(EconomicInequalityError):
        quantized_gini((-1, 1))
    with pytest.raises(EconomicInequalityError):
        inequality_distribution_summary((1, 2), min_samples=0)
