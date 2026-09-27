"""Semantic adapter keeps structural facts and drops utterance text."""

from __future__ import annotations

import json

import pytest

from observer.adapt import adapt_event, adapt_events
from observer.contracts import ObserverContractError, ObserverEvent
from observer.version import OBSERVER_PROTOCOL_VERSION
from world.communications import origin_utterance
from world.effects import ActionCause, SystemCause, SystemEffectFamily
from world.events import (
    Given,
    ResourceRegenerated,
    Talked,
    WeatherChanged,
    build_occurrence_context,
    make_physical_replayable_event,
)
from world.identifiers import EntityId, EventId, RequestId, WorldId, WorldRevision
from world.values import WeatherCondition

pytestmark = pytest.mark.unit


def _event(
    *,
    event_id: str,
    details: object,
    cause: ActionCause | SystemCause,
    tick: int,
    sequence: int,
    origin: str = "loc-1",
) -> object:
    return make_physical_replayable_event(
        event_id=EventId(event_id),
        run_id="run-1",
        world_id=WorldId("world-1"),
        tick=tick,
        sequence=sequence,
        cause=cause,
        resulting_revision=WorldRevision(1),
        details=details,  # type: ignore[arg-type]
        occurrence=build_occurrence_context(
            details,  # type: ignore[arg-type]
            origin_location_id=EntityId(origin),
        ),
    )


def test_given_weather_resource_talk_and_order() -> None:
    actor = ActionCause(RequestId("req-give"), EntityId("body-1"))
    given = _event(
        event_id="evt-give",
        details=Given(
            recipient_id=EntityId("body-2"),
            item_id=EntityId("item-1"),
            resulting_holder_id=EntityId("body-2"),
        ),
        cause=actor,
        tick=2,
        sequence=0,
        origin="loc-camp",
    )
    weather = _event(
        event_id="evt-weather",
        details=WeatherChanged(EntityId("loc-1"), WeatherCondition.RAIN),
        cause=SystemCause(
            RequestId("req-weather"),
            SystemEffectFamily.WEATHER,
            EntityId("loc-1"),
            0,
        ),
        tick=2,
        sequence=4,
    )
    resource = _event(
        event_id="evt-resource",
        details=ResourceRegenerated(
            EntityId("res-1"),
            quantity_delta=1.0,
            resulting_quantity=4.0,
        ),
        cause=SystemCause(
            RequestId("req-resource"),
            SystemEffectFamily.REGENERATION,
            EntityId("res-1"),
            0,
        ),
        tick=3,
        sequence=0,
    )
    secret = "secret-utterance-text"
    talked = _event(
        event_id="evt-talk",
        details=Talked(
            EntityId("body-2"),
            origin_utterance(text=secret, speaker_id=EntityId("body-1")),
        ),
        cause=ActionCause(RequestId("req-talk"), EntityId("body-1")),
        tick=3,
        sequence=1,
    )
    page = adapt_events((given, weather, resource, talked))  # type: ignore[arg-type]
    assert [item.event_id for item in page] == [
        "evt-give",
        "evt-weather",
        "evt-resource",
        "evt-talk",
    ]
    gave = page[0]
    assert gave.type == "AGENT_GAVE_ITEM"
    assert gave.actor_id == "body-1"
    assert gave.target_id == "body-2"
    assert gave.item_id == "item-1"
    assert gave.origin_location_id == "loc-camp"
    assert page[1].domain_kind == "weather_changed"
    assert page[1].type == "WEATHER_CHANGED"
    assert page[2].domain_kind == "resource_regenerated"
    assert page[2].type == "RESOURCE_REGENERATED"
    encoded = json.dumps(page[3].public_mapping())
    assert secret not in encoded
    assert "private_recipient" not in encoded


def test_unknown_kind_and_inverse_type() -> None:
    with pytest.raises(TypeError, match="unknown_event_kind"):
        adapt_event(object())  # type: ignore[arg-type]
    with pytest.raises(ObserverContractError):
        ObserverEvent(
            protocol_version=OBSERVER_PROTOCOL_VERSION,
            type="AGENT_UNDIED",
            domain_kind="died",
            event_id="evt-x",
            tick=0,
            sequence=0,
        )
