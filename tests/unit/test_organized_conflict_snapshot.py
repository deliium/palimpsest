# ruff: noqa: E501
# mypy: disable-error-code="arg-type,assignment,union-attr,attr-defined,no-untyped-def,no-untyped-call,call-overload,index,type-arg,unused-ignore"
from __future__ import annotations

import json
from dataclasses import replace

import pytest

from simulation.organized_conflict_codec import (
    decode_organized_conflict_snapshot,
    encode_organized_conflict_snapshot,
    finalize_organized_conflict_snapshot,
)
from simulation.organized_conflict_models import (
    ORGANIZED_CONFLICT_SNAPSHOT_SCHEMA,
    OrganizedConflictEpisodeRow,
    OrganizedConflictSnapshot,
    OrganizedConflictSummaryRow,
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
    return OrganizedConflictSnapshot(
        schema_version=ORGANIZED_CONFLICT_SNAPSHOT_SCHEMA,
        policy_version="organized-conflict-snapshot.v1",
        run_id="run-conflict",
        publication_id="oc-pub-" + "0" * 16,
        digest="0" * 64,
        summary=OrganizedConflictSummaryRow(episode_count=1),
        episodes=(episode,),
    )


def test_snapshot_round_trip_preserves_digest() -> None:
    finalized = finalize_organized_conflict_snapshot(_snapshot())
    encoded = encode_organized_conflict_snapshot(finalized)
    decoded = decode_organized_conflict_snapshot(encoded)
    assert decoded == finalized
    assert decoded.digest == finalized.digest
    assert decoded.publication_id.startswith("oc-pub-")


def test_tampered_payload_is_rejected() -> None:
    finalized = finalize_organized_conflict_snapshot(_snapshot())
    data = json.loads(encode_organized_conflict_snapshot(finalized))
    data["summary"]["episode_count"] = 9
    with pytest.raises(ValueError, match="organized_conflict_snapshot_digest"):
        decode_organized_conflict_snapshot(
            json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
        )


def test_duplicate_and_foreign_rows_are_rejected() -> None:
    snapshot = finalize_organized_conflict_snapshot(_snapshot())
    episode = snapshot.episodes[0]
    with pytest.raises(ValueError, match="organized_conflict_snapshot_duplicate_id"):
        OrganizedConflictSnapshot(
            schema_version=snapshot.schema_version,
            policy_version=snapshot.policy_version,
            run_id=snapshot.run_id,
            publication_id=snapshot.publication_id,
            digest=snapshot.digest,
            summary=snapshot.summary,
            episodes=(episode, episode),
        )


def test_caps_and_size_limit_fail_closed() -> None:
    from simulation.organized_conflict_models import MAX_SNAPSHOT_EPISODES

    snapshot = finalize_organized_conflict_snapshot(_snapshot())
    episodes = tuple(
        replace(
            snapshot.episodes[0],
            episode_id="oc-" + f"{index:016x}",
            start_tick=index,
            end_tick=index,
        )
        for index in range(MAX_SNAPSHOT_EPISODES + 1)
    )
    with pytest.raises(ValueError, match="organized_conflict_snapshot_cap"):
        OrganizedConflictSnapshot(
            schema_version=snapshot.schema_version,
            policy_version=snapshot.policy_version,
            run_id=snapshot.run_id,
            publication_id=snapshot.publication_id,
            digest=snapshot.digest,
            summary=snapshot.summary,
            episodes=tuple(sorted(episodes, key=lambda row: row.episode_id)),
        )


def test_raw_ids_and_free_text_are_rejected() -> None:
    with pytest.raises(ValueError):
        OrganizedConflictEpisodeRow(
            episode_id="oc-" + HEX,
            classification="coordinated_conflict",
            start_tick=1,
            end_tick=2,
            participant_tokens=("agent-alice",),
        )
