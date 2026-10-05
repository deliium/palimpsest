"""Dependency-care perception modes: none vs self_and_colocated parity."""

from __future__ import annotations

import logging
from dataclasses import replace

import pytest

from agents.models import AgentId
from simulation.bootstrap import AgentRegistration, WorldBootstrap
from simulation.engine import WorldEngine
from simulation.models import SimulationRunConfig
from simulation.runner_models import (
    example_dependency_care_spec,
    example_population_lifecycle_spec,
    seed_bootstrap_lifecycle_records,
)
from simulation.serialization import decode_domain, encode_domain
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.identifiers import EntityId, WorldId, WorldRevision
from world.lifecycle import DependencyStatus, LifecycleStageId
from world.models import non_lethal_physical_rules
from world.observations import ObservedDependencyNeeds
from world.values import Hunger

_LOG = logging.getLogger("tests.dependency_care_perception_parity")


def _engine(*, perception_mode: str) -> WorldEngine:
    dependent = replace(alive_body("body-dep"), hunger=Hunger(50.0))
    caregiver = alive_body("body-care")
    bootstrap = WorldBootstrap(
        world_id=WorldId("world-dep-perc"),
        revision=WorldRevision(0),
        locations=(make_location(body_capacity=8),),
        bodies=(dependent, caregiver),
        weather=(make_weather(),),
        registrations=(
            AgentRegistration(AgentId("agent-dep"), dependent.entity_id),
            AgentRegistration(AgentId("agent-care"), caregiver.entity_id),
        ),
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
    care = example_dependency_care_spec(perception_mode=perception_mode)
    return WorldEngine(
        config=SimulationRunConfig(
            seed=81, physical_rules=non_lethal_physical_rules()
        ),
        bootstrap=bootstrap,
        population_lifecycle=spec,
        lifecycle_records=(dep_record, care_record),
        dependency_care_spec=care,
    )


def test_perception_none_omits_dependency_needs() -> None:
    engine = _engine(perception_mode="none")
    batch = engine.observe()
    for observation in batch.observations:
        assert observation.self_body is not None
        assert observation.self_body.dependency_needs is None
        for other in observation.visible_bodies:
            assert other.dependency_needs is None


def test_perception_self_and_colocated_exposes_need_summaries(
    caplog: pytest.LogCaptureFixture,
) -> None:
    engine = _engine(perception_mode="self_and_colocated")
    with caplog.at_level(logging.DEBUG):
        batch = engine.observe()
    dep_obs = next(
        obs
        for obs in batch.observations
        if obs.observer_id == EntityId("body-dep")
    )
    assert dep_obs.self_body is not None
    assert type(dep_obs.self_body.dependency_needs) is ObservedDependencyNeeds
    need_ids = {row.need_id for row in dep_obs.self_body.dependency_needs.needs}
    assert "food" in need_ids
    care_obs = next(
        obs
        for obs in batch.observations
        if obs.observer_id == EntityId("body-care")
    )
    visible_dep = next(
        body for body in care_obs.visible_bodies if body.entity_id.value == "body-dep"
    )
    assert type(visible_dep.dependency_needs) is ObservedDependencyNeeds
    assert "perception_dependency_need_fact_count" in caplog.text
    # Live/restored observation encode parity for dependency needs.
    encoded = encode_domain(dep_obs)
    restored = decode_domain(encoded)
    assert restored.self_body.dependency_needs is not None
    assert restored.self_body.dependency_needs.needs[0].need_id in need_ids
    _LOG.debug("perception_parity ok need_ids=%s", sorted(need_ids))
