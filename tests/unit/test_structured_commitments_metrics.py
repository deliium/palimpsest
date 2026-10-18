"""Known answers for commitment metric families. Channel off stays empty."""

from __future__ import annotations

from analysis.specifications import METRIC_FAMILY_COUNT, MetricFamilyId
from analysis.structured_commitments import CommitmentLedgerSnapshot
from analysis.structured_commitments_metrics import (
    assemble_structured_commitment_metrics,
)
from world.effects import ActionCause
from world.events import (
    EVENT_SCHEMA_REPLAY_V17,
    CommitmentDeclared,
    OccurrenceContext,
    make_physical_replayable_event,
)
from world.identifiers import EntityId, EventId, RequestId, WorldId, WorldRevision


def _event():
    return make_physical_replayable_event(
        event_id=EventId("evt-1-1"),
        run_id="run-1",
        world_id=WorldId("world-1"),
        tick=1,
        sequence=1,
        cause=ActionCause(
            request_id=RequestId("req-1"),
            actor_id=EntityId("body-a"),
        ),
        resulting_revision=WorldRevision(0),
        details=CommitmentDeclared(
            EntityId("body-a"),
            EntityId("body-b"),
            "promise",
            "propose",
            "self",
            "none",
            1,
            "none",
            "material",
        ),
        occurrence=OccurrenceContext(origin_location_id=EntityId("loc-1")),
        schema_version=EVENT_SCHEMA_REPLAY_V17,
    )


def test_family_count_is_77() -> None:
    assert METRIC_FAMILY_COUNT == 115
    assert MetricFamilyId.COMMITMENT_TERM_DIVERGENCE.value == (
        "commitment_term_divergence"
    )


def test_channel_off_harvest_is_empty() -> None:
    assert (
        assemble_structured_commitment_metrics(
            (),
            run_id="run-1",
            input_revision="rev-1",
            spec=None,
            as_of_tick=1,
        )
        == ()
    )


def test_divergence_and_request_counts() -> None:
    docs = assemble_structured_commitment_metrics(
        (_event(),),
        run_id="run-1",
        input_revision="rev-1",
        spec=object(),
        as_of_tick=1,
        ledgers=(
            CommitmentLedgerSnapshot(
                "owner-a",
                ("evt-1-1",),
                "promise",
                "material",
                "none",
                1,
                "self",
                "none",
                "open",
            ),
            CommitmentLedgerSnapshot(
                "owner-b",
                ("evt-1-1",),
                "promise",
                "food",
                "none",
                1,
                "self",
                "none",
                "partial",
            ),
        ),
        owner_ids=("owner-a", "owner-b", "owner-c"),
        consequence_counts={
            "relationship": 1,
            "reputation": 0,
            "norm": 0,
            "sanction": 1,
        },
    )
    by_family = {doc.metric_family: doc for doc in docs}
    divergence = by_family["commitment_term_divergence"].values
    assert divergence["speech_count"] == 1
    assert divergence["divergent_count"] == 1
    assert divergence["unformed_count"] == 1
    assert divergence["layer"] == "research_inference"
    fulfillment = by_family["commitment_fulfillment_status"].values
    assert fulfillment["partial_count"] == 1
    assert fulfillment["status_histogram"] == "open:1,partial:1"
    consequences = by_family["commitment_social_consequences"].values
    assert consequences["relationship_request_count"] == 1
    assert consequences["sanction_request_count"] == 1
    assert "health" not in consequences
