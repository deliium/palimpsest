"""Optional co-enable of developmental_learning + mentorship."""

from __future__ import annotations

import logging
from types import SimpleNamespace

from agents.cognition.developmental_learning import (
    DevelopmentalAcquisitionContext,
    DevelopmentalSourceId,
    apply_developmental_acquisition,
    empty_developmental_knowledge_ledger,
)
from agents.cognition.mentorship import (
    apply_mentorship_from_teaching,
    empty_mentorship_ledger,
)
from agents.models import AgentId
from simulation.runner_models import (
    MentorshipBondPolicy,
    MentorshipLineagePolicy,
    example_developmental_learning_spec,
)
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import LifeStatus
from world.observations import Observation, ObservedSelf
from world.values import (
    CarryCapacity,
    Fatigue,
    Health,
    Hunger,
    TemperatureCelsius,
    Thirst,
)

_LOG = logging.getLogger("tests.mentorship_developmental_compose")


def test_instruction_cites_same_teacher_when_both_channels_on() -> None:
    _LOG.debug("case_id=compose_teacher_present")
    teacher = AgentId("alice")
    advice = SimpleNamespace(
        occurrence_id="occ-compose-1",
        source_agent_id=teacher,
        domain=SimpleNamespace(value="foraging"),
        act=SimpleNamespace(value="explain"),
        band=SimpleNamespace(value="mid"),
    )
    mentorship_ledger, mentorship_audits = apply_mentorship_from_teaching(
        empty_mentorship_ledger(AgentId("bob")),
        enabled_content_kinds=("practical_skills",),
        advice_delta=(advice,),
        tick=2,
        bond_policy=MentorshipBondPolicy(form_after_successful_acts=1, min_trust=0.1),
        lineage_policy=MentorshipLineagePolicy(),
    )
    assert mentorship_audits
    assert mentorship_ledger.bonds[0].partner_agent_id == teacher

    result = apply_developmental_acquisition(
        empty_developmental_knowledge_ledger(AgentId("bob")),
        spec=example_developmental_learning_spec(
            enabled_domains=("skills",),
            enabled_sources=("instruction", "observation"),
        ),
        observation=Observation(
            world_id=WorldId("w"),
            observer_id=EntityId("body-bob"),
            revision=WorldRevision(0),
            tick=2,
            self_body=ObservedSelf(
                entity_id=EntityId("body-bob"),
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
        ),
        context=DevelopmentalAcquisitionContext(
            skill_learning_on=True,
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


def test_either_channel_alone_still_works() -> None:
    _LOG.debug("case_id=channel_isolation")
    advice = SimpleNamespace(
        occurrence_id="occ-alone",
        source_agent_id=AgentId("alice"),
        domain=SimpleNamespace(value="foraging"),
        act=SimpleNamespace(value="explain"),
        band=SimpleNamespace(value="high"),
    )
    only_mentorship, _ = apply_mentorship_from_teaching(
        empty_mentorship_ledger(AgentId("solo-m")),
        enabled_content_kinds=("practical_skills",),
        advice_delta=(advice,),
        tick=1,
        bond_policy=MentorshipBondPolicy(form_after_successful_acts=1, min_trust=0.0),
        lineage_policy=MentorshipLineagePolicy(),
    )
    assert only_mentorship.lineage
    only_dev = apply_developmental_acquisition(
        empty_developmental_knowledge_ledger(AgentId("solo-d")),
        spec=example_developmental_learning_spec(
            enabled_domains=("skills",),
            enabled_sources=("instruction",),
        ),
        observation=Observation(
            world_id=WorldId("w"),
            observer_id=EntityId("body-solo"),
            revision=WorldRevision(0),
            tick=1,
            self_body=ObservedSelf(
                entity_id=EntityId("body-solo"),
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
        ),
        context=DevelopmentalAcquisitionContext(
            skill_learning_on=True,
            teaching_on=True,
            advice_delta=(advice,),
        ),
    )
    assert only_dev.ledger.entries
