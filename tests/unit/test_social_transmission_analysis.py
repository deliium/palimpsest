"""Unit tests for read-only social transmission analysis."""

from __future__ import annotations

from agents.cognition.communication import build_communicated_memory_trace
from agents.models import AgentId
from analysis.social_transmission import build_social_transmission_report
from world.communications import origin_utterance, retell_utterance
from world.effects import ActionCause
from world.events import (
    OccurrenceContext,
    Told,
    make_physical_replayable_event,
)
from world.identifiers import EntityId, EventId, RequestId, WorldId, WorldRevision
from world.observations import (
    ObservationProvenance,
    ObservationSourceKind,
    ObservedCommunication,
)


def test_build_social_transmission_report_tracks_hops_and_agents() -> None:
    origin = origin_utterance(
        text="water",
        speaker_id=EntityId("body-alice"),
        communication_id="comm-root",
        concepts=("water",),
    )
    retell = retell_utterance(
        prior=origin,
        speaker_id=EntityId("body-bob"),
        communication_id="comm-hop-1",
        sender_confidence=0.7,
    )
    events = (
        make_physical_replayable_event(
            event_id=EventId("evt-1"),
            run_id="run-1",
            world_id=WorldId("world-1"),
            tick=1,
            sequence=0,
            cause=ActionCause(RequestId("req-1"), EntityId("body-alice")),
            resulting_revision=WorldRevision(1),
            details=Told(EntityId("body-bob"), origin),
            occurrence=OccurrenceContext(
                origin_location_id=EntityId("loc-1"),
                private_recipient_ids=(EntityId("body-bob"),),
                affected_entity_ids=(EntityId("body-alice"), EntityId("body-bob")),
            ),
        ),
        make_physical_replayable_event(
            event_id=EventId("evt-2"),
            run_id="run-1",
            world_id=WorldId("world-1"),
            tick=2,
            sequence=0,
            cause=ActionCause(RequestId("req-2"), EntityId("body-bob")),
            resulting_revision=WorldRevision(2),
            details=Told(EntityId("body-carol"), retell),
            occurrence=OccurrenceContext(
                origin_location_id=EntityId("loc-1"),
                private_recipient_ids=(EntityId("body-carol"),),
                affected_entity_ids=(EntityId("body-bob"), EntityId("body-carol")),
            ),
        ),
    )
    bob_obs = ObservedCommunication(
        provenance=ObservationProvenance(
            source_kind=ObservationSourceKind.COMMUNICATION,
            source_tick=1,
            source_event_id=EventId("evt-1"),
        ),
        speaker_id=EntityId("body-alice"),
        listener_id=EntityId("body-bob"),
        utterance=origin,
        action_kind="tell",
    )
    bob_trace = build_communicated_memory_trace(
        owner_id=AgentId("agent-bob"),
        observation_tick=2,
        observation_revision=WorldRevision(1),
        message=bob_obs,
        location_id=EntityId("loc-1"),
    )
    report = build_social_transmission_report(
        experiment_id="exp-1",
        run_id="run-1",
        events=events,
        traces=(bob_trace,),
        transmission_root_id="comm-root",
    )
    assert report.max_hop_count >= 1
    assert report.unique_agent_count >= 2
    assert report.event_count == 2
    assert report.trace_count == 1
    assert "water" not in repr(report)
