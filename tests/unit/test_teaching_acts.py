"""Teaching acts ride an existing talk and do not change the search draw."""

from __future__ import annotations

import logging

import pytest

from agents.cognition.competence import (
    CompetenceBelief,
    CompetenceDomain,
    CompetenceSelfModel,
    empty_competence_model,
)
from agents.cognition.configuration import CognitionTeachingInteractionMode
from agents.cognition.teaching import (
    AdviceAct,
    AdviceDomain,
    TeachingClaimPolicy,
    attach_teaching_act,
    band_for_belief,
    teaching_response_term,
)
from agents.models import AgentId
from simulation.engine import WorldEngine
from simulation.lifecycle import ActionSubmission
from tests.physical_helpers import physical_config, two_location_fixture
from world._skills import (
    SkillDomain,
    adjusted_search_probability,
    default_objective_skill_policy,
)
from world._teaching import default_teaching_interaction_policy
from world.actions import Talk
from world.communications import CommunicationRelation, origin_utterance
from world.identifiers import EntityId, EventId, WorldId, WorldRevision
from world.models import PhysicalRules
from world.observations import (
    Observation,
    ObservationProvenance,
    ObservationSourceKind,
    ObservedCommunication,
)

pytestmark = pytest.mark.unit

_OWNER = AgentId("learner")


def _model(level: float) -> CompetenceSelfModel:
    base = empty_competence_model(_OWNER)
    beliefs = list(base.beliefs)
    beliefs[0] = CompetenceBelief(
        domain=CompetenceDomain.FORAGING,
        believed_level=level,
        support_mass=1.0,
        counter_mass=0.0,
    )
    return CompetenceSelfModel(
        owner_id=base.owner_id,
        beliefs=tuple(beliefs),
        cursors=base.cursors,
    )


def _talk(*relations: CommunicationRelation) -> Talk:
    return Talk(
        EntityId("body-2"),
        origin_utterance(
            text="a public act",
            speaker_id=EntityId("body-1"),
            communication_id="comm-1",
            relations=relations,
        ),
    )


def _request() -> Observation:
    utterance = origin_utterance(
        text="show me",
        speaker_id=EntityId("body-2"),
        communication_id="comm-ask",
        relations=(
            CommunicationRelation(
                subject="skill",
                predicate="request_instruction",
                object="foraging",
            ),
        ),
    )
    return Observation(
        observer_id=EntityId("body-1"),
        world_id=WorldId("world-1"),
        revision=WorldRevision(1),
        tick=2,
        communications=(
            ObservedCommunication(
                provenance=ObservationProvenance(
                    source_kind=ObservationSourceKind.COMMUNICATION,
                    source_tick=1,
                    source_event_id=EventId("evt-ask"),
                ),
                speaker_id=EntityId("body-2"),
                listener_id=EntityId("body-1"),
                utterance=utterance,
                action_kind="tell",
            ),
        ),
    )


def test_disabled_leaves_the_command_and_a_request_explains(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger="agents.cognition.teaching")
    policy = TeachingClaimPolicy()
    plain = _talk()
    unchanged = attach_teaching_act(
        plain,
        model=_model(1.0),
        policy=policy,
        observation=_request(),
        mode=CognitionTeachingInteractionMode.DISABLED,
    )
    assert unchanged == plain
    explained = attach_teaching_act(
        plain,
        model=_model(1.0),
        policy=policy,
        observation=_request(),
        mode=CognitionTeachingInteractionMode.DETERMINISTIC,
    )
    relation = explained.utterance.content.relations[0]
    assert relation.predicate == "explain"
    assert relation.object == f"foraging:{band_for_belief(1.0, policy).value}"
    assert "teaching_act owner_id=learner" in caplog.text
    assert "act=explain" in caplog.text
    assert "domain=foraging" in caplog.text
    assert "band=high" in caplog.text
    weight = teaching_response_term(
        _request(),
        policy,
        type("Direction", (), {"value": "communicate"})(),
        _OWNER,
    )
    assert weight == policy.teaching_response_weight
    assert "teaching_response_bias owner_id=learner" in caplog.text
    assert f"weight={policy.teaching_response_weight}" in caplog.text


def test_occupied_relation_is_left_in_place(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG, logger="agents.cognition.teaching")
    occupied = _talk(
        CommunicationRelation(subject="skill", predicate="uncertain", object="camp")
    )
    result = attach_teaching_act(
        occupied,
        model=_model(1.0),
        policy=TeachingClaimPolicy(),
        observation=None,
        mode=CognitionTeachingInteractionMode.DETERMINISTIC,
    )
    assert result == occupied
    assert "reason_code=relation_occupied" in caplog.text


def test_missing_model_and_false_provider_do_not_call_out() -> None:
    command = _talk()
    provider_calls: list[object] = []

    class Provider:
        async def generate(self, request: object) -> object:
            provider_calls.append(request)
            raise AssertionError("provider")

    kept = attach_teaching_act(
        command,
        model=None,
        policy=TeachingClaimPolicy(allow_provider=True),
        observation=None,
        mode=CognitionTeachingInteractionMode.DETERMINISTIC,
    )
    assert kept == command
    assert provider_calls == []
    demonstrated = attach_teaching_act(
        command,
        model=_model(1.0),
        policy=TeachingClaimPolicy(allow_provider=False),
        observation=None,
        mode=CognitionTeachingInteractionMode.DETERMINISTIC,
    )
    relation = demonstrated.utterance.content.relations[0]
    assert relation.predicate == AdviceAct.DEMONSTRATE.value
    assert relation.object == AdviceDomain.FORAGING.value


def test_explain_leaves_the_level_zero_search_probability() -> None:
    rules = PhysicalRules(search_base_probability=0.35, search_visibility_weight=0.0)
    engine = WorldEngine(
        config=physical_config(11, rules=rules),
        bootstrap=two_location_fixture(item_on_ground=False).as_bootstrap(),
        skill_policy=default_objective_skill_policy(),
        skill_entity_ids=(EntityId("body-1"), EntityId("body-2")),
        teaching_policy=default_teaching_interaction_policy(),
        teaching_entity_ids=(EntityId("body-1"), EntityId("body-2")),
    )
    batch = engine.observe()
    engine.resolve_tick(
        (
            ActionSubmission(
                batch.token,
                AgentId("agent-1"),
                Talk(
                    EntityId("body-2"),
                    origin_utterance(
                        text="forage high",
                        speaker_id=EntityId("body-1"),
                        communication_id="comm-high",
                        relations=(
                            CommunicationRelation(
                                subject="skill",
                                predicate="explain",
                                object="foraging:high",
                            ),
                        ),
                    ),
                ),
            ),
        )
    )
    ledger = engine._skill_ledger
    assert ledger is not None
    foraging = ledger.level(EntityId("body-2"), SkillDomain.FORAGING)
    assert foraging == 0.0
    policy = default_objective_skill_policy()
    draw = adjusted_search_probability(
        search_base_probability=rules.search_base_probability,
        search_visibility_weight=rules.search_visibility_weight,
        visibility=1.0,
        foraging_level=foraging,
        resource_detection_level=0.0,
        policy=policy,
    )
    level_zero = adjusted_search_probability(
        search_base_probability=rules.search_base_probability,
        search_visibility_weight=rules.search_visibility_weight,
        visibility=1.0,
        foraging_level=0.0,
        resource_detection_level=0.0,
        policy=policy,
    )
    assert draw == level_zero
    assert engine._skill_ledger.level(EntityId("body-2"), SkillDomain.FORAGING) == 0.0
