"""Owner-scoped scientific replication. A design is not objective truth.

This module holds only detached, frozen owner state. It never imports private
world modules, never constructs authority tokens, and never executes effects.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Final, NoReturn

from agents.cognition.experimentation import HypothesisCondition
from agents.models import AgentId
from world.experimentation import (
    ExperimentOperator,
    ExperimentOutcomeClass,
    ExperimentProcessToken,
)

_LOG: Final[logging.Logger] = logging.getLogger("agents.cognition.replication")

REPLICATION_POLICY_VERSION: Final[str] = "scientific-replication.v1"

MAX_DESIGNS: Final[int] = 32
MAX_ATTEMPTS: Final[int] = 128
MAX_OUTBOX_ENTRIES: Final[int] = 128
MAX_SEND_ATTEMPTS: Final[int] = 3
MAX_RESULT_REPORTS: Final[int] = 256
MAX_INTERPRETATIONS: Final[int] = 256
MAX_DELIVERY_RECEIPTS: Final[int] = 256
MAX_COLLABORATIONS: Final[int] = 32
MAX_PARTICIPANTS: Final[int] = 8
MAX_INTERPRETATION_REVISIONS: Final[int] = 32
MAX_SOURCE_DRAFTS: Final[int] = 32
MAX_NOTICE_CODES: Final[int] = 16
MAX_DESIGN_CONDITIONS: Final[int] = 8

_ID_HEX = re.compile(r"^[0-9a-f]{32}$")
_RECEIPT_ORIGIN = re.compile(r"^(?:rorg|rrep|rtrl)-[0-9a-f]{32}$")
_KIND_TOKEN = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_REFERENCE_MAX_LEN: Final[int] = 160
_MESSAGE_TOKEN_MAX_LEN: Final[int] = 128


class ReplicationError(ValueError):
    """Stable-code replication contract violation with no payload detail."""

    __slots__ = ("code",)

    def __init__(self, code: str) -> None:
        if not isinstance(code, str) or not code:
            raise ValueError("replication_invalid_error_code")
        self.code: str = code
        super().__init__(code)


def _fail(code: str) -> NoReturn:
    raise ReplicationError(code)


class ReplicationSelectorFamily(StrEnum):
    """Closed visible entity families a design selector may name."""

    ITEM = "item"
    RESOURCE = "resource"
    STRUCTURE = "structure"
    ARTIFACT = "artifact"


class ReplicationBindingMode(StrEnum):
    """Exact reference data or an observation-only same-kind binding."""

    EXACT = "exact"
    SAME_KIND = "same_kind"


class ReplicationRelationKind(StrEnum):
    """How one attempt relates to the rehearsed source trial."""

    REPEAT = "repeat"
    ADAPTED = "adapted"
    UNKNOWN = "unknown"


class ReplicationNoticeCode(StrEnum):
    """Closed owner-local notice codes. No notice carries a payload."""

    DESIGN_CAPACITY = "design_capacity"
    DRAFT_CAPACITY = "draft_capacity"
    ATTEMPT_CAPACITY = "attempt_capacity"
    OUTBOX_CAPACITY = "outbox_capacity"
    REPORT_CAPACITY = "report_capacity"
    INTERPRETATION_CAPACITY = "interpretation_capacity"
    RECEIPT_CAPACITY = "receipt_capacity"
    COLLABORATION_CAPACITY = "collaboration_capacity"
    DESIGN_UNAVAILABLE = "design_unavailable"
    SOURCE_RESULT_MISSING = "source_result_missing"
    UNKNOWN_PARENT = "unknown_parent"
    DUPLICATE_DELIVERY = "duplicate_delivery"
    INVALID_DESIGN = "invalid_design"
    SELECTOR_UNAVAILABLE = "selector_unavailable"
    CONDITION_UNKNOWN = "condition_unknown"
    REPLY_UNROUTABLE = "reply_unroutable"


class ReplicationOutboxStatus(StrEnum):
    """Closed transport lifecycle for one recipient-specific message."""

    PENDING = "pending"
    PROPOSED = "proposed"
    ATTEMPTED = "attempted"
    DELIVERY_OBSERVED = "delivery_observed"
    DELIVERY_UNKNOWN = "delivery_unknown"
    UNSENDABLE = "unsendable"
    CANCELLED = "cancelled"


class ReplicationInvitationStatus(StrEnum):
    """Closed owner-local collaboration lifecycle."""

    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    ATTEMPTED = "attempted"
    COMPLETED = "completed"
    UNRESOLVED = "unresolved"


class ReplicationAttemptState(StrEnum):
    """Observed result is the only successful measurement state."""

    PLANNED = "planned"
    PROPOSED = "proposed"
    OBSERVED = "observed"
    REJECTED = "rejected"
    UNRESOLVED = "unresolved"
    CANCELLED = "cancelled"


class ReplicationConditionComparison(StrEnum):
    """Slot-level comparison of the design and the actual attempt."""

    MATCHED = "matched"
    DIFFERENT = "different"
    UNKNOWN = "unknown"


class ReplicationMeasurementBasis(StrEnum):
    """Provenance of one result measurement. Never an independence claim."""

    OWN_OBSERVATION = "own_observation"
    COMMUNICATED = "communicated"
    UNKNOWN = "unknown"


class ReplicationUncertaintyKind(StrEnum):
    """Explicit measurement-resolution statement."""

    UNREPORTED = "unreported"
    DECLARED_SET = "declared_set"


class ReplicationMeasurementResolution(StrEnum):
    """Current physics exposes categorical outcomes, not numeric intervals."""

    OUTCOME_CLASS = "outcome_class"


class ReplicationCollaborationAct(StrEnum):
    """Closed speech acts about participation. Intent is not execution."""

    INVITE = "invite"
    PARTICIPATE = "participate"
    DECLINE = "decline"


class ReplicationCategoricalAppraisal(StrEnum):
    """Owner-relative categorical reading. Never objective truth."""

    COMPATIBLE = "compatible"
    CONFLICTING = "conflicting"
    INCONCLUSIVE = "inconclusive"
    NOT_COMPARABLE = "not_comparable"


class ReplicationSourceAppraisal(StrEnum):
    """How one owner currently regards one source. Never reliability truth."""

    OWN_OBSERVATION = "own_observation"
    TRUSTED_TESTIMONY = "trusted_testimony"
    CONTESTED_TESTIMONY = "contested_testimony"
    UNKNOWN = "unknown"


class ReplicationRevisionReason(StrEnum):
    """Closed reasons for one append-only interpretation revision."""

    EVIDENCE_ADDED = "evidence_added"
    SOURCE_REAPPRAISED = "source_reappraised"
    UNCERTAINTY_NOTED = "uncertainty_noted"
    CONDITION_RECHECKED = "condition_rechecked"



_ATTEMPT_TRANSITIONS: Final[Mapping[ReplicationAttemptState, frozenset[str]]] = (
    MappingProxyType(
        {
            ReplicationAttemptState.PLANNED: frozenset({"proposed", "cancelled"}),
            ReplicationAttemptState.PROPOSED: frozenset(
                {"observed", "rejected", "unresolved", "cancelled"}
            ),
            ReplicationAttemptState.OBSERVED: frozenset(),
            ReplicationAttemptState.REJECTED: frozenset(),
            ReplicationAttemptState.UNRESOLVED: frozenset({"cancelled"}),
            ReplicationAttemptState.CANCELLED: frozenset(),
        }
    )
)



@dataclass(frozen=True, slots=True)
class ReplicationPolicy:
    """Locked owner-local replication bounds.

    Every value is part of the accepted contract. Any deviation is a
    programming error and fails closed with ``replication_policy_not_locked``.
    """

    version: str = REPLICATION_POLICY_VERSION
    max_designs: int = MAX_DESIGNS
    max_attempts: int = MAX_ATTEMPTS
    max_outbox_entries: int = MAX_OUTBOX_ENTRIES
    max_send_attempts: int = MAX_SEND_ATTEMPTS
    max_result_reports: int = MAX_RESULT_REPORTS
    max_interpretations: int = MAX_INTERPRETATIONS
    max_delivery_receipts: int = MAX_DELIVERY_RECEIPTS
    max_collaborations: int = MAX_COLLABORATIONS
    max_participants: int = MAX_PARTICIPANTS
    max_interpretation_revisions: int = MAX_INTERPRETATION_REVISIONS
    max_source_drafts: int = MAX_SOURCE_DRAFTS
    max_notice_codes: int = MAX_NOTICE_CODES
    trust_threshold_high: float = 0.75
    trust_threshold_low: float = 0.25

    def __post_init__(self) -> None:
        for name, expected in _LOCKED_POLICY_VALUES.items():
            actual = getattr(self, name)
            if type(actual) is not type(expected) or actual != expected:
                _fail("replication_policy_not_locked")


_LOCKED_POLICY_VALUES: Final[Mapping[str, str | int | float]] = MappingProxyType(
    {
        "version": REPLICATION_POLICY_VERSION,
        "max_designs": MAX_DESIGNS,
        "max_attempts": MAX_ATTEMPTS,
        "max_outbox_entries": MAX_OUTBOX_ENTRIES,
        "max_send_attempts": MAX_SEND_ATTEMPTS,
        "max_result_reports": MAX_RESULT_REPORTS,
        "max_interpretations": MAX_INTERPRETATIONS,
        "max_delivery_receipts": MAX_DELIVERY_RECEIPTS,
        "max_collaborations": MAX_COLLABORATIONS,
        "max_participants": MAX_PARTICIPANTS,
        "max_interpretation_revisions": MAX_INTERPRETATION_REVISIONS,
        "max_source_drafts": MAX_SOURCE_DRAFTS,
        "max_notice_codes": MAX_NOTICE_CODES,
        "trust_threshold_high": 0.75,
        "trust_threshold_low": 0.25,
    }
)

_DEFAULT_POLICY: Final[ReplicationPolicy] = ReplicationPolicy()
_LOG.debug(
    "replication_policy_constructed policy_version=%s",
    REPLICATION_POLICY_VERSION,
)


def default_replication_policy() -> ReplicationPolicy:
    """Return the single locked policy instance."""

    return _DEFAULT_POLICY


def require_replication_policy(policy: object | None) -> ReplicationPolicy:
    """Require the locked policy, installing the default when absent."""

    if policy is None:
        return _DEFAULT_POLICY
    if type(policy) is not ReplicationPolicy:
        _fail("replication_policy_mismatch")
    return policy


def _require_owner(value: object) -> AgentId:
    if type(value) is not AgentId:
        _fail("replication_invalid_owner")
    return value


def _require_tick(value: object) -> int:
    if isinstance(value, bool) or type(value) is not int or value < 0:
        _fail("replication_invalid_tick")
    return value


def _require_text(value: object, code: str) -> str:
    if type(value) is not str or not value or value != value.strip():
        _fail(code)
    if len(value) > _REFERENCE_MAX_LEN or any(ord(char) < 32 for char in value):
        _fail(code)
    return value


def _require_reference(value: object, code: str) -> str:
    return _require_text(value, code)


def _require_prefixed_digest(value: object, prefix: str) -> str:
    if type(value) is not str or not value.startswith(f"{prefix}-"):
        _fail("replication_invalid_id")
    digest = value[len(prefix) + 1 :]
    if _ID_HEX.fullmatch(digest) is None:
        _fail("replication_invalid_id")
    return value


def _require_kind(value: object) -> str:
    if type(value) is not str or _KIND_TOKEN.fullmatch(value) is None:
        _fail("replication_invalid_kind")
    return value


_NAMESPACE_PREFIXES: Final[frozenset[str]] = frozenset(
    {"rorg", "rhyp", "rtrl", "rrep", "rlrep", "ratt", "rinv", "rint", "rgcl", "rpart"}
)


def _json_ready(value: object) -> str:
    if type(value) is str:
        return value
    if isinstance(value, StrEnum):
        return value.value
    raw = getattr(value, "value", None)
    if type(raw) is str:
        return raw
    if type(value) is int and not isinstance(value, bool):
        return str(value)
    raise ReplicationError("replication_invalid_reference_value")


def replication_ref(namespace: str, *values: object) -> str:
    """Return one closed-namespace content reference.

    References are identity helpers, not authenticity claims. The first 32 hex
    characters of SHA-256 over canonical ASCII JSON are used.
    """

    if namespace not in _NAMESPACE_PREFIXES:
        raise ReplicationError("replication_invalid_namespace")
    payload = [
        REPLICATION_POLICY_VERSION,
        namespace,
        *(_json_ready(value) for value in values),
    ]
    try:
        material = json.dumps(
            payload,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ReplicationError("replication_invalid_reference_value") from exc
    digest = hashlib.sha256(material.encode("ascii")).hexdigest()[:32]
    reference = f"{namespace}-{digest}"
    _LOG.debug(
        "replication_reference_derived namespace=%s reference_prefix=%s",
        namespace,
        reference[:12],
    )
    return reference


def _require_optional_reference(value: object, code: str) -> str | None:
    if value is None:
        return None
    return _require_reference(value, code)


def _validated_conditions(
    conditions: object,
) -> tuple[HypothesisCondition, ...]:
    if not isinstance(conditions, tuple):
        _fail("replication_invalid_conditions")
    if len(conditions) > MAX_DESIGN_CONDITIONS:
        _fail("replication_condition_capacity")
    seen: set[str] = set()
    for condition in conditions:
        if type(condition) is not HypothesisCondition:
            _fail("replication_invalid_conditions")
        slot = condition.slot.value
        if slot in seen:
            _fail("replication_duplicate_condition")
        seen.add(slot)
    return tuple(sorted(conditions, key=lambda row: row.slot.value))


@dataclass(frozen=True, slots=True)
class ExperimentSelector:
    """Visible family/kind selector. Exact IDs are reference data, not proof."""

    family: ReplicationSelectorFamily
    kind: str
    binding_mode: ReplicationBindingMode
    exact_entity_id: str | None = None

    def __post_init__(self) -> None:
        if type(self.family) is not ReplicationSelectorFamily:
            _fail("replication_invalid_selector")
        if type(self.binding_mode) is not ReplicationBindingMode:
            _fail("replication_invalid_selector")
        object.__setattr__(self, "kind", _require_kind(self.kind))
        if self.binding_mode is ReplicationBindingMode.EXACT:
            if self.exact_entity_id is None:
                _fail("replication_invalid_selector")
            object.__setattr__(
                self,
                "exact_entity_id",
                _require_reference(
                    self.exact_entity_id, "replication_invalid_selector"
                ),
            )
        elif self.exact_entity_id is not None:
            _fail("replication_invalid_selector")


def _optional_selector(value: object) -> ExperimentSelector | None:
    if value is None:
        return None
    if type(value) is not ExperimentSelector:
        _fail("replication_invalid_selector")
    return value


@dataclass(frozen=True, slots=True)
class ExperimentDesign:
    """Immutable full-content procedure identity.

    ``design_token`` covers every other field through the canonical preimage in
    :mod:`agents.cognition.replication_designs`. A design never carries a
    hypothesis status, confidence, transport ID, or receiver-local row ID.
    """

    design_token: str
    origin_token: str
    parent_design_token: str | None
    source_hypothesis_token: str
    source_trial_token: str
    created_tick: int
    operator: ExperimentOperator
    process_token: ExperimentProcessToken
    operand_a_selector: ExperimentSelector
    operand_b_selector: ExperimentSelector | None
    predicted_outcome: ExperimentOutcomeClass | None
    conditions: tuple[HypothesisCondition, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "design_token", _require_prefixed_digest(self.design_token, "rdes")
        )
        object.__setattr__(
            self, "origin_token", _require_prefixed_digest(self.origin_token, "rorg")
        )
        if self.parent_design_token is not None:
            object.__setattr__(
                self,
                "parent_design_token",
                _require_prefixed_digest(self.parent_design_token, "rdes"),
            )
        object.__setattr__(
            self,
            "source_hypothesis_token",
            _require_prefixed_digest(self.source_hypothesis_token, "rhyp"),
        )
        object.__setattr__(
            self,
            "source_trial_token",
            _require_prefixed_digest(self.source_trial_token, "rtrl"),
        )
        object.__setattr__(self, "created_tick", _require_tick(self.created_tick))
        if type(self.operator) is not ExperimentOperator:
            _fail("replication_invalid_operator")
        if type(self.process_token) is not ExperimentProcessToken:
            _fail("replication_invalid_process")
        if type(self.operand_a_selector) is not ExperimentSelector:
            _fail("replication_invalid_selector")
        _optional_selector(self.operand_b_selector)
        if self.predicted_outcome is not None and (
            type(self.predicted_outcome) is not ExperimentOutcomeClass
        ):
            _fail("replication_invalid_outcome")
        object.__setattr__(
            self, "conditions", _validated_conditions(self.conditions)
        )


@dataclass(frozen=True, slots=True)
class ReplicationSourceDraft:
    """Pre-action owner-safe descriptor for a locally original test.

    A draft exists only until the actor-visible result can freeze a source
    design. It never reconstructs a consumed operand from hidden world state.
    """

    owner_id: AgentId
    actor_entity_id: str
    created_tick: int
    hypothesis_id: str
    operator: ExperimentOperator
    process_token: ExperimentProcessToken
    operand_a_selector: ExperimentSelector
    operand_b_selector: ExperimentSelector | None
    predicted_outcome: ExperimentOutcomeClass | None
    conditions: tuple[HypothesisCondition, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "owner_id", _require_owner(self.owner_id))
        object.__setattr__(
            self,
            "actor_entity_id",
            _require_reference(self.actor_entity_id, "replication_invalid_actor"),
        )
        object.__setattr__(self, "created_tick", _require_tick(self.created_tick))
        if type(self.hypothesis_id) is not str or not self.hypothesis_id:
            _fail("replication_invalid_hypothesis")
        if type(self.operator) is not ExperimentOperator:
            _fail("replication_invalid_operator")
        if type(self.process_token) is not ExperimentProcessToken:
            _fail("replication_invalid_process")
        if type(self.operand_a_selector) is not ExperimentSelector:
            _fail("replication_invalid_selector")
        _optional_selector(self.operand_b_selector)
        if self.predicted_outcome is not None and (
            type(self.predicted_outcome) is not ExperimentOutcomeClass
        ):
            _fail("replication_invalid_outcome")
        object.__setattr__(
            self, "conditions", _validated_conditions(self.conditions)
        )


@dataclass(frozen=True, slots=True)
class ReplicationOutboxEntry:
    """One recipient-specific attempted message. Behavior-significant state."""

    owner_id: AgentId
    recipient_entity_id: str
    message_kind: str
    message_token: str
    design_token: str | None
    invitation_token: str | None
    prerequisite_message_token: str | None
    proposed_tick: int
    attempted_tick: int | None = None
    attempt_count: int = 0
    observed_delivery_event_id: str | None = None
    status: ReplicationOutboxStatus = ReplicationOutboxStatus.PENDING

    def __post_init__(self) -> None:
        object.__setattr__(self, "owner_id", _require_owner(self.owner_id))
        object.__setattr__(
            self,
            "recipient_entity_id",
            _require_reference(
                self.recipient_entity_id, "replication_invalid_recipient"
            ),
        )
        if self.message_kind not in _MESSAGE_KINDS:
            _fail("replication_invalid_message_kind")
        if (
            type(self.message_token) is not str
            or not self.message_token
            or len(self.message_token) > _MESSAGE_TOKEN_MAX_LEN
        ):
            _fail("replication_invalid_message_token")
        if self.design_token is not None:
            object.__setattr__(
                self,
                "design_token",
                _require_prefixed_digest(self.design_token, "rdes"),
            )
        if self.invitation_token is not None:
            object.__setattr__(
                self,
                "invitation_token",
                _require_prefixed_digest(self.invitation_token, "rinv"),
            )
        if self.prerequisite_message_token is not None and (
            type(self.prerequisite_message_token) is not str
            or not self.prerequisite_message_token
            or len(self.prerequisite_message_token) > _MESSAGE_TOKEN_MAX_LEN
        ):
            _fail("replication_invalid_message_token")
        object.__setattr__(
            self, "proposed_tick", _require_tick(self.proposed_tick)
        )
        if self.attempted_tick is not None:
            object.__setattr__(
                self, "attempted_tick", _require_tick(self.attempted_tick)
            )
        if (
            isinstance(self.attempt_count, bool)
            or type(self.attempt_count) is not int
            or not 0 <= self.attempt_count <= MAX_SEND_ATTEMPTS
        ):
            _fail("replication_invalid_attempt_count")
        if self.observed_delivery_event_id is not None:
            object.__setattr__(
                self,
                "observed_delivery_event_id",
                _require_reference(
                    self.observed_delivery_event_id,
                    "replication_invalid_delivery",
                ),
            )
        if type(self.status) is not ReplicationOutboxStatus:
            _fail("replication_invalid_status")


_MESSAGE_KINDS: Final[frozenset[str]] = frozenset(
    {
        "design",
        "invite",
        "invitation",
        "participate",
        "decline",
        "result",
        "interpret",
    }
)


@dataclass(frozen=True, slots=True)
class ReplicationReceipt:
    """Receiver-owned acknowledgement that one design was actually delivered."""

    owner_id: AgentId
    design_token: str
    origin_token: str
    delivery_event_id: str
    received_tick: int
    inviter_entity_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "owner_id", _require_owner(self.owner_id))
        object.__setattr__(
            self, "design_token", _require_prefixed_digest(self.design_token, "rdes")
        )
        if _RECEIPT_ORIGIN.fullmatch(self.origin_token) is None:
            _fail("replication_invalid_id")
        object.__setattr__(
            self,
            "delivery_event_id",
            _require_reference(
                self.delivery_event_id, "replication_invalid_delivery"
            ),
        )
        object.__setattr__(
            self, "received_tick", _require_tick(self.received_tick)
        )
        if self.inviter_entity_id is not None:
            object.__setattr__(
                self,
                "inviter_entity_id",
                _require_reference(
                    self.inviter_entity_id, "replication_invalid_inviter"
                ),
            )


@dataclass(frozen=True, slots=True)
class ReplicationAttempt:
    """One owner's attempted repetition. Intent is not a measurement."""

    owner_id: AgentId
    attempt_token: str
    design_token: str
    source_trial_token: str
    actor_entity_id: str
    hypothesis_id: str
    request_tick: int
    collaboration_token: str | None = None
    submission_tick: int | None = None
    operand_a_id: str | None = None
    operand_b_id: str | None = None
    observed_conditions: tuple[HypothesisCondition, ...] = ()
    condition_comparison: ReplicationConditionComparison = (
        ReplicationConditionComparison.UNKNOWN
    )
    state: ReplicationAttemptState = ReplicationAttemptState.PLANNED
    resolution_event_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "owner_id", _require_owner(self.owner_id))
        object.__setattr__(
            self, "attempt_token", _require_prefixed_digest(self.attempt_token, "ratt")
        )
        object.__setattr__(
            self, "design_token", _require_prefixed_digest(self.design_token, "rdes")
        )
        object.__setattr__(
            self,
            "source_trial_token",
            _require_prefixed_digest(self.source_trial_token, "rtrl"),
        )
        object.__setattr__(
            self,
            "actor_entity_id",
            _require_reference(self.actor_entity_id, "replication_invalid_actor"),
        )
        if type(self.hypothesis_id) is not str or not self.hypothesis_id:
            _fail("replication_invalid_hypothesis")
        object.__setattr__(
            self, "request_tick", _require_tick(self.request_tick)
        )
        if self.collaboration_token is not None:
            object.__setattr__(
                self,
                "collaboration_token",
                _require_prefixed_digest(self.collaboration_token, "rinv"),
            )
        if self.submission_tick is not None:
            object.__setattr__(
                self, "submission_tick", _require_tick(self.submission_tick)
            )
            if self.submission_tick < self.request_tick:
                _fail("replication_invalid_tick_order")
        for name in ("operand_a_id", "operand_b_id"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(
                    self,
                    name,
                    _require_reference(value, "replication_invalid_operand"),
                )
        object.__setattr__(
            self,
            "observed_conditions",
            _validated_conditions(self.observed_conditions),
        )
        if type(self.condition_comparison) is not ReplicationConditionComparison:
            _fail("replication_invalid_comparison")
        if type(self.state) is not ReplicationAttemptState:
            _fail("replication_invalid_state")
        if self.resolution_event_id is not None:
            object.__setattr__(
                self,
                "resolution_event_id",
                _require_reference(
                    self.resolution_event_id, "replication_invalid_resolution"
                ),
            )
        if (
            self.state is ReplicationAttemptState.OBSERVED
            and not self.resolution_event_id
        ):
            _fail("replication_missing_resolution")


@dataclass(frozen=True, slots=True)
class ReplicationMeasurement:
    """Categorical result plus explicit uncertainty resolution."""

    resolution: ReplicationMeasurementResolution
    uncertainty_kind: ReplicationUncertaintyKind
    basis: ReplicationMeasurementBasis
    outcome: ExperimentOutcomeClass | None = None
    possible_outcomes: tuple[ExperimentOutcomeClass, ...] = ()

    def __post_init__(self) -> None:
        if type(self.resolution) is not ReplicationMeasurementResolution:
            _fail("replication_invalid_measurement")
        if type(self.uncertainty_kind) is not ReplicationUncertaintyKind:
            _fail("replication_invalid_uncertainty")
        if type(self.basis) is not ReplicationMeasurementBasis:
            _fail("replication_invalid_basis")
        if self.outcome is not None and (
            type(self.outcome) is not ExperimentOutcomeClass
        ):
            _fail("replication_invalid_outcome")
        if not isinstance(self.possible_outcomes, tuple):
            _fail("replication_invalid_uncertainty")
        seen: set[str] = set()
        for row in self.possible_outcomes:
            if type(row) is not ExperimentOutcomeClass:
                _fail("replication_invalid_uncertainty")
            if row.value in seen:
                _fail("replication_invalid_uncertainty")
            seen.add(row.value)
        outcomes = tuple(
            sorted(self.possible_outcomes, key=lambda item: item.value)
        )
        object.__setattr__(self, "possible_outcomes", outcomes)
        if self.uncertainty_kind is ReplicationUncertaintyKind.UNREPORTED:
            if outcomes:
                _fail("replication_invalid_uncertainty")
        else:
            if not 1 <= len(outcomes) <= len(ExperimentOutcomeClass):
                _fail("replication_invalid_uncertainty")
            if self.outcome is not None and self.outcome not in outcomes:
                _fail("replication_invalid_uncertainty")


@dataclass(frozen=True, slots=True)
class ReplicationResultReport:
    """One attributed result claim. Conflicting claims coexist by design."""

    owner_id: AgentId
    report_token: str
    origin_report_token: str
    content_digest: str
    design_token: str
    attempt_token: str
    source_trial_token: str
    source_root_token: str
    measurement: ReplicationMeasurement
    declared_measurement_basis: ReplicationMeasurementBasis
    performer_claim_token: str
    observed_conditions: tuple[HypothesisCondition, ...] = ()
    reported_conditions: tuple[HypothesisCondition, ...] = ()
    delivery_event_id: str | None = None
    collaboration_claim_token: str | None = None
    source_entity_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "owner_id", _require_owner(self.owner_id))
        object.__setattr__(
            self,
            "report_token",
            _require_prefixed_digest(self.report_token, "rlrep"),
        )
        object.__setattr__(
            self,
            "origin_report_token",
            _require_prefixed_digest(self.origin_report_token, "rrep"),
        )
        if (
            type(self.content_digest) is not str
            or _ID_HEX.fullmatch(self.content_digest) is None
        ):
            _fail("replication_invalid_digest")
        object.__setattr__(
            self, "design_token", _require_prefixed_digest(self.design_token, "rdes")
        )
        object.__setattr__(
            self, "attempt_token", _require_prefixed_digest(self.attempt_token, "ratt")
        )
        object.__setattr__(
            self,
            "source_trial_token",
            _require_prefixed_digest(self.source_trial_token, "rtrl"),
        )
        object.__setattr__(
            self,
            "source_root_token",
            _require_prefixed_digest(self.source_root_token, "rrep"),
        )
        if type(self.measurement) is not ReplicationMeasurement:
            _fail("replication_invalid_measurement")
        if type(self.declared_measurement_basis) is not ReplicationMeasurementBasis:
            _fail("replication_invalid_basis")
        object.__setattr__(
            self,
            "performer_claim_token",
            _require_prefixed_digest(self.performer_claim_token, "rpart"),
        )
        object.__setattr__(
            self,
            "observed_conditions",
            _validated_conditions(self.observed_conditions),
        )
        object.__setattr__(
            self,
            "reported_conditions",
            _validated_conditions(self.reported_conditions),
        )
        if self.delivery_event_id is not None:
            object.__setattr__(
                self,
                "delivery_event_id",
                _require_reference(
                    self.delivery_event_id, "replication_invalid_delivery"
                ),
            )
        if self.collaboration_claim_token is not None:
            object.__setattr__(
                self,
                "collaboration_claim_token",
                _require_prefixed_digest(self.collaboration_claim_token, "rgcl"),
            )
        if self.source_entity_id is not None:
            object.__setattr__(
                self,
                "source_entity_id",
                _require_reference(
                    self.source_entity_id, "replication_invalid_source"
                ),
            )
        if (
            self.measurement.basis is ReplicationMeasurementBasis.COMMUNICATED
            and self.delivery_event_id is None
        ):
            _fail("replication_missing_delivery")


def _measurement_payload(measurement: ReplicationMeasurement) -> dict[str, object]:
    return {
        "basis": measurement.basis.value,
        "outcome": None if measurement.outcome is None else measurement.outcome.value,
        "possible_outcomes": [row.value for row in measurement.possible_outcomes],
        "resolution": measurement.resolution.value,
        "uncertainty_kind": measurement.uncertainty_kind.value,
    }


def _conditions_payload(
    conditions: tuple[HypothesisCondition, ...],
) -> list[dict[str, str]]:
    return [
        {"slot": row.slot.value, "value_token": row.value_token}
        for row in conditions
    ]


def replication_report_digest(
    *,
    origin_report_token: str,
    design_token: str,
    attempt_token: str,
    source_trial_token: str,
    source_root_token: str,
    measurement: ReplicationMeasurement,
    declared_measurement_basis: ReplicationMeasurementBasis,
    performer_claim_token: str,
    observed_conditions: tuple[HypothesisCondition, ...],
    reported_conditions: tuple[HypothesisCondition, ...],
    delivery_event_id: str | None,
    collaboration_claim_token: str | None,
    source_entity_id: str | None = None,
) -> str:
    """Canonical content digest for one report version."""

    payload = {
        "attempt_token": attempt_token,
        "collaboration_claim_token": collaboration_claim_token,
        "declared_measurement_basis": declared_measurement_basis.value,
        "delivery_event_id": delivery_event_id,
        "design_token": design_token,
        "measurement": _measurement_payload(measurement),
        "observed_conditions": _conditions_payload(observed_conditions),
        "origin_report_token": origin_report_token,
        "performer_claim_token": performer_claim_token,
        "policy_version": REPLICATION_POLICY_VERSION,
        "reported_conditions": _conditions_payload(reported_conditions),
        "source_root_token": source_root_token,
        "source_trial_token": source_trial_token,
        "source_entity_id": source_entity_id,
    }
    material = json.dumps(
        payload,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return hashlib.sha256(material.encode("ascii")).hexdigest()[:32]


def build_replication_result_report(
    owner_id: AgentId,
    *,
    origin_report_token: str,
    design_token: str,
    attempt_token: str,
    source_trial_token: str,
    source_root_token: str,
    measurement: ReplicationMeasurement,
    declared_measurement_basis: ReplicationMeasurementBasis,
    performer_claim_token: str,
    observed_conditions: tuple[HypothesisCondition, ...] = (),
    reported_conditions: tuple[HypothesisCondition, ...] = (),
    delivery_event_id: str | None = None,
    collaboration_claim_token: str | None = None,
    source_entity_id: str | None = None,
) -> ReplicationResultReport:
    """Build one local report while preserving its origin identity."""

    digest = replication_report_digest(
        origin_report_token=origin_report_token,
        design_token=design_token,
        attempt_token=attempt_token,
        source_trial_token=source_trial_token,
        source_root_token=source_root_token,
        measurement=measurement,
        declared_measurement_basis=declared_measurement_basis,
        performer_claim_token=performer_claim_token,
        observed_conditions=observed_conditions,
        reported_conditions=reported_conditions,
        delivery_event_id=delivery_event_id,
        collaboration_claim_token=collaboration_claim_token,
        source_entity_id=source_entity_id,
    )
    report_token = replication_ref(
        "rlrep", owner_id.value, origin_report_token, digest
    )
    return ReplicationResultReport(
        owner_id=owner_id,
        report_token=report_token,
        origin_report_token=origin_report_token,
        content_digest=digest,
        design_token=design_token,
        attempt_token=attempt_token,
        source_trial_token=source_trial_token,
        source_root_token=source_root_token,
        measurement=measurement,
        declared_measurement_basis=declared_measurement_basis,
        performer_claim_token=performer_claim_token,
        observed_conditions=tuple(observed_conditions),
        reported_conditions=tuple(reported_conditions),
        delivery_event_id=delivery_event_id,
        collaboration_claim_token=collaboration_claim_token,
        source_entity_id=source_entity_id,
    )


def replication_attempt_token(
    owner_id: AgentId,
    design_token: str,
    source_trial_token: str,
    request_tick: int,
    collaboration_token: str | None = None,
) -> str:
    """Owner-local attempt identity including its request ordering."""

    return replication_ref(
        "ratt",
        owner_id.value,
        design_token,
        source_trial_token,
        request_tick,
        collaboration_token or "none",
    )


def record_replication_attempt(
    ledger: ReplicationLedger, attempt: ReplicationAttempt
) -> tuple[ReplicationLedger, str]:
    """Add one attempt. Unknown design references are rejected."""

    if ledger.owner_id != attempt.owner_id:
        raise ReplicationError("replication_ledger_owner_mismatch")
    if not any(row.design_token == attempt.design_token for row in ledger.designs):
        return ledger, "unknown_design"
    if any(row.attempt_token == attempt.attempt_token for row in ledger.attempts):
        return ledger, "duplicate_attempt"
    if len(ledger.attempts) >= MAX_ATTEMPTS:
        return _add_notice(ledger, ReplicationNoticeCode.ATTEMPT_CAPACITY), (
            "attempt_capacity"
        )
    updated = _replace_ledger(ledger, attempts=(*ledger.attempts, attempt))
    source_report = any(
        getattr(row, "source_trial_token", None) == attempt.source_trial_token
        for row in updated.reports
    )
    if not source_report:
        updated = _add_notice(
            updated, ReplicationNoticeCode.SOURCE_RESULT_MISSING
        )
        return updated, "source_result_missing"
    _LOG.info(
        "replication_attempt_recorded state=%s attempt_count=%s",
        attempt.state.value,
        len(updated.attempts),
    )
    return updated, "attempt_recorded"


def transition_replication_attempt(
    ledger: ReplicationLedger,
    attempt_token: str,
    state: ReplicationAttemptState,
    *,
    submission_tick: int | None = None,
    resolution_event_id: str | None = None,
    observed_conditions: tuple[HypothesisCondition, ...] | None = None,
    condition_comparison: ReplicationConditionComparison | None = None,
) -> tuple[ReplicationLedger, str]:
    """Apply one forward lifecycle transition to a local attempt."""

    if type(state) is not ReplicationAttemptState:
        raise ReplicationError("replication_invalid_state")
    rows = [row for row in ledger.attempts if row.attempt_token == attempt_token]
    if not rows:
        return ledger, "attempt_missing"
    attempt = rows[0]
    if attempt.state is state:
        return ledger, "attempt_unchanged"
    if state.value not in _ATTEMPT_TRANSITIONS[attempt.state]:
        return ledger, "attempt_transition_rejected"
    changes: dict[str, Any] = {"state": state}
    if submission_tick is not None:
        changes["submission_tick"] = submission_tick
    if resolution_event_id is not None:
        changes["resolution_event_id"] = resolution_event_id
    if observed_conditions is not None:
        changes["observed_conditions"] = observed_conditions
    if condition_comparison is not None:
        changes["condition_comparison"] = condition_comparison
    if state is ReplicationAttemptState.OBSERVED and resolution_event_id is None:
        return ledger, "resolution_missing"
    updated_attempt = ReplicationAttempt(
        owner_id=attempt.owner_id,
        attempt_token=attempt.attempt_token,
        design_token=attempt.design_token,
        source_trial_token=attempt.source_trial_token,
        actor_entity_id=attempt.actor_entity_id,
        hypothesis_id=attempt.hypothesis_id,
        request_tick=attempt.request_tick,
        collaboration_token=attempt.collaboration_token,
        submission_tick=changes.get("submission_tick", attempt.submission_tick),
        operand_a_id=attempt.operand_a_id,
        operand_b_id=attempt.operand_b_id,
        observed_conditions=changes.get(
            "observed_conditions", attempt.observed_conditions
        ),
        condition_comparison=changes.get(
            "condition_comparison", attempt.condition_comparison
        ),
        state=state,
        resolution_event_id=changes.get(
            "resolution_event_id", attempt.resolution_event_id
        ),
    )
    attempts = tuple(
        updated_attempt if row.attempt_token == attempt_token else row
        for row in ledger.attempts
    )
    _LOG.info(
        "replication_attempt_transitioned from_state=%s to_state=%s",
        attempt.state.value,
        state.value,
    )
    return _replace_ledger(ledger, attempts=attempts), "attempt_transitioned"


def ingest_replication_report(
    ledger: ReplicationLedger, report: ReplicationResultReport
) -> tuple[ReplicationLedger, str]:
    """Append one attributed report version. Same-origin conflicts coexist."""

    if ledger.owner_id != report.owner_id:
        raise ReplicationError("replication_ledger_owner_mismatch")
    if any(row.report_token == report.report_token for row in ledger.reports):
        return ledger, "duplicate_report"
    if len(ledger.reports) >= MAX_RESULT_REPORTS:
        return _add_notice(ledger, ReplicationNoticeCode.REPORT_CAPACITY), (
            "report_capacity"
        )
    updated = _replace_ledger(ledger, reports=(*ledger.reports, report))
    _LOG.info(
        "replication_report_ingested report_count=%s content_digest_prefix=%s",
        len(updated.reports),
        report.content_digest[:12],
    )
    return updated, "report_ingested"


def record_replication_measurement(
    ledger: ReplicationLedger,
    attempt_token: str,
    *,
    measurement: ReplicationMeasurement,
    condition_comparison: ReplicationConditionComparison,
    resolution_event_id: str,
    performer_claim_token: str,
    observed_conditions: tuple[HypothesisCondition, ...] = (),
    reported_conditions: tuple[HypothesisCondition, ...] = (),
    origin_report_token: str | None = None,
) -> tuple[ReplicationLedger, str]:
    """Record one own observation; missing outcomes remain unresolved."""

    rows = [row for row in ledger.attempts if row.attempt_token == attempt_token]
    if not rows:
        return ledger, "attempt_missing"
    attempt = rows[0]
    if attempt.state is not ReplicationAttemptState.PROPOSED:
        return ledger, "attempt_not_proposed"
    if measurement.basis is not ReplicationMeasurementBasis.OWN_OBSERVATION:
        return ledger, "measurement_basis_invalid"
    if measurement.outcome is None:
        return transition_replication_attempt(
            ledger,
            attempt_token,
            ReplicationAttemptState.UNRESOLVED,
            condition_comparison=condition_comparison,
            observed_conditions=observed_conditions,
        )
    origin = origin_report_token or replication_ref(
        "rrep", attempt.owner_id.value, attempt.source_trial_token, resolution_event_id
    )
    report = build_replication_result_report(
        attempt.owner_id,
        origin_report_token=origin,
        design_token=attempt.design_token,
        attempt_token=attempt.attempt_token,
        source_trial_token=attempt.source_trial_token,
        source_root_token=origin,
        measurement=measurement,
        declared_measurement_basis=ReplicationMeasurementBasis.OWN_OBSERVATION,
        performer_claim_token=performer_claim_token,
        observed_conditions=observed_conditions,
        reported_conditions=reported_conditions,
        collaboration_claim_token=None,
    )
    updated, reason = ingest_replication_report(ledger, report)
    if reason not in {"report_ingested", "duplicate_report"}:
        return updated, reason
    updated, transition = transition_replication_attempt(
        updated,
        attempt_token,
        ReplicationAttemptState.OBSERVED,
        resolution_event_id=resolution_event_id,
        observed_conditions=observed_conditions,
        condition_comparison=condition_comparison,
    )
    return updated, transition


@dataclass(frozen=True, slots=True)
class ReplicationParticipantClaim:
    """One attributed participation act. Acknowledgement is not execution."""

    actor_entity_id: str
    act: ReplicationCollaborationAct
    tick: int
    claim_token: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "actor_entity_id",
            _require_reference(self.actor_entity_id, "replication_invalid_actor"),
        )
        if type(self.act) is not ReplicationCollaborationAct:
            _fail("replication_invalid_act")
        object.__setattr__(self, "tick", _require_tick(self.tick))
        object.__setattr__(
            self, "claim_token", _require_prefixed_digest(self.claim_token, "rpart")
        )


@dataclass(frozen=True, slots=True)
class ReplicationCollaboration:
    """Owner-local invitation view. No roster, group owner, or executor."""

    owner_id: AgentId
    invitation_token: str
    design_token: str
    source_trial_token: str
    inviter_entity_id: str
    created_tick: int
    status: ReplicationInvitationStatus = ReplicationInvitationStatus.PENDING
    group_claim_token: str | None = None
    delivery_event_id: str | None = None
    participants: tuple[ReplicationParticipantClaim, ...] = ()
    requested: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "owner_id", _require_owner(self.owner_id))
        object.__setattr__(
            self,
            "invitation_token",
            _require_prefixed_digest(self.invitation_token, "rinv"),
        )
        object.__setattr__(
            self, "design_token", _require_prefixed_digest(self.design_token, "rdes")
        )
        object.__setattr__(
            self,
            "source_trial_token",
            _require_prefixed_digest(self.source_trial_token, "rtrl"),
        )
        object.__setattr__(
            self,
            "inviter_entity_id",
            _require_reference(self.inviter_entity_id, "replication_invalid_inviter"),
        )
        object.__setattr__(self, "created_tick", _require_tick(self.created_tick))
        if type(self.status) is not ReplicationInvitationStatus:
            _fail("replication_invalid_status")
        if self.group_claim_token is not None:
            object.__setattr__(
                self,
                "group_claim_token",
                _require_prefixed_digest(self.group_claim_token, "rgcl"),
            )
        if self.delivery_event_id is not None:
            object.__setattr__(
                self,
                "delivery_event_id",
                _require_reference(
                    self.delivery_event_id, "replication_invalid_delivery"
                ),
            )
        if not isinstance(self.participants, tuple):
            _fail("replication_invalid_participants")
        if len(self.participants) > MAX_PARTICIPANTS:
            _fail("replication_participant_capacity")
        seen: set[str] = set()
        for claim in self.participants:
            if type(claim) is not ReplicationParticipantClaim:
                _fail("replication_invalid_participants")
            if claim.claim_token in seen:
                _fail("replication_duplicate_claim")
            seen.add(claim.claim_token)
        if self.status in {
            ReplicationInvitationStatus.ACCEPTED,
            ReplicationInvitationStatus.COMPLETED,
        } and self.delivery_event_id is None and not self.requested:
            _fail("replication_missing_delivery")
        if type(self.requested) is not bool:
            _fail("replication_invalid_status")


@dataclass(frozen=True, slots=True)
class ReplicationInterpretationRevision:
    """One append-only revision of an owner appraisal."""

    revision_index: int
    tick: int
    reason: ReplicationRevisionReason
    appraisal: ReplicationCategoricalAppraisal
    condition_comparison: ReplicationConditionComparison
    source_appraisal: ReplicationSourceAppraisal
    uncertainty_notice: bool

    def __post_init__(self) -> None:
        if (
            isinstance(self.revision_index, bool)
            or type(self.revision_index) is not int
            or self.revision_index < 0
        ):
            _fail("replication_invalid_revision")
        object.__setattr__(self, "tick", _require_tick(self.tick))
        if type(self.reason) is not ReplicationRevisionReason:
            _fail("replication_invalid_revision")
        if type(self.appraisal) is not ReplicationCategoricalAppraisal:
            _fail("replication_invalid_appraisal")
        if type(self.condition_comparison) is not ReplicationConditionComparison:
            _fail("replication_invalid_comparison")
        if type(self.source_appraisal) is not ReplicationSourceAppraisal:
            _fail("replication_invalid_appraisal")
        if type(self.uncertainty_notice) is not bool:
            _fail("replication_invalid_uncertainty")


@dataclass(frozen=True, slots=True)
class ReplicationInterpretation:
    """One owner's retained reading of one attributed report version."""

    owner_id: AgentId
    interpretation_token: str
    design_token: str
    report_tokens: tuple[str, ...]
    appraisal: ReplicationCategoricalAppraisal
    condition_comparison: ReplicationConditionComparison
    source_appraisal: ReplicationSourceAppraisal
    uncertainty_notice: bool
    created_tick: int
    revisions: tuple[ReplicationInterpretationRevision, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "owner_id", _require_owner(self.owner_id))
        object.__setattr__(
            self,
            "interpretation_token",
            _require_prefixed_digest(self.interpretation_token, "rint"),
        )
        object.__setattr__(
            self, "design_token", _require_prefixed_digest(self.design_token, "rdes")
        )
        if not isinstance(self.report_tokens, tuple) or not self.report_tokens:
            _fail("replication_invalid_report_reference")
        seen: set[str] = set()
        for token in self.report_tokens:
            _require_prefixed_digest(token, "rlrep")
            if token in seen:
                _fail("replication_invalid_report_reference")
            seen.add(token)
        if type(self.appraisal) is not ReplicationCategoricalAppraisal:
            _fail("replication_invalid_appraisal")
        if type(self.condition_comparison) is not ReplicationConditionComparison:
            _fail("replication_invalid_comparison")
        if type(self.source_appraisal) is not ReplicationSourceAppraisal:
            _fail("replication_invalid_appraisal")
        if type(self.uncertainty_notice) is not bool:
            _fail("replication_invalid_uncertainty")
        object.__setattr__(self, "created_tick", _require_tick(self.created_tick))
        if not isinstance(self.revisions, tuple):
            _fail("replication_invalid_revision")
        if len(self.revisions) > MAX_INTERPRETATION_REVISIONS:
            _fail("replication_invalid_revision")
        previous = -1
        for revision in self.revisions:
            if type(revision) is not ReplicationInterpretationRevision:
                _fail("replication_invalid_revision")
            if revision.revision_index <= previous:
                _fail("replication_invalid_revision")
            previous = revision.revision_index


@dataclass(frozen=True, slots=True)
class ReplicationLedger:
    """Owner replication sidecar. Separate from ``ExperimentLedger``."""

    owner_id: AgentId
    policy_version: str
    source_drafts: tuple[ReplicationSourceDraft, ...] = ()
    designs: tuple[ExperimentDesign, ...] = ()
    attempts: tuple[ReplicationAttempt, ...] = ()
    reports: tuple[ReplicationResultReport, ...] = ()
    collaborations: tuple[ReplicationCollaboration, ...] = ()
    interpretations: tuple[ReplicationInterpretation, ...] = ()
    outbox: tuple[ReplicationOutboxEntry, ...] = ()
    receipts: tuple[ReplicationReceipt, ...] = ()
    notices: tuple[ReplicationNoticeCode, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "owner_id", _require_owner(self.owner_id))
        if self.policy_version != REPLICATION_POLICY_VERSION:
            _fail("replication_policy_mismatch")
        for name in (
            "source_drafts",
            "designs",
            "attempts",
            "reports",
            "collaborations",
            "interpretations",
            "outbox",
            "receipts",
            "notices",
        ):
            if not isinstance(getattr(self, name), tuple):
                _fail("replication_invalid_ledger")
        for row in self.source_drafts:
            if type(row) is not ReplicationSourceDraft or row.owner_id != self.owner_id:
                _fail("replication_invalid_ledger")
        for design in self.designs:
            if type(design) is not ExperimentDesign:
                _fail("replication_invalid_ledger")
        for attempt in self.attempts:
            if (
                type(attempt) is not ReplicationAttempt
                or attempt.owner_id != self.owner_id
            ):
                _fail("replication_invalid_ledger")
        for report in self.reports:
            if (
                type(report) is not ReplicationResultReport
                or report.owner_id != self.owner_id
            ):
                _fail("replication_invalid_ledger")
        for collaboration in self.collaborations:
            if (
                type(collaboration) is not ReplicationCollaboration
                or collaboration.owner_id != self.owner_id
            ):
                _fail("replication_invalid_ledger")
        for interpretation in self.interpretations:
            if (
                type(interpretation) is not ReplicationInterpretation
                or interpretation.owner_id != self.owner_id
            ):
                _fail("replication_invalid_ledger")
        for entry in self.outbox:
            if (
                type(entry) is not ReplicationOutboxEntry
                or entry.owner_id != self.owner_id
            ):
                _fail("replication_invalid_ledger")
        for receipt in self.receipts:
            if (
                type(receipt) is not ReplicationReceipt
                or receipt.owner_id != self.owner_id
            ):
                _fail("replication_invalid_ledger")
        for notice in self.notices:
            if type(notice) is not ReplicationNoticeCode:
                _fail("replication_invalid_ledger")
        if len(self.source_drafts) > MAX_SOURCE_DRAFTS:
            _fail("replication_invalid_ledger")
        if len(self.designs) > MAX_DESIGNS:
            _fail("replication_invalid_ledger")
        if len(self.attempts) > MAX_ATTEMPTS:
            _fail("replication_invalid_ledger")
        if len(self.reports) > MAX_RESULT_REPORTS:
            _fail("replication_invalid_ledger")
        if len(self.collaborations) > MAX_COLLABORATIONS:
            _fail("replication_invalid_ledger")
        if len(self.interpretations) > MAX_INTERPRETATIONS:
            _fail("replication_invalid_ledger")
        if len(self.outbox) > MAX_OUTBOX_ENTRIES:
            _fail("replication_invalid_ledger")
        if len(self.receipts) > MAX_DELIVERY_RECEIPTS:
            _fail("replication_invalid_ledger")
        _LOG.debug(
            "replication_ledger_constructed owner_id=%s design_count=%s",
            self.owner_id.value,
            len(self.designs),
        )


def empty_replication_ledger(owner_id: AgentId) -> ReplicationLedger:
    """Empty owner ledger. Construction copies no other owner's state."""

    ledger = ReplicationLedger(
        owner_id=_require_owner(owner_id),
        policy_version=REPLICATION_POLICY_VERSION,
    )
    _LOG.debug(
        "replication_ledger_initialized owner_id=%s", ledger.owner_id.value
    )
    return ledger


def require_owner_replication_ledger(
    ledger: object | None, owner_id: object
) -> ReplicationLedger:
    """Return the ledger only when it belongs to the exact owner."""

    if ledger is None:
        raise ReplicationError("replication_ledger_missing")
    if type(ledger) is not ReplicationLedger:
        raise ReplicationError("replication_ledger_invalid")
    if type(owner_id) is not AgentId or ledger.owner_id != owner_id:
        raise ReplicationError("replication_ledger_owner_mismatch")
    return ledger


def _add_notice(
    ledger: ReplicationLedger, notice: ReplicationNoticeCode
) -> ReplicationLedger:
    if notice in ledger.notices:
        return ledger
    rows = (*ledger.notices, notice)
    if len(rows) > MAX_NOTICE_CODES:
        rows = rows[-MAX_NOTICE_CODES:]
    return _replace_ledger(ledger, notices=rows)


def _replace_ledger(ledger: ReplicationLedger, **changes: Any) -> ReplicationLedger:
    return ReplicationLedger(
        owner_id=ledger.owner_id,
        policy_version=ledger.policy_version,
        source_drafts=changes.get("source_drafts", ledger.source_drafts),
        designs=changes.get("designs", ledger.designs),
        attempts=changes.get("attempts", ledger.attempts),
        reports=changes.get("reports", ledger.reports),
        collaborations=changes.get(
            "collaborations", ledger.collaborations
        ),
        interpretations=changes.get(
            "interpretations", ledger.interpretations
        ),
        outbox=changes.get("outbox", ledger.outbox),
        receipts=changes.get("receipts", ledger.receipts),
        notices=changes.get("notices", ledger.notices),
    )


def append_replication_design(
    ledger: ReplicationLedger, design: ExperimentDesign
) -> tuple[ReplicationLedger, str]:
    """Add a design unless it is a duplicate, cyclic, or over capacity."""

    require_owner_replication_ledger(ledger, ledger.owner_id)
    if type(design) is not ExperimentDesign:
        raise ReplicationError("replication_invalid_design")
    if any(row.design_token == design.design_token for row in ledger.designs):
        return ledger, "duplicate_design"
    reason = _lineage_reason(ledger.designs, design)
    if reason:
        return _add_notice(ledger, ReplicationNoticeCode.INVALID_DESIGN), reason
    if len(ledger.designs) >= MAX_DESIGNS:
        return (
            _add_notice(ledger, ReplicationNoticeCode.DESIGN_CAPACITY),
            "design_capacity",
        )
    updated = _replace_ledger(ledger, designs=(*ledger.designs, design))
    if design.parent_design_token is not None and not any(
        row.design_token == design.parent_design_token for row in ledger.designs
    ):
        updated = _add_notice(
            updated, ReplicationNoticeCode.UNKNOWN_PARENT
        )
    _LOG.debug(
        "replication_design_appended design_prefix=%s design_count=%s",
        design.design_token[:12],
        len(updated.designs),
    )
    return updated, "design_adopted"


def _lineage_reason(
    designs: tuple[ExperimentDesign, ...], design: ExperimentDesign
) -> str:
    parent = design.parent_design_token
    if parent is None:
        return ""
    if parent == design.design_token:
        return "self_parent"
    by_token = {row.design_token: row for row in designs}
    candidate = {**by_token, design.design_token: design}
    seen: set[str] = set()
    cursor: str | None = parent
    while cursor is not None and cursor in candidate:
        if cursor == design.design_token:
            return "design_cycle"
        if cursor in seen:
            return "design_cycle"
        seen.add(cursor)
        cursor = candidate[cursor].parent_design_token
    return ""


__all__ = [
    "MAX_ATTEMPTS",
    "MAX_COLLABORATIONS",
    "MAX_DELIVERY_RECEIPTS",
    "MAX_DESIGNS",
    "MAX_DESIGN_CONDITIONS",
    "MAX_INTERPRETATIONS",
    "MAX_INTERPRETATION_REVISIONS",
    "MAX_NOTICE_CODES",
    "MAX_OUTBOX_ENTRIES",
    "MAX_PARTICIPANTS",
    "MAX_RESULT_REPORTS",
    "MAX_SEND_ATTEMPTS",
    "MAX_SOURCE_DRAFTS",
    "REPLICATION_POLICY_VERSION",
    "ExperimentDesign",
    "ExperimentSelector",
    "ReplicationBindingMode",
    "ReplicationError",
    "ReplicationInvitationStatus",
    "ReplicationLedger",
    "ReplicationNoticeCode",
    "ReplicationOutboxEntry",
    "ReplicationOutboxStatus",
    "ReplicationPolicy",
    "ReplicationReceipt",
    "ReplicationRelationKind",
    "ReplicationSelectorFamily",
    "ReplicationSourceDraft",
    "append_replication_design",
    "default_replication_policy",
    "empty_replication_ledger",
    "require_owner_replication_ledger",
    "require_replication_policy",
]
