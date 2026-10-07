"""Deterministic durable copy fidelity transforms."""

from __future__ import annotations

import logging
import random

import pytest

from world.artifacts import ArtifactContent, ArtifactRelation
from world.durable_copy import apply_copy_fidelity

pytestmark = pytest.mark.unit


def _content(*marks: str, relations: tuple[ArtifactRelation, ...] = ()) -> ArtifactContent:
    return ArtifactContent(marks=marks, relations=relations)


def test_perfect_is_identity() -> None:
    parent = _content(
        "a",
        "b",
        "c",
        relations=(ArtifactRelation("a", "near", "b"),),
    )
    result = apply_copy_fidelity(
        parent,
        fidelity_mode="perfect",
        max_mark_edits=2,
        max_relation_edits=1,
    )
    assert result.content == parent
    assert result.mark_edit_count == 0
    assert result.relation_edit_count == 0


def test_mutation_bounded_and_seed_stable(
    caplog: pytest.LogCaptureFixture,
) -> None:
    parent = _content(
        "a",
        "b",
        "c",
        "d",
        relations=(
            ArtifactRelation("a", "near", "b"),
            ArtifactRelation("c", "near", "d"),
        ),
    )
    with caplog.at_level(logging.DEBUG, logger="world.artifacts"):
        first = apply_copy_fidelity(
            parent,
            fidelity_mode="deterministic_mutation",
            max_mark_edits=2,
            max_relation_edits=1,
            rng=random.Random(7),
        )
        second = apply_copy_fidelity(
            parent,
            fidelity_mode="deterministic_mutation",
            max_mark_edits=2,
            max_relation_edits=1,
            rng=random.Random(7),
        )
    assert first.content == second.content
    assert first.mark_edit_count == second.mark_edit_count
    assert first.mark_edit_count <= 2
    assert first.relation_edit_count <= 1
    assert len(first.content.marks) <= len(parent.marks)
    assert set(first.content.marks).issubset(set(parent.marks))
    assert any("durable_copy_fidelity" in r.getMessage() for r in caplog.records)
    assert not any("a,b,c" in r.getMessage() for r in caplog.records)


def test_lossy_reduces_marks() -> None:
    parent = _content("a", "b", "c", "d")
    result = apply_copy_fidelity(
        parent,
        fidelity_mode="lossy",
        max_mark_edits=2,
        max_relation_edits=0,
        rng=random.Random(3),
    )
    assert len(result.content.marks) < len(parent.marks)
    assert result.mark_edit_count >= 1
    assert set(result.content.marks).issubset(set(parent.marks))


def test_same_seed_same_child_across_modes() -> None:
    parent = _content("w", "x", "y", "z")
    for mode in ("deterministic_mutation", "lossy"):
        a = apply_copy_fidelity(
            parent,
            fidelity_mode=mode,
            max_mark_edits=2,
            max_relation_edits=1,
            rng=random.Random(99),
        )
        b = apply_copy_fidelity(
            parent,
            fidelity_mode=mode,
            max_mark_edits=2,
            max_relation_edits=1,
            rng=random.Random(99),
        )
        assert a.content == b.content
        assert a.mark_edit_count == b.mark_edit_count


def test_unknown_fidelity_rejects() -> None:
    with pytest.raises(ValueError, match="durable_copy_fidelity_invalid"):
        apply_copy_fidelity(
            _content("a"),
            fidelity_mode="random",
            max_mark_edits=1,
            max_relation_edits=0,
        )
