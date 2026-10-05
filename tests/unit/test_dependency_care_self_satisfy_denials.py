"""DEPENDENT self-satisfy denials for dependency_care channel."""

from __future__ import annotations

import logging
from dataclasses import replace

import pytest

from agents.models import AgentId
from simulation.bootstrap import AgentRegistration, WorldBootstrap
from simulation.engine import WorldEngine
from simulation.lifecycle import (
    ActionResolutionReason,
    ActionResolutionStatus,
    ActionSubmission,
)
from simulation.models import SimulationRunConfig
from simulation.runner_models import (
    example_dependency_care_spec,
    example_population_lifecycle_spec,
    seed_bootstrap_lifecycle_records,
)
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.actions import Eat, Wait
from world.identifiers import EntityId, WorldId, WorldRevision
from world.lifecycle import DependencyStatus, LifecycleStageId
from world.models import Item, non_lethal_physical_rules
from world.values import ItemKind, ItemLoad

_LOG = logging.getLogger("tests.dependency_care_self_satisfy_denials")


def _engine(*, dependency_care: bool = True) -> WorldEngine:
    body = alive_body("body-1")
    adult = alive_body("body-adult")
    food = Item(
        entity_id=EntityId("item-food"),
        name="Food",
        kind=ItemKind.FOOD,
        location_id=EntityId("loc-1"),
        load=ItemLoad(1),
    )
    bootstrap = WorldBootstrap(
        world_id=WorldId("world-dep-deny"),
        revision=WorldRevision(0),
        locations=(make_location(body_capacity=8),),
        bodies=(body, adult),
        weather=(make_weather(),),
        items=(food,),
        registrations=(
            AgentRegistration(AgentId("agent-1"), body.entity_id),
            AgentRegistration(AgentId("agent-adult"), adult.entity_id),
        ),
    )
    spec = example_population_lifecycle_spec(lifespan_ticks=40, max_population=4)
    records = seed_bootstrap_lifecycle_records(
        registrations=bootstrap.registrations, spec=spec
    )
    adult_record = replace(
        records[1],
        stage=LifecycleStageId("adult"),
        dependency_status=DependencyStatus.INDEPENDENT,
    )
    records = (records[0], adult_record)
    care = example_dependency_care_spec() if dependency_care else None
    return WorldEngine(
        config=SimulationRunConfig(
            seed=40, physical_rules=non_lethal_physical_rules()
        ),
        bootstrap=bootstrap,
        population_lifecycle=spec,
        lifecycle_records=records,
        dependency_care_spec=care,
    )


def test_dependent_eat_denied_by_dependency_care(
    caplog: pytest.LogCaptureFixture,
) -> None:
    engine = _engine()
    assert engine.dependency_care_channel_active is True
    assert engine.lifecycle_records[0].dependency_status is DependencyStatus.DEPENDENT
    batch = engine.observe()
    with caplog.at_level(logging.DEBUG):
        result = engine.resolve_tick(
            (
                ActionSubmission(
                    batch.token,
                    AgentId("agent-1"),
                    Eat(EntityId("item-food")),
                ),
            )
        )
    assert result.resolutions[0].status is ActionResolutionStatus.REJECTED
    assert (
        result.resolutions[0].reason is ActionResolutionReason.STRUCTURAL_REJECTION
    )
    assert "dependency_care_self_satisfy_denied" in caplog.text


def test_independent_wait_not_dependency_denied() -> None:
    engine = _engine()
    batch = engine.observe()
    result = engine.resolve_tick(
        (ActionSubmission(batch.token, AgentId("agent-adult"), Wait()),)
    )
    assert result.resolutions[0].status is ActionResolutionStatus.APPLIED


def test_channel_off_does_not_emit_dependency_care_denial(
    caplog: pytest.LogCaptureFixture,
) -> None:
    engine = _engine(dependency_care=False)
    assert engine.dependency_care_channel_active is False
    batch = engine.observe()
    with caplog.at_level(logging.DEBUG):
        engine.resolve_tick(
            (
                ActionSubmission(
                    batch.token,
                    AgentId("agent-1"),
                    Eat(EntityId("item-food")),
                ),
            )
        )
    assert "dependency_care_self_satisfy_denied" not in caplog.text
    assert "dependency_care_self_satisfy_denied" not in "".join(
        record.getMessage() for record in caplog.records
    )