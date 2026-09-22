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
        transmission_root_id=(
            declared.communication_id.value
            if declared.hop_count == 0
            else (
                declared.parent_communication_id.value
                if declared.parent_communication_id is not None
                and declared.hop_count == 1
                else (
                    declared.parent_communication_id.value
                    if declared.parent_communication_id is not None
                    else declared.communication_id.value
                )
            )
        ),
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
    ) -> tuple[MemoryUpdateIntent, ...]:
        _ = plan, intention, memory
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


class CompositeMemoryUpdateHook:
    """Run memory-update hooks in order and concatenate proposed intents."""

    __slots__ = ("_hooks",)

    def __init__(self, hooks: Sequence[object]) -> None:
        if isinstance(hooks, (str, bytes)) or not isinstance(hooks, Sequence):
            raise TypeError("hooks must be an ordered sequence")
        if isinstance(hooks, (set, frozenset)):
            raise TypeError("hooks must be an ordered sequence")
        self._hooks = tuple(hooks)

    async def propose_updates(
        self,
        loop_input: CognitiveLoopInput,
        plan: ActionPlan,
        perception: InterpretedPerception,
        memory: RetrievedMemoryContext,
        intention: SelectedIntention,
    ) -> tuple[MemoryUpdateIntent, ...]:
        intents: list[MemoryUpdateIntent] = []
        for hook in self._hooks:
            propose = getattr(hook, "propose_updates", None)
            if propose is None:
                raise TypeError("hook missing propose_updates")
            batch = await propose(loop_input, plan, perception, memory, intention)
            if not isinstance(batch, tuple):
                raise TypeError("propose_updates must return a tuple")
            for item in batch:
                if type(item) is not MemoryUpdateIntent:
                    raise TypeError(
                        "propose_updates entries must be MemoryUpdateIntent"
                    )
                intents.append(item)
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
            return None
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
        decision: SocialMessageDecision | None = None
        if selected_ids and beliefs and beliefs[0].confidence.confidence >= 0.5:
            claim = beliefs[0]
            conf = claim.confidence.confidence
            utterance = origin_utterance(
                text=f"claim:{claim.belief_id.value}",
                speaker_id=speaker_id,
                communication_id=f"plan-tell-{claim.belief_id.value}",
                sender_confidence=conf,
                source_basis=CommunicationSourceBasis.BELIEF,
                concepts=(claim.belief_id.value,),
            )
            decision = SocialMessageDecision(
                command=Tell(recipient_id=recipient, utterance=utterance),
                action_kind="tell",
                source_basis=CommunicationSourceBasis.BELIEF,
                hop_count=0,
                sender_confidence=conf,
                fallback=False,
                candidate_count=candidate_count,
            )
            _LOG.debug(
                "social_message_belief_testify",
                extra={
                    "cognition": {
                        "owner_id": owner_id.value,
                        "policy_version": SOCIAL_MESSAGE_POLICY_VERSION,
                        "reason_code": "selected_belief_testify",
                        "selected_belief_count": len(selected_ids),
                        "confidence_band": confidence_band(conf),
                    }
                },
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
                        communication_id=(
                            f"plan-retell-{recon.episode_id}"
                        ),
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
