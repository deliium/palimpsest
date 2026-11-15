# mypy: ignore-errors
"""Hypothesis invariants for quantized social-mobility detection."""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from analysis.social_mobility_contract import (
    SocialMobilityCoverage,
    SocialMobilityDomain,
    SocialMobilityLayer,
    SocialMobilityMeasure,
    social_mobility_lineage_token,
    social_mobility_owner_token,
)
from analysis.social_mobility_detection import detect_social_mobility_rows
from analysis.social_mobility_genealogy import SocialMobilityGenealogyHarvest
from analysis.social_mobility_outcomes import SocialMobilityOutcomeHarvest
from analysis.social_mobility_policy import SocialMobilityAnalysisPolicy
from analysis.social_mobility_rows import (
    SocialMobilityLineageEntry,
    SocialMobilityOutcomeRow,
)

pytestmark = pytest.mark.unit


def _outcome(owner: str, quantity: int) -> SocialMobilityOutcomeRow:
    return SocialMobilityOutcomeRow(
        owner_token=social_mobility_owner_token(owner),
        generation_index=1,
        tick=31,
        window_index=0,
        domain=SocialMobilityDomain.RESOURCES,
        measure=SocialMobilityMeasure.OBSERVED_RESOURCE_ITEM_COUNT,
        quantity=quantity,
        layer=SocialMobilityLayer.OBJECTIVE_OUTCOME,
    )


@settings(max_examples=40, deadline=None)
@given(
    quantities=st.lists(st.integers(min_value=0, max_value=50), min_size=8, max_size=8),
    offset=st.integers(min_value=-5, max_value=5),
)
def test_statistics_stay_inside_closed_ranges(
    quantities: list[int], offset: int
) -> None:
    lineages = tuple(
        SocialMobilityLineageEntry(
            lineage_token=social_mobility_lineage_token(
                social_mobility_owner_token(f"entity:a{index}"),
                social_mobility_owner_token(f"entity:b{index}"),
            ),
            ancestor_token=social_mobility_owner_token(f"entity:a{index}"),
            descendant_token=social_mobility_owner_token(f"entity:b{index}"),
            generation_lag=1,
            ancestor_generation=0,
            descendant_generation=1,
        )
        for index in range(8)
    )
    rows = tuple(
        _outcome(f"entity:a{index}", value) for index, value in enumerate(quantities)
    ) + tuple(
        _outcome(f"entity:b{index}", max(0, value + offset))
        for index, value in enumerate(quantities)
    )
    genealogy = SocialMobilityGenealogyHarvest(
        lineages=lineages,
        coverage=SocialMobilityCoverage.COMPLETE,
        owner_count=16,
    )
    outcomes = SocialMobilityOutcomeHarvest(
        rows=rows,
        coverage=SocialMobilityCoverage.COMPLETE,
        owner_count=16,
    )
    result = detect_social_mobility_rows(
        genealogy=genealogy, outcomes=outcomes, policy=SocialMobilityAnalysisPolicy()
    )
    resource = next(
        row
        for row in result.domain_rows
        if row.domain is SocialMobilityDomain.RESOURCES
    )
    assert -1_000 <= resource.rank_correlation_milli <= 1_000
    assert 0 <= resource.same_bin_share_milli <= 1_000
    assert 0 <= resource.upward_share_milli <= 1_000
    assert 0 <= resource.downward_share_milli <= 1_000
    assert 0 <= resource.mean_absolute_rank_change_milli <= 1_000
    assert (
        resource.same_bin_share_milli
        + resource.upward_share_milli
        + resource.downward_share_milli
        <= 1_001
    )
    for row in result.pair_rows:
        if row.resolved:
            assert 0 <= row.ancestor_bin <= 4
            assert 0 <= row.descendant_bin <= 4
