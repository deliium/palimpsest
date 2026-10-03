"""Owner-scoped habitual convention beliefs.

A ledger is a private habit of the form "we usually do X in situation Y."
It is not a world rule, a semantic belief, a norm belief, or an analysis label.
Updates read one owner's observation, previous ledger, identity projection, and
already-loaded memories (reinforce-only). They do not read world authority,
another owner's ledger, or a metric document.
"""

from __future__ import annotations

import hashlib
import logging
import math
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum
from typing import Final

from agents.cognition.models import ActionDirection, OwnerSafeSocialIdentity
from agents.models import AgentId
from world.identifiers import EntityId, require_exact_nonneg_int
from world.observations import Observation, ObservedCommunication, ObservedOccurrence
from world.values import DayPhase, ResourceKind

_LOG: Final[logging.Logger] = logging.getLogger("agents.cognition.social_conventions")

SOCIAL_CONVENTION_POLICY_VERSION: Final[str] = "social-conventions.v1"
_QUANTUM: Final[Decimal] = Decimal("0.000001")
_ACTIVE_STRENGTH: Final[float] = 0.40
_RETIRE_STRENGTH: Final[float] = 0.20
_DECAY: Final[float] = 0.05
_CONFORMING_MEETING: Final[float] = 0.12
_CONFORMING_GATHERING: Final[float] = 0.15
_CONFORMING_GREETING: Final[float] = 0.12
_CONFORMING_EXCHANGE: Final[float] = 0.15
_CONFORMING_COLLECTIVE: Final[float] = 0.15
_TRANSMISSION_DELTA: Final[float] = 0.10
_REMEMBERED_DELTA: Final[float] = 0.08
_PENALTY: Final[float] = 0.30
_PROMOTION_COUNT: Final[int] = 3
_EXPLANATION_FADE_TICKS: Final[int] = 8
_UTTERANCE_INTERVAL: Final[int] = 4
_MAX_BELIEFS: Final[int] = 8
_MAX_EVIDENCE: Final[int] = 32
_MAX_PARTICIPANTS: Final[int] = 8
_MAX_VARIANTS: Final[int] = 4
_HEX: Final[frozenset[str]] = frozenset("0123456789abcdef")
_UNREFERENCED: Final[str] = "unreferenced"
_USUAL_ACTIONS: Final[frozenset[str]] = frozenset(
    {
        "wait",
        "talk",
        "ask",
        "tell",
        "give",
        "sleep",
        "eat",
        "drink",
        "move",
        "search",
        "flee",
        "help",
        "attack",
    }
)
_NOTICE_REASONS: Final[frozenset[str]] = frozenset(
    {
        "cap_exceeded",
        "ignored_kind",
        "unresolved_entity",
        "no_candidate",
        "candidate_only",
        "utterance_interval",
        "below_count",
        "below_strength",
        "memory_no_match",
    }
)
_FORBIDDEN_TYPES: Final[frozenset[str]] = frozenset(
    {"WorldState", "WorldEvent", "PhysicalRules", "AgentBody", "MetricDocument"}
)


class ConventionSituation(StrEnum):
    """Closed situation shapes. These are detectors, not tradition scripts."""

    COLOCATED_MEETING = "colocated_meeting"
    TIMED_GATHERING = "timed_gathering"
    GREETING_EXCHANGE = "greeting_exchange"
    HABITUAL_EXCHANGE = "habitual_exchange"
    COLLECTIVE_ACTION = "collective_action"


class ConventionExplanation(StrEnum):
    """Closed remembered explanation for why a habit formed."""

    RESOURCE_ACCESS = "resource_access"
    FATIGUE_REST = "fatigue_rest"
    COORDINATION = "coordination"
    HUNGER_RELIEF = "hunger_relief"
    SOCIAL_CONTACT = "social_contact"
    UNKNOWN = "unknown"
    FORGOTTEN = "forgotten"


class ConventionTransmission(StrEnum):
    """Closed transmission provenance on a belief (not evidence channel)."""

    OBSERVED = "observed"
    COMMUNICATED = "communicated"
    BOTH = "both"


class ConventionEvidenceChannel(StrEnum):
    """Closed evidence channel for one ledger item."""

    OBSERVED = "observed"
    COMMUNICATED = "communicated"
    REMEMBERED = "remembered"


class ConventionConceptualization(StrEnum):
    """Closed agent-side conceptualization token."""

    NONE = "none"
    NAMED_USUAL = "named_usual"
    NAMED_CUSTOM = "named_custom"


class ConventionStatus(StrEnum):
    """Closed lifecycle for one owner's habit belief."""

    CANDIDATE = "candidate"
    ACTIVE = "active"
    RETIRED = "retired"


class ConventionCounterpartClass(StrEnum):
    """Closed counterpart scoping for habit content."""

    NONE = "none"
    SPECIFIC_AGENT = "specific_agent"
    ANY_PRESENT = "any_present"


def _fail(field_name: str, code: str) -> ValueError:
    _LOG.error(
        "convention_validation_failed field=%s reason_code=%s",
        field_name,
        code,
    )
    return ValueError(f"{field_name}: {code}")


def _sha256_hex(material: str) -> str:
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _quantize(value: float) -> float:
    steps = round(value / 1e-6)
    quantized = float(Decimal(steps) * _QUANTUM)
    return 0.0 if quantized == 0.0 else quantized


def _apply_delta(current: float, delta: float) -> float:
    total = (Decimal(str(current)) + Decimal(str(delta))).quantize(
        _QUANTUM, rounding=ROUND_HALF_UP
    )
    number = float(total)
    if number < 0.0:
        return 0.0
    if number > 1.0:
        return 1.0
    return 0.0 if number == 0.0 else number


def _finite(field_name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _fail(field_name, "not_finite")
    number = float(value)
    if not math.isfinite(number):
        raise _fail(field_name, "not_finite")
    return number


def _locked_float(field_name: str, value: object, expected: float) -> float:
    number = _finite(field_name, value)
    if _quantize(number) != _quantize(expected):
        raise _fail(field_name, "unsupported_policy")
    return _quantize(expected)


def _locked_int(field_name: str, value: object, expected: int) -> int:
    if isinstance(value, bool) or type(value) is not int:
        raise _fail(field_name, "invalid_type")
    if value != expected:
        raise _fail(field_name, "unsupported_policy")
    return value


def _require_hex_id(field_name: str, value: object) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(char not in _HEX for char in value)
    ):
        raise _fail(field_name, "invalid_id")
    return value


def _require_tuple(field_name: str, values: object) -> tuple[object, ...]:
    if isinstance(values, (str, bytes, set, frozenset)) or not isinstance(
        values, Sequence
    ):
        raise _fail(field_name, "invalid_type")
    return tuple(values)


def _sign(before: float, after: float) -> str:
    if after > before:
        return "positive"
    if after < before:
        return "negative"
    return "zero"


def convention_content_key(content: ConventionContent) -> str:
    """Canonical content key used inside belief ids."""
    if type(content) is not ConventionContent:
        raise _fail("content", "invalid_type")
    location = "-" if content.location_id is None else content.location_id.value
    phase = "-" if content.day_phase is None else content.day_phase.value
    counterpart = (
        "-" if content.counterpart_id is None else content.counterpart_id.value
    )
    return "|".join(
        (
            content.situation.value,
            content.usual_action,
            location,
            phase,
            content.counterpart_class.value,
            counterpart,
        )
    )


def convention_belief_id(owner_id: AgentId, content: ConventionContent) -> str:
    """sha256 of owner id and the canonical content key."""
    if type(owner_id) is not AgentId:
        raise _fail("owner_id", "invalid_type")
    return _sha256_hex(f"{owner_id.value}|{convention_content_key(content)}")


def convention_evidence_id(
    belief_id: str,
    ordinal: int,
    channel: ConventionEvidenceChannel,
    lineage_ref: str,
) -> str:
    """sha256 of belief id, ordinal, channel, and lineage ref."""
    head = _require_hex_id("belief_id", belief_id)
    if isinstance(ordinal, bool) or type(ordinal) is not int or ordinal < 0:
        raise _fail("ordinal", "invalid_type")
    if type(channel) is not ConventionEvidenceChannel:
        raise _fail("channel", "unknown_channel")
    if not isinstance(lineage_ref, str) or not lineage_ref:
        raise _fail("lineage_ref", "invalid_type")
    return _sha256_hex(f"{head}|{ordinal}|{channel.value}|{lineage_ref}")


def _reject_forbidden(value: object) -> None:
    if value is None or isinstance(value, (str, int, float, bool)):
        return
    name = type(value).__name__
    module = type(value).__module__
    if (
        name in _FORBIDDEN_TYPES
        or module.startswith("analysis")
        or module.startswith("analysis.")
    ):
        raise TypeError(f"{name}: forbidden_input")


@dataclass(frozen=True, slots=True)
class ConventionContent:
    """Situation plus usual action. Competing variants differ in usual_action."""

    situation: ConventionSituation
    usual_action: str
    location_id: EntityId | None = None
    day_phase: DayPhase | None = None
    counterpart_class: ConventionCounterpartClass = ConventionCounterpartClass.NONE
    counterpart_id: AgentId | None = None

    def __post_init__(self) -> None:
        if type(self.situation) is not ConventionSituation:
            raise _fail("content.situation", "unknown_situation")
        if (
            not isinstance(self.usual_action, str)
            or self.usual_action not in _USUAL_ACTIONS
        ):
            raise _fail("content.usual_action", "unknown_action")
        if self.location_id is not None and type(self.location_id) is not EntityId:
            raise _fail("content.location_id", "invalid_type")
        if self.day_phase is not None and type(self.day_phase) is not DayPhase:
            raise _fail("content.day_phase", "invalid_type")
        if type(self.counterpart_class) is not ConventionCounterpartClass:
            raise _fail("content.counterpart_class", "unknown_counterpart_class")
        if self.counterpart_id is not None and type(self.counterpart_id) is not AgentId:
            raise _fail("content.counterpart_id", "invalid_type")
        if (
            self.counterpart_class is ConventionCounterpartClass.SPECIFIC_AGENT
            and self.counterpart_id is None
        ):
            raise _fail("content.counterpart_id", "missing_counterpart")
        if (
            self.counterpart_class is not ConventionCounterpartClass.SPECIFIC_AGENT
            and self.counterpart_id is not None
        ):
            raise _fail("content.counterpart_id", "unexpected_counterpart")
        if (
            self.situation is ConventionSituation.TIMED_GATHERING
            and self.day_phase is None
        ):
            raise _fail("content.day_phase", "missing_day_phase")
        if (
            self.situation is ConventionSituation.COLOCATED_MEETING
            and self.day_phase is not None
        ):
            raise _fail("content.day_phase", "unexpected_day_phase")


@dataclass(frozen=True, slots=True)
class ConventionEvidenceItem:
    """One observed, communicated, or remembered item on a belief."""

    evidence_id: str
    ordinal: int
    channel: ConventionEvidenceChannel
    lineage_ref: str
    tick: int
    actor_id: AgentId | None = None
    predicate: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "evidence_id", _require_hex_id("evidence_id", self.evidence_id)
        )
        if isinstance(self.ordinal, bool) or type(self.ordinal) is not int:
            raise _fail("evidence.ordinal", "invalid_type")
        if self.ordinal < 0:
            raise _fail("evidence.ordinal", "out_of_range")
        if type(self.channel) is not ConventionEvidenceChannel:
            raise _fail("evidence.channel", "unknown_channel")
        if not isinstance(self.lineage_ref, str) or not self.lineage_ref:
            raise _fail("evidence.lineage_ref", "invalid_type")
        object.__setattr__(
            self,
            "tick",
            require_exact_nonneg_int("ConventionEvidenceItem.tick", self.tick),
        )
        if self.actor_id is not None and type(self.actor_id) is not AgentId:
            raise _fail("evidence.actor_id", "invalid_type")
        if self.predicate is not None:
            if not isinstance(self.predicate, str) or self.predicate not in {
                "usually",
                "greet",
                "custom",
            }:
                raise _fail("evidence.predicate", "unknown_predicate")


@dataclass(frozen=True, slots=True)
class ConventionUtterancePlan:
    """Relation recipe the planner may place on an existing talk future."""

    situation: ConventionSituation
    predicate: str
    subject: str
    object: str
    source_basis: str = _UNREFERENCED

    def __post_init__(self) -> None:
        if type(self.situation) is not ConventionSituation:
            raise _fail("utterance.situation", "unknown_situation")
        if self.predicate not in {"usually", "custom"}:
            raise _fail("utterance.predicate", "unknown_predicate")
        if self.subject != self.situation.value:
            raise _fail("utterance.subject", "situation_mismatch")
        if not isinstance(self.object, str) or self.object not in _USUAL_ACTIONS:
            raise _fail("utterance.object", "unknown_action")
        if self.source_basis != _UNREFERENCED:
            raise _fail("utterance.source_basis", "unsupported_basis")


@dataclass(frozen=True, slots=True)
class ConventionBelief:
    """One owner's habit belief. It is not a semantic belief or norm belief."""

    belief_id: str
    owner_id: AgentId
    content: ConventionContent
    status: ConventionStatus
    strength: float
    repetition_count: int = 0
    participant_ids: tuple[AgentId, ...] = ()
    first_tick: int | None = None
    last_tick: int | None = None
    transmission: ConventionTransmission = ConventionTransmission.OBSERVED
    remembered_explanation: ConventionExplanation = ConventionExplanation.UNKNOWN
    competing_variant_ids: tuple[str, ...] = ()
    conceptualization: ConventionConceptualization = ConventionConceptualization.NONE
    evidence: tuple[ConventionEvidenceItem, ...] = ()
    last_utterance_tick: int | None = None
    explanation_cue_absent_ticks: int = 0
    notices: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "belief_id", _require_hex_id("belief_id", self.belief_id)
        )
        if type(self.owner_id) is not AgentId:
            raise _fail("owner_id", "invalid_type")
        if type(self.content) is not ConventionContent:
            raise _fail("content", "invalid_type")
        if type(self.status) is not ConventionStatus:
            raise _fail("status", "unknown_status")
        if type(self.transmission) is not ConventionTransmission:
            raise _fail("transmission", "unknown_transmission")
        if type(self.remembered_explanation) is not ConventionExplanation:
            raise _fail("remembered_explanation", "unknown_explanation")
        if type(self.conceptualization) is not ConventionConceptualization:
            raise _fail("conceptualization", "unknown_conceptualization")
        strength = _finite("strength", self.strength)
        quantized = _quantize(strength)
        if quantized < 0.0 or quantized > 1.0:
            raise _fail("strength", "out_of_range")
        object.__setattr__(self, "strength", quantized)
        if isinstance(self.repetition_count, bool) or type(
            self.repetition_count
        ) is not int:
            raise _fail("repetition_count", "invalid_type")
        if self.repetition_count < 0:
            raise _fail("repetition_count", "out_of_range")
        if isinstance(self.explanation_cue_absent_ticks, bool) or type(
            self.explanation_cue_absent_ticks
        ) is not int:
            raise _fail("explanation_cue_absent_ticks", "invalid_type")
        if self.explanation_cue_absent_ticks < 0:
            raise _fail("explanation_cue_absent_ticks", "out_of_range")
        participants = _require_tuple("participant_ids", self.participant_ids)
        checked_participants: list[AgentId] = []
        seen_participants: set[str] = set()
        for agent in participants:
            if type(agent) is not AgentId:
                raise _fail("participant_ids", "invalid_type")
            if agent.value in seen_participants:
                raise _fail("participant_ids", "duplicate_participant")
            seen_participants.add(agent.value)
            checked_participants.append(agent)
        if len(checked_participants) > _MAX_PARTICIPANTS:
            raise _fail("participant_ids", "cap_exceeded")
        ordered_participants = tuple(
            sorted(checked_participants, key=lambda item: item.value)
        )
        if self.first_tick is not None:
            object.__setattr__(
                self,
                "first_tick",
                require_exact_nonneg_int(
                    "ConventionBelief.first_tick", self.first_tick
                ),
            )
        if self.last_tick is not None:
            object.__setattr__(
                self,
                "last_tick",
                require_exact_nonneg_int(
                    "ConventionBelief.last_tick", self.last_tick
                ),
            )
        if (
            self.first_tick is not None
            and self.last_tick is not None
            and self.last_tick < self.first_tick
        ):
            raise _fail("last_tick", "before_first_tick")
        variants = _require_tuple("competing_variant_ids", self.competing_variant_ids)
        checked_variants: list[str] = []
        seen_variants: set[str] = set()
        for item in variants:
            head = _require_hex_id("competing_variant_ids", item)
            if head == self.belief_id:
                raise _fail("competing_variant_ids", "self_variant")
            if head in seen_variants:
                raise _fail("competing_variant_ids", "duplicate_variant")
            seen_variants.add(head)
            checked_variants.append(head)
        if len(checked_variants) > _MAX_VARIANTS:
            raise _fail("competing_variant_ids", "cap_exceeded")
        evidence = _require_tuple("evidence", self.evidence)
        checked_evidence: list[ConventionEvidenceItem] = []
        seen_ids: set[str] = set()
        has_custom_lineage = False
        for item in evidence:
            if type(item) is not ConventionEvidenceItem:
                raise _fail("evidence", "invalid_type")
            if item.evidence_id in seen_ids:
                raise _fail("evidence", "duplicate_evidence")
            seen_ids.add(item.evidence_id)
            if (
                item.channel is ConventionEvidenceChannel.COMMUNICATED
                and item.predicate == "custom"
            ):
                has_custom_lineage = True
            checked_evidence.append(item)
        if len(checked_evidence) > _MAX_EVIDENCE:
            raise _fail("evidence", "cap_exceeded")
        if (
            self.conceptualization is ConventionConceptualization.NAMED_CUSTOM
            and not has_custom_lineage
        ):
            raise _fail("conceptualization", "custom_lineage_required")
        expected_id = convention_belief_id(self.owner_id, self.content)
        if self.belief_id != expected_id:
            raise _fail("belief_id", "id_mismatch")
        if self.last_utterance_tick is not None:
            object.__setattr__(
                self,
                "last_utterance_tick",
                require_exact_nonneg_int(
                    "ConventionBelief.last_utterance_tick", self.last_utterance_tick
                ),
            )
        notices = _require_tuple("notices", self.notices)
        checked_notices: list[str] = []
        for item in notices:
            if not isinstance(item, str) or item not in _NOTICE_REASONS:
                raise _fail("notices", "invalid_notice")
            if item not in checked_notices:
                checked_notices.append(item)
        object.__setattr__(self, "participant_ids", ordered_participants)
        object.__setattr__(self, "competing_variant_ids", tuple(checked_variants))
        object.__setattr__(self, "evidence", tuple(checked_evidence))
        object.__setattr__(self, "notices", tuple(checked_notices))


@dataclass(frozen=True, slots=True)
class ConventionLedger:
    """Private habits for one owner. ``None`` means the mode is off."""

    owner_id: AgentId
    beliefs: tuple[ConventionBelief, ...] = ()
    notices: tuple[str, ...] = ()
    utterance_plans: tuple[ConventionUtterancePlan, ...] = ()
    policy_version: str = SOCIAL_CONVENTION_POLICY_VERSION

    def __post_init__(self) -> None:
        if type(self.owner_id) is not AgentId:
            raise _fail("owner_id", "invalid_type")
        if self.policy_version != SOCIAL_CONVENTION_POLICY_VERSION:
            raise _fail("policy_version", "unsupported_policy")
        beliefs = _require_tuple("beliefs", self.beliefs)
        checked: list[ConventionBelief] = []
        seen: set[str] = set()
        for item in beliefs:
            if type(item) is not ConventionBelief:
                raise _fail("beliefs", "invalid_type")
            if item.owner_id != self.owner_id:
                raise _fail("beliefs.owner_id", "owner_mismatch")
            if item.belief_id in seen:
                raise _fail("beliefs", "duplicate_belief")
            seen.add(item.belief_id)
            checked.append(item)
        if len(checked) > _MAX_BELIEFS:
            raise _fail("beliefs", "cap_exceeded")
        notices = _require_tuple("notices", self.notices)
        checked_notices: list[str] = []
        for item in notices:
            if not isinstance(item, str) or item not in _NOTICE_REASONS:
                raise _fail("notices", "invalid_notice")
            if item not in checked_notices:
                checked_notices.append(item)
        plans = _require_tuple("utterance_plans", self.utterance_plans)
        for item in plans:
            if type(item) is not ConventionUtterancePlan:
                raise _fail("utterance_plans", "invalid_type")
        object.__setattr__(self, "beliefs", tuple(checked))
        object.__setattr__(self, "notices", tuple(checked_notices))
        object.__setattr__(self, "utterance_plans", tuple(plans))
        _LOG.debug(
            "convention_ledger_constructed owner_id=%s policy_version=%s "
            "belief_count=%s",
            self.owner_id.value,
            self.policy_version,
            len(self.beliefs),
        )


@dataclass(frozen=True, slots=True)
class SocialConventionPolicy:
    """Locked convention constants. Runner JSON does not carry these weights."""

    version: str = SOCIAL_CONVENTION_POLICY_VERSION
    active_strength: float = _ACTIVE_STRENGTH
    retire_strength: float = _RETIRE_STRENGTH
    decay: float = _DECAY
    conforming_colocated_meeting: float = _CONFORMING_MEETING
    conforming_timed_gathering: float = _CONFORMING_GATHERING
    conforming_greeting_exchange: float = _CONFORMING_GREETING
    conforming_habitual_exchange: float = _CONFORMING_EXCHANGE
    conforming_collective_action: float = _CONFORMING_COLLECTIVE
    transmission_delta: float = _TRANSMISSION_DELTA
    remembered_delta: float = _REMEMBERED_DELTA
    penalty: float = _PENALTY
    promotion_count: int = _PROMOTION_COUNT
    explanation_fade_ticks: int = _EXPLANATION_FADE_TICKS
    utterance_interval: int = _UTTERANCE_INTERVAL
    max_beliefs: int = _MAX_BELIEFS
    max_evidence: int = _MAX_EVIDENCE
    max_participants: int = _MAX_PARTICIPANTS
    max_variants: int = _MAX_VARIANTS

    def __post_init__(self) -> None:
        if self.version != SOCIAL_CONVENTION_POLICY_VERSION:
            raise _fail("version", "unsupported_policy")
        floats = (
            ("active_strength", _ACTIVE_STRENGTH),
            ("retire_strength", _RETIRE_STRENGTH),
            ("decay", _DECAY),
            ("conforming_colocated_meeting", _CONFORMING_MEETING),
            ("conforming_timed_gathering", _CONFORMING_GATHERING),
            ("conforming_greeting_exchange", _CONFORMING_GREETING),
            ("conforming_habitual_exchange", _CONFORMING_EXCHANGE),
            ("conforming_collective_action", _CONFORMING_COLLECTIVE),
            ("transmission_delta", _TRANSMISSION_DELTA),
            ("remembered_delta", _REMEMBERED_DELTA),
            ("penalty", _PENALTY),
        )
        for name, expected in floats:
            object.__setattr__(
                self, name, _locked_float(name, getattr(self, name), expected)
            )
        counts = (
            ("promotion_count", _PROMOTION_COUNT),
            ("explanation_fade_ticks", _EXPLANATION_FADE_TICKS),
            ("utterance_interval", _UTTERANCE_INTERVAL),
            ("max_beliefs", _MAX_BELIEFS),
            ("max_evidence", _MAX_EVIDENCE),
            ("max_participants", _MAX_PARTICIPANTS),
            ("max_variants", _MAX_VARIANTS),
        )
        for name, expected in counts:
            object.__setattr__(
                self, name, _locked_int(name, getattr(self, name), expected)
            )
        _LOG.debug(
            "convention_policy_constructed owner_id=%s policy_version=%s "
            "belief_count=%s",
            "-",
            self.version,
            0,
        )


def default_social_convention_policy() -> SocialConventionPolicy:
    """Return the only accepted social-convention policy."""
    return SocialConventionPolicy()


def empty_convention_ledger(owner_id: AgentId) -> ConventionLedger:
    """Ledger with no beliefs. Disabled mode does not call this."""
    return ConventionLedger(owner_id=owner_id)


def require_owner_social_conventions(
    ledger: object,
    owner_id: AgentId,
    *,
    field_name: str,
) -> None:
    """Reject a foreign or mistyped ledger. ``None`` is passthrough."""
    if ledger is None:
        return
    if type(owner_id) is not AgentId:
        raise _fail("owner_id", "invalid_type")
    if type(ledger) is not ConventionLedger:
        _LOG.warning(
            "convention_carry_rejected reason=%s",
            "invalid_type",
        )
        raise TypeError(f"{field_name} must be ConventionLedger")
    if ledger.owner_id != owner_id:
        _LOG.error(
            "convention_validation_failed field=%s reason_code=%s",
            field_name,
            "owner_mismatch",
        )
        _LOG.warning(
            "convention_carry_rejected reason=%s",
            "owner_mismatch",
        )
        raise ValueError(f"{field_name} owner_id mismatch")


@dataclass
class _BeliefDraft:
    content: ConventionContent
    strength: float
    status: ConventionStatus
    repetition_count: int
    participant_ids: list[AgentId]
    first_tick: int | None
    last_tick: int | None
    transmission: ConventionTransmission
    remembered_explanation: ConventionExplanation
    competing_variant_ids: list[str]
    conceptualization: ConventionConceptualization
    evidence: list[ConventionEvidenceItem]
    last_utterance_tick: int | None
    explanation_cue_absent_ticks: int
    notices: list[str] = field(default_factory=list)
    touched: bool = False
    cue_present: bool = False
    initial_others: int = 0


def _lineage(tick: int, ordinal: int, occurrence: ObservedOccurrence) -> str:
    event_id = occurrence.provenance.source_event_id
    if event_id is None:
        return f"tick-{tick}-{ordinal}"
    return event_id.value


def _comm_lineage(tick: int, ordinal: int, communication: ObservedCommunication) -> str:
    event_id = communication.provenance.source_event_id
    if event_id is None:
        return f"tick-{tick}-c{ordinal}"
    return event_id.value


def _resolve_agent(
    identity: OwnerSafeSocialIdentity, entity_id: EntityId | None
) -> AgentId | None:
    if type(entity_id) is not EntityId:
        return None
    if entity_id == identity.owner_entity_id:
        return identity.owner_id
    for binding in identity.counterparts:
        if binding.entity_id == entity_id:
            return binding.agent_id
    return None


def _notice(notices: list[str], reason: str) -> None:
    if reason not in notices:
        notices.append(reason)


def _log_drop(reason: str) -> None:
    _LOG.warning("convention_evidence_dropped reason=%s", reason)


def _situation_key(content: ConventionContent) -> str:
    location = "-" if content.location_id is None else content.location_id.value
    phase = "-" if content.day_phase is None else content.day_phase.value
    return f"{content.situation.value}|{location}|{phase}"


def _delta_for(
    situation: ConventionSituation, policy: SocialConventionPolicy
) -> float:
    if situation is ConventionSituation.COLOCATED_MEETING:
        return policy.conforming_colocated_meeting
    if situation is ConventionSituation.TIMED_GATHERING:
        return policy.conforming_timed_gathering
    if situation is ConventionSituation.GREETING_EXCHANGE:
        return policy.conforming_greeting_exchange
    if situation is ConventionSituation.HABITUAL_EXCHANGE:
        return policy.conforming_habitual_exchange
    return policy.conforming_collective_action


def _initial_explanation(
    content: ConventionContent,
    *,
    others_present: int,
    scarce: bool,
) -> ConventionExplanation:
    if content.situation in {
        ConventionSituation.COLOCATED_MEETING,
        ConventionSituation.TIMED_GATHERING,
    }:
        if others_present >= 2:
            return ConventionExplanation.COORDINATION
        return ConventionExplanation.SOCIAL_CONTACT
    if content.situation is ConventionSituation.GREETING_EXCHANGE:
        return ConventionExplanation.SOCIAL_CONTACT
    if content.situation is ConventionSituation.HABITUAL_EXCHANGE:
        if scarce:
            return ConventionExplanation.RESOURCE_ACCESS
        return ConventionExplanation.UNKNOWN
    if content.situation is ConventionSituation.COLLECTIVE_ACTION:
        if content.usual_action == "sleep":
            return ConventionExplanation.FATIGUE_REST
        if content.usual_action == "eat":
            return ConventionExplanation.HUNGER_RELIEF
    return ConventionExplanation.UNKNOWN


def _scarce(observation: Observation) -> bool:
    for resource in observation.resources:
        if resource.kind is ResourceKind.FOOD and resource.quantity <= 1.0:
            return True
    return False


def _drafts_from(
    previous: ConventionLedger | None, owner_id: AgentId
) -> list[_BeliefDraft]:
    drafts: list[_BeliefDraft] = []
    if previous is None:
        return drafts
    if previous.owner_id != owner_id:
        _LOG.error(
            "convention_validation_failed field=%s reason_code=%s",
            "owner_id",
            "owner_mismatch",
        )
        raise ValueError("owner_id: owner_mismatch")
    for belief in previous.beliefs:
        drafts.append(
            _BeliefDraft(
                content=belief.content,
                strength=belief.strength,
                status=belief.status,
                repetition_count=belief.repetition_count,
                participant_ids=list(belief.participant_ids),
                first_tick=belief.first_tick,
                last_tick=belief.last_tick,
                transmission=belief.transmission,
                remembered_explanation=belief.remembered_explanation,
                competing_variant_ids=list(belief.competing_variant_ids),
                conceptualization=belief.conceptualization,
                evidence=list(belief.evidence),
                last_utterance_tick=belief.last_utterance_tick,
                explanation_cue_absent_ticks=belief.explanation_cue_absent_ticks,
                notices=list(belief.notices),
            )
        )
    return drafts


def _find_draft(
    drafts: list[_BeliefDraft], content: ConventionContent
) -> _BeliefDraft | None:
    key = convention_content_key(content)
    for draft in drafts:
        if convention_content_key(draft.content) == key:
            return draft
    return None


def _merge_participants(
    draft: _BeliefDraft,
    participants: Sequence[AgentId],
    notices: list[str],
    policy: SocialConventionPolicy,
) -> None:
    seen = {agent.value for agent in draft.participant_ids}
    for agent in participants:
        if agent.value in seen:
            continue
        if len(draft.participant_ids) >= policy.max_participants:
            _notice(notices, "cap_exceeded")
            _log_drop("cap_exceeded")
            return
        draft.participant_ids.append(agent)
        seen.add(agent.value)


def _record_conforming(
    *,
    drafts: list[_BeliefDraft],
    notices: list[str],
    owner_id: AgentId,
    content: ConventionContent,
    delta: float,
    channel: ConventionEvidenceChannel,
    lineage_ref: str,
    tick: int,
    actor_id: AgentId | None,
    participants: Sequence[AgentId],
    policy: SocialConventionPolicy,
    seen: set[tuple[str, str, str]],
    others_present: int,
    scarce: bool,
    predicate: str | None = None,
    transmission: ConventionTransmission | None = None,
) -> None:
    dedup = (content.situation.value, content.usual_action, lineage_ref)
    if dedup in seen:
        return
    seen.add(dedup)
    draft = _find_draft(drafts, content)
    if draft is None:
        if len(drafts) >= policy.max_beliefs:
            _notice(notices, "cap_exceeded")
            _log_drop("cap_exceeded")
            return
        draft = _BeliefDraft(
            content=content,
            strength=0.0,
            status=ConventionStatus.CANDIDATE,
            repetition_count=0,
            participant_ids=[],
            first_tick=tick,
            last_tick=tick,
            transmission=transmission or ConventionTransmission.OBSERVED,
            remembered_explanation=_initial_explanation(
                content, others_present=others_present, scarce=scarce
            ),
            competing_variant_ids=[],
            conceptualization=ConventionConceptualization.NONE,
            evidence=[],
            last_utterance_tick=None,
            explanation_cue_absent_ticks=0,
            initial_others=others_present,
        )
        drafts.append(draft)
    if len(draft.evidence) >= policy.max_evidence:
        _notice(notices, "cap_exceeded")
        _log_drop("cap_exceeded")
        return
    before = draft.strength
    draft.strength = _apply_delta(before, delta)
    draft.repetition_count += 1
    if draft.first_tick is None:
        draft.first_tick = tick
    draft.last_tick = tick
    draft.touched = True
    draft.cue_present = True
    if transmission is not None:
        if (
            draft.transmission is ConventionTransmission.OBSERVED
            and transmission is ConventionTransmission.COMMUNICATED
        ):
            draft.transmission = ConventionTransmission.BOTH
        elif draft.transmission is ConventionTransmission.COMMUNICATED and (
            transmission is ConventionTransmission.OBSERVED
        ):
            draft.transmission = ConventionTransmission.BOTH
        elif draft.transmission is ConventionTransmission.OBSERVED:
            draft.transmission = transmission
    _merge_participants(draft, participants, notices, policy)
    belief_id = convention_belief_id(owner_id, draft.content)
    ordinal = len(draft.evidence)
    draft.evidence.append(
        ConventionEvidenceItem(
            evidence_id=convention_evidence_id(
                belief_id, ordinal, channel, lineage_ref
            ),
            ordinal=ordinal,
            channel=channel,
            lineage_ref=lineage_ref,
            tick=tick,
            actor_id=actor_id,
            predicate=predicate,
        )
    )
    if (
        draft.status is ConventionStatus.RETIRED
        and channel is ConventionEvidenceChannel.OBSERVED
    ):
        draft.status = ConventionStatus.CANDIDATE
    _LOG.debug(
        "convention_belief_applied owner_id=%s tick=%s sign=%s",
        owner_id.value,
        tick,
        _sign(before, draft.strength),
    )


def _present_agents(
    observation: Observation,
    identity: OwnerSafeSocialIdentity,
    notices: list[str],
) -> list[AgentId]:
    present: list[AgentId] = []
    seen: set[str] = set()
    if observation.self_body is not None:
        present.append(identity.owner_id)
        seen.add(identity.owner_id.value)
    for body in observation.visible_bodies:
        agent = _resolve_agent(identity, body.entity_id)
        if agent is None:
            _notice(notices, "unresolved_entity")
            _log_drop("unresolved_entity")
            continue
        if agent.value not in seen:
            present.append(agent)
            seen.add(agent.value)
    return present


def _apply_meeting_evidence(
    *,
    observation: Observation,
    identity: OwnerSafeSocialIdentity,
    drafts: list[_BeliefDraft],
    notices: list[str],
    policy: SocialConventionPolicy,
    seen: set[tuple[str, str, str]],
    scarce: bool,
) -> None:
    present = _present_agents(observation, identity, notices)
    if len(present) < 2:
        return
    location = (
        None if observation.self_body is None else observation.self_body.location_id
    )
    tick = observation.tick
    others = len(present) - 1
    for ordinal, occurrence in enumerate(observation.occurrences):
        if occurrence.kind not in {"wait", "talk"}:
            continue
        actor = _resolve_agent(identity, occurrence.actor_id)
        if actor is None:
            if occurrence.actor_id is not None:
                _notice(notices, "unresolved_entity")
                _log_drop("unresolved_entity")
            continue
        if actor.value not in {agent.value for agent in present}:
            continue
        if observation.day_phase is None:
            situation = ConventionSituation.COLOCATED_MEETING
            day_phase = None
        else:
            situation = ConventionSituation.TIMED_GATHERING
            day_phase = observation.day_phase
        if situation is ConventionSituation.TIMED_GATHERING:
            phase_mismatch = False
            for draft in drafts:
                if (
                    draft.content.situation is ConventionSituation.TIMED_GATHERING
                    and draft.content.usual_action == occurrence.kind
                    and draft.content.location_id == location
                    and draft.content.day_phase is not None
                    and draft.content.day_phase is not day_phase
                ):
                    phase_mismatch = True
                    break
            if phase_mismatch:
                continue
        content = ConventionContent(
            situation=situation,
            usual_action=occurrence.kind,
            location_id=location,
            day_phase=day_phase,
            counterpart_class=ConventionCounterpartClass.ANY_PRESENT,
        )
        _record_conforming(
            drafts=drafts,
            notices=notices,
            owner_id=identity.owner_id,
            content=content,
            delta=_delta_for(situation, policy),
            channel=ConventionEvidenceChannel.OBSERVED,
            lineage_ref=_lineage(tick, ordinal, occurrence),
            tick=tick,
            actor_id=actor,
            participants=present,
            policy=policy,
            seen=seen,
            others_present=others,
            scarce=scarce,
        )


def _apply_greeting_evidence(
    *,
    observation: Observation,
    identity: OwnerSafeSocialIdentity,
    drafts: list[_BeliefDraft],
    notices: list[str],
    policy: SocialConventionPolicy,
    seen: set[tuple[str, str, str]],
    scarce: bool,
) -> None:
    location = (
        None if observation.self_body is None else observation.self_body.location_id
    )
    tick = observation.tick
    for ordinal, communication in enumerate(observation.communications):
        if communication.action_kind not in {"talk", "ask", "tell"}:
            continue
        hop = communication.utterance.declared.hop_count
        if hop not in {0, 1}:
            continue
        relations = communication.utterance.content.relations
        if not any(relation.predicate == "greet" for relation in relations):
            continue
        speaker = _resolve_agent(identity, communication.speaker_id)
        listener = _resolve_agent(identity, communication.listener_id)
        if speaker is None or listener is None:
            _notice(notices, "unresolved_entity")
            _log_drop("unresolved_entity")
            continue
        content = ConventionContent(
            situation=ConventionSituation.GREETING_EXCHANGE,
            usual_action="talk",
            location_id=location,
            counterpart_class=ConventionCounterpartClass.ANY_PRESENT,
        )
        _record_conforming(
            drafts=drafts,
            notices=notices,
            owner_id=identity.owner_id,
            content=content,
            delta=policy.conforming_greeting_exchange,
            channel=ConventionEvidenceChannel.OBSERVED,
            lineage_ref=_comm_lineage(tick, ordinal, communication),
            tick=tick,
            actor_id=speaker,
            participants=(speaker, listener),
            policy=policy,
            seen=seen,
            others_present=1,
            scarce=scarce,
            predicate="greet",
        )


def _apply_give_evidence(
    *,
    observation: Observation,
    identity: OwnerSafeSocialIdentity,
    drafts: list[_BeliefDraft],
    notices: list[str],
    policy: SocialConventionPolicy,
    seen: set[tuple[str, str, str]],
    scarce: bool,
) -> None:
    location = (
        None if observation.self_body is None else observation.self_body.location_id
    )
    tick = observation.tick
    owner = identity.owner_id
    for ordinal, occurrence in enumerate(observation.occurrences):
        if occurrence.kind != "give":
            continue
        if occurrence.success is False:
            continue
        actor = _resolve_agent(identity, occurrence.actor_id)
        other = _resolve_agent(identity, occurrence.other_entity_id)
        if actor is None or other is None:
            if (
                occurrence.actor_id is not None
                or occurrence.other_entity_id is not None
            ):
                _notice(notices, "unresolved_entity")
                _log_drop("unresolved_entity")
            continue
        involved = owner in {actor, other}
        witnessed = observation.self_body is not None and len(
            observation.visible_bodies
        ) >= 0
        if not involved and not witnessed:
            continue
        if actor == owner:
            counterpart = other
        elif other == owner:
            counterpart = actor
        else:
            counterpart = other
        content = ConventionContent(
            situation=ConventionSituation.HABITUAL_EXCHANGE,
            usual_action="give",
            location_id=location,
            counterpart_class=ConventionCounterpartClass.SPECIFIC_AGENT,
            counterpart_id=counterpart,
        )
        _record_conforming(
            drafts=drafts,
            notices=notices,
            owner_id=owner,
            content=content,
            delta=policy.conforming_habitual_exchange,
            channel=ConventionEvidenceChannel.OBSERVED,
            lineage_ref=_lineage(tick, ordinal, occurrence),
            tick=tick,
            actor_id=actor,
            participants=(actor, other),
            policy=policy,
            seen=seen,
            others_present=1,
            scarce=scarce,
        )


def _apply_collective_evidence(
    *,
    observation: Observation,
    identity: OwnerSafeSocialIdentity,
    drafts: list[_BeliefDraft],
    notices: list[str],
    policy: SocialConventionPolicy,
    seen: set[tuple[str, str, str]],
    scarce: bool,
) -> None:
    location = (
        None if observation.self_body is None else observation.self_body.location_id
    )
    tick = observation.tick
    by_kind: dict[str, list[tuple[int, ObservedOccurrence, AgentId]]] = defaultdict(
        list
    )
    for ordinal, occurrence in enumerate(observation.occurrences):
        if occurrence.kind not in _USUAL_ACTIONS:
            if "ignored_kind" not in notices:
                _notice(notices, "ignored_kind")
                _log_drop("ignored_kind")
            continue
        actor = _resolve_agent(identity, occurrence.actor_id)
        if actor is None:
            if occurrence.actor_id is not None:
                _notice(notices, "unresolved_entity")
                _log_drop("unresolved_entity")
            continue
        by_kind[occurrence.kind].append((ordinal, occurrence, actor))
    for kind, items in by_kind.items():
        agents = []
        seen_agents: set[str] = set()
        for _, _, agent in items:
            if agent.value not in seen_agents:
                agents.append(agent)
                seen_agents.add(agent.value)
        if len(agents) < 2:
            continue
        # One conforming update per kind this tick using first lineage.
        ordinal, occurrence, actor = items[0]
        content = ConventionContent(
            situation=ConventionSituation.COLLECTIVE_ACTION,
            usual_action=kind,
            location_id=location,
            counterpart_class=ConventionCounterpartClass.ANY_PRESENT,
        )
        _record_conforming(
            drafts=drafts,
            notices=notices,
            owner_id=identity.owner_id,
            content=content,
            delta=policy.conforming_collective_action,
            channel=ConventionEvidenceChannel.OBSERVED,
            lineage_ref=_lineage(tick, ordinal, occurrence),
            tick=tick,
            actor_id=actor,
            participants=agents[: policy.max_participants],
            policy=policy,
            seen=seen,
            others_present=len(agents) - 1,
            scarce=scarce,
        )


def _memory_tokens(trace: object) -> tuple[set[str], list[tuple[str, str, str]]]:
    concepts: set[str] = set()
    relations: list[tuple[str, str, str]] = []
    for item in getattr(trace, "concepts", ()) or ():
        token = getattr(item, "concept", None)
        if isinstance(token, str):
            concepts.add(token)
    concept_by_id: dict[str, str] = {}
    for item in getattr(trace, "concepts", ()) or ():
        mention = getattr(item, "mention_id", None)
        token = getattr(item, "concept", None)
        if mention is not None and isinstance(token, str):
            concept_by_id[getattr(mention, "value", "")] = token
    for item in getattr(trace, "relations", ()) or ():
        predicate = getattr(item, "predicate", None)
        subject = getattr(item, "subject", None)
        obj = getattr(item, "object", None)
        if not isinstance(predicate, str):
            continue
        subject_token = ""
        object_token = ""
        if subject is not None:
            mid = getattr(getattr(subject, "mention_id", None), "value", "")
            subject_token = concept_by_id.get(mid, mid)
        if obj is not None:
            mid = getattr(getattr(obj, "mention_id", None), "value", "")
            object_token = concept_by_id.get(mid, mid)
        relations.append((subject_token, predicate, object_token))
    return concepts, relations


def _apply_memory_reinforcement(
    *,
    memories: Sequence[object] | None,
    drafts: list[_BeliefDraft],
    notices: list[str],
    owner_id: AgentId,
    tick: int,
    policy: SocialConventionPolicy,
) -> None:
    if not memories or not drafts:
        return
    remembered_seen: set[tuple[str, str]] = set()
    content_keys = {
        convention_content_key(draft.content): draft for draft in drafts
    }
    situation_tokens = {draft.content.situation.value for draft in drafts}
    action_tokens = {draft.content.usual_action for draft in drafts}
    matched_any = False
    for trace in memories:
        forgotten = getattr(trace, "forgotten_at_tick", None)
        expires = getattr(trace, "expires_at_tick", None)
        if forgotten is not None:
            continue
        if expires is not None and isinstance(expires, int) and expires <= tick:
            continue
        memory_id = getattr(getattr(trace, "memory_id", None), "value", None)
        if not isinstance(memory_id, str) or not memory_id:
            continue
        concepts, relations = _memory_tokens(trace)
        matched_drafts: list[_BeliefDraft] = []
        for key, draft in content_keys.items():
            situation = draft.content.situation.value
            action = draft.content.usual_action
            if situation in concepts and action in concepts:
                matched_drafts.append(draft)
                continue
            for subject, predicate, obj in relations:
                if predicate not in {"usually", "greet", "custom"}:
                    continue
                if subject == situation and obj == action:
                    matched_drafts.append(draft)
                    break
                if key in {subject, obj} or situation in {subject, obj}:
                    matched_drafts.append(draft)
                    break
        if not matched_drafts and (
            situation_tokens & concepts or action_tokens & concepts
        ):
            # Concepts alone without a full content key do not mint or reinforce.
            pass
        for draft in matched_drafts:
            belief_id = convention_belief_id(owner_id, draft.content)
            dedup = (belief_id, memory_id)
            if dedup in remembered_seen:
                continue
            remembered_seen.add(dedup)
            if len(draft.evidence) >= policy.max_evidence:
                _notice(notices, "cap_exceeded")
                _log_drop("cap_exceeded")
                continue
            before = draft.strength
            draft.strength = _apply_delta(before, policy.remembered_delta)
            draft.repetition_count += 1
            draft.touched = True
            if draft.last_tick is None or tick > draft.last_tick:
                draft.last_tick = tick
            ordinal = len(draft.evidence)
            draft.evidence.append(
                ConventionEvidenceItem(
                    evidence_id=convention_evidence_id(
                        belief_id,
                        ordinal,
                        ConventionEvidenceChannel.REMEMBERED,
                        memory_id,
                    ),
                    ordinal=ordinal,
                    channel=ConventionEvidenceChannel.REMEMBERED,
                    lineage_ref=memory_id,
                    tick=tick,
                )
            )
            matched_any = True
            _LOG.debug(
                "convention_memory_reinforced owner_id=%s tick=%s",
                owner_id.value,
                tick,
            )
    if memories and drafts and not matched_any:
        _notice(notices, "memory_no_match")
        _log_drop("memory_no_match")


def _apply_transmission(
    *,
    observation: Observation,
    identity: OwnerSafeSocialIdentity,
    drafts: list[_BeliefDraft],
    notices: list[str],
    policy: SocialConventionPolicy,
    seen: set[tuple[str, str, str]],
    scarce: bool,
) -> None:
    location = (
        None if observation.self_body is None else observation.self_body.location_id
    )
    tick = observation.tick
    owner_entity = identity.owner_entity_id
    for ordinal, communication in enumerate(observation.communications):
        if communication.listener_id != owner_entity:
            continue
        if communication.action_kind not in {"talk", "ask", "tell"}:
            continue
        hop = communication.utterance.declared.hop_count
        if hop not in {0, 1}:
            continue
        speaker = _resolve_agent(identity, communication.speaker_id)
        if speaker is None:
            _notice(notices, "unresolved_entity")
            _log_drop("unresolved_entity")
            continue
        for relation in communication.utterance.content.relations:
            predicate = relation.predicate
            if predicate not in {"usually", "custom"}:
                continue
            situation_token = relation.subject
            action_token = relation.object
            try:
                situation = ConventionSituation(situation_token)
            except ValueError:
                continue
            if action_token not in _USUAL_ACTIONS:
                continue
            content = ConventionContent(
                situation=situation,
                usual_action=action_token,
                location_id=location,
                day_phase=(
                    observation.day_phase
                    if situation is ConventionSituation.TIMED_GATHERING
                    else None
                ),
                counterpart_class=ConventionCounterpartClass.ANY_PRESENT,
            )
            if predicate == "custom":
                draft = _find_draft(drafts, content)
                if draft is None:
                    continue
                if len(draft.evidence) >= policy.max_evidence:
                    _notice(notices, "cap_exceeded")
                    _log_drop("cap_exceeded")
                    continue
                belief_id = convention_belief_id(identity.owner_id, draft.content)
                lineage = _comm_lineage(tick, ordinal, communication)
                ordinal_e = len(draft.evidence)
                draft.evidence.append(
                    ConventionEvidenceItem(
                        evidence_id=convention_evidence_id(
                            belief_id,
                            ordinal_e,
                            ConventionEvidenceChannel.COMMUNICATED,
                            lineage,
                        ),
                        ordinal=ordinal_e,
                        channel=ConventionEvidenceChannel.COMMUNICATED,
                        lineage_ref=lineage,
                        tick=tick,
                        actor_id=speaker,
                        predicate="custom",
                    )
                )
                draft.conceptualization = ConventionConceptualization.NAMED_CUSTOM
                draft.touched = True
                _LOG.debug(
                    "convention_transmission_applied owner_id=%s tick=%s "
                    "channel=%s",
                    identity.owner_id.value,
                    tick,
                    "custom",
                )
                continue
            _record_conforming(
                drafts=drafts,
                notices=notices,
                owner_id=identity.owner_id,
                content=content,
                delta=policy.transmission_delta,
                channel=ConventionEvidenceChannel.COMMUNICATED,
                lineage_ref=_comm_lineage(tick, ordinal, communication),
                tick=tick,
                actor_id=speaker,
                participants=(speaker, identity.owner_id),
                policy=policy,
                seen=seen,
                others_present=1,
                scarce=scarce,
                predicate="usually",
                transmission=ConventionTransmission.COMMUNICATED,
            )
            draft = _find_draft(drafts, content)
            if (
                draft is not None
                and draft.conceptualization is ConventionConceptualization.NONE
            ):
                draft.conceptualization = ConventionConceptualization.NAMED_USUAL
            _LOG.debug(
                "convention_transmission_applied owner_id=%s tick=%s channel=%s",
                identity.owner_id.value,
                tick,
                "communicated",
            )


def _practical_cue_present(draft: _BeliefDraft, observation: Observation) -> bool:
    explanation = draft.remembered_explanation
    if explanation is ConventionExplanation.FORGOTTEN:
        return False
    if explanation is ConventionExplanation.RESOURCE_ACCESS:
        return _scarce(observation)
    if explanation is ConventionExplanation.COORDINATION:
        return len(observation.visible_bodies) >= 2
    if explanation is ConventionExplanation.SOCIAL_CONTACT:
        return len(observation.visible_bodies) >= 1
    if explanation is ConventionExplanation.FATIGUE_REST:
        return any(
            occurrence.kind == "sleep" for occurrence in observation.occurrences
        )
    if explanation is ConventionExplanation.HUNGER_RELIEF:
        return any(occurrence.kind == "eat" for occurrence in observation.occurrences)
    if explanation is ConventionExplanation.UNKNOWN:
        return True
    return False


def _fade_explanations(
    drafts: list[_BeliefDraft],
    observation: Observation,
    policy: SocialConventionPolicy,
    owner_id: AgentId,
) -> None:
    tick = observation.tick
    for draft in drafts:
        if draft.status is ConventionStatus.RETIRED:
            continue
        if draft.remembered_explanation is ConventionExplanation.FORGOTTEN:
            continue
        # Reason fade requires continuing conforming evidence without the cue.
        if not draft.touched:
            continue
        if _practical_cue_present(draft, observation):
            draft.explanation_cue_absent_ticks = 0
            continue
        draft.explanation_cue_absent_ticks += 1
        if draft.explanation_cue_absent_ticks >= policy.explanation_fade_ticks:
            draft.remembered_explanation = ConventionExplanation.FORGOTTEN
            _LOG.debug(
                "convention_explanation_forgotten owner_id=%s tick=%s status=%s",
                owner_id.value,
                tick,
                draft.status.value,
            )


def _promote(
    drafts: list[_BeliefDraft],
    owner_id: AgentId,
    tick: int,
    policy: SocialConventionPolicy,
    notices: list[str],
) -> None:
    for draft in drafts:
        if draft.status is not ConventionStatus.CANDIDATE:
            continue
        participants = len(draft.participant_ids)
        min_participants = 1 if (
            draft.content.situation is ConventionSituation.HABITUAL_EXCHANGE
        ) else 2
        if draft.repetition_count < policy.promotion_count:
            _notice(notices, "below_count")
            _LOG.warning("convention_belief_withheld reason=%s", "below_count")
            continue
        if participants < min_participants:
            _notice(notices, "below_count")
            _LOG.warning("convention_belief_withheld reason=%s", "below_count")
            continue
        if draft.strength < policy.active_strength:
            _notice(notices, "below_strength")
            _LOG.warning("convention_belief_withheld reason=%s", "below_strength")
            continue
        draft.status = ConventionStatus.ACTIVE
        _LOG.debug(
            "convention_belief_promoted owner_id=%s tick=%s status=%s",
            owner_id.value,
            tick,
            draft.status.value,
        )


def _link_variants(
    drafts: list[_BeliefDraft],
    owner_id: AgentId,
    policy: SocialConventionPolicy,
    notices: list[str],
) -> None:
    by_key: dict[str, list[_BeliefDraft]] = defaultdict(list)
    for draft in drafts:
        if draft.status is ConventionStatus.RETIRED:
            continue
        by_key[_situation_key(draft.content)].append(draft)
    for group in by_key.values():
        if len(group) < 2:
            continue
        ids = [convention_belief_id(owner_id, draft.content) for draft in group]
        for index, draft in enumerate(group):
            others = [item for j, item in enumerate(ids) if j != index]
            for other in others:
                if other in draft.competing_variant_ids:
                    continue
                if len(draft.competing_variant_ids) >= policy.max_variants:
                    _notice(notices, "cap_exceeded")
                    _log_drop("cap_exceeded")
                    break
                draft.competing_variant_ids.append(other)


def _decay(
    drafts: list[_BeliefDraft],
    owner_id: AgentId,
    tick: int,
    policy: SocialConventionPolicy,
) -> None:
    for draft in drafts:
        if draft.status is ConventionStatus.RETIRED:
            continue
        if draft.touched:
            continue
        before = draft.strength
        draft.strength = _apply_delta(before, -policy.decay)
        if draft.strength < policy.retire_strength:
            draft.status = ConventionStatus.RETIRED
            _LOG.debug(
                "convention_belief_retired owner_id=%s tick=%s status=%s",
                owner_id.value,
                tick,
                draft.status.value,
            )


def _freeze(
    owner_id: AgentId,
    drafts: list[_BeliefDraft],
    notices: list[str],
    plans: Sequence[ConventionUtterancePlan] = (),
) -> ConventionLedger:
    beliefs: list[ConventionBelief] = []
    for draft in drafts:
        beliefs.append(
            ConventionBelief(
                belief_id=convention_belief_id(owner_id, draft.content),
                owner_id=owner_id,
                content=draft.content,
                status=draft.status,
                strength=draft.strength,
                repetition_count=draft.repetition_count,
                participant_ids=tuple(draft.participant_ids),
                first_tick=draft.first_tick,
                last_tick=draft.last_tick,
                transmission=draft.transmission,
                remembered_explanation=draft.remembered_explanation,
                competing_variant_ids=tuple(draft.competing_variant_ids),
                conceptualization=draft.conceptualization,
                evidence=tuple(draft.evidence),
                last_utterance_tick=draft.last_utterance_tick,
                explanation_cue_absent_ticks=draft.explanation_cue_absent_ticks,
                notices=tuple(draft.notices),
            )
        )
    return ConventionLedger(
        owner_id=owner_id,
        beliefs=tuple(beliefs),
        notices=tuple(notices),
        utterance_plans=tuple(plans),
    )


def apply_convention_update(
    observation: object,
    identity: object,
    previous: object = None,
    memories: Sequence[object] | None = None,
    policy: SocialConventionPolicy | None = None,
) -> ConventionLedger:
    """Apply one tick of habit evidence for a single owner.

    Disabled callers do not call this function. Passing world authority or a
    metric document raises ``TypeError``. Memory reinforces existing beliefs
    only and never mints a new belief.
    """
    _LOG.debug(
        "apply_convention_update owner_id=%s tick=%s",
        getattr(getattr(identity, "owner_id", None), "value", None),
        getattr(observation, "tick", None),
    )
    for value in (observation, identity, previous, policy, memories):
        _reject_forbidden(value)
    if memories is not None:
        for item in memories:
            _reject_forbidden(item)
    if type(observation) is not Observation:
        raise TypeError("observation must be Observation")
    if type(identity) is not OwnerSafeSocialIdentity:
        raise TypeError("identity must be OwnerSafeSocialIdentity")
    if previous is not None and type(previous) is not ConventionLedger:
        raise TypeError("previous must be ConventionLedger or None")
    active_policy = default_social_convention_policy() if policy is None else policy
    if type(active_policy) is not SocialConventionPolicy:
        raise TypeError("policy must be SocialConventionPolicy")
    owner_id = identity.owner_id
    tick = observation.tick
    drafts = _drafts_from(previous, owner_id)
    notices: list[str] = []
    seen: set[tuple[str, str, str]] = set()
    scarce = _scarce(observation)

    _apply_meeting_evidence(
        observation=observation,
        identity=identity,
        drafts=drafts,
        notices=notices,
        policy=active_policy,
        seen=seen,
        scarce=scarce,
    )
    _apply_greeting_evidence(
        observation=observation,
        identity=identity,
        drafts=drafts,
        notices=notices,
        policy=active_policy,
        seen=seen,
        scarce=scarce,
    )
    _apply_give_evidence(
        observation=observation,
        identity=identity,
        drafts=drafts,
        notices=notices,
        policy=active_policy,
        seen=seen,
        scarce=scarce,
    )
    _apply_collective_evidence(
        observation=observation,
        identity=identity,
        drafts=drafts,
        notices=notices,
        policy=active_policy,
        seen=seen,
        scarce=scarce,
    )
    _apply_transmission(
        observation=observation,
        identity=identity,
        drafts=drafts,
        notices=notices,
        policy=active_policy,
        seen=seen,
        scarce=scarce,
    )
    _apply_memory_reinforcement(
        memories=memories,
        drafts=drafts,
        notices=notices,
        owner_id=owner_id,
        tick=tick,
        policy=active_policy,
    )
    _fade_explanations(drafts, observation, active_policy, owner_id)
    _promote(drafts, owner_id, tick, active_policy, notices)
    _link_variants(drafts, owner_id, active_policy, notices)
    _decay(drafts, owner_id, tick, active_policy)
    ledger = _freeze(owner_id, drafts, notices)
    _LOG.info(
        "convention_belief_updated owner_id=%s belief_count=%s",
        owner_id.value,
        len(ledger.beliefs),
    )
    return ledger


def _direction_value(future: object) -> str | None:
    direction = getattr(future, "direction", None)
    if type(direction) is ActionDirection:
        return direction.value
    value = getattr(direction, "value", None)
    return value if isinstance(value, str) else None


def _future_id(future: object) -> str | None:
    value = getattr(future, "future_id", None)
    return value if isinstance(value, str) and value else None


def _observation_matches_situation(
    observation: Observation, content: ConventionContent
) -> bool:
    if content.location_id is not None and observation.self_body is not None:
        if observation.self_body.location_id != content.location_id:
            return False
    if content.situation is ConventionSituation.TIMED_GATHERING:
        return (
            observation.day_phase is not None
            and content.day_phase is not None
            and observation.day_phase is content.day_phase
        )
    if content.situation is ConventionSituation.COLOCATED_MEETING:
        return observation.day_phase is None and len(observation.visible_bodies) >= 1
    if content.situation is ConventionSituation.GREETING_EXCHANGE:
        return True
    if content.situation is ConventionSituation.HABITUAL_EXCHANGE:
        return True
    if content.situation is ConventionSituation.COLLECTIVE_ACTION:
        return len(observation.visible_bodies) >= 1
    return False


def convention_habit_penalties(
    ledger: object,
    observation: object,
    futures: Sequence[object],
    *,
    mode: object | None = None,
    policy: SocialConventionPolicy | None = None,
) -> Mapping[str, float]:
    """Penalize non-matching futures. Does not construct commands."""
    _reject_forbidden(observation)
    _reject_forbidden(ledger)
    if mode is not None:
        from agents.cognition.configuration import CognitionSocialConventionMode

        if mode is not CognitionSocialConventionMode.DETERMINISTIC:
            return {}
    if ledger is None or type(ledger) is not ConventionLedger:
        return {}
    if type(observation) is not Observation:
        raise TypeError("observation must be Observation")
    active_policy = default_social_convention_policy() if policy is None else policy
    if type(active_policy) is not SocialConventionPolicy:
        raise TypeError("policy must be SocialConventionPolicy")
    penalties: dict[str, float] = {}
    notices: list[str] = []
    for belief in ledger.beliefs:
        if belief.status is not ConventionStatus.ACTIVE:
            if belief.status is ConventionStatus.CANDIDATE:
                _notice(notices, "candidate_only")
                _LOG.warning(
                    "convention_response_withheld reason=%s", "candidate_only"
                )
            continue
        if belief.strength < active_policy.active_strength:
            continue
        if not _observation_matches_situation(observation, belief.content):
            continue
        preferred = belief.content.usual_action
        # Map talk/give to planner directions where needed.
        preferred_directions = {preferred}
        if preferred == "talk":
            preferred_directions.add(ActionDirection.COMMUNICATE.value)
        if preferred == "give":
            preferred_directions.add(ActionDirection.HELP.value)
        matching_ids = [
            future_id
            for future in futures
            if (future_id := _future_id(future)) is not None
            and _direction_value(future) in preferred_directions
        ]
        if not matching_ids:
            _notice(notices, "no_candidate")
            _LOG.warning("convention_response_withheld reason=%s", "no_candidate")
            continue
        for future in futures:
            future_id = _future_id(future)
            if future_id is None or future_id in matching_ids:
                continue
            current = penalties.get(future_id, 0.0)
            total = _apply_delta(current, active_policy.penalty)
            if total < 0.0:
                raise _fail("penalty", "negative_penalty")
            penalties[future_id] = total
        _LOG.debug(
            "convention_response_selected owner_id=%s tick=%s response=%s",
            ledger.owner_id.value,
            observation.tick,
            "habit",
        )
    return penalties


def convention_communicate_utterance(
    command: object,
    *,
    owner_id: AgentId,
    tick: int,
    observation: Observation,
    identity: OwnerSafeSocialIdentity | None,
    ledger: object | None,
    mode: object | None,
) -> object:
    """Stamp an existing Talk command with one convention relation recipe."""
    from agents.cognition.configuration import CognitionSocialConventionMode
    from world.actions import Talk
    from world.communications import (
        CommunicationRelation,
        CommunicationSourceBasis,
        origin_utterance,
    )

    if mode is not CognitionSocialConventionMode.DETERMINISTIC:
        return command
    if type(observation) is not Observation:
        return command
    if type(command) is not Talk:
        return command
    if type(ledger) is not ConventionLedger or not ledger.beliefs:
        return command
    if identity is None:
        return command
    if observation.tick != tick:
        return command
    policy = default_social_convention_policy()
    chosen: ConventionBelief | None = None
    for belief in ledger.beliefs:
        if belief.status is not ConventionStatus.ACTIVE:
            continue
        if belief.strength < policy.active_strength:
            continue
        if belief.last_utterance_tick is not None and (
            tick - belief.last_utterance_tick < policy.utterance_interval
        ):
            _LOG.warning(
                "convention_response_withheld reason=%s", "utterance_interval"
            )
            continue
        chosen = belief
        break
    if chosen is None:
        return command
    predicate = (
        "custom"
        if chosen.conceptualization is ConventionConceptualization.NAMED_CUSTOM
        else "usually"
    )
    utterance = origin_utterance(
        text=predicate,
        speaker_id=identity.owner_entity_id,
        communication_id=(
            f"social-conventions-{owner_id.value}-{tick}-"
            f"{chosen.content.situation.value}"
        ),
        relations=(
            CommunicationRelation(
                subject=chosen.content.situation.value,
                predicate=predicate,
                object=chosen.content.usual_action,
            ),
        ),
        source_basis=CommunicationSourceBasis.UNREFERENCED,
    )
    _LOG.debug(
        "convention_response_selected owner_id=%s tick=%s response=%s",
        owner_id.value,
        tick,
        "communicate",
    )
    return Talk(recipient_id=command.recipient_id, utterance=utterance)
