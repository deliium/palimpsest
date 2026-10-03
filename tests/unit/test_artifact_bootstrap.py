"""Bootstrap seeds objective artifacts without interpretation ledgers."""

from __future__ import annotations

import logging

import pytest

from agents.cognition.models import SubjectiveSnapshot
from agents.models import AgentId
from simulation.bootstrap import WorldBootstrap, _materialize_world
from simulation.engine import WorldEngine
from tests.physical_helpers import physical_config, two_location_fixture
from world.artifacts import ArtifactContent, ArtifactKind, InformationArtifact
from world.identifiers import EntityId

pytestmark = pytest.mark.unit


def _record(*, artifact_id: str = "art-record-1") -> InformationArtifact:
    return InformationArtifact(
        artifact_id=EntityId(artifact_id),
        kind=ArtifactKind.RECORD,
        author_id=EntityId("body-1"),
        created_tick=0,
        content=ArtifactContent(marks=("water", "north")),
        location_id=EntityId("loc-1"),
    )


def test_bootstrap_seeds_record_without_interpretation(
    caplog: pytest.LogCaptureFixture,
) -> None:
    fixture = two_location_fixture()
    record = _record()
    with caplog.at_level(logging.DEBUG, logger="simulation.bootstrap"):
        bootstrap = WorldBootstrap(
            world_id=fixture.world_id,
            revision=fixture.revision,
            locations=fixture.locations,
            items=fixture.items,
            resources=fixture.resources,
            bodies=fixture.bodies,
            weather=fixture.weather,
            registrations=fixture.registrations,
            artifacts=(record,),
        )
    assert bootstrap.artifacts == (record,)
    assert any(
        "artifacts_seeded count=1" in record_msg.getMessage()
        for record_msg in caplog.records
    )
    assert not any(
        "water" in record_msg.getMessage() and record_msg.levelno >= logging.INFO
        for record_msg in caplog.records
    )

    engine = WorldEngine(
        config=physical_config(1),
        bootstrap=bootstrap,
    )
    assert engine.tick.value == 0
    assert engine._artifacts_enabled is True
    batch = engine.observe()
    assert batch is not None
    assert len(batch.observations) >= 1

    seeded = engine._snapshot.world.state.artifacts[EntityId("art-record-1")]
    assert seeded.kind is ArtifactKind.RECORD
    assert seeded.created_tick == 0
    assert seeded.location_id == EntityId("loc-1")
    assert seeded.content.marks == ("water", "north")

    # Seeded ground record is objectively present in observation; no ledger.
    agent_obs = next(
        obs for obs in batch.observations if obs.observer_id == EntityId("body-1")
    )
    observed_ids = {artifact.entity_id for artifact in agent_obs.artifacts}
    assert EntityId("art-record-1") in observed_ids

    # DISABLED interpretation: snapshot field exists but stays None by default.
    assert "artifact_interpretations" in SubjectiveSnapshot.__dataclass_fields__
    assert getattr(agent_obs, "artifact_interpretations", None) is None


def test_empty_artifacts_default_keeps_bootstrap_empty() -> None:
    fixture = two_location_fixture()
    bootstrap = fixture.as_bootstrap()
    assert bootstrap.artifacts == ()
    world = _materialize_world(bootstrap)
    assert world.state.artifacts == {}
    engine = WorldEngine(config=physical_config(2), bootstrap=bootstrap)
    assert engine._artifacts_enabled is False
    assert engine._snapshot.world.state.artifacts == {}


def test_artifacts_enabled_without_seed() -> None:
    fixture = two_location_fixture()
    engine = WorldEngine(
        config=physical_config(3),
        bootstrap=fixture.as_bootstrap(),
        artifacts_enabled=True,
    )
    assert engine._artifacts_enabled is True
    assert engine._snapshot.world.state.artifacts == {}


def test_artifact_id_collision_logs_and_rejects(
    caplog: pytest.LogCaptureFixture,
) -> None:
    fixture = two_location_fixture()
    # Collide with an existing item id (not a registration body id).
    colliding = InformationArtifact(
        artifact_id=fixture.items[0].entity_id,
        kind=ArtifactKind.RECORD,
        author_id=EntityId("body-1"),
        created_tick=0,
        content=ArtifactContent(marks=("water", "north")),
        location_id=EntityId("loc-1"),
    )
    with caplog.at_level(logging.ERROR, logger="simulation.bootstrap"):
        with pytest.raises(ValueError, match="duplicate physical EntityId"):
            WorldBootstrap(
                world_id=fixture.world_id,
                revision=fixture.revision,
                locations=fixture.locations,
                items=fixture.items,
                resources=fixture.resources,
                bodies=fixture.bodies,
                weather=fixture.weather,
                registrations=fixture.registrations,
                artifacts=(colliding,),
            )
    assert any(
        "reason_code=artifact_id_collision" in record.getMessage()
        for record in caplog.records
    )


def test_duplicate_artifact_ids_reject(
    caplog: pytest.LogCaptureFixture,
) -> None:
    fixture = two_location_fixture()
    first = _record(artifact_id="art-dup")
    second = _record(artifact_id="art-dup")
    with caplog.at_level(logging.ERROR, logger="simulation.bootstrap"):
        with pytest.raises(ValueError, match="duplicate artifact entity_id"):
            WorldBootstrap(
                world_id=fixture.world_id,
                revision=fixture.revision,
                locations=fixture.locations,
                items=fixture.items,
                resources=fixture.resources,
                bodies=fixture.bodies,
                weather=fixture.weather,
                registrations=fixture.registrations,
                artifacts=(first, second),
            )
    assert any(
        "reason_code=artifact_id_collision" in record.getMessage()
        for record in caplog.records
    )


def test_materialize_does_not_attach_interpretation_ledgers() -> None:
    fixture = two_location_fixture()
    bootstrap = WorldBootstrap(
        world_id=fixture.world_id,
        revision=fixture.revision,
        locations=fixture.locations,
        items=fixture.items,
        resources=fixture.resources,
        bodies=fixture.bodies,
        weather=fixture.weather,
        registrations=fixture.registrations,
        artifacts=(_record(),),
    )
    world = _materialize_world(bootstrap)
    assert EntityId("art-record-1") in world.state.artifacts
    assert not hasattr(world.state, "artifact_interpretations")
    assert not hasattr(world, "artifact_interpretations")
    # Registrations remain agent→body only; no ledger side channel.
    assert all(
        registration.agent_id == AgentId(registration.agent_id.value)
        for registration in bootstrap.registrations
    )
