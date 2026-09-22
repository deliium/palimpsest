"""Deterministic semantic belief extraction, revision, and confidence decay.

Pure functions only: no wall clocks, UUID defaults, global RNG, embedding-only
identity, Python ``hash()``, or logging. Scores use :func:`quantize_score`.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from agents.models import AgentId
from memory.beliefs import (
    AppliedTestimonyFactors,
    BeliefActivationState,
    BeliefConfidenceState,
    BeliefEvidenceBundle,
    BeliefEvidenceContribution,
    BeliefPolicyRef,
    BeliefRevision,
    BeliefRevisionId,
    BeliefValueKind,
    ClaimSubject,
    ClaimSubjectKind,
    ClaimValue,
    CommunicatedEvidenceDecision,
    EvidenceStance,
    SemanticBelief,
    SemanticBeliefHistory,
    SemanticClaim,
    canonical_claim_identity,
    canonical_subject_predicate_key,
)
from memory.models import (
    BeliefId,
    MemoryId,
    MemoryRelation,
    MemorySourceKind,
    MemoryTrace,
    RelationEndpointKind,
    quantize_score,
)
from world.identifiers import (
    require_bounded_text,
    require_exact_nonneg_int,
)

_MAX_POLICY_ID_CHARS: Final[int] = 64
_MAX_CANDIDATES: Final[int] = 256


@dataclass(frozen=True, slots=True)
class BeliefFormationPolicy:
    """Versioned deterministic extractor and revision policy."""

    policy_id: str
    version: str
    min_independent_observations: int = 2
    direct_weight: float = 1.0
    communicated_weight: float = 0.5
    decay_half_life_ticks: int = 100
    activate_confidence_threshold: float = 0.4
    retire_confidence_threshold: float = 0.05
    base_contribution: float = 0.35
    hop_attenuation: float = 0.85
    trust_accept_threshold: float = 0.45
    trust_contradict_ceiling: float = 0.25
    defer_max_hop: int = 8
    min_context_relevance: float = 0.15

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "policy_id",
            require_bounded_text(
                "BeliefFormationPolicy.policy_id",
                self.policy_id,
                max_length=_MAX_POLICY_ID_CHARS,
            ),
        )
        object.__setattr__(
            self,
            "version",
            require_bounded_text(
                "BeliefFormationPolicy.version",
                self.version,
                max_length=_MAX_POLICY_ID_CHARS,
            ),
        )
        object.__setattr__(
            self,
            "min_independent_observations",
            require_exact_nonneg_int(
                "BeliefFormationPolicy.min_independent_observations",
                self.min_independent_observations,
            ),
        )
        if self.min_independent_observations < 1:
            raise ValueError(
                "BeliefFormationPolicy.min_independent_observations: must_be_positive"
            )
        object.__setattr__(
            self,
            "decay_half_life_ticks",
            require_exact_nonneg_int(
                "BeliefFormationPolicy.decay_half_life_ticks",
                self.decay_half_life_ticks,
            ),
        )
        object.__setattr__(
            self,
            "defer_max_hop",
            require_exact_nonneg_int(
                "BeliefFormationPolicy.defer_max_hop", self.defer_max_hop
            ),
        )
        for name in (
            "direct_weight",
            "communicated_weight",
            "activate_confidence_threshold",
            "retire_confidence_threshold",
            "base_contribution",
            "hop_attenuation",
            "trust_accept_threshold",
            "trust_contradict_ceiling",
            "min_context_relevance",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"BeliefFormationPolicy.{name}: not_unit_interval")
            number = float(value)
            if not math.isfinite(number) or number < 0.0 or number > 1.0:
                raise ValueError(f"BeliefFormationPolicy.{name}: not_unit_interval")
            object.__setattr__(self, name, 0.0 if number == 0.0 else number)
        if self.retire_confidence_threshold > self.activate_confidence_threshold:
            raise ValueError("BeliefFormationPolicy: retire_above_activate")
        if self.trust_contradict_ceiling > self.trust_accept_threshold:
            raise ValueError("BeliefFormationPolicy: contradict_above_accept")

    def as_ref(self) -> BeliefPolicyRef:
        return BeliefPolicyRef(policy_id=self.policy_id, version=self.version)

    def __repr__(self) -> str:
        return (
            f"BeliefFormationPolicy(policy_id={self.policy_id!r}, "
            f"version={self.version!r}, "
            f"min_independent_observations={self.min_independent_observations})"
        )


DEFAULT_BELIEF_FORMATION_POLICY: Final[BeliefFormationPolicy] = BeliefFormationPolicy(
    policy_id="semantic-belief-formation",
    version="1",
)


@dataclass(frozen=True, slots=True)
class BeliefEvidenceCandidate:
    """One extracted evidence candidate before ownership/idempotency checks."""

    memory_id: MemoryId
    claim: SemanticClaim
    stance: EvidenceStance
    contribution: float
    lineage_root_id: MemoryId
    source_tick: int
    provenance_kind: MemorySourceKind
    applied_factors: AppliedTestimonyFactors | None = None

    def __post_init__(self) -> None:
        if type(self.memory_id) is not MemoryId:
            raise TypeError("BeliefEvidenceCandidate.memory_id: invalid_type")
        if type(self.claim) is not SemanticClaim:
            raise TypeError("BeliefEvidenceCandidate.claim: invalid_type")
        if type(self.stance) is not EvidenceStance:
            raise TypeError("BeliefEvidenceCandidate.stance: invalid_type")
        if type(self.lineage_root_id) is not MemoryId:
            raise TypeError("BeliefEvidenceCandidate.lineage_root_id: invalid_type")
        if type(self.provenance_kind) is not MemorySourceKind:
            raise TypeError("BeliefEvidenceCandidate.provenance_kind: invalid_type")
        if (
            self.applied_factors is not None
            and type(self.applied_factors) is not AppliedTestimonyFactors
        ):
            raise TypeError("BeliefEvidenceCandidate.applied_factors: invalid_type")
        object.__setattr__(
            self,
            "contribution",
            quantize_score(
                _unit("BeliefEvidenceCandidate.contribution", self.contribution)
            ),
        )
        object.__setattr__(
            self,
            "source_tick",
            require_exact_nonneg_int(
                "BeliefEvidenceCandidate.source_tick", self.source_tick
            ),
        )

    def __repr__(self) -> str:
        return (
            f"BeliefEvidenceCandidate(memory_id={self.memory_id.value!r}, "
            f"stance={self.stance.value!r}, "
            f"lineage_root_id={self.lineage_root_id.value!r}, "
            f"source_tick={self.source_tick})"
        )


def _unit(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name}: not_unit_interval")
    number = float(value)
    if not math.isfinite(number) or number < 0.0 or number > 1.0:
        raise ValueError(f"{name}: not_unit_interval")
    return 0.0 if number == 0.0 else number


def provenance_weight(
    kind: MemorySourceKind, *, policy: BeliefFormationPolicy
) -> float:
    """Return provenance weight for direct versus communicated memories."""
    if type(kind) is not MemorySourceKind:
        raise TypeError("provenance_weight: invalid_type")
    if type(policy) is not BeliefFormationPolicy:
        raise TypeError("provenance_weight: invalid_policy")
    if kind is MemorySourceKind.DIRECT_OBSERVATION:
        return policy.direct_weight
    if kind is MemorySourceKind.COMMUNICATED:
        return policy.communicated_weight
    raise ValueError("provenance_weight: unsupported_kind")


def transmission_root_for_trace(trace: MemoryTrace) -> MemoryId:
    """Opaque transmission-root id for independent-evidence deduplication.

    Uses speaker-declared communication correlation when present; falls back to
    the episodic memory id. Never exposes content fingerprints in the returned id.
    """
    if type(trace) is not MemoryTrace:
        raise TypeError("transmission_root_for_trace: invalid_trace")
    meta = trace.provenance.transmission
    if meta is None:
        return trace.memory_id
    root = meta.transmission_root_id or (
        meta.communication_id
        if meta.hop_count == 0
        else (
            meta.parent_communication_id
            if meta.hop_count == 1 and meta.parent_communication_id is not None
            else meta.communication_id
        )
    )
    material = f"tr|{root}"
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return MemoryId(f"tr-{digest[:48]}")


def evaluate_communicated_testimony(
    *,
    sender_confidence: float,
    receiver_confidence: float,
    trust: float,
    trust_confidence: float,
    hop_count: int,
    context_relevance: float,
    base_contribution: float,
    policy: BeliefFormationPolicy,
) -> AppliedTestimonyFactors:
    """Evaluate communicated evidence without treating testimony as fact.

    Neutral policy inputs only — cognition projects relationship trust into
    ``trust`` / ``trust_confidence`` floats before calling this function.
    """
    if type(policy) is not BeliefFormationPolicy:
        raise TypeError("evaluate_communicated_testimony: invalid_policy")
    hop = require_exact_nonneg_int(
        "evaluate_communicated_testimony.hop_count", hop_count
    )
    sender = _unit("sender_confidence", sender_confidence)
    receiver = _unit("receiver_confidence", receiver_confidence)
    trust_v = _unit("trust", trust)
    trust_conf = _unit("trust_confidence", trust_confidence)
    relevance = _unit("context_relevance", context_relevance)
    base = _unit("base_contribution", base_contribution)
    attenuation = quantize_score(policy.hop_attenuation**hop)
    weighted = quantize_score(
        min(
            1.0,
            base
            * sender
            * receiver
            * max(trust_v, 0.05)
            * max(trust_conf, 0.05)
            * relevance
            * attenuation,
        )
    )
    if hop > policy.defer_max_hop or relevance < policy.min_context_relevance:
        decision = CommunicatedEvidenceDecision.DEFER
        adjusted = 0.0
        delta = 0.0
    elif trust_v < policy.trust_contradict_ceiling and trust_conf >= 0.4:
        decision = CommunicatedEvidenceDecision.CONTRADICT
        adjusted = weighted
        delta = quantize_score(-adjusted)
    elif trust_v >= policy.trust_accept_threshold and trust_conf >= 0.3:
        decision = CommunicatedEvidenceDecision.ACCEPT
        adjusted = weighted
        delta = adjusted
    else:
        decision = CommunicatedEvidenceDecision.DISCOUNT
        adjusted = quantize_score(weighted * 0.5)
        delta = adjusted
    return AppliedTestimonyFactors(
        decision=decision,
        hop_count=hop,
        trust=trust_v,
        trust_confidence=trust_conf,
        sender_confidence=sender,
        receiver_confidence=receiver,
        context_relevance=relevance,
        hop_attenuation=attenuation,
        base_contribution=base,
        adjusted_contribution=adjusted,
        confidence_delta=delta,
        policy_version=policy.version,
    )


def lineage_root_for_trace(
    trace: MemoryTrace,
    traces: Mapping[MemoryId, MemoryTrace],
) -> MemoryId:
    """Return the episodic lineage root used for independent-evidence dedup."""
    if type(trace) is not MemoryTrace:
        raise TypeError("lineage_root_for_trace: invalid_trace")
    current = trace
    seen: set[str] = set()
    while True:
        if current.memory_id.value in seen:
            raise ValueError("lineage_root_for_trace: cycle")
        seen.add(current.memory_id.value)
        sources = current.lineage.source_memory_ids
        if not sources:
            return current.memory_id
        # Prefer principal predecessor when present; else first source.
        next_id = current.lineage.supersedes_memory_id or sources[0]
        parent = traces.get(next_id)
        if parent is None:
            return next_id
        current = parent


def belief_id_for_claim(*, owner_id: AgentId, claim: SemanticClaim) -> BeliefId:
    """Deterministic belief ID from owner and subject/predicate key (sha256)."""
    if type(owner_id) is not AgentId:
        raise TypeError("belief_id_for_claim: invalid_owner")
    if type(claim) is not SemanticClaim:
        raise TypeError("belief_id_for_claim: invalid_claim")
    material = f"v1|{owner_id.value}|{canonical_subject_predicate_key(claim)}"
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return BeliefId(f"sb-{digest[:48]}")


def revision_id_for(
    *,
    belief_id: BeliefId,
    ordinal: int,
    logical_tick: int,
    claim: SemanticClaim,
    operation_id: str,
) -> BeliefRevisionId:
    """Deterministic revision ID (no wall clock / UUID / hash())."""
    material = (
        f"v1|{belief_id.value}|{ordinal}|{logical_tick}|"
        f"{canonical_claim_identity(claim)}|{operation_id}"
    )
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return BeliefRevisionId(f"br-{digest[:48]}")


def _endpoint_subject(
    trace: MemoryTrace, endpoint_kind: RelationEndpointKind, mention_id: str
) -> ClaimSubject:
    if endpoint_kind is RelationEndpointKind.CONCEPT:
        for concept in trace.concepts:
            if concept.mention_id.value == mention_id:
                return ClaimSubject(
                    kind=ClaimSubjectKind.CONCEPT, concept=concept.concept
                )
        raise ValueError("extract_evidence_candidates: unknown_concept")
    for entity in trace.entities:
        if entity.mention_id.value == mention_id:
            if entity.entity_id is not None:
                return ClaimSubject(
                    kind=ClaimSubjectKind.ENTITY, entity_id=entity.entity_id
                )
            return ClaimSubject(kind=ClaimSubjectKind.CONCEPT, concept=entity.label)
    raise ValueError("extract_evidence_candidates: unknown_entity")


def _endpoint_value(
    trace: MemoryTrace, endpoint_kind: RelationEndpointKind, mention_id: str
) -> ClaimValue:
    if endpoint_kind is RelationEndpointKind.CONCEPT:
        for concept in trace.concepts:
            if concept.mention_id.value == mention_id:
                return ClaimValue(kind=BeliefValueKind.TEXT, text_value=concept.concept)
        raise ValueError("extract_evidence_candidates: unknown_concept")
    for entity in trace.entities:
        if entity.mention_id.value == mention_id:
            if entity.entity_id is not None:
                return ClaimValue(
                    kind=BeliefValueKind.ENTITY, entity_id=entity.entity_id
                )
            return ClaimValue(kind=BeliefValueKind.TEXT, text_value=entity.label)
    raise ValueError("extract_evidence_candidates: unknown_entity")


def _relation_claim(trace: MemoryTrace, relation: MemoryRelation) -> SemanticClaim:
    return SemanticClaim(
        subject=_endpoint_subject(
            trace, relation.subject.kind, relation.subject.mention_id.value
        ),
        predicate=relation.predicate,
        value=_endpoint_value(
            trace, relation.object.kind, relation.object.mention_id.value
        ),
    )


def bundle_from_candidates(
    candidates: Sequence[BeliefEvidenceCandidate],
    *,
    target_claim: SemanticClaim,
) -> BeliefEvidenceBundle:
    """Group candidates into supporting/contradicting evidence for ``target_claim``.

    One memory may emit multiple claim values under the same subject/predicate
    (for example several ``experienced_concept`` values). Collapse to one
    contribution per ``memory_id``: prefer SUPPORTING when any identity matches
    the target claim, otherwise CONTRADICTING with the strongest contribution.
    """
    target_key = canonical_subject_predicate_key(target_claim)
    target_identity = canonical_claim_identity(target_claim)
    # memory_id -> (stance, contribution, lineage_root, factors, sort_key)
    collapsed: dict[
        str,
        tuple[
            EvidenceStance,
            float,
            MemoryId,
            AppliedTestimonyFactors | None,
            tuple[int, float, str, str],
        ],
    ] = {}
    for candidate in candidates:
        if canonical_subject_predicate_key(candidate.claim) != target_key:
            continue
        if candidate.stance is EvidenceStance.CONTRADICTING:
            stance = EvidenceStance.CONTRADICTING
        elif canonical_claim_identity(candidate.claim) == target_identity:
            stance = EvidenceStance.SUPPORTING
        else:
            stance = EvidenceStance.CONTRADICTING
        mid = candidate.memory_id.value
        sort_key = (
            0 if stance is EvidenceStance.SUPPORTING else 1,
            -candidate.contribution,
            candidate.lineage_root_id.value,
            mid,
        )
        incoming = (
            stance,
            candidate.contribution,
            candidate.lineage_root_id,
            candidate.applied_factors,
            sort_key,
        )
        existing = collapsed.get(mid)
        if existing is None:
            collapsed[mid] = incoming
            continue
        existing_stance = existing[0]
        if existing_stance is EvidenceStance.SUPPORTING:
            if stance is EvidenceStance.SUPPORTING and sort_key < existing[4]:
                collapsed[mid] = incoming
            continue
        if stance is EvidenceStance.SUPPORTING or sort_key < existing[4]:
            collapsed[mid] = incoming

    ordered = sorted(collapsed.items(), key=lambda item: item[1][4])
    supporting: list[BeliefEvidenceContribution] = []
    contradicting: list[BeliefEvidenceContribution] = []
    ordinal = 0
    for mid, (stance, contribution, lineage_root, factors, _) in ordered:
        item = BeliefEvidenceContribution(
            memory_id=MemoryId(mid),
            stance=stance,
            contribution=contribution,
            ordinal=ordinal,
            lineage_root_id=lineage_root,
            applied_factors=factors,
        )
        ordinal += 1
        if stance is EvidenceStance.SUPPORTING:
            supporting.append(item)
        else:
            contradicting.append(item)
    return BeliefEvidenceBundle(
        supporting=tuple(supporting), contradicting=tuple(contradicting)
    )


def extract_evidence_candidates(
    traces: Sequence[MemoryTrace],
    *,
    owner_id: AgentId,
    policy: BeliefFormationPolicy,
    trace_index: Mapping[MemoryId, MemoryTrace] | None = None,
) -> tuple[BeliefEvidenceCandidate, ...]:
    """Convert owned traces into ordered canonical evidence candidates."""
    if type(owner_id) is not AgentId:
        raise TypeError("extract_evidence_candidates: invalid_owner")
    if type(policy) is not BeliefFormationPolicy:
        raise TypeError("extract_evidence_candidates: invalid_policy")
    index: dict[MemoryId, MemoryTrace] = (
        dict(trace_index) if trace_index is not None else {}
    )
    for trace in traces:
        if type(trace) is not MemoryTrace:
            raise TypeError("extract_evidence_candidates: invalid_trace")
        index[trace.memory_id] = trace

    candidates: list[BeliefEvidenceCandidate] = []
    for trace in traces:
        if trace.owner_id != owner_id:
            raise ValueError("extract_evidence_candidates: ownership")
        if trace.forgotten_at_tick is not None:
            continue
        weight = provenance_weight(trace.provenance.kind, policy=policy)
        hop = 0
        if (
            trace.provenance.kind is MemorySourceKind.COMMUNICATED
            and trace.provenance.transmission is not None
        ):
            hop = trace.provenance.transmission.hop_count
            weight = quantize_score(weight * (policy.hop_attenuation**hop))
        contribution = quantize_score(
            min(1.0, policy.base_contribution * weight * trace.confidence)
        )
        if contribution <= 0.0:
            continue
        if trace.provenance.kind is MemorySourceKind.COMMUNICATED:
            root = transmission_root_for_trace(trace)
        else:
            root = lineage_root_for_trace(trace, index)

        for concept in trace.concepts:
            claim = SemanticClaim(
                subject=ClaimSubject(kind=ClaimSubjectKind.AGENT, agent_id=owner_id),
                predicate="experienced_concept",
                value=ClaimValue(kind=BeliefValueKind.TEXT, text_value=concept.concept),
            )
            candidates.append(
                BeliefEvidenceCandidate(
                    memory_id=trace.memory_id,
                    claim=claim,
                    stance=EvidenceStance.SUPPORTING,
                    contribution=contribution,
                    lineage_root_id=root,
                    source_tick=trace.source_tick,
                    provenance_kind=trace.provenance.kind,
                )
            )

        for entity in trace.entities:
            if entity.entity_id is None:
                subject = ClaimSubject(
                    kind=ClaimSubjectKind.CONCEPT, concept=entity.label
                )
            else:
                subject = ClaimSubject(
                    kind=ClaimSubjectKind.ENTITY, entity_id=entity.entity_id
                )
            claim = SemanticClaim(
                subject=subject,
                predicate="observed",
                value=ClaimValue(kind=BeliefValueKind.BOOL, bool_value=True),
            )
            candidates.append(
                BeliefEvidenceCandidate(
                    memory_id=trace.memory_id,
                    claim=claim,
                    stance=EvidenceStance.SUPPORTING,
                    contribution=contribution,
                    lineage_root_id=root,
                    source_tick=trace.source_tick,
                    provenance_kind=trace.provenance.kind,
                )
            )

        for relation in trace.relations:
            claim = _relation_claim(trace, relation)
            candidates.append(
                BeliefEvidenceCandidate(
                    memory_id=trace.memory_id,
                    claim=claim,
                    stance=EvidenceStance.SUPPORTING,
                    contribution=contribution,
                    lineage_root_id=root,
                    source_tick=trace.source_tick,
                    provenance_kind=trace.provenance.kind,
                )
            )

    # Stable order: claim identity, lineage root, memory id, source tick.
    candidates.sort(
        key=lambda item: (
            canonical_claim_identity(item.claim),
            item.lineage_root_id.value,
            item.memory_id.value,
            item.source_tick,
        )
    )
    if len(candidates) > _MAX_CANDIDATES:
        raise ValueError("extract_evidence_candidates: exceeds_max_length")
    return tuple(candidates)


def apply_confidence_decay(
    state: BeliefConfidenceState,
    *,
    elapsed_ticks: int,
    policy: BeliefFormationPolicy,
) -> BeliefConfidenceState:
    """Decay accumulated masses and confidence toward uncertainty (``0.0``)."""
    if type(state) is not BeliefConfidenceState:
        raise TypeError("apply_confidence_decay: invalid_state")
    if type(policy) is not BeliefFormationPolicy:
        raise TypeError("apply_confidence_decay: invalid_policy")
    elapsed = require_exact_nonneg_int(
        "apply_confidence_decay.elapsed_ticks", elapsed_ticks
    )
    if elapsed == 0 or policy.decay_half_life_ticks == 0:
        return state
    # Exponential decay: factor = 0.5 ** (elapsed / half_life)
    factor = 0.5 ** (elapsed / float(policy.decay_half_life_ticks))
    factor = quantize_score(max(0.0, min(1.0, factor)))
    return BeliefConfidenceState(
        confidence=quantize_score(state.confidence * factor),
        support_mass=quantize_score(state.support_mass * factor),
        contradiction_mass=quantize_score(state.contradiction_mass * factor),
    )


def revise_confidence(
    *,
    prior: BeliefConfidenceState | None,
    support_delta: float,
    contradiction_delta: float,
) -> BeliefConfidenceState:
    """Combine prior masses with new evidence; confidence is net support."""
    base = prior or BeliefConfidenceState(
        confidence=0.0, support_mass=0.0, contradiction_mass=0.0
    )
    support = quantize_score(
        min(1.0, base.support_mass + _unit("support_delta", support_delta))
    )
    contradiction = quantize_score(
        min(
            1.0,
            base.contradiction_mass + _unit("contradiction_delta", contradiction_delta),
        )
    )
    confidence = quantize_score(max(0.0, support - contradiction))
    return BeliefConfidenceState(
        confidence=confidence,
        support_mass=support,
        contradiction_mass=contradiction,
    )


def _dedup_independent(
    contributions: Sequence[BeliefEvidenceContribution],
) -> tuple[BeliefEvidenceContribution, ...]:
    """Keep highest-contribution item per lineage root (stable by ordinal)."""
    best: dict[str, BeliefEvidenceContribution] = {}
    order: list[str] = []
    for item in contributions:
        key = item.lineage_root_id.value
        existing = best.get(key)
        if existing is None:
            best[key] = item
            order.append(key)
            continue
        if item.contribution > existing.contribution:
            best[key] = item
        elif (
            item.contribution == existing.contribution
            and item.memory_id.value < existing.memory_id.value
        ):
            best[key] = item
    return tuple(best[key] for key in order)


def _activation_for(
    *,
    confidence: BeliefConfidenceState,
    independent_support: int,
    prior_state: BeliefActivationState | None,
    policy: BeliefFormationPolicy,
) -> BeliefActivationState:
    if (
        independent_support >= policy.min_independent_observations
        and confidence.confidence >= policy.activate_confidence_threshold
    ):
        return BeliefActivationState.ACTIVE
    if (
        prior_state is BeliefActivationState.ACTIVE
        and confidence.confidence < policy.retire_confidence_threshold
    ):
        return BeliefActivationState.RETIRED
    if prior_state is BeliefActivationState.RETIRED:
        if (
            independent_support >= policy.min_independent_observations
            and confidence.confidence >= policy.activate_confidence_threshold
        ):
            return BeliefActivationState.ACTIVE
        return BeliefActivationState.RETIRED
    return BeliefActivationState.CANDIDATE


def merge_revision(
    *,
    owner_id: AgentId,
    claim: SemanticClaim,
    new_evidence: BeliefEvidenceBundle,
    prior: SemanticBeliefHistory | None,
    logical_tick: int,
    operation_id: str,
    policy: BeliefFormationPolicy,
) -> tuple[SemanticBeliefHistory, bool, bool, bool]:
    """Append one revision from new evidence; return history and change flags.

    Returns ``(history, created, retired, materially_changed)``.
    """
    if type(owner_id) is not AgentId:
        raise TypeError("merge_revision: invalid_owner")
    if type(claim) is not SemanticClaim:
        raise TypeError("merge_revision: invalid_claim")
    if type(new_evidence) is not BeliefEvidenceBundle:
        raise TypeError("merge_revision: invalid_evidence")
    if type(policy) is not BeliefFormationPolicy:
        raise TypeError("merge_revision: invalid_policy")
    tick = require_exact_nonneg_int("merge_revision.logical_tick", logical_tick)
    belief_id = (
        prior.belief.belief_id
        if prior is not None
        else belief_id_for_claim(owner_id=owner_id, claim=claim)
    )

    prior_conf: BeliefConfidenceState | None = None
    prior_state: BeliefActivationState | None = None
    previous_revision_id = None
    ordinal = 0
    created_tick = tick
    prior_claim: SemanticClaim | None = None
    if prior is not None:
        if prior.belief.owner_id != owner_id:
            raise ValueError("merge_revision: ownership")
        if prior.belief.updated_tick > tick:
            raise ValueError("merge_revision: chronology")
        elapsed = tick - prior.belief.updated_tick
        prior_conf = apply_confidence_decay(
            prior.belief.confidence, elapsed_ticks=elapsed, policy=policy
        )
        prior_state = prior.belief.activation_state
        previous_revision_id = prior.belief.current_revision_id
        ordinal = prior.belief.revision_ordinal + 1
        created_tick = prior.belief.created_tick
        prior_claim = prior.belief.claim

    # Competing values for the same subject/predicate are contradictions.
    effective_claim = claim
    support_items = list(new_evidence.supporting)
    contradict_items = list(new_evidence.contradicting)
    if prior_claim is not None:
        same_key = canonical_subject_predicate_key(prior_claim) == (
            canonical_subject_predicate_key(claim)
        )
        if same_key and canonical_claim_identity(prior_claim) != (
            canonical_claim_identity(claim)
        ):
            # Keep prior claim; treat incoming support as contradiction.
            effective_claim = prior_claim
            remapped: list[BeliefEvidenceContribution] = []
            for item in support_items:
                remapped.append(
                    BeliefEvidenceContribution(
                        memory_id=item.memory_id,
                        stance=EvidenceStance.CONTRADICTING,
                        contribution=item.contribution,
                        ordinal=item.ordinal,
                        lineage_root_id=item.lineage_root_id,
                    )
                )
            contradict_items.extend(remapped)
            support_items = []
        elif same_key:
            effective_claim = prior_claim

    # Rebuild dense ordinals after possible remapping.
    combined: list[BeliefEvidenceContribution] = []
    for index, item in enumerate((*support_items, *contradict_items)):
        combined.append(
            BeliefEvidenceContribution(
                memory_id=item.memory_id,
                stance=item.stance,
                contribution=item.contribution,
                ordinal=index,
                lineage_root_id=item.lineage_root_id,
            )
        )
    support_final = tuple(
        item for item in combined if item.stance is EvidenceStance.SUPPORTING
    )
    contradict_final = tuple(
        item for item in combined if item.stance is EvidenceStance.CONTRADICTING
    )
    evidence = BeliefEvidenceBundle(
        supporting=support_final, contradicting=contradict_final
    )

    independent_support = _dedup_independent(evidence.supporting)
    independent_contradict = _dedup_independent(evidence.contradicting)
    support_delta = quantize_score(
        min(1.0, sum(item.contribution for item in independent_support))
    )
    contradict_delta = quantize_score(
        min(1.0, sum(item.contribution for item in independent_contradict))
    )
    confidence = revise_confidence(
        prior=prior_conf,
        support_delta=support_delta,
        contradiction_delta=contradict_delta,
    )

    cumulative_support = len(independent_support)
    cumulative_contradict = len(independent_contradict)
    if prior is not None and prior_claim is not None:
        if canonical_claim_identity(prior_claim) == canonical_claim_identity(
            effective_claim
        ):
            cumulative_support = min(
                256, prior.belief.evidence_support_count + len(independent_support)
            )
            cumulative_contradict = min(
                256,
                prior.belief.evidence_contradiction_count + len(independent_contradict),
            )
        else:
            cumulative_support = len(independent_support)
            cumulative_contradict = min(
                256,
                prior.belief.evidence_contradiction_count + len(independent_contradict),
            )

    activation = _activation_for(
        confidence=confidence,
        independent_support=cumulative_support,
        prior_state=prior_state,
        policy=policy,
    )

    revision_id = revision_id_for(
        belief_id=belief_id,
        ordinal=ordinal,
        logical_tick=tick,
        claim=effective_claim,
        operation_id=operation_id,
    )
    revision = BeliefRevision(
        revision_id=revision_id,
        belief_id=belief_id,
        owner_id=owner_id,
        ordinal=ordinal,
        logical_tick=tick,
        claim=effective_claim,
        confidence=confidence,
        evidence=evidence,
        activation_state=activation,
        policy=policy.as_ref(),
        previous_revision_id=previous_revision_id,
    )
    belief = SemanticBelief(
        belief_id=belief_id,
        owner_id=owner_id,
        claim=effective_claim,
        confidence=confidence,
        activation_state=activation,
        current_revision_id=revision_id,
        revision_ordinal=ordinal,
        created_tick=created_tick,
        updated_tick=tick,
        policy=policy.as_ref(),
        evidence_support_count=cumulative_support,
        evidence_contradiction_count=cumulative_contradict,
    )
    revisions = (revision,) if prior is None else (*prior.revisions, revision)
    history = SemanticBeliefHistory(belief=belief, revisions=revisions)
    created = prior is None
    retired = activation is BeliefActivationState.RETIRED and (
        prior_state is not BeliefActivationState.RETIRED
    )
    materially_changed = created or (
        prior is not None
        and (
            prior.belief.activation_state != activation
            or prior.belief.confidence.confidence != confidence.confidence
            or canonical_claim_identity(prior.belief.claim)
            != canonical_claim_identity(effective_claim)
        )
    )
    return history, created, retired, materially_changed


__all__ = [
    "DEFAULT_BELIEF_FORMATION_POLICY",
    "BeliefEvidenceCandidate",
    "BeliefFormationPolicy",
    "apply_confidence_decay",
    "belief_id_for_claim",
    "bundle_from_candidates",
    "evaluate_communicated_testimony",
    "extract_evidence_candidates",
    "lineage_root_for_trace",
    "merge_revision",
    "provenance_weight",
    "revise_confidence",
    "revision_id_for",
    "transmission_root_for_trace",
]
