"""Filesystem store: atomicity, quotas, and read-side verification."""

from __future__ import annotations

import pytest

from analysis.macro_society_contract import MacroSocietyLane
from analysis.macro_society_evidence import (
    MacroSocietyEdge,
    MacroSocietyWindowEvidence,
)
from experiments.macro_society_publication import (
    MacroSocietyHarvest,
    build_macro_society_harvest_result,
)
from persistence.macro_society_filesystem import (
    create_macro_society_publisher,
    create_macro_society_reader,
)
from simulation.macro_society_codec import encode_macro_society_snapshot
from simulation.macro_society_models import MacroSocietyArtifactError
from simulation.macro_society_ports import MacroSocietyPublication

PERSONS = tuple(f"person-{index}" for index in range(1, 9))


def _harvest(*, generated_tick: int = 9) -> MacroSocietyHarvest:
    edges = tuple(
        MacroSocietyEdge(MacroSocietyLane.INTERACTION, source, target, 0)
        for index, source in enumerate(PERSONS[:4])
        for target in PERSONS[:4][index + 1 :]
    )
    window = MacroSocietyWindowEvidence(
        window_index=0,
        tick_start=0,
        tick_end=9,
        person_ids=PERSONS,
        edges=edges,
    )
    return MacroSocietyHarvest(
        run_id="run-1",
        input_revision="rev-1",
        windows=(window,),
        objective_rows=(
            {"region_id": "region-a", "tick": 0, "population_count": 8},
        ),
        generated_tick=generated_tick,
    )


def _publication(*, generated_tick: int = 9):
    result = build_macro_society_harvest_result(_harvest(generated_tick=generated_tick))
    payload = encode_macro_society_snapshot(result.snapshot)
    return MacroSocietyPublication(
        snapshot=result.snapshot,
        payload=payload,
        created_at_utc="2026-10-30T00:00:00Z",
    )


def test_publish_then_read_round_trips(tmp_path) -> None:
    publisher = create_macro_society_publisher(tmp_path)
    reader = create_macro_society_reader(tmp_path)
    assert publisher is not None and reader is not None
    publication = _publication()
    ref = publisher.publish(publication)
    assert ref.publication_id == publication.publication_id

    summary = reader.read_summary("run-1")
    assert summary.publication_id == publication.publication_id
    assert summary.candidate_count == 1
    assert summary.window_count == 1

    rows, next_offset = reader.read_candidates(
        "run-1", publication_id=None, offset=0, limit=10
    )
    assert len(rows) == 1
    assert next_offset is None

    lineage, next_offset = reader.read_lineage(
        "run-1", publication_id=None, offset=0, limit=10
    )
    assert len(lineage) == 1
    assert next_offset is None

    candidate = reader.read_candidate(
        "run-1", rows[0].macro_society_id, publication_id=None
    )
    assert candidate == rows[0]


def test_duplicate_publication_is_rejected(tmp_path) -> None:
    publisher = create_macro_society_publisher(tmp_path)
    assert publisher is not None
    publication = _publication()
    publisher.publish(publication)
    with pytest.raises(
        MacroSocietyArtifactError, match="macro_society_publication_exists"
    ):
        publisher.publish(publication)


def test_publication_quota_is_enforced(tmp_path) -> None:
    publisher = create_macro_society_publisher(tmp_path, max_publications=1)
    assert publisher is not None
    publisher.publish(_publication())
    with pytest.raises(MacroSocietyArtifactError, match="macro_society_quota_exceeded"):
        publisher.publish(_publication(generated_tick=10))


def test_corrupt_snapshot_fails_digest_check(tmp_path) -> None:
    publisher = create_macro_society_publisher(tmp_path)
    reader = create_macro_society_reader(tmp_path)
    assert publisher is not None and reader is not None
    publication = _publication()
    publisher.publish(publication)
    path = (
        tmp_path
        / "run-1"
        / "publications"
        / publication.publication_id
        / "snapshot.json"
    )
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(
        MacroSocietyArtifactError, match="macro_society_digest_mismatch"
    ):
        reader.read_summary("run-1")


def test_lock_file_blocks_a_concurrent_publish(tmp_path) -> None:
    publisher = create_macro_society_publisher(tmp_path)
    assert publisher is not None
    (tmp_path / "run-1").mkdir(parents=True)
    (tmp_path / "run-1" / "writer.lock").write_text("other", encoding="utf-8")
    with pytest.raises(MacroSocietyArtifactError, match="macro_society_store_locked"):
        publisher.publish(_publication())


def test_missing_publication_is_reported(tmp_path) -> None:
    reader = create_macro_society_reader(tmp_path)
    assert reader is not None
    with pytest.raises(
        MacroSocietyArtifactError, match="macro_society_publication_missing"
    ):
        reader.read_summary("run-1")


def test_disabled_store_returns_none() -> None:
    assert create_macro_society_publisher(None) is None
    assert create_macro_society_reader(None) is None
