# mypy: ignore-errors
"""Candidates, forward-only lineage, read-only joins, and researcher alignment."""

from __future__ import annotations

import dataclasses
import logging
from pathlib import Path

import pytest

from analysis.migration_displacement_alignment import (
    MIGRATION_ALIGNMENTS,
    align_migration_interpretations,
)
from analysis.migration_displacement_contract import (
    MIGRATION_CANDIDATE_PREFIX,
    analysis_migration_candidate_id,
)
from analysis.migration_displacement_detection import detect_migration_waves
from analysis.migration_displacement_identity import (
    join_read_only_identities,
    link_migration_lineage,
    migration_candidate_row,
    migration_candidates_from_rows,
)
from tests.unit.migration_displacement_analysis_helpers import (
    POLICY,
    cause,
    loc,
    movement,
    p,
)

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2] / "src"


def token(material: str, kind: str = "wave") -> str:
    return analysis_migration_candidate_id(kind, material)


def candidate(
    material,
    members,
    *,
    first=1,
    last=None,
    destination="loc-b",
    kind="wave",
    classification="unknown",
):
    return migration_candidate_row(
        kind,
        token(material, kind),
        first_tick=first,
        last_tick=first + 4 if last is None else last,
        member_count=len(members),
        destination_token=loc(destination),
        classification=classification,
        member_tokens=tuple(p(item) for item in members),
    )


def relations(rows):
    return sorted(
        (row.relation, row.candidate_token, row.previous_token) for row in rows
    )


def test_candidate_tokens_are_content_addressed() -> None:
    first = token("material-1")
    assert first == token("material-1")
    assert first != token("material-2")
    assert first != token("material-1", "cluster")
    assert first.startswith(MIGRATION_CANDIDATE_PREFIX)
    movements = (
        movement("agent-1", "loc-a", "loc-b", 1),
        movement("agent-2", "loc-a", "loc-b", 2),
    )
    reversed_order = tuple(reversed(movements))
    one = detect_migration_waves(movements, (), (), POLICY)
    two = detect_migration_waves(reversed_order, (), (), POLICY)
    assert one[0].wave_token == two[0].wave_token
    with pytest.raises(ValueError, match="migration_identity: candidate_token"):
        migration_candidate_row("wave", "org-1234")
    with pytest.raises(ValueError, match="migration_identity: candidate_token"):
        migration_candidate_row("wave", "mig-UPPER")
    with pytest.raises(ValueError):
        analysis_migration_candidate_id("wave", "")


def test_lineage_continued_transformed_split_merge_dissolved_emerged() -> None:
    old = candidate("old", ("a1", "a2", "a3", "a4"), first=1, last=5)
    same = candidate("old", ("a1", "a2", "a3", "a4"), first=1, last=9)
    moved = candidate("moved", ("a1", "a2", "a3", "a9"), first=6, destination="loc-c")
    assert relations(link_migration_lineage((old,), (same,), POLICY)) == [
        ("continued", same.candidate_token, old.candidate_token)
    ]
    assert relations(link_migration_lineage((old,), (moved,), POLICY)) == [
        ("transformed", moved.candidate_token, old.candidate_token)
    ]
    half_one = candidate("half-1", ("a1", "a2"), first=6)
    half_two = candidate("half-2", ("a3", "a4"), first=6)
    split = link_migration_lineage((old,), (half_one, half_two), POLICY)
    assert {row.relation for row in split} == {"split"}
    assert len(split) == 2
    left = candidate("left", ("b1", "b2"), first=1)
    right = candidate("right", ("b3", "b4"), first=1)
    merged = candidate("merged", ("b1", "b2", "b3", "b4"), first=6)
    merge = link_migration_lineage((left, right), (merged,), POLICY)
    assert {row.relation for row in merge} == {"merge"}
    assert len(merge) == 2
    gone = link_migration_lineage((old,), (), POLICY)
    assert [(r.relation, r.candidate_token) for r in gone] == [("dissolved", "none")]
    assert gone[0].previous_token == old.candidate_token
    fresh = link_migration_lineage((), (old,), POLICY)
    assert [(r.relation, r.previous_token) for r in fresh] == [("emerged", "none")]
    unrelated = candidate("other", ("z1", "z2"), first=7)
    assert {
        r.relation for r in link_migration_lineage((old,), (unrelated,), POLICY)
    } == {
        "dissolved",
        "emerged",
    }


def test_lineage_is_forward_only_and_sorted() -> None:
    early = candidate("early", ("a1", "a2"), first=1, last=3)
    late = candidate("late", ("a1", "a2"), first=10, last=12)
    # A later previous candidate cannot be an ancestor of an earlier one.
    with pytest.raises(ValueError, match="lineage_not_forward"):
        link_migration_lineage((late,), (early,), POLICY)
    rows = link_migration_lineage(
        (early,),
        (
            candidate("z-new", ("c1", "c2"), first=20),
            candidate("a-new", ("d1", "d2"), first=4),
            late,
        ),
        POLICY,
    )
    keys = [(r.first_tick, r.candidate_token, r.previous_token) for r in rows]
    assert keys == sorted(keys)
    # The previous candidate is never rewritten.
    assert early.last_tick == 3 and early.candidate_token == token("early")
    with pytest.raises(ValueError, match="migration_detection: invalid_policy"):
        link_migration_lineage((), (), object())


def test_org_and_msoc_joins_are_read_only() -> None:
    row = candidate("wave-1", ("a1", "a2"))
    org = {"org-" + "1" * 8: (p("a1"), p("zz"))}
    msoc = {"msoc-" + "2" * 8: (p("a2"),), "msoc-" + "3" * 8: (p("nobody"),)}
    snapshot = (dict(org), dict(msoc))
    joins = join_read_only_identities((row,), org, msoc)
    assert joins == (
        (row.candidate_token, "msoc-" + "2" * 8),
        (row.candidate_token, "org-" + "1" * 8),
    )
    assert (org, msoc) == snapshot
    assert join_read_only_identities((row,), {}, {}) == ()
    assert join_read_only_identities((row,), None, None) == ()
    with pytest.raises(ValueError, match="migration_identity: read_only_identity"):
        join_read_only_identities((row,), {"mig-" + "a" * 32: (p("a1"),)}, {})
    with pytest.raises(ValueError, match="migration_identity: read_only_identity"):
        join_read_only_identities((row,), {}, {"org-" + "1" * 8: (p("a1"),)})


def test_no_org_or_msoc_identity_is_minted() -> None:
    movements = (
        movement("agent-1", "loc-a", "loc-b", 1),
        movement("agent-2", "loc-a", "loc-b", 2),
    )
    waves = detect_migration_waves(movements, (), (), POLICY)
    candidates = migration_candidates_from_rows(waves, (), ())
    assert all(item.candidate_token.startswith("mig-") for item in candidates)
    org = {"org-" + "1" * 8: tuple(waves[0].participant_tokens)}
    joins = join_read_only_identities(candidates, org, {})
    assert {target for _, target in joins} <= set(org)
    lineage = link_migration_lineage((), candidates, POLICY)
    tokens = {row.candidate_token for row in lineage} | {
        row.previous_token for row in lineage
    }
    assert not any(item.startswith(("org-", "msoc-")) for item in tokens)
    source = (ROOT / "analysis" / "migration_displacement_identity.py").read_text(
        encoding="utf-8"
    )
    assert "organization_id" not in source and "society_id" not in source


def _wave(classification_causes=()):
    movements = (
        movement("agent-1", "loc-a", "loc-b", 1),
        movement("agent-2", "loc-a", "loc-b", 2),
    )
    return detect_migration_waves(movements, classification_causes, (), POLICY)


def align(causes, waves, outcomes=()):
    return {
        (row.owner_token, row.candidate_token): row
        for row in align_migration_interpretations(causes, waves, outcomes)
    }


def test_alignment_missing_evidence_is_unresolved(caplog) -> None:
    (wave,) = _wave()
    with caplog.at_level(logging.DEBUG):
        rows = align((), (wave,))
    assert {row.alignment for row in rows.values()} == {"unresolved"}
    assert {row.basis for row in rows.values()} == {"no-owner-cause"}
    assert "migration_alignment_unresolved count=2" in caplog.text
    assert p("agent-1") not in caplog.text and wave.wave_token not in caplog.text
    # An unclassified wave leaves a present cause unresolved, never inconsistent.
    own = (cause("agent-1", "conflict", anchor="attack", tick=1),)
    rows = align(own, (wave,))
    assert rows[(p("agent-1"), wave.wave_token)].alignment == "unresolved"
    # Partial coverage is unresolved too.
    partial_wave = _wave((cause("agent-1", "environmental_hazard"),))[0]
    partial_wave = dataclasses.replace(partial_wave, coverage="partial")
    rows = align((cause("agent-1", "environmental_hazard"),), (partial_wave,))
    assert rows[(p("agent-1"), partial_wave.wave_token)].alignment == "unresolved"


def test_inconsistency_requires_positive_contradiction() -> None:
    causes_all = (
        cause("agent-1", "environmental_hazard"),
        cause("agent-2", "opportunity"),
    )
    (mixed_wave,) = _wave(causes_all)
    rows = align(causes_all, (mixed_wave,))
    assert rows[(p("agent-1"), mixed_wave.wave_token)].alignment == "consistent"
    assert rows[(p("agent-2"), mixed_wave.wave_token)].alignment == "consistent"
    # The wave is positively opportunity-only; an owner who believes in a hazard
    # contradicts it.
    wave_causes = (
        cause("agent-1", "opportunity"),
        cause("agent-2", "opportunity"),
    )
    (opp_wave,) = _wave(wave_causes)
    assert opp_wave.displacement_classification == "not_displacement_like"
    contradicting = (
        cause("agent-1", "opportunity"),
        cause("agent-2", "opportunity"),
        cause(
            "agent-1", "environmental_hazard", tick=2, status="active", token="mdc-x"
        ),
    )
    rows = align(contradicting, (opp_wave,))
    assert rows[(p("agent-1"), opp_wave.wave_token)].alignment == "unresolved"
    only_hazard = (cause("agent-3", "environmental_hazard"),)
    rows = align(wave_causes + only_hazard, (opp_wave,))
    assert rows[(p("agent-3"), "none")].alignment == "not_applicable"
    # Owner-only contradiction with a positive wave label.
    (disp_wave,) = _wave((cause("agent-1", "environmental_hazard"),))
    rows = align((cause("agent-2", "opportunity", tick=2),), (disp_wave,))
    assert rows[(p("agent-2"), disp_wave.wave_token)].alignment == "inconsistent"
    assert rows[(p("agent-1"), disp_wave.wave_token)].alignment == "unresolved"
    assert MIGRATION_ALIGNMENTS == frozenset(
        {"consistent", "unresolved", "inconsistent", "not_applicable"}
    )
    # An unusable owner cause is unresolved, not inconsistent.
    rows = align(
        (cause("agent-2", "opportunity", status="contradicted"),), (disp_wave,)
    )
    assert rows[(p("agent-2"), disp_wave.wave_token)].alignment == "unresolved"


def test_alignment_does_not_reach_cognition_inputs() -> None:
    needles = (
        "migration_displacement_alignment",
        "align_migration_interpretations",
        "MigrationAlignmentRow",
    )
    for package in ("agents", "world", "simulation", "memory", "social", "llm"):
        for path in (ROOT / package).rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            for needle in needles:
                assert needle not in text, (path.name, needle)
    # The cognition projection never mentions researcher alignment labels.
    cognition = (ROOT / "agents" / "cognition" / "migration_displacement.py").read_text(
        encoding="utf-8"
    )
    assert "alignment" not in cognition.lower()
