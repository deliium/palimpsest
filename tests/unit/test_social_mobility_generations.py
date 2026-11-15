# mypy: ignore-errors
"""Generation and generation-lag strata for many-generation studies."""

from __future__ import annotations

import pytest

from analysis.social_mobility_contract import (
    SocialMobilityAvailability,
    SocialMobilityCoverage,
    SocialMobilityDomain,
    SocialMobilityLayer,
    SocialMobilityMeasure,
    social_mobility_owner_token,
)
from analysis.social_mobility_genealogy import SocialMobilityGenealogyHarvest
from analysis.social_mobility_generations import (
    compare_social_mobility_generations,
)
from analysis.social_mobility_outcomes import SocialMobilityOutcomeHarvest
from analysis.social_mobility_rows import (
    SocialMobilityOutcomeRow,
    SocialMobilityPairRow,
)

pytestmark = pytest.mark.unit


def _token(name: str) -> str:
    return social_mobility_owner_token(name)


def _pair(
    ancestor: str, descendant: str, lag: int, left: int, right: int, *, window: int = 0
):
    return SocialMobilityPairRow(
        window_index=window,
        ancestor_token=_token(ancestor),
        descendant_token=_token(descendant),
        generation_lag=lag,
        domain=SocialMobilityDomain.RESOURCES,
        ancestor_quantity=left,
        descendant_quantity=right,
        ancestor_bin=0,
        descendant_bin=0,
        ancestor_window_index=window,
        descendant_window_index=window,
        resolved=True,
    )


def _outcome(owner: str, generation: int, *, window: int = 0):
    return SocialMobilityOutcomeRow(
        owner_token=_token(owner),
        generation_index=generation,
        tick=window * 32 + 31,
        window_index=window,
        domain=SocialMobilityDomain.RESOURCES,
        measure=SocialMobilityMeasure.OBSERVED_RESOURCE_ITEM_COUNT,
        quantity=1,
        layer=SocialMobilityLayer.OBJECTIVE_OUTCOME,
    )


def _genealogy(generations: dict[str, int]) -> SocialMobilityGenealogyHarvest:
    return SocialMobilityGenealogyHarvest(
        generations=tuple(
            sorted((_token(name), value) for name, value in generations.items())
        ),
        coverage=SocialMobilityCoverage.COMPLETE,
        owner_count=len(generations),
        max_generation_index=max(generations.values(), default=0),
    )


def test_three_generation_fixture_yields_lag_one_and_two() -> None:
    genealogy = _genealogy({"a": 0, "b": 1, "c": 2})
    outcomes = SocialMobilityOutcomeHarvest(
        rows=tuple(
            _outcome(name, generation)
            for name, generation in (("a", 0), ("b", 1), ("c", 2))
        ),
        coverage=SocialMobilityCoverage.COMPLETE,
        owner_count=3,
    )
    pairs = tuple(
        _pair(f"a{index}", f"b{index}", 1, index, index) for index in range(8)
    ) + tuple(
        _pair(f"a{index}", f"c{index}", 2, index, 7 - index) for index in range(8)
    )
    # Generation membership drives grouping; all b/c tokens resolve to the
    # declared generation indices.
    genealogy = SocialMobilityGenealogyHarvest(
        generations=tuple(
            sorted(
                {
                    **{_token(f"a{index}"): 0 for index in range(8)},
                    **{_token(f"b{index}"): 1 for index in range(8)},
                    **{_token(f"c{index}"): 2 for index in range(8)},
                }.items()
            )
        ),
        coverage=SocialMobilityCoverage.COMPLETE,
        owner_count=24,
        max_generation_index=2,
    )
    result = compare_social_mobility_generations(
        genealogy=genealogy, outcomes=outcomes, pair_rows=pairs
    )
    assert {row.generation_index for row in result.generation_rows} == {1, 2}
    assert {row.generation_lag for row in result.lag_rows} == {1, 2}
    assert result.comparable_generation_count == 2
    assert result.comparable_lag_count == 2
    lag_one = next(row for row in result.lag_rows if row.generation_lag == 1)
    lag_two = next(row for row in result.lag_rows if row.generation_lag == 2)
    assert lag_one.same_bin_share_milli == 1_000
    assert lag_two.same_bin_share_milli < lag_one.same_bin_share_milli


def test_four_generation_fixture_yields_lag_three() -> None:
    generations = {
        **{_token(f"a{index}"): 0 for index in range(8)},
        **{_token(f"b{index}"): 1 for index in range(8)},
        **{_token(f"c{index}"): 2 for index in range(8)},
        **{_token(f"d{index}"): 3 for index in range(8)},
    }
    genealogy = SocialMobilityGenealogyHarvest(
        generations=tuple(sorted(generations.items())),
        coverage=SocialMobilityCoverage.COMPLETE,
        owner_count=len(generations),
        max_generation_index=3,
    )
    pairs = tuple(
        _pair(f"a{index}", f"d{index}", 3, index, 7 - index) for index in range(8)
    )
    result = compare_social_mobility_generations(
        genealogy=genealogy,
        outcomes=SocialMobilityOutcomeHarvest(
            coverage=SocialMobilityCoverage.COMPLETE,
            owner_count=len(generations),
        ),
        pair_rows=pairs,
    )
    assert {row.generation_lag for row in result.lag_rows} == {3}
    assert result.comparable_lag_count == 1


def test_insufficient_generation_is_marked_not_zeroed() -> None:
    genealogy = _genealogy({"a": 0, "b": 1})
    outcomes = SocialMobilityOutcomeHarvest(
        rows=(_outcome("a", 0), _outcome("b", 1)),
        coverage=SocialMobilityCoverage.COMPLETE,
        owner_count=2,
    )
    result = compare_social_mobility_generations(
        genealogy=genealogy,
        outcomes=outcomes,
        pair_rows=(_pair("a", "b", 1, 1, 1),),
    )
    assert result.generation_rows[0].comparable is False
    assert (
        result.generation_rows[0].availability
        is SocialMobilityAvailability.INSUFFICIENT_SAMPLES
    )


def test_out_of_range_generation_is_excluded_with_notice() -> None:
    genealogy = _genealogy({"a": 0, "b": 40})
    outcomes = SocialMobilityOutcomeHarvest(
        rows=(_outcome("a", 0), _outcome("b", 40)),
        coverage=SocialMobilityCoverage.COMPLETE,
        owner_count=2,
    )
    result = compare_social_mobility_generations(
        genealogy=genealogy,
        outcomes=outcomes,
        pair_rows=(_pair("a", "b", 1, 1, 1),),
    )
    assert result.generation_rows == ()
    assert "social_mobility_generation_out_of_range" in result.notices


def test_generation_rows_are_deterministically_ordered() -> None:
    genealogy = _genealogy({"a": 0, "b": 1, "c": 2})
    outcomes = SocialMobilityOutcomeHarvest(
        rows=(_outcome("a", 0), _outcome("b", 1), _outcome("c", 2)),
        coverage=SocialMobilityCoverage.COMPLETE,
        owner_count=3,
    )
    pairs = tuple(
        _pair("a", f"b{index}", 1, index, index) for index in range(8)
    ) + tuple(_pair("a", f"c{index}", 2, index, index) for index in range(8))
    genealogy = SocialMobilityGenealogyHarvest(
        generations=tuple(
            sorted(
                {
                    _token("a"): 0,
                    **{_token(f"b{index}"): 1 for index in range(8)},
                    **{_token(f"c{index}"): 2 for index in range(8)},
                }.items()
            )
        ),
        coverage=SocialMobilityCoverage.COMPLETE,
        owner_count=17,
        max_generation_index=2,
    )
    first = compare_social_mobility_generations(
        genealogy=genealogy, outcomes=outcomes, pair_rows=pairs
    )
    second = compare_social_mobility_generations(
        genealogy=genealogy, outcomes=outcomes, pair_rows=pairs
    )
    assert first == second
    assert list(first.generation_rows) == sorted(
        first.generation_rows, key=lambda row: (row.window_index, row.generation_index)
    )
    assert list(first.lag_rows) == sorted(
        first.lag_rows, key=lambda row: (row.window_index, row.generation_lag)
    )
