"""Closed owner-scoped formal social rule vocabulary.

A formal rule is one owner's belief about a socially recognized constraint. It
is never a world law, admission rule, permission, prohibition, court order,
verdict, or enforcement engine. This module defines only the frozen vocabulary,
stage progression, identity grammar, policy bounds, and error codes that later
formal-rule code consumes.

Physical impossibility stays with ``WorldEngine`` action rules. A formal rule may
label an action prohibited, obligated, or permitted for its owner, but it can
never make a physically possible action impossible or a physically impossible
action possible. No rule engine, sanction engine, policy engine, global registry,
command, or permission is created here.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, fields, is_dataclass, replace
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Final, NoReturn

from agents.models import AgentId

if TYPE_CHECKING:
    from agents.cognition.formal_rule_communication import FormalRuleClaim

_LOG: Final[logging.Logger] = logging.getLogger("agents.cognition.formal_rules")

FORMAL_RULE_POLICY_VERSION: Final[str] = "formal-rules.v1"
FORMAL_RULE_ID_HEX_LEN: Final[int] = 16

FORMAL_RULE_SYSTEM_ID_PREFIX: Final[str] = "frs-"
FORMAL_RULE_ID_PREFIX: Final[str] = "frl-"
FORMAL_RULE_VERSION_ID_PREFIX: Final[str] = "frv-"
FORMAL_RULE_EVIDENCE_ID_PREFIX: Final[str] = "fre-"
FORMAL_RULE_POSITION_ID_PREFIX: Final[str] = "frp-"
FORMAL_RULE_RESPONSE_ID_PREFIX: Final[str] = "frr-"
FORMAL_RULE_EXCEPTION_ID_PREFIX: Final[str] = "frx-"

FORMAL_RULE_SYSTEM_NAMESPACE: Final[str] = "formal-rule-system"
FORMAL_RULE_NAMESPACE: Final[str] = "formal-rule"
FORMAL_RULE_VERSION_NAMESPACE: Final[str] = "formal-rule-version"
FORMAL_RULE_EVIDENCE_NAMESPACE: Final[str] = "formal-rule-evidence"
FORMAL_RULE_POSITION_NAMESPACE: Final[str] = "formal-rule-position"
FORMAL_RULE_RESPONSE_NAMESPACE: Final[str] = "formal-rule-response"
FORMAL_RULE_EXCEPTION_NAMESPACE: Final[str] = "formal-rule-exception"
FORMAL_RULE_SCOPE_NAMESPACE: Final[str] = "formal-rule-scope"

_SEPARATOR: Final[str] = "\x1f"
_QUANTUM: Final[Decimal] = Decimal("0.000001")
_HEX64_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{64}$")
_TOKEN_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[a-z][a-z0-9_]*$")
_TOKEN_MAX_LEN: Final[int] = 64
_REFERENCE_MAX_LEN: Final[int] = 128

_SYSTEM_ID_PATTERN: Final[re.Pattern[str]] = re.compile(
    rf"^{FORMAL_RULE_SYSTEM_ID_PREFIX}[0-9a-f]{{{FORMAL_RULE_ID_HEX_LEN}}}$"
)
_RULE_ID_PATTERN: Final[re.Pattern[str]] = re.compile(
    rf"^{FORMAL_RULE_ID_PREFIX}[0-9a-f]{{{FORMAL_RULE_ID_HEX_LEN}}}$"
)
_VERSION_ID_PATTERN: Final[re.Pattern[str]] = re.compile(
    rf"^{FORMAL_RULE_VERSION_ID_PREFIX}[0-9a-f]{{{FORMAL_RULE_ID_HEX_LEN}}}$"
)
_EVIDENCE_ID_PATTERN: Final[re.Pattern[str]] = re.compile(
    rf"^{FORMAL_RULE_EVIDENCE_ID_PREFIX}[0-9a-f]{{{FORMAL_RULE_ID_HEX_LEN}}}$"
)
_POSITION_ID_PATTERN: Final[re.Pattern[str]] = re.compile(
    rf"^{FORMAL_RULE_POSITION_ID_PREFIX}[0-9a-f]{{{FORMAL_RULE_ID_HEX_LEN}}}$"
)
_RESPONSE_ID_PATTERN: Final[re.Pattern[str]] = re.compile(
    rf"^{FORMAL_RULE_RESPONSE_ID_PREFIX}[0-9a-f]{{{FORMAL_RULE_ID_HEX_LEN}}}$"
)
_EXCEPTION_ID_PATTERN: Final[re.Pattern[str]] = re.compile(
    rf"^{FORMAL_RULE_EXCEPTION_ID_PREFIX}[0-9a-f]{{{FORMAL_RULE_ID_HEX_LEN}}}$"
)


class FormalRuleStage(StrEnum):
    """Closed monotone progression for one owner's rule belief.

    Evidence may promote a stage; no missing evidence silently demotes it.
    Retirement is an explicit status, never a stage regression.
    """

    HABIT = "habit"
    EXPECTATION = "expectation"
    NORM = "norm"
    DOCUMENTED = "documented"
    RECOGNIZED_ENFORCEMENT = "recognized_enforcement"


FORMAL_RULE_STAGE_ORDER: Final[Mapping[FormalRuleStage, int]] = MappingProxyType(
    {
        FormalRuleStage.HABIT: 0,
        FormalRuleStage.EXPECTATION: 1,
        FormalRuleStage.NORM: 2,
        FormalRuleStage.DOCUMENTED: 3,
        FormalRuleStage.RECOGNIZED_ENFORCEMENT: 4,
    }
)


class FormalRuleConstraintKind(StrEnum):
    """Closed social constraint kind. Physical impossibility is not a member."""

    PROHIBITION = "prohibition"
    OBLIGATION = "obligation"
    PERMISSION = "permission"


class FormalRuleScopeKind(StrEnum):
    """Closed scope dimension a rule belief may address."""

    PERSON = "person"
    PLACE = "place"
    RESOURCE = "resource"
    ACTION = "action"
    COLLECTIVE = "collective"
    UNSPECIFIED = "unspecified"


class FormalRuleAuthorityKind(StrEnum):
    """Closed basis on which an owner believes a rule is recognized."""

    SELF = "self"
    OFFICE = "office"
    ORGANIZATION = "organization"
    COLLECTIVE_DECISION = "collective_decision"
    PROCEDURE = "procedure"
    WRITTEN_RECORD = "written_record"
    CUSTOM = "custom"
    UNKNOWN = "unknown"


class FormalRuleRecognition(StrEnum):
    """Closed owner belief about whether authority is recognized."""

    UNRECOGNIZED = "unrecognized"
    CLAIMED = "claimed"
    RECOGNIZED = "recognized"
    CONTESTED = "contested"


class FormalRuleStatus(StrEnum):
    """Closed owner-local lifecycle status for one rule belief."""

    CANDIDATE = "candidate"
    ACTIVE = "active"
    CONTESTED = "contested"
    SUPERSEDED = "superseded"
    RETIRED = "retired"


class FormalRulePositionStance(StrEnum):
    """Closed stance one actor may hold toward a rule belief."""

    PROPONENT = "proponent"
    SUPPORTER = "supporter"
    OPPONENT = "opponent"
    CHALLENGER = "challenger"
    REINTERPRETER = "reinterpreter"
    AMENDER = "amender"
    WITHDRAWER = "withdrawer"


class FormalRuleResponseKind(StrEnum):
    """Closed owner response declaration; never an objective compliance finding."""

    FOLLOW = "follow"
    VIOLATE = "violate"
    CHALLENGE = "challenge"
    REINTERPRET = "reinterpret"
    IGNORE = "ignore"


class FormalRuleEvidenceChannel(StrEnum):
    """Closed provenance channel for one formal-rule evidence contribution."""

    OBSERVED = "observed"
    COMMUNICATED = "communicated"
    REMEMBERED = "remembered"
    RECORDED = "recorded"
    DERIVED = "derived"


class FormalRuleSanctionKind(StrEnum):
    """Closed expected-sanction belief. No sanction is dispatched automatically."""

    CRITICISM = "criticism"
    REFUSAL = "refusal"
    REDUCED_TRUST = "reduced_trust"
    RETALIATION = "retaliation"
    EXCLUSION = "exclusion"
    RESTITUTION = "restitution"


class FormalRuleReportKind(StrEnum):
    """Closed claim kind an owner may assert about conduct or enforcement."""

    COMPLIANCE = "compliance"
    VIOLATION = "violation"
    EXEMPTION = "exemption"
    ENFORCEMENT = "enforcement"


class FormalRuleRepresentationStatus(StrEnum):
    """Closed owner belief about the integrity of a written representation."""

    INTACT = "intact"
    DAMAGED = "damaged"
    MISSING = "missing"
    UNKNOWN = "unknown"


class FormalRuleProvenance(StrEnum):
    """Closed provenance for one formal-rule belief or version."""

    SELF_AUTHORED = "self_authored"
    COMMUNICATED = "communicated"
    DERIVED_FROM_NORM = "derived_from_norm"
    DERIVED_FROM_CONVENTION = "derived_from_convention"
    DERIVED_FROM_RECORD = "derived_from_record"
    AUTHORITY_RECOGNIZED = "authority_recognized"
    OBSERVED_EFFECT = "observed_effect"
    REINTERPRETATION = "reinterpretation"
    AMENDMENT = "amendment"
    CONTESTED = "contested"
    UNRECOGNIZED = "unrecognized"
    EXPIRED = "expired"
    ORPHANED = "orphaned"
    UNKNOWN = "unknown"


class FormalRuleRevisionKind(StrEnum):
    """Closed reason one historical rule version was appended."""

    INITIAL = "initial"
    STAGE_PROMOTION = "stage_promotion"
    SCOPE_CHANGE = "scope_change"
    AUTHORITY_CHANGE = "authority_change"
    WRITTEN_CHANGE = "written_change"
    SANCTION_CHANGE = "sanction_change"
    EXCEPTION_CHANGE = "exception_change"
    RECOGNITION_CHANGE = "recognition_change"
    RETIREMENT = "retirement"
    REINTERPRETATION = "reinterpretation"
    AMENDMENT = "amendment"


class FormalRuleExceptionReason(StrEnum):
    """Closed owner belief about why an exception applies."""

    EXEMPT_ACTOR = "exempt_actor"
    EXEMPT_PLACE = "exempt_place"
    EMERGENCY = "emergency"
    ROLE_DUTY = "role_duty"
    PRIOR_OBLIGATION = "prior_obligation"
    UNKNOWN = "unknown"


FORMAL_RULE_NOTICE_CODES: Final[frozenset[str]] = frozenset(
    {
        "cap_exceeded",
        "ignored_kind",
        "unresolved_scope",
        "no_candidate",
        "orphaned_rule_system",
        "formal_rule_version_out_of_order",
        "formal_rule_truncated",
        "representation_damaged",
        "representation_missing",
        "unrecognized_authority",
        "contested_system",
        "expired",
    }
)


FORMAL_RULE_ERROR_CODES: Final[frozenset[str]] = frozenset(
    {
        "formal_rule_invalid_id",
        "formal_rule_invalid_mode",
        "formal_rule_invalid_owner",
        "formal_rule_invalid_action",
        "formal_rule_invalid_anchor",
        "formal_rule_invalid_scope",
        "formal_rule_invalid_reference",
        "formal_rule_invalid_digest",
        "formal_rule_invalid_ordinal",
        "formal_rule_invalid_tick",
        "formal_rule_scope_limit",
        "formal_rule_policy_not_locked",
        "formal_rule_policy_mismatch",
        "formal_rule_invalid_ledger",
        "formal_rule_invalid_record",
        "formal_rule_owner_mismatch",
        "formal_rule_forbidden_field",
        "formal_rule_forbidden_input",
        "formal_rule_tick_regression",
        "formal_rule_frame_invalid",
        "formal_rule_frame_unsupported_command",
        "formal_rule_action_invalid",
        "formal_rule_response_invalid",
    }
)

FORMAL_RULE_FORBIDDEN_FIELD_NAMES: Final[frozenset[str]] = frozenset(
    {
        "law",
        "statute",
        "legal_code",
        "court",
        "judge",
        "police",
        "government",
        "jurisdiction",
        "sovereign",
        "rule_engine",
        "sanction_engine",
        "policy_engine",
        "enforced_by_world",
        "physical_law",
        "objective_rule",
        "global_rule_registry",
        "current_law",
        "binding_rule",
    }
)


class FormalRuleError(ValueError):
    """Stable-code formal-rule contract violation with no payload detail."""

    __slots__ = ("code",)

    def __init__(self, code: str) -> None:
        if code not in FORMAL_RULE_ERROR_CODES:
            raise ValueError("formal_rule_invalid_error_code")
        self.code: str = code
        super().__init__(code)


def _fail(code: str) -> NoReturn:
    raise FormalRuleError(code)


@dataclass(frozen=True, slots=True)
class FormalRulePolicy:
    """Locked owner-local formal-rule cognition bounds.

    Every value is part of the accepted contract. Any deviation is a programming
    error and fails closed with ``formal_rule_policy_not_locked``.
    """

    version: str = FORMAL_RULE_POLICY_VERSION
    max_systems: int = 8
    max_rules: int = 32
    max_versions_per_rule: int = 16
    max_evidence_per_rule: int = 64
    max_positions_per_rule: int = 64
    max_responses_per_rule: int = 64
    max_exceptions_per_rule: int = 8
    max_sanctions_per_rule: int = 8
    max_scope_anchors: int = 8
    max_total_records: int = 512
    min_supporters_for_recognition: int = 2
    min_enforcement_recurrence: int = 2
    version_window_ticks: int = 64
    max_frame_chars: int = 384
    max_relations: int = 32

    def __post_init__(self) -> None:
        for name, expected in _LOCKED_POLICY_VALUES.items():
            actual = getattr(self, name)
            if type(actual) is not type(expected) or actual != expected:
                _fail("formal_rule_policy_not_locked")


_LOCKED_POLICY_VALUES: Final[Mapping[str, str | int]] = MappingProxyType(
    {
        "version": FORMAL_RULE_POLICY_VERSION,
        "max_systems": 8,
        "max_rules": 32,
        "max_versions_per_rule": 16,
        "max_evidence_per_rule": 64,
        "max_positions_per_rule": 64,
        "max_responses_per_rule": 64,
        "max_exceptions_per_rule": 8,
        "max_sanctions_per_rule": 8,
        "max_scope_anchors": 8,
        "max_total_records": 512,
        "min_supporters_for_recognition": 2,
        "min_enforcement_recurrence": 2,
        "version_window_ticks": 64,
        "max_frame_chars": 384,
        "max_relations": 32,
    }
)

_DEFAULT_POLICY: Final[FormalRulePolicy] = FormalRulePolicy()
_LOG.info(
    "formal_rule_policy_constructed policy_version=%s", FORMAL_RULE_POLICY_VERSION
)


def default_formal_rule_policy() -> FormalRulePolicy:
    """Return the single locked policy instance."""

    return _DEFAULT_POLICY


def require_formal_rule_policy(policy: object | None) -> FormalRulePolicy:
    """Require the locked policy, installing the default when absent."""

    if policy is None:
        return _DEFAULT_POLICY
    if type(policy) is not FormalRulePolicy:
        _fail("formal_rule_policy_mismatch")
    return policy


def _require_text(value: object, code: str) -> str:
    if type(value) is not str or not value:
        _fail(code)
    return value


def _require_reference(
    value: object, code: str = "formal_rule_invalid_reference"
) -> str:
    reference = _require_text(value, code)
    if len(reference) > _REFERENCE_MAX_LEN:
        _fail(code)
    return reference


def _require_enum[EnumT: StrEnum](
    value: object, enum_type: type[EnumT]
) -> EnumT:
    if type(value) is not enum_type:
        _fail("formal_rule_invalid_mode")
    _LOG.debug(
        "formal_rule_contract_validated name=%s count=%s",
        enum_type.__name__,
        len(enum_type),
    )
    return value


def _require_action_token(value: object) -> str:
    if type(value) is not str or len(value) > _TOKEN_MAX_LEN:
        _fail("formal_rule_invalid_action")
    if _TOKEN_PATTERN.match(value) is None:
        _fail("formal_rule_invalid_action")
    return value


def _require_digest(value: object, code: str = "formal_rule_invalid_digest") -> str:
    if type(value) is not str or _HEX64_PATTERN.match(value) is None:
        _fail(code)
    return value


def _require_ordinal(value: object) -> int:
    if type(value) is not int or value < 0:
        _fail("formal_rule_invalid_ordinal")
    return value


def _require_tick(value: object) -> int:
    if type(value) is not int or value < 0:
        _fail("formal_rule_invalid_tick")
    return value


def _digest(namespace: str, material: Sequence[str]) -> str:
    payload = _SEPARATOR.join((namespace, *material))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _short_digest(namespace: str, material: Sequence[str]) -> str:
    return _digest(namespace, material)[:FORMAL_RULE_ID_HEX_LEN]


def formal_rule_scope_digest(kind: object, anchor_ids: object) -> str:
    """Return a canonical digest of one scope kind and its sorted anchors.

    Anchors are sorted and de-duplicated so equivalent scope sets produce the
    same digest. More than ``max_scope_anchors`` anchors fail closed.
    """

    scope_kind = _require_enum(kind, FormalRuleScopeKind)
    if type(anchor_ids) is not list and type(anchor_ids) is not tuple:
        _fail("formal_rule_invalid_anchor")
    anchors: list[str] = []
    for anchor in anchor_ids:
        anchors.append(_require_text(anchor, "formal_rule_invalid_anchor"))
    unique = sorted(set(anchors))
    if len(unique) > _DEFAULT_POLICY.max_scope_anchors:
        _fail("formal_rule_scope_limit")
    return _digest(FORMAL_RULE_SCOPE_NAMESPACE, (scope_kind.value, *unique))


def formal_rule_system_id(owner_id: str, scope_digest: str, authority: str) -> str:
    """Mint one owner-local rule-system id from its scope and authority."""

    owner = _require_text(owner_id, "formal_rule_invalid_owner")
    scope = _require_digest(scope_digest)
    authority_kind = _require_enum(authority, FormalRuleAuthorityKind)
    body = _short_digest(
        FORMAL_RULE_SYSTEM_NAMESPACE,
        (owner, scope, authority_kind.value),
    )
    return f"{FORMAL_RULE_SYSTEM_ID_PREFIX}{body}"


def formal_rule_id(
    owner_id: str,
    system_id: str,
    constraint: str,
    action: str,
    scope_digest: str,
) -> str:
    """Mint one owner-local rule id from constraint, action, and scope.

    Labels and evidence ordinals are intentionally excluded so later revisions
    keep the same rule identity.
    """

    owner = _require_text(owner_id, "formal_rule_invalid_owner")
    system = require_formal_rule_system_id(system_id)
    constraint_kind = _require_enum(constraint, FormalRuleConstraintKind)
    action_token = _require_action_token(action)
    scope = _require_digest(scope_digest)
    body = _short_digest(
        FORMAL_RULE_NAMESPACE,
        (owner, system, constraint_kind.value, action_token, scope),
    )
    return f"{FORMAL_RULE_ID_PREFIX}{body}"


def formal_rule_version_id(
    rule_id: str, version_number: int, content_digest: str
) -> str:
    """Mint one owner-local rule-version id from rule and content."""

    rule = require_formal_rule_id(rule_id)
    version = _require_ordinal(version_number)
    if version < 1:
        _fail("formal_rule_invalid_ordinal")
    content = _require_digest(content_digest)
    body = _short_digest(
        FORMAL_RULE_VERSION_NAMESPACE,
        (rule, str(version), content),
    )
    return f"{FORMAL_RULE_VERSION_ID_PREFIX}{body}"


def formal_rule_evidence_id(
    rule_id: str, ordinal: int, channel: str, lineage_ref: str
) -> str:
    """Mint one owner-local evidence id from its bounded provenance."""

    rule = require_formal_rule_id(rule_id)
    evidence_ordinal = _require_ordinal(ordinal)
    evidence_channel = _require_enum(channel, FormalRuleEvidenceChannel)
    reference = _require_reference(lineage_ref, "formal_rule_invalid_reference")
    body = _short_digest(
        FORMAL_RULE_EVIDENCE_NAMESPACE,
        (rule, str(evidence_ordinal), evidence_channel.value, reference),
    )
    return f"{FORMAL_RULE_EVIDENCE_ID_PREFIX}{body}"


def formal_rule_position_id(
    rule_id: str, actor_id: str, stance: str, ordinal: int
) -> str:
    """Mint one owner-local position id from actor, stance, and ordinal."""

    rule = require_formal_rule_id(rule_id)
    actor = _require_text(actor_id, "formal_rule_invalid_reference")
    position_stance = _require_enum(stance, FormalRulePositionStance)
    position_ordinal = _require_ordinal(ordinal)
    body = _short_digest(
        FORMAL_RULE_POSITION_NAMESPACE,
        (rule, actor, position_stance.value, str(position_ordinal)),
    )
    return f"{FORMAL_RULE_POSITION_ID_PREFIX}{body}"


def formal_rule_response_id(rule_id: str, actor_id: str, kind: str, tick: int) -> str:
    """Mint one owner-local response id from actor, kind, and absolute tick."""

    rule = require_formal_rule_id(rule_id)
    actor = _require_text(actor_id, "formal_rule_invalid_reference")
    response_kind = _require_enum(kind, FormalRuleResponseKind)
    absolute_tick = _require_tick(tick)
    body = _short_digest(
        FORMAL_RULE_RESPONSE_NAMESPACE,
        (rule, actor, response_kind.value, str(absolute_tick)),
    )
    return f"{FORMAL_RULE_RESPONSE_ID_PREFIX}{body}"


def formal_rule_exception_id(
    rule_id: str, ordinal: int, condition_digest: str
) -> str:
    """Mint one owner-local exception id from ordinal and condition digest."""

    rule = require_formal_rule_id(rule_id)
    exception_ordinal = _require_ordinal(ordinal)
    condition = _require_digest(condition_digest)
    body = _short_digest(
        FORMAL_RULE_EXCEPTION_NAMESPACE,
        (rule, str(exception_ordinal), condition),
    )
    return f"{FORMAL_RULE_EXCEPTION_ID_PREFIX}{body}"


def _require_prefix(value: object, pattern: re.Pattern[str]) -> str:
    if type(value) is not str or pattern.match(value) is None:
        _fail("formal_rule_invalid_id")
    return value


def require_formal_rule_system_id(value: object) -> str:
    """Require an owner-local ``frs-`` rule-system identity."""

    return _require_prefix(value, _SYSTEM_ID_PATTERN)


def require_formal_rule_id(value: object) -> str:
    """Require an owner-local ``frl-`` rule identity."""

    return _require_prefix(value, _RULE_ID_PATTERN)


def require_formal_rule_version_id(value: object) -> str:
    """Require an owner-local ``frv-`` rule-version identity."""

    return _require_prefix(value, _VERSION_ID_PATTERN)


def require_formal_rule_evidence_id(value: object) -> str:
    """Require an owner-local ``fre-`` evidence identity."""

    return _require_prefix(value, _EVIDENCE_ID_PATTERN)


def require_formal_rule_position_id(value: object) -> str:
    """Require an owner-local ``frp-`` position identity."""

    return _require_prefix(value, _POSITION_ID_PATTERN)


def require_formal_rule_response_id(value: object) -> str:
    """Require an owner-local ``frr-`` response identity."""

    return _require_prefix(value, _RESPONSE_ID_PATTERN)


def require_formal_rule_exception_id(value: object) -> str:
    """Require an owner-local ``frx-`` exception identity."""

    return _require_prefix(value, _EXCEPTION_ID_PATTERN)


# ---------------------------------------------------------------------------
# Bounded owner-scoped belief records
# ---------------------------------------------------------------------------


def _reject_forbidden_fields(cls: type[object]) -> None:
    names = set(getattr(cls, "__dataclass_fields__", {}))
    if names & FORMAL_RULE_FORBIDDEN_FIELD_NAMES:
        _fail("formal_rule_forbidden_field")


def _require_owner_id(value: object) -> AgentId:
    if type(value) is not AgentId:
        _fail("formal_rule_invalid_owner")
    return value


def _require_unit(value: object, code: str = "formal_rule_invalid_mode") -> float:
    if type(value) is not float:
        _fail(code)
    if value != value or value in (float("inf"), float("-inf")):
        _fail(code)
    quantized = float(Decimal(str(value)).quantize(_QUANTUM, rounding=ROUND_HALF_UP))
    if quantized < 0.0 or quantized > 1.0:
        _fail(code)
    return quantized


def _optional_reference(
    value: object, code: str = "formal_rule_invalid_reference"
) -> str | None:
    if value is None:
        return None
    return _require_reference(value, code)


def _optional_count(
    value: object, code: str = "formal_rule_invalid_ordinal"
) -> int | None:
    if value is None:
        return None
    return _require_ordinal(value)


def _require_sequence(value: object, code: str) -> tuple[object, ...]:
    if not isinstance(value, (list, tuple)):
        _fail(code)
    return tuple(value)


def _ordered_references(
    values: object, code: str = "formal_rule_invalid_record"
) -> tuple[str, ...]:
    items = _require_sequence(values, code)
    references: list[str] = []
    for item in items:
        references.append(_require_reference(item, code))
    if len(set(references)) != len(references):
        _fail(code)
    return tuple(sorted(references))


def _require_span(first_tick: object, last_tick: object) -> tuple[int, int]:
    first = _require_tick(first_tick)
    last = _require_tick(last_tick)
    if last < first:
        _fail("formal_rule_tick_regression")
    return first, last


def _validate_notices(values: object) -> tuple[str, ...]:
    items = _require_sequence(values, "formal_rule_invalid_ledger")
    checked: list[str] = []
    for item in items:
        if type(item) is not str or item not in FORMAL_RULE_NOTICE_CODES:
            _fail("formal_rule_invalid_ledger")
        if item not in checked:
            checked.append(item)
    return tuple(sorted(checked))


@dataclass(frozen=True, slots=True)
class FormalRuleScope:
    """One owner's scope claim; anchors are bounded opaque references."""

    kind: FormalRuleScopeKind
    anchor_ids: tuple[str, ...] = ()
    digest: str = ""

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        scope_kind = _require_enum(self.kind, FormalRuleScopeKind)
        anchors = _ordered_references(
            self.anchor_ids, "formal_rule_invalid_anchor"
        )
        expected = formal_rule_scope_digest(scope_kind, anchors)
        if self.digest:
            if _require_digest(self.digest) != expected:
                _fail("formal_rule_invalid_scope")
        object.__setattr__(self, "kind", scope_kind)
        object.__setattr__(self, "anchor_ids", anchors)
        object.__setattr__(self, "digest", expected)


@dataclass(frozen=True, slots=True)
class FormalRuleWrittenRepresentation:
    """Observed anchor to a written record; never parsed into objective law."""

    artifact_id: str
    artifact_revision: int
    genre: str
    repository_id: str | None = None
    status: FormalRuleRepresentationStatus = FormalRuleRepresentationStatus.UNKNOWN
    tick: int = 0

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        object.__setattr__(
            self, "artifact_id", _require_reference(self.artifact_id)
        )
        object.__setattr__(
            self, "artifact_revision", _require_ordinal(self.artifact_revision)
        )
        object.__setattr__(self, "genre", _require_action_token(self.genre))
        object.__setattr__(
            self, "repository_id", _optional_reference(self.repository_id)
        )
        object.__setattr__(
            self,
            "status",
            _require_enum(self.status, FormalRuleRepresentationStatus),
        )
        object.__setattr__(self, "tick", _require_tick(self.tick))


@dataclass(frozen=True, slots=True)
class FormalRuleSanctionExpectation:
    """One expected sanction belief. Nothing is dispatched from this record."""

    kind: FormalRuleSanctionKind
    severity: float = 0.0
    source: str = "unknown"
    enforcement_ref: str | None = None

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        object.__setattr__(
            self, "kind", _require_enum(self.kind, FormalRuleSanctionKind)
        )
        object.__setattr__(self, "severity", _require_unit(self.severity))
        object.__setattr__(self, "source", _require_action_token(self.source))
        object.__setattr__(
            self, "enforcement_ref", _optional_reference(self.enforcement_ref)
        )


@dataclass(frozen=True, slots=True)
class FormalRuleException:
    """One owner-local exception; it never removes a prohibition."""

    exception_id: str
    rule_id: str
    condition_digest: str
    reason: FormalRuleExceptionReason = FormalRuleExceptionReason.UNKNOWN
    scope: FormalRuleScope | None = None
    evidence_ref: str | None = None
    tick: int = 0

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        object.__setattr__(
            self, "exception_id", require_formal_rule_exception_id(self.exception_id)
        )
        object.__setattr__(self, "rule_id", require_formal_rule_id(self.rule_id))
        object.__setattr__(
            self, "condition_digest", _require_digest(self.condition_digest)
        )
        object.__setattr__(
            self, "reason", _require_enum(self.reason, FormalRuleExceptionReason)
        )
        if self.scope is not None and type(self.scope) is not FormalRuleScope:
            _fail("formal_rule_invalid_record")
        object.__setattr__(
            self, "evidence_ref", _optional_reference(self.evidence_ref)
        )
        object.__setattr__(self, "tick", _require_tick(self.tick))


@dataclass(frozen=True, slots=True)
class FormalRuleEvidence:
    """One bounded owner-local contribution toward a rule belief."""

    evidence_id: str
    rule_id: str
    channel: FormalRuleEvidenceChannel
    provenance: FormalRuleProvenance
    tick: int
    source_actor: str | None = None
    artifact_id: str | None = None
    artifact_revision: int | None = None
    claim_ref: str | None = None
    lineage_ref: str | None = None

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        object.__setattr__(
            self, "evidence_id", require_formal_rule_evidence_id(self.evidence_id)
        )
        object.__setattr__(self, "rule_id", require_formal_rule_id(self.rule_id))
        object.__setattr__(
            self, "channel", _require_enum(self.channel, FormalRuleEvidenceChannel)
        )
        object.__setattr__(
            self, "provenance", _require_enum(self.provenance, FormalRuleProvenance)
        )
        object.__setattr__(self, "tick", _require_tick(self.tick))
        object.__setattr__(
            self, "source_actor", _optional_reference(self.source_actor)
        )
        object.__setattr__(self, "artifact_id", _optional_reference(self.artifact_id))
        object.__setattr__(
            self,
            "artifact_revision",
            _optional_count(self.artifact_revision),
        )
        object.__setattr__(self, "claim_ref", _optional_reference(self.claim_ref))
        object.__setattr__(
            self, "lineage_ref", _optional_reference(self.lineage_ref)
        )


@dataclass(frozen=True, slots=True)
class FormalRuleProponent:
    """One actor stance recorded by the owner; never an objective endorsement."""

    position_id: str
    rule_id: str
    actor_id: str
    stance: FormalRulePositionStance
    provenance: FormalRuleProvenance
    tick: int
    ordinal: int

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        object.__setattr__(
            self,
            "position_id",
            require_formal_rule_position_id(self.position_id),
        )
        object.__setattr__(self, "rule_id", require_formal_rule_id(self.rule_id))
        object.__setattr__(self, "actor_id", _require_reference(self.actor_id))
        object.__setattr__(
            self, "stance", _require_enum(self.stance, FormalRulePositionStance)
        )
        object.__setattr__(
            self, "provenance", _require_enum(self.provenance, FormalRuleProvenance)
        )
        object.__setattr__(self, "tick", _require_tick(self.tick))
        object.__setattr__(self, "ordinal", _require_ordinal(self.ordinal))


@dataclass(frozen=True, slots=True)
class FormalRuleVersion:
    """One historical version of a rule belief."""

    version_id: str
    rule_id: str
    version_number: int
    stage: FormalRuleStage
    constraint: FormalRuleConstraintKind
    authority: FormalRuleAuthorityKind
    recognition: FormalRuleRecognition
    scope: FormalRuleScope
    written: FormalRuleWrittenRepresentation | None = None
    sanction_kinds: tuple[FormalRuleSanctionKind, ...] = ()
    exception_ids: tuple[str, ...] = ()
    tick: int = 0
    revision_kind: FormalRuleRevisionKind = FormalRuleRevisionKind.INITIAL
    supersedes_version_id: str | None = None
    provenance: FormalRuleProvenance = FormalRuleProvenance.UNKNOWN

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        object.__setattr__(
            self, "version_id", require_formal_rule_version_id(self.version_id)
        )
        object.__setattr__(self, "rule_id", require_formal_rule_id(self.rule_id))
        number = _require_ordinal(self.version_number)
        if number < 1:
            _fail("formal_rule_invalid_ordinal")
        object.__setattr__(self, "version_number", number)
        object.__setattr__(
            self, "stage", _require_enum(self.stage, FormalRuleStage)
        )
        object.__setattr__(
            self,
            "constraint",
            _require_enum(self.constraint, FormalRuleConstraintKind),
        )
        object.__setattr__(
            self,
            "authority",
            _require_enum(self.authority, FormalRuleAuthorityKind),
        )
        object.__setattr__(
            self,
            "recognition",
            _require_enum(self.recognition, FormalRuleRecognition),
        )
        if type(self.scope) is not FormalRuleScope:
            _fail("formal_rule_invalid_scope")
        if self.written is not None and (
            type(self.written) is not FormalRuleWrittenRepresentation
        ):
            _fail("formal_rule_invalid_record")
        for kind in _require_sequence(
            self.sanction_kinds, "formal_rule_invalid_record"
        ):
            _require_enum(kind, FormalRuleSanctionKind)
        sanction_kinds = tuple(
            sorted(
                {kind for kind in self.sanction_kinds},
                key=lambda item: item.value,
            )
        )
        object.__setattr__(self, "sanction_kinds", sanction_kinds)
        object.__setattr__(
            self,
            "exception_ids",
            _ordered_ids(
                self.exception_ids,
                require_formal_rule_exception_id,
                "formal_rule_invalid_id",
            ),
        )
        object.__setattr__(self, "tick", _require_tick(self.tick))
        object.__setattr__(
            self,
            "revision_kind",
            _require_enum(self.revision_kind, FormalRuleRevisionKind),
        )
        if self.supersedes_version_id is not None:
            object.__setattr__(
                self,
                "supersedes_version_id",
                require_formal_rule_version_id(self.supersedes_version_id),
            )
        object.__setattr__(
            self, "provenance", _require_enum(self.provenance, FormalRuleProvenance)
        )


def _ordered_ids(
    values: object,
    require: Callable[[object], str],
    code: str,
) -> tuple[str, ...]:
    items = _require_sequence(values, code)
    identifiers: list[str] = []
    for item in items:
        identifiers.append(require(item))
    if len(set(identifiers)) != len(identifiers):
        _fail(code)
    return tuple(sorted(identifiers))


@dataclass(frozen=True, slots=True)
class FormalRuleResponse:
    """One owner declaration about a rule; never objective compliance."""

    response_id: str
    rule_id: str
    actor_id: str
    kind: FormalRuleResponseKind
    tick: int
    provenance: FormalRuleProvenance = FormalRuleProvenance.SELF_AUTHORED
    claim_ref: str | None = None

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        object.__setattr__(
            self, "response_id", require_formal_rule_response_id(self.response_id)
        )
        object.__setattr__(self, "rule_id", require_formal_rule_id(self.rule_id))
        object.__setattr__(self, "actor_id", _require_reference(self.actor_id))
        object.__setattr__(
            self, "kind", _require_enum(self.kind, FormalRuleResponseKind)
        )
        object.__setattr__(self, "tick", _require_tick(self.tick))
        object.__setattr__(
            self, "provenance", _require_enum(self.provenance, FormalRuleProvenance)
        )
        object.__setattr__(self, "claim_ref", _optional_reference(self.claim_ref))


@dataclass(frozen=True, slots=True)
class FormalRule:
    """One owner's belief about a socially recognized constraint."""

    rule_id: str
    system_id: str
    owner_id: AgentId
    stage: FormalRuleStage
    constraint: FormalRuleConstraintKind
    action_token: str
    scope: FormalRuleScope
    authority: FormalRuleAuthorityKind
    recognition: FormalRuleRecognition
    status: FormalRuleStatus
    strength: float
    proponents: tuple[FormalRuleProponent, ...] = ()
    versions: tuple[FormalRuleVersion, ...] = ()
    evidence: tuple[FormalRuleEvidence, ...] = ()
    sanctions: tuple[FormalRuleSanctionExpectation, ...] = ()
    exceptions: tuple[FormalRuleException, ...] = ()
    responses: tuple[FormalRuleResponse, ...] = ()
    first_tick: int = 0
    last_tick: int = 0
    notices: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        rule_id = require_formal_rule_id(self.rule_id)
        system_id = require_formal_rule_system_id(self.system_id)
        owner_id = _require_owner_id(self.owner_id)
        object.__setattr__(self, "rule_id", rule_id)
        object.__setattr__(self, "system_id", system_id)
        object.__setattr__(self, "owner_id", owner_id)
        object.__setattr__(
            self, "stage", _require_enum(self.stage, FormalRuleStage)
        )
        object.__setattr__(
            self,
            "constraint",
            _require_enum(self.constraint, FormalRuleConstraintKind),
        )
        object.__setattr__(
            self, "action_token", _require_action_token(self.action_token)
        )
        if type(self.scope) is not FormalRuleScope:
            _fail("formal_rule_invalid_scope")
        object.__setattr__(
            self,
            "authority",
            _require_enum(self.authority, FormalRuleAuthorityKind),
        )
        object.__setattr__(
            self,
            "recognition",
            _require_enum(self.recognition, FormalRuleRecognition),
        )
        object.__setattr__(
            self, "status", _require_enum(self.status, FormalRuleStatus)
        )
        object.__setattr__(self, "strength", _require_unit(self.strength))
        first, last = _require_span(self.first_tick, self.last_tick)
        object.__setattr__(self, "first_tick", first)
        object.__setattr__(self, "last_tick", last)

        proponents = tuple(
            _require_records(
                self.proponents,
                FormalRuleProponent,
                "position_id",
            )
        )
        versions = tuple(
            _require_records(
                self.versions,
                FormalRuleVersion,
                "version_number",
            )
        )
        evidence = tuple(
            _require_records(self.evidence, FormalRuleEvidence, "evidence_id")
        )
        exceptions = tuple(
            _require_records(
                self.exceptions,
                FormalRuleException,
                "exception_id",
            )
        )
        responses = tuple(
            _require_records(self.responses, FormalRuleResponse, "response_id")
        )
        if not isinstance(self.sanctions, (list, tuple)):
            _fail("formal_rule_invalid_record")
        sanctions = tuple(self.sanctions)
        for sanction in sanctions:
            if type(sanction) is not FormalRuleSanctionExpectation:
                _fail("formal_rule_invalid_record")
        sanctions = tuple(
            sorted(
                sanctions,
                key=lambda item: (
                    item.kind.value,
                    item.source,
                    item.severity,
                    item.enforcement_ref or "",
                ),
            )
        )
        for proponent in proponents:
            if proponent.rule_id != rule_id:
                _fail("formal_rule_invalid_ledger")
        for evidence_item in evidence:
            if evidence_item.rule_id != rule_id:
                _fail("formal_rule_invalid_ledger")
        for exception in exceptions:
            if exception.rule_id != rule_id:
                _fail("formal_rule_invalid_ledger")
        for response in responses:
            if response.rule_id != rule_id:
                _fail("formal_rule_invalid_ledger")
        if not versions:
            _fail("formal_rule_invalid_ledger")
        previous_number = 0
        previous_id: str | None = None
        for version in versions:
            if version.rule_id != rule_id:
                _fail("formal_rule_invalid_ledger")
            if version.version_number != previous_number + 1:
                _fail("formal_rule_invalid_ledger")
            if version.supersedes_version_id != previous_id:
                _fail("formal_rule_invalid_ledger")
            previous_number = version.version_number
            previous_id = version.version_id
        object.__setattr__(self, "proponents", proponents)
        object.__setattr__(self, "versions", versions)
        object.__setattr__(self, "evidence", evidence)
        object.__setattr__(self, "sanctions", sanctions)
        object.__setattr__(self, "exceptions", exceptions)
        object.__setattr__(self, "responses", responses)
        object.__setattr__(self, "notices", _validate_notices(self.notices))


def _require_records(
    values: object,
    record_type: type[object],
    key: str,
) -> tuple[Any, ...]:
    items = _require_sequence(values, "formal_rule_invalid_record")
    records: list[Any] = []
    for item in items:
        if type(item) is not record_type:
            _fail("formal_rule_invalid_record")
        records.append(item)
    keys = [getattr(item, key) for item in records]
    if len(set(keys)) != len(keys):
        _fail("formal_rule_invalid_record")
    return tuple(sorted(records, key=lambda item: getattr(item, key)))


@dataclass(frozen=True, slots=True)
class FormalRuleSystem:
    """One owner's belief about a coherent rule system; never a jurisdiction."""

    system_id: str
    owner_id: AgentId
    scope: FormalRuleScope
    authority: FormalRuleAuthorityKind
    status: FormalRuleStatus
    proponent_ids: tuple[str, ...] = ()
    rule_ids: tuple[str, ...] = ()
    competing_system_ids: tuple[str, ...] = ()
    first_tick: int = 0
    last_tick: int = 0

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        object.__setattr__(
            self, "system_id", require_formal_rule_system_id(self.system_id)
        )
        object.__setattr__(self, "owner_id", _require_owner_id(self.owner_id))
        if type(self.scope) is not FormalRuleScope:
            _fail("formal_rule_invalid_scope")
        object.__setattr__(
            self,
            "authority",
            _require_enum(self.authority, FormalRuleAuthorityKind),
        )
        object.__setattr__(
            self, "status", _require_enum(self.status, FormalRuleStatus)
        )
        object.__setattr__(
            self,
            "proponent_ids",
            _ordered_references(self.proponent_ids),
        )
        object.__setattr__(
            self,
            "rule_ids",
            _ordered_ids(
                self.rule_ids, require_formal_rule_id, "formal_rule_invalid_id"
            ),
        )
        object.__setattr__(
            self,
            "competing_system_ids",
            _ordered_ids(
                self.competing_system_ids,
                require_formal_rule_system_id,
                "formal_rule_invalid_id",
            ),
        )
        first, last = _require_span(self.first_tick, self.last_tick)
        object.__setattr__(self, "first_tick", first)
        object.__setattr__(self, "last_tick", last)


@dataclass(frozen=True, slots=True)
class FormalRuleLedger:
    """One owner's formal-rule beliefs. ``None`` means the mode is off."""

    owner_id: AgentId
    systems: tuple[FormalRuleSystem, ...] = ()
    rules: tuple[FormalRule, ...] = ()
    notices: tuple[str, ...] = ()
    policy_version: str = FORMAL_RULE_POLICY_VERSION

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        object.__setattr__(self, "owner_id", _require_owner_id(self.owner_id))
        if self.policy_version != FORMAL_RULE_POLICY_VERSION:
            _fail("formal_rule_policy_mismatch")
        systems = tuple(
            _require_records(self.systems, FormalRuleSystem, "system_id")
        )
        rules = tuple(_require_records(self.rules, FormalRule, "rule_id"))
        if len(systems) > _DEFAULT_POLICY.max_systems:
            _fail("formal_rule_invalid_ledger")
        if len(rules) > _DEFAULT_POLICY.max_rules:
            _fail("formal_rule_invalid_ledger")
        by_system: dict[str, list[str]] = {system.system_id: [] for system in systems}
        for system in systems:
            if system.owner_id != self.owner_id:
                _fail("formal_rule_owner_mismatch")
        for rule in rules:
            if rule.owner_id != self.owner_id:
                _fail("formal_rule_owner_mismatch")
            if rule.system_id not in by_system:
                _fail("formal_rule_invalid_ledger")
            by_system[rule.system_id].append(rule.rule_id)
            if len(rule.versions) > _DEFAULT_POLICY.max_versions_per_rule:
                _fail("formal_rule_invalid_ledger")
            if len(rule.evidence) > _DEFAULT_POLICY.max_evidence_per_rule:
                _fail("formal_rule_invalid_ledger")
            if len(rule.proponents) > _DEFAULT_POLICY.max_positions_per_rule:
                _fail("formal_rule_invalid_ledger")
            if len(rule.responses) > _DEFAULT_POLICY.max_responses_per_rule:
                _fail("formal_rule_invalid_ledger")
            if len(rule.exceptions) > _DEFAULT_POLICY.max_exceptions_per_rule:
                _fail("formal_rule_invalid_ledger")
            if len(rule.sanctions) > _DEFAULT_POLICY.max_sanctions_per_rule:
                _fail("formal_rule_invalid_ledger")
        system_ids = {system.system_id for system in systems}
        for system in systems:
            expected = tuple(sorted(by_system[system.system_id]))
            if system.rule_ids != expected:
                _fail("formal_rule_invalid_ledger")
            for competitor in system.competing_system_ids:
                if competitor not in system_ids or competitor == system.system_id:
                    _fail("formal_rule_invalid_ledger")
                other = next(
                    item for item in systems if item.system_id == competitor
                )
                if system.system_id not in other.competing_system_ids:
                    _fail("formal_rule_invalid_ledger")
        total = (
            len(systems)
            + len(rules)
            + sum(
                len(rule.versions)
                + len(rule.evidence)
                + len(rule.proponents)
                + len(rule.responses)
                + len(rule.exceptions)
                + len(rule.sanctions)
                for rule in rules
            )
        )
        if total > _DEFAULT_POLICY.max_total_records:
            _fail("formal_rule_invalid_ledger")
        object.__setattr__(self, "systems", systems)
        object.__setattr__(self, "rules", rules)
        object.__setattr__(self, "notices", _validate_notices(self.notices))
        _LOG.debug(
            "formal_rule_ledger_validated systems=%s rules=%s",
            len(systems),
            len(rules),
        )


def empty_formal_rule_ledger(
    owner_id: AgentId,
    policy: FormalRulePolicy | None = None,
) -> FormalRuleLedger:
    """Return an enabled-but-empty ledger for one owner."""

    if policy is not None and type(policy) is not FormalRulePolicy:
        _fail("formal_rule_policy_mismatch")
    return FormalRuleLedger(owner_id=owner_id)


def require_owner_formal_rules(
    value: object | None,
    owner_id: AgentId,
    *,
    field_name: str,
) -> FormalRuleLedger | None:
    """Reject a foreign or mistyped formal-rule ledger. ``None`` passes."""

    if value is None:
        return None
    if type(owner_id) is not AgentId:
        _fail("formal_rule_invalid_owner")
    if type(value) is not FormalRuleLedger:
        _LOG.warning("formal_rule_carry_rejected reason=invalid_type")
        raise TypeError(f"{field_name} must be FormalRuleLedger")
    if value.owner_id != owner_id:
        _LOG.error(
            "formal_rule_validation_failed field=%s reason_code=owner_mismatch",
            field_name,
        )
        _fail("formal_rule_owner_mismatch")
    return value


FORMAL_RULE_ACTION_TOKENS: Final[frozenset[str]] = frozenset(
    {
        "give",
        "take",
        "attack",
        "move",
        "sleep",
        "inscribe",
        "amend",
        "erase",
        "maintain",
        "produce",
        "exchange",
        "teach",
        "heal",
        "feed",
        "transport",
        "wait",
        "communicate",
        "tell",
        "ask",
        "share",
        "withhold",
        "enter",
        "leave",
        "unspecified",
    }
)

_NORM_EXPECTATION_ACTIONS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "give_back": "give",
        "give": "give",
        "withhold_attack": "withhold",
        "give_again": "give",
        "maintain_structure": "maintain",
    }
)
_NORM_PATTERN_ACTIONS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "return_transfer": "give",
        "share_under_scarcity": "share",
        "spare_after_sleep": "withhold",
        "reciprocal_exchange": "exchange",
        "shared_upkeep": "maintain",
    }
)
_CONVENTION_ACTIONS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "wait": "wait",
        "talk": "communicate",
        "ask": "ask",
        "tell": "tell",
        "give": "give",
        "sleep": "sleep",
        "eat": "feed",
        "drink": "feed",
        "move": "move",
        "search": "move",
        "flee": "move",
        "help": "give",
        "attack": "attack",
    }
)
_DUTY_ACTIONS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "perform": "unspecified",
        "coordinate": "communicate",
        "maintain": "maintain",
        "transmit": "communicate",
        "mediate": "communicate",
    }
)
_SANCTION_SEVERITY: Final[Mapping[str, float]] = MappingProxyType(
    {
        "criticism": 0.3,
        "refusal": 0.4,
        "reduced_trust": 0.5,
        "retaliation": 0.7,
        "exclusion": 0.8,
        "restitution": 0.6,
    }
)
_ENFORCEMENT_OUTCOMES: Final[frozenset[str]] = frozenset({"adopted", "effected"})
_ACTIVE_TOKENS: Final[frozenset[str]] = frozenset({"active"})
_RECOGNIZED_TOKENS: Final[frozenset[str]] = frozenset({"recognized"})
_LIVE_RULE_STATUSES: Final[frozenset[FormalRuleStatus]] = frozenset(
    {
        FormalRuleStatus.CANDIDATE,
        FormalRuleStatus.ACTIVE,
        FormalRuleStatus.CONTESTED,
    }
)
_FORBIDDEN_INPUT_SYMBOLS: Final[frozenset[str]] = frozenset(
    {"WorldState", "WorldEvent", "PhysicalRules", "MetricDocument", "AgentCommand"}
)


def _enum_token(value: object) -> str:
    token = getattr(value, "value", value)
    return token if type(token) is str else ""


def _scope_from(
    location_id: object | None, counterpart_id: object | None
) -> FormalRuleScope:
    if location_id is not None:
        return FormalRuleScope(
            FormalRuleScopeKind.PLACE,
            (getattr(location_id, "value", str(location_id)),),
        )
    if counterpart_id is not None:
        return FormalRuleScope(
            FormalRuleScopeKind.PERSON,
            (getattr(counterpart_id, "value", str(counterpart_id)),),
        )
    return FormalRuleScope(FormalRuleScopeKind.UNSPECIFIED, ())


def _reject_forbidden_input(value: object) -> None:
    if value is None:
        return
    if type(value).__name__ in _FORBIDDEN_INPUT_SYMBOLS:
        _fail("formal_rule_forbidden_input")


@dataclass(frozen=True, slots=True)
class _WrittenRecord:
    representation: FormalRuleWrittenRepresentation
    tokens: frozenset[str]


@dataclass(frozen=True, slots=True)
class _RuleCandidate:
    action_token: str
    scope: FormalRuleScope
    constraint: FormalRuleConstraintKind
    authority: FormalRuleAuthorityKind
    stage: FormalRuleStage
    provenance: FormalRuleProvenance
    lineage_ref: str
    tick: int
    sanction_kinds: tuple[FormalRuleSanctionKind, ...]
    actors: tuple[str, ...] = ()


def _collect_written(
    observation: object, artifact_interpretations: object | None
) -> tuple[_WrittenRecord, ...]:
    tokens_by_artifact: dict[str, set[str]] = {}
    if artifact_interpretations is not None:
        interpretations = (
            getattr(artifact_interpretations, "interpretations", ()) or ()
        )
        for interpretation in interpretations:
            artifact = getattr(interpretation, "artifact_id", None)
            artifact_id = getattr(artifact, "value", None)
            if type(artifact_id) is not str:
                continue
            tokens: set[str] = set()
            for mark in getattr(interpretation, "reading_marks", ()) or ():
                if type(mark) is str and mark:
                    tokens.add(mark)
            for relation in getattr(interpretation, "reading_relations", ()) or ():
                for name in ("subject", "predicate", "object"):
                    token = getattr(relation, name, None)
                    if type(token) is str and token:
                        tokens.add(token)
            tokens_by_artifact[artifact_id] = tokens
    records: list[_WrittenRecord] = []
    for artifact in getattr(observation, "artifacts", ()) or ():
        genre = getattr(artifact, "record_genre", None)
        if genre is None:
            continue
        entity_id = getattr(artifact, "entity_id", None)
        artifact_id = getattr(entity_id, "value", None)
        if type(artifact_id) is not str:
            continue
        integrity = getattr(artifact, "integrity", None)
        integrity_token = _enum_token(integrity)
        if integrity is None:
            status = FormalRuleRepresentationStatus.UNKNOWN
        elif integrity_token == "intact":
            status = FormalRuleRepresentationStatus.INTACT
        elif integrity_token in {"damaged", "partially_lost"}:
            status = FormalRuleRepresentationStatus.DAMAGED
        else:
            status = FormalRuleRepresentationStatus.MISSING
        repository = getattr(artifact, "custodian_repository_id", None)
        representation = FormalRuleWrittenRepresentation(
            artifact_id=artifact_id,
            artifact_revision=getattr(artifact, "content_revision", 0),
            genre=_enum_token(genre) or "unknown",
            repository_id=getattr(repository, "value", None),
            status=status,
            tick=getattr(artifact, "created_tick", 0),
        )
        records.append(
            _WrittenRecord(
                representation=representation,
                tokens=frozenset(tokens_by_artifact.get(artifact_id, ())),
            )
        )
    return tuple(sorted(records, key=lambda item: item.representation.artifact_id))


def _sanction_expectation(token: str) -> FormalRuleSanctionKind:
    try:
        return FormalRuleSanctionKind(token)
    except ValueError:
        return FormalRuleSanctionKind.CRITICISM


def _collect_norms(ledger: object | None, tick: int) -> tuple[_RuleCandidate, ...]:
    candidates: list[_RuleCandidate] = []
    for belief in getattr(ledger, "beliefs", ()) or ():
        if _enum_token(getattr(belief, "status", None)) not in _ACTIVE_TOKENS:
            continue
        expectation = _enum_token(getattr(belief, "expectation", None))
        pattern = _enum_token(getattr(belief, "pattern", None))
        action = _NORM_EXPECTATION_ACTIONS.get(
            expectation
        ) or _NORM_PATTERN_ACTIONS.get(pattern)
        if action is None:
            continue
        context = getattr(belief, "context", None)
        scope = _scope_from(
            getattr(context, "location_id", None),
            getattr(context, "counterpart_id", None),
        )
        constraint = (
            FormalRuleConstraintKind.PROHIBITION
            if expectation == "withhold_attack"
            else FormalRuleConstraintKind.OBLIGATION
        )
        sanction = _enum_token(getattr(belief, "chosen_sanction", None))
        sanction_kinds = (
            (_sanction_expectation(sanction),)
            if sanction
            else (FormalRuleSanctionKind.CRITICISM,)
        )
        supporters = getattr(belief, "supporters", ()) or ()
        actors = tuple(
            getattr(supporter, "value", str(supporter)) for supporter in supporters
        )
        candidates.append(
            _RuleCandidate(
                action_token=action,
                scope=scope,
                constraint=constraint,
                authority=FormalRuleAuthorityKind.CUSTOM,
                stage=FormalRuleStage.NORM,
                provenance=FormalRuleProvenance.DERIVED_FROM_NORM,
                lineage_ref=f"norm:{getattr(belief, 'belief_id', '')}",
                tick=tick,
                sanction_kinds=sanction_kinds,
                actors=actors,
            )
        )
    return tuple(candidates)


def _collect_conventions(
    ledger: object | None, tick: int
) -> tuple[_RuleCandidate, ...]:
    candidates: list[_RuleCandidate] = []
    for belief in getattr(ledger, "beliefs", ()) or ():
        if _enum_token(getattr(belief, "status", None)) not in _ACTIVE_TOKENS:
            continue
        content = getattr(belief, "content", None)
        usual_action = getattr(content, "usual_action", None)
        if type(usual_action) is not str:
            continue
        action = _CONVENTION_ACTIONS.get(usual_action)
        if action is None:
            continue
        scope = _scope_from(
            getattr(content, "location_id", None),
            getattr(content, "counterpart_id", None),
        )
        participants = getattr(belief, "participant_ids", ()) or ()
        actors = tuple(
            getattr(participant, "value", str(participant))
            for participant in participants
        )
        candidates.append(
            _RuleCandidate(
                action_token=action,
                scope=scope,
                constraint=FormalRuleConstraintKind.PERMISSION,
                authority=FormalRuleAuthorityKind.CUSTOM,
                stage=FormalRuleStage.HABIT,
                provenance=FormalRuleProvenance.DERIVED_FROM_CONVENTION,
                lineage_ref=f"convention:{getattr(belief, 'belief_id', '')}",
                tick=tick,
                sanction_kinds=(),
                actors=actors,
            )
        )
    return tuple(candidates)


def _collect_authority(
    office_concepts: object | None,
    institution_concepts: object | None,
    organization_concepts: object | None,
    collective_decisions: object | None,
) -> tuple[dict[str, FormalRuleAuthorityKind], tuple[str, ...]]:
    authority_by_action: dict[str, FormalRuleAuthorityKind] = {}
    recognized_actors: list[str] = []

    for concept in getattr(office_concepts, "concepts", ()) or ():
        if _enum_token(getattr(concept, "status", None)) not in _RECOGNIZED_TOKENS:
            continue
        for duty in getattr(concept, "duties", ()) or ():
            action = _DUTY_ACTIONS.get(_enum_token(getattr(duty, "duty_kind", None)))
            if action is not None:
                authority_by_action.setdefault(
                    action, FormalRuleAuthorityKind.OFFICE
                )
        for supporter in getattr(concept, "supporters", ()) or ():
            actor = getattr(supporter, "actor_id", None) or getattr(
                supporter, "supporter_id", None
            )
            actor_token = getattr(actor, "value", None)
            if type(actor_token) is str:
                recognized_actors.append(actor_token)

    for concept in getattr(institution_concepts, "concepts", ()) or ():
        if _enum_token(getattr(concept, "status", None)) not in _RECOGNIZED_TOKENS:
            continue
        if float(getattr(concept, "social_expectation", 0.0) or 0.0) < 0.5:
            continue
        authority_by_action.setdefault(
            "unspecified", FormalRuleAuthorityKind.PROCEDURE
        )

    for concept in getattr(organization_concepts, "concepts", ()) or ():
        for procedure in getattr(concept, "procedures", ()) or ():
            recurrence = int(getattr(procedure, "recurrence", 0) or 0)
            if recurrence < _DEFAULT_POLICY.min_enforcement_recurrence:
                continue
            authority_by_action.setdefault(
                "unspecified", FormalRuleAuthorityKind.PROCEDURE
            )

    for proposal in getattr(collective_decisions, "proposals", ()) or ():
        proposal_ref = getattr(proposal, "proposal_ref", None)
        action = getattr(proposal, "action_token", None)
        if type(action) is not str:
            continue
        for outcome in getattr(collective_decisions, "outcomes", ()) or ():
            if getattr(outcome, "proposal_ref", None) != proposal_ref:
                continue
            if _enum_token(getattr(outcome, "kind", None)) in _ENFORCEMENT_OUTCOMES:
                authority_by_action.setdefault(
                    action, FormalRuleAuthorityKind.COLLECTIVE_DECISION
                )

    return authority_by_action, tuple(sorted(set(recognized_actors)))


def _collect_claims(
    observation: object,
    known_system_ids: frozenset[str],
    tick: int,
) -> tuple[list[tuple[FormalRuleClaim, str]], tuple[str, ...]]:
    from agents.cognition.formal_rule_communication import (
        parse_formal_rule_claim_relation,
    )

    claims: list[tuple[FormalRuleClaim, str]] = []
    orphaned: list[str] = []
    for communication in getattr(observation, "communications", ()) or ():
        utterance = getattr(communication, "utterance", None)
        content = getattr(utterance, "content", None)
        relations = tuple(getattr(content, "relations", ()) or ())
        speaker = getattr(communication, "speaker_id", None)
        speaker_token = getattr(speaker, "value", "")
        for relation in relations:
            claim = parse_formal_rule_claim_relation(
                getattr(relation, "subject", ""),
                getattr(relation, "predicate", ""),
                getattr(relation, "object", ""),
            )
            if claim is None:
                continue
            if claim.system_ref is None or claim.system_ref not in known_system_ids:
                orphaned.append("orphaned_rule_system")
                continue
            claims.append((claim, speaker_token))
    _ = tick
    return claims, tuple(sorted(set(orphaned)))


def _revision_kind(
    prior: FormalRule, stage: FormalRuleStage, recognition: FormalRuleRecognition
) -> FormalRuleRevisionKind:
    if stage is not prior.stage:
        return FormalRuleRevisionKind.STAGE_PROMOTION
    if recognition is not prior.recognition:
        return FormalRuleRevisionKind.RECOGNITION_CHANGE
    return FormalRuleRevisionKind.AUTHORITY_CHANGE


def apply_formal_rule_update(
    owner_id: AgentId,
    tick: int,
    observation: object,
    prior: FormalRuleLedger | None,
    *,
    social_norms: object | None = None,
    social_conventions: object | None = None,
    institution_concepts: object | None = None,
    office_concepts: object | None = None,
    organization_concepts: object | None = None,
    collective_decisions: object | None = None,
    artifact_interpretations: object | None = None,
    policy: FormalRulePolicy | None = None,
) -> FormalRuleLedger:
    """Derive one owner's formal-rule ledger from owner-visible evidence.

    The update reads only the owner observation and prepared owner ledgers. It
    never reads a peer ledger, world state, event store, or command, and it never
    returns or submits a command.
    """

    owner = _require_owner_id(owner_id)
    absolute_tick = _require_tick(tick)
    locked_policy = require_formal_rule_policy(policy)
    _reject_forbidden_input(observation)
    for value in (
        social_norms,
        social_conventions,
        institution_concepts,
        office_concepts,
        organization_concepts,
        collective_decisions,
        artifact_interpretations,
    ):
        _reject_forbidden_input(value)
    if prior is not None:
        require_owner_formal_rules(prior, owner, field_name="prior")
        if prior.policy_version != FORMAL_RULE_POLICY_VERSION:
            _fail("formal_rule_policy_mismatch")

    written = _collect_written(observation, artifact_interpretations)
    authority_by_action, recognized_actors = _collect_authority(
        office_concepts,
        institution_concepts,
        organization_concepts,
        collective_decisions,
    )
    candidates = tuple(
        replace(
            candidate,
            authority=authority_by_action.get(
                candidate.action_token, candidate.authority
            ),
        )
        for candidate in (
            *_collect_norms(social_norms, absolute_tick),
            *_collect_conventions(social_conventions, absolute_tick),
        )
    )

    candidate_systems: dict[tuple[str, str], str] = {}
    for candidate in candidates:
        system_id = formal_rule_system_id(
            owner.value,
            candidate.scope.digest,
            candidate.authority,
        )
        candidate_systems[(candidate.action_token, candidate.scope.digest)] = system_id
    known_systems = frozenset(
        {
            *candidate_systems.values(),
            *(system.system_id for system in (prior.systems if prior else ())),
        }
    )
    claims, orphaned_notices = _collect_claims(
        observation, known_systems, absolute_tick
    )

    prior_rules = {rule.rule_id: rule for rule in (prior.rules if prior else ())}
    grouped: dict[str, list[_RuleCandidate]] = {}
    for candidate in candidates:
        system_id = formal_rule_system_id(
            owner.value, candidate.scope.digest, candidate.authority
        )
        rule_id = formal_rule_id(
            owner.value,
            system_id,
            candidate.constraint,
            candidate.action_token,
            candidate.scope.digest,
        )
        grouped.setdefault(rule_id, []).append(candidate)

    claims_by_rule: dict[str, list[tuple[FormalRuleClaim, str]]] = {}
    for claim, actor in claims:
        if claim.rule_ref is None:
            continue
        claims_by_rule.setdefault(claim.rule_ref, []).append((claim, actor))

    new_rules: list[FormalRule] = []
    system_meta: dict[str, tuple[FormalRuleScope, FormalRuleAuthorityKind]] = {}

    for rule_id, group in sorted(grouped.items()):
        first = group[0]
        system_id = formal_rule_system_id(
            owner.value, first.scope.digest, first.authority
        )
        system_meta[system_id] = (first.scope, first.authority)
        rule_claims = claims_by_rule.get(rule_id, [])
        new_rules.append(
            _materialize_rule(
                owner=owner,
                tick=absolute_tick,
                rule_id=rule_id,
                system_id=system_id,
                group=group,
                prior=prior_rules.get(rule_id),
                claims=rule_claims,
                written=written,
                authority_by_action=authority_by_action,
                recognized_actors=recognized_actors,
                policy=locked_policy,
            )
        )

    for rule_id, rule in sorted(prior_rules.items()):
        if rule_id in grouped:
            continue
        system_meta.setdefault(rule.system_id, (rule.scope, rule.authority))
        new_rules.append(
            _age_or_carry_prior(rule, absolute_tick, locked_policy)
        )

    new_rules.sort(key=lambda rule: rule.rule_id)
    notices: list[str] = list(orphaned_notices)
    if len(new_rules) > locked_policy.max_rules:
        new_rules = new_rules[: locked_policy.max_rules]
        notices.append("formal_rule_truncated")
    new_rules = [
        _trim_rule(rule, locked_policy, notices) for rule in new_rules
    ]

    new_rules = _link_competing(new_rules)
    systems = _materialize_systems(
        owner, new_rules, system_meta, absolute_tick
    )
    notices.extend(
        "contested_system"
        for system in systems
        if system.status is FormalRuleStatus.CONTESTED
    )

    ledger = FormalRuleLedger(
        owner_id=owner,
        systems=tuple(systems),
        rules=tuple(new_rules),
        notices=tuple(notices),
        policy_version=FORMAL_RULE_POLICY_VERSION,
    )
    _LOG.info(
        "formal_rule_update owner=%s rules=%s systems=%s",
        owner.value,
        len(ledger.rules),
        len(ledger.systems),
    )
    return ledger


def _materialize_rule(
    *,
    owner: AgentId,
    tick: int,
    rule_id: str,
    system_id: str,
    group: list[_RuleCandidate],
    prior: FormalRule | None,
    claims: list[tuple[FormalRuleClaim, str]],
    written: tuple[_WrittenRecord, ...],
    authority_by_action: dict[str, FormalRuleAuthorityKind],
    recognized_actors: tuple[str, ...],
    policy: FormalRulePolicy,
) -> FormalRule:
    first = group[0]
    action = first.action_token
    scope = first.scope
    constraint = first.constraint
    stage = max(
        (item.stage for item in group),
        key=lambda item: FORMAL_RULE_STAGE_ORDER[item],
    )
    authority = first.authority
    provenance = first.provenance
    tick_floor = min(item.tick for item in group)
    notices: set[str] = set()

    matching_written = next(
        (
            record.representation
            for record in written
            if record.representation.status
            in (
                FormalRuleRepresentationStatus.INTACT,
                FormalRuleRepresentationStatus.DAMAGED,
            )
            and (
                action in record.tokens
                or scope.digest in record.tokens
                or not record.tokens
            )
        ),
        None,
    )
    if matching_written is not None and stage is FormalRuleStage.HABIT:
        stage = FormalRuleStage.EXPECTATION
    if matching_written is not None and stage is not FormalRuleStage.HABIT:
        stage = max(
            stage,
            FormalRuleStage.DOCUMENTED,
            key=lambda item: FORMAL_RULE_STAGE_ORDER[item],
        )

    if matching_written is None and prior is not None:
        prior_written = prior.versions[-1].written
        if (
            prior_written is not None
            and prior_written.status is not FormalRuleRepresentationStatus.MISSING
        ):
            matching_written = replace(
                prior_written, status=FormalRuleRepresentationStatus.MISSING
            )
            notices.add("representation_missing")

    current_version_count = len(prior.versions) if prior else 0
    if any(
        _enum_token(claim.act) == "amend"
        and claim.revision != current_version_count + 1
        for claim, _ in claims
    ):
        notices.add("formal_rule_version_out_of_order")

    if action in authority_by_action:
        authority = authority_by_action[action]
        provenance = FormalRuleProvenance.AUTHORITY_RECOGNIZED

    supporters = {
        actor
        for claim, actor in claims
        if _enum_token(claim.act) in {"support", "assert", "recognize"}
    }
    challengers = {
        actor
        for claim, actor in claims
        if _enum_token(claim.act) in {"oppose", "challenge"}
    }
    recognize_count = sum(
        1 for claim, _ in claims if _enum_token(claim.act) == "recognize"
    )
    prior_actors = (
        {proponent.actor_id for proponent in prior.proponents} if prior else set()
    )
    actors = (
        prior_actors
        | supporters
        | challengers
        | set(recognized_actors)
        | {actor for item in group for actor in item.actors}
        | {owner.value}
    )
    evidence_refs = {item.lineage_ref for item in group}
    evidence_refs |= {
        f"{claim.act.value}:{claim.system_ref}:{claim.rule_ref}"
        for claim, _ in claims
    }
    if prior is not None:
        evidence_refs |= {
            item.lineage_ref for item in prior.evidence if item.lineage_ref
        }
    recurrence = len(evidence_refs)

    if challengers:
        recognition = FormalRuleRecognition.CONTESTED
    elif (
        action in authority_by_action
        or len(supporters) >= policy.min_supporters_for_recognition
    ):
        recognition = FormalRuleRecognition.RECOGNIZED
    elif stage is FormalRuleStage.HABIT:
        recognition = FormalRuleRecognition.UNRECOGNIZED
    else:
        recognition = FormalRuleRecognition.CLAIMED

    if (
        stage is FormalRuleStage.DOCUMENTED
        and recurrence >= policy.min_enforcement_recurrence
        and len(actors) >= policy.min_supporters_for_recognition
        and (
            action in authority_by_action
            or recognize_count >= policy.min_supporters_for_recognition
        )
    ):
        stage = FormalRuleStage.RECOGNIZED_ENFORCEMENT
        recognition = FormalRuleRecognition.RECOGNIZED
        provenance = FormalRuleProvenance.AUTHORITY_RECOGNIZED

    if (
        prior is not None
        and FORMAL_RULE_STAGE_ORDER[prior.stage]
        > FORMAL_RULE_STAGE_ORDER[stage]
    ):
        stage = prior.stage
        if prior.recognition is FormalRuleRecognition.RECOGNIZED:
            recognition = FormalRuleRecognition.RECOGNIZED

    status = FormalRuleStatus.ACTIVE
    if recognition is FormalRuleRecognition.CONTESTED:
        status = FormalRuleStatus.CONTESTED

    evidence: list[FormalRuleEvidence] = []
    seen_refs: set[str] = set()
    normalized_claims = sorted(claims, key=lambda item: (item[0].act.value, item[1]))
    if prior is not None:
        for item in prior.evidence:
            if item.lineage_ref in seen_refs:
                continue
            if item.lineage_ref is not None:
                seen_refs.add(item.lineage_ref)
            evidence.append(item)
    for candidate in sorted(group, key=lambda entry: entry.lineage_ref):
        if candidate.lineage_ref in seen_refs:
            continue
        seen_refs.add(candidate.lineage_ref)
        evidence.append(
            FormalRuleEvidence(
                evidence_id=formal_rule_evidence_id(
                    rule_id,
                    len(evidence),
                    FormalRuleEvidenceChannel.OBSERVED,
                    candidate.lineage_ref,
                ),
                rule_id=rule_id,
                channel=FormalRuleEvidenceChannel.OBSERVED,
                provenance=candidate.provenance,
                tick=candidate.tick,
                lineage_ref=candidate.lineage_ref,
            )
        )
    for claim, actor in normalized_claims:
        reference = f"{claim.act.value}:{claim.system_ref}:{claim.rule_ref}"
        if reference in seen_refs:
            continue
        seen_refs.add(reference)
        evidence.append(
            FormalRuleEvidence(
                evidence_id=formal_rule_evidence_id(
                    rule_id,
                    len(evidence),
                    FormalRuleEvidenceChannel.COMMUNICATED,
                    reference,
                ),
                rule_id=rule_id,
                channel=FormalRuleEvidenceChannel.COMMUNICATED,
                provenance=FormalRuleProvenance.COMMUNICATED,
                tick=tick,
                source_actor=actor or None,
                claim_ref=reference,
                lineage_ref=reference,
            )
        )

    proponents: list[FormalRuleProponent] = list(prior.proponents) if prior else []
    seen_positions = {proponent.position_id for proponent in proponents}
    for actor, stance in _position_stances(owner, normalized_claims, prior):
        ordinal = len(proponents)
        position = FormalRuleProponent(
            position_id=formal_rule_position_id(
                rule_id, actor, stance, ordinal
            ),
            rule_id=rule_id,
            actor_id=actor,
            stance=stance,
            provenance=FormalRuleProvenance.SELF_AUTHORED
            if actor == owner.value
            else FormalRuleProvenance.COMMUNICATED,
            tick=tick,
            ordinal=ordinal,
        )
        if position.position_id in seen_positions:
            continue
        seen_positions.add(position.position_id)
        proponents.append(position)

    sanctions = _merge_sanctions(
        tuple(prior.sanctions) if prior else (),
        tuple(
            FormalRuleSanctionExpectation(
                kind=kind,
                severity=_SANCTION_SEVERITY.get(kind.value, 0.5),
                source=first.provenance.value,
            )
            for item in group
            for kind in item.sanction_kinds
        ),
        policy,
    )
    exceptions = tuple(prior.exceptions) if prior else ()

    versions = list(prior.versions) if prior else []
    version_scope = scope
    candidate_version = FormalRuleVersion(
        version_id=formal_rule_version_id(
            rule_id,
            len(versions) + 1,
            formal_rule_scope_digest(scope.kind, scope.anchor_ids),
        ),
        rule_id=rule_id,
        version_number=len(versions) + 1,
        stage=stage,
        constraint=constraint,
        authority=authority,
        recognition=recognition,
        scope=version_scope,
        written=matching_written,
        sanction_kinds=tuple(item.kind for item in sanctions),
        exception_ids=tuple(item.exception_id for item in exceptions),
        tick=tick,
        revision_kind=FormalRuleRevisionKind.INITIAL
        if not versions
        else _revision_kind(prior, stage, recognition),  # type: ignore[arg-type]
        supersedes_version_id=versions[-1].version_id if versions else None,
        provenance=provenance,
    )
    if not versions:
        versions.append(candidate_version)
    else:
        assert prior is not None
        if _signature_from_parts(
            prior.stage,
            prior.constraint,
            prior.scope.digest,
            prior.authority,
            prior.recognition,
            prior.versions[-1].written,
            prior.sanctions,
            prior.exceptions,
        ) != _signature_from_parts(
            stage,
            constraint,
            scope.digest,
            authority,
            recognition,
            matching_written,
            sanctions,
            exceptions,
        ):
            versions.append(candidate_version)
            _LOG.debug(
                "formal_rule_version_appended number=%s",
                candidate_version.version_number,
            )

    return FormalRule(
        rule_id=rule_id,
        system_id=system_id,
        owner_id=owner,
        stage=stage,
        constraint=constraint,
        action_token=action,
        scope=scope,
        authority=authority,
        recognition=recognition,
        status=status,
        strength=min(1.0, 0.2 + 0.1 * len(evidence)),
        proponents=tuple(proponents),
        versions=tuple(versions),
        evidence=tuple(evidence),
        sanctions=sanctions,
        exceptions=exceptions,
        responses=tuple(prior.responses) if prior else (),
        first_tick=prior.first_tick if prior else tick_floor,
        last_tick=tick,
        notices=tuple(sorted(notices)),
    )


def _signature_from_parts(
    stage: FormalRuleStage,
    constraint: FormalRuleConstraintKind,
    scope_digest: str,
    authority: FormalRuleAuthorityKind,
    recognition: FormalRuleRecognition,
    written: FormalRuleWrittenRepresentation | None,
    sanctions: tuple[FormalRuleSanctionExpectation, ...],
    exceptions: tuple[FormalRuleException, ...],
) -> tuple[object, ...]:
    return (
        stage.value,
        constraint.value,
        scope_digest,
        authority.value,
        recognition.value,
        None
        if written is None
        else (written.artifact_id, written.artifact_revision, written.status.value),
        tuple(item.kind.value for item in sanctions),
        tuple(item.exception_id for item in exceptions),
    )


def _position_stances(
    owner: AgentId,
    claims: list[tuple[FormalRuleClaim, str]],
    prior: FormalRule | None,
) -> list[tuple[str, FormalRulePositionStance]]:
    derived_owner = owner.value
    if prior is not None and prior.proponents:
        derived_owner = prior.proponents[0].actor_id
    stances: list[tuple[str, FormalRulePositionStance]] = [
        (derived_owner, FormalRulePositionStance.PROPONENT)
    ]
    by_act = {
        "support": FormalRulePositionStance.SUPPORTER,
        "oppose": FormalRulePositionStance.OPPONENT,
        "challenge": FormalRulePositionStance.CHALLENGER,
        "reinterpret": FormalRulePositionStance.REINTERPRETER,
        "amend": FormalRulePositionStance.AMENDER,
        "withdraw": FormalRulePositionStance.WITHDRAWER,
    }
    for claim, actor in claims:
        stance = by_act.get(_enum_token(claim.act))
        if stance is not None and actor:
            stances.append((actor, stance))
    return stances


def _merge_sanctions(
    prior: tuple[FormalRuleSanctionExpectation, ...],
    fresh: tuple[FormalRuleSanctionExpectation, ...],
    policy: FormalRulePolicy,
) -> tuple[FormalRuleSanctionExpectation, ...]:
    merged: dict[tuple[str, str], FormalRuleSanctionExpectation] = {
        (item.kind.value, item.source): item for item in prior
    }
    for item in fresh:
        merged.setdefault((item.kind.value, item.source), item)
    ordered = tuple(
        sorted(
            merged.values(),
            key=lambda item: (item.kind.value, item.source, -item.severity),
        )
    )
    return ordered[: policy.max_sanctions_per_rule]


def _age_or_carry_prior(
    rule: FormalRule, tick: int, policy: FormalRulePolicy
) -> FormalRule:
    if (
        rule.status in _LIVE_RULE_STATUSES
        and tick - rule.last_tick >= policy.version_window_ticks
    ):
        version = FormalRuleVersion(
            version_id=formal_rule_version_id(
                rule.rule_id,
                len(rule.versions) + 1,
                formal_rule_scope_digest(rule.scope.kind, rule.scope.anchor_ids),
            ),
            rule_id=rule.rule_id,
            version_number=len(rule.versions) + 1,
            stage=rule.stage,
            constraint=rule.constraint,
            authority=rule.authority,
            recognition=rule.recognition,
            scope=rule.scope,
            written=rule.versions[-1].written,
            sanction_kinds=tuple(item.kind for item in rule.sanctions),
            exception_ids=tuple(item.exception_id for item in rule.exceptions),
            tick=tick,
            revision_kind=FormalRuleRevisionKind.RETIREMENT,
            supersedes_version_id=rule.versions[-1].version_id,
            provenance=FormalRuleProvenance.EXPIRED,
        )
        return FormalRule(
            rule_id=rule.rule_id,
            system_id=rule.system_id,
            owner_id=rule.owner_id,
            stage=rule.stage,
            constraint=rule.constraint,
            action_token=rule.action_token,
            scope=rule.scope,
            authority=rule.authority,
            recognition=rule.recognition,
            status=FormalRuleStatus.RETIRED,
            strength=rule.strength,
            proponents=rule.proponents,
            versions=(*rule.versions, version),
            evidence=rule.evidence,
            sanctions=rule.sanctions,
            exceptions=rule.exceptions,
            responses=rule.responses,
            first_tick=rule.first_tick,
            last_tick=rule.last_tick,
            notices=tuple(sorted({*rule.notices, "expired"})),
        )
    return rule


def _trim_rule(
    rule: FormalRule, policy: FormalRulePolicy, notices: list[str]
) -> FormalRule:
    evidence = rule.evidence
    proponents = rule.proponents
    responses = rule.responses
    exceptions = rule.exceptions
    if len(evidence) > policy.max_evidence_per_rule:
        evidence = evidence[: policy.max_evidence_per_rule]
        notices.append("formal_rule_truncated")
    if len(proponents) > policy.max_positions_per_rule:
        proponents = proponents[: policy.max_positions_per_rule]
        notices.append("formal_rule_truncated")
    if len(responses) > policy.max_responses_per_rule:
        responses = responses[: policy.max_responses_per_rule]
        notices.append("formal_rule_truncated")
    if len(exceptions) > policy.max_exceptions_per_rule:
        exceptions = exceptions[: policy.max_exceptions_per_rule]
        notices.append("formal_rule_truncated")
    if len(rule.versions) > policy.max_versions_per_rule:
        # Keep the initial version and the most recent window. The ledger requires
        # contiguous numbering, so trimming versions is a bounded refusal: the
        # update keeps the last accepted version and notices truncation instead.
        notices.append("formal_rule_truncated")
    if (
        evidence is rule.evidence
        and proponents is rule.proponents
        and responses is rule.responses
        and exceptions is rule.exceptions
    ):
        return rule
    return FormalRule(
        rule_id=rule.rule_id,
        system_id=rule.system_id,
        owner_id=rule.owner_id,
        stage=rule.stage,
        constraint=rule.constraint,
        action_token=rule.action_token,
        scope=rule.scope,
        authority=rule.authority,
        recognition=rule.recognition,
        status=rule.status,
        strength=rule.strength,
        proponents=proponents,
        versions=rule.versions,
        evidence=evidence,
        sanctions=rule.sanctions,
        exceptions=exceptions,
        responses=responses,
        first_tick=rule.first_tick,
        last_tick=rule.last_tick,
        notices=rule.notices,
    )


def _materialize_systems(
    owner: AgentId,
    rules: list[FormalRule],
    system_meta: dict[str, tuple[FormalRuleScope, FormalRuleAuthorityKind]],
    tick: int,
    *,
    previous: tuple[FormalRuleSystem, ...] = (),
) -> tuple[FormalRuleSystem, ...]:
    previous_by_id = {system.system_id: system for system in previous}
    by_system: dict[str, list[FormalRule]] = {}
    for rule in rules:
        by_system.setdefault(rule.system_id, []).append(rule)
    competing: dict[str, set[str]] = {system_id: set() for system_id in by_system}
    for index, left in enumerate(rules):
        for right in rules[index + 1 :]:
            if left.system_id == right.system_id:
                continue
            if (
                left.scope.digest != right.scope.digest
                or left.action_token != right.action_token
            ):
                continue
            if (
                left.constraint is right.constraint
                and left.authority is right.authority
            ):
                continue
            competing[left.system_id].add(right.system_id)
            competing[right.system_id].add(left.system_id)
    systems: list[FormalRuleSystem] = []
    for system_id in sorted(by_system):
        members = by_system[system_id]
        prior_system = previous_by_id.get(system_id)
        scope, authority = system_meta.get(
            system_id,
            (
                prior_system.scope if prior_system else members[0].scope,
                prior_system.authority
                if prior_system
                else members[0].authority,
            ),
        )
        status = FormalRuleStatus.ACTIVE
        if any(rule.status is FormalRuleStatus.CONTESTED for rule in members):
            status = FormalRuleStatus.CONTESTED
        systems.append(
            FormalRuleSystem(
                system_id=system_id,
                owner_id=owner,
                scope=scope,
                authority=authority,
                status=status,
                proponent_ids=tuple(
                    sorted(
                        {
                            proponent.actor_id
                            for rule in members
                            for proponent in rule.proponents
                        }
                    )
                ),
                rule_ids=tuple(sorted(rule.rule_id for rule in members)),
                competing_system_ids=tuple(
                    sorted(competing.get(system_id, ()))
                ),
                first_tick=prior_system.first_tick
                if prior_system
                else min(rule.first_tick for rule in members),
                last_tick=tick,
            )
        )
    return tuple(systems)


def _link_competing(rules: list[FormalRule]) -> list[FormalRule]:
    signatures: dict[tuple[str, str], list[FormalRule]] = {}
    for rule in rules:
        signatures.setdefault((rule.scope.digest, rule.action_token), []).append(rule)
    contested_ids: set[str] = set()
    for group in signatures.values():
        if len(group) < 2:
            continue
        for rule in group:
            if any(
                other.rule_id != rule.rule_id
                and (
                    other.constraint is not rule.constraint
                    or other.authority is not rule.authority
                )
                for other in group
            ):
                contested_ids.add(rule.rule_id)
    if not contested_ids:
        return rules
    linked: list[FormalRule] = []
    for rule in rules:
        if rule.rule_id not in contested_ids:
            linked.append(rule)
            continue
        linked.append(
            FormalRule(
                rule_id=rule.rule_id,
                system_id=rule.system_id,
                owner_id=rule.owner_id,
                stage=rule.stage,
                constraint=rule.constraint,
                action_token=rule.action_token,
                scope=rule.scope,
                authority=rule.authority,
                recognition=FormalRuleRecognition.CONTESTED,
                status=FormalRuleStatus.CONTESTED,
                strength=rule.strength,
                proponents=rule.proponents,
                versions=rule.versions,
                evidence=rule.evidence,
                sanctions=rule.sanctions,
                exceptions=rule.exceptions,
                responses=rule.responses,
                first_tick=rule.first_tick,
                last_tick=rule.last_tick,
                notices=tuple(sorted({*rule.notices, "contested_system"})),
            )
        )
    return linked


def _rebuild_ledger(
    ledger: FormalRuleLedger,
    rules: list[FormalRule],
    notices: tuple[str, ...] = (),
) -> FormalRuleLedger:
    by_system: dict[str, list[FormalRule]] = {}
    for rule in rules:
        by_system.setdefault(rule.system_id, []).append(rule)
    systems: list[FormalRuleSystem] = []
    for system in ledger.systems:
        members = by_system.get(system.system_id, [])
        status = (
            FormalRuleStatus.CONTESTED
            if any(rule.status is FormalRuleStatus.CONTESTED for rule in members)
            else system.status
        )
        systems.append(
            replace(
                system,
                status=status,
                rule_ids=tuple(sorted(rule.rule_id for rule in members)),
            )
        )
    return FormalRuleLedger(
        owner_id=ledger.owner_id,
        systems=tuple(systems),
        rules=tuple(sorted(rules, key=lambda rule: rule.rule_id)),
        notices=tuple(sorted({*ledger.notices, *notices})),
        policy_version=ledger.policy_version,
    )


def _find_rule(ledger: FormalRuleLedger, rule_id: object) -> FormalRule | None:
    for rule in ledger.rules:
        if rule.rule_id == rule_id:
            return rule
    return None


def _append_position(
    rule: FormalRule,
    *,
    tick: int,
    stance: FormalRulePositionStance,
    provenance: FormalRuleProvenance,
    policy: FormalRulePolicy,
    actor_id: str,
) -> tuple[FormalRule, bool]:
    ordinal = len(rule.proponents)
    position = FormalRuleProponent(
        position_id=formal_rule_position_id(
            rule.rule_id, actor_id, stance, ordinal
        ),
        rule_id=rule.rule_id,
        actor_id=actor_id,
        stance=stance,
        provenance=provenance,
        tick=tick,
        ordinal=ordinal,
    )
    if any(item.position_id == position.position_id for item in rule.proponents):
        return rule, False
    proponents = (*rule.proponents, position)
    if len(proponents) > policy.max_positions_per_rule:
        proponents = proponents[-policy.max_positions_per_rule:]
        return (
            replace(
                rule,
                proponents=proponents,
                notices=tuple(sorted({*rule.notices, "cap_exceeded"})),
            ),
            True,
        )
    return replace(rule, proponents=proponents), True


def _append_rule_version(
    rule: FormalRule,
    *,
    tick: int,
    revision_kind: FormalRuleRevisionKind,
    provenance: FormalRuleProvenance,
    recognition: FormalRuleRecognition | None = None,
    status: FormalRuleStatus | None = None,
    exceptions: tuple[FormalRuleException, ...] | None = None,
    notices: tuple[str, ...] = (),
    force: bool = False,
) -> FormalRule:
    new_recognition = rule.recognition if recognition is None else recognition
    new_status = rule.status if status is None else status
    new_exceptions = rule.exceptions if exceptions is None else exceptions
    if (
        not force
        and new_recognition is rule.recognition
        and new_status is rule.status
        and len(new_exceptions) == len(rule.exceptions)
        and all(
            left.exception_id == right.exception_id
            for left, right in zip(new_exceptions, rule.exceptions, strict=True)
        )
    ):
        return rule
    version = FormalRuleVersion(
        version_id=formal_rule_version_id(
            rule.rule_id,
            len(rule.versions) + 1,
            formal_rule_scope_digest(rule.scope.kind, rule.scope.anchor_ids),
        ),
        rule_id=rule.rule_id,
        version_number=len(rule.versions) + 1,
        stage=rule.stage,
        constraint=rule.constraint,
        authority=rule.authority,
        recognition=new_recognition,
        scope=rule.scope,
        written=rule.versions[-1].written,
        sanction_kinds=tuple(item.kind for item in rule.sanctions),
        exception_ids=tuple(item.exception_id for item in new_exceptions),
        tick=tick,
        revision_kind=revision_kind,
        supersedes_version_id=rule.versions[-1].version_id,
        provenance=provenance,
    )
    return replace(
        rule,
        recognition=new_recognition,
        status=new_status,
        exceptions=new_exceptions,
        versions=(*rule.versions, version),
        notices=tuple(sorted({*rule.notices, *notices})),
    )


def generate_formal_rule_position(
    ledger: FormalRuleLedger,
    *,
    tick: int,
    rule_id: str,
    policy: FormalRulePolicy,
) -> FormalRuleLedger:
    """Append the owner's deterministic position for one rule belief."""

    if type(ledger) is not FormalRuleLedger:
        raise TypeError("ledger must be FormalRuleLedger")
    locked = require_formal_rule_policy(policy)
    absolute_tick = _require_tick(tick)
    rule = _find_rule(ledger, require_formal_rule_id(rule_id))
    if rule is None:
        return ledger
    stance = (
        FormalRulePositionStance.SUPPORTER
        if rule.versions[-1].provenance
        is FormalRuleProvenance.AUTHORITY_RECOGNIZED
        else FormalRulePositionStance.PROPONENT
    )
    updated, _ = _append_position(
        rule,
        tick=absolute_tick,
        stance=stance,
        provenance=FormalRuleProvenance.SELF_AUTHORED,
        policy=locked,
        actor_id=ledger.owner_id.value,
    )
    if updated is rule:
        return ledger
    rules = [
        updated if item.rule_id == rule.rule_id else item for item in ledger.rules
    ]
    return _rebuild_ledger(ledger, rules)


def appraise_formal_rule_position(
    ledger: FormalRuleLedger,
    *,
    tick: int,
    claim: object,
    policy: FormalRulePolicy,
) -> FormalRuleLedger:
    """Append the owner's appraisal of one newly delivered claim."""

    from agents.cognition.formal_rule_communication import FormalRuleClaim

    if type(ledger) is not FormalRuleLedger:
        raise TypeError("ledger must be FormalRuleLedger")
    if type(claim) is not FormalRuleClaim:
        raise TypeError("claim must be FormalRuleClaim")
    locked = require_formal_rule_policy(policy)
    absolute_tick = _require_tick(tick)
    if claim.rule_ref is None:
        return ledger
    rule = _find_rule(ledger, claim.rule_ref)
    if rule is None:
        return _rebuild_ledger(
            ledger, list(ledger.rules), ("orphaned_rule_system",)
        )
    act = _enum_token(claim.act)
    updated = rule
    notices: tuple[str, ...] = ()
    if act == "support":
        updated, _ = _append_position(
            updated,
            tick=absolute_tick,
            stance=FormalRulePositionStance.SUPPORTER,
            provenance=FormalRuleProvenance.COMMUNICATED,
            policy=locked,
            actor_id=ledger.owner_id.value,
        )
    elif act in {"oppose", "challenge"}:
        stance = (
            FormalRulePositionStance.OPPONENT
            if act == "oppose"
            else FormalRulePositionStance.CHALLENGER
        )
        updated, _ = _append_position(
            updated,
            tick=absolute_tick,
            stance=stance,
            provenance=FormalRuleProvenance.COMMUNICATED,
            policy=locked,
            actor_id=ledger.owner_id.value,
        )
        updated = _append_rule_version(
            updated,
            tick=absolute_tick,
            revision_kind=FormalRuleRevisionKind.RECOGNITION_CHANGE,
            provenance=FormalRuleProvenance.CONTESTED,
            recognition=FormalRuleRecognition.CONTESTED,
            status=FormalRuleStatus.CONTESTED,
            notices=("contested_system",),
        )
        notices = ("contested_system",)
    elif act == "reinterpret":
        updated, _ = _append_position(
            updated,
            tick=absolute_tick,
            stance=FormalRulePositionStance.REINTERPRETER,
            provenance=FormalRuleProvenance.COMMUNICATED,
            policy=locked,
            actor_id=ledger.owner_id.value,
        )
        updated = _append_rule_version(
            updated,
            tick=absolute_tick,
            revision_kind=FormalRuleRevisionKind.REINTERPRETATION,
            provenance=FormalRuleProvenance.REINTERPRETATION,
            force=True,
        )
    elif act == "amend":
        if claim.revision != len(rule.versions) + 1:
            notices = ("formal_rule_version_out_of_order",)
        else:
            updated = _append_rule_version(
                updated,
                tick=absolute_tick,
                revision_kind=FormalRuleRevisionKind.AMENDMENT,
                provenance=FormalRuleProvenance.AMENDMENT,
                force=True,
            )
    elif act == "withdraw":
        updated, _ = _append_position(
            updated,
            tick=absolute_tick,
            stance=FormalRulePositionStance.WITHDRAWER,
            provenance=FormalRuleProvenance.COMMUNICATED,
            policy=locked,
            actor_id=ledger.owner_id.value,
        )
        if updated.recognition is FormalRuleRecognition.RECOGNIZED:
            updated = _append_rule_version(
                updated,
                tick=absolute_tick,
                revision_kind=FormalRuleRevisionKind.RECOGNITION_CHANGE,
                provenance=FormalRuleProvenance.COMMUNICATED,
                recognition=FormalRuleRecognition.CLAIMED,
            )
    elif act == "report":
        report_kind = _enum_token(claim.report_kind)
        if report_kind == "exemption":
            exception = FormalRuleException(
                exception_id=formal_rule_exception_id(
                    rule.rule_id, len(rule.exceptions), rule.scope.digest
                ),
                rule_id=rule.rule_id,
                condition_digest=rule.scope.digest,
                reason=FormalRuleExceptionReason.UNKNOWN,
                scope=rule.scope,
                evidence_ref=claim.rule_ref,
                tick=absolute_tick,
            )
            exceptions = tuple(
                sorted(
                    {*rule.exceptions, exception},
                    key=lambda item: item.exception_id,
                )
            )[: locked.max_exceptions_per_rule]
            updated = _append_rule_version(
                updated,
                tick=absolute_tick,
                revision_kind=FormalRuleRevisionKind.EXCEPTION_CHANGE,
                provenance=FormalRuleProvenance.COMMUNICATED,
                exceptions=exceptions,
            )
    if updated is rule:
        if not notices:
            return ledger
        annotated = replace(
            rule, notices=tuple(sorted({*rule.notices, *notices}))
        )
        rules = [
            annotated if item.rule_id == rule.rule_id else item
            for item in ledger.rules
        ]
        return _rebuild_ledger(ledger, rules, notices)
    if notices:
        updated = replace(
            updated,
            notices=tuple(sorted({*updated.notices, *notices})),
        )
    rules = [
        updated if item.rule_id == rule.rule_id else item for item in ledger.rules
    ]
    return _rebuild_ledger(ledger, rules, notices)


_RESPONSE_PENALTY: Final[Mapping[str, float]] = MappingProxyType(
    {
        "follow": 0.0,
        "ignore": 0.05,
        "reinterpret": 0.05,
        "challenge": 0.1,
        "violate": 0.2,
    }
)


def select_formal_rule_response(
    ledger: FormalRuleLedger,
    *,
    tick: int,
    action_token: str,
    policy: FormalRulePolicy,
    plan_action_tokens: Sequence[str] = (),
) -> tuple[FormalRuleLedger, FormalRuleResponse | None]:
    """Choose one declared owner response for an existing action token.

    The selector returns a record only. It never constructs, suppresses, or
    rewrites a command and never decides physical possibility.
    """

    if type(ledger) is not FormalRuleLedger:
        raise TypeError("ledger must be FormalRuleLedger")
    locked = require_formal_rule_policy(policy)
    absolute_tick = _require_tick(tick)
    if action_token not in FORMAL_RULE_ACTION_TOKENS:
        _fail("formal_rule_action_invalid")
    matches = tuple(
        rule for rule in ledger.rules if rule.action_token == action_token
    )
    if not matches:
        return ledger, None
    rule = min(matches, key=lambda item: item.rule_id)
    opponent = any(
        proponent.stance
        in (
            FormalRulePositionStance.OPPONENT,
            FormalRulePositionStance.CHALLENGER,
        )
        for proponent in rule.proponents
    )
    written = rule.versions[-1].written
    if rule.recognition is FormalRuleRecognition.RECOGNIZED and (
        rule.status is not FormalRuleStatus.CONTESTED
    ):
        kind = FormalRuleResponseKind.FOLLOW
    elif opponent and action_token in plan_action_tokens:
        kind = FormalRuleResponseKind.VIOLATE
    elif rule.status is FormalRuleStatus.CONTESTED and opponent:
        kind = FormalRuleResponseKind.CHALLENGE
    elif written is not None and written.status in (
        FormalRuleRepresentationStatus.DAMAGED,
        FormalRuleRepresentationStatus.MISSING,
    ):
        kind = FormalRuleResponseKind.REINTERPRET
    else:
        kind = FormalRuleResponseKind.IGNORE
    response = FormalRuleResponse(
        response_id=formal_rule_response_id(
            rule.rule_id, ledger.owner_id.value, kind, absolute_tick
        ),
        rule_id=rule.rule_id,
        actor_id=ledger.owner_id.value,
        kind=kind,
        tick=absolute_tick,
        provenance=FormalRuleProvenance.SELF_AUTHORED,
    )
    responses = (*rule.responses, response)
    if len(responses) > locked.max_responses_per_rule:
        ordered = sorted(
            responses, key=lambda item: (item.tick, item.response_id)
        )
        responses = tuple(ordered[-locked.max_responses_per_rule :])
        notices = tuple(sorted({*rule.notices, "cap_exceeded"}))
    else:
        notices = rule.notices
    updated = replace(rule, responses=responses, notices=notices)
    rules = [
        updated if item.rule_id == rule.rule_id else item for item in ledger.rules
    ]
    _LOG.info("formal_rule_response kind=%s", kind.value)
    return _rebuild_ledger(ledger, rules), response


def formal_rule_direction_preference(
    ledger: FormalRuleLedger, *, action_token: str
) -> float:
    """Return a weak bounded bias for existing plan candidates."""

    if type(ledger) is not FormalRuleLedger:
        raise TypeError("ledger must be FormalRuleLedger")
    if action_token not in FORMAL_RULE_ACTION_TOKENS:
        _fail("formal_rule_action_invalid")
    score = 0.0
    for rule in ledger.rules:
        if rule.action_token != action_token:
            continue
        if rule.recognition is FormalRuleRecognition.RECOGNIZED:
            score += 0.15
        elif rule.recognition is FormalRuleRecognition.CONTESTED:
            score -= 0.1
        if rule.constraint is FormalRuleConstraintKind.OBLIGATION:
            score += 0.05
        elif rule.constraint is FormalRuleConstraintKind.PROHIBITION:
            score -= 0.2
        elif rule.constraint is FormalRuleConstraintKind.PERMISSION:
            score += 0.05
    return max(-0.25, min(0.25, round(score, 6)))


def formal_rule_response_penalties(
    ledger: FormalRuleLedger, *, tick: int
) -> Mapping[str, float]:
    """Return bounded penalties keyed by rule id for existing futures."""

    if type(ledger) is not FormalRuleLedger:
        raise TypeError("ledger must be FormalRuleLedger")
    absolute_tick = _require_tick(tick)
    penalties: dict[str, float] = {}
    for rule in ledger.rules:
        recent = [
            response
            for response in rule.responses
            if 0 <= absolute_tick - response.tick <= 8
        ]
        if not recent:
            continue
        latest = max(recent, key=lambda item: (item.tick, item.response_id))
        magnitude = _RESPONSE_PENALTY.get(latest.kind.value, 0.0)
        if magnitude > 0.0:
            penalties[rule.rule_id] = min(0.25, magnitude)
    return MappingProxyType(penalties)


def _canonical_value(value: object) -> object:
    if is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: _canonical_value(getattr(value, field.name))
            for field in fields(value)
        }
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, AgentId):
        return value.value
    if isinstance(value, (tuple, list)):
        return [_canonical_value(item) for item in value]
    if isinstance(value, float):
        return float(Decimal(str(value)).quantize(_QUANTUM, rounding=ROUND_HALF_UP))
    return value


def formal_rule_ledger_digest(ledger: object) -> str:
    """Return the canonical content digest of one formal-rule ledger."""

    if type(ledger) is not FormalRuleLedger:
        raise TypeError("formal_rule_ledger_digest requires FormalRuleLedger")
    payload = json.dumps(
        _canonical_value(ledger),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


__all__ = [
    "FORMAL_RULE_ERROR_CODES",
    "FORMAL_RULE_EVIDENCE_ID_PREFIX",
    "FORMAL_RULE_EVIDENCE_NAMESPACE",
    "FORMAL_RULE_EXCEPTION_ID_PREFIX",
    "FORMAL_RULE_EXCEPTION_NAMESPACE",
    "FORMAL_RULE_FORBIDDEN_FIELD_NAMES",
    "FORMAL_RULE_ID_HEX_LEN",
    "FORMAL_RULE_ID_PREFIX",
    "FORMAL_RULE_NAMESPACE",
    "FORMAL_RULE_NOTICE_CODES",
    "FORMAL_RULE_POLICY_VERSION",
    "FORMAL_RULE_POSITION_ID_PREFIX",
    "FORMAL_RULE_POSITION_NAMESPACE",
    "FORMAL_RULE_RESPONSE_ID_PREFIX",
    "FORMAL_RULE_RESPONSE_NAMESPACE",
    "FORMAL_RULE_SCOPE_NAMESPACE",
    "FORMAL_RULE_STAGE_ORDER",
    "FORMAL_RULE_SYSTEM_ID_PREFIX",
    "FORMAL_RULE_SYSTEM_NAMESPACE",
    "FORMAL_RULE_VERSION_ID_PREFIX",
    "FORMAL_RULE_VERSION_NAMESPACE",
    "FormalRule",
    "FormalRuleAuthorityKind",
    "FormalRuleConstraintKind",
    "FormalRuleError",
    "FormalRuleEvidence",
    "FormalRuleEvidenceChannel",
    "FormalRuleException",
    "FormalRuleExceptionReason",
    "FormalRuleLedger",
    "FormalRulePolicy",
    "FormalRulePositionStance",
    "FormalRuleProponent",
    "FormalRuleProvenance",
    "FormalRuleRecognition",
    "FormalRuleReportKind",
    "FormalRuleRepresentationStatus",
    "FormalRuleResponse",
    "FormalRuleResponseKind",
    "FormalRuleRevisionKind",
    "FormalRuleSanctionExpectation",
    "FormalRuleSanctionKind",
    "FormalRuleScope",
    "FormalRuleScopeKind",
    "FormalRuleStage",
    "FormalRuleStatus",
    "FormalRuleSystem",
    "FormalRuleVersion",
    "FormalRuleWrittenRepresentation",
    "default_formal_rule_policy",
    "empty_formal_rule_ledger",
    "formal_rule_evidence_id",
    "formal_rule_exception_id",
    "formal_rule_id",
    "formal_rule_ledger_digest",
    "formal_rule_position_id",
    "formal_rule_response_id",
    "formal_rule_scope_digest",
    "formal_rule_system_id",
    "formal_rule_version_id",
    "require_formal_rule_evidence_id",
    "require_formal_rule_exception_id",
    "require_formal_rule_id",
    "require_formal_rule_policy",
    "require_formal_rule_position_id",
    "require_formal_rule_response_id",
    "require_formal_rule_system_id",
    "require_formal_rule_version_id",
    "require_owner_formal_rules",
]
