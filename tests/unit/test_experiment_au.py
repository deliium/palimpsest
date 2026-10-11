"""Off-gate Experiment AU. A swap moves named items, not a price."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from agents.cognition.subjective_value import (
    propose_exchange_command,
    refresh_owner_ledgers,
)
from agents.models import AgentId
from analysis.subjective_value import ExchangeLedgerSnapshot, classify_exchange
from experiments import (
    OFF_GATE_MATRIX_EXPERIMENT_IDS,
    experiment_au_subjective_exchange,
)
from experiments.catalog import base_runner_config_from_scenario
from experiments.matrix_schema import finalize_matrix_cell_config
from simulation.bootstrap import AgentRegistration, WorldBootstrap
from simulation.engine import WorldEngine
from simulation.lifecycle import ActionResolutionStatus, ActionSubmission
from simulation.models import SimulationRunConfig
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V4,
    RUNNER_SCHEMA_VERSION_V39,
    RUNNER_SCHEMA_VERSION_V40,
    AgentCognitionSpec,
    AgentRunnerSpec,
    V3CapabilityFlags,
    WorldScenarioSpec,
    example_structured_commitments_spec,
    example_subjective_valuation_spec,
)
from tests.simulation_helpers import alive_body, make_item, make_location, make_weather
from world.actions import Give, NegotiateExchange, Wait
from world.events import ExchangeCompleted, ExchangeProposed
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import non_lethal_physical_rules
from world.values import ItemKind


def _base():
    alice = alive_body("body-a", carry_capacity=10)
    bob = alive_body("body-b", carry_capacity=10)
    return base_runner_config_from_scenario(
        seed=17,
        stochastic_identity="cmp-au-exchange",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-au"),
            revision=WorldRevision(0),
            physical_rules=non_lethal_physical_rules(),
            locations=(make_location(),),
            bodies=(alice, bob),
            weather=(make_weather(),),
        ),
        agents=(
            AgentRunnerSpec(
                agent_id=AgentId("agent-1"),
                entity_id=alice.entity_id,
                cognition=AgentCognitionSpec(agent_id=AgentId("agent-1")),
            ),
            AgentRunnerSpec(
                agent_id=AgentId("agent-2"),
                entity_id=bob.entity_id,
                cognition=AgentCognitionSpec(agent_id=AgentId("agent-2")),
            ),
        ),
        max_ticks=6,
    )


def _arm(arm_id: str):
    definition = experiment_au_subjective_exchange(_base())
    return next(
        item.runner_config
        for item in definition.conditions
        if item.condition_id == arm_id
    )


def _engine(*, active: bool, foods: int):
    tool = make_item(
        "tool-1",
        name="Axe",
        kind=ItemKind.TOOL,
        location_id=None,
        holder_id="body-a",
    )
    food = tuple(
        make_item(
            f"food-{index}",
            name="Bread",
            kind=ItemKind.FOOD,
            location_id=None,
            holder_id="body-b",
        )
        for index in range(1, foods + 1)
    )
    alice = alive_body(
        "body-a", inventory=(tool.entity_id,), carry_capacity=10
    )
    bob = alive_body(
        "body-b",
        inventory=tuple(item.entity_id for item in food),
        carry_capacity=10,
    )
    bootstrap = WorldBootstrap(
        world_id=WorldId("world-au-run"),
        revision=WorldRevision(0),
        locations=(make_location(),),
        bodies=(alice, bob),
        items=(tool, *food),
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
        subjective_valuation_active=active,
        subjective_valuation_horizon=8,
        subjective_valuation_max_bundle=8,
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


def _holder(engine: WorldEngine, item_id: str) -> EntityId | None:
    return engine._snapshot.world.state.items[EntityId(item_id)].holder_id


def test_au_is_off_the_v1_gate(caplog) -> None:
    caplog.set_level(logging.INFO)
    gate = Path("tests/unit/test_v1_regression_gate.py").read_text(encoding="utf-8")
    invariants = Path("tests/unit/test_v2_scientific_invariants.py").read_text(
        encoding="utf-8"
    )
    assert "subjective_exchange@1" in OFF_GATE_MATRIX_EXPERIMENT_IDS
    assert "subjective_exchange@1" not in gate
    assert "subjective_exchange@1" not in invariants
    definition = experiment_au_subjective_exchange(_base())
    assert definition.experiment_id == "subjective_exchange@1"
    assert [item.condition_id for item in definition.conditions] == [
        "au-channel-off",
        "au-divergent-reservation",
        "au-agreed-swap",
        "au-history",
    ]
    assert "experiment_arm_start arm_id=au-channel-off" in caplog.text
    divergent = _arm("au-divergent-reservation")
    assert divergent.v3_capability_flags == V3CapabilityFlags()


def test_channel_off_matches_the_pre_plan_give() -> None:
    assert _arm("au-channel-off").schema_version == RUNNER_SCHEMA_VERSION_V4
    assert _arm("au-channel-off").subjective_valuation is None
    off = _engine(active=False, foods=1)
    pre_plan = _engine(active=False, foods=1)
    command = {"agent-2": Give(EntityId("body-a"), EntityId("food-1"))}
    _, off_result = _step(off, command)
    _, pre_result = _step(pre_plan, command)
    assert _digest(off_result) == _digest(pre_result)
    assert "ExchangeProposed" not in _kinds(off_result)
    assert "ExchangeCompleted" not in _kinds(off_result)
    assert _holder(off, "food-1") == EntityId("body-a")
    assert not hasattr(off._snapshot.world.state, "subjective_valuations")


def test_divergent_reservations_do_not_complete() -> None:
    assert _arm("au-divergent-reservation").schema_version == RUNNER_SCHEMA_VERSION_V40
    engine = _engine(active=True, foods=8)
    seen, _idle = _step(engine, {})
    alice_obs = _observation(seen, "body-a")
    bob_obs = _observation(seen, "body-b")
    alice, _alice_scarcity = refresh_owner_ledgers(
        owner_id=AgentId("agent-1"),
        valuations=None,
        scarcity=None,
        tick=alice_obs.tick,
        hunger=0,
        thirst=0,
        health=100,
        body_present=True,
        held_counts={ItemKind.TOOL: 1},
        ground_kinds=(),
        other_held_kinds=(),
        location_id=EntityId("loc-1"),
        plan_kinds=frozenset({ItemKind.TOOL}),
        risk_active=False,
        future_kinds=frozenset(),
    )
    bob, _bob_scarcity = refresh_owner_ledgers(
        owner_id=AgentId("agent-2"),
        valuations=None,
        scarcity=None,
        tick=bob_obs.tick,
        hunger=0,
        thirst=0,
        health=100,
        body_present=True,
        held_counts={ItemKind.FOOD: 8},
        ground_kinds=(),
        other_held_kinds=(ItemKind.TOOL,),
        location_id=EntityId("loc-1"),
        plan_kinds=frozenset(),
        risk_active=False,
        future_kinds=frozenset(),
    )
    foods = tuple(EntityId(f"food-{index}") for index in range(1, 4))
    _, offered = _step(
        engine,
        {
            "agent-2": NegotiateExchange(
                EntityId("body-a"),
                "offer",
                foods,
                (EntityId("tool-1"),),
            )
        },
    )
    offered_kinds = [type(record.event.details) for record in offered.events]
    assert ExchangeCompleted not in offered_kinds
    proposed = next(
        record.event.details
        for record in offered.events
        if type(record.event.details) is ExchangeProposed
    )
    assert not hasattr(proposed, "reservation")
    heard, _waiting = _step(engine, {})
    alice_next = _observation(heard, "body-a")
    counter = propose_exchange_command(
        Wait(),
        alice_next,
        channel_on=True,
        max_bundle=8,
        valuations=alice,
        owner_entity_id=EntityId("body-a"),
    )
    assert type(counter) is NegotiateExchange
    assert counter.act == "counteroffer"
    _, answered = _step(engine, {"agent-1": counter})
    names = [type(event.details).__name__ for event in engine._snapshot.event_history]
    assert "ExchangeCompleted" not in names
    answered_names = [
        type(record.event.details).__name__ for record in answered.events
    ]
    assert "ExchangeProposed" in answered_names
    assert _reservation(alice, ItemKind.TOOL) == 8
    assert _reservation(bob, ItemKind.TOOL) == 3
    assert _holder(engine, "tool-1") == EntityId("body-a")


def test_agreed_swap_moves_the_named_items_and_a_broken_accept_moves_none() -> None:
    engine = _engine(active=True, foods=4)
    foods = tuple(EntityId(f"food-{index}") for index in range(1, 5))
    _step(
        engine,
        {
            "agent-1": NegotiateExchange(
                EntityId("body-b"), "offer", (EntityId("tool-1"),), foods
            )
        },
    )
    _, swapped = _step(
        engine,
        {
            "agent-2": NegotiateExchange(
                EntityId("body-a"), "accept", foods, (EntityId("tool-1"),)
            )
        },
    )
    completed = [
        record
        for record in swapped.events
        if type(record.event.details) is ExchangeCompleted
    ]
    assert len(completed) == 1
    assert _holder(engine, "tool-1") == EntityId("body-b")
    for index in range(1, 5):
        assert _holder(engine, f"food-{index}") == EntityId("body-a")

    broken = _engine(active=True, foods=4)
    _, _offered = _step(
        broken,
        {
            "agent-1": NegotiateExchange(
                EntityId("body-b"), "offer", (EntityId("tool-1"),), foods
            )
        },
    )
    _step(broken, {"agent-2": Give(EntityId("body-a"), EntityId("food-1"))})
    _, rejected = _step(
        broken,
        {
            "agent-2": NegotiateExchange(
                EntityId("body-a"), "accept", foods, (EntityId("tool-1"),)
            )
        },
    )
    assert _resolution(rejected, "agent-2").status is ActionResolutionStatus.REJECTED
    assert _holder(broken, "tool-1") == EntityId("body-a")
    assert _holder(broken, "food-2") == EntityId("body-b")
    assert _holder(broken, "food-1") == EntityId("body-a")


def test_history_keeps_offer_counteroffer_and_completion() -> None:
    engine = _engine(active=True, foods=4)
    foods = tuple(EntityId(f"food-{index}") for index in range(1, 4))
    _step(
        engine,
        {
            "agent-1": NegotiateExchange(
                EntityId("body-b"), "offer", (EntityId("tool-1"),), foods
            )
        },
    )
    _step(
        engine,
        {
            "agent-2": NegotiateExchange(
                EntityId("body-a"), "counteroffer", foods, (EntityId("tool-1"),)
            )
        },
    )
    _step(
        engine,
        {
            "agent-1": NegotiateExchange(
                EntityId("body-b"), "accept", (EntityId("tool-1"),), foods
            )
        },
    )
    events = tuple(engine._snapshot.event_history)
    views = classify_exchange(
        events,
        as_of_tick=events[-1].tick,
        ledgers=(
            ExchangeLedgerSnapshot("alice", "tool", 3),
            ExchangeLedgerSnapshot("bob", "tool", 3),
        ),
    )
    assert views[0].path == ("offer", "counteroffer", "complete")
    assert views[0].realized_bundle == (("food", 3), ("tool", 1))
    assert views[0].institution == "none"
    assert "world_price" not in views[0].__slots__


def test_matrix_subjective_valuation_beats_commitments() -> None:
    from dataclasses import replace

    both = replace(
        _base(),
        schema_version=RUNNER_SCHEMA_VERSION_V40,
        v3_capability_flags=V3CapabilityFlags(),
        subjective_valuation=example_subjective_valuation_spec(),
        structured_commitments=example_structured_commitments_spec(),
        population_lifecycle=None,
    )
    finalized = finalize_matrix_cell_config(both)
    assert finalized.schema_version == RUNNER_SCHEMA_VERSION_V40
    commitments = replace(
        both,
        subjective_valuation=None,
        schema_version=RUNNER_SCHEMA_VERSION_V39,
    )
    assert (
        finalize_matrix_cell_config(commitments).schema_version
        == RUNNER_SCHEMA_VERSION_V39
    )


def _observation(batch, body_id: str):
    return next(
        observation
        for observation in batch.observations
        if observation.observer_id == EntityId(body_id)
    )


def _reservation(ledger, kind: ItemKind) -> int:
    return next(row.reservation for row in ledger.kind_rows if row.item_kind is kind)


def _resolution(result, agent: str):
    return next(
        resolution
        for resolution in result.resolutions
        if resolution.agent_id == AgentId(agent)
    )
