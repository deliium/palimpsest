"""Owner-scoped first-order hypotheses about other agents.

Confidence is a support ratio. It is not an estimate of another agent's true
drive, goal, or next command. This module reads observations and records the
owner already holds. It does not read world authority or another mind.
"""

from __future__ import annotations

import hashlib
import logging
import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from typing import Final

from agents.cognition.models import (
    _EFFECT_QUANTUM,
    EmotionKind,
    RetrievedMemoryContext,
)
from agents.models import AgentId
from memory.models import MemoryId, ReconstructedMemory
from social.relationships import DirectedRelationshipProfile, RelationshipDimension
from world.communications import CommunicationRelation
from world.identifiers import EntityId, require_exact_nonneg_int, require_stable_id
from world.observations import (
    CoarseHealth,
    Observation,
    ObservedCommunication,
    ObservedOccurrence,
    VisibleBody,
)

_LOG: Final[logging.Logger] = logging.getLogger("agents.cognition.theory_of_mind")

THEORY_OF_MIND_POLICY_VERSION: Final[str] = "theory-of-mind-v1"
_ID_PREFIX: Final[str] = "mh-"
_PRIOR: Final[float] = 1.0
_BEHAVIOR_WEIGHT: Final[float] = 4.0
_TESTIMONY_WEIGHT: Final[float] = 2.0
_TRUST_HIGH_MULTIPLIER: Final[float] = 2.0
_TRUST_LOW_MULTIPLIER: Final[float] = 0.5
_TRUST_HIGH_THRESHOLD: Final[float] = 0.5
_EMOTION_MULTIPLIER: Final[float] = 2.0
_EMOTION_THRESHOLD: Final[float] = 0.5
_FUTURE_DISCOUNT: Final[float] = 0.5
_ACTION_THRESHOLD: Final[float] = 0.55
_MAX_HYPOTHESES: Final[int] = 64
_MAX_HISTORY: Final[int] = 32

_NESTED_MIND_PREDICATES: Final[frozenset[str]] = frozenset(
    {
        "believes",
        "thinks",
        "wants",
        "feels",
        "knows",
        "intends",
    }
)
_BELIEF_PREDICATES: Final[frozenset[str]] = frozenset({"at", "has", "empty", "danger"})
_NEED_KINDS: Final[frozenset[str]] = frozenset(
    {"hunger", "thirst", "fatigue", "safety"}
)
_GOAL_OUTCOMES: Final[frozenset[str]] = frozenset({"reach_place"})
_CONCEPTS: Final[frozenset[str]] = frozenset({"food", "water", "rest", "danger"})
_COMMAND_KINDS: Final[frozenset[str]] = frozenset(
    {
        "move",
        "search",
        "take",
        "drop",
        "give",
        "eat",
        "drink",
        "sleep",
        "talk",
        "ask",
        "tell",
        "help",
        "attack",
        "flee",
        "wait",
    }
)
_EMOTION_KINDS: Final[frozenset[str]] = frozenset(item.value for item in EmotionKind)
_DIMENSIONS: Final[frozenset[str]] = frozenset(
    item.value for item in RelationshipDimension
)
_POLARITIES: Final[frozenset[str]] = frozenset({"positive", "negative"})


class MindAspect(StrEnum):
    """Closed first-order aspects. A hypothesis has no child model."""

    NEED = "need"
    GOAL = "goal"
    BELIEF = "belief"
    INTENTION = "intention"
    EMOTION = "emotion"
    RELATIONSHIP = "relationship"
    KNOWLEDGE = "knowledge"
    FUTURE_ACTION = "future_action"


class MindSlot(StrEnum):
    """Closed atom slots copied from records the owner already holds."""

    NEED_KIND = "need_kind"
    OUTCOME = "outcome"
    LOCATION = "location"
    CONCEPT = "concept"
    CLAIM_PREDICATE = "claim_predicate"
    CLAIM_OBJECT = "claim_object"
    ACTION = "action"
    EMOTION_KIND = "emotion_kind"
    DIMENSION = "dimension"
    POLARITY = "polarity"
    TARGET = "target"


class MindPolarity(StrEnum):
    """Closed polarity stored on a relationship hypothesis."""

    POSITIVE = "positive"
    NEGATIVE = "negative"


class MindEvidenceChannel(StrEnum):
    """Closed provenance channel for one hypothesis or cue."""

    OBSERVED_BEHAVIOR = "observed_behavior"
    COMMUNICATION = "communication"
    MEMORY = "memory"
    RELATIONSHIP = "relationship"
    SOCIAL_HISTORY = "social_history"
    DERIVED = "derived"


class MindUpdateReason(StrEnum):
    """Closed reason for one arithmetic hypothesis update."""

    SUPPORT = "support"
    COUNTER = "counter"
    DERIVE = "derive"
    DROP = "drop"


_SLOT_ORDER: Final[dict[MindSlot, int]] = {
    slot: index for index, slot in enumerate(MindSlot)
}


def _fail(field_name: str, code: str) -> ValueError:
    _LOG.error(
        "theory_of_mind_validation_failed field=%s reason_code=%s",
        field_name,
        code,
    )
    return ValueError(f"{field_name}: {code}")


def _quantize_mass(value: float) -> float:
    steps = round(value / _EFFECT_QUANTUM)
    if steps == 0:
        return 0.0
    quantized = float(Decimal(steps) * Decimal(str(_EFFECT_QUANTUM)))
    return 0.0 if quantized == 0.0 else quantized


def _quantize_confidence(value: float) -> float:
    quantized = _quantize_mass(value)
    if quantized < 0.0:
        return 0.0
    if quantized > 1.0:
        return 1.0
    return quantized


def _finite_nonnegative(field_name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _fail(field_name, "not_finite")
    number = float(value)
    if not math.isfinite(number) or number < 0.0:
        raise _fail(field_name, "not_finite")
    return _quantize_mass(number)


def _positive_quantum(field_name: str, value: object) -> float:
    number = _finite_nonnegative(field_name, value)
    if number <= 0.0:
        raise _fail(field_name, "not_positive")
    return number


def _unit_quantum(field_name: str, value: object) -> float:
    number = _finite_nonnegative(field_name, value)
    if number > 1.0:
        raise _fail(field_name, "not_unit_interval")
    return number


def _bounded_int(field_name: str, value: object, *, upper: int) -> int:
    try:
        number = require_exact_nonneg_int(field_name, value)
    except ValueError as exc:
        raise _fail(field_name, "not_positive") from exc
    if number < 1 or number > upper:
        raise _fail(field_name, "out_of_bounds")
    return number


def mind_canonical_atom_key(atoms: Sequence[MindAtom]) -> str:
    """Stable slot=value key. Slot order follows ``MindSlot`` declaration."""
    ordered = tuple(sorted(atoms, key=lambda item: _SLOT_ORDER[item.slot]))
    return "|".join(f"{item.slot.value}={item.value}" for item in ordered)


def mind_hypothesis_id_for(
    *,
    owner_id: AgentId,
    subject_id: EntityId,
    aspect: MindAspect,
    atoms: Sequence[MindAtom],
) -> str:
    """sha256 of owner, subject, aspect, and canonical atom key."""
    if type(owner_id) is not AgentId:
        raise _fail("owner_id", "invalid_type")
    if type(subject_id) is not EntityId:
        raise _fail("subject_id", "invalid_type")
    if type(aspect) is not MindAspect:
        raise _fail("aspect", "unknown_aspect")
    if not atoms:
        raise _fail("atoms", "empty_atoms")
    material = (
        f"{THEORY_OF_MIND_POLICY_VERSION}|{owner_id.value}|{subject_id.value}|"
        f"{aspect.value}|{mind_canonical_atom_key(atoms)}"
    )
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return f"{_ID_PREFIX}{digest[:48]}"


def confidence_from_masses(
    support: float,
    counter: float,
    *,
    prior: float = _PRIOR,
) -> float:
    """``support / (support + counter + prior)`` quantized at ``_EFFECT_QUANTUM``."""
    support_mass = _finite_nonnegative("support", support)
    counter_mass = _finite_nonnegative("counter", counter)
    prior_mass = _positive_quantum("prior", prior)
    total = support_mass + counter_mass + prior_mass
    return _quantize_confidence(support_mass / total)


def _catalog_value(slot: MindSlot, value: str) -> None:
    allowed: frozenset[str] | None
    if slot is MindSlot.NEED_KIND:
        allowed = _NEED_KINDS
    elif slot is MindSlot.OUTCOME:
        allowed = _GOAL_OUTCOMES
    elif slot is MindSlot.CONCEPT:
        allowed = _CONCEPTS
    elif slot is MindSlot.CLAIM_PREDICATE:
        allowed = _BELIEF_PREDICATES | _NESTED_MIND_PREDICATES
    elif slot is MindSlot.ACTION:
        allowed = _COMMAND_KINDS
    elif slot is MindSlot.EMOTION_KIND:
        allowed = _EMOTION_KINDS
    elif slot is MindSlot.DIMENSION:
        allowed = _DIMENSIONS
    elif slot is MindSlot.POLARITY:
        allowed = _POLARITIES
    else:
        allowed = None
    if allowed is not None and value not in allowed:
        raise _fail("value", "unknown_enum")


def _value_for(atoms: Sequence[MindAtom], slot: MindSlot) -> str | None:
    for item in atoms:
        if item.slot is slot:
            return item.value
    return None


def _reject_nested(aspect: MindAspect, atoms: tuple[MindAtom, ...]) -> None:
    predicate = _value_for(atoms, MindSlot.CLAIM_PREDICATE)
    claim_object = _value_for(atoms, MindSlot.CLAIM_OBJECT)
    if predicate in _NESTED_MIND_PREDICATES or claim_object in _NESTED_MIND_PREDICATES:
        raise _fail("atoms", "nested_mind_rejected")
    if aspect is MindAspect.BELIEF and predicate not in _BELIEF_PREDICATES:
        raise _fail("atoms", "nested_mind_rejected")


@dataclass(frozen=True, slots=True)
class MindAtom:
    """One copied slot value. The value is a token, not stored prose."""

    slot: MindSlot
    value: str

    def __post_init__(self) -> None:
        if type(self.slot) is not MindSlot:
            raise _fail("slot", "unknown_enum")
        try:
            text = require_stable_id("MindAtom.value", self.value)
        except ValueError as exc:
            raise _fail("value", "invalid_value") from exc
        if "|" in text or "=" in text:
            raise _fail("value", "invalid_value")
        _catalog_value(self.slot, text)
        object.__setattr__(self, "value", text)


@dataclass(frozen=True, slots=True)
class MindUpdateRecord:
    """One arithmetic change. No utterance text and no foreign drive values."""

    tick: int
    hypothesis_id: str
    support_delta: float
    counter_delta: float
    channel: MindEvidenceChannel
    reason: MindUpdateReason
    parent_hypothesis_id: str | None = None

    def __post_init__(self) -> None:
        try:
            tick = require_exact_nonneg_int("MindUpdateRecord.tick", self.tick)
        except ValueError as exc:
            raise _fail("tick", "not_positive") from exc
        object.__setattr__(self, "tick", tick)
        try:
            hypothesis_id = require_stable_id(
                "MindUpdateRecord.hypothesis_id", self.hypothesis_id
            )
        except ValueError as exc:
            raise _fail("hypothesis_id", "invalid_value") from exc
        object.__setattr__(self, "hypothesis_id", hypothesis_id)
        if type(self.channel) is not MindEvidenceChannel:
            raise _fail("channel", "unknown_enum")
        if type(self.reason) is not MindUpdateReason:
            raise _fail("reason", "unknown_enum")
        support_delta = _finite_nonnegative("support_delta", self.support_delta)
        counter_delta = _finite_nonnegative("counter_delta", self.counter_delta)
        if (
            self.reason is not MindUpdateReason.DROP
            and support_delta == 0.0
            and counter_delta == 0.0
        ):
            raise _fail("support_delta", "empty_delta")
        object.__setattr__(self, "support_delta", support_delta)
        object.__setattr__(self, "counter_delta", counter_delta)
        parent = self.parent_hypothesis_id
        if parent is not None:
            try:
                parent = require_stable_id(
                    "MindUpdateRecord.parent_hypothesis_id", parent
                )
            except ValueError as exc:
                raise _fail("parent_hypothesis_id", "invalid_value") from exc
        object.__setattr__(self, "parent_hypothesis_id", parent)


@dataclass(frozen=True, slots=True)
class MindHypothesis:
    """One first-order guess about another agent. Not a semantic belief."""

    owner_id: AgentId
    subject_id: EntityId
    aspect: MindAspect
    atoms: tuple[MindAtom, ...]
    support: float
    counter: float
    evidence_ids: tuple[str, ...]
    counter_evidence_ids: tuple[str, ...]
    channel: MindEvidenceChannel
    update_history: tuple[MindUpdateRecord, ...] = ()
    prior: float = field(default=_PRIOR, repr=False)
    hypothesis_id: str = field(init=False)
    confidence: float = field(init=False)

    def __post_init__(self) -> None:
        if type(self.owner_id) is not AgentId:
            raise _fail("owner_id", "invalid_type")
        if type(self.subject_id) is not EntityId:
            raise _fail("subject_id", "invalid_type")
        if self.subject_id.value == self.owner_id.value:
            raise _fail("subject_id", "self_subject")
        if type(self.aspect) is not MindAspect:
            raise _fail("aspect", "unknown_enum")
        if type(self.channel) is not MindEvidenceChannel:
            raise _fail("channel", "unknown_enum")
        atoms = _atoms_tuple("atoms", self.atoms)
        _reject_nested(self.aspect, atoms)
        object.__setattr__(self, "atoms", atoms)
        support = _finite_nonnegative("support", self.support)
        counter = _finite_nonnegative("counter", self.counter)
        prior = _positive_quantum("prior", self.prior)
        object.__setattr__(self, "support", support)
        object.__setattr__(self, "counter", counter)
        object.__setattr__(self, "prior", prior)
        object.__setattr__(
            self,
            "confidence",
            confidence_from_masses(support, counter, prior=prior),
        )
        object.__setattr__(
            self,
            "hypothesis_id",
            mind_hypothesis_id_for(
                owner_id=self.owner_id,
                subject_id=self.subject_id,
                aspect=self.aspect,
                atoms=atoms,
            ),
        )
        object.__setattr__(
            self, "evidence_ids", _id_tuple("evidence_ids", self.evidence_ids)
        )
        object.__setattr__(
            self,
            "counter_evidence_ids",
            _id_tuple("counter_evidence_ids", self.counter_evidence_ids),
        )
        history = _history_tuple(self.update_history, self.hypothesis_id)
        object.__setattr__(self, "update_history", history)

    def last_update_tick(self) -> int:
        if not self.update_history:
            return 0
        return self.update_history[-1].tick


@dataclass(frozen=True, slots=True)
class TheoryOfMind:
    """Private first-order store for one owner. Flag-off leaves this ``None``."""

    owner_id: AgentId
    hypotheses: tuple[MindHypothesis, ...] = ()
    cue_cursor: tuple[str, ...] = ()
    last_tick: int | None = None
    preferred_ids: tuple[str, ...] = ()
    selection_fallback_used: bool = False

    def __post_init__(self) -> None:
        if type(self.owner_id) is not AgentId:
            raise _fail("owner_id", "invalid_type")
        hypotheses = _hypotheses_tuple(self.owner_id, self.hypotheses)
        object.__setattr__(self, "hypotheses", hypotheses)
        object.__setattr__(self, "cue_cursor", _id_tuple("cue_cursor", self.cue_cursor))
        if self.last_tick is not None:
            try:
                tick = require_exact_nonneg_int("last_tick", self.last_tick)
            except ValueError as exc:
                raise _fail("last_tick", "not_positive") from exc
            object.__setattr__(self, "last_tick", tick)
        if type(self.selection_fallback_used) is not bool:
            raise _fail("selection_fallback_used", "invalid_type")
        object.__setattr__(
            self, "preferred_ids", _id_tuple("preferred_ids", self.preferred_ids)
        )
        _LOG.debug(
            "theory_of_mind_constructed owner_id=%s policy_version=%s "
            "hypothesis_count=%s",
            self.owner_id.value,
            THEORY_OF_MIND_POLICY_VERSION,
            len(self.hypotheses),
        )


@dataclass(frozen=True, slots=True)
class TheoryOfMindPolicy:
    """``theory-of-mind-v1`` thresholds. Not a runner JSON key."""

    version: str = THEORY_OF_MIND_POLICY_VERSION
    prior: float = _PRIOR
    behavior_weight: float = _BEHAVIOR_WEIGHT
    testimony_weight: float = _TESTIMONY_WEIGHT
    trust_high_multiplier: float = _TRUST_HIGH_MULTIPLIER
    trust_low_multiplier: float = _TRUST_LOW_MULTIPLIER
    trust_high_threshold: float = _TRUST_HIGH_THRESHOLD
    emotion_multiplier: float = _EMOTION_MULTIPLIER
    emotion_threshold: float = _EMOTION_THRESHOLD
    future_discount: float = _FUTURE_DISCOUNT
    action_threshold: float = _ACTION_THRESHOLD
    max_hypotheses: int = _MAX_HYPOTHESES
    max_history: int = _MAX_HISTORY
    allow_provider: bool = False

    def __post_init__(self) -> None:
        if self.version != THEORY_OF_MIND_POLICY_VERSION:
            raise _fail("version", "unsupported")
        object.__setattr__(self, "prior", _positive_quantum("prior", self.prior))
        object.__setattr__(
            self,
            "behavior_weight",
            _positive_quantum("behavior_weight", self.behavior_weight),
        )
        object.__setattr__(
            self,
            "testimony_weight",
            _positive_quantum("testimony_weight", self.testimony_weight),
        )
        object.__setattr__(
            self,
            "trust_high_multiplier",
            _positive_quantum("trust_high_multiplier", self.trust_high_multiplier),
        )
        object.__setattr__(
            self,
            "trust_low_multiplier",
            _positive_quantum("trust_low_multiplier", self.trust_low_multiplier),
        )
        object.__setattr__(
            self,
            "trust_high_threshold",
            _unit_quantum("trust_high_threshold", self.trust_high_threshold),
        )
        object.__setattr__(
            self,
            "emotion_multiplier",
            _positive_quantum("emotion_multiplier", self.emotion_multiplier),
        )
        object.__setattr__(
            self,
            "emotion_threshold",
            _unit_quantum("emotion_threshold", self.emotion_threshold),
        )
        object.__setattr__(
            self,
            "future_discount",
            _unit_quantum("future_discount", self.future_discount),
        )
        object.__setattr__(
            self,
            "action_threshold",
            _unit_quantum("action_threshold", self.action_threshold),
        )
        object.__setattr__(
            self,
            "max_hypotheses",
            _bounded_int("max_hypotheses", self.max_hypotheses, upper=_MAX_HYPOTHESES),
        )
        object.__setattr__(
            self,
            "max_history",
            _bounded_int("max_history", self.max_history, upper=_MAX_HISTORY),
        )
        if type(self.allow_provider) is not bool:
            raise _fail("allow_provider", "invalid_type")
        _LOG.debug(
            "theory_of_mind_policy_constructed policy_version=%s hypothesis_count=%s",
            self.version,
            0,
        )


def default_theory_of_mind_policy(
    *, allow_provider: bool = False
) -> TheoryOfMindPolicy:
    """Return ``theory-of-mind-v1``. Provider calls stay off unless a test opts in."""
    if type(allow_provider) is not bool:
        raise _fail("allow_provider", "invalid_type")
    return TheoryOfMindPolicy(allow_provider=allow_provider)


def empty_theory_of_mind(owner_id: AgentId) -> TheoryOfMind:
    """An owner store with no hypotheses and an empty cue cursor."""
    return TheoryOfMind(owner_id=owner_id)


def require_owner_theory(
    model: object,
    owner_id: AgentId,
    *,
    field_name: str,
) -> None:
    """Reject a foreign or mistyped mind model. ``None`` is passthrough."""
    if model is None:
        return
    if type(owner_id) is not AgentId:
        raise _fail("owner_id", "invalid_type")
    if type(model) is not TheoryOfMind:
        raise TypeError(f"{field_name} must be TheoryOfMind")
    if model.owner_id != owner_id:
        raise ValueError(f"{field_name} owner_id mismatch")


def _atoms_tuple(name: str, values: object) -> tuple[MindAtom, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise _fail(name, "invalid_type")
    if isinstance(values, (set, frozenset)):
        raise _fail(name, "invalid_type")
    atoms = tuple(values)
    if not atoms:
        raise _fail(name, "empty_atoms")
    seen: set[MindSlot] = set()
    for item in atoms:
        if type(item) is not MindAtom:
            raise _fail(name, "invalid_type")
        if item.slot in seen:
            raise _fail(name, "duplicate_slot")
        seen.add(item.slot)
    return atoms


def _id_tuple(name: str, values: object) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise _fail(name, "invalid_type")
    if isinstance(values, (set, frozenset)):
        raise _fail(name, "invalid_type")
    resolved: list[str] = []
    for item in values:
        try:
            text = require_stable_id(name, item)
        except ValueError as exc:
            raise _fail(name, "invalid_value") from exc
        resolved.append(text)
    return tuple(resolved)


def _history_tuple(
    values: object,
    hypothesis_id: str,
) -> tuple[MindUpdateRecord, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise _fail("update_history", "invalid_type")
    if isinstance(values, (set, frozenset)):
        raise _fail("update_history", "invalid_type")
    records = tuple(values)
    for item in records:
        if type(item) is not MindUpdateRecord:
            raise _fail("update_history", "invalid_type")
        if item.hypothesis_id != hypothesis_id:
            raise _fail("update_history", "owner_mismatch")
    return records


def _hypotheses_tuple(
    owner_id: AgentId,
    values: object,
) -> tuple[MindHypothesis, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise _fail("hypotheses", "invalid_type")
    if isinstance(values, (set, frozenset)):
        raise _fail("hypotheses", "invalid_type")
    items = tuple(values)
    seen: set[str] = set()
    for item in items:
        if type(item) is not MindHypothesis:
            raise _fail("hypotheses", "invalid_type")
        if item.owner_id != owner_id:
            raise _fail("hypotheses", "owner_mismatch")
        if item.hypothesis_id in seen:
            raise _fail("hypotheses", "duplicate_hypothesis")
        seen.add(item.hypothesis_id)
    return items


def aspect_rank(aspect: MindAspect) -> int:
    """Bias order: future action, intention, need, goal, emotion, then the rest."""
    order = (
        MindAspect.FUTURE_ACTION,
        MindAspect.INTENTION,
        MindAspect.NEED,
        MindAspect.GOAL,
        MindAspect.EMOTION,
        MindAspect.RELATIONSHIP,
        MindAspect.KNOWLEDGE,
        MindAspect.BELIEF,
    )
    return order.index(aspect)


_NEED_FROM_CONCEPT: Final[dict[str, str]] = {
    "food": "hunger",
    "water": "thirst",
    "rest": "fatigue",
    "danger": "safety",
}
_FUTURE_FROM_NEED: Final[dict[str, str]] = {
    "hunger": "eat",
    "thirst": "drink",
    "fatigue": "sleep",
    "safety": "flee",
}
_CLOSED_RELATIONS: Final[frozenset[str]] = frozenset(
    {
        "at",
        "has",
        "empty",
        "danger",
        "trusts",
        "distrusts",
        "fears",
        "wants",
        "needs",
        "knows",
        "intends",
        "feels",
    }
)
_BELIEF_OBJECTS_WITHOUT_ID: Final[frozenset[str]] = frozenset({"empty", "danger"})
_MILD_COUNTER_WEIGHT: Final[float] = 1.0


@dataclass(frozen=True, slots=True)
class MindCue:
    """One owner-visible cue. Dropped cues are not stored on the model."""

    owner_id: AgentId
    tick: int
    evidence_id: str
    channel: MindEvidenceChannel
    reason: MindUpdateReason
    subject_id: EntityId | None = None
    aspect: MindAspect | None = None
    atoms: tuple[MindAtom, ...] = ()
    support_weight: float = 0.0
    counter_weight: float = 0.0
    drop_code: str | None = None

    def __post_init__(self) -> None:
        if type(self.owner_id) is not AgentId:
            raise _fail("owner_id", "invalid_type")
        if type(self.channel) is not MindEvidenceChannel:
            raise _fail("channel", "unknown_enum")
        if type(self.reason) is not MindUpdateReason:
            raise _fail("reason", "unknown_enum")
        try:
            require_exact_nonneg_int("MindCue.tick", self.tick)
        except ValueError as exc:
            raise _fail("tick", "not_positive") from exc
        try:
            require_stable_id("MindCue.evidence_id", self.evidence_id)
        except ValueError as exc:
            raise _fail("evidence_id", "invalid_value") from exc


@dataclass
class _Acc:
    subject_id: EntityId
    aspect: MindAspect
    atoms: tuple[MindAtom, ...]
    support: float
    counter: float
    evidence_ids: list[str]
    counter_evidence_ids: list[str]
    channel: MindEvidenceChannel
    history: list[MindUpdateRecord]
    prior: float

    def hypothesis_id(self, owner_id: AgentId) -> str:
        return mind_hypothesis_id_for(
            owner_id=owner_id,
            subject_id=self.subject_id,
            aspect=self.aspect,
            atoms=self.atoms,
        )


def _atom(slot: MindSlot, value: str) -> MindAtom:
    return MindAtom(slot=slot, value=value)


def _evidence_id(provenance: object) -> str:
    event_id = getattr(provenance, "source_event_id", None)
    if event_id is None:
        raise _fail("evidence_id", "invalid_value")
    return str(event_id.value)


def _append_limited(bucket: list[str], value: str, limit: int) -> None:
    if value in bucket:
        return
    bucket.append(value)
    overflow = len(bucket) - limit
    if overflow > 0:
        del bucket[:overflow]


def _append_history(acc: _Acc, record: MindUpdateRecord, limit: int) -> None:
    acc.history.append(record)
    overflow = len(acc.history) - limit
    if overflow > 0:
        del acc.history[:overflow]


def _emotion_multiplier(intensity: float | None, policy: TheoryOfMindPolicy) -> float:
    if intensity is None:
        return 1.0
    number = _finite_nonnegative("owner_emotion_intensity", intensity)
    if number >= policy.emotion_threshold:
        return policy.emotion_multiplier
    return 1.0


def _trust_multiplier(
    profiles: Sequence[DirectedRelationshipProfile],
    *,
    owner_id: AgentId,
    speaker: EntityId,
    policy: TheoryOfMindPolicy,
) -> float:
    for profile in profiles:
        if type(profile) is not DirectedRelationshipProfile:
            raise _fail("profiles", "invalid_type")
        if profile.source_id != owner_id:
            continue
        if profile.target_id.value != speaker.value:
            continue
        trust = None
        for dimension in profile.dimensions:
            if dimension.dimension is RelationshipDimension.TRUST:
                trust = dimension.value
                break
        if trust is None:
            return 1.0
        if trust >= policy.trust_high_threshold:
            return policy.trust_high_multiplier
        if trust < 0.0:
            return policy.trust_low_multiplier
        return 1.0
    return 1.0


def _known_subjects(observation: Observation) -> set[EntityId]:
    known: set[EntityId] = set()
    for body in observation.visible_bodies:
        known.add(body.entity_id)
    for occurrence in observation.occurrences:
        if occurrence.actor_id is not None:
            known.add(occurrence.actor_id)
        if occurrence.other_entity_id is not None:
            known.add(occurrence.other_entity_id)
    for communication in observation.communications:
        known.add(communication.speaker_id)
        known.add(communication.listener_id)
    return known


def _visible_tokens(observation: Observation) -> set[str]:
    tokens = {item.value for item in _known_subjects(observation)}
    for location in observation.locations:
        tokens.add(location.entity_id.value)
    for exit_ in observation.exits:
        tokens.add(exit_.destination_id.value)
    for occurrence in observation.occurrences:
        if occurrence.destination_id is not None:
            tokens.add(occurrence.destination_id.value)
    return tokens


def _cue(
    *,
    owner_id: AgentId,
    tick: int,
    evidence_id: str,
    channel: MindEvidenceChannel,
    reason: MindUpdateReason,
    subject_id: EntityId | None = None,
    aspect: MindAspect | None = None,
    atoms: tuple[MindAtom, ...] = (),
    support_weight: float = 0.0,
    counter_weight: float = 0.0,
    drop_code: str | None = None,
) -> MindCue:
    return MindCue(
        owner_id=owner_id,
        tick=tick,
        evidence_id=evidence_id,
        channel=channel,
        reason=reason,
        subject_id=subject_id,
        aspect=aspect,
        atoms=atoms,
        support_weight=support_weight,
        counter_weight=counter_weight,
        drop_code=drop_code,
    )


def _drop(
    *,
    owner_id: AgentId,
    tick: int,
    evidence_id: str,
    channel: MindEvidenceChannel,
    code: str,
) -> MindCue:
    return _cue(
        owner_id=owner_id,
        tick=tick,
        evidence_id=evidence_id,
        channel=channel,
        reason=MindUpdateReason.DROP,
        drop_code=code,
    )


def _eligible_subject(
    subject: EntityId | None,
    *,
    observer_id: EntityId,
    known: set[EntityId],
) -> str | None:
    if subject is None:
        return "unknown_subject"
    if subject == observer_id:
        return "self_subject"
    if subject not in known:
        return "unknown_subject"
    return None


def _knowledge_atoms(
    observation: Observation,
    kind: str,
) -> tuple[MindAtom, ...] | None:
    if kind not in _COMMAND_KINDS:
        return None
    body = observation.self_body
    if body is None:
        return None
    if len({location.entity_id for location in observation.locations}) > 1:
        return None
    return (
        _atom(MindSlot.ACTION, kind),
        _atom(MindSlot.LOCATION, body.location_id.value),
    )


def _behavior_pairs(
    occurrence: ObservedOccurrence,
    observation: Observation,
    subject: EntityId,
) -> list[tuple[MindAspect, tuple[MindAtom, ...]]]:
    kind = occurrence.kind
    is_actor = occurrence.actor_id == subject
    is_other = occurrence.other_entity_id == subject
    target = occurrence.other_entity_id
    pairs: list[tuple[MindAspect, tuple[MindAtom, ...]]] = []
    if is_actor and kind == "eat":
        pairs.append((MindAspect.NEED, (_atom(MindSlot.NEED_KIND, "hunger"),)))
    elif is_actor and kind == "drink":
        pairs.append((MindAspect.NEED, (_atom(MindSlot.NEED_KIND, "thirst"),)))
    elif is_actor and kind == "sleep":
        pairs.append((MindAspect.NEED, (_atom(MindSlot.NEED_KIND, "fatigue"),)))
    elif is_actor and kind == "flee":
        pairs.append((MindAspect.NEED, (_atom(MindSlot.NEED_KIND, "safety"),)))
        pairs.append((MindAspect.EMOTION, (_atom(MindSlot.EMOTION_KIND, "fear"),)))
    elif is_other and kind == "attack":
        pairs.append((MindAspect.NEED, (_atom(MindSlot.NEED_KIND, "safety"),)))
    elif is_actor and kind == "move" and occurrence.destination_id is not None:
        pairs.append(
            (
                MindAspect.GOAL,
                (
                    _atom(MindSlot.OUTCOME, "reach_place"),
                    _atom(MindSlot.LOCATION, occurrence.destination_id.value),
                ),
            )
        )
    elif is_actor and kind in {"attack", "help"} and target is not None:
        polarity = "positive" if kind == "help" else "negative"
        pairs.append(
            (
                MindAspect.RELATIONSHIP,
                (
                    _atom(MindSlot.DIMENSION, "trust"),
                    _atom(MindSlot.POLARITY, polarity),
                    _atom(MindSlot.TARGET, target.value),
                ),
            )
        )
        if kind == "attack":
            pairs.append((MindAspect.EMOTION, (_atom(MindSlot.EMOTION_KIND, "anger"),)))
    elif is_actor and kind == "attack":
        pairs.append((MindAspect.EMOTION, (_atom(MindSlot.EMOTION_KIND, "anger"),)))
    elif is_other and kind == "help":
        pairs.append((MindAspect.EMOTION, (_atom(MindSlot.EMOTION_KIND, "relief"),)))
    elif is_actor and kind in _COMMAND_KINDS:
        pairs.append((MindAspect.INTENTION, (_atom(MindSlot.ACTION, kind),)))
    knowledge = _knowledge_atoms(observation, kind)
    witnessed = is_actor or any(
        body.entity_id == subject for body in observation.visible_bodies
    )
    if knowledge is not None and witnessed:
        pairs.append((MindAspect.KNOWLEDGE, knowledge))
    return pairs


def _support_cue(
    *,
    owner_id: AgentId,
    tick: int,
    evidence_id: str,
    channel: MindEvidenceChannel,
    subject: EntityId,
    aspect: MindAspect,
    atoms: tuple[MindAtom, ...],
    weight: float,
) -> MindCue:
    return _cue(
        owner_id=owner_id,
        tick=tick,
        evidence_id=evidence_id,
        channel=channel,
        reason=MindUpdateReason.SUPPORT,
        subject_id=subject,
        aspect=aspect,
        atoms=atoms,
        support_weight=_quantize_mass(weight),
    )


def _occurrence_cues(
    observation: Observation,
    *,
    owner_id: AgentId,
    known: set[EntityId],
    weight: float,
    channel: MindEvidenceChannel,
) -> list[MindCue]:
    observer = observation.observer_id
    cues: list[MindCue] = []
    for occurrence in observation.occurrences:
        if type(occurrence) is not ObservedOccurrence:
            raise _fail("occurrences", "invalid_type")
        if occurrence.audience_role.value == "":
            continue
        if occurrence.success is False:
            continue
        evidence_id = _evidence_id(occurrence.provenance)
        candidates: list[EntityId] = []
        if occurrence.actor_id is not None:
            candidates.append(occurrence.actor_id)
        if (
            occurrence.other_entity_id is not None
            and occurrence.other_entity_id not in candidates
        ):
            candidates.append(occurrence.other_entity_id)
        for body in observation.visible_bodies:
            if body.entity_id not in candidates:
                candidates.append(body.entity_id)
        produced = False
        for subject in candidates:
            refusal = _eligible_subject(subject, observer_id=observer, known=known)
            if refusal is not None:
                cues.append(
                    _drop(
                        owner_id=owner_id,
                        tick=observation.tick,
                        evidence_id=evidence_id,
                        channel=channel,
                        code=refusal,
                    )
                )
                continue
            for aspect, atoms in _behavior_pairs(occurrence, observation, subject):
                produced = True
                cues.append(
                    _support_cue(
                        owner_id=owner_id,
                        tick=observation.tick,
                        evidence_id=evidence_id,
                        channel=channel,
                        subject=subject,
                        aspect=aspect,
                        atoms=atoms,
                        weight=weight,
                    )
                )
        if not produced and not cues:
            continue
    for body in observation.visible_bodies:
        if type(body) is not VisibleBody:
            raise _fail("visible_bodies", "invalid_type")
        if body.coarse_health not in {CoarseHealth.CRITICAL, CoarseHealth.INJURED}:
            continue
        refusal = _eligible_subject(body.entity_id, observer_id=observer, known=known)
        evidence_id = f"health-{body.entity_id.value}"
        if refusal is not None:
            cues.append(
                _drop(
                    owner_id=owner_id,
                    tick=observation.tick,
                    evidence_id=evidence_id,
                    channel=channel,
                    code=refusal,
                )
            )
            continue
        cues.append(
            _support_cue(
                owner_id=owner_id,
                tick=observation.tick,
                evidence_id=evidence_id,
                channel=channel,
                subject=body.entity_id,
                aspect=MindAspect.EMOTION,
                atoms=(_atom(MindSlot.EMOTION_KIND, "anxiety"),),
                weight=weight,
            )
        )
    return cues


def _relation_atoms(
    relation: CommunicationRelation,
    *,
    visible: set[str],
) -> tuple[MindAspect, tuple[MindAtom, ...]] | str:
    predicate = relation.predicate
    token = relation.object
    if predicate in _NESTED_MIND_PREDICATES or token in _NESTED_MIND_PREDICATES:
        return "nested_mind_rejected"
    if predicate not in _CLOSED_RELATIONS:
        return "ambiguous_utterance"
    if predicate in {"empty", "danger"}:
        return (
            MindAspect.BELIEF,
            (_atom(MindSlot.CLAIM_PREDICATE, predicate),),
        )
    if predicate in {"at", "has"}:
        if token not in visible:
            return "ambiguous_utterance"
        return (
            MindAspect.BELIEF,
            (
                _atom(MindSlot.CLAIM_PREDICATE, predicate),
                _atom(MindSlot.CLAIM_OBJECT, token),
            ),
        )
    if predicate in {"trusts", "distrusts", "fears"}:
        if token not in visible:
            return "ambiguous_utterance"
        if predicate == "fears":
            dimension = "fear"
            polarity = "positive"
        else:
            dimension = "trust"
            polarity = "positive" if predicate == "trusts" else "negative"
        return (
            MindAspect.RELATIONSHIP,
            (
                _atom(MindSlot.DIMENSION, dimension),
                _atom(MindSlot.POLARITY, polarity),
                _atom(MindSlot.TARGET, token),
            ),
        )
    if predicate in {"wants", "needs"}:
        if token in _NEED_FROM_CONCEPT or token in _NEED_KINDS:
            kind = _NEED_FROM_CONCEPT.get(token, token)
            return (MindAspect.NEED, (_atom(MindSlot.NEED_KIND, kind),))
        if token in visible:
            return (
                MindAspect.GOAL,
                (
                    _atom(MindSlot.OUTCOME, "reach_place"),
                    _atom(MindSlot.LOCATION, token),
                ),
            )
        return "ambiguous_utterance"
    if predicate == "intends":
        if token not in _COMMAND_KINDS:
            return "ambiguous_utterance"
        return (MindAspect.INTENTION, (_atom(MindSlot.ACTION, token),))
    if predicate == "feels":
        if token not in _EMOTION_KINDS:
            return "ambiguous_utterance"
        return (MindAspect.EMOTION, (_atom(MindSlot.EMOTION_KIND, token),))
    if token not in _COMMAND_KINDS and token not in visible:
        return "ambiguous_utterance"
    if token in _COMMAND_KINDS:
        return (MindAspect.KNOWLEDGE, (_atom(MindSlot.ACTION, token),))
    return (MindAspect.KNOWLEDGE, (_atom(MindSlot.LOCATION, token),))


def _communication_cues(
    observation: Observation,
    *,
    owner_id: AgentId,
    known: set[EntityId],
    profiles: Sequence[DirectedRelationshipProfile],
    policy: TheoryOfMindPolicy,
    emotion_scale: float,
) -> list[MindCue]:
    visible = _visible_tokens(observation)
    cues: list[MindCue] = []
    base = policy.testimony_weight * emotion_scale
    for item in observation.communications:
        if type(item) is not ObservedCommunication:
            raise _fail("communications", "invalid_type")
        evidence_id = _evidence_id(item.provenance)
        hop = item.utterance.declared.hop_count
        if hop > 1:
            cues.append(
                _drop(
                    owner_id=owner_id,
                    tick=observation.tick,
                    evidence_id=evidence_id,
                    channel=MindEvidenceChannel.COMMUNICATION,
                    code="multi_hop_deferred",
                )
            )
            continue
        refusal = _eligible_subject(
            item.speaker_id,
            observer_id=observation.observer_id,
            known=known,
        )
        if refusal is not None:
            cues.append(
                _drop(
                    owner_id=owner_id,
                    tick=observation.tick,
                    evidence_id=evidence_id,
                    channel=MindEvidenceChannel.COMMUNICATION,
                    code=refusal,
                )
            )
            continue
        content = item.utterance.content
        concepts = tuple(content.concepts)
        relations = tuple(content.relations)
        mapped: tuple[MindAspect, tuple[MindAtom, ...]] | str
        if len(concepts) == 1 and not relations:
            token = concepts[0]
            if token not in _NEED_FROM_CONCEPT:
                mapped = "ambiguous_utterance"
            else:
                mapped = (
                    MindAspect.NEED,
                    (
                        _atom(MindSlot.NEED_KIND, _NEED_FROM_CONCEPT[token]),
                        _atom(MindSlot.CONCEPT, token),
                    ),
                )
        elif len(relations) == 1 and not concepts:
            relation = relations[0]
            if type(relation) is not CommunicationRelation:
                raise _fail("relations", "invalid_type")
            if relation.subject != item.speaker_id.value:
                mapped = "ambiguous_utterance"
            else:
                mapped = _relation_atoms(relation, visible=visible)
        else:
            mapped = "ambiguous_utterance"
        if isinstance(mapped, str):
            cues.append(
                _drop(
                    owner_id=owner_id,
                    tick=observation.tick,
                    evidence_id=evidence_id,
                    channel=MindEvidenceChannel.COMMUNICATION,
                    code=mapped,
                )
            )
            continue
        aspect, atoms = mapped
        scale = _trust_multiplier(
            profiles,
            owner_id=owner_id,
            speaker=item.speaker_id,
            policy=policy,
        )
        cues.append(
            _support_cue(
                owner_id=owner_id,
                tick=observation.tick,
                evidence_id=evidence_id,
                channel=MindEvidenceChannel.COMMUNICATION,
                subject=item.speaker_id,
                aspect=aspect,
                atoms=atoms,
                weight=base * scale,
            )
        )
    return cues


def _slot_value(atoms: Sequence[MindAtom], slot: MindSlot) -> str | None:
    return _value_for(atoms, slot)


def _contradicts(
    hypothesis: MindHypothesis,
    *,
    kinds: set[str],
    destinations: set[str],
    helped: set[str],
) -> bool:
    if hypothesis.aspect is MindAspect.NEED:
        kind = _slot_value(hypothesis.atoms, MindSlot.NEED_KIND)
        required = {"hunger": "eat", "thirst": "drink", "fatigue": "sleep"}.get(
            kind or ""
        )
        if required is None:
            return False
        return required not in kinds
    if hypothesis.aspect is MindAspect.GOAL:
        location = _slot_value(hypothesis.atoms, MindSlot.LOCATION)
        if "move" not in kinds or location is None or not destinations:
            return False
        return any(item != location for item in destinations)
    if hypothesis.aspect is MindAspect.FUTURE_ACTION:
        action = _slot_value(hypothesis.atoms, MindSlot.ACTION)
        if action is None:
            return False
        return action not in kinds
    if hypothesis.aspect is MindAspect.RELATIONSHIP:
        polarity = _slot_value(hypothesis.atoms, MindSlot.POLARITY)
        target = _slot_value(hypothesis.atoms, MindSlot.TARGET)
        dimension = _slot_value(hypothesis.atoms, MindSlot.DIMENSION)
        if dimension != "trust" or polarity != "negative" or target is None:
            return False
        return target in helped
    return False


def _counter_cues(
    observation: Observation,
    *,
    owner_id: AgentId,
    model: TheoryOfMind | None,
) -> list[MindCue]:
    if model is None or not model.hypotheses:
        return []
    visible = {body.entity_id for body in observation.visible_bodies}
    kinds: dict[EntityId, set[str]] = {}
    destinations: dict[EntityId, set[str]] = {}
    helped: dict[EntityId, set[str]] = {}
    evidence_for: dict[EntityId, str] = {}
    for occurrence in observation.occurrences:
        actor = occurrence.actor_id
        if actor is None or actor not in visible:
            continue
        kinds.setdefault(actor, set()).add(occurrence.kind)
        evidence_for.setdefault(actor, _evidence_id(occurrence.provenance))
        if occurrence.kind == "move" and occurrence.destination_id is not None:
            destinations.setdefault(actor, set()).add(occurrence.destination_id.value)
        if occurrence.kind == "help" and occurrence.other_entity_id is not None:
            helped.setdefault(actor, set()).add(occurrence.other_entity_id.value)
    cues: list[MindCue] = []
    for hypothesis in model.hypotheses:
        subject = hypothesis.subject_id
        if subject not in visible or subject not in kinds:
            continue
        if not _contradicts(
            hypothesis,
            kinds=kinds[subject],
            destinations=destinations.get(subject, set()),
            helped=helped.get(subject, set()),
        ):
            continue
        cues.append(
            _cue(
                owner_id=owner_id,
                tick=observation.tick,
                evidence_id=evidence_for[subject],
                channel=MindEvidenceChannel.OBSERVED_BEHAVIOR,
                reason=MindUpdateReason.COUNTER,
                subject_id=subject,
                aspect=hypothesis.aspect,
                atoms=hypothesis.atoms,
                counter_weight=_MILD_COUNTER_WEIGHT,
            )
        )
    return cues


def cues_from_observation(
    observation: object,
    *,
    owner_id: AgentId,
    profiles: Sequence[DirectedRelationshipProfile] = (),
    cue_cursor: Sequence[str] = (),
    owner_emotion_intensity: float | None = None,
    model: TheoryOfMind | None = None,
    policy: TheoryOfMindPolicy | None = None,
) -> tuple[MindCue, ...]:
    """Build cues from one observation. The argument must be an ``Observation``."""
    if type(observation) is not Observation:
        raise TypeError("cues_from_observation requires Observation")
    if type(owner_id) is not AgentId:
        raise _fail("owner_id", "invalid_type")
    if isinstance(profiles, (str, bytes)) or not isinstance(profiles, Sequence):
        raise _fail("profiles", "invalid_type")
    if model is not None and type(model) is not TheoryOfMind:
        raise _fail("model", "invalid_type")
    if model is not None and model.owner_id != owner_id:
        _LOG.error(
            "theory_of_mind_owner_mismatch owner_id=%s reason_code=owner_mismatch",
            owner_id.value,
        )
        raise _fail("owner_id", "owner_mismatch")
    resolved_policy = policy if policy is not None else default_theory_of_mind_policy()
    if type(resolved_policy) is not TheoryOfMindPolicy:
        raise _fail("policy", "invalid_type")
    _id_tuple("cue_cursor", cue_cursor)
    scale = _emotion_multiplier(owner_emotion_intensity, resolved_policy)
    known = _known_subjects(observation)
    behavior = resolved_policy.behavior_weight * scale
    cues = _occurrence_cues(
        observation,
        owner_id=owner_id,
        known=known,
        weight=behavior,
        channel=MindEvidenceChannel.OBSERVED_BEHAVIOR,
    )
    cues.extend(
        _communication_cues(
            observation,
            owner_id=owner_id,
            known=known,
            profiles=tuple(profiles),
            policy=resolved_policy,
            emotion_scale=scale,
        )
    )
    cues.extend(_counter_cues(observation, owner_id=owner_id, model=model))
    return tuple(cues)


def cues_from_reconstructions(
    context: object,
    *,
    owner_id: AgentId,
    observer_id: EntityId,
    used_provenance_ids: Sequence[str],
    policy: TheoryOfMindPolicy | None = None,
) -> tuple[MindCue, ...]:
    """Memory cues whose provenance is not already on this observation."""
    if type(context) is not RetrievedMemoryContext:
        raise TypeError("cues_from_reconstructions requires RetrievedMemoryContext")
    if type(owner_id) is not AgentId:
        raise _fail("owner_id", "invalid_type")
    if type(observer_id) is not EntityId:
        raise _fail("observer_id", "invalid_type")
    if context.owner_id != owner_id:
        _LOG.error(
            "theory_of_mind_owner_mismatch owner_id=%s reason_code=owner_mismatch",
            owner_id.value,
        )
        raise _fail("owner_id", "owner_mismatch")
    resolved = policy if policy is not None else default_theory_of_mind_policy()
    used = set(_id_tuple("used_provenance_ids", used_provenance_ids))
    known_ids = {item.value for item in context.memory_ids}
    cues: list[MindCue] = []
    for item in context.reconstructions:
        if type(item) is not ReconstructedMemory:
            raise _fail("reconstructions", "invalid_type")
        if item.owner_id != owner_id:
            _LOG.error(
                "theory_of_mind_owner_mismatch owner_id=%s reason_code=owner_mismatch",
                owner_id.value,
            )
            raise _fail("reconstruction.owner_id", "owner_mismatch")
        sources = tuple(source.value for source in item.source_memory_ids)
        if any(type(source) is not MemoryId for source in item.source_memory_ids):
            raise _fail("source_memory_ids", "foreign_memory")
        if any(source not in known_ids for source in sources):
            raise _fail("source_memory_ids", "foreign_memory")
        if any(source in used for source in sources):
            continue
        action = next((tag for tag in item.context.tags if tag in _COMMAND_KINDS), None)
        actors = [
            entity.entity_id
            for entity in item.entities
            if entity.entity_id is not None and entity.entity_id != observer_id
        ]
        if action is None or len(actors) != 1 or not sources:
            _LOG.warning(
                "theory_of_mind_cue_dropped reason_code=%s",
                "ambiguous_utterance",
            )
            continue
        subject = actors[0]
        if subject is None:
            continue
        cues.append(
            _support_cue(
                owner_id=owner_id,
                tick=item.reconstructed_at_tick,
                evidence_id=sources[0],
                channel=MindEvidenceChannel.MEMORY,
                subject=subject,
                aspect=MindAspect.INTENTION,
                atoms=(_atom(MindSlot.ACTION, action),),
                weight=resolved.behavior_weight,
            )
        )
    return tuple(cues)


def _acc_from(item: MindHypothesis) -> _Acc:
    return _Acc(
        subject_id=item.subject_id,
        aspect=item.aspect,
        atoms=item.atoms,
        support=item.support,
        counter=item.counter,
        evidence_ids=list(item.evidence_ids),
        counter_evidence_ids=list(item.counter_evidence_ids),
        channel=item.channel,
        history=list(item.update_history),
        prior=item.prior,
    )


def _freeze(owner_id: AgentId, acc: _Acc) -> MindHypothesis:
    return MindHypothesis(
        owner_id=owner_id,
        subject_id=acc.subject_id,
        aspect=acc.aspect,
        atoms=acc.atoms,
        support=acc.support,
        counter=acc.counter,
        evidence_ids=tuple(acc.evidence_ids),
        counter_evidence_ids=tuple(acc.counter_evidence_ids),
        channel=acc.channel,
        update_history=tuple(acc.history),
        prior=acc.prior,
    )


def _evict(store: dict[str, _Acc], limit: int) -> int:
    dropped = 0
    while len(store) > limit:
        ranked = sorted(
            store.items(),
            key=lambda item: (
                confidence_from_masses(
                    item[1].support, item[1].counter, prior=item[1].prior
                ),
                item[1].history[-1].tick if item[1].history else 0,
                "",
            ),
        )
        # Lowest confidence, then oldest tick, then greater id.
        ranked.sort(
            key=lambda item: (
                confidence_from_masses(
                    item[1].support, item[1].counter, prior=item[1].prior
                ),
                item[1].history[-1].tick if item[1].history else 0,
                "",
            )
        )
        greatest = max(store, key=lambda key: key)
        lowest_conf = min(
            confidence_from_masses(item.support, item.counter, prior=item.prior)
            for item in store.values()
        )
        candidates = [
            key
            for key, item in store.items()
            if confidence_from_masses(item.support, item.counter, prior=item.prior)
            == lowest_conf
        ]
        oldest_tick = min(
            (store[key].history[-1].tick if store[key].history else 0)
            for key in candidates
        )
        oldest = [
            key
            for key in candidates
            if (store[key].history[-1].tick if store[key].history else 0) == oldest_tick
        ]
        victim = max(oldest)
        del store[victim]
        dropped += 1
        _ = (ranked, greatest)
    return dropped


def _future_action_for(
    parent: _Acc, *, owner_entity_id: str | None = None
) -> str | None:
    if parent.aspect is MindAspect.NEED:
        kind = _slot_value(parent.atoms, MindSlot.NEED_KIND)
        return None if kind is None else _FUTURE_FROM_NEED.get(kind)
    if parent.aspect is MindAspect.GOAL:
        if _slot_value(parent.atoms, MindSlot.OUTCOME) == "reach_place":
            return "move"
        return None
    if parent.aspect is MindAspect.INTENTION:
        return _slot_value(parent.atoms, MindSlot.ACTION)
    if parent.aspect is MindAspect.EMOTION:
        kind = _slot_value(parent.atoms, MindSlot.EMOTION_KIND)
        if kind == "anger":
            return "attack"
        if kind == "fear":
            return "flee"
        return None
    if parent.aspect is MindAspect.RELATIONSHIP:
        polarity = _slot_value(parent.atoms, MindSlot.POLARITY)
        dimension = _slot_value(parent.atoms, MindSlot.DIMENSION)
        if dimension == "trust" and polarity == "negative":
            target = _slot_value(parent.atoms, MindSlot.TARGET)
            if owner_entity_id is not None and target != owner_entity_id:
                return None
            return "attack"
        return None
    return None


def derive_future_actions(
    model: TheoryOfMind,
    policy: TheoryOfMindPolicy,
    *,
    tick: int,
    owner_entity_id: EntityId | None = None,
) -> TheoryOfMind:
    """Derive at most one future action per subject from the best parent."""
    if type(model) is not TheoryOfMind:
        raise _fail("model", "invalid_type")
    if type(policy) is not TheoryOfMindPolicy:
        raise _fail("policy", "invalid_type")
    if owner_entity_id is not None and type(owner_entity_id) is not EntityId:
        raise _fail("owner_entity_id", "invalid_type")
    by_subject: dict[EntityId, list[_Acc]] = {}
    store = {
        item.hypothesis_id: _acc_from(item)
        for item in model.hypotheses
        if item.aspect is not MindAspect.FUTURE_ACTION
    }
    derived = {
        item.hypothesis_id: _acc_from(item)
        for item in model.hypotheses
        if item.aspect is MindAspect.FUTURE_ACTION
    }
    for acc in store.values():
        confidence = confidence_from_masses(acc.support, acc.counter, prior=acc.prior)
        if confidence < policy.action_threshold:
            continue
        by_subject.setdefault(acc.subject_id, []).append(acc)
    for subject, parents in by_subject.items():
        parents.sort(key=lambda item: item.hypothesis_id(model.owner_id))
        parents.sort(key=lambda item: aspect_rank(item.aspect))
        parents.sort(
            key=lambda item: confidence_from_masses(
                item.support, item.counter, prior=item.prior
            ),
            reverse=True,
        )
        parent = parents[0]
        action = _future_action_for(
            parent,
            owner_entity_id=None if owner_entity_id is None else owner_entity_id.value,
        )
        if action is None:
            continue
        mass = _quantize_mass(parent.support * policy.future_discount)
        if mass <= 0.0:
            continue
        atoms = (_atom(MindSlot.ACTION, action),)
        parent_id = parent.hypothesis_id(model.owner_id)
        existing = next(
            (
                item
                for item in derived.values()
                if item.subject_id == subject and item.atoms == atoms
            ),
            None,
        )
        for key, item in list(derived.items()):
            if item.subject_id == subject and item is not existing:
                del derived[key]
        if existing is None:
            existing = _Acc(
                subject_id=subject,
                aspect=MindAspect.FUTURE_ACTION,
                atoms=atoms,
                support=0.0,
                counter=0.0,
                evidence_ids=[],
                counter_evidence_ids=[],
                channel=MindEvidenceChannel.DERIVED,
                history=[],
                prior=policy.prior,
            )
        existing.support = mass
        existing.channel = MindEvidenceChannel.DERIVED
        hypothesis_id = existing.hypothesis_id(model.owner_id)
        _append_limited(existing.evidence_ids, parent_id, policy.max_history)
        _append_history(
            existing,
            MindUpdateRecord(
                tick=tick,
                hypothesis_id=hypothesis_id,
                support_delta=mass,
                counter_delta=0.0,
                channel=MindEvidenceChannel.DERIVED,
                reason=MindUpdateReason.DERIVE,
                parent_hypothesis_id=parent_id,
            ),
            policy.max_history,
        )
        derived[hypothesis_id] = existing
    merged = {**store, **derived}
    _evict(merged, policy.max_hypotheses)
    hypotheses = tuple(
        _freeze(model.owner_id, item)
        for _, item in sorted(merged.items(), key=lambda pair: pair[0])
    )
    return TheoryOfMind(
        owner_id=model.owner_id,
        hypotheses=hypotheses,
        cue_cursor=model.cue_cursor,
        last_tick=tick if tick is not None else model.last_tick,
    )


def update_theory_of_mind(
    model: TheoryOfMind,
    cues: Sequence[MindCue],
    policy: TheoryOfMindPolicy,
    *,
    owner_entity_id: EntityId | None = None,
) -> TheoryOfMind:
    """Apply support, counters, and one derived future action per subject."""
    if type(model) is not TheoryOfMind:
        raise _fail("model", "invalid_type")
    if type(policy) is not TheoryOfMindPolicy:
        raise _fail("policy", "invalid_type")
    if owner_entity_id is not None and type(owner_entity_id) is not EntityId:
        raise _fail("owner_entity_id", "invalid_type")
    if isinstance(cues, (str, bytes)) or not isinstance(cues, Sequence):
        raise _fail("cues", "invalid_type")
    store = {item.hypothesis_id: _acc_from(item) for item in model.hypotheses}
    cursor = list(model.cue_cursor)
    seen = set(cursor)
    created = 0
    updated = 0
    dropped = 0
    last_tick = model.last_tick
    for cue in cues:
        if type(cue) is not MindCue:
            raise _fail("cues", "invalid_type")
        if cue.owner_id != model.owner_id:
            _LOG.error(
                "theory_of_mind_owner_mismatch owner_id=%s reason_code=owner_mismatch",
                model.owner_id.value,
            )
            raise _fail("owner_id", "owner_mismatch")
        last_tick = cue.tick
        if cue.reason is MindUpdateReason.DROP or cue.drop_code is not None:
            dropped += 1
            _LOG.warning(
                "theory_of_mind_cue_dropped reason_code=%s",
                cue.drop_code or cue.reason.value,
            )
            continue
        if cue.evidence_id in seen and cue.reason is MindUpdateReason.SUPPORT:
            continue
        if cue.subject_id is None or cue.aspect is None or not cue.atoms:
            dropped += 1
            _LOG.warning(
                "theory_of_mind_cue_dropped reason_code=%s",
                "ambiguous_utterance",
            )
            continue
        acc = next(
            (
                item
                for item in store.values()
                if item.subject_id == cue.subject_id
                and item.aspect is cue.aspect
                and item.atoms == cue.atoms
            ),
            None,
        )
        fresh = acc is None
        if acc is None:
            acc = _Acc(
                subject_id=cue.subject_id,
                aspect=cue.aspect,
                atoms=cue.atoms,
                support=0.0,
                counter=0.0,
                evidence_ids=[],
                counter_evidence_ids=[],
                channel=cue.channel,
                history=[],
                prior=policy.prior,
            )
        hypothesis_id = acc.hypothesis_id(model.owner_id)
        if cue.reason is MindUpdateReason.COUNTER:
            if fresh:
                continue
            if cue.evidence_id in acc.counter_evidence_ids:
                continue
            acc.counter = _quantize_mass(acc.counter + cue.counter_weight)
            _append_limited(
                acc.counter_evidence_ids, cue.evidence_id, policy.max_history
            )
            delta_support = 0.0
            delta_counter = cue.counter_weight
        else:
            if cue.evidence_id in acc.evidence_ids:
                continue
            acc.support = _quantize_mass(acc.support + cue.support_weight)
            acc.channel = cue.channel
            _append_limited(acc.evidence_ids, cue.evidence_id, policy.max_history)
            delta_support = cue.support_weight
            delta_counter = 0.0
        _append_history(
            acc,
            MindUpdateRecord(
                tick=cue.tick,
                hypothesis_id=hypothesis_id,
                support_delta=delta_support,
                counter_delta=delta_counter,
                channel=cue.channel,
                reason=cue.reason,
            ),
            policy.max_history,
        )
        if fresh:
            created += 1
        else:
            updated += 1
        store[hypothesis_id] = acc
        if cue.evidence_id not in seen:
            cursor.append(cue.evidence_id)
            seen.add(cue.evidence_id)
        confidence = confidence_from_masses(acc.support, acc.counter, prior=acc.prior)
        _LOG.debug(
            "theory_of_mind_update owner_id=%s tick=%s hypothesis_id=%s aspect=%s "
            "channel=%s reason_code=%s atom_count=%s confidence=%s",
            model.owner_id.value,
            cue.tick,
            hypothesis_id,
            cue.aspect.value,
            cue.channel.value,
            cue.reason.value,
            len(cue.atoms),
            confidence,
        )
    overflow = len(cursor) - policy.max_history
    if overflow > 0:
        del cursor[:overflow]
    dropped += _evict(store, policy.max_hypotheses)
    hypotheses = tuple(
        _freeze(model.owner_id, item)
        for _, item in sorted(store.items(), key=lambda pair: pair[0])
    )
    updated_model = TheoryOfMind(
        owner_id=model.owner_id,
        hypotheses=hypotheses,
        cue_cursor=tuple(cursor),
        last_tick=last_tick,
    )
    derived = derive_future_actions(
        updated_model,
        policy,
        tick=last_tick or 0,
        owner_entity_id=owner_entity_id,
    )
    _LOG.info(
        "theory_of_mind_updated cue_count=%s created_count=%s updated_count=%s "
        "dropped_count=%s",
        len(cues),
        created,
        updated,
        dropped,
    )
    return derived


_NEED_TO_CONCEPT: Final[dict[str, str]] = {
    "hunger": "food",
    "thirst": "water",
    "fatigue": "rest",
    "safety": "danger",
}
_COOPERATIVE_ACTIONS: Final[frozenset[str]] = frozenset(
    {"help", "give", "talk", "ask", "tell"}
)


@dataclass(frozen=True, slots=True)
class MindMessageHint:
    """Recipient and concept copied from an above-threshold hypothesis."""

    preferred_recipient_id: str | None = None
    excluded_front_id: str | None = None
    concept: str | None = None
    confidence: float = 0.0
    hypothesis_id: str = ""
    aspect: str = ""


def _ranked_actionable(
    model: TheoryOfMind, policy: TheoryOfMindPolicy
) -> list[MindHypothesis]:
    ranked = [
        item for item in model.hypotheses if item.confidence >= policy.action_threshold
    ]
    preferred = set(model.preferred_ids)
    ranked.sort(key=lambda item: item.hypothesis_id)
    ranked.sort(key=lambda item: aspect_rank(item.aspect))
    ranked.sort(key=lambda item: item.confidence, reverse=True)
    if preferred and not model.selection_fallback_used:
        ranked.sort(key=lambda item: item.hypothesis_id not in preferred)
    return ranked


def _matches_candidate(
    hypothesis: MindHypothesis,
    candidates: Sequence[tuple[str, str, str | None]],
) -> bool:
    subject = hypothesis.subject_id.value
    if any(target == subject for _, _, target in candidates if target):
        return True
    if hypothesis.aspect is not MindAspect.GOAL:
        return False
    location = _slot_value(hypothesis.atoms, MindSlot.LOCATION)
    return bool(
        location
        and any(
            direction == "move" and target == location
            for _, direction, target in candidates
        )
    )


def _preferred_direction(
    hypothesis: MindHypothesis,
    *,
    visible_destinations: frozenset[str],
    visible_entities: frozenset[str],
) -> tuple[str, str | None] | None:
    subject = hypothesis.subject_id.value
    if hypothesis.aspect is MindAspect.NEED:
        return ("help", subject)
    if hypothesis.aspect is MindAspect.GOAL:
        if _slot_value(hypothesis.atoms, MindSlot.OUTCOME) != "reach_place":
            return None
        location = _slot_value(hypothesis.atoms, MindSlot.LOCATION)
        if location is not None and location in visible_destinations:
            return ("move", location)
        return ("help", subject)
    action = _slot_value(hypothesis.atoms, MindSlot.ACTION)
    if hypothesis.aspect in {MindAspect.FUTURE_ACTION, MindAspect.INTENTION}:
        if action == "attack":
            return ("flee", None)
        return None
    if hypothesis.aspect is MindAspect.EMOTION:
        if (
            _slot_value(hypothesis.atoms, MindSlot.EMOTION_KIND) == "anger"
            and subject in visible_entities
        ):
            return ("flee", None)
    return None


def mind_direction_deltas(
    model: object,
    *,
    candidates: Sequence[tuple[str, str, str | None]],
    visible_destinations: frozenset[str],
    visible_entities: frozenset[str],
    policy: TheoryOfMindPolicy | None = None,
) -> tuple[tuple[tuple[str, float], ...], str, str, float]:
    """One bias for the best matching hypothesis, keyed by candidate id.

    The fourth and fifth return values are direction and confidence. Status is
    ``skipped`` when the model is absent and ``none`` when nothing matches.
    """
    if model is None:
        return (), "skipped", "", 0.0, "", ""
    if type(model) is not TheoryOfMind:
        raise _fail("theory_of_mind", "invalid_type")
    if isinstance(candidates, (str, bytes)) or not isinstance(candidates, Sequence):
        raise _fail("candidates", "invalid_type")
    active = policy if policy is not None else default_theory_of_mind_policy()
    if type(active) is not TheoryOfMindPolicy:
        raise _fail("policy", "invalid_type")
    winner = next(
        (
            item
            for item in _ranked_actionable(model, active)
            if _matches_candidate(item, candidates)
            and _preferred_direction(
                item,
                visible_destinations=visible_destinations,
                visible_entities=visible_entities,
            )
            is not None
        ),
        None,
    )
    if winner is None:
        return (), "none", "", 0.0, "", ""
    preferred = _preferred_direction(
        winner,
        visible_destinations=visible_destinations,
        visible_entities=visible_entities,
    )
    assert preferred is not None
    direction, required_target = preferred
    deltas: list[tuple[str, float]] = []
    for candidate_id, candidate_direction, target in candidates:
        delta = 0.0
        if (
            direction == "help"
            and candidate_direction == "help"
            and target == required_target
        ):
            delta = winner.confidence
        elif (
            direction == "move"
            and candidate_direction == "move"
            and target == required_target
        ):
            delta = winner.confidence
        elif direction == "flee" and candidate_direction == "flee":
            delta = winner.confidence
        elif direction == "flee" and candidate_direction == "attack":
            delta = -winner.confidence
        if delta != 0.0:
            deltas.append((candidate_id, _quantize_mass(delta)))
    return (
        tuple(deltas),
        "applied",
        direction,
        winner.confidence,
        winner.hypothesis_id,
        winner.aspect.value,
    )


def mind_message_hint(
    model: object,
    *,
    recipient_ids: Sequence[str],
    policy: TheoryOfMindPolicy | None = None,
) -> MindMessageHint | None:
    """Preferred recipient, a third party to move off the front, and one concept."""
    if model is None:
        return None
    if type(model) is not TheoryOfMind:
        raise _fail("theory_of_mind", "invalid_type")
    if isinstance(recipient_ids, (str, bytes)) or not isinstance(
        recipient_ids, Sequence
    ):
        raise _fail("recipient_ids", "invalid_type")
    active = policy if policy is not None else default_theory_of_mind_policy()
    if type(active) is not TheoryOfMindPolicy:
        raise _fail("policy", "invalid_type")
    known = set(recipient_ids)
    winner = next(
        (
            item
            for item in _ranked_actionable(model, active)
            if item.subject_id.value in known
        ),
        None,
    )
    if winner is None:
        return None
    concept = _slot_value(winner.atoms, MindSlot.CONCEPT)
    if concept not in _NEED_TO_CONCEPT.values():
        concept = None
    excluded = next(
        (
            _slot_value(item.atoms, MindSlot.TARGET)
            for item in _ranked_actionable(model, active)
            if item.aspect is MindAspect.RELATIONSHIP
            and _slot_value(item.atoms, MindSlot.DIMENSION) == "trust"
            and _slot_value(item.atoms, MindSlot.POLARITY) == "negative"
            and _slot_value(item.atoms, MindSlot.TARGET)
            not in {None, winner.subject_id.value}
        ),
        None,
    )
    return MindMessageHint(
        preferred_recipient_id=winner.subject_id.value,
        excluded_front_id=excluded,
        concept=concept,
        confidence=winner.confidence,
        hypothesis_id=winner.hypothesis_id,
        aspect=winner.aspect.value,
    )


def mind_imagination_deltas(
    model: object,
    *,
    direction: str,
    target_id: str | None,
    policy: TheoryOfMindPolicy | None = None,
) -> tuple[float, float, str, str]:
    """Physical-harm and belonging deltas from a matching future action."""
    if model is None or target_id is None:
        return 0.0, 0.0, "", ""
    if type(model) is not TheoryOfMind:
        raise _fail("theory_of_mind", "invalid_type")
    active = policy if policy is not None else default_theory_of_mind_policy()
    if type(active) is not TheoryOfMindPolicy:
        raise _fail("policy", "invalid_type")
    harm = 0.0
    belonging = 0.0
    hypothesis_id = ""
    action_atom = ""
    for item in model.hypotheses:
        if item.aspect is not MindAspect.FUTURE_ACTION:
            continue
        if item.confidence < active.action_threshold:
            continue
        if item.subject_id.value != target_id:
            continue
        action = _slot_value(item.atoms, MindSlot.ACTION) or ""
        if direction == "move" and action == "attack" and item.confidence >= harm:
            harm = item.confidence
            hypothesis_id = item.hypothesis_id
            action_atom = action
        if (
            direction == "communicate"
            and action in _COOPERATIVE_ACTIONS
            and item.confidence >= belonging
        ):
            belonging = item.confidence
            hypothesis_id = item.hypothesis_id
            action_atom = action
    return harm, belonging, hypothesis_id, action_atom


@dataclass(frozen=True, slots=True)
class MindHypothesisSnapshot:
    """Bounded audit row. Canonical atom tokens, no utterance text."""

    hypothesis_id: str
    subject_id: str
    aspect: str
    atom_tokens: tuple[str, ...]
    channel: str
    confidence: float

    def __post_init__(self) -> None:
        require_stable_id("hypothesis_id", self.hypothesis_id)
        require_stable_id("subject_id", self.subject_id)
        if self.aspect not in {item.value for item in MindAspect}:
            raise _fail("aspect", "unknown_enum")
        if self.channel not in {item.value for item in MindEvidenceChannel}:
            raise _fail("channel", "unknown_enum")
        tokens = tuple(self.atom_tokens)
        if isinstance(self.atom_tokens, (str, bytes)) or not isinstance(
            self.atom_tokens, tuple
        ):
            raise _fail("atom_tokens", "invalid_type")
        object.__setattr__(self, "atom_tokens", tokens)
        object.__setattr__(
            self, "confidence", _unit_like("confidence", self.confidence)
        )


def _unit_like(field_name: str, value: float) -> float:
    number = _quantize_mass(value)
    if number < 0.0 or number > 1.0:
        raise _fail(field_name, "out_of_bounds")
    return number


@dataclass(frozen=True, slots=True)
class MindAudit:
    """In-run audit. Not written by runner-result serialization."""

    owner_id: AgentId
    tick: int
    mode: str
    hypothesis_count: int
    update_count: int
    max_confidence: float
    fallback_used: bool
    snapshots: tuple[MindHypothesisSnapshot, ...] = ()

    def __post_init__(self) -> None:
        if type(self.owner_id) is not AgentId:
            raise _fail("owner_id", "invalid_type")
        try:
            tick = require_exact_nonneg_int("tick", self.tick)
        except ValueError as exc:
            raise _fail("tick", "not_positive") from exc
        object.__setattr__(self, "tick", tick)
        if self.mode != "enabled":
            raise _fail("mode", "invalid_mode")
        if type(self.fallback_used) is not bool:
            raise _fail("fallback_used", "invalid_type")
        object.__setattr__(
            self, "max_confidence", _unit_like("max_confidence", self.max_confidence)
        )
        if isinstance(self.snapshots, (set, frozenset, str)):
            raise _fail("snapshots", "not_ordered")
        snapshots = tuple(self.snapshots)
        for item in snapshots:
            if type(item) is not MindHypothesisSnapshot:
                raise _fail("snapshots", "invalid_type")
        object.__setattr__(self, "snapshots", snapshots)


def build_mind_audit(model: TheoryOfMind) -> MindAudit:
    """Snapshot the committed model. Omits evidence payloads."""
    if type(model) is not TheoryOfMind:
        raise _fail("model", "invalid_type")
    snapshots = tuple(
        MindHypothesisSnapshot(
            hypothesis_id=item.hypothesis_id,
            subject_id=item.subject_id.value,
            aspect=item.aspect.value,
            atom_tokens=tuple(mind_canonical_atom_key(item.atoms).split("|")),
            channel=item.channel.value,
            confidence=item.confidence,
        )
        for item in model.hypotheses
    )
    peak = max((item.confidence for item in model.hypotheses), default=0.0)
    updates = sum(len(item.update_history) for item in model.hypotheses)
    return MindAudit(
        owner_id=model.owner_id,
        tick=0 if model.last_tick is None else model.last_tick,
        mode="enabled",
        hypothesis_count=len(model.hypotheses),
        update_count=updates,
        max_confidence=peak,
        fallback_used=model.selection_fallback_used,
        snapshots=snapshots,
    )
