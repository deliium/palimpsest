"""Owner-scoped bounded compositional symbols over a terminology ledger.

A composition combines exactly two label tokens that are already active in one
owner's ``TerminologyLedger``. It is speaker testimony about symbol co-use,
never an objective world fact and never a shared lexicon. This module carries
no world authority: updates read one owner's ``Observation``, identity,
previous ``SymbolicLedger``, and already-loaded memories. They never read
``WorldState``, ``WorldEvent``, another owner's ledger, or analysis documents.
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
from agents.cognition.semantic_naming import (
    LabelBinding,
    NamingReferentKind,
    NamingStatus,
    TerminologyLedger,
    require_owner_semantic_naming,
)
from agents.models import AgentId
from world.identifiers import require_exact_nonneg_int
from world.observations import Observation, ObservedCommunication, ObservedOccurrence

_LOG: Final[logging.Logger] = logging.getLogger("agents.cognition.symbolic_language")

SYMBOLIC_LANGUAGE_POLICY_VERSION: Final[str] = "symbolic-language.v1"
_QUANTUM: Final[Decimal] = Decimal("0.000001")
_ACTIVE_STRENGTH: Final[float] = 0.40
_RETIRE_STRENGTH: Final[float] = 0.20
_DECAY: Final[float] = 0.05
_OBSERVED_DELTA: Final[float] = 0.12
_COMMUNICATED_DELTA: Final[float] = 0.10
_REMEMBERED_DELTA: Final[float] = 0.08
_SELF_USE_DELTA: Final[float] = 0.06
_PROMOTION_COUNT: Final[int] = 3
_MAX_COMPOSITIONS: Final[int] = 8
_MAX_EVIDENCE: Final[int] = 24
_MAX_PER_MESSAGE: Final[int] = 2
_MAX_INTERPRETATIONS: Final[int] = 32
_MEANING_SHIFT_TICKS: Final[int] = 6
_UTTERANCE_INTERVAL: Final[int] = 4
_LABEL_TOKEN_RE: Final[re.Pattern[str]] = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
_HEX: Final[frozenset[str]] = frozenset("0123456789abcdef")
_OPERATORS: Final[frozenset[str]] = frozenset({"attributive", "relational"})
_NOTICE_REASONS: Final[frozenset[str]] = frozenset(
    {
        "cap_exceeded",
        "constituent_missing",
        "constituent_inactive",
        "unsupported_predicate",
        "illegal_token",
        "owner_mismatch",
        "no_candidate",
        "candidate_only",
        "below_count",
        "below_strength",
        "utterance_interval",
        "empty_candidates",
        "memory_no_match",
        "duplicate_composition",
        "invalid_token",
        "forbidden_type",
        "unresolved_entity",
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
        "TerminologyLedger",
        "LabelBinding",
        "SymbolicLedger",
        "SymbolicComposition",
    }
)
_FORBIDDEN_CUE_TYPE_NAMES: Final[frozenset[str]] = frozenset(
    {
        "GroupLedger",
        "NormLedger",
        "ConventionLedger",
        "ArtifactInterpretationLedger",
        "TerminologyLedger",
        "LabelBinding",
        "SymbolicLedger",
        "SymbolicComposition",
    }
)

__all__ = [
    "SYMBOLIC_LANGUAGE_POLICY_VERSION",
    "SymbolicComposition",
    "SymbolicCompositionKind",
    "SymbolicCueSummary",
    "SymbolicEvidenceChannel",
    "SymbolicEvidenceItem",
    "SymbolicInterpretation",
    "SymbolicLanguagePolicy",
    "SymbolicLedger",
    "SymbolicParseOutcome",
    "SymbolicReferentHypothesis",
    "SymbolicStatus",
    "SymbolicStrengthBand",
    "SymbolicUtterancePlan",
    "apply_symbolic_update",
    "composition_evidence_id",
    "composition_id",
    "default_symbolic_language_policy",
    "empty_symbolic_ledger",
    "require_owner_symbolic_language",
    "symbolic_communicate_utterance",
    "symbolic_strength_band",
    "symbolic_usage_update",
]


class SymbolicCompositionKind(StrEnum):
    """Closed binary composition operator."""

    ATTRIBUTIVE = "attributive"
    RELATIONAL = "relational"


class SymbolicStatus(StrEnum):
    """Closed lifecycle for one owner's composition."""

    CANDIDATE = "candidate"
    ACTIVE = "active"
    RETIRED = "retired"


class SymbolicEvidenceChannel(StrEnum):
    """Closed evidence channel for one composition item."""

    OBSERVED = "observed"
    COMMUNICATED = "communicated"
    REMEMBERED = "remembered"
    SELF_USE = "self_use"


class SymbolicParseOutcome(StrEnum):
    """Closed structural parse result for one delivered composition."""

    PARSED = "parsed"
    PARTIAL = "partial"
    UNRESOLVED = "unresolved"
    IGNORED = "ignored"


class SymbolicStrengthBand(StrEnum):
    """Closed researcher-facing strength band."""

    CANDIDATE = "candidate"
    LOW = "low"
    MID = "mid"
    HIGH = "high"


def _fail(field_name: str, code: str) -> ValueError:
    _LOG.error(
        "symbolic_validation_failed field=%s reason_code=%s",
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
    if name in _FORBIDDEN_TYPES or module.startswith("analysis"):
        raise TypeError(f"{name}: forbidden_input")
    if isinstance(value, Mapping):
        keys = {str(key) for key in value}
        if "metric_family" in keys or "availability" in keys:
            raise TypeError(f"{name}: forbidden_input")


def composition_id(
    owner_id: AgentId,
    kind: SymbolicCompositionKind,
    parts: Sequence[str],
) -> str:
    """Owner-scoped deterministic id for (owner, kind, ordered parts)."""
    if type(owner_id) is not AgentId:
        raise _fail("owner_id", "invalid_type")
    if type(kind) is not SymbolicCompositionKind:
        raise _fail("kind", "unknown_kind")
    checked = _require_parts(parts)
    material = f"{owner_id.value}|{kind.value}|{checked[0]}|{checked[1]}"
    return _sha256_hex(material)


def composition_evidence_id(
    composition_id_value: str,
    ordinal: int,
    channel: SymbolicEvidenceChannel,
    lineage_ref: str,
) -> str:
    """sha256 of composition id, ordinal, channel, and lineage ref."""
    head = _require_hex_id("composition_id", composition_id_value)
    if isinstance(ordinal, bool) or type(ordinal) is not int or ordinal < 0:
        raise _fail("ordinal", "invalid_type")
    if type(channel) is not SymbolicEvidenceChannel:
        raise _fail("channel", "unknown_channel")
    if not isinstance(lineage_ref, str) or not lineage_ref:
        raise _fail("lineage_ref", "invalid_type")
    return _sha256_hex(f"{head}|{ordinal}|{channel.value}|{lineage_ref}")


def _require_parts(values: object) -> tuple[str, str]:
    items = _require_tuple("parts", values)
    if len(items) != 2:
        raise _fail("parts", "invalid_arity")
    first = _require_label_token("parts[0]", items[0])
    second = _require_label_token("parts[1]", items[1])
    if first == second:
        raise _fail("parts", "self_reference")
    return first, second


def symbolic_strength_band(
    status: SymbolicStatus, strength: float
) -> SymbolicStrengthBand:
    """Closed overlay band from status and quantized strength."""
    if type(status) is not SymbolicStatus:
        raise _fail("status", "unknown_status")
    quantized = _quantize(_finite("strength", strength))
    if status is SymbolicStatus.CANDIDATE:
        return SymbolicStrengthBand.CANDIDATE
    if quantized < 0.40:
        return SymbolicStrengthBand.LOW
    if quantized < 0.70:
        return SymbolicStrengthBand.MID
    return SymbolicStrengthBand.HIGH


@dataclass(frozen=True, slots=True)
class SymbolicReferentHypothesis:
    """Owner-local guess about what a composition refers to."""

    referent_kind: NamingReferentKind
    confidence: float

    def __post_init__(self) -> None:
        if type(self.referent_kind) is not NamingReferentKind:
            raise _fail("hypothesis.referent_kind", "unknown_kind")
        quantized = _quantize(_finite("hypothesis.confidence", self.confidence))
        if quantized < 0.0 or quantized > 1.0:
            raise _fail("hypothesis.confidence", "out_of_range")
        object.__setattr__(self, "confidence", quantized)


@dataclass(frozen=True, slots=True)
class SymbolicEvidenceItem:
    """One observed, communicated, remembered, or self-use item."""

    evidence_id: str
    ordinal: int
    channel: SymbolicEvidenceChannel
    lineage_ref: str
    tick: int
    actor_id: AgentId | None = None
    speaker_id: AgentId | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "evidence_id", _require_hex_id("evidence_id", self.evidence_id)
        )
        if isinstance(self.ordinal, bool) or type(self.ordinal) is not int:
            raise _fail("evidence.ordinal", "invalid_type")
        if self.ordinal < 0:
            raise _fail("evidence.ordinal", "out_of_range")
        if type(self.channel) is not SymbolicEvidenceChannel:
            raise _fail("evidence.channel", "unknown_channel")
        if not isinstance(self.lineage_ref, str) or not self.lineage_ref:
            raise _fail("evidence.lineage_ref", "invalid_type")
        object.__setattr__(
            self,
            "tick",
            require_exact_nonneg_int("SymbolicEvidenceItem.tick", self.tick),
        )
        if self.actor_id is not None and type(self.actor_id) is not AgentId:
            raise _fail("evidence.actor_id", "invalid_type")
        if self.speaker_id is not None and type(self.speaker_id) is not AgentId:
            raise _fail("evidence.speaker_id", "invalid_type")


@dataclass(frozen=True, slots=True)
class SymbolicComposition:
    """One owner's private binary composition of two active labels."""

    composition_id: str
    owner_id: AgentId
    kind: SymbolicCompositionKind
    parts: tuple[str, str]
    referent_hypothesis: SymbolicReferentHypothesis | None = None
    status: SymbolicStatus = SymbolicStatus.CANDIDATE
    strength: float = 0.0
    evidence_count: int = 0
    usage_count: int = 0
    first_tick: int | None = None
    last_tick: int | None = None
    last_utterance_tick: int | None = None
    sense_revision: int = 0
    notices: tuple[str, ...] = ()
    evidence: tuple[SymbolicEvidenceItem, ...] = ()
    pending_referent_kind: NamingReferentKind | None = None
    meaning_shift_streak: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "composition_id",
            _require_hex_id("composition_id", self.composition_id),
        )
        if type(self.owner_id) is not AgentId:
            raise _fail("owner_id", "invalid_type")
        if type(self.kind) is not SymbolicCompositionKind:
            raise _fail("kind", "unknown_kind")
        parts = _require_parts(self.parts)
        object.__setattr__(self, "parts", parts)
        if self.referent_hypothesis is not None:
            if type(self.referent_hypothesis) is not SymbolicReferentHypothesis:
                raise _fail("referent_hypothesis", "invalid_type")
        if type(self.status) is not SymbolicStatus:
            raise _fail("status", "unknown_status")
        quantized = _quantize(_finite("strength", self.strength))
        if quantized < 0.0 or quantized > 1.0:
            raise _fail("strength", "out_of_range")
        object.__setattr__(self, "strength", quantized)
        for name in ("evidence_count", "usage_count", "sense_revision"):
            value = getattr(self, name)
            if isinstance(value, bool) or type(value) is not int or value < 0:
                raise _fail(name, "invalid_type")
        for name in ("first_tick", "last_tick", "last_utterance_tick"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(
                    self,
                    name,
                    require_exact_nonneg_int(f"SymbolicComposition.{name}", value),
                )
        if self.first_tick is not None and self.last_tick is not None:
            if self.last_tick < self.first_tick:
                raise _fail("last_tick", "before_first_tick")
        if (
            isinstance(self.meaning_shift_streak, bool)
            or type(self.meaning_shift_streak) is not int
            or self.meaning_shift_streak < 0
        ):
            raise _fail("meaning_shift_streak", "invalid_type")
        if self.pending_referent_kind is not None:
            if type(self.pending_referent_kind) is not NamingReferentKind:
                raise _fail("pending_referent_kind", "unknown_kind")
        observed: list[SymbolicEvidenceItem] = []
        seen_ids: set[str] = set()
        for item in _require_tuple("evidence", self.evidence):
            if type(item) is not SymbolicEvidenceItem:
                raise _fail("evidence", "invalid_type")
            if item.evidence_id in seen_ids:
                raise _fail("evidence", "duplicate_evidence")
            seen_ids.add(item.evidence_id)
            observed.append(item)
        if len(observed) > _MAX_EVIDENCE:
            raise _fail("evidence", "cap_exceeded")
        object.__setattr__(self, "evidence", tuple(observed))
        checked_notices: list[str] = []
        for item in _require_tuple("notices", self.notices):
            if not isinstance(item, str) or item not in _NOTICE_REASONS:
                raise _fail("notices", "invalid_notice")
            if item not in checked_notices:
                checked_notices.append(item)
        object.__setattr__(self, "notices", tuple(checked_notices))
        expected = composition_id(self.owner_id, self.kind, parts)
        if self.composition_id != expected:
            raise _fail("composition_id", "id_mismatch")


@dataclass(frozen=True, slots=True)
class SymbolicInterpretation:
    """One listener-side structural parse outcome."""

    owner_id: AgentId
    message_id: str
    outcome: SymbolicParseOutcome
    composition_id: str
    tick: int

    def __post_init__(self) -> None:
        if type(self.owner_id) is not AgentId:
            raise _fail("interpretation.owner_id", "invalid_type")
        if not isinstance(self.message_id, str) or not self.message_id:
            raise _fail("interpretation.message_id", "invalid_type")
        if type(self.outcome) is not SymbolicParseOutcome:
            raise _fail("interpretation.outcome", "unknown_outcome")
        object.__setattr__(
            self,
            "composition_id",
            _require_hex_id("interpretation.composition_id", self.composition_id),
        )
        object.__setattr__(
            self,
            "tick",
            require_exact_nonneg_int("SymbolicInterpretation.tick", self.tick),
        )


@dataclass(frozen=True, slots=True)
class SymbolicUtterancePlan:
    """Ordered composition ids selected for one utterance."""

    composition_ids: tuple[str, ...] = ()
    created_tick: int | None = None

    def __post_init__(self) -> None:
        ids = _require_tuple("composition_ids", self.composition_ids)
        if len(ids) > _MAX_PER_MESSAGE:
            raise _fail("composition_ids", "cap_exceeded")
        checked: list[str] = []
        seen: set[str] = set()
        for item in ids:
            head = _require_hex_id("composition_ids", item)
            if head in seen:
                raise _fail("composition_ids", "duplicate_composition")
            seen.add(head)
            checked.append(head)
        object.__setattr__(self, "composition_ids", tuple(checked))
        if self.created_tick is not None:
            object.__setattr__(
                self,
                "created_tick",
                require_exact_nonneg_int(
                    "SymbolicUtterancePlan.created_tick", self.created_tick
                ),
            )


@dataclass(frozen=True, slots=True)
class SymbolicCueSummary:
    """Closed bag of opaque observed entity keys built by CognitiveLoop."""

    observed_entity_keys: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        checked: list[str] = []
        for item in _require_tuple("observed_entity_keys", self.observed_entity_keys):
            if type(item).__name__ in _FORBIDDEN_CUE_TYPE_NAMES:
                raise TypeError("SymbolicCueSummary: forbidden_type")
            if not isinstance(item, str) or not item:
                raise _fail("observed_entity_keys", "invalid_token")
            checked.append(item)
        object.__setattr__(self, "observed_entity_keys", tuple(dict.fromkeys(checked)))


@dataclass(frozen=True, slots=True)
class SymbolicLedger:
    """Private compositions for one owner. ``None`` means the mode is off."""

    owner_id: AgentId
    compositions: tuple[SymbolicComposition, ...] = ()
    interpretations: tuple[SymbolicInterpretation, ...] = ()
    notices: tuple[str, ...] = ()
    utterance_plans: tuple[SymbolicUtterancePlan, ...] = ()
    policy_version: str = SYMBOLIC_LANGUAGE_POLICY_VERSION

    def __post_init__(self) -> None:
        if type(self.owner_id) is not AgentId:
            raise _fail("owner_id", "invalid_type")
        if self.policy_version != SYMBOLIC_LANGUAGE_POLICY_VERSION:
            raise _fail("policy_version", "unsupported_policy")
        checked: list[SymbolicComposition] = []
        seen: set[str] = set()
        for item in _require_tuple("compositions", self.compositions):
            if type(item) is not SymbolicComposition:
                raise _fail("compositions", "invalid_type")
            if item.owner_id != self.owner_id:
                raise _fail("compositions.owner_id", "owner_mismatch")
            if item.composition_id in seen:
                raise _fail("compositions", "duplicate_composition")
            seen.add(item.composition_id)
            checked.append(item)
        if len(checked) > _MAX_COMPOSITIONS:
            raise _fail("compositions", "cap_exceeded")
        checked_interps: list[SymbolicInterpretation] = []
        for item in _require_tuple("interpretations", self.interpretations):
            if type(item) is not SymbolicInterpretation:
                raise _fail("interpretations", "invalid_type")
            if item.owner_id != self.owner_id:
                raise _fail("interpretations.owner_id", "owner_mismatch")
            checked_interps.append(item)
        if len(checked_interps) > _MAX_INTERPRETATIONS:
            raise _fail("interpretations", "cap_exceeded")
        checked_notices: list[str] = []
        for item in _require_tuple("notices", self.notices):
            if not isinstance(item, str) or item not in _NOTICE_REASONS:
                raise _fail("notices", "invalid_notice")
            if item not in checked_notices:
                checked_notices.append(item)
        plans: list[SymbolicUtterancePlan] = []
        for item in _require_tuple("utterance_plans", self.utterance_plans):
            if type(item) is not SymbolicUtterancePlan:
                raise _fail("utterance_plans", "invalid_type")
            plans.append(item)
        if len(plans) > 2:
            raise _fail("utterance_plans", "cap_exceeded")
        object.__setattr__(self, "compositions", tuple(checked))
        object.__setattr__(self, "interpretations", tuple(checked_interps))
        object.__setattr__(self, "notices", tuple(checked_notices))
        object.__setattr__(self, "utterance_plans", tuple(plans))
        _LOG.debug(
            "symbolic_ledger_constructed owner_id=%s policy_version=%s "
            "composition_count=%s",
            self.owner_id.value,
            self.policy_version,
            len(self.compositions),
        )


@dataclass(frozen=True, slots=True)
class SymbolicLanguagePolicy:
    """Locked symbolic constants. Runner JSON does not carry these weights."""

    version: str = SYMBOLIC_LANGUAGE_POLICY_VERSION
    active_strength: float = _ACTIVE_STRENGTH
    retire_strength: float = _RETIRE_STRENGTH
    decay: float = _DECAY
    observed_delta: float = _OBSERVED_DELTA
    communicated_delta: float = _COMMUNICATED_DELTA
    remembered_delta: float = _REMEMBERED_DELTA
    self_use_delta: float = _SELF_USE_DELTA
    promotion_count: int = _PROMOTION_COUNT
    max_compositions: int = _MAX_COMPOSITIONS
    max_evidence: int = _MAX_EVIDENCE
    max_per_message: int = _MAX_PER_MESSAGE
    meaning_shift_ticks: int = _MEANING_SHIFT_TICKS
    utterance_interval: int = _UTTERANCE_INTERVAL

    def __post_init__(self) -> None:
        if self.version != SYMBOLIC_LANGUAGE_POLICY_VERSION:
            raise _fail("version", "unsupported_policy")
        for name, expected in (
            ("active_strength", _ACTIVE_STRENGTH),
            ("retire_strength", _RETIRE_STRENGTH),
            ("decay", _DECAY),
            ("observed_delta", _OBSERVED_DELTA),
            ("communicated_delta", _COMMUNICATED_DELTA),
            ("remembered_delta", _REMEMBERED_DELTA),
            ("self_use_delta", _SELF_USE_DELTA),
        ):
            object.__setattr__(
                self, name, _locked_float(name, getattr(self, name), expected)
            )
        for name, expected in (
            ("promotion_count", _PROMOTION_COUNT),
            ("max_compositions", _MAX_COMPOSITIONS),
            ("max_evidence", _MAX_EVIDENCE),
            ("max_per_message", _MAX_PER_MESSAGE),
            ("meaning_shift_ticks", _MEANING_SHIFT_TICKS),
            ("utterance_interval", _UTTERANCE_INTERVAL),
        ):
            object.__setattr__(
                self, name, _locked_int(name, getattr(self, name), expected)
            )


def default_symbolic_language_policy() -> SymbolicLanguagePolicy:
    """Return the only accepted symbolic-language policy."""
    return SymbolicLanguagePolicy()


def empty_symbolic_ledger(owner_id: AgentId) -> SymbolicLedger:
    """Ledger with no compositions. Disabled mode does not call this."""
    return SymbolicLedger(owner_id=owner_id)


def require_owner_symbolic_language(
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
    if type(ledger) is not SymbolicLedger:
        _LOG.warning("symbolic_carry_rejected reason=%s", "invalid_type")
        raise TypeError(f"{field_name} must be SymbolicLedger")
    if ledger.owner_id != owner_id:
        _LOG.error(
            "symbolic_validation_failed field=%s reason_code=%s",
            field_name,
            "owner_mismatch",
        )
        _LOG.warning("symbolic_carry_rejected reason=%s", "owner_mismatch")
        raise ValueError(f"{field_name} owner_id mismatch")


@dataclass
class _CompositionDraft:
    kind: SymbolicCompositionKind
    parts: tuple[str, str]
    referent_hypothesis: SymbolicReferentHypothesis | None
    status: SymbolicStatus
    strength: float
    evidence_count: int
    usage_count: int
    first_tick: int | None
    last_tick: int | None
    last_utterance_tick: int | None
    sense_revision: int
    evidence: list[SymbolicEvidenceItem]
    pending_referent_kind: NamingReferentKind | None = None
    meaning_shift_streak: int = 0
    notices: list[str] = field(default_factory=list)
    touched: bool = False


def _drafts_from(
    previous: SymbolicLedger | None, owner_id: AgentId
) -> list[_CompositionDraft]:
    if previous is None:
        return []
    require_owner_symbolic_language(previous, owner_id, field_name="previous")
    return [
        _CompositionDraft(
            kind=item.kind,
            parts=item.parts,
            referent_hypothesis=item.referent_hypothesis,
            status=item.status,
            strength=item.strength,
            evidence_count=item.evidence_count,
            usage_count=item.usage_count,
            first_tick=item.first_tick,
            last_tick=item.last_tick,
            last_utterance_tick=item.last_utterance_tick,
            sense_revision=item.sense_revision,
            evidence=list(item.evidence),
            pending_referent_kind=item.pending_referent_kind,
            meaning_shift_streak=item.meaning_shift_streak,
            notices=list(item.notices),
        )
        for item in previous.compositions
    ]


def _find_draft(
    drafts: list[_CompositionDraft],
    *,
    kind: SymbolicCompositionKind,
    parts: tuple[str, str],
) -> _CompositionDraft | None:
    for draft in drafts:
        if draft.kind is kind and draft.parts == parts:
            return draft
    return None


def _notice(notices: list[str], reason: str) -> None:
    if reason not in notices:
        notices.append(reason)


def _bindings(terminology: TerminologyLedger) -> dict[str, LabelBinding]:
    return {binding.label_token: binding for binding in terminology.bindings}


def _active_binding(
    bindings: Mapping[str, LabelBinding], token: str
) -> LabelBinding | None:
    binding = bindings.get(token)
    if binding is None or binding.status is not NamingStatus.ACTIVE:
        return None
    return binding


def _top_kind(binding: LabelBinding) -> NamingReferentKind | None:
    if not binding.candidates:
        return None
    ordered = sorted(
        binding.candidates, key=lambda item: (-item.confidence, item.entity_id)
    )
    return ordered[0].kind


def _top_entity(binding: LabelBinding) -> tuple[NamingReferentKind, str] | None:
    if not binding.candidates:
        return None
    ordered = sorted(
        binding.candidates, key=lambda item: (-item.confidence, item.entity_id)
    )
    return ordered[0].kind, ordered[0].entity_id


def _record_evidence(
    *,
    drafts: list[_CompositionDraft],
    notices: list[str],
    owner_id: AgentId,
    kind: SymbolicCompositionKind,
    parts: tuple[str, str],
    delta: float,
    channel: SymbolicEvidenceChannel,
    lineage_ref: str,
    tick: int,
    policy: SymbolicLanguagePolicy,
    actor_id: AgentId | None = None,
    speaker_id: AgentId | None = None,
    hypothesis: SymbolicReferentHypothesis | None = None,
) -> tuple[bool, str]:
    draft = _find_draft(drafts, kind=kind, parts=parts)
    if draft is None:
        if len(drafts) >= policy.max_compositions:
            _notice(notices, "cap_exceeded")
            return False, "cap_exceeded"
        draft = _CompositionDraft(
            kind=kind,
            parts=parts,
            referent_hypothesis=hypothesis,
            status=SymbolicStatus.CANDIDATE,
            strength=0.0,
            evidence_count=0,
            usage_count=0,
            first_tick=tick,
            last_tick=tick,
            last_utterance_tick=None,
            sense_revision=0,
            evidence=[],
        )
        drafts.append(draft)
    if any(item.lineage_ref == lineage_ref for item in draft.evidence):
        return False, "duplicate_composition"
    if len(draft.evidence) >= policy.max_evidence:
        _notice(notices, "cap_exceeded")
        return False, "cap_exceeded"
    before = draft.strength
    draft.strength = _apply_delta(before, delta)
    draft.evidence_count += 1
    draft.touched = True
    if draft.first_tick is None:
        draft.first_tick = tick
    draft.last_tick = tick
    if hypothesis is not None:
        draft.referent_hypothesis = hypothesis
    binding_id = composition_id(owner_id, kind, parts)
    ordinal = len(draft.evidence)
    draft.evidence.append(
        SymbolicEvidenceItem(
            evidence_id=composition_evidence_id(
                binding_id, ordinal, channel, lineage_ref
            ),
            ordinal=ordinal,
            channel=channel,
            lineage_ref=lineage_ref,
            tick=tick,
            actor_id=actor_id,
            speaker_id=speaker_id,
        )
    )
    _LOG.debug(
        "symbolic_composition_evidence owner_id=%s tick=%s channel=%s",
        owner_id.value,
        tick,
        channel.value,
    )
    return True, "applied"


def _observed_keys(
    observation: Observation, cues: SymbolicCueSummary | None
) -> set[str]:
    keys: set[str] = set()
    if observation.self_body is not None:
        keys.add(observation.self_body.location_id.value)
    for body in observation.visible_bodies:
        keys.add(body.entity_id.value)
    for item in observation.items:
        keys.add(item.entity_id.value)
    for art in observation.artifacts:
        artifact_id = getattr(art, "artifact_id", None)
        if artifact_id is not None:
            keys.add(artifact_id.value)
    for resource in observation.resources:
        keys.add(resource.kind.value)
    if cues is not None:
        keys.update(cues.observed_entity_keys)
    return keys


def _apply_observed(
    *,
    observation: Observation,
    identity: OwnerSafeSocialIdentity,
    drafts: list[_CompositionDraft],
    notices: list[str],
    bindings: Mapping[str, LabelBinding],
    cues: SymbolicCueSummary | None,
    policy: SymbolicLanguagePolicy,
) -> None:
    owner_id = identity.owner_id
    tick = observation.tick
    observed = _observed_keys(observation, cues)
    groups: dict[tuple[NamingReferentKind, str], list[str]] = {}
    for token, binding in bindings.items():
        if binding.status is not NamingStatus.ACTIVE:
            continue
        top = _top_entity(binding)
        if top is None:
            continue
        kind, entity_id = top
        if entity_id not in observed:
            continue
        groups.setdefault((kind, entity_id), []).append(token)
    for (kind, entity_id), tokens in sorted(
        groups.items(), key=lambda item: (item[0][0].value, item[0][1])
    ):
        unique = sorted(set(tokens))
        if len(unique) < 2:
            continue
        head = unique[0]
        for other in unique[1:]:
            parts = (head, other)
            _record_evidence(
                drafts=drafts,
                notices=notices,
                owner_id=owner_id,
                kind=SymbolicCompositionKind.RELATIONAL,
                parts=parts,
                delta=policy.observed_delta,
                channel=SymbolicEvidenceChannel.OBSERVED,
                lineage_ref=f"tick-{tick}-obs-{kind.value}-{entity_id[:16]}",
                tick=tick,
                policy=policy,
                hypothesis=SymbolicReferentHypothesis(
                    referent_kind=kind, confidence=policy.observed_delta
                ),
            )


def _memory_contents(trace: object) -> tuple[set[str], list[tuple[str, str, str]]]:
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


def _apply_memory(
    *,
    memories: Sequence[object] | None,
    drafts: list[_CompositionDraft],
    notices: list[str],
    owner_id: AgentId,
    tick: int,
    policy: SymbolicLanguagePolicy,
) -> None:
    if not memories or not drafts:
        if memories and not drafts:
            _notice(notices, "memory_no_match")
        return
    matched = False
    for trace in memories:
        if getattr(trace, "forgotten_at_tick", None) is not None:
            continue
        expires = getattr(trace, "expires_at_tick", None)
        if isinstance(expires, int) and expires <= tick:
            continue
        memory_id = getattr(getattr(trace, "memory_id", None), "value", None)
        if not isinstance(memory_id, str) or not memory_id:
            continue
        concepts, relations = _memory_contents(trace)
        for draft in drafts:
            if draft.status is SymbolicStatus.RETIRED:
                continue
            first, second = draft.parts
            present = (first in concepts and second in concepts) or any(
                predicate in {"call", "attributive", "relational"}
                and (
                    (subject == first and obj == second)
                    or (subject == second and obj == first)
                )
                for subject, predicate, obj in relations
            )
            if not present:
                continue
            _record_evidence(
                drafts=drafts,
                notices=notices,
                owner_id=owner_id,
                kind=draft.kind,
                parts=draft.parts,
                delta=policy.remembered_delta,
                channel=SymbolicEvidenceChannel.REMEMBERED,
                lineage_ref=memory_id,
                tick=tick,
                policy=policy,
            )
            matched = True
            _LOG.debug(
                "symbolic_memory_reinforced owner_id=%s tick=%s",
                owner_id.value,
                tick,
            )
    if not matched:
        _notice(notices, "memory_no_match")


def _operator_atoms(communication: ObservedCommunication) -> list[tuple[str, str, str]]:
    atoms: list[tuple[str, str, str]] = []
    content = communication.utterance.content
    if len(content.relations) > 32:
        return atoms
    for relation in content.relations:
        predicate = getattr(relation, "predicate", None)
        subject = getattr(relation, "subject", None)
        obj = getattr(relation, "object", None)
        if not isinstance(predicate, str):
            continue
        if predicate not in _OPERATORS:
            continue
        if not isinstance(subject, str) or not isinstance(obj, str):
            continue
        atoms.append((subject, predicate, obj))
    return atoms


def _apply_transmission(
    *,
    observation: Observation,
    identity: OwnerSafeSocialIdentity,
    drafts: list[_CompositionDraft],
    notices: list[str],
    interpretations: list[SymbolicInterpretation],
    bindings: Mapping[str, LabelBinding],
    policy: SymbolicLanguagePolicy,
) -> None:
    owner_id = identity.owner_id
    tick = observation.tick
    for index, communication in enumerate(observation.communications):
        if type(communication) is not ObservedCommunication:
            continue
        if communication.listener_id != identity.owner_entity_id:
            continue
        atoms = _operator_atoms(communication)
        if not atoms:
            continue
        message_id = (
            None
            if communication.provenance.source_event_id is None
            else communication.provenance.source_event_id.value
        )
        lineage = f"tick-{tick}-c{index}"
        speaker_agent: AgentId | None = next(
            (
                item.agent_id
                for item in identity.counterparts
                if item.entity_id == communication.speaker_id
            ),
            None,
        )
        for atom in atoms:
            subject, predicate, obj = atom
            try:
                kind = SymbolicCompositionKind(predicate)
                parts = _require_parts((subject, obj))
            except ValueError:
                _notice(notices, "illegal_token")
                continue
            first = _active_binding(bindings, parts[0])
            second = _active_binding(bindings, parts[1])
            if first is None or second is None:
                outcome = (
                    SymbolicParseOutcome.UNRESOLVED
                    if first is None and second is None
                    else SymbolicParseOutcome.PARTIAL
                )
                _notice(
                    notices,
                    "constituent_missing"
                    if first is None and second is None
                    else "constituent_inactive",
                )
                composition_value = composition_id(owner_id, kind, parts)
                if (
                    message_id is not None
                    and len(interpretations) < _MAX_INTERPRETATIONS
                ):
                    interpretations.append(
                        SymbolicInterpretation(
                            owner_id=owner_id,
                            message_id=message_id,
                            outcome=outcome,
                            composition_id=composition_value,
                            tick=tick,
                        )
                    )
                continue
            first_kind = _top_kind(first)
            second_kind = _top_kind(second)
            hypothesis = None
            if first_kind is not None and first_kind is second_kind:
                hypothesis = SymbolicReferentHypothesis(
                    referent_kind=first_kind, confidence=policy.communicated_delta
                )
            applied, reason = _record_evidence(
                drafts=drafts,
                notices=notices,
                owner_id=owner_id,
                kind=kind,
                parts=parts,
                delta=policy.communicated_delta,
                channel=SymbolicEvidenceChannel.COMMUNICATED,
                lineage_ref=f"{lineage}-{kind.value}",
                tick=tick,
                policy=policy,
                speaker_id=speaker_agent,
                hypothesis=hypothesis,
            )
            composition_value = composition_id(owner_id, kind, parts)
            if message_id is not None and len(interpretations) < _MAX_INTERPRETATIONS:
                interpretations.append(
                    SymbolicInterpretation(
                        owner_id=owner_id,
                        message_id=message_id,
                        outcome=(
                            SymbolicParseOutcome.PARSED
                            if applied
                            else SymbolicParseOutcome.IGNORED
                        ),
                        composition_id=composition_value,
                        tick=tick,
                    )
                )
            if not applied and reason == "duplicate_composition":
                _notice(notices, "duplicate_composition")


def _promote(
    drafts: list[_CompositionDraft],
    owner_id: AgentId,
    tick: int,
    policy: SymbolicLanguagePolicy,
    notices: list[str],
) -> None:
    for draft in drafts:
        if draft.status is not SymbolicStatus.CANDIDATE:
            continue
        if draft.evidence_count < policy.promotion_count:
            _notice(notices, "below_count")
            continue
        if draft.strength < policy.active_strength:
            _notice(notices, "below_strength")
            continue
        draft.status = SymbolicStatus.ACTIVE
        _LOG.debug(
            "symbolic_composition_promoted owner_id=%s tick=%s status=%s",
            owner_id.value,
            tick,
            draft.status.value,
        )


def _meaning_shift(
    drafts: list[_CompositionDraft],
    owner_id: AgentId,
    tick: int,
    policy: SymbolicLanguagePolicy,
) -> None:
    for draft in drafts:
        if draft.status is not SymbolicStatus.ACTIVE:
            draft.meaning_shift_streak = 0
            continue
        hypothesis = draft.referent_hypothesis
        if hypothesis is None:
            draft.meaning_shift_streak = 0
            continue
        if draft.pending_referent_kind is None:
            draft.pending_referent_kind = hypothesis.referent_kind
            draft.meaning_shift_streak = 0
            continue
        if hypothesis.referent_kind is draft.pending_referent_kind:
            draft.meaning_shift_streak = 0
            continue
        draft.meaning_shift_streak += 1
        if draft.meaning_shift_streak >= policy.meaning_shift_ticks:
            draft.pending_referent_kind = hypothesis.referent_kind
            draft.sense_revision += 1
            draft.meaning_shift_streak = 0
            _LOG.debug(
                "symbolic_meaning_shifted owner_id=%s tick=%s",
                owner_id.value,
                tick,
            )


def _decay(
    drafts: list[_CompositionDraft],
    owner_id: AgentId,
    tick: int,
    policy: SymbolicLanguagePolicy,
) -> None:
    for draft in drafts:
        if draft.status is SymbolicStatus.RETIRED or draft.touched:
            continue
        draft.strength = _apply_delta(draft.strength, -policy.decay)
        if draft.strength < policy.retire_strength:
            draft.status = SymbolicStatus.RETIRED
            _LOG.debug(
                "symbolic_composition_retired owner_id=%s tick=%s",
                owner_id.value,
                tick,
            )


def _freeze(
    owner_id: AgentId,
    drafts: list[_CompositionDraft],
    notices: list[str],
    interpretations: list[SymbolicInterpretation],
) -> SymbolicLedger:
    compositions: list[SymbolicComposition] = []
    for draft in drafts:
        compositions.append(
            SymbolicComposition(
                composition_id=composition_id(owner_id, draft.kind, draft.parts),
                owner_id=owner_id,
                kind=draft.kind,
                parts=draft.parts,
                referent_hypothesis=draft.referent_hypothesis,
                status=draft.status,
                strength=draft.strength,
                evidence_count=draft.evidence_count,
                usage_count=draft.usage_count,
                first_tick=draft.first_tick,
                last_tick=draft.last_tick,
                last_utterance_tick=draft.last_utterance_tick,
                sense_revision=draft.sense_revision,
                notices=tuple(draft.notices),
                evidence=tuple(draft.evidence[-_MAX_EVIDENCE:]),
                pending_referent_kind=draft.pending_referent_kind,
                meaning_shift_streak=draft.meaning_shift_streak,
            )
        )
    return SymbolicLedger(
        owner_id=owner_id,
        compositions=tuple(compositions),
        interpretations=tuple(interpretations[-_MAX_INTERPRETATIONS:]),
        notices=tuple(notices),
    )


def apply_symbolic_update(
    observation: object,
    identity: object,
    previous: object = None,
    terminology: object = None,
    memories: Sequence[object] | None = None,
    cues: SymbolicCueSummary | None = None,
    policy: SymbolicLanguagePolicy | None = None,
) -> SymbolicLedger:
    """Apply one tick of owner-scoped composition evidence.

    Disabled callers do not call this function. Both constituents must already
    be ``ACTIVE`` in the supplied owner ``TerminologyLedger``. Memory may only
    reinforce an existing composition; it never mints one.
    """
    _LOG.debug(
        "apply_symbolic_update owner_id=%s tick=%s",
        getattr(getattr(identity, "owner_id", None), "value", None),
        getattr(observation, "tick", None),
    )
    for value in (observation, identity, policy, memories, cues):
        _reject_forbidden(value)
    if memories is not None:
        for item in memories:
            _reject_forbidden(item)
    if type(observation) is not Observation:
        raise TypeError("observation must be Observation")
    if type(identity) is not OwnerSafeSocialIdentity:
        raise TypeError("identity must be OwnerSafeSocialIdentity")
    if previous is not None and type(previous) is not SymbolicLedger:
        raise TypeError("previous must be SymbolicLedger or None")
    if type(terminology) is not TerminologyLedger:
        raise TypeError("terminology must be TerminologyLedger")
    if cues is not None and type(cues) is not SymbolicCueSummary:
        raise TypeError("cues must be SymbolicCueSummary or None")
    owner_id = identity.owner_id
    require_owner_semantic_naming(terminology, owner_id, field_name="terminology")
    active_policy = default_symbolic_language_policy() if policy is None else policy
    if type(active_policy) is not SymbolicLanguagePolicy:
        raise TypeError("policy must be SymbolicLanguagePolicy")
    tick = observation.tick
    drafts = _drafts_from(previous, owner_id)
    notices: list[str] = []
    interpretations: list[SymbolicInterpretation] = (
        [] if previous is None else list(previous.interpretations)
    )
    bindings = _bindings(terminology)
    _apply_observed(
        observation=observation,
        identity=identity,
        drafts=drafts,
        notices=notices,
        bindings=bindings,
        cues=cues,
        policy=active_policy,
    )
    _apply_transmission(
        observation=observation,
        identity=identity,
        drafts=drafts,
        notices=notices,
        interpretations=interpretations,
        bindings=bindings,
        policy=active_policy,
    )
    _apply_memory(
        memories=memories,
        drafts=drafts,
        notices=notices,
        owner_id=owner_id,
        tick=tick,
        policy=active_policy,
    )
    _promote(drafts, owner_id, tick, active_policy, notices)
    _meaning_shift(drafts, owner_id, tick, active_policy)
    _decay(drafts, owner_id, tick, active_policy)
    ledger = _freeze(owner_id, drafts, notices, interpretations)
    _LOG.info(
        "symbolic_ledger_updated owner_id=%s composition_count=%s",
        owner_id.value,
        len(ledger.compositions),
    )
    return ledger


def _selectable(
    ledger: SymbolicLedger,
    terminology: TerminologyLedger,
    *,
    tick: int,
    policy: SymbolicLanguagePolicy,
) -> list[SymbolicComposition]:
    bindings = _bindings(terminology)
    selected: list[SymbolicComposition] = []
    for composition in ledger.compositions:
        if composition.status is not SymbolicStatus.ACTIVE:
            continue
        if composition.strength < policy.active_strength:
            continue
        if composition.last_utterance_tick is not None:
            if tick - composition.last_utterance_tick < policy.utterance_interval:
                continue
        if any(_active_binding(bindings, part) is None for part in composition.parts):
            continue
        selected.append(composition)
    selected.sort(key=lambda item: (-item.strength, item.composition_id))
    return selected[: policy.max_per_message]


def symbolic_communicate_utterance(
    command: object,
    *,
    owner_id: AgentId,
    tick: int,
    observation: Observation,
    identity: OwnerSafeSocialIdentity | None,
    ledger: object | None,
    terminology: object | None,
    mode: object | None,
) -> object:
    """Stamp an existing ``Talk`` with bounded composition relations.

    Returns the command unchanged when the mode is disabled, no active
    composition is speakable, or the command is not a ``Talk``.
    """
    from agents.cognition.configuration import CognitionSymbolicLanguageMode
    from world.actions import Talk
    from world.communications import CommunicationContent, StructuredUtterance

    if mode is not CognitionSymbolicLanguageMode.DETERMINISTIC:
        return command
    if type(observation) is not Observation or type(command) is not Talk:
        return command
    if type(ledger) is not SymbolicLedger or not ledger.compositions:
        return command
    if type(terminology) is not TerminologyLedger:
        return command
    if identity is None or observation.tick != tick:
        return command
    policy = default_symbolic_language_policy()
    selected = _selectable(ledger, terminology, tick=tick, policy=policy)
    if not selected:
        return command
    bindings = _bindings(terminology)
    relations: list[object] = []
    for composition in selected:
        for part in composition.parts:
            binding = _active_binding(bindings, part)
            if binding is None:  # pragma: no cover - guarded by _selectable
                return command
            relations.append(_relation(part, "call", binding.referent_kind.value))
        relations.append(
            _relation(
                composition.parts[0],
                composition.kind.value,
                composition.parts[1],
            )
        )
    existing = command.utterance.content
    from world.communications import CommunicationRelation

    checked_relations = tuple(
        item for item in relations if type(item) is CommunicationRelation
    )
    content = CommunicationContent(
        text=existing.text,
        concepts=existing.concepts,
        relations=checked_relations,
    )
    utterance = StructuredUtterance(
        content=content,
        declared=command.utterance.declared,
    )
    _LOG.info(
        "symbolic_message_emitted owner_id=%s tick=%s composition_count=%s",
        owner_id.value,
        tick,
        len(selected),
    )
    return Talk(recipient_id=command.recipient_id, utterance=utterance)


def _relation(subject: str, predicate: str, obj: str) -> object:
    from world.communications import CommunicationRelation

    return CommunicationRelation(subject=subject, predicate=predicate, object=obj)


def _selected_ids(command: object, ledger: SymbolicLedger) -> tuple[str, ...]:
    from world.actions import Talk

    if type(command) is not Talk:
        return ()
    operators: list[tuple[str, str, str]] = []
    for relation in command.utterance.content.relations:
        predicate = getattr(relation, "predicate", None)
        subject = getattr(relation, "subject", None)
        obj = getattr(relation, "object", None)
        if isinstance(predicate, str) and predicate in _OPERATORS:
            if isinstance(subject, str) and isinstance(obj, str):
                operators.append((subject, predicate, obj))
    selected: list[str] = []
    by_key = {
        (item.kind.value, item.parts): item.composition_id
        for item in ledger.compositions
    }
    for subject, predicate, obj in operators:
        value = by_key.get((predicate, (subject, obj)))
        if value is not None and value not in selected:
            selected.append(value)
    return tuple(selected)


def symbolic_usage_update(
    ledger: object,
    command: object,
    *,
    tick: int,
    policy: SymbolicLanguagePolicy | None = None,
) -> object:
    """Commit usage for the compositions actually present in ``command``.

    Returns the same ledger object when nothing was selected so disabled or
    non-composed runs remain byte-identical.
    """
    if type(ledger) is not SymbolicLedger:
        return ledger
    selected = _selected_ids(command, ledger)
    if not selected:
        return ledger
    active_policy = default_symbolic_language_policy() if policy is None else policy
    updated: list[SymbolicComposition] = []
    changed = False
    for composition in ledger.compositions:
        if composition.composition_id not in selected:
            updated.append(composition)
            continue
        new_strength = _apply_delta(composition.strength, active_policy.self_use_delta)
        evidence = list(composition.evidence)
        if len(evidence) < active_policy.max_evidence:
            ordinal = len(evidence)
            evidence.append(
                SymbolicEvidenceItem(
                    evidence_id=composition_evidence_id(
                        composition.composition_id,
                        ordinal,
                        SymbolicEvidenceChannel.SELF_USE,
                        f"tick-{tick}",
                    ),
                    ordinal=ordinal,
                    channel=SymbolicEvidenceChannel.SELF_USE,
                    lineage_ref=f"tick-{tick}",
                    tick=tick,
                )
            )
        updated.append(
            SymbolicComposition(
                composition_id=composition.composition_id,
                owner_id=composition.owner_id,
                kind=composition.kind,
                parts=composition.parts,
                referent_hypothesis=composition.referent_hypothesis,
                status=composition.status,
                strength=new_strength,
                evidence_count=composition.evidence_count + 1,
                usage_count=composition.usage_count + 1,
                first_tick=composition.first_tick,
                last_tick=tick,
                last_utterance_tick=tick,
                sense_revision=composition.sense_revision,
                notices=composition.notices,
                evidence=tuple(evidence),
                pending_referent_kind=composition.pending_referent_kind,
                meaning_shift_streak=composition.meaning_shift_streak,
            )
        )
        changed = True
    if not changed:
        return ledger
    _LOG.info(
        "symbolic_usage_committed owner_id=%s tick=%s composition_count=%s",
        ledger.owner_id.value,
        tick,
        len(selected),
    )
    return SymbolicLedger(
        owner_id=ledger.owner_id,
        compositions=tuple(updated),
        interpretations=ledger.interpretations,
        notices=ledger.notices,
        utterance_plans=(
            *ledger.utterance_plans,
            SymbolicUtterancePlan(composition_ids=selected, created_tick=tick),
        )[-2:],
        policy_version=ledger.policy_version,
    )


def observed_occurrence_key(occurrence: object) -> str | None:
    """Opaque stable key for one observed occurrence when available."""
    if type(occurrence) is not ObservedOccurrence:
        return None
    event_id = occurrence.provenance.source_event_id
    return None if event_id is None else event_id.value
