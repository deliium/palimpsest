"""Durable record Observation projection: marks_and_meta vs marks_only."""

from __future__ import annotations

import pytest

from agents.models import AgentId
from simulation.engine import WorldEngine
from simulation.lifecycle import ActionResolutionStatus, ActionSubmission
from simulation.runner_models import example_durable_records_spec
from tests.physical_helpers import physical_config, two_location_fixture
from world.actions import DamageRecord, Inscribe
from world.artifacts import (
    ArtifactContent,
    ArtifactKind,
    DurableRecordGenre,
    RecordIntegrity,
)
from world.identifiers import EntityId
from world.observations import ObservationContext
from world._perception import PerceptionService

pytestmark = pytest.mark.unit


def _content(*marks: str) -> ArtifactContent:
    return ArtifactContent(marks=marks)


def _engine(*, perception_mode: str = "marks_and_meta") -> WorldEngine:
    return WorldEngine(
        config=physical_config(1),
        bootstrap=two_location_fixture().as_bootstrap(),
        artifacts_enabled=True,
        durable_records_spec=example_durable_records_spec(
            perception_mode=perception_mode
        ),
    )


def test_marks_and_meta_projects_lineage_and_integrity() -> None:
    engine = _engine(perception_mode="marks_and_meta")
    batch = engine.observe()
    result = engine.resolve_tick(
        (
            ActionSubmission(
                batch.token,
                AgentId("agent-1"),
                Inscribe(
                    ArtifactKind.RECORD,
                    _content("a"),
                    record_genre=DurableRecordGenre.WARNING,
                ),
            ),
        )
    )
    assert result.resolutions[0].status is ActionResolutionStatus.APPLIED
    obs = engine.observe().observations[0]
    assert len(obs.artifacts) == 1
    seen = obs.artifacts[0]
    assert seen.record_genre is DurableRecordGenre.WARNING
    assert seen.integrity is RecordIntegrity.INTACT
    assert seen.copy_generation == 0
    assert seen.source_artifact_id is not None


def test_marks_only_omits_lineage_meta() -> None:
    engine = _engine(perception_mode="marks_only")
    batch = engine.observe()
    engine.resolve_tick(
        (
            ActionSubmission(
                batch.token,
                AgentId("agent-1"),
                Inscribe(
                    ArtifactKind.NOTE,
                    _content("memo"),
                    hold=True,
                    record_genre=DurableRecordGenre.STORY,
                ),
            ),
        )
    )
    obs = engine.observe().observations[0]
    assert len(obs.artifacts) == 1
    seen = obs.artifacts[0]
    assert seen.record_genre is DurableRecordGenre.STORY
    assert seen.integrity is None
    assert seen.parent_artifact_id is None
    assert seen.copy_generation is None


def test_tombstone_invisible_to_agents() -> None:
    engine = _engine()
    batch = engine.observe()
    created = engine.resolve_tick(
        (
            ActionSubmission(
                batch.token,
                AgentId("agent-1"),
                Inscribe(
                    ArtifactKind.RECORD,
                    _content("x"),
                    record_genre=DurableRecordGenre.CHRONICLE,
                ),
            ),
        )
    )
    assert created.resolutions[0].status is ActionResolutionStatus.APPLIED
    artifact_id = next(iter(engine._snapshot.world.state.artifacts))
    batch = engine.observe()
    engine.resolve_tick(
        (
            ActionSubmission(
                batch.token,
                AgentId("agent-1"),
                DamageRecord(artifact_id, "destroy"),
            ),
        )
    )
    assert (
        engine._snapshot.world.state.artifacts[artifact_id].integrity
        is RecordIntegrity.DESTROYED
    )
    obs = engine.observe().observations[0]
    assert obs.artifacts == ()
