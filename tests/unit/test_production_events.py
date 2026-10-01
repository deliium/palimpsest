"""Replay-v6 production details stay off the default physical schema."""

from __future__ import annotations

import logging

import pytest

from simulation.serialization import (
    DomainSerializationError,
    decode_domain,
    encode_domain,
)
from world.actions import Build, Craft, Harvest, Repair, Store
from world.effects import ActionCause
from world.events import (
    CURRENT_PHYSICAL_EVENT_SCHEMA_VERSION,
    EVENT_SCHEMA_REPLAY_V5,
    EVENT_SCHEMA_REPLAY_V6,
    REPLAYABLE_EVENT_SCHEMA_VERSIONS,
    SUPPORTED_EVENT_SCHEMA_VERSIONS,
    CraftStarted,
    EventValidationCode,
    ItemCrafted,
    ItemStored,
    OccurrenceContext,
    ResourceHarvested,
    StructureBuilt,
    StructureRepaired,
    WorldEvent,
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


def _cause() -> ActionCause:
    return ActionCause(
        request_id=RequestId("req-1"),
        actor_id=EntityId("body-1"),
    )


def _event(details: object, *, schema_version: int) -> WorldEvent:
    cause = _cause()
    return make_physical_replayable_event(
        event_id=EventId("evt-1"),
        run_id="run-1",
        world_id=WorldId("world-1"),
        tick=1,
        sequence=0,
        cause=cause,
        resulting_revision=WorldRevision(1),
        details=details,  # type: ignore[arg-type]
        occurrence=OccurrenceContext(origin_location_id=EntityId("loc-1")),
        schema_version=schema_version,
    )


def test_default_schema_stays_replay_v5_and_v6_is_accepted() -> None:
    assert CURRENT_PHYSICAL_EVENT_SCHEMA_VERSION == EVENT_SCHEMA_REPLAY_V5
    assert EVENT_SCHEMA_REPLAY_V6 in SUPPORTED_EVENT_SCHEMA_VERSIONS
    assert EVENT_SCHEMA_REPLAY_V6 in REPLAYABLE_EVENT_SCHEMA_VERSIONS
    assert 6 in SUPPORTED_EVENT_SCHEMA_VERSIONS


def test_v5_rejects_production_details(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.ERROR, logger="world.events")
    details = ResourceHarvested(
        RecipeId("harvest_wood"),
        EntityId("res-wood"),
        False,
        1,
        2.0,
    )
    with pytest.raises(ValueError, match="invalid_event_schema_version"):
        _event(details, schema_version=EVENT_SCHEMA_REPLAY_V5)
    assert any(
        "invalid_event_schema_version" in record.getMessage()
        and "kind=resource_harvested" in record.getMessage()
        and "schema_version=5" in record.getMessage()
        for record in caplog.records
    )


def test_failed_harvest_and_craft_have_no_created_outputs(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger="world.events")
    harvested = ResourceHarvested(
        RecipeId("harvest_wood"),
        EntityId("res-wood"),
        False,
        1,
        4.0,
    )
    assert harvested.created_item_id is None
    event = _event(harvested, schema_version=EVENT_SCHEMA_REPLAY_V6)
    assert event.schema_version == 6
    assert any(
        "production_event_built schema_version=6 kind=resource_harvested success=False"
        in record.getMessage()
        for record in caplog.records
    )
    started = CraftStarted(RecipeId("craft_tool"), False, 2)
    assert started.consumed_item_ids == ()
    crafted_absent = _event(started, schema_version=EVENT_SCHEMA_REPLAY_V6)
    assert type(crafted_absent.details) is CraftStarted
    with pytest.raises(ValueError, match="failure detail"):
        ItemCrafted(
            RecipeId("craft_tool"),
            EntityId("item-tool"),
            EntityId("body-1"),
            2,
            success=False,
        )
    with pytest.raises(ValueError, match="failure detail"):
        StructureBuilt(
            RecipeId("build_shelter"),
            EntityId("struct-1"),
            EntityId("loc-1"),
            0.75,
            1,
            EntityId("item-wood"),
            success=False,
        )


def test_store_event_is_effect_complete_and_has_no_presentation() -> None:
    stored = ItemStored(
        RecipeId("store_food"),
        EntityId("struct-store"),
        1,
        1,
        EntityId("item-food"),
    )
    event = _event(stored, schema_version=EVENT_SCHEMA_REPLAY_V6)
    assert event.target_id == EntityId("struct-store")
    payload = event.details
    assert type(payload) is ItemStored
    assert payload.resulting_stored_quantity == 1
    forbidden = {"pixels", "sprite", "animation", "dx", "dy", "screen_x", "screen_y"}
    assert forbidden.isdisjoint(payload.__slots__)
    encoded = encode_domain(event)
    assert decode_domain(encoded) == event
    assert b"sprite" not in encoded
    assert b"screen_x" not in encoded


def test_command_codecs_use_exact_keys() -> None:
    harvest = Harvest(RecipeId("harvest_wood"), EntityId("res-wood"))
    craft = Craft(RecipeId("craft_tool"))
    build = Build(RecipeId("build_shelter"))
    repair = Repair(RecipeId("repair_shelter"), EntityId("struct-1"))
    store = Store(RecipeId("store_food"), EntityId("item-food"))
    for command in (harvest, craft, build, repair, store):
        assert decode_domain(encode_domain(command)) == command
    assert b'"type":"craft"' in encode_domain(craft)


def test_command_extra_key_is_rejected() -> None:
    import json

    encoded = decode_domain(encode_domain(Craft(RecipeId("craft_tool"))))
    assert type(encoded) is Craft
    payload = {
        "data": {"extra": 1, "recipe_id": "craft_tool"},
        "schema_version": 1,
        "type": "craft",
    }
    with pytest.raises(DomainSerializationError) as exc:
        decode_domain(json.dumps(payload).encode())
    assert exc.value.code == "invalid_fields"


def test_v5_detail_decoder_rejects_production_kind() -> None:
    import json

    from world.effects import ActionCause
    from world.events import OccurrenceContext, Waited

    waited = make_physical_replayable_event(
        event_id=EventId("evt-wait"),
        run_id="run-1",
        world_id=WorldId("world-1"),
        tick=0,
        sequence=0,
        cause=ActionCause(RequestId("req-1"), EntityId("body-1")),
        resulting_revision=WorldRevision(1),
        details=Waited(),
        occurrence=OccurrenceContext(origin_location_id=EntityId("loc-1")),
    )
    encoded = json.loads(encode_domain(waited))
    encoded["data"]["details"] = {
        "duration_ticks": 1,
        "kind": "resource_harvested",
        "recipe_id": "harvest_wood",
        "resource_id": "res-wood",
        "resulting_resource_quantity": 1.0,
        "success": False,
    }
    encoded["data"]["schema_version"] = EVENT_SCHEMA_REPLAY_V5
    with pytest.raises(DomainSerializationError) as exc:
        decode_domain(json.dumps(encoded).encode())
    assert exc.value.code == "invalid_event_schema_version"


def test_success_events_round_trip() -> None:
    events = [
        ResourceHarvested(
            RecipeId("harvest_wood"),
            EntityId("res-wood"),
            True,
            1,
            3.0,
            created_item_id=EntityId("item-wood"),
        ),
        CraftStarted(
            RecipeId("craft_tool"),
            True,
            2,
            (EntityId("item-wood"), EntityId("item-stone")),
        ),
        ItemCrafted(
            RecipeId("craft_tool"),
            EntityId("item-tool"),
            EntityId("body-1"),
            2,
        ),
        StructureBuilt(
            RecipeId("build_shelter"),
            EntityId("struct-shelter"),
            EntityId("loc-1"),
            0.75,
            1,
            EntityId("item-wood"),
        ),
        StructureRepaired(
            RecipeId("repair_shelter"),
            EntityId("struct-shelter"),
            1.0,
            1,
            EntityId("item-stone"),
        ),
        ItemStored(
            RecipeId("store_food"),
            EntityId("struct-store"),
            2,
            1,
            EntityId("item-food"),
        ),
    ]
    for index, details in enumerate(events):
        event = make_physical_replayable_event(
            event_id=EventId(f"evt-{index}"),
            run_id="run-1",
            world_id=WorldId("world-1"),
            tick=1,
            sequence=0,
            cause=_cause(),
            resulting_revision=WorldRevision(1),
            details=details,
            occurrence=OccurrenceContext(origin_location_id=EntityId("loc-1")),
            schema_version=EVENT_SCHEMA_REPLAY_V6,
        )
        assert event.schema_version == EVENT_SCHEMA_REPLAY_V6
        assert decode_domain(encode_domain(event)) == event
        assert EventValidationCode.INVALID_SCHEMA_VERSION.value == (
            "invalid_event_schema_version"
        )
