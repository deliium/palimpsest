"""Historical population metadata folds from an earlier checkpoint."""

from __future__ import annotations

import hashlib
import logging
from dataclasses import replace

import pytest

from agents.models import AgentId
from api.errors import ApiError
from api.observer_replay_context import (
    ObserverReplayContextError,
    PersistenceObserverReplayContextSource,
)
from api.observer_service import ObserverReadService
from experiments.catalog import base_runner_config_from_scenario
from simulation.clock import Tick
from simulation.journal import (
    compute_commit_hash,
    hash_snapshot,
    hash_tick_events,
    hash_tick_payload,
)
from simulation.models import RunId
from simulation.new_agent_initialization import default_new_agent_initialization_spec
from simulation.observer_facts import scene_from_facts
from simulation.persistence import (
    PROJECTOR_VERSION,
    CommitHash,
    PayloadHash,
    ReplayRequest,
    ReplayStatus,
    RunManifest,
    SnapshotId,
    TickAppendRequest,
    TickCommit,
    WorldSnapshot,
)
from simulation.population_replay import (
    PopulationMetadataError,
    fold_population_metadata,
)
from simulation.replay import (
    ObserverReplayContext,
    ReplayService,
    scene_at_tick,
    scene_through_event,
)
from simulation.run_control import (
    ConfigAvailability,
    RunControlRecord,
    RunLifecycleState,
)
from simulation.runner import SimulationRunner
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V26,
    AgentCognitionSpec,
    AgentRunnerSpec,
    MortalityMode,
    RunnerStopPolicy,
    V3CapabilityFlags,
    WorldScenarioSpec,
    example_population_lifecycle_spec,
)
from simulation.runner_serialization import encode_runner_config
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.events import (
    EVENT_SCHEMA_REPLAY_V10,
    AgentCreated,
    AgentEnteredWorld,
    AgentInitializationRecorded,
    Died,
    LifecycleStageChanged,
)
from world.identifiers import WorldId, WorldRevision
from world.models import non_lethal_physical_rules

pytestmark = pytest.mark.unit

RUN_ID = "run-observer-generations"
WORLD_ID = "world-observer-generations"
TICKS = 22


def _config(*, max_ticks: int = TICKS):
    body = alive_body("body-1")
    agent_id = AgentId("agent-1")
    return replace(
        base_runner_config_from_scenario(
            seed=23,
            stochastic_identity="cmp-observer-generations-23",
            scenario=WorldScenarioSpec(
                world_id=WorldId(WORLD_ID),
                revision=WorldRevision(0),
                physical_rules=non_lethal_physical_rules(),
                locations=(make_location(body_capacity=8),),
                bodies=(body,),
                weather=(make_weather(),),
            ),
            agents=(
                AgentRunnerSpec(
                    agent_id=agent_id,
                    entity_id=body.entity_id,
                    cognition=AgentCognitionSpec(agent_id=agent_id),
                ),
            ),
            max_ticks=max_ticks,
        ),
        schema_version=RUNNER_SCHEMA_VERSION_V26,
        mortality_mode=MortalityMode.DISABLED,
        stop_policy=RunnerStopPolicy(max_ticks=max_ticks),
        v3_capability_flags=V3CapabilityFlags(generational_population=True),
        population_lifecycle=example_population_lifecycle_spec(
            lifespan_ticks=20,
            max_population=8,
            policy_id="fixed_interval_entry",
        ),
        new_agent_initialization=default_new_agent_initialization_spec(),
    )


def _snapshot_from_engine(engine: object) -> WorldSnapshot:
    state = engine._snapshot.world.state  # type: ignore[attr-defined]
    draft = WorldSnapshot(
        snapshot_id=SnapshotId("snap-generations"),
        run_id=RunId(RUN_ID),
        world_id=WorldId(WORLD_ID),
        seed=engine._config.seed,  # type: ignore[attr-defined]
        config=engine._config,  # type: ignore[attr-defined]
        registrations=engine.ordered_registrations,  # type: ignore[attr-defined]
        locations=tuple(state.locations.values()),
        bodies=tuple(state.bodies.values()),
        items=tuple(state.items.values()),
        resources=tuple(state.resources.values()),
        weather=tuple(state.weather.values()),
        next_tick=engine._snapshot.tick,  # type: ignore[attr-defined]
        revision=engine.revision,  # type: ignore[attr-defined]
        event_schema_version=EVENT_SCHEMA_REPLAY_V10,
        projector_version=PROJECTOR_VERSION,
        persistence_codec_version="v7",
        derivation_version=engine._config.derivation_version,  # type: ignore[attr-defined]
        integrity_hash=PayloadHash("a" * 64),
        predecessor_commit_hash=None,
        lifecycle_records=engine.lifecycle_records,  # type: ignore[attr-defined]
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
        lifecycle_records=draft.lifecycle_records,
    )


class _Runs:
    def __init__(self, snapshot: WorldSnapshot) -> None:
        self._config = snapshot.config
        self._manifest = RunManifest(
            run_id=snapshot.run_id,
            world_id=snapshot.world_id,
            seed=snapshot.seed,
            config=snapshot.config,
            derivation_version=snapshot.derivation_version,
            event_schema_version=snapshot.event_schema_version,
            projector_version=snapshot.projector_version,
            persistence_codec_version=snapshot.persistence_codec_version,
        )

    async def get_run(self, run_id: RunId) -> RunManifest | None:
        return self._manifest if run_id == self._manifest.run_id else None

    async def create_run(self, request: object) -> RunManifest:
        raise NotImplementedError


class _Snapshots:
    def __init__(self, snapshot: WorldSnapshot) -> None:
        self._snapshot = snapshot

    async def get_latest_at_or_before(
        self, run_id: RunId, tick: Tick
    ) -> WorldSnapshot | None:
        if run_id != self._snapshot.run_id:
            return None
        return self._snapshot if self._snapshot.next_tick.value <= tick.value else None

    async def get_snapshot(self, snapshot_id: SnapshotId) -> WorldSnapshot | None:
        return self._snapshot if snapshot_id == self._snapshot.snapshot_id else None


class _Journal:
    def __init__(
        self, events: tuple[object, ...], commits: tuple[TickCommit, ...]
    ) -> None:
        self._events = events
        self._commits = commits

    async def append_tick(self, request: TickAppendRequest) -> TickCommit:
        raise NotImplementedError

    async def get_tick_commit(
        self, run_id: RunId, tick: Tick
    ) -> TickCommit | None:
        return next(
            (
                item
                for item in self._commits
                if item.run_id == run_id and item.tick == tick
            ),
            None,
        )

    async def list_events(
        self,
        run_id: RunId,
        *,
        from_tick: Tick,
        to_tick: Tick | None,
        limit: int,
        offset: int,
    ) -> tuple[object, ...]:
        selected = [
            event
            for event in self._events
            if event.run_id == run_id.value
            and event.tick >= from_tick.value
            and (to_tick is None or event.tick <= to_tick.value)
        ]
        return tuple(selected[offset : offset + limit])

    async def list_tick_commits(
        self,
        run_id: RunId,
        *,
        from_tick: Tick,
        to_tick: Tick | None,
    ) -> tuple[TickCommit, ...]:
        selected = [
            item
            for item in self._commits
            if item.run_id == run_id
            and item.tick.value >= from_tick.value
            and (to_tick is None or item.tick.value <= to_tick.value)
        ]
        return tuple(selected)


def _commits_for(events: tuple[object, ...]) -> tuple[TickCommit, ...]:
    by_tick: dict[int, list[object]] = {}
    for event in events:
        by_tick.setdefault(event.tick, []).append(event)
    if not by_tick:
        return ()
    commits: list[TickCommit] = []
    predecessor: CommitHash | None = None
    revision = 0
    for tick in range(max(by_tick) + 1):
        tick_events = tuple(
            sorted(by_tick.get(tick, ()), key=lambda item: item.sequence)
        )
        if tick_events:
            resulting = max(event.resulting_revision.value for event in tick_events)
        else:
            resulting = revision
        request = TickAppendRequest(
            run_id=RunId(RUN_ID),
            tick=Tick(tick),
            expected_base_revision=WorldRevision(revision),
            expected_predecessor_commit_hash=predecessor,
            idempotency_key=f"idem-observer-{tick}",
            events=tick_events,
        )
        payload = hash_tick_payload(request.events)
        commit_hash = compute_commit_hash(
            predecessor_commit_hash=predecessor,
            run_id=request.run_id,
            tick=request.tick,
            base_revision=request.expected_base_revision,
            resulting_revision=WorldRevision(resulting),
            event_hashes=hash_tick_events(request.events),
            payload_hash=payload,
        )
        commits.append(
            TickCommit(
                run_id=request.run_id,
                tick=request.tick,
                resulting_tick=Tick(tick + 1),
                base_revision=request.expected_base_revision,
                resulting_revision=WorldRevision(resulting),
                predecessor_commit_hash=predecessor,
                commit_hash=commit_hash,
                idempotency_key=request.idempotency_key,
                event_count=len(request.events),
                payload_hash=payload,
                snapshot_id=None,
            )
        )
        predecessor = commit_hash
        revision = resulting
    return tuple(commits)


async def _run_scenario(
    *, ticks: int = TICKS
) -> tuple[WorldSnapshot, tuple[object, ...], object, object]:
    config = _config(max_ticks=ticks)
    async with await SimulationRunner.from_config(
        config, run_id=RunId(RUN_ID)
    ) as runner:
        snapshot = _snapshot_from_engine(runner.engine)
        for _ in range(ticks):
            await runner.run_tick()
        events = tuple(runner.engine._snapshot.event_history)
        live_facts = runner.engine.detached_objective_facts()
        live_scene = scene_from_facts(live_facts)
    return snapshot, events, config, live_scene


def _service(snapshot: WorldSnapshot, events: tuple[object, ...]) -> ReplayService:
    return ReplayService(
        _Runs(snapshot),
        _Journal(events, _commits_for(events)),
        _Snapshots(snapshot),
    )


def _context(config: object) -> ObserverReplayContext:
    return ObserverReplayContext(
        population_lifecycle=config.population_lifecycle,  # type: ignore[attr-defined]
        new_agent_initialization=config.new_agent_initialization,  # type: ignore[attr-defined]
    )


@pytest.mark.asyncio
async def test_scene_at_tick_rebuilds_registrations_lifecycle_and_death(
    caplog: pytest.LogCaptureFixture,
) -> None:
    snapshot, events, config, live_scene = await _run_scenario()
    service = _service(snapshot, events)
    with caplog.at_level(logging.DEBUG, logger="simulation.engine"):
        history = await scene_at_tick(
            service,
            RunId(RUN_ID),
            target_tick=Tick(TICKS),
            context=_context(config),
        )
    assert history.result.status is ReplayStatus.OK
    assert history.scene.tick == TICKS
    assert history.scene.registrations == live_scene.registrations
    assert history.scene.lifecycle_records == live_scene.lifecycle_records
    assert {
        body.entity_id.value for body in history.scene.bodies
    } == {body.entity_id.value for body in live_scene.bodies}
    assert any(type(event.details) is Died for event in events)
    dead = [
        record
        for record in history.scene.lifecycle_records or ()
        if record.agent_id == "agent-1"
    ]
    assert dead and dead[0].stage is not None
    assert "population_metadata_restore" in caplog.text


@pytest.mark.asyncio
async def test_scene_through_event_withholds_unentered_agents(
    caplog: pytest.LogCaptureFixture,
) -> None:
    snapshot, events, config, _live = await _run_scenario(ticks=6)
    service = _service(snapshot, events)
    context = _context(config)
    created = next(
        event
        for event in events
        if type(event.details) is AgentCreated
        and event.details.agent_id != "agent-1"
    )
    tick = created.tick
    recorded = next(
        event
        for event in events
        if event.tick == tick
        and type(event.details) is AgentInitializationRecorded
        and event.details.body_id == created.details.body_id
    )
    entered = next(
        event
        for event in events
        if event.tick == tick
        and type(event.details) is AgentEnteredWorld
        and event.details.body_id == created.details.body_id
    )
    created_history = await scene_through_event(
        service,
        RunId(RUN_ID),
        tick=Tick(tick),
        through_sequence=created.sequence,
        context=context,
    )
    assert created.details.agent_id not in {
        registration.agent_id.value
        for registration in created_history.scene.registrations
    }
    recorded_history = await scene_through_event(
        service,
        RunId(RUN_ID),
        tick=Tick(tick),
        through_sequence=recorded.sequence,
        context=context,
    )
    assert recorded.details.agent_id not in {
        registration.agent_id.value
        for registration in recorded_history.scene.registrations
    }
    entered_history = await scene_through_event(
        service,
        RunId(RUN_ID),
        tick=Tick(tick),
        through_sequence=entered.sequence,
        context=context,
    )
    assert entered.details.agent_id in {
        registration.agent_id.value
        for registration in entered_history.scene.registrations
    }
    assert entered.details.body_id.value in {
        body.entity_id.value for body in entered_history.scene.bodies
    }
    assert any(
        record.agent_id == entered.details.agent_id
        for record in entered_history.scene.lifecycle_records or ()
    )
    last_sequence = max(
        event.sequence for event in events if event.tick == tick
    )
    full = await scene_through_event(
        service,
        RunId(RUN_ID),
        tick=Tick(tick),
        through_sequence=last_sequence,
        context=context,
    )
    next_tick = await scene_at_tick(
        service,
        RunId(RUN_ID),
        target_tick=Tick(tick + 1),
        context=context,
    )
    assert full.scene.registrations == next_tick.scene.registrations
    assert full.scene.lifecycle_records == next_tick.scene.lifecycle_records


@pytest.mark.asyncio
async def test_stage_change_prefix_keeps_the_last_recorded_stage() -> None:
    snapshot, events, config, _live = await _run_scenario(ticks=8)
    service = _service(snapshot, events)
    context = _context(config)
    changed = next(
        event
        for event in events
        if type(event.details) is LifecycleStageChanged
        and event.details.body_id.value == "body-1"
    )
    tick = changed.tick
    before = await scene_at_tick(
        service, RunId(RUN_ID), target_tick=Tick(tick), context=context
    )
    after = await scene_through_event(
        service,
        RunId(RUN_ID),
        tick=Tick(tick),
        through_sequence=changed.sequence,
        context=context,
    )
    before_record = next(
        record
        for record in before.scene.lifecycle_records or ()
        if record.agent_id == "agent-1"
    )
    after_record = next(
        record
        for record in after.scene.lifecycle_records or ()
        if record.agent_id == "agent-1"
    )
    assert before_record.stage.value == changed.details.previous_stage
    assert after_record.stage.value == changed.details.new_stage


def _first_admission(events: tuple[object, ...]) -> tuple[object, object, object]:
    created = next(
        event
        for event in events
        if type(event.details) is AgentCreated
        and event.details.agent_id != "agent-1"
    )
    recorded = next(
        event
        for event in events
        if event.tick == created.tick
        and type(event.details) is AgentInitializationRecorded
        and event.details.body_id == created.details.body_id
    )
    entered = next(
        event
        for event in events
        if event.tick == created.tick
        and type(event.details) is AgentEnteredWorld
        and event.details.body_id == created.details.body_id
    )
    return created, recorded, entered


def test_fold_reserves_identity_until_entered_world() -> None:
    import asyncio

    snapshot, events, config, _live = asyncio.run(_run_scenario(ticks=6))
    created, recorded, entered = _first_admission(events)
    reserved = fold_population_metadata(
        registrations=snapshot.registrations,
        lifecycle_records=snapshot.lifecycle_records,
        events=(created, recorded),
        population_lifecycle=config.population_lifecycle,
        run_config=snapshot.config,
        run_id=RUN_ID,
        world_id=WORLD_ID,
    )
    assert len(reserved.pending_reservations) == 1
    assert reserved.pending_reservations[0].initialization_recorded is True
    assert reserved.registrations == snapshot.registrations
    assert recorded.details.agent_id not in {
        item.agent_id.value for item in reserved.registrations
    }
    folded = fold_population_metadata(
        registrations=snapshot.registrations,
        lifecycle_records=snapshot.lifecycle_records,
        events=(created, recorded, entered),
        population_lifecycle=config.population_lifecycle,
        run_config=snapshot.config,
        run_id=RUN_ID,
        world_id=WORLD_ID,
    )
    assert not folded.pending_reservations
    assert any(
        item.agent_id.value == entered.details.agent_id
        for item in folded.registrations
    )
    assert any(
        record.agent_id == entered.details.agent_id
        for record in folded.lifecycle_records
    )


def test_fold_rejects_missing_and_duplicate_witnesses() -> None:
    import asyncio

    snapshot, events, config, _live = asyncio.run(_run_scenario(ticks=6))
    created, recorded, entered = _first_admission(events)
    with pytest.raises(PopulationMetadataError) as orphan:
        fold_population_metadata(
            registrations=snapshot.registrations,
            lifecycle_records=snapshot.lifecycle_records,
            events=(recorded,),
            population_lifecycle=config.population_lifecycle,
            run_config=snapshot.config,
            run_id=RUN_ID,
            world_id=WORLD_ID,
        )
    assert orphan.value.reason_code == "population_metadata_orphan_initialization"
    with pytest.raises(PopulationMetadataError) as missing:
        fold_population_metadata(
            registrations=snapshot.registrations,
            lifecycle_records=snapshot.lifecycle_records,
            events=(entered,),
            population_lifecycle=config.population_lifecycle,
            run_config=snapshot.config,
            run_id=RUN_ID,
            world_id=WORLD_ID,
        )
    assert missing.value.reason_code == "population_metadata_missing_created"
    folded = fold_population_metadata(
        registrations=snapshot.registrations,
        lifecycle_records=snapshot.lifecycle_records,
        events=(created, recorded, entered),
        population_lifecycle=config.population_lifecycle,
        run_config=snapshot.config,
        run_id=RUN_ID,
        world_id=WORLD_ID,
    )
    assert any(
        item.agent_id.value == entered.details.agent_id
        for item in folded.registrations
    )
    with pytest.raises(PopulationMetadataError) as repeated:
        fold_population_metadata(
            registrations=folded.registrations,
            lifecycle_records=folded.lifecycle_records,
            events=(created, recorded, entered),
            population_lifecycle=config.population_lifecycle,
            run_config=snapshot.config,
            run_id=RUN_ID,
            world_id=WORLD_ID,
        )
    assert repeated.value.reason_code == "population_metadata_duplicate_created"


def test_fold_rejects_channel_off_and_wrong_event_order() -> None:
    import asyncio

    snapshot, events, _config_value, _live = asyncio.run(_run_scenario(ticks=6))
    created, _recorded, _entered = _first_admission(events)
    with pytest.raises(PopulationMetadataError) as off:
        fold_population_metadata(
            registrations=snapshot.registrations,
            lifecycle_records=(),
            events=(created,),
            population_lifecycle=None,
            run_config=snapshot.config,
            run_id=RUN_ID,
            world_id=WORLD_ID,
        )
    assert off.value.reason_code == "lifecycle_channel_off"
    config = _config()
    with pytest.raises(PopulationMetadataError) as order:
        fold_population_metadata(
            registrations=snapshot.registrations,
            lifecycle_records=(),
            events=(created, created),
            population_lifecycle=config.population_lifecycle,
            run_config=snapshot.config,
            run_id=RUN_ID,
            world_id=WORLD_ID,
        )
    assert order.value.reason_code == "population_metadata_event_order"


class _ContextSource:
    def __init__(self, value: object | None) -> None:
        self._value = value

    async def read_context(self, run_id: str) -> object | None:
        return self._value


@pytest.mark.asyncio
async def test_observer_service_maps_missing_context_to_503() -> None:
    snapshot, events, _config_value, _live = await _run_scenario(ticks=6)
    service = _service(snapshot, events)
    reader = ObserverReadService(service, replay_context=_ContextSource(None))
    with pytest.raises(ApiError) as unavailable:
        await reader.state(RUN_ID, tick=6, layout_id="reference-v1")
    assert unavailable.value.status == 503
    assert unavailable.value.code == "observer_replay_context_unavailable"


@pytest.mark.asyncio
async def test_persistence_context_source_validates_fingerprint_and_schema() -> None:
    config = _config(max_ticks=1)
    payload = encode_runner_config(config)
    fingerprint = hashlib.sha256(payload).hexdigest()

    class _RunControl:
        def __init__(self, record: RunControlRecord | None) -> None:
            self._record = record

        async def get(self, run_id: RunId) -> RunControlRecord | None:
            return self._record

    def _record(**overrides: object) -> RunControlRecord:
        values: dict[str, object] = {
            "run_id": RunId(RUN_ID),
            "lifecycle_state": RunLifecycleState.RUNNING,
            "lifecycle_version": 1,
            "config_availability": ConfigAvailability.AVAILABLE,
            "ticks_committed": 0,
            "progress_cursor": 0,
            "config_schema_version": config.schema_version,
            "config_fingerprint": fingerprint,
            "config_payload": payload,
        }
        values.update(overrides)
        return RunControlRecord(**values)  # type: ignore[arg-type]

    missing = PersistenceObserverReplayContextSource(_RunControl(None))
    assert await missing.read_context(RUN_ID) is None
    source = PersistenceObserverReplayContextSource(_RunControl(_record()))
    context = await source.read_context(RUN_ID)
    assert context is not None
    assert context.population_lifecycle == config.population_lifecycle
    assert context.new_agent_initialization == config.new_agent_initialization
    tampered = PersistenceObserverReplayContextSource(
        _RunControl(_record(config_fingerprint="0" * 64))
    )
    with pytest.raises(ObserverReplayContextError) as invalid:
        await tampered.read_context(RUN_ID)
    assert invalid.value.reason_code == "observer_replay_context_invalid"
    wrong_schema = PersistenceObserverReplayContextSource(
        _RunControl(_record(config_schema_version="runner-config-v4"))
    )
    with pytest.raises(ObserverReplayContextError):
        await wrong_schema.read_context(RUN_ID)


def test_replay_request_carries_the_trusted_context() -> None:
    config = _config(max_ticks=1)
    context = _context(config)
    from simulation.replay import _replay_request

    request: ReplayRequest = _replay_request(
        RunId(RUN_ID), target_tick=Tick(1), context=context
    )
    assert request.new_agent_initialization is config.new_agent_initialization
    assert request.kinship_spec is None
    assert request.population_lifecycle is config.population_lifecycle


def test_app_attaches_the_persistence_replay_context_source() -> None:
    from fastapi import FastAPI

    from api.app import _attach_persistence_services
    from api.observer_service import ObserverReadService

    app = FastAPI()
    _attach_persistence_services(app, object())
    reader = app.state.observer_service
    assert isinstance(reader, ObserverReadService)
    assert isinstance(
        reader._replay_context,
        PersistenceObserverReplayContextSource,
    )
