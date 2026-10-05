"""Replay-v7 environment details stay off schemas that do not own them."""

from __future__ import annotations

import json
import logging

import pytest

from agents.models import AgentId
from simulation.bootstrap import AgentRegistration
from simulation.clock import Tick
from simulation.engine import select_checkpoint_schema
from simulation.models import DERIVATION_VERSION, RunId, SimulationRunConfig
from simulation.persistence import (
    ACCEPTED_EVENT_SCHEMA_VERSIONS,
    ACCEPTED_PERSISTENCE_CODEC_VERSIONS,
    EVENT_SCHEMA_VERSION,
    PERSISTENCE_CODEC_VERSION,
    PROJECTOR_VERSION,
    PayloadHash,
    RunCreateRequest,
    SnapshotId,
    WorldSnapshot,
    checkpoint_schema_for_production,
    schema_projector_compatible,
)
from simulation.serialization import (
    DomainSerializationError,
    decode_domain,
    encode_domain,
)
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.effects import ActionCause, SystemCause, SystemEffectFamily
from world.environment import HazardKind, Season, TemperatureBand
from world.events import (
    CURRENT_PHYSICAL_EVENT_SCHEMA_VERSION,
    EVENT_SCHEMA_REPLAY_V5,
    EVENT_SCHEMA_REPLAY_V6,
    EVENT_SCHEMA_REPLAY_V7,
    REPLAYABLE_EVENT_SCHEMA_VERSIONS,
    SUPPORTED_EVENT_SCHEMA_VERSIONS,
    EnvironmentalHazardEnded,
    EnvironmentalHazardStarted,
    EventValidationCode,
    OccurrenceContext,
    ResourceHarvested,
    ResourceNodeDepleted,
    ResourceNodeRecovered,
    SeasonChanged,
    TemperatureBandChanged,
    WorldEvent,
    _payload_effect_complete,
    build_occurrence_context,
    make_physical_replayable_event,
)
from world.identifiers import (
    EntityId,
    EventId,
    RecipeId,
    RequestId,
    WorldId,
    WorldRevision,
)

_FORBIDDEN = {
    "animation",
    "color",
    "dx",
    "dy",
    "pixels",
    "screen_x",
    "screen_y",
    "sprite",
}


def _system(family: SystemEffectFamily, entity: str) -> SystemCause:
    return SystemCause(RequestId("sys-1"), family, EntityId(entity), 0)


def _event(details: object, *, schema_version: int, cause: SystemCause) -> WorldEvent:
    return make_physical_replayable_event(
        event_id=EventId("evt-1"),
        run_id="run-1",
        world_id=WorldId("world-1"),
        tick=4,
        sequence=0,
        cause=cause,
        resulting_revision=WorldRevision(1),
        details=details,  # type: ignore[arg-type]
        occurrence=build_occurrence_context(
            details,  # type: ignore[arg-type]
            origin_location_id=EntityId("loc-a"),
        ),
        schema_version=schema_version,
    )


def _environment_details() -> tuple[object, ...]:
    return (
        SeasonChanged(Season.SUMMER),
        TemperatureBandChanged(EntityId("loc-b"), TemperatureBand.HOT),
        ResourceNodeDepleted(EntityId("res-food"), 0.0),
        ResourceNodeRecovered(EntityId("res-food"), 1.0),
        EnvironmentalHazardStarted(
            EntityId("loc-b"),
            HazardKind.HEAT,
            6,
            6,
        ),
        EnvironmentalHazardEnded(EntityId("loc-b"), HazardKind.HEAT, 0),
    )


def test_default_write_stays_replay_v5_and_v7_is_accepted() -> None:
    assert CURRENT_PHYSICAL_EVENT_SCHEMA_VERSION == EVENT_SCHEMA_REPLAY_V5 == 5
    assert EVENT_SCHEMA_VERSION == 5
    assert EVENT_SCHEMA_REPLAY_V7 == 7
    assert 7 in SUPPORTED_EVENT_SCHEMA_VERSIONS
    assert 7 in REPLAYABLE_EVENT_SCHEMA_VERSIONS
    assert 7 in ACCEPTED_EVENT_SCHEMA_VERSIONS
    names = [family.value for family in SystemEffectFamily]
    assert names[:5] == [
        "weather",
        "regeneration",
        "combined_needs",
        "exposure",
        "production",
    ]
    assert names[-5:] == [
        "season",
        "temperature_band",
        "hazard",
        "resource_node",
        "lifecycle",
    ]


def test_lower_schemas_reject_environment_details(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.ERROR, logger="world.events")
    cause = _system(SystemEffectFamily.SEASON, "loc-a")
    for schema in (EVENT_SCHEMA_REPLAY_V5, EVENT_SCHEMA_REPLAY_V6):
        for details in _environment_details():
            with pytest.raises(ValueError, match="invalid_event_schema_version"):
                _event(details, schema_version=schema, cause=cause)
            assert _payload_effect_complete(details, schema_version=schema) is False  # type: ignore[arg-type]
    assert any(
        "invalid_event_schema_version" in record.getMessage()
        and "kind=season_changed" in record.getMessage()
        and "schema_version=5" in record.getMessage()
        for record in caplog.records
    )
    assert not any("color" in record.getMessage() for record in caplog.records)


def test_v7_accepts_environment_details_and_logs_the_kind(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger="world.events")
    families = {
        "season_changed": SystemEffectFamily.SEASON,
        "temperature_band_changed": SystemEffectFamily.TEMPERATURE_BAND,
        "resource_node_depleted": SystemEffectFamily.RESOURCE_NODE,
        "resource_node_recovered": SystemEffectFamily.RESOURCE_NODE,
        "environmental_hazard_started": SystemEffectFamily.HAZARD,
        "environmental_hazard_ended": SystemEffectFamily.HAZARD,
    }
    for details in _environment_details():
        family = families[details.kind]  # type: ignore[attr-defined]
        event = _event(
            details,
            schema_version=EVENT_SCHEMA_REPLAY_V7,
            cause=_system(family, "loc-a"),
        )
        assert event.schema_version == 7
        assert _payload_effect_complete(details, schema_version=7) is True  # type: ignore[arg-type]
        assert decode_domain(encode_domain(event)) == event
        encoded = json.loads(encode_domain(event))
        payload = encoded["data"]["details"]
        assert _FORBIDDEN.isdisjoint(payload)
        assert "color" not in payload
    assert any(
        record.levelno == logging.DEBUG
        and "environment_event_built schema_version=7 kind=season_changed"
        in record.getMessage()
        for record in caplog.records
    )
    assert not any(
        "environment_event_built" in record.getMessage()
        and "resource_harvested" in record.getMessage()
        for record in caplog.records
    )


def test_v5_and_v6_decoders_reject_environment_payloads() -> None:
    event = _event(
        SeasonChanged(Season.WINTER),
        schema_version=EVENT_SCHEMA_REPLAY_V7,
        cause=_system(SystemEffectFamily.SEASON, "loc-a"),
    )
    raw = json.loads(encode_domain(event))
    for schema in (5, 6):
        raw["data"]["schema_version"] = schema
        with pytest.raises(
            DomainSerializationError,
            match="invalid_event_schema_version",
        ):
            decode_domain(json.dumps(raw).encode())


def test_production_details_are_legal_on_v6_and_v7() -> None:
    harvested = ResourceHarvested(
        RecipeId("harvest_wood"),
        EntityId("res-wood"),
        False,
        1,
        2.0,
    )
    cause = ActionCause(RequestId("req-1"), EntityId("body-1"))
    for schema in (EVENT_SCHEMA_REPLAY_V6, EVENT_SCHEMA_REPLAY_V7):
        event = make_physical_replayable_event(
            event_id=EventId("evt-h"),
            run_id="run-1",
            world_id=WorldId("world-1"),
            tick=1,
            sequence=0,
            cause=cause,
            resulting_revision=WorldRevision(1),
            details=harvested,
            occurrence=OccurrenceContext(origin_location_id=EntityId("loc-1")),
            schema_version=schema,
        )
        assert decode_domain(encode_domain(event)) == event
        assert _payload_effect_complete(harvested, schema_version=schema) is True


def test_node_and_hazard_witnesses_constrain_quantities() -> None:
    with pytest.raises(ValueError, match="resulting_quantity must be 0"):
        ResourceNodeDepleted(EntityId("res-food"), 1.0)
    with pytest.raises(ValueError, match="resulting_quantity must be > 0"):
        ResourceNodeRecovered(EntityId("res-food"), 0.0)
    with pytest.raises(ValueError, match="remaining_ticks must be 0"):
        EnvironmentalHazardEnded(EntityId("loc-b"), HazardKind.COLD_SNAP, 1)
    with pytest.raises(ValueError, match="remaining_ticks must equal duration"):
        EnvironmentalHazardStarted(EntityId("loc-b"), HazardKind.HEAT, 6, 5)
    for details in _environment_details():
        assert _FORBIDDEN.isdisjoint(details.__slots__)  # type: ignore[attr-defined]


def test_occurrence_uses_location_or_resource_not_the_calendar() -> None:
    lowest = EntityId("loc-a")
    season = build_occurrence_context(
        SeasonChanged(Season.SUMMER),
        origin_location_id=lowest,
    )
    assert season.origin_location_id == lowest
    band = build_occurrence_context(
        TemperatureBandChanged(EntityId("loc-b"), TemperatureBand.COLD),
        origin_location_id=EntityId("loc-ignored"),
    )
    assert band.origin_location_id == EntityId("loc-b")
    started = build_occurrence_context(
        EnvironmentalHazardStarted(EntityId("loc-b"), HazardKind.HEAT, 6, 6),
        origin_location_id=EntityId("loc-ignored"),
    )
    assert started.origin_location_id == EntityId("loc-b")
    node = build_occurrence_context(
        ResourceNodeDepleted(EntityId("res-food"), 0.0),
        origin_location_id=lowest,
    )
    assert node.affected_entity_ids == (EntityId("res-food"),)
    assert node.origin_location_id == lowest
    event = _event(
        SeasonChanged(Season.SUMMER),
        schema_version=EVENT_SCHEMA_REPLAY_V7,
        cause=_system(SystemEffectFamily.SEASON, "loc-a"),
    )
    assert event.cause is not None
    assert event.actor_id is None
    assert event.target_id is None
    assert event.cause.entity_id == lowest  # type: ignore[union-attr]
    assert EventValidationCode.INVALID_SCHEMA_VERSION.value == (
        "invalid_event_schema_version"
    )


def test_checkpoint_pair_follows_the_spec(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert PERSISTENCE_CODEC_VERSION == "v2"
    assert EVENT_SCHEMA_VERSION == 5
    assert "v4" in ACCEPTED_PERSISTENCE_CODEC_VERSIONS
    assert checkpoint_schema_for_production(
        production_active=False, dynamics_active=False
    ) == (EVENT_SCHEMA_VERSION, "v2")
    assert checkpoint_schema_for_production(
        production_active=True, dynamics_active=False
    ) == (EVENT_SCHEMA_REPLAY_V6, "v3")
    assert checkpoint_schema_for_production(
        production_active=True, dynamics_active=True
    ) == (EVENT_SCHEMA_REPLAY_V7, "v4")
    assert schema_projector_compatible(
        event_schema_version=EVENT_SCHEMA_REPLAY_V7, projector_version="v2"
    )

    def _snap(*, schema: int, codec: str) -> WorldSnapshot:
        return WorldSnapshot(
            snapshot_id=SnapshotId("snap-env"),
            run_id=RunId("run-env"),
            world_id=WorldId("world-1"),
            seed=7,
            config=SimulationRunConfig(seed=7),
            registrations=(
                AgentRegistration(AgentId("agent-1"), EntityId("body-1")),
            ),
            locations=(make_location("loc-1"),),
            bodies=(alive_body(),),
            items=(),
            resources=(),
            weather=(make_weather(),),
            next_tick=Tick(0),
            revision=WorldRevision(0),
            event_schema_version=schema,
            projector_version=PROJECTOR_VERSION,
            persistence_codec_version=codec,
            derivation_version=DERIVATION_VERSION,
            integrity_hash=PayloadHash("a" * 64),
            predecessor_commit_hash=None,
        )

    paired = _snap(schema=EVENT_SCHEMA_REPLAY_V7, codec="v4")
    assert paired.persistence_codec_version == "v4"
    with pytest.raises(ValueError, match="codec v4 requires event schema 7"):
        _snap(schema=EVENT_SCHEMA_REPLAY_V6, codec="v4")
    with pytest.raises(ValueError, match="codec v3 requires event schema 6"):
        _snap(schema=EVENT_SCHEMA_REPLAY_V7, codec="v3")
    assert _snap(schema=EVENT_SCHEMA_REPLAY_V6, codec="v3").event_schema_version == 6
    created = RunCreateRequest(
        run_id=RunId("run-env"),
        world_id=WorldId("world-1"),
        seed=7,
        config=SimulationRunConfig(seed=7),
        bootstrap=paired,
        event_schema_version=EVENT_SCHEMA_REPLAY_V7,
        persistence_codec_version="v4",
    )
    assert created.event_schema_version == EVENT_SCHEMA_REPLAY_V7
    assert created.persistence_codec_version == "v4"
    with pytest.raises(ValueError, match="EVENT_SCHEMA_VERSION"):
        RunCreateRequest(
            run_id=RunId("run-env"),
            world_id=WorldId("world-1"),
            seed=7,
            config=SimulationRunConfig(seed=7),
            bootstrap=_snap(schema=EVENT_SCHEMA_VERSION, codec="v2"),
            event_schema_version=EVENT_SCHEMA_REPLAY_V7,
            persistence_codec_version="v2",
        )
    caplog.set_level(logging.DEBUG, logger="simulation.engine")
    selected = select_checkpoint_schema(
        production_active=False, dynamics_active=True
    )
    assert selected == (EVENT_SCHEMA_REPLAY_V7, "v4")
    assert any(
        "environment_schema_selected schema_version=7 codec=v4" in record.getMessage()
        for record in caplog.records
    )
    monkeypatch.setattr(
        "simulation.persistence.checkpoint_schema_for_production",
        lambda **_kwargs: (EVENT_SCHEMA_REPLAY_V7, "v2"),
    )
    with pytest.raises(ValueError, match="unsupported_schema_version"):
        select_checkpoint_schema(production_active=False, dynamics_active=True)
    assert any(
        record.levelno == logging.ERROR
        and "unsupported_schema_version schema_version=7 codec=v2"
        in record.getMessage()
        for record in caplog.records
    )
