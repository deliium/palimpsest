"""Structured semantic beliefs with append-only revision contracts.

Beliefs are owner-scoped subjective claims with typed values and evidence that
references owned ``MemoryTrace`` IDs only. Domain values remain log-free; safe
``repr`` exposes IDs and counts, never propositions, typed values, or evidence
payloads. Exceptions use field names and stable reason codes only.

The legacy :class:`~memory.models.Belief` (proposition string) remains unchanged
for schema-v1 codecs; use :func:`project_legacy_belief` for a lossy projection.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from agents.models import AgentId
from memory.models import (
    Belief,
    BeliefId,
    MemoryId,
    OwnershipError,
    quantize_score,
)
from world.identifiers import (
    EntityId,
    require_bounded_text,
    require_exact_nonneg_int,
    require_stable_id,
)

__all__ = [
    "AppliedTestimonyFactors",
    "BeliefActivationState",
    "BeliefConfidenceState",
    "BeliefEvidenceBundle",
    "BeliefEvidenceContribution",
    "BeliefPolicyRef",
    "BeliefRevision",
    "BeliefRevisionId",
    "BeliefRevisionRequest",
    "BeliefRevisionResult",
    "BeliefValueKind",
    "ClaimSubject",
    "ClaimSubjectKind",
    "ClaimValue",
    "CommunicatedEvidenceDecision",
    "EvidenceStance",
    "OwnershipError",
    "SemanticBelief",
    "SemanticBeliefHistory",
    "SemanticBeliefStore",
    "SemanticClaim",
    "canonical_claim_identity",
    "canonical_subject_predicate_key",
    "project_legacy_belief",
]

_MAX_PREDICATE_CHARS: Final[int] = 128
_MAX_TEXT_VALUE_CHARS: Final[int] = 256
_MAX_CONCEPT_CHARS: Final[int] = 256
_MAX_POLICY_ID_CHARS: Final[int] = 64
_MAX_EVIDENCE_ITEMS: Final[int] = 256
_MAX_OPERATION_ID_CHARS: Final[int] = 128
_MAX_REVISIONS: Final[int] = 10_000
_NUMBER_ABS_MAX: Final[float] = 1.0e6


class ClaimSubjectKind(StrEnum):
    """What a semantic claim is about."""

    AGENT = "agent"
    ENTITY = "entity"
    CONCEPT = "concept"


class BeliefValueKind(StrEnum):
    """Closed typed-value grammar for semantic claims."""

    BOOL = "bool"
    NUMBER = "number"
    TEXT = "text"
    AGENT = "agent"
    ENTITY = "entity"


class EvidenceStance(StrEnum):
    """Whether an evidence item supports or contradicts the current claim value."""

    SUPPORTING = "supporting"
    CONTRADICTING = "contradicting"


class CommunicatedEvidenceDecision(StrEnum):
    """Closed outcomes for trust-aware communicated evidence evaluation."""

    ACCEPT = "accept"
    DISCOUNT = "discount"
    CONTRADICT = "contradict"
    DEFER = "defer"


@dataclass(frozen=True, slots=True)
class AppliedTestimonyFactors:
    """Audit snapshot of factors applied to one communicated evidence item.

    Domain-neutral floats only. Never carries propositions, trust labels, or
    content fingerprints.
    """

    decision: CommunicatedEvidenceDecision
    hop_count: int
    trust: float
    trust_confidence: float
    sender_confidence: float
    receiver_confidence: float
    context_relevance: float
    hop_attenuation: float
    base_contribution: float
    adjusted_contribution: float
    confidence_delta: float
    policy_version: str

    def __post_init__(self) -> None:
        if type(self.decision) is not CommunicatedEvidenceDecision:
            raise TypeError("AppliedTestimonyFactors.decision: invalid_type")
        object.__setattr__(
            self,
            "hop_count",
            require_exact_nonneg_int(
                "AppliedTestimonyFactors.hop_count", self.hop_count
            ),
        )
        for name in (
            "trust",
            "trust_confidence",
            "sender_confidence",
            "receiver_confidence",
            "context_relevance",
            "hop_attenuation",
            "base_contribution",
            "adjusted_contribution",
        ):
            object.__setattr__(
                self,
                name,
                quantize_score(
                    _unit_interval(
                        f"AppliedTestimonyFactors.{name}", getattr(self, name)
                    )
                ),
            )
        object.__setattr__(
            self,
            "confidence_delta",
            quantize_score(
                _signed_unit(
                    "AppliedTestimonyFactors.confidence_delta", self.confidence_delta
                )
            ),
        )
        object.__setattr__(
            self,
            "policy_version",
            require_bounded_text(
                "AppliedTestimonyFactors.policy_version",
                self.policy_version,
                max_length=64,
            ),
        )

    def __repr__(self) -> str:
        return (
            f"AppliedTestimonyFactors(decision={self.decision.value!r}, "
            f"hop_count={self.hop_count}, "
            f"confidence_delta={self.confidence_delta}, "
            f"policy_version={self.policy_version!r})"
        )


def _signed_unit(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name}: not_finite_number")
    number = float(value)
    if not math.isfinite(number) or number < -1.0 or number > 1.0:
        raise ValueError(f"{name}: not_signed_unit")
    return 0.0 if number == 0.0 else number


class BeliefActivationState(StrEnum):
    """Lifecycle state for a semantic belief head."""

    CANDIDATE = "candidate"
    ACTIVE = "active"
    RETIRED = "retired"


def _unit_interval(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name}: not_unit_interval")
    number = float(value)
    if not math.isfinite(number) or number < 0.0 or number > 1.0:
        raise ValueError(f"{name}: not_unit_interval")
    return 0.0 if number == 0.0 else number


def _bounded_number(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name}: not_finite_number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{name}: not_finite_number")
    if number < -_NUMBER_ABS_MAX or number > _NUMBER_ABS_MAX:
        raise ValueError(f"{name}: out_of_bounds")
    quantized = quantize_score(number)
    return 0.0 if quantized == 0.0 else quantized


def _require_ordered_models[T](
    name: str, values: Sequence[object], *, model_type: type[T], max_items: int
) -> tuple[T, ...]:
    if isinstance(values, (set, frozenset, Mapping)):
        raise TypeError(f"{name}: not_ordered_sequence")
    if isinstance(values, (str, bytes, bytearray)) or not isinstance(values, Sequence):
        raise TypeError(f"{name}: not_ordered_sequence")
    items = tuple(values)
    if len(items) > max_items:
        raise ValueError(f"{name}: exceeds_max_length")
    for item in items:
        if type(item) is not model_type:
            raise TypeError(f"{name}: invalid_item_type")
    return items  # type: ignore[return-value]


def _escape_token(value: str) -> str:
    """Escape a token for deterministic identity strings (no hashing)."""
    return (
        value.replace("\\", "\\\\")
        .replace("|", "\\|")
        .replace("=", "\\=")
        .replace("\n", "\\n")
    )


@dataclass(frozen=True, slots=True)
class ClaimSubject:
    """Canonical claim subject; identity is independent of display prose."""

    kind: ClaimSubjectKind
    agent_id: AgentId | None = None
    entity_id: EntityId | None = None
    concept: str | None = None

    def __post_init__(self) -> None:
        if type(self.kind) is not ClaimSubjectKind:
            raise TypeError("ClaimSubject.kind: invalid_type")
        if self.kind is ClaimSubjectKind.AGENT:
            if type(self.agent_id) is not AgentId:
                raise TypeError("ClaimSubject.agent_id: invalid_type")
            if self.entity_id is not None or self.concept is not None:
                raise ValueError("ClaimSubject: unexpected_fields")
        elif self.kind is ClaimSubjectKind.ENTITY:
            if type(self.entity_id) is not EntityId:
                raise TypeError("ClaimSubject.entity_id: invalid_type")
            if self.agent_id is not None or self.concept is not None:
                raise ValueError("ClaimSubject: unexpected_fields")
        elif self.kind is ClaimSubjectKind.CONCEPT:
            if self.concept is None:
                raise ValueError("ClaimSubject.concept: missing")
            object.__setattr__(
                self,
                "concept",
                require_bounded_text(
                    "ClaimSubject.concept",
                    self.concept,
                    max_length=_MAX_CONCEPT_CHARS,
                ),
            )
            if self.agent_id is not None or self.entity_id is not None:
                raise ValueError("ClaimSubject: unexpected_fields")
        else:  # pragma: no cover - closed enum
            raise ValueError("ClaimSubject.kind: unsupported")

    def canonical_token(self) -> str:
        if self.kind is ClaimSubjectKind.AGENT:
            assert self.agent_id is not None
            return f"agent={_escape_token(self.agent_id.value)}"
        if self.kind is ClaimSubjectKind.ENTITY:
            assert self.entity_id is not None
            return f"entity={_escape_token(self.entity_id.value)}"
        assert self.concept is not None
        return f"concept={_escape_token(self.concept)}"

    def __repr__(self) -> str:
        return f"ClaimSubject(kind={self.kind.value!r})"


@dataclass(frozen=True, slots=True)
class ClaimValue:
    """Closed typed value for a semantic claim."""

    kind: BeliefValueKind
    bool_value: bool | None = None
    number_value: float | None = None
    text_value: str | None = None
    agent_id: AgentId | None = None
    entity_id: EntityId | None = None

    def __post_init__(self) -> None:
        if type(self.kind) is not BeliefValueKind:
            raise TypeError("ClaimValue.kind: invalid_type")
        if self.kind is BeliefValueKind.BOOL:
            if type(self.bool_value) is not bool:
                raise TypeError("ClaimValue.bool_value: invalid_type")
            if (
                self.number_value is not None
                or self.text_value is not None
                or self.agent_id is not None
                or self.entity_id is not None
            ):
                raise ValueError("ClaimValue: unexpected_fields")
        elif self.kind is BeliefValueKind.NUMBER:
            if self.number_value is None:
                raise ValueError("ClaimValue.number_value: missing")
            object.__setattr__(
                self,
                "number_value",
                _bounded_number("ClaimValue.number_value", self.number_value),
            )
            if (
                self.bool_value is not None
                or self.text_value is not None
                or self.agent_id is not None
                or self.entity_id is not None
            ):
                raise ValueError("ClaimValue: unexpected_fields")
        elif self.kind is BeliefValueKind.TEXT:
            if self.text_value is None:
                raise ValueError("ClaimValue.text_value: missing")
            object.__setattr__(
                self,
                "text_value",
                require_bounded_text(
                    "ClaimValue.text_value",
                    self.text_value,
                    max_length=_MAX_TEXT_VALUE_CHARS,
                ),
            )
            if (
                self.bool_value is not None
                or self.number_value is not None
                or self.agent_id is not None
                or self.entity_id is not None
            ):
                raise ValueError("ClaimValue: unexpected_fields")
        elif self.kind is BeliefValueKind.AGENT:
            if type(self.agent_id) is not AgentId:
                raise TypeError("ClaimValue.agent_id: invalid_type")
            if (
                self.bool_value is not None
                or self.number_value is not None
                or self.text_value is not None
                or self.entity_id is not None
            ):
                raise ValueError("ClaimValue: unexpected_fields")
        elif self.kind is BeliefValueKind.ENTITY:
            if type(self.entity_id) is not EntityId:
                raise TypeError("ClaimValue.entity_id: invalid_type")
            if (
                self.bool_value is not None
                or self.number_value is not None
                or self.text_value is not None
                or self.agent_id is not None
            ):
                raise ValueError("ClaimValue: unexpected_fields")
        else:  # pragma: no cover - closed enum
            raise ValueError("ClaimValue.kind: unsupported")

    def canonical_token(self) -> str:
        if self.kind is BeliefValueKind.BOOL:
            assert self.bool_value is not None
            return f"bool={'1' if self.bool_value else '0'}"
        if self.kind is BeliefValueKind.NUMBER:
            assert self.number_value is not None
            return f"number={self.number_value:.6f}"
        if self.kind is BeliefValueKind.TEXT:
            assert self.text_value is not None
            return f"text={_escape_token(self.text_value)}"
        if self.kind is BeliefValueKind.AGENT:
            assert self.agent_id is not None
            return f"agent={_escape_token(self.agent_id.value)}"
        assert self.entity_id is not None
        return f"entity={_escape_token(self.entity_id.value)}"

    def __repr__(self) -> str:
        return f"ClaimValue(kind={self.kind.value!r})"


@dataclass(frozen=True, slots=True)
class SemanticClaim:
    """Canonical subject/predicate/typed-value claim."""

    subject: ClaimSubject
    predicate: str
    value: ClaimValue

    def __post_init__(self) -> None:
        if type(self.subject) is not ClaimSubject:
            raise TypeError("SemanticClaim.subject: invalid_type")
        if type(self.value) is not ClaimValue:
            raise TypeError("SemanticClaim.value: invalid_type")
        object.__setattr__(
            self,
            "predicate",
            require_bounded_text(
                "SemanticClaim.predicate",
                self.predicate,
                max_length=_MAX_PREDICATE_CHARS,
            ),
        )

    def __repr__(self) -> str:
        return (
            f"SemanticClaim(subject_kind={self.subject.kind.value!r}, "
            f"predicate_len={len(self.predicate)}, "
            f"value_kind={self.value.kind.value!r})"
        )


def canonical_subject_predicate_key(claim: SemanticClaim) -> str:
    """Deterministic belief key for ``(subject, predicate)`` (value-independent)."""
    if type(claim) is not SemanticClaim:
        raise TypeError("canonical_subject_predicate_key: invalid_type")
    return (
        f"v1|{claim.subject.canonical_token()}|"
        f"predicate={_escape_token(claim.predicate)}"
    )


def canonical_claim_identity(claim: SemanticClaim) -> str:
    """Deterministic full claim identity including typed value."""
    if type(claim) is not SemanticClaim:
        raise TypeError("canonical_claim_identity: invalid_type")
    return f"{canonical_subject_predicate_key(claim)}|{claim.value.canonical_token()}"


@dataclass(frozen=True, slots=True)
class BeliefRevisionId:
    """Stable identity for one append-only belief revision."""

    value: str

    def __post_init__(self) -> None:
        require_stable_id("BeliefRevisionId.value", self.value)


@dataclass(frozen=True, slots=True)
class BeliefPolicyRef:
    """Versioned revision-policy provenance (metadata only)."""

    policy_id: str
    version: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "policy_id",
            require_bounded_text(
                "BeliefPolicyRef.policy_id",
                self.policy_id,
                max_length=_MAX_POLICY_ID_CHARS,
            ),
        )
        object.__setattr__(
            self,
            "version",
            require_bounded_text(
                "BeliefPolicyRef.version",
                self.version,
                max_length=_MAX_POLICY_ID_CHARS,
            ),
        )

    def __repr__(self) -> str:
        return (
            f"BeliefPolicyRef(policy_id={self.policy_id!r}, version={self.version!r})"
        )


@dataclass(frozen=True, slots=True)
class BeliefConfidenceState:
    """Confidence and accumulated evidence masses for the current claim value.

    Confidence is certainty that the current value holds (``0.0`` = uncertainty).
    Decay moves confidence toward ``0.0``, not toward contradiction.
    """

    confidence: float
    support_mass: float
    contradiction_mass: float

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "confidence",
            quantize_score(
                _unit_interval("BeliefConfidenceState.confidence", self.confidence)
            ),
        )
        object.__setattr__(
            self,
            "support_mass",
            quantize_score(
                _unit_interval("BeliefConfidenceState.support_mass", self.support_mass)
            ),
        )
        object.__setattr__(
            self,
            "contradiction_mass",
            quantize_score(
                _unit_interval(
                    "BeliefConfidenceState.contradiction_mass",
                    self.contradiction_mass,
                )
            ),
        )

    def __repr__(self) -> str:
        return (
            f"BeliefConfidenceState(confidence={self.confidence}, "
            f"support_mass={self.support_mass}, "
            f"contradiction_mass={self.contradiction_mass})"
        )


@dataclass(frozen=True, slots=True)
class BeliefEvidenceContribution:
    """One ordered evidence link to an owned memory trace."""

    memory_id: MemoryId
    stance: EvidenceStance
    contribution: float
    ordinal: int
    lineage_root_id: MemoryId
    applied_factors: AppliedTestimonyFactors | None = None

    def __post_init__(self) -> None:
        if type(self.memory_id) is not MemoryId:
            raise TypeError("BeliefEvidenceContribution.memory_id: invalid_type")
        if type(self.stance) is not EvidenceStance:
            raise TypeError("BeliefEvidenceContribution.stance: invalid_type")
        if type(self.lineage_root_id) is not MemoryId:
            raise TypeError("BeliefEvidenceContribution.lineage_root_id: invalid_type")
        if (
            self.applied_factors is not None
            and type(self.applied_factors) is not AppliedTestimonyFactors
        ):
            raise TypeError("BeliefEvidenceContribution.applied_factors: invalid_type")
        object.__setattr__(
            self,
            "contribution",
            quantize_score(
                _unit_interval(
                    "BeliefEvidenceContribution.contribution", self.contribution
                )
            ),
        )
        object.__setattr__(
            self,
            "ordinal",
            require_exact_nonneg_int(
                "BeliefEvidenceContribution.ordinal", self.ordinal
            ),
        )

    def __repr__(self) -> str:
        return (
            f"BeliefEvidenceContribution(memory_id={self.memory_id.value!r}, "
            f"stance={self.stance.value!r}, ordinal={self.ordinal}, "
            f"lineage_root_id={self.lineage_root_id.value!r}, "
            f"has_factors={self.applied_factors is not None})"
        )


@dataclass(frozen=True, slots=True)
class BeliefEvidenceBundle:
    """Supporting and contradicting evidence; mutually exclusive per revision."""

    supporting: tuple[BeliefEvidenceContribution, ...]
    contradicting: tuple[BeliefEvidenceContribution, ...]

    def __post_init__(self) -> None:
        supporting = _require_ordered_models(
            "BeliefEvidenceBundle.supporting",
            self.supporting,
            model_type=BeliefEvidenceContribution,
            max_items=_MAX_EVIDENCE_ITEMS,
        )
        contradicting = _require_ordered_models(
            "BeliefEvidenceBundle.contradicting",
            self.contradicting,
            model_type=BeliefEvidenceContribution,
            max_items=_MAX_EVIDENCE_ITEMS,
        )
        if len(supporting) + len(contradicting) > _MAX_EVIDENCE_ITEMS:
            raise ValueError("BeliefEvidenceBundle: exceeds_max_length")

        for item in supporting:
            if item.stance is not EvidenceStance.SUPPORTING:
                raise ValueError("BeliefEvidenceBundle.supporting: stance_mismatch")
        for item in contradicting:
            if item.stance is not EvidenceStance.CONTRADICTING:
                raise ValueError("BeliefEvidenceBundle.contradicting: stance_mismatch")

        memory_ids: set[str] = set()
        for item in (*supporting, *contradicting):
            mid = item.memory_id.value
            if mid in memory_ids:
                raise ValueError("BeliefEvidenceBundle: duplicate_memory_id")
            memory_ids.add(mid)

        for name, group in (
            ("supporting", supporting),
            ("contradicting", contradicting),
        ):
            ordinals = [item.ordinal for item in group]
            if ordinals != sorted(ordinals):
                raise ValueError(f"BeliefEvidenceBundle.{name}: ordinals_not_monotonic")

        all_ordinals = sorted(item.ordinal for item in (*supporting, *contradicting))
        if len(all_ordinals) != len(set(all_ordinals)):
            raise ValueError("BeliefEvidenceBundle: duplicate_ordinal")
        if all_ordinals and all_ordinals != list(range(len(all_ordinals))):
            raise ValueError("BeliefEvidenceBundle: ordinals_not_dense")

        object.__setattr__(self, "supporting", supporting)
        object.__setattr__(self, "contradicting", contradicting)

    @property
    def total_count(self) -> int:
        return len(self.supporting) + len(self.contradicting)

    def __repr__(self) -> str:
        return (
            f"BeliefEvidenceBundle(support_count={len(self.supporting)}, "
            f"contradiction_count={len(self.contradicting)})"
        )


@dataclass(frozen=True, slots=True)
class BeliefRevision:
    """One append-only revision of an owner-scoped semantic belief."""

    revision_id: BeliefRevisionId
    belief_id: BeliefId
    owner_id: AgentId
    ordinal: int
    logical_tick: int
    claim: SemanticClaim
    confidence: BeliefConfidenceState
    evidence: BeliefEvidenceBundle
    activation_state: BeliefActivationState
    policy: BeliefPolicyRef
    previous_revision_id: BeliefRevisionId | None = None

    def __post_init__(self) -> None:
        if type(self.revision_id) is not BeliefRevisionId:
            raise TypeError("BeliefRevision.revision_id: invalid_type")
        if type(self.belief_id) is not BeliefId:
            raise TypeError("BeliefRevision.belief_id: invalid_type")
        if type(self.owner_id) is not AgentId:
            raise TypeError("BeliefRevision.owner_id: invalid_type")
        if type(self.claim) is not SemanticClaim:
            raise TypeError("BeliefRevision.claim: invalid_type")
        if type(self.confidence) is not BeliefConfidenceState:
            raise TypeError("BeliefRevision.confidence: invalid_type")
        if type(self.evidence) is not BeliefEvidenceBundle:
            raise TypeError("BeliefRevision.evidence: invalid_type")
        if type(self.activation_state) is not BeliefActivationState:
            raise TypeError("BeliefRevision.activation_state: invalid_type")
        if type(self.policy) is not BeliefPolicyRef:
            raise TypeError("BeliefRevision.policy: invalid_type")
        if (
            self.previous_revision_id is not None
            and type(self.previous_revision_id) is not BeliefRevisionId
        ):
            raise TypeError("BeliefRevision.previous_revision_id: invalid_type")
        if (
            self.previous_revision_id is not None
            and self.previous_revision_id.value == self.revision_id.value
        ):
            raise ValueError("BeliefRevision.previous_revision_id: self_reference")
        object.__setattr__(
            self,
            "ordinal",
            require_exact_nonneg_int("BeliefRevision.ordinal", self.ordinal),
        )
        object.__setattr__(
            self,
            "logical_tick",
            require_exact_nonneg_int("BeliefRevision.logical_tick", self.logical_tick),
        )
        if self.ordinal == 0 and self.previous_revision_id is not None:
            raise ValueError("BeliefRevision: initial_has_previous")
        if self.ordinal > 0 and self.previous_revision_id is None:
            raise ValueError("BeliefRevision: non_initial_missing_previous")

    def __repr__(self) -> str:
        return (
            f"BeliefRevision(revision_id={self.revision_id.value!r}, "
            f"belief_id={self.belief_id.value!r}, "
            f"owner_id={self.owner_id.value!r}, "
            f"ordinal={self.ordinal}, "
            f"logical_tick={self.logical_tick}, "
            f"activation_state={self.activation_state.value!r}, "
            f"evidence_count={self.evidence.total_count})"
        )


@dataclass(frozen=True, slots=True)
class SemanticBelief:
    """Current head of an append-only semantic belief revision chain."""

    belief_id: BeliefId
    owner_id: AgentId
    claim: SemanticClaim
    confidence: BeliefConfidenceState
    activation_state: BeliefActivationState
    current_revision_id: BeliefRevisionId
    revision_ordinal: int
    created_tick: int
    updated_tick: int
    policy: BeliefPolicyRef
    evidence_support_count: int
    evidence_contradiction_count: int

    def __post_init__(self) -> None:
        if type(self.belief_id) is not BeliefId:
            raise TypeError("SemanticBelief.belief_id: invalid_type")
        if type(self.owner_id) is not AgentId:
            raise TypeError("SemanticBelief.owner_id: invalid_type")
        if type(self.claim) is not SemanticClaim:
            raise TypeError("SemanticBelief.claim: invalid_type")
        if type(self.confidence) is not BeliefConfidenceState:
            raise TypeError("SemanticBelief.confidence: invalid_type")
        if type(self.activation_state) is not BeliefActivationState:
            raise TypeError("SemanticBelief.activation_state: invalid_type")
        if type(self.current_revision_id) is not BeliefRevisionId:
            raise TypeError("SemanticBelief.current_revision_id: invalid_type")
        if type(self.policy) is not BeliefPolicyRef:
            raise TypeError("SemanticBelief.policy: invalid_type")
        object.__setattr__(
            self,
            "revision_ordinal",
            require_exact_nonneg_int(
                "SemanticBelief.revision_ordinal", self.revision_ordinal
            ),
        )
        created = require_exact_nonneg_int(
            "SemanticBelief.created_tick", self.created_tick
        )
        updated = require_exact_nonneg_int(
            "SemanticBelief.updated_tick", self.updated_tick
        )
        if updated < created:
            raise ValueError("SemanticBelief.updated_tick: before_created")
        object.__setattr__(self, "created_tick", created)
        object.__setattr__(self, "updated_tick", updated)
        object.__setattr__(
            self,
            "evidence_support_count",
            require_exact_nonneg_int(
                "SemanticBelief.evidence_support_count",
                self.evidence_support_count,
            ),
        )
        object.__setattr__(
            self,
            "evidence_contradiction_count",
            require_exact_nonneg_int(
                "SemanticBelief.evidence_contradiction_count",
                self.evidence_contradiction_count,
            ),
        )

    def __repr__(self) -> str:
        return (
            f"SemanticBelief(belief_id={self.belief_id.value!r}, "
            f"owner_id={self.owner_id.value!r}, "
            f"revision_ordinal={self.revision_ordinal}, "
            f"activation_state={self.activation_state.value!r}, "
            f"support_count={self.evidence_support_count}, "
            f"contradiction_count={self.evidence_contradiction_count})"
        )


@dataclass(frozen=True, slots=True)
class SemanticBeliefHistory:
    """Belief head plus ordered append-only revision chain."""

    belief: SemanticBelief
    revisions: tuple[BeliefRevision, ...]

    def __post_init__(self) -> None:
        if type(self.belief) is not SemanticBelief:
            raise TypeError("SemanticBeliefHistory.belief: invalid_type")
        revisions = _require_ordered_models(
            "SemanticBeliefHistory.revisions",
            self.revisions,
            model_type=BeliefRevision,
            max_items=_MAX_REVISIONS,
        )
        if not revisions:
            raise ValueError("SemanticBeliefHistory.revisions: empty")
        if revisions[-1].revision_id != self.belief.current_revision_id:
            raise ValueError("SemanticBeliefHistory: head_revision_mismatch")
        if revisions[-1].ordinal != self.belief.revision_ordinal:
            raise ValueError("SemanticBeliefHistory: head_ordinal_mismatch")
        prev: BeliefRevisionId | None = None
        for index, revision in enumerate(revisions):
            if revision.belief_id != self.belief.belief_id:
                raise ValueError("SemanticBeliefHistory: belief_id_mismatch")
            if revision.owner_id != self.belief.owner_id:
                raise ValueError("SemanticBeliefHistory: owner_mismatch")
            if revision.ordinal != index:
                raise ValueError("SemanticBeliefHistory: ordinal_gap")
            if revision.previous_revision_id != prev:
                raise ValueError("SemanticBeliefHistory: previous_link_mismatch")
            if index > 0 and revision.logical_tick < revisions[index - 1].logical_tick:
                raise ValueError("SemanticBeliefHistory: tick_regression")
            prev = revision.revision_id
        object.__setattr__(self, "revisions", revisions)

    def __repr__(self) -> str:
        return (
            f"SemanticBeliefHistory(belief_id={self.belief.belief_id.value!r}, "
            f"revision_count={len(self.revisions)})"
        )


@dataclass(frozen=True, slots=True)
class BeliefRevisionRequest:
    """Owner-scoped request to form or revise a semantic belief."""

    owner_id: AgentId
    operation_id: str
    logical_tick: int
    claim: SemanticClaim
    evidence: BeliefEvidenceBundle
    policy: BeliefPolicyRef
    belief_id: BeliefId | None = None
    expected_revision_ordinal: int | None = None
    activation_state: BeliefActivationState | None = None
    confidence: BeliefConfidenceState | None = None

    def __post_init__(self) -> None:
        if type(self.owner_id) is not AgentId:
            raise TypeError("BeliefRevisionRequest.owner_id: invalid_type")
        if type(self.claim) is not SemanticClaim:
            raise TypeError("BeliefRevisionRequest.claim: invalid_type")
        if type(self.evidence) is not BeliefEvidenceBundle:
            raise TypeError("BeliefRevisionRequest.evidence: invalid_type")
        if type(self.policy) is not BeliefPolicyRef:
            raise TypeError("BeliefRevisionRequest.policy: invalid_type")
        if self.belief_id is not None and type(self.belief_id) is not BeliefId:
            raise TypeError("BeliefRevisionRequest.belief_id: invalid_type")
        if (
            self.activation_state is not None
            and type(self.activation_state) is not BeliefActivationState
        ):
            raise TypeError("BeliefRevisionRequest.activation_state: invalid_type")
        if (
            self.confidence is not None
            and type(self.confidence) is not BeliefConfidenceState
        ):
            raise TypeError("BeliefRevisionRequest.confidence: invalid_type")
        object.__setattr__(
            self,
            "operation_id",
            require_bounded_text(
                "BeliefRevisionRequest.operation_id",
                self.operation_id,
                max_length=_MAX_OPERATION_ID_CHARS,
            ),
        )
        object.__setattr__(
            self,
            "logical_tick",
            require_exact_nonneg_int(
                "BeliefRevisionRequest.logical_tick", self.logical_tick
            ),
        )
        if self.expected_revision_ordinal is not None:
            object.__setattr__(
                self,
                "expected_revision_ordinal",
                require_exact_nonneg_int(
                    "BeliefRevisionRequest.expected_revision_ordinal",
                    self.expected_revision_ordinal,
                ),
            )

    def __repr__(self) -> str:
        belief = None if self.belief_id is None else self.belief_id.value
        return (
            f"BeliefRevisionRequest(owner_id={self.owner_id.value!r}, "
            f"operation_id={self.operation_id!r}, "
            f"logical_tick={self.logical_tick}, "
            f"belief_id={belief!r}, "
            f"evidence_count={self.evidence.total_count})"
        )


@dataclass(frozen=True, slots=True)
class BeliefRevisionResult:
    """Metadata-only result of a belief revision attempt."""

    belief_id: BeliefId
    revision_id: BeliefRevisionId
    revision_ordinal: int
    activation_state: BeliefActivationState
    idempotent: bool
    created: bool
    retired: bool
    materially_changed: bool
    support_count: int
    contradiction_count: int

    def __post_init__(self) -> None:
        if type(self.belief_id) is not BeliefId:
            raise TypeError("BeliefRevisionResult.belief_id: invalid_type")
        if type(self.revision_id) is not BeliefRevisionId:
            raise TypeError("BeliefRevisionResult.revision_id: invalid_type")
        if type(self.activation_state) is not BeliefActivationState:
            raise TypeError("BeliefRevisionResult.activation_state: invalid_type")
        for name in ("idempotent", "created", "retired", "materially_changed"):
            if type(getattr(self, name)) is not bool:
                raise TypeError(f"BeliefRevisionResult.{name}: invalid_type")
        object.__setattr__(
            self,
            "revision_ordinal",
            require_exact_nonneg_int(
                "BeliefRevisionResult.revision_ordinal", self.revision_ordinal
            ),
        )
        object.__setattr__(
            self,
            "support_count",
            require_exact_nonneg_int(
                "BeliefRevisionResult.support_count", self.support_count
            ),
        )
        object.__setattr__(
            self,
            "contradiction_count",
            require_exact_nonneg_int(
                "BeliefRevisionResult.contradiction_count",
                self.contradiction_count,
            ),
        )

    def __repr__(self) -> str:
        return (
            f"BeliefRevisionResult(belief_id={self.belief_id.value!r}, "
            f"revision_id={self.revision_id.value!r}, "
            f"revision_ordinal={self.revision_ordinal}, "
            f"activation_state={self.activation_state.value!r}, "
            f"idempotent={self.idempotent}, "
            f"created={self.created}, "
            f"retired={self.retired}, "
            f"materially_changed={self.materially_changed}, "
            f"support_count={self.support_count}, "
            f"contradiction_count={self.contradiction_count})"
        )


def project_legacy_belief(belief: SemanticBelief) -> Belief:
    """Lossy projection onto schema-v1 ``Belief`` (opaque claim key as proposition).

    Preserves ownership, confidence, and empty evidence links so legacy readers
    do not reinterpret semantic typed values as free-form proposition text.
    """
    if type(belief) is not SemanticBelief:
        raise TypeError("project_legacy_belief: invalid_type")
    return Belief(
        belief_id=belief.belief_id,
        owner_id=belief.owner_id,
        proposition=canonical_subject_predicate_key(belief.claim),
        confidence=belief.confidence.confidence,
        evidence_memory_ids=(),
    )


class SemanticBeliefStore:
    """Mutable semantic-belief aggregate bound to a single owner."""

    __slots__ = ("_beliefs", "_histories", "_owner_id")

    def __init__(self, owner_id: AgentId) -> None:
        if type(owner_id) is not AgentId:
            raise TypeError("SemanticBeliefStore: invalid_owner_type")
        self._owner_id = owner_id
        self._beliefs: dict[BeliefId, SemanticBelief] = {}
        self._histories: dict[BeliefId, tuple[BeliefRevision, ...]] = {}

    @property
    def owner_id(self) -> AgentId:
        return self._owner_id

    def snapshot(self) -> tuple[SemanticBelief, ...]:
        return tuple(self._beliefs.values())

    def history(self, belief_id: BeliefId) -> SemanticBeliefHistory | None:
        if type(belief_id) is not BeliefId:
            raise TypeError("SemanticBeliefStore.history: invalid_type")
        belief = self._beliefs.get(belief_id)
        revisions = self._histories.get(belief_id)
        if belief is None or revisions is None:
            return None
        return SemanticBeliefHistory(belief=belief, revisions=revisions)

    def write(self, history: SemanticBeliefHistory) -> None:
        if type(history) is not SemanticBeliefHistory:
            raise TypeError("SemanticBeliefStore.write: invalid_type")
        if history.belief.owner_id != self._owner_id:
            raise OwnershipError("ownership")
        self._beliefs[history.belief.belief_id] = history.belief
        self._histories[history.belief.belief_id] = history.revisions

    def __repr__(self) -> str:
        return (
            f"SemanticBeliefStore(owner_id={self._owner_id.value!r}, "
            f"belief_count={len(self._beliefs)})"
        )
