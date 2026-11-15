# mypy: ignore-errors
"""Atomic social-mobility filesystem store: quota, idempotency, corruption."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from persistence.social_mobility_filesystem import (
    SOCIAL_MOBILITY_STORE_VERSION,
    SocialMobilityPublisherOptions,
    create_social_mobility_publisher,
    create_social_mobility_reader,
)
from simulation.social_mobility_codec import (
    encode_social_mobility_snapshot,
    finalize_social_mobility_snapshot,
)
from simulation.social_mobility_models import (
    SOCIAL_MOBILITY_POLICY_VERSION,
    SOCIAL_MOBILITY_SNAPSHOT_VERSION,
    SocialMobilityDomainRecord,
    SocialMobilitySnapshot,
    empty_social_mobility_snapshot,
)

pytestmark = pytest.mark.unit


def _snapshot(offset: int = 0) -> SocialMobilitySnapshot:
    base = empty_social_mobility_snapshot("run-1")
    domain = SocialMobilityDomainRecord(
        window_index=offset,
        window_tick=offset * 32 + 31,
        domain="resources",
        measure="observed_resource_item_count",
        pair_count=8,
        resolved_pair_count=8,
        rank_correlation_milli=100 + offset,
        same_bin_share_milli=500,
        upward_share_milli=300,
        downward_share_milli=200,
        mean_absolute_rank_change_milli=250,
        persistence_direction="persistent",
        coverage="complete",
        availability="available",
    )
    summary = replace(
        base.summary,
        domain_row_count=1,
        window_count=1,
        owner_count=8,
        generation_count=2,
        genealogy_edge_count=8,
        pair_count=8,
        resolved_pair_count=8,
        unresolved_pair_count=0,
        domain_available_count=1,
        coverage="complete",
        evidence_coverage="complete",
        domain_coverage="complete",
        generation_coverage="complete",
    )
    return finalize_social_mobility_snapshot(
        SocialMobilitySnapshot(
            run_id="run-1",
            schema_version=SOCIAL_MOBILITY_SNAPSHOT_VERSION,
            policy_version=SOCIAL_MOBILITY_POLICY_VERSION,
            summary=summary,
            domains=(domain,),
        )
    )


def test_publish_and_read_round_trip(tmp_path: Path) -> None:
    publisher = create_social_mobility_publisher(tmp_path)
    reader = create_social_mobility_reader(tmp_path)
    snapshot = _snapshot()
    receipt = publisher.publish(snapshot)
    assert receipt.reason_code == "published"
    assert receipt.stored is True
    loaded = reader.read_snapshot("run-1")
    assert loaded == snapshot


def test_identical_republish_is_idempotent(tmp_path: Path) -> None:
    publisher = create_social_mobility_publisher(tmp_path)
    snapshot = _snapshot()
    first = publisher.publish(snapshot)
    second = publisher.publish(snapshot)
    assert first.stored is True
    assert second.stored is False
    assert second.digest == first.digest


def test_digest_conflict_for_same_publication_id_fails(tmp_path: Path) -> None:
    publisher = create_social_mobility_publisher(tmp_path)
    first = _snapshot(0)
    second = _snapshot(1)
    publisher.publish(first)
    conflicting = replace(
        second,
        publication_id=first.publication_id,
        digest=second.digest,
    )
    with pytest.raises(ValueError, match="social_mobility_publication_exists"):
        publisher.publish(conflicting)


def test_publication_count_quota(tmp_path: Path) -> None:
    publisher = create_social_mobility_publisher(
        tmp_path, options=SocialMobilityPublisherOptions(max_publications=1)
    )
    publisher.publish(_snapshot(0))
    with pytest.raises(ValueError, match="social_mobility_store_quota_exceeded"):
        publisher.publish(_snapshot(1))


def test_cumulative_byte_quota_across_three_publications(tmp_path: Path) -> None:
    first, second, third = _snapshot(0), _snapshot(1), _snapshot(2)
    size = len(encode_social_mobility_snapshot(first))
    publisher = create_social_mobility_publisher(
        tmp_path,
        options=SocialMobilityPublisherOptions(max_bytes=size * 2 + size // 2),
    )
    publisher.publish(first)
    publisher.publish(second)
    with pytest.raises(ValueError, match="social_mobility_store_quota_exceeded"):
        publisher.publish(third)


def test_corrupt_state_and_missing_reports(tmp_path: Path) -> None:
    reader = create_social_mobility_reader(tmp_path)
    with pytest.raises(ValueError, match="social_mobility_store_missing"):
        reader.read_snapshot("run-1")
    run_dir = tmp_path / "run-1"
    run_dir.mkdir(parents=True)
    (run_dir / "state.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError, match="social_mobility_store_corrupt"):
        reader.read_snapshot("run-1")


def test_state_file_carries_store_version_and_bytes(tmp_path: Path) -> None:
    publisher = create_social_mobility_publisher(tmp_path)
    publisher.publish(_snapshot())
    state = json.loads((tmp_path / "run-1" / "state.json").read_text())
    assert state["store_version"] == SOCIAL_MOBILITY_STORE_VERSION
    entry = next(iter(state["publications"].values()))
    assert entry["bytes"] > 0
    assert (tmp_path / "run-1" / "store.lock").exists()
