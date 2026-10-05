"""Inspection projection helpers for dependency-care channel."""

from __future__ import annotations

from dataclasses import replace

from agents.models import AgentId
from simulation.bootstrap import AgentRegistration, WorldBootstrap
from simulation.engine import WorldEngine
from simulation.inspection import (
    DEPENDENCY_CARE_INSPECTION_SCHEMA,
    DetachedInspectionProjector,
)
from simulation.models import RunId, SimulationRunConfig
from simulation.runner_models import (
    example_dependency_care_spec,
    example_population_lifecycle_spec,
    seed_bootstrap_lifecycle_records,
)
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.identifiers import WorldId, WorldRevision
from world.lifecycle import DependencyStatus, LifecycleStageId
from world.models import non_lethal_physical_rules


def _engine(*, channel_on: bool = True) -> WorldEngine:
    dependent = alive_body("body-dep")
    caregiver = alive_body("body-care")
    bootstrap = WorldBootstrap(
        world_id=WorldId("world-dep-inspect"),
        revision=WorldRevision(0),
        locations=(make_location(body_capacity=8),),
        bodies=(dependent, caregiver),
        weather=(make_weather(),),
        registrations=(
            AgentRegistration(AgentId("agent-dep"), dependent.entity_id),
            AgentRegistration(AgentId("agent-care"), caregiver.entity_id),
        ),
    )
    if not channel_on:
        return WorldEngine(
            config=SimulationRunConfig(
                seed=21, physical_rules=non_lethal_physical_rules()
            ),
            bootstrap=bootstrap,
            run_id=RunId("run-dep-inspect-off"),
        )
    spec = example_population_lifecycle_spec(lifespan_ticks=40, max_population=4)
    records = seed_bootstrap_lifecycle_records(
        registrations=bootstrap.registrations, spec=spec
    )
    dep_record = replace(
        records[0],
        stage=LifecycleStageId("infant"),
        dependency_status=DependencyStatus.DEPENDENT,
    )
    care_record = replace(
        records[1],
        stage=LifecycleStageId("adult"),
        dependency_status=DependencyStatus.INDEPENDENT,
    )
    return WorldEngine(
        config=SimulationRunConfig(
            seed=21, physical_rules=non_lethal_physical_rules()
        ),
        bootstrap=bootstrap,
        run_id=RunId("run-dep-inspect"),
        population_lifecycle=spec,
        lifecycle_records=(dep_record, care_record),
        dependency_care_spec=example_dependency_care_spec(
            perception_mode="self_and_colocated",
            caregiving_cognition_mode="deterministic",
        ),
    )


def test_project_dependency_care_channel_on() -> None:
    projector = DetachedInspectionProjector()
    document = projector.project_dependency_care(_engine(channel_on=True))
    assert document.schema_version == DEPENDENCY_CARE_INSPECTION_SCHEMA
    assert document.channel_active is True
    assert document.perception_mode == "self_and_colocated"
    assert document.caregiving_cognition_mode == "deterministic"


def test_project_dependency_care_channel_off() -> None:
    projector = DetachedInspectionProjector()
    document = projector.project_dependency_care(_engine(channel_on=False))
    assert document.channel_active is False
    assert document.need_rows == ()
    assert document.recent_care_acts == ()
