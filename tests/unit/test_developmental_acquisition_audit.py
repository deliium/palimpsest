"""Metadata-only DevelopmentalAcquisitionAudit harvest."""

from __future__ import annotations

from agents.cognition.developmental_learning import (
    DevelopmentalAcquisitionAudit,
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


def test_acquisition_emits_metadata_audits_without_concept_payloads() -> None:
    result = apply_developmental_acquisition(
        empty_developmental_knowledge_ledger(AgentId("aud-1")),
        spec=example_developmental_learning_spec(),
        observation=Observation(
            world_id=WorldId("w"),
            observer_id=EntityId("body-1"),
            revision=WorldRevision(0),
            tick=2,
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
            locations=(
                ObservedLocation(entity_id=EntityId("clearing"), name="Clearing"),
            ),
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
        ),
        context=DevelopmentalAcquisitionContext(),
    )
    assert result.audits
    assert all(type(row) is DevelopmentalAcquisitionAudit for row in result.audits)
    acquired = [row for row in result.audits if row.acquired]
    assert acquired
    for row in acquired:
        assert row.domain_id in {
            DevelopmentalDomainId.LOCATIONS,
            DevelopmentalDomainId.RESOURCES,
            DevelopmentalDomainId.HAZARDS,
        }
        assert row.source_id is DevelopmentalSourceId.OBSERVATION
        assert row.reason_code == "acquired"
        assert not hasattr(row, "concept_key")
