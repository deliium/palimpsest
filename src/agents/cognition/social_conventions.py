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
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum
from typing import Final

from agents.models import AgentId
from world.identifiers import EntityId, require_exact_nonneg_int
from world.values import DayPhase

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
