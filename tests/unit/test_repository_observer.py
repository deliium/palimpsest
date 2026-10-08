"""Observer SEMANTIC 53 and repository scene/event projection."""

from __future__ import annotations

import pytest

from agents.models import AgentId
from observer.adapt import adapt_event
from observer.layout import catalog_from_mapping
from observer.project import project_frame
from observer.version import OBSERVER_PROTOCOL_VERSION, SEMANTIC_EVENT_TYPES
from simulation.engine import WorldEngine
from simulation.lifecycle import ActionResolutionStatus, ActionSubmission
from simulation.observer_facts import scene_from_facts
from simulation.runner_models import (
    example_durable_records_spec,
    example_knowledge_repositories_spec,
)
from tests.physical_helpers import physical_config, two_location_fixture
from world.actions import EstablishRepository
from world.effects import ActionCause
from world.events import (
    EVENT_SCHEMA_REPLAY_V14,
    OccurrenceContext,
    RepositoryEstablished,
    RepositoryNeglected,
    make_physical_replayable_event,
)
from world.identifiers import EntityId, EventId, RequestId, WorldId, WorldRevision

pytestmark = pytest.mark.unit

_REPOSITORY_SEMANTIC = (
    "REPOSITORY_ESTABLISHED",
    "REPOSITORY_MEMBER_DEPOSITED",
    "REPOSITORY_MEMBER_RETRIEVED",
    "REPOSITORY_MAINTAINED",
    "REPOSITORY_INDEXED",
    "REPOSITORY_NEGLECTED",
)

_EMPTY_LAYOUT = catalog_from_mapping(
    {
        "schema_version": "observer-layout-v1",
        "layout_id": "repository-empty",
        "locations": [],
    }
)


def test_semantic_catalog_appends_six_repository_types() -> None:
    assert OBSERVER_PROTOCOL_VERSION == "observer-protocol-v1"
    assert len(SEMANTIC_EVENT_TYPES) == 54
    assert SEMANTIC_EVENT_TYPES[-7:-1] == _REPOSITORY_SEMANTIC
    for name in _REPOSITORY_SEMANTIC:
        assert name in SEMANTIC_EVENT_TYPES


def test_adapt_repository_established_and_neglected() -> None:
    established = make_physical_replayable_event(
        event_id=EventId("evt-1"),
        run_id="run-1",
        world_id=WorldId("world-1"),
        tick=1,
        sequence=0,
        cause=ActionCause(RequestId("req-1"), EntityId("body-1")),
        resulting_revision=WorldRevision(1),
        details=RepositoryEstablished(
            EntityId("repo-1"),
            EntityId("loc-1"),
            None,
            (EntityId("body-1"),),
            "open",
            0,
        ),
        occurrence=OccurrenceContext(origin_location_id=EntityId("loc-1")),
        schema_version=EVENT_SCHEMA_REPLAY_V14,
    )
    adapted = adapt_event(established)
    assert adapted.type == "REPOSITORY_ESTABLISHED"
    assert adapted.repository_id == "repo-1"
    assert adapted.origin_location_id == "loc-1"

    from world.effects import SystemCause, SystemEffectFamily

    neglected = make_physical_replayable_event(
        event_id=EventId("evt-2"),
        run_id="run-1",
        world_id=WorldId("world-1"),
        tick=2,
        sequence=0,
        cause=SystemCause(
            RequestId("sys-1"),
            SystemEffectFamily.KNOWLEDGE_REPOSITORY,
            EntityId("repo-1"),
            2,
        ),
        resulting_revision=WorldRevision(2),
        details=RepositoryNeglected(
            EntityId("repo-1"), 1, "intact", "neglected", 0
        ),
        occurrence=OccurrenceContext(origin_location_id=EntityId("loc-1")),
        schema_version=EVENT_SCHEMA_REPLAY_V14,
    )
    adapted_neg = adapt_event(neglected)
    assert adapted_neg.type == "REPOSITORY_NEGLECTED"
    assert adapted_neg.repository_id == "repo-1"


def test_project_frame_includes_objective_repositories() -> None:
    engine = WorldEngine(
        config=physical_config(1),
        bootstrap=two_location_fixture().as_bootstrap(),
        artifacts_enabled=True,
        durable_records_spec=example_durable_records_spec(),
        knowledge_repositories_spec=example_knowledge_repositories_spec(),
    )
    batch = engine.observe()
    result = engine.resolve_tick(
        (
            ActionSubmission(
                batch.token,
                AgentId("agent-1"),
                EstablishRepository(location_id=EntityId("loc-1")),
            ),
        )
    )
    assert result.resolutions[0].status is ActionResolutionStatus.APPLIED
    facts = engine.detached_objective_facts()
    scene = scene_from_facts(facts)
    assert len(scene.repositories) == 1
    frame = project_frame(scene, _EMPTY_LAYOUT, mode="live", events=())
    assert len(frame.world.repositories) == 1
    row = frame.world.repositories[0]
    assert row.status == "intact"
    assert row.member_count == 0
    for forbidden in ("library", "archive", "sacred"):
        assert forbidden not in row.__dataclass_fields__
