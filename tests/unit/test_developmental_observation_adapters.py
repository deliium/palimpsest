"""Observation / experimentation developmental acquisition adapters."""

from __future__ import annotations

from agents.cognition.developmental_learning import (
    DevelopmentalAcquisitionContext,
    DevelopmentalDomainId,
    DevelopmentalSourceId,
    apply_developmental_acquisition,
    empty_developmental_knowledge_ledger,
)
from agents.models import AgentId
from simulation.runner_models import example_developmental_learning_spec
from world.environment import HazardKind
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import LifeStatus, ResourceKind
from world.observations import (
    Observation,
    ObservedLocation,
    ObservedResource,
    ObservedSelf,
)
from world.values import (
    CarryCapacity,
    Fatigue,
    Health,
    Hunger,
    TemperatureCelsius,
    Thirst,
)


def _obs(*, tick: int = 2) -> Observation:
    return Observation(
        world_id=WorldId("world-w"),
        observer_id=EntityId("body-1"),
        revision=WorldRevision(0),
        tick=tick,
        self_body=ObservedSelf(
            entity_id=EntityId("body-1"),
            location_id=EntityId("clearing"),
            health=Health(100),
            hunger=Hunger(0),
            thirst=Thirst(0),
            fatigue=Fatigue(0),
            temperature=TemperatureCelsius(36.5),
            inventory=(),
            life_status=LifeStatus.ALIVE,
            carry_capacity=CarryCapacity(10),
        ),
        locations=(ObservedLocation(entity_id=EntityId("clearing"), name="Clearing"),),
        resources=(
            ObservedResource(
                entity_id=EntityId("berry"),
                name="berry",
                kind=ResourceKind.FOOD,
                quantity=1.0,
                unit="unit",
            ),
        ),
        hazard_kinds=(HazardKind.COLD_SNAP,),
    )


def test_observation_writes_location_resource_hazard_ledger_rows() -> None:
    owner = AgentId("learner-obs")
    ledger = empty_developmental_knowledge_ledger(owner)
    result = apply_developmental_acquisition(
        ledger,
        spec=example_developmental_learning_spec(),
        observation=_obs(),
        context=DevelopmentalAcquisitionContext(),
    )
    keys = {row.concept_key for row in result.ledger.entries}
    assert "loc:clearing" in keys
    assert "res:berry" in keys
    assert "haz:cold_snap" in keys
    assert all(
        row.source_id is DevelopmentalSourceId.OBSERVATION
        for row in result.ledger.entries
        if row.domain_id
        in {
            DevelopmentalDomainId.LOCATIONS,
            DevelopmentalDomainId.RESOURCES,
            DevelopmentalDomainId.HAZARDS,
        }
    )
    assert result.world_model_uplift is False


def test_world_model_uplift_flag_only_when_predictive_on() -> None:
    owner = AgentId("learner-wm")
    ledger = empty_developmental_knowledge_ledger(owner)
    off = apply_developmental_acquisition(
        ledger,
        spec=example_developmental_learning_spec(),
        observation=_obs(),
        context=DevelopmentalAcquisitionContext(predictive_world_model=False),
    )
    on = apply_developmental_acquisition(
        ledger,
        spec=example_developmental_learning_spec(),
        observation=_obs(),
        context=DevelopmentalAcquisitionContext(predictive_world_model=True),
    )
    assert off.world_model_uplift is False
    assert on.world_model_uplift is True
    assert len(off.ledger.entries) == len(on.ledger.entries) > 0
