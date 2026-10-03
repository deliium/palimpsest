"""Replay-v8 artifact details stay off schemas that do not own them."""

from __future__ import annotations

import json
import logging

import pytest

from simulation.persistence import ACCEPTED_EVENT_SCHEMA_VERSIONS, EVENT_SCHEMA_VERSION
from simulation.serialization import (
    DomainSerializationError,
    decode_domain,
    encode_domain,
)
from world.actions import Amend, Erase, Inscribe, TransferArtifact
from world.artifacts import ArtifactContent, ArtifactKind, ArtifactRelation
from world.effects import ActionCause
from world.environment import HazardKind, Season, TemperatureBand
from world.events import (
    CURRENT_PHYSICAL_EVENT_SCHEMA_VERSION,
    EVENT_SCHEMA_REPLAY_V5,
    EVENT_SCHEMA_REPLAY_V6,
    EVENT_SCHEMA_REPLAY_V7,
    EVENT_SCHEMA_REPLAY_V8,
    REPLAYABLE_EVENT_SCHEMA_VERSIONS,
    SUPPORTED_EVENT_SCHEMA_VERSIONS,
    ArtifactCreated,
    ArtifactDestroyed,
    ArtifactModified,
    ArtifactMoved,
    EnvironmentalHazardStarted,
    EventValidationCode,
    OccurrenceContext,
    ResourceHarvested,
    SeasonChanged,
    TemperatureBandChanged,
    WorldEvent,
    _payload_effect_complete,
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


def _cause() -> ActionCause:
    return ActionCause(
        request_id=RequestId("req-1"),
        actor_id=EntityId("body-1"),
    )


def _event(details: object, *, schema_version: int) -> WorldEvent:
    return make_physical_replayable_event(
        event_id=EventId("evt-1"),
        run_id="run-1",
        world_id=WorldId("world-1"),
        tick=1,
        sequence=0,
        cause=_cause(),
        resulting_revision=WorldRevision(1),
        details=details,  # type: ignore[arg-type]
        occurrence=OccurrenceContext(origin_location_id=EntityId("loc-1")),
        schema_version=schema_version,
    )


def _artifact_details() -> tuple[object, ...]:
    return (
        ArtifactCreated(
            EntityId("art-1"),
            ArtifactKind.SIGN,
            EntityId("body-1"),
            0,
            resulting_location_id=EntityId("loc-1"),
        ),
        ArtifactModified(
            EntityId("art-1"),
            ArtifactKind.NOTE,
            1,
            resulting_holder_id=EntityId("body-1"),
        ),
        ArtifactMoved(
            EntityId("art-1"),
            ArtifactKind.NOTE,
            1,
            resulting_location_id=EntityId("loc-2"),
        ),
        ArtifactDestroyed(EntityId("art-1"), ArtifactKind.RECORD, 2),
    )


def test_default_schema_stays_replay_v5_and_v8_is_accepted() -> None:
    assert CURRENT_PHYSICAL_EVENT_SCHEMA_VERSION == EVENT_SCHEMA_REPLAY_V5 == 5
    assert EVENT_SCHEMA_VERSION == 5
    assert EVENT_SCHEMA_REPLAY_V8 == 8
    assert 8 in SUPPORTED_EVENT_SCHEMA_VERSIONS
    assert 8 in REPLAYABLE_EVENT_SCHEMA_VERSIONS
    assert 8 in ACCEPTED_EVENT_SCHEMA_VERSIONS


def test_below_v8_rejects_artifact_details(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.ERROR, logger="world.events")
    for schema in (
        EVENT_SCHEMA_REPLAY_V5,
        EVENT_SCHEMA_REPLAY_V6,
        EVENT_SCHEMA_REPLAY_V7,
    ):
        for details in _artifact_details():
            with pytest.raises(ValueError, match="invalid_event_schema_version"):
                _event(details, schema_version=schema)
            assert _payload_effect_complete(details, schema_version=schema) is False  # type: ignore[arg-type]
    assert any(
        "invalid_event_schema_version" in record.getMessage()
        and "kind=artifact_created" in record.getMessage()
        and "schema_version=5" in record.getMessage()
        for record in caplog.records
    )


def test_v8_accepts_artifact_details_and_logs_ids(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger="world.events")
    for details in _artifact_details():
        event = _event(details, schema_version=EVENT_SCHEMA_REPLAY_V8)
        assert event.schema_version == 8
        assert event.target_id == EntityId("art-1")
        assert _payload_effect_complete(details, schema_version=8) is True  # type: ignore[arg-type]
        assert decode_domain(encode_domain(event)) == event
        encoded = json.loads(encode_domain(event))
        payload = encoded["data"]["details"]
        assert _FORBIDDEN.isdisjoint(payload)
        assert "marks" not in payload
        assert "relations" not in payload
    assert any(
        record.levelno == logging.DEBUG
        and "artifact_event_built schema_version=8 kind=artifact_created "
        "artifact_id=art-1" in record.getMessage()
        for record in caplog.records
    )


def test_lower_schema_decoders_reject_artifact_payloads() -> None:
    event = _event(
        ArtifactDestroyed(EntityId("art-1"), ArtifactKind.MEMORIAL, 0),
        schema_version=EVENT_SCHEMA_REPLAY_V8,
    )
    raw = json.loads(encode_domain(event))
    for schema in (5, 6, 7):
        raw["data"]["schema_version"] = schema
        with pytest.raises(
            DomainSerializationError,
            match="invalid_event_schema_version",
        ):
            decode_domain(json.dumps(raw).encode())


def test_production_and_environment_details_are_legal_on_v8() -> None:
    harvested = ResourceHarvested(
        RecipeId("harvest_wood"),
        EntityId("res-wood"),
        False,
        1,
        2.0,
    )
    season = SeasonChanged(Season.SUMMER)
    band = TemperatureBandChanged(EntityId("loc-b"), TemperatureBand.HOT)
    hazard = EnvironmentalHazardStarted(
        EntityId("loc-b"),
        HazardKind.HEAT,
        6,
        6,
    )
    for details in (harvested, season, band, hazard):
        event = make_physical_replayable_event(
            event_id=EventId("evt-combo"),
            run_id="run-1",
            world_id=WorldId("world-1"),
            tick=1,
            sequence=0,
            cause=_cause(),
            resulting_revision=WorldRevision(1),
            details=details,
            occurrence=OccurrenceContext(origin_location_id=EntityId("loc-1")),
            schema_version=EVENT_SCHEMA_REPLAY_V8,
        )
        assert decode_domain(encode_domain(event)) == event
        assert _payload_effect_complete(details, schema_version=8) is True


def test_command_codecs_use_exact_keys() -> None:
    content = ArtifactContent(
        marks=("water", "north"),
        relations=(ArtifactRelation("water", "at", "north"),),
    )
    inscribe = Inscribe(ArtifactKind.NOTE, content, hold=True)
    amend = Amend(EntityId("art-1"), content)
    erase = Erase(EntityId("art-1"))
    transfer = TransferArtifact(EntityId("art-1"), "deposit")
    give = TransferArtifact(EntityId("art-1"), "give", EntityId("body-2"))
    for command in (inscribe, amend, erase, transfer, give):
        assert decode_domain(encode_domain(command)) == command
    assert b'"type":"inscribe"' in encode_domain(inscribe)
    assert b'"type":"transfer_artifact"' in encode_domain(transfer)


def test_command_extra_key_is_rejected() -> None:
    payload = {
        "data": {
            "artifact_id": "art-1",
            "extra": 1,
        },
        "schema_version": 1,
        "type": "erase",
    }
    with pytest.raises(DomainSerializationError) as exc:
        decode_domain(json.dumps(payload).encode())
    assert exc.value.code == "invalid_fields"


def test_no_presentation_fields_on_artifact_details() -> None:
    for details in _artifact_details():
        assert _FORBIDDEN.isdisjoint(details.__slots__)  # type: ignore[attr-defined]
    with pytest.raises(ValueError, match="portable"):
        ArtifactMoved(
            EntityId("art-1"),
            ArtifactKind.SIGN,
            0,
            resulting_location_id=EntityId("loc-1"),
        )
    with pytest.raises(ValueError, match="failure detail"):
        ArtifactDestroyed(
            EntityId("art-1"),
            ArtifactKind.NOTE,
            0,
            success=False,
        )
    assert EventValidationCode.INVALID_SCHEMA_VERSION.value == (
        "invalid_event_schema_version"
    )
