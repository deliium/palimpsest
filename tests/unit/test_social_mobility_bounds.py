# mypy: ignore-errors
"""Independent caps, prefix stability, and statistic ranges."""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from analysis.social_mobility_analysis import harvest_social_mobility_analysis
from analysis.social_mobility_contract import (
    SocialMobilityAvailability,
    SocialMobilityCoverage,
    SocialMobilityDomain,
    SocialMobilityLayer,
    SocialMobilityMeasure,
    social_mobility_lineage_token,
    social_mobility_owner_token,
)
from analysis.social_mobility_genealogy import SocialMobilityGenealogyHarvest
from analysis.social_mobility_outcomes import SocialMobilityOutcomeHarvest
from analysis.social_mobility_policy import SocialMobilityAnalysisPolicy
from analysis.social_mobility_rows import (
    SocialMobilityGenealogyRow,
    SocialMobilityLineageEntry,
    SocialMobilityOutcomeRow,
)


def _token(name: str) -> str:
    return social_mobility_owner_token(name)


def _fixture(count: int):
    lineages = []
    edges = []
    generations = {}
    rows = []
    for index in range(count):
        ancestor = f"entity:a{index}"
        descendant = f"entity:b{index}"
        lineages.append(
            SocialMobilityLineageEntry(
                lineage_token=social_mobility_lineage_token(
                    _token(ancestor), _token(descendant)
                ),
                ancestor_token=_token(ancestor),
                descendant_token=_token(descendant),
                generation_lag=1,
                ancestor_generation=0,
                descendant_generation=1,
            )
        )
        edges.append(
            SocialMobilityGenealogyRow(
                parent_token=_token(ancestor),
                child_token=_token(descendant),
                parent_generation=0,
                child_generation=1,
                established_tick=index,
                window_index=0,
            )
        )
        generations[_token(ancestor)] = 0
        generations[_token(descendant)] = 1
        rows.append(
            SocialMobilityOutcomeRow(
                owner_token=_token(ancestor),
                generation_index=0,
                tick=31,
                window_index=0,
                domain=SocialMobilityDomain.RESOURCES,
                measure=SocialMobilityMeasure.OBSERVED_RESOURCE_ITEM_COUNT,
                quantity=index,
                layer=SocialMobilityLayer.OBJECTIVE_OUTCOME,
            )
        )
        rows.append(
            SocialMobilityOutcomeRow(
                owner_token=_token(descendant),
                generation_index=1,
                tick=31,
                window_index=0,
                domain=SocialMobilityDomain.RESOURCES,
                measure=SocialMobilityMeasure.OBSERVED_RESOURCE_ITEM_COUNT,
                quantity=count - index,
                layer=SocialMobilityLayer.OBJECTIVE_OUTCOME,
            )
        )
    return (
        SocialMobilityGenealogyHarvest(
            edges=tuple(edges),
            generations=tuple(sorted(generations.items())),
            lineages=tuple(lineages),
            coverage=SocialMobilityCoverage.COMPLETE,
            event_count=count,
            owner_count=2 * count,
            max_generation_index=1,
        ),
        SocialMobilityOutcomeHarvest(
            rows=tuple(rows),
            coverage=SocialMobilityCoverage.COMPLETE,
            event_count=2 * count,
            owner_count=2 * count,
        ),
    )


@settings(max_examples=25, deadline=None)
@given(
    count=st.integers(min_value=2, max_value=12),
    max_owners=st.integers(min_value=1, max_value=8),
    max_pairs=st.integers(min_value=1, max_value=16),
    max_domain_rows=st.integers(min_value=1, max_value=6),
)
def test_every_cap_is_enforced_and_prefix_is_stable(
    count: int, max_owners: int, max_pairs: int, max_domain_rows: int
) -> None:
    genealogy, outcomes = _fixture(count)
    policy = SocialMobilityAnalysisPolicy(
        max_owners=max_owners,
        max_pairs=max_pairs,
        max_domain_rows=max_domain_rows,
    )
    analysis = harvest_social_mobility_analysis(
        genealogy=genealogy, outcomes=outcomes, policy=policy
    )
    assert analysis.owner_count <= max_owners
    assert len(analysis.pair_rows) <= max_pairs
    assert len(analysis.domain_rows) <= max_domain_rows
    assert analysis.resolved_pair_count + analysis.unresolved_pair_count == (
        analysis.pair_count
    )
    assert analysis.pair_count == len(analysis.pair_rows)
    second = harvest_social_mobility_analysis(
        genealogy=genealogy, outcomes=outcomes, policy=policy
    )
    assert analysis == second
    for row in analysis.domain_rows:
        assert -1_000 <= row.rank_correlation_milli <= 1_000
        assert 0 <= row.same_bin_share_milli <= 1_000
        assert 0 <= row.upward_share_milli <= 1_000
        assert 0 <= row.downward_share_milli <= 1_000
        assert 0 <= row.mean_absolute_rank_change_milli <= 1_000


def test_below_threshold_is_insufficient_samples() -> None:
    genealogy, outcomes = _fixture(8)
    policy = SocialMobilityAnalysisPolicy(min_mobility_pairs=9)
    analysis = harvest_social_mobility_analysis(
        genealogy=genealogy, outcomes=outcomes, policy=policy
    )
    resources = next(
        row
        for row in analysis.domain_rows
        if row.domain is SocialMobilityDomain.RESOURCES
    )
    assert resources.availability is SocialMobilityAvailability.INSUFFICIENT_SAMPLES
    assert resources.pair_count == 8
    assert resources.rank_correlation_milli == 0
