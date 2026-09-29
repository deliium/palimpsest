"""Contracts for per-utterance communication strategy."""

from __future__ import annotations

import logging
import math
from pathlib import Path

import pytest

from agents.cognition.communication_strategy import (
    COMMUNICATION_STRATEGY_POLICY_VERSION,
    CommunicationDivergence,
    CommunicationFactor,
    CommunicationIntentAudit,
    CommunicationStrategy,
    SpeakerStance,
    apply_communication_strategy,
    choose_communication_strategy,
    communication_intent,
    communication_intent_id,
    default_communication_strategy_policy,
    reject_empty_refusal_render,
    render_communication_intent,
)
from agents.cognition.configuration import CognitionCommunicationStrategyMode
from agents.cognition.epistemic import EpistemicJudgment
from agents.cognition.models import SubjectiveRisk, SubjectiveRiskKind
from agents.models import AgentId
from simulation.runner_models import CommunicationStrategyMode
from social.relationships import (
    DirectedRelationshipProfile,
    RelationshipActivationState,
    RelationshipConfidence,
    RelationshipDimension,
    RelationshipDimensionState,
    RelationshipId,
    RelationshipPolicyRef,
    RelationshipRevisionId,
)
from world.communications import CommunicationSourceBasis, confidence_band
from world.identifiers import EntityId, WorldId, WorldRevision
from world.observations import Observation, ObservedLocation

_OWNER = AgentId("agent-speaker")
_RECIPIENT = AgentId("agent-listener")
_SPEAKER = EntityId("body-speaker")
_LISTENER = EntityId("body-listener")
_LOGGER = "agents.cognition.communication_strategy"
_SOURCE = (
    Path("src/agents/cognition/communication_strategy.py").read_text(encoding="utf-8")
)


def _intent(**overrides: object):
    payload: dict[str, object] = {
        "owner_id": _OWNER,
        "recipient_id": _RECIPIENT,
        "tick": 3,
        "strategy": CommunicationStrategy.TRUTHFUL,
        "stance": SpeakerStance.ASSERT_MATCH,
        "divergence": CommunicationDivergence.NONE,
        "source_basis": CommunicationSourceBasis.BELIEF,
        "source_confidence": 0.8,
        "source_atom_tokens": ("food",),
        "cited_event_id": None,
        "factor_codes": (CommunicationFactor.NORMS_UNAVAILABLE,),
        "delivered": True,
    }
    payload.update(overrides)
    return communication_intent(**payload)  # type: ignore[arg-type]


def test_policy_defaults() -> None:
    policy = default_communication_strategy_policy()
    assert policy.version == COMMUNICATION_STRATEGY_POLICY_VERSION
    assert policy.relationship_high == 0.4
    assert policy.low_confidence == 0.55
    assert policy.emotion_intensity == 0.4


def test_intent_id_is_sha256_of_owner_recipient_tick_strategy_and_atoms() -> None:
    intent = _intent()
    again = _intent()
    assert intent.intent_id == again.intent_id
    assert intent.intent_id == communication_intent_id(
        owner_id=_OWNER,
        recipient_id=_RECIPIENT,
        tick=3,
        strategy=CommunicationStrategy.TRUTHFUL,
        source_atom_tokens=("food",),
    )
    assert intent.intent_id.startswith("cs-")
    assert len(intent.intent_id) <= 128
    assert intent.cited_event_id is None


def test_modes_match_runner_and_cognition() -> None:
    assert CognitionCommunicationStrategyMode.DISABLED.value == "disabled"
    assert CognitionCommunicationStrategyMode.DETERMINISTIC.value == "deterministic"
    assert CommunicationStrategyMode.DISABLED.value == (
        CognitionCommunicationStrategyMode.DISABLED.value
    )
    assert CommunicationStrategyMode.DETERMINISTIC.value == (
        CognitionCommunicationStrategyMode.DETERMINISTIC.value
    )


def test_constructor_rejects_non_finite_confidence() -> None:
    with pytest.raises(ValueError, match="source_confidence: non_finite_confidence"):
        _intent(source_confidence=math.nan)


def test_constructor_rejects_more_than_eight_atoms() -> None:
    tokens = tuple(f"atom-{index}" for index in range(9))
    with pytest.raises(ValueError, match="source_atom_tokens: cap_exceeded"):
        _intent(source_atom_tokens=tokens)


def test_constructor_rejects_more_than_eight_factors() -> None:
    factors = tuple(CommunicationFactor)[:9]
    with pytest.raises(ValueError, match="factor_codes: cap_exceeded"):
        _intent(factor_codes=factors)


def test_constructor_rejects_unknown_strategy() -> None:
    with pytest.raises(ValueError, match="strategy: unknown_enum"):
        _intent(strategy="truthful")


def test_refusal_render_rejects_empty_predicates_with_a_source_token() -> None:
    with pytest.raises(ValueError, match="rendered_predicates: empty_refusal_render"):
        reject_empty_refusal_render(
            CommunicationStrategy.REFUSAL,
            rendered_predicates=(),
            rendered_object_tokens=("food",),
        )
    with pytest.raises(ValueError, match="empty_refusal_render"):
        _intent(
            strategy=CommunicationStrategy.REFUSAL,
            stance=SpeakerStance.REFUSE,
            divergence=CommunicationDivergence.REFUSED,
            rendered_predicates=(),
            rendered_object_tokens=("food",),
        )


def test_construction_log_names_owner_policy_and_strategy(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger=_LOGGER)
    intent = _intent(source_atom_tokens=("secret-place",))
    assert "communication_intent_built" in caplog.text
    assert "owner_id=agent-speaker" in caplog.text
    assert f"policy_version={COMMUNICATION_STRATEGY_POLICY_VERSION}" in caplog.text
    assert "strategy=truthful" in caplog.text
    assert "secret-place" not in caplog.text
    audit = CommunicationIntentAudit(
        intent_id=intent.intent_id,
        owner_id=intent.owner_id,
        recipient_id=intent.recipient_id,
        tick=intent.tick,
        strategy=intent.strategy,
        stance=intent.stance,
        divergence=intent.divergence,
        source_basis=intent.source_basis,
        source_confidence=intent.source_confidence,
        source_atom_tokens=intent.source_atom_tokens,
        cited_event_id=intent.cited_event_id,
        factor_codes=intent.factor_codes,
        delivered=intent.delivered,
        fallback_used=False,
    )
    assert audit.fallback_used is False


def test_strategy_module_has_no_trait_field() -> None:
    for word in ("liar", "honesty", "deception_propensity"):
        assert word not in _SOURCE
    assert "reliability" not in _SOURCE


def _profile(**values: float) -> DirectedRelationshipProfile:
    policy = RelationshipPolicyRef(policy_id="rel-v1", version="1")
    confidence = RelationshipConfidence(
        confidence=0.9, support_mass=0.9, contradiction_mass=0.0
    )
    dimensions = tuple(
        RelationshipDimensionState(
            dimension=kind,
            value=values.get(kind.value, 0.0),
            confidence=confidence,
            evidence=(),
            logical_tick=1,
            policy=policy,
        )
        for kind in (
            RelationshipDimension.TRUST,
            RelationshipDimension.FEAR,
            RelationshipDimension.RESENTMENT,
        )
    )
    return DirectedRelationshipProfile(
        relationship_id=RelationshipId("rel-listener"),
        source_id=_OWNER,
        target_id=_RECIPIENT,
        dimensions=dimensions,
        activation_state=RelationshipActivationState.ACTIVE,
        current_revision_id=RelationshipRevisionId("rrev-1"),
        revision_ordinal=1,
        created_tick=1,
        updated_tick=1,
        policy=policy,
    )


def _choose(**overrides: object):
    payload: dict[str, object] = {
        "owner_id": _OWNER,
        "recipient_id": _RECIPIENT,
        "recipient_entity_id": _LISTENER,
        "tick": 4,
        "source_basis": CommunicationSourceBasis.BELIEF,
        "source_confidence": 0.9,
        "source_atom_tokens": ("food", "water"),
        "owner_entity_id": _SPEAKER,
    }
    payload.update(overrides)
    intent, audit = choose_communication_strategy(**payload)  # type: ignore[arg-type]
    return intent, audit


def test_empty_atoms_stay_truthful_when_pressure_has_no_claim(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger=_LOGGER)
    intent, audit = _choose(
        source_atom_tokens=(),
        source_confidence=1.0,
        relationships=(_profile(fear=0.9, resentment=0.9, trust=0.1),),
        source_basis=CommunicationSourceBasis.UNREFERENCED,
    )
    assert intent.strategy is CommunicationStrategy.TRUTHFUL
    assert intent.stance is SpeakerStance.ASSERT_MATCH
    assert audit.fallback_used is False
    assert "communication_strategy_cap" in caplog.text
    assert "reason_code=cap_exceeded" in caplog.text
    assert "communication_strategy_chosen" in caplog.text
    assert "strategy=truthful" in caplog.text
    assert "stance=assert_match" in caplog.text
    plain, _plain_audit = _choose(source_atom_tokens=(), source_confidence=1.0)
    assert CommunicationFactor.NORMS_UNAVAILABLE in plain.factor_codes


def test_secret_with_harm_refuses_and_secret_alone_omits() -> None:
    harm = SubjectiveRisk(
        kind=SubjectiveRiskKind.PHYSICAL_HARM,
        severity=0.8,
        likelihood=0.8,
        confidence=0.8,
    )
    refused, _audit = _choose(
        epistemic_judgment=EpistemicJudgment.SECRET,
        risks=(harm,),
        source_atom_tokens=("food",),
    )
    assert refused.strategy is CommunicationStrategy.REFUSAL
    assert refused.stance is SpeakerStance.REFUSE
    assert refused.divergence is CommunicationDivergence.REFUSED
    assert refused.delivered is True
    omitted, _audit = _choose(
        epistemic_judgment=EpistemicJudgment.SECRET,
        risks=(),
        source_atom_tokens=("food",),
    )
    assert omitted.strategy is CommunicationStrategy.OMISSION
    assert omitted.delivered is False
    assert omitted.source_atom_tokens == ("food",)


def test_low_confidence_asks_and_exaggeration_inflates() -> None:
    uncertain, _audit = _choose(source_confidence=0.4, source_atom_tokens=("food",))
    assert uncertain.strategy is CommunicationStrategy.UNCERTAIN
    assert uncertain.stance is SpeakerStance.HEDGE
    exaggerated, _audit = _choose(
        source_confidence=0.8,
        source_atom_tokens=("food",),
        relationships=(_profile(resentment=0.5, trust=0.8),),
    )
    assert exaggerated.strategy is CommunicationStrategy.EXAGGERATION
    assert exaggerated.divergence is CommunicationDivergence.CONFIDENCE_INFLATED


def test_trust_selects_one_atom_and_a_stranger_stays_truthful() -> None:
    selected, _audit = _choose(
        relationships=(_profile(trust=0.2),),
        source_atom_tokens=("water", "food"),
    )
    assert selected.strategy is CommunicationStrategy.SELECTIVE_DISCLOSURE
    command, intent, _audit = apply_communication_strategy(
        owner_id=_OWNER,
        recipient_id=_RECIPIENT,
        recipient_entity_id=_LISTENER,
        speaker_id=_SPEAKER,
        tick=4,
        source_basis=CommunicationSourceBasis.BELIEF,
        source_confidence=0.9,
        source_atom_tokens=("water", "food"),
        action_kind="tell",
        relationships=(_profile(trust=0.2),),
    )
    assert intent.strategy is CommunicationStrategy.SELECTIVE_DISCLOSURE
    assert command is not None
    assert command.utterance.content.concepts == ("water",)
    other = _profile(resentment=0.9, trust=0.1, fear=0.9)
    stranger, _audit = _choose(
        relationships=(
            DirectedRelationshipProfile(
                relationship_id=other.relationship_id,
                source_id=_OWNER,
                target_id=AgentId("agent-other"),
                dimensions=other.dimensions,
                activation_state=other.activation_state,
                current_revision_id=other.current_revision_id,
                revision_ordinal=other.revision_ordinal,
                created_tick=other.created_tick,
                updated_tick=other.updated_tick,
                policy=other.policy,
            ),
        ),
        source_atom_tokens=("food", "water"),
    )
    assert stranger.strategy is CommunicationStrategy.TRUTHFUL
    assert CommunicationFactor.RELATIONSHIP_MISSING in stranger.factor_codes


def test_alternate_location_replaces_one_object_token() -> None:
    view = Observation(
        world_id=WorldId("world-1"),
        observer_id=_SPEAKER,
        revision=WorldRevision(0),
        locations=(ObservedLocation(entity_id=EntityId("loc-other"), name="other"),),
    )
    command, intent, _audit = apply_communication_strategy(
        owner_id=_OWNER,
        recipient_id=_RECIPIENT,
        recipient_entity_id=_LISTENER,
        speaker_id=_SPEAKER,
        tick=4,
        source_basis=CommunicationSourceBasis.BELIEF,
        source_confidence=0.9,
        source_atom_tokens=("loc-true",),
        action_kind="tell",
        relationships=(_profile(fear=0.5),),
        observation=view,
    )
    assert intent.strategy is CommunicationStrategy.DELIBERATE_FALSE_STATEMENT
    assert intent.source_atom_tokens == ("loc-true",)
    assert command is not None
    assert command.utterance.content.concepts == ("loc-other",)
    assert command.utterance.declared.sender_confidence == 0.9
    assert not hasattr(command.utterance, "strategy")


def test_refusal_render_drops_source_and_omission_has_no_command() -> None:
    harm = SubjectiveRisk(
        kind=SubjectiveRiskKind.PHYSICAL_HARM,
        severity=0.8,
        likelihood=0.8,
        confidence=0.8,
    )
    command, intent, _audit = apply_communication_strategy(
        owner_id=_OWNER,
        recipient_id=_RECIPIENT,
        recipient_entity_id=_LISTENER,
        speaker_id=_SPEAKER,
        tick=4,
        source_basis=CommunicationSourceBasis.BELIEF,
        source_confidence=0.9,
        source_atom_tokens=("food",),
        action_kind="tell",
        epistemic_judgment=EpistemicJudgment.SECRET,
        risks=(harm,),
    )
    assert intent.strategy is CommunicationStrategy.REFUSAL
    assert command is not None
    assert command.kind == "talk"
    assert command.utterance.content.concepts == ()
    assert command.utterance.content.relations[0].predicate == "decline"
    assert "food" not in command.utterance.content.text
    omitted = render_communication_intent(
        _choose(
            epistemic_judgment=EpistemicJudgment.SECRET,
            risks=(),
            source_atom_tokens=("food",),
        )[0],
        speaker_id=_SPEAKER,
        recipient_entity_id=_LISTENER,
        action_kind="tell",
    )
    assert omitted is None


def test_uncertain_render_is_ask_without_the_word_in_text() -> None:
    intent, _audit = _choose(source_confidence=0.4, source_atom_tokens=("food",))
    command = render_communication_intent(
        intent,
        speaker_id=_SPEAKER,
        recipient_entity_id=_LISTENER,
        action_kind="tell",
    )
    assert command is not None
    assert command.kind == "ask"
    assert command.utterance.content.concepts == ("food",)
    assert "uncertain" not in command.utterance.content.text
    assert command.utterance.content.relations[0].predicate == "uncertain"
    assert command.utterance.declared.sender_confidence < 1.0


def test_exaggeration_sets_sender_confidence_to_one() -> None:
    intent, _audit = _choose(
        source_confidence=0.8,
        source_atom_tokens=("food",),
        relationships=(_profile(resentment=0.5, trust=0.8),),
    )
    command = render_communication_intent(
        intent,
        speaker_id=_SPEAKER,
        recipient_entity_id=_LISTENER,
        action_kind="tell",
    )
    assert command is not None
    assert command.utterance.content.concepts == ("food",)
    assert command.utterance.declared.sender_confidence == 1.0
    assert confidence_band(command.utterance.declared.sender_confidence) == "high"


def test_norms_object_fails_closed_to_the_source() -> None:
    intent, audit = _choose(
        norms=object(),
        relationships=(_profile(fear=0.9),),
        source_atom_tokens=("loc-true",),
        observation=Observation(
            world_id=WorldId("world-1"),
            observer_id=_SPEAKER,
            revision=WorldRevision(0),
            locations=(
                ObservedLocation(entity_id=EntityId("loc-other"), name="other"),
            ),
        ),
    )
    assert intent.strategy is CommunicationStrategy.TRUTHFUL
    assert intent.source_atom_tokens == ("loc-true",)
    assert audit.fallback_used is True
    assert CommunicationFactor.NORMS_UNAVAILABLE not in intent.factor_codes


def test_world_authority_is_rejected() -> None:
    class WorldState:
        pass

    with pytest.raises(TypeError):
        _choose(observation=WorldState())


def test_disabled_select_leaves_intent_unset_and_hello_stays_truthful(
    caplog: pytest.LogCaptureFixture,
) -> None:
    from agents.cognition.communication import DeterministicSocialMessagePolicy
    from agents.cognition.models import DecisionMetadata, RetrievedMemoryContext
    from world.models import LifeStatus
    from world.observations import CoarseHealth, VisibleBody

    observation = Observation(
        observer_id=_SPEAKER,
        world_id=WorldId("world-1"),
        revision=WorldRevision(1),
        tick=2,
        visible_bodies=(
            VisibleBody(
                entity_id=_LISTENER,
                life_status=LifeStatus.ALIVE,
                coarse_health=CoarseHealth.STABLE,
            ),
        ),
        visibility=1.0,
    )
    memory = RetrievedMemoryContext(
        owner_id=_OWNER,
        memory_ids=(),
        belief_ids=(),
        confidence=1.0,
        decision_metadata=DecisionMetadata(candidate_count=0),
    )
    policy = DeterministicSocialMessagePolicy()
    with caplog.at_level(logging.DEBUG):
        disabled = policy.select(
            owner_id=_OWNER,
            speaker_id=_SPEAKER,
            observation=observation,
            memory=memory,
            strategy_mode=CognitionCommunicationStrategyMode.DISABLED,
        )
        enabled = policy.select(
            owner_id=_OWNER,
            speaker_id=_SPEAKER,
            observation=observation,
            memory=memory,
            strategy_mode=CognitionCommunicationStrategyMode.DETERMINISTIC,
        )
    assert disabled is not None
    assert disabled.intent is None
    assert disabled.command is not None
    assert enabled is not None
    assert enabled.intent is not None
    assert enabled.intent.strategy is CommunicationStrategy.TRUTHFUL
    assert enabled.command is not None
    assert type(enabled.command) is type(disabled.command)
    chosen = [
        record
        for record in caplog.records
        if record.name == "agents.cognition.communication_strategy"
        and "communication_strategy_chosen" in record.getMessage()
    ]
    assert len(chosen) == 1
    channel = [
        record.getMessage()
        for record in caplog.records
        if record.name == "agents.cognition.communication"
    ]
    assert any("communication_strategy_message" in item for item in channel)
    assert any("mode_disabled" in item for item in channel)
    assert all("hello" not in item for item in channel)
