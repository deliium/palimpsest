"""Owner-scoped subjective collective decisions.

A collective decision is one owner's revisable, locally understood course of
action. It is never a world permission, a binding plan, a canonical electorate,
a vote tally, or an authoritative leader. Owners learn about proposals only
through their own observations, memories, and delivered testimony.

Updates read only one owner's ``Observation``, the owner-safe identity
projection, the previous ``CollectiveDecisionLedger``, and prepared owner-local
cognition inputs. They never read ``WorldState``, ``WorldEvent``, another
owner's ledger, or analysis rows.
"""

from __future__ import annotations

import hashlib
import logging
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, fields
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum
from typing import Final, cast

from agents.cognition.models import ActionDirection, OwnerSafeSocialIdentity
from agents.models import AgentId
from world.identifiers import EntityId, require_exact_nonneg_int
from world.observations import Observation

__all__ = [
    "COLLECTIVE_DECISION_POLICY_VERSION",
    "FORBIDDEN_COLLECTIVE_DECISION_FIELD_NAMES",
    "CollectiveAct",
    "CollectiveCompliance",
    "CollectiveComplianceStatus",
    "CollectiveDecisionBiasAudit",
    "CollectiveDecisionLedger",
    "CollectiveDecisionPolicy",
    "CollectiveDecisionPreference",
    "CollectiveDelegation",
    "CollectiveEvidence",
    "CollectiveEvidenceChannel",
    "CollectiveExecutionStatus",
    "CollectiveInfluence",
    "CollectiveInfluenceKind",
    "CollectiveOutcome",
    "CollectiveOutcomeKind",
    "CollectivePosition",
    "CollectivePositionStance",
    "CollectiveProposal",
    "CollectiveProposalStatus",
    "CollectiveRetraction",
    "CollectiveTopic",
    "append_collective_decision_influence",
    "apply_collective_decision_update",
    "appraise_collective_compliance",
    "classify_collective_decision_influence",
    "collective_context_key",
    "collective_decision_direction_preference",
    "collective_decision_evidence_id",
    "collective_decision_preference",
    "collective_decision_topic_direction",
    "collective_proposal_id",
    "collective_proposal_ref",
    "create_collective_proposal",
    "default_collective_decision_policy",
    "empty_collective_decision_ledger",
    "generate_collective_decision_proposal",
    "require_owner_collective_decisions",
]

_LOG: Final[logging.Logger] = logging.getLogger("agents.cognition.collective_decisions")

COLLECTIVE_DECISION_POLICY_VERSION: Final[str] = "collective-decisions.v1"
_QUANTUM: Final[Decimal] = Decimal("0.000001")
_HEX: Final[frozenset[str]] = frozenset("0123456789abcdef")
_DIGEST_LEN: Final[int] = 16

_MAX_PROPOSALS: Final[int] = 16
_MAX_POSITIONS: Final[int] = 32
_MAX_DELEGATIONS: Final[int] = 16
_MAX_RETRACTIONS: Final[int] = 16
_MAX_OUTCOMES: Final[int] = 32
_MAX_COMPLIANCE: Final[int] = 32
_MAX_INFLUENCE: Final[int] = 32
_MAX_EVIDENCE: Final[int] = 32
_MAX_REVISIONS: Final[int] = 8
_MAX_TERMS: Final[int] = 8
_MAX_NOTICES: Final[int] = 16
_DEFAULT_PROPOSAL_WINDOW: Final[int] = 8
_MAX_PROPOSAL_WINDOW: Final[int] = 32
_EVIDENCE_RETENTION: Final[int] = 64
_REFERENCE_FRESHNESS: Final[int] = 32
_DEDUP_RETENTION: Final[int] = 64
_DECAY: Final[float] = 0.03

_NOTICE_REASONS: Final[frozenset[str]] = frozenset(
    {
        "cap_exceeded",
        "unsupported_evidence",
        "duplicate_evidence",
        "foreign_owner",
        "invalid_token",
        "unknown_proposal",
        "ambiguous_reference",
        "expired_reference",
        "retired_reference",
        "stale_reference",
        "self_endorsement",
        "self_delegation",
        "duplicate_root",
        "unresolved_entity",
        "unsupported_action",
    }
)

_FORBIDDEN_TYPES: Final[frozenset[str]] = frozenset(
    {
        "MetricDocument",
        "MetricComputationInputs",
        "CollectiveDecisionRow",
        "CollectiveDecisionDisagreementRow",
        "CollectiveDecisionProcessRow",
        "CollectiveDecisionOutcomeRow",
    }
)

FORBIDDEN_COLLECTIVE_DECISION_FIELD_NAMES: Final[frozenset[str]] = frozenset(
    {
        "government",
        "election",
        "electorate",
        "vote",
        "voting_weight",
        "quorum",
        "majority",
        "legitimacy",
        "binding",
        "winner",
        "law",
        "tax",
        "police",
        "court",
        "political_party",
        "institution_type",
        "authoritative_leader",
        "current_decision",
    }
)


class CollectiveAct(StrEnum):
    """Closed speech acts over an identified proposal revision."""

    PROPOSE = "propose"
    SUPPORT = "support"
    OPPOSE = "oppose"
    DELEGATE = "delegate"
    WITHDRAW_SUPPORT = "withdraw_support"
    COORDINATE = "coordinate"


class CollectiveTopic(StrEnum):
    """Subject matter, never a government type or jurisdiction."""

    COLLECTIVE_PROJECT = "collective_project"
    RESOURCE_ALLOCATION = "resource_allocation"
    MIGRATION = "migration"
    SHARED_DEFENSE = "shared_defense"
    STORAGE = "storage"
    NORM_ENFORCEMENT = "norm_enforcement"


class CollectiveEvidenceChannel(StrEnum):
    """Closed provenance for one item of decision evidence."""

    OBSERVED = "observed"
    COMMUNICATED = "communicated"
    REMEMBERED = "remembered"


class CollectiveProposalStatus(StrEnum):
    """Closed lifecycle for one local proposal revision."""

    DRAFT = "draft"
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    EXPIRED = "expired"
    RETIRED = "retired"
    ABANDONED = "abandoned"


class CollectivePositionStance(StrEnum):
    """One actor's expressed stance, never an obligation."""

    SUPPORT = "support"
    OPPOSE = "oppose"
    DELEGATE = "delegate"
    WITHDRAW = "withdraw"


class CollectiveExecutionStatus(StrEnum):
    """Whether a proposed term has an executable adapter or a known effect."""

    UNSUPPORTED_ACTION = "unsupported_action"
    UNKNOWN = "unknown"
    ATTEMPTED = "attempted"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


class CollectiveOutcomeKind(StrEnum):
    """Closed claimed / observed course outcomes."""

    CLAIMED = "claimed"
    ADOPTED = "adopted"
    ATTEMPTED = "attempted"
    EFFECTED = "effected"
    WITHDRAWN = "withdrawn"
    ABANDONED = "abandoned"
    EXPIRED = "expired"
    DISPUTED = "disputed"
    UNKNOWN = "unknown"


class CollectiveComplianceStatus(StrEnum):
    """Descriptive match between an actor-scoped course and observable action."""

    MATCHED = "matched"
    CONTRARY = "contrary"
    BLOCKED = "blocked"
    UNKNOWN = "unknown"


class CollectiveInfluenceKind(StrEnum):
    """Local algorithmic attribution, never a claim of real-world causation."""

    PREFERENCE_CHANGED = "preference_changed"
    FINAL_COMMAND_CHANGED = "final_command_changed"
    EXECUTED = "executed"
    UNAVAILABLE = "unavailable"


def _fail(field_name: str, code: str) -> ValueError:
    _LOG.error(
        "collective_decision_validation_failed field=%s reason_code=%s",
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
    if not isinstance(value, str) or not value:
        raise _fail(field_name, "illegal_token")
    if len(value) > 32:
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


def _require_id_tuple(field_name: str, values: object) -> tuple[str, ...]:
    items: list[str] = []
    for item in _require_tuple(field_name, values):
        item_id = _require_hex_id(field_name, item)
        if item_id in items:
            raise _fail(field_name, "duplicate_id")
        items.append(item_id)
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
    forbidden = names & FORBIDDEN_COLLECTIVE_DECISION_FIELD_NAMES
    if forbidden:
        _LOG.error(
            "collective_decision_forbidden_field model=%s field_count=%s",
            model.__name__,
            len(forbidden),
        )
        raise ValueError(f"{model.__name__}: forbidden_field_name")


def collective_context_key(observation: Observation) -> str:
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
        f"collective-decision-context|{observation.world_id.value}|{location}|{day_phase}"
    )


def collective_proposal_ref(
    owner_id: AgentId,
    *,
    originator_id: AgentId | None,
    topic: CollectiveTopic,
    context_key: str,
    inception_tick: int,
    inception_lineage: str,
) -> str:
    """Claimed proposal lineage, stable for a locally created proposal."""
    if type(owner_id) is not AgentId:
        raise _fail("owner_id", "invalid_type")
    if originator_id is not None and type(originator_id) is not AgentId:
        raise _fail("originator_id", "invalid_type")
    if type(topic) is not CollectiveTopic:
        raise _fail("topic", "invalid_type")
    context = _require_digest("context_key", context_key)
    tick = _require_nonneg_int("inception_tick", inception_tick)
    if not isinstance(inception_lineage, str) or not inception_lineage:
        raise _fail("inception_lineage", "invalid_type")
    originator = "-" if originator_id is None else originator_id.value
    return _sha256_hex(
        f"{owner_id.value}|collective-proposal|{originator}|{topic.value}|"
        f"{context}|{tick}|{inception_lineage}"
    )


def collective_proposal_id(
    owner_id: AgentId,
    proposal_ref: str,
    revision: int,
) -> str:
    """Stable owner-local identity for one proposal revision."""
    if type(owner_id) is not AgentId:
        raise _fail("owner_id", "invalid_type")
    ref = _require_hex_id("proposal_ref", proposal_ref)
    rev = _require_nonneg_int("revision", revision)
    return _sha256_hex(f"{owner_id.value}|collective-proposal-id|{ref}|{rev}")


def collective_decision_evidence_id(
    proposal_ref: str,
    ordinal: int,
    channel: CollectiveEvidenceChannel,
    lineage_ref: str,
) -> str:
    ref = _require_hex_id("proposal_ref", proposal_ref)
    order = _require_nonneg_int("ordinal", ordinal)
    if type(channel) is not CollectiveEvidenceChannel:
        raise _fail("channel", "unknown_channel")
    if not isinstance(lineage_ref, str) or not lineage_ref:
        raise _fail("lineage_ref", "invalid_type")
    return _sha256_hex(
        f"{ref}|collective-evidence|{order}|{channel.value}|{lineage_ref}"
    )


@dataclass(frozen=True, slots=True)
class CollectiveEvidence:
    """One bounded item of provenance-aware proposal evidence."""

    evidence_id: str
    ordinal: int
    channel: CollectiveEvidenceChannel
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
        if type(self.channel) is not CollectiveEvidenceChannel:
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
        if self.actor_id is not None and type(self.actor_id) is not AgentId:
            raise _fail("evidence.actor_id", "invalid_type")

    def __repr__(self) -> str:
        return (
            f"CollectiveEvidence(evidence_id={self.evidence_id[:8]!r}, "
            f"ordinal={self.ordinal}, channel={self.channel.value!r}, "
            f"tick={self.tick}, independently_evidenced="
            f"{self.independently_evidenced})"
        )


@dataclass(frozen=True, slots=True)
class CollectiveProposal:
    """One owner-local revision of a claimed shared course of action."""

    proposal_id: str
    owner_id: AgentId
    proposal_ref: str
    revision: int
    topic: CollectiveTopic
    context_key: str
    action_token: str
    first_tick: int
    last_tick: int
    window_first_tick: int
    window_last_tick: int
    status: CollectiveProposalStatus = CollectiveProposalStatus.ACTIVE
    originator_id: AgentId | None = None
    target_token: str | None = None
    terms: tuple[str, ...] = ()
    evidence: tuple[CollectiveEvidence, ...] = ()
    pruned_evidence_count: int = 0
    notices: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        if type(self.owner_id) is not AgentId:
            raise _fail("owner_id", "invalid_type")
        object.__setattr__(
            self, "proposal_id", _require_hex_id("proposal_id", self.proposal_id)
        )
        object.__setattr__(
            self, "proposal_ref", _require_hex_id("proposal_ref", self.proposal_ref)
        )
        rev = _require_nonneg_int("revision", self.revision)
        object.__setattr__(self, "revision", rev)
        expected = collective_proposal_id(self.owner_id, self.proposal_ref, rev)
        if self.proposal_id != expected:
            raise _fail("proposal_id", "id_mismatch")
        if type(self.topic) is not CollectiveTopic:
            raise _fail("topic", "invalid_type")
        object.__setattr__(
            self, "context_key", _require_digest("context_key", self.context_key)
        )
        object.__setattr__(
            self, "action_token", _require_token("action_token", self.action_token)
        )
        if self.originator_id is not None and type(self.originator_id) is not AgentId:
            raise _fail("originator_id", "invalid_type")
        if self.target_token is not None:
            object.__setattr__(
                self,
                "target_token",
                _require_token("target_token", self.target_token),
            )
        terms = _require_tuple("terms", self.terms)
        normalized_terms: list[str] = []
        for term in terms:
            token = _require_token("terms", term)
            if token in normalized_terms:
                raise _fail("terms", "duplicate_term")
            normalized_terms.append(token)
        if len(normalized_terms) > _MAX_TERMS:
            raise _fail("terms", "cap_exceeded")
        object.__setattr__(self, "terms", tuple(normalized_terms))
        _require_span("proposal", self.first_tick, self.last_tick)
        first_window = _require_nonneg_int(
            "proposal.window_first_tick", self.window_first_tick
        )
        last_window = _require_nonneg_int(
            "proposal.window_last_tick", self.window_last_tick
        )
        if last_window < first_window:
            raise _fail("proposal.window_last_tick", "before_first_tick")
        if type(self.status) is not CollectiveProposalStatus:
            raise _fail("status", "unknown_status")
        evidence = _require_tuple("evidence", self.evidence)
        checked_evidence: list[CollectiveEvidence] = []
        seen: set[str] = set()
        previous_ordinal = -1
        previous_tick = -1
        for item in evidence:
            if type(item) is not CollectiveEvidence:
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
            checked_evidence.append(item)
        if len(checked_evidence) > _MAX_EVIDENCE:
            raise _fail("evidence", "cap_exceeded")
        object.__setattr__(self, "evidence", tuple(checked_evidence))
        pruned = _require_nonneg_int(
            "pruned_evidence_count", self.pruned_evidence_count
        )
        if len(checked_evidence) + pruned == 0 and self.status is not (
            CollectiveProposalStatus.DRAFT
        ):
            raise _fail("status", "missing_evidence")
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
        return self.status is CollectiveProposalStatus.ACTIVE

    @property
    def evidence_coverage(self) -> str:
        return "partial" if self.pruned_evidence_count else "complete"

    def supports_tick(self, tick: int) -> bool:
        return self.window_first_tick <= tick <= self.window_last_tick

    def __repr__(self) -> str:
        return (
            f"CollectiveProposal(proposal_id={self.proposal_id[:8]!r}, "
            f"revision={self.revision}, topic={self.topic.value!r}, "
            f"status={self.status.value!r}, evidence_count={len(self.evidence)})"
        )


@dataclass(frozen=True, slots=True)
class CollectivePosition:
    """One owner-relative observation of an actor's expressed stance."""

    position_id: str
    actor_id: AgentId
    proposal_ref: str
    revision: int
    stance: CollectivePositionStance
    strength: float
    channel: CollectiveEvidenceChannel
    root_ref: str
    independently_evidenced: bool
    first_tick: int
    last_tick: int
    evidence_id: str
    active: bool = True

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        object.__setattr__(
            self, "position_id", _require_hex_id("position_id", self.position_id)
        )
        if type(self.actor_id) is not AgentId:
            raise _fail("position.actor_id", "invalid_type")
        object.__setattr__(
            self, "proposal_ref", _require_hex_id("proposal_ref", self.proposal_ref)
        )
        object.__setattr__(
            self, "revision", _require_nonneg_int("position.revision", self.revision)
        )
        if type(self.stance) is not CollectivePositionStance:
            raise _fail("position.stance", "invalid_type")
        object.__setattr__(
            self, "strength", _require_strength("position.strength", self.strength)
        )
        if type(self.channel) is not CollectiveEvidenceChannel:
            raise _fail("position.channel", "unknown_channel")
        if not isinstance(self.root_ref, str) or not self.root_ref:
            raise _fail("position.root_ref", "invalid_type")
        if type(self.independently_evidenced) is not bool:
            raise _fail("position.independently_evidenced", "invalid_type")
        _require_span("position", self.first_tick, self.last_tick)
        object.__setattr__(
            self,
            "evidence_id",
            _require_hex_id("position.evidence_id", self.evidence_id),
        )
        if type(self.active) is not bool:
            raise _fail("position.active", "invalid_type")

    def __repr__(self) -> str:
        return (
            f"CollectivePosition(position_id={self.position_id[:8]!r}, "
            f"revision={self.revision}, stance={self.stance.value!r}, "
            f"channel={self.channel.value!r}, active={self.active})"
        )


@dataclass(frozen=True, slots=True)
class CollectiveDelegation:
    """One-hop, proposal-scoped, non-transitive delegation preference."""

    delegation_id: str
    delegator_id: AgentId
    delegate_id: AgentId
    proposal_ref: str
    revision: int
    strength: float
    first_tick: int
    last_tick: int
    expires_tick: int
    evidence_id: str
    active: bool = True

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        object.__setattr__(
            self, "delegation_id", _require_hex_id("delegation_id", self.delegation_id)
        )
        for name in ("delegator_id", "delegate_id"):
            value = getattr(self, name)
            if type(value) is not AgentId:
                raise _fail(f"delegation.{name}", "invalid_type")
        if self.delegator_id == self.delegate_id:
            raise _fail("delegation.delegate_id", "self_delegation")
        object.__setattr__(
            self, "proposal_ref", _require_hex_id("proposal_ref", self.proposal_ref)
        )
        object.__setattr__(
            self, "revision", _require_nonneg_int("delegation.revision", self.revision)
        )
        object.__setattr__(
            self,
            "strength",
            _require_strength("delegation.strength", self.strength),
        )
        _require_span("delegation", self.first_tick, self.last_tick)
        object.__setattr__(
            self,
            "expires_tick",
            _require_nonneg_int("delegation.expires_tick", self.expires_tick),
        )
        object.__setattr__(
            self,
            "evidence_id",
            _require_hex_id("delegation.evidence_id", self.evidence_id),
        )
        if type(self.active) is not bool:
            raise _fail("delegation.active", "invalid_type")

    def __repr__(self) -> str:
        return (
            f"CollectiveDelegation(delegation_id={self.delegation_id[:8]!r}, "
            f"revision={self.revision}, expires_tick={self.expires_tick}, "
            f"active={self.active})"
        )


@dataclass(frozen=True, slots=True)
class CollectiveRetraction:
    """Explicit self-authored withdrawal of one prior position/delegation."""

    retraction_id: str
    actor_id: AgentId
    target_kind: str
    target_id: str
    proposal_ref: str
    revision: int
    tick: int
    evidence_id: str

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        object.__setattr__(
            self, "retraction_id", _require_hex_id("retraction_id", self.retraction_id)
        )
        if type(self.actor_id) is not AgentId:
            raise _fail("retraction.actor_id", "invalid_type")
        if self.target_kind not in {"position", "delegation"}:
            raise _fail("retraction.target_kind", "invalid_kind")
        object.__setattr__(
            self, "target_id", _require_hex_id("retraction.target_id", self.target_id)
        )
        object.__setattr__(
            self, "proposal_ref", _require_hex_id("proposal_ref", self.proposal_ref)
        )
        object.__setattr__(
            self, "revision", _require_nonneg_int("retraction.revision", self.revision)
        )
        object.__setattr__(
            self, "tick", _require_nonneg_int("retraction.tick", self.tick)
        )
        object.__setattr__(
            self,
            "evidence_id",
            _require_hex_id("retraction.evidence_id", self.evidence_id),
        )

    def __repr__(self) -> str:
        return (
            f"CollectiveRetraction(retraction_id={self.retraction_id[:8]!r}, "
            f"target_kind={self.target_kind!r}, revision={self.revision}, "
            f"tick={self.tick})"
        )


@dataclass(frozen=True, slots=True)
class CollectiveOutcome:
    """Claimed or locally adopted course state; never a binding resolution."""

    outcome_id: str
    proposal_ref: str
    revision: int
    kind: CollectiveOutcomeKind
    execution_status: CollectiveExecutionStatus
    claimed: bool
    first_tick: int
    last_tick: int
    actor_id: AgentId | None = None
    evidence_id: str | None = None

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        object.__setattr__(
            self, "outcome_id", _require_hex_id("outcome_id", self.outcome_id)
        )
        object.__setattr__(
            self, "proposal_ref", _require_hex_id("proposal_ref", self.proposal_ref)
        )
        object.__setattr__(
            self, "revision", _require_nonneg_int("outcome.revision", self.revision)
        )
        if type(self.kind) is not CollectiveOutcomeKind:
            raise _fail("outcome.kind", "invalid_type")
        if type(self.execution_status) is not CollectiveExecutionStatus:
            raise _fail("outcome.execution_status", "invalid_type")
        if type(self.claimed) is not bool:
            raise _fail("outcome.claimed", "invalid_type")
        _require_span("outcome", self.first_tick, self.last_tick)
        if self.actor_id is not None and type(self.actor_id) is not AgentId:
            raise _fail("outcome.actor_id", "invalid_type")
        if self.evidence_id is not None:
            object.__setattr__(
                self,
                "evidence_id",
                _require_hex_id("outcome.evidence_id", self.evidence_id),
            )

    def __repr__(self) -> str:
        return (
            f"CollectiveOutcome(outcome_id={self.outcome_id[:8]!r}, "
            f"revision={self.revision}, kind={self.kind.value!r}, "
            f"execution_status={self.execution_status.value!r}, "
            f"claimed={self.claimed})"
        )


@dataclass(frozen=True, slots=True)
class CollectiveCompliance:
    """Descriptive match/contrast between a supported course and observed action."""

    compliance_id: str
    actor_id: AgentId
    proposal_ref: str
    revision: int
    status: CollectiveComplianceStatus
    window_first_tick: int
    window_last_tick: int
    observed_action_token: str | None = None
    tick: int = 0
    evidence_id: str | None = None

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        object.__setattr__(
            self, "compliance_id", _require_hex_id("compliance_id", self.compliance_id)
        )
        if type(self.actor_id) is not AgentId:
            raise _fail("compliance.actor_id", "invalid_type")
        object.__setattr__(
            self, "proposal_ref", _require_hex_id("proposal_ref", self.proposal_ref)
        )
        object.__setattr__(
            self, "revision", _require_nonneg_int("compliance.revision", self.revision)
        )
        if type(self.status) is not CollectiveComplianceStatus:
            raise _fail("compliance.status", "invalid_type")
        first = _require_nonneg_int(
            "compliance.window_first_tick", self.window_first_tick
        )
        last = _require_nonneg_int("compliance.window_last_tick", self.window_last_tick)
        if last < first:
            raise _fail("compliance.window_last_tick", "before_first_tick")
        if self.observed_action_token is not None:
            object.__setattr__(
                self,
                "observed_action_token",
                _require_token(
                    "compliance.observed_action_token", self.observed_action_token
                ),
            )
        object.__setattr__(
            self, "tick", _require_nonneg_int("compliance.tick", self.tick)
        )
        if self.evidence_id is not None:
            object.__setattr__(
                self,
                "evidence_id",
                _require_hex_id("compliance.evidence_id", self.evidence_id),
            )

    def __repr__(self) -> str:
        return (
            f"CollectiveCompliance(compliance_id={self.compliance_id[:8]!r}, "
            f"revision={self.revision}, status={self.status.value!r}, "
            f"window=({self.window_first_tick},{self.window_last_tick}))"
        )


@dataclass(frozen=True, slots=True)
class CollectiveInfluence:
    """Bounded local decision-attribution record, never a causal proof."""

    influence_id: str
    proposal_ref: str
    revision: int
    source_act: CollectiveAct
    kind: CollectiveInfluenceKind
    strength: float
    tick: int
    unavailable_reason: str | None = None

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        object.__setattr__(
            self, "influence_id", _require_hex_id("influence_id", self.influence_id)
        )
        object.__setattr__(
            self, "proposal_ref", _require_hex_id("proposal_ref", self.proposal_ref)
        )
        object.__setattr__(
            self, "revision", _require_nonneg_int("influence.revision", self.revision)
        )
        if type(self.source_act) is not CollectiveAct:
            raise _fail("influence.source_act", "invalid_type")
        if type(self.kind) is not CollectiveInfluenceKind:
            raise _fail("influence.kind", "invalid_type")
        object.__setattr__(
            self, "strength", _require_strength("influence.strength", self.strength)
        )
        object.__setattr__(
            self, "tick", _require_nonneg_int("influence.tick", self.tick)
        )
        if self.unavailable_reason is not None:
            if (
                not isinstance(self.unavailable_reason, str)
                or not self.unavailable_reason
                or len(self.unavailable_reason) > 32
            ):
                raise _fail("influence.unavailable_reason", "invalid_type")
        if self.kind is CollectiveInfluenceKind.UNAVAILABLE:
            if self.unavailable_reason is None:
                raise _fail("influence.unavailable_reason", "required")
        elif self.unavailable_reason is not None:
            raise _fail("influence.unavailable_reason", "unexpected")

    def __repr__(self) -> str:
        return (
            f"CollectiveInfluence(influence_id={self.influence_id[:8]!r}, "
            f"revision={self.revision}, source_act={self.source_act.value!r}, "
            f"kind={self.kind.value!r}, tick={self.tick})"
        )


@dataclass(frozen=True, slots=True)
class CollectiveDecisionPolicy:
    """Locked collective-decision constants. Runner JSON does not carry these."""

    version: str = COLLECTIVE_DECISION_POLICY_VERSION
    decay: float = _DECAY
    default_proposal_window: int = _DEFAULT_PROPOSAL_WINDOW
    max_proposal_window: int = _MAX_PROPOSAL_WINDOW
    evidence_retention: int = _EVIDENCE_RETENTION
    reference_freshness: int = _REFERENCE_FRESHNESS
    dedup_retention: int = _DEDUP_RETENTION
    max_proposals: int = _MAX_PROPOSALS
    max_positions: int = _MAX_POSITIONS
    max_delegations: int = _MAX_DELEGATIONS
    max_retractions: int = _MAX_RETRACTIONS
    max_outcomes: int = _MAX_OUTCOMES
    max_compliance: int = _MAX_COMPLIANCE
    max_influence: int = _MAX_INFLUENCE
    max_evidence: int = _MAX_EVIDENCE
    max_revisions: int = _MAX_REVISIONS
    max_terms: int = _MAX_TERMS

    def __post_init__(self) -> None:
        if self.version != COLLECTIVE_DECISION_POLICY_VERSION:
            raise _fail("version", "unsupported_policy")
        object.__setattr__(self, "decay", _locked_float("decay", self.decay, _DECAY))
        for name, expected in (
            ("default_proposal_window", _DEFAULT_PROPOSAL_WINDOW),
            ("max_proposal_window", _MAX_PROPOSAL_WINDOW),
            ("evidence_retention", _EVIDENCE_RETENTION),
            ("reference_freshness", _REFERENCE_FRESHNESS),
            ("dedup_retention", _DEDUP_RETENTION),
            ("max_proposals", _MAX_PROPOSALS),
            ("max_positions", _MAX_POSITIONS),
            ("max_delegations", _MAX_DELEGATIONS),
            ("max_retractions", _MAX_RETRACTIONS),
            ("max_outcomes", _MAX_OUTCOMES),
            ("max_compliance", _MAX_COMPLIANCE),
            ("max_influence", _MAX_INFLUENCE),
            ("max_evidence", _MAX_EVIDENCE),
            ("max_revisions", _MAX_REVISIONS),
            ("max_terms", _MAX_TERMS),
        ):
            object.__setattr__(
                self, name, _locked_int(name, getattr(self, name), expected)
            )


@dataclass(frozen=True, slots=True)
class CollectiveDecisionLedger:
    """Owner-scoped collective decisions. ``None`` means the mode is off."""

    owner_id: AgentId
    proposals: tuple[CollectiveProposal, ...] = ()
    positions: tuple[CollectivePosition, ...] = ()
    delegations: tuple[CollectiveDelegation, ...] = ()
    retractions: tuple[CollectiveRetraction, ...] = ()
    outcomes: tuple[CollectiveOutcome, ...] = ()
    compliance: tuple[CollectiveCompliance, ...] = ()
    influence: tuple[CollectiveInfluence, ...] = ()
    notices: tuple[str, ...] = ()
    policy_version: str = COLLECTIVE_DECISION_POLICY_VERSION
    retired_proposal_refs: tuple[str, ...] = ()
    first_observed_tick: int | None = None
    last_observed_tick: int | None = None
    observation_count: int = 0
    pruned_proposal_count: int = 0
    pruned_evidence_count: int = 0
    pruned_position_count: int = 0
    pruned_outcome_count: int = 0

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        if type(self.owner_id) is not AgentId:
            raise _fail("owner_id", "invalid_type")
        if self.policy_version != COLLECTIVE_DECISION_POLICY_VERSION:
            raise _fail("policy_version", "unsupported_policy")
        for name, expected_type, key_field, cap in (
            ("proposals", CollectiveProposal, "proposal_id", _MAX_PROPOSALS),
            ("positions", CollectivePosition, "position_id", _MAX_POSITIONS),
            ("delegations", CollectiveDelegation, "delegation_id", _MAX_DELEGATIONS),
            ("retractions", CollectiveRetraction, "retraction_id", _MAX_RETRACTIONS),
            ("outcomes", CollectiveOutcome, "outcome_id", _MAX_OUTCOMES),
            ("compliance", CollectiveCompliance, "compliance_id", _MAX_COMPLIANCE),
            ("influence", CollectiveInfluence, "influence_id", _MAX_INFLUENCE),
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
        retired = _require_tuple("retired_proposal_refs", self.retired_proposal_refs)
        checked_retired: list[str] = []
        for item in retired:
            ref = _require_hex_id("retired_proposal_refs", item)
            if ref in checked_retired:
                raise _fail("retired_proposal_refs", "duplicate_id")
            checked_retired.append(ref)
        if len(checked_retired) > _MAX_PROPOSALS:
            raise _fail("retired_proposal_refs", "cap_exceeded")
        object.__setattr__(self, "retired_proposal_refs", tuple(checked_retired))
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
            "pruned_proposal_count",
            "pruned_evidence_count",
            "pruned_position_count",
            "pruned_outcome_count",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or type(value) is not int or value < 0:
                raise _fail(name, "invalid_type")
        for proposal in self.proposals:
            if proposal.owner_id != self.owner_id:
                raise _fail("proposals.owner_id", "owner_mismatch")
        _LOG.debug(
            "collective_decision_ledger_constructed owner_id=%s policy_version=%s "
            "proposal_count=%s observation_count=%s",
            self.owner_id.value,
            self.policy_version,
            len(self.proposals),
            self.observation_count,
        )

    @property
    def enabled(self) -> bool:
        return True

    @property
    def has_content(self) -> bool:
        return bool(
            self.proposals
            or self.positions
            or self.delegations
            or self.outcomes
            or self.compliance
            or self.influence
        )

    @property
    def coverage(self) -> str:
        return (
            "partial"
            if any(
                (
                    self.pruned_proposal_count,
                    self.pruned_evidence_count,
                    self.pruned_position_count,
                    self.pruned_outcome_count,
                )
            )
            else "complete"
        )

    @property
    def actionable_proposals(self) -> tuple[CollectiveProposal, ...]:
        return tuple(proposal for proposal in self.proposals if proposal.actionable)

    def __repr__(self) -> str:
        return (
            f"CollectiveDecisionLedger(owner_id={self.owner_id.value!r}, "
            f"proposal_count={len(self.proposals)}, "
            f"position_count={len(self.positions)}, "
            f"observation_count={self.observation_count}, "
            f"coverage={self.coverage!r})"
        )


def default_collective_decision_policy() -> CollectiveDecisionPolicy:
    """Return the only accepted collective-decisions policy."""
    return CollectiveDecisionPolicy()


def empty_collective_decision_ledger(
    owner_id: AgentId,
) -> CollectiveDecisionLedger:
    """Ledger with no content. Disabled mode does not call this."""
    return CollectiveDecisionLedger(owner_id=owner_id)


def require_owner_collective_decisions(
    ledger: object,
    owner_id: AgentId,
    *,
    field_name: str,
) -> None:
    """Reject a foreign or mistyped collective-decision ledger."""
    if ledger is None:
        return
    if type(owner_id) is not AgentId:
        raise _fail("owner_id", "invalid_type")
    if type(ledger) is not CollectiveDecisionLedger:
        _LOG.warning("collective_decision_carry_rejected reason=%s", "invalid_type")
        raise TypeError(f"{field_name} must be CollectiveDecisionLedger")
    if ledger.owner_id != owner_id:
        _LOG.error(
            "collective_decision_validation_failed field=%s reason_code=%s",
            field_name,
            "owner_mismatch",
        )
        _LOG.warning("collective_decision_carry_rejected reason=%s", "owner_mismatch")
        raise ValueError(f"{field_name} owner_id mismatch")


# ---------------------------------------------------------------------------
# Evidence adapters, deterministic updates, and local proposal generation
# ---------------------------------------------------------------------------

_COLLECTIVE_PREDICATE: Final[str] = "collective"
_PREDICATE_BY_ACT: Final[dict[str, CollectiveAct]] = {
    "collective_propose": CollectiveAct.PROPOSE,
    "collective_support": CollectiveAct.SUPPORT,
    "collective_oppose": CollectiveAct.OPPOSE,
    "collective_delegate": CollectiveAct.DELEGATE,
    "collective_withdraw": CollectiveAct.WITHDRAW_SUPPORT,
    "collective_coordinate": CollectiveAct.COORDINATE,
}


@dataclass(frozen=True, slots=True)
class _CollectiveSignal:
    act: CollectiveAct
    topic: CollectiveTopic
    proposal_ref: str
    revision: int
    context_key: str
    lineage_ref: str
    root_ref: str
    channel: CollectiveEvidenceChannel
    actor_id: AgentId | None = None
    originator_id: AgentId | None = None
    action_token: str | None = None
    target_token: str | None = None
    terms: tuple[str, ...] = ()
    window_first_tick: int | None = None
    window_last_tick: int | None = None
    delegate_id: AgentId | None = None
    retract_kind: str | None = None
    retract_id: str | None = None
    claimed_status: CollectiveExecutionStatus = CollectiveExecutionStatus.UNKNOWN
    confidence: float = 1.0
    independently_evidenced: bool = True


def _parse_topic(token: str) -> CollectiveTopic | None:
    try:
        return CollectiveTopic(token.strip())
    except ValueError:
        return None


def _parse_revision(token: str) -> int | None:
    try:
        value = int(token.strip())
    except (TypeError, ValueError):
        return None
    if value < 0:
        return None
    return value


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


def _parse_status(token: str) -> CollectiveExecutionStatus:
    try:
        return CollectiveExecutionStatus(token.strip())
    except ValueError:
        return CollectiveExecutionStatus.UNKNOWN


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


def _signal_from_relation(
    *,
    speaker_id: EntityId | None,
    identity: OwnerSafeSocialIdentity,
    topic_text: str,
    predicate: str,
    object_text: str,
    context_key: str,
    lineage_ref: str,
    root_ref: str,
    channel: CollectiveEvidenceChannel,
    confidence: float,
) -> _CollectiveSignal | None:
    act = _PREDICATE_BY_ACT.get(predicate)
    topic = _parse_topic(topic_text)
    if act is None or topic is None:
        return None
    parts = object_text.split("|")
    if len(parts) < 2:
        return None
    ref = parts[0].strip()
    if len(ref) != 64 or any(char not in _HEX for char in ref):
        return None
    revision = _parse_revision(parts[1])
    if revision is None:
        return None
    actor = _resolve_entity(identity, speaker_id)
    base = _CollectiveSignal(
        act=act,
        topic=topic,
        proposal_ref=ref,
        revision=revision,
        context_key=context_key,
        lineage_ref=lineage_ref,
        root_ref=root_ref,
        channel=channel,
        actor_id=actor,
        confidence=confidence,
        independently_evidenced=actor is not None,
    )
    if act is CollectiveAct.PROPOSE:
        if len(parts) < 8:
            return None
        action = _parse_optional_token(parts[2])
        if action is None:
            return None
        target = _parse_optional_token(parts[3])
        terms = _parse_terms(parts[4])
        first_window = _parse_revision(parts[5])
        last_window = _parse_revision(parts[6])
        if first_window is None or last_window is None:
            return None
        context = parts[7].strip()
        if len(context) != _DIGEST_LEN or any(char not in _HEX for char in context):
            context = context_key
        return _CollectiveSignal(
            act=act,
            topic=topic,
            proposal_ref=ref,
            revision=revision,
            context_key=context,
            lineage_ref=lineage_ref,
            root_ref=root_ref,
            channel=channel,
            actor_id=actor,
            originator_id=actor,
            action_token=action,
            target_token=target,
            terms=terms,
            window_first_tick=first_window,
            window_last_tick=last_window,
            confidence=confidence,
            independently_evidenced=actor is not None,
        )
    if act is CollectiveAct.DELEGATE:
        if len(parts) < 3:
            return None
        delegate = _resolve_entity(identity, _parse_optional_entity(parts[2]))
        return _CollectiveSignal(
            act=act,
            topic=topic,
            proposal_ref=ref,
            revision=revision,
            context_key=context_key,
            lineage_ref=lineage_ref,
            root_ref=root_ref,
            channel=channel,
            actor_id=actor,
            delegate_id=delegate,
            confidence=confidence,
            independently_evidenced=actor is not None and delegate is not None,
        )
    if act is CollectiveAct.WITHDRAW_SUPPORT:
        if len(parts) < 4:
            return None
        kind = parts[2].strip()
        target_id = parts[3].strip()
        if kind not in {"position", "delegation"}:
            return None
        if len(target_id) != 64 or any(char not in _HEX for char in target_id):
            return None
        return _CollectiveSignal(
            act=act,
            topic=topic,
            proposal_ref=ref,
            revision=revision,
            context_key=context_key,
            lineage_ref=lineage_ref,
            root_ref=root_ref,
            channel=channel,
            actor_id=actor,
            retract_kind=kind,
            retract_id=target_id,
            confidence=confidence,
            independently_evidenced=actor is not None,
        )
    if act is CollectiveAct.COORDINATE:
        action = _parse_optional_token(parts[2]) if len(parts) > 2 else None
        target = _parse_optional_token(parts[3]) if len(parts) > 3 else None
        status = (
            _parse_status(parts[4])
            if len(parts) > 4
            else (CollectiveExecutionStatus.UNKNOWN)
        )
        return _CollectiveSignal(
            act=act,
            topic=topic,
            proposal_ref=ref,
            revision=revision,
            context_key=context_key,
            lineage_ref=lineage_ref,
            root_ref=root_ref,
            channel=channel,
            actor_id=actor,
            action_token=action,
            target_token=target,
            claimed_status=status,
            confidence=confidence,
            independently_evidenced=actor is not None,
        )
    return base


def _signals_from_observation(
    observation: Observation,
    identity: OwnerSafeSocialIdentity,
    context_key: str,
) -> list[_CollectiveSignal]:
    signals: list[_CollectiveSignal] = []
    for ordinal, communication in enumerate(observation.communications):
        declared = communication.utterance.declared
        root_ref = f"communication|{declared.root_communication_id.value}"
        for relation_index, relation in enumerate(
            communication.utterance.content.relations
        ):
            signal = _signal_from_relation(
                speaker_id=communication.speaker_id,
                identity=identity,
                topic_text=relation.subject,
                predicate=relation.predicate,
                object_text=relation.object,
                context_key=context_key,
                lineage_ref=(
                    f"communication-{observation.tick}-{ordinal}-"
                    f"{relation_index}-{relation.predicate}"
                ),
                root_ref=root_ref,
                channel=CollectiveEvidenceChannel.COMMUNICATED,
                confidence=declared.sender_confidence,
            )
            if signal is not None:
                signals.append(signal)
    return signals


def _signals_from_episodes(
    context: object,
    identity: OwnerSafeSocialIdentity,
    context_key: str,
) -> list[_CollectiveSignal]:
    from agents.cognition.models import RetrievedMemoryContext, episode_facts

    if context is None:
        return []
    if type(context) is not RetrievedMemoryContext:
        raise TypeError("retrieved_memory_context must be RetrievedMemoryContext")
    if context.owner_id != identity.owner_id:
        raise ValueError("retrieved_memory_context owner_id mismatch")
    signals: list[_CollectiveSignal] = []
    for facts in episode_facts(context):
        concept_text = {item.mention_id: item.concept for item in facts.concepts}
        entity_by_mention = {
            item.mention_id: item.entity_id
            for item in facts.entities
            if item.entity_id is not None
        }
        for relation_index, relation in enumerate(facts.relations):
            if relation.predicate not in _PREDICATE_BY_ACT:
                continue
            subject_text = concept_text.get(relation.subject.mention_id, "")
            object_text = concept_text.get(relation.object.mention_id, "")
            speaker_entity = entity_by_mention.get(relation.subject.mention_id)
            signal = _signal_from_relation(
                speaker_id=speaker_entity,
                identity=identity,
                topic_text=subject_text,
                predicate=relation.predicate,
                object_text=object_text,
                context_key=context_key,
                lineage_ref=(
                    f"remembered-{facts.episode_id}-{relation.relation_id.value}-"
                    f"{relation_index}"
                ),
                root_ref=f"remembered|{facts.episode_id}",
                channel=CollectiveEvidenceChannel.REMEMBERED,
                confidence=facts.confidence,
            )
            if signal is not None:
                signals.append(signal)
    return signals


def create_collective_proposal(
    owner_id: AgentId,
    *,
    topic: CollectiveTopic,
    context_key: str,
    action_token: str,
    tick: int,
    originator_id: AgentId | None = None,
    target_token: str | None = None,
    terms: Sequence[str] = (),
    window_first_tick: int | None = None,
    window_last_tick: int | None = None,
    policy: CollectiveDecisionPolicy | None = None,
) -> CollectiveProposal:
    """Create one local draft proposal from owner-visible opportunity evidence.

    A draft is not proof of support, adoption, coordination, or legitimacy.
    """
    active = default_collective_decision_policy() if policy is None else policy
    if type(active) is not CollectiveDecisionPolicy:
        raise TypeError("policy must be CollectiveDecisionPolicy or None")
    if type(owner_id) is not AgentId:
        raise _fail("owner_id", "invalid_type")
    if type(topic) is not CollectiveTopic:
        raise _fail("topic", "invalid_type")
    start = _require_nonneg_int("tick", tick)
    first_window = start if window_first_tick is None else window_first_tick
    last_window = (
        start + active.default_proposal_window
        if window_last_tick is None
        else window_last_tick
    )
    if last_window - first_window > active.max_proposal_window:
        raise _fail("window_last_tick", "window_too_long")
    ref = collective_proposal_ref(
        owner_id,
        originator_id=originator_id,
        topic=topic,
        context_key=context_key,
        inception_tick=start,
        inception_lineage=f"local-{action_token}",
    )
    return CollectiveProposal(
        proposal_id=collective_proposal_id(owner_id, ref, 0),
        owner_id=owner_id,
        proposal_ref=ref,
        revision=0,
        topic=topic,
        context_key=context_key,
        action_token=action_token,
        first_tick=start,
        last_tick=start,
        window_first_tick=first_window,
        window_last_tick=last_window,
        status=CollectiveProposalStatus.DRAFT,
        originator_id=originator_id,
        target_token=target_token,
        terms=tuple(terms),
    )


def _notice(notices: list[str], reason: str) -> None:
    if reason not in notices:
        notices.append(reason)


@dataclass(slots=True)
class _LedgerDraft:
    owner_id: AgentId
    proposals: dict[tuple[str, int], CollectiveProposal]
    positions: dict[str, CollectivePosition]
    delegations: dict[str, CollectiveDelegation]
    retractions: list[CollectiveRetraction]
    outcomes: dict[str, CollectiveOutcome]
    compliance: dict[str, CollectiveCompliance]
    influence: dict[str, CollectiveInfluence]
    retired_refs: list[str]
    notices: list[str]
    first_observed_tick: int | None
    last_observed_tick: int | None
    observation_count: int
    pruned_proposal_count: int = 0
    pruned_evidence_count: int = 0
    pruned_position_count: int = 0
    pruned_outcome_count: int = 0


def _draft_from_ledger(ledger: CollectiveDecisionLedger) -> _LedgerDraft:
    return _LedgerDraft(
        owner_id=ledger.owner_id,
        proposals={
            (item.proposal_ref, item.revision): item for item in ledger.proposals
        },
        positions={item.position_id: item for item in ledger.positions},
        delegations={item.delegation_id: item for item in ledger.delegations},
        retractions=list(ledger.retractions),
        outcomes={item.outcome_id: item for item in ledger.outcomes},
        compliance={item.compliance_id: item for item in ledger.compliance},
        influence={item.influence_id: item for item in ledger.influence},
        retired_refs=list(ledger.retired_proposal_refs),
        notices=list(ledger.notices),
        first_observed_tick=ledger.first_observed_tick,
        last_observed_tick=ledger.last_observed_tick,
        observation_count=ledger.observation_count,
        pruned_proposal_count=ledger.pruned_proposal_count,
        pruned_evidence_count=ledger.pruned_evidence_count,
        pruned_position_count=ledger.pruned_position_count,
        pruned_outcome_count=ledger.pruned_outcome_count,
    )


def _latest_revision(draft: _LedgerDraft, ref: str) -> int | None:
    revisions = [
        revision for (item_ref, revision) in draft.proposals if item_ref == ref
    ]
    return None if not revisions else max(revisions)


def _retire_reference(
    draft: _LedgerDraft, ref: str, policy: CollectiveDecisionPolicy
) -> None:
    if ref not in draft.retired_refs:
        draft.retired_refs.append(ref)
    for key, proposal in tuple(draft.proposals.items()):
        if key[0] != ref:
            continue
        if proposal.status is not CollectiveProposalStatus.RETIRED:
            draft.proposals[key] = _replace_proposal(
                proposal, status=CollectiveProposalStatus.RETIRED
            )
    for position_id, position in tuple(draft.positions.items()):
        if position.proposal_ref == ref and position.active:
            draft.positions[position_id] = _replace_position(position, active=False)
    for delegation_id, delegation in tuple(draft.delegations.items()):
        if delegation.proposal_ref == ref and delegation.active:
            draft.delegations[delegation_id] = _replace_delegation(
                delegation, active=False
            )


def _replace_proposal(
    proposal: CollectiveProposal, **changes: object
) -> CollectiveProposal:
    values = {
        "proposal_id": proposal.proposal_id,
        "owner_id": proposal.owner_id,
        "proposal_ref": proposal.proposal_ref,
        "revision": proposal.revision,
        "topic": proposal.topic,
        "context_key": proposal.context_key,
        "action_token": proposal.action_token,
        "first_tick": proposal.first_tick,
        "last_tick": proposal.last_tick,
        "window_first_tick": proposal.window_first_tick,
        "window_last_tick": proposal.window_last_tick,
        "status": proposal.status,
        "originator_id": proposal.originator_id,
        "target_token": proposal.target_token,
        "terms": proposal.terms,
        "evidence": proposal.evidence,
        "pruned_evidence_count": proposal.pruned_evidence_count,
        "notices": proposal.notices,
    }
    values.update(changes)
    return CollectiveProposal(**values)  # type: ignore[arg-type]


def _replace_position(
    position: CollectivePosition, **changes: object
) -> CollectivePosition:
    values = {
        "position_id": position.position_id,
        "actor_id": position.actor_id,
        "proposal_ref": position.proposal_ref,
        "revision": position.revision,
        "stance": position.stance,
        "strength": position.strength,
        "channel": position.channel,
        "root_ref": position.root_ref,
        "independently_evidenced": position.independently_evidenced,
        "first_tick": position.first_tick,
        "last_tick": position.last_tick,
        "evidence_id": position.evidence_id,
        "active": position.active,
    }
    values.update(changes)
    return CollectivePosition(**values)  # type: ignore[arg-type]


def _replace_delegation(
    delegation: CollectiveDelegation, **changes: object
) -> CollectiveDelegation:
    values = {
        "delegation_id": delegation.delegation_id,
        "delegator_id": delegation.delegator_id,
        "delegate_id": delegation.delegate_id,
        "proposal_ref": delegation.proposal_ref,
        "revision": delegation.revision,
        "strength": delegation.strength,
        "first_tick": delegation.first_tick,
        "last_tick": delegation.last_tick,
        "expires_tick": delegation.expires_tick,
        "evidence_id": delegation.evidence_id,
        "active": delegation.active,
    }
    values.update(changes)
    return CollectiveDelegation(**values)  # type: ignore[arg-type]


def _append_evidence(
    proposal: CollectiveProposal,
    *,
    signal: _CollectiveSignal,
    tick: int,
    policy: CollectiveDecisionPolicy,
) -> tuple[CollectiveProposal, CollectiveEvidence | None]:
    if any(item.lineage_ref == signal.lineage_ref for item in proposal.evidence):
        return proposal, None
    if len(proposal.evidence) >= policy.max_evidence:
        return (
            _replace_proposal(
                proposal,
                pruned_evidence_count=proposal.pruned_evidence_count + 1,
            ),
            None,
        )
    ordinal = (proposal.evidence[-1].ordinal + 1) if proposal.evidence else 0
    same_root = any(item.root_ref == signal.root_ref for item in proposal.evidence)
    evidence = CollectiveEvidence(
        evidence_id=collective_decision_evidence_id(
            proposal.proposal_ref, ordinal, signal.channel, signal.lineage_ref
        ),
        ordinal=ordinal,
        channel=signal.channel,
        lineage_ref=signal.lineage_ref,
        root_ref=signal.root_ref,
        tick=tick,
        independently_evidenced=(signal.independently_evidenced and not same_root),
        actor_id=signal.actor_id,
    )
    return (
        _replace_proposal(
            proposal,
            evidence=(*proposal.evidence, evidence),
            last_tick=max(proposal.last_tick, tick),
        ),
        evidence,
    )


def _apply_propose(
    draft: _LedgerDraft,
    signal: _CollectiveSignal,
    tick: int,
    policy: CollectiveDecisionPolicy,
) -> None:
    if signal.proposal_ref in draft.retired_refs:
        _notice(draft.notices, "retired_reference")
        return
    if signal.action_token is None:
        _notice(draft.notices, "unsupported_evidence")
        return
    first_window = (
        tick if signal.window_first_tick is None else signal.window_first_tick
    )
    last_window = (
        tick + policy.default_proposal_window
        if signal.window_last_tick is None
        else signal.window_last_tick
    )
    if last_window < first_window:
        _notice(draft.notices, "unsupported_evidence")
        return
    if last_window - first_window > policy.max_proposal_window:
        _notice(draft.notices, "unsupported_evidence")
        return
    key = (signal.proposal_ref, signal.revision)
    existing = draft.proposals.get(key)
    if existing is not None:
        updated, _ = _append_evidence(existing, signal=signal, tick=tick, policy=policy)
        draft.proposals[key] = updated
        return
    if len(draft.proposals) >= policy.max_proposals:
        _evict_proposal(draft, policy, target=policy.max_proposals - 1)
        if len(draft.proposals) >= policy.max_proposals:
            _notice(draft.notices, "cap_exceeded")
            return
    latest = _latest_revision(draft, signal.proposal_ref)
    if latest is not None and signal.revision <= latest:
        _notice(draft.notices, "stale_reference")
        return
    if latest is not None:
        for revision in range(latest + 1):
            prior = draft.proposals.get((signal.proposal_ref, revision))
            if prior is not None and prior.status is CollectiveProposalStatus.ACTIVE:
                draft.proposals[(signal.proposal_ref, revision)] = _replace_proposal(
                    prior, status=CollectiveProposalStatus.SUPERSEDED
                )
    proposal = CollectiveProposal(
        proposal_id=collective_proposal_id(
            draft.owner_id, signal.proposal_ref, signal.revision
        ),
        owner_id=draft.owner_id,
        proposal_ref=signal.proposal_ref,
        revision=signal.revision,
        topic=signal.topic,
        context_key=signal.context_key,
        action_token=signal.action_token,
        first_tick=tick,
        last_tick=tick,
        window_first_tick=first_window,
        window_last_tick=last_window,
        status=CollectiveProposalStatus.DRAFT,
        originator_id=signal.actor_id,
        target_token=signal.target_token,
        terms=signal.terms,
        evidence=(),
    )
    proposal, evidence = _append_evidence(
        proposal, signal=signal, tick=tick, policy=policy
    )
    if evidence is not None:
        proposal = _replace_proposal(proposal, status=CollectiveProposalStatus.ACTIVE)
    draft.proposals[key] = proposal


def _evict_proposal(
    draft: _LedgerDraft,
    policy: CollectiveDecisionPolicy,
    *,
    target: int | None = None,
) -> None:
    limit = policy.max_proposals if target is None else target
    if len(draft.proposals) <= limit:
        return
    ordered = sorted(
        draft.proposals.items(),
        key=lambda item: (
            item[1].status is CollectiveProposalStatus.ACTIVE,
            item[1].last_tick,
            item[1].proposal_id,
        ),
    )
    for key, proposal in ordered:
        if len(draft.proposals) <= limit:
            break
        del draft.proposals[key]
        draft.pruned_proposal_count += 1
        if proposal.proposal_ref not in draft.retired_refs:
            draft.retired_refs.append(proposal.proposal_ref)
        for position_id, position in tuple(draft.positions.items()):
            if position.proposal_ref == proposal.proposal_ref:
                del draft.positions[position_id]
        for delegation_id, delegation in tuple(draft.delegations.items()):
            if delegation.proposal_ref == proposal.proposal_ref:
                del draft.delegations[delegation_id]


def _require_known(
    draft: _LedgerDraft,
    signal: _CollectiveSignal,
    tick: int,
    policy: CollectiveDecisionPolicy,
) -> tuple[CollectiveProposal, int] | None:
    if signal.proposal_ref in draft.retired_refs:
        _notice(draft.notices, "retired_reference")
        return None
    revision = _latest_revision(draft, signal.proposal_ref)
    if revision is None:
        _notice(draft.notices, "unknown_proposal")
        return None
    proposal = draft.proposals.get((signal.proposal_ref, signal.revision))
    if proposal is None:
        _notice(draft.notices, "ambiguous_reference")
        return None
    if proposal.status is CollectiveProposalStatus.RETIRED:
        _notice(draft.notices, "retired_reference")
        return None
    if _time_distance(tick, proposal.window_first_tick) > policy.reference_freshness:
        _notice(draft.notices, "stale_reference")
        return None
    if tick > proposal.window_last_tick:
        _notice(draft.notices, "expired_reference")
        return None
    return proposal, revision


def _time_distance(tick: int, other: int) -> int:
    return abs(tick - other)


def _existing_position(
    draft: _LedgerDraft, actor_id: AgentId, ref: str, revision: int
) -> CollectivePosition | None:
    matches = [
        item
        for item in draft.positions.values()
        if item.actor_id == actor_id
        and item.proposal_ref == ref
        and item.revision == revision
    ]
    if not matches:
        return None
    return max(matches, key=lambda item: (item.last_tick, item.position_id))


def _apply_stance(
    draft: _LedgerDraft,
    signal: _CollectiveSignal,
    tick: int,
    policy: CollectiveDecisionPolicy,
) -> None:
    found = _require_known(draft, signal, tick, policy)
    if found is None:
        return
    proposal, _ = found
    if signal.actor_id is None:
        _notice(draft.notices, "unresolved_entity")
        return
    proposal, evidence = _append_evidence(
        proposal, signal=signal, tick=tick, policy=policy
    )
    draft.proposals[(proposal.proposal_ref, proposal.revision)] = proposal
    if evidence is None:
        return
    actor = signal.actor_id
    if actor == proposal.originator_id:
        _notice(proposal_notices := list(proposal.notices), "self_endorsement")
        draft.proposals[(proposal.proposal_ref, proposal.revision)] = _replace_proposal(
            proposal, notices=tuple(proposal_notices)
        )
    root_duplicate = any(
        item.root_ref == signal.root_ref
        and item.proposal_ref == signal.proposal_ref
        and item.revision == signal.revision
        for item in draft.positions.values()
    )
    independently = signal.independently_evidenced and not root_duplicate
    if root_duplicate:
        _notice(draft.notices, "duplicate_root")
    stance = (
        CollectivePositionStance.SUPPORT
        if signal.act is CollectiveAct.SUPPORT
        else CollectivePositionStance.OPPOSE
    )
    position_id = _sha256_hex(
        f"{draft.owner_id.value}|position|{signal.proposal_ref}|{signal.revision}|"
        f"{actor.value}|{signal.lineage_ref}"
    )
    if position_id in draft.positions:
        return
    if len(draft.positions) >= policy.max_positions:
        _evict_position(draft, policy)
        if len(draft.positions) >= policy.max_positions:
            _notice(draft.notices, "cap_exceeded")
            return
    draft.positions[position_id] = CollectivePosition(
        position_id=position_id,
        actor_id=actor,
        proposal_ref=signal.proposal_ref,
        revision=signal.revision,
        stance=stance,
        strength=_quantize(signal.confidence),
        channel=signal.channel,
        root_ref=signal.root_ref,
        independently_evidenced=independently,
        first_tick=tick,
        last_tick=tick,
        evidence_id=evidence.evidence_id,
    )


def _evict_position(draft: _LedgerDraft, policy: CollectiveDecisionPolicy) -> None:
    if len(draft.positions) <= policy.max_positions:
        return
    ordered = sorted(
        draft.positions.items(),
        key=lambda item: (
            item[1].active,
            item[1].last_tick,
            item[1].position_id,
        ),
    )
    for position_id, _ in ordered:
        if len(draft.positions) <= policy.max_positions:
            break
        del draft.positions[position_id]
        draft.pruned_position_count += 1


def _apply_delegate(
    draft: _LedgerDraft,
    signal: _CollectiveSignal,
    tick: int,
    policy: CollectiveDecisionPolicy,
) -> None:
    found = _require_known(draft, signal, tick, policy)
    if found is None:
        return
    proposal, _ = found
    if signal.actor_id is None or signal.delegate_id is None:
        _notice(draft.notices, "unresolved_entity")
        return
    if signal.actor_id == signal.delegate_id:
        _notice(draft.notices, "self_delegation")
        return
    proposal, evidence = _append_evidence(
        proposal, signal=signal, tick=tick, policy=policy
    )
    draft.proposals[(proposal.proposal_ref, proposal.revision)] = proposal
    if evidence is None:
        return
    delegation_id = _sha256_hex(
        f"{draft.owner_id.value}|delegation|{signal.proposal_ref}|"
        f"{signal.revision}|{signal.actor_id.value}|{signal.delegate_id.value}|"
        f"{signal.lineage_ref}"
    )
    if delegation_id in draft.delegations:
        return
    if len(draft.delegations) >= policy.max_delegations:
        _notice(draft.notices, "cap_exceeded")
        return
    draft.delegations[delegation_id] = CollectiveDelegation(
        delegation_id=delegation_id,
        delegator_id=signal.actor_id,
        delegate_id=signal.delegate_id,
        proposal_ref=signal.proposal_ref,
        revision=signal.revision,
        strength=_quantize(signal.confidence),
        first_tick=tick,
        last_tick=tick,
        expires_tick=min(
            tick + policy.default_proposal_window, proposal.window_last_tick
        ),
        evidence_id=evidence.evidence_id,
    )


def _apply_withdraw(
    draft: _LedgerDraft,
    signal: _CollectiveSignal,
    tick: int,
    policy: CollectiveDecisionPolicy,
) -> None:
    found = _require_known(draft, signal, tick, policy)
    if found is None:
        return
    proposal, _ = found
    if (
        signal.actor_id is None
        or signal.retract_kind is None
        or signal.retract_id is None
    ):
        _notice(draft.notices, "unresolved_entity")
        return
    if len(draft.retractions) >= policy.max_retractions:
        _retire_reference(draft, proposal.proposal_ref, policy)
        _notice(draft.notices, "cap_exceeded")
        return
    actor = signal.actor_id
    target_id = signal.retract_id
    if signal.retract_kind == "position":
        position = draft.positions.get(target_id)
        if position is None or position.actor_id != actor:
            _notice(draft.notices, "unknown_proposal")
            return
        draft.positions[target_id] = _replace_position(
            position, active=False, last_tick=max(position.last_tick, tick)
        )
    else:
        delegation = draft.delegations.get(target_id)
        if delegation is None or delegation.delegator_id != actor:
            _notice(draft.notices, "unknown_proposal")
            return
        draft.delegations[target_id] = _replace_delegation(
            delegation, active=False, last_tick=max(delegation.last_tick, tick)
        )
    proposal, evidence = _append_evidence(
        proposal, signal=signal, tick=tick, policy=policy
    )
    draft.proposals[(proposal.proposal_ref, proposal.revision)] = proposal
    if evidence is None:
        return
    retraction_id = _sha256_hex(
        f"{draft.owner_id.value}|retraction|{signal.proposal_ref}|"
        f"{signal.revision}|{actor.value}|{signal.retract_kind}|{target_id}|"
        f"{signal.lineage_ref}"
    )
    if any(item.retraction_id == retraction_id for item in draft.retractions):
        return
    draft.retractions.append(
        CollectiveRetraction(
            retraction_id=retraction_id,
            actor_id=actor,
            target_kind=signal.retract_kind,
            target_id=target_id,
            proposal_ref=signal.proposal_ref,
            revision=signal.revision,
            tick=tick,
            evidence_id=evidence.evidence_id,
        )
    )


def _apply_coordinate(
    draft: _LedgerDraft,
    signal: _CollectiveSignal,
    tick: int,
    policy: CollectiveDecisionPolicy,
) -> None:
    found = _require_known(draft, signal, tick, policy)
    if found is None:
        return
    proposal, _ = found
    proposal, evidence = _append_evidence(
        proposal, signal=signal, tick=tick, policy=policy
    )
    draft.proposals[(proposal.proposal_ref, proposal.revision)] = proposal
    if evidence is None:
        return
    if len(draft.outcomes) >= policy.max_outcomes:
        draft.pruned_outcome_count += 1
        _notice(draft.notices, "cap_exceeded")
        return
    outcome_id = _sha256_hex(
        f"{draft.owner_id.value}|outcome|{signal.proposal_ref}|{signal.revision}|"
        f"{signal.actor_id.value if signal.actor_id else '-'}|{signal.lineage_ref}"
    )
    if outcome_id in draft.outcomes:
        return
    draft.outcomes[outcome_id] = CollectiveOutcome(
        outcome_id=outcome_id,
        proposal_ref=signal.proposal_ref,
        revision=signal.revision,
        kind=CollectiveOutcomeKind.CLAIMED,
        execution_status=signal.claimed_status,
        claimed=True,
        first_tick=tick,
        last_tick=tick,
        actor_id=signal.actor_id,
        evidence_id=evidence.evidence_id,
    )


def _apply_signal(
    draft: _LedgerDraft,
    signal: _CollectiveSignal,
    tick: int,
    policy: CollectiveDecisionPolicy,
) -> None:
    if signal.confidence <= 0.0:
        _notice(draft.notices, "unsupported_evidence")
        return
    if signal.act is CollectiveAct.PROPOSE:
        _apply_propose(draft, signal, tick, policy)
    elif signal.act in {CollectiveAct.SUPPORT, CollectiveAct.OPPOSE}:
        _apply_stance(draft, signal, tick, policy)
    elif signal.act is CollectiveAct.DELEGATE:
        _apply_delegate(draft, signal, tick, policy)
    elif signal.act is CollectiveAct.WITHDRAW_SUPPORT:
        _apply_withdraw(draft, signal, tick, policy)
    elif signal.act is CollectiveAct.COORDINATE:
        _apply_coordinate(draft, signal, tick, policy)
    else:  # pragma: no cover - closed enum
        _notice(draft.notices, "unsupported_evidence")


def _expire(draft: _LedgerDraft, tick: int) -> None:
    for key, proposal in tuple(draft.proposals.items()):
        if proposal.status is CollectiveProposalStatus.ACTIVE and tick > (
            proposal.window_last_tick
        ):
            draft.proposals[key] = _replace_proposal(
                proposal, status=CollectiveProposalStatus.EXPIRED
            )
    for delegation_id, delegation in tuple(draft.delegations.items()):
        if delegation.active and tick > delegation.expires_tick:
            draft.delegations[delegation_id] = _replace_delegation(
                delegation, active=False
            )


def _prune_evidence(
    draft: _LedgerDraft, tick: int, policy: CollectiveDecisionPolicy
) -> None:
    retention = max(0, tick - policy.evidence_retention)
    for key, proposal in tuple(draft.proposals.items()):
        kept = tuple(item for item in proposal.evidence if item.tick >= retention)
        pruned = len(proposal.evidence) - len(kept)
        if not pruned:
            continue
        draft.proposals[key] = _replace_proposal(
            proposal,
            evidence=kept,
            pruned_evidence_count=proposal.pruned_evidence_count + pruned,
        )
        draft.pruned_evidence_count += pruned


def _freeze(
    draft: _LedgerDraft, tick: int, policy: CollectiveDecisionPolicy
) -> CollectiveDecisionLedger:
    _expire(draft, tick)
    _prune_evidence(draft, tick, policy)
    proposals = tuple(
        sorted(
            draft.proposals.values(),
            key=lambda item: (item.proposal_ref, item.revision),
        )
    )
    positions = tuple(
        sorted(draft.positions.values(), key=lambda item: item.position_id)
    )
    delegations = tuple(
        sorted(draft.delegations.values(), key=lambda item: item.delegation_id)
    )
    outcomes = tuple(sorted(draft.outcomes.values(), key=lambda item: item.outcome_id))
    compliance = tuple(
        sorted(draft.compliance.values(), key=lambda item: item.compliance_id)
    )
    influence = tuple(
        sorted(draft.influence.values(), key=lambda item: item.influence_id)
    )
    return CollectiveDecisionLedger(
        owner_id=draft.owner_id,
        proposals=proposals,
        positions=positions,
        delegations=delegations,
        retractions=tuple(draft.retractions),
        outcomes=outcomes,
        compliance=compliance,
        influence=influence,
        notices=tuple(draft.notices),
        retired_proposal_refs=tuple(draft.retired_refs[-_MAX_PROPOSALS:]),
        first_observed_tick=draft.first_observed_tick,
        last_observed_tick=draft.last_observed_tick,
        observation_count=draft.observation_count,
        pruned_proposal_count=draft.pruned_proposal_count,
        pruned_evidence_count=draft.pruned_evidence_count,
        pruned_position_count=draft.pruned_position_count,
        pruned_outcome_count=draft.pruned_outcome_count,
    )


def apply_collective_decision_update(
    observation: object,
    identity: object,
    previous: object = None,
    retrieved_memory_context: object = None,
    speaker_trust: dict[str, float] | None = None,
    policy: CollectiveDecisionPolicy | None = None,
) -> CollectiveDecisionLedger:
    """Apply one tick of owner-scoped collective-decision evidence."""
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
    if previous is not None and type(previous) is not CollectiveDecisionLedger:
        raise TypeError("previous must be CollectiveDecisionLedger or None")
    if previous is not None and previous.owner_id != identity.owner_id:
        _LOG.warning("collective_decision_carry_rejected reason=%s", "owner_mismatch")
        raise ValueError("previous owner_id mismatch")
    active_policy = default_collective_decision_policy() if policy is None else policy
    if type(active_policy) is not CollectiveDecisionPolicy:
        raise TypeError("policy must be CollectiveDecisionPolicy or None")
    owner_id = identity.owner_id
    base = previous or empty_collective_decision_ledger(owner_id)
    draft = _draft_from_ledger(base)
    tick = observation.tick
    if draft.last_observed_tick != tick:
        draft.first_observed_tick = (
            tick if draft.first_observed_tick is None else draft.first_observed_tick
        )
        draft.last_observed_tick = tick
        draft.observation_count += 1
    context_key = collective_context_key(observation)
    trust = _normalize_trust(speaker_trust)
    signals = _signals_from_observation(observation, identity, context_key)
    signals.extend(
        _signals_from_episodes(retrieved_memory_context, identity, context_key)
    )
    for signal in signals:
        confidence = signal.confidence
        if signal.actor_id is not None:
            confidence *= trust.get(signal.actor_id.value, 1.0)
        adjusted = _CollectiveSignal(
            act=signal.act,
            topic=signal.topic,
            proposal_ref=signal.proposal_ref,
            revision=signal.revision,
            context_key=signal.context_key,
            lineage_ref=signal.lineage_ref,
            root_ref=signal.root_ref,
            channel=signal.channel,
            actor_id=signal.actor_id,
            originator_id=signal.originator_id,
            action_token=signal.action_token,
            target_token=signal.target_token,
            terms=signal.terms,
            window_first_tick=signal.window_first_tick,
            window_last_tick=signal.window_last_tick,
            delegate_id=signal.delegate_id,
            retract_kind=signal.retract_kind,
            retract_id=signal.retract_id,
            claimed_status=signal.claimed_status,
            confidence=_quantize(confidence),
            independently_evidenced=signal.independently_evidenced,
        )
        _apply_signal(draft, adjusted, tick, active_policy)
    ledger = _freeze(draft, tick, active_policy)
    _LOG.info(
        "collective_decision_ledger_updated owner_id=%s proposal_count=%s "
        "position_count=%s outcome_count=%s",
        owner_id.value,
        len(ledger.proposals),
        len(ledger.positions),
        len(ledger.outcomes),
    )
    return ledger


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


# ---------------------------------------------------------------------------
# Bounded behavior preference and local influence attribution
# ---------------------------------------------------------------------------

_TOPIC_DIRECTION: Final[Mapping[CollectiveTopic, ActionDirection]] = {
    CollectiveTopic.COLLECTIVE_PROJECT: ActionDirection.HELP,
    CollectiveTopic.RESOURCE_ALLOCATION: ActionDirection.FEED,
    CollectiveTopic.MIGRATION: ActionDirection.MOVE,
    CollectiveTopic.SHARED_DEFENSE: ActionDirection.HELP,
    CollectiveTopic.STORAGE: ActionDirection.SEARCH,
    CollectiveTopic.NORM_ENFORCEMENT: ActionDirection.COMMUNICATE,
}


def collective_decision_topic_direction(
    topic: CollectiveTopic,
) -> ActionDirection:
    """Map a closed topic to an already-admissible action direction."""
    if type(topic) is not CollectiveTopic:
        raise TypeError("topic must be CollectiveTopic")
    return _TOPIC_DIRECTION[topic]


def classify_collective_decision_influence(
    *,
    preferred_direction: ActionDirection | None,
    baseline_direction: ActionDirection | None,
    final_direction: ActionDirection | None,
) -> tuple[CollectiveInfluenceKind, str | None]:
    """Classify a local comparison; never claim real-world causation.

    The comparison must use the same prepared candidate set and deterministic
    selection rules with only the decision preference disabled. Unsupported or
    side-effecting comparisons return ``UNAVAILABLE`` with a closed reason.
    """
    for value in (preferred_direction, baseline_direction, final_direction):
        if value is not None and type(value) is not ActionDirection:
            raise TypeError("directions must be ActionDirection or None")
    if preferred_direction is None or baseline_direction is None:
        return CollectiveInfluenceKind.UNAVAILABLE, "no_comparator"
    preference_changed = preferred_direction is not baseline_direction
    final_changed = (
        final_direction is not None and final_direction is not baseline_direction
    )
    if final_changed:
        return CollectiveInfluenceKind.FINAL_COMMAND_CHANGED, None
    if preference_changed:
        return CollectiveInfluenceKind.PREFERENCE_CHANGED, None
    return CollectiveInfluenceKind.EXECUTED, None


_COMPLIANCE_MATCH_KINDS: Final[Mapping[CollectiveTopic, frozenset[str]]] = {
    CollectiveTopic.COLLECTIVE_PROJECT: frozenset(
        {"collective_project_contributed", "collective_project_started"}
    ),
    CollectiveTopic.RESOURCE_ALLOCATION: frozenset(
        {"gave", "received", "exchanged", "traded"}
    ),
    CollectiveTopic.MIGRATION: frozenset({"move", "journey_started", "journey_ended"}),
    CollectiveTopic.SHARED_DEFENSE: frozenset({"helped", "help", "defended"}),
    CollectiveTopic.STORAGE: frozenset(
        {"deposited", "retrieved", "stored", "maintained"}
    ),
    CollectiveTopic.NORM_ENFORCEMENT: frozenset({"warned", "admonished", "mediated"}),
}
_COMPLIANCE_CONTRARY_KINDS: Final[Mapping[CollectiveTopic, frozenset[str]]] = {
    CollectiveTopic.COLLECTIVE_PROJECT: frozenset({"damaged", "opposed_public_good"}),
    CollectiveTopic.RESOURCE_ALLOCATION: frozenset({"took", "hoarded"}),
    CollectiveTopic.MIGRATION: frozenset({"fled", "retreated"}),
    CollectiveTopic.SHARED_DEFENSE: frozenset({"attacked", "abandoned"}),
    CollectiveTopic.STORAGE: frozenset({"destroyed", "scattered"}),
    CollectiveTopic.NORM_ENFORCEMENT: frozenset({"attacked", "punished"}),
}


def appraise_collective_compliance(
    ledger: object,
    observation: object,
    identity: object,
    *,
    policy: CollectiveDecisionPolicy | None = None,
) -> CollectiveDecisionLedger:
    """Append descriptive compliance appraisals for owner-visible actions.

    Death, unreachability, missing visibility, and run ending before a window
    closes remain ``UNKNOWN``; they are never classified as defiance.
    """
    if type(ledger) is not CollectiveDecisionLedger:
        raise TypeError("ledger must be CollectiveDecisionLedger")
    if type(observation) is not Observation:
        raise TypeError("observation must be Observation")
    if type(identity) is not OwnerSafeSocialIdentity:
        raise TypeError("identity must be OwnerSafeSocialIdentity")
    if identity.owner_id != ledger.owner_id:
        raise ValueError("identity owner_id mismatch")
    active_policy = default_collective_decision_policy() if policy is None else policy
    if type(active_policy) is not CollectiveDecisionPolicy:
        raise TypeError("policy must be CollectiveDecisionPolicy or None")
    proposals = {
        (proposal.proposal_ref, proposal.revision): proposal
        for proposal in ledger.proposals
        if proposal.actionable
    }
    if not proposals:
        return ledger
    tick = observation.tick
    existing = list(ledger.compliance)
    seen = {item.compliance_id for item in existing}
    occurrences = observation.occurrences
    for position in ledger.positions:
        if not position.active or position.stance is CollectivePositionStance.OPPOSE:
            continue
        proposal = proposals.get((position.proposal_ref, position.revision))
        if proposal is None:
            continue
        if tick < proposal.window_first_tick:
            continue
        actor_occurrences = (
            [
                item
                for item in occurrences
                if _actor_agent(identity, item.actor_id) == position.actor_id
            ]
            if tick <= proposal.window_last_tick
            else []
        )
        status = CollectiveComplianceStatus.UNKNOWN
        observed_kind: str | None = None
        for occurrence in actor_occurrences:
            if occurrence.kind == "died":
                status = CollectiveComplianceStatus.UNKNOWN
                observed_kind = occurrence.kind
                continue
            if occurrence.kind in _COMPLIANCE_MATCH_KINDS[proposal.topic]:
                status = CollectiveComplianceStatus.MATCHED
                observed_kind = occurrence.kind
                break
            if occurrence.kind in _COMPLIANCE_CONTRARY_KINDS[proposal.topic]:
                status = CollectiveComplianceStatus.CONTRARY
                observed_kind = occurrence.kind
                break
        window_last = min(tick, proposal.window_last_tick)
        compliance_id = _sha256_hex(
            f"{ledger.owner_id.value}|compliance|{position.proposal_ref}|"
            f"{position.revision}|{position.actor_id.value}|{tick}"
        )
        if compliance_id in seen:
            continue
        if len(existing) >= active_policy.max_compliance:
            break
        existing.append(
            CollectiveCompliance(
                compliance_id=compliance_id,
                actor_id=position.actor_id,
                proposal_ref=position.proposal_ref,
                revision=position.revision,
                status=status,
                window_first_tick=proposal.window_first_tick,
                window_last_tick=window_last,
                observed_action_token=observed_kind,
                tick=tick,
            )
        )
        seen.add(compliance_id)
    if len(existing) == len(ledger.compliance):
        return ledger
    return CollectiveDecisionLedger(
        owner_id=ledger.owner_id,
        proposals=ledger.proposals,
        positions=ledger.positions,
        delegations=ledger.delegations,
        retractions=ledger.retractions,
        outcomes=ledger.outcomes,
        compliance=tuple(existing),
        influence=ledger.influence,
        notices=ledger.notices,
        policy_version=ledger.policy_version,
        retired_proposal_refs=ledger.retired_proposal_refs,
        first_observed_tick=ledger.first_observed_tick,
        last_observed_tick=ledger.last_observed_tick,
        observation_count=ledger.observation_count,
        pruned_proposal_count=ledger.pruned_proposal_count,
        pruned_evidence_count=ledger.pruned_evidence_count,
        pruned_position_count=ledger.pruned_position_count,
        pruned_outcome_count=ledger.pruned_outcome_count,
    )


def _actor_agent(
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


@dataclass(frozen=True, slots=True)
class CollectiveDecisionBiasAudit:
    """Detached comparison of candidates before and after the decision bias."""

    proposal_ref: str
    revision: int
    preferred_direction: ActionDirection
    baseline_directions: tuple[ActionDirection, ...]
    biased_directions: tuple[ActionDirection, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "proposal_ref", _require_hex_id("proposal_ref", self.proposal_ref)
        )
        object.__setattr__(
            self, "revision", _require_nonneg_int("revision", self.revision)
        )
        if type(self.preferred_direction) is not ActionDirection:
            raise _fail("preferred_direction", "invalid_type")
        for name in ("baseline_directions", "biased_directions"):
            values = _require_tuple(name, getattr(self, name))
            checked: list[ActionDirection] = []
            for value in values:
                if type(value) is not ActionDirection:
                    raise _fail(name, "invalid_type")
                if value not in checked:
                    checked.append(value)
            object.__setattr__(self, name, tuple(checked))

    @property
    def changed_candidates(self) -> bool:
        return set(self.baseline_directions) != set(self.biased_directions)


@dataclass(frozen=True, slots=True)
class CollectiveDecisionPreference:
    """One supported proposal's bounded action-direction preference."""

    direction: ActionDirection
    proposal_ref: str
    revision: int

    def __post_init__(self) -> None:
        if type(self.direction) is not ActionDirection:
            raise _fail("preference.direction", "invalid_type")
        object.__setattr__(
            self, "proposal_ref", _require_hex_id("proposal_ref", self.proposal_ref)
        )
        object.__setattr__(
            self, "revision", _require_nonneg_int("preference.revision", self.revision)
        )


def collective_decision_preference(
    ledger: object | None,
    *,
    tick: int | None = None,
) -> CollectiveDecisionPreference | None:
    """Return the owner-supported proposal driving a bounded direction bias."""
    if type(ledger) is not CollectiveDecisionLedger:
        return None
    owner_id = ledger.owner_id
    for proposal in sorted(ledger.proposals, key=lambda item: item.proposal_id):
        if not proposal.actionable:
            continue
        if tick is not None and tick > proposal.window_last_tick:
            continue
        own = [
            item
            for item in ledger.positions
            if item.actor_id == owner_id
            and item.proposal_ref == proposal.proposal_ref
            and item.revision == proposal.revision
            and item.active
        ]
        latest = (
            None
            if not own
            else max(own, key=lambda item: (item.last_tick, item.position_id))
        )
        if latest is not None and latest.stance is CollectivePositionStance.OPPOSE:
            continue
        supported = (
            latest is not None
            and latest.stance
            in {CollectivePositionStance.SUPPORT, CollectivePositionStance.DELEGATE}
        ) or proposal.originator_id == owner_id
        if not supported:
            continue
        return CollectiveDecisionPreference(
            direction=_TOPIC_DIRECTION[proposal.topic],
            proposal_ref=proposal.proposal_ref,
            revision=proposal.revision,
        )
    return None


def collective_decision_direction_preference(
    ledger: object | None,
    *,
    tick: int | None = None,
) -> ActionDirection | None:
    """A bounded preference among admissible futures, never an obligation."""
    preference = collective_decision_preference(ledger, tick=tick)
    return None if preference is None else preference.direction


def append_collective_decision_influence(
    ledger: object,
    *,
    audit: CollectiveDecisionBiasAudit,
    final_direction: ActionDirection | None,
    tick: int,
    policy: CollectiveDecisionPolicy | None = None,
) -> CollectiveDecisionLedger:
    """Record one local attribution only when the bias changed the candidates.

    ``FINAL_COMMAND_CHANGED`` means the final command no longer matches the
    preferred direction; it does not claim the decision caused the execution.
    """
    if type(ledger) is not CollectiveDecisionLedger:
        raise TypeError("ledger must be CollectiveDecisionLedger")
    if type(audit) is not CollectiveDecisionBiasAudit:
        raise TypeError("audit must be CollectiveDecisionBiasAudit")
    active_policy = default_collective_decision_policy() if policy is None else policy
    if type(active_policy) is not CollectiveDecisionPolicy:
        raise TypeError("policy must be CollectiveDecisionPolicy or None")
    if not audit.changed_candidates:
        return ledger
    if final_direction is not None and type(final_direction) is not ActionDirection:
        raise TypeError("final_direction must be ActionDirection or None")
    kind = (
        CollectiveInfluenceKind.PREFERENCE_CHANGED
        if final_direction is audit.preferred_direction
        else CollectiveInfluenceKind.FINAL_COMMAND_CHANGED
    )
    if len(ledger.influence) >= active_policy.max_influence:
        return ledger
    influence_id = _sha256_hex(
        f"{ledger.owner_id.value}|influence|{audit.proposal_ref}|{audit.revision}|"
        f"{kind.value}|{tick}|{len(ledger.influence)}"
    )
    return CollectiveDecisionLedger(
        owner_id=ledger.owner_id,
        proposals=ledger.proposals,
        positions=ledger.positions,
        delegations=ledger.delegations,
        retractions=ledger.retractions,
        outcomes=ledger.outcomes,
        compliance=ledger.compliance,
        influence=(
            *ledger.influence,
            CollectiveInfluence(
                influence_id=influence_id,
                proposal_ref=audit.proposal_ref,
                revision=audit.revision,
                source_act=CollectiveAct.SUPPORT,
                kind=kind,
                strength=1.0,
                tick=tick,
            ),
        ),
        notices=ledger.notices,
        policy_version=ledger.policy_version,
        retired_proposal_refs=ledger.retired_proposal_refs,
        first_observed_tick=ledger.first_observed_tick,
        last_observed_tick=ledger.last_observed_tick,
        observation_count=ledger.observation_count,
        pruned_proposal_count=ledger.pruned_proposal_count,
        pruned_evidence_count=ledger.pruned_evidence_count,
        pruned_position_count=ledger.pruned_position_count,
        pruned_outcome_count=ledger.pruned_outcome_count,
    )


def _opportunity_topic(
    observation: Observation,
) -> tuple[CollectiveTopic, str, str | None]:
    """Closed, deterministic topic/action choice from owner-visible context."""
    for occurrence in observation.occurrences:
        if occurrence.kind.startswith("collective_project"):
            return (
                CollectiveTopic.COLLECTIVE_PROJECT,
                "start_project",
                "field",
            )
    for exit_item in observation.exits:
        return (
            CollectiveTopic.MIGRATION,
            "move",
            _require_token("destination", exit_item.destination_id.value),
        )
    if observation.visible_bodies:
        return (CollectiveTopic.SHARED_DEFENSE, "help", "neighbour")
    if observation.self_body is not None and observation.self_body.inventory:
        return (CollectiveTopic.STORAGE, "store", "carried")
    return (CollectiveTopic.NORM_ENFORCEMENT, "communicate", "peer")


def generate_collective_decision_proposal(
    ledger: object,
    observation: object,
    identity: object,
    *,
    policy: CollectiveDecisionPolicy | None = None,
) -> CollectiveDecisionLedger:
    """Create one owner-visible proposal when the ledger has none actionable.

    The proposal is a tentative course, not evidence of peer support, adoption,
    or legitimacy. Repeated ticks reuse the existing proposal instead of
    flooding the ledger.
    """
    if type(ledger) is not CollectiveDecisionLedger:
        raise TypeError("ledger must be CollectiveDecisionLedger")
    if type(observation) is not Observation:
        raise TypeError("observation must be Observation")
    if type(identity) is not OwnerSafeSocialIdentity:
        raise TypeError("identity must be OwnerSafeSocialIdentity")
    if identity.owner_id != ledger.owner_id:
        raise ValueError("identity owner_id mismatch")
    active_policy = default_collective_decision_policy() if policy is None else policy
    if type(active_policy) is not CollectiveDecisionPolicy:
        raise TypeError("policy must be CollectiveDecisionPolicy or None")
    tick = observation.tick
    if any(
        proposal.window_last_tick >= tick
        and proposal.status
        in {CollectiveProposalStatus.ACTIVE, CollectiveProposalStatus.DRAFT}
        for proposal in ledger.proposals
    ):
        return ledger
    if len(ledger.proposals) >= active_policy.max_proposals:
        return ledger
    topic, action, target = _opportunity_topic(observation)
    context_key = collective_context_key(observation)
    ref = collective_proposal_ref(
        ledger.owner_id,
        originator_id=ledger.owner_id,
        topic=topic,
        context_key=context_key,
        inception_tick=tick,
        inception_lineage=f"opportunity-{action}",
    )
    lineage = f"opportunity-{tick}-{action}"
    evidence = CollectiveEvidence(
        evidence_id=collective_decision_evidence_id(
            ref, 0, CollectiveEvidenceChannel.OBSERVED, lineage
        ),
        ordinal=0,
        channel=CollectiveEvidenceChannel.OBSERVED,
        lineage_ref=lineage,
        root_ref=f"opportunity|{topic.value}|{tick}",
        tick=tick,
        actor_id=ledger.owner_id,
    )
    proposal = CollectiveProposal(
        proposal_id=collective_proposal_id(ledger.owner_id, ref, 0),
        owner_id=ledger.owner_id,
        proposal_ref=ref,
        revision=0,
        topic=topic,
        context_key=context_key,
        action_token=action,
        first_tick=tick,
        last_tick=tick,
        window_first_tick=tick,
        window_last_tick=tick + active_policy.default_proposal_window,
        status=CollectiveProposalStatus.ACTIVE,
        originator_id=ledger.owner_id,
        target_token=target,
        evidence=(evidence,),
    )
    _LOG.debug(
        "collective_decision_proposal_generated owner_id=%s topic=%s tick=%s",
        ledger.owner_id.value,
        topic.value,
        tick,
    )
    return CollectiveDecisionLedger(
        owner_id=ledger.owner_id,
        proposals=(*ledger.proposals, proposal),
        positions=ledger.positions,
        delegations=ledger.delegations,
        retractions=ledger.retractions,
        outcomes=ledger.outcomes,
        compliance=ledger.compliance,
        influence=ledger.influence,
        notices=ledger.notices,
        policy_version=ledger.policy_version,
        retired_proposal_refs=ledger.retired_proposal_refs,
        first_observed_tick=ledger.first_observed_tick,
        last_observed_tick=ledger.last_observed_tick,
        observation_count=ledger.observation_count,
        pruned_proposal_count=ledger.pruned_proposal_count,
        pruned_evidence_count=ledger.pruned_evidence_count,
        pruned_position_count=ledger.pruned_position_count,
        pruned_outcome_count=ledger.pruned_outcome_count,
    )
