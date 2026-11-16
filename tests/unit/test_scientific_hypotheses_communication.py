# mypy: ignore-errors
"""Bounded ``hyp_v1`` claim communication and evidence-free adoption."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from agents.cognition.configuration import CognitionScientificHypothesesMode
from agents.cognition.emotion import PassthroughEmotionalStateAppraiser
from agents.cognition.experimentation import (
    ExperimentCognitionBinding,
    HypothesisCondition,
    HypothesisConditionSlot,
    HypothesisRevisionReason,
    HypothesisSourceKind,
    HypothesisStatus,
    empty_experiment_ledger,
    formulate_hypothesis,
)
from agents.cognition.goal_manager import PassthroughGoalManager
from agents.cognition.loop import CognitiveLoop
from agents.cognition.scientific_hypothesis_communication import (
    SCIENTIFIC_HYPOTHESIS_FRAME,
    SCIENTIFIC_HYPOTHESIS_RELATION_MAX,
    adopt_communicated_hypothesis,
    attach_scientific_hypothesis_claim,
    encode_scientific_hypothesis_claim,
    parse_scientific_hypothesis_claim_relation,
)
from agents.models import AgentId
from tests.typecheck.cognitive_loop import (
    ScriptedFutureImagination,
    ScriptedIntentionSelector,
    ScriptedMemoryRetriever,
    ScriptedMemoryUpdateHook,
    ScriptedMotivationEvaluator,
    ScriptedPerceptionInterpreter,
    ScriptedPlanner,
    ScriptedSelfStateProjector,
    ScriptedSituationModeler,
)
from world.actions import Ask, Talk, Tell, Wait
from world.communications import (
    CommunicationRelation,
    CommunicationSourceBasis,
    origin_utterance,
)
from world.experimentation import (
    ExperimentOperator,
    ExperimentOutcomeClass,
    ExperimentProcessToken,
)
from world.identifiers import EntityId

pytestmark = pytest.mark.unit

OWNER = AgentId("agent-1")
BASE_RELATIONS = (
    CommunicationRelation(subject="greeting", predicate="hello", object="once"),
)


def _binding() -> ExperimentCognitionBinding:
    return ExperimentCognitionBinding(
        max_hypotheses=8,
        max_trials_per_tick=1,
        repeat_threshold=2,
        learn_into_genealogy=False,
        allow_provider=False,
    )


def _talk(relations=BASE_RELATIONS) -> Talk:
    return Talk(
        recipient_id=EntityId("body-ben"),
        utterance=origin_utterance(
            text="hello",
            speaker_id=EntityId("body-ada"),
            communication_id="talk-1",
            relations=tuple(relations),
            source_basis=CommunicationSourceBasis.UNREFERENCED,
        ),
    )


def _hypothesis(
    *,
    conditions: tuple[HypothesisCondition, ...] = (
        HypothesisCondition(HypothesisConditionSlot.LOCATION, "loc-1"),
        HypothesisCondition(HypothesisConditionSlot.DAY_PHASE, "day"),
    ),
    operand_a: str = "item-material",
):
    return formulate_hypothesis(
        owner_id=OWNER,
        hypothesis_id="hyp:communicated",
        operator=ExperimentOperator.COMBINE,
        operand_a_id=operand_a,
        operand_b_id="resource-material",
        process_token=ExperimentProcessToken.NONE,
        predicted_outcome=ExperimentOutcomeClass.SUCCESS,
        conditions=conditions,
    )


def test_encode_parse_round_trip() -> None:
    relation = encode_scientific_hypothesis_claim(_hypothesis())
    assert relation.subject == SCIENTIFIC_HYPOTHESIS_FRAME
    parsed = parse_scientific_hypothesis_claim_relation(relation)
    assert parsed is not None
    assert parsed.operator is ExperimentOperator.COMBINE
    assert parsed.operand_a_id == "item-material"
    assert parsed.predicted_outcome is ExperimentOutcomeClass.SUCCESS
    assert parsed.conditions[0].slot is HypothesisConditionSlot.LOCATION
    assert parsed.confidence_milli == 500
    assert parsed.source_kind is HypothesisSourceKind.SELF_FORMULATED


def test_encode_parse_without_conditions() -> None:
    relation = encode_scientific_hypothesis_claim(_hypothesis(conditions=()))
    parsed = parse_scientific_hypothesis_claim_relation(relation)
    assert parsed is not None
    assert parsed.conditions == ()


def test_encode_rejects_separator_and_whitespace_values() -> None:
    with pytest.raises(ValueError):
        encode_scientific_hypothesis_claim(_hypothesis(operand_a="bad:value"))
    with pytest.raises(ValueError):
        encode_scientific_hypothesis_claim(_hypothesis(operand_a="bad value"))


def test_parse_rejects_objective_rule_payloads() -> None:
    relation = CommunicationRelation(
        subject=SCIENTIFIC_HYPOTHESIS_FRAME,
        predicate="claim",
        object=(
            "combine:item-material:resource-material:none:success:500:none:"
            "self_formulated:self:law"
        ),
    )
    assert parse_scientific_hypothesis_claim_relation(relation) is None


def test_parse_rejects_malformed_frames() -> None:
    for body in (
        "a:b",
        "combine:item-material:resource-material:none:success:notdigits:none:"
        "self_formulated:self:claim-1",
        "combine:item-material:resource-material:none:success:500:none:"
        "unknown_source:self:claim-1",
    ):
        relation = CommunicationRelation(
            subject=SCIENTIFIC_HYPOTHESIS_FRAME, predicate="claim", object=body
        )
        assert parse_scientific_hypothesis_claim_relation(relation) is None


def test_unrelated_relation_returns_none() -> None:
    assert (
        parse_scientific_hypothesis_claim_relation(BASE_RELATIONS[0]) is None
    )


def test_attach_only_talk_and_tell() -> None:
    hypothesis = _hypothesis()
    talk = attach_scientific_hypothesis_claim(_talk(), hypothesis)
    assert type(talk) is Talk
    assert talk.recipient_id == EntityId("body-ben")
    assert len(talk.utterance.content.relations) == 2
    assert talk.utterance.content.relations[0] == BASE_RELATIONS[0]

    tell = Tell(
        recipient_id=EntityId("body-ben"),
        utterance=origin_utterance(
            text="hello",
            speaker_id=EntityId("body-ada"),
            communication_id="tell-1",
            relations=BASE_RELATIONS,
            source_basis=CommunicationSourceBasis.UNREFERENCED,
        ),
    )
    assert type(attach_scientific_hypothesis_claim(tell, hypothesis)) is Tell

    with pytest.raises(TypeError):
        attach_scientific_hypothesis_claim(Wait(), hypothesis)
    with pytest.raises(TypeError):
        attach_scientific_hypothesis_claim(
            Ask(
                recipient_id=EntityId("body-ben"),
                utterance=origin_utterance(
                    text="?",
                    speaker_id=EntityId("body-ada"),
                    communication_id="ask-1",
                    relations=BASE_RELATIONS,
                    source_basis=CommunicationSourceBasis.UNREFERENCED,
                ),
            ),
            hypothesis,
        )


def test_attach_at_most_once_and_respects_relation_cap() -> None:
    hypothesis = _hypothesis()
    once = attach_scientific_hypothesis_claim(_talk(), hypothesis)
    twice = attach_scientific_hypothesis_claim(once, hypothesis)
    assert twice == once
    assert (
        sum(
            1
            for relation in twice.utterance.content.relations
            if relation.subject == SCIENTIFIC_HYPOTHESIS_FRAME
        )
        == 1
    )

    full = tuple(
        CommunicationRelation(
            subject=f"rel-{index}", predicate="value", object="once"
        )
        for index in range(SCIENTIFIC_HYPOTHESIS_RELATION_MAX)
    )
    capped = attach_scientific_hypothesis_claim(_talk(full), hypothesis)
    assert len(capped.utterance.content.relations) == (
        SCIENTIFIC_HYPOTHESIS_RELATION_MAX
    )


def test_adoption_is_provisional_and_evidence_free() -> None:
    relation = encode_scientific_hypothesis_claim(_hypothesis())
    claim = parse_scientific_hypothesis_claim_relation(relation)
    assert claim is not None
    ledger = empty_experiment_ledger(OWNER, _binding())
    adopted = adopt_communicated_hypothesis(
        ledger, claim, source_token="evt:delivery-1", tick=3
    )
    row = adopted.hypotheses[0]
    assert row.source_kind is HypothesisSourceKind.COMMUNICATED
    assert row.source_token == "evt:delivery-1"
    assert row.support == 0
    assert row.counter == 0
    assert row.evidence_event_ids == ()
    assert row.counter_evidence_event_ids == ()
    assert row.status is HypothesisStatus.PROVISIONAL
    assert row.revisions[0].reason is HypothesisRevisionReason.SOURCE_ADOPTED


def test_adoption_is_idempotent() -> None:
    relation = encode_scientific_hypothesis_claim(_hypothesis())
    claim = parse_scientific_hypothesis_claim_relation(relation)
    assert claim is not None
    ledger = empty_experiment_ledger(OWNER, _binding())
    once = adopt_communicated_hypothesis(
        ledger, claim, source_token="evt:delivery-1", tick=3
    )
    twice = adopt_communicated_hypothesis(
        once, claim, source_token="evt:delivery-2", tick=4
    )
    assert twice is once
    assert len(twice.hypotheses) == 1


def test_adoption_rejects_self_source_token() -> None:
    relation = encode_scientific_hypothesis_claim(_hypothesis())
    claim = parse_scientific_hypothesis_claim_relation(relation)
    assert claim is not None
    ledger = empty_experiment_ledger(OWNER, _binding())
    with pytest.raises(ValueError, match="source_token: invalid_source_token"):
        adopt_communicated_hypothesis(
            ledger, claim, source_token="self", tick=3
        )


def test_loop_ingest_adopts_exactly_one_claim() -> None:
    relation = encode_scientific_hypothesis_claim(_hypothesis())
    loop = CognitiveLoop(
        perception=ScriptedPerceptionInterpreter(),
        memory=ScriptedMemoryRetriever(),
        situation=ScriptedSituationModeler(),
        self_state=ScriptedSelfStateProjector(),
        goal_manager=PassthroughGoalManager(),
        emotional_state=PassthroughEmotionalStateAppraiser(),
        futures=ScriptedFutureImagination(),
        motivation=ScriptedMotivationEvaluator(),
        intention=ScriptedIntentionSelector(),
        planner=ScriptedPlanner(),
        memory_updates=ScriptedMemoryUpdateHook(),
        scientific_hypotheses_mode=CognitionScientificHypothesesMode.DETERMINISTIC,
    )
    loop._bounded_experimentation_caps = _binding()
    communication = SimpleNamespace(
        provenance=SimpleNamespace(
            source_event_id=SimpleNamespace(value="delivery-1")
        ),
        utterance=SimpleNamespace(content=SimpleNamespace(relations=(relation,))),
    )
    loop_input = SimpleNamespace(
        agent_id=OWNER,
        observation=SimpleNamespace(tick=3, communications=(communication,)),
    )
    loop._ingest_scientific_hypotheses(loop_input)
    ledger = loop._experiment_ledger
    assert ledger is not None
    assert len(ledger.hypotheses) == 1
    row = ledger.hypotheses[0]
    assert row.source_kind is HypothesisSourceKind.COMMUNICATED
    assert row.source_token == "evt:delivery-1"
    assert row.evidence_event_ids == ()
