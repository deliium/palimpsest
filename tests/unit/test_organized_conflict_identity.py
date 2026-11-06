# ruff: noqa: E501
# mypy: disable-error-code="arg-type,assignment,union-attr,attr-defined,no-untyped-def,no-untyped-call,call-overload,index,type-arg,unused-ignore"
from __future__ import annotations

from types import SimpleNamespace

import pytest

from analysis.organized_conflict_detection import ConflictEpisodeCandidate
from analysis.organized_conflict_identity import (
    ConflictLineageEdge,
    assign_organized_conflict_identities,
    derive_organized_conflict_lineage,
    join_organized_conflict_identities,
)


def _candidate(
    start: int,
    participants=("a" * 16,),
    opponents=("b" * 16,),
    classification="coordinated_conflict",
):
    return ConflictEpisodeCandidate(
        candidate_key=f"key-{start}",
        classification=classification,
        start_tick=start,
        end_tick=start + 3,
        participant_tokens=participants,
        opponent_tokens=opponents,
        side_count=1,
    )


def test_candidate_ids_are_stable_and_content_addressed() -> None:
    first = assign_organized_conflict_identities((_candidate(1),))
    second = assign_organized_conflict_identities((_candidate(1),))
    assert first[0].candidate_id == second[0].candidate_id
    assert first[0].candidate_id.startswith("oc-")
    assert len(first[0].candidate_id) == len("oc-") + 16
    assert (
        first[0].candidate_id
        != assign_organized_conflict_identities((_candidate(2),))[0].candidate_id
    )


def test_lineage_is_forward_only() -> None:
    candidates = assign_organized_conflict_identities((_candidate(1), _candidate(10)))
    edges = derive_organized_conflict_lineage(candidates)
    assert len(edges) == 1
    assert edges[0].from_id == candidates[0].candidate_id
    assert edges[0].to_id == candidates[1].candidate_id
    assert edges[0].tick >= candidates[0].start_tick
    with pytest.raises(ValueError):
        ConflictLineageEdge(
            edge_id="oc-edge-" + "a" * 16,
            from_id="oc-" + "a" * 16,
            to_id="oc-" + "b" * 16,
            kind="continued",
            tick=-1,
        )


def test_lineage_derives_split_and_merge() -> None:
    first = assign_organized_conflict_identities((_candidate(1),))[0]
    branches = assign_organized_conflict_identities(
        (
            _candidate(10, participants=("a" * 16, "c" * 16)),
            _candidate(11, participants=("a" * 16, "d" * 16)),
        )
    )
    edges = derive_organized_conflict_lineage((first, *branches))
    kinds = {edge.kind for edge in edges}
    assert "split" in kinds
    merged = assign_organized_conflict_identities(
        (_candidate(20, participants=("a" * 16, "e" * 16)),)
    )[0]
    merge_edges = derive_organized_conflict_lineage((*branches, merged))
    assert "merge" in {edge.kind for edge in merge_edges}


def test_read_only_identity_joins_never_mutate() -> None:
    candidates = assign_organized_conflict_identities((_candidate(1),))
    org = SimpleNamespace(
        candidate_id="org-" + "a" * 16, participant_tokens=("a" * 16,)
    )
    msoc = SimpleNamespace(
        candidate_id="msoc-" + "a" * 16, participant_tokens=("a" * 16,)
    )
    joined = join_organized_conflict_identities(candidates, (org,), (msoc,))
    assert joined[0].org_ids == (org.candidate_id,)
    assert joined[0].macro_society_ids == (msoc.candidate_id,)
    assert candidates[0].org_ids == ()
    assert org.candidate_id == "org-" + "a" * 16
