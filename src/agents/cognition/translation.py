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


