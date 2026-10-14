"""Replay 20 and codec v18 keep public acts off the v17 channel."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from simulation.engine import select_checkpoint_schema
from simulation.journal import (
    PersistenceSerializationError,
    decode_persistence,
    encode_persistence,
)
from simulation.persistence import (
    EVENT_SCHEMA_REPLAY_V19,
    EVENT_SCHEMA_REPLAY_V20,
    checkpoint_schema_for_production,
)
from tests.unit.test_collective_project_replay_schema import (
    _engine,
    _open_project,
    _snapshot,
)
from world.collective_projects import (
    PublicGoodAct,
    PublicGoodActKind,
    PublicGoodActSource,
)
from world.identifiers import EntityId
from world.production import Structure, StructureKind

pytestmark = pytest.mark.unit


def test_channel_on_selects_replay_20() -> None:
    pair = checkpoint_schema_for_production(
        production_active=False,
        collective_projects_active=True,
        public_goods_active=True,
    )
    assert pair == (EVENT_SCHEMA_REPLAY_V20, "v18")
    agreed = select_checkpoint_schema(
        production_active=False,
        dynamics_active=False,
        collective_projects_active=True,
        public_goods_active=True,
    )
    assert agreed == (EVENT_SCHEMA_REPLAY_V20, "v18")


def test_channel_off_does_not_select_v18() -> None:
    pair = checkpoint_schema_for_production(
        production_active=False,
        collective_projects_active=True,
    )
    assert pair == (EVENT_SCHEMA_REPLAY_V19, "v17")


def test_v18_round_trips_public_acts() -> None:
    linked = EntityId("structure-store")
    project = replace(
        _open_project(),
        linked_structure_id=linked,
        public_acts=(
            PublicGoodAct(
                actor_id=EntityId("body-a"),
                tick=1,
                act=PublicGoodActKind.DRAW,
                source=PublicGoodActSource.COMMAND,
            ),
        ),
    )
    engine = _engine()
    snap = _snapshot(
        engine,
        codec="v18",
        schema=EVENT_SCHEMA_REPLAY_V20,
        projects=(project,),
    )
    decoded = decode_persistence(encode_persistence(snap), type(snap))
    assert decoded.persistence_codec_version == "v18"
    restored = decoded.collective_projects[0]
    assert restored.linked_structure_id == linked
    assert restored.public_acts[0].act is PublicGoodActKind.DRAW


def test_v17_rejects_public_acts_and_well() -> None:
    engine = _engine()
    snap = _snapshot(engine, codec="v17", schema=EVENT_SCHEMA_REPLAY_V19)
    document = json.loads(encode_persistence(snap))
    document["data"]["collective_projects"] = [
        {
            "contributions": [],
            "kind": "storage",
            "labor_done": 0,
            "labor_required": 1,
            "last_accepted_tick": 0,
            "location_id": "loc-1",
            "materials_done": 0,
            "materials_required": 1,
            "opened_tick": 0,
            "project_id": "project-1",
            "shortage_count": 0,
            "status": "open",
            "target_structure_id": None,
            "public_acts": [],
        }
    ]
    with pytest.raises(PersistenceSerializationError):
        decode_persistence(json.dumps(document).encode(), type(snap))
    well = Structure(
        entity_id=EntityId("structure-well"),
        location_id=EntityId("loc-1"),
        kind=StructureKind.WELL,
        integrity=1.0,
        stored_quantity=0,
    )
    with pytest.raises(ValueError, match="well and warning_post require codec v18"):
        _snapshot(
            engine,
            codec="v17",
            schema=EVENT_SCHEMA_REPLAY_V19,
            structures=(well,),
        )
