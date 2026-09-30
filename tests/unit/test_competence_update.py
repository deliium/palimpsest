"""Competence beliefs move from the owner's observation, not the skill ledger."""

from __future__ import annotations

import logging

import pytest

from agents.cognition.competence import (
    CompetenceDomain,
    default_competence_belief_policy,
    empty_competence_model,
    update_competence,
)
from agents.models import AgentId
from world._skills import ObjectiveSkillLedger
from world.identifiers import EntityId, EventId, WorldId, WorldRevision
from world.observations import (
    Observation,
    ObservationAudienceRole,
    ObservationProvenance,
    ObservationSourceKind,
    ObservedOccurrence,
)

pytestmark = pytest.mark.unit


def _quantize(value: float) -> float:
    return round(value / 1e-6) * 1e-6


def _search(event: str, *, success: bool) -> ObservedOccurrence:
    return ObservedOccurrence(
        provenance=ObservationProvenance(
            source_kind=ObservationSourceKind.OCCURRENCE,
            source_tick=1,
            source_event_id=EventId(event),
        ),
        kind="search",
        audience_role=ObservationAudienceRole.ACTOR,
        actor_id=EntityId("body-1"),
        success=success,
    )


def _observation(*occurrences: ObservedOccurrence) -> Observation:
    return Observation(
        observer_id=EntityId("body-1"),
        world_id=WorldId("world-1"),
        revision=WorldRevision(1),
        tick=2,
        occurrences=occurrences,
    )


def test_success_and_failure_beliefs_diverge_from_the_ledger(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger="agents.cognition.competence")
    policy = default_competence_belief_policy()
    owner = AgentId("agent-1")
    prior = empty_competence_model(owner)
    success = update_competence(
        prior, _observation(_search("evt-hit", success=True)), (), policy
    )
    belief = success.belief_for(CompetenceDomain.FORAGING)
    assert belief.support_mass == 0.10
    assert belief.counter_mass == 0.0
    assert belief.believed_level == _quantize(0.10 / 1.10)
    missed = update_competence(
        prior, _observation(_search("evt-miss", success=False)), (), policy
    )
    failed = missed.belief_for(CompetenceDomain.FORAGING)
    assert failed.support_mass == 0.0
    assert failed.believed_level == 0.0
    again = update_competence(
        success, _observation(_search("evt-hit", success=True)), (), policy
    )
    assert again.belief_for(CompetenceDomain.FORAGING).support_mass == 0.10
    assert "competence_update " in caplog.text
    assert "domain=foraging" in caplog.text
    assert "channel=success" in caplog.text
    assert "believed=" in caplog.text
    assert "probability" not in caplog.text


def test_ledger_and_foreign_reconstruction_are_rejected(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.ERROR, logger="agents.cognition.competence")
    policy = default_competence_belief_policy()
    model = empty_competence_model(AgentId("agent-1"))
    ledger = ObjectiveSkillLedger.bootstrap((EntityId("body-1"),))
    with pytest.raises(TypeError):
        update_competence(model, ledger, (), policy)
    foreign = type("Memory", (), {"owner_id": AgentId("agent-2")})()
    update_competence(model, _observation(), (foreign,), policy)
    assert "reason_code=owner_mismatch" in caplog.text
