"""Holder, record, and teaching grounding."""

from __future__ import annotations

from types import SimpleNamespace

from analysis.models import AppliedActionRow
from analysis.technique_lifecycle import ground_technique_lifecycle


def _audit(**overrides: object) -> SimpleNamespace:
    payload: dict[str, object] = {
        "owner_id": "agent-a",
        "entry_id": "entry-1",
        "kind": "practical",
        "content_key": "tech:hafting",
        "origin": "independent_discovery",
        "lineage_root_id": "root-1",
        "hop_index": 0,
        "acquired_tick": 1,
        "tick": 1,
        "active": True,
        "parent_entry_ids": (),
        "mutated": False,
        "evidence_refs": (),
        "capability_anchor": "craft",
    }
    payload.update(overrides)
    return SimpleNamespace(**payload)


def _global():
    rows = ground_technique_lifecycle(
        (_audit(),),
        as_of_tick=2,
        applied_actions=(
            AppliedActionRow(
                tick=1,
                ordinal=0,
                agent_id="agent-a",
                action_kind="move",
                location_id="loc-1",
            ),
        ),
    )
    return rows[0]


def test_one_living_holder() -> None:
    row = _global()
    assert row.living_holder_ids == ("agent-a",)
    assert row.intact_record_count == 0
    assert row.teaching_chain_intact is False


def test_dead_former_holder_is_dropped() -> None:
    rows = ground_technique_lifecycle(
        (_audit(),),
        as_of_tick=5,
        death_ticks={"agent-a": 3},
        applied_actions=(
            AppliedActionRow(
                tick=1,
                ordinal=0,
                agent_id="agent-a",
                action_kind="move",
                location_id="loc-1",
            ),
        ),
    )
    assert rows[0].living_holder_ids == ()


def test_intact_cited_record_counts() -> None:
    rows = ground_technique_lifecycle(
        (_audit(evidence_refs=("artifact:mark-1",)),),
        as_of_tick=2,
        artifact_rows=(
            {
                "artifact_id": "mark-1",
                "integrity": "intact",
                "location_id": "loc-1",
            },
        ),
    )
    assert rows[0].intact_record_count == 1


def test_destroyed_cited_record_contributes_zero() -> None:
    rows = ground_technique_lifecycle(
        (_audit(evidence_refs=("artifact:mark-1",)),),
        as_of_tick=2,
        artifact_rows=(
            {
                "artifact_id": "mark-1",
                "integrity": "destroyed",
                "location_id": "loc-1",
            },
        ),
    )
    assert rows[0].intact_record_count == 0


def test_uncited_artifact_ignored() -> None:
    rows = ground_technique_lifecycle(
        (_audit(),),
        as_of_tick=2,
        artifact_rows=(
            {
                "artifact_id": "other",
                "integrity": "intact",
                "location_id": "loc-1",
            },
        ),
    )
    assert rows[0].intact_record_count == 0


def test_holder_without_action_row_is_unknown_place() -> None:
    rows = ground_technique_lifecycle((_audit(),), as_of_tick=2)
    assert rows[0].location_ids == ("location:unknown",)


def test_teaching_origin_marks_chain_intact() -> None:
    rows = ground_technique_lifecycle(
        (_audit(origin="teaching", hop_index=1),),
        as_of_tick=2,
    )
    assert rows[0].teaching_chain_intact is True
