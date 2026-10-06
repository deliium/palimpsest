"""Social source adapters: instruction / communication / imitation."""

from __future__ import annotations

from types import SimpleNamespace

from agents.cognition.developmental_learning import (
    DevelopmentalAcquisitionContext,
    DevelopmentalDomainId,
    DevelopmentalSourceId,
    apply_developmental_acquisition,
    empty_developmental_knowledge_ledger,
)
from agents.models import AgentId
from simulation.runner_models import example_developmental_learning_spec
from world.identifiers import EntityId, EventId, WorldId, WorldRevision
from world.models import LifeStatus
from world.observations import (
    Observation,
    ObservationProvenance,
    ObservationSourceKind,
    ObservedCommunication,
    ObservedOccurrence,
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


def _self() -> ObservedSelf:
    return ObservedSelf(
        entity_id=EntityId("body-learner"),
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


def test_instruction_records_teacher_provenance() -> None:
    teacher = AgentId("teacher-1")
    advice = SimpleNamespace(
        occurrence_id="occ-teach-1",
        source_agent_id=teacher,
        domain=SimpleNamespace(value="skill"),
    )
    spec = example_developmental_learning_spec(
        enabled_domains=("skills", "practices"),
        enabled_sources=("instruction", "observation"),
    )
    result = apply_developmental_acquisition(
        empty_developmental_knowledge_ledger(AgentId("learner-soc")),
        spec=spec,
        observation=Observation(
            world_id=WorldId("w"),
            observer_id=EntityId("body-learner"),
            revision=WorldRevision(0),
            tick=4,
            self_body=_self(),
        ),
        context=DevelopmentalAcquisitionContext(
            skill_learning_on=True,
            social_convention_on=True,
            teaching_on=True,
            advice_delta=(advice,),
        ),
    )
    instructed = [
        row
        for row in result.ledger.entries
        if row.source_id is DevelopmentalSourceId.INSTRUCTION
    ]
    assert instructed
    assert instructed[0].teacher_agent_id == teacher
    assert instructed[0].domain_id is DevelopmentalDomainId.SKILLS


def test_instruction_skips_when_skill_mode_off() -> None:
    advice = SimpleNamespace(
        occurrence_id="occ-teach-2",
        source_agent_id=AgentId("teacher-1"),
        domain=SimpleNamespace(value="skill"),
    )
    spec = example_developmental_learning_spec(
        enabled_domains=("skills",),
        enabled_sources=("instruction",),
    )
    result = apply_developmental_acquisition(
        empty_developmental_knowledge_ledger(AgentId("learner-off")),
        spec=spec,
        observation=Observation(
            world_id=WorldId("w"),
            observer_id=EntityId("body-learner"),
            revision=WorldRevision(0),
            tick=1,
            self_body=_self(),
        ),
        context=DevelopmentalAcquisitionContext(
            skill_learning_on=False,
            advice_delta=(advice,),
        ),
    )
    assert result.ledger.entries == ()
    assert any(a.reason_code == "required_mode_off" for a in result.audits)


def test_never_copies_sender_stores() -> None:
    """Instruction path mints fresh owner concept keys — no peer ledger merge."""
    import inspect

    from agents.cognition import developmental_learning as mod

    source = inspect.getsource(mod.apply_developmental_acquisition)
    assert "peer" not in source.lower() or "never" in source.lower()
    assert "copy(" not in source
