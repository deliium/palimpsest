"""Production checkpoints and event folds stay optional."""

from __future__ import annotations

import json
import logging

import pytest

from agents.models import AgentId
from simulation.clock import Tick
from simulation.engine import WorldEngine
from simulation.journal import (
    PersistenceSerializationError,
    decode_persistence,
    encode_persistence,
    hash_snapshot,
)
from simulation.lifecycle import ActionSubmission
from simulation.models import DERIVATION_VERSION
from simulation.persistence import (
    EVENT_SCHEMA_REPLAY_V6,
    PROJECTOR_VERSION,
    PayloadHash,
    SnapshotId,
    WorldSnapshot,
)
from tests.physical_helpers import (
    PhysicalWorldFixture,
    physical_config,
    two_location_fixture,
)
from tests.simulation_helpers import alive_body, make_item, make_resource
from tests.unit.determinism_helpers import project_world_state
from world._replay import ProjectionError, project_events
from world.actions import Build, Craft, Harvest, Move, Repair, Search, Store
from world.events import EVENT_SCHEMA_REPLAY_V5
from world.identifiers import EntityId, RecipeId, WorldRevision
from world.production import (
    ProductionCatalog,
    Structure,
    StructureKind,
    ToolMark,
    ToolRole,
    example_production_catalog,
    production_catalog_digest,
)
from world.values import ItemKind, ResourceKind

pytestmark = pytest.mark.unit

_V2_KEYS = {
    "snapshot_id",
    "run_id",
    "world_id",
    "seed",
    "config",
    "registrations",
    "locations",
    "bodies",
    "items",
    "resources",
    "weather",
    "next_tick",
    "revision",
    "event_schema_version",
    "projector_version",
    "persistence_codec_version",
    "derivation_version",
    "integrity_hash",
    "predecessor_commit_hash",
}


def _fixture(
    *,
    resources: tuple[object, ...] | None = None,
    items: tuple[object, ...] | None = None,
    bodies: tuple[object, ...] | None = None,
) -> PhysicalWorldFixture:
    base = two_location_fixture(item_on_ground=False)
    return PhysicalWorldFixture(
        world_id=base.world_id,
        locations=base.locations,
        bodies=base.bodies if bodies is None else bodies,  # type: ignore[arg-type]
        items=() if items is None else items,  # type: ignore[arg-type]
        resources=base.resources if resources is None else resources,  # type: ignore[arg-type]
        weather=base.weather,
        registrations=base.registrations,
    )


def _engine(
    fixture: PhysicalWorldFixture,
    *,
    seed: int = 1,
    catalog: ProductionCatalog | None = None,
) -> WorldEngine:
    kwargs: dict[str, object] = {}
    if catalog is not None:
        kwargs["production_catalog"] = catalog
    return WorldEngine(
        config=physical_config(seed),
        bootstrap=fixture.as_bootstrap(),
        **kwargs,
    )


def _act(engine: WorldEngine, command: object) -> None:
    batch = engine.observe()
    engine.resolve_tick((ActionSubmission(batch.token, AgentId("agent-1"), command),))  # type: ignore[arg-type]


def _snapshot(engine: WorldEngine, *, codec: str, schema: int) -> WorldSnapshot:
    state = engine._snapshot.world.state
    draft = WorldSnapshot(
        snapshot_id=SnapshotId("snap-production"),
        run_id=engine.run_id,
        world_id=engine.world_id,
        seed=engine._config.seed,
        config=engine._config,
        registrations=tuple(engine._bootstrap.registrations),
        locations=tuple(state.locations.values()),
        bodies=tuple(state.bodies.values()),
        items=tuple(state.items.values()),
        resources=tuple(state.resources.values()),
        weather=tuple(state.weather.values()),
        next_tick=engine.tick,
        revision=state.revision,
        event_schema_version=schema,
        projector_version=PROJECTOR_VERSION,
        persistence_codec_version=codec,
        derivation_version=engine._config.derivation_version or DERIVATION_VERSION,
        integrity_hash=PayloadHash("a" * 64),
        predecessor_commit_hash=None,
        structures=tuple(state.structures.values()),
        production_jobs=tuple(state.production_jobs.values()),
        tool_marks=tuple(state.tool_marks.values()),
    )
    return WorldSnapshot(
        snapshot_id=draft.snapshot_id,
        run_id=draft.run_id,
        world_id=draft.world_id,
        seed=draft.seed,
        config=draft.config,
        registrations=draft.registrations,
        locations=draft.locations,
        bodies=draft.bodies,
        items=draft.items,
        resources=draft.resources,
        weather=draft.weather,
        next_tick=draft.next_tick,
        revision=draft.revision,
        event_schema_version=draft.event_schema_version,
        projector_version=draft.projector_version,
        persistence_codec_version=draft.persistence_codec_version,
        derivation_version=draft.derivation_version,
        integrity_hash=hash_snapshot(draft),
        predecessor_commit_hash=None,
        structures=draft.structures,
        production_jobs=draft.production_jobs,
        tool_marks=draft.tool_marks,
    )


def _fold(engine: WorldEngine, catalog: ProductionCatalog | None) -> object:
    start = WorldEngine(
        config=engine._config,
        bootstrap=engine._bootstrap,
        production_catalog=catalog,
    )
    return project_events(
        start._snapshot.world.state,
        engine._snapshot.event_history,
        expected_run_id=engine.run_id.value,
        expected_world_id=engine.world_id,
        production_catalog=catalog,
    )


def test_v2_snapshot_keeps_the_current_key_set_and_rejects_production_rows() -> None:
    engine = _engine(_fixture())
    encoded = json.loads(encode_persistence(_snapshot(engine, codec="v2", schema=5)))
    assert set(encoded["data"]) == _V2_KEYS
    encoded["data"]["structures"] = []
    with pytest.raises(PersistenceSerializationError) as rejected:
        decode_persistence(json.dumps(encoded).encode(), WorldSnapshot)
    assert rejected.value.code == "unknown_field"


def test_v3_snapshot_round_trips_the_three_production_collections() -> None:
    catalog = example_production_catalog()
    engine = _engine(
        _fixture(
            items=(
                make_item(
                    "mat-1",
                    name="plank",
                    kind=ItemKind.MATERIAL,
                    location_id=None,
                    holder_id="body-1",
                ),
            ),
            bodies=(
                alive_body("body-1", inventory=(EntityId("mat-1"),)),
                alive_body("body-2"),
            ),
        ),
        catalog=catalog,
    )
    _act(engine, Build(RecipeId("build_shelter")))
    snapshot = _snapshot(engine, codec="v3", schema=EVENT_SCHEMA_REPLAY_V6)
    encoded = json.loads(encode_persistence(snapshot))
    assert set(encoded["data"]) == _V2_KEYS | {
        "structures",
        "production_jobs",
        "tool_marks",
    }
    assert encoded["data"]["event_schema_version"] == 6
    decoded = decode_persistence(encode_persistence(snapshot), WorldSnapshot)
    assert isinstance(decoded, WorldSnapshot)
    assert decoded.structures[0].kind is StructureKind.SHELTER
    assert decoded.structures[0].integrity == 0.75
    restored = WorldEngine.restore_from_snapshot(
        decoded,
        production_catalog=catalog,
    )
    assert restored._snapshot.world.state.structures[
        decoded.structures[0].entity_id
    ].integrity == 0.75


def test_v3_restore_without_a_catalog_fails_closed(
    caplog: pytest.LogCaptureFixture,
) -> None:
    engine = _engine(_fixture())
    state = engine._snapshot.world.state
    draft = _snapshot(engine, codec="v2", schema=5)
    snapshot = WorldSnapshot(
        snapshot_id=draft.snapshot_id,
        run_id=draft.run_id,
        world_id=draft.world_id,
        seed=draft.seed,
        config=draft.config,
        registrations=draft.registrations,
        locations=draft.locations,
        bodies=draft.bodies,
        items=draft.items,
        resources=draft.resources,
        weather=draft.weather,
        next_tick=draft.next_tick,
        revision=WorldRevision(state.revision.value),
        event_schema_version=EVENT_SCHEMA_REPLAY_V6,
        projector_version=PROJECTOR_VERSION,
        persistence_codec_version="v3",
        derivation_version=draft.derivation_version,
        integrity_hash=PayloadHash("b" * 64),
        predecessor_commit_hash=None,
        structures=(
            Structure(
                entity_id=EntityId("shelter-1"),
                location_id=EntityId("loc-1"),
                kind=StructureKind.SHELTER,
                integrity=0.75,
                stored_quantity=0,
            ),
        ),
        production_jobs=(),
        tool_marks=(
            ToolMark(item_id=EntityId("unused-tool"), role=ToolRole.STRIKE),
        ),
    )
    snapshot = WorldSnapshot(
        snapshot_id=snapshot.snapshot_id,
        run_id=snapshot.run_id,
        world_id=snapshot.world_id,
        seed=snapshot.seed,
        config=snapshot.config,
        registrations=snapshot.registrations,
        locations=snapshot.locations,
        bodies=snapshot.bodies,
        items=snapshot.items,
        resources=snapshot.resources,
        weather=snapshot.weather,
        next_tick=snapshot.next_tick,
        revision=snapshot.revision,
        event_schema_version=snapshot.event_schema_version,
        projector_version=snapshot.projector_version,
        persistence_codec_version=snapshot.persistence_codec_version,
        derivation_version=snapshot.derivation_version,
        integrity_hash=hash_snapshot(snapshot),
        predecessor_commit_hash=None,
        structures=snapshot.structures,
        production_jobs=snapshot.production_jobs,
        tool_marks=snapshot.tool_marks,
    )
    with caplog.at_level(logging.ERROR, logger="simulation.engine"):
        with pytest.raises(ValueError, match="production_catalog_mismatch"):
            WorldEngine.restore_from_snapshot(snapshot)
    assert production_catalog_digest(()) in caplog.text


def test_v5_search_fold_matches_the_live_world() -> None:
    fixture = _fixture()
    live = _engine(fixture, seed=4)
    start = live._snapshot.world.state
    _act(live, Search())
    folded = project_events(
        start,
        live._snapshot.event_history,
        expected_run_id=live.run_id.value,
        expected_world_id=live.world_id,
    )
    assert folded.revision == live._snapshot.world.state.revision
    assert project_world_state(folded) == project_world_state(
        live._snapshot.world.state
    )
    assert all(
        event.schema_version == EVENT_SCHEMA_REPLAY_V5
        for event in live._snapshot.event_history
    )


def _successful_harvest(catalog: ProductionCatalog) -> WorldEngine:
    fixture = _fixture(
        resources=(
            make_resource(
                "res-wood",
                name="wood",
                kind=ResourceKind.MATERIAL,
                location_id="loc-1",
                quantity=2.0,
                maximum_quantity=5.0,
                regeneration_per_tick=0.0,
            ),
        )
    )
    for seed in range(1, 40):
        candidate = _engine(fixture, seed=seed, catalog=catalog)
        _act(candidate, Harvest(RecipeId("harvest_wood"), EntityId("res-wood")))
        if any(
            item.name == "wood"
            for item in candidate._snapshot.world.state.items.values()
        ):
            return candidate
    raise AssertionError("harvest never succeeded")


def test_production_event_fold_matches_the_live_world(
    caplog: pytest.LogCaptureFixture,
) -> None:
    catalog = example_production_catalog()
    harvest = _successful_harvest(catalog)
    with caplog.at_level(logging.DEBUG, logger="simulation.replay"):
        folded = _fold(harvest, catalog)
    assert project_world_state(folded) == project_world_state(
        harvest._snapshot.world.state
    )
    assert "production_fold" in caplog.text
    with pytest.raises(ProjectionError) as mismatch:
        _fold(harvest, None)
    assert mismatch.value.code == "production_catalog_mismatch"

    shelter = _engine(
        _fixture(
            items=(
                make_item(
                    "mat-1",
                    name="plank",
                    kind=ItemKind.MATERIAL,
                    location_id=None,
                    holder_id="body-1",
                ),
                make_item(
                    "mat-2",
                    name="plank",
                    kind=ItemKind.MATERIAL,
                    location_id=None,
                    holder_id="body-1",
                ),
                make_item(
                    "food-1",
                    name="ration",
                    kind=ItemKind.FOOD,
                    location_id=None,
                    holder_id="body-1",
                ),
            ),
            bodies=(
                alive_body(
                    "body-1",
                    inventory=(
                        EntityId("mat-1"),
                        EntityId("mat-2"),
                        EntityId("food-1"),
                    ),
                ),
                alive_body("body-2"),
            ),
        ),
        catalog=catalog,
    )
    _act(shelter, Build(RecipeId("build_shelter")))
    structure_id = next(iter(shelter._snapshot.world.state.structures))
    batch = shelter.observe()
    shelter.resolve_tick(
        (
            ActionSubmission(
                batch.token,
                AgentId("agent-1"),
                Repair(RecipeId("repair_shelter"), structure_id),
            ),
        )
    )
    batch = shelter.observe()
    shelter.resolve_tick(
        (
            ActionSubmission(
                batch.token,
                AgentId("agent-1"),
                Store(RecipeId("store_food"), EntityId("food-1")),
            ),
        )
    )
    folded_shelter = _fold(shelter, catalog)
    assert project_world_state(folded_shelter) == project_world_state(
        shelter._snapshot.world.state
    )
    assert len(folded_shelter.structures) == 2
    store = next(
        value
        for value in folded_shelter.structures.values()
        if value.kind is StructureKind.STORE
    )
    assert store.stored_quantity == 1

    craft = _engine(
        _fixture(
            items=(
                make_item(
                    "item-wood",
                    name="wood",
                    kind=ItemKind.MATERIAL,
                    location_id=None,
                    holder_id="body-1",
                ),
                make_item(
                    "item-stone",
                    name="stone",
                    kind=ItemKind.MATERIAL,
                    location_id=None,
                    holder_id="body-1",
                ),
            ),
            bodies=(
                alive_body(
                    "body-1",
                    inventory=(EntityId("item-wood"), EntityId("item-stone")),
                ),
                alive_body("body-2"),
            ),
        ),
        catalog=catalog,
    )
    for seed in range(1, 40):
        candidate = _engine(
            _fixture(
                items=(
                    make_item(
                        "item-wood",
                        name="wood",
                        kind=ItemKind.MATERIAL,
                        location_id=None,
                        holder_id="body-1",
                    ),
                    make_item(
                        "item-stone",
                        name="stone",
                        kind=ItemKind.MATERIAL,
                        location_id=None,
                        holder_id="body-1",
                    ),
                ),
                bodies=(
                    alive_body(
                        "body-1",
                        inventory=(EntityId("item-wood"), EntityId("item-stone")),
                    ),
                    alive_body("body-2"),
                ),
            ),
            seed=seed,
            catalog=catalog,
        )
        _act(candidate, Craft(RecipeId("craft_tool")))
        if candidate._snapshot.world.state.production_jobs:
            craft = candidate
            break
    else:
        raise AssertionError("duration-2 craft never started")
    snapshot = _snapshot(craft, codec="v3", schema=EVENT_SCHEMA_REPLAY_V6)
    decoded = decode_persistence(encode_persistence(snapshot), WorldSnapshot)
    assert isinstance(decoded, WorldSnapshot)
    live_job = next(iter(craft._snapshot.world.state.production_jobs.values()))
    assert decoded.production_jobs[0].created_item_id == live_job.created_item_id
    restored = WorldEngine.restore_from_snapshot(decoded, production_catalog=catalog)
    restored_job = next(iter(restored._snapshot.world.state.production_jobs.values()))
    assert restored_job.created_item_id == live_job.created_item_id
    _act(craft, Move(EntityId("loc-2")))
    later = tuple(
        event
        for event in craft._snapshot.event_history
        if event.tick >= snapshot.next_tick.value
    )
    resumed = WorldEngine.restore_from_snapshot(
        decoded,
        events=later,
        committed_through_tick=Tick(later[-1].tick),
        production_catalog=catalog,
    )
    assert project_world_state(resumed._snapshot.world.state) == project_world_state(
        craft._snapshot.world.state
    )
