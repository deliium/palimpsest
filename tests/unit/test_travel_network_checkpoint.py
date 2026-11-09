"""V4-17 codec-v25 checkpoints and selection priority."""

from __future__ import annotations

from dataclasses import replace
from typing import cast

import pytest

from agents.models import AgentId
from simulation.bootstrap import AgentRegistration
from simulation.clock import Tick
from simulation.journal import (
    PersistenceSerializationError,
    decode_persistence,
    encode_persistence,
    hash_snapshot,
)
from simulation.models import DERIVATION_VERSION, RunId, SimulationRunConfig
from simulation.persistence import (
    PROJECTOR_VERSION,
    PayloadHash,
    SnapshotId,
    WorldSnapshot,
    checkpoint_schema_for_production,
)
from tests.simulation_helpers import (
    alive_body,
    connected_locations,
    weather_for_locations,
)
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import default_physical_rules
from world.regions import (
    CognitionMode,
    LocationRegion,
    RegionDefinition,
    RegionsMigrationSpec,
    RouteSpec,
)
from world.travel_network import (
    RouteBlockageCause,
    RouteCondition,
    RouteStatus,
    SeasonalAvailability,
)

pytestmark = pytest.mark.unit

ROUTE = RouteCondition(
    origin_id=EntityId("loc-1"),
    destination_id=EntityId("loc-2"),
    status=RouteStatus.RESTRICTED,
    seasonal_availability=SeasonalAvailability.RESTRICTED,
    blockage_cause=RouteBlockageCause.SEASONAL,
    duration_ticks=3,
    fatigue_cost=4.5,
    capacity=6,
    risk=0.3,
    infrastructure_quality=0.4,
    reason_codes=("season_autumn", "route_restricted"),
    as_of_tick=1,
)


def _snapshot(*, codec: str = "v25", schema: int = 27) -> WorldSnapshot:
    locations = connected_locations(("loc-1", "One"), ("loc-2", "Two"))
    body = alive_body("body-1", location_id="loc-1")
    spec = RegionsMigrationSpec(
        regions=(
            RegionDefinition("north", "North"),
            RegionDefinition("south", "South"),
        ),
        location_regions=(
            LocationRegion(EntityId("loc-1"), "north"),
            LocationRegion(EntityId("loc-2"), "south"),
        ),
        routes=(RouteSpec(EntityId("loc-1"), EntityId("loc-2"), 2, 4.0),),
        max_arrival_wait_ticks=1,
        residence_min_ticks=3,
        destination_memory_limit=2,
        destination_hop_limit=1,
        cognition_mode=CognitionMode.DISABLED,
    )
    draft = WorldSnapshot(
        snapshot_id=SnapshotId("snapshot-travel"),
        run_id=RunId("run-travel"),
        world_id=WorldId("world-travel"),
        seed=7,
        config=SimulationRunConfig(
            seed=7,
            physical_rules=default_physical_rules(),
        ),
        registrations=(AgentRegistration(AgentId("agent-1"), body.entity_id),),
        locations=locations,
        bodies=(body,),
        items=(),
        resources=(),
        weather=weather_for_locations(locations),
        next_tick=Tick(2),
        revision=WorldRevision(1),
        event_schema_version=schema,
        projector_version=PROJECTOR_VERSION,
        persistence_codec_version=codec,
        derivation_version=DERIVATION_VERSION,
        integrity_hash=PayloadHash("a" * 64),
        predecessor_commit_hash=None,
        regions_migration=spec,
        journeys=(),
        infrastructure=(),
        travel_network=(ROUTE,) if codec == "v25" else None,
    )
    return replace(draft, integrity_hash=hash_snapshot(draft))


def test_selection_priority() -> None:
    assert checkpoint_schema_for_production(
        production_active=False, travel_network_active=True
    ) == (27, "v25")
    assert checkpoint_schema_for_production(
        production_active=False, infrastructure_networks_active=True
    ) == (23, "v21")
    assert checkpoint_schema_for_production(
        production_active=False, regions_migration_active=True
    ) == (21, "v19")


def test_v25_round_trip_and_hash_stability() -> None:
    snapshot = _snapshot()
    payload = encode_persistence(snapshot)
    decoded = decode_persistence(payload, expected_type=WorldSnapshot)
    assert decoded == snapshot
    assert decoded.travel_network == (ROUTE,)
    assert hash_snapshot(decoded) == hash_snapshot(snapshot)


def test_v25_requires_schema_27_and_route_rows() -> None:
    with pytest.raises(ValueError, match="codec v25 requires event schema 27"):
        _snapshot(schema=23)
    with pytest.raises(
        ValueError, match="travel_network_checkpoint_fields_require_codec_v25"
    ):
        replace(
            _snapshot(),
            travel_network=None,
        )


def test_v25_requires_regions_channel() -> None:
    with pytest.raises(ValueError, match="travel_network_checkpoint_requires_regions"):
        replace(_snapshot(), regions_migration=None, journeys=None)


def test_v21_rejects_route_rows() -> None:
    with pytest.raises(
        ValueError, match="travel_network_checkpoint_fields_require_codec_v25"
    ):
        replace(_snapshot(codec="v21", schema=23), travel_network=(ROUTE,))


def test_v21_checkpoint_still_decodes() -> None:
    snapshot = _snapshot(codec="v21", schema=23)
    decoded = cast(
        WorldSnapshot,
        decode_persistence(encode_persistence(snapshot), expected_type=WorldSnapshot),
    )
    assert decoded.persistence_codec_version == "v21"
    assert decoded.travel_network is None


def test_empty_route_tuple_is_valid() -> None:
    snapshot = replace(_snapshot(), travel_network=())
    decoded = cast(
        WorldSnapshot,
        decode_persistence(encode_persistence(snapshot), expected_type=WorldSnapshot),
    )
    assert decoded.travel_network == ()


def test_v25_unknown_route_key_is_rejected() -> None:
    payload = encode_persistence(_snapshot())
    import json

    document = json.loads(payload)
    document["data"]["travel_network"][0]["unexpected"] = True
    with pytest.raises(PersistenceSerializationError):
        decode_persistence(
            json.dumps(document).encode("utf-8"), expected_type=WorldSnapshot
        )
