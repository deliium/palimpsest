"""Off-gate Experiment AV. Counts are not a currency designation."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from agents.models import AgentId
from analysis.exchange_functions import classify_exchange_functions
from analysis.exchange_functions_metrics import assemble_exchange_function_metrics
from experiments import (
    OFF_GATE_MATRIX_EXPERIMENT_IDS,
    experiment_av_exchange_functions,
)
from experiments.catalog import base_runner_config_from_scenario
from experiments.matrix_schema import finalize_matrix_cell_config
from simulation.bootstrap import AgentRegistration, WorldBootstrap
from simulation.engine import WorldEngine
from simulation.lifecycle import ActionSubmission
from simulation.models import SimulationRunConfig
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V40,
    RUNNER_SCHEMA_VERSION_V41,
    AgentCognitionSpec,
    AgentRunnerSpec,
    WorldScenarioSpec,
    example_resource_exchange_profile_spec,
)
from tests.simulation_helpers import alive_body, make_item, make_location, make_weather
from world.actions import NegotiateExchange, Wait
from world.events import ExchangeCompleted
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import non_lethal_physical_rules
from world.values import ItemKind


def _base():
    alice = alive_body("body-a", carry_capacity=10)
    bob = alive_body("body-b", carry_capacity=10)
    return base_runner_config_from_scenario(
        seed=19,
        stochastic_identity="cmp-av-exchange",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-av"),
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
    definition = experiment_av_exchange_functions(_base())
    return next(
        item.runner_config
        for item in definition.conditions
        if item.condition_id == arm_id
    )


def _engine(
    items: tuple[object, ...],
    bodies: tuple[object, ...],
    registrations: tuple[AgentRegistration, ...],
    *,
    profile_active: bool,
) -> WorldEngine:
    return WorldEngine(
        config=SimulationRunConfig(seed=19, physical_rules=non_lethal_physical_rules()),
        bootstrap=WorldBootstrap(
            world_id=WorldId("world-av-run"),
            revision=WorldRevision(0),
            locations=(make_location(),),
            bodies=bodies,
            items=items,
            weather=(make_weather(),),
            registrations=registrations,
        ),
        subjective_valuation_active=True,
        subjective_valuation_horizon=8,
        subjective_valuation_max_bundle=8,
        resource_exchange_profile_active=profile_active,
    )


def _pair() -> tuple[object, ...]:
    pebble = make_item(
        "pebble-1",
        name="Pebble",
        kind=ItemKind.GENERIC,
        load=1,
        location_id=None,
        holder_id="body-a",
    )
    tool = make_item(
        "tool-1",
        name="Axe",
        kind=ItemKind.TOOL,
        location_id=None,
        holder_id="body-b",
    )
    alice = alive_body("body-a", inventory=(pebble.entity_id,), carry_capacity=10)
    bob = alive_body("body-b", inventory=(tool.entity_id,), carry_capacity=10)
    regs = (
        AgentRegistration(AgentId("agent-1"), EntityId("body-a")),
        AgentRegistration(AgentId("agent-2"), EntityId("body-b")),
    )
    return (pebble, tool), (alice, bob), regs


def _digest(result) -> str:
    names = tuple(type(record.event.details).__name__ for record in result.events)
    return hashlib.sha256("|".join(names).encode()).hexdigest()


def _history(engine: WorldEngine) -> tuple[object, ...]:
    return tuple(engine._snapshot.event_history)


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


def test_av_is_off_the_v1_gate(caplog) -> None:
    caplog.set_level(logging.INFO)
    gate = Path("tests/unit/test_v1_regression_gate.py").read_text(encoding="utf-8")
    assert "exchange_functions@1" in OFF_GATE_MATRIX_EXPERIMENT_IDS
    assert "exchange_functions@1" not in gate
    definition = experiment_av_exchange_functions(_base())
    assert [item.condition_id for item in definition.conditions] == [
        "av-channel-off",
        "av-inert-unused",
        "av-later-trade",
        "av-quote-kind",
    ]
    assert "experiment_arm_start condition_id=av-channel-off" in caplog.text
    off = _arm("av-channel-off")
    assert off.schema_version == RUNNER_SCHEMA_VERSION_V40
    assert off.resource_exchange_profile is None
    assert off.subjective_valuation is not None
    assert _arm("av-later-trade").schema_version == RUNNER_SCHEMA_VERSION_V41
    finalized = finalize_matrix_cell_config(_arm("av-later-trade"))
    assert finalized.schema_version == RUNNER_SCHEMA_VERSION_V41


def _same_tick_swap(engine: WorldEngine) -> object:
    _, swapped = _step(
        engine,
        {
            "agent-1": NegotiateExchange(
                EntityId("body-b"),
                "offer",
                (EntityId("pebble-1"),),
                (EntityId("tool-1"),),
            ),
            "agent-2": NegotiateExchange(
                EntityId("body-a"),
                "accept",
                (EntityId("tool-1"),),
                (EntityId("pebble-1"),),
            ),
        },
    )
    return swapped


def test_channel_off_swap_hash_matches_the_v40_baseline() -> None:
    off = _engine(*_pair(), profile_active=False)
    baseline = _engine(*_pair(), profile_active=False)
    profile = _engine(*_pair(), profile_active=True)
    seen, _idle = _step(off, {})
    item = next(iter(seen.observations[0].items))
    assert not hasattr(item, "physical_profile")
    _step(baseline, {})
    _step(profile, {})
    off_swap = _same_tick_swap(off)
    baseline_swap = _same_tick_swap(baseline)
    profile_swap = _same_tick_swap(profile)
    assert _digest(off_swap) == _digest(baseline_swap) == _digest(profile_swap)
    completed = [
        record
        for record in off_swap.events
        if type(record.event.details) is ExchangeCompleted
    ]
    assert completed
    documents = assemble_exchange_function_metrics(
        tuple(record.event for record in off_swap.events),
        run_id="run-av",
        input_revision="rev-1",
        spec=None,
        as_of_tick=2,
    )
    assert documents == ()


def test_inert_item_is_unused_and_scripted_arms_stay_numeric(caplog) -> None:
    caplog.set_level(logging.DEBUG, logger="analysis.exchange_functions")
    spec = example_resource_exchange_profile_spec()
    pebble = make_item(
        "pebble-1",
        name="Pebble",
        kind=ItemKind.GENERIC,
        load=1,
        location_id=None,
        holder_id="body-a",
    )
    alice = alive_body("body-a", inventory=(pebble.entity_id,), carry_capacity=10)
    bob = alive_body("body-b", carry_capacity=10)
    unused_engine = _engine(
        (pebble,),
        (alice, bob),
        (
            AgentRegistration(AgentId("agent-1"), EntityId("body-a")),
            AgentRegistration(AgentId("agent-2"), EntityId("body-b")),
        ),
        profile_active=True,
    )
    _step(unused_engine, {})
    unused = classify_exchange_functions(_history(unused_engine), spec=spec)
    generic = next(row for row in unused.acquisition_fate if row.item_kind == "generic")
    assert generic.later_transferred_count == 0
    assert generic.consumed_count == 0

    bread = make_item(
        "bread-1",
        name="Bread",
        kind=ItemKind.FOOD,
        location_id=None,
        holder_id="body-b",
    )
    axe = make_item(
        "axe-1",
        name="Axe",
        kind=ItemKind.TOOL,
        location_id=None,
        holder_id="body-c",
    )
    pebble_a = make_item(
        "pebble-1",
        name="Pebble",
        kind=ItemKind.GENERIC,
        load=1,
        location_id=None,
        holder_id="body-a",
    )
    bodies = (
        alive_body("body-a", inventory=(pebble_a.entity_id,), carry_capacity=10),
        alive_body("body-b", inventory=(bread.entity_id,), carry_capacity=10),
        alive_body("body-c", inventory=(axe.entity_id,), carry_capacity=10),
    )
    regs = (
        AgentRegistration(AgentId("agent-1"), EntityId("body-a")),
        AgentRegistration(AgentId("agent-2"), EntityId("body-b")),
        AgentRegistration(AgentId("agent-3"), EntityId("body-c")),
    )
    later_engine = _engine((pebble_a, bread, axe), bodies, regs, profile_active=True)
    _step(
        later_engine,
        {
            "agent-1": NegotiateExchange(
                EntityId("body-b"),
                "offer",
                (EntityId("pebble-1"),),
                (EntityId("bread-1"),),
            ),
            "agent-2": NegotiateExchange(
                EntityId("body-a"),
                "accept",
                (EntityId("bread-1"),),
                (EntityId("pebble-1"),),
            ),
        },
    )
    _step(
        later_engine,
        {
            "agent-2": NegotiateExchange(
                EntityId("body-c"),
                "offer",
                (EntityId("pebble-1"),),
                (EntityId("axe-1"),),
            ),
            "agent-3": NegotiateExchange(
                EntityId("body-b"),
                "accept",
                (EntityId("axe-1"),),
                (EntityId("pebble-1"),),
            ),
        },
    )
    later = classify_exchange_functions(_history(later_engine), spec=spec)
    fate = next(row for row in later.acquisition_fate if row.item_kind == "generic")
    share = next(row for row in later.acceptance_share if row.item_kind == "generic")
    assert fate.later_transferred_count >= 1
    assert fate.consumed_count == 0
    assert share.kind_present_count >= 2
    assert "exchange_functions_assembled" in caplog.text

    tool_b = make_item(
        "tool-b",
        name="Axe",
        kind=ItemKind.TOOL,
        location_id=None,
        holder_id="body-b",
    )
    tool_c = make_item(
        "tool-c",
        name="Axe",
        kind=ItemKind.TOOL,
        location_id=None,
        holder_id="body-c",
    )
    quote_pebble = make_item(
        "pebble-1",
        name="Pebble",
        kind=ItemKind.GENERIC,
        load=1,
        location_id=None,
        holder_id="body-a",
    )
    quote_bread = make_item(
        "bread-1",
        name="Bread",
        kind=ItemKind.FOOD,
        location_id=None,
        holder_id="body-a",
    )
    quote_bodies = (
        alive_body(
            "body-a",
            inventory=(quote_pebble.entity_id, quote_bread.entity_id),
            carry_capacity=10,
        ),
        alive_body("body-b", inventory=(tool_b.entity_id,), carry_capacity=10),
        alive_body("body-c", inventory=(tool_c.entity_id,), carry_capacity=10),
    )
    quote_engine = _engine(
        (quote_pebble, quote_bread, tool_b, tool_c),
        quote_bodies,
        regs,
        profile_active=True,
    )
    _step(
        quote_engine,
        {
            "agent-1": NegotiateExchange(
                EntityId("body-b"),
                "offer",
                (EntityId("pebble-1"),),
                (EntityId("tool-b"),),
            ),
            "agent-2": NegotiateExchange(
                EntityId("body-a"),
                "accept",
                (EntityId("tool-b"),),
                (EntityId("pebble-1"),),
            ),
        },
    )
    _step(
        quote_engine,
        {
            "agent-1": NegotiateExchange(
                EntityId("body-c"),
                "offer",
                (EntityId("bread-1"),),
                (EntityId("tool-c"),),
            ),
            "agent-3": NegotiateExchange(
                EntityId("body-a"),
                "accept",
                (EntityId("tool-c"),),
                (EntityId("bread-1"),),
            ),
        },
    )
    quote = classify_exchange_functions(_history(quote_engine), spec=spec)
    generic_quote = next(
        row for row in quote.quote_homogeneity if row.item_kind == "generic"
    )
    food_quote = next(row for row in quote.quote_homogeneity if row.item_kind == "food")
    assert generic_quote.homogeneous_side_count >= 1
    assert food_quote.homogeneous_side_count >= 1
    assert "is_money" not in caplog.text
