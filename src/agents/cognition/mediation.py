"""Owner-scoped subjective conflict mediation.

Mediation is one owner's revisable, locally understood attempt to help other
agents coordinate a voluntary response to a dispute. It is never an objective
dispute registry, a court, a verdict, a binding settlement, or a world
permission.

Updates read only one owner's ``Observation``, the owner-safe identity
projection, prepared owner-local cognition inputs, and the previous
``MediationLedger``. They never read ``WorldState``, ``WorldEvent``, another
owner's ledger, or analysis rows.
"""

from __future__ import annotations

import hashlib
import logging
import math
from collections.abc import Sequence
from dataclasses import dataclass, fields
from decimal import Decimal
from enum import StrEnum
from typing import Any, Final, cast

from agents.cognition.models import OwnerSafeSocialIdentity
from agents.models import AgentId
from world.identifiers import EntityId, require_exact_nonneg_int
from world.observations import Observation

__all__ = [
    "FORBIDDEN_MEDIATION_FIELD_NAMES",
    "MEDIATION_POLICY_VERSION",
    "MediationAccount",
    "MediationAct",
    "MediationAttempt",
    "MediationAttemptStatus",
    "MediationAuthorityAppraisal",
    "MediationAuthorityChannel",
    "MediationAuthorityComponent",
    "MediationCase",
    "MediationCaseStatus",
    "MediationEvidence",
    "MediationEvidenceChannel",
    "MediationFunctionEvidence",
    "MediationLedger",
    "MediationOutcome",
    "MediationOutcomeKind",
    "MediationPolicy",
    "MediationRecommendation",
    "MediationRecommendationStatus",
    "MediationResponse",
    "MediationResponseKind",
    "MediationRoleExpression",
    "MediationRoleExpressionKind",
    "apply_mediation_update",
    "appraise_mediation_authority",
    "default_mediation_policy",
    "empty_mediation_ledger",
    "generate_mediation_opportunities",
    "mediation_case_id",
    "mediation_case_ref",
    "mediation_context_key",
    "mediation_evidence_id",
    "mediation_evidence_id_prefix",
    "mediation_function_evidence",
    "mediation_recommendation_id",
    "mediation_response_id",
    "mediation_role_expression_id",
    "require_owner_mediation",
]

_LOG: Final[logging.Logger] = logging.getLogger("agents.cognition.mediation")

MEDIATION_POLICY_VERSION: Final[str] = "mediation.v1"
_QUANTUM: Final[Decimal] = Decimal("0.000001")
_HEX: Final[frozenset[str]] = frozenset("0123456789abcdef")
_DIGEST_LEN: Final[int] = 16

_MAX_CASES: Final[int] = 16
_MAX_ACCOUNTS: Final[int] = 32
_MAX_RECOMMENDATIONS: Final[int] = 32
_MAX_RESPONSES: Final[int] = 32
_MAX_ROLE_EXPRESSIONS: Final[int] = 32
_MAX_ATTEMPTS: Final[int] = 32
_MAX_OUTCOMES: Final[int] = 32
_MAX_EVIDENCE: Final[int] = 24
_MAX_REVISIONS: Final[int] = 8
_MAX_TERMS: Final[int] = 8
_MAX_PARTIES: Final[int] = 8
_MAX_TARGETS: Final[int] = 8
_MAX_NOTICES: Final[int] = 16
_MAX_PROVENANCE: Final[int] = 8
_DEFAULT_ACTION_WINDOW: Final[int] = 8
_MAX_ACTION_WINDOW: Final[int] = 32
_EVIDENCE_RETENTION: Final[int] = 64
_REFERENCE_FRESHNESS: Final[int] = 32
_DEDUP_RETENTION: Final[int] = 64
_MAX_QUANTITY: Final[int] = 999
_MAX_CONFIDENCE: Final[float] = 1.0

_NOTICE_REASONS: Final[frozenset[str]] = frozenset(
    {
        "cap_exceeded",
        "unsupported_evidence",
        "duplicate_evidence",
        "foreign_owner",
        "invalid_token",
        "unknown_case",
        "unknown_recommendation",
        "ambiguous_reference",
        "expired_reference",
        "retired_reference",
        "stale_reference",
        "self_endorsement",
        "duplicate_root",
        "unresolved_party",
        "unsupported_action",
        "superseded_revision",
        "pruned_history",
    }
)

_FORBIDDEN_TYPES: Final[frozenset[str]] = frozenset(
    {
        "MetricDocument",
        "MetricComputationInputs",
        "ConflictMediationRow",
        "MediationRoleEmergenceRow",
        "MediationAnalysisRow",
    }
)

FORBIDDEN_MEDIATION_FIELD_NAMES: Final[frozenset[str]] = frozenset(
    {
        "verdict",
        "judgment",
        "judgement",
        "court",
        "jurisdiction",
        "tribunal",
        "binding",
        "debt",
        "fine",
        "guilt",
        "culpability",
        "sentence",
        "enforce",
        "enforcement",
        "global_registry",
        "dispute_registry",
        "settlement_registry",
        "authoritative_settlement",
        "judge",
    }
)


class MediationAct(StrEnum):
    """Closed primary speech acts. These are speech, not world commands."""

    HEAR_DISPUTE = "hear_dispute"
    REQUEST_ACCOUNTS = "request_accounts"
    PROPOSE_COMPROMISE = "propose_compromise"
    VOUCH = "vouch"
    MEDIATE = "mediate"
    RECOMMEND_RESTITUTION = "recommend_restitution"


class MediationResponseKind(StrEnum):
    """Closed response vocabulary for accounts and recommendations."""

    ACCOUNT = "account"
    ACCEPT = "accept"
    REFUSE = "refuse"
    DEFER = "defer"
    COUNTERPROPOSE = "counterpropose"
    WITHDRAW = "withdraw"
    CLAIM_SETTLEMENT = "claim_settlement"


class MediationRoleExpressionKind(StrEnum):
    """Auxiliary role-directed relations, not additional world commands."""

    INVITE_MEDIATOR = "invite_mediator"
    ENDORSE_ROLE = "endorse_role"
    WITHDRAW_ROLE_ENDORSEMENT = "withdraw_role_endorsement"


class MediationEvidenceChannel(StrEnum):
    """Closed provenance for one item of mediation evidence."""

    OBSERVED = "observed"
    COMMUNICATED = "communicated"
    REMEMBERED = "remembered"


class MediationCaseStatus(StrEnum):
    """Closed local case lifecycle. No status implies fault or obligation."""

    UNRESOLVED = "unresolved"
    PARTIALLY_ADDRESSED = "partially_addressed"
    DECLINED = "declined"
    EXPIRED = "expired"
    ABANDONED = "abandoned"
    APPARENTLY_SETTLED = "apparently_settled"
    DISPUTED = "disputed"
    REOPENED = "reopened"


class MediationRecommendationStatus(StrEnum):
    """Closed lifecycle for one recommendation revision."""

    DRAFT = "draft"
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    WITHDRAWN = "withdrawn"
    EXPIRED = "expired"
    ABANDONED = "abandoned"


class MediationAttemptStatus(StrEnum):
    """Whether a locally selected undertaking has an existing adapter."""

    UNSUPPORTED_ACTION = "unsupported_action"
    UNKNOWN = "unknown"
    ATTEMPTED = "attempted"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


class MediationOutcomeKind(StrEnum):
    """Closed claimed or observed case outcomes."""

    CLAIMED = "claimed"
    OBSERVED = "observed"
    EFFECTED = "effected"
    UNRESOLVED = "unresolved"
    PARTIAL = "partial"
    DISPUTED = "disputed"
    SETTLED = "settled"
    REOPENED = "reopened"
    EXPIRED = "expired"
    UNKNOWN = "unknown"


class MediationAuthorityChannel(StrEnum):
    """Recipient-relative appraisal inputs. None grants binding authority."""

    RELATIONSHIP = "relationship"
    REPUTATION = "reputation"
    ROLE = "role"
    NORM = "norm"
    INSTITUTION = "institution"


def _fail(field_name: str, code: str) -> ValueError:
    _LOG.error(
        "mediation_validation_failed field=%s reason_code=%s",
        field_name,
        code,
    )
    return ValueError(f"{field_name}: {code}")


def _sha256_hex(material: str) -> str:
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _digest16(material: str) -> str:
    return _sha256_hex(material)[:_DIGEST_LEN]


def _quantize(value: float) -> float:
    steps = round(value / 1e-6)
    quantized = float(Decimal(steps) * _QUANTUM)
    return 0.0 if quantized == 0.0 else quantized


def _finite(field_name: str, value: object) -> float:
    if isinstance(value, bool) or type(value) not in {int, float}:
        raise _fail(field_name, "invalid_type")
    number = float(cast("float | int", value))
    if not math.isfinite(number):
        raise _fail(field_name, "nonfinite")
    return _quantize(number)


def _require_strength(field_name: str, value: object) -> float:
    number = _finite(field_name, value)
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
    if not isinstance(value, str) or not value or len(value) > 32:
        raise _fail(field_name, "illegal_token")
    lowered = value.lower()
    if not lowered.replace("_", "").replace("-", "").isalnum():
        raise _fail(field_name, "illegal_token")
    return lowered


def _require_tuple(field_name: str, values: object) -> tuple[object, ...]:
    if isinstance(values, (str, bytes, set, frozenset)) or not isinstance(
        values, Sequence
    ):
        raise _fail(field_name, "invalid_type")
    return tuple(values)


def _require_nonneg_int(field_name: str, value: object) -> int:
    return require_exact_nonneg_int(field_name, value)


def _require_span(prefix: str, first_tick: object, last_tick: object) -> None:
    first = _require_nonneg_int(f"{prefix}.first_tick", first_tick)
    last = _require_nonneg_int(f"{prefix}.last_tick", last_tick)
    if last < first:
        raise _fail(f"{prefix}.last_tick", "before_first_tick")


def _require_window(prefix: str, first_tick: object, last_tick: object) -> None:
    first = _require_nonneg_int(f"{prefix}.window_first_tick", first_tick)
    last = _require_nonneg_int(f"{prefix}.window_last_tick", last_tick)
    if last < first:
        raise _fail(f"{prefix}.window_last_tick", "before_first_tick")


def _require_agent(field_name: str, value: object) -> AgentId:
    if type(value) is not AgentId:
        raise _fail(field_name, "invalid_type")
    return value


def _require_optional_agent(field_name: str, value: object) -> AgentId | None:
    if value is None:
        return None
    return _require_agent(field_name, value)


def _require_agent_tuple(
    field_name: str, values: object, *, max_items: int
) -> tuple[AgentId, ...]:
    items: list[AgentId] = []
    for item in _require_tuple(field_name, values):
        agent = _require_agent(field_name, item)
        if any(agent == existing for existing in items):
            raise _fail(field_name, "duplicate_id")
        items.append(agent)
    if len(items) > max_items:
        raise _fail(field_name, "cap_exceeded")
    return tuple(items)


def _require_terms(field_name: str, values: object) -> tuple[str, ...]:
    items: list[str] = []
    for item in _require_tuple(field_name, values):
        token = _require_token(field_name, item)
        if token in items:
            raise _fail(field_name, "duplicate_term")
        items.append(token)
    if len(items) > _MAX_TERMS:
        raise _fail(field_name, "cap_exceeded")
    return tuple(items)


def _reject_forbidden(value: object) -> None:
    if value is None or isinstance(value, (str, int, float, bool)):
        return
    name = type(value).__name__
    module = type(value).__module__
    if (
        name in _FORBIDDEN_TYPES
        or module == "analysis"
        or module.startswith("analysis.")
    ):
        raise TypeError(f"{name}: forbidden_input")


def _reject_forbidden_fields(model: type) -> None:
    names = {item.name for item in fields(model)}
    forbidden = names & FORBIDDEN_MEDIATION_FIELD_NAMES
    if forbidden:
        _LOG.error(
            "mediation_forbidden_field model=%s field_count=%s",
            model.__name__,
            len(forbidden),
        )
        raise ValueError(f"{model.__name__}: forbidden_field_name")


def mediation_context_key(observation: Observation) -> str:
    """Observable context digest; never derived from hidden world state."""
    if type(observation) is not Observation:
        raise TypeError("observation must be Observation")
    location = (
        "none"
        if observation.self_body is None
        else observation.self_body.location_id.value
    )
    day_phase = "none" if observation.day_phase is None else observation.day_phase.value
    return _digest16(
        f"mediation-context|{observation.world_id.value}|{location}|{day_phase}"
    )


def mediation_case_ref(
    owner_id: AgentId,
    *,
    origin_id: AgentId | None,
    subject_token: str,
    context_key: str,
    inception_tick: int,
    inception_lineage: str,
) -> str:
    """Claimed dispute lineage, stable for a locally created case."""
    owner = _require_agent("owner_id", owner_id)
    origin = _require_optional_agent("origin_id", origin_id)
    subject = _require_token("subject_token", subject_token)
    context = _require_digest("context_key", context_key)
    tick = _require_nonneg_int("inception_tick", inception_tick)
    if not isinstance(inception_lineage, str) or not inception_lineage:
        raise _fail("inception_lineage", "invalid_type")
    origin_token = "-" if origin is None else origin.value
    return _sha256_hex(
        f"{owner.value}|mediation-case|{origin_token}|{subject}|"
        f"{context}|{tick}|{inception_lineage}"
    )


def mediation_case_id(owner_id: AgentId, case_ref: str) -> str:
    """Stable owner-local identity for one interpreted case."""
    owner = _require_agent("owner_id", owner_id)
    ref = _require_hex_id("case_ref", case_ref)
    return _sha256_hex(f"{owner.value}|mediation-case-id|{ref}")


def mediation_recommendation_id(
    owner_id: AgentId,
    case_ref: str,
    revision: int,
) -> str:
    """Stable owner-local identity for one recommendation revision."""
    owner = _require_agent("owner_id", owner_id)
    ref = _require_hex_id("case_ref", case_ref)
    rev = _require_nonneg_int("revision", revision)
    return _sha256_hex(f"{owner.value}|mediation-recommendation|{ref}|{rev}")


def mediation_response_id(
    owner_id: AgentId,
    case_ref: str,
    actor_id: AgentId,
    kind: MediationResponseKind,
    ordinal: int,
) -> str:
    owner = _require_agent("owner_id", owner_id)
    ref = _require_hex_id("case_ref", case_ref)
    actor = _require_agent("actor_id", actor_id)
    if type(kind) is not MediationResponseKind:
        raise _fail("kind", "unknown_response")
    order = _require_nonneg_int("ordinal", ordinal)
    return _sha256_hex(
        f"{owner.value}|mediation-response|{ref}|{actor.value}|{kind.value}|{order}"
    )


def mediation_role_expression_id(
    owner_id: AgentId,
    actor_id: AgentId,
    kind: MediationRoleExpressionKind,
    context_key: str,
    ordinal: int,
) -> str:
    owner = _require_agent("owner_id", owner_id)
    actor = _require_agent("actor_id", actor_id)
    if type(kind) is not MediationRoleExpressionKind:
        raise _fail("kind", "unknown_role_expression")
    context = _require_digest("context_key", context_key)
    order = _require_nonneg_int("ordinal", ordinal)
    return _sha256_hex(
        f"{owner.value}|mediation-role-expression|{actor.value}|"
        f"{kind.value}|{context}|{order}"
    )


def mediation_evidence_id(
    case_ref: str,
    ordinal: int,
    channel: MediationEvidenceChannel,
    lineage_ref: str,
) -> str:
    ref = _require_hex_id("case_ref", case_ref)
    order = _require_nonneg_int("ordinal", ordinal)
    if type(channel) is not MediationEvidenceChannel:
        raise _fail("channel", "unknown_channel")
    if not isinstance(lineage_ref, str) or not lineage_ref:
        raise _fail("lineage_ref", "invalid_type")
    return _sha256_hex(
        f"{ref}|mediation-evidence|{order}|{channel.value}|{lineage_ref}"
    )


def mediation_evidence_id_prefix(
    case_ref: str,
    channel: MediationEvidenceChannel,
    lineage_ref: str,
) -> str:
    """Digest used only for deterministic deduplication before assignment."""
    ref = _require_hex_id("case_ref", case_ref)
    if type(channel) is not MediationEvidenceChannel:
        raise _fail("channel", "unknown_channel")
    if not isinstance(lineage_ref, str) or not lineage_ref:
        raise _fail("lineage_ref", "invalid_type")
    return _digest16(f"{ref}|mediation-evidence-root|{channel.value}|{lineage_ref}")


@dataclass(frozen=True, slots=True)
class MediationEvidence:
    """One bounded item of provenance-aware case evidence."""

    evidence_id: str
    ordinal: int
    channel: MediationEvidenceChannel
    lineage_ref: str
    root_ref: str
    tick: int
    independently_evidenced: bool = True
    actor_id: AgentId | None = None

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        object.__setattr__(
            self, "evidence_id", _require_hex_id("evidence_id", self.evidence_id)
        )
        object.__setattr__(
            self, "ordinal", _require_nonneg_int("evidence.ordinal", self.ordinal)
        )
        if type(self.channel) is not MediationEvidenceChannel:
            raise _fail("evidence.channel", "unknown_channel")
        if not isinstance(self.lineage_ref, str) or not self.lineage_ref:
            raise _fail("evidence.lineage_ref", "invalid_type")
        if not isinstance(self.root_ref, str) or not self.root_ref:
            raise _fail("evidence.root_ref", "invalid_type")
        object.__setattr__(
            self, "tick", _require_nonneg_int("evidence.tick", self.tick)
        )
        if type(self.independently_evidenced) is not bool:
            raise _fail("evidence.independently_evidenced", "invalid_type")
        if self.actor_id is not None:
            _require_agent("evidence.actor_id", self.actor_id)

    def __repr__(self) -> str:
        return (
            f"MediationEvidence(evidence_id={self.evidence_id[:8]!r}, "
            f"ordinal={self.ordinal}, channel={self.channel.value!r}, "
            f"tick={self.tick}, "
            f"independently_evidenced={self.independently_evidenced})"
        )


@dataclass(frozen=True, slots=True)
class MediationAccount:
    """One attributed assertion. It is never a finding of fault."""

    account_id: str
    owner_id: AgentId
    actor_id: AgentId
    case_ref: str
    subject_token: str
    claim_token: str
    direct: bool
    channel: MediationEvidenceChannel
    root_ref: str
    first_tick: int
    last_tick: int
    evidence_id: str
    reported_by_id: AgentId | None = None
    occurrence_ref: str | None = None
    contradiction_refs: tuple[str, ...] = ()
    uncertainty: float = 0.0
    active: bool = True

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        object.__setattr__(
            self, "account_id", _require_hex_id("account_id", self.account_id)
        )
        object.__setattr__(self, "owner_id", _require_agent("owner_id", self.owner_id))
        object.__setattr__(self, "actor_id", _require_agent("actor_id", self.actor_id))
        object.__setattr__(self, "case_ref", _require_hex_id("case_ref", self.case_ref))
        object.__setattr__(
            self,
            "subject_token",
            _require_token("account.subject_token", self.subject_token),
        )
        object.__setattr__(
            self,
            "claim_token",
            _require_token("account.claim_token", self.claim_token),
        )
        if type(self.direct) is not bool:
            raise _fail("account.direct", "invalid_type")
        if type(self.channel) is not MediationEvidenceChannel:
            raise _fail("account.channel", "unknown_channel")
        if not isinstance(self.root_ref, str) or not self.root_ref:
            raise _fail("account.root_ref", "invalid_type")
        _require_span("account", self.first_tick, self.last_tick)
        object.__setattr__(
            self,
            "evidence_id",
            _require_hex_id("account.evidence_id", self.evidence_id),
        )
        _require_optional_agent("account.reported_by_id", self.reported_by_id)
        if self.occurrence_ref is not None:
            if (
                not isinstance(self.occurrence_ref, str)
                or not self.occurrence_ref
                or len(self.occurrence_ref) > 64
            ):
                raise _fail("account.occurrence_ref", "invalid_type")
        refs = _require_tuple("account.contradiction_refs", self.contradiction_refs)
        checked: list[str] = []
        for item in refs:
            ref = _require_hex_id("account.contradiction_refs", item)
            if ref in checked:
                raise _fail("account.contradiction_refs", "duplicate_id")
            checked.append(ref)
        if len(checked) > _MAX_ACCOUNTS:
            raise _fail("account.contradiction_refs", "cap_exceeded")
        object.__setattr__(self, "contradiction_refs", tuple(checked))
        object.__setattr__(
            self,
            "uncertainty",
            _require_strength("account.uncertainty", self.uncertainty),
        )
        if type(self.active) is not bool:
            raise _fail("account.active", "invalid_type")

    def __repr__(self) -> str:
        return (
            f"MediationAccount(account_id={self.account_id[:8]!r}, "
            f"case_ref={self.case_ref[:8]!r}, direct={self.direct}, "
            f"channel={self.channel.value!r}, active={self.active})"
        )


@dataclass(frozen=True, slots=True)
class MediationRecommendation:
    """One owner-local revision of bounded proposed terms."""

    recommendation_id: str
    owner_id: AgentId
    case_ref: str
    revision: int
    proposed_actor_id: AgentId
    action_token: str
    first_tick: int
    last_tick: int
    window_first_tick: int
    window_last_tick: int
    status: MediationRecommendationStatus = MediationRecommendationStatus.ACTIVE
    originator_id: AgentId | None = None
    target_ids: tuple[AgentId, ...] = ()
    item_token: str | None = None
    project_token: str | None = None
    terms: tuple[str, ...] = ()
    quantity: int = 1
    evidence: tuple[MediationEvidence, ...] = ()
    pruned_evidence_count: int = 0
    notices: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        _require_agent("owner_id", self.owner_id)
        object.__setattr__(
            self,
            "recommendation_id",
            _require_hex_id("recommendation_id", self.recommendation_id),
        )
        object.__setattr__(self, "case_ref", _require_hex_id("case_ref", self.case_ref))
        rev = _require_nonneg_int("revision", self.revision)
        object.__setattr__(self, "revision", rev)
        expected = mediation_recommendation_id(self.owner_id, self.case_ref, rev)
        if self.recommendation_id != expected:
            raise _fail("recommendation_id", "id_mismatch")
        _require_agent("proposed_actor_id", self.proposed_actor_id)
        object.__setattr__(
            self,
            "action_token",
            _require_token("action_token", self.action_token),
        )
        _require_span("recommendation", self.first_tick, self.last_tick)
        _require_window("recommendation", self.window_first_tick, self.window_last_tick)
        if type(self.status) is not MediationRecommendationStatus:
            raise _fail("status", "unknown_status")
        _require_optional_agent("originator_id", self.originator_id)
        object.__setattr__(
            self,
            "target_ids",
            _require_agent_tuple("target_ids", self.target_ids, max_items=_MAX_TARGETS),
        )
        if self.item_token is not None:
            object.__setattr__(
                self, "item_token", _require_token("item_token", self.item_token)
            )
        if self.project_token is not None:
            object.__setattr__(
                self,
                "project_token",
                _require_token("project_token", self.project_token),
            )
        object.__setattr__(self, "terms", _require_terms("terms", self.terms))
        quantity = _require_nonneg_int("quantity", self.quantity)
        if quantity > _MAX_QUANTITY:
            raise _fail("quantity", "out_of_range")
        object.__setattr__(self, "quantity", quantity)
        evidence = _require_tuple("evidence", self.evidence)
        checked: list[MediationEvidence] = []
        seen: set[str] = set()
        previous_ordinal = -1
        previous_tick = -1
        for item in evidence:
            if type(item) is not MediationEvidence:
                raise _fail("evidence", "invalid_type")
            if item.evidence_id in seen:
                raise _fail("evidence", "duplicate_evidence")
            if item.ordinal <= previous_ordinal:
                raise _fail("evidence.ordinal", "not_monotonic")
            if item.tick < previous_tick:
                raise _fail("evidence.tick", "not_monotonic")
            seen.add(item.evidence_id)
            previous_ordinal = item.ordinal
            previous_tick = item.tick
            checked.append(item)
        if len(checked) > _MAX_EVIDENCE:
            raise _fail("evidence", "cap_exceeded")
        object.__setattr__(self, "evidence", tuple(checked))
        pruned = _require_nonneg_int(
            "pruned_evidence_count", self.pruned_evidence_count
        )
        object.__setattr__(self, "pruned_evidence_count", pruned)
        notices = _require_tuple("notices", self.notices)
        checked_notices: list[str] = []
        for notice in notices:
            if not isinstance(notice, str) or notice not in _NOTICE_REASONS:
                raise _fail("notices", "invalid_notice")
            if notice not in checked_notices:
                checked_notices.append(notice)
        if len(checked_notices) > _MAX_NOTICES:
            raise _fail("notices", "cap_exceeded")
        object.__setattr__(self, "notices", tuple(checked_notices))

    @property
    def actionable(self) -> bool:
        return self.status is MediationRecommendationStatus.ACTIVE

    @property
    def evidence_coverage(self) -> str:
        return "partial" if self.pruned_evidence_count else "complete"

    def supports_tick(self, tick: int) -> bool:
        return self.window_first_tick <= tick <= self.window_last_tick

    def __repr__(self) -> str:
        return (
            f"MediationRecommendation("
            f"recommendation_id={self.recommendation_id[:8]!r}, "
            f"revision={self.revision}, status={self.status.value!r}, "
            f"evidence_count={len(self.evidence)})"
        )


@dataclass(frozen=True, slots=True)
class MediationResponse:
    """One actor-specific response bound to a case and optional revision."""

    response_id: str
    owner_id: AgentId
    actor_id: AgentId
    case_ref: str
    kind: MediationResponseKind
    tick: int
    evidence_id: str
    recommendation_ref: str | None = None
    recommendation_revision: int | None = None
    undertaking_token: str | None = None
    terms: tuple[str, ...] = ()
    accepted_terms: tuple[str, ...] = ()
    new_case_ref: str | None = None
    withdraws_response_id: str | None = None
    direct: bool = True
    active: bool = True

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        _require_agent("owner_id", self.owner_id)
        _require_agent("actor_id", self.actor_id)
        object.__setattr__(
            self, "response_id", _require_hex_id("response_id", self.response_id)
        )
        object.__setattr__(self, "case_ref", _require_hex_id("case_ref", self.case_ref))
        if type(self.kind) is not MediationResponseKind:
            raise _fail("kind", "unknown_response")
        object.__setattr__(
            self, "tick", _require_nonneg_int("response.tick", self.tick)
        )
        object.__setattr__(
            self,
            "evidence_id",
            _require_hex_id("response.evidence_id", self.evidence_id),
        )
        if self.recommendation_ref is not None:
            _require_hex_id("recommendation_ref", self.recommendation_ref)
        if (self.recommendation_ref is None) != (self.recommendation_revision is None):
            raise _fail("recommendation_revision", "incomplete_reference")
        if self.recommendation_revision is not None:
            _require_nonneg_int("recommendation_revision", self.recommendation_revision)
        if self.undertaking_token is not None:
            object.__setattr__(
                self,
                "undertaking_token",
                _require_token("undertaking_token", self.undertaking_token),
            )
        object.__setattr__(self, "terms", _require_terms("terms", self.terms))
        object.__setattr__(
            self,
            "accepted_terms",
            _require_terms("accepted_terms", self.accepted_terms),
        )
        if self.kind is MediationResponseKind.ACCEPT:
            if self.recommendation_ref is None:
                raise _fail("recommendation_ref", "required_for_acceptance")
            if self.undertaking_token is None and not self.accepted_terms:
                raise _fail("accepted_terms", "required_for_acceptance")
        if (
            self.kind is MediationResponseKind.ACCOUNT
            and self.undertaking_token is None
        ):
            object.__setattr__(self, "undertaking_token", "account")
        if self.kind is MediationResponseKind.COUNTERPROPOSE:
            if self.new_case_ref is not None:
                _require_hex_id("new_case_ref", self.new_case_ref)
            if not self.terms:
                raise _fail("terms", "required_for_counterproposal")
        elif self.new_case_ref is not None:
            raise _fail("new_case_ref", "unexpected")
        if self.withdraws_response_id is not None:
            _require_hex_id("withdraws_response_id", self.withdraws_response_id)
        if self.kind is MediationResponseKind.WITHDRAW:
            if self.withdraws_response_id is None:
                raise _fail("withdraws_response_id", "required_for_withdrawal")
        elif self.withdraws_response_id is not None:
            raise _fail("withdraws_response_id", "unexpected")
        if type(self.direct) is not bool:
            raise _fail("response.direct", "invalid_type")
        if type(self.active) is not bool:
            raise _fail("response.active", "invalid_type")

    def __repr__(self) -> str:
        return (
            f"MediationResponse(response_id={self.response_id[:8]!r}, "
            f"case_ref={self.case_ref[:8]!r}, kind={self.kind.value!r}, "
            f"tick={self.tick}, active={self.active})"
        )


@dataclass(frozen=True, slots=True)
class MediationRoleExpression:
    """Auxiliary role-directed evidence, never a mandatory stage."""

    expression_id: str
    owner_id: AgentId
    actor_id: AgentId
    kind: MediationRoleExpressionKind
    context_key: str
    first_tick: int
    last_tick: int
    evidence_id: str
    case_ref: str | None = None
    function_token: str = "conflict_mediation"
    withdraws_expression_id: str | None = None
    active: bool = True

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        _require_agent("owner_id", self.owner_id)
        _require_agent("actor_id", self.actor_id)
        object.__setattr__(
            self,
            "expression_id",
            _require_hex_id("expression_id", self.expression_id),
        )
        if type(self.kind) is not MediationRoleExpressionKind:
            raise _fail("kind", "unknown_role_expression")
        object.__setattr__(
            self, "context_key", _require_digest("context_key", self.context_key)
        )
        _require_span("role_expression", self.first_tick, self.last_tick)
        object.__setattr__(
            self,
            "evidence_id",
            _require_hex_id("role_expression.evidence_id", self.evidence_id),
        )
        if self.case_ref is not None:
            _require_hex_id("role_expression.case_ref", self.case_ref)
        object.__setattr__(
            self,
            "function_token",
            _require_token("function_token", self.function_token),
        )
        if self.withdraws_expression_id is not None:
            _require_hex_id("withdraws_expression_id", self.withdraws_expression_id)
        if self.kind is MediationRoleExpressionKind.WITHDRAW_ROLE_ENDORSEMENT:
            if self.withdraws_expression_id is None:
                raise _fail("withdraws_expression_id", "required_for_withdrawal")
        elif self.withdraws_expression_id is not None:
            raise _fail("withdraws_expression_id", "unexpected")
        if type(self.active) is not bool:
            raise _fail("role_expression.active", "invalid_type")

    def __repr__(self) -> str:
        return (
            f"MediationRoleExpression(expression_id={self.expression_id[:8]!r}, "
            f"kind={self.kind.value!r}, "
            f"window=({self.first_tick},{self.last_tick}), active={self.active})"
        )


@dataclass(frozen=True, slots=True)
class MediationCase:
    """One owner's interpretation of a claimed dispute lineage."""

    case_id: str
    owner_id: AgentId
    case_ref: str
    subject_token: str
    context_key: str
    status: MediationCaseStatus
    first_tick: int
    last_tick: int
    window_first_tick: int
    window_last_tick: int
    origin_id: AgentId | None = None
    party_ids: tuple[AgentId, ...] = ()
    uncertainty: float = 0.0
    evidence: tuple[MediationEvidence, ...] = ()
    pruned_evidence_count: int = 0
    notices: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        _require_agent("owner_id", self.owner_id)
        object.__setattr__(self, "case_id", _require_hex_id("case_id", self.case_id))
        object.__setattr__(self, "case_ref", _require_hex_id("case_ref", self.case_ref))
        expected = mediation_case_id(self.owner_id, self.case_ref)
        if self.case_id != expected:
            raise _fail("case_id", "id_mismatch")
        object.__setattr__(
            self,
            "subject_token",
            _require_token("subject_token", self.subject_token),
        )
        object.__setattr__(
            self, "context_key", _require_digest("context_key", self.context_key)
        )
        if type(self.status) is not MediationCaseStatus:
            raise _fail("status", "unknown_status")
        _require_span("case", self.first_tick, self.last_tick)
        _require_window("case", self.window_first_tick, self.window_last_tick)
        _require_optional_agent("origin_id", self.origin_id)
        party_ids = _require_agent_tuple(
            "party_ids", self.party_ids, max_items=_MAX_PARTIES
        )
        object.__setattr__(self, "party_ids", party_ids)
        object.__setattr__(
            self, "uncertainty", _require_strength("case.uncertainty", self.uncertainty)
        )
        evidence = _require_tuple("evidence", self.evidence)
        checked: list[MediationEvidence] = []
        seen: set[str] = set()
        previous_ordinal = -1
        previous_tick = -1
        for item in evidence:
            if type(item) is not MediationEvidence:
                raise _fail("evidence", "invalid_type")
            if item.evidence_id in seen:
                raise _fail("evidence", "duplicate_evidence")
            if item.ordinal <= previous_ordinal:
                raise _fail("evidence.ordinal", "not_monotonic")
            if item.tick < previous_tick:
                raise _fail("evidence.tick", "not_monotonic")
            seen.add(item.evidence_id)
            previous_ordinal = item.ordinal
            previous_tick = item.tick
            checked.append(item)
        if len(checked) > _MAX_EVIDENCE:
            raise _fail("evidence", "cap_exceeded")
        object.__setattr__(self, "evidence", tuple(checked))
        object.__setattr__(
            self,
            "pruned_evidence_count",
            _require_nonneg_int("pruned_evidence_count", self.pruned_evidence_count),
        )
        notices = _require_tuple("notices", self.notices)
        checked_notices: list[str] = []
        for notice in notices:
            if not isinstance(notice, str) or notice not in _NOTICE_REASONS:
                raise _fail("notices", "invalid_notice")
            if notice not in checked_notices:
                checked_notices.append(notice)
        if len(checked_notices) > _MAX_NOTICES:
            raise _fail("notices", "cap_exceeded")
        object.__setattr__(self, "notices", tuple(checked_notices))

    @property
    def third_party_actionable(self) -> bool:
        """A third-party attempt needs two distinct known others."""
        return self.owner_id not in self.party_ids and len(self.party_ids) >= 2

    @property
    def actionable(self) -> bool:
        return (
            self.status
            in {
                MediationCaseStatus.UNRESOLVED,
                MediationCaseStatus.PARTIALLY_ADDRESSED,
                MediationCaseStatus.REOPENED,
                MediationCaseStatus.DISPUTED,
            }
            and self.third_party_actionable
        )

    @property
    def evidence_coverage(self) -> str:
        return "partial" if self.pruned_evidence_count else "complete"

    def supports_tick(self, tick: int) -> bool:
        return self.window_first_tick <= tick <= self.window_last_tick

    def __repr__(self) -> str:
        return (
            f"MediationCase(case_id={self.case_id[:8]!r}, "
            f"status={self.status.value!r}, party_count={len(self.party_ids)}, "
            f"evidence_count={len(self.evidence)})"
        )


@dataclass(frozen=True, slots=True)
class MediationAttempt:
    """One locally selected undertaking and its observable status."""

    attempt_id: str
    owner_id: AgentId
    case_ref: str
    actor_id: AgentId
    status: MediationAttemptStatus
    tick: int
    recommendation_ref: str | None = None
    recommendation_revision: int | None = None
    action_token: str | None = None
    target_ids: tuple[AgentId, ...] = ()
    item_token: str | None = None
    project_token: str | None = None
    resulting_command_token: str | None = None
    notices: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        _require_agent("owner_id", self.owner_id)
        _require_agent("actor_id", self.actor_id)
        object.__setattr__(
            self, "attempt_id", _require_hex_id("attempt_id", self.attempt_id)
        )
        object.__setattr__(
            self, "case_ref", _require_hex_id("attempt.case_ref", self.case_ref)
        )
        if type(self.status) is not MediationAttemptStatus:
            raise _fail("attempt.status", "unknown_status")
        object.__setattr__(self, "tick", _require_nonneg_int("attempt.tick", self.tick))
        if (self.recommendation_ref is None) != (self.recommendation_revision is None):
            raise _fail("attempt.recommendation_revision", "incomplete_reference")
        if self.recommendation_ref is not None:
            _require_hex_id("attempt.recommendation_ref", self.recommendation_ref)
            _require_nonneg_int(
                "attempt.recommendation_revision", self.recommendation_revision
            )
        if self.action_token is not None:
            object.__setattr__(
                self,
                "action_token",
                _require_token("attempt.action_token", self.action_token),
            )
        object.__setattr__(
            self,
            "target_ids",
            _require_agent_tuple(
                "attempt.target_ids", self.target_ids, max_items=_MAX_TARGETS
            ),
        )
        for name in ("item_token", "project_token", "resulting_command_token"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, _require_token(name, value))
        notices = _require_tuple("attempt.notices", self.notices)
        checked_notices: list[str] = []
        for notice in notices:
            if not isinstance(notice, str) or notice not in _NOTICE_REASONS:
                raise _fail("attempt.notices", "invalid_notice")
            if notice not in checked_notices:
                checked_notices.append(notice)
        if len(checked_notices) > _MAX_NOTICES:
            raise _fail("attempt.notices", "cap_exceeded")
        object.__setattr__(self, "notices", tuple(checked_notices))

    def __repr__(self) -> str:
        return (
            f"MediationAttempt(attempt_id={self.attempt_id[:8]!r}, "
            f"status={self.status.value!r}, tick={self.tick})"
        )


@dataclass(frozen=True, slots=True)
class MediationOutcome:
    """Claimed or observed case outcome; never an authoritative settlement."""

    outcome_id: str
    owner_id: AgentId
    case_ref: str
    kind: MediationOutcomeKind
    claimed: bool
    first_tick: int
    last_tick: int
    actor_id: AgentId | None = None
    evidence_id: str | None = None
    notice: str | None = None

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        _require_agent("owner_id", self.owner_id)
        object.__setattr__(
            self, "outcome_id", _require_hex_id("outcome_id", self.outcome_id)
        )
        object.__setattr__(
            self, "case_ref", _require_hex_id("outcome.case_ref", self.case_ref)
        )
        if type(self.kind) is not MediationOutcomeKind:
            raise _fail("outcome.kind", "unknown_status")
        if type(self.claimed) is not bool:
            raise _fail("outcome.claimed", "invalid_type")
        _require_span("outcome", self.first_tick, self.last_tick)
        _require_optional_agent("outcome.actor_id", self.actor_id)
        if self.evidence_id is not None:
            _require_hex_id("outcome.evidence_id", self.evidence_id)
        if self.notice is not None:
            if not isinstance(self.notice, str) or self.notice not in _NOTICE_REASONS:
                raise _fail("outcome.notice", "invalid_notice")

    def __repr__(self) -> str:
        return (
            f"MediationOutcome(outcome_id={self.outcome_id[:8]!r}, "
            f"kind={self.kind.value!r}, claimed={self.claimed})"
        )


@dataclass(frozen=True, slots=True)
class MediationAuthorityComponent:
    """One recipient-relative appraisal component with provenance."""

    channel: MediationAuthorityChannel
    available: bool
    strength: float
    uncertainty: float
    provenance: tuple[str, ...] = ()
    dissenting: bool = False

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        if type(self.channel) is not MediationAuthorityChannel:
            raise _fail("authority.channel", "unknown_channel")
        if type(self.available) is not bool:
            raise _fail("authority.available", "invalid_type")
        object.__setattr__(
            self,
            "strength",
            _require_strength("authority.strength", self.strength),
        )
        object.__setattr__(
            self,
            "uncertainty",
            _require_strength("authority.uncertainty", self.uncertainty),
        )
        provenance = _require_tuple("authority.provenance", self.provenance)
        checked: list[str] = []
        for item in provenance:
            token = _require_token("authority.provenance", item)
            if token in checked:
                raise _fail("authority.provenance", "duplicate_id")
            checked.append(token)
        if len(checked) > _MAX_PROVENANCE:
            raise _fail("authority.provenance", "cap_exceeded")
        object.__setattr__(self, "provenance", tuple(checked))
        if type(self.dissenting) is not bool:
            raise _fail("authority.dissenting", "invalid_type")
        if not self.available and self.strength != 0.0:
            raise _fail("authority.strength", "unavailable_nonzero")
        if not self.available and checked:
            raise _fail("authority.provenance", "unavailable_provenance")

    def __repr__(self) -> str:
        return (
            f"MediationAuthorityComponent(channel={self.channel.value!r}, "
            f"available={self.available}, strength={self.strength}, "
            f"provenance_count={len(self.provenance)})"
        )


@dataclass(frozen=True, slots=True)
class MediationAuthorityAppraisal:
    """Small immutable recipient-relative appraisal. No universal score."""

    owner_id: AgentId
    mediator_id: AgentId
    context_key: str
    components: tuple[MediationAuthorityComponent, ...] = ()
    reason: str | None = None

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        _require_agent("appraisal.owner_id", self.owner_id)
        _require_agent("appraisal.mediator_id", self.mediator_id)
        if self.owner_id == self.mediator_id:
            raise _fail("appraisal.mediator_id", "owner_is_mediator")
        object.__setattr__(
            self, "context_key", _require_digest("context_key", self.context_key)
        )
        components = _require_tuple("appraisal.components", self.components)
        checked: list[MediationAuthorityComponent] = []
        seen: set[str] = set()
        previous = -1
        for item in components:
            if type(item) is not MediationAuthorityComponent:
                raise _fail("appraisal.components", "invalid_type")
            channel = item.channel.value
            if channel in seen:
                raise _fail("appraisal.components", "duplicate_channel")
            index = list(MediationAuthorityChannel).index(item.channel)
            if index <= previous:
                raise _fail("appraisal.components", "unordered")
            previous = index
            seen.add(channel)
            checked.append(item)
        if len(checked) > len(MediationAuthorityChannel):
            raise _fail("appraisal.components", "cap_exceeded")
        object.__setattr__(self, "components", tuple(checked))
        if self.reason is not None:
            if not isinstance(self.reason, str) or self.reason not in _NOTICE_REASONS:
                raise _fail("appraisal.reason", "invalid_notice")

    @property
    def available_channels(self) -> tuple[MediationAuthorityChannel, ...]:
        return tuple(item.channel for item in self.components if item.available)

    @property
    def unavailable_channels(self) -> tuple[MediationAuthorityChannel, ...]:
        return tuple(item.channel for item in self.components if not item.available)

    def component(
        self, channel: MediationAuthorityChannel
    ) -> MediationAuthorityComponent:
        if type(channel) is not MediationAuthorityChannel:
            raise _fail("channel", "unknown_channel")
        for item in self.components:
            if item.channel is channel:
                return item
        raise _fail("channel", "missing_component")

    def __repr__(self) -> str:
        return (
            f"MediationAuthorityAppraisal("
            f"owner_id={self.owner_id.value!r}, "
            f"mediator_id={self.mediator_id.value!r}, "
            f"available_count={len(self.available_channels)})"
        )


@dataclass(frozen=True, slots=True)
class MediationPolicy:
    """Locked mediation constants. Runner JSON does not carry these."""

    version: str = MEDIATION_POLICY_VERSION
    default_action_window: int = _DEFAULT_ACTION_WINDOW
    max_action_window: int = _MAX_ACTION_WINDOW
    evidence_retention: int = _EVIDENCE_RETENTION
    reference_freshness: int = _REFERENCE_FRESHNESS
    dedup_retention: int = _DEDUP_RETENTION
    max_cases: int = _MAX_CASES
    max_accounts: int = _MAX_ACCOUNTS
    max_recommendations: int = _MAX_RECOMMENDATIONS
    max_responses: int = _MAX_RESPONSES
    max_role_expressions: int = _MAX_ROLE_EXPRESSIONS
    max_attempts: int = _MAX_ATTEMPTS
    max_outcomes: int = _MAX_OUTCOMES
    max_evidence: int = _MAX_EVIDENCE
    max_revisions: int = _MAX_REVISIONS
    max_terms: int = _MAX_TERMS
    max_parties: int = _MAX_PARTIES

    def __post_init__(self) -> None:
        if self.version != MEDIATION_POLICY_VERSION:
            raise _fail("version", "unsupported_policy")
        for name, expected in (
            ("default_action_window", _DEFAULT_ACTION_WINDOW),
            ("max_action_window", _MAX_ACTION_WINDOW),
            ("evidence_retention", _EVIDENCE_RETENTION),
            ("reference_freshness", _REFERENCE_FRESHNESS),
            ("dedup_retention", _DEDUP_RETENTION),
            ("max_cases", _MAX_CASES),
            ("max_accounts", _MAX_ACCOUNTS),
            ("max_recommendations", _MAX_RECOMMENDATIONS),
            ("max_responses", _MAX_RESPONSES),
            ("max_role_expressions", _MAX_ROLE_EXPRESSIONS),
            ("max_attempts", _MAX_ATTEMPTS),
            ("max_outcomes", _MAX_OUTCOMES),
            ("max_evidence", _MAX_EVIDENCE),
            ("max_revisions", _MAX_REVISIONS),
            ("max_terms", _MAX_TERMS),
            ("max_parties", _MAX_PARTIES),
        ):
            object.__setattr__(
                self, name, _locked_int(name, getattr(self, name), expected)
            )


@dataclass(frozen=True, slots=True)
class MediationLedger:
    """Owner-scoped mediation. ``None`` means the mode is off."""

    owner_id: AgentId
    cases: tuple[MediationCase, ...] = ()
    accounts: tuple[MediationAccount, ...] = ()
    recommendations: tuple[MediationRecommendation, ...] = ()
    responses: tuple[MediationResponse, ...] = ()
    role_expressions: tuple[MediationRoleExpression, ...] = ()
    attempts: tuple[MediationAttempt, ...] = ()
    outcomes: tuple[MediationOutcome, ...] = ()
    notices: tuple[str, ...] = ()
    policy_version: str = MEDIATION_POLICY_VERSION
    retired_case_refs: tuple[str, ...] = ()
    first_observed_tick: int | None = None
    last_observed_tick: int | None = None
    observation_count: int = 0
    pruned_case_count: int = 0
    pruned_evidence_count: int = 0
    pruned_recommendation_count: int = 0
    pruned_response_count: int = 0

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        _require_agent("owner_id", self.owner_id)
        if self.policy_version != MEDIATION_POLICY_VERSION:
            raise _fail("policy_version", "unsupported_policy")
        for name, expected_type, key_field, cap in (
            ("cases", MediationCase, "case_id", _MAX_CASES),
            ("accounts", MediationAccount, "account_id", _MAX_ACCOUNTS),
            (
                "recommendations",
                MediationRecommendation,
                "recommendation_id",
                _MAX_RECOMMENDATIONS,
            ),
            ("responses", MediationResponse, "response_id", _MAX_RESPONSES),
            (
                "role_expressions",
                MediationRoleExpression,
                "expression_id",
                _MAX_ROLE_EXPRESSIONS,
            ),
            ("attempts", MediationAttempt, "attempt_id", _MAX_ATTEMPTS),
            ("outcomes", MediationOutcome, "outcome_id", _MAX_OUTCOMES),
        ):
            items = _require_tuple(name, getattr(self, name))
            checked: list[object] = []
            seen: set[str] = set()
            for item in items:
                if type(item) is not expected_type:
                    raise _fail(name, "invalid_type")
                key = cast(str, getattr(item, key_field))
                if key in seen:
                    raise _fail(name, "duplicate_id")
                seen.add(key)
                checked.append(item)
            if len(checked) > cap:
                raise _fail(name, "cap_exceeded")
            object.__setattr__(self, name, tuple(checked))
        for item in self.cases:
            if item.owner_id != self.owner_id:
                raise _fail("cases.owner_id", "owner_mismatch")
        for item in self.accounts:
            if item.owner_id != self.owner_id:
                raise _fail("accounts.owner_id", "owner_mismatch")
        for item in self.recommendations:
            if item.owner_id != self.owner_id:
                raise _fail("recommendations.owner_id", "owner_mismatch")
        for item in self.responses:
            if item.owner_id != self.owner_id:
                raise _fail("responses.owner_id", "owner_mismatch")
        for item in self.role_expressions:
            if item.owner_id != self.owner_id:
                raise _fail("role_expressions.owner_id", "owner_mismatch")
        for item in self.attempts:
            if item.owner_id != self.owner_id:
                raise _fail("attempts.owner_id", "owner_mismatch")
        for item in self.outcomes:
            if item.owner_id != self.owner_id:
                raise _fail("outcomes.owner_id", "owner_mismatch")
        notices = _require_tuple("notices", self.notices)
        checked_notices: list[str] = []
        for notice in notices:
            if not isinstance(notice, str) or notice not in _NOTICE_REASONS:
                raise _fail("notices", "invalid_notice")
            if notice not in checked_notices:
                checked_notices.append(notice)
        if len(checked_notices) > _MAX_NOTICES:
            raise _fail("notices", "cap_exceeded")
        object.__setattr__(self, "notices", tuple(checked_notices))
        retired = _require_tuple("retired_case_refs", self.retired_case_refs)
        checked_retired: list[str] = []
        for item in retired:
            ref = _require_hex_id("retired_case_refs", item)
            if ref in checked_retired:
                raise _fail("retired_case_refs", "duplicate_id")
            checked_retired.append(ref)
        if len(checked_retired) > _MAX_CASES:
            raise _fail("retired_case_refs", "cap_exceeded")
        object.__setattr__(self, "retired_case_refs", tuple(checked_retired))
        first = self.first_observed_tick
        last = self.last_observed_tick
        if (first is None) != (last is None):
            raise _fail("first_observed_tick", "incomplete_window")
        if first is not None:
            first_tick = _require_nonneg_int("first_observed_tick", first)
            last_tick = _require_nonneg_int("last_observed_tick", last)
            if last_tick < first_tick:
                raise _fail("last_observed_tick", "before_first_tick")
        if (
            isinstance(self.observation_count, bool)
            or type(self.observation_count) is not int
            or self.observation_count < 0
        ):
            raise _fail("observation_count", "invalid_type")
        if first is None and self.observation_count:
            raise _fail("observation_count", "missing_window")
        for name in (
            "pruned_case_count",
            "pruned_evidence_count",
            "pruned_recommendation_count",
            "pruned_response_count",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or type(value) is not int or value < 0:
                raise _fail(name, "invalid_type")
        _LOG.debug(
            "mediation_ledger_constructed owner_id=%s policy_version=%s "
            "case_count=%s observation_count=%s",
            self.owner_id.value,
            self.policy_version,
            len(self.cases),
            self.observation_count,
        )

    @property
    def enabled(self) -> bool:
        return True

    @property
    def has_content(self) -> bool:
        return bool(
            self.cases
            or self.accounts
            or self.recommendations
            or self.responses
            or self.role_expressions
            or self.attempts
            or self.outcomes
        )

    @property
    def coverage(self) -> str:
        return (
            "partial"
            if any(
                (
                    self.pruned_case_count,
                    self.pruned_evidence_count,
                    self.pruned_recommendation_count,
                    self.pruned_response_count,
                )
            )
            else "complete"
        )

    @property
    def actionable_cases(self) -> tuple[MediationCase, ...]:
        return tuple(case for case in self.cases if case.actionable)

    def __repr__(self) -> str:
        return (
            f"MediationLedger(owner_id={self.owner_id.value!r}, "
            f"case_count={len(self.cases)}, "
            f"recommendation_count={len(self.recommendations)}, "
            f"response_count={len(self.responses)}, "
            f"observation_count={self.observation_count}, "
            f"coverage={self.coverage!r})"
        )


def default_mediation_policy() -> MediationPolicy:
    """Return the only accepted mediation policy."""
    return MediationPolicy()


def empty_mediation_ledger(owner_id: AgentId) -> MediationLedger:
    """Ledger with no content. Disabled mode does not call this."""
    return MediationLedger(owner_id=owner_id)


def require_owner_mediation(
    ledger: object,
    owner_id: AgentId,
    *,
    field_name: str,
) -> None:
    """Reject a foreign or mistyped mediation ledger."""
    if ledger is None:
        return
    if type(owner_id) is not AgentId:
        raise _fail("owner_id", "invalid_type")
    if type(ledger) is not MediationLedger:
        _LOG.warning("mediation_carry_rejected reason=%s", "invalid_type")
        raise TypeError(f"{field_name} must be MediationLedger")
    if ledger.owner_id != owner_id:
        _LOG.error(
            "mediation_validation_failed field=%s reason_code=%s",
            field_name,
            "owner_mismatch",
        )
        _LOG.warning("mediation_carry_rejected reason=%s", "owner_mismatch")
        raise ValueError(f"{field_name} owner_id mismatch")


# ---------------------------------------------------------------------------
# Evidence adapters, deterministic updates, and authority appraisal
# ---------------------------------------------------------------------------

_MEDIATION_PREDICATE_BY_ACT: Final[dict[str, MediationAct]] = {
    "mediation_hear": MediationAct.HEAR_DISPUTE,
    "mediation_request": MediationAct.REQUEST_ACCOUNTS,
    "mediation_compromise": MediationAct.PROPOSE_COMPROMISE,
    "mediation_vouch": MediationAct.VOUCH,
    "mediation_mediate": MediationAct.MEDIATE,
    "mediation_restitution": MediationAct.RECOMMEND_RESTITUTION,
}
_RESPONSE_PREDICATE_BY_KIND: Final[dict[str, MediationResponseKind]] = {
    "mediation_account": MediationResponseKind.ACCOUNT,
    "mediation_accept": MediationResponseKind.ACCEPT,
    "mediation_refuse": MediationResponseKind.REFUSE,
    "mediation_defer": MediationResponseKind.DEFER,
    "mediation_counter": MediationResponseKind.COUNTERPROPOSE,
    "mediation_withdraw": MediationResponseKind.WITHDRAW,
    "mediation_claim_settlement": MediationResponseKind.CLAIM_SETTLEMENT,
}
_ROLE_PREDICATE_BY_KIND: Final[dict[str, MediationRoleExpressionKind]] = {
    "mediation_invite": MediationRoleExpressionKind.INVITE_MEDIATOR,
    "mediation_endorse": MediationRoleExpressionKind.ENDORSE_ROLE,
    "mediation_withdraw_role": MediationRoleExpressionKind.WITHDRAW_ROLE_ENDORSEMENT,
}
_DEFAULT_SUBJECT: Final[str] = "item_share"


@dataclass(frozen=True, slots=True)
class _MediationSignal:
    kind: str
    act: MediationAct | None
    response_kind: MediationResponseKind | None
    role_kind: MediationRoleExpressionKind | None
    case_ref: str
    revision: int
    lineage_ref: str
    root_ref: str
    channel: MediationEvidenceChannel
    context_key: str
    actor_id: AgentId | None = None
    subject_token: str = _DEFAULT_SUBJECT
    claim_token: str = "reported_claim"
    occurrence_ref: str | None = None
    action_token: str | None = None
    proposed_actor_id: AgentId | None = None
    target_ids: tuple[AgentId, ...] = ()
    item_token: str | None = None
    project_token: str | None = None
    terms: tuple[str, ...] = ()
    accepted_terms: tuple[str, ...] = ()
    undertaking_token: str | None = None
    recommendation_ref: str | None = None
    recommendation_revision: int | None = None
    new_case_ref: str | None = None
    withdraws_id: str | None = None
    window_first_tick: int | None = None
    window_last_tick: int | None = None
    quantity: int = 1
    confidence: float = 1.0
    independently_evidenced: bool = True


def _resolve_entity(
    identity: OwnerSafeSocialIdentity, entity_id: EntityId | None
) -> AgentId | None:
    if entity_id is None:
        return None
    if entity_id == identity.owner_entity_id:
        return identity.owner_id
    for binding in identity.counterparts:
        if binding.entity_id == entity_id:
            return binding.agent_id
    return None


def _parse_optional_entity(token: str) -> EntityId | None:
    token = token.strip()
    if not token or token == "-":
        return None
    try:
        return EntityId(token)
    except ValueError:
        return None


def _parse_optional_id(token: str) -> str | None:
    token = token.strip()
    if not token or token == "-":
        return None
    if len(token) != 64 or any(char not in _HEX for char in token):
        return None
    return token


def _parse_optional_token(token: str) -> str | None:
    token = token.strip()
    if not token or token == "-":
        return None
    return _require_token("signal.token", token)


def _parse_terms(token: str) -> tuple[str, ...]:
    token = token.strip()
    if not token or token == "-":
        return ()
    terms: list[str] = []
    for part in token.split(","):
        if not part:
            continue
        value = _require_token("signal.term", part)
        if value not in terms:
            terms.append(value)
    if len(terms) > _MAX_TERMS:
        raise _fail("signal.terms", "cap_exceeded")
    return tuple(terms)


def _parse_revision(token: str) -> int | None:
    try:
        value = int(token.strip())
    except (TypeError, ValueError):
        return None
    return value if value >= 0 else None


def _signal_from_relation(
    *,
    speaker_id: EntityId | None,
    identity: OwnerSafeSocialIdentity,
    predicate: str,
    object_text: str,
    context_key: str,
    lineage_ref: str,
    root_ref: str,
    channel: MediationEvidenceChannel,
    confidence: float,
) -> _MediationSignal | None:
    act = _MEDIATION_PREDICATE_BY_ACT.get(predicate)
    response_kind = _RESPONSE_PREDICATE_BY_KIND.get(predicate)
    role_kind = _ROLE_PREDICATE_BY_KIND.get(predicate)
    if act is None and response_kind is None and role_kind is None:
        return None
    parts = object_text.split("|")
    if len(parts) < 2:
        return None
    case_ref = _parse_optional_id(parts[0])
    if case_ref is None:
        return None
    revision = _parse_revision(parts[1])
    if revision is None:
        return None
    actor = _resolve_entity(identity, speaker_id)
    base: Any = dict(
        act=act,
        response_kind=response_kind,
        role_kind=role_kind,
        case_ref=case_ref,
        revision=revision,
        lineage_ref=lineage_ref,
        root_ref=root_ref,
        channel=channel,
        context_key=context_key,
        actor_id=actor,
        confidence=_quantize(confidence),
        independently_evidenced=actor is not None,
    )
    kind = (
        "act"
        if act is not None
        else ("response" if response_kind is not None else "role")
    )
    if act is not None:
        if act in {MediationAct.HEAR_DISPUTE, MediationAct.REQUEST_ACCOUNTS}:
            subject = _parse_optional_token(parts[2]) if len(parts) > 2 else None
            claim = _parse_optional_token(parts[3]) if len(parts) > 3 else None
            return _MediationSignal(
                kind=kind,
                subject_token=subject or _DEFAULT_SUBJECT,
                claim_token=claim or "reported_claim",
                **base,
            )
        if act in {MediationAct.MEDIATE, MediationAct.VOUCH}:
            target = (
                _resolve_entity(identity, _parse_optional_entity(parts[2]))
                if len(parts) > 2
                else None
            )
            claim = _parse_optional_token(parts[3]) if len(parts) > 3 else None
            return _MediationSignal(
                kind=kind,
                target_ids=() if target is None else (target,),
                claim_token=claim or "reported_claim",
                **base,
            )
        if len(parts) < 9:
            return None
        action = _parse_optional_token(parts[2])
        if action is None:
            return None
        proposed = _resolve_entity(identity, _parse_optional_entity(parts[3]))
        item = _parse_optional_token(parts[4])
        try:
            quantity = int(parts[5].strip())
        except ValueError:
            return None
        if quantity < 0 or quantity > _MAX_QUANTITY:
            return None
        terms = _parse_terms(parts[6])
        first = _parse_revision(parts[7])
        last = _parse_revision(parts[8])
        if first is None or last is None or last < first:
            return None
        return _MediationSignal(
            kind=kind,
            action_token=action,
            proposed_actor_id=proposed,
            item_token=item,
            quantity=quantity,
            terms=terms,
            window_first_tick=first,
            window_last_tick=last,
            **base,
        )
    if response_kind is not None:
        rec_ref = _parse_optional_id(parts[2]) if len(parts) > 2 else None
        rec_rev = _parse_revision(parts[3]) if len(parts) > 3 else None
        undertaking = _parse_optional_token(parts[4]) if len(parts) > 4 else None
        terms = _parse_terms(parts[5]) if len(parts) > 5 else ()
        accepted = _parse_terms(parts[6]) if len(parts) > 6 else ()
        new_case = _parse_optional_id(parts[7]) if len(parts) > 7 else None
        withdraws = _parse_optional_id(parts[8]) if len(parts) > 8 else None
        if (rec_ref is None) != (rec_rev is None):
            return None
        return _MediationSignal(
            kind=kind,
            recommendation_ref=rec_ref,
            recommendation_revision=rec_rev,
            undertaking_token=undertaking,
            terms=terms,
            accepted_terms=accepted,
            new_case_ref=new_case,
            withdraws_id=withdraws,
            **base,
        )
    function = _parse_optional_token(parts[2]) if len(parts) > 2 else None
    context = parts[3].strip() if len(parts) > 3 else context_key
    if len(context) != _DIGEST_LEN or any(char not in _HEX for char in context):
        context = context_key
    withdraws = _parse_optional_id(parts[4]) if len(parts) > 4 else None
    return _MediationSignal(
        kind=kind,
        subject_token=function or "conflict_mediation",
        context_key=context,
        withdraws_id=withdraws,
        **base,
    )


def _signals_from_observation(
    observation: Observation,
    identity: OwnerSafeSocialIdentity,
    context_key: str,
) -> list[_MediationSignal]:
    signals: list[_MediationSignal] = []
    for ordinal, communication in enumerate(observation.communications):
        declared = communication.utterance.declared
        root_ref = f"communication|{declared.root_communication_id.value}"
        for relation_index, relation in enumerate(
            communication.utterance.content.relations
        ):
            signal = _signal_from_relation(
                speaker_id=communication.speaker_id,
                identity=identity,
                predicate=relation.predicate,
                object_text=relation.object,
                context_key=context_key,
                lineage_ref=(
                    f"communication-{observation.tick}-{ordinal}-"
                    f"{relation_index}-{relation.predicate}"
                ),
                root_ref=root_ref,
                channel=MediationEvidenceChannel.COMMUNICATED,
                confidence=declared.sender_confidence,
            )
            if signal is not None:
                signals.append(signal)
    return signals


def _signals_from_episodes(
    context: object,
    identity: OwnerSafeSocialIdentity,
    context_key: str,
) -> list[_MediationSignal]:
    from agents.cognition.models import RetrievedMemoryContext, episode_facts

    if context is None:
        return []
    if type(context) is not RetrievedMemoryContext:
        raise TypeError("retrieved_memory_context must be RetrievedMemoryContext")
    if context.owner_id != identity.owner_id:
        raise ValueError("retrieved_memory_context owner_id mismatch")
    signals: list[_MediationSignal] = []
    for facts in episode_facts(context):
        concept_text = {item.mention_id: item.concept for item in facts.concepts}
        entity_by_mention = {
            item.mention_id: item.entity_id
            for item in facts.entities
            if item.entity_id is not None
        }
        for relation_index, relation in enumerate(facts.relations):
            if (
                relation.predicate not in _MEDIATION_PREDICATE_BY_ACT
                and relation.predicate not in _RESPONSE_PREDICATE_BY_KIND
                and relation.predicate not in _ROLE_PREDICATE_BY_KIND
            ):
                continue
            object_text = concept_text.get(relation.object.mention_id, "")
            speaker_entity = entity_by_mention.get(relation.subject.mention_id)
            signal = _signal_from_relation(
                speaker_id=speaker_entity,
                identity=identity,
                predicate=relation.predicate,
                object_text=object_text,
                context_key=context_key,
                lineage_ref=(
                    f"remembered-{facts.episode_id}-{relation.relation_id.value}-"
                    f"{relation_index}"
                ),
                root_ref=f"remembered|{facts.episode_id}",
                channel=MediationEvidenceChannel.REMEMBERED,
                confidence=facts.confidence,
            )
            if signal is not None:
                signals.append(signal)
    return signals


@dataclass(slots=True)
class _MediationDraft:
    owner_id: AgentId
    cases: dict[str, MediationCase]
    accounts: dict[str, MediationAccount]
    recommendations: dict[str, MediationRecommendation]
    responses: dict[str, MediationResponse]
    role_expressions: dict[str, MediationRoleExpression]
    attempts: dict[str, MediationAttempt]
    outcomes: dict[str, MediationOutcome]
    retired_refs: list[str]
    notices: list[str]
    first_observed_tick: int | None
    last_observed_tick: int | None
    observation_count: int
    pruned_case_count: int = 0
    pruned_evidence_count: int = 0
    pruned_recommendation_count: int = 0
    pruned_response_count: int = 0
    seen_roots: set[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.seen_roots is None:
            self.seen_roots = set()


def _draft_from_ledger(ledger: MediationLedger) -> _MediationDraft:
    return _MediationDraft(
        owner_id=ledger.owner_id,
        cases={item.case_ref: item for item in ledger.cases},
        accounts={item.account_id: item for item in ledger.accounts},
        recommendations={
            item.recommendation_id: item for item in ledger.recommendations
        },
        responses={item.response_id: item for item in ledger.responses},
        role_expressions={item.expression_id: item for item in ledger.role_expressions},
        attempts={item.attempt_id: item for item in ledger.attempts},
        outcomes={item.outcome_id: item for item in ledger.outcomes},
        retired_refs=list(ledger.retired_case_refs),
        notices=list(ledger.notices),
        first_observed_tick=ledger.first_observed_tick,
        last_observed_tick=ledger.last_observed_tick,
        observation_count=ledger.observation_count,
        pruned_case_count=ledger.pruned_case_count,
        pruned_evidence_count=ledger.pruned_evidence_count,
        pruned_recommendation_count=ledger.pruned_recommendation_count,
        pruned_response_count=ledger.pruned_response_count,
    )


def _notice(notices: list[str], reason: str) -> None:
    if reason not in notices:
        notices.append(reason)


def _case_evidence(
    case: MediationCase,
    *,
    case_ref: str,
    channel: MediationEvidenceChannel,
    lineage_ref: str,
    root_ref: str,
    tick: int,
    actor_id: AgentId | None,
    independently_evidenced: bool,
) -> MediationCase:
    if any(item.lineage_ref == lineage_ref for item in case.evidence):
        return case
    ordinal = len(case.evidence)
    evidence = MediationEvidence(
        evidence_id=mediation_evidence_id(case_ref, ordinal, channel, lineage_ref),
        ordinal=ordinal,
        channel=channel,
        lineage_ref=lineage_ref,
        root_ref=root_ref,
        tick=tick,
        actor_id=actor_id,
        independently_evidenced=independently_evidenced,
    )
    items = (*case.evidence, evidence)
    pruned = case.pruned_evidence_count
    if len(items) > _MAX_EVIDENCE:
        overflow = len(items) - _MAX_EVIDENCE
        items = items[overflow:]
        pruned += overflow
    return MediationCase(
        case_id=case.case_id,
        owner_id=case.owner_id,
        case_ref=case.case_ref,
        subject_token=case.subject_token,
        context_key=case.context_key,
        status=case.status,
        first_tick=case.first_tick,
        last_tick=max(case.last_tick, tick),
        window_first_tick=case.window_first_tick,
        window_last_tick=case.window_last_tick,
        origin_id=case.origin_id,
        party_ids=case.party_ids,
        uncertainty=case.uncertainty,
        evidence=items,
        pruned_evidence_count=pruned,
        notices=case.notices,
    )


def _ensure_case(
    draft: _MediationDraft,
    signal: _MediationSignal,
    tick: int,
    policy: MediationPolicy,
) -> MediationCase:
    existing = draft.cases.get(signal.case_ref)
    if existing is not None:
        updated = _case_evidence(
            existing,
            case_ref=signal.case_ref,
            channel=signal.channel,
            lineage_ref=signal.lineage_ref,
            root_ref=signal.root_ref,
            tick=tick,
            actor_id=signal.actor_id,
            independently_evidenced=signal.independently_evidenced,
        )
        draft.cases[signal.case_ref] = updated
        return updated
    if len(draft.cases) >= policy.max_cases:
        victim = min(
            draft.cases.values(), key=lambda item: (item.last_tick, item.case_id)
        )
        draft.cases.pop(victim.case_ref, None)
        draft.retired_refs.append(victim.case_ref)
        draft.pruned_case_count += 1
        _notice(draft.notices, "cap_exceeded")
    origin = signal.actor_id
    party_ids: tuple[AgentId, ...] = ()
    if origin is not None and origin != draft.owner_id:
        party_ids = (origin,)
    if signal.target_ids:
        party_ids = tuple(dict.fromkeys((*party_ids, *signal.target_ids)))
    case = MediationCase(
        case_id=mediation_case_id(draft.owner_id, signal.case_ref),
        owner_id=draft.owner_id,
        case_ref=signal.case_ref,
        subject_token=signal.subject_token,
        context_key=signal.context_key,
        status=MediationCaseStatus.UNRESOLVED,
        first_tick=tick,
        last_tick=tick,
        window_first_tick=tick,
        window_last_tick=tick + policy.default_action_window,
        origin_id=origin,
        party_ids=party_ids,
        evidence=(
            MediationEvidence(
                evidence_id=mediation_evidence_id(
                    signal.case_ref, 0, signal.channel, signal.lineage_ref
                ),
                ordinal=0,
                channel=signal.channel,
                lineage_ref=signal.lineage_ref,
                root_ref=signal.root_ref,
                tick=tick,
                actor_id=signal.actor_id,
                independently_evidenced=signal.independently_evidenced,
            ),
        ),
    )
    draft.cases[signal.case_ref] = case
    return case


def _replace_case_parties(
    case: MediationCase, party_ids: tuple[AgentId, ...]
) -> MediationCase:
    return MediationCase(
        case_id=case.case_id,
        owner_id=case.owner_id,
        case_ref=case.case_ref,
        subject_token=case.subject_token,
        context_key=case.context_key,
        status=case.status,
        first_tick=case.first_tick,
        last_tick=case.last_tick,
        window_first_tick=case.window_first_tick,
        window_last_tick=case.window_last_tick,
        origin_id=case.origin_id,
        party_ids=party_ids,
        uncertainty=case.uncertainty,
        evidence=case.evidence,
        pruned_evidence_count=case.pruned_evidence_count,
        notices=case.notices,
    )


def _existing_recommendation(
    draft: _MediationDraft,
    case_ref: str,
    revision: int | None,
) -> MediationRecommendation | None:
    matches = [
        item
        for item in draft.recommendations.values()
        if item.case_ref == case_ref and (revision is None or item.revision == revision)
    ]
    if not matches:
        return None
    return max(matches, key=lambda item: (item.revision, item.recommendation_id))


def _latest_revision(draft: _MediationDraft, case_ref: str) -> int:
    revisions = [
        item.revision
        for item in draft.recommendations.values()
        if item.case_ref == case_ref
    ]
    return max(revisions) if revisions else -1


def _apply_recommendation(
    draft: _MediationDraft,
    signal: _MediationSignal,
    case: MediationCase,
    tick: int,
    policy: MediationPolicy,
) -> None:
    if signal.action_token is None:
        _notice(draft.notices, "invalid_token")
        return
    proposed = signal.proposed_actor_id
    if proposed is None:
        _notice(draft.notices, "unresolved_party")
        return
    if proposed == draft.owner_id and signal.actor_id == draft.owner_id:
        _notice(draft.notices, "self_endorsement")
        return
    revision = _latest_revision(draft, case.case_ref) + 1
    if revision >= policy.max_revisions:
        _notice(draft.notices, "cap_exceeded")
        return
    first = tick if signal.window_first_tick is None else signal.window_first_tick
    last = (
        first + policy.default_action_window
        if signal.window_last_tick is None
        else signal.window_last_tick
    )
    if last - first > policy.max_action_window:
        _notice(draft.notices, "invalid_token")
        return
    for item in tuple(draft.recommendations.values()):
        if (
            item.case_ref == case.case_ref
            and item.status is MediationRecommendationStatus.ACTIVE
        ):
            draft.recommendations[item.recommendation_id] = _with_recommendation_status(
                item, MediationRecommendationStatus.SUPERSEDED
            )
    recommendation = MediationRecommendation(
        recommendation_id=mediation_recommendation_id(
            draft.owner_id, case.case_ref, revision
        ),
        owner_id=draft.owner_id,
        case_ref=case.case_ref,
        revision=revision,
        proposed_actor_id=proposed,
        action_token=signal.action_token,
        first_tick=tick,
        last_tick=tick,
        window_first_tick=first,
        window_last_tick=last,
        originator_id=signal.actor_id,
        target_ids=signal.target_ids,
        item_token=signal.item_token,
        project_token=signal.project_token,
        terms=signal.terms,
        quantity=max(1, signal.quantity),
    )
    if len(draft.recommendations) >= policy.max_recommendations:
        _notice(draft.notices, "cap_exceeded")
        return
    draft.recommendations[recommendation.recommendation_id] = recommendation
    _LOG.debug(
        "mediation_recommendation_observed owner_id=%s case_ref=%s revision=%s act=%s",
        draft.owner_id.value,
        case.case_ref[:8],
        revision,
        signal.act.value if signal.act is not None else "unknown",
    )


def _with_recommendation_status(
    item: MediationRecommendation,
    status: MediationRecommendationStatus,
) -> MediationRecommendation:
    return MediationRecommendation(
        recommendation_id=item.recommendation_id,
        owner_id=item.owner_id,
        case_ref=item.case_ref,
        revision=item.revision,
        proposed_actor_id=item.proposed_actor_id,
        action_token=item.action_token,
        first_tick=item.first_tick,
        last_tick=item.last_tick,
        window_first_tick=item.window_first_tick,
        window_last_tick=item.window_last_tick,
        status=status,
        originator_id=item.originator_id,
        target_ids=item.target_ids,
        item_token=item.item_token,
        project_token=item.project_token,
        terms=item.terms,
        quantity=item.quantity,
        evidence=item.evidence,
        pruned_evidence_count=item.pruned_evidence_count,
        notices=item.notices,
    )


def _apply_response(
    draft: _MediationDraft,
    signal: _MediationSignal,
    case: MediationCase,
    tick: int,
    policy: MediationPolicy,
) -> None:
    assert signal.response_kind is not None
    actor = signal.actor_id
    if actor is None:
        _notice(draft.notices, "unresolved_party")
        return
    if actor == draft.owner_id:
        _notice(draft.notices, "self_endorsement")
        return
    revision = signal.recommendation_revision
    recommendation = None
    if signal.recommendation_ref is not None:
        recommendation = _existing_recommendation(draft, case.case_ref, revision)
        if (
            recommendation is None
            or recommendation.recommendation_id != signal.recommendation_ref
            or recommendation.revision != revision
        ):
            _notice(draft.notices, "unknown_recommendation")
            return
        if recommendation.window_last_tick < tick:
            _notice(draft.notices, "expired_reference")
            return
    ordinal = sum(
        1
        for item in draft.responses.values()
        if item.case_ref == case.case_ref and item.actor_id == actor
    )
    response_id = mediation_response_id(
        draft.owner_id, case.case_ref, actor, signal.response_kind, ordinal
    )
    direct = signal.independently_evidenced and signal.actor_id is not None
    try:
        response = MediationResponse(
            response_id=response_id,
            owner_id=draft.owner_id,
            actor_id=actor,
            case_ref=case.case_ref,
            kind=signal.response_kind,
            tick=tick,
            evidence_id=mediation_evidence_id(
                case.case_ref,
                len(case.evidence),
                signal.channel,
                signal.lineage_ref,
            ),
            recommendation_ref=(
                None if recommendation is None else recommendation.recommendation_id
            ),
            recommendation_revision=(
                None if recommendation is None else recommendation.revision
            ),
            undertaking_token=signal.undertaking_token,
            terms=signal.terms,
            accepted_terms=signal.accepted_terms,
            new_case_ref=signal.new_case_ref,
            withdraws_response_id=signal.withdraws_id,
            direct=direct,
        )
    except ValueError:
        _notice(draft.notices, "invalid_token")
        return
    if len(draft.responses) >= policy.max_responses:
        _notice(draft.notices, "cap_exceeded")
        draft.pruned_response_count += 1
        victim = min(
            draft.responses.values(), key=lambda item: (item.tick, item.response_id)
        )
        draft.responses.pop(victim.response_id, None)
    draft.responses[response.response_id] = response
    if (
        response.kind is MediationResponseKind.WITHDRAW
        and response.withdraws_response_id
    ):
        target = draft.responses.get(response.withdraws_response_id)
        if target is not None and target.actor_id == actor:
            draft.responses[target.response_id] = _deactivate_response(target)
    if response.kind is MediationResponseKind.COUNTERPROPOSE:
        _apply_recommendation(
            draft,
            signal,
            case,
            tick,
            policy,
        )
    if response.kind is MediationResponseKind.CLAIM_SETTLEMENT:
        _append_outcome(
            draft,
            case.case_ref,
            MediationOutcomeKind.CLAIMED,
            tick,
            claimed=True,
            actor_id=actor,
            evidence_id=response.evidence_id,
        )
    elif response.kind is MediationResponseKind.DEFER:
        if case.status is MediationCaseStatus.UNRESOLVED:
            draft.cases[case.case_ref] = _with_case_status(
                case, MediationCaseStatus.PARTIALLY_ADDRESSED
            )
    elif response.kind is MediationResponseKind.REFUSE:
        if case.status is MediationCaseStatus.UNRESOLVED:
            draft.cases[case.case_ref] = _with_case_status(
                case, MediationCaseStatus.DECLINED
            )


def _deactivate_response(item: MediationResponse) -> MediationResponse:
    return MediationResponse(
        response_id=item.response_id,
        owner_id=item.owner_id,
        actor_id=item.actor_id,
        case_ref=item.case_ref,
        kind=item.kind,
        tick=item.tick,
        evidence_id=item.evidence_id,
        recommendation_ref=item.recommendation_ref,
        recommendation_revision=item.recommendation_revision,
        undertaking_token=item.undertaking_token,
        terms=item.terms,
        accepted_terms=item.accepted_terms,
        new_case_ref=item.new_case_ref,
        withdraws_response_id=item.withdraws_response_id,
        direct=item.direct,
        active=False,
    )


def _with_case_status(
    case: MediationCase, status: MediationCaseStatus
) -> MediationCase:
    return MediationCase(
        case_id=case.case_id,
        owner_id=case.owner_id,
        case_ref=case.case_ref,
        subject_token=case.subject_token,
        context_key=case.context_key,
        status=status,
        first_tick=case.first_tick,
        last_tick=case.last_tick,
        window_first_tick=case.window_first_tick,
        window_last_tick=case.window_last_tick,
        origin_id=case.origin_id,
        party_ids=case.party_ids,
        uncertainty=case.uncertainty,
        evidence=case.evidence,
        pruned_evidence_count=case.pruned_evidence_count,
        notices=case.notices,
    )


def _append_outcome(
    draft: _MediationDraft,
    case_ref: str,
    kind: MediationOutcomeKind,
    tick: int,
    *,
    claimed: bool,
    actor_id: AgentId | None = None,
    evidence_id: str | None = None,
    notice: str | None = None,
) -> None:
    existing = next(
        (
            item
            for item in draft.outcomes.values()
            if item.case_ref == case_ref
            and item.kind is kind
            and item.actor_id == actor_id
            and item.claimed == claimed
        ),
        None,
    )
    if existing is not None:
        draft.outcomes[existing.outcome_id] = MediationOutcome(
            outcome_id=existing.outcome_id,
            owner_id=existing.owner_id,
            case_ref=existing.case_ref,
            kind=existing.kind,
            claimed=existing.claimed,
            first_tick=existing.first_tick,
            last_tick=max(existing.last_tick, tick),
            actor_id=existing.actor_id,
            evidence_id=existing.evidence_id,
            notice=existing.notice,
        )
        return
    ordinal = len(draft.outcomes)
    outcome_id = _sha256_hex(
        f"{draft.owner_id.value}|mediation-outcome|{case_ref}|{kind.value}|"
        f"{actor_id.value if actor_id else '-'}|{ordinal}"
    )
    draft.outcomes[outcome_id] = MediationOutcome(
        outcome_id=outcome_id,
        owner_id=draft.owner_id,
        case_ref=case_ref,
        kind=kind,
        claimed=claimed,
        first_tick=tick,
        last_tick=tick,
        actor_id=actor_id,
        evidence_id=evidence_id,
        notice=notice,
    )


def _apply_role_expression(
    draft: _MediationDraft,
    signal: _MediationSignal,
    tick: int,
    policy: MediationPolicy,
) -> None:
    assert signal.role_kind is not None
    actor = signal.actor_id
    if actor is None:
        _notice(draft.notices, "unresolved_party")
        return
    ordinal = sum(
        1
        for item in draft.role_expressions.values()
        if item.actor_id == actor and item.kind is signal.role_kind
    )
    expression_id = mediation_role_expression_id(
        draft.owner_id, actor, signal.role_kind, signal.context_key, ordinal
    )
    if len(draft.role_expressions) >= policy.max_role_expressions:
        _notice(draft.notices, "cap_exceeded")
        return
    try:
        expression = MediationRoleExpression(
            expression_id=expression_id,
            owner_id=draft.owner_id,
            actor_id=actor,
            kind=signal.role_kind,
            context_key=signal.context_key,
            first_tick=tick,
            last_tick=tick,
            evidence_id=mediation_evidence_id(
                signal.case_ref,
                0,
                signal.channel,
                signal.lineage_ref,
            ),
            case_ref=signal.case_ref,
            function_token=signal.subject_token,
            withdraws_expression_id=signal.withdraws_id,
        )
    except ValueError:
        _notice(draft.notices, "invalid_token")
        return
    draft.role_expressions[expression.expression_id] = expression
    if (
        expression.kind is MediationRoleExpressionKind.WITHDRAW_ROLE_ENDORSEMENT
        and expression.withdraws_expression_id is not None
    ):
        target = draft.role_expressions.get(expression.withdraws_expression_id)
        if target is not None and target.actor_id == actor:
            draft.role_expressions[target.expression_id] = _deactivate_role_expression(
                target
            )


def _deactivate_role_expression(
    item: MediationRoleExpression,
) -> MediationRoleExpression:
    return MediationRoleExpression(
        expression_id=item.expression_id,
        owner_id=item.owner_id,
        actor_id=item.actor_id,
        kind=item.kind,
        context_key=item.context_key,
        first_tick=item.first_tick,
        last_tick=item.last_tick,
        evidence_id=item.evidence_id,
        case_ref=item.case_ref,
        function_token=item.function_token,
        withdraws_expression_id=item.withdraws_expression_id,
        active=False,
    )


def _apply_signal(
    draft: _MediationDraft,
    signal: _MediationSignal,
    tick: int,
    policy: MediationPolicy,
) -> None:
    if signal.case_ref in draft.retired_refs:
        _notice(draft.notices, "retired_reference")
        return
    if signal.root_ref in draft.seen_roots:
        _notice(draft.notices, "duplicate_root")
        return
    case = _ensure_case(draft, signal, tick, policy)
    draft.seen_roots.add(signal.root_ref)
    if signal.kind == "act":
        if signal.act in {
            MediationAct.PROPOSE_COMPROMISE,
            MediationAct.RECOMMEND_RESTITUTION,
        }:
            _apply_recommendation(draft, signal, case, tick, policy)
        elif signal.act in {MediationAct.HEAR_DISPUTE, MediationAct.REQUEST_ACCOUNTS}:
            _apply_heard_claim(draft, signal, case, tick)
        elif signal.act is MediationAct.VOUCH:
            if signal.actor_id is None:
                _notice(draft.notices, "unresolved_party")
            elif not signal.target_ids:
                _notice(draft.notices, "unresolved_party")
        else:
            if not case.third_party_actionable:
                _notice(draft.notices, "unresolved_party")
    elif signal.kind == "response":
        _apply_response(draft, signal, case, tick, policy)
    else:
        _apply_role_expression(draft, signal, tick, policy)


def _apply_heard_claim(
    draft: _MediationDraft,
    signal: _MediationSignal,
    case: MediationCase,
    tick: int,
) -> None:
    actor = signal.actor_id
    if actor is None:
        _notice(draft.notices, "unresolved_party")
        return
    account_id = _sha256_hex(
        f"{draft.owner_id.value}|mediation-account|{case.case_ref}|"
        f"{actor.value}|{signal.claim_token}|{signal.lineage_ref}"
    )
    if account_id in draft.accounts:
        return
    if len(draft.accounts) >= _MAX_ACCOUNTS:
        _notice(draft.notices, "cap_exceeded")
        return
    account = MediationAccount(
        account_id=account_id,
        owner_id=draft.owner_id,
        actor_id=actor,
        case_ref=case.case_ref,
        subject_token=signal.subject_token,
        claim_token=signal.claim_token,
        direct=signal.independently_evidenced,
        channel=signal.channel,
        root_ref=signal.root_ref,
        first_tick=tick,
        last_tick=tick,
        evidence_id=mediation_evidence_id(
            case.case_ref, len(case.evidence), signal.channel, signal.lineage_ref
        ),
        reported_by_id=None if signal.independently_evidenced else signal.actor_id,
        uncertainty=_quantize(1.0 - signal.confidence),
    )
    draft.accounts[account.account_id] = account
    parties = tuple(dict.fromkeys((*case.party_ids, actor)))
    if len(parties) <= _MAX_PARTIES:
        draft.cases[case.case_ref] = _replace_case_parties(case, parties)


def _expire(draft: _MediationDraft, tick: int, policy: MediationPolicy) -> None:
    for case_ref, case in tuple(draft.cases.items()):
        if case.window_last_tick < tick and case.status in {
            MediationCaseStatus.UNRESOLVED,
            MediationCaseStatus.PARTIALLY_ADDRESSED,
            MediationCaseStatus.REOPENED,
        }:
            draft.cases[case_ref] = _with_case_status(case, MediationCaseStatus.EXPIRED)
    for item in tuple(draft.recommendations.values()):
        if (
            item.window_last_tick < tick
            and item.status is MediationRecommendationStatus.ACTIVE
        ):
            draft.recommendations[item.recommendation_id] = _with_recommendation_status(
                item, MediationRecommendationStatus.EXPIRED
            )
    for ref in tuple(draft.retired_refs):
        _ = ref
    _ = policy


def _freeze(
    draft: _MediationDraft, tick: int, policy: MediationPolicy
) -> MediationLedger:
    _expire(draft, tick, policy)
    return MediationLedger(
        owner_id=draft.owner_id,
        cases=tuple(sorted(draft.cases.values(), key=lambda item: item.case_id)),
        accounts=tuple(
            sorted(draft.accounts.values(), key=lambda item: item.account_id)
        ),
        recommendations=tuple(
            sorted(
                draft.recommendations.values(),
                key=lambda item: (item.case_ref, item.revision),
            )
        ),
        responses=tuple(
            sorted(draft.responses.values(), key=lambda item: item.response_id)
        ),
        role_expressions=tuple(
            sorted(
                draft.role_expressions.values(),
                key=lambda item: item.expression_id,
            )
        ),
        attempts=tuple(
            sorted(draft.attempts.values(), key=lambda item: item.attempt_id)
        ),
        outcomes=tuple(
            sorted(draft.outcomes.values(), key=lambda item: item.outcome_id)
        ),
        notices=tuple(draft.notices),
        policy_version=MEDIATION_POLICY_VERSION,
        retired_case_refs=tuple(draft.retired_refs),
        first_observed_tick=draft.first_observed_tick,
        last_observed_tick=draft.last_observed_tick,
        observation_count=draft.observation_count,
        pruned_case_count=draft.pruned_case_count,
        pruned_evidence_count=draft.pruned_evidence_count,
        pruned_recommendation_count=draft.pruned_recommendation_count,
        pruned_response_count=draft.pruned_response_count,
    )


def _normalize_trust(speaker_trust: dict[str, float] | None) -> dict[str, float]:
    if speaker_trust is None:
        return {}
    if not isinstance(speaker_trust, dict):
        raise TypeError("speaker_trust must be a mapping")
    normalized: dict[str, float] = {}
    for key, value in speaker_trust.items():
        if not isinstance(key, str) or not key:
            raise ValueError("speaker_trust key invalid")
        normalized[key] = _require_strength(f"speaker_trust.{key}", value)
    return normalized


def apply_mediation_update(
    observation: object,
    identity: object,
    previous: object = None,
    retrieved_memory_context: object = None,
    speaker_trust: dict[str, float] | None = None,
    policy: MediationPolicy | None = None,
) -> MediationLedger:
    """Apply one tick of owner-scoped mediation evidence."""
    for value in (
        observation,
        identity,
        previous,
        retrieved_memory_context,
        speaker_trust,
        policy,
    ):
        _reject_forbidden(value)
    if type(observation) is not Observation:
        raise TypeError("observation must be Observation")
    if type(identity) is not OwnerSafeSocialIdentity:
        raise TypeError("identity must be OwnerSafeSocialIdentity")
    if previous is not None and type(previous) is not MediationLedger:
        raise TypeError("previous must be MediationLedger or None")
    if previous is not None and previous.owner_id != identity.owner_id:
        _LOG.warning("mediation_carry_rejected reason=%s", "owner_mismatch")
        raise ValueError("previous owner_id mismatch")
    active_policy = default_mediation_policy() if policy is None else policy
    if type(active_policy) is not MediationPolicy:
        raise TypeError("policy must be MediationPolicy or None")
    owner_id = identity.owner_id
    base = previous or empty_mediation_ledger(owner_id)
    draft = _draft_from_ledger(base)
    tick = observation.tick
    if draft.last_observed_tick != tick:
        draft.first_observed_tick = (
            tick if draft.first_observed_tick is None else draft.first_observed_tick
        )
        draft.last_observed_tick = tick
        draft.observation_count += 1
    context_key = mediation_context_key(observation)
    trust = _normalize_trust(speaker_trust)
    signals = _signals_from_observation(observation, identity, context_key)
    signals.extend(
        _signals_from_episodes(retrieved_memory_context, identity, context_key)
    )
    for signal in signals:
        confidence = signal.confidence
        if signal.actor_id is not None:
            confidence *= trust.get(signal.actor_id.value, 1.0)
        adjusted = _MediationSignal(
            kind=signal.kind,
            act=signal.act,
            response_kind=signal.response_kind,
            role_kind=signal.role_kind,
            case_ref=signal.case_ref,
            revision=signal.revision,
            lineage_ref=signal.lineage_ref,
            root_ref=signal.root_ref,
            channel=signal.channel,
            context_key=signal.context_key,
            actor_id=signal.actor_id,
            subject_token=signal.subject_token,
            claim_token=signal.claim_token,
            occurrence_ref=signal.occurrence_ref,
            action_token=signal.action_token,
            proposed_actor_id=signal.proposed_actor_id,
            target_ids=signal.target_ids,
            item_token=signal.item_token,
            project_token=signal.project_token,
            terms=signal.terms,
            accepted_terms=signal.accepted_terms,
            undertaking_token=signal.undertaking_token,
            recommendation_ref=signal.recommendation_ref,
            recommendation_revision=signal.recommendation_revision,
            new_case_ref=signal.new_case_ref,
            withdraws_id=signal.withdraws_id,
            window_first_tick=signal.window_first_tick,
            window_last_tick=signal.window_last_tick,
            quantity=signal.quantity,
            confidence=confidence,
            independently_evidenced=signal.independently_evidenced,
        )
        _apply_signal(draft, adjusted, tick, active_policy)
    ledger = _freeze(draft, tick, active_policy)
    _LOG.info(
        "mediation_ledger_updated owner_id=%s case_count=%s "
        "recommendation_count=%s response_count=%s",
        owner_id.value,
        len(ledger.cases),
        len(ledger.recommendations),
        len(ledger.responses),
    )
    return ledger


# ---------------------------------------------------------------------------
# Recipient-relative authority appraisal
# ---------------------------------------------------------------------------


def _clamp_unit(value: float) -> float:
    return 0.0 if value <= 0.0 else (1.0 if value >= 1.0 else _quantize(value))


def _relationship_component(
    owner_id: AgentId,
    mediator_id: AgentId,
    relationships: Sequence[object] | None,
) -> MediationAuthorityComponent:
    if relationships is None:
        return _unavailable(MediationAuthorityChannel.RELATIONSHIP)
    from social.relationships import (
        DirectedRelationshipProfile,
        RelationshipDimension,
    )

    for profile in relationships:
        if type(profile) is not DirectedRelationshipProfile:
            raise TypeError("relationships entries must be DirectedRelationshipProfile")
        if profile.source_id != owner_id:
            raise ValueError("relationships source_id mismatch")
        if profile.target_id != mediator_id:
            continue
        dimensions = profile.dimension_map()
        trust = dimensions.get(RelationshipDimension.TRUST)
        familiarity = dimensions.get(RelationshipDimension.FAMILIARITY)
        affection = dimensions.get(RelationshipDimension.AFFECTION)
        selected = [
            item for item in (trust, familiarity, affection) if item is not None
        ]
        if not selected:
            continue
        strength = _clamp_unit(
            sum((item.value + 1.0) / 2.0 for item in selected) / len(selected)
        )
        confidence = sum(item.confidence.confidence for item in selected) / len(
            selected
        )
        provenance = tuple(item.dimension.value for item in selected)
        return MediationAuthorityComponent(
            channel=MediationAuthorityChannel.RELATIONSHIP,
            available=True,
            strength=strength,
            uncertainty=_quantize(1.0 - confidence),
            provenance=provenance,
            dissenting=any(item.value < 0.0 for item in selected),
        )
    return _unavailable(MediationAuthorityChannel.RELATIONSHIP)


def _reputation_component(
    owner_id: AgentId,
    mediator_id: AgentId,
    reputation: object | None,
) -> MediationAuthorityComponent:
    if reputation is None:
        return _unavailable(MediationAuthorityChannel.REPUTATION)
    from agents.cognition.reputation import ReputationLedger

    if type(reputation) is not ReputationLedger:
        raise TypeError("reputation must be ReputationLedger or None")
    if reputation.owner_id != owner_id:
        raise ValueError("reputation owner_id mismatch")
    profile = next(
        (item for item in reputation.profiles if item.target_id == mediator_id), None
    )
    if profile is None:
        return _unavailable(MediationAuthorityChannel.REPUTATION)
    reliability = profile.reliability
    harm = profile.harm
    generosity = profile.generosity
    competence = profile.competence
    normalized = (
        (reliability.value + 1.0) / 2.0,
        (competence.value + 1.0) / 2.0,
        (generosity.value + 1.0) / 2.0,
        (1.0 - (harm.value + 1.0) / 2.0),
    )
    support = sum(
        item.support_mass for item in (reliability, harm, generosity, competence)
    )
    contradiction = sum(
        item.contradiction_mass for item in (reliability, harm, generosity, competence)
    )
    total = support + contradiction
    uncertainty = 1.0 if total == 0.0 else contradiction / total
    provenance = ("competence", "generosity", "harm", "reliability")
    return MediationAuthorityComponent(
        channel=MediationAuthorityChannel.REPUTATION,
        available=True,
        strength=_clamp_unit(sum(normalized) / len(normalized)),
        uncertainty=_clamp_unit(uncertainty),
        provenance=provenance,
        dissenting=harm.value > 0.0,
    )


def _office_component(
    owner_id: AgentId,
    mediator_id: AgentId,
    context_key: str,
    office_concepts: object | None,
) -> MediationAuthorityComponent:
    if office_concepts is None:
        return _unavailable(MediationAuthorityChannel.ROLE)
    from agents.cognition.offices import (
        OfficeConceptLedger,
        OfficeConceptStatus,
        OfficeFunction,
    )

    if type(office_concepts) is not OfficeConceptLedger:
        raise TypeError("office_concepts must be OfficeConceptLedger or None")
    if office_concepts.owner_id != owner_id:
        raise ValueError("office_concepts owner_id mismatch")
    best: tuple[float, frozenset[str], bool] | None = None
    for concept in office_concepts.concepts:
        if concept.function is not OfficeFunction.CONFLICT_MEDIATION:
            continue
        if concept.context_key != context_key:
            continue
        if concept.status in {
            OfficeConceptStatus.ABANDONED,
            OfficeConceptStatus.VACANT,
        }:
            continue
        claims = [
            claim for claim in concept.occupants if claim.occupant_id == mediator_id
        ]
        supporters = [
            item
            for item in concept.supporters
            if item.target_occupant_id == mediator_id
            and (item.supporter_id is None or item.supporter_id != owner_id)
        ]
        if not claims and not supporters:
            continue
        claim_strength = max(
            (
                _clamp_unit(claim.support_strength * (1.0 - claim.opposition_strength))
                for claim in claims
            ),
            default=0.0,
        )
        support_strength = max((item.strength for item in supporters), default=0.0)
        strength = _clamp_unit(max(claim_strength, support_strength))
        provenance = {"conflict_mediation"}
        if claims:
            provenance.add("occupant_evidence")
        if supporters:
            provenance.add("endorsement_evidence")
        if concept.status is OfficeConceptStatus.DISPUTED:
            provenance.add("contested_recognition")
        candidate = (
            strength,
            frozenset(provenance),
            concept.status is OfficeConceptStatus.DISPUTED,
        )
        if best is None or candidate[0] > best[0]:
            best = candidate
    if best is None:
        return _unavailable(MediationAuthorityChannel.ROLE)
    return MediationAuthorityComponent(
        channel=MediationAuthorityChannel.ROLE,
        available=True,
        strength=best[0],
        uncertainty=_quantize(0.5 if best[2] else 0.2),
        provenance=tuple(sorted(best[1])),
        dissenting=best[2],
    )


_PROCEDURE_PATTERNS: Final[frozenset[str]] = frozenset(
    {
        "reciprocal_exchange",
        "return_transfer",
        "shared_upkeep",
    }
)


def _norm_component(
    owner_id: AgentId,
    mediator_id: AgentId,
    social_norms: object | None,
) -> MediationAuthorityComponent:
    if social_norms is None:
        return _unavailable(MediationAuthorityChannel.NORM)
    from agents.cognition.social_norms import NormLedger, NormStatus

    if type(social_norms) is not NormLedger:
        raise TypeError("social_norms must be NormLedger or None")
    if social_norms.owner_id != owner_id:
        raise ValueError("social_norms owner_id mismatch")
    matches = []
    for belief in social_norms.beliefs:
        if belief.status is not NormStatus.ACTIVE:
            continue
        if belief.pattern.value not in _PROCEDURE_PATTERNS:
            continue
        counterpart = belief.context.counterpart_id
        if counterpart is not None and counterpart != mediator_id:
            continue
        matches.append(belief)
    if not matches:
        return _unavailable(MediationAuthorityChannel.NORM)
    strength = max(belief.confidence for belief in matches)
    provenance = tuple(sorted({belief.pattern.value for belief in matches}))
    return MediationAuthorityComponent(
        channel=MediationAuthorityChannel.NORM,
        available=True,
        strength=_clamp_unit(strength),
        uncertainty=_quantize(1.0 - strength),
        provenance=provenance,
        dissenting=len(matches) > 1,
    )


def _institution_component(
    owner_id: AgentId,
    mediator_id: AgentId,
    context_key: str,
    institution_concepts: object | None,
) -> MediationAuthorityComponent:
    if institution_concepts is None:
        return _unavailable(MediationAuthorityChannel.INSTITUTION)
    from agents.cognition.institution_concepts import (
        InstitutionConceptLedger,
        InstitutionConceptStatus,
    )

    if type(institution_concepts) is not InstitutionConceptLedger:
        raise TypeError("institution_concepts must be InstitutionConceptLedger or None")
    if institution_concepts.owner_id != owner_id:
        raise ValueError("institution_concepts owner_id mismatch")
    matches = []
    for concept in institution_concepts.concepts:
        if concept.status not in {
            InstitutionConceptStatus.RECOGNIZED,
            InstitutionConceptStatus.CANDIDATE,
        }:
            continue
        linked = context_key in concept.anchor_digests or any(
            item.actor_id == mediator_id for item in concept.evidence
        )
        if not linked:
            continue
        matches.append(concept)
    if not matches:
        return _unavailable(MediationAuthorityChannel.INSTITUTION)
    concept = max(
        matches,
        key=lambda item: (item.legitimacy_belief, item.concept_id),
    )
    strength = _clamp_unit(
        0.5 * concept.legitimacy_belief + 0.5 * concept.social_expectation
    )
    provenance = ("legitimacy_belief", "social_expectation")
    return MediationAuthorityComponent(
        channel=MediationAuthorityChannel.INSTITUTION,
        available=True,
        strength=strength,
        uncertainty=_quantize(1.0 - strength),
        provenance=provenance,
        dissenting=concept.status is InstitutionConceptStatus.CANDIDATE,
    )


def _unavailable(channel: MediationAuthorityChannel) -> MediationAuthorityComponent:
    return MediationAuthorityComponent(
        channel=channel,
        available=False,
        strength=0.0,
        uncertainty=1.0,
    )


def appraise_mediation_authority(
    owner_id: AgentId,
    mediator_id: AgentId,
    context_key: str,
    *,
    relationships: Sequence[object] | None = None,
    reputation: object | None = None,
    social_norms: object | None = None,
    office_concepts: object | None = None,
    institution_concepts: object | None = None,
) -> MediationAuthorityAppraisal:
    """Project available owner-relative sources. Missing sources stay absent.

    No component grants binding authority, and an available component never
    forces the owner to accept a recommendation.
    """
    _require_agent("owner_id", owner_id)
    _require_agent("mediator_id", mediator_id)
    if owner_id == mediator_id:
        raise _fail("mediator_id", "owner_is_mediator")
    context = _require_digest("context_key", context_key)
    for value in (
        relationships,
        reputation,
        social_norms,
        office_concepts,
        institution_concepts,
    ):
        _reject_forbidden(value)
    components = (
        _relationship_component(owner_id, mediator_id, relationships),
        _reputation_component(owner_id, mediator_id, reputation),
        _office_component(owner_id, mediator_id, context, office_concepts),
        _norm_component(owner_id, mediator_id, social_norms),
        _institution_component(owner_id, mediator_id, context, institution_concepts),
    )
    ordered = tuple(
        component
        for component in (
            components[0],
            components[1],
            components[2],
            components[3],
            components[4],
        )
        if True
    )
    appraisal = MediationAuthorityAppraisal(
        owner_id=owner_id,
        mediator_id=mediator_id,
        context_key=context,
        components=ordered,
    )
    _LOG.debug(
        "mediation_authority_appraised owner_id=%s mediator_id=%s "
        "available_count=%s context_key=%s",
        owner_id.value,
        mediator_id.value,
        len(appraisal.available_channels),
        context[:8],
    )
    return appraisal


# ---------------------------------------------------------------------------
# Owner-visible opportunity generation
# ---------------------------------------------------------------------------

_OBSERVED_CONTENTION_SUBJECT: Final[str] = "observed_contention"
_CONTENTION_OCCURRENCE_KINDS: Final[frozenset[str]] = frozenset({"attack"})


def _contentious_party_ids(
    observation: Observation, identity: OwnerSafeSocialIdentity
) -> tuple[AgentId, ...]:
    """Return distinct others only when the owner observed actual contention.

    Mere co-presence is not a dispute. Evidence is either a visible contention
    occurrence or two speakers making incompatible claims about one subject.
    """
    parties: list[AgentId] = []

    def add(entity_id: EntityId | None) -> None:
        if entity_id is None:
            return
        agent = _resolve_entity(identity, entity_id)
        if agent is None or agent == identity.owner_id:
            return
        if agent not in parties:
            parties.append(agent)

    for occurrence in observation.occurrences:
        if occurrence.kind.strip().lower() not in _CONTENTION_OCCURRENCE_KINDS:
            continue
        add(occurrence.actor_id)
        add(occurrence.other_entity_id)

    claims: dict[str, dict[str, str]] = {}
    for communication in observation.communications:
        speaker = _resolve_entity(identity, communication.speaker_id)
        if speaker is None or speaker == identity.owner_id:
            continue
        for relation in communication.utterance.content.relations:
            subject = relation.subject.strip().lower()
            if not subject:
                continue
            claim = f"{relation.predicate.strip().lower()}:{relation.object.strip()}"
            claims.setdefault(subject, {})[claim] = speaker.value
    for by_claim in claims.values():
        if len(set(by_claim.values())) >= 2 and len(by_claim) >= 2:
            for agent_value in sorted(set(by_claim.values())):
                add(_entity_from_value(identity, agent_value))

    return tuple(parties[:_MAX_PARTIES])


def _entity_from_value(
    identity: OwnerSafeSocialIdentity, agent_value: str
) -> EntityId | None:
    if identity.owner_id.value == agent_value:
        return identity.owner_entity_id
    for binding in identity.counterparts:
        if binding.agent_id.value == agent_value:
            return binding.entity_id
    return None


def generate_mediation_opportunities(
    ledger: object,
    observation: object,
    identity: object,
    *,
    policy: MediationPolicy | None = None,
) -> MediationLedger:
    """Create a tentative case from owner-visible contention evidence."""
    if type(ledger) is not MediationLedger:
        raise TypeError("ledger must be MediationLedger")
    if type(observation) is not Observation:
        raise TypeError("observation must be Observation")
    if type(identity) is not OwnerSafeSocialIdentity:
        raise TypeError("identity must be OwnerSafeSocialIdentity")
    if identity.owner_id != ledger.owner_id:
        raise ValueError("identity owner_id mismatch")
    active_policy = default_mediation_policy() if policy is None else policy
    if type(active_policy) is not MediationPolicy:
        raise TypeError("policy must be MediationPolicy or None")
    tick = observation.tick
    if any(
        case.window_last_tick >= tick
        and case.status
        in {
            MediationCaseStatus.UNRESOLVED,
            MediationCaseStatus.PARTIALLY_ADDRESSED,
            MediationCaseStatus.REOPENED,
            MediationCaseStatus.DISPUTED,
        }
        for case in ledger.cases
    ):
        return ledger
    if len(ledger.cases) >= active_policy.max_cases:
        return ledger
    parties = _contentious_party_ids(observation, identity)
    if len(parties) < 2:
        return ledger
    context_key = mediation_context_key(observation)
    ref = mediation_case_ref(
        ledger.owner_id,
        origin_id=parties[0],
        subject_token=_OBSERVED_CONTENTION_SUBJECT,
        context_key=context_key,
        inception_tick=tick,
        inception_lineage=f"opportunity-{tick}-{len(parties)}",
    )
    if ref in ledger.retired_case_refs:
        return ledger
    evidence = MediationEvidence(
        evidence_id=mediation_evidence_id(
            ref, 0, MediationEvidenceChannel.OBSERVED, f"opportunity-{tick}"
        ),
        ordinal=0,
        channel=MediationEvidenceChannel.OBSERVED,
        lineage_ref=f"opportunity-{tick}",
        root_ref=f"opportunity|{context_key}|{tick}",
        tick=tick,
        actor_id=ledger.owner_id,
    )
    case = MediationCase(
        case_id=mediation_case_id(ledger.owner_id, ref),
        owner_id=ledger.owner_id,
        case_ref=ref,
        subject_token=_OBSERVED_CONTENTION_SUBJECT,
        context_key=context_key,
        status=MediationCaseStatus.UNRESOLVED,
        first_tick=tick,
        last_tick=tick,
        window_first_tick=tick,
        window_last_tick=tick + active_policy.default_action_window,
        origin_id=parties[0],
        party_ids=parties,
        uncertainty=0.5,
        evidence=(evidence,),
    )
    _LOG.debug(
        "mediation_opportunity_generated owner_id=%s party_count=%s tick=%s",
        ledger.owner_id.value,
        len(parties),
        tick,
    )
    return MediationLedger(
        owner_id=ledger.owner_id,
        cases=(*ledger.cases, case),
        accounts=ledger.accounts,
        recommendations=ledger.recommendations,
        responses=ledger.responses,
        role_expressions=ledger.role_expressions,
        attempts=ledger.attempts,
        outcomes=ledger.outcomes,
        notices=ledger.notices,
        policy_version=ledger.policy_version,
        retired_case_refs=ledger.retired_case_refs,
        first_observed_tick=ledger.first_observed_tick,
        last_observed_tick=ledger.last_observed_tick,
        observation_count=ledger.observation_count,
        pruned_case_count=ledger.pruned_case_count,
        pruned_evidence_count=ledger.pruned_evidence_count,
        pruned_recommendation_count=ledger.pruned_recommendation_count,
        pruned_response_count=ledger.pruned_response_count,
    )


# ---------------------------------------------------------------------------
# Neutral mediation-function evidence for the existing office update seam
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class MediationFunctionEvidence:
    """Neutral delivered function evidence. It never asserts success.

    The shape intentionally matches the optional local-ledger rows accepted by
    ``apply_office_concept_update``. ``status='shared'`` means the owner saw or
    received a mediation-function expression, not that facilitation succeeded.
    """

    concept_id: str
    function: str
    context_key: str
    status: str = "shared"
    recognized: bool = False

    def __post_init__(self) -> None:
        _require_hex_id("concept_id", self.concept_id)
        object.__setattr__(self, "function", _require_token("function", self.function))
        object.__setattr__(
            self, "context_key", _require_digest("context_key", self.context_key)
        )
        if self.status not in {"shared", "observed"}:
            raise _fail("status", "invalid_status")
        if self.recognized is not False:
            raise _fail("recognized", "not_authoritative")


_FUNCTION_PREDICATES: Final[frozenset[str]] = frozenset(
    {
        "mediation_mediate",
        "mediation_invite",
        "mediation_endorse",
    }
)


def mediation_function_evidence(
    observation: object,
    identity: object,
) -> tuple[MediationFunctionEvidence, ...]:
    """Extract deduplicated neutral function evidence from delivered speech.

    Self-authored plans, emitted-but-unobserved speech, and claimed success are
    never inputs. Only the owner's delivered observation is read.
    """
    if type(observation) is not Observation:
        raise TypeError("observation must be Observation")
    if type(identity) is not OwnerSafeSocialIdentity:
        raise TypeError("identity must be OwnerSafeSocialIdentity")
    context_key = mediation_context_key(observation)
    rows: list[MediationFunctionEvidence] = []
    seen: set[str] = set()
    for communication in observation.communications:
        declared = communication.utterance.declared
        for relation in communication.utterance.content.relations:
            if relation.predicate not in _FUNCTION_PREDICATES:
                continue
            parts = relation.object.split("|")
            if len(parts) < 2:
                continue
            case_ref = _parse_optional_id(parts[0])
            if case_ref is None:
                continue
            if relation.predicate in {"mediation_invite", "mediation_endorse"}:
                context = parts[3].strip() if len(parts) > 3 else context_key
                if len(context) != _DIGEST_LEN or any(
                    char not in _HEX for char in context
                ):
                    context = context_key
            else:
                context = context_key
            root = (
                f"communication|{declared.root_communication_id.value}|"
                f"{relation.predicate}"
            )
            if root in seen:
                continue
            seen.add(root)
            rows.append(
                MediationFunctionEvidence(
                    concept_id=_sha256_hex(
                        f"{identity.owner_id.value}|mediation-function|"
                        f"{relation.predicate}|{context}|{root}"
                    ),
                    function="conflict_mediation",
                    context_key=context,
                )
            )
    return tuple(rows)
