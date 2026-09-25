"""History-derived identity beliefs.

Aspect kinds name what a belief is about. They do not name a person class.
Model construction and the stability helper log nothing. Appraisal logs
metadata only. Validation errors expose field names and stable reason codes.
"""

from __future__ import annotations

import hashlib
import logging
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from agents.models import (
    AgentId,
    DriveKind,
    Goal,
    GoalHorizon,
    GoalOutcomeKind,
    GoalStatus,
)
from memory.belief_formation import DEFAULT_BELIEF_FORMATION_POLICY
from memory.beliefs import (
    BeliefActivationState,
    BeliefEvidenceBundle,
    BeliefEvidenceContribution,
    BeliefRevisionRequest,
    BeliefValueKind,
    ClaimSubject,
    ClaimSubjectKind,
    ClaimValue,
    EvidenceStance,
    SemanticBelief,
    SemanticClaim,
    canonical_subject_predicate_key,
)
from memory.models import (
    BeliefId,
    MemoryId,
    MemorySourceKind,
    MemoryTrace,
    quantize_score,
)
from social.relationships import DirectedRelationshipProfile
from world.identifiers import (
    require_bounded_text,
    require_exact_nonneg_int,
    require_stable_id,
)
from world.observations import ObservedOccurrence

_LOG: Final[logging.Logger] = logging.getLogger("agents.cognition.identity")

IDENTITY_POLICY_ID: Final[str] = "identity-projection"
IDENTITY_POLICY_VERSION: Final[str] = "1"

_PREDICATE_PREFIX: Final[str] = "identity"
_MAX_PREDICATE_CHARS: Final[int] = 128
_MAX_VIEWS: Final[int] = 256
_MAX_EVIDENCE: Final[int] = 64
_MAX_REVISIONS: Final[int] = 64
_MAX_NOTICES: Final[int] = 64
_MAX_TEXT: Final[int] = 128

_FORBIDDEN_IDENTITY_TOKENS: Final[frozenset[str]] = frozenset(
    {
        "warrior",
        "leader",
        "trader",
        "good_person",
        "evil_person",
        "goodperson",
        "evilperson",
        "friend",
        "enemy",
    }
)

_VALUE_REJECTION: Final[dict[BeliefValueKind, str]] = {
    BeliefValueKind.TEXT: "text_value_rejected",
    BeliefValueKind.NUMBER: "number_value_rejected",
    BeliefValueKind.AGENT: "agent_value_rejected",
    BeliefValueKind.ENTITY: "entity_value_rejected",
}


class IdentityAspect(StrEnum):
    """Closed topics a self-belief can be about. Not person classes."""

    ABILITY = "ability"
    WEAKNESS = "weakness"
    RECURRING_BEHAVIOR = "recurring_behavior"
    INFERRED_VALUE = "inferred_value"
    SOCIAL_ROLE = "social_role"
    RELATIONSHIP = "relationship"
    COMMITMENT = "commitment"
    PERCEIVED_STATUS = "perceived_status"
    RELIABILITY = "reliability"
    RISK_TOLERANCE = "risk_tolerance"
    COMPETENCE = "competence"


class IdentityProvenanceKind(StrEnum):
    """Closed predicate segment naming where the evidence came from."""

    OBSERVED_OUTCOME = "observed_outcome"
    OWN_CHOICE = "own_choice"
    SOCIAL_FEEDBACK = "social_feedback"
    RELATIONSHIP_EVIDENCE = "relationship_evidence"
    GOAL_OUTCOME = "goal_outcome"


class IdentityConflictCode(StrEnum):
    """Closed pairing of a selected command with an identity view."""

    COMMITMENT_COMMAND = "commitment_command"
    INFERRED_VALUE_COMMAND = "inferred_value_command"
    RISK_ABOVE_TOLERANCE = "risk_above_tolerance"


def _reason(field: str, code: str) -> ValueError:
    return ValueError(f"{field}: {code}")


def _quantized_unit(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _reason(name, "not_unit_interval")
    number = float(value)
    if not math.isfinite(number) or number < 0.0 or number > 1.0:
        raise _reason(name, "not_unit_interval")
    quantized = quantize_score(number)
    if quantized < 0.0 or quantized > 1.0:
        raise _reason(name, "not_unit_interval")
    return quantized


def _positive_int(name: str, value: object) -> int:
    number = require_exact_nonneg_int(name, value)
    if number < 1:
        raise _reason(name, "not_positive")
    return number


def _ordered[T](
    name: str,
    values: object,
    *,
    item_type: type[T],
    max_items: int,
) -> tuple[T, ...]:
    if isinstance(values, (set, frozenset, Mapping)):
        raise TypeError(f"{name}: not_ordered")
    if isinstance(values, (str, bytes, bytearray)) or not isinstance(values, Sequence):
        raise TypeError(f"{name}: not_ordered")
    items = tuple(values)
    if len(items) > max_items:
        raise _reason(name, "exceeds_max_length")
    for item in items:
        if type(item) is not item_type:
            raise TypeError(f"{name}: invalid_type")
    return items


def _reject_forbidden_token(token: str) -> str:
    if token.casefold() in _FORBIDDEN_IDENTITY_TOKENS:
        raise _reason("identity_claim.token", "forbidden_identity_token")
    return token


def parse_identity_predicate(
    predicate: str,
) -> tuple[IdentityAspect, IdentityProvenanceKind, str]:
    """Parse ``identity.<aspect>.<provenance>.<token>`` or fail closed."""
    text = require_bounded_text(
        "identity_claim.predicate", predicate, max_length=_MAX_PREDICATE_CHARS
    )
    parts = text.split(".")
    if len(parts) != 4 or parts[0] != _PREDICATE_PREFIX:
        raise _reason("identity_claim.predicate", "malformed")
    aspect_token, provenance_token, evidence_token = parts[1], parts[2], parts[3]
    try:
        aspect = IdentityAspect(aspect_token)
    except ValueError as exc:
        raise _reason("identity_claim.aspect", "unknown_aspect") from exc
    try:
        provenance = IdentityProvenanceKind(provenance_token)
    except ValueError as exc:
        raise _reason("identity_claim.provenance", "unknown_provenance") from exc
    token = require_stable_id("identity_claim.token", evidence_token)
    return aspect, provenance, _reject_forbidden_token(token)


def identity_predicate(
    aspect: IdentityAspect,
    provenance: IdentityProvenanceKind,
    token: str,
) -> str:
    """Canonical predicate. Rejects unknown segments and forbidden tokens."""
    if type(aspect) is not IdentityAspect:
        raise TypeError("identity_claim.aspect: invalid_type")
    if type(provenance) is not IdentityProvenanceKind:
        raise TypeError("identity_claim.provenance: invalid_type")
    stable = require_stable_id("identity_claim.token", token)
    _reject_forbidden_token(stable)
    predicate = f"{_PREDICATE_PREFIX}.{aspect.value}.{provenance.value}.{stable}"
    require_bounded_text(
        "identity_claim.predicate", predicate, max_length=_MAX_PREDICATE_CHARS
    )
    return predicate


def build_identity_claim(
    owner_id: AgentId,
    predicate: str,
    value: ClaimValue,
) -> SemanticClaim:
    """Owner subject, identity predicate, and ``BOOL`` ``true`` only.

    Raises a field reason code and returns nothing when validation fails.
    """
    if type(owner_id) is not AgentId:
        raise TypeError("identity_claim.owner_id: invalid_type")
    if type(value) is not ClaimValue:
        raise TypeError("identity_claim.value: invalid_type")
    rejection = _VALUE_REJECTION.get(value.kind)
    if rejection is not None:
        raise _reason("identity_claim.value", rejection)
    if value.bool_value is not True:
        raise _reason("identity_claim.value", "bool_not_true")
    aspect, provenance, token = parse_identity_predicate(predicate)
    return SemanticClaim(
        subject=ClaimSubject(kind=ClaimSubjectKind.AGENT, agent_id=owner_id),
        predicate=identity_predicate(aspect, provenance, token),
        value=ClaimValue(kind=BeliefValueKind.BOOL, bool_value=True),
    )


@dataclass(frozen=True, slots=True)
class IdentityPolicy:
    """Versioned ``identity-projection`` / ``1`` constants. Not runner JSON."""

    policy_id: str = IDENTITY_POLICY_ID
    version: str = IDENTITY_POLICY_VERSION
    min_confidence: float = 0.0
    max_beliefs: int = 32
    depth_weight: float = 0.5
    recency_weight: float = 0.35
    change_weight: float = 0.15
    depth_horizon: int = 4
    tick_horizon: int = 8
    competence_floor: float = 0.6
    weakness_floor: float = 0.6
    conflict_weight: float = 1.0
    inferred_value_confidence_floor: float = 0.4
    risk_rate_ceiling: float = 0.4
    social_scale_floor: float = 0.85
    social_scale_ceiling: float = 1.15
    dissonance_cue_floor: float = 0.5

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "policy_id",
            require_bounded_text(
                "IdentityPolicy.policy_id", self.policy_id, max_length=_MAX_TEXT
            ),
        )
        object.__setattr__(
            self,
            "version",
            require_bounded_text(
                "IdentityPolicy.version", self.version, max_length=_MAX_TEXT
            ),
        )
        if self.policy_id != IDENTITY_POLICY_ID:
            raise _reason("IdentityPolicy.policy_id", "unsupported")
        if self.version != IDENTITY_POLICY_VERSION:
            raise _reason("IdentityPolicy.version", "unsupported")
        object.__setattr__(
            self,
            "min_confidence",
            _quantized_unit("IdentityPolicy.min_confidence", self.min_confidence),
        )
        max_beliefs = _positive_int("IdentityPolicy.max_beliefs", self.max_beliefs)
        if max_beliefs > _MAX_VIEWS:
            raise _reason("IdentityPolicy.max_beliefs", "exceeds_max_length")
        object.__setattr__(self, "max_beliefs", max_beliefs)
        depth_weight = _quantized_unit(
            "IdentityPolicy.depth_weight", self.depth_weight
        )
        recency_weight = _quantized_unit(
            "IdentityPolicy.recency_weight", self.recency_weight
        )
        change_weight = _quantized_unit(
            "IdentityPolicy.change_weight", self.change_weight
        )
        if quantize_score(depth_weight + recency_weight + change_weight) != 1.0:
            raise _reason("IdentityPolicy.weights", "weight_sum")
        object.__setattr__(self, "depth_weight", depth_weight)
        object.__setattr__(self, "recency_weight", recency_weight)
        object.__setattr__(self, "change_weight", change_weight)
        object.__setattr__(
            self,
            "depth_horizon",
            _positive_int("IdentityPolicy.depth_horizon", self.depth_horizon),
        )
        object.__setattr__(
            self,
            "tick_horizon",
            _positive_int("IdentityPolicy.tick_horizon", self.tick_horizon),
        )
        object.__setattr__(
            self,
            "competence_floor",
            _quantized_unit("IdentityPolicy.competence_floor", self.competence_floor),
        )
        object.__setattr__(
            self,
            "weakness_floor",
            _quantized_unit("IdentityPolicy.weakness_floor", self.weakness_floor),
        )
        object.__setattr__(
            self,
            "conflict_weight",
            _quantized_unit("IdentityPolicy.conflict_weight", self.conflict_weight),
        )
        object.__setattr__(
            self,
            "inferred_value_confidence_floor",
            _quantized_unit(
                "IdentityPolicy.inferred_value_confidence_floor",
                self.inferred_value_confidence_floor,
            ),
        )
        object.__setattr__(
            self,
            "risk_rate_ceiling",
            _quantized_unit(
                "IdentityPolicy.risk_rate_ceiling", self.risk_rate_ceiling
            ),
        )
        floor = self.social_scale_floor
        ceiling = self.social_scale_ceiling
        if isinstance(floor, bool) or not isinstance(floor, (int, float)):
            raise _reason("IdentityPolicy.social_scale_floor", "not_finite")
        if isinstance(ceiling, bool) or not isinstance(ceiling, (int, float)):
            raise _reason("IdentityPolicy.social_scale_ceiling", "not_finite")
        floor_number = float(floor)
        ceiling_number = float(ceiling)
        if not math.isfinite(floor_number) or floor_number <= 0.0 or floor_number > 2.0:
            raise _reason("IdentityPolicy.social_scale_floor", "out_of_bounds")
        if (
            not math.isfinite(ceiling_number)
            or ceiling_number <= 0.0
            or ceiling_number > 2.0
        ):
            raise _reason("IdentityPolicy.social_scale_ceiling", "out_of_bounds")
        quantized_floor = quantize_score(floor_number)
        quantized_ceiling = quantize_score(ceiling_number)
        if quantized_floor > quantized_ceiling:
            raise _reason("IdentityPolicy.social_scale", "floor_above_ceiling")
        object.__setattr__(self, "social_scale_floor", quantized_floor)
        object.__setattr__(self, "social_scale_ceiling", quantized_ceiling)
        object.__setattr__(
            self,
            "dissonance_cue_floor",
            _quantized_unit(
                "IdentityPolicy.dissonance_cue_floor", self.dissonance_cue_floor
            ),
        )

    def __repr__(self) -> str:
        return (
            f"IdentityPolicy(version={self.version!r}, "
            f"min_confidence={self.min_confidence}, "
            f"max_beliefs={self.max_beliefs}, "
            f"social_scale_floor={self.social_scale_floor}, "
            f"social_scale_ceiling={self.social_scale_ceiling})"
        )


def default_identity_policy() -> IdentityPolicy:
    return IdentityPolicy()


_LOW_STABILITY_BAND: Final[float] = 0.34
_MID_STABILITY_BAND: Final[float] = 0.67


def identity_stability_band(stability: float) -> str:
    """Closed band for metadata logs. Does not log."""
    if isinstance(stability, bool) or not isinstance(stability, (int, float)):
        raise _reason("identity_stability_band", "not_unit_interval")
    number = float(stability)
    if number < _LOW_STABILITY_BAND:
        return "low"
    if number < _MID_STABILITY_BAND:
        return "mid"
    return "high"


@dataclass(frozen=True, slots=True)
class IdentityRevisionPoint:
    """One revision used only to derive stability. Not a stored belief row."""

    ordinal: int
    tick: int
    confidence: float
    contradicted: bool

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "ordinal",
            require_exact_nonneg_int("IdentityRevisionPoint.ordinal", self.ordinal),
        )
        object.__setattr__(
            self,
            "tick",
            require_exact_nonneg_int("IdentityRevisionPoint.tick", self.tick),
        )
        object.__setattr__(
            self,
            "confidence",
            _quantized_unit("IdentityRevisionPoint.confidence", self.confidence),
        )
        if type(self.contradicted) is not bool:
            raise TypeError("IdentityRevisionPoint.contradicted: invalid_type")

    def __repr__(self) -> str:
        return (
            f"IdentityRevisionPoint(ordinal={self.ordinal}, "
            f"tick={self.tick}, confidence={self.confidence}, "
            f"contradicted={self.contradicted})"
        )


@dataclass(frozen=True, slots=True)
class IdentityRevisionSummary:
    """Ordered public summary of one identity revision."""

    ordinal: int
    tick: int
    activation: BeliefActivationState

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "ordinal",
            require_exact_nonneg_int("IdentityRevisionSummary.ordinal", self.ordinal),
        )
        object.__setattr__(
            self,
            "tick",
            require_exact_nonneg_int("IdentityRevisionSummary.tick", self.tick),
        )
        if type(self.activation) is not BeliefActivationState:
            raise TypeError("IdentityRevisionSummary.activation: invalid_type")

    def __repr__(self) -> str:
        return (
            f"IdentityRevisionSummary(ordinal={self.ordinal}, "
            f"tick={self.tick}, activation={self.activation.value!r})"
        )


def derive_identity_rate(*, support_count: int, contradiction_count: int) -> float:
    """Quantized ``support / (support + contradiction)``. Claim value is unused."""
    support = require_exact_nonneg_int(
        "derive_identity_rate.support_count", support_count
    )
    contradiction = require_exact_nonneg_int(
        "derive_identity_rate.contradiction_count", contradiction_count
    )
    total = support + contradiction
    if total == 0:
        raise _reason("derive_identity_rate", "empty_evidence")
    return quantize_score(support / total)


def derive_identity_stability(
    revisions: Sequence[IdentityRevisionPoint],
    *,
    policy: IdentityPolicy | None = None,
) -> float:
    """Quantized unit stability from ordinal depth, contradiction recency, and change.

    An empty chain is not a view. A first revision is less stable than a long
    uncontradicted chain. This function logs nothing.
    """
    active = policy if policy is not None else default_identity_policy()
    if type(active) is not IdentityPolicy:
        raise TypeError("derive_identity_stability.policy: invalid_type")
    points = _ordered(
        "derive_identity_stability.revisions",
        revisions,
        item_type=IdentityRevisionPoint,
        max_items=_MAX_REVISIONS,
    )
    if not points:
        raise _reason("derive_identity_stability", "empty_history")
    ordered = tuple(sorted(points, key=lambda item: (item.ordinal, item.tick)))
    for index, point in enumerate(ordered):
        if point.ordinal != index:
            raise _reason("derive_identity_stability.revisions", "ordinal_gap")
        if index > 0 and point.tick < ordered[index - 1].tick:
            raise _reason("derive_identity_stability.revisions", "tick_regression")
    depth = len(ordered)
    depth_span = depth - 1
    depth_term = depth_span / (depth_span + active.depth_horizon)
    last_contradicted = max(
        (point.tick for point in ordered if point.contradicted),
        default=ordered[0].tick,
    )
    if any(point.contradicted for point in ordered):
        ticks_since = ordered[-1].tick - last_contradicted
    else:
        ticks_since = ordered[-1].tick - ordered[0].tick
    recency_term = ticks_since / (ticks_since + active.tick_horizon)
    if depth == 1:
        change_term = 0.0
    else:
        delta = abs(ordered[-1].confidence - ordered[-2].confidence)
        change_term = 1.0 - min(1.0, delta)
    raw = (
        active.depth_weight * depth_term
        + active.recency_weight * recency_term
        + active.change_weight * change_term
    )
    return quantize_score(min(1.0, max(0.0, raw)))


@dataclass(frozen=True, slots=True)
class IdentityDissonanceNotice:
    """Prior-cursor notice that an action contradicted a self-belief."""

    owner_id: AgentId
    tick: int
    belief_id: BeliefId
    aspect: IdentityAspect
    conflict_code: IdentityConflictCode
    magnitude: float

    def __post_init__(self) -> None:
        if type(self.owner_id) is not AgentId:
            raise TypeError("IdentityDissonanceNotice.owner_id: invalid_type")
        if type(self.belief_id) is not BeliefId:
            raise TypeError("IdentityDissonanceNotice.belief_id: invalid_type")
        if type(self.aspect) is not IdentityAspect:
            raise TypeError("IdentityDissonanceNotice.aspect: invalid_type")
        if type(self.conflict_code) is not IdentityConflictCode:
            raise TypeError("IdentityDissonanceNotice.conflict_code: invalid_type")
        object.__setattr__(
            self,
            "tick",
            require_exact_nonneg_int("IdentityDissonanceNotice.tick", self.tick),
        )
        object.__setattr__(
            self,
            "magnitude",
            _quantized_unit("IdentityDissonanceNotice.magnitude", self.magnitude),
        )

    def __repr__(self) -> str:
        return (
            f"IdentityDissonanceNotice(tick={self.tick}, "
            f"aspect={self.aspect.value!r}, "
            f"conflict_code={self.conflict_code.value!r}, "
            f"magnitude={self.magnitude})"
        )


@dataclass(frozen=True, slots=True)
class IdentityBeliefView:
    """One structured identity belief. Rate and stability are derived."""

    belief_id: BeliefId
    aspect: IdentityAspect
    provenance: IdentityProvenanceKind
    evidence_token: str
    claim: SemanticClaim
    confidence: float
    derived_rate: float
    supporting_memory_ids: tuple[MemoryId, ...]
    contradicting_memory_ids: tuple[MemoryId, ...]
    derived_stability: float
    activation: BeliefActivationState
    revisions: tuple[IdentityRevisionSummary, ...]

    def __post_init__(self) -> None:
        if type(self.belief_id) is not BeliefId:
            raise TypeError("IdentityBeliefView.belief_id: invalid_type")
        if type(self.aspect) is not IdentityAspect:
            raise TypeError("IdentityBeliefView.aspect: invalid_type")
        if type(self.provenance) is not IdentityProvenanceKind:
            raise TypeError("IdentityBeliefView.provenance: invalid_type")
        if type(self.claim) is not SemanticClaim:
            raise TypeError("IdentityBeliefView.claim: invalid_type")
        if type(self.activation) is not BeliefActivationState:
            raise TypeError("IdentityBeliefView.activation: invalid_type")
        if self.activation is BeliefActivationState.RETIRED:
            raise _reason("IdentityBeliefView.activation", "retired")
        token = _reject_forbidden_token(
            require_stable_id("IdentityBeliefView.evidence_token", self.evidence_token)
        )
        object.__setattr__(self, "evidence_token", token)
        expected = identity_predicate(self.aspect, self.provenance, token)
        if self.claim.predicate != expected:
            raise _reason("IdentityBeliefView.claim", "predicate_mismatch")
        if (
            self.claim.value.kind is not BeliefValueKind.BOOL
            or self.claim.value.bool_value is not True
        ):
            raise _reason("IdentityBeliefView.claim", "bool_not_true")
        if self.claim.subject.kind is not ClaimSubjectKind.AGENT:
            raise _reason("IdentityBeliefView.claim", "owner_mismatch")
        object.__setattr__(
            self,
            "confidence",
            _quantized_unit("IdentityBeliefView.confidence", self.confidence),
        )
        object.__setattr__(
            self,
            "derived_rate",
            _quantized_unit("IdentityBeliefView.derived_rate", self.derived_rate),
        )
        object.__setattr__(
            self,
            "derived_stability",
            _quantized_unit(
                "IdentityBeliefView.derived_stability", self.derived_stability
            ),
        )
        supporting = _ordered(
            "IdentityBeliefView.supporting_memory_ids",
            self.supporting_memory_ids,
            item_type=MemoryId,
            max_items=_MAX_EVIDENCE,
        )
        contradicting = _ordered(
            "IdentityBeliefView.contradicting_memory_ids",
            self.contradicting_memory_ids,
            item_type=MemoryId,
            max_items=_MAX_EVIDENCE,
        )
        seen: set[str] = set()
        for item in (*supporting, *contradicting):
            if item.value in seen:
                raise _reason("IdentityBeliefView.memory_ids", "duplicate_memory_id")
            seen.add(item.value)
        object.__setattr__(self, "supporting_memory_ids", supporting)
        object.__setattr__(self, "contradicting_memory_ids", contradicting)
        revisions = _ordered(
            "IdentityBeliefView.revisions",
            self.revisions,
            item_type=IdentityRevisionSummary,
            max_items=_MAX_REVISIONS,
        )
        if not revisions:
            raise _reason("IdentityBeliefView.revisions", "empty_history")
        for index, revision in enumerate(revisions):
            if revision.ordinal != index:
                raise _reason("IdentityBeliefView.revisions", "ordinal_gap")
            if index > 0 and revision.tick < revisions[index - 1].tick:
                raise _reason("IdentityBeliefView.revisions", "tick_regression")
        object.__setattr__(self, "revisions", revisions)

    def __repr__(self) -> str:
        return (
            f"IdentityBeliefView(aspect={self.aspect.value!r}, "
            f"provenance={self.provenance.value!r}, "
            f"support_count={len(self.supporting_memory_ids)}, "
            f"contradiction_count={len(self.contradicting_memory_ids)}, "
            f"confidence={self.confidence}, "
            f"derived_rate={self.derived_rate}, "
            f"derived_stability={self.derived_stability}, "
            f"revision_count={len(self.revisions)}, "
            f"activation={self.activation.value!r})"
        )


def assemble_identity_belief_view(
    *,
    belief_id: BeliefId,
    claim: SemanticClaim,
    confidence: float,
    supporting_memory_ids: Sequence[MemoryId],
    contradicting_memory_ids: Sequence[MemoryId],
    activation: BeliefActivationState,
    revision_points: Sequence[IdentityRevisionPoint],
    revision_summaries: Sequence[IdentityRevisionSummary],
    policy: IdentityPolicy | None = None,
) -> IdentityBeliefView:
    """Build one view. The same chain and counts always yield the same numbers."""
    aspect, provenance, token = parse_identity_predicate(claim.predicate)
    support_ids = tuple(supporting_memory_ids)
    contradict_ids = tuple(contradicting_memory_ids)
    summaries = tuple(revision_summaries)
    points = tuple(revision_points)
    if len(summaries) != len(points):
        raise _reason("assemble_identity_belief_view", "revision_mismatch")
    for summary, point in zip(summaries, points, strict=True):
        if summary.ordinal != point.ordinal or summary.tick != point.tick:
            raise _reason("assemble_identity_belief_view", "revision_mismatch")
    return IdentityBeliefView(
        belief_id=belief_id,
        aspect=aspect,
        provenance=provenance,
        evidence_token=token,
        claim=claim,
        confidence=confidence,
        derived_rate=derive_identity_rate(
            support_count=len(support_ids),
            contradiction_count=len(contradict_ids),
        ),
        supporting_memory_ids=support_ids,
        contradicting_memory_ids=contradict_ids,
        derived_stability=derive_identity_stability(points, policy=policy),
        activation=activation,
        revisions=summaries,
    )


@dataclass(frozen=True, slots=True)
class IdentityState:
    """Ordered identity views for one owner. Empty history is not a view."""

    owner_id: AgentId
    policy_id: str
    policy_version: str
    views: tuple[IdentityBeliefView, ...]
    aggregate_confidence: float
    dissonance_notices: tuple[IdentityDissonanceNotice, ...] = ()

    def __post_init__(self) -> None:
        if type(self.owner_id) is not AgentId:
            raise TypeError("IdentityState.owner_id: invalid_type")
        object.__setattr__(
            self,
            "policy_id",
            require_bounded_text(
                "IdentityState.policy_id", self.policy_id, max_length=_MAX_TEXT
            ),
        )
        object.__setattr__(
            self,
            "policy_version",
            require_bounded_text(
                "IdentityState.policy_version",
                self.policy_version,
                max_length=_MAX_TEXT,
            ),
        )
        if self.policy_id != IDENTITY_POLICY_ID:
            raise _reason("IdentityState.policy_id", "unsupported")
        if self.policy_version != IDENTITY_POLICY_VERSION:
            raise _reason("IdentityState.policy_version", "unsupported")
        views = _ordered(
            "IdentityState.views",
            self.views,
            item_type=IdentityBeliefView,
            max_items=_MAX_VIEWS,
        )
        seen: set[str] = set()
        for view in views:
            if view.claim.subject.agent_id != self.owner_id:
                raise _reason("IdentityState.views", "owner_mismatch")
            if view.belief_id.value in seen:
                raise _reason("IdentityState.views", "duplicate_belief_id")
            seen.add(view.belief_id.value)
        object.__setattr__(self, "views", views)
        object.__setattr__(
            self,
            "aggregate_confidence",
            _quantized_unit(
                "IdentityState.aggregate_confidence", self.aggregate_confidence
            ),
        )
        notices = _ordered(
            "IdentityState.dissonance_notices",
            self.dissonance_notices,
            item_type=IdentityDissonanceNotice,
            max_items=_MAX_NOTICES,
        )
        for notice in notices:
            if notice.owner_id != self.owner_id:
                raise _reason("IdentityState.dissonance_notices", "owner_mismatch")
        object.__setattr__(self, "dissonance_notices", notices)

    def __repr__(self) -> str:
        return (
            f"IdentityState(owner_id={self.owner_id.value!r}, "
            f"policy_version={self.policy_version!r}, "
            f"view_count={len(self.views)}, "
            f"aggregate_confidence={self.aggregate_confidence}, "
            f"dissonance_count={len(self.dissonance_notices)})"
        )


def aggregate_identity_confidence(views: Sequence[IdentityBeliefView]) -> float:
    """Quantized mean confidence. An empty tuple is ``0.0``."""
    items = tuple(views)
    if not items:
        return 0.0
    return quantize_score(sum(item.confidence for item in items) / len(items))


_REPEAT_MIN: Final[int] = 2
_COMMITMENT_HORIZONS: Final[frozenset[GoalHorizon]] = frozenset(
    {GoalHorizon.LONG_TERM, GoalHorizon.DESIRE}
)


@dataclass(frozen=True, slots=True)
class IdentityAppraisal:
    """Revision requests from one owner tick. Not a belief write."""

    owner_id: AgentId
    tick: int
    requests: tuple[BeliefRevisionRequest, ...]
    reason_counts: tuple[tuple[str, int], ...]

    def __post_init__(self) -> None:
        if type(self.owner_id) is not AgentId:
            raise TypeError("IdentityAppraisal.owner_id: invalid_type")
        object.__setattr__(
            self, "tick", require_exact_nonneg_int("IdentityAppraisal.tick", self.tick)
        )
        requests = _ordered(
            "IdentityAppraisal.requests",
            self.requests,
            item_type=BeliefRevisionRequest,
            max_items=_MAX_VIEWS,
        )
        object.__setattr__(self, "requests", requests)
        if isinstance(self.reason_counts, (set, frozenset, Mapping)):
            raise TypeError("IdentityAppraisal.reason_counts: not_ordered")
        counts = tuple(self.reason_counts)
        object.__setattr__(self, "reason_counts", counts)

    def __repr__(self) -> str:
        return (
            f"IdentityAppraisal(owner_id={self.owner_id.value!r}, tick={self.tick}, "
            f"request_count={len(self.requests)}, "
            f"reason_count={len(self.reason_counts)})"
        )


def _count_reason(counts: dict[str, int], code: str) -> None:
    counts[code] = counts.get(code, 0) + 1
    _LOG.warning(
        "identity_appraisal_skipped",
        extra={"reason_code": code},
    )


def _safe_token(token: str) -> str | None:
    try:
        stable = require_stable_id("identity_claim.token", token)
    except ValueError:
        return None
    if stable.casefold() in _FORBIDDEN_IDENTITY_TOKENS:
        return None
    return stable


def _citable_memories(
    owner_id: AgentId, memories: Sequence[MemoryTrace]
) -> tuple[MemoryTrace, ...]:
    cited: list[MemoryTrace] = []
    for memory in memories:
        if type(memory) is not MemoryTrace:
            raise TypeError("appraise_identity.memories: invalid_type")
        if memory.owner_id != owner_id:
            _LOG.error(
                "identity_appraisal_rejected",
                extra={"reason_code": "owner_mismatch", "owner_id": owner_id.value},
            )
            raise ValueError("appraise_identity: owner_mismatch")
        if memory.forgotten_at_tick is not None:
            continue
        cited.append(memory)
    return tuple(cited)


def _evidence_bundle(memory_ids: Sequence[MemoryId]) -> BeliefEvidenceBundle:
    supporting: list[BeliefEvidenceContribution] = []
    for ordinal, memory_id in enumerate(memory_ids):
        supporting.append(
            BeliefEvidenceContribution(
                memory_id=memory_id,
                stance=EvidenceStance.SUPPORTING,
                contribution=0.5,
                ordinal=ordinal,
                lineage_root_id=memory_id,
            )
        )
    return BeliefEvidenceBundle(supporting=tuple(supporting), contradicting=())


def _operation_id(
    owner_id: AgentId, tick: int, aspect: IdentityAspect, claim: SemanticClaim
) -> str:
    raw = (
        f"{owner_id.value}|{tick}|{aspect.value}|"
        f"{canonical_subject_predicate_key(claim)}"
    )
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]
    return f"identity-{aspect.value}-{digest}"


def _future_harm(future: object) -> float:
    risks = getattr(future, "risks", ())
    if not risks:
        return 0.0
    return max(float(risk.severity) for risk in risks)


def appraise_identity(
    *,
    owner_id: AgentId,
    tick: int,
    memories: Sequence[MemoryTrace],
    occurrences: Sequence[ObservedOccurrence],
    goals: Sequence[Goal],
    relationships: Sequence[DirectedRelationshipProfile],
    futures: object | None,
    beliefs: Sequence[SemanticBelief],
    self_model: object,
) -> IdentityAppraisal:
    """Emit identity revision requests. Does not write beliefs or read journals."""
    from agents.cognition.models import PossibleFutures, SelfModel

    if type(owner_id) is not AgentId:
        raise TypeError("appraise_identity.owner_id: invalid_type")
    tick = require_exact_nonneg_int("appraise_identity.tick", tick)
    if type(self_model) is not SelfModel:
        raise TypeError("appraise_identity.self_model: invalid_type")
    if self_model.owner_id != owner_id:
        _LOG.error(
            "identity_appraisal_rejected",
            extra={"reason_code": "owner_mismatch", "owner_id": owner_id.value},
        )
        raise ValueError("appraise_identity: owner_mismatch")
    if futures is not None and type(futures) is not PossibleFutures:
        raise TypeError("appraise_identity.futures: invalid_type")
    if futures is not None and futures.owner_id != owner_id:
        _LOG.error(
            "identity_appraisal_rejected",
            extra={"reason_code": "owner_mismatch", "owner_id": owner_id.value},
        )
        raise ValueError("appraise_identity: owner_mismatch")
    _LOG.debug(
        "identity_appraisal_start",
        extra={
            "owner_id": owner_id.value,
            "tick": tick,
            "policy_version": IDENTITY_POLICY_VERSION,
        },
    )
    cited = _citable_memories(owner_id, memories)
    cited_by_id = {memory.memory_id.value: memory.memory_id for memory in cited}
    reason_counts: dict[str, int] = {}
    if not cited:
        _count_reason(reason_counts, "no_memory_evidence")
        appraisal = _finish_appraisal(owner_id, tick, (), reason_counts, 0)
        return appraisal

    by_key: dict[str, SemanticBelief] = {}
    for belief in beliefs:
        if type(belief) is not SemanticBelief:
            raise TypeError("appraise_identity.beliefs: invalid_type")
        if belief.owner_id != owner_id:
            _LOG.error(
                "identity_appraisal_rejected",
                extra={"reason_code": "owner_mismatch", "owner_id": owner_id.value},
            )
            raise ValueError("appraise_identity: owner_mismatch")
        by_key[canonical_subject_predicate_key(belief.claim)] = belief

    grouped: dict[
        tuple[IdentityAspect, IdentityProvenanceKind, str], list[MemoryId]
    ] = {}

    def add(
        aspect: IdentityAspect,
        provenance: IdentityProvenanceKind,
        token: str,
        memory_ids: Sequence[MemoryId],
    ) -> None:
        stable = _safe_token(token)
        if stable is None:
            _count_reason(reason_counts, "forbidden_identity_token")
            return
        ids = tuple(memory_ids)
        if not ids:
            _count_reason(reason_counts, "no_memory_evidence")
            return
        key = (aspect, provenance, stable)
        bucket = grouped.setdefault(key, [])
        seen = {item.value for item in bucket}
        for memory_id in ids:
            if memory_id.value not in seen:
                bucket.append(memory_id)
                seen.add(memory_id.value)

    kind_counts: dict[str, int] = {}
    success_kinds: set[str] = set()
    failure_kinds: set[str] = set()
    for occurrence in occurrences:
        if type(occurrence) is not ObservedOccurrence:
            raise TypeError("appraise_identity.occurrences: invalid_type")
        kind_counts[occurrence.kind] = kind_counts.get(occurrence.kind, 0) + 1
        matched = tuple(
            memory.memory_id
            for memory in cited
            if memory.source_tick == occurrence.provenance.source_tick
        )
        evidence = matched or (cited[0].memory_id,)
        if occurrence.success is True:
            success_kinds.add(occurrence.kind)
            add(
                IdentityAspect.ABILITY,
                IdentityProvenanceKind.OBSERVED_OUTCOME,
                occurrence.kind,
                evidence,
            )
            add(
                IdentityAspect.COMPETENCE,
                IdentityProvenanceKind.OBSERVED_OUTCOME,
                occurrence.kind,
                evidence,
            )
        elif occurrence.success is False:
            failure_kinds.add(occurrence.kind)
            add(
                IdentityAspect.WEAKNESS,
                IdentityProvenanceKind.OBSERVED_OUTCOME,
                occurrence.kind,
                evidence,
            )

    for memory in cited:
        for concept in memory.concepts:
            text = concept.concept
            if text in kind_counts:
                kind_counts[text] = kind_counts.get(text, 0) + 1
    for kind, count in sorted(kind_counts.items()):
        if count < _REPEAT_MIN:
            continue
        evidence = (cited[0].memory_id,)
        add(
            IdentityAspect.RECURRING_BEHAVIOR,
            IdentityProvenanceKind.OWN_CHOICE,
            kind,
            evidence,
        )
        add(
            IdentityAspect.INFERRED_VALUE,
            IdentityProvenanceKind.OWN_CHOICE,
            kind,
            evidence,
        )

    drive_counts: dict[str, int] = {}
    for goal in goals:
        if type(goal) is not Goal:
            raise TypeError("appraise_identity.goals: invalid_type")
        if goal.owner_id != owner_id:
            _LOG.error(
                "identity_appraisal_rejected",
                extra={"reason_code": "owner_mismatch", "owner_id": owner_id.value},
            )
            raise ValueError("appraise_identity: owner_mismatch")
        for drive in goal.drive_links:
            if type(drive) is not DriveKind:
                continue
            drive_counts[drive.value] = drive_counts.get(drive.value, 0) + 1
        committed = goal.status is GoalStatus.ACTIVE and (
            goal.horizon in _COMMITMENT_HORIZONS
        )
        if committed:
            add(
                IdentityAspect.COMMITMENT,
                IdentityProvenanceKind.GOAL_OUTCOME,
                goal.goal_id.value,
                (cited[0].memory_id,),
            )
    for drive, count in sorted(drive_counts.items()):
        if count < _REPEAT_MIN:
            continue
        add(
            IdentityAspect.INFERRED_VALUE,
            IdentityProvenanceKind.OWN_CHOICE,
            drive,
            (cited[0].memory_id,),
        )

    for kind in sorted(success_kinds | failure_kinds):
        add(
            IdentityAspect.RELIABILITY,
            IdentityProvenanceKind.OBSERVED_OUTCOME,
            kind,
            (cited[0].memory_id,),
        )

    social_ids = tuple(
        memory.memory_id
        for memory in cited
        if memory.provenance.kind is MemorySourceKind.COMMUNICATED
    )
    for profile in relationships:
        if type(profile) is not DirectedRelationshipProfile:
            raise TypeError("appraise_identity.relationships: invalid_type")
        if profile.source_id != owner_id:
            _LOG.error(
                "identity_appraisal_rejected",
                extra={"reason_code": "owner_mismatch", "owner_id": owner_id.value},
            )
            raise ValueError("appraise_identity: owner_mismatch")
        if social_ids:
            add(
                IdentityAspect.SOCIAL_ROLE,
                IdentityProvenanceKind.SOCIAL_FEEDBACK,
                profile.target_id.value,
                social_ids[:1],
            )
            add(
                IdentityAspect.PERCEIVED_STATUS,
                IdentityProvenanceKind.SOCIAL_FEEDBACK,
                profile.target_id.value,
                social_ids[:1],
            )
        for dimension in profile.dimensions:
            refs = tuple(
                cited_by_id[item.memory_ref]
                for item in dimension.evidence
                if item.memory_ref in cited_by_id
            )
            add(
                IdentityAspect.RELATIONSHIP,
                IdentityProvenanceKind.RELATIONSHIP_EVIDENCE,
                dimension.dimension.value,
                refs,
            )

    if futures is not None and len(futures.futures) >= 2:
        ranked = tuple(sorted(futures.futures, key=lambda item: item.future_id))
        harms = tuple(_future_harm(item) for item in ranked)
        winner_index = max(
            range(len(ranked)),
            key=lambda index: (harms[index], ranked[index].future_id),
        )
        winner = ranked[winner_index]
        if _future_harm(winner) > min(harms):
            cited_future = tuple(
                cited_by_id[memory_id]
                for memory_id in winner.source_refs.memory_ids
                if memory_id in cited_by_id
            )
            add(
                IdentityAspect.RISK_TOLERANCE,
                IdentityProvenanceKind.OWN_CHOICE,
                winner.direction.value,
                cited_future,
            )

    requests: list[BeliefRevisionRequest] = []
    for (aspect, provenance, token), memory_ids in sorted(
        grouped.items(),
        key=lambda item: (item[0][0].value, item[0][1].value, item[0][2]),
    ):
        predicate = identity_predicate(aspect, provenance, token)
        claim = build_identity_claim(
            owner_id,
            predicate,
            ClaimValue(kind=BeliefValueKind.BOOL, bool_value=True),
        )
        prior = by_key.get(canonical_subject_predicate_key(claim))
        requests.append(
            BeliefRevisionRequest(
                owner_id=owner_id,
                operation_id=_operation_id(owner_id, tick, aspect, claim),
                logical_tick=tick,
                claim=claim,
                evidence=_evidence_bundle(memory_ids),
                policy=DEFAULT_BELIEF_FORMATION_POLICY.as_ref(),
                belief_id=None if prior is None else prior.belief_id,
                expected_revision_ordinal=(
                    None if prior is None else prior.revision_ordinal
                ),
            )
        )
    return _finish_appraisal(
        owner_id, tick, tuple(requests), reason_counts, len(grouped)
    )


def _finish_appraisal(
    owner_id: AgentId,
    tick: int,
    requests: tuple[BeliefRevisionRequest, ...],
    reason_counts: dict[str, int],
    candidate_count: int,
) -> IdentityAppraisal:
    ordered_reasons = tuple(sorted(reason_counts.items()))
    _LOG.debug(
        "identity_appraisal_complete",
        extra={
            "owner_id": owner_id.value,
            "tick": tick,
            "policy_version": IDENTITY_POLICY_VERSION,
            "candidate_count": candidate_count,
            "emitted_count": len(requests),
            "skipped_count": sum(reason_counts.values()),
            "reason_counts": ordered_reasons,
        },
    )
    return IdentityAppraisal(
        owner_id=owner_id,
        tick=tick,
        requests=requests,
        reason_counts=ordered_reasons,
    )


def without_overlapping_identity_requests(
    requests: Sequence[BeliefRevisionRequest],
    *,
    consolidation: object | None,
    reflection: object | None,
) -> tuple[BeliefRevisionRequest, ...]:
    """Drop identity requests whose belief id another writer already revises."""
    blocked: dict[str, str] = {}
    _collect_blocked_belief_ids(consolidation, "consolidation", blocked)
    _collect_blocked_belief_ids(reflection, "reflection", blocked)
    kept: list[BeliefRevisionRequest] = []
    dropped_by_writer: dict[str, int] = {}
    for request in requests:
        if type(request) is not BeliefRevisionRequest:
            raise TypeError("identity_requests: invalid_type")
        belief_id = None if request.belief_id is None else request.belief_id.value
        writer = None if belief_id is None else blocked.get(belief_id)
        if writer is None:
            kept.append(request)
            continue
        dropped_by_writer[writer] = dropped_by_writer.get(writer, 0) + 1
    for writer, dropped_count in sorted(dropped_by_writer.items()):
        _LOG.debug(
            "identity_overlap_dropped",
            extra={"dropped_count": dropped_count, "writer": writer},
        )
    return tuple(kept)


def _collect_blocked_belief_ids(
    plan: object | None, writer: str, blocked: dict[str, str]
) -> None:
    if plan is None:
        return
    from agents.cognition.consolidation import OfflineConsolidationPlan
    from agents.cognition.reflection import ReflectionPlan

    if (
        type(plan) is not OfflineConsolidationPlan
        and type(plan) is not ReflectionPlan
    ):
        return
    revisions = plan.belief_revisions
    for request in revisions:
        if type(request) is not BeliefRevisionRequest or request.belief_id is None:
            continue
        blocked.setdefault(request.belief_id.value, writer)


_COMMAND_DIRECTION: Final[Mapping[str, str]] = {
    "wait": "wait",
    "sleep": "sleep",
    "search": "search",
    "drink": "drink",
    "eat": "eat",
    "move": "move",
    "flee": "flee",
    "talk": "communicate",
    "ask": "communicate",
    "tell": "communicate",
    "help": "help",
    "attack": "attack",
}
_OPEN_ACTIVATION: Final[frozenset[BeliefActivationState]] = frozenset(
    {BeliefActivationState.CANDIDATE, BeliefActivationState.ACTIVE}
)


@dataclass(frozen=True, slots=True)
class IdentityDissonanceResult:
    """Notices emitted now, contradicting revisions, and notices still waiting."""

    notices: tuple[IdentityDissonanceNotice, ...]
    requests: tuple[BeliefRevisionRequest, ...]
    deferred: tuple[IdentityDissonanceNotice, ...]

    def __post_init__(self) -> None:
        notices = _ordered(
            "IdentityDissonanceResult.notices",
            self.notices,
            item_type=IdentityDissonanceNotice,
            max_items=_MAX_NOTICES,
        )
        requests = _ordered(
            "IdentityDissonanceResult.requests",
            self.requests,
            item_type=BeliefRevisionRequest,
            max_items=_MAX_VIEWS,
        )
        deferred = _ordered(
            "IdentityDissonanceResult.deferred",
            self.deferred,
            item_type=IdentityDissonanceNotice,
            max_items=_MAX_NOTICES,
        )
        object.__setattr__(self, "notices", notices)
        object.__setattr__(self, "requests", requests)
        object.__setattr__(self, "deferred", deferred)

    def __repr__(self) -> str:
        return (
            f"IdentityDissonanceResult(notice_count={len(self.notices)}, "
            f"request_count={len(self.requests)}, "
            f"deferred_count={len(self.deferred)})"
        )


def command_direction_code(command: object) -> str:
    """Closed direction code for a selected command. Not an argument dump."""
    from world.actions import require_agent_command

    selected = require_agent_command(command)
    raw = type(selected).__name__.lower()
    return _COMMAND_DIRECTION.get(raw, raw)


def satisfying_command_kinds(goal: Goal) -> frozenset[str]:
    """Command directions that advance this goal. Mirrors closed goal effects."""
    if type(goal) is not Goal:
        raise TypeError("satisfying_command_kinds: invalid_type")
    outcome = goal.outcome
    if outcome is None:
        return frozenset()
    if outcome.kind is GoalOutcomeKind.SATISFY_DRIVE:
        if outcome.drive_kind is DriveKind.THIRST:
            return frozenset({"drink"})
        if outcome.drive_kind is DriveKind.HUNGER:
            return frozenset({"eat"})
        if outcome.drive_kind is DriveKind.FATIGUE:
            return frozenset({"sleep"})
        return frozenset()
    if outcome.kind is GoalOutcomeKind.PRESERVE_LIFE:
        return frozenset({"flee"})
    if outcome.kind is GoalOutcomeKind.GATHER_INFORMATION:
        return frozenset({"search"})
    if outcome.kind is GoalOutcomeKind.REACH_PLACE:
        return frozenset({"move"})
    if outcome.kind is GoalOutcomeKind.RELATE_TO_AGENT:
        return frozenset({"communicate", "help"})
    if outcome.kind is GoalOutcomeKind.AVOID_ENTITY:
        return frozenset({"flee"})
    return frozenset()


def detect_identity_dissonance(
    *,
    owner_id: AgentId,
    tick: int,
    command: object,
    goals: Sequence[Goal],
    futures: object | None,
    identity: object | None,
    memories: Sequence[MemoryTrace],
    selected_future_id: str | None = None,
    policy: IdentityPolicy | None = None,
    deferred: Sequence[IdentityDissonanceNotice] = (),
) -> IdentityDissonanceResult:
    """Pair the chosen command with identity views. Does not change the command."""
    from agents.cognition.models import PossibleFutures

    if type(owner_id) is not AgentId:
        raise TypeError("detect_identity_dissonance.owner_id: invalid_type")
    tick = require_exact_nonneg_int("detect_identity_dissonance.tick", tick)
    direction = command_direction_code(command)
    active = policy if policy is not None else IdentityPolicy()
    if type(active) is not IdentityPolicy:
        raise TypeError("detect_identity_dissonance.policy: invalid_type")
    if identity is not None and type(identity) is not IdentityState:
        raise TypeError("detect_identity_dissonance.identity: invalid_type")
    if identity is not None and identity.owner_id != owner_id:
        _LOG.error(
            "identity_dissonance_rejected",
            extra={"reason_code": "owner_mismatch", "owner_id": owner_id.value},
        )
        raise ValueError("detect_identity_dissonance: owner_mismatch")
    if futures is not None and type(futures) is not PossibleFutures:
        raise TypeError("detect_identity_dissonance.futures: invalid_type")
    cited = _citable_memories(owner_id, memories)
    cited_ids = {memory.memory_id.value: memory.memory_id for memory in cited}
    goals_by_id = _goals_by_id(owner_id, goals)
    views = () if identity is None else identity.views
    views_by_id = {view.belief_id.value: view for view in views}
    emitted: list[IdentityDissonanceNotice] = []
    requests: list[BeliefRevisionRequest] = []
    still_deferred: list[IdentityDissonanceNotice] = []
    handled: set[str] = set()

    for notice in deferred:
        if type(notice) is not IdentityDissonanceNotice:
            raise TypeError("detect_identity_dissonance.deferred: invalid_type")
        if notice.owner_id != owner_id:
            _LOG.error(
                "identity_dissonance_rejected",
                extra={"reason_code": "owner_mismatch", "owner_id": owner_id.value},
            )
            raise ValueError("detect_identity_dissonance: owner_mismatch")
        view = views_by_id.get(notice.belief_id.value)
        memory_id = None if view is None else _cite_memory(view, cited_ids)
        if view is None or memory_id is None:
            if view is not None:
                still_deferred.append(notice)
            continue
        _emit_contradiction(
            view, memory_id=memory_id, tick=tick, requests=requests
        )
        emitted.append(notice)
        handled.add(notice.belief_id.value)

    if identity is not None:
        for view in views:
            if view.belief_id.value in handled:
                continue
            if view.activation not in _OPEN_ACTIVATION:
                continue
            conflict = _conflict_for_view(
                view,
                direction=direction,
                goals_by_id=goals_by_id,
                futures=futures,
                selected_future_id=selected_future_id,
                policy=active,
            )
            if conflict is None:
                continue
            magnitude = quantize_score(
                min(
                    1.0,
                    view.confidence * view.derived_stability * active.conflict_weight,
                )
            )
            notice = IdentityDissonanceNotice(
                owner_id=owner_id,
                tick=tick,
                belief_id=view.belief_id,
                aspect=view.aspect,
                conflict_code=conflict,
                magnitude=magnitude,
            )
            memory_id = _cite_memory(view, cited_ids)
            if memory_id is None:
                still_deferred.append(notice)
                _LOG.warning(
                    "identity_dissonance_deferred",
                    extra={
                        "owner_id": owner_id.value,
                        "tick": tick,
                        "aspect": view.aspect.value,
                        "conflict_code": conflict.value,
                    },
                )
                continue
            _emit_contradiction(
                view, memory_id=memory_id, tick=tick, requests=requests
            )
            emitted.append(notice)

    result = IdentityDissonanceResult(
        notices=tuple(emitted),
        requests=tuple(requests),
        deferred=tuple(still_deferred),
    )
    if result.notices:
        _LOG.debug(
            "identity_dissonance",
            extra={
                "notice_count": len(result.notices),
                "aspect_codes": tuple(item.aspect.value for item in result.notices),
                "conflict_codes": tuple(
                    item.conflict_code.value for item in result.notices
                ),
                "magnitude_bands": tuple(
                    identity_stability_band(item.magnitude) for item in result.notices
                ),
            },
        )
    return result


def _goals_by_id(owner_id: AgentId, goals: Sequence[Goal]) -> dict[str, Goal]:
    indexed: dict[str, Goal] = {}
    for goal in goals:
        if type(goal) is not Goal:
            raise TypeError("detect_identity_dissonance.goals: invalid_type")
        if goal.owner_id != owner_id:
            _LOG.error(
                "identity_dissonance_rejected",
                extra={"reason_code": "owner_mismatch", "owner_id": owner_id.value},
            )
            raise ValueError("detect_identity_dissonance: owner_mismatch")
        indexed[goal.goal_id.value] = goal
    return indexed


def _cite_memory(
    view: IdentityBeliefView, cited_ids: Mapping[str, MemoryId]
) -> MemoryId | None:
    for memory_id in view.supporting_memory_ids:
        cited = cited_ids.get(memory_id.value)
        if cited is not None:
            return cited
    if not cited_ids:
        return None
    return next(iter(cited_ids.values()))


def _emit_contradiction(
    view: IdentityBeliefView,
    *,
    memory_id: MemoryId,
    tick: int,
    requests: list[BeliefRevisionRequest],
) -> None:
    raw = (
        f"{view.claim.subject.agent_id.value}|{tick}|{view.belief_id.value}|"
        f"{view.aspect.value}"
    )
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]
    requests.append(
        BeliefRevisionRequest(
            owner_id=view.claim.subject.agent_id,
            operation_id=f"identity-dissonance-{view.aspect.value}-{digest}",
            logical_tick=tick,
            claim=view.claim,
            evidence=BeliefEvidenceBundle(
                supporting=(),
                contradicting=(
                    BeliefEvidenceContribution(
                        memory_id=memory_id,
                        stance=EvidenceStance.CONTRADICTING,
                        contribution=0.5,
                        ordinal=0,
                        lineage_root_id=memory_id,
                    ),
                ),
            ),
            policy=DEFAULT_BELIEF_FORMATION_POLICY.as_ref(),
            belief_id=view.belief_id,
        )
    )


def _conflict_for_view(
    view: IdentityBeliefView,
    *,
    direction: str,
    goals_by_id: Mapping[str, Goal],
    futures: object | None,
    selected_future_id: str | None,
    policy: IdentityPolicy,
) -> IdentityConflictCode | None:
    if view.aspect is IdentityAspect.COMMITMENT:
        goal = goals_by_id.get(view.evidence_token)
        if goal is None:
            return None
        satisfying = satisfying_command_kinds(goal)
        if not satisfying or direction in satisfying:
            return None
        return IdentityConflictCode.COMMITMENT_COMMAND
    if view.aspect is IdentityAspect.INFERRED_VALUE:
        if view.confidence < policy.inferred_value_confidence_floor:
            return None
        if view.evidence_token not in _COMMAND_DIRECTION.values():
            return None
        if direction == view.evidence_token:
            return None
        if not _future_direction_present(futures, view.evidence_token):
            return None
        return IdentityConflictCode.INFERRED_VALUE_COMMAND
    if view.aspect is IdentityAspect.RISK_TOLERANCE:
        if view.derived_rate >= policy.risk_rate_ceiling:
            return None
        if not _harm_exceeds_minimum(
            futures, direction=direction, selected_future_id=selected_future_id
        ):
            return None
        return IdentityConflictCode.RISK_ABOVE_TOLERANCE
    return None


def _future_direction_present(futures: object | None, token: str) -> bool:
    if futures is None:
        return False
    return any(item.direction.value == token for item in futures.futures)


def _harm_exceeds_minimum(
    futures: object | None, *, direction: str, selected_future_id: str | None
) -> bool:
    if futures is None or not futures.futures:
        return False
    harms = tuple(_future_harm(item) for item in futures.futures)
    minimum = min(harms)
    selected_harm: float | None = None
    for future in futures.futures:
        if (
            selected_future_id is not None
            and future.future_id == selected_future_id
            and future.direction.value == direction
        ):
            selected_harm = _future_harm(future)
            break
    if selected_harm is None:
        matching = tuple(
            _future_harm(item)
            for item in futures.futures
            if item.direction.value == direction
        )
        if not matching:
            return False
        selected_harm = max(matching)
    return selected_harm > minimum
