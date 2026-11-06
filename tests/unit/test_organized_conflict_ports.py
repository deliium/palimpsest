# ruff: noqa: E501
# mypy: disable-error-code="arg-type,assignment,union-attr,attr-defined,no-untyped-def,no-untyped-call,call-overload,index,type-arg,unused-ignore"
from __future__ import annotations

import pytest

from simulation.organized_conflict_codec import finalize_organized_conflict_snapshot
from simulation.organized_conflict_models import (
    ORGANIZED_CONFLICT_SNAPSHOT_SCHEMA,
    OrganizedConflictEpisodeRow,
    OrganizedConflictInterpretationRow,
    OrganizedConflictPlanRow,
    OrganizedConflictSnapshot,
    OrganizedConflictSummaryRow,
)
from simulation.organized_conflict_paging import (
    select_conflict_episode_detail,
    select_conflict_episodes,
    select_conflict_interpretations,
    select_conflict_plan_detail,
    select_conflict_plans,
)
from simulation.organized_conflict_ports import (
    ORGANIZED_CONFLICT_CURSOR_PURPOSES,
    OrganizedConflictCursor,
    organized_conflict_cursor_matches,
    organized_conflict_query_fingerprint,
)

HEX = "a" * 16


def _snapshot() -> OrganizedConflictSnapshot:
    episode = OrganizedConflictEpisodeRow(
        episode_id="oc-" + HEX,
        classification="coordinated_conflict",
        start_tick=1,
        end_tick=5,
        participant_tokens=(HEX,),
    )
    plan = OrganizedConflictPlanRow(
        plan_id="ocp-" + HEX,
        owner_token=HEX,
        operation="coordinated_attack",
        target_kind="agent",
        status="active",
        participant_count=1,
        tick=1,
    )
    interpretation = OrganizedConflictInterpretationRow(
        interpretation_id="oci-" + HEX,
        owner_token=HEX,
        episode_id="oc-" + HEX,
        kind="coordinated_conflict",
        alignment="consistent",
        tick=1,
    )
    return finalize_organized_conflict_snapshot(
        OrganizedConflictSnapshot(
            schema_version=ORGANIZED_CONFLICT_SNAPSHOT_SCHEMA,
            policy_version="organized-conflict-snapshot.v1",
            run_id="run-conflict",
            publication_id="oc-pub-" + "0" * 16,
            digest="0" * 64,
            summary=OrganizedConflictSummaryRow(episode_count=1),
            episodes=(episode,),
            plans=(plan,),
            interpretations=(interpretation,),
        )
    )


def test_six_cursor_purposes_exist() -> None:
    assert ORGANIZED_CONFLICT_CURSOR_PURPOSES == frozenset(
        {"summary", "episodes", "episode", "plans", "plan", "interpretations"}
    )
    with pytest.raises(ValueError):
        OrganizedConflictCursor(purpose="other", fingerprint="x")


def test_paging_is_bounded_and_sorted() -> None:
    snapshot = _snapshot()
    page = select_conflict_episodes(snapshot, limit=1)
    assert len(page.rows) == 1
    assert page.rows[0].episode_id == "oc-" + HEX
    assert page.next_key is None
    empty = select_conflict_episodes(snapshot, after="oc-" + "f" * 16)
    assert empty.rows == ()
    assert select_conflict_plans(snapshot).rows[0].plan_id == "ocp-" + HEX
    assert (
        select_conflict_interpretations(snapshot).rows[0].interpretation_id
        == "oci-" + HEX
    )


def test_detail_truncation_is_explicit() -> None:
    snapshot = _snapshot()
    episodes, participants, truncated = select_conflict_episode_detail(
        snapshot, "oc-" + HEX
    )
    assert len(episodes) == 1
    assert participants == ()
    assert truncated is False
    plans, rows, truncated = select_conflict_plan_detail(snapshot, "ocp-" + HEX)
    assert len(plans) == 1
    assert rows == ()
    assert truncated is False


def test_cursor_fingerprint_binds_every_field() -> None:
    base = organized_conflict_query_fingerprint(
        run_id="run",
        publication_id="pub",
        digest="d",
        purpose="episodes",
        filters={"classification": "coordinated_conflict"},
    )
    assert organized_conflict_cursor_matches(
        OrganizedConflictCursor(purpose="episodes", fingerprint=base), base
    )
    for changed in (
        {"run_id": "run2"},
        {"publication_id": "pub2"},
        {"digest": "d2"},
        {"purpose": "plans"},
        {"filters": {"classification": "individual_violence"}},
    ):
        arguments = {
            "run_id": "run",
            "publication_id": "pub",
            "digest": "d",
            "purpose": "episodes",
            "filters": {"classification": "coordinated_conflict"},
        }
        arguments.update(changed)
        assert (
            organized_conflict_query_fingerprint(**arguments) != base
        )
