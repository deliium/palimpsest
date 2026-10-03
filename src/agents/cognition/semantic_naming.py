"""Owner-scoped bounded semantic naming (terminology ledger).

A ledger is a private label system — not a natural language, not a world
dictionary, and not a semantic belief. Updates read one owner's Observation,
previous TerminologyLedger, OwnerSafeSocialIdentity, already-loaded memories
(reinforce-only), and an optional caller-built NamingCueSummary. They never
read WorldState, WorldEvent, PhysicalRules, another owner's ledger, sibling
group/norm/convention/artifact ledger objects, or analysis documents.
"""

from __future__ import annotations

import hashlib
import logging
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum
from typing import Final

from agents.cognition.models import OwnerSafeSocialIdentity
from agents.models import AgentId
from world.environment import HazardKind
from world.identifiers import EntityId, require_exact_nonneg_int
from world.observations import Observation, ObservedCommunication, ObservedOccurrence
from world.values import ResourceKind

_LOG: Final[logging.Logger] = logging.getLogger("agents.cognition.semantic_naming")

SEMANTIC_NAMING_POLICY_VERSION: Final[str] = "semantic-naming.v1"
_QUANTUM: Final[Decimal] = Decimal("0.000001")
_ACTIVE_STRENGTH: Final[float] = 0.40
_RETIRE_STRENGTH: Final[float] = 0.20
_DECAY: Final[float] = 0.05
_CONFORMING_LOCATION: Final[float] = 0.12
_CONFORMING_AGENT: Final[float] = 0.10
_CONFORMING_GROUP: Final[float] = 0.12
_CONFORMING_RECURRING: Final[float] = 0.12
_CONFORMING_DANGEROUS: Final[float] = 0.15
_CONFORMING_PRACTICE: Final[float] = 0.10
_TRANSMISSION_DELTA: Final[float] = 0.10
_REMEMBERED_DELTA: Final[float] = 0.08
_PENALTY: Final[float] = 0.30
_PROMOTION_COUNT: Final[int] = 3
_MEANING_SHIFT_TICKS: Final[int] = 6
_MERGE_JACCARD: Final[float] = 0.50
_UTTERANCE_INTERVAL: Final[int] = 4
_MAX_BINDINGS: Final[int] = 16
_MAX_EVIDENCE: Final[int] = 32
_MAX_CANDIDATES: Final[int] = 4
_MAX_COMPETITORS: Final[int] = 4
_MAX_MERGE_FAN_IN: Final[int] = 4
_MEANING_SHIFT_LEAD: Final[float] = 0.20
_HEX: Final[frozenset[str]] = frozenset("0123456789abcdef")
_LABEL_TOKEN_RE: Final[re.Pattern[str]] = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
_UNREFERENCED: Final[str] = "unreferenced"
_NOTICE_REASONS: Final[frozenset[str]] = frozenset(
    {
        "cap_exceeded",
        "ignored_kind",
        "unresolved_entity",
        "illegal_token",
        "memory_no_match",
        "no_candidate",
        "candidate_only",
        "empty_candidates",
        "utterance_interval",
        "below_count",
        "below_strength",
        "invalid_token",
        "forbidden_type",
    }
)
_FORBIDDEN_TYPES: Final[frozenset[str]] = frozenset(
    {
        "WorldState",
        "WorldEvent",
        "PhysicalRules",
        "AgentBody",
        "MetricDocument",
        "GroupLedger",
        "NormLedger",
        "ConventionLedger",
        "ArtifactInterpretationLedger",
    }
)
_FORBIDDEN_CUE_TYPE_NAMES: Final[frozenset[str]] = frozenset(
    {
        "GroupLedger",
        "NormLedger",
        "ConventionLedger",
        "ArtifactInterpretationLedger",
        "GroupConcept",
        "NormBelief",
        "ConventionBelief",
        "TerminologyLedger",
        "LabelBinding",
    }
)

__all__ = [
    "SEMANTIC_NAMING_POLICY_VERSION",
    "LabelBinding",
    "NamingCandidate",
    "NamingCueSummary",
    "NamingEvidenceChannel",
    "NamingEvidenceItem",
    "NamingReferentKind",
    "NamingStatus",
    "NamingStrengthBand",
    "NamingTransmission",
    "NamingUtterancePlan",
    "SemanticNamingPolicy",
    "TerminologyLedger",
    "apply_naming_update",
    "default_semantic_naming_policy",
    "empty_terminology_ledger",
    "label_binding_id",
    "label_display",
    "naming_communicate_penalties",
    "naming_communicate_utterance",
    "naming_evidence_id",
    "naming_strength_band",
    "require_owner_semantic_naming",
    "stable8_digest",
]


class NamingReferentKind(StrEnum):
    """Closed referent kinds the owner may try to label."""

    LOCATION = "location"
    AGENT = "agent"
    GROUP = "group"
    RECURRING_EVENT = "recurring_event"
    DANGEROUS_RESOURCE = "dangerous_resource"
    SOCIAL_PRACTICE = "social_practice"


class NamingTransmission(StrEnum):
    """Closed transmission provenance on a binding."""

    OBSERVED = "observed"
    COMMUNICATED = "communicated"
    BOTH = "both"


class NamingEvidenceChannel(StrEnum):
    """Closed evidence channel for one ledger item."""

    OBSERVED = "observed"
    COMMUNICATED = "communicated"
    REMEMBERED = "remembered"


class NamingStatus(StrEnum):
    """Closed lifecycle for one owner's label binding."""

    CANDIDATE = "candidate"
    ACTIVE = "active"
    RETIRED = "retired"


class NamingStrengthBand(StrEnum):
    """Closed overlay strength band for researcher presentation."""

    CANDIDATE = "candidate"
    LOW = "low"
    MID = "mid"
    HIGH = "high"


def _fail(field_name: str, code: str) -> ValueError:
    _LOG.error(
        "naming_validation_failed field=%s reason_code=%s",
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


def _require_label_token(field_name: str, value: object) -> str:
    if not isinstance(value, str) or not _LABEL_TOKEN_RE.fullmatch(value):
        raise _fail(field_name, "illegal_token")
    return value


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
    if isinstance(value, Mapping):
        keys = {str(key) for key in value}
        if "metric_family" in keys or "availability" in keys:
            raise TypeError(f"{name}: forbidden_input")


def stable8_digest(
    owner_id: AgentId,
    referent_kind: NamingReferentKind,
    referent_id: str,
) -> str:
    """First 8 hex chars of sha256(owner|kind|referent). Never Python hash()."""
    if type(owner_id) is not AgentId:
        raise _fail("owner_id", "invalid_type")
    if type(referent_kind) is not NamingReferentKind:
        raise _fail("referent_kind", "unknown_kind")
    if not isinstance(referent_id, str) or not referent_id:
        raise _fail("referent_id", "invalid_type")
    return _sha256_hex(f"{owner_id.value}|{referent_kind.value}|{referent_id}")[:8]


def label_binding_id(
    owner_id: AgentId,
    referent_kind: NamingReferentKind,
    label_token: str,
) -> str:
    """sha256 hex of owner id, referent kind, and closed label token."""
    if type(owner_id) is not AgentId:
        raise _fail("owner_id", "invalid_type")
    if type(referent_kind) is not NamingReferentKind:
        raise _fail("referent_kind", "unknown_kind")
    token = _require_label_token("label_token", label_token)
    return _sha256_hex(f"{owner_id.value}|{referent_kind.value}|{token}")


def label_display(label_token: str) -> str:
    """Title-case underscores for researcher overlays only."""
    token = _require_label_token("label_token", label_token)
    return " ".join(part.capitalize() for part in token.split("_") if part)


def naming_strength_band(status: NamingStatus, strength: float) -> NamingStrengthBand:
    """Closed overlay strength band from status and quantized strength."""
    if type(status) is not NamingStatus:
        raise _fail("status", "unknown_status")
    quantized = _quantize(_finite("strength", strength))
    if status is NamingStatus.CANDIDATE:
        return NamingStrengthBand.CANDIDATE
    if quantized < 0.40:
        return NamingStrengthBand.LOW
    if quantized < 0.70:
        return NamingStrengthBand.MID
    return NamingStrengthBand.HIGH


@dataclass(frozen=True, slots=True)
class NamingCandidate:
    """Private soft link from a label to a possible objective referent."""

    kind: NamingReferentKind
    entity_id: str
    confidence: float

    def __post_init__(self) -> None:
        if type(self.kind) is not NamingReferentKind:
            raise _fail("candidate.kind", "unknown_kind")
        if not isinstance(self.entity_id, str) or not self.entity_id:
            raise _fail("candidate.entity_id", "invalid_type")
        confidence = _finite("candidate.confidence", self.confidence)
        quantized = _quantize(confidence)
        if quantized < 0.0 or quantized > 1.0:
            raise _fail("candidate.confidence", "out_of_range")
        object.__setattr__(self, "confidence", quantized)


@dataclass(frozen=True, slots=True)
class NamingEvidenceItem:
    """One observed, communicated, or remembered item on a binding."""

    evidence_id: str
    ordinal: int
    channel: NamingEvidenceChannel
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
        if type(self.channel) is not NamingEvidenceChannel:
            raise _fail("evidence.channel", "unknown_channel")
        if not isinstance(self.lineage_ref, str) or not self.lineage_ref:
            raise _fail("evidence.lineage_ref", "invalid_type")
        object.__setattr__(
            self,
            "tick",
            require_exact_nonneg_int("NamingEvidenceItem.tick", self.tick),
        )
        if self.actor_id is not None and type(self.actor_id) is not AgentId:
            raise _fail("evidence.actor_id", "invalid_type")
        if self.predicate is not None:
            if not isinstance(self.predicate, str) or self.predicate != "call":
                raise _fail("evidence.predicate", "unknown_predicate")


@dataclass(frozen=True, slots=True)
class NamingUtterancePlan:
    """Relation recipe the planner may place on an existing talk future."""

    label_token: str
    referent_kind: NamingReferentKind
    predicate: str = "call"
    source_basis: str = _UNREFERENCED

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "label_token",
            _require_label_token("utterance.label_token", self.label_token),
        )
        if type(self.referent_kind) is not NamingReferentKind:
            raise _fail("utterance.referent_kind", "unknown_kind")
        if self.predicate != "call":
            raise _fail("utterance.predicate", "unknown_predicate")
        if self.source_basis != _UNREFERENCED:
            raise _fail("utterance.source_basis", "unsupported_basis")


@dataclass(frozen=True, slots=True)
class LabelBinding:
    """One owner's private term for a possible referent."""

    binding_id: str
    owner_id: AgentId
    label_token: str
    referent_kind: NamingReferentKind
    status: NamingStatus
    strength: float
    candidates: tuple[NamingCandidate, ...] = ()
    evidence_count: int = 0
    first_tick: int | None = None
    last_tick: int | None = None
    transmission: NamingTransmission = NamingTransmission.OBSERVED
    sense_revision: int = 0
    merged_into: str | None = None
    competing_label_ids: tuple[str, ...] = ()
    evidence: tuple[NamingEvidenceItem, ...] = ()
    last_utterance_tick: int | None = None
    meaning_shift_streak: int = 0
    notices: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "binding_id", _require_hex_id("binding_id", self.binding_id)
        )
        if type(self.owner_id) is not AgentId:
            raise _fail("owner_id", "invalid_type")
        object.__setattr__(
            self, "label_token", _require_label_token("label_token", self.label_token)
        )
        if type(self.referent_kind) is not NamingReferentKind:
            raise _fail("referent_kind", "unknown_kind")
        if type(self.status) is not NamingStatus:
            raise _fail("status", "unknown_status")
        if type(self.transmission) is not NamingTransmission:
            raise _fail("transmission", "unknown_transmission")
        strength = _finite("strength", self.strength)
        quantized = _quantize(strength)
        if quantized < 0.0 or quantized > 1.0:
            raise _fail("strength", "out_of_range")
        object.__setattr__(self, "strength", quantized)
        if isinstance(self.evidence_count, bool) or type(
            self.evidence_count
        ) is not int:
            raise _fail("evidence_count", "invalid_type")
        if self.evidence_count < 0:
            raise _fail("evidence_count", "out_of_range")
        if isinstance(self.sense_revision, bool) or type(
            self.sense_revision
        ) is not int:
            raise _fail("sense_revision", "invalid_type")
        if self.sense_revision < 0:
            raise _fail("sense_revision", "out_of_range")
        if isinstance(self.meaning_shift_streak, bool) or type(
            self.meaning_shift_streak
        ) is not int:
            raise _fail("meaning_shift_streak", "invalid_type")
        if self.meaning_shift_streak < 0:
            raise _fail("meaning_shift_streak", "out_of_range")
        candidates = _require_tuple("candidates", self.candidates)
        checked_candidates: list[NamingCandidate] = []
        for item in candidates:
            if type(item) is not NamingCandidate:
                raise _fail("candidates", "invalid_type")
            checked_candidates.append(item)
        if len(checked_candidates) > _MAX_CANDIDATES:
            raise _fail("candidates", "cap_exceeded")
        if self.first_tick is not None:
            object.__setattr__(
                self,
                "first_tick",
                require_exact_nonneg_int("LabelBinding.first_tick", self.first_tick),
            )
        if self.last_tick is not None:
            object.__setattr__(
                self,
                "last_tick",
                require_exact_nonneg_int("LabelBinding.last_tick", self.last_tick),
            )
        if (
            self.first_tick is not None
            and self.last_tick is not None
            and self.last_tick < self.first_tick
        ):
            raise _fail("last_tick", "before_first_tick")
        if self.merged_into is not None:
            object.__setattr__(
                self, "merged_into", _require_hex_id("merged_into", self.merged_into)
            )
            if self.merged_into == self.binding_id:
                raise _fail("merged_into", "self_merge")
        competitors = _require_tuple("competing_label_ids", self.competing_label_ids)
        checked_competitors: list[str] = []
        seen_competitors: set[str] = set()
        for item in competitors:
            head = _require_hex_id("competing_label_ids", item)
            if head == self.binding_id:
                raise _fail("competing_label_ids", "self_competitor")
            if head in seen_competitors:
                raise _fail("competing_label_ids", "duplicate_competitor")
            seen_competitors.add(head)
            checked_competitors.append(head)
        if len(checked_competitors) > _MAX_COMPETITORS:
            raise _fail("competing_label_ids", "cap_exceeded")
        evidence = _require_tuple("evidence", self.evidence)
        checked_evidence: list[NamingEvidenceItem] = []
        seen_ids: set[str] = set()
        for item in evidence:
            if type(item) is not NamingEvidenceItem:
                raise _fail("evidence", "invalid_type")
            if item.evidence_id in seen_ids:
                raise _fail("evidence", "duplicate_evidence")
            seen_ids.add(item.evidence_id)
            checked_evidence.append(item)
        if len(checked_evidence) > _MAX_EVIDENCE:
            raise _fail("evidence", "cap_exceeded")
        expected_id = label_binding_id(
            self.owner_id, self.referent_kind, self.label_token
        )
        if self.binding_id != expected_id:
            raise _fail("binding_id", "id_mismatch")
        if self.last_utterance_tick is not None:
            object.__setattr__(
                self,
                "last_utterance_tick",
                require_exact_nonneg_int(
                    "LabelBinding.last_utterance_tick", self.last_utterance_tick
                ),
            )
        notices = _require_tuple("notices", self.notices)
        checked_notices: list[str] = []
        for item in notices:
            if not isinstance(item, str) or item not in _NOTICE_REASONS:
                raise _fail("notices", "invalid_notice")
            if item not in checked_notices:
                checked_notices.append(item)
        object.__setattr__(self, "candidates", tuple(checked_candidates))
        object.__setattr__(self, "competing_label_ids", tuple(checked_competitors))
        object.__setattr__(self, "evidence", tuple(checked_evidence))
        object.__setattr__(self, "notices", tuple(checked_notices))


@dataclass(frozen=True, slots=True)
class TerminologyLedger:
    """Private labels for one owner. ``None`` means the mode is off."""

    owner_id: AgentId
    bindings: tuple[LabelBinding, ...] = ()
    notices: tuple[str, ...] = ()
    utterance_plans: tuple[NamingUtterancePlan, ...] = ()
    policy_version: str = SEMANTIC_NAMING_POLICY_VERSION

    def __post_init__(self) -> None:
        if type(self.owner_id) is not AgentId:
            raise _fail("owner_id", "invalid_type")
        if self.policy_version != SEMANTIC_NAMING_POLICY_VERSION:
            raise _fail("policy_version", "unsupported_policy")
        bindings = _require_tuple("bindings", self.bindings)
        checked: list[LabelBinding] = []
        seen: set[str] = set()
        for item in bindings:
            if type(item) is not LabelBinding:
                raise _fail("bindings", "invalid_type")
            if item.owner_id != self.owner_id:
                raise _fail("bindings.owner_id", "owner_mismatch")
            if item.binding_id in seen:
                raise _fail("bindings", "duplicate_binding")
            seen.add(item.binding_id)
            checked.append(item)
        if len(checked) > _MAX_BINDINGS:
            raise _fail("bindings", "cap_exceeded")
        notices = _require_tuple("notices", self.notices)
        checked_notices: list[str] = []
        for item in notices:
            if not isinstance(item, str) or item not in _NOTICE_REASONS:
                raise _fail("notices", "invalid_notice")
            if item not in checked_notices:
                checked_notices.append(item)
        plans = _require_tuple("utterance_plans", self.utterance_plans)
        for item in plans:
            if type(item) is not NamingUtterancePlan:
                raise _fail("utterance_plans", "invalid_type")
        object.__setattr__(self, "bindings", tuple(checked))
        object.__setattr__(self, "notices", tuple(checked_notices))
        object.__setattr__(self, "utterance_plans", tuple(plans))
        _LOG.debug(
            "naming_ledger_constructed owner_id=%s policy_version=%s binding_count=%s",
            self.owner_id.value,
            self.policy_version,
            len(self.bindings),
        )


@dataclass(frozen=True, slots=True)
class NamingCueSummary:
    """Duck-typed closed cue bag built only by CognitiveLoop.

    Holds optional group concept id tokens and practice action-kind tokens
    already known from the owner's updated snapshot fields. Must not carry
    ledger objects, analysis rows, or free-form prose.
    """

    group_concept_ids: tuple[str, ...] = ()
    practice_action_kinds: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        groups = _require_tuple("group_concept_ids", self.group_concept_ids)
        practices = _require_tuple(
            "practice_action_kinds", self.practice_action_kinds
        )
        checked_groups: list[str] = []
        checked_practices: list[str] = []
        for item in groups:
            if type(item).__name__ in _FORBIDDEN_CUE_TYPE_NAMES:
                _LOG.warning(
                    "naming_cues_dropped reason=%s",
                    "forbidden_type",
                )
                raise TypeError("NamingCueSummary: forbidden_type")
            # Group concept ids are 64-char hex digests; also accept closed
            # snake_case tokens for duck-typed tests.
            if not isinstance(item, str) or not item:
                _LOG.warning(
                    "naming_cues_dropped reason=%s",
                    "invalid_token",
                )
                raise _fail("group_concept_ids", "invalid_token")
            is_hex = (
                len(item) == 64 and all(char in _HEX for char in item)
            )
            if not is_hex and not _LABEL_TOKEN_RE.fullmatch(item):
                _LOG.warning(
                    "naming_cues_dropped reason=%s",
                    "invalid_token",
                )
                raise _fail("group_concept_ids", "invalid_token")
            checked_groups.append(item)
        for item in practices:
            if type(item).__name__ in _FORBIDDEN_CUE_TYPE_NAMES:
                _LOG.warning(
                    "naming_cues_dropped reason=%s",
                    "forbidden_type",
                )
                raise TypeError("NamingCueSummary: forbidden_type")
            if not isinstance(item, str) or not _LABEL_TOKEN_RE.fullmatch(item):
                _LOG.warning(
                    "naming_cues_dropped reason=%s",
                    "invalid_token",
                )
                raise _fail("practice_action_kinds", "invalid_token")
            checked_practices.append(item)
        # Drop duplicates while preserving order.
        object.__setattr__(
            self, "group_concept_ids", tuple(dict.fromkeys(checked_groups))
        )
        object.__setattr__(
            self,
            "practice_action_kinds",
            tuple(dict.fromkeys(checked_practices)),
        )
        _LOG.debug(
            "naming_cues_accepted owner_id=%s group_count=%s practice_count=%s",
            "-",
            len(self.group_concept_ids),
            len(self.practice_action_kinds),
        )


@dataclass(frozen=True, slots=True)
class SemanticNamingPolicy:
    """Locked naming constants. Runner JSON does not carry these weights."""

    version: str = SEMANTIC_NAMING_POLICY_VERSION
    active_strength: float = _ACTIVE_STRENGTH
    retire_strength: float = _RETIRE_STRENGTH
    decay: float = _DECAY
    conforming_location: float = _CONFORMING_LOCATION
    conforming_agent: float = _CONFORMING_AGENT
    conforming_group: float = _CONFORMING_GROUP
    conforming_recurring_event: float = _CONFORMING_RECURRING
    conforming_dangerous_resource: float = _CONFORMING_DANGEROUS
    conforming_social_practice: float = _CONFORMING_PRACTICE
    transmission_delta: float = _TRANSMISSION_DELTA
    remembered_delta: float = _REMEMBERED_DELTA
    penalty: float = _PENALTY
    promotion_count: int = _PROMOTION_COUNT
    meaning_shift_ticks: int = _MEANING_SHIFT_TICKS
    merge_jaccard: float = _MERGE_JACCARD
    utterance_interval: int = _UTTERANCE_INTERVAL
    max_bindings: int = _MAX_BINDINGS
    max_evidence: int = _MAX_EVIDENCE
    max_candidates: int = _MAX_CANDIDATES
    max_competitors: int = _MAX_COMPETITORS
    max_merge_fan_in: int = _MAX_MERGE_FAN_IN
    meaning_shift_lead: float = _MEANING_SHIFT_LEAD

    def __post_init__(self) -> None:
        if self.version != SEMANTIC_NAMING_POLICY_VERSION:
            raise _fail("version", "unsupported_policy")
        floats = (
            ("active_strength", _ACTIVE_STRENGTH),
            ("retire_strength", _RETIRE_STRENGTH),
            ("decay", _DECAY),
            ("conforming_location", _CONFORMING_LOCATION),
            ("conforming_agent", _CONFORMING_AGENT),
            ("conforming_group", _CONFORMING_GROUP),
            ("conforming_recurring_event", _CONFORMING_RECURRING),
            ("conforming_dangerous_resource", _CONFORMING_DANGEROUS),
            ("conforming_social_practice", _CONFORMING_PRACTICE),
            ("transmission_delta", _TRANSMISSION_DELTA),
            ("remembered_delta", _REMEMBERED_DELTA),
            ("penalty", _PENALTY),
            ("merge_jaccard", _MERGE_JACCARD),
            ("meaning_shift_lead", _MEANING_SHIFT_LEAD),
        )
        for name, expected in floats:
            object.__setattr__(
                self, name, _locked_float(name, getattr(self, name), expected)
            )
        counts = (
            ("promotion_count", _PROMOTION_COUNT),
            ("meaning_shift_ticks", _MEANING_SHIFT_TICKS),
            ("utterance_interval", _UTTERANCE_INTERVAL),
            ("max_bindings", _MAX_BINDINGS),
            ("max_evidence", _MAX_EVIDENCE),
            ("max_candidates", _MAX_CANDIDATES),
            ("max_competitors", _MAX_COMPETITORS),
            ("max_merge_fan_in", _MAX_MERGE_FAN_IN),
        )
        for name, expected in counts:
            object.__setattr__(
                self, name, _locked_int(name, getattr(self, name), expected)
            )
        _LOG.debug(
            "naming_policy_constructed owner_id=%s policy_version=%s binding_count=%s",
            "-",
            self.version,
            0,
        )


def default_semantic_naming_policy() -> SemanticNamingPolicy:
    """Return the only accepted semantic-naming policy."""
    return SemanticNamingPolicy()


def empty_terminology_ledger(owner_id: AgentId) -> TerminologyLedger:
    """Ledger with no bindings. Disabled mode does not call this."""
    return TerminologyLedger(owner_id=owner_id)


def require_owner_semantic_naming(
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
    if type(ledger) is not TerminologyLedger:
        _LOG.warning(
            "naming_carry_rejected reason=%s",
            "invalid_type",
        )
        raise TypeError(f"{field_name} must be TerminologyLedger")
    if ledger.owner_id != owner_id:
        _LOG.error(
            "naming_validation_failed field=%s reason_code=%s",
            field_name,
            "owner_mismatch",
        )
        _LOG.warning(
            "naming_carry_rejected reason=%s",
            "owner_mismatch",
        )
        raise ValueError(f"{field_name} owner_id mismatch")


def naming_evidence_id(
    binding_id: str,
    ordinal: int,
    channel: NamingEvidenceChannel,
    lineage_ref: str,
) -> str:
    """sha256 of binding id, ordinal, channel, and lineage ref."""
    head = _require_hex_id("binding_id", binding_id)
    if isinstance(ordinal, bool) or type(ordinal) is not int or ordinal < 0:
        raise _fail("ordinal", "invalid_type")
    if type(channel) is not NamingEvidenceChannel:
        raise _fail("channel", "unknown_channel")
    if not isinstance(lineage_ref, str) or not lineage_ref:
        raise _fail("lineage_ref", "invalid_type")
    return _sha256_hex(f"{head}|{ordinal}|{channel.value}|{lineage_ref}")


@dataclass
class _BindingDraft:
    label_token: str
    referent_kind: NamingReferentKind
    strength: float
    status: NamingStatus
    candidates: list[NamingCandidate]
    evidence_count: int
    first_tick: int | None
    last_tick: int | None
    transmission: NamingTransmission
    sense_revision: int
    merged_into: str | None
    competing_label_ids: list[str]
    evidence: list[NamingEvidenceItem]
    last_utterance_tick: int | None
    meaning_shift_streak: int
    notices: list[str] = field(default_factory=list)
    touched: bool = False
    pending_top_id: str | None = None


def _sign(before: float, after: float) -> str:
    if after > before:
        return "positive"
    if after < before:
        return "negative"
    return "zero"


def _notice(notices: list[str], reason: str) -> None:
    if reason not in notices:
        notices.append(reason)


def _log_drop(reason: str) -> None:
    _LOG.warning("naming_evidence_dropped reason=%s", reason)


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


def _seed_token(
    owner_id: AgentId,
    kind: NamingReferentKind,
    referent_id: str,
    *,
    action_kind: str | None = None,
) -> str:
    digest = stable8_digest(owner_id, kind, referent_id)
    if kind is NamingReferentKind.LOCATION:
        return f"place_{digest}"
    if kind is NamingReferentKind.AGENT:
        return f"agent_{digest}"
    if kind is NamingReferentKind.GROUP:
        return f"group_{digest}"
    if kind is NamingReferentKind.RECURRING_EVENT:
        return f"gathering_{digest}"
    if kind is NamingReferentKind.DANGEROUS_RESOURCE:
        if action_kind is not None:
            token = f"hazard_{action_kind}"
            return token if _LABEL_TOKEN_RE.fullmatch(token) else f"hazard_{digest}"
        return f"hazard_{digest}"
    if kind is NamingReferentKind.SOCIAL_PRACTICE:
        if action_kind is None:
            raise _fail("practice_action", "invalid_token")
        token = f"practice_{action_kind}"
        return token if _LABEL_TOKEN_RE.fullmatch(token) else f"practice_{digest}"
    raise _fail("referent_kind", "unknown_kind")


def _drafts_from(
    previous: TerminologyLedger | None, owner_id: AgentId
) -> list[_BindingDraft]:
    drafts: list[_BindingDraft] = []
    if previous is None:
        return drafts
    if previous.owner_id != owner_id:
        _LOG.error(
            "naming_validation_failed field=%s reason_code=%s",
            "owner_id",
            "owner_mismatch",
        )
        raise ValueError("owner_id: owner_mismatch")
    for binding in previous.bindings:
        drafts.append(
            _BindingDraft(
                label_token=binding.label_token,
                referent_kind=binding.referent_kind,
                strength=binding.strength,
                status=binding.status,
                candidates=list(binding.candidates),
                evidence_count=binding.evidence_count,
                first_tick=binding.first_tick,
                last_tick=binding.last_tick,
                transmission=binding.transmission,
                sense_revision=binding.sense_revision,
                merged_into=binding.merged_into,
                competing_label_ids=list(binding.competing_label_ids),
                evidence=list(binding.evidence),
                last_utterance_tick=binding.last_utterance_tick,
                meaning_shift_streak=binding.meaning_shift_streak,
                notices=list(binding.notices),
            )
        )
    return drafts


def _find_draft(
    drafts: list[_BindingDraft],
    *,
    label_token: str,
    referent_kind: NamingReferentKind,
) -> _BindingDraft | None:
    for draft in drafts:
        if (
            draft.label_token == label_token
            and draft.referent_kind is referent_kind
            and draft.status is not NamingStatus.RETIRED
        ):
            return draft
    return None


def _top_candidate(draft: _BindingDraft) -> NamingCandidate | None:
    if not draft.candidates:
        return None
    return max(draft.candidates, key=lambda item: (item.confidence, item.entity_id))


def _upsert_candidate(
    draft: _BindingDraft,
    kind: NamingReferentKind,
    entity_id: str,
    confidence_delta: float,
    policy: SemanticNamingPolicy,
    notices: list[str],
) -> None:
    updated: list[NamingCandidate] = []
    found = False
    for candidate in draft.candidates:
        if candidate.kind is kind and candidate.entity_id == entity_id:
            updated.append(
                NamingCandidate(
                    kind=kind,
                    entity_id=entity_id,
                    confidence=_apply_delta(candidate.confidence, confidence_delta),
                )
            )
            found = True
        else:
            updated.append(candidate)
    if not found:
        if len(updated) >= policy.max_candidates:
            _notice(notices, "cap_exceeded")
            _log_drop("cap_exceeded")
            return
        updated.append(
            NamingCandidate(
                kind=kind,
                entity_id=entity_id,
                confidence=_quantize(min(1.0, max(0.0, confidence_delta))),
            )
        )
    updated.sort(key=lambda item: (-item.confidence, item.entity_id))
    draft.candidates = updated[: policy.max_candidates]


def _record_evidence(
    *,
    drafts: list[_BindingDraft],
    notices: list[str],
    owner_id: AgentId,
    label_token: str,
    referent_kind: NamingReferentKind,
    delta: float,
    channel: NamingEvidenceChannel,
    lineage_ref: str,
    tick: int,
    policy: SemanticNamingPolicy,
    seen: set[tuple[str, str, str]],
    candidate_kind: NamingReferentKind | None = None,
    candidate_id: str | None = None,
    actor_id: AgentId | None = None,
    predicate: str | None = None,
    transmission: NamingTransmission | None = None,
    allow_empty_candidates: bool = False,
) -> None:
    try:
        token = _require_label_token("label_token", label_token)
    except ValueError:
        _notice(notices, "illegal_token")
        _log_drop("illegal_token")
        return
    dedup = (token, referent_kind.value, lineage_ref)
    if dedup in seen:
        return
    seen.add(dedup)
    draft = _find_draft(drafts, label_token=token, referent_kind=referent_kind)
    if draft is not None and any(
        item.lineage_ref == lineage_ref for item in draft.evidence
    ):
        return
    if draft is None:
        if len(drafts) >= policy.max_bindings:
            _notice(notices, "cap_exceeded")
            _log_drop("cap_exceeded")
            return
        draft = _BindingDraft(
            label_token=token,
            referent_kind=referent_kind,
            strength=0.0,
            status=NamingStatus.CANDIDATE,
            candidates=[],
            evidence_count=0,
            first_tick=tick,
            last_tick=tick,
            transmission=transmission or NamingTransmission.OBSERVED,
            sense_revision=0,
            merged_into=None,
            competing_label_ids=[],
            evidence=[],
            last_utterance_tick=None,
            meaning_shift_streak=0,
        )
        drafts.append(draft)
    if len(draft.evidence) >= policy.max_evidence:
        _notice(notices, "cap_exceeded")
        _log_drop("cap_exceeded")
        return
    before = draft.strength
    # First self-bound observation crystallizes strength at the active floor so
    # promotion_count (3) ticks of location evidence can clear active_strength.
    if (
        before == 0.0
        and channel is NamingEvidenceChannel.OBSERVED
        and candidate_kind is not None
        and candidate_id is not None
    ):
        draft.strength = _apply_delta(0.0, max(delta, policy.active_strength))
    else:
        draft.strength = _apply_delta(before, delta)
    draft.evidence_count += 1
    if draft.first_tick is None:
        draft.first_tick = tick
    draft.last_tick = tick
    draft.touched = True
    if transmission is not None:
        if (
            draft.transmission is NamingTransmission.OBSERVED
            and transmission is NamingTransmission.COMMUNICATED
        ) or (
            draft.transmission is NamingTransmission.COMMUNICATED
            and transmission is NamingTransmission.OBSERVED
        ):
            draft.transmission = NamingTransmission.BOTH
        else:
            draft.transmission = transmission
    if candidate_kind is not None and candidate_id is not None:
        _upsert_candidate(
            draft,
            candidate_kind,
            candidate_id,
            max(delta, 0.40),
            policy,
            notices,
        )
    elif not allow_empty_candidates and not draft.candidates:
        pass
    binding_id = label_binding_id(owner_id, referent_kind, token)
    ordinal = len(draft.evidence)
    draft.evidence.append(
        NamingEvidenceItem(
            evidence_id=naming_evidence_id(
                binding_id, ordinal, channel, lineage_ref
            ),
            ordinal=ordinal,
            channel=channel,
            lineage_ref=lineage_ref,
            tick=tick,
            actor_id=actor_id,
            predicate=predicate,
        )
    )
    _LOG.debug(
        "naming_binding_applied owner_id=%s tick=%s sign=%s",
        owner_id.value,
        tick,
        _sign(before, draft.strength),
    )


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


def _apply_observation_cues(
    *,
    observation: Observation,
    identity: OwnerSafeSocialIdentity,
    drafts: list[_BindingDraft],
    notices: list[str],
    policy: SemanticNamingPolicy,
    cues: NamingCueSummary | None,
    seen: set[tuple[str, str, str]],
) -> None:
    owner_id = identity.owner_id
    tick = observation.tick
    ordinal = 0
    location = (
        None
        if observation.self_body is None
        else observation.self_body.location_id
    )
    if location is not None:
        token = _seed_token(owner_id, NamingReferentKind.LOCATION, location.value)
        _record_evidence(
            drafts=drafts,
            notices=notices,
            owner_id=owner_id,
            label_token=token,
            referent_kind=NamingReferentKind.LOCATION,
            delta=policy.conforming_location,
            channel=NamingEvidenceChannel.OBSERVED,
            lineage_ref=f"tick-{tick}-loc",
            tick=tick,
            policy=policy,
            seen=seen,
            candidate_kind=NamingReferentKind.LOCATION,
            candidate_id=location.value,
        )
        for body in observation.visible_bodies:
            agent = _resolve_agent(identity, body.entity_id)
            if agent is None:
                _notice(notices, "unresolved_entity")
                _log_drop("unresolved_entity")
                continue
            agent_token = _seed_token(
                owner_id, NamingReferentKind.AGENT, agent.value
            )
            _record_evidence(
                drafts=drafts,
                notices=notices,
                owner_id=owner_id,
                label_token=agent_token,
                referent_kind=NamingReferentKind.AGENT,
                delta=policy.conforming_agent,
                channel=NamingEvidenceChannel.OBSERVED,
                lineage_ref=f"tick-{tick}-agent-{agent.value}",
                tick=tick,
                policy=policy,
                seen=seen,
                candidate_kind=NamingReferentKind.AGENT,
                candidate_id=agent.value,
            )
        # Recurring colocated action: >=2 resolved agents incl owner share action.
        action_actors: dict[str, set[str]] = {}
        for index, occurrence in enumerate(observation.occurrences):
            if type(occurrence) is not ObservedOccurrence:
                continue
            kind = occurrence.kind
            if not isinstance(kind, str) or not kind:
                continue
            actor = _resolve_agent(identity, occurrence.actor_id)
            if actor is None:
                continue
            action_actors.setdefault(kind, set()).add(actor.value)
            if occurrence.kind in {"death", "die", "killed"} and location is not None:
                _mint_modifier(
                    drafts=drafts,
                    notices=notices,
                    owner_id=owner_id,
                    location_id=location.value,
                    tick=tick,
                    policy=policy,
                    seen=seen,
                    death=True,
                    ordinal=index,
                )
            ordinal = index
        for action_kind, actors in action_actors.items():
            if owner_id.value not in actors or len(actors) < 2 or location is None:
                continue
            referent = f"{action_kind}|{location.value}"
            token = _seed_token(
                owner_id, NamingReferentKind.RECURRING_EVENT, referent
            )
            _record_evidence(
                drafts=drafts,
                notices=notices,
                owner_id=owner_id,
                label_token=token,
                referent_kind=NamingReferentKind.RECURRING_EVENT,
                delta=policy.conforming_recurring_event,
                channel=NamingEvidenceChannel.OBSERVED,
                lineage_ref=f"tick-{tick}-gather-{action_kind}",
                tick=tick,
                policy=policy,
                seen=seen,
                candidate_kind=NamingReferentKind.RECURRING_EVENT,
                candidate_id=referent,
            )
    hazards = observation.hazard_kinds or ()
    if hazards:
        for hazard in hazards:
            if type(hazard) is not HazardKind:
                continue
            token = f"hazard_{hazard.value}"
            _record_evidence(
                drafts=drafts,
                notices=notices,
                owner_id=owner_id,
                label_token=token,
                referent_kind=NamingReferentKind.DANGEROUS_RESOURCE,
                delta=policy.conforming_dangerous_resource,
                channel=NamingEvidenceChannel.OBSERVED,
                lineage_ref=f"tick-{tick}-hazard-{hazard.value}",
                tick=tick,
                policy=policy,
                seen=seen,
                candidate_kind=NamingReferentKind.DANGEROUS_RESOURCE,
                candidate_id=hazard.value,
            )
        if location is not None:
            _mint_modifier(
                drafts=drafts,
                notices=notices,
                owner_id=owner_id,
                location_id=location.value,
                tick=tick,
                policy=policy,
                seen=seen,
                death=False,
                ordinal=ordinal,
            )
    depleting_kinds = {
        occurrence.kind
        for occurrence in observation.occurrences
        if isinstance(occurrence.kind, str)
        and occurrence.kind in {"take", "gather", "eat", "drink", "consume"}
        and occurrence.success is not False
    }
    if depleting_kinds:
        for resource in observation.resources:
            kind = resource.kind
            if type(kind) is not ResourceKind:
                continue
            token = f"hazard_{kind.value}"
            if not _LABEL_TOKEN_RE.fullmatch(token):
                continue
            _record_evidence(
                drafts=drafts,
                notices=notices,
                owner_id=owner_id,
                label_token=token,
                referent_kind=NamingReferentKind.DANGEROUS_RESOURCE,
                delta=policy.conforming_dangerous_resource,
                channel=NamingEvidenceChannel.OBSERVED,
                lineage_ref=f"tick-{tick}-resource-{kind.value}",
                tick=tick,
                policy=policy,
                seen=seen,
                candidate_kind=NamingReferentKind.DANGEROUS_RESOURCE,
                candidate_id=kind.value,
            )
    if cues is not None:
        for concept_id in cues.group_concept_ids:
            token = _seed_token(owner_id, NamingReferentKind.GROUP, concept_id)
            _record_evidence(
                drafts=drafts,
                notices=notices,
                owner_id=owner_id,
                label_token=token,
                referent_kind=NamingReferentKind.GROUP,
                delta=policy.conforming_group,
                channel=NamingEvidenceChannel.OBSERVED,
                lineage_ref=f"tick-{tick}-group-{concept_id[:16]}",
                tick=tick,
                policy=policy,
                seen=seen,
                candidate_kind=NamingReferentKind.GROUP,
                candidate_id=concept_id,
            )
        for action in cues.practice_action_kinds:
            token = _seed_token(
                owner_id,
                NamingReferentKind.SOCIAL_PRACTICE,
                action,
                action_kind=action,
            )
            _record_evidence(
                drafts=drafts,
                notices=notices,
                owner_id=owner_id,
                label_token=token,
                referent_kind=NamingReferentKind.SOCIAL_PRACTICE,
                delta=policy.conforming_social_practice,
                channel=NamingEvidenceChannel.OBSERVED,
                lineage_ref=f"tick-{tick}-practice-{action}",
                tick=tick,
                policy=policy,
                seen=seen,
                candidate_kind=NamingReferentKind.SOCIAL_PRACTICE,
                candidate_id=action,
            )


def _mint_modifier(
    *,
    drafts: list[_BindingDraft],
    notices: list[str],
    owner_id: AgentId,
    location_id: str,
    tick: int,
    policy: SemanticNamingPolicy,
    seen: set[tuple[str, str, str]],
    death: bool,
    ordinal: int,
) -> None:
    digest = stable8_digest(owner_id, NamingReferentKind.LOCATION, location_id)
    base_token = f"place_{digest}"
    dark_token = f"dark_{digest}"
    dead_token = f"dead_{digest}"
    base = _find_draft(
        drafts, label_token=base_token, referent_kind=NamingReferentKind.LOCATION
    )
    dark = _find_draft(
        drafts, label_token=dark_token, referent_kind=NamingReferentKind.LOCATION
    )
    active_base = base is not None and base.status is NamingStatus.ACTIVE
    active_dark = dark is not None and dark.status is NamingStatus.ACTIVE
    if not active_base and not active_dark:
        # Need an active location binding first; promote path may catch later ticks.
        if base is None or base.status is NamingStatus.CANDIDATE:
            return
    target = dark_token
    if death or active_dark or (active_base and death):
        if active_dark or (active_base and death):
            target = dead_token if (death or active_dark) else dark_token
        if death and (active_dark or active_base):
            target = dead_token
        elif not death:
            target = dark_token
    _record_evidence(
        drafts=drafts,
        notices=notices,
        owner_id=owner_id,
        label_token=target,
        referent_kind=NamingReferentKind.LOCATION,
        delta=policy.conforming_dangerous_resource,
        channel=NamingEvidenceChannel.OBSERVED,
        lineage_ref=f"tick-{tick}-mod-{target}-{ordinal}",
        tick=tick,
        policy=policy,
        seen=seen,
        candidate_kind=NamingReferentKind.LOCATION,
        candidate_id=location_id,
    )


def _apply_transmission(
    *,
    observation: Observation,
    identity: OwnerSafeSocialIdentity,
    drafts: list[_BindingDraft],
    notices: list[str],
    policy: SemanticNamingPolicy,
    seen: set[tuple[str, str, str]],
) -> None:
    owner_id = identity.owner_id
    tick = observation.tick
    for index, communication in enumerate(observation.communications):
        if type(communication) is not ObservedCommunication:
            continue
        if communication.listener_id != identity.owner_entity_id:
            continue
        speaker = _resolve_agent(identity, communication.speaker_id)
        if speaker is None:
            _notice(notices, "unresolved_entity")
            _log_drop("unresolved_entity")
            continue
        content = communication.utterance.content
        for relation in content.relations:
            predicate = getattr(relation, "predicate", None)
            subject = getattr(relation, "subject", None)
            obj = getattr(relation, "object", None)
            if predicate != "call" or not isinstance(subject, str):
                continue
            if not _LABEL_TOKEN_RE.fullmatch(subject):
                _notice(notices, "illegal_token")
                _log_drop("illegal_token")
                continue
            kind = NamingReferentKind.LOCATION
            if isinstance(obj, str):
                try:
                    kind = NamingReferentKind(obj)
                except ValueError:
                    kind = NamingReferentKind.LOCATION
            _record_evidence(
                drafts=drafts,
                notices=notices,
                owner_id=owner_id,
                label_token=subject,
                referent_kind=kind,
                delta=policy.transmission_delta,
                channel=NamingEvidenceChannel.COMMUNICATED,
                lineage_ref=_comm_lineage(tick, index, communication),
                tick=tick,
                policy=policy,
                seen=seen,
                actor_id=speaker,
                predicate="call",
                transmission=NamingTransmission.COMMUNICATED,
                allow_empty_candidates=True,
            )
            _LOG.debug(
                "naming_transmission_applied owner_id=%s tick=%s channel=%s",
                owner_id.value,
                tick,
                "communicated",
            )


def _memory_tokens(trace: object) -> tuple[set[str], list[tuple[str, str, str]]]:
    concepts: set[str] = set()
    for item in getattr(trace, "concepts", ()) or ():
        token = getattr(item, "concept", None)
        if isinstance(token, str) and token:
            concepts.add(token)
        elif isinstance(item, str):
            concepts.add(item)
    relations: list[tuple[str, str, str]] = []
    for item in getattr(trace, "relations", ()) or ():
        subject = getattr(item, "subject", None)
        predicate = getattr(item, "predicate", None)
        obj = getattr(item, "object", None)
        if (
            isinstance(subject, str)
            and isinstance(predicate, str)
            and isinstance(obj, str)
        ):
            relations.append((subject, predicate, obj))
    return concepts, relations


def _apply_memory_reinforcement(
    *,
    memories: Sequence[object] | None,
    drafts: list[_BindingDraft],
    notices: list[str],
    owner_id: AgentId,
    tick: int,
    policy: SemanticNamingPolicy,
) -> None:
    if not memories or not drafts:
        if memories and not drafts:
            _notice(notices, "memory_no_match")
            _log_drop("memory_no_match")
        return
    remembered_seen: set[tuple[str, str]] = set()
    by_token = {
        (draft.label_token, draft.referent_kind): draft for draft in drafts
    }
    matched_any = False
    for trace in memories:
        if getattr(trace, "forgotten_at_tick", None) is not None:
            continue
        expires = getattr(trace, "expires_at_tick", None)
        if expires is not None and isinstance(expires, int) and expires <= tick:
            continue
        memory_id = getattr(getattr(trace, "memory_id", None), "value", None)
        if not isinstance(memory_id, str) or not memory_id:
            continue
        concepts, relations = _memory_tokens(trace)
        matched: list[_BindingDraft] = []
        for (token, kind), draft in by_token.items():
            if token in concepts:
                matched.append(draft)
                continue
            for subject, predicate, obj in relations:
                if predicate != "call":
                    continue
                if subject == token or obj == token or obj == kind.value:
                    matched.append(draft)
                    break
        for draft in matched:
            binding_id = label_binding_id(
                owner_id, draft.referent_kind, draft.label_token
            )
            dedup = (binding_id, memory_id)
            if dedup in remembered_seen:
                continue
            remembered_seen.add(dedup)
            if len(draft.evidence) >= policy.max_evidence:
                _notice(notices, "cap_exceeded")
                _log_drop("cap_exceeded")
                continue
            before = draft.strength
            draft.strength = _apply_delta(before, policy.remembered_delta)
            draft.touched = True
            if draft.last_tick is None or tick > draft.last_tick:
                draft.last_tick = tick
            ordinal = len(draft.evidence)
            draft.evidence.append(
                NamingEvidenceItem(
                    evidence_id=naming_evidence_id(
                        binding_id,
                        ordinal,
                        NamingEvidenceChannel.REMEMBERED,
                        memory_id,
                    ),
                    ordinal=ordinal,
                    channel=NamingEvidenceChannel.REMEMBERED,
                    lineage_ref=memory_id,
                    tick=tick,
                )
            )
            matched_any = True
            _LOG.debug(
                "naming_memory_reinforced owner_id=%s tick=%s",
                owner_id.value,
                tick,
            )
            _LOG.debug(
                "naming_binding_applied owner_id=%s tick=%s sign=%s",
                owner_id.value,
                tick,
                _sign(before, draft.strength),
            )
    if not matched_any:
        _notice(notices, "memory_no_match")
        _log_drop("memory_no_match")


def _promote(
    drafts: list[_BindingDraft],
    owner_id: AgentId,
    tick: int,
    policy: SemanticNamingPolicy,
    notices: list[str],
) -> None:
    for draft in drafts:
        if draft.status is not NamingStatus.CANDIDATE:
            continue
        if draft.merged_into is not None:
            continue
        top = _top_candidate(draft)
        if top is None:
            _notice(notices, "empty_candidates")
            _LOG.warning("naming_binding_withheld reason=%s", "empty_candidates")
            continue
        if draft.evidence_count < policy.promotion_count:
            _notice(notices, "below_count")
            _LOG.warning("naming_binding_withheld reason=%s", "below_count")
            continue
        if top.confidence < policy.active_strength:
            _notice(notices, "candidate")
            _LOG.warning("naming_binding_withheld reason=%s", "candidate")
            continue
        if draft.strength < policy.active_strength:
            _notice(notices, "below_strength")
            _LOG.warning("naming_binding_withheld reason=%s", "below_strength")
            continue
        draft.status = NamingStatus.ACTIVE
        _LOG.debug(
            "naming_binding_promoted owner_id=%s tick=%s status=%s",
            owner_id.value,
            tick,
            draft.status.value,
        )


def _link_competitors(
    drafts: list[_BindingDraft],
    policy: SemanticNamingPolicy,
) -> None:
    active = [
        draft
        for draft in drafts
        if draft.status is NamingStatus.ACTIVE
        and draft.merged_into is None
        and _top_candidate(draft) is not None
    ]
    for draft in active:
        top = _top_candidate(draft)
        assert top is not None
        competitors: list[str] = []
        for other in active:
            if other is draft:
                continue
            other_top = _top_candidate(other)
            if other_top is None:
                continue
            if (
                other_top.kind is top.kind
                and other_top.entity_id == top.entity_id
            ):
                competitors.append(
                    label_binding_id(
                        # owner filled later in freeze; store token-kind pair via temp
                        AgentId("tmp"),
                        other.referent_kind,
                        other.label_token,
                    )
                    if False
                    else other.label_token
                )
        # Store competitor binding ids after we know owner in freeze; keep tokens now.
        draft.competing_label_ids = competitors[: policy.max_competitors]


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left and not right:
        return 0.0
    union = left | right
    if not union:
        return 0.0
    return len(left & right) / len(union)


def _merge(
    drafts: list[_BindingDraft],
    owner_id: AgentId,
    tick: int,
    policy: SemanticNamingPolicy,
) -> None:
    active = [
        draft
        for draft in drafts
        if draft.status is NamingStatus.ACTIVE
        and draft.merged_into is None
        and draft.candidates
        and draft.strength >= policy.active_strength
    ]
    active.sort(key=lambda item: (-item.strength, item.label_token))
    merge_counts: dict[str, int] = {}
    for index, left in enumerate(active):
        left_ids = {item.entity_id for item in left.candidates}
        for right in active[index + 1 :]:
            if right.merged_into is not None:
                continue
            if left.referent_kind is not right.referent_kind:
                continue
            right_ids = {item.entity_id for item in right.candidates}
            if _jaccard(left_ids, right_ids) < policy.merge_jaccard:
                continue
            if right.strength < policy.active_strength:
                continue
            stronger, weaker = (
                (left, right) if left.strength >= right.strength else (right, left)
            )
            strong_id = label_binding_id(
                owner_id, stronger.referent_kind, stronger.label_token
            )
            if merge_counts.get(strong_id, 0) >= policy.max_merge_fan_in:
                continue
            weaker.status = NamingStatus.RETIRED
            weaker.merged_into = strong_id
            merge_counts[strong_id] = merge_counts.get(strong_id, 0) + 1
            # Copy residual evidence if room.
            for item in weaker.evidence:
                if len(stronger.evidence) >= policy.max_evidence:
                    break
                seen_ids = {entry.evidence_id for entry in stronger.evidence}
                if item.evidence_id in seen_ids:
                    continue
                stronger.evidence.append(item)
            stronger.touched = True
            _LOG.debug(
                "naming_labels_merged owner_id=%s tick=%s status=%s",
                owner_id.value,
                tick,
                weaker.status.value,
            )


def _meaning_shift(
    drafts: list[_BindingDraft],
    owner_id: AgentId,
    tick: int,
    policy: SemanticNamingPolicy,
) -> None:
    for draft in drafts:
        if draft.status is not NamingStatus.ACTIVE or len(draft.candidates) < 2:
            draft.meaning_shift_streak = 0
            continue
        ordered = sorted(
            draft.candidates, key=lambda item: (-item.confidence, item.entity_id)
        )
        top, second = ordered[0], ordered[1]
        lead = _quantize(top.confidence - second.confidence)
        # pending_top_id tracks the alternate leader when lead flips.
        if draft.pending_top_id is None:
            draft.pending_top_id = top.entity_id
        if second.confidence - (
            next(
                (
                    item.confidence
                    for item in draft.candidates
                    if item.entity_id == draft.pending_top_id
                ),
                top.confidence,
            )
        ) >= policy.meaning_shift_lead or (
            top.entity_id != draft.pending_top_id
            and lead >= 0.0
            and (top.confidence - second.confidence) >= 0.0
            and second.entity_id == draft.pending_top_id
            and top.confidence - second.confidence >= policy.meaning_shift_lead
        ):
            # Alternate candidate leads current pending by >= 0.20
            if top.entity_id != draft.pending_top_id and (
                top.confidence
                - next(
                    (
                        c.confidence
                        for c in draft.candidates
                        if c.entity_id == draft.pending_top_id
                    ),
                    0.0,
                )
                >= policy.meaning_shift_lead
            ):
                draft.meaning_shift_streak += 1
                if draft.meaning_shift_streak >= policy.meaning_shift_ticks:
                    draft.pending_top_id = top.entity_id
                    draft.sense_revision += 1
                    draft.meaning_shift_streak = 0
                    draft.candidates = tuple(ordered)  # type: ignore[assignment]
                    draft.candidates = list(ordered)
                    _LOG.debug(
                        "naming_meaning_shifted owner_id=%s tick=%s status=%s",
                        owner_id.value,
                        tick,
                        draft.status.value,
                    )
            else:
                draft.meaning_shift_streak = 0
                draft.pending_top_id = top.entity_id
        else:
            draft.meaning_shift_streak = 0
            draft.pending_top_id = top.entity_id


def _decay(
    drafts: list[_BindingDraft],
    owner_id: AgentId,
    tick: int,
    policy: SemanticNamingPolicy,
) -> None:
    for draft in drafts:
        if draft.status is NamingStatus.RETIRED:
            continue
        if draft.touched:
            continue
        before = draft.strength
        draft.strength = _apply_delta(before, -policy.decay)
        if draft.strength < policy.retire_strength:
            draft.status = NamingStatus.RETIRED
            _LOG.debug(
                "naming_binding_retired owner_id=%s tick=%s status=%s",
                owner_id.value,
                tick,
                draft.status.value,
            )


def _freeze(
    owner_id: AgentId,
    drafts: list[_BindingDraft],
    notices: list[str],
) -> TerminologyLedger:
    # Resolve competing ids now that owner is known.
    token_to_id: dict[tuple[str, NamingReferentKind], str] = {}
    for draft in drafts:
        token_to_id[(draft.label_token, draft.referent_kind)] = label_binding_id(
            owner_id, draft.referent_kind, draft.label_token
        )
    bindings: list[LabelBinding] = []
    for draft in drafts:
        competitor_ids: list[str] = []
        top = _top_candidate(draft)
        if (
            draft.status is NamingStatus.ACTIVE
            and top is not None
            and draft.merged_into is None
        ):
            for other in drafts:
                if other is draft or other.status is not NamingStatus.ACTIVE:
                    continue
                if other.merged_into is not None:
                    continue
                other_top = _top_candidate(other)
                if other_top is None:
                    continue
                if (
                    other_top.kind is top.kind
                    and other_top.entity_id == top.entity_id
                ):
                    competitor_ids.append(
                        token_to_id[(other.label_token, other.referent_kind)]
                    )
        competitor_ids = competitor_ids[:4]
        bindings.append(
            LabelBinding(
                binding_id=token_to_id[(draft.label_token, draft.referent_kind)],
                owner_id=owner_id,
                label_token=draft.label_token,
                referent_kind=draft.referent_kind,
                status=draft.status,
                strength=draft.strength,
                candidates=tuple(draft.candidates),
                evidence_count=draft.evidence_count,
                first_tick=draft.first_tick,
                last_tick=draft.last_tick,
                transmission=draft.transmission,
                sense_revision=draft.sense_revision,
                merged_into=draft.merged_into,
                competing_label_ids=tuple(competitor_ids),
                evidence=tuple(draft.evidence),
                last_utterance_tick=draft.last_utterance_tick,
                meaning_shift_streak=draft.meaning_shift_streak,
                notices=tuple(draft.notices),
            )
        )
    return TerminologyLedger(
        owner_id=owner_id,
        bindings=tuple(bindings),
        notices=tuple(notices),
    )


def apply_naming_update(
    observation: object,
    identity: object,
    previous: object = None,
    memories: Sequence[object] | None = None,
    cues: NamingCueSummary | None = None,
    policy: SemanticNamingPolicy | None = None,
) -> TerminologyLedger:
    """Apply one tick of naming evidence for a single owner.

    Disabled callers do not call this function. Passing world authority or a
    metric document raises ``TypeError``. Memory reinforces existing bindings
    only and never mints a new binding.
    """
    _LOG.debug(
        "apply_naming_update owner_id=%s tick=%s",
        getattr(getattr(identity, "owner_id", None), "value", None),
        getattr(observation, "tick", None),
    )
    for value in (observation, identity, previous, policy, memories, cues):
        _reject_forbidden(value)
    if memories is not None:
        for item in memories:
            _reject_forbidden(item)
    if type(observation) is not Observation:
        raise TypeError("observation must be Observation")
    if type(identity) is not OwnerSafeSocialIdentity:
        raise TypeError("identity must be OwnerSafeSocialIdentity")
    if previous is not None and type(previous) is not TerminologyLedger:
        raise TypeError("previous must be TerminologyLedger or None")
    if cues is not None and type(cues) is not NamingCueSummary:
        raise TypeError("cues must be NamingCueSummary or None")
    active_policy = default_semantic_naming_policy() if policy is None else policy
    if type(active_policy) is not SemanticNamingPolicy:
        raise TypeError("policy must be SemanticNamingPolicy")
    owner_id = identity.owner_id
    tick = observation.tick
    drafts = _drafts_from(previous, owner_id)
    notices: list[str] = []
    seen: set[tuple[str, str, str]] = set()
    _apply_observation_cues(
        observation=observation,
        identity=identity,
        drafts=drafts,
        notices=notices,
        policy=active_policy,
        cues=cues,
        seen=seen,
    )
    _apply_transmission(
        observation=observation,
        identity=identity,
        drafts=drafts,
        notices=notices,
        policy=active_policy,
        seen=seen,
    )
    _apply_memory_reinforcement(
        memories=memories,
        drafts=drafts,
        notices=notices,
        owner_id=owner_id,
        tick=tick,
        policy=active_policy,
    )
    _promote(drafts, owner_id, tick, active_policy, notices)
    _link_competitors(drafts, active_policy)
    _meaning_shift(drafts, owner_id, tick, active_policy)
    _merge(drafts, owner_id, tick, active_policy)
    _decay(drafts, owner_id, tick, active_policy)
    ledger = _freeze(owner_id, drafts, notices)
    _LOG.info(
        "naming_ledger_updated owner_id=%s binding_count=%s",
        owner_id.value,
        len(ledger.bindings),
    )
    return ledger


def _direction_value(future: object) -> str | None:
    from agents.cognition.models import ActionDirection

    direction = getattr(future, "direction", None)
    if type(direction) is ActionDirection:
        return direction.value
    value = getattr(direction, "value", None)
    return value if isinstance(value, str) else None


def _future_id(future: object) -> str | None:
    value = getattr(future, "future_id", None)
    return value if isinstance(value, str) and value else None


def naming_communicate_penalties(
    ledger: object,
    futures: Sequence[object],
    *,
    tick: int,
    mode: object | None = None,
    policy: SemanticNamingPolicy | None = None,
) -> Mapping[str, float]:
    """Prefer an existing COMMUNICATE future for a speakable label."""
    _reject_forbidden(ledger)
    if mode is not None:
        from agents.cognition.configuration import CognitionSemanticNamingMode

        if mode is not CognitionSemanticNamingMode.DETERMINISTIC:
            return {}
    if ledger is None or type(ledger) is not TerminologyLedger:
        return {}
    active_policy = default_semantic_naming_policy() if policy is None else policy
    if type(active_policy) is not SemanticNamingPolicy:
        raise TypeError("policy must be SemanticNamingPolicy")
    communicate_ids = [
        future_id
        for future in futures
        if (future_id := _future_id(future)) is not None
        and _direction_value(future) == "communicate"
    ]
    if not communicate_ids:
        _LOG.warning("naming_response_withheld reason=%s", "no_candidate")
        return {}
    speakable = False
    for binding in ledger.bindings:
        if binding.status is NamingStatus.CANDIDATE:
            _LOG.warning("naming_response_withheld reason=%s", "candidate_only")
            continue
        if binding.status is not NamingStatus.ACTIVE:
            continue
        if not binding.candidates:
            _LOG.warning("naming_response_withheld reason=%s", "empty_candidates")
            continue
        if binding.strength < active_policy.active_strength:
            continue
        if (
            binding.last_utterance_tick is not None
            and tick - binding.last_utterance_tick < active_policy.utterance_interval
        ):
            _LOG.warning("naming_response_withheld reason=%s", "utterance_interval")
            continue
        speakable = True
        break
    if not speakable:
        return {}
    penalties: dict[str, float] = {}
    for future in futures:
        future_id = _future_id(future)
        if future_id is None or future_id in communicate_ids:
            continue
        total = _apply_delta(penalties.get(future_id, 0.0), active_policy.penalty)
        if total < 0.0:
            raise _fail("penalty", "negative_penalty")
        penalties[future_id] = total
    _LOG.debug(
        "naming_penalty_applied future_count=%s",
        len(penalties),
    )
    _LOG.debug(
        "naming_response_selected owner_id=%s tick=%s response=%s",
        ledger.owner_id.value,
        tick,
        "communicate",
    )
    return penalties


def naming_communicate_utterance(
    command: object,
    *,
    owner_id: AgentId,
    tick: int,
    observation: Observation,
    identity: OwnerSafeSocialIdentity | None,
    ledger: object | None,
    mode: object | None,
) -> object:
    """Stamp an existing Talk command with one naming relation recipe."""
    from agents.cognition.configuration import CognitionSemanticNamingMode
    from world.actions import Talk
    from world.communications import (
        CommunicationRelation,
        CommunicationSourceBasis,
        origin_utterance,
    )

    if mode is not CognitionSemanticNamingMode.DETERMINISTIC:
        return command
    if type(observation) is not Observation:
        return command
    if type(command) is not Talk:
        return command
    if type(ledger) is not TerminologyLedger or not ledger.bindings:
        return command
    if identity is None:
        return command
    if observation.tick != tick:
        return command
    policy = default_semantic_naming_policy()
    chosen: LabelBinding | None = None
    for binding in ledger.bindings:
        if binding.status is not NamingStatus.ACTIVE:
            continue
        if binding.strength < policy.active_strength:
            continue
        if not binding.candidates:
            continue
        if (
            binding.last_utterance_tick is not None
            and tick - binding.last_utterance_tick < policy.utterance_interval
        ):
            continue
        if chosen is None or binding.strength > chosen.strength:
            chosen = binding
    if chosen is None:
        return command
    utterance = origin_utterance(
        text="call",
        speaker_id=identity.owner_entity_id,
        communication_id=(
            f"semantic-naming-{owner_id.value}-{tick}-{chosen.label_token}"
        ),
        relations=(
            CommunicationRelation(
                subject=chosen.label_token,
                predicate="call",
                object=chosen.referent_kind.value,
            ),
        ),
        source_basis=CommunicationSourceBasis.UNREFERENCED,
    )
    _LOG.debug(
        "naming_response_selected owner_id=%s tick=%s response=%s",
        owner_id.value,
        tick,
        "communicate",
    )
    return Talk(recipient_id=command.recipient_id, utterance=utterance)
