"""Owner-local, default-off institutional decay contracts.

Decay is a private belief process, not an objective institution. The owner may
stop recognizing a recurring pattern when its own fresh evidence stops renewing
the supporting channels. Nothing here creates, destroys, transfers, or grants
authority over world state, and no collapse command or global registry exists.

The five measured dimensions (support, participation, procedure repetition,
succession continuity, knowledge continuity) are deliberately separate from the
six institution-concept strengths. Raw per-update sufficient statistics are
retained; four-tick aggregation belongs to detached analysis only.
"""

from __future__ import annotations

import hashlib
import logging
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, fields, replace
from decimal import Decimal
from enum import StrEnum
from typing import Final

from agents.cognition.institution_concepts import (
    InstitutionConcept,
    InstitutionConceptLedger,
    InstitutionConceptPolicy,
    InstitutionConceptStatus,
    InstitutionEvidenceChannel,
    InstitutionPatternChannel,
    apply_institution_concept_update,
    default_institution_concept_policy,
)
from agents.models import AgentId
from world.identifiers import require_exact_nonneg_int
from world.observations import Observation

__all__ = [
    "FORBIDDEN_INSTITUTION_DECAY_FIELD_NAMES",
    "INSTITUTIONAL_DECAY_POLICY_VERSION",
    "InstitutionDecayAvailability",
    "InstitutionDecayBinding",
    "InstitutionDecayDimension",
    "InstitutionDecayLedger",
    "InstitutionDecayPolicy",
    "InstitutionDecayReceipt",
    "InstitutionDecayRecord",
    "InstitutionDecaySample",
    "InstitutionDecaySignal",
    "InstitutionDecayUpdate",
    "InstitutionDimensionEvidence",
    "InstitutionKnowledgeAssessment",
    "append_institution_decay_receipt",
    "apply_institution_decay_update",
    "default_institutional_decay_policy",
    "empty_institution_decay_ledger",
    "institution_decay_local_pattern_id",
    "require_owner_institution_decay",
    "retain_institution_decay_sample",
]

_LOG: Final[logging.Logger] = logging.getLogger("agents.cognition.institutional_decay")

INSTITUTIONAL_DECAY_POLICY_VERSION: Final[str] = "institutional-decay.v1"
_QUANTUM: Final[Decimal] = Decimal("0.000001")
_CHANNEL_LOSS: Final[float] = 0.04
_WINDOW_TICKS: Final[int] = 4
_MAX_PATTERNS: Final[int] = 16
_MAX_SAMPLES: Final[int] = 256
_MAX_RECEIPTS: Final[int] = 512
_INACTIVE_STREAK_CAP: Final[int] = 8

_HEX: Final[frozenset[str]] = frozenset("0123456789abcdef")
_TOKEN_RE: Final[re.Pattern[str]] = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
_DIGEST_LEN: Final[int] = 16
_MAX_KEY_LEN: Final[int] = 256

_NOTICE_REASONS: Final[frozenset[str]] = frozenset(
    {
        "cap_exceeded",
        "unresolved_entity",
        "unsupported_evidence",
        "duplicate_evidence",
        "foreign_owner",
        "invalid_token",
        "pruned",
        "incomplete",
        "conflicting_update",
        "tick_regression",
    }
)

FORBIDDEN_INSTITUTION_DECAY_FIELD_NAMES: Final[frozenset[str]] = frozenset(
    {
        "government",
        "religion",
        "religious_body",
        "court",
        "police",
        "corporation",
        "political_party",
        "institution",
        "institution_id",
        "institution_type",
        "office",
        "state",
        "health_score",
        "collapse_command",
    }
)


class InstitutionDecayAvailability(StrEnum):
    """Whether one measurement lane has honest evidence."""

    OBSERVED = "observed"
    UNKNOWN = "unknown"
    DISABLED = "disabled"
    PARTIAL = "partial"
    NOT_APPLICABLE = "not_applicable"


class InstitutionDecayDimension(StrEnum):
    """Closed set of tracked continuity dimensions. No scalar health score."""

    SUPPORT = "support"
    PARTICIPATION = "participation"
    PROCEDURE_REPETITION = "procedure_repetition"
    SUCCESSION_CONTINUITY = "succession_continuity"
    KNOWLEDGE_CONTINUITY = "knowledge_continuity"


def _fail(field_name: str, code: str) -> ValueError:
    _LOG.error(
        "institution_decay_validation_failed field=%s reason_code=%s",
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


def _finite(field_name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _fail(field_name, "not_finite")
    number = float(value)
    if not math.isfinite(number):
        raise _fail(field_name, "not_finite")
    return number


def _unit(field_name: str, value: object) -> float:
    number = _quantize(_finite(field_name, value))
    if number < 0.0 or number > 1.0:
        raise _fail(field_name, "out_of_range")
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


def _nonneg_int(field_name: str, value: object) -> int:
    return require_exact_nonneg_int(field_name, value)


def _require_bool(field_name: str, value: object) -> bool:
    if type(value) is not bool:
        raise _fail(field_name, "invalid_type")
    return value


def _require_owner(field_name: str, value: object) -> AgentId:
    if type(value) is not AgentId:
        raise _fail(field_name, "invalid_type")
    return value


def _require_hex_id(field_name: str, value: object) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(char not in _HEX for char in value)
    ):
        raise _fail(field_name, "invalid_id")
    return value


def _require_digest(field_name: str, value: object) -> str:
    if (
        not isinstance(value, str)
        or len(value) != _DIGEST_LEN
        or any(char not in _HEX for char in value)
    ):
        raise _fail(field_name, "invalid_digest")
    return value


def _require_token(field_name: str, value: object) -> str:
    if not isinstance(value, str) or not _TOKEN_RE.fullmatch(value):
        raise _fail(field_name, "illegal_token")
    return value


def _require_key(field_name: str, value: object) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > _MAX_KEY_LEN
        or any(ord(char) < 32 for char in value)
    ):
        raise _fail(field_name, "invalid_key")
    return value


def _require_tuple(field_name: str, values: object) -> tuple[object, ...]:
    if isinstance(values, (str, bytes, set, frozenset)) or not isinstance(
        values, Sequence
    ):
        raise _fail(field_name, "invalid_type")
    return tuple(values)


def _require_optional_key(field_name: str, value: object) -> str | None:
    if value is None:
        return None
    return _require_key(field_name, value)


def _require_optional_agent(field_name: str, value: object) -> AgentId | None:
    if value is None:
        return None
    return _require_owner(field_name, value)


def _reject_forbidden_fields(model: type) -> None:
    names = {item.name for item in fields(model)}
    forbidden = names & FORBIDDEN_INSTITUTION_DECAY_FIELD_NAMES
    if forbidden:
        _LOG.error(
            "institution_decay_forbidden_field model=%s field_count=%s",
            model.__name__,
            len(forbidden),
        )
        raise ValueError(f"{model.__name__}: forbidden_field_name")


def institution_decay_local_pattern_id(
    owner_id: AgentId, group_key: str, inception_tick: int
) -> str:
    """Stable owner-local pattern identity, independent of mutable concepts."""
    owner = _require_owner("owner_id", owner_id)
    group = _require_hex_id("group_key", group_key)
    tick = _nonneg_int("inception_tick", inception_tick)
    return _sha256_hex(f"{owner.value}|institutional-decay|{group}|{tick}")


@dataclass(frozen=True, slots=True)
class InstitutionDecayPolicy:
    """Locked decay constants. Runner JSON never carries these values."""

    version: str = INSTITUTIONAL_DECAY_POLICY_VERSION
    channel_loss: float = _CHANNEL_LOSS
    quantum: float = float(_QUANTUM)
    window_ticks: int = _WINDOW_TICKS
    max_patterns: int = _MAX_PATTERNS
    max_samples: int = _MAX_SAMPLES
    max_receipts: int = _MAX_RECEIPTS
    inactive_streak_cap: int = _INACTIVE_STREAK_CAP

    def __post_init__(self) -> None:
        if self.version != INSTITUTIONAL_DECAY_POLICY_VERSION:
            raise _fail("version", "unsupported_policy")
        floats = (
            ("channel_loss", _CHANNEL_LOSS),
            ("quantum", float(_QUANTUM)),
        )
        for name, expected in floats:
            object.__setattr__(
                self, name, _locked_float(name, getattr(self, name), expected)
            )
        counts = (
            ("window_ticks", _WINDOW_TICKS),
            ("max_patterns", _MAX_PATTERNS),
            ("max_samples", _MAX_SAMPLES),
            ("max_receipts", _MAX_RECEIPTS),
            ("inactive_streak_cap", _INACTIVE_STREAK_CAP),
        )
        for name, expected in counts:
            object.__setattr__(
                self, name, _locked_int(name, getattr(self, name), expected)
            )


def default_institutional_decay_policy() -> InstitutionDecayPolicy:
    """Return the only accepted institutional-decay policy."""
    return InstitutionDecayPolicy()


@dataclass(frozen=True, slots=True)
class InstitutionDecaySignal:
    """One bounded input signal used by the enabled update path."""

    local_pattern_id: str
    channel: InstitutionPatternChannel
    action_key: str
    observation_tick: int
    source_tick: int
    evidence_channel: InstitutionEvidenceChannel
    actor_id: AgentId | None = None
    source_root: str | None = None
    context_key: str | None = None

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        object.__setattr__(
            self,
            "local_pattern_id",
            _require_hex_id("local_pattern_id", self.local_pattern_id),
        )
        if type(self.channel) is not InstitutionPatternChannel:
            raise _fail("channel", "unknown_channel")
        object.__setattr__(
            self, "action_key", _require_key("action_key", self.action_key)
        )
        object.__setattr__(
            self,
            "observation_tick",
            _nonneg_int("observation_tick", self.observation_tick),
        )
        object.__setattr__(
            self, "source_tick", _nonneg_int("source_tick", self.source_tick)
        )
        if self.source_tick > self.observation_tick:
            raise _fail("source_tick", "future_source")
        if type(self.evidence_channel) is not InstitutionEvidenceChannel:
            raise _fail("evidence_channel", "unknown_evidence_channel")
        object.__setattr__(
            self,
            "actor_id",
            _require_optional_agent("actor_id", self.actor_id),
        )
        object.__setattr__(
            self,
            "source_root",
            _require_optional_key("source_root", self.source_root),
        )
        object.__setattr__(
            self,
            "context_key",
            _require_optional_key("context_key", self.context_key),
        )


@dataclass(frozen=True, slots=True)
class InstitutionDecayBinding:
    """Owner-local stable identity for one recurring structural pattern."""

    local_pattern_id: str
    owner_id: AgentId
    group_key: str
    concept_id: str
    inception_tick: int
    anchor_digests: tuple[str, ...]
    structural_components: tuple[str, ...] = ()
    context_key: str | None = None
    office_id: str | None = None

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        owner = _require_owner("owner_id", self.owner_id)
        object.__setattr__(
            self, "group_key", _require_hex_id("group_key", self.group_key)
        )
        object.__setattr__(
            self, "concept_id", _require_hex_id("concept_id", self.concept_id)
        )
        object.__setattr__(
            self,
            "inception_tick",
            _nonneg_int("inception_tick", self.inception_tick),
        )
        expected = institution_decay_local_pattern_id(
            owner, self.group_key, self.inception_tick
        )
        object.__setattr__(
            self,
            "local_pattern_id",
            _require_hex_id("local_pattern_id", self.local_pattern_id),
        )
        if self.local_pattern_id != expected:
            raise _fail("local_pattern_id", "id_mismatch")
        anchors = _require_tuple("anchor_digests", self.anchor_digests)
        checked_anchors: list[str] = []
        for anchor in anchors:
            head = _require_digest("anchor_digests", anchor)
            if head in checked_anchors:
                raise _fail("anchor_digests", "duplicate_anchor")
            checked_anchors.append(head)
        if not checked_anchors:
            raise _fail("anchor_digests", "empty")
        components = _require_tuple("structural_components", self.structural_components)
        checked_components: list[str] = []
        for component in components:
            head = _require_digest("structural_components", component)
            if head in checked_components:
                raise _fail("structural_components", "duplicate_component")
            checked_components.append(head)
        object.__setattr__(self, "anchor_digests", tuple(checked_anchors))
        object.__setattr__(self, "structural_components", tuple(checked_components))
        object.__setattr__(
            self,
            "context_key",
            _require_optional_key("context_key", self.context_key),
        )
        object.__setattr__(
            self, "office_id", _require_optional_key("office_id", self.office_id)
        )


@dataclass(frozen=True, slots=True)
class InstitutionDecayRecord:
    """Factual identity/activity witnesses independent of the sample ring."""

    owner_id: AgentId
    local_pattern_id: str
    group_key: str
    concept_id: str
    anchor_digests: tuple[str, ...]
    structural_signature_key: str
    inception_tick: int
    last_activity_tick: int
    current_span_start_tick: int
    previous_span_start_tick: int | None = None
    covered_inactive_streak: int = 0
    pruned_activity_witness_count: int = 0
    sample_pruned_through_tick: int | None = None

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        owner = _require_owner("owner_id", self.owner_id)
        object.__setattr__(
            self, "group_key", _require_hex_id("group_key", self.group_key)
        )
        object.__setattr__(
            self, "concept_id", _require_hex_id("concept_id", self.concept_id)
        )
        object.__setattr__(
            self,
            "inception_tick",
            _nonneg_int("inception_tick", self.inception_tick),
        )
        expected = institution_decay_local_pattern_id(
            owner, self.group_key, self.inception_tick
        )
        object.__setattr__(
            self,
            "local_pattern_id",
            _require_hex_id("local_pattern_id", self.local_pattern_id),
        )
        if self.local_pattern_id != expected:
            raise _fail("local_pattern_id", "id_mismatch")
        anchors = _require_tuple("anchor_digests", self.anchor_digests)
        checked_anchors: list[str] = []
        for anchor in anchors:
            head = _require_digest("anchor_digests", anchor)
            if head in checked_anchors:
                raise _fail("anchor_digests", "duplicate_anchor")
            checked_anchors.append(head)
        if not checked_anchors:
            raise _fail("anchor_digests", "empty")
        object.__setattr__(self, "anchor_digests", tuple(checked_anchors))
        object.__setattr__(
            self,
            "structural_signature_key",
            _require_digest("structural_signature_key", self.structural_signature_key),
        )
        object.__setattr__(
            self,
            "last_activity_tick",
            _nonneg_int("last_activity_tick", self.last_activity_tick),
        )
        object.__setattr__(
            self,
            "current_span_start_tick",
            _nonneg_int("current_span_start_tick", self.current_span_start_tick),
        )
        if self.current_span_start_tick > self.last_activity_tick:
            raise _fail("current_span_start_tick", "after_activity")
        if self.inception_tick > self.current_span_start_tick:
            raise _fail("inception_tick", "after_span_start")
        if self.previous_span_start_tick is not None:
            object.__setattr__(
                self,
                "previous_span_start_tick",
                _nonneg_int("previous_span_start_tick", self.previous_span_start_tick),
            )
            if self.previous_span_start_tick >= self.current_span_start_tick:
                raise _fail("previous_span_start_tick", "not_before_current")
        if (
            isinstance(self.covered_inactive_streak, bool)
            or type(self.covered_inactive_streak) is not int
        ):
            raise _fail("covered_inactive_streak", "invalid_type")
        if self.covered_inactive_streak < 0 or self.covered_inactive_streak > (
            _INACTIVE_STREAK_CAP
        ):
            raise _fail("covered_inactive_streak", "out_of_range")
        object.__setattr__(
            self,
            "pruned_activity_witness_count",
            _nonneg_int(
                "pruned_activity_witness_count", self.pruned_activity_witness_count
            ),
        )
        if self.sample_pruned_through_tick is not None:
            object.__setattr__(
                self,
                "sample_pruned_through_tick",
                _nonneg_int(
                    "sample_pruned_through_tick", self.sample_pruned_through_tick
                ),
            )


@dataclass(frozen=True, slots=True)
class InstitutionKnowledgeAssessment:
    """Owner-local before/retained entry sets for one transition."""

    transition_id: str
    before_entry_ids: tuple[str, ...]
    retained_entry_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        object.__setattr__(
            self, "transition_id", _require_key("transition_id", self.transition_id)
        )
        for name in ("before_entry_ids", "retained_entry_ids"):
            values = _require_tuple(name, getattr(self, name))
            checked: list[str] = []
            for value in values:
                key = _require_key(name, value)
                if key in checked:
                    raise _fail(name, "duplicate_entry")
                checked.append(key)
            object.__setattr__(self, name, tuple(checked))


@dataclass(frozen=True, slots=True)
class InstitutionDimensionEvidence:
    """Raw per-update sufficient statistics. No rolling ratios live here."""

    observed_cohort: tuple[AgentId, ...] = ()
    supporters: tuple[tuple[AgentId, str], ...] = ()
    participant_actions: tuple[tuple[AgentId, str], ...] = ()
    performed_procedure_keys: tuple[str, ...] = ()
    succession_transitions: tuple[str, ...] = ()
    completed_transitions: tuple[str, ...] = ()
    knowledge_assessments: tuple[InstitutionKnowledgeAssessment, ...] = ()
    support_availability: InstitutionDecayAvailability = (
        InstitutionDecayAvailability.UNKNOWN
    )
    participation_availability: InstitutionDecayAvailability = (
        InstitutionDecayAvailability.UNKNOWN
    )
    procedure_availability: InstitutionDecayAvailability = (
        InstitutionDecayAvailability.UNKNOWN
    )
    succession_availability: InstitutionDecayAvailability = (
        InstitutionDecayAvailability.UNKNOWN
    )
    knowledge_availability: InstitutionDecayAvailability = (
        InstitutionDecayAvailability.UNKNOWN
    )
    source_first_tick: int | None = None
    source_last_tick: int | None = None

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        cohort = _require_tuple("observed_cohort", self.observed_cohort)
        seen_cohort: list[AgentId] = []
        for item in cohort:
            agent = _require_owner("observed_cohort", item)
            if agent in seen_cohort:
                raise _fail("observed_cohort", "duplicate_actor")
            seen_cohort.append(agent)
        object.__setattr__(
            self,
            "observed_cohort",
            tuple(sorted(seen_cohort, key=lambda item: item.value)),
        )
        supporters = _require_tuple("supporters", self.supporters)
        checked_supporters: list[tuple[AgentId, str]] = []
        for item in supporters:
            if not isinstance(item, tuple) or len(item) != 2:
                raise _fail("supporters", "invalid_type")
            agent = _require_owner("supporters", item[0])
            root = _require_key("supporters", item[1])
            pair = (agent, root)
            if pair in checked_supporters:
                raise _fail("supporters", "duplicate_supporter")
            checked_supporters.append(pair)
        object.__setattr__(
            self,
            "supporters",
            tuple(
                sorted(
                    checked_supporters,
                    key=lambda pair: (pair[0].value, pair[1]),
                )
            ),
        )
        participant_actions = _require_tuple(
            "participant_actions", self.participant_actions
        )
        checked_actions: list[tuple[AgentId, str]] = []
        for item in participant_actions:
            if not isinstance(item, tuple) or len(item) != 2:
                raise _fail("participant_actions", "invalid_type")
            agent = _require_owner("participant_actions", item[0])
            action_key = _require_key("participant_actions", item[1])
            pair = (agent, action_key)
            if pair in checked_actions:
                raise _fail("participant_actions", "duplicate_action")
            checked_actions.append(pair)
        object.__setattr__(
            self,
            "participant_actions",
            tuple(sorted(checked_actions, key=lambda pair: (pair[0].value, pair[1]))),
        )
        for name in (
            "performed_procedure_keys",
            "succession_transitions",
            "completed_transitions",
        ):
            values = _require_tuple(name, getattr(self, name))
            checked: list[str] = []
            for value in values:
                key = _require_key(name, value)
                if key in checked:
                    raise _fail(name, "duplicate_key")
                checked.append(key)
            object.__setattr__(self, name, tuple(checked))
        assessments = _require_tuple(
            "knowledge_assessments", self.knowledge_assessments
        )
        checked_assessments: list[InstitutionKnowledgeAssessment] = []
        seen_transitions: set[str] = set()
        for item in assessments:
            if type(item) is not InstitutionKnowledgeAssessment:
                raise _fail("knowledge_assessments", "invalid_type")
            if item.transition_id in seen_transitions:
                raise _fail("knowledge_assessments", "duplicate_transition")
            seen_transitions.add(item.transition_id)
            checked_assessments.append(item)
        object.__setattr__(self, "knowledge_assessments", tuple(checked_assessments))
        for name in (
            "support_availability",
            "participation_availability",
            "procedure_availability",
            "succession_availability",
            "knowledge_availability",
        ):
            if type(getattr(self, name)) is not InstitutionDecayAvailability:
                raise _fail(name, "unknown_availability")
        if self.source_first_tick is not None:
            object.__setattr__(
                self,
                "source_first_tick",
                _nonneg_int("source_first_tick", self.source_first_tick),
            )
        if self.source_last_tick is not None:
            object.__setattr__(
                self,
                "source_last_tick",
                _nonneg_int("source_last_tick", self.source_last_tick),
            )
        if self.source_first_tick is not None and self.source_last_tick is not None:
            if self.source_last_tick < self.source_first_tick:
                raise _fail("source_last_tick", "before_source_first_tick")


@dataclass(frozen=True, slots=True)
class InstitutionDecaySample:
    """One subjective measurement, not a lifecycle classification."""

    owner_id: AgentId
    local_pattern_id: str
    observation_tick: int
    source_first_tick: int
    source_last_tick: int
    role_recognition: float
    procedure_recurrence: float
    social_expectation: float
    legitimacy_belief: float
    succession_observed: float
    generational_continuity: float
    recognized: bool
    evidence: InstitutionDimensionEvidence
    anchor_digests: tuple[str, ...]
    structural_components: tuple[str, ...] = ()
    context_key: str | None = None
    office_id: str | None = None
    covered: bool = True
    pruned: bool = False

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        _require_owner("owner_id", self.owner_id)
        object.__setattr__(
            self,
            "local_pattern_id",
            _require_hex_id("local_pattern_id", self.local_pattern_id),
        )
        object.__setattr__(
            self,
            "observation_tick",
            _nonneg_int("observation_tick", self.observation_tick),
        )
        object.__setattr__(
            self,
            "source_first_tick",
            _nonneg_int("source_first_tick", self.source_first_tick),
        )
        object.__setattr__(
            self,
            "source_last_tick",
            _nonneg_int("source_last_tick", self.source_last_tick),
        )
        if self.source_first_tick > self.source_last_tick:
            raise _fail("source_first_tick", "after_source_last_tick")
        if self.source_last_tick > self.observation_tick:
            raise _fail("source_last_tick", "future_source")
        for name in (
            "role_recognition",
            "procedure_recurrence",
            "social_expectation",
            "legitimacy_belief",
            "succession_observed",
            "generational_continuity",
        ):
            object.__setattr__(self, name, _unit(name, getattr(self, name)))
        object.__setattr__(
            self, "recognized", _require_bool("recognized", self.recognized)
        )
        if type(self.evidence) is not InstitutionDimensionEvidence:
            raise _fail("evidence", "invalid_type")
        anchors = _require_tuple("anchor_digests", self.anchor_digests)
        checked_anchors: list[str] = []
        for anchor in anchors:
            head = _require_digest("anchor_digests", anchor)
            if head in checked_anchors:
                raise _fail("anchor_digests", "duplicate_anchor")
            checked_anchors.append(head)
        if not checked_anchors:
            raise _fail("anchor_digests", "empty")
        object.__setattr__(self, "anchor_digests", tuple(checked_anchors))
        components = _require_tuple("structural_components", self.structural_components)
        checked_components: list[str] = []
        for component in components:
            head = _require_digest("structural_components", component)
            if head in checked_components:
                raise _fail("structural_components", "duplicate_component")
            checked_components.append(head)
        object.__setattr__(self, "structural_components", tuple(checked_components))
        object.__setattr__(
            self,
            "context_key",
            _require_optional_key("context_key", self.context_key),
        )
        object.__setattr__(
            self, "office_id", _require_optional_key("office_id", self.office_id)
        )
        object.__setattr__(self, "covered", _require_bool("covered", self.covered))
        object.__setattr__(self, "pruned", _require_bool("pruned", self.pruned))


@dataclass(frozen=True, slots=True)
class InstitutionDecayReceipt:
    """Per pattern/channel/source dedup receipt for fresh evidence."""

    owner_id: AgentId
    local_pattern_id: str
    channel: InstitutionPatternChannel
    evidence_key: str
    source_tick: int
    observation_tick: int

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        _require_owner("owner_id", self.owner_id)
        object.__setattr__(
            self,
            "local_pattern_id",
            _require_hex_id("local_pattern_id", self.local_pattern_id),
        )
        if type(self.channel) is not InstitutionPatternChannel:
            raise _fail("channel", "unknown_channel")
        object.__setattr__(
            self, "evidence_key", _require_key("evidence_key", self.evidence_key)
        )
        object.__setattr__(
            self, "source_tick", _nonneg_int("source_tick", self.source_tick)
        )
        object.__setattr__(
            self,
            "observation_tick",
            _nonneg_int("observation_tick", self.observation_tick),
        )
        if self.source_tick > self.observation_tick:
            raise _fail("source_tick", "future_source")


def _validated_bindings(
    owner_id: AgentId, values: object
) -> tuple[InstitutionDecayBinding, ...]:
    items = _require_tuple("bindings", values)
    checked: list[InstitutionDecayBinding] = []
    seen: set[str] = set()
    for item in items:
        if type(item) is not InstitutionDecayBinding:
            raise _fail("bindings", "invalid_type")
        if item.owner_id != owner_id:
            raise _fail("bindings.owner_id", "owner_mismatch")
        if item.local_pattern_id in seen:
            raise _fail("bindings", "duplicate_pattern")
        seen.add(item.local_pattern_id)
        checked.append(item)
    if len(checked) > _MAX_PATTERNS:
        raise _fail("bindings", "cap_exceeded")
    return tuple(checked)


def _validated_records(
    owner_id: AgentId, values: object, bindings: Sequence[InstitutionDecayBinding]
) -> tuple[InstitutionDecayRecord, ...]:
    items = _require_tuple("records", values)
    known = {binding.local_pattern_id for binding in bindings}
    checked: list[InstitutionDecayRecord] = []
    seen: set[str] = set()
    for item in items:
        if type(item) is not InstitutionDecayRecord:
            raise _fail("records", "invalid_type")
        if item.owner_id != owner_id:
            raise _fail("records.owner_id", "owner_mismatch")
        if item.local_pattern_id not in known:
            raise _fail("records.local_pattern_id", "unknown_pattern")
        if item.local_pattern_id in seen:
            raise _fail("records", "duplicate_pattern")
        seen.add(item.local_pattern_id)
        checked.append(item)
    return tuple(checked)


def _validated_samples(
    owner_id: AgentId, values: object, bindings: Sequence[InstitutionDecayBinding]
) -> tuple[InstitutionDecaySample, ...]:
    items = _require_tuple("samples", values)
    known = {binding.local_pattern_id for binding in bindings}
    checked: list[InstitutionDecaySample] = []
    seen: set[tuple[int, str]] = set()
    previous: tuple[int, str] | None = None
    for item in items:
        if type(item) is not InstitutionDecaySample:
            raise _fail("samples", "invalid_type")
        if item.owner_id != owner_id:
            raise _fail("samples.owner_id", "owner_mismatch")
        if item.local_pattern_id not in known:
            raise _fail("samples.local_pattern_id", "unknown_pattern")
        key = (item.observation_tick, item.local_pattern_id)
        if key in seen:
            raise _fail("samples", "duplicate_sample")
        if previous is not None and key < previous:
            raise _fail("samples", "not_ordered")
        seen.add(key)
        previous = key
        checked.append(item)
    if len(checked) > _MAX_SAMPLES:
        raise _fail("samples", "cap_exceeded")
    return tuple(checked)


def _validated_receipts(
    owner_id: AgentId,
    values: object,
    bindings: Sequence[InstitutionDecayBinding],
    pruned_through: int | None,
) -> tuple[InstitutionDecayReceipt, ...]:
    items = _require_tuple("receipts", values)
    known = {binding.local_pattern_id for binding in bindings}
    checked: list[InstitutionDecayReceipt] = []
    seen: set[tuple[str, InstitutionPatternChannel, str]] = set()
    previous: tuple[int, str] | None = None
    for item in items:
        if type(item) is not InstitutionDecayReceipt:
            raise _fail("receipts", "invalid_type")
        if item.owner_id != owner_id:
            raise _fail("receipts.owner_id", "owner_mismatch")
        if item.local_pattern_id not in known:
            raise _fail("receipts.local_pattern_id", "unknown_pattern")
        key = (item.local_pattern_id, item.channel, item.evidence_key)
        if key in seen:
            raise _fail("receipts", "duplicate_receipt")
        if pruned_through is not None and item.source_tick <= pruned_through:
            raise _fail("receipts.source_tick", "pruned")
        order = (item.source_tick, item.evidence_key)
        if previous is not None and order < previous:
            raise _fail("receipts", "not_ordered")
        seen.add(key)
        previous = order
        checked.append(item)
    if len(checked) > _MAX_RECEIPTS:
        raise _fail("receipts", "cap_exceeded")
    return tuple(checked)


@dataclass(frozen=True, slots=True)
class InstitutionDecayLedger:
    """Owner-scoped decay history. ``None`` means the mode is off."""

    owner_id: AgentId
    bindings: tuple[InstitutionDecayBinding, ...] = ()
    records: tuple[InstitutionDecayRecord, ...] = ()
    samples: tuple[InstitutionDecaySample, ...] = ()
    receipts: tuple[InstitutionDecayReceipt, ...] = ()
    last_update_tick: int | None = None
    receipt_pruned_through_source_tick: int | None = None
    sample_count_pruned: int = 0
    receipt_count_pruned: int = 0
    notices: tuple[str, ...] = ()
    policy_version: str = INSTITUTIONAL_DECAY_POLICY_VERSION

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        owner = _require_owner("owner_id", self.owner_id)
        if self.policy_version != INSTITUTIONAL_DECAY_POLICY_VERSION:
            raise _fail("policy_version", "unsupported_policy")
        bindings = _validated_bindings(owner, self.bindings)
        records = _validated_records(owner, self.records, bindings)
        samples = _validated_samples(owner, self.samples, bindings)
        if self.receipt_pruned_through_source_tick is not None:
            object.__setattr__(
                self,
                "receipt_pruned_through_source_tick",
                _nonneg_int(
                    "receipt_pruned_through_source_tick",
                    self.receipt_pruned_through_source_tick,
                ),
            )
        receipts = _validated_receipts(
            owner,
            self.receipts,
            bindings,
            self.receipt_pruned_through_source_tick,
        )
        if self.last_update_tick is not None:
            object.__setattr__(
                self,
                "last_update_tick",
                _nonneg_int("last_update_tick", self.last_update_tick),
            )
            for sample in samples:
                if sample.observation_tick > self.last_update_tick:
                    raise _fail("last_update_tick", "before_sample")
        object.__setattr__(
            self,
            "sample_count_pruned",
            _nonneg_int("sample_count_pruned", self.sample_count_pruned),
        )
        object.__setattr__(
            self,
            "receipt_count_pruned",
            _nonneg_int("receipt_count_pruned", self.receipt_count_pruned),
        )
        notices = _require_tuple("notices", self.notices)
        checked_notices: list[str] = []
        for item in notices:
            if not isinstance(item, str) or item not in _NOTICE_REASONS:
                raise _fail("notices", "invalid_notice")
            if item not in checked_notices:
                checked_notices.append(item)
        object.__setattr__(self, "bindings", bindings)
        object.__setattr__(self, "records", records)
        object.__setattr__(self, "samples", samples)
        object.__setattr__(self, "receipts", receipts)
        object.__setattr__(self, "notices", tuple(checked_notices))
        _LOG.debug(
            "institution_decay_ledger_constructed owner_id=%s policy_version=%s "
            "pattern_count=%s sample_count=%s receipt_count=%s",
            owner.value,
            self.policy_version,
            len(self.bindings),
            len(self.samples),
            len(self.receipts),
        )


@dataclass(frozen=True, slots=True)
class InstitutionDecayUpdate:
    """Paired owner-local concepts and decay history from one update."""

    concepts: InstitutionConceptLedger
    decay: InstitutionDecayLedger

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        if type(self.concepts) is not InstitutionConceptLedger:
            raise _fail("concepts", "invalid_type")
        if type(self.decay) is not InstitutionDecayLedger:
            raise _fail("decay", "invalid_type")
        if self.concepts.owner_id != self.decay.owner_id:
            raise _fail("decay.owner_id", "owner_mismatch")


def empty_institution_decay_ledger(owner_id: AgentId) -> InstitutionDecayLedger:
    """Ledger with no patterns or samples. Disabled mode does not call this."""
    return InstitutionDecayLedger(owner_id=owner_id)


def require_owner_institution_decay(
    value: object,
    owner_id: AgentId,
    *,
    field_name: str = "institutional_decay",
) -> None:
    """Reject a foreign or mistyped sidecar. ``None`` is passthrough."""
    if value is None:
        return
    _require_owner("owner_id", owner_id)
    if type(value) is not InstitutionDecayLedger:
        _LOG.warning("institution_decay_carry_rejected reason=%s", "invalid_type")
        raise TypeError(f"{field_name} must be InstitutionDecayLedger")
    if value.owner_id != owner_id:
        _LOG.error(
            "institution_decay_validation_failed field=%s reason_code=%s",
            field_name,
            "owner_mismatch",
        )
        _LOG.warning("institution_decay_carry_rejected reason=%s", "owner_mismatch")
        raise ValueError(f"{field_name} owner_id mismatch")


def _updated_record_pruning(
    record: InstitutionDecayRecord, evicted_tick: int
) -> InstitutionDecayRecord:
    boundary = (
        evicted_tick
        if record.sample_pruned_through_tick is None
        else max(record.sample_pruned_through_tick, evicted_tick)
    )
    return replace(record, sample_pruned_through_tick=boundary)


def retain_institution_decay_sample(
    ledger: InstitutionDecayLedger,
    sample: InstitutionDecaySample,
    *,
    policy: InstitutionDecayPolicy | None = None,
) -> InstitutionDecayLedger:
    """Append one sample, pruning oldest by ``(tick, pattern)`` deterministically."""
    if type(ledger) is not InstitutionDecayLedger:
        raise TypeError("ledger must be InstitutionDecayLedger")
    if type(sample) is not InstitutionDecaySample:
        raise TypeError("sample must be InstitutionDecaySample")
    if sample.owner_id != ledger.owner_id:
        raise _fail("sample.owner_id", "owner_mismatch")
    if sample.local_pattern_id not in {
        binding.local_pattern_id for binding in ledger.bindings
    }:
        raise _fail("sample.local_pattern_id", "unknown_pattern")
    active = default_institutional_decay_policy() if policy is None else policy
    if type(active) is not InstitutionDecayPolicy:
        raise TypeError("policy must be InstitutionDecayPolicy or None")
    existing = {
        (item.observation_tick, item.local_pattern_id): item for item in ledger.samples
    }
    key = (sample.observation_tick, sample.local_pattern_id)
    previous = existing.get(key)
    if previous is not None:
        if previous != sample:
            raise _fail("sample", "conflicting_duplicate")
        return ledger
    samples = sorted(
        [*ledger.samples, sample],
        key=lambda item: (item.observation_tick, item.local_pattern_id),
    )
    pruned = 0
    records = {record.local_pattern_id: record for record in ledger.records}
    while len(samples) > active.max_samples:
        evicted = samples.pop(0)
        pruned += 1
        record = records.get(evicted.local_pattern_id)
        if record is not None:
            records[evicted.local_pattern_id] = _updated_record_pruning(
                record, evicted.observation_tick
            )
    return replace(
        ledger,
        samples=tuple(samples),
        records=tuple(records[item.local_pattern_id] for item in ledger.records),
        sample_count_pruned=ledger.sample_count_pruned + pruned,
    )


def append_institution_decay_receipt(
    ledger: InstitutionDecayLedger,
    receipt: InstitutionDecayReceipt,
    *,
    policy: InstitutionDecayPolicy | None = None,
) -> InstitutionDecayLedger:
    """Append one receipt, pruning oldest ``(source_tick, key)`` deterministically."""
    if type(ledger) is not InstitutionDecayLedger:
        raise TypeError("ledger must be InstitutionDecayLedger")
    if type(receipt) is not InstitutionDecayReceipt:
        raise TypeError("receipt must be InstitutionDecayReceipt")
    if receipt.owner_id != ledger.owner_id:
        raise _fail("receipt.owner_id", "owner_mismatch")
    if receipt.local_pattern_id not in {
        binding.local_pattern_id for binding in ledger.bindings
    }:
        raise _fail("receipt.local_pattern_id", "unknown_pattern")
    active = default_institutional_decay_policy() if policy is None else policy
    if type(active) is not InstitutionDecayPolicy:
        raise TypeError("policy must be InstitutionDecayPolicy or None")
    if (
        ledger.receipt_pruned_through_source_tick is not None
        and receipt.source_tick <= ledger.receipt_pruned_through_source_tick
    ):
        raise _fail("receipt.source_tick", "pruned")
    for item in ledger.receipts:
        if (
            item.local_pattern_id == receipt.local_pattern_id
            and item.channel is receipt.channel
            and item.evidence_key == receipt.evidence_key
        ):
            if item != receipt:
                raise _fail("receipt", "conflicting_duplicate")
            return ledger
    receipts = sorted(
        [*ledger.receipts, receipt],
        key=lambda item: (item.source_tick, item.evidence_key),
    )
    pruned = 0
    boundary = ledger.receipt_pruned_through_source_tick
    while len(receipts) > active.max_receipts:
        evicted = receipts.pop(0)
        pruned += 1
        boundary = (
            evicted.source_tick
            if boundary is None
            else max(boundary, evicted.source_tick)
        )
    return replace(
        ledger,
        receipts=tuple(receipts),
        receipt_pruned_through_source_tick=boundary,
        receipt_count_pruned=ledger.receipt_count_pruned + pruned,
    )


