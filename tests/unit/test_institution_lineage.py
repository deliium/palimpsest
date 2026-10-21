"""Detached institution lineage identity and structural matching."""

from __future__ import annotations

from dataclasses import replace

import pytest

from analysis.institution_lineage import (
    InstitutionLineageEdgeKind,
    InstitutionLineageError,
    compute_institution_lineage,
    episode_id,
)
from analysis.institutional_decay import InstitutionTemporalRow

_OWNER = "owner"
_CONTEXT = "clearing"


def _row(
    tick: int,
    *,
    pattern: str = "p" * 64,
    components: tuple[str, ...] = ("a" * 16, "b" * 16, "c" * 16, "d" * 16),
    context: str = _CONTEXT,
) -> InstitutionTemporalRow:
    return InstitutionTemporalRow(
        owner_id=_OWNER,
        local_pattern_id=pattern,
        observation_tick=tick,
        source_first_tick=tick,
        source_last_tick=tick,
        role_recognition=0.6,
        procedure_recurrence=0.6,
        social_expectation=0.5,
        legitimacy_belief=0.5,
        succession_observed=0.0,
        generational_continuity=0.0,
        recognized=True,
        performed_procedure_keys=("proc",),
        structural_components=components,
        context_key=context,
    )


def _rows(
    start: int, pattern: str, components: tuple[str, ...]
) -> tuple[InstitutionTemporalRow, ...]:
    return tuple(
        _row(tick, pattern=pattern, components=components)
        for tick in range(start, start + 4)
    )


def test_episode_id_rejects_self_declared_mismatch() -> None:
    from analysis.institution_lineage import InstitutionEpisode

    with pytest.raises(InstitutionLineageError, match="episode_id"):
        InstitutionEpisode(
            episode_id="0" * 64,
            owner_id=_OWNER,
            local_pattern_id="p" * 64,
            span_start_tick=1,
            structural_revision=episode_id(_OWNER, "p" * 64, 1, "r" * 16),
            first_tick=1,
            last_tick=4,
            active_ticks=4,
        )


def test_stable_episode_id_after_added_evidence() -> None:
    first = compute_institution_lineage(
        _rows(1, "p" * 64, ("a" * 16, "b" * 16)), as_of_tick=4
    )
    second = compute_institution_lineage(
        _rows(1, "p" * 64, ("a" * 16, "b" * 16))
        + _rows(5, "p" * 64, ("a" * 16, "b" * 16)),
        as_of_tick=8,
    )
    assert [episode.episode_id for episode in first.episodes] == [
        episode.episode_id for episode in second.episodes
    ]


def test_structural_transformation_edge() -> None:
    parent = _rows(1, "p" * 64, ("a" * 16, "b" * 16, "c" * 16, "d" * 16))
    child = _rows(9, "q" * 64, ("a" * 16, "b" * 16))
    result = compute_institution_lineage(parent + child, as_of_tick=12)
    assert [edge.kind for edge in result.edges] == [
        InstitutionLineageEdgeKind.TRANSFORMED
    ]
    assert result.edges[0].shared_components == 2
    assert result.edges[0].jaccard == pytest.approx(0.5)


def test_two_child_split() -> None:
    parent = _rows(1, "p" * 64, ("a" * 16, "b" * 16, "c" * 16, "d" * 16))
    left = _rows(9, "q" * 64, ("a" * 16, "b" * 16))
    right = _rows(9, "r" * 64, ("c" * 16, "d" * 16))
    result = compute_institution_lineage(parent + left + right, as_of_tick=12)
    assert len(result.edges) == 2
    assert all(edge.kind is InstitutionLineageEdgeKind.SPLIT for edge in result.edges)


def test_label_only_similarity_is_not_lineage() -> None:
    parent = _rows(1, "p" * 64, ("a" * 16, "b" * 16))
    child = _rows(9, "q" * 64, ("x" * 16, "y" * 16))
    result = compute_institution_lineage(parent + child, as_of_tick=12)
    assert result.edges == ()


def test_ambiguous_parents_are_excluded() -> None:
    first = _rows(1, "p" * 64, ("a" * 16, "b" * 16, "c" * 16, "d" * 16))
    second = _rows(1, "q" * 64, ("a" * 16, "b" * 16, "c" * 16, "d" * 16))
    child = _rows(9, "r" * 64, ("a" * 16, "b" * 16))
    result = compute_institution_lineage(first + second + child, as_of_tick=12)
    assert result.edges == ()
    assert result.ambiguous


def test_reappearance_after_a_gap_requires_prior_collapse() -> None:
    first = _rows(1, "p" * 64, ("a" * 16, "b" * 16))
    second = _rows(20, "p" * 64, ("a" * 16, "b" * 16))
    without_collapse = compute_institution_lineage(first + second, as_of_tick=24)
    assert len(without_collapse.episodes) == 2
    assert without_collapse.edges == ()

    from analysis.institutional_decay import (
        InstitutionLifecycleResult,
    )

    lifecycle = InstitutionLifecycleResult(
        policy_version="institutional-lifecycle.v1",
        as_of_tick=24,
        states=(),
        windows=(),
        context=(),
        collapsed_intervals=(("owner", "p" * 64, 1, 8),),
    )
    with_collapse = compute_institution_lineage(
        first + second, as_of_tick=24, lifecycle=lifecycle
    )
    assert [edge.kind for edge in with_collapse.edges] == [
        InstitutionLineageEdgeKind.REAPPEARED
    ]


def test_pure_component_growth_is_continued() -> None:
    parent = _rows(1, "p" * 64, ("a" * 16, "b" * 16))
    child = _rows(9, "q" * 64, ("a" * 16, "b" * 16, "c" * 16))
    result = compute_institution_lineage(parent + child, as_of_tick=12)
    assert [edge.kind for edge in result.edges] == [
        InstitutionLineageEdgeKind.CONTINUED
    ]


def test_pruned_parent_becomes_stub_without_confirmed_edge() -> None:
    parent = tuple(
        replace(row, pruned=True)
        for row in _rows(1, "p" * 64, ("a" * 16, "b" * 16))
    )
    child = _rows(9, "q" * 64, ("a" * 16, "b" * 16))
    result = compute_institution_lineage(parent + child, as_of_tick=12)
    assert result.stubs
    assert result.stubs[0].local_pattern_id == "p" * 64
    stub_ids = {stub.episode_id for stub in result.stubs}
    assert all(edge.parent_id not in stub_ids for edge in result.edges)


def test_backward_or_cyclic_edges_are_rejected() -> None:
    from analysis.institution_lineage import (
        InstitutionLineageConfidence,
        InstitutionLineageEdge,
    )

    with pytest.raises(InstitutionLineageError, match="self_edge"):
        InstitutionLineageEdge(
            kind=InstitutionLineageEdgeKind.CONTINUED,
            parent_id="a",
            child_id="a",
            parent_tick=1,
            child_tick=2,
            confidence=InstitutionLineageConfidence.STRUCTURAL_MATCH,
        )
