"""Detached harvest slices for technique lifecycle."""

from __future__ import annotations

from types import SimpleNamespace

from analysis.metric_service import MetricComputationInputs, assemble_metric_documents
from experiments.composition import (
    artifact_objective_rows_from_artifacts,
    technique_item_rows_from_items,
    technique_node_rows_from_resources,
)
from experiments.metric_collection import inputs_with_opt_in_metric_rows
from world.identifiers import EntityId


def test_artifact_row_copies_location_id() -> None:
    artifact = SimpleNamespace(
        artifact_id=EntityId("mark-1"),
        kind=SimpleNamespace(value="mark"),
        content=SimpleNamespace(marks=()),
        content_revision=1,
        record_genre=SimpleNamespace(value="mark"),
        integrity=SimpleNamespace(value="intact"),
        location_id=EntityId("loc-1"),
        parent_artifact_id=None,
        source_artifact_id=None,
        author_id=None,
        created_tick=1,
        copy_generation=0,
        annotation_revisions=0,
        lost_mark_count=0,
    )
    rows = artifact_objective_rows_from_artifacts((artifact,), tick=1)
    assert rows[0]["location_id"] == "loc-1"


def test_zero_quantity_node_and_dead_holder_item() -> None:
    nodes = technique_node_rows_from_resources(
        (SimpleNamespace(name="wood", location_id=EntityId("loc-1"), quantity=0),)
    )
    items = technique_item_rows_from_items(
        (
            SimpleNamespace(
                entity_id=EntityId("item-1"),
                name="stone",
                kind=SimpleNamespace(value="material"),
                location_id=None,
                holder_id=EntityId("dead-agent"),
            ),
        )
    )
    assert nodes is not None and nodes[0]["quantity"] == 0.0
    assert items is not None and items[0]["holder_id"] == "dead-agent"


def test_channel_off_leaves_slices_absent() -> None:
    base = MetricComputationInputs(
        run_id="run-1", input_revision="rev-1", window_end=1
    )
    updated = inputs_with_opt_in_metric_rows(base)
    assert updated.technique_lifecycle_spec is None
    assert updated.technique_node_rows is None
    assert updated.technique_item_rows is None
    bundle = assemble_metric_documents(updated)
    families = {doc.metric_family for doc in bundle.documents}
    assert "technique_lifecycle_state" not in families
