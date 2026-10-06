"""Cross-agent developmental ledger divergence under matched seeds."""

from __future__ import annotations

from agents.cognition.developmental_learning import (
    DevelopmentalAcquisitionContext,
    apply_developmental_acquisition,
    empty_developmental_knowledge_ledger,
)
from agents.models import AgentId
from simulation.runner_models import example_developmental_learning_spec
from world.artifacts import ArtifactContent, ArtifactKind as WorldArtifactKind, ArtifactRelation
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import LifeStatus
from world.observations import (
    Observation,
    ObservedArtifact,
    ObservedItemPlacement,
    ObservedLocation,
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


def _self(body: str = "body-a") -> ObservedSelf:
    return ObservedSelf(
        entity_id=EntityId(body),
        location_id=EntityId("clearing"),
        health=Health(100),
        hunger=Hunger(0),
        thirst=Thirst(0),
        fatigue=Fatigue(0),
        temperature=TemperatureCelsius(36.5),
        inventory=(),
        life_status=LifeStatus.ALIVE,
        carry_capacity=CarryCapacity(10),
    )


def _artifact(aid: str) -> ObservedArtifact:
    return ObservedArtifact(
        entity_id=EntityId(aid),
        kind=WorldArtifactKind.SIGN,
        author_id=EntityId("body-author"),
        created_tick=0,
        content=ArtifactContent(
            marks=("water", "north"),
            relations=(ArtifactRelation("water", "at", "north"),),
        ),
        content_revision=0,
        placement=ObservedItemPlacement.GROUND_HERE,
    )


def test_different_artifact_exposures_diverge_ledgers() -> None:
    spec = example_developmental_learning_spec(
        enabled_domains=("vocabulary", "practices", "locations"),
        enabled_sources=("observation", "artifact"),
    )
    ctx = DevelopmentalAcquisitionContext(
        artifact_interpretation_on=True,
        semantic_naming_on=True,
        social_convention_on=True,
    )
    a = apply_developmental_acquisition(
        empty_developmental_knowledge_ledger(AgentId("learner-a")),
        spec=spec,
        observation=Observation(
            world_id=WorldId("w"),
            observer_id=EntityId("body-a"),
            revision=WorldRevision(0),
            tick=1,
            self_body=_self("body-a"),
            locations=(ObservedLocation(entity_id=EntityId("clearing"), name="C"),),
            artifacts=(_artifact("art-alpha"),),
        ),
        context=ctx,
    )
    b = apply_developmental_acquisition(
        empty_developmental_knowledge_ledger(AgentId("learner-b")),
        spec=spec,
        observation=Observation(
            world_id=WorldId("w"),
            observer_id=EntityId("body-b"),
            revision=WorldRevision(0),
            tick=1,
            self_body=_self("body-b"),
            locations=(ObservedLocation(entity_id=EntityId("clearing"), name="C"),),
            artifacts=(_artifact("art-beta"),),
        ),
        context=ctx,
    )
    keys_a = {row.concept_key for row in a.ledger.entries}
    keys_b = {row.concept_key for row in b.ledger.entries}
    assert keys_a != keys_b
    assert "vocab:art:art-alpha" in keys_a
    assert "vocab:art:art-beta" in keys_b


def test_isolated_arm_cannot_acquire_teacher_only_concepts() -> None:
    isolated = example_developmental_learning_spec(
        enabled_domains=("locations", "resources", "hazards", "skills"),
        enabled_sources=("observation", "experimentation"),
    )
    from types import SimpleNamespace

    advice = SimpleNamespace(
        occurrence_id="secret-teach",
        source_agent_id=AgentId("teacher"),
        domain=SimpleNamespace(value="skill"),
    )
    result = apply_developmental_acquisition(
        empty_developmental_knowledge_ledger(AgentId("isolated")),
        spec=isolated,
        observation=Observation(
            world_id=WorldId("w"),
            observer_id=EntityId("body-a"),
            revision=WorldRevision(0),
            tick=1,
            self_body=_self(),
            locations=(ObservedLocation(entity_id=EntityId("clearing"), name="C"),),
        ),
        context=DevelopmentalAcquisitionContext(
            skill_learning_on=True,
            teaching_on=True,
            advice_delta=(advice,),
        ),
    )
    assert all(
        row.source_id.value != "instruction" for row in result.ledger.entries
    )
    assert not any(
        "instr:" in row.concept_key for row in result.ledger.entries
    )
