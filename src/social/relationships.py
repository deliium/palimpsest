"""Evidence-backed asymmetric relationship profiles and revision math.

``social`` stays independent of ``memory``: evidence references are opaque
stable ID strings supplied by cognition/composition. Pure values emit no logs.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from agents.models import AgentId
from social.models import Relationship, RelationshipId
from world.identifiers import (
    require_bounded_text,
    require_exact_nonneg_int,
    require_stable_id,
)

__all__ = [
    "DEFAULT_RELATIONSHIP_POLICY",
    "DirectedRelationshipProfile",
    "RelationshipActivationState",
    "RelationshipConfidence",
    "RelationshipDimension",
    "RelationshipDimensionState",
    "RelationshipEvidenceItem",
    "RelationshipFormationPolicy",
    "RelationshipHistory",
    "RelationshipInteractionSignal",
    "RelationshipPolicyRef",
    "RelationshipProfileStore",
    "RelationshipRevision",
    "RelationshipRevisionId",
    "RelationshipRevisionRequest",
    "RelationshipRevisionResult",
    "RelationshipSignalKind",
    "apply_relationship_decay",
    "merge_relationship_revision",
    "profile_id_for",
    "project_legacy_relationship",
    "revision_id_for_relationship",
    "signals_to_dimension_deltas",
]

_MAX_POLICY_CHARS: Final[int] = 64
_MAX_EVIDENCE: Final[int] = 256
_MAX_OPERATION_CHARS: Final[int] = 128
_SCORE_QUANTUM: Final[float] = 1e-6


class RelationshipDimension(StrEnum):
    """Closed set of independent directed relationship dimensions."""

    TRUST = "trust"
    FEAR = "fear"
    AFFECTION = "affection"
    DEBT = "debt"
    RESPECT = "respect"
    RESENTMENT = "resentment"
    FAMILIARITY = "familiarity"
    DEPENDENCY = "dependency"


class RelationshipSignalKind(StrEnum):
    """Versioned low-level episodic interaction signals (not social labels)."""

    HELP_RECEIVED = "help_received"
    HELP_GIVEN = "help_given"
    HARM_RECEIVED = "harm_received"
    HARM_GIVEN = "harm_given"
    PROXIMITY = "proximity"
    COMMUNICATION = "communication"
    RESOURCE_RECEIVED = "resource_received"
    RESOURCE_GIVEN = "resource_given"
    PROTECTION_RECEIVED = "protection_received"
    PROTECTION_GIVEN = "protection_given"


class RelationshipActivationState(StrEnum):
    CANDIDATE = "candidate"
    ACTIVE = "active"
    RETIRED = "retired"


def _quantize(value: float) -> float:
    if not math.isfinite(value):
        raise ValueError("quantize: not_finite")
    steps = round(value / _SCORE_QUANTUM)
    quantized = steps * _SCORE_QUANTUM
    return 0.0 if quantized == 0.0 else quantized


def _unit(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name}: not_unit_interval")
    number = float(value)
    if not math.isfinite(number) or number < 0.0 or number > 1.0:
        raise ValueError(f"{name}: not_unit_interval")
    return 0.0 if number == 0.0 else number


def _signed_unit(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name}: not_signed_unit")
    number = float(value)
    if not math.isfinite(number) or number < -1.0 or number > 1.0:
        raise ValueError(f"{name}: not_signed_unit")
    return 0.0 if number == 0.0 else number


def _require_ordered[T](
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


@dataclass(frozen=True, slots=True)
class RelationshipRevisionId:
    value: str

    def __post_init__(self) -> None:
        require_stable_id("RelationshipRevisionId.value", self.value)


@dataclass(frozen=True, slots=True)
class RelationshipPolicyRef:
    policy_id: str
    version: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "policy_id",
            require_bounded_text(
                "RelationshipPolicyRef.policy_id",
                self.policy_id,
                max_length=_MAX_POLICY_CHARS,
            ),
        )
        object.__setattr__(
            self,
            "version",
            require_bounded_text(
                "RelationshipPolicyRef.version",
                self.version,
                max_length=_MAX_POLICY_CHARS,
            ),
        )

    def __repr__(self) -> str:
        return (
            f"RelationshipPolicyRef(policy_id={self.policy_id!r}, "
            f"version={self.version!r})"
        )


@dataclass(frozen=True, slots=True)
class RelationshipConfidence:
    confidence: float
    support_mass: float
    contradiction_mass: float

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "confidence",
            _quantize(_unit("RelationshipConfidence.confidence", self.confidence)),
        )
        object.__setattr__(
            self,
            "support_mass",
            _quantize(_unit("RelationshipConfidence.support_mass", self.support_mass)),
        )
        object.__setattr__(
            self,
            "contradiction_mass",
            _quantize(
                _unit(
                    "RelationshipConfidence.contradiction_mass",
                    self.contradiction_mass,
                )
            ),
        )

    def __repr__(self) -> str:
        return (
            f"RelationshipConfidence(confidence={self.confidence}, "
            f"support_mass={self.support_mass}, "
            f"contradiction_mass={self.contradiction_mass})"
        )


@dataclass(frozen=True, slots=True)
class RelationshipEvidenceItem:
    """Opaque owned episodic evidence reference (never dereferenced here)."""

    memory_ref: str
    contribution: float
    ordinal: int
    lineage_root_ref: str

    def __post_init__(self) -> None:
        require_stable_id("RelationshipEvidenceItem.memory_ref", self.memory_ref)
        require_stable_id(
            "RelationshipEvidenceItem.lineage_root_ref", self.lineage_root_ref
        )
        object.__setattr__(
            self,
            "contribution",
            _quantize(
                _unit("RelationshipEvidenceItem.contribution", self.contribution)
            ),
        )
        object.__setattr__(
            self,
            "ordinal",
            require_exact_nonneg_int("RelationshipEvidenceItem.ordinal", self.ordinal),
        )

    def __repr__(self) -> str:
        return (
            f"RelationshipEvidenceItem(memory_ref={self.memory_ref!r}, "
            f"ordinal={self.ordinal}, "
            f"lineage_root_ref={self.lineage_root_ref!r})"
        )


@dataclass(frozen=True, slots=True)
class RelationshipDimensionState:
    """One directed dimension assessment."""

    dimension: RelationshipDimension
    value: float
    confidence: RelationshipConfidence
    evidence: tuple[RelationshipEvidenceItem, ...]
    logical_tick: int
    policy: RelationshipPolicyRef

    def __post_init__(self) -> None:
        if type(self.dimension) is not RelationshipDimension:
            raise TypeError("RelationshipDimensionState.dimension: invalid_type")
        if type(self.confidence) is not RelationshipConfidence:
            raise TypeError("RelationshipDimensionState.confidence: invalid_type")
        if type(self.policy) is not RelationshipPolicyRef:
            raise TypeError("RelationshipDimensionState.policy: invalid_type")
        object.__setattr__(
            self,
            "value",
            _quantize(_signed_unit("RelationshipDimensionState.value", self.value)),
        )
        evidence = _require_ordered(
            "RelationshipDimensionState.evidence",
            self.evidence,
            model_type=RelationshipEvidenceItem,
            max_items=_MAX_EVIDENCE,
        )
        refs = [item.memory_ref for item in evidence]
        if len(refs) != len(set(refs)):
            raise ValueError(
                "RelationshipDimensionState.evidence: duplicate_memory_ref"
            )
        ordinals = [item.ordinal for item in evidence]
        if ordinals != sorted(ordinals):
            raise ValueError(
                "RelationshipDimensionState.evidence: ordinals_not_monotonic"
            )
        if ordinals and ordinals != list(range(len(ordinals))):
            raise ValueError("RelationshipDimensionState.evidence: ordinals_not_dense")
        object.__setattr__(self, "evidence", evidence)
        object.__setattr__(
            self,
            "logical_tick",
            require_exact_nonneg_int(
                "RelationshipDimensionState.logical_tick", self.logical_tick
            ),
        )

    def __repr__(self) -> str:
        return (
            f"RelationshipDimensionState(dimension={self.dimension.value!r}, "
            f"evidence_count={len(self.evidence)}, "
            f"logical_tick={self.logical_tick})"
        )


@dataclass(frozen=True, slots=True)
class DirectedRelationshipProfile:
    """Owner-bound directed ``source -> target`` relationship snapshot."""

    relationship_id: RelationshipId
    source_id: AgentId
    target_id: AgentId
    dimensions: tuple[RelationshipDimensionState, ...]
    activation_state: RelationshipActivationState
    current_revision_id: RelationshipRevisionId
    revision_ordinal: int
    created_tick: int
    updated_tick: int
    policy: RelationshipPolicyRef

    def __post_init__(self) -> None:
        if type(self.relationship_id) is not RelationshipId:
            raise TypeError("DirectedRelationshipProfile.relationship_id: invalid_type")
        if type(self.source_id) is not AgentId:
            raise TypeError("DirectedRelationshipProfile.source_id: invalid_type")
        if type(self.target_id) is not AgentId:
            raise TypeError("DirectedRelationshipProfile.target_id: invalid_type")
        if self.source_id == self.target_id:
            raise ValueError("DirectedRelationshipProfile: self_target")
        if type(self.activation_state) is not RelationshipActivationState:
            raise TypeError(
                "DirectedRelationshipProfile.activation_state: invalid_type"
            )
        if type(self.current_revision_id) is not RelationshipRevisionId:
            raise TypeError(
                "DirectedRelationshipProfile.current_revision_id: invalid_type"
            )
        if type(self.policy) is not RelationshipPolicyRef:
            raise TypeError("DirectedRelationshipProfile.policy: invalid_type")
        dims = _require_ordered(
            "DirectedRelationshipProfile.dimensions",
            self.dimensions,
            model_type=RelationshipDimensionState,
            max_items=len(RelationshipDimension),
        )
        seen: set[str] = set()
        for item in dims:
            if item.dimension.value in seen:
                raise ValueError("DirectedRelationshipProfile.dimensions: duplicate")
            seen.add(item.dimension.value)
        # Stable dimension order.
        ordered = tuple(sorted(dims, key=lambda item: item.dimension.value))
        object.__setattr__(self, "dimensions", ordered)
        object.__setattr__(
            self,
            "revision_ordinal",
            require_exact_nonneg_int(
                "DirectedRelationshipProfile.revision_ordinal",
                self.revision_ordinal,
            ),
        )
        created = require_exact_nonneg_int(
            "DirectedRelationshipProfile.created_tick", self.created_tick
        )
        updated = require_exact_nonneg_int(
            "DirectedRelationshipProfile.updated_tick", self.updated_tick
        )
        if updated < created:
            raise ValueError("DirectedRelationshipProfile.updated_tick: before_created")
        object.__setattr__(self, "created_tick", created)
        object.__setattr__(self, "updated_tick", updated)

    def dimension_map(
        self,
    ) -> Mapping[RelationshipDimension, RelationshipDimensionState]:
        return {item.dimension: item for item in self.dimensions}

    def __repr__(self) -> str:
        return (
            f"DirectedRelationshipProfile("
            f"relationship_id={self.relationship_id.value!r}, "
            f"source_id={self.source_id.value!r}, "
            f"target_id={self.target_id.value!r}, "
            f"dimension_count={len(self.dimensions)}, "
            f"activation_state={self.activation_state.value!r}, "
            f"revision_ordinal={self.revision_ordinal})"
        )


@dataclass(frozen=True, slots=True)
class RelationshipRevision:
    revision_id: RelationshipRevisionId
    relationship_id: RelationshipId
    source_id: AgentId
    target_id: AgentId
    ordinal: int
    logical_tick: int
    dimensions: tuple[RelationshipDimensionState, ...]
    activation_state: RelationshipActivationState
    policy: RelationshipPolicyRef
    previous_revision_id: RelationshipRevisionId | None = None

    def __post_init__(self) -> None:
        if type(self.revision_id) is not RelationshipRevisionId:
            raise TypeError("RelationshipRevision.revision_id: invalid_type")
        if type(self.relationship_id) is not RelationshipId:
            raise TypeError("RelationshipRevision.relationship_id: invalid_type")
        if type(self.source_id) is not AgentId or type(self.target_id) is not AgentId:
            raise TypeError("RelationshipRevision: invalid_agent")
        if self.source_id == self.target_id:
            raise ValueError("RelationshipRevision: self_target")
        if type(self.activation_state) is not RelationshipActivationState:
            raise TypeError("RelationshipRevision.activation_state: invalid_type")
        if type(self.policy) is not RelationshipPolicyRef:
            raise TypeError("RelationshipRevision.policy: invalid_type")
        if (
            self.previous_revision_id is not None
            and type(self.previous_revision_id) is not RelationshipRevisionId
        ):
            raise TypeError("RelationshipRevision.previous_revision_id: invalid_type")
        dims = _require_ordered(
            "RelationshipRevision.dimensions",
            self.dimensions,
            model_type=RelationshipDimensionState,
            max_items=len(RelationshipDimension),
        )
        object.__setattr__(
            self,
            "dimensions",
            tuple(sorted(dims, key=lambda item: item.dimension.value)),
        )
        object.__setattr__(
            self,
            "ordinal",
            require_exact_nonneg_int("RelationshipRevision.ordinal", self.ordinal),
        )
        object.__setattr__(
            self,
            "logical_tick",
            require_exact_nonneg_int(
                "RelationshipRevision.logical_tick", self.logical_tick
            ),
        )
        if self.ordinal == 0 and self.previous_revision_id is not None:
            raise ValueError("RelationshipRevision: initial_has_previous")
        if self.ordinal > 0 and self.previous_revision_id is None:
            raise ValueError("RelationshipRevision: non_initial_missing_previous")

    def __repr__(self) -> str:
        return (
            f"RelationshipRevision(revision_id={self.revision_id.value!r}, "
            f"relationship_id={self.relationship_id.value!r}, "
            f"source_id={self.source_id.value!r}, "
            f"target_id={self.target_id.value!r}, "
            f"ordinal={self.ordinal}, "
            f"logical_tick={self.logical_tick}, "
            f"dimension_count={len(self.dimensions)})"
        )


@dataclass(frozen=True, slots=True)
class RelationshipHistory:
    profile: DirectedRelationshipProfile
    revisions: tuple[RelationshipRevision, ...]

    def __post_init__(self) -> None:
        if type(self.profile) is not DirectedRelationshipProfile:
            raise TypeError("RelationshipHistory.profile: invalid_type")
        revisions = _require_ordered(
            "RelationshipHistory.revisions",
            self.revisions,
            model_type=RelationshipRevision,
            max_items=10_000,
        )
        if not revisions:
            raise ValueError("RelationshipHistory.revisions: empty")
        if revisions[-1].revision_id != self.profile.current_revision_id:
            raise ValueError("RelationshipHistory: head_revision_mismatch")
        prev: RelationshipRevisionId | None = None
        for index, revision in enumerate(revisions):
            if revision.relationship_id != self.profile.relationship_id:
                raise ValueError("RelationshipHistory: id_mismatch")
            if revision.source_id != self.profile.source_id:
                raise ValueError("RelationshipHistory: source_mismatch")
            if revision.target_id != self.profile.target_id:
                raise ValueError("RelationshipHistory: target_mismatch")
            if revision.ordinal != index:
                raise ValueError("RelationshipHistory: ordinal_gap")
            if revision.previous_revision_id != prev:
                raise ValueError("RelationshipHistory: previous_link_mismatch")
            if index > 0 and revision.logical_tick < revisions[index - 1].logical_tick:
                raise ValueError("RelationshipHistory: tick_regression")
            prev = revision.revision_id
        object.__setattr__(self, "revisions", revisions)

    def __repr__(self) -> str:
        return (
            f"RelationshipHistory("
            f"relationship_id={self.profile.relationship_id.value!r}, "
            f"revision_count={len(self.revisions)})"
        )


@dataclass(frozen=True, slots=True)
class RelationshipInteractionSignal:
    """Low-level owned episodic interaction signal (no high-level labels)."""

    counterpart_id: AgentId
    kind: RelationshipSignalKind
    strength: float
    memory_ref: str
    lineage_root_ref: str
    source_tick: int

    def __post_init__(self) -> None:
        if type(self.counterpart_id) is not AgentId:
            raise TypeError(
                "RelationshipInteractionSignal.counterpart_id: invalid_type"
            )
        if type(self.kind) is not RelationshipSignalKind:
            raise TypeError("RelationshipInteractionSignal.kind: invalid_type")
        require_stable_id("RelationshipInteractionSignal.memory_ref", self.memory_ref)
        require_stable_id(
            "RelationshipInteractionSignal.lineage_root_ref", self.lineage_root_ref
        )
        object.__setattr__(
            self,
            "strength",
            _quantize(_unit("RelationshipInteractionSignal.strength", self.strength)),
        )
        object.__setattr__(
            self,
            "source_tick",
            require_exact_nonneg_int(
                "RelationshipInteractionSignal.source_tick", self.source_tick
            ),
        )

    def __repr__(self) -> str:
        return (
            f"RelationshipInteractionSignal("
            f"counterpart_id={self.counterpart_id.value!r}, "
            f"kind={self.kind.value!r}, "
            f"memory_ref={self.memory_ref!r}, "
            f"source_tick={self.source_tick})"
        )


@dataclass(frozen=True, slots=True)
class RelationshipFormationPolicy:
    policy_id: str
    version: str
    decay_half_life_ticks: int = 100
    activate_confidence_threshold: float = 0.25
    retire_confidence_threshold: float = 0.05

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "policy_id",
            require_bounded_text(
                "RelationshipFormationPolicy.policy_id",
                self.policy_id,
                max_length=_MAX_POLICY_CHARS,
            ),
        )
        object.__setattr__(
            self,
            "version",
            require_bounded_text(
                "RelationshipFormationPolicy.version",
                self.version,
                max_length=_MAX_POLICY_CHARS,
            ),
        )
        object.__setattr__(
            self,
            "decay_half_life_ticks",
            require_exact_nonneg_int(
                "RelationshipFormationPolicy.decay_half_life_ticks",
                self.decay_half_life_ticks,
            ),
        )
        for name in (
            "activate_confidence_threshold",
            "retire_confidence_threshold",
        ):
            object.__setattr__(
                self,
                name,
                _unit(f"RelationshipFormationPolicy.{name}", getattr(self, name)),
            )

    def as_ref(self) -> RelationshipPolicyRef:
        return RelationshipPolicyRef(policy_id=self.policy_id, version=self.version)

    def __repr__(self) -> str:
        return (
            f"RelationshipFormationPolicy(policy_id={self.policy_id!r}, "
            f"version={self.version!r})"
        )


DEFAULT_RELATIONSHIP_POLICY: Final[RelationshipFormationPolicy] = (
    RelationshipFormationPolicy(policy_id="relationship-formation", version="1")
)


# Signal -> (dimension, signed delta scale)
_SIGNAL_EFFECTS: Final[
    Mapping[RelationshipSignalKind, tuple[tuple[RelationshipDimension, float], ...]]
] = {
    RelationshipSignalKind.HELP_RECEIVED: (
        (RelationshipDimension.TRUST, 0.4),
        (RelationshipDimension.AFFECTION, 0.2),
        (RelationshipDimension.DEBT, 0.3),
        (RelationshipDimension.FAMILIARITY, 0.1),
    ),
    RelationshipSignalKind.HELP_GIVEN: (
        (RelationshipDimension.AFFECTION, 0.2),
        (RelationshipDimension.FAMILIARITY, 0.1),
        (RelationshipDimension.DEPENDENCY, -0.1),
    ),
    RelationshipSignalKind.HARM_RECEIVED: (
        (RelationshipDimension.FEAR, 0.4),
        (RelationshipDimension.RESENTMENT, 0.4),
        (RelationshipDimension.TRUST, -0.3),
        (RelationshipDimension.FAMILIARITY, 0.1),
    ),
    RelationshipSignalKind.HARM_GIVEN: (
        (RelationshipDimension.RESENTMENT, 0.1),
        (RelationshipDimension.FAMILIARITY, 0.1),
    ),
    RelationshipSignalKind.PROXIMITY: ((RelationshipDimension.FAMILIARITY, 0.2),),
    RelationshipSignalKind.COMMUNICATION: ((RelationshipDimension.FAMILIARITY, 0.15),),
    RelationshipSignalKind.RESOURCE_RECEIVED: (
        (RelationshipDimension.DEBT, 0.35),
        (RelationshipDimension.TRUST, 0.15),
        (RelationshipDimension.FAMILIARITY, 0.1),
    ),
    RelationshipSignalKind.RESOURCE_GIVEN: (
        (RelationshipDimension.DEBT, -0.2),
        (RelationshipDimension.FAMILIARITY, 0.1),
    ),
    RelationshipSignalKind.PROTECTION_RECEIVED: (
        (RelationshipDimension.TRUST, 0.35),
        (RelationshipDimension.DEPENDENCY, 0.25),
        (RelationshipDimension.RESPECT, 0.2),
        (RelationshipDimension.FAMILIARITY, 0.1),
    ),
    RelationshipSignalKind.PROTECTION_GIVEN: (
        (RelationshipDimension.AFFECTION, 0.15),
        (RelationshipDimension.RESPECT, 0.1),
        (RelationshipDimension.FAMILIARITY, 0.1),
    ),
}


@dataclass(frozen=True, slots=True)
class RelationshipRevisionRequest:
    source_id: AgentId
    target_id: AgentId
    operation_id: str
    logical_tick: int
    signals: tuple[RelationshipInteractionSignal, ...]
    policy: RelationshipPolicyRef
    expected_revision_ordinal: int | None = None

    def __post_init__(self) -> None:
        if type(self.source_id) is not AgentId or type(self.target_id) is not AgentId:
            raise TypeError("RelationshipRevisionRequest: invalid_agent")
        if self.source_id == self.target_id:
            raise ValueError("RelationshipRevisionRequest: self_target")
        if type(self.policy) is not RelationshipPolicyRef:
            raise TypeError("RelationshipRevisionRequest.policy: invalid_type")
        object.__setattr__(
            self,
            "operation_id",
            require_bounded_text(
                "RelationshipRevisionRequest.operation_id",
                self.operation_id,
                max_length=_MAX_OPERATION_CHARS,
            ),
        )
        object.__setattr__(
            self,
            "logical_tick",
            require_exact_nonneg_int(
                "RelationshipRevisionRequest.logical_tick", self.logical_tick
            ),
        )
        signals = _require_ordered(
            "RelationshipRevisionRequest.signals",
            self.signals,
            model_type=RelationshipInteractionSignal,
            max_items=_MAX_EVIDENCE,
        )
        for signal in signals:
            if signal.counterpart_id != self.target_id:
                raise ValueError("RelationshipRevisionRequest: counterpart_mismatch")
        object.__setattr__(self, "signals", signals)
        if self.expected_revision_ordinal is not None:
            object.__setattr__(
                self,
                "expected_revision_ordinal",
                require_exact_nonneg_int(
                    "RelationshipRevisionRequest.expected_revision_ordinal",
                    self.expected_revision_ordinal,
                ),
            )

    def __repr__(self) -> str:
        return (
            f"RelationshipRevisionRequest(source_id={self.source_id.value!r}, "
            f"target_id={self.target_id.value!r}, "
            f"operation_id={self.operation_id!r}, "
            f"logical_tick={self.logical_tick}, "
            f"signal_count={len(self.signals)})"
        )


@dataclass(frozen=True, slots=True)
class RelationshipRevisionResult:
    relationship_id: RelationshipId
    revision_id: RelationshipRevisionId
    revision_ordinal: int
    changed_dimension_count: int
    evidence_count: int
    idempotent: bool
    created: bool
    activation_state: RelationshipActivationState

    def __post_init__(self) -> None:
        if type(self.relationship_id) is not RelationshipId:
            raise TypeError("RelationshipRevisionResult.relationship_id: invalid_type")
        if type(self.revision_id) is not RelationshipRevisionId:
            raise TypeError("RelationshipRevisionResult.revision_id: invalid_type")
        if type(self.activation_state) is not RelationshipActivationState:
            raise TypeError("RelationshipRevisionResult.activation_state: invalid_type")
        for name in ("idempotent", "created"):
            if type(getattr(self, name)) is not bool:
                raise TypeError(f"RelationshipRevisionResult.{name}: invalid_type")
        for name in (
            "revision_ordinal",
            "changed_dimension_count",
            "evidence_count",
        ):
            object.__setattr__(
                self,
                name,
                require_exact_nonneg_int(
                    f"RelationshipRevisionResult.{name}", getattr(self, name)
                ),
            )

    def __repr__(self) -> str:
        return (
            f"RelationshipRevisionResult("
            f"relationship_id={self.relationship_id.value!r}, "
            f"revision_id={self.revision_id.value!r}, "
            f"revision_ordinal={self.revision_ordinal}, "
            f"changed_dimension_count={self.changed_dimension_count}, "
            f"evidence_count={self.evidence_count}, "
            f"idempotent={self.idempotent}, created={self.created})"
        )


def profile_id_for(*, source_id: AgentId, target_id: AgentId) -> RelationshipId:
    material = f"v1|{source_id.value}|{target_id.value}"
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return RelationshipId(f"rp-{digest[:48]}")


def revision_id_for_relationship(
    *,
    relationship_id: RelationshipId,
    ordinal: int,
    logical_tick: int,
    operation_id: str,
) -> RelationshipRevisionId:
    material = f"v1|{relationship_id.value}|{ordinal}|{logical_tick}|{operation_id}"
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return RelationshipRevisionId(f"rr-{digest[:48]}")


def apply_relationship_decay(
    confidence: RelationshipConfidence,
    *,
    elapsed_ticks: int,
    policy: RelationshipFormationPolicy,
) -> RelationshipConfidence:
    elapsed = require_exact_nonneg_int(
        "apply_relationship_decay.elapsed_ticks", elapsed_ticks
    )
    if elapsed == 0 or policy.decay_half_life_ticks == 0:
        return confidence
    factor = 0.5 ** (elapsed / float(policy.decay_half_life_ticks))
    factor = _quantize(max(0.0, min(1.0, factor)))
    return RelationshipConfidence(
        confidence=_quantize(confidence.confidence * factor),
        support_mass=_quantize(confidence.support_mass * factor),
        contradiction_mass=_quantize(confidence.contradiction_mass * factor),
    )


def signals_to_dimension_deltas(
    signals: Sequence[RelationshipInteractionSignal],
) -> Mapping[RelationshipDimension, tuple[float, tuple[RelationshipEvidenceItem, ...]]]:
    """Map low-level signals to per-dimension signed deltas and evidence."""
    buckets: dict[
        RelationshipDimension, list[tuple[float, RelationshipEvidenceItem]]
    ] = {dim: [] for dim in RelationshipDimension}
    # Dedup by lineage root within signal kind+counterpart already scoped.
    seen_roots: set[tuple[str, str]] = set()
    ordered_signals = sorted(
        signals,
        key=lambda item: (item.source_tick, item.memory_ref, item.kind.value),
    )
    for signal in ordered_signals:
        root_key = (signal.kind.value, signal.lineage_root_ref)
        if root_key in seen_roots:
            continue
        seen_roots.add(root_key)
        effects = _SIGNAL_EFFECTS.get(signal.kind, ())
        for dimension, scale in effects:
            delta = _quantize(scale * signal.strength)
            if delta == 0.0:
                continue
            evidence = RelationshipEvidenceItem(
                memory_ref=signal.memory_ref,
                contribution=_quantize(min(1.0, abs(delta))),
                ordinal=0,
                lineage_root_ref=signal.lineage_root_ref,
            )
            buckets[dimension].append((delta, evidence))

    result: dict[
        RelationshipDimension, tuple[float, tuple[RelationshipEvidenceItem, ...]]
    ] = {}
    for dimension, items in buckets.items():
        if not items:
            continue
        total = _quantize(sum(delta for delta, _ in items))
        total = max(-1.0, min(1.0, total))
        evidence_items: list[RelationshipEvidenceItem] = []
        for ordinal, (_, evidence) in enumerate(items):
            evidence_items.append(
                RelationshipEvidenceItem(
                    memory_ref=evidence.memory_ref,
                    contribution=evidence.contribution,
                    ordinal=ordinal,
                    lineage_root_ref=evidence.lineage_root_ref,
                )
            )
        result[dimension] = (total, tuple(evidence_items))
    return result


def merge_relationship_revision(
    *,
    source_id: AgentId,
    target_id: AgentId,
    signals: Sequence[RelationshipInteractionSignal],
    prior: RelationshipHistory | None,
    logical_tick: int,
    operation_id: str,
    policy: RelationshipFormationPolicy,
) -> tuple[RelationshipHistory, bool, int, int]:
    """Append one directed revision; never writes the reverse direction.

    Returns ``(history, created, changed_dimension_count, evidence_count)``.
    """
    if source_id == target_id:
        raise ValueError("merge_relationship_revision: self_target")
    tick = require_exact_nonneg_int("merge_relationship_revision.tick", logical_tick)
    relationship_id = (
        prior.profile.relationship_id
        if prior is not None
        else profile_id_for(source_id=source_id, target_id=target_id)
    )
    if prior is not None:
        if prior.profile.source_id != source_id or prior.profile.target_id != target_id:
            raise ValueError("merge_relationship_revision: direction_mismatch")
        if prior.profile.updated_tick > tick:
            raise ValueError("merge_relationship_revision: chronology")

    deltas = signals_to_dimension_deltas(signals)
    prior_map = prior.profile.dimension_map() if prior is not None else {}
    elapsed = 0 if prior is None else tick - prior.profile.updated_tick

    new_dims: list[RelationshipDimensionState] = []
    changed = 0
    evidence_count = 0
    for dimension in RelationshipDimension:
        prior_dim = prior_map.get(dimension)
        prior_conf = (
            apply_relationship_decay(
                prior_dim.confidence, elapsed_ticks=elapsed, policy=policy
            )
            if prior_dim is not None
            else RelationshipConfidence(
                confidence=0.0, support_mass=0.0, contradiction_mass=0.0
            )
        )
        prior_value = 0.0 if prior_dim is None else prior_dim.value
        if dimension not in deltas:
            if prior_dim is None:
                continue
            decayed_value = prior_value
            if policy.decay_half_life_ticks and elapsed:
                factor = 0.5 ** (elapsed / float(policy.decay_half_life_ticks))
                decayed_value = _quantize(prior_value * factor)
            new_dims.append(
                RelationshipDimensionState(
                    dimension=dimension,
                    value=decayed_value,
                    confidence=prior_conf,
                    evidence=(),
                    logical_tick=tick,
                    policy=policy.as_ref(),
                )
            )
            continue
        delta, evidence = deltas[dimension]
        evidence_count += len(evidence)
        support = _quantize(min(1.0, prior_conf.support_mass + abs(delta) * 0.5))
        confidence = RelationshipConfidence(
            confidence=_quantize(max(0.0, support - prior_conf.contradiction_mass)),
            support_mass=support,
            contradiction_mass=prior_conf.contradiction_mass,
        )
        value = _quantize(max(-1.0, min(1.0, prior_value + delta)))
        if prior_dim is None or prior_dim.value != value or evidence:
            changed += 1
        new_dims.append(
            RelationshipDimensionState(
                dimension=dimension,
                value=value,
                confidence=confidence,
                evidence=evidence,
                logical_tick=tick,
                policy=policy.as_ref(),
            )
        )

    max_conf = max((item.confidence.confidence for item in new_dims), default=0.0)
    if max_conf >= policy.activate_confidence_threshold:
        activation = RelationshipActivationState.ACTIVE
    elif (
        prior is not None
        and prior.profile.activation_state is RelationshipActivationState.ACTIVE
        and max_conf < policy.retire_confidence_threshold
    ):
        activation = RelationshipActivationState.RETIRED
    elif prior is not None:
        activation = prior.profile.activation_state
    else:
        activation = RelationshipActivationState.CANDIDATE

    ordinal = 0 if prior is None else prior.profile.revision_ordinal + 1
    previous = None if prior is None else prior.profile.current_revision_id
    revision_id = revision_id_for_relationship(
        relationship_id=relationship_id,
        ordinal=ordinal,
        logical_tick=tick,
        operation_id=operation_id,
    )
    dims_tuple = tuple(sorted(new_dims, key=lambda item: item.dimension.value))
    revision = RelationshipRevision(
        revision_id=revision_id,
        relationship_id=relationship_id,
        source_id=source_id,
        target_id=target_id,
        ordinal=ordinal,
        logical_tick=tick,
        dimensions=dims_tuple,
        activation_state=activation,
        policy=policy.as_ref(),
        previous_revision_id=previous,
    )
    profile = DirectedRelationshipProfile(
        relationship_id=relationship_id,
        source_id=source_id,
        target_id=target_id,
        dimensions=dims_tuple,
        activation_state=activation,
        current_revision_id=revision_id,
        revision_ordinal=ordinal,
        created_tick=tick if prior is None else prior.profile.created_tick,
        updated_tick=tick,
        policy=policy.as_ref(),
    )
    revisions = (revision,) if prior is None else (*prior.revisions, revision)
    return (
        RelationshipHistory(profile=profile, revisions=revisions),
        prior is None,
        changed,
        evidence_count,
    )


def project_legacy_relationship(profile: DirectedRelationshipProfile) -> Relationship:
    """Lossy schema-v1 projection using familiarity as affinity."""
    if type(profile) is not DirectedRelationshipProfile:
        raise TypeError("project_legacy_relationship: invalid_type")
    familiarity = 0.0
    for item in profile.dimensions:
        if item.dimension is RelationshipDimension.FAMILIARITY:
            familiarity = item.value
            break
    return Relationship(
        relationship_id=profile.relationship_id,
        source_id=profile.source_id,
        target_id=profile.target_id,
        kind="directed_profile",
        affinity=familiarity,
    )


class RelationshipProfileStore:
    """Mutable directed relationship aggregate bound to one source owner."""

    __slots__ = ("_histories", "_profiles", "_source_id")

    def __init__(self, source_id: AgentId) -> None:
        if type(source_id) is not AgentId:
            raise TypeError("RelationshipProfileStore: invalid_source")
        self._source_id = source_id
        self._profiles: dict[RelationshipId, DirectedRelationshipProfile] = {}
        self._histories: dict[RelationshipId, tuple[RelationshipRevision, ...]] = {}

    @property
    def source_id(self) -> AgentId:
        return self._source_id

    def snapshot(self) -> tuple[DirectedRelationshipProfile, ...]:
        return tuple(self._profiles.values())

    def history(self, relationship_id: RelationshipId) -> RelationshipHistory | None:
        profile = self._profiles.get(relationship_id)
        revisions = self._histories.get(relationship_id)
        if profile is None or revisions is None:
            return None
        return RelationshipHistory(profile=profile, revisions=revisions)

    def write(self, history: RelationshipHistory) -> None:
        if type(history) is not RelationshipHistory:
            raise TypeError("RelationshipProfileStore.write: invalid_type")
        if history.profile.source_id != self._source_id:
            raise PermissionError("ownership")
        self._profiles[history.profile.relationship_id] = history.profile
        self._histories[history.profile.relationship_id] = history.revisions

    def __repr__(self) -> str:
        return (
            f"RelationshipProfileStore(source_id={self._source_id.value!r}, "
            f"profile_count={len(self._profiles)})"
        )
