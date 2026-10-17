"""Hybrid practices resolve only detached cross-community lineage."""

from __future__ import annotations

from analysis.contact_hybrid_practice import (
    ContactCulturalLineageRow,
    ContactMergeRow,
    ContactNarrativeRootRow,
    ContactPracticalLineageRow,
    compute_contact_hybrid_practice,
    compute_contact_hybrid_practice_metric,
)
from analysis.society_emergence import CandidateCommunityRow


def _communities() -> tuple[CandidateCommunityRow, ...]:
    return (
        CandidateCommunityRow.from_members(
            person_ids=("a-1", "a-2"), lane_coverage=("interaction",)
        ),
        CandidateCommunityRow.from_members(
            person_ids=("b-1",), lane_coverage=("interaction",)
        ),
    )


def test_same_community_combination_is_not_hybrid() -> None:
    result = compute_contact_hybrid_practice(
        _communities(),
        practical=(ContactPracticalLineageRow("a-1", ("a-2",), "combination", 3),),
    )
    assert result.hybrid_practical_knowledge_count == 0
    assert result.resolvable_lineage_entry_count == 1


def test_cross_community_combination_is_hybrid() -> None:
    result = compute_contact_hybrid_practice(
        _communities(),
        practical=(
            ContactPracticalLineageRow("a-1", ("a-2", "b-1"), "combination", 3),
        ),
    )
    assert result.hybrid_practical_knowledge_count == 1
    assert result.intercommunity_combination_count == 1


def test_unresolved_parent_is_not_hybrid() -> None:
    result = compute_contact_hybrid_practice(
        _communities(),
        practical=(
            ContactPracticalLineageRow("a-1", ("a-2", "ghost"), "combination", 3),
        ),
    )
    assert result.hybrid_practical_knowledge_count == 0
    assert result.unresolved_lineage_count == 1


def test_recombined_cultural_belief_with_cross_parents_is_hybrid() -> None:
    result = compute_contact_hybrid_practice(
        _communities(),
        cultural=(ContactCulturalLineageRow("a-1", ("a-2", "b-1"), True, 4),),
    )
    assert result.hybrid_cultural_belief_count == 1


def test_recombined_with_unknown_donor_is_not_cross_hybrid() -> None:
    result = compute_contact_hybrid_practice(
        _communities(),
        cultural=(ContactCulturalLineageRow("a-1", ("ghost",), True, 4),),
    )
    assert result.hybrid_cultural_belief_count == 0
    assert result.unresolved_lineage_count == 1


def test_shared_narrative_root_across_communities_counts_once() -> None:
    result = compute_contact_hybrid_practice(
        _communities(),
        narratives=(
            ContactNarrativeRootRow("a-1", "root-1", 1),
            ContactNarrativeRootRow("b-1", "root-1", 2),
            ContactNarrativeRootRow("a-2", "root-2", 2),
        ),
    )
    assert result.narrative_shared_root_pair_count == 1


def test_naming_merge_across_communities_counts() -> None:
    result = compute_contact_hybrid_practice(
        _communities(),
        merges=(ContactMergeRow("a-1", ("b-1",), "naming", 5),),
    )
    assert result.narrative_merge_count == 1


def test_metric_reports_rate_and_denominator() -> None:
    result = compute_contact_hybrid_practice(
        _communities(),
        practical=(
            ContactPracticalLineageRow("a-1", ("a-2", "b-1"), "combination", 3),
            ContactPracticalLineageRow("a-1", ("a-2",), "combination", 4),
        ),
    )
    document = compute_contact_hybrid_practice_metric(
        result, run_id="run", input_revision="rev"
    )
    assert document.values["resolvable_lineage_entry_count"] == 2
    assert document.values["hybridization_rate"] == 0.5
    assert document.availability.value == "present"


def test_convention_merge_across_communities_counts() -> None:
    result = compute_contact_hybrid_practice(
        _communities(),
        merges=(ContactMergeRow("a-1", ("b-1",), "convention", 5),),
    )
    assert result.narrative_merge_count == 1
