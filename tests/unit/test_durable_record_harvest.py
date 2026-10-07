"""Durable-record harvest composition + collector opt-in wiring."""

from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest

from analysis.metric_service import MetricComputationInputs, assemble_metric_documents
from experiments.composition import (
    artifact_objective_rows_from_artifacts,
    durable_record_event_rows_from_events,
    durable_record_harvest_from_run,
)
from experiments.metric_collection import inputs_with_opt_in_metric_rows
from simulation.runner_models import example_durable_records_spec
from world.artifacts import (
    ArtifactContent,
    ArtifactKind,
    DurableRecordGenre,
    InformationArtifact,
    RecordIntegrity,
)
from world.events import ArtifactCopied, ArtifactDamaged
from world.identifiers import EntityId

pytestmark = pytest.mark.unit


def test_artifact_rows_include_durable_meta() -> None:
    artifact = InformationArtifact(
        artifact_id=EntityId("art-1"),
        kind=ArtifactKind.RECORD,
        author_id=EntityId("body-1"),
        created_tick=2,
        content=ArtifactContent(marks=("a", "b")),
        location_id=EntityId("loc-1"),
        record_genre=DurableRecordGenre.WARNING,
        parent_artifact_id=EntityId("art-0"),
        source_artifact_id=EntityId("art-0"),
        copy_generation=1,
        integrity=RecordIntegrity.DAMAGED,
        annotation_revisions=2,
        lost_mark_count=1,
    )
    rows = artifact_objective_rows_from_artifacts((artifact,), tick=5)
    assert len(rows) == 1
    row = rows[0]
    assert row["record_genre"] == "warning"
    assert row["parent_artifact_id"] == "art-0"
    assert row["source_artifact_id"] == "art-0"
    assert row["copy_generation"] == 1
    assert row["integrity"] == "damaged"
    assert row["annotation_revisions"] == 2
    assert row["lost_mark_count"] == 1
    assert row["author_id"] == "body-1"
    assert row["created_tick"] == 2
    assert "truth" not in row
    assert "meaning" not in row


def test_event_rows_from_durable_details() -> None:
    events = (
        SimpleNamespace(
            tick=3,
            details=ArtifactCopied(
                child_artifact_id=EntityId("child"),
                parent_artifact_id=EntityId("parent"),
                source_artifact_id=EntityId("root"),
                fidelity_mode="lossy",
                copy_generation=1,
                content_revision=0,
                record_genre="story",
            ),
        ),
        SimpleNamespace(
            tick=4,
            details=ArtifactDamaged(
                artifact_id=EntityId("parent"),
                prior_integrity="intact",
                next_integrity="damaged",
                lost_mark_count_delta=1,
                content_revision=1,
            ),
        ),
        SimpleNamespace(tick=5, details=SimpleNamespace(kind="wait")),
    )
    rows = durable_record_event_rows_from_events(events)
    assert len(rows) == 2
    assert rows[0]["kind"] == "artifact_copied"
    assert rows[0]["child_artifact_id"] == "child"
    assert rows[0]["fidelity_mode"] == "lossy"
    assert rows[1]["kind"] == "artifact_damaged"
    assert rows[1]["next_integrity"] == "damaged"


def test_harvest_skips_when_durable_absent(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.DEBUG, logger="experiments.composition"):
        payload = durable_record_harvest_from_run(durable_records_spec=None)
    assert payload is None
    assert "durable_absent" in caplog.text


def test_harvest_attaches_rows_when_durable_enabled(
    caplog: pytest.LogCaptureFixture,
) -> None:
    artifact = InformationArtifact(
        artifact_id=EntityId("art-1"),
        kind=ArtifactKind.NOTE,
        author_id=EntityId("body-1"),
        created_tick=0,
        content=ArtifactContent(marks=("memo",)),
        holder_id=EntityId("body-1"),
        record_genre=DurableRecordGenre.INSTRUCTION,
        source_artifact_id=EntityId("art-1"),
        integrity=RecordIntegrity.INTACT,
    )
    events = (
        SimpleNamespace(
            tick=1,
            details=ArtifactCopied(
                child_artifact_id=EntityId("art-2"),
                parent_artifact_id=EntityId("art-1"),
                source_artifact_id=EntityId("art-1"),
                fidelity_mode="perfect",
                copy_generation=1,
                content_revision=0,
                record_genre="instruction",
            ),
        ),
    )
    with caplog.at_level(logging.DEBUG, logger="experiments.composition"):
        payload = durable_record_harvest_from_run(
            durable_records_spec=example_durable_records_spec(),
            artifacts=(artifact,),
            events=events,
            tick=1,
        )
    assert payload is not None
    assert len(payload["durable_record_rows"]) == 1
    assert len(payload["durable_record_event_rows"]) == 1
    assert "durable_record_harvest_built" in caplog.text


def test_opt_in_and_assemble_attach_durable_families() -> None:
    base = MetricComputationInputs(
        run_id="run-1",
        input_revision="rev-1",
        window_end=1,
    )
    updated = inputs_with_opt_in_metric_rows(
        base,
        durable_record_rows=(
            {
                "artifact_id": "a0",
                "copy_generation": 0,
                "source_artifact_id": "a0",
                "integrity": "intact",
                "author_id": "body-1",
                "created_tick": 0,
            },
        ),
        durable_record_event_rows=(
            {
                "kind": "artifact_copied",
                "fidelity_mode": "perfect",
                "child_artifact_id": "a1",
                "parent_artifact_id": "a0",
            },
        ),
        death_ticks_by_body={"body-1": 3},
    )
    assert updated.durable_record_rows is not None
    bundle = assemble_metric_documents(updated)
    families = {doc.metric_family for doc in bundle.documents}
    assert "durable_record_lineage" in families
    assert "durable_record_fidelity" in families
    assert "durable_record_survival" in families
