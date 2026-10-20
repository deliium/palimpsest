"""Known answers for collective-project metric families."""

from __future__ import annotations

import logging

import pytest

from analysis.collective_project_metrics import assemble_collective_project_metrics
from analysis.specifications import METRIC_FAMILY_COUNT, MetricFamilyId
from world.effects import ActionCause
from world.events import (
    EVENT_SCHEMA_REPLAY_V19,
    OccurrenceContext,
    ProjectAbandoned,
    ProjectCompleted,
    ProjectContributed,
    ProjectCreated,
    ProjectShortage,
    make_physical_replayable_event,
)
from world.identifiers import EntityId, EventId, RequestId, WorldId, WorldRevision


def test_family_count_is_94() -> None:
    assert METRIC_FAMILY_COUNT == 124
    assert MetricFamilyId.COLLECTIVE_PROJECT_OUTCOME.value == (
        "collective_project_outcome"
    )


def test_absent_spec_writes_no_rows(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger="analysis.collective_project_metrics"):
        documents = assemble_collective_project_metrics(
            (),
            run_id="run-1",
            input_revision="rev-1",
            spec=None,
            as_of_tick=1,
        )
    assert documents == ()
    assert (
        "collective_project_metrics_empty reason=collective_projects_absent"
        in caplog.text
    )


def test_sums_contributors_and_outcomes() -> None:
    documents = assemble_collective_project_metrics(
        (
            _event(
                ProjectCreated(
                    EntityId("project-1"),
                    EntityId("loc-1"),
                    "shared_shelter",
                    EntityId("body-a"),
                    3,
                    2,
                ),
                1,
            ),
            _event(
                ProjectContributed(
                    EntityId("project-1"),
                    EntityId("body-a"),
                    True,
                    1,
                    1,
                    EntityId("wood-1"),
                ),
                2,
            ),
            _event(
                ProjectContributed(
                    EntityId("project-1"),
                    EntityId("body-b"),
                    True,
                    2,
                    2,
                    EntityId("wood-2"),
                ),
                3,
            ),
            _event(
                ProjectShortage(
                    EntityId("project-1"),
                    EntityId("body-a"),
                    1,
                ),
                4,
            ),
            _event(
                ProjectCompleted(
                    EntityId("project-1"),
                    "shared_shelter",
                    EntityId("shelter-1"),
                    0,
                ),
                5,
            ),
            _event(
                ProjectCreated(
                    EntityId("project-2"),
                    EntityId("loc-2"),
                    "storage",
                    EntityId("body-a"),
                    2,
                    1,
                ),
                6,
            ),
            _event(ProjectAbandoned(EntityId("project-2"), 4), 7),
        ),
        run_id="run-1",
        input_revision="rev-1",
        spec=object(),
        as_of_tick=7,
    )
    by_family: dict[str, list[dict[str, object]]] = {}
    for document in documents:
        by_family.setdefault(document.metric_family, []).append(dict(document.values))
        assert "leader" not in document.values
        assert document.values["layer"] == "research_inference"
    shelter = next(
        row
        for row in by_family["collective_project_progress"]
        if row["project_kind"] == "shared_shelter"
    )
    assert shelter["labor_done"] == 2
    assert shelter["labor_required"] == 3
    assert shelter["labor_num"] == 2
    assert shelter["labor_den"] == 3
    assert shelter["materials_done"] == 2
    assert shelter["materials_den"] == 2
    storage = next(
        row
        for row in by_family["collective_project_progress"]
        if row["project_kind"] == "storage"
    )
    assert storage["labor_done"] == 0
    contribution = by_family["collective_project_contribution"][0]
    assert contribution["distinct_contributor_count"] == 2
    assert contribution["accepted_contribution_count"] == 2
    assert contribution["shortage_count"] == 1
    assert contribution["contribution_num"] == 2
    assert contribution["contribution_den"] == 3
    outcome = by_family["collective_project_outcome"][0]
    assert outcome["completed_count"] == 1
    assert outcome["abandoned_count"] == 1
    assert outcome["open_count"] == 0
    assert outcome["outcome_num"] == 1
    assert outcome["outcome_den"] == 2


def _event(details: object, tick: int):
    return make_physical_replayable_event(
        event_id=EventId(f"evt-{tick}-1"),
        run_id="run-1",
        world_id=WorldId("world-1"),
        tick=tick,
        sequence=1,
        cause=ActionCause(
            request_id=RequestId(f"req-{tick}"),
            actor_id=EntityId("body-a"),
        ),
        resulting_revision=WorldRevision(tick),
        details=details,  # type: ignore[arg-type]
        occurrence=OccurrenceContext(origin_location_id=EntityId("loc-1")),
        schema_version=EVENT_SCHEMA_REPLAY_V19,
    )
