"""Owner-scoped bounded translation inference between foreign and own terms.

A translation mapping is a private hypothesis: "this foreign surface term
probably means one of my own active labels". It is never an objective
dictionary, never shared between owners, and never corrected by the engine.
Only detached analysis may classify an outcome as exact, partial, ambiguous, or
wrong. Updates read one owner's ``Observation``, identity, previous
``TranslationLedger``, the owner's own updated ``TerminologyLedger``, and
optional already-loaded memories / advice / mentorship facts. They never read
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
from typing import Any, Final, cast

from agents.cognition.models import OwnerSafeSocialIdentity
from agents.cognition.semantic_naming import (
    LabelBinding,
    NamingReferentKind,
    NamingStatus,
    TerminologyLedger,
    require_owner_semantic_naming,
)
from agents.models import AgentId
from world.identifiers import EntityId, require_exact_nonneg_int
from world.observations import (
    Observation,
    ObservedArtifact,
    ObservedCommunication,
)

_LOG: Final[logging.Logger] = logging.getLogger("agents.cognition.translation")

TRANSLATION_POLICY_VERSION: Final[str] = "translation.v1"
_QUANTUM: Final[Decimal] = Decimal("0.000001")

_ACTIVE_STRENGTH: Final[float] = 0.45
_RETIRE_STRENGTH: Final[float] = 0.15
_DECAY: Final[float] = 0.04
_PROMOTION_COUNT: Final[int] = 3
_MAX_MAPPINGS: Final[int] = 16
_MAX_TARGETS: Final[int] = 3
_MAX_EVIDENCE: Final[int] = 32
_MAX_APPLICATIONS: Final[int] = 32
_MAX_NOTICES: Final[int] = 16
_AMBIGUITY_MARGIN: Final[float] = 0.10
_OUTBOUND_INTERVAL: Final[int] = 4
_TEACHING_WINDOW: Final[int] = 8

_SHARED_OBSERVATION_DELTA: Final[float] = 0.18
_DEMONSTRATION_DELTA: Final[float] = 0.14
_REPEATED_INTERACTION_DELTA: Final[float] = 0.10
_TEACHING_DELTA: Final[float] = 0.20
_ARTIFACT_DELTA: Final[float] = 0.12
_CONTEXT_DELTA: Final[float] = 0.06

_HEX: Final[frozenset[str]] = frozenset("0123456789abcdef")
_LABEL_TOKEN_RE: Final[re.Pattern[str]] = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
_SOURCE_DIGEST_LEN: Final[int] = 16

_NOTICE_REASONS: Final[frozenset[str]] = frozenset(
    {
        "cap_exceeded",
        "ignored_kind",
        "unresolved_entity",
        "illegal_token",
        "invalid_token",
        "no_candidate",
        "candidate_only",
        "ambiguous_translation",
        "constituent_missing",
        "owner_mismatch",
        "source_known",
        "source_self_target",
    }
)
_FORBIDDEN_TYPES: Final[frozenset[str]] = frozenset(
    {
        "WorldState",
        "WorldEvent",
        "PhysicalRules",
        "AgentBody",
        "MetricDocument",
        "TranslationRow",
        "TranslationAnalysisInputs",
    }
)

__all__ = [
    "TRANSLATION_POLICY_VERSION",
    "TranslationApplication",
    "TranslationApplicationKind",
    "TranslationApplicationOutcome",
    "TranslationEvidenceChannel",
    "TranslationEvidenceItem",
    "TranslationFit",
    "TranslationLedger",
    "TranslationMapping",
    "TranslationMappingStatus",
    "TranslationMode",
    "TranslationPolicy",
    "TranslationResolution",
    "TranslationSourceKind",
    "TranslationStrengthBand",
    "TranslationTarget",
    "apply_translation_update",
    "default_translation_policy",
    "empty_translation_ledger",
    "record_translation_application",
    "require_owner_translation",
    "resolve_translation_token",
    "translation_application_id",
    "translation_communicate_utterance",
    "translation_evidence_id",
    "translation_mapping_id",
    "translation_source_digest",
    "translation_strength_band",
    "translation_targets_for_kind",
    "translation_usage_update",
]


class TranslationMode(StrEnum):
    """Owner-scoped translation treatment. Disabled allocates nothing."""

    DISABLED = "disabled"
    DETERMINISTIC = "deterministic"


class TranslationSourceKind(StrEnum):
    """Closed source kind for a foreign surface form."""

    LABEL = "label"


class TranslationMappingStatus(StrEnum):
    """Closed lifecycle for one owner's translation mapping."""

    CANDIDATE = "candidate"
    ACTIVE = "active"
    RETIRED = "retired"


class TranslationFit(StrEnum):
    """Owner's structural self-assessment. Never a correctness claim."""

    RESOLVED = "resolved"
    PARTIAL = "partial"
    AMBIGUOUS = "ambiguous"
    UNRESOLVED = "unresolved"


class TranslationEvidenceChannel(StrEnum):
    """Closed evidence channel for one mapping item."""

    SHARED_OBSERVATION = "shared_observation"
    DEMONSTRATION = "demonstration"
    REPEATED_INTERACTION = "repeated_interaction"
    TEACHING = "teaching"
    ARTIFACT = "artifact"
    CONTEXT = "context"


class TranslationApplicationKind(StrEnum):
    """Closed downstream use of a mapping."""

    SYMBOLIC_INTERPRETATION = "symbolic_interpretation"
    OUTBOUND_TERM = "outbound_term"


class TranslationApplicationOutcome(StrEnum):
    """Closed outcome band for one application."""

    APPLIED = "applied"
    SKIPPED = "skipped"
    AMBIGUOUS = "ambiguous"
    UNRESOLVED = "unresolved"


class TranslationStrengthBand(StrEnum):
    """Closed overlay strength band for researcher presentation."""

    CANDIDATE = "candidate"
    LOW = "low"
    MID = "mid"
    HIGH = "high"


def _fail(field_name: str, code: str) -> ValueError:
    _LOG.error(
        "translation_validation_failed field=%s reason_code=%s",
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


def _require_token(field_name: str, value: object) -> str:
    if not isinstance(value, str) or not _LABEL_TOKEN_RE.fullmatch(value):
        raise _fail(field_name, "illegal_token")
    return value


def _require_digest(field_name: str, value: object) -> str:
    if (
        not isinstance(value, str)
        or len(value) != _SOURCE_DIGEST_LEN
        or any(char not in _HEX for char in value)
    ):
        raise _fail(field_name, "invalid_digest")
    return value


def _require_tuple(field_name: str, values: object) -> tuple[object, ...]:
    if isinstance(values, (str, bytes, set, frozenset)) or not isinstance(
        values, Sequence
    ):
        raise _fail(field_name, "invalid_type")
    return tuple(values)


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


def translation_source_digest(source_token: str) -> str:
    """SHA-256 of ``translation|<token>`` truncated to 16 hex chars."""
    token = _require_token("source_token", source_token)
    return _sha256_hex(f"translation|{token}")[:_SOURCE_DIGEST_LEN]


def translation_mapping_id(owner_id: AgentId, source_digest: str) -> str:
    """Owner-scoped deterministic mapping identity."""
    if type(owner_id) is not AgentId:
        raise _fail("owner_id", "invalid_type")
    digest = _require_digest("source_digest", source_digest)
    return _sha256_hex(f"{owner_id.value}|translation|{digest}")


def translation_evidence_id(
    mapping_id: str,
    ordinal: int,
    channel: TranslationEvidenceChannel,
    lineage_ref: str,
) -> str:
    head = _require_hex_id("mapping_id", mapping_id)
    if isinstance(ordinal, bool) or type(ordinal) is not int or ordinal < 0:
        raise _fail("ordinal", "invalid_type")
    if type(channel) is not TranslationEvidenceChannel:
        raise _fail("channel", "unknown_channel")
    if not isinstance(lineage_ref, str) or not lineage_ref:
        raise _fail("lineage_ref", "invalid_type")
    return _sha256_hex(f"{head}|{ordinal}|{channel.value}|{lineage_ref}")


def translation_application_id(
    mapping_id: str,
    ordinal: int,
    kind: TranslationApplicationKind,
    message_id: str | None,
) -> str:
    head = _require_hex_id("mapping_id", mapping_id)
    if isinstance(ordinal, bool) or type(ordinal) is not int or ordinal < 0:
        raise _fail("ordinal", "invalid_type")
    if type(kind) is not TranslationApplicationKind:
        raise _fail("kind", "unknown_kind")
    if message_id is not None and (not isinstance(message_id, str) or not message_id):
        raise _fail("message_id", "invalid_type")
    return _sha256_hex(f"{head}|{ordinal}|{kind.value}|{message_id or '-'}")


def translation_strength_band(
    status: TranslationMappingStatus, strength: float
) -> TranslationStrengthBand:
    """Closed overlay strength band from status and quantized strength."""
    if type(status) is not TranslationMappingStatus:
        raise _fail("status", "unknown_status")
    quantized = _quantize(_finite("strength", strength))
    if status is TranslationMappingStatus.CANDIDATE:
        return TranslationStrengthBand.CANDIDATE
    if quantized < _ACTIVE_STRENGTH:
        return TranslationStrengthBand.LOW
    if quantized < 0.75:
        return TranslationStrengthBand.MID
    return TranslationStrengthBand.HIGH


@dataclass(frozen=True, slots=True)
class TranslationTarget:
    """One own active label the owner hypothesizes a foreign term maps to."""

    binding_id: str
    label_token: str
    referent_kind: NamingReferentKind
    weight: float

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "binding_id", _require_hex_id("target.binding_id", self.binding_id)
        )
        object.__setattr__(
            self,
            "label_token",
            _require_token("target.label_token", self.label_token),
        )
        if type(self.referent_kind) is not NamingReferentKind:
            raise _fail("target.referent_kind", "unknown_kind")
        weight = _quantize(_finite("target.weight", self.weight))
        if weight < 0.0 or weight > 1.0:
            raise _fail("target.weight", "out_of_range")
        object.__setattr__(self, "weight", weight)


@dataclass(frozen=True, slots=True)
class TranslationEvidenceItem:
    """One bounded item of translation evidence for a mapping."""

    evidence_id: str
    ordinal: int
    channel: TranslationEvidenceChannel
    lineage_ref: str
    tick: int
    actor_id: AgentId | None = None
    target_binding_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "evidence_id", _require_hex_id("evidence_id", self.evidence_id)
        )
        if isinstance(self.ordinal, bool) or type(self.ordinal) is not int:
            raise _fail("evidence.ordinal", "invalid_type")
        if self.ordinal < 0:
            raise _fail("evidence.ordinal", "out_of_range")
        if type(self.channel) is not TranslationEvidenceChannel:
            raise _fail("evidence.channel", "unknown_channel")
        if not isinstance(self.lineage_ref, str) or not self.lineage_ref:
            raise _fail("evidence.lineage_ref", "invalid_type")
        object.__setattr__(
            self,
            "tick",
            require_exact_nonneg_int("TranslationEvidenceItem.tick", self.tick),
        )
        if self.actor_id is not None and type(self.actor_id) is not AgentId:
            raise _fail("evidence.actor_id", "invalid_type")
        targets: list[str] = []
        seen: set[str] = set()
        for item in _require_tuple("target_binding_ids", self.target_binding_ids):
            head = _require_hex_id("target_binding_ids", item)
            if head in seen:
                raise _fail("target_binding_ids", "duplicate_target")
            seen.add(head)
            targets.append(head)
        if len(targets) > _MAX_TARGETS:
            raise _fail("target_binding_ids", "cap_exceeded")
        object.__setattr__(self, "target_binding_ids", tuple(targets))


@dataclass(frozen=True, slots=True)
class TranslationApplication:
    """One bounded downstream use of a mapping."""

    application_id: str
    ordinal: int
    tick: int
    kind: TranslationApplicationKind
    mapping_id: str
    outcome: TranslationApplicationOutcome
    message_id: str | None = None
    target_binding_id: str | None = None
    actor_id: AgentId | None = None
    command_kind: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "application_id",
            _require_hex_id("application_id", self.application_id),
        )
        if isinstance(self.ordinal, bool) or type(self.ordinal) is not int:
            raise _fail("application.ordinal", "invalid_type")
        if self.ordinal < 0:
            raise _fail("application.ordinal", "out_of_range")
        object.__setattr__(
            self,
            "tick",
            require_exact_nonneg_int("TranslationApplication.tick", self.tick),
        )
        if type(self.kind) is not TranslationApplicationKind:
            raise _fail("application.kind", "unknown_kind")
        object.__setattr__(
            self,
            "mapping_id",
            _require_hex_id("application.mapping_id", self.mapping_id),
        )
        if type(self.outcome) is not TranslationApplicationOutcome:
            raise _fail("application.outcome", "unknown_outcome")
        if self.message_id is not None and (
            not isinstance(self.message_id, str) or not self.message_id
        ):
            raise _fail("application.message_id", "invalid_type")
        if self.target_binding_id is not None:
            object.__setattr__(
                self,
                "target_binding_id",
                _require_hex_id(
                    "application.target_binding_id", self.target_binding_id
                ),
            )
        if self.actor_id is not None and type(self.actor_id) is not AgentId:
            raise _fail("application.actor_id", "invalid_type")
        if self.command_kind is not None and self.command_kind not in {
            "talk",
            "ask",
            "tell",
        }:
            raise _fail("application.command_kind", "unknown_kind")


@dataclass(frozen=True, slots=True)
class TranslationMapping:
    """One owner's hypothesis about what a foreign term means in own terms."""

    mapping_id: str
    owner_id: AgentId
    source_token: str
    source_digest: str
    source_kind: TranslationSourceKind
    targets: tuple[TranslationTarget, ...]
    status: TranslationMappingStatus
    fit: TranslationFit
    strength: float
    evidence_count: int
    first_tick: int
    last_tick: int
    last_use_tick: int | None = None
    usage_count: int = 0
    evidence: tuple[TranslationEvidenceItem, ...] = ()
    applications: tuple[TranslationApplication, ...] = ()
    notices: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "mapping_id", _require_hex_id("mapping_id", self.mapping_id)
        )
        if type(self.owner_id) is not AgentId:
            raise _fail("owner_id", "invalid_type")
        object.__setattr__(
            self, "source_token", _require_token("source_token", self.source_token)
        )
        object.__setattr__(
            self,
            "source_digest",
            _require_digest("source_digest", self.source_digest),
        )
        if self.source_digest != translation_source_digest(self.source_token):
            raise _fail("source_digest", "digest_mismatch")
        expected_id = translation_mapping_id(self.owner_id, self.source_digest)
        if self.mapping_id != expected_id:
            raise _fail("mapping_id", "id_mismatch")
        if type(self.source_kind) is not TranslationSourceKind:
            raise _fail("source_kind", "unknown_kind")
        if type(self.status) is not TranslationMappingStatus:
            raise _fail("status", "unknown_status")
        if type(self.fit) is not TranslationFit:
            raise _fail("fit", "unknown_fit")
        targets = _require_tuple("targets", self.targets)
        checked_targets: list[TranslationTarget] = []
        seen_bindings: set[str] = set()
        seen_tokens: set[str] = set()
        for item in targets:
            if type(item) is not TranslationTarget:
                raise _fail("targets", "invalid_type")
            if item.binding_id in seen_bindings:
                raise _fail("targets", "duplicate_target")
            if item.label_token == self.source_token:
                raise _fail("targets", "source_self_target")
            if item.label_token in seen_tokens:
                raise _fail("targets", "duplicate_token")
            seen_bindings.add(item.binding_id)
            seen_tokens.add(item.label_token)
            checked_targets.append(item)
        if len(checked_targets) > _MAX_TARGETS:
            raise _fail("targets", "cap_exceeded")
        if not checked_targets and self.fit is not TranslationFit.UNRESOLVED:
            raise _fail("fit", "empty_targets_require_unresolved")
        if checked_targets and self.fit is TranslationFit.UNRESOLVED:
            raise _fail("fit", "unresolved_requires_no_targets")
        strength = _quantize(_finite("strength", self.strength))
        if strength < 0.0 or strength > 1.0:
            raise _fail("strength", "out_of_range")
        object.__setattr__(self, "strength", strength)
        if (
            isinstance(self.evidence_count, bool)
            or type(self.evidence_count) is not int
        ):
            raise _fail("evidence_count", "invalid_type")
        if self.evidence_count < 0:
            raise _fail("evidence_count", "out_of_range")
        if isinstance(self.usage_count, bool) or type(self.usage_count) is not int:
            raise _fail("usage_count", "invalid_type")
        if self.usage_count < 0:
            raise _fail("usage_count", "out_of_range")
        object.__setattr__(
            self,
            "first_tick",
            require_exact_nonneg_int("TranslationMapping.first_tick", self.first_tick),
        )
        object.__setattr__(
            self,
            "last_tick",
            require_exact_nonneg_int("TranslationMapping.last_tick", self.last_tick),
        )
        if self.last_tick < self.first_tick:
            raise _fail("last_tick", "before_first_tick")
        if self.last_use_tick is not None:
            object.__setattr__(
                self,
                "last_use_tick",
                require_exact_nonneg_int(
                    "TranslationMapping.last_use_tick", self.last_use_tick
                ),
            )
        evidence = _require_tuple("evidence", self.evidence)
        checked_evidence: list[TranslationEvidenceItem] = []
        seen_evidence: set[str] = set()
        previous_ordinal = -1
        previous_tick = -1
        for item in evidence:
            if type(item) is not TranslationEvidenceItem:
                raise _fail("evidence", "invalid_type")
            if item.evidence_id in seen_evidence:
                raise _fail("evidence", "duplicate_evidence")
            if item.ordinal <= previous_ordinal:
                raise _fail("evidence.ordinal", "not_monotonic")
            if item.tick < previous_tick:
                raise _fail("evidence.tick", "not_monotonic")
            for head in item.target_binding_ids:
                if head not in seen_bindings:
                    raise _fail("evidence.target_binding_ids", "target_not_in_mapping")
            seen_evidence.add(item.evidence_id)
            previous_ordinal = item.ordinal
            previous_tick = item.tick
            checked_evidence.append(item)
        if len(checked_evidence) > _MAX_EVIDENCE:
            raise _fail("evidence", "cap_exceeded")
        if checked_evidence and self.evidence_count < len(checked_evidence):
            raise _fail("evidence_count", "below_evidence")
        applications = _require_tuple("applications", self.applications)
        checked_applications: list[TranslationApplication] = []
        seen_applications: set[str] = set()
        previous_ordinal = -1
        previous_tick = -1
        for item in applications:
            if type(item) is not TranslationApplication:
                raise _fail("applications", "invalid_type")
            if item.application_id in seen_applications:
                raise _fail("applications", "duplicate_application")
            if item.mapping_id != self.mapping_id:
                raise _fail("applications.mapping_id", "mapping_mismatch")
            if item.ordinal <= previous_ordinal:
                raise _fail("applications.ordinal", "not_monotonic")
            if item.tick < previous_tick:
                raise _fail("applications.tick", "not_monotonic")
            if (
                item.target_binding_id is not None
                and item.target_binding_id not in seen_bindings
            ):
                raise _fail("applications.target_binding_id", "target_not_in_mapping")
            seen_applications.add(item.application_id)
            previous_ordinal = item.ordinal
            previous_tick = item.tick
            checked_applications.append(item)
        if len(checked_applications) > _MAX_APPLICATIONS:
            raise _fail("applications", "cap_exceeded")
        notices = _require_tuple("notices", self.notices)
        checked_notices: list[str] = []
        for item in notices:
            if not isinstance(item, str) or item not in _NOTICE_REASONS:
                raise _fail("notices", "invalid_notice")
            if item not in checked_notices:
                checked_notices.append(item)
        if len(checked_notices) > _MAX_NOTICES:
            raise _fail("notices", "cap_exceeded")
        object.__setattr__(self, "targets", tuple(checked_targets))
        object.__setattr__(self, "evidence", tuple(checked_evidence))
        object.__setattr__(self, "applications", tuple(checked_applications))
        object.__setattr__(self, "notices", tuple(checked_notices))

    def validate_against(self, terminology: TerminologyLedger) -> None:
        """Validate every target against the owner's own terminology ledger."""
        if type(terminology) is not TerminologyLedger:
            raise TypeError("terminology must be TerminologyLedger")
        if terminology.owner_id != self.owner_id:
            raise _fail("terminology.owner_id", "owner_mismatch")
        bindings = {binding.binding_id: binding for binding in terminology.bindings}
        for target in self.targets:
            binding = bindings.get(target.binding_id)
            if binding is None:
                raise _fail("targets.binding_id", "dangling_target")
            if binding.owner_id != self.owner_id:
                raise _fail("targets.binding_id", "foreign_owner")
            if binding.status is not NamingStatus.ACTIVE:
                raise _fail("targets.binding_id", "inactive_target")
            if binding.merged_into is not None:
                raise _fail("targets.binding_id", "merged_target")
            if binding.label_token != target.label_token:
                raise _fail("targets.label_token", "token_mismatch")
            if binding.referent_kind is not target.referent_kind:
                raise _fail("targets.referent_kind", "kind_mismatch")


@dataclass(frozen=True, slots=True)
class TranslationLedger:
    """Owner-scoped translation hypotheses. ``None`` means the mode is off."""

    owner_id: AgentId
    mappings: tuple[TranslationMapping, ...] = ()
    notices: tuple[str, ...] = ()
    policy_version: str = TRANSLATION_POLICY_VERSION

    def __post_init__(self) -> None:
        if type(self.owner_id) is not AgentId:
            raise _fail("owner_id", "invalid_type")
        if self.policy_version != TRANSLATION_POLICY_VERSION:
            raise _fail("policy_version", "unsupported_policy")
        mappings = _require_tuple("mappings", self.mappings)
        checked: list[TranslationMapping] = []
        seen: set[str] = set()
        seen_sources: set[str] = set()
        for item in mappings:
            if type(item) is not TranslationMapping:
                raise _fail("mappings", "invalid_type")
            if item.owner_id != self.owner_id:
                raise _fail("mappings.owner_id", "owner_mismatch")
            if item.mapping_id in seen:
                raise _fail("mappings", "duplicate_mapping")
            if item.source_digest in seen_sources:
                raise _fail("mappings", "duplicate_source")
            seen.add(item.mapping_id)
            seen_sources.add(item.source_digest)
            checked.append(item)
        if len(checked) > _MAX_MAPPINGS:
            raise _fail("mappings", "cap_exceeded")
        notices = _require_tuple("notices", self.notices)
        checked_notices: list[str] = []
        for item in notices:
            if not isinstance(item, str) or item not in _NOTICE_REASONS:
                raise _fail("notices", "invalid_notice")
            if item not in checked_notices:
                checked_notices.append(item)
        if len(checked_notices) > _MAX_NOTICES:
            raise _fail("notices", "cap_exceeded")
        object.__setattr__(self, "mappings", tuple(checked))
        object.__setattr__(self, "notices", tuple(checked_notices))
        _LOG.debug(
            "translation_ledger_constructed owner_id=%s policy_version=%s "
            "mapping_count=%s",
            self.owner_id.value,
            self.policy_version,
            len(self.mappings),
        )

    def validate_against(self, terminology: TerminologyLedger) -> None:
        if type(terminology) is not TerminologyLedger:
            raise TypeError("terminology must be TerminologyLedger")
        if terminology.owner_id != self.owner_id:
            raise _fail("terminology.owner_id", "owner_mismatch")
        for mapping in self.mappings:
            mapping.validate_against(terminology)


@dataclass(frozen=True, slots=True)
class TranslationPolicy:
    """Locked translation constants. Runner JSON does not carry these weights."""

    version: str = TRANSLATION_POLICY_VERSION
    active_strength: float = _ACTIVE_STRENGTH
    retire_strength: float = _RETIRE_STRENGTH
    decay: float = _DECAY
    promotion_count: int = _PROMOTION_COUNT
    max_mappings: int = _MAX_MAPPINGS
    max_targets: int = _MAX_TARGETS
    max_evidence: int = _MAX_EVIDENCE
    max_applications: int = _MAX_APPLICATIONS
    ambiguity_margin: float = _AMBIGUITY_MARGIN
    outbound_interval: int = _OUTBOUND_INTERVAL
    teaching_window: int = _TEACHING_WINDOW
    shared_observation_delta: float = _SHARED_OBSERVATION_DELTA
    demonstration_delta: float = _DEMONSTRATION_DELTA
    repeated_interaction_delta: float = _REPEATED_INTERACTION_DELTA
    teaching_delta: float = _TEACHING_DELTA
    artifact_delta: float = _ARTIFACT_DELTA
    context_delta: float = _CONTEXT_DELTA

    def __post_init__(self) -> None:
        if self.version != TRANSLATION_POLICY_VERSION:
            raise _fail("version", "unsupported_policy")
        floats = (
            ("active_strength", _ACTIVE_STRENGTH),
            ("retire_strength", _RETIRE_STRENGTH),
            ("decay", _DECAY),
            ("ambiguity_margin", _AMBIGUITY_MARGIN),
            ("shared_observation_delta", _SHARED_OBSERVATION_DELTA),
            ("demonstration_delta", _DEMONSTRATION_DELTA),
            ("repeated_interaction_delta", _REPEATED_INTERACTION_DELTA),
            ("teaching_delta", _TEACHING_DELTA),
            ("artifact_delta", _ARTIFACT_DELTA),
            ("context_delta", _CONTEXT_DELTA),
        )
        for name, expected in floats:
            object.__setattr__(
                self, name, _locked_float(name, getattr(self, name), expected)
            )
        counts = (
            ("promotion_count", _PROMOTION_COUNT),
            ("max_mappings", _MAX_MAPPINGS),
            ("max_targets", _MAX_TARGETS),
            ("max_evidence", _MAX_EVIDENCE),
            ("max_applications", _MAX_APPLICATIONS),
            ("outbound_interval", _OUTBOUND_INTERVAL),
            ("teaching_window", _TEACHING_WINDOW),
        )
        for name, expected in counts:
            object.__setattr__(
                self, name, _locked_int(name, getattr(self, name), expected)
            )


def default_translation_policy() -> TranslationPolicy:
    """Return the only accepted translation policy."""
    return TranslationPolicy()


def empty_translation_ledger(owner_id: AgentId) -> TranslationLedger:
    """Ledger with no mappings. Disabled mode does not call this."""
    return TranslationLedger(owner_id=owner_id)


def require_owner_translation(
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
    if type(ledger) is not TranslationLedger:
        _LOG.warning("translation_carry_rejected reason=%s", "invalid_type")
        raise TypeError(f"{field_name} must be TranslationLedger")
    if ledger.owner_id != owner_id:
        _LOG.error(
            "translation_validation_failed field=%s reason_code=%s",
            field_name,
            "owner_mismatch",
        )
        _LOG.warning("translation_carry_rejected reason=%s", "owner_mismatch")
        raise ValueError(f"{field_name} owner_id mismatch")


@dataclass(frozen=True, slots=True)
class TranslationResolution:
    """Structural resolution of one foreign token against one owner ledger."""

    status: str
    binding: LabelBinding | None = None
    mapping: TranslationMapping | None = None
    target: TranslationTarget | None = None

    def __post_init__(self) -> None:
        if self.status not in {"resolved", "ambiguous", "unresolved"}:
            raise _fail("resolution.status", "unknown_status")
        if self.status == "resolved":
            if self.binding is None or self.mapping is None or self.target is None:
                raise _fail("resolution", "incomplete_resolution")
        else:
            if self.binding is not None:
                raise _fail("resolution", "unexpected_binding")


def _active_bindings(terminology: TerminologyLedger) -> tuple[LabelBinding, ...]:
    return tuple(
        binding
        for binding in terminology.bindings
        if binding.status is NamingStatus.ACTIVE and binding.merged_into is None
    )


def _own_token(
    terminology: TerminologyLedger, token: str
) -> LabelBinding | None:
    for binding in _active_bindings(terminology):
        if binding.label_token == token:
            return binding
    return None


def _top_candidate(binding: LabelBinding) -> Any:
    if not binding.candidates:
        return None
    return max(
        binding.candidates,
        key=lambda candidate: (candidate.confidence, candidate.entity_id),
    )


def _resolution_sort_key(mapping: TranslationMapping) -> tuple[float, str]:
    return (mapping.strength, mapping.mapping_id)


def translation_targets_for_kind(
    terminology: TerminologyLedger, referent_kind: NamingReferentKind
) -> tuple[LabelBinding, ...]:
    """Active own bindings of one kind, strongest first with a stable tie-break."""
    if type(terminology) is not TerminologyLedger:
        raise TypeError("terminology must be TerminologyLedger")
    if type(referent_kind) is not NamingReferentKind:
        raise TypeError("referent_kind must be NamingReferentKind")
    matches = [
        binding
        for binding in _active_bindings(terminology)
        if binding.referent_kind is referent_kind
    ]
    matches.sort(key=lambda binding: (-binding.strength, binding.binding_id))
    return tuple(matches)


def resolve_translation_token(
    ledger: TranslationLedger | None,
    terminology: TerminologyLedger,
    source_token: str,
) -> TranslationResolution:
    """Resolve a foreign token from the owner's own translation hypothesis."""
    if type(terminology) is not TerminologyLedger:
        raise TypeError("terminology must be TerminologyLedger")
    if not isinstance(source_token, str) or not _LABEL_TOKEN_RE.fullmatch(source_token):
        return TranslationResolution(status="unresolved")
    if ledger is None:
        return TranslationResolution(status="unresolved")
    if type(ledger) is not TranslationLedger:
        raise TypeError("ledger must be TranslationLedger or None")
    if ledger.owner_id != terminology.owner_id:
        raise _fail("ledger.owner_id", "owner_mismatch")
    candidates = [
        mapping
        for mapping in ledger.mappings
        if mapping.source_token == source_token
        and mapping.status is TranslationMappingStatus.ACTIVE
    ]
    if not candidates:
        return TranslationResolution(status="unresolved")
    mapping = max(candidates, key=_resolution_sort_key)
    bindings = {binding.binding_id: binding for binding in terminology.bindings}
    if mapping.fit is TranslationFit.AMBIGUOUS or len(mapping.targets) > 1:
        return TranslationResolution(
            status="ambiguous", mapping=mapping
        )
    if mapping.fit is not TranslationFit.RESOLVED or not mapping.targets:
        return TranslationResolution(
            status="ambiguous"
            if mapping.fit is TranslationFit.PARTIAL
            else "unresolved",
            mapping=mapping,
        )
    target = mapping.targets[0]
    binding = bindings.get(target.binding_id)
    if (
        binding is None
        or binding.status is not NamingStatus.ACTIVE
        or binding.label_token != target.label_token
    ):
        return TranslationResolution(status="unresolved", mapping=mapping)
    return TranslationResolution(
        status="resolved", binding=binding, mapping=mapping, target=target
    )


def _kind_of_object(value: object) -> NamingReferentKind | None:
    if not isinstance(value, str):
        return None
    try:
        return NamingReferentKind(value)
    except ValueError:
        return None


def _observed_entities(observation: Observation, kind: NamingReferentKind) -> set[str]:
    if kind is NamingReferentKind.LOCATION:
        return {item.entity_id.value for item in observation.locations}
    if kind is NamingReferentKind.AGENT:
        return {item.entity_id.value for item in observation.visible_bodies}
    if kind is NamingReferentKind.DANGEROUS_RESOURCE:
        return {item.entity_id.value for item in observation.resources}
    return set()


def _call_atoms(communication: ObservedCommunication) -> list[tuple[str, str, str]]:
    atoms: list[tuple[str, str, str]] = []
    for relation in communication.utterance.content.relations:
        subject = getattr(relation, "subject", None)
        predicate = getattr(relation, "predicate", None)
        obj = getattr(relation, "object", None)
        if (
            isinstance(subject, str)
            and isinstance(predicate, str)
            and isinstance(obj, str)
        ):
            atoms.append((subject, predicate, obj))
    return atoms


def _speaker_agent(
    identity: OwnerSafeSocialIdentity, speaker_id: EntityId
) -> AgentId | None:
    for item in identity.counterparts:
        if item.entity_id == speaker_id:
            return item.agent_id
    return None


def _teacher_ids(
    advice_delta: Sequence[object] | None,
    mentorship: object | None,
    tick: int,
    window: int,
) -> set[AgentId]:
    teachers: set[AgentId] = set()
    for item in advice_delta or ():
        if getattr(item, "act", None) is not None and str(
            getattr(item, "act", "")
        ) not in {"explain", "demonstrate", "warn"}:
            continue
        delivery = getattr(item, "delivery_tick", None)
        if isinstance(delivery, int) and tick - delivery > window:
            continue
        for attribute in ("source_agent_id", "teacher_agent_id", "actor_id"):
            candidate = getattr(item, attribute, None)
            if type(candidate) is AgentId:
                teachers.add(candidate)
                break
    bonds = getattr(mentorship, "bonds", ()) or ()
    for bond in bonds:
        role = getattr(bond, "role", None)
        role_value = getattr(role, "value", role)
        if role_value != "mentor":
            continue
        partner = getattr(bond, "partner_agent_id", None)
        if type(partner) is AgentId:
            teachers.add(partner)
    return teachers


@dataclass
class _TargetDraft:
    binding_id: str
    label_token: str
    referent_kind: NamingReferentKind
    weight: float


@dataclass
class _MappingDraft:
    source_token: str
    source_digest: str
    targets: list[_TargetDraft] = field(default_factory=list)
    status: TranslationMappingStatus = TranslationMappingStatus.CANDIDATE
    strength: float = 0.0
    evidence: list[TranslationEvidenceItem] = field(default_factory=list)
    applications: list[TranslationApplication] = field(default_factory=list)
    notices: list[str] = field(default_factory=list)
    first_tick: int = 0
    last_tick: int = 0
    last_use_tick: int | None = None
    usage_count: int = 0
    touched: bool = False


def _drafts_from(
    previous: TranslationLedger | None, owner_id: AgentId
) -> dict[str, _MappingDraft]:
    drafts: dict[str, _MappingDraft] = {}
    if previous is None:
        return drafts
    for mapping in previous.mappings:
        if mapping.owner_id != owner_id:
            raise _fail("previous.owner_id", "owner_mismatch")
        drafts[mapping.source_token] = _MappingDraft(
            source_token=mapping.source_token,
            source_digest=mapping.source_digest,
            targets=[
                _TargetDraft(
                    binding_id=target.binding_id,
                    label_token=target.label_token,
                    referent_kind=target.referent_kind,
                    weight=target.weight,
                )
                for target in mapping.targets
            ],
            status=mapping.status,
            strength=mapping.strength,
            evidence=list(mapping.evidence),
            applications=list(mapping.applications),
            notices=list(mapping.notices),
            first_tick=mapping.first_tick,
            last_tick=mapping.last_tick,
            last_use_tick=mapping.last_use_tick,
            usage_count=mapping.usage_count,
        )
    return drafts


def _notice(notices: list[str], reason: str) -> None:
    if reason in _NOTICE_REASONS and reason not in notices:
        notices.append(reason)


def _target_for(
    draft: _MappingDraft, binding: LabelBinding
) -> _TargetDraft | None:
    for target in draft.targets:
        if target.binding_id == binding.binding_id:
            return target
    return None


def _bump_target(
    draft: _MappingDraft, binding: LabelBinding, delta: float, policy: TranslationPolicy
) -> tuple[_TargetDraft | None, bool]:
    target = _target_for(draft, binding)
    if target is None:
        if len(draft.targets) >= policy.max_targets:
            return None, False
        target = _TargetDraft(
            binding_id=binding.binding_id,
            label_token=binding.label_token,
            referent_kind=binding.referent_kind,
            weight=0.0,
        )
        draft.targets.append(target)
    target.weight = _apply_delta(target.weight, delta)
    return target, True


def _record_evidence(
    draft: _MappingDraft,
    mapping_id: str,
    channel: TranslationEvidenceChannel,
    lineage_ref: str,
    tick: int,
    actor_id: AgentId | None,
    target_binding_ids: tuple[str, ...],
    policy: TranslationPolicy,
    seen: set[tuple[str, str, str, str, str]],
) -> bool:
    if not target_binding_ids:
        return False
    fresh = tuple(
        binding_id
        for binding_id in target_binding_ids
        if (
            channel.value,
            lineage_ref,
            str(tick),
            actor_id.value if actor_id else "-",
            binding_id,
        )
        not in seen
    )
    if not fresh:
        return False
    if len(draft.evidence) >= policy.max_evidence:
        _notice(draft.notices, "cap_exceeded")
        return False
    for binding_id in fresh:
        seen.add(
            (
                channel.value,
                lineage_ref,
                str(tick),
                actor_id.value if actor_id else "-",
                binding_id,
            )
        )
    ordinal = len(draft.evidence)
    draft.evidence.append(
        TranslationEvidenceItem(
            evidence_id=translation_evidence_id(
                mapping_id, ordinal, channel, lineage_ref
            ),
            ordinal=ordinal,
            channel=channel,
            lineage_ref=lineage_ref,
            tick=tick,
            actor_id=actor_id,
            target_binding_ids=fresh,
        )
    )
    return True


def _binding_map(terminology: TerminologyLedger) -> dict[str, LabelBinding]:
    return {binding.binding_id: binding for binding in terminology.bindings}


def _compute_fit(
    draft: _MappingDraft,
    terminology: TerminologyLedger,
    policy: TranslationPolicy,
) -> TranslationFit:
    if not draft.targets:
        return TranslationFit.UNRESOLVED
    ordered = sorted(draft.targets, key=lambda item: (-item.weight, item.binding_id))
    if len(ordered) > 1:
        if ordered[0].weight - ordered[1].weight <= policy.ambiguity_margin:
            return TranslationFit.AMBIGUOUS
        return TranslationFit.PARTIAL
    binding = _binding_map(terminology).get(ordered[0].binding_id)
    if binding is None or binding.status is not NamingStatus.ACTIVE:
        return TranslationFit.UNRESOLVED
    candidates = binding.candidates
    if not candidates:
        return TranslationFit.PARTIAL
    top = _top_candidate(binding)
    if top is None:
        return TranslationFit.PARTIAL
    tied = [
        candidate
        for candidate in candidates
        if _quantize(candidate.confidence) == _quantize(top.confidence)
    ]
    if len(tied) > 1:
        return TranslationFit.PARTIAL
    return TranslationFit.RESOLVED


def _freeze_mapping(
    draft: _MappingDraft,
    owner_id: AgentId,
    terminology: TerminologyLedger,
    tick: int,
    policy: TranslationPolicy,
) -> TranslationMapping | None:
    if not draft.targets:
        return None
    bindings = _binding_map(terminology)
    valid_targets: list[_TargetDraft] = []
    for target in sorted(
        draft.targets, key=lambda item: (-item.weight, item.binding_id)
    ):
        binding = bindings.get(target.binding_id)
        if binding is None or binding.status is not NamingStatus.ACTIVE:
            _notice(draft.notices, "no_candidate")
            continue
        if binding.owner_id != owner_id or binding.merged_into is not None:
            _notice(draft.notices, "owner_mismatch")
            continue
        if binding.label_token == draft.source_token:
            _notice(draft.notices, "source_self_target")
            continue
        valid_targets.append(target)
    if not valid_targets:
        return None
    targets = tuple(
        TranslationTarget(
            binding_id=item.binding_id,
            label_token=item.label_token,
            referent_kind=item.referent_kind,
            weight=item.weight,
        )
        for item in valid_targets
    )
    strength = max((item.weight for item in valid_targets), default=0.0)
    evidence_count = len(draft.evidence)
    if strength >= policy.active_strength and evidence_count >= policy.promotion_count:
        status = TranslationMappingStatus.ACTIVE
    elif strength < policy.retire_strength:
        status = TranslationMappingStatus.RETIRED
    elif draft.status is TranslationMappingStatus.ACTIVE:
        status = TranslationMappingStatus.ACTIVE
    else:
        status = TranslationMappingStatus.CANDIDATE
    fit = _compute_fit(draft, terminology, policy)
    mapping_id = translation_mapping_id(owner_id, draft.source_digest)
    mapping = TranslationMapping(
        mapping_id=mapping_id,
        owner_id=owner_id,
        source_token=draft.source_token,
        source_digest=draft.source_digest,
        source_kind=TranslationSourceKind.LABEL,
        targets=targets,
        status=status,
        fit=fit,
        strength=strength,
        evidence_count=evidence_count,
        first_tick=draft.first_tick,
        last_tick=max(draft.last_tick, tick),
        last_use_tick=draft.last_use_tick,
        usage_count=draft.usage_count,
        evidence=tuple(draft.evidence),
        applications=tuple(draft.applications),
        notices=tuple(draft.notices),
    )
    mapping.validate_against(terminology)
    return mapping


def _decay_drafts(
    drafts: dict[str, _MappingDraft],
    tick: int,
    policy: TranslationPolicy,
) -> None:
    for draft in drafts.values():
        if draft.touched or draft.last_tick >= tick:
            continue
        for target in draft.targets:
            target.weight = _apply_delta(target.weight, -policy.decay)
        draft.targets = [target for target in draft.targets if target.weight > 0.0]
        draft.strength = max((item.weight for item in draft.targets), default=0.0)
        if draft.strength < policy.retire_strength:
            draft.status = TranslationMappingStatus.RETIRED
        draft.last_tick = tick


def apply_translation_update(
    observation: object,
    identity: object,
    previous: object = None,
    terminology: object = None,
    symbolic: object = None,
    memories: Sequence[object] = (),
    advice_delta: Sequence[object] = (),
    mentorship: object | None = None,
    policy: TranslationPolicy | None = None,
) -> TranslationLedger | None:
    """Apply one tick of owner-scoped translation evidence.

    Disabled callers do not call this function. Foreign terms are inferred only
    from delivered communication, shared observation, observed artifacts, and
    owner-scoped teaching/context. The owner's own terminology ledger is the
    only source of target labels.
    """
    _LOG.debug(
        "apply_translation_update owner_id=%s tick=%s",
        getattr(getattr(identity, "owner_id", None), "value", None),
        getattr(observation, "tick", None),
    )
    for value in (
        observation,
        identity,
        previous,
        terminology,
        symbolic,
        policy,
        memories,
        advice_delta,
        mentorship,
    ):
        _reject_forbidden(value)
    if type(observation) is not Observation:
        raise TypeError("observation must be Observation")
    if type(identity) is not OwnerSafeSocialIdentity:
        raise TypeError("identity must be OwnerSafeSocialIdentity")
    if previous is not None and type(previous) is not TranslationLedger:
        raise TypeError("previous must be TranslationLedger or None")
    if type(terminology) is not TerminologyLedger:
        raise TypeError("terminology must be TerminologyLedger")
    if terminology.owner_id != identity.owner_id:
        raise _fail("terminology.owner_id", "owner_mismatch")
    require_owner_semantic_naming(
        terminology, identity.owner_id, field_name="translation.terminology"
    )
    if previous is not None and previous.owner_id != identity.owner_id:
        raise _fail("previous.owner_id", "owner_mismatch")
    active_policy = default_translation_policy() if policy is None else policy
    if type(active_policy) is not TranslationPolicy:
        raise TypeError("policy must be TranslationPolicy")

    owner_id = identity.owner_id
    tick = observation.tick
    drafts = _drafts_from(previous, owner_id)
    notices: list[str] = []
    seen: set[tuple[str, str, str, str, str]] = set()
    bindings = _active_bindings(terminology)
    teachers = _teacher_ids(
        advice_delta, mentorship, tick, active_policy.teaching_window
    )

    for index, communication in enumerate(observation.communications):
        if type(communication) is not ObservedCommunication:
            continue
        if communication.listener_id != identity.owner_entity_id:
            continue
        speaker = _speaker_agent(identity, communication.speaker_id)
        lineage = f"tick-{tick}-c{index}"
        atoms = _call_atoms(communication)
        if not atoms:
            continue
        foreign: list[tuple[str, NamingReferentKind]] = []
        own_by_kind: dict[NamingReferentKind, list[LabelBinding]] = {}
        for subject, predicate, obj in atoms:
            if predicate not in {"attributive", "relational"}:
                continue
            for own_part, other_part in ((subject, obj), (obj, subject)):
                own_binding = _own_token(terminology, own_part)
                if own_binding is None:
                    continue
                if not isinstance(other_part, str) or not _LABEL_TOKEN_RE.fullmatch(
                    other_part
                ):
                    continue
                if _own_token(terminology, other_part) is not None:
                    continue
                composition_kind = own_binding.referent_kind
                if not any(
                    binding.binding_id == own_binding.binding_id
                    for binding in own_by_kind.get(composition_kind, ())
                ):
                    own_by_kind.setdefault(composition_kind, []).append(own_binding)
                if not any(token == other_part for token, _ in foreign):
                    foreign.append((other_part, composition_kind))
        for subject, predicate, obj in atoms:
            if predicate != "call":
                continue
            if not isinstance(subject, str) or not _LABEL_TOKEN_RE.fullmatch(subject):
                _notice(notices, "illegal_token")
                continue
            kind = _kind_of_object(obj)
            if kind is None:
                continue
            own_binding = _own_token(terminology, subject)
            if own_binding is not None:
                own_by_kind.setdefault(kind, []).append(own_binding)
                continue
            if any(token == subject for token, _ in foreign):
                continue
            foreign.append((subject, kind))

        evidenced_tokens: set[str] = set()
        for source_token, kind in foreign:
            source_digest = translation_source_digest(source_token)
            mapping_id = translation_mapping_id(owner_id, source_digest)
            draft = drafts.get(source_token)
            if draft is None:
                if len(drafts) >= active_policy.max_mappings:
                    _notice(notices, "cap_exceeded")
                    continue
                draft = _MappingDraft(
                    source_token=source_token,
                    source_digest=source_digest,
                    first_tick=tick,
                    last_tick=tick,
                )
                draft.notices = []
                drafts[source_token] = draft
            own = [binding for binding in bindings if binding.referent_kind is kind]
            if not own:
                _notice(notices, "no_candidate")
                continue
            own.sort(key=lambda binding: (-binding.strength, binding.binding_id))

            # shared observation
            observed = _observed_entities(observation, kind)
            shared_targets = []
            for binding in own:
                top = _top_candidate(binding)
                if top is not None and top.entity_id in observed:
                    shared_targets.append(binding)
            if shared_targets:
                bumped: list[str] = []
                for binding in shared_targets[: active_policy.max_targets]:
                    target, ok = _bump_target(
                        draft,
                        binding,
                        active_policy.shared_observation_delta,
                        active_policy,
                    )
                    if ok and target is not None:
                        bumped.append(target.binding_id)
                if bumped and _record_evidence(
                    draft,
                    mapping_id,
                    TranslationEvidenceChannel.SHARED_OBSERVATION,
                    lineage,
                    tick,
                    speaker,
                    tuple(bumped),
                    active_policy,
                    seen,
                ):
                    evidenced_tokens.add(source_token)
                    draft.touched = True

            # demonstration
            demonstration = [
                binding
                for binding in own_by_kind.get(kind, [])
                if binding.label_token != source_token
            ]
            if demonstration:
                bumped = []
                for binding in demonstration[: active_policy.max_targets]:
                    target, ok = _bump_target(
                        draft, binding, active_policy.demonstration_delta, active_policy
                    )
                    if ok and target is not None:
                        bumped.append(target.binding_id)
                if bumped and _record_evidence(
                    draft,
                    mapping_id,
                    TranslationEvidenceChannel.DEMONSTRATION,
                    lineage,
                    tick,
                    speaker,
                    tuple(bumped),
                    active_policy,
                    seen,
                ):
                    evidenced_tokens.add(source_token)
                    draft.touched = True

            # repeated interaction
            prior_ticks = {
                item.tick
                for item in draft.evidence
                if item.actor_id is not None
                and speaker is not None
                and item.actor_id == speaker
                and item.tick < tick
            }
            if len(prior_ticks) >= 2:
                bumped = []
                for binding in own[: min(2, active_policy.max_targets)]:
                    target, ok = _bump_target(
                        draft,
                        binding,
                        active_policy.repeated_interaction_delta,
                        active_policy,
                    )
                    if ok and target is not None:
                        bumped.append(target.binding_id)
                if bumped and _record_evidence(
                    draft,
                    mapping_id,
                    TranslationEvidenceChannel.REPEATED_INTERACTION,
                    lineage,
                    tick,
                    speaker,
                    tuple(bumped),
                    active_policy,
                    seen,
                ):
                    evidenced_tokens.add(source_token)
                    draft.touched = True

            # teaching
            if speaker is not None and speaker in teachers:
                bumped = []
                for binding in own[: active_policy.max_targets]:
                    target, ok = _bump_target(
                        draft, binding, active_policy.teaching_delta, active_policy
                    )
                    if ok and target is not None:
                        bumped.append(target.binding_id)
                if bumped and _record_evidence(
                    draft,
                    mapping_id,
                    TranslationEvidenceChannel.TEACHING,
                    lineage,
                    tick,
                    speaker,
                    tuple(bumped),
                    active_policy,
                    seen,
                ):
                    evidenced_tokens.add(source_token)
                    draft.touched = True

            # context fallback
            if (
                source_token not in evidenced_tokens
                and len(own) == 1
            ):
                target, ok = _bump_target(
                    draft, own[0], active_policy.context_delta, active_policy
                )
                if ok and target is not None and _record_evidence(
                    draft,
                    mapping_id,
                    TranslationEvidenceChannel.CONTEXT,
                    lineage,
                    tick,
                    speaker,
                    (target.binding_id,),
                    active_policy,
                    seen,
                ):
                    evidenced_tokens.add(source_token)
                    draft.touched = True

    # artifact channel
    for artifact in observation.artifacts:
        if type(artifact) is not ObservedArtifact:
            continue
        entity_value = artifact.entity_id.value
        lineage = f"artifact-{entity_value}"
        for relation in artifact.content.relations:
            if relation.predicate != "call":
                continue
            source_token = relation.subject
            if not isinstance(source_token, str) or not _LABEL_TOKEN_RE.fullmatch(
                source_token
            ):
                continue
            if _own_token(terminology, source_token) is not None:
                continue
            kind = _kind_of_object(relation.object)
            if kind is None:
                continue
            own = [
                binding
                for binding in bindings
                if binding.referent_kind is kind
            ]
            if not own:
                continue
            own.sort(key=lambda binding: (-binding.strength, binding.binding_id))
            source_digest = translation_source_digest(source_token)
            mapping_id = translation_mapping_id(owner_id, source_digest)
            draft = drafts.get(source_token)
            if draft is None:
                if len(drafts) >= active_policy.max_mappings:
                    _notice(notices, "cap_exceeded")
                    continue
                draft = _MappingDraft(
                    source_token=source_token,
                    source_digest=source_digest,
                    first_tick=tick,
                    last_tick=tick,
                )
                drafts[source_token] = draft
            bumped = []
            for binding in own[: active_policy.max_targets]:
                target, ok = _bump_target(
                    draft, binding, active_policy.artifact_delta, active_policy
                )
                if ok and target is not None:
                    bumped.append(target.binding_id)
            if bumped and _record_evidence(
                draft,
                mapping_id,
                TranslationEvidenceChannel.ARTIFACT,
                lineage,
                tick,
                None,
                tuple(bumped),
                active_policy,
                seen,
            ):
                draft.touched = True

    _decay_drafts(drafts, tick, active_policy)
    mappings: list[TranslationMapping] = []
    for draft in drafts.values():
        mapping = _freeze_mapping(
            draft, owner_id, terminology, tick, active_policy
        )
        if mapping is not None:
            mappings.append(mapping)
    ledger = TranslationLedger(
        owner_id=owner_id,
        mappings=tuple(mappings),
        notices=tuple(notices),
    )
    ledger.validate_against(terminology)
    active_count = sum(
        1
        for mapping in ledger.mappings
        if mapping.status is TranslationMappingStatus.ACTIVE
    )
    ambiguous = sum(
        1 for mapping in ledger.mappings if mapping.fit is TranslationFit.AMBIGUOUS
    )
    _LOG.info(
        "translation_ledger_updated owner_id=%s mapping_count=%s active_count=%s "
        "ambiguous_count=%s",
        owner_id.value,
        len(ledger.mappings),
        active_count,
        ambiguous,
    )
    return ledger
def _is_communication_command(command: object) -> bool:
    from world.actions import Ask, Talk, Tell

    return type(command) in {Talk, Ask, Tell}


def _rebuild_command_with_relations(
    command: Any, relations: Sequence[Any]
) -> object:
    from world.actions import Ask, Talk, Tell
    from world.communications import CommunicationContent, StructuredUtterance

    content = command.utterance.content
    utterance = StructuredUtterance(
        content=CommunicationContent(
            text=content.text,
            concepts=content.concepts,
            relations=tuple(relations),
        ),
        declared=command.utterance.declared,
    )
    if type(command) is Talk:
        return Talk(recipient_id=command.recipient_id, utterance=utterance)
    if type(command) is Ask:
        return Ask(recipient_id=command.recipient_id, utterance=utterance)
    if type(command) is Tell:
        return Tell(recipient_id=command.recipient_id, utterance=utterance)
    return command  # pragma: no cover - guarded by caller


def _recipient_agent(
    identity: OwnerSafeSocialIdentity, recipient_id: EntityId
) -> AgentId | None:
    for item in identity.counterparts:
        if item.entity_id == recipient_id:
            return item.agent_id
    return None


def translation_communicate_utterance(
    command: Any,
    *,
    owner_id: AgentId,
    tick: int,
    observation: Observation,
    identity: OwnerSafeSocialIdentity | None,
    translation: object | None,
    terminology: object | None,
    mode: object | None,
    policy: TranslationPolicy | None = None,
) -> object:
    """Rewrite at most two own ``call`` terms to a foreign term for the recipient.

    Returns the command unchanged unless an active, unambiguous mapping was
    learned from the exact current recipient. Never chooses a new recipient,
    mints a command kind, or adds a relation.
    """
    from agents.cognition.configuration import CognitionTranslationMode
    from world.communications import CommunicationRelation

    if mode is not CognitionTranslationMode.DETERMINISTIC:
        return command
    if type(observation) is not Observation or observation.tick != tick:
        return command
    if not _is_communication_command(command):
        return command
    command = cast(Any, command)
    if type(translation) is not TranslationLedger or not translation.mappings:
        return command
    if type(terminology) is not TerminologyLedger or identity is None:
        return command
    if translation.owner_id != owner_id or terminology.owner_id != owner_id:
        return command
    recipient_agent = _recipient_agent(identity, command.recipient_id)
    if recipient_agent is None:
        return command
    active_policy = default_translation_policy() if policy is None else policy
    selected: list[TranslationMapping] = []
    for mapping in translation.mappings:
        if mapping.status is not TranslationMappingStatus.ACTIVE:
            continue
        if mapping.strength < active_policy.active_strength:
            continue
        if mapping.fit is not TranslationFit.RESOLVED or len(mapping.targets) != 1:
            continue
        if (
            mapping.last_use_tick is not None
            and tick - mapping.last_use_tick < active_policy.outbound_interval
        ):
            continue
        if not any(
            item.actor_id is not None and item.actor_id == recipient_agent
            for item in mapping.evidence
        ):
            continue
        selected.append(mapping)
    if not selected:
        return command
    selected.sort(key=lambda mapping: (-mapping.strength, mapping.mapping_id))
    replacements: dict[str, str] = {}
    for mapping in selected:
        if len(replacements) >= 2:
            break
        replacements[mapping.targets[0].label_token] = mapping.source_token
    if not replacements:
        return command
    rebuilt: list[Any] = []
    rewrite_count = 0
    for relation in command.utterance.content.relations:
        subject = getattr(relation, "subject", None)
        predicate = getattr(relation, "predicate", None)
        obj = getattr(relation, "object", None)
        if (
            predicate == "call"
            and isinstance(subject, str)
            and subject in replacements
            and rewrite_count < 2
        ):
            rebuilt.append(
                CommunicationRelation(
                    subject=replacements[subject],
                    predicate="call",
                    object=cast(str, obj),
                )
            )
            rewrite_count += 1
            continue
        rebuilt.append(relation)
    if rewrite_count == 0:
        return command
    _LOG.debug(
        "translation_outbound_selected owner_id=%s tick=%s recipient_id=%s "
        "mapping_status=%s rewrite_count=%s",
        owner_id.value,
        tick,
        command.recipient_id.value,
        "active",
        rewrite_count,
    )
    return _rebuild_command_with_relations(command, tuple(rebuilt))


def translation_usage_update(
    ledger: object,
    command: Any,
    *,
    tick: int,
    terminology: object | None,
    mode: object | None,
    policy: TranslationPolicy | None = None,
) -> object:
    """Commit usage for mappings whose foreign source term appears in ``command``."""
    from agents.cognition.configuration import CognitionTranslationMode

    if mode is not CognitionTranslationMode.DETERMINISTIC:
        return ledger
    if type(ledger) is not TranslationLedger or not _is_communication_command(command):
        return ledger
    command = cast(Any, command)
    if type(terminology) is not TerminologyLedger:
        return ledger
    active_policy = default_translation_policy() if policy is None else policy
    used_tokens = {
        relation.subject
        for relation in command.utterance.content.relations
        if getattr(relation, "predicate", None) == "call"
        and isinstance(getattr(relation, "subject", None), str)
    }
    changed = False
    updated: list[TranslationMapping] = []
    for mapping in ledger.mappings:
        if mapping.source_token not in used_tokens:
            updated.append(mapping)
            continue
        applications = list(mapping.applications)
        if len(applications) < active_policy.max_applications:
            ordinal = len(applications)
            target = mapping.targets[0] if mapping.targets else None
            applications.append(
                TranslationApplication(
                    application_id=translation_application_id(
                        mapping.mapping_id,
                        ordinal,
                        TranslationApplicationKind.OUTBOUND_TERM,
                        None,
                    ),
                    ordinal=ordinal,
                    tick=tick,
                    kind=TranslationApplicationKind.OUTBOUND_TERM,
                    mapping_id=mapping.mapping_id,
                    outcome=TranslationApplicationOutcome.APPLIED,
                    target_binding_id=None if target is None else target.binding_id,
                    command_kind=str(getattr(command, "kind", "talk")),
                )
            )
        updated.append(
            TranslationMapping(
                mapping_id=mapping.mapping_id,
                owner_id=mapping.owner_id,
                source_token=mapping.source_token,
                source_digest=mapping.source_digest,
                source_kind=mapping.source_kind,
                targets=mapping.targets,
                status=mapping.status,
                fit=mapping.fit,
                strength=mapping.strength,
                evidence_count=mapping.evidence_count,
                first_tick=mapping.first_tick,
                last_tick=mapping.last_tick,
                last_use_tick=tick,
                usage_count=mapping.usage_count + 1,
                evidence=mapping.evidence,
                applications=tuple(applications),
                notices=mapping.notices,
            )
        )
        changed = True
    if not changed:
        return ledger
    result = TranslationLedger(
        owner_id=ledger.owner_id,
        mappings=tuple(updated),
        notices=ledger.notices,
    )
    result.validate_against(terminology)
    _LOG.info(
        "translation_usage_committed owner_id=%s tick=%s usage_count=%s",
        ledger.owner_id.value,
        tick,
        sum(mapping.usage_count for mapping in result.mappings),
    )
    return result


def record_translation_application(
    ledger: TranslationLedger,
    terminology: TerminologyLedger,
    *,
    mapping_id: str,
    kind: TranslationApplicationKind,
    outcome: TranslationApplicationOutcome,
    tick: int,
    message_id: str | None = None,
    target_binding_id: str | None = None,
    actor_id: AgentId | None = None,
    command_kind: str | None = None,
) -> TranslationLedger:
    """Append one bounded application row. Returns the ledger unchanged at cap."""
    if type(ledger) is not TranslationLedger:
        raise TypeError("ledger must be TranslationLedger")
    if type(terminology) is not TerminologyLedger:
        raise TypeError("terminology must be TerminologyLedger")
    updated: list[TranslationMapping] = []
    changed = False
    for mapping in ledger.mappings:
        if mapping.mapping_id != mapping_id:
            updated.append(mapping)
            continue
        applications = list(mapping.applications)
        if len(applications) < _MAX_APPLICATIONS:
            ordinal = len(applications)
            applications.append(
                TranslationApplication(
                    application_id=translation_application_id(
                        mapping.mapping_id, ordinal, kind, message_id
                    ),
                    ordinal=ordinal,
                    tick=tick,
                    kind=kind,
                    mapping_id=mapping.mapping_id,
                    outcome=outcome,
                    message_id=message_id,
                    target_binding_id=target_binding_id,
                    actor_id=actor_id,
                    command_kind=command_kind,
                )
            )
        updated.append(
            TranslationMapping(
                mapping_id=mapping.mapping_id,
                owner_id=mapping.owner_id,
                source_token=mapping.source_token,
                source_digest=mapping.source_digest,
                source_kind=mapping.source_kind,
                targets=mapping.targets,
                status=mapping.status,
                fit=mapping.fit,
                strength=mapping.strength,
                evidence_count=mapping.evidence_count,
                first_tick=mapping.first_tick,
                last_tick=mapping.last_tick,
                last_use_tick=mapping.last_use_tick,
                usage_count=mapping.usage_count,
                evidence=mapping.evidence,
                applications=tuple(applications),
                notices=mapping.notices,
            )
        )
        changed = True
    if not changed:
        return ledger
    result = TranslationLedger(
        owner_id=ledger.owner_id,
        mappings=tuple(updated),
        notices=ledger.notices,
    )
    result.validate_against(terminology)
    return result
