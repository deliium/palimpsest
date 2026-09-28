"""Owner-scoped communicated memory formation from observed utterances.

Converts each owned ``ObservedCommunication`` into a fresh ``MemoryTrace`` with
transmission provenance. Never copies sender memory, reconstruction, belief, or
relationship state. Domain payloads stay out of logs.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final, Literal, Protocol

from agents.cognition.models import (
    ActionPlan,
    CognitiveLoopInput,
    InterpretedPerception,
    MemoryUpdateIntent,
    MemoryUpdateKind,
    RetrievedMemoryContext,
    SelectedIntention,
    episode_facts,
)
from agents.models import AgentId
from memory.models import (
    BeliefId,
    CommunicatedTransmissionMeta,
    ConceptMention,
    EntityMention,
    MemoryId,
    MemoryLineage,
    MemoryProvenance,
    MemoryRelation,
    MemorySituationContext,
    MemorySourceKind,
    MemoryTrace,
    MentionId,
    RelationEndpoint,
    RelationEndpointKind,
)
from world.actions import Ask, Talk, Tell
from world.communications import (
    CommunicationContent,
    CommunicationId,
    CommunicationRelation,
    CommunicationSourceBasis,
    DeclaredTransmission,
    StructuredUtterance,
    confidence_band,
    observation_allows_communication_target,
    origin_utterance,
    retell_utterance,
)
from world.identifiers import EntityId, EventId
from world.observations import (
    CONTENT_VISIBILITY_THRESHOLD,
    Observation,
    ObservedCommunication,
)

__all__ = [
    "COMMUNICATED_MEMORY_POLICY_VERSION",
    "SOCIAL_MESSAGE_POLICY_VERSION",
    "CommunicatedMemoryUpdateHook",
    "CompositeMemoryUpdateHook",
    "DeterministicSocialMessagePolicy",
    "PendingEvidenceAccumulator",
    "SocialMessageDecision",
    "SocialMessagePolicy",
    "build_communicated_memory_trace",
    "project_trust_inputs",
    "receiver_confidence_for_transmission",
]

_LOG: Final[logging.Logger] = logging.getLogger("agents.cognition.communication")
COMMUNICATED_MEMORY_POLICY_VERSION: Final[str] = "communicated-memory.v1"
SOCIAL_MESSAGE_POLICY_VERSION: Final[str] = "social-message.v1"
_HOP_ATTENUATION: Final[float] = 0.9
_SAFE_TALK_TEXT: Final[str] = "hello"
_SAFE_ASK_TEXT: Final[str] = "status?"
_SAFE_TELL_TEXT: Final[str] = "update"


def project_trust_inputs(profile: object | None) -> tuple[float, float]:
    """Project directed relationship trust into memory-neutral policy floats.

    Cognition owns the social dependency; memory never imports ``social``.
    Missing profiles yield cautious defaults (mid trust, low confidence).
    """
    if profile is None:
        return 0.5, 0.2
    from social.relationships import (
        DirectedRelationshipProfile,
        RelationshipDimension,
    )

    if type(profile) is not DirectedRelationshipProfile:
        raise TypeError("project_trust_inputs: invalid_profile")
    dims = profile.dimension_map()
    trust_state = dims.get(RelationshipDimension.TRUST)
    if trust_state is None:
        return 0.5, 0.2
    # Map signed trust [-1,1] to [0,1] for belief policy.
    trust = max(0.0, min(1.0, 0.5 + 0.5 * trust_state.value))
    return trust, trust_state.confidence.confidence


def identity_social_scale_factor(
    identity: object | None,
    counterpart_id: str,
) -> float:
    """Bound the trust multiplier from relationship and reliability views.

    Missing views yield ``1``. The factor stays inside the identity policy
    floor and ceiling.
    """
    from agents.cognition.identity import IdentityAspect, IdentityPolicy, IdentityState
    from memory.models import quantize_score

    if identity is None:
        return 1.0
    if type(identity) is not IdentityState:
        raise TypeError("identity_social_scale.identity: invalid_type")
    if not isinstance(counterpart_id, str) or not counterpart_id:
        raise TypeError("identity_social_scale.counterpart_id: invalid_type")
    policy = IdentityPolicy()
    floor = policy.social_scale_floor
    ceiling = policy.social_scale_ceiling
    span = ceiling - floor

    def _mapped(rate: float) -> float:
        return floor + span * rate

    relationship = [
        view.derived_rate
        for view in identity.views
        if view.aspect is IdentityAspect.RELATIONSHIP
        and view.evidence_token == counterpart_id
    ]
    reliability = [
        view.derived_rate
        for view in identity.views
        if view.aspect is IdentityAspect.RELIABILITY
    ]
    parts: list[float] = []
    if relationship:
        parts.append(_mapped(sum(relationship) / len(relationship)))
    if reliability:
        parts.append(_mapped(sum(reliability) / len(reliability)))
    if not parts:
        return 1.0
    factor = quantize_score(sum(parts) / len(parts))
    if factor < floor:
        return floor
    if factor > ceiling:
        return ceiling
    return factor


def scale_trust_for_identity(
    trust: float, *, identity: object | None, counterpart_id: str
) -> tuple[float, float]:
    """Return clamped trust and the factor. ``identity is None`` leaves trust."""
    from memory.models import quantize_score

    factor = identity_social_scale_factor(identity, counterpart_id)
    if identity is None:
        return trust, factor
    product = quantize_score(trust * factor)
    if product < 0.0:
        product = 0.0
    elif product > 1.0:
        product = 1.0
    return quantize_score(product), factor


def receiver_confidence_for_transmission(
    *, sender_confidence: float, hop_count: int
) -> float:
    """Deterministic receipt confidence from declared send confidence and hops."""
    if isinstance(sender_confidence, bool) or not isinstance(
        sender_confidence, (int, float)
    ):
        raise ValueError("sender_confidence: not_confidence")
    send = float(sender_confidence)
    if not math.isfinite(send) or send < 0.0 or send > 1.0:
        raise ValueError("sender_confidence: not_confidence")
    if isinstance(hop_count, bool) or not isinstance(hop_count, int) or hop_count < 0:
        raise ValueError("hop_count: not_nonneg_int")
    attenuated = send * (_HOP_ATTENUATION**hop_count)
    if not math.isfinite(attenuated):
        return 0.0
    return max(0.0, min(1.0, attenuated))


def _memory_id_for_communication(
    *,
    owner_id: AgentId,
    communication_id: str,
    source_event_id: EventId | None,
) -> MemoryId:
    event_token = "none" if source_event_id is None else source_event_id.value
    # Stable, opaque owner-scoped id; keep within stable-id length bounds.
    raw = f"cm-{owner_id.value}-{communication_id}-{event_token}"
    if len(raw) > 128:
        raw = raw[:128]
    return MemoryId(raw)


def build_communicated_memory_trace(
    *,
    owner_id: AgentId,
    observation_tick: int,
    observation_revision: object,
    message: ObservedCommunication,
    location_id: EntityId | None,
    receiver_confidence: float | None = None,
) -> MemoryTrace:
    """Build a fresh communicated trace from one owned observation delivery."""
    if type(message) is not ObservedCommunication:
        raise TypeError("message must be ObservedCommunication")
    declared = message.utterance.declared
    content = message.utterance.content
    receipt = (
        receiver_confidence
        if receiver_confidence is not None
        else receiver_confidence_for_transmission(
            sender_confidence=declared.sender_confidence,
            hop_count=declared.hop_count,
        )
    )
    transmission = CommunicatedTransmissionMeta(
        communication_id=declared.communication_id.value,
        action_kind=message.action_kind,
        hop_count=declared.hop_count,
        sender_confidence=declared.sender_confidence,
        receiver_confidence=receipt,
        content_fingerprint=message.utterance.content_fingerprint,
        parent_communication_id=(
            None
            if declared.parent_communication_id is None
            else declared.parent_communication_id.value
        ),
        source_agent_chain=tuple(declared.source_agent_chain),
        transmission_root_id=declared.root_communication_id.value,
        policy_version=COMMUNICATED_MEMORY_POLICY_VERSION,
    )
    concepts: list[ConceptMention] = []
    for index, concept in enumerate(content.concepts):
        concepts.append(
            ConceptMention(
                mention_id=MentionId(f"c-{index}"),
                concept=concept,
            )
        )
    # Speaker as grounded entity mention (opaque body id, not memory lineage).
    entities: list[EntityMention] = [
        EntityMention(
            mention_id=MentionId("e-speaker"),
            label="speaker",
            entity_id=message.speaker_id,
        )
    ]
    relations: list[MemoryRelation] = []
    for index, relation in enumerate(content.relations):
        subject_mention = MentionId(f"c-rel-s-{index}")
        object_mention = MentionId(f"c-rel-o-{index}")
        concepts.append(
            ConceptMention(mention_id=subject_mention, concept=relation.subject)
        )
        concepts.append(
            ConceptMention(mention_id=object_mention, concept=relation.object)
        )
        relations.append(
            MemoryRelation(
                relation_id=MentionId(f"r-{index}"),
                predicate=relation.predicate,
                subject=RelationEndpoint(
                    kind=RelationEndpointKind.CONCEPT,
                    mention_id=subject_mention,
                ),
                object=RelationEndpoint(
                    kind=RelationEndpointKind.CONCEPT,
                    mention_id=object_mention,
                ),
            )
        )
    source_tick = message.provenance.source_tick
    memory_id = _memory_id_for_communication(
        owner_id=owner_id,
        communication_id=declared.communication_id.value,
        source_event_id=message.provenance.source_event_id,
    )
    from world.identifiers import WorldRevision

    if type(observation_revision) is not WorldRevision:
        raise TypeError("observation_revision must be WorldRevision")
    return MemoryTrace(
        memory_id=memory_id,
        owner_id=owner_id,
        world_revision=observation_revision,
        concepts=tuple(concepts),
        entities=tuple(entities),
        relations=tuple(relations),
        context=MemorySituationContext(
            location_id=location_id,
            tags=("communicated", message.action_kind),
        ),
        emotional_salience=min(1.0, 0.2 + 0.1 * declared.hop_count),
        confidence=receipt,
        provenance=MemoryProvenance(
            kind=MemorySourceKind.COMMUNICATED,
            source_tick=source_tick,
            observed_source_id=message.provenance.source_event_id,
            speaker_id=message.speaker_id,
            transmission=transmission,
        ),
        created_tick=observation_tick,
        source_tick=source_tick,
        last_access_tick=observation_tick,
        access_count=0,
        lineage=MemoryLineage(),
    )


class CommunicatedMemoryUpdateHook:
    """Propose WRITE_MEMORY intents for each newly observed communication."""

    __slots__ = ()

    async def propose_updates(
        self,
        loop_input: CognitiveLoopInput,
        plan: ActionPlan,
        perception: InterpretedPerception,
        memory: RetrievedMemoryContext,
        intention: SelectedIntention,
        self_state: object | None = None,
    ) -> tuple[MemoryUpdateIntent, ...]:
        _ = plan, intention, memory, self_state
        owner = loop_input.agent_id
        observation = loop_input.observation
        tick = observation.tick
        seen_ids: set[str] = set()
        if loop_input.snapshot is not None:
            for trace in loop_input.snapshot.memories:
                if trace.owner_id != owner:
                    continue
                meta = trace.provenance.transmission
                if meta is not None:
                    seen_ids.add(meta.communication_id)
                if trace.provenance.observed_source_id is not None:
                    seen_ids.add(f"evt:{trace.provenance.observed_source_id.value}")

        intents: list[MemoryUpdateIntent] = []
        proposed = 0
        deduped = 0
        for message in observation.communications:
            if type(message) is not ObservedCommunication:
                _LOG.error(
                    "communicated_memory_rejected",
                    extra={
                        "cognition": {
                            "owner_id": owner.value,
                            "tick": tick,
                            "reason_code": "invalid_message_type",
                        }
                    },
                )
                continue
            if message.listener_id != observation.observer_id:
                _LOG.warning(
                    "communicated_memory_rejected",
                    extra={
                        "cognition": {
                            "owner_id": owner.value,
                            "tick": tick,
                            "reason_code": "listener_mismatch",
                            "immediate_source_id": message.speaker_id.value,
                        }
                    },
                )
                continue
            try:
                chain = message.utterance.declared.source_agent_chain
                if not chain or chain[-1] != message.speaker_id:
                    raise ValueError("malformed_chain")
            except (TypeError, ValueError):
                _LOG.warning(
                    "communicated_memory_rejected",
                    extra={
                        "cognition": {
                            "owner_id": owner.value,
                            "tick": tick,
                            "reason_code": "malformed_chain",
                            "immediate_source_id": message.speaker_id.value,
                        }
                    },
                )
                continue
            comm_id = message.utterance.declared.communication_id.value
            event_key = (
                None
                if message.provenance.source_event_id is None
                else f"evt:{message.provenance.source_event_id.value}"
            )
            if comm_id in seen_ids or (event_key is not None and event_key in seen_ids):
                deduped += 1
                _LOG.debug(
                    "communicated_memory_deduped",
                    extra={
                        "cognition": {
                            "owner_id": owner.value,
                            "tick": tick,
                            "communication_id": comm_id,
                            "event_id": (
                                None
                                if message.provenance.source_event_id is None
                                else message.provenance.source_event_id.value
                            ),
                            "immediate_source_id": message.speaker_id.value,
                            "action_kind": message.action_kind,
                            "hop_count": message.utterance.declared.hop_count,
                            "deduplication_result": "duplicate",
                        }
                    },
                )
                continue
            try:
                trace = build_communicated_memory_trace(
                    owner_id=owner,
                    observation_tick=tick,
                    observation_revision=observation.revision,
                    message=message,
                    location_id=perception.location_id,
                )
            except (TypeError, ValueError) as exc:
                _LOG.error(
                    "communicated_memory_rejected",
                    extra={
                        "cognition": {
                            "owner_id": owner.value,
                            "tick": tick,
                            "reason_code": "trace_build_failed",
                            "immediate_source_id": message.speaker_id.value,
                            "detail": type(exc).__name__,
                        }
                    },
                )
                continue
            seen_ids.add(comm_id)
            if event_key is not None:
                seen_ids.add(event_key)
            proposed += 1
            intents.append(
                MemoryUpdateIntent(
                    owner_id=owner,
                    kind=MemoryUpdateKind.WRITE_MEMORY,
                    memory=trace,
                )
            )
            _LOG.debug(
                "communicated_memory_proposed",
                extra={
                    "cognition": {
                        "owner_id": owner.value,
                        "tick": tick,
                        "communication_id": comm_id,
                        "event_id": (
                            None
                            if message.provenance.source_event_id is None
                            else message.provenance.source_event_id.value
                        ),
                        "immediate_source_id": message.speaker_id.value,
                        "action_kind": message.action_kind,
                        "hop_count": message.utterance.declared.hop_count,
                        "sender_confidence_band": confidence_band(
                            message.utterance.declared.sender_confidence
                        ),
                        "receiver_confidence_band": confidence_band(trace.confidence),
                        "deduplication_result": "new",
                        "policy_version": COMMUNICATED_MEMORY_POLICY_VERSION,
                    }
                },
            )
        _LOG.debug(
            "communicated_memory_batch",
            extra={
                "cognition": {
                    "owner_id": owner.value,
                    "tick": tick,
                    "proposed_count": proposed,
                    "deduped_count": deduped,
                    "applied_candidate_count": len(intents),
                    "policy_version": COMMUNICATED_MEMORY_POLICY_VERSION,
                }
            },
        )
        return tuple(intents)


class PendingEvidenceAccumulator:
    """Typed pending-trace accumulator for one cognition update pass.

    Traces proposed by earlier hooks (direct/communicated) are recorded here so
    later hooks can form belief/relationship revisions in the same atomic batch
    without mutating stores between hooks.
    """

    __slots__ = ("_traces",)

    def __init__(self) -> None:
        self._traces: list[MemoryTrace] = []

    def clear(self) -> None:
        self._traces.clear()

    def record(self, trace: MemoryTrace) -> None:
        if type(trace) is not MemoryTrace:
            raise TypeError("PendingEvidenceAccumulator.record: invalid_type")
        self._traces.append(trace)

    def record_from_intents(self, intents: Sequence[MemoryUpdateIntent]) -> int:
        recorded = 0
        for intent in intents:
            if type(intent) is not MemoryUpdateIntent:
                raise TypeError("PendingEvidenceAccumulator: invalid_intent")
            if (
                intent.kind is MemoryUpdateKind.WRITE_MEMORY
                and intent.memory is not None
            ):
                self.record(intent.memory)
                recorded += 1
        return recorded

    def traces(self) -> tuple[MemoryTrace, ...]:
        return tuple(self._traces)

    def __repr__(self) -> str:
        return f"PendingEvidenceAccumulator(trace_count={len(self._traces)})"


class CompositeMemoryUpdateHook:
    """Run memory-update hooks in order and concatenate proposed intents.

    When a shared ``PendingEvidenceAccumulator`` is supplied, each WRITE_MEMORY
    intent is recorded before the next hook runs so belief/relationship hooks
    can consume same-tick pending evidence.
    """

    __slots__ = ("_hooks", "_pending")

    def __init__(
        self,
        hooks: Sequence[object],
        *,
        pending: PendingEvidenceAccumulator | None = None,
    ) -> None:
        if isinstance(hooks, (str, bytes)) or not isinstance(hooks, Sequence):
            raise TypeError("hooks must be an ordered sequence")
        if isinstance(hooks, (set, frozenset)):
            raise TypeError("hooks must be an ordered sequence")
        self._hooks = tuple(hooks)
        self._pending = pending if pending is not None else PendingEvidenceAccumulator()

    @property
    def pending(self) -> PendingEvidenceAccumulator:
        return self._pending

    async def propose_updates(
        self,
        loop_input: CognitiveLoopInput,
        plan: ActionPlan,
        perception: InterpretedPerception,
        memory: RetrievedMemoryContext,
        intention: SelectedIntention,
        self_state: object | None = None,
    ) -> tuple[MemoryUpdateIntent, ...]:
        self._pending.clear()
        intents: list[MemoryUpdateIntent] = []
        for hook in self._hooks:
            propose = getattr(hook, "propose_updates", None)
            if propose is None:
                raise TypeError("hook missing propose_updates")
            batch = await propose(
                loop_input, plan, perception, memory, intention, self_state
            )
            if not isinstance(batch, tuple):
                raise TypeError("propose_updates must return a tuple")
            for item in batch:
                if type(item) is not MemoryUpdateIntent:
                    raise TypeError(
                        "propose_updates entries must be MemoryUpdateIntent"
                    )
                intents.append(item)
            recorded = self._pending.record_from_intents(batch)
            if recorded:
                _LOG.debug(
                    "pending_evidence_recorded",
                    extra={
                        "cognition": {
                            "owner_id": loop_input.agent_id.value,
                            "tick": perception.tick,
                            "recorded_count": recorded,
                            "pending_count": len(self._pending.traces()),
                            "status": "accumulated",
                        }
                    },
                )
        return tuple(intents)


@dataclass(frozen=True, slots=True)
class SocialMessageDecision:
    """One validated social command plus metadata-only selection diagnostics."""

    command: Talk | Ask | Tell
    action_kind: Literal["talk", "ask", "tell"]
    source_basis: CommunicationSourceBasis
    hop_count: int
    sender_confidence: float
    fallback: bool
    rejection_code: str | None = None
    candidate_count: int = 0

    def __repr__(self) -> str:
        return (
            f"SocialMessageDecision(action_kind={self.action_kind!r}, "
            f"source_basis={self.source_basis.value!r}, "
            f"hop_count={self.hop_count}, "
            f"confidence_band={confidence_band(self.sender_confidence)!r}, "
            f"fallback={self.fallback}, "
            f"candidate_count={self.candidate_count})"
        )


_EPISTEMIC_CONCEPTS: Final[frozenset[str]] = frozenset(
    {"food", "water", "rest", "danger"}
)


def _allowlisted_claim_token(claim: object) -> str | None:
    from memory import BeliefValueKind, SemanticBelief

    if type(claim) is not SemanticBelief:
        return None
    if claim.claim.predicate in _EPISTEMIC_CONCEPTS:
        return claim.claim.predicate
    value = claim.claim.value
    if value.kind is BeliefValueKind.TEXT and value.text_value in _EPISTEMIC_CONCEPTS:
        return value.text_value
    return None


def _select_belief_utterance(
    *,
    owner_id: AgentId,
    speaker_id: EntityId,
    recipient: EntityId,
    observation: Observation,
    beliefs: Sequence[object],
    mind: object | None,
    act_pref: str,
    selected_ids: frozenset[object],
    candidate_count: int,
) -> SocialMessageDecision | None:
    """Tell the first unblocked belief, or ask when the judgment is uncertain."""
    from agents.cognition.epistemic import (
        EpistemicJudgment,
        default_epistemic_policy,
        epistemic_disclosure,
        epistemic_proposition_ref,
    )
    from agents.cognition.theory_of_mind import TheoryOfMind
    from memory import SemanticBelief

    _LOG.debug(
        "epistemic_message_select_start owner_id=%s tick=%s",
        owner_id.value,
        observation.tick,
    )
    policy = default_epistemic_policy()
    has_ledger = type(mind) is TheoryOfMind and bool(mind.attributions)
    if mind is None or type(mind) is not TheoryOfMind:
        _LOG.debug(
            "epistemic_message_skipped owner_id=%s tick=%s status=skipped",
            owner_id.value,
            observation.tick,
        )
    elif not has_ledger:
        _LOG.debug(
            "epistemic_message_skipped owner_id=%s tick=%s reason=empty_ledger",
            owner_id.value,
            observation.tick,
        )
    blocking = {
        EpistemicJudgment.ALREADY_KNOWN,
        EpistemicJudgment.SECRET,
        EpistemicJudgment.CONTRADICTORY,
    }
    for claim in beliefs:
        if type(claim) is not SemanticBelief:
            raise TypeError("beliefs must be SemanticBelief")
        if claim.confidence.confidence < 0.5:
            continue
        proposition = epistemic_proposition_ref(belief_id=claim.belief_id.value)
        disclosure = (
            epistemic_disclosure(mind, recipient.value, proposition, policy)
            if has_ledger and type(mind) is TheoryOfMind
            else None
        )
        judgment = None if disclosure is None else disclosure.judgment
        band = confidence_band(
            claim.confidence.confidence if disclosure is None else disclosure.confidence
        )
        if judgment in blocking:
            _LOG.debug(
                "epistemic_message owner_id=%s tick=%s action_kind=%s "
                "recipient_id=%s judgment=%s confidence_band=%s",
                owner_id.value,
                observation.tick,
                "tell",
                recipient.value,
                judgment.value,
                band,
            )
            continue
        if judgment is EpistemicJudgment.UNCERTAIN:
            token = _allowlisted_claim_token(claim)
            _LOG.debug(
                "epistemic_message owner_id=%s tick=%s action_kind=%s "
                "recipient_id=%s judgment=%s confidence_band=%s",
                owner_id.value,
                observation.tick,
                "ask" if token is not None else "tell",
                recipient.value,
                judgment.value,
                band,
            )
            if token is None:
                return None
            utterance = origin_utterance(
                text=token,
                speaker_id=speaker_id,
                communication_id=f"plan-ask-{claim.belief_id.value}",
                sender_confidence=claim.confidence.confidence,
                source_basis=CommunicationSourceBasis.UNREFERENCED,
                concepts=(token,),
            )
            return SocialMessageDecision(
                command=Ask(recipient_id=recipient, utterance=utterance),
                action_kind="ask",
                source_basis=CommunicationSourceBasis.UNREFERENCED,
                hop_count=0,
                sender_confidence=claim.confidence.confidence,
                fallback=False,
                candidate_count=candidate_count,
            )
        if judgment is EpistemicJudgment.NEW:
            _LOG.debug(
                "epistemic_message owner_id=%s tick=%s action_kind=%s "
                "recipient_id=%s judgment=%s confidence_band=%s",
                owner_id.value,
                observation.tick,
                "tell",
                recipient.value,
                judgment.value,
                band,
            )
        conf = claim.confidence.confidence
        utterance = origin_utterance(
            text=f"claim:{claim.belief_id.value}",
            speaker_id=speaker_id,
            communication_id=f"plan-tell-{claim.belief_id.value}",
            sender_confidence=conf,
            source_basis=CommunicationSourceBasis.BELIEF,
            concepts=(claim.belief_id.value,),
        )
        _LOG.debug(
            "social_message_belief_testify",
            extra={
                "cognition": {
                    "owner_id": owner_id.value,
                    "policy_version": SOCIAL_MESSAGE_POLICY_VERSION,
                    "reason_code": (
                        "emotion_prefer_tell"
                        if act_pref == "tell" and not selected_ids
                        else "selected_belief_testify"
                    ),
                    "selected_belief_count": len(selected_ids),
                    "confidence_band": confidence_band(conf),
                }
            },
        )
        return SocialMessageDecision(
            command=Tell(recipient_id=recipient, utterance=utterance),
            action_kind="tell",
            source_basis=CommunicationSourceBasis.BELIEF,
            hop_count=0,
            sender_confidence=conf,
            fallback=False,
            candidate_count=candidate_count,
        )
    return None


class SocialMessagePolicy(Protocol):
    """Replaceable port for structured talk/ask/tell generation."""

    def select(
        self,
        *,
        owner_id: AgentId,
        speaker_id: EntityId,
        observation: Observation,
        memory: RetrievedMemoryContext,
        preferred_recipient_id: EntityId | None = None,
        snapshot_memories: Sequence[MemoryTrace] = (),
        selected_belief_ids: Sequence[BeliefId] = (),
        emotional_state: object | None = None,
        mind: object | None = None,
    ) -> SocialMessageDecision | None: ...


class DeterministicSocialMessagePolicy:
    """Deterministic talk/ask/tell selection from owner-scoped evidence only."""

    __slots__ = ()

    def select(
        self,
        *,
        owner_id: AgentId,
        speaker_id: EntityId,
        observation: Observation,
        memory: RetrievedMemoryContext,
        preferred_recipient_id: EntityId | None = None,
        snapshot_memories: Sequence[MemoryTrace] = (),
        selected_belief_ids: Sequence[BeliefId] = (),
        emotional_state: object | None = None,
        mind: object | None = None,
    ) -> SocialMessageDecision | None:
        recipients = _eligible_recipients(observation)
        candidate_count = len(recipients)
        if not recipients:
            _LOG.warning(
                "social_message_rejected",
                extra={
                    "cognition": {
                        "owner_id": owner_id.value,
                        "policy_version": SOCIAL_MESSAGE_POLICY_VERSION,
                        "reason_code": "no_eligible_recipient",
                        "candidate_count": 0,
                    }
                },
            )
            _LOG.warning(
                "theory_of_mind_message_skipped owner_id=%s tick=%s "
                "reason_code=no_eligible_recipient",
                owner_id.value,
                observation.tick,
            )
            return None
        from agents.cognition.theory_of_mind import MindMessageHint, mind_message_hint

        caller_recipient = preferred_recipient_id
        hint = mind_message_hint(
            mind,
            recipient_ids=tuple(item.value for item in recipients),
        )
        if type(hint) is MindMessageHint:
            if hint.excluded_front_id is not None and recipients:
                front = recipients[0].value
                if (
                    front == hint.excluded_front_id
                    and front != hint.preferred_recipient_id
                ):
                    recipients = (*recipients[1:], recipients[0])
            if caller_recipient is None and hint.preferred_recipient_id is not None:
                preferred = next(
                    (
                        item
                        for item in recipients
                        if item.value == hint.preferred_recipient_id
                    ),
                    None,
                )
                if preferred is not None:
                    preferred_recipient_id = preferred
            _LOG.debug(
                "theory_of_mind_message owner_id=%s tick=%s action_kind=%s "
                "recipient_id=%s aspect=%s concept_count=%s confidence_band=%s "
                "mind_present=%s",
                owner_id.value,
                observation.tick,
                "ask" if hint.concept is not None else "unspecified",
                hint.preferred_recipient_id,
                hint.aspect,
                0 if hint.concept is None else 1,
                confidence_band(hint.confidence),
                True,
            )
        elif mind is None:
            _LOG.warning(
                "theory_of_mind_message_skipped owner_id=%s tick=%s status=skipped",
                owner_id.value,
                observation.tick,
            )
        recipient = preferred_recipient_id
        if recipient is None or recipient not in recipients:
            recipient = recipients[0]
        selected_ids = frozenset(selected_belief_ids)
        beliefs = sorted(
            (
                b
                for b in memory.semantic_beliefs
                if b.owner_id == owner_id
                and (not selected_ids or b.belief_id in selected_ids)
            ),
            key=lambda item: (
                -item.confidence.confidence,
                item.belief_id.value,
            ),
        )
        reconstructions = sorted(
            (r for r in episode_facts(memory) if r.owner_id == owner_id),
            key=lambda item: (-item.confidence, item.episode_id),
        )
        communicated = _owned_communicated_traces(
            owner_id=owner_id,
            snapshot_memories=snapshot_memories,
        )
        # Tell from beliefs only when the caller selected specific belief IDs
        # (share-intent). Bare COMMUNICATE stays talk/ask/retell/recon grounded.
        # Anger-biased emotion may prefer tell without explicit belief selection.
        from agents.cognition.emotion_bias import social_act_preference
        from agents.cognition.models import EmotionalStateEvaluation

        emotion_eval: EmotionalStateEvaluation | None = None
        if emotional_state is not None:
            if type(emotional_state) is not EmotionalStateEvaluation:
                raise TypeError("emotional_state must be EmotionalStateEvaluation")
            emotion_eval = emotional_state
        act_pref = social_act_preference(emotion_eval)

        decision: SocialMessageDecision | None = None
        allow_belief_tell = bool(selected_ids) or act_pref == "tell"
        if allow_belief_tell and beliefs:
            decision = _select_belief_utterance(
                owner_id=owner_id,
                speaker_id=speaker_id,
                recipient=recipient,
                observation=observation,
                beliefs=beliefs,
                mind=mind,
                act_pref=act_pref,
                selected_ids=selected_ids,
                candidate_count=candidate_count,
            )
        elif not selected_ids and beliefs and beliefs[0].confidence.confidence >= 0.5:
            _LOG.debug(
                "social_message_belief_skipped",
                extra={
                    "cognition": {
                        "owner_id": owner_id.value,
                        "policy_version": SOCIAL_MESSAGE_POLICY_VERSION,
                        "reason_code": "belief_testify_requires_selection",
                        "belief_count": len(beliefs),
                    }
                },
            )

        if (
            decision is None
            and type(hint) is MindMessageHint
            and hint.concept is not None
            and not selected_ids
        ):
            utterance = origin_utterance(
                text=_SAFE_ASK_TEXT,
                speaker_id=speaker_id,
                communication_id=f"plan-ask-{hint.hypothesis_id}",
                sender_confidence=hint.confidence,
                source_basis=CommunicationSourceBasis.UNREFERENCED,
                concepts=(hint.concept,),
            )
            decision = SocialMessageDecision(
                command=Ask(recipient_id=recipient, utterance=utterance),
                action_kind="ask",
                source_basis=CommunicationSourceBasis.UNREFERENCED,
                hop_count=0,
                sender_confidence=hint.confidence,
                fallback=False,
                candidate_count=candidate_count,
            )
        elif decision is None and act_pref == "ask":
            utterance = origin_utterance(
                text=_SAFE_ASK_TEXT,
                speaker_id=speaker_id,
                communication_id="plan-ask-emotion",
                sender_confidence=0.5,
                source_basis=CommunicationSourceBasis.DIRECT_OBSERVATION,
                concepts=(),
            )
            decision = SocialMessageDecision(
                command=Ask(recipient_id=recipient, utterance=utterance),
                action_kind="ask",
                source_basis=CommunicationSourceBasis.DIRECT_OBSERVATION,
                hop_count=0,
                sender_confidence=utterance.declared.sender_confidence,
                fallback=False,
                candidate_count=candidate_count,
            )
        elif decision is None and act_pref == "talk":
            utterance = origin_utterance(
                text=_SAFE_TALK_TEXT,
                speaker_id=speaker_id,
                communication_id="plan-talk-emotion",
                sender_confidence=0.5,
                source_basis=CommunicationSourceBasis.DIRECT_OBSERVATION,
                concepts=(),
            )
            decision = SocialMessageDecision(
                command=Talk(recipient_id=recipient, utterance=utterance),
                action_kind="talk",
                source_basis=CommunicationSourceBasis.DIRECT_OBSERVATION,
                hop_count=0,
                sender_confidence=utterance.declared.sender_confidence,
                fallback=False,
                candidate_count=candidate_count,
            )

        if decision is None:
            if reconstructions and reconstructions[0].confidence < 0.55:
                recon = reconstructions[0]
                utterance = origin_utterance(
                    text=_SAFE_ASK_TEXT,
                    speaker_id=speaker_id,
                    communication_id=f"plan-ask-{recon.episode_id}",
                    sender_confidence=max(0.2, 1.0 - recon.confidence),
                    source_basis=CommunicationSourceBasis.RECONSTRUCTED_MEMORY,
                    concepts=tuple(item.concept for item in recon.concepts[:4]),
                )
                decision = SocialMessageDecision(
                    command=Ask(recipient_id=recipient, utterance=utterance),
                    action_kind="ask",
                    source_basis=CommunicationSourceBasis.RECONSTRUCTED_MEMORY,
                    hop_count=0,
                    sender_confidence=utterance.declared.sender_confidence,
                    fallback=False,
                    candidate_count=candidate_count,
                )
            else:
                retell = _try_retell_from_communicated(
                    owner_id=owner_id,
                    speaker_id=speaker_id,
                    recipient_id=recipient,
                    traces=communicated,
                    candidate_count=candidate_count,
                )
                if retell is not None:
                    decision = retell
                elif reconstructions:
                    recon = reconstructions[0]
                    concepts = tuple(item.concept for item in recon.concepts[:4])
                    utterance = origin_utterance(
                        text=_SAFE_TELL_TEXT if not concepts else concepts[0],
                        speaker_id=speaker_id,
                        communication_id=(f"plan-retell-{recon.episode_id}"),
                        sender_confidence=recon.confidence,
                        source_basis=CommunicationSourceBasis.RECONSTRUCTED_MEMORY,
                        concepts=concepts,
                    )
                    decision = SocialMessageDecision(
                        command=Tell(recipient_id=recipient, utterance=utterance),
                        action_kind="tell",
                        source_basis=CommunicationSourceBasis.RECONSTRUCTED_MEMORY,
                        hop_count=0,
                        sender_confidence=recon.confidence,
                        fallback=False,
                        candidate_count=candidate_count,
                    )
                else:
                    utterance = origin_utterance(
                        text=_SAFE_TALK_TEXT,
                        speaker_id=speaker_id,
                        communication_id="plan-social-1",
                        sender_confidence=1.0,
                        source_basis=CommunicationSourceBasis.UNREFERENCED,
                    )
                    decision = SocialMessageDecision(
                        command=Talk(recipient_id=recipient, utterance=utterance),
                        action_kind="talk",
                        source_basis=CommunicationSourceBasis.UNREFERENCED,
                        hop_count=0,
                        sender_confidence=1.0,
                        fallback=True,
                        candidate_count=candidate_count,
                    )
        _LOG.debug(
            "social_message_selected",
            extra={
                "cognition": {
                    "owner_id": owner_id.value,
                    "recipient_id": recipient.value,
                    "policy_version": SOCIAL_MESSAGE_POLICY_VERSION,
                    "action_kind": decision.action_kind,
                    "source_basis": decision.source_basis.value,
                    "candidate_count": candidate_count,
                    "hop_count": decision.hop_count,
                    "confidence_band": confidence_band(decision.sender_confidence),
                    "fallback": decision.fallback,
                }
            },
        )
        return decision


def _owned_communicated_traces(
    *,
    owner_id: AgentId,
    snapshot_memories: Sequence[MemoryTrace],
) -> tuple[MemoryTrace, ...]:
    owned = [
        trace
        for trace in snapshot_memories
        if trace.owner_id == owner_id
        and trace.provenance.kind is MemorySourceKind.COMMUNICATED
        and trace.provenance.transmission is not None
        and trace.forgotten_at_tick is None
    ]
    owned.sort(
        key=lambda item: (
            -item.confidence,
            -(
                0
                if item.provenance.transmission is None
                else item.provenance.transmission.hop_count
            ),
            item.memory_id.value,
        )
    )
    return tuple(owned)


def _utterance_from_communicated_trace(
    trace: MemoryTrace,
) -> StructuredUtterance | None:
    """Rebuild speaker-declared prior utterance from an owned communicated trace."""
    transmission = trace.provenance.transmission
    if transmission is None:
        return None
    concepts = tuple(
        mention.concept
        for mention in trace.concepts
        if mention.mention_id.value.startswith("c-")
        and not mention.mention_id.value.startswith("c-rel-")
    )[:8]
    concept_by_id = {mention.mention_id: mention.concept for mention in trace.concepts}
    relations: list[CommunicationRelation] = []
    for relation in trace.relations[:4]:
        subject = concept_by_id.get(relation.subject.mention_id)
        obj = concept_by_id.get(relation.object.mention_id)
        if subject is None or obj is None:
            continue
        relations.append(
            CommunicationRelation(
                subject=subject,
                predicate=relation.predicate,
                object=obj,
            )
        )
    text = concepts[0] if concepts else _SAFE_TELL_TEXT
    parent_id = (
        None
        if transmission.parent_communication_id is None
        else CommunicationId(transmission.parent_communication_id)
    )
    return StructuredUtterance(
        content=CommunicationContent(
            text=text,
            concepts=concepts,
            relations=tuple(relations),
        ),
        declared=DeclaredTransmission(
            communication_id=CommunicationId(transmission.communication_id),
            immediate_source_id=(
                trace.provenance.speaker_id
                if trace.provenance.speaker_id is not None
                else transmission.source_agent_chain[-1]
            ),
            parent_communication_id=parent_id,
            root_communication_id=CommunicationId(transmission.transmission_root_id),
            source_agent_chain=tuple(transmission.source_agent_chain),
            hop_count=transmission.hop_count,
            sender_confidence=transmission.sender_confidence,
            source_basis=CommunicationSourceBasis.RECONSTRUCTED_MEMORY,
        ),
    )


def _try_retell_from_communicated(
    *,
    owner_id: AgentId,
    speaker_id: EntityId,
    recipient_id: EntityId,
    traces: Sequence[MemoryTrace],
    candidate_count: int,
) -> SocialMessageDecision | None:
    for trace in traces:
        prior = _utterance_from_communicated_trace(trace)
        if prior is None:
            continue
        if speaker_id in prior.declared.source_agent_chain:
            _LOG.debug(
                "social_message_retell_skipped",
                extra={
                    "cognition": {
                        "owner_id": owner_id.value,
                        "policy_version": SOCIAL_MESSAGE_POLICY_VERSION,
                        "reason_code": "speaker_already_in_chain",
                        "hop_count": prior.declared.hop_count,
                    }
                },
            )
            continue
        try:
            utterance = retell_utterance(
                prior=prior,
                speaker_id=speaker_id,
                communication_id=f"plan-hop-{trace.memory_id.value}",
                sender_confidence=trace.confidence,
                source_basis=CommunicationSourceBasis.RECONSTRUCTED_MEMORY,
            )
        except (TypeError, ValueError) as exc:
            _LOG.warning(
                "social_message_retell_rejected",
                extra={
                    "cognition": {
                        "owner_id": owner_id.value,
                        "policy_version": SOCIAL_MESSAGE_POLICY_VERSION,
                        "reason_code": type(exc).__name__,
                        "hop_count": prior.declared.hop_count,
                    }
                },
            )
            continue
        return SocialMessageDecision(
            command=Tell(recipient_id=recipient_id, utterance=utterance),
            action_kind="tell",
            source_basis=CommunicationSourceBasis.RECONSTRUCTED_MEMORY,
            hop_count=utterance.declared.hop_count,
            sender_confidence=utterance.declared.sender_confidence,
            fallback=False,
            candidate_count=candidate_count,
        )
    return None


def _eligible_recipients(observation: Observation) -> tuple[EntityId, ...]:
    visible = tuple(
        sorted(
            (body.entity_id for body in observation.visible_bodies),
            key=lambda item: item.value,
        )
    )
    allowed: list[EntityId] = []
    for recipient in visible:
        if observation_allows_communication_target(
            visibility=observation.visibility,
            visible_body_ids=visible,
            recipient_id=recipient,
            visibility_threshold=CONTENT_VISIBILITY_THRESHOLD,
        ):
            allowed.append(recipient)
    return tuple(allowed)
