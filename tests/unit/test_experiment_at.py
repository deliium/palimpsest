"""Off-gate Experiment AT. Speech does not collect a debt."""

from __future__ import annotations

import asyncio
import hashlib
import logging
from pathlib import Path

from agents.cognition.memory import build_direct_observation_memory_trace
from agents.cognition.structured_commitments import (
    apply_structured_commitment_update,
    empty_structured_commitments,
    forget_structured_commitments,
    link_structured_commitment_traces,
)
from agents.models import AgentId
from analysis.structured_commitments import classify_commitment_speech
from experiments import (
    OFF_GATE_MATRIX_EXPERIMENT_IDS,
    experiment_at_structured_commitments,
)
from experiments.catalog import base_runner_config_from_scenario
from experiments.matrix_schema import finalize_matrix_cell_config
from memory.models import MemoryMutationBatch, MemoryRunId, MemoryScope
from memory.service import InMemoryMemoryService
from simulation.bootstrap import AgentRegistration, WorldBootstrap
from simulation.engine import WorldEngine
from simulation.lifecycle import ActionResolutionStatus, ActionSubmission
from simulation.models import SimulationRunConfig
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V4,
    RUNNER_SCHEMA_VERSION_V38,
    RUNNER_SCHEMA_VERSION_V39,
    AgentCognitionSpec,
    AgentRunnerSpec,
    V3CapabilityFlags,
    WorldScenarioSpec,
    example_possession_succession_spec,
    example_structured_commitments_spec,
)
from tests.simulation_helpers import alive_body, make_item, make_location, make_weather
from world.actions import Attack, DeclareCommitment, Give, Wait
from world.events import CommitmentDeclared
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import non_lethal_physical_rules
from world.values import ItemKind


def _base():
    giver = alive_body("body-a")
    other = alive_body("body-b")
    return base_runner_config_from_scenario(
        seed=17,
        stochastic_identity="cmp-at-commitments",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-at"),
            revision=WorldRevision(0),
            physical_rules=non_lethal_physical_rules(),
            locations=(make_location(),),
            bodies=(giver, other),
            weather=(make_weather(),),
        ),
        agents=(
            AgentRunnerSpec(
                agent_id=AgentId("agent-1"),
                entity_id=giver.entity_id,
                cognition=AgentCognitionSpec(agent_id=AgentId("agent-1")),
            ),
            AgentRunnerSpec(
                agent_id=AgentId("agent-2"),
                entity_id=other.entity_id,
                cognition=AgentCognitionSpec(agent_id=AgentId("agent-2")),
            ),
        ),
        max_ticks=6,
    )


def _arm(arm_id: str):
    definition = experiment_at_structured_commitments(_base())
    return next(
        item.runner_config
        for item in definition.conditions
        if item.condition_id == arm_id
    )


def _engine(*, active: bool, food_holder: str, material_holder: str | None):
    food = make_item(
        "food-1", location_id=None, holder_id=food_holder, kind=ItemKind.FOOD
    )
    items = [food]
    inventories = {
        "body-a": [],
        "body-b": [],
    }
    inventories[food_holder].append(food.entity_id)
    if material_holder is not None:
        material = make_item(
            "material-1",
            location_id=None,
            holder_id=material_holder,
            kind=ItemKind.MATERIAL,
        )
        items.append(material)
        inventories[material_holder].append(material.entity_id)
    bodies = tuple(
        alive_body(body_id, inventory=tuple(inventories[body_id]))
        for body_id in ("body-a", "body-b")
    )
    bootstrap = WorldBootstrap(
        world_id=WorldId("world-at-run"),
        revision=WorldRevision(0),
        locations=(make_location(),),
        bodies=bodies,
        items=tuple(items),
        weather=(make_weather(),),
        registrations=(
            AgentRegistration(AgentId("agent-1"), EntityId("body-a")),
            AgentRegistration(AgentId("agent-2"), EntityId("body-b")),
        ),
    )
    return WorldEngine(
        config=SimulationRunConfig(
            seed=17, physical_rules=non_lethal_physical_rules()
        ),
        bootstrap=bootstrap,
        structured_commitments_active=active,
        structured_commitments_horizon=8,
    )


def _step(engine: WorldEngine, commands: dict[str, object]):
    batch = engine.observe()
    submissions = []
    for observation in batch.observations:
        agent_id = engine.registration_translator.to_agent_id(observation.observer_id)
        command = commands.get(agent_id.value, Wait())
        submissions.append(ActionSubmission(batch.token, agent_id, command))
    engine.resolve_tick(tuple(submissions))
    result = engine.last_tick_result
    assert result is not None
    return batch, result


def _kinds(result) -> tuple[str, ...]:
    return tuple(type(record.event.details).__name__ for record in result.events)


def _digest(result) -> str:
    payload = "|".join(_kinds(result)).encode()
    return hashlib.sha256(payload).hexdigest()


def _status(result, kind: str):
    match = [
        resolution
        for resolution in result.resolutions
        if resolution.command.kind == kind
    ]
    assert len(match) == 1
    return match[0].status


def _declare(*, due_tick: int, kind: str = "future_exchange"):
    return DeclareCommitment(
        EntityId("body-b"),
        kind,
        "propose",
        "counterparty" if kind == "future_exchange" else "self",
        "none",
        1,
        "by_tick" if kind == "future_exchange" else "none",
        ItemKind.MATERIAL,
        due_tick if kind == "future_exchange" else None,
        ItemKind.FOOD if kind == "future_exchange" else None,
    )


def test_at_is_off_the_v1_gate(caplog) -> None:
    caplog.set_level(logging.INFO)
    gate = Path("tests/unit/test_v1_regression_gate.py").read_text(encoding="utf-8")
    assert "structured_commitments@1" in OFF_GATE_MATRIX_EXPERIMENT_IDS
    assert "structured_commitments@1" not in gate
    definition = experiment_at_structured_commitments(_base())
    assert definition.experiment_id == "structured_commitments@1"
    assert [item.condition_id for item in definition.conditions] == [
        "at-channel-off",
        "at-food-now-material-later",
        "at-divergent-terms",
        "at-no-collection",
    ]
    assert "experiment_arm_start arm_id=at-channel-off" in caplog.text


def test_at_channel_off_matches_the_pre_plan_give() -> None:
    assert _arm("at-channel-off").schema_version == RUNNER_SCHEMA_VERSION_V4
    assert _arm("at-channel-off").structured_commitments is None
    off = _engine(active=False, food_holder="body-a", material_holder=None)
    pre_plan = _engine(active=False, food_holder="body-a", material_holder=None)
    command = {"agent-1": Give(EntityId("body-b"), EntityId("food-1"))}
    _, off_result = _step(off, command)
    _, pre_result = _step(pre_plan, command)
    assert _digest(off_result) == _digest(pre_result)
    assert "CommitmentDeclared" not in _kinds(off_result)
    assert off._snapshot.world.state.items[EntityId("food-1")].holder_id == EntityId(
        "body-b"
    )
    assert not hasattr(off._snapshot.world.state, "agreements")


def test_food_stays_open_until_the_scripted_material_give() -> None:
    assert _arm("at-food-now-material-later").schema_version == (
        RUNNER_SCHEMA_VERSION_V39
    )
    engine = _engine(active=True, food_holder="body-b", material_holder="body-b")
    _, declared = _step(
        engine, {"agent-1": _declare(due_tick=8)}
    )
    assert _status(declared, "declare_commitment") is ActionResolutionStatus.APPLIED
    declared_kinds = [type(record.event.details) for record in declared.events]
    assert CommitmentDeclared in declared_kinds
    heard, given = _step(
        engine, {"agent-2": Give(EntityId("body-a"), EntityId("food-1"))}
    )
    assert _status(given, "give") is ActionResolutionStatus.APPLIED
    ledger = empty_structured_commitments(AgentId("agent-1"))
    speech = next(
        observation
        for observation in heard.observations
        if observation.observer_id == EntityId("body-a")
    )
    ledger = apply_structured_commitment_update(ledger, speech, tick=speech.tick)
    food_view, _waiting = _step(engine, {})
    food_obs = next(
        observation
        for observation in food_view.observations
        if observation.observer_id == EntityId("body-a")
    )
    ledger = apply_structured_commitment_update(ledger, food_obs, tick=food_obs.tick)
    assert ledger.interpretations[0].status == "open"
    assert ledger.interpretations[0].matched_quantity == 0
    later, moved = _step(
        engine, {"agent-2": Give(EntityId("body-a"), EntityId("material-1"))}
    )
    assert _status(moved, "give") is ActionResolutionStatus.APPLIED
    assert type(later) is not Attack
    material_view, _done = _step(engine, {})
    material_obs = next(
        observation
        for observation in material_view.observations
        if observation.observer_id == EntityId("body-a")
    )
    ledger = apply_structured_commitment_update(
        ledger, material_obs, tick=material_obs.tick
    )
    assert ledger.interpretations[0].status == "fulfilled"
    gives = [
        event
        for event in engine._snapshot.event_history
        if type(event.details).__name__ == "Given"
    ]
    assert len(gives) == 2


def test_divergent_terms_forget_only_one_owners_traces() -> None:
    engine = _engine(active=True, food_holder="body-a", material_holder=None)
    _, declared = _step(engine, {"agent-1": _declare(due_tick=0, kind="promise")})
    heard, _idle = _step(engine, {})
    rows = {}
    traces = {}
    for owner, entity in (("agent-1", "body-a"), ("agent-2", "body-b")):
        observation = next(
            item
            for item in heard.observations
            if item.observer_id == EntityId(entity)
        )
        ledger = apply_structured_commitment_update(
            empty_structured_commitments(AgentId(owner)),
            observation,
            tick=observation.tick,
        )
        occurrence = next(
            item
            for item in observation.occurrences
            if item.kind == "commitment_declared"
        )
        trace = build_direct_observation_memory_trace(
            owner_id=AgentId(owner),
            observation_tick=observation.tick,
            observation_revision=observation.revision,
            occurrence=occurrence,
            location_id=None,
        )
        rows[owner] = link_structured_commitment_traces(ledger, (trace,))
        traces[owner] = trace
    speech = next(
        record.event
        for record in declared.events
        if type(record.event.details) is CommitmentDeclared
    )
    assert speech.details.item_kind == "material"

    async def forget() -> None:
        service = InMemoryMemoryService(
            MemoryScope(MemoryRunId("run-at"), AgentId("agent-1"))
        )
        await service.apply(MemoryMutationBatch(writes=(traces["agent-1"],)))
        await service.forget_selected_ids((traces["agent-1"].memory_id,), tick=6)
        forgotten_trace = await service.get(traces["agent-1"].memory_id)
        assert forgotten_trace is not None
        rows["agent-1"] = forget_structured_commitments(
            rows["agent-1"], (forgotten_trace,)
        )

    asyncio.run(forget())
    assert rows["agent-1"].interpretations[0].status == "forgotten"
    assert rows["agent-2"].interpretations[0].status == "open"
    assert rows["agent-1"].interpretations[0].item_kind == "unspecified"
    assert rows["agent-2"].interpretations[0].item_kind == "material"
    assert not hasattr(engine._snapshot.world.state, "agreements")


def test_no_collection_leaves_health_and_inventory() -> None:
    engine = _engine(active=True, food_holder="body-a", material_holder="body-b")
    before = engine._snapshot.world.state.bodies[EntityId("body-b")]
    health = before.health
    inventory = before.inventory
    _, declared = _step(engine, {"agent-1": _declare(due_tick=0)})
    heard, _passed = _step(engine, {})
    observation = next(
        item
        for item in heard.observations
        if item.observer_id == EntityId("body-a")
    )
    ledger = apply_structured_commitment_update(
        empty_structured_commitments(AgentId("agent-1")),
        observation,
        tick=observation.tick,
    )
    after = engine._snapshot.world.state.bodies[EntityId("body-b")]
    assert after.health == health
    assert after.inventory == inventory
    assert ledger.interpretations[0].status == "violated"
    assert "Attack" not in _kinds(declared)
    views = classify_commitment_speech(
        tuple(record.event for record in declared.events),
        as_of_tick=declared.events[-1].event.tick,
        ledgers=(),
    )
    assert views[0].world_enforcement is False


def test_matrix_structured_commitments_beat_possession() -> None:
    from dataclasses import replace

    both = replace(
        _base(),
        schema_version=RUNNER_SCHEMA_VERSION_V39,
        v3_capability_flags=V3CapabilityFlags(),
        structured_commitments=example_structured_commitments_spec(),
        possession_succession=example_possession_succession_spec(),
        population_lifecycle=None,
    )
    finalized = finalize_matrix_cell_config(both)
    assert finalized.schema_version == RUNNER_SCHEMA_VERSION_V39
    possession = replace(
        both,
        structured_commitments=None,
        schema_version=RUNNER_SCHEMA_VERSION_V38,
    )
    assert (
        finalize_matrix_cell_config(possession).schema_version
        == RUNNER_SCHEMA_VERSION_V38
    )
