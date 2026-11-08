# mypy: ignore-errors
"""Owner-scoped migration-displacement carry through cognition and runtime."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from agents.cognition.configuration import (
    CognitionMigrationDisplacementMode,
    build_cognitive_loop,
    production_cognition_config,
)
from agents.cognition.contracts import Perspective
from agents.cognition.fork_state import (
    CognitiveLoopForkState,
    CognitiveLoopForkStateError,
)
from agents.cognition.migration_displacement import (
    MigrationDisplacementLedger,
    empty_migration_displacement_ledger,
    require_owner_migration_displacement,
)
from agents.cognition.models import (
    CognitiveLoopProposal,
    CognitiveLoopResult,
    SubjectiveSnapshot,
)
from agents.models import Agent, AgentId
from memory.models import BeliefStore, MemoryStore
from simulation.agent_runtime import AgentRuntime
from simulation.bootstrap import registration_translator
from simulation.clock import Tick
from simulation.lifecycle import TickToken
from simulation.models import RunId
from simulation.run_control import AgentRuntimeCheckpoint
from simulation.runner_models import RunnerStopReasonCode, SimulationRunnerResult
from tests.unit.migration_displacement_helpers import (
    cause,
    intent,
    ledger,
    route,
)
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import AgentBody, LifeStatus
from world.observations import Observation, ObservedSelf
from world.values import (
    CarryCapacity,
    Fatigue,
    Health,
    Hunger,
    TemperatureCelsius,
    Thirst,
)

pytestmark = pytest.mark.unit

OWNER = AgentId("agent-1")
OTHER = AgentId("agent-2")
OWNER_ENTITY = EntityId("body-1")
SRC = Path(__file__).resolve().parents[2] / "src"


def _observation(tick: int = 0) -> Observation:
    body = AgentBody(
        entity_id=OWNER_ENTITY,
        location_id=EntityId("loc-1"),
        health=Health(100),
        hunger=Hunger(0),
        thirst=Thirst(0),
        fatigue=Fatigue(0),
        temperature=TemperatureCelsius(36.5),
        inventory=(),
        life_status=LifeStatus.ALIVE,
        carry_capacity=CarryCapacity(10),
    )
    return Observation(
        world_id=WorldId("world-carry"),
        observer_id=OWNER_ENTITY,
        revision=WorldRevision(0),
        tick=tick,
        self_body=ObservedSelf(
            entity_id=body.entity_id,
            location_id=body.location_id,
            health=body.health,
            hunger=body.hunger,
            thirst=body.thirst,
            fatigue=body.fatigue,
            temperature=body.temperature,
            inventory=body.inventory,
            life_status=body.life_status,
            carry_capacity=body.carry_capacity,
        ),
    )


def _bootstrap():
    from tests.unit.test_agent_runtime import _bootstrap as helper

    return helper()


def _loop(*, migration: bool):
    config = production_cognition_config()
    if migration:
        config = dataclasses.replace(
            config,
            migration_displacement_mode=CognitionMigrationDisplacementMode.DETERMINISTIC,
        )
    return build_cognitive_loop(config)


def _runtime(*, migration: bool) -> AgentRuntime:
    bootstrap = _bootstrap()
    memories = MemoryStore(OWNER)
    beliefs = BeliefStore(OWNER)
    return AgentRuntime(
        agent=Agent(agent_id=OWNER, name="agent-1", goals=()),
        translator=registration_translator(bootstrap),
        cognitive_loop=_loop(migration=migration),
        memory_reader=memories,
        memory_writer=memories,
        belief_reader=beliefs,
        belief_writer=beliefs,
    )


def _token(tick: int = 0) -> TickToken:
    return TickToken(value=f"tok-{tick}", tick=Tick(tick))


def _own_ledger() -> MigrationDisplacementLedger:
    cause_row = cause(tick=1)
    return ledger(
        intents=(intent(causes=(cause_row,)),),
        routes=(route(),),
        causes=(cause_row,),
    )


def _result(**kwargs) -> SimulationRunnerResult:
    return SimulationRunnerResult(
        run_id=RunId("run-migration-export"),
        ticks_committed=1,
        stop_reason=RunnerStopReasonCode.MAX_TICKS,
        attempt_receipts=(),
        **kwargs,
    )


@pytest.mark.asyncio
async def test_disabled_mode_carries_none() -> None:
    runtime = _runtime(migration=False)
    runtime.start()
    result = await runtime.process_observation(_observation(), token=_token())
    assert result.loop_result is not None
    assert result.loop_result.migration_displacement is None
    assert runtime.export_runtime_checkpoint().migration_displacement is None


@pytest.mark.asyncio
async def test_enabled_mode_carries_an_empty_ledger() -> None:
    runtime = _runtime(migration=True)
    runtime.start()
    result = await runtime.process_observation(_observation(), token=_token())
    assert result.loop_result is not None
    carried = result.loop_result.migration_displacement
    assert type(carried) is MigrationDisplacementLedger
    assert carried.owner_id == OWNER
    assert carried.intents == ()
    assert carried.routes == ()
    assert carried.causes == ()
    assert runtime.export_runtime_checkpoint().migration_displacement == carried


def test_perspective_rejects_a_foreign_ledger() -> None:
    foreign = empty_migration_displacement_ledger(OTHER)
    with pytest.raises(ValueError, match="foreign_owner"):
        Perspective(
            agent_id=OWNER,
            observation=_observation(),
            memories=(),
            beliefs=(),
            inbox=(),
            migration_displacement=foreign,
        )
    with pytest.raises(TypeError):
        Perspective(
            agent_id=OWNER,
            observation=_observation(),
            memories=(),
            beliefs=(),
            inbox=(),
            migration_displacement=object(),
        )
    own = _own_ledger()
    perspective = Perspective(
        agent_id=OWNER,
        observation=_observation(),
        memories=(),
        beliefs=(),
        inbox=(),
        migration_displacement=own,
    )
    assert perspective.migration_displacement == own
    assert perspective.to_snapshot().migration_displacement == own
    none_perspective = Perspective(
        agent_id=OWNER,
        observation=_observation(),
        memories=(),
        beliefs=(),
        inbox=(),
    )
    assert none_perspective.to_snapshot().migration_displacement is None


def test_snapshot_proposal_and_result_require_owner_identity() -> None:
    for model in (SubjectiveSnapshot, CognitiveLoopProposal, CognitiveLoopResult):
        fields = {item.name for item in dataclasses.fields(model)}
        assert "migration_displacement" in fields
    own = empty_migration_displacement_ledger(OWNER)
    foreign = empty_migration_displacement_ledger(OTHER)
    require_owner_migration_displacement(own, OWNER, field_name="x")
    require_owner_migration_displacement(None, OWNER, field_name="x")
    with pytest.raises(ValueError, match="foreign_owner"):
        require_owner_migration_displacement(foreign, OWNER, field_name="x")
    with pytest.raises(TypeError):
        require_owner_migration_displacement(object(), OWNER, field_name="x")
    snapshot = SubjectiveSnapshot(
        owner_id=OWNER,
        revision=0,
        memories=(),
        legacy_beliefs=(),
        semantic_beliefs=(),
        migration_displacement=own,
    )
    assert snapshot.migration_displacement == own
    with pytest.raises(ValueError, match="foreign_owner"):
        dataclasses.replace(snapshot, migration_displacement=foreign)
    with pytest.raises(TypeError):
        dataclasses.replace(snapshot, migration_displacement=object())


@pytest.mark.asyncio
async def test_result_rejects_a_foreign_ledger() -> None:
    runtime = _runtime(migration=True)
    runtime.start()
    outcome = await runtime.process_observation(_observation(), token=_token())
    loop_result = outcome.loop_result
    assert loop_result is not None
    foreign = empty_migration_displacement_ledger(OTHER)
    with pytest.raises(ValueError, match="foreign_owner"):
        dataclasses.replace(loop_result, migration_displacement=foreign)


@pytest.mark.asyncio
async def test_checkpoint_restore_and_export_round_trip() -> None:
    runtime = _runtime(migration=True)
    runtime.start()
    await runtime.process_observation(_observation(), token=_token())
    checkpoint = runtime.export_runtime_checkpoint()
    assert type(checkpoint) is AgentRuntimeCheckpoint
    assert type(checkpoint.migration_displacement) is MigrationDisplacementLedger
    restored = _runtime(migration=True)
    restored.restore_runtime_checkpoint(checkpoint)
    reexported = restored.export_runtime_checkpoint()
    assert reexported.migration_displacement == checkpoint.migration_displacement
    # A foreign ledger is rejected at the checkpoint boundary.
    foreign = empty_migration_displacement_ledger(OTHER)
    with pytest.raises(ValueError, match="foreign_owner"):
        dataclasses.replace(checkpoint, migration_displacement=foreign)
    # So is a ledger above the exact caps.
    over = ledger(
        causes=tuple(cause(tick=index) for index in range(1, 40)),
    )
    with pytest.raises(ValueError, match="capacity_reached"):
        dataclasses.replace(checkpoint, migration_displacement=over)


def test_fork_state_carries_prepared_migration_displacement() -> None:
    fields = {item.name for item in dataclasses.fields(CognitiveLoopForkState)}
    assert "prepared_migration_displacement" in fields
    assert "prepared_migration_displacement_biases" in fields
    loop = _loop(migration=True)
    prepared = _own_ledger()
    loop._prepared_migration_displacement = prepared
    loop._prepared_migration_displacement_biases = {"loc-b": 0.1, "loc-a": 0.05}
    state = loop.export_fork_state()
    assert state.prepared_migration_displacement == prepared
    assert state.prepared_migration_displacement_biases == (
        ("loc-a", 0.05),
        ("loc-b", 0.1),
    )
    other = _loop(migration=True)
    other.restore_fork_state(state)
    assert other._prepared_migration_displacement == prepared
    assert other._prepared_migration_displacement_biases == {
        "loc-a": 0.05,
        "loc-b": 0.1,
    }
    with pytest.raises(CognitiveLoopForkStateError):
        dataclasses.replace(state, prepared_migration_displacement=object())
    with pytest.raises(CognitiveLoopForkStateError):
        dataclasses.replace(
            state, prepared_migration_displacement_biases=(("loc-a", float("nan")),)
        )
    with pytest.raises(CognitiveLoopForkStateError):
        dataclasses.replace(
            state,
            prepared_migration_displacement_biases=(("loc-a", 0.1), ("loc-a", 0.2)),
        )


def test_runner_result_exports_owner_ordered_ledgers() -> None:
    fields = {item.name for item in dataclasses.fields(SimulationRunnerResult)}
    assert "migration_displacement_ledgers" in fields
    assert _result().migration_displacement_ledgers == ()
    first = empty_migration_displacement_ledger(AgentId("agent-a"))
    second = empty_migration_displacement_ledger(AgentId("agent-b"))
    result = _result(migration_displacement_ledgers=(first, second))
    assert result.migration_displacement_ledgers == (first, second)
    with pytest.raises(ValueError, match="invalid_order"):
        _result(migration_displacement_ledgers=(second, first))
    with pytest.raises(ValueError, match="invalid_order"):
        _result(migration_displacement_ledgers=(first, first))
    with pytest.raises(TypeError):
        _result(migration_displacement_ledgers=(object(),))
    with pytest.raises(TypeError):
        _result(migration_displacement_ledgers=frozenset({first}))
    with pytest.raises(TypeError):
        _result(migration_displacement_ledgers=[first])


def test_world_and_observer_do_not_receive_migration_fields() -> None:
    from simulation import perception
    from world import observations

    assert "migration_displacement" in {
        item.name for item in dataclasses.fields(Perspective)
    }
    assert "migration_displacement" in perception.build_perspective.__code__.co_varnames
    for model in (
        observations.Observation,
        observations.ObservedSelf,
    ):
        assert not any(
            "migration_displacement" in item.name for item in dataclasses.fields(model)
        )
    for package in ("world", "observer"):
        for path in (SRC / package).rglob("*.py"):
            assert "migration_displacement" not in path.read_text(encoding="utf-8"), (
                path
            )
    # The wire subject never leaks into the objective event or observer layers.
    for package in ("world", "observer"):
        for path in (SRC / package).rglob("*.py"):
            assert "mdp_v1" not in path.read_text(encoding="utf-8"), path
