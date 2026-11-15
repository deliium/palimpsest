# mypy: ignore-errors
"""Bounded social-mobility analysis composition and digest."""

from __future__ import annotations

from dataclasses import replace

import pytest

from analysis.social_mobility_analysis import (
    empty_social_mobility_analysis,
    harvest_social_mobility_analysis,
    social_mobility_analysis_digest,
)
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

pytestmark = pytest.mark.unit


def _token(name: str) -> str:
    return social_mobility_owner_token(name)


def _outcome(
    owner: str, quantity: int, *, window: int = 0, domain=SocialMobilityDomain.RESOURCES
):
    measures = {
        SocialMobilityDomain.RESOURCES: (
            SocialMobilityMeasure.OBSERVED_RESOURCE_ITEM_COUNT
        ),
        SocialMobilityDomain.SKILLS: SocialMobilityMeasure.KNOWN_TECHNIQUE_COUNT,
    }
    return SocialMobilityOutcomeRow(
        owner_token=_token(owner),
        generation_index=1,
        tick=window * 32 + 31,
        window_index=window,
        domain=domain,
        measure=measures[domain],
        quantity=quantity,
        layer=(
            SocialMobilityLayer.OWNER_OUTCOME
            if domain is SocialMobilityDomain.SKILLS
            else SocialMobilityLayer.OBJECTIVE_OUTCOME
        ),
    )


def _fixture(count: int = 8, *, windows: int = 1):
    lineages = tuple(
        SocialMobilityLineageEntry(
            lineage_token=social_mobility_lineage_token(
                _token(f"entity:a{index}"), _token(f"entity:b{index}")
            ),
            ancestor_token=_token(f"entity:a{index}"),
            descendant_token=_token(f"entity:b{index}"),
            generation_lag=1,
            ancestor_generation=0,
            descendant_generation=1,
        )
        for index in range(count)
    )
    edges = tuple(
        SocialMobilityGenealogyRow(
            parent_token=_token(f"entity:a{index}"),
            child_token=_token(f"entity:b{index}"),
            parent_generation=0,
            child_generation=1,
            established_tick=index,
            window_index=0,
        )
        for index in range(count)
    )
    genealogy = SocialMobilityGenealogyHarvest(
        edges=edges,
        generations=tuple(
            sorted(
                {
                    **{_token(f"entity:a{index}"): 0 for index in range(count)},
                    **{_token(f"entity:b{index}"): 1 for index in range(count)},
                }.items()
            )
        ),
        lineages=lineages,
        coverage=SocialMobilityCoverage.COMPLETE,
        event_count=count,
        owner_count=2 * count,
        max_generation_index=1,
    )
    rows = tuple(
        _outcome(
            f"entity:{side}{index}", index if side == "a" else index + 1, window=window
        )
        for window in range(windows)
        for index in range(count)
        for side in ("a", "b")
    )
    outcomes = SocialMobilityOutcomeHarvest(
        rows=rows,
        coverage=SocialMobilityCoverage.COMPLETE,
        event_count=len(rows),
        owner_count=2 * count,
    )
    return genealogy, outcomes


def test_empty_inputs_return_missing_without_rows() -> None:
    analysis = harvest_social_mobility_analysis(
        genealogy=SocialMobilityGenealogyHarvest(),
        outcomes=SocialMobilityOutcomeHarvest(),
    )
    assert analysis == empty_social_mobility_analysis()
    assert analysis.coverage is SocialMobilityCoverage.MISSING
    assert analysis.row_count == 0


def test_full_evidence_composes_all_row_families() -> None:
    genealogy, outcomes = _fixture()
    analysis = harvest_social_mobility_analysis(genealogy=genealogy, outcomes=outcomes)
    assert analysis.policy_version == "social-mobility.v1"
    assert analysis.domain_rows
    assert analysis.generation_rows
    assert analysis.lag_rows
    assert analysis.pair_rows
    assert analysis.coverage_row is not None
    resources = next(
        row
        for row in analysis.domain_rows
        if row.domain is SocialMobilityDomain.RESOURCES
    )
    assert resources.availability is SocialMobilityAvailability.AVAILABLE
    assert analysis.domain_available_count == 1
    assert analysis.resolved_pair_count == 8
    assert analysis.unresolved_pair_count == 40
    assert analysis.coverage_row.truncated is True
    assert analysis.coverage_row.genealogy_edge_count == 8
    assert analysis.coverage_row.domain_available_count == 1


def test_window_end_filters_later_windows() -> None:
    genealogy, outcomes = _fixture(windows=2)
    analysis = harvest_social_mobility_analysis(
        genealogy=genealogy, outcomes=outcomes, window_end=31
    )
    assert analysis.window_count == 1
    assert all(row.window_index == 0 for row in analysis.domain_rows)


def test_window_end_excludes_later_genealogy_edges() -> None:
    genealogy, outcomes = _fixture(windows=2)
    later_edges = tuple(
        replace(edge, window_index=1, established_tick=40)
        for edge in genealogy.edges
    )
    later = replace(genealogy, edges=later_edges)
    analysis = harvest_social_mobility_analysis(
        genealogy=later, outcomes=outcomes, window_end=31
    )
    assert analysis.coverage is SocialMobilityCoverage.MISSING
    assert analysis.domain_rows == ()
    assert analysis.pair_rows == ()


def test_caps_are_independent_and_reported() -> None:
    genealogy, outcomes = _fixture()
    policy = SocialMobilityAnalysisPolicy(
        max_owners=2,
        max_pairs=1,
        max_domain_rows=1,
    )
    analysis = harvest_social_mobility_analysis(
        genealogy=genealogy, outcomes=outcomes, policy=policy
    )
    assert analysis.owner_count == 2
    assert "social_mobility_owners_truncated" in analysis.notices
    assert "social_mobility_pairs_truncated" in analysis.notices
    assert "social_mobility_domains_truncated" in analysis.notices
    assert len(analysis.notices) <= policy.max_notices


def test_generation_and_lag_caps_are_reported() -> None:
    lineages = []
    edges = []
    generations = {}
    rows = []
    for index in range(8):
        generation = 1 if index < 4 else 2
        ancestor = f"entity:a{index}"
        descendant = f"entity:b{index}"
        lineages.append(
            SocialMobilityLineageEntry(
                lineage_token=social_mobility_lineage_token(
                    _token(ancestor), _token(descendant)
                ),
                ancestor_token=_token(ancestor),
                descendant_token=_token(descendant),
                generation_lag=generation,
                ancestor_generation=0,
                descendant_generation=generation,
            )
        )
        edges.append(
            SocialMobilityGenealogyRow(
                parent_token=_token(ancestor),
                child_token=_token(descendant),
                parent_generation=0,
                child_generation=generation,
                established_tick=index,
                window_index=0,
            )
        )
        generations[_token(ancestor)] = 0
        generations[_token(descendant)] = generation
        rows.append(_outcome(ancestor, index))
        rows.append(_outcome(descendant, index))
    genealogy = SocialMobilityGenealogyHarvest(
        edges=tuple(edges),
        generations=tuple(sorted(generations.items())),
        lineages=tuple(lineages),
        coverage=SocialMobilityCoverage.COMPLETE,
        event_count=8,
        owner_count=16,
        max_generation_index=2,
    )
    outcomes = SocialMobilityOutcomeHarvest(
        rows=tuple(rows),
        coverage=SocialMobilityCoverage.COMPLETE,
        event_count=16,
        owner_count=16,
    )
    policy = SocialMobilityAnalysisPolicy(max_generation_rows=1, max_lag_rows=1)
    analysis = harvest_social_mobility_analysis(
        genealogy=genealogy, outcomes=outcomes, policy=policy
    )
    assert "social_mobility_generations_truncated" in analysis.notices
    assert "social_mobility_lags_truncated" in analysis.notices


def test_digest_is_stable_and_metadata_only() -> None:
    genealogy, outcomes = _fixture()
    first = harvest_social_mobility_analysis(genealogy=genealogy, outcomes=outcomes)
    second = harvest_social_mobility_analysis(genealogy=genealogy, outcomes=outcomes)
    assert first == second
    digest = social_mobility_analysis_digest(first)
    assert digest == social_mobility_analysis_digest(second)
    assert len(digest) == 64
