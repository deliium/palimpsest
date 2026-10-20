"""Known answers for the public-good metric families."""

from __future__ import annotations

import logging

import pytest

from analysis.public_good_metrics import assemble_public_good_metrics
from analysis.specifications import METRIC_FAMILY_COUNT, MetricFamilyId
from world.effects import ActionCause
from world.events import (
    EVENT_SCHEMA_REPLAY_V20,
    OccurrenceContext,
    ProjectCompleted,
    ProjectContributed,
    ProjectCreated,
    PublicGoodBenefit,
    PublicGoodMaintained,
    PublicGoodOpposed,
    WorldEvent,
    make_physical_replayable_event,
)
from world.identifiers import EntityId, EventId, RequestId, WorldId, WorldRevision


def test_public_good_families_extend_catalog() -> None:
    assert METRIC_FAMILY_COUNT == 119
    assert MetricFamilyId.PUBLIC_GOOD_COOPERATION_STABILITY.value == (
        "public_good_cooperation_stability"
    )


def test_absent_spec_writes_no_rows(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger="analysis.public_good_metrics"):
        documents = assemble_public_good_metrics(
            (),
            run_id="run-1",
            input_revision="rev-1",
            spec=None,
            as_of_tick=1,
        )
    assert documents == ()
    assert "public_good_metrics_empty reason=public_goods_absent" in caplog.text


def test_counts_contribution_and_use_patterns_from_events() -> None:
    events = (
        _event(
            ProjectCreated(
                EntityId("project-well"),
                EntityId("loc-1"),
                "well",
                EntityId("body-a"),
                3,
                2,
            ),
            0,
            1,
        ),
        _event(
            ProjectCreated(
                EntityId("project-store"),
                EntityId("loc-1"),
                "storage",
                EntityId("body-c"),
                2,
                1,
            ),
            0,
            2,
        ),
        _event(
            ProjectContributed(
                EntityId("project-well"), EntityId("body-a"), True, 1, 0
            ),
            1,
            1,
        ),
        _event(
            ProjectCompleted(
                EntityId("project-well"),
                "well",
                EntityId("structure-well"),
                decay_millis=10,
            ),
            1,
            2,
        ),
        _event(
            ProjectContributed(
                EntityId("project-store"), EntityId("body-c"), True, 1, 0
            ),
            1,
            3,
        ),
        _event(
            ProjectCompleted(
                EntityId("project-store"),
                "storage",
                EntityId("structure-store"),
                decay_millis=0,
            ),
            1,
            4,
        ),
        _event(
            PublicGoodBenefit(
                EntityId("project-well"),
                EntityId("body-a"),
                "well",
                "draw",
                "command",
                990,
                resulting_thirst=4.0,
            ),
            2,
            1,
        ),
        _event(
            PublicGoodBenefit(
                EntityId("project-well"),
                EntityId("body-a"),
                "well",
                "draw",
                "command",
                990,
                resulting_thirst=3.0,
            ),
            2,
            2,
        ),
        _event(
            PublicGoodBenefit(
                EntityId("project-well"),
                EntityId("body-b"),
                "well",
                "draw",
                "command",
                990,
                resulting_thirst=4.0,
            ),
            2,
            3,
        ),
        _event(
            PublicGoodBenefit(
                EntityId("project-store"),
                EntityId("body-c"),
                "storage",
                "draw",
                "command",
                1000,
                resulting_hunger=4.0,
            ),
            2,
            4,
        ),
        _event(
            PublicGoodMaintained(
                EntityId("project-well"), EntityId("body-d"), True, 1000
            ),
            3,
            1,
        ),
        _event(
            PublicGoodOpposed(
                EntityId("project-well"), EntityId("body-e"), "completed", 800
            ),
            4,
            1,
        ),
    )
    documents = assemble_public_good_metrics(
        events,
        run_id="run-1",
        input_revision="rev-1",
        spec=object(),
        as_of_tick=5,
    )
    by_family: dict[str, list[dict[str, object]]] = {}
    for document in documents:
        by_family.setdefault(document.metric_family, []).append(dict(document.values))
        assert document.values["layer"] == "research_inference"

    pattern = by_family["public_good_free_rider_pattern"][0]
    assert pattern["contribute_and_use_count"] == 2
    assert pattern["contribute_low_use_count"] == 1
    assert pattern["use_without_contribution_count"] == 1
    assert pattern["oppose_actor_count"] == 1
    assert pattern["maintain_actor_count"] == 1

    inequality = next(
        row
        for row in by_family["public_good_contribution_inequality"]
        if row["project_id"] == "project-well"
    )
    assert inequality["contributor_count"] == 1
    assert inequality["recorded_actor_count"] == 4
    assert inequality["labor_sum"] == 1
    assert inequality["gini_millis"] == 750_000

    well = next(
        row
        for row in by_family["public_good_benefit_distribution"]
        if row["project_kind"] == "well"
    )
    assert well["benefit_event_count"] == 3
    assert well["distinct_beneficiary_count"] == 2
    assert well["beneficiary_without_labor_count"] == 1
    assert well["contributor_without_benefit_count"] == 0

    burden = by_family["public_good_maintenance_burden"][0]
    assert burden["maintain_attempt_count"] == 1
    assert burden["maintain_accepted_count"] == 1
    assert burden["oppose_count"] == 1
    assert burden["decay_tick_count"] == 5
    assert burden["integrity_millis_sum"] == 1780

    stability = by_family["public_good_cooperation_stability"][0]
    assert stability["completed_public_count"] == 2
    assert stability["ticks_with_accepted_work"] == 1
    assert stability["ticks_observed"] == 6
    assert stability["longest_quiet_gap"] == 4


def _event(details: object, tick: int, sequence: int) -> WorldEvent:
    return make_physical_replayable_event(
        event_id=EventId(f"evt-{tick}-{sequence}"),
        run_id="run-1",
        world_id=WorldId("world-1"),
        tick=tick,
        sequence=sequence,
        cause=ActionCause(
            request_id=RequestId(f"req-{tick}-{sequence}"),
            actor_id=EntityId("body-a"),
        ),
        resulting_revision=WorldRevision(tick * 10 + sequence),
        details=details,  # type: ignore[arg-type]
        occurrence=OccurrenceContext(origin_location_id=EntityId("loc-1")),
        schema_version=EVENT_SCHEMA_REPLAY_V20,
    )
