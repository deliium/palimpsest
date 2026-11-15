# mypy: ignore-errors
"""Quantized mobility detection over paired ancestor/descendant outcomes."""

from __future__ import annotations

import pytest

from analysis.social_mobility_contract import (
    SocialMobilityAvailability,
    SocialMobilityCoverage,
    SocialMobilityDomain,
    SocialMobilityLayer,
    SocialMobilityMeasure,
    SocialMobilityPersistence,
    social_mobility_lineage_token,
    social_mobility_owner_token,
)
from analysis.social_mobility_detection import (
    detect_social_mobility_rows,
    spearman_rank_correlation_milli,
)
from analysis.social_mobility_genealogy import SocialMobilityGenealogyHarvest
from analysis.social_mobility_outcomes import SocialMobilityOutcomeHarvest
from analysis.social_mobility_policy import SocialMobilityAnalysisPolicy
from analysis.social_mobility_rows import (
    SocialMobilityLineageEntry,
    SocialMobilityOutcomeRow,
)

pytestmark = pytest.mark.unit

_MEASURES = {
    SocialMobilityDomain.RESOURCES: SocialMobilityMeasure.OBSERVED_RESOURCE_ITEM_COUNT,
    SocialMobilityDomain.SKILLS: SocialMobilityMeasure.KNOWN_TECHNIQUE_COUNT,
    SocialMobilityDomain.SOCIAL_INFLUENCE: (
        SocialMobilityMeasure.INBOUND_COMMUNICATION_PARTNER_COUNT
    ),
    SocialMobilityDomain.ORGANIZATION_ROLES: (
        SocialMobilityMeasure.HELD_ORGANIZATION_ROLE_COUNT
    ),
    SocialMobilityDomain.EDUCATIONAL_ACCESS: (
        SocialMobilityMeasure.EDUCATIONAL_ACCESS_RECEIPT_COUNT
    ),
    SocialMobilityDomain.PRODUCTIVE_ASSETS: (
        SocialMobilityMeasure.OBSERVED_PRODUCTIVE_ASSET_COUNT
    ),
}


def _owner(name: str) -> str:
    return social_mobility_owner_token(name)


def _outcome(
    owner: str,
    quantity: int,
    *,
    window: int = 0,
    domain: SocialMobilityDomain = SocialMobilityDomain.RESOURCES,
) -> SocialMobilityOutcomeRow:
    return SocialMobilityOutcomeRow(
        owner_token=_owner(owner),
        generation_index=1,
        tick=window * 32 + 31,
        window_index=window,
        domain=domain,
        measure=_MEASURES[domain],
        quantity=quantity,
        layer=SocialMobilityLayer.OBJECTIVE_OUTCOME,
    )


def _lineage(
    ancestor: str, descendant: str, lag: int = 1
) -> SocialMobilityLineageEntry:
    return SocialMobilityLineageEntry(
        lineage_token=social_mobility_lineage_token(
            _owner(ancestor), _owner(descendant)
        ),
        ancestor_token=_owner(ancestor),
        descendant_token=_owner(descendant),
        generation_lag=lag,
        ancestor_generation=max(0, 3 - lag),
        descendant_generation=3,
    )


def _genealogy(*lineages: SocialMobilityLineageEntry) -> SocialMobilityGenealogyHarvest:
    return SocialMobilityGenealogyHarvest(
        lineages=tuple(lineages),
        generations=tuple(
            sorted(
                {
                    (token, 1)
                    for entry in lineages
                    for token in (entry.ancestor_token, entry.descendant_token)
                }
            )
        ),
        coverage=SocialMobilityCoverage.COMPLETE,
        event_count=1,
        owner_count=2,
        max_generation_index=3,
    )


def _outcomes(*rows: SocialMobilityOutcomeRow) -> SocialMobilityOutcomeHarvest:
    return SocialMobilityOutcomeHarvest(
        rows=tuple(rows),
        coverage=SocialMobilityCoverage.COMPLETE,
        event_count=1,
        owner_count=len({row.owner_token for row in rows}),
    )


def _pairs(count: int, *, reverse: bool = False) -> tuple:
    lineages = []
    rows = []
    for index in range(count):
        ancestor = f"entity:a{index}"
        descendant = f"entity:b{index}"
        lineages.append(_lineage(ancestor, descendant))
        rows.append(_outcome(ancestor, index))
        rows.append(_outcome(descendant, count - 1 - index if reverse else index))
    return tuple(lineages), tuple(rows)


def test_threshold_boundary_marks_insufficient_samples() -> None:
    lineages, rows = _pairs(2)
    result = detect_social_mobility_rows(
        genealogy=_genealogy(*lineages),
        outcomes=_outcomes(*rows),
    )
    domain = next(
        row
        for row in result.domain_rows
        if row.domain is SocialMobilityDomain.RESOURCES
    )
    assert domain.availability is SocialMobilityAvailability.INSUFFICIENT_SAMPLES
    assert (
        domain.persistence_direction is SocialMobilityPersistence.INSUFFICIENT_SAMPLES
    )
    assert domain.resolved_pair_count == 2


def test_perfect_persistence_and_perfect_reversal() -> None:
    lineages, rows = _pairs(8)
    persistent = next(
        row
        for row in detect_social_mobility_rows(
            genealogy=_genealogy(*lineages), outcomes=_outcomes(*rows)
        ).domain_rows
        if row.domain is SocialMobilityDomain.RESOURCES
    )
    assert persistent.persistence_direction is SocialMobilityPersistence.PERSISTENT
    assert persistent.same_bin_share_milli == 1_000
    assert persistent.rank_correlation_milli == 1_000

    lineages, rows = _pairs(8, reverse=True)
    reversed_row = next(
        row
        for row in detect_social_mobility_rows(
            genealogy=_genealogy(*lineages), outcomes=_outcomes(*rows)
        ).domain_rows
        if row.domain is SocialMobilityDomain.RESOURCES
    )
    assert reversed_row.rank_correlation_milli == -1_000
    assert reversed_row.same_bin_share_milli == 0


def test_all_equal_values_bin_zero_correlation_zero() -> None:
    lineages = tuple(
        _lineage(f"entity:a{index}", f"entity:b{index}") for index in range(8)
    )
    rows = tuple(
        _outcome(name, 5)
        for index in range(8)
        for name in (f"entity:a{index}", f"entity:b{index}")
    )
    result = detect_social_mobility_rows(
        genealogy=_genealogy(*lineages), outcomes=_outcomes(*rows)
    )
    domain = next(
        row
        for row in result.domain_rows
        if row.domain is SocialMobilityDomain.RESOURCES
    )
    assert domain.same_bin_share_milli == 1_000
    assert domain.rank_correlation_milli == 0
    assert domain.upward_share_milli == 0
    assert domain.downward_share_milli == 0
    assert all(
        row.ancestor_bin == 0 and row.descendant_bin == 0
        for row in result.pair_rows
        if row.domain is SocialMobilityDomain.RESOURCES
    )


def test_unresolved_pair_is_retained_without_invented_bins() -> None:
    lineages, rows = _pairs(8)
    dangling = _lineage("entity:a99", "entity:b99")
    result = detect_social_mobility_rows(
        genealogy=_genealogy(*lineages, dangling),
        outcomes=_outcomes(*rows),
    )
    unresolved = [row for row in result.pair_rows if not row.resolved]
    assert len(unresolved) >= 1
    assert unresolved[0].ancestor_bin == -1
    assert unresolved[0].descendant_bin == -1
    assert result.coverage.value == "partial"


def test_lag_two_lineage_produces_lag_two_pairs() -> None:
    entry = _lineage("entity:a", "entity:c", lag=2)
    result = detect_social_mobility_rows(
        genealogy=_genealogy(entry),
        outcomes=_outcomes(_outcome("entity:a", 1), _outcome("entity:c", 2)),
    )
    assert result.pair_rows[0].generation_lag == 2


def test_latest_window_survives_per_group_truncation() -> None:
    lineages = (_lineage("entity:a0", "entity:b0"), _lineage("entity:a1", "entity:b1"))
    rows = []
    for window in (0, 1):
        for ancestor, descendant in (
            ("entity:a0", "entity:b0"),
            ("entity:a1", "entity:b1"),
        ):
            rows.append(_outcome(ancestor, window, window=window))
            rows.append(_outcome(descendant, window, window=window))
    policy = SocialMobilityAnalysisPolicy(max_pairs=1, min_mobility_pairs=2)
    result = detect_social_mobility_rows(
        genealogy=_genealogy(*lineages), outcomes=_outcomes(*rows), policy=policy
    )
    resources = [
        row
        for row in result.domain_rows
        if row.domain is SocialMobilityDomain.RESOURCES
    ]
    assert {row.window_index for row in resources} == {0, 1}
    assert "social_mobility_pairs_truncated" in result.notices


def test_empty_evidence_returns_missing() -> None:
    result = detect_social_mobility_rows(
        genealogy=SocialMobilityGenealogyHarvest(),
        outcomes=SocialMobilityOutcomeHarvest(),
    )
    assert result.coverage.value == "missing"
    assert result.pair_rows == ()


def test_spearman_is_quantized_without_negative_zero() -> None:
    assert spearman_rank_correlation_milli([1, 2, 3], [1, 2, 3]) == 1_000
    assert spearman_rank_correlation_milli([1, 2, 3], [3, 2, 1]) == -1_000
    assert spearman_rank_correlation_milli([1, 1, 1], [1, 2, 3]) == 0
    assert str(spearman_rank_correlation_milli([1, 2], [2, 1])) == "-1000"
