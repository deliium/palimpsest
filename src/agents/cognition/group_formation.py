"""Owner-scoped membership beliefs and optional group concepts.

A ledger is private to one agent. It is not a team, a semantic belief, a
reputation profile, or a territorial claim. This module reads the owner's
observation, identity projection, and caller-supplied trust floats. It does
not read world authority, another agent's ledger, or an analysis aggregate.
"""

from __future__ import annotations

import hashlib
import logging
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum
from typing import Final

from agents.cognition.models import OwnerSafeSocialIdentity
from agents.models import AgentId
from world.identifiers import EntityId, require_exact_nonneg_int, require_stable_id
from world.observations import (
    Observation,
    ObservedCommunication,
    ObservedOccurrence,
    VisibleBody,
)

_LOG: Final[logging.Logger] = logging.getLogger("agents.cognition.group_formation")

GROUP_FORMATION_POLICY_VERSION: Final[str] = "group-formation.v1"
_QUANTUM: Final[Decimal] = Decimal("0.000001")
_CONCEPT_THRESHOLD: Final[float] = 0.40
_RETIRE_THRESHOLD: Final[float] = 0.20
_DECAY: Final[float] = 0.05
_TRUST_FLOOR: Final[float] = 0.60
_MERGE_JACCARD: Final[float] = 0.5
_MAX_BELIEFS: Final[int] = 16
_MAX_CONCEPTS: Final[int] = 8
_MAX_EVIDENCE: Final[int] = 64
_MIN_SET_SIZE: Final[int] = 2
_MAX_SET_SIZE: Final[int] = 8
_PROXIMITY_DELTA: Final[float] = 0.10
_TRUST_DELTA: Final[float] = 0.10
_ASSISTANCE_DELTA: Final[float] = 0.25
_EXCHANGE_DELTA: Final[float] = 0.30
_COMMUNICATION_DELTA: Final[float] = 0.20
_SHARED_HARM_DELTA: Final[float] = 0.20
_HEX: Final[frozenset[str]] = frozenset("0123456789abcdef")
_RETIRE_REASONS: Final[frozenset[str]] = frozenset({"promoted", "decay"})
_NOTICE_REASONS: Final[frozenset[str]] = frozenset(
    {
        "cap_exceeded",
        "ignored_kind",
        "hop_dropped",
        "unresolved_entity",
        "no_social_evidence",
        "below_threshold",
        "proximity_only",
        "stance_mismatch",
        "merge_blocked",
        "remainder_too_small",
    }
)
_FORBIDDEN_TYPES: Final[frozenset[str]] = frozenset(
    {"WorldState", "WorldEvent", "PhysicalRules", "AgentBody"}
)


class GroupStance(StrEnum):
    """Closed private wording for a member set."""

    WE = "we"
    OUR_GROUP = "our_group"
    THOSE_AGENTS = "those_agents"


class GroupChannel(StrEnum):
    """Closed provenance channel for one contribution."""

    PROXIMITY = "proximity"
    TRUST = "trust"
    ASSISTANCE = "assistance"
    EXCHANGE = "exchange"
    COMMUNICATION = "communication"
    SHARED_HARM = "shared_harm"


class GroupStatus(StrEnum):
    """Closed lifecycle for one belief or concept."""

    ACTIVE = "active"
    RETIRED = "retired"
    SPLIT = "split"
    MERGED = "merged"


def _fail(field_name: str, code: str) -> ValueError:
    _LOG.error(
        "group_validation_failed field=%s reason_code=%s",
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


def _unit(field_name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _fail(field_name, "not_finite")
    number = float(value)
    if not math.isfinite(number):
        raise _fail(field_name, "not_finite")
    if number < 0.0 or number > 1.0:
        raise _fail(field_name, "out_of_range")
    quantized = _quantize(number)
    if quantized < 0.0 or quantized > 1.0:
        raise _fail(field_name, "out_of_range")
    return quantized


def _require_hex_id(field_name: str, value: object, code: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(char not in _HEX for char in value)
    ):
        raise _fail(field_name, code)
    return value


def _require_tuple(field_name: str, values: object) -> tuple[object, ...]:
    if isinstance(values, (str, bytes, set, frozenset)) or not isinstance(
        values, Sequence
    ):
        raise _fail(field_name, "invalid_type")
    return tuple(values)


def _locked_unit(field_name: str, value: object, expected: float) -> float:
    quantized = _unit(field_name, value)
    if quantized != _quantize(expected):
        raise _fail(field_name, "unsupported_policy")
    return quantized


def _locked_int(field_name: str, value: object, expected: int) -> int:
    if isinstance(value, bool) or type(value) is not int:
        raise _fail(field_name, "invalid_type")
    if value != expected:
        raise _fail(field_name, "unsupported_policy")
    return value


def _member_key(members: Sequence[AgentId]) -> tuple[str, ...]:
    return tuple(member.value for member in members)


def group_belief_id(
    owner_id: AgentId,
    stance: GroupStance,
    member_ids: Sequence[AgentId],
) -> str:
    """sha256 of owner id, stance, and sorted member ids."""
    if type(owner_id) is not AgentId:
        raise _fail("owner_id", "invalid_type")
    if type(stance) is not GroupStance:
        raise _fail("stance", "unknown_stance")
    members = _validated_members(owner_id, stance, member_ids)
    material = f"{owner_id.value}|{stance.value}|{','.join(_member_key(members))}"
    return _sha256_hex(material)


def group_concept_id(belief_id: str) -> str:
    """sha256 of the backing belief id and the literal ``concept``."""
    head = _require_hex_id("belief_id", belief_id, "invalid_belief_id")
    return _sha256_hex(f"{head}|concept")


def group_evidence_id(
    *,
    belief_id: str,
    ordinal: int,
    channel: GroupChannel,
    lineage_ref: str,
) -> str:
    """sha256 of belief id, ordinal, channel, and lineage ref."""
    head = _require_hex_id("belief_id", belief_id, "invalid_belief_id")
    if type(channel) is not GroupChannel:
        raise _fail("channel", "unknown_channel")
    try:
        ordinal_value = require_exact_nonneg_int("ordinal", ordinal)
    except ValueError as exc:
        raise _fail("ordinal", "invalid_ordinal") from exc
    try:
        lineage = require_stable_id("lineage_ref", lineage_ref)
    except ValueError as exc:
        raise _fail("lineage_ref", "invalid_lineage") from exc
    material = f"{head}|{ordinal_value}|{channel.value}|{lineage}"
    return _sha256_hex(material)


def _validated_members(
    owner_id: AgentId,
    stance: GroupStance,
    member_ids: object,
) -> tuple[AgentId, ...]:
    raw = _require_tuple("member_ids", member_ids)
    members: list[AgentId] = []
    seen: set[str] = set()
    for item in raw:
        if type(item) is not AgentId:
            raise _fail("member_ids", "invalid_type")
        if item.value in seen:
            raise _fail("member_ids", "duplicate_member")
        seen.add(item.value)
        members.append(item)
    if len(members) < _MIN_SET_SIZE or len(members) > _MAX_SET_SIZE:
        raise _fail("member_ids", "set_size")
    ordered = tuple(sorted(members, key=lambda member: member.value))
    owner_present = any(member == owner_id for member in ordered)
    if stance is GroupStance.THOSE_AGENTS and owner_present:
        raise _fail("member_ids", "owner_in_exclusive")
    if stance is not GroupStance.THOSE_AGENTS and not owner_present:
        raise _fail("member_ids", "owner_missing")
    return ordered


def _validated_parent_ids(values: object) -> tuple[str, ...]:
    raw = _require_tuple("parent_ids", values)
    checked: list[str] = []
    seen: set[str] = set()
    for item in raw:
        parent = _require_hex_id("parent_ids", item, "invalid_parent_id")
        if parent in seen:
            raise _fail("parent_ids", "duplicate_parent")
        seen.add(parent)
        checked.append(parent)
    return tuple(checked)


@dataclass(frozen=True, slots=True)
class GroupEvidenceItem:
    """One witnessed contribution. The id is derived; it is not chosen by RNG."""

    belief_id: str
    channel: GroupChannel
    lineage_ref: str
    ordinal: int
    tick: int
    actor_id: AgentId
    counterpart_id: AgentId
    evidence_id: str = field(init=False)

    def __post_init__(self) -> None:
        head = _require_hex_id("belief_id", self.belief_id, "invalid_belief_id")
        if type(self.channel) is not GroupChannel:
            raise _fail("channel", "unknown_channel")
        if type(self.actor_id) is not AgentId:
            raise _fail("actor_id", "invalid_type")
        if type(self.counterpart_id) is not AgentId:
            raise _fail("counterpart_id", "invalid_type")
        if self.actor_id == self.counterpart_id:
            raise _fail("counterpart_id", "duplicate_member")
        try:
            lineage = require_stable_id("lineage_ref", self.lineage_ref)
        except ValueError as exc:
            raise _fail("lineage_ref", "invalid_lineage") from exc
        try:
            ordinal = require_exact_nonneg_int("ordinal", self.ordinal)
        except ValueError as exc:
            raise _fail("ordinal", "invalid_ordinal") from exc
        try:
            tick = require_exact_nonneg_int("tick", self.tick)
        except ValueError as exc:
            raise _fail("tick", "invalid_tick") from exc
        object.__setattr__(self, "belief_id", head)
        object.__setattr__(self, "lineage_ref", lineage)
        object.__setattr__(self, "ordinal", ordinal)
        object.__setattr__(self, "tick", tick)
        object.__setattr__(
            self,
            "evidence_id",
            group_evidence_id(
                belief_id=head,
                ordinal=ordinal,
                channel=self.channel,
                lineage_ref=lineage,
            ),
        )


@dataclass(frozen=True, slots=True)
class GroupMembershipBelief:
    """One owner's stance toward one member set."""

    belief_id: str
    owner_id: AgentId
    stance: GroupStance
    member_ids: tuple[AgentId, ...]
    support: float
    social_evidence: bool
    status: GroupStatus
    evidence: tuple[GroupEvidenceItem, ...] = ()
    parent_ids: tuple[str, ...] = ()
    retire_reason: str | None = None

    def __post_init__(self) -> None:
        if type(self.owner_id) is not AgentId:
            raise _fail("owner_id", "invalid_type")
        if type(self.stance) is not GroupStance:
            raise _fail("stance", "unknown_stance")
        if type(self.status) is not GroupStatus:
            raise _fail("status", "unknown_status")
        if type(self.social_evidence) is not bool:
            raise _fail("social_evidence", "invalid_type")
        members = _validated_members(self.owner_id, self.stance, self.member_ids)
        head = _require_hex_id("belief_id", self.belief_id, "invalid_belief_id")
        expected = group_belief_id(self.owner_id, self.stance, members)
        if head != expected:
            raise _fail("belief_id", "belief_id_mismatch")
        if self.retire_reason is not None and self.retire_reason not in _RETIRE_REASONS:
            raise _fail("retire_reason", "invalid_retire_reason")
        parents = _validated_parent_ids(self.parent_ids)
        evidence = _require_tuple("evidence", self.evidence)
        if len(evidence) > _MAX_EVIDENCE:
            raise _fail("evidence", "cap_exceeded")
        seen: set[tuple[GroupChannel, str]] = set()
        checked: list[GroupEvidenceItem] = []
        member_values = {member.value for member in members}
        for ordinal, item in enumerate(evidence):
            if type(item) is not GroupEvidenceItem:
                raise _fail("evidence", "invalid_type")
            if item.belief_id != head or item.ordinal != ordinal:
                raise _fail("evidence", "evidence_id_mismatch")
            if (
                item.actor_id.value not in member_values
                or item.counterpart_id.value not in member_values
            ):
                raise _fail("evidence", "member_mismatch")
            key = (item.channel, item.lineage_ref)
            if key in seen:
                raise _fail("evidence", "duplicate_evidence")
            seen.add(key)
            checked.append(item)
        object.__setattr__(self, "belief_id", head)
        object.__setattr__(self, "member_ids", members)
        object.__setattr__(self, "support", _unit("support", self.support))
        object.__setattr__(self, "parent_ids", parents)
        object.__setattr__(self, "evidence", tuple(checked))


@dataclass(frozen=True, slots=True)
class GroupConcept:
    """Optional record minted only from socially evidenced membership."""

    concept_id: str
    belief_id: str
    owner_id: AgentId
    stance: GroupStance
    member_ids: tuple[AgentId, ...]
    support: float
    social_evidence: bool
    status: GroupStatus
    parent_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if type(self.owner_id) is not AgentId:
            raise _fail("owner_id", "invalid_type")
        if type(self.stance) is not GroupStance:
            raise _fail("stance", "unknown_stance")
        if self.stance is GroupStance.WE:
            raise _fail("stance", "concept_stance")
        if type(self.status) is not GroupStatus:
            raise _fail("status", "unknown_status")
        if type(self.social_evidence) is not bool:
            raise _fail("social_evidence", "invalid_type")
        if self.social_evidence is not True:
            raise _fail("social_evidence", "social_evidence_required")
        members = _validated_members(self.owner_id, self.stance, self.member_ids)
        belief = _require_hex_id("belief_id", self.belief_id, "invalid_belief_id")
        expected_belief = group_belief_id(self.owner_id, self.stance, members)
        if belief != expected_belief:
            raise _fail("belief_id", "belief_id_mismatch")
        concept = _require_hex_id("concept_id", self.concept_id, "invalid_concept_id")
        if concept != group_concept_id(belief):
            raise _fail("concept_id", "concept_id_mismatch")
        object.__setattr__(self, "belief_id", belief)
        object.__setattr__(self, "concept_id", concept)
        object.__setattr__(self, "member_ids", members)
        object.__setattr__(self, "support", _unit("support", self.support))
        object.__setattr__(self, "parent_ids", _validated_parent_ids(self.parent_ids))


@dataclass(frozen=True, slots=True)
class GroupLedger:
    """Private beliefs and concepts owned by one agent."""

    owner_id: AgentId
    beliefs: tuple[GroupMembershipBelief, ...] = ()
    concepts: tuple[GroupConcept, ...] = ()
    notices: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if type(self.owner_id) is not AgentId:
            raise _fail("owner_id", "invalid_type")
        beliefs = _require_tuple("beliefs", self.beliefs)
        if len(beliefs) > _MAX_BELIEFS:
            raise _fail("beliefs", "cap_exceeded")
        seen_beliefs: set[str] = set()
        checked_beliefs: list[GroupMembershipBelief] = []
        for item in beliefs:
            if type(item) is not GroupMembershipBelief:
                raise _fail("beliefs", "invalid_type")
            if item.owner_id != self.owner_id:
                raise _fail("beliefs.owner_id", "owner_mismatch")
            if item.belief_id in seen_beliefs:
                raise _fail("beliefs", "duplicate_belief")
            seen_beliefs.add(item.belief_id)
            checked_beliefs.append(item)
        concepts = _require_tuple("concepts", self.concepts)
        if len(concepts) > _MAX_CONCEPTS:
            raise _fail("concepts", "cap_exceeded")
        seen_concepts: set[str] = set()
        checked_concepts: list[GroupConcept] = []
        for item in concepts:
            if type(item) is not GroupConcept:
                raise _fail("concepts", "invalid_type")
            if item.owner_id != self.owner_id:
                raise _fail("concepts.owner_id", "owner_mismatch")
            if item.belief_id not in seen_beliefs:
                raise _fail("concepts.belief_id", "belief_missing")
            if item.concept_id in seen_concepts:
                raise _fail("concepts", "duplicate_concept")
            seen_concepts.add(item.concept_id)
            checked_concepts.append(item)
        notices = _require_tuple("notices", self.notices)
        checked_notices: list[str] = []
        seen_notices: set[str] = set()
        for item in notices:
            if not isinstance(item, str) or item not in _NOTICE_REASONS:
                raise _fail("notices", "invalid_notice")
            if item in seen_notices:
                raise _fail("notices", "duplicate_notice")
            seen_notices.add(item)
            checked_notices.append(item)
        object.__setattr__(self, "beliefs", tuple(checked_beliefs))
        object.__setattr__(self, "concepts", tuple(checked_concepts))
        object.__setattr__(self, "notices", tuple(checked_notices))
        _LOG.debug(
            "group_ledger_constructed owner_id=%s policy_version=%s "
            "belief_count=%s concept_count=%s",
            self.owner_id.value,
            GROUP_FORMATION_POLICY_VERSION,
            len(self.beliefs),
            len(self.concepts),
        )


@dataclass(frozen=True, slots=True)
class GroupFormationPolicy:
    """Locked group constants. Runner JSON does not carry these weights."""

    version: str = GROUP_FORMATION_POLICY_VERSION
    concept_threshold: float = _CONCEPT_THRESHOLD
    retire_threshold: float = _RETIRE_THRESHOLD
    decay: float = _DECAY
    trust_floor: float = _TRUST_FLOOR
    merge_jaccard: float = _MERGE_JACCARD
    max_beliefs: int = _MAX_BELIEFS
    max_concepts: int = _MAX_CONCEPTS
    max_evidence: int = _MAX_EVIDENCE
    min_set_size: int = _MIN_SET_SIZE
    max_set_size: int = _MAX_SET_SIZE

    def __post_init__(self) -> None:
        if self.version != GROUP_FORMATION_POLICY_VERSION:
            raise _fail("version", "unsupported_policy")
        units = (
            ("concept_threshold", _CONCEPT_THRESHOLD),
            ("retire_threshold", _RETIRE_THRESHOLD),
            ("decay", _DECAY),
            ("trust_floor", _TRUST_FLOOR),
            ("merge_jaccard", _MERGE_JACCARD),
        )
        for name, expected in units:
            object.__setattr__(
                self, name, _locked_unit(name, getattr(self, name), expected)
            )
        counts = (
            ("max_beliefs", _MAX_BELIEFS),
            ("max_concepts", _MAX_CONCEPTS),
            ("max_evidence", _MAX_EVIDENCE),
            ("min_set_size", _MIN_SET_SIZE),
            ("max_set_size", _MAX_SET_SIZE),
        )
        for name, expected in counts:
            object.__setattr__(
                self, name, _locked_int(name, getattr(self, name), expected)
            )
        _LOG.debug(
            "group_policy_constructed policy_version=%s",
            self.version,
        )


def default_group_formation_policy() -> GroupFormationPolicy:
    """Return the only accepted group-formation policy."""
    return GroupFormationPolicy()


def empty_group_ledger(owner_id: AgentId) -> GroupLedger:
    """Ledger with no beliefs. Disabled mode does not call this."""
    return GroupLedger(owner_id=owner_id)


def require_owner_group_formation(
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
    if type(ledger) is not GroupLedger:
        raise TypeError(f"{field_name} must be GroupLedger")
    if ledger.owner_id != owner_id:
        _LOG.error(
            "group_validation_failed field=%s reason_code=%s",
            field_name,
            "owner_mismatch",
        )
        raise ValueError(f"{field_name} owner_id mismatch")


@dataclass
class _EvidenceDraft:
    channel: GroupChannel
    lineage_ref: str
    tick: int
    actor_id: AgentId
    counterpart_id: AgentId


@dataclass
class _BeliefDraft:
    stance: GroupStance
    members: tuple[AgentId, ...]
    support: float
    social_evidence: bool
    status: GroupStatus
    evidence: list[_EvidenceDraft]
    parent_ids: tuple[str, ...]
    retire_reason: str | None
    touched: bool
    keep: bool = False


@dataclass
class _ConceptDraft:
    stance: GroupStance
    members: tuple[AgentId, ...]
    support: float
    social_evidence: bool
    status: GroupStatus
    parent_ids: tuple[str, ...]


def _reject_forbidden(value: object) -> None:
    if value is None or isinstance(value, (str, int, float, bool)):
        return
    name = type(value).__name__
    module = type(value).__module__
    if (
        name in _FORBIDDEN_TYPES
        or "Cluster" in name
        or module.startswith("analysis")
        or module.startswith("analysis.")
    ):
        raise TypeError(f"{name}: forbidden_input")


def _sign(before: float, after: float) -> str:
    if after > before:
        return "positive"
    if after < before:
        return "negative"
    return "zero"


def _log_applied(
    owner_id: AgentId, tick: int, channel: GroupChannel, sign: str
) -> None:
    _LOG.debug(
        "group_belief_applied owner_id=%s tick=%s channel=%s sign=%s",
        owner_id.value,
        tick,
        channel.value,
        sign,
    )


def _log_drop(owner_id: AgentId, reason: str) -> None:
    _LOG.warning(
        "group_evidence_dropped owner_id=%s reason=%s",
        owner_id.value,
        reason,
    )


def _log_withheld(owner_id: AgentId, reason: str) -> None:
    _LOG.warning(
        "group_concept_withheld owner_id=%s reason=%s",
        owner_id.value,
        reason,
    )


def _log_minted(
    owner_id: AgentId, tick: int, stance: GroupStance, status: GroupStatus
) -> None:
    _LOG.debug(
        "group_concept_minted owner_id=%s tick=%s stance=%s status=%s",
        owner_id.value,
        tick,
        stance.value,
        status.value,
    )


def _log_retired(
    owner_id: AgentId, tick: int, stance: GroupStance, status: GroupStatus
) -> None:
    _LOG.debug(
        "group_concept_retired owner_id=%s tick=%s stance=%s status=%s",
        owner_id.value,
        tick,
        stance.value,
        status.value,
    )


def _sorted_members(members: Sequence[AgentId]) -> tuple[AgentId, ...]:
    return tuple(sorted(members, key=lambda member: member.value))


def _belief_id_of(owner_id: AgentId, draft: _BeliefDraft) -> str:
    return group_belief_id(owner_id, draft.stance, draft.members)


def _concept_id_of(owner_id: AgentId, draft: _ConceptDraft) -> str:
    return group_concept_id(group_belief_id(owner_id, draft.stance, draft.members))


def _same_members(left: Sequence[AgentId], right: Sequence[AgentId]) -> bool:
    return _member_key(left) == _member_key(right)


def _find_belief(
    beliefs: Sequence[_BeliefDraft],
    stance: GroupStance,
    members: Sequence[AgentId],
) -> _BeliefDraft | None:
    for belief in beliefs:
        if belief.stance is stance and _same_members(belief.members, members):
            return belief
    return None


def _find_concept(
    concepts: Sequence[_ConceptDraft],
    stance: GroupStance,
    members: Sequence[AgentId],
) -> _ConceptDraft | None:
    for concept in concepts:
        if concept.stance is stance and _same_members(concept.members, members):
            return concept
    return None


def _age(belief: _BeliefDraft) -> int:
    if not belief.evidence:
        return 10**9
    return min(item.tick for item in belief.evidence)


def _lineage_taken(
    beliefs: Sequence[_BeliefDraft], channel: GroupChannel, lineage_ref: str
) -> bool:
    for belief in beliefs:
        for item in belief.evidence:
            if item.channel is channel and item.lineage_ref == lineage_ref:
                return True
    return False


def _inclusive_target(
    beliefs: list[_BeliefDraft], members: tuple[AgentId, ...]
) -> _BeliefDraft | None:
    active_group = None
    active_we = None
    retired = None
    for belief in beliefs:
        if not _same_members(belief.members, members):
            continue
        if belief.stance is GroupStance.THOSE_AGENTS:
            continue
        if (
            belief.status is GroupStatus.ACTIVE
            and belief.stance is GroupStance.OUR_GROUP
        ):
            active_group = belief
        elif belief.status is GroupStatus.ACTIVE and belief.stance is GroupStance.WE:
            active_we = belief
        elif (
            belief.status is GroupStatus.RETIRED
            and belief.stance is GroupStance.OUR_GROUP
        ):
            retired = belief
        elif (
            belief.status is GroupStatus.RETIRED
            and belief.stance is GroupStance.WE
            and retired is None
        ):
            retired = belief
    if active_group is not None:
        return active_group
    if active_we is not None:
        return active_we
    return retired


def _exclusive_target(
    beliefs: list[_BeliefDraft], members: tuple[AgentId, ...]
) -> _BeliefDraft | None:
    retired = None
    for belief in beliefs:
        if belief.stance is not GroupStance.THOSE_AGENTS:
            continue
        if not _same_members(belief.members, members):
            continue
        if belief.status is GroupStatus.ACTIVE:
            return belief
        if belief.status is GroupStatus.RETIRED and retired is None:
            retired = belief
    return retired


def _shrink_beliefs(
    beliefs: list[_BeliefDraft],
    owner_id: AgentId,
    policy: GroupFormationPolicy,
    notices: list[str],
) -> None:
    del notices
    while len(beliefs) > policy.max_beliefs:
        inactive = [
            belief
            for belief in beliefs
            if belief.status is not GroupStatus.ACTIVE and not belief.keep
        ]
        if not inactive:
            inactive = [
                belief for belief in beliefs if belief.status is not GroupStatus.ACTIVE
            ]
        if not inactive:
            return
        oldest = min(
            inactive,
            key=lambda belief: (_age(belief), _belief_id_of(owner_id, belief)),
        )
        beliefs.remove(oldest)


def _shrink_concepts(
    concepts: list[_ConceptDraft],
    owner_id: AgentId,
    policy: GroupFormationPolicy,
    notices: list[str],
) -> None:
    while len(concepts) > policy.max_concepts:
        inactive = [
            concept for concept in concepts if concept.status is not GroupStatus.ACTIVE
        ]
        if not inactive:
            return
        inactive.sort(key=lambda concept: _concept_id_of(owner_id, concept))
        concepts.remove(inactive[0])


def _add_evidence(
    *,
    beliefs: list[_BeliefDraft],
    owner_id: AgentId,
    members: tuple[AgentId, ...],
    stance: GroupStance,
    channel: GroupChannel,
    lineage_ref: str,
    tick: int,
    actor_id: AgentId,
    counterpart_id: AgentId,
    delta: float,
    policy: GroupFormationPolicy,
    notices: list[str],
) -> None:
    if _lineage_taken(beliefs, channel, lineage_ref):
        _log_applied(owner_id, tick, channel, "zero")
        return
    if stance is GroupStance.THOSE_AGENTS:
        target = _exclusive_target(beliefs, members)
    else:
        target = _inclusive_target(beliefs, members)
    if target is None:
        if len(beliefs) >= policy.max_beliefs:
            _shrink_beliefs(beliefs, owner_id, policy, notices)
        if len(beliefs) >= policy.max_beliefs:
            notices.append("cap_exceeded")
            _log_drop(owner_id, "cap_exceeded")
            return
        target = _BeliefDraft(
            stance=stance,
            members=members,
            support=0.0,
            social_evidence=False,
            status=GroupStatus.ACTIVE,
            evidence=[],
            parent_ids=(),
            retire_reason=None,
            touched=True,
        )
        beliefs.append(target)
    elif target.status in {GroupStatus.SPLIT, GroupStatus.MERGED}:
        return
    elif target.status is GroupStatus.RETIRED:
        target.status = GroupStatus.ACTIVE
        target.retire_reason = None
    if len(target.evidence) >= policy.max_evidence:
        notices.append("cap_exceeded")
        _log_drop(owner_id, "cap_exceeded")
        return
    before = target.support
    target.support = _apply_delta(before, delta)
    target.evidence.append(
        _EvidenceDraft(
            channel=channel,
            lineage_ref=lineage_ref,
            tick=tick,
            actor_id=actor_id,
            counterpart_id=counterpart_id,
        )
    )
    target.touched = True
    _log_applied(owner_id, tick, channel, _sign(before, target.support))


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


def _lineage_for(tick: int, ordinal: int, event_id: object) -> str:
    if event_id is None:
        return f"tick-{tick}-{ordinal}"
    value = getattr(event_id, "value", None)
    if isinstance(value, str) and value:
        return value
    return f"tick-{tick}-{ordinal}"


def _hop_count(communication: ObservedCommunication) -> int | None:
    utterance = getattr(communication, "utterance", None)
    declared = getattr(utterance, "declared", None)
    hop = getattr(declared, "hop_count", None)
    if isinstance(hop, bool) or type(hop) is not int or hop < 0:
        return None
    return hop


def _reciprocal(items: Sequence[_EvidenceDraft], channel: GroupChannel) -> bool:
    directions = {
        (item.actor_id.value, item.counterpart_id.value)
        for item in items
        if item.channel is channel
    }
    return any((other, actor) in directions for actor, other in directions)


def _refresh_social(belief: _BeliefDraft, owner_id: AgentId) -> None:
    if belief.social_evidence:
        return
    channels = {item.channel for item in belief.evidence}
    if GroupChannel.COMMUNICATION in channels:
        belief.social_evidence = True
        return
    owner_in = any(member == owner_id for member in belief.members)
    for channel in (GroupChannel.ASSISTANCE, GroupChannel.EXCHANGE):
        if channel not in channels:
            continue
        if not owner_in or _reciprocal(belief.evidence, channel):
            belief.social_evidence = True
            return


def _mint_concept(
    *,
    concepts: list[_ConceptDraft],
    owner_id: AgentId,
    tick: int,
    stance: GroupStance,
    members: tuple[AgentId, ...],
    support: float,
    social_evidence: bool,
    parent_ids: tuple[str, ...],
    policy: GroupFormationPolicy,
    notices: list[str],
) -> _ConceptDraft | None:
    below_concept = support < policy.concept_threshold
    if stance is GroupStance.WE or not social_evidence or below_concept:
        return None
    existing = _find_concept(concepts, stance, members)
    if existing is not None and existing.status is GroupStatus.ACTIVE:
        existing.support = support
        existing.social_evidence = True
        return existing
    if existing is not None and existing.status is GroupStatus.RETIRED:
        existing.status = GroupStatus.ACTIVE
        existing.support = support
        existing.social_evidence = True
        existing.parent_ids = parent_ids or existing.parent_ids
        _log_minted(owner_id, tick, stance, GroupStatus.ACTIVE)
        return existing
    if len(concepts) >= policy.max_concepts:
        _shrink_concepts(concepts, owner_id, policy, notices)
    if len(concepts) >= policy.max_concepts:
        notices.append("cap_exceeded")
        _log_drop(owner_id, "cap_exceeded")
        return None
    concept = _ConceptDraft(
        stance=stance,
        members=members,
        support=support,
        social_evidence=True,
        status=GroupStatus.ACTIVE,
        parent_ids=parent_ids,
    )
    concepts.append(concept)
    _log_minted(owner_id, tick, stance, GroupStatus.ACTIVE)
    return concept


def _promote(
    beliefs: list[_BeliefDraft],
    concepts: list[_ConceptDraft],
    owner_id: AgentId,
    tick: int,
    policy: GroupFormationPolicy,
    notices: list[str],
) -> None:
    for belief in list(beliefs):
        we_is_active = (
            belief.status is GroupStatus.ACTIVE and belief.stance is GroupStance.WE
        )
        if not we_is_active:
            continue
        if not belief.social_evidence or belief.support < policy.concept_threshold:
            continue
        belief.status = GroupStatus.RETIRED
        belief.retire_reason = "promoted"
        belief.keep = True
        belief.touched = True
        current = _find_belief(beliefs, GroupStance.OUR_GROUP, belief.members)
        if current is None:
            current = _BeliefDraft(
                stance=GroupStance.OUR_GROUP,
                members=belief.members,
                support=belief.support,
                social_evidence=True,
                status=GroupStatus.ACTIVE,
                evidence=list(belief.evidence),
                parent_ids=(),
                retire_reason=None,
                touched=True,
            )
            beliefs.append(current)
        else:
            current.support = max(current.support, belief.support)
            current.social_evidence = True
            current.status = GroupStatus.ACTIVE
            current.retire_reason = None
            current.touched = True
            seen = {(item.channel, item.lineage_ref) for item in current.evidence}
            for item in belief.evidence:
                key = (item.channel, item.lineage_ref)
                if key not in seen:
                    current.evidence.append(item)
                    seen.add(key)
        _mint_concept(
            concepts=concepts,
            owner_id=owner_id,
            tick=tick,
            stance=GroupStance.OUR_GROUP,
            members=current.members,
            support=current.support,
            social_evidence=True,
            parent_ids=(),
            policy=policy,
            notices=notices,
        )
    for belief in beliefs:
        if (
            belief.status is GroupStatus.ACTIVE
            and belief.stance is GroupStance.THOSE_AGENTS
            and belief.social_evidence
            and belief.support >= policy.concept_threshold
        ):
            _mint_concept(
                concepts=concepts,
                owner_id=owner_id,
                tick=tick,
                stance=belief.stance,
                members=belief.members,
                support=belief.support,
                social_evidence=True,
                parent_ids=belief.parent_ids,
                policy=policy,
                notices=notices,
            )


def _withhold(
    beliefs: Sequence[_BeliefDraft],
    concepts: Sequence[_ConceptDraft],
    owner_id: AgentId,
    policy: GroupFormationPolicy,
    notices: list[str],
) -> None:
    for belief in beliefs:
        if belief.status is not GroupStatus.ACTIVE:
            continue
        concept = _find_concept(concepts, belief.stance, belief.members)
        if concept is not None and concept.status is GroupStatus.ACTIVE:
            continue
        if belief.stance is GroupStance.WE:
            concept_ready = False
        else:
            concept_ready = concept is not None
        channels = {item.channel for item in belief.evidence}
        if belief.support >= policy.concept_threshold and not belief.social_evidence:
            if channels and channels <= {GroupChannel.PROXIMITY}:
                reason = "proximity_only"
            else:
                reason = "no_social_evidence"
            notices.append(reason)
            _log_withheld(owner_id, reason)
        elif (
            belief.social_evidence
            and belief.support < policy.concept_threshold
            and not concept_ready
        ):
            notices.append("below_threshold")
            _log_withheld(owner_id, "below_threshold")


def _split(
    beliefs: list[_BeliefDraft],
    concepts: list[_ConceptDraft],
    owner_id: AgentId,
    tick: int,
    pairs: Sequence[frozenset[str]],
    policy: GroupFormationPolicy,
    notices: list[str],
) -> None:
    if not pairs:
        return
    for concept in list(concepts):
        if concept.status is not GroupStatus.ACTIVE or len(concept.members) < 3:
            continue
        present = {member.value for member in concept.members}
        matching = [pair for pair in pairs if pair <= present]
        if not matching:
            continue
        chosen = min(matching, key=lambda pair: tuple(sorted(pair)))
        removed = max(chosen)
        remaining = tuple(
            member for member in concept.members if member.value != removed
        )
        parent_id = _concept_id_of(owner_id, concept)
        concept.status = GroupStatus.SPLIT
        parent = _find_belief(beliefs, concept.stance, concept.members)
        if parent is not None:
            parent.status = GroupStatus.SPLIT
        if len(remaining) < _MIN_SET_SIZE:
            notices.append("remainder_too_small")
            _LOG.warning(
                "group_concept_rewrite_skipped owner_id=%s reason=%s",
                owner_id.value,
                "remainder_too_small",
            )
            continue
        inclusive = concept.stance is GroupStance.OUR_GROUP
        owner_remains = any(member == owner_id for member in remaining)
        child_stance = (
            GroupStance.OUR_GROUP
            if inclusive and owner_remains
            else GroupStance.THOSE_AGENTS
        )
        support = concept.support if parent is None else parent.support
        social = concept.social_evidence if parent is None else parent.social_evidence
        child = _find_belief(beliefs, child_stance, remaining)
        if child is None or child.status in {GroupStatus.SPLIT, GroupStatus.MERGED}:
            child = _BeliefDraft(
                stance=child_stance,
                members=_sorted_members(remaining),
                support=support,
                social_evidence=social,
                status=GroupStatus.ACTIVE,
                evidence=[],
                parent_ids=(parent_id,),
                retire_reason=None,
                touched=True,
            )
            beliefs.append(child)
        else:
            child.support = support
            child.social_evidence = social
            child.status = GroupStatus.ACTIVE
            child.retire_reason = None
            child.parent_ids = (parent_id,)
            child.touched = True
        minted = None
        if social and support >= policy.concept_threshold:
            minted = _mint_concept(
                concepts=concepts,
                owner_id=owner_id,
                tick=tick,
                stance=child_stance,
                members=child.members,
                support=support,
                social_evidence=True,
                parent_ids=(parent_id,),
                policy=policy,
                notices=notices,
            )
        _LOG.debug(
            "group_concept_split owner_id=%s tick=%s parent_count=%s child_status=%s",
            owner_id.value,
            tick,
            1,
            GroupStatus.ACTIVE.value if minted is not None else "withheld",
        )


def _merge(
    beliefs: list[_BeliefDraft],
    concepts: list[_ConceptDraft],
    owner_id: AgentId,
    tick: int,
    policy: GroupFormationPolicy,
    notices: list[str],
) -> None:
    changed = True
    while changed:
        changed = False
        active = [
            concept for concept in concepts if concept.status is GroupStatus.ACTIVE
        ]
        active.sort(key=lambda concept: _concept_id_of(owner_id, concept))
        for index, left in enumerate(active):
            left_ids = {member.value for member in left.members}
            for right in active[index + 1 :]:
                right_ids = {member.value for member in right.members}
                union_ids = left_ids | right_ids
                if not union_ids:
                    continue
                similarity = len(left_ids & right_ids) / len(union_ids)
                if similarity < policy.merge_jaccard:
                    continue
                if (
                    left.support < policy.concept_threshold
                    or right.support < policy.concept_threshold
                ):
                    continue
                if left.stance is not right.stance:
                    notices.append("stance_mismatch")
                    _LOG.warning(
                        "group_concept_rewrite_skipped owner_id=%s reason=%s",
                        owner_id.value,
                        "stance_mismatch",
                    )
                    continue
                if len(union_ids) > policy.max_set_size:
                    notices.append("merge_blocked")
                    _LOG.warning(
                        "group_concept_rewrite_skipped owner_id=%s reason=%s",
                        owner_id.value,
                        "merge_blocked",
                    )
                    continue
                union = _sorted_members(
                    tuple(member for member in (*left.members, *right.members))
                )
                deduped: list[AgentId] = []
                seen: set[str] = set()
                for member in union:
                    if member.value in seen:
                        continue
                    seen.add(member.value)
                    deduped.append(member)
                union_members = tuple(deduped)
                left_id = _concept_id_of(owner_id, left)
                right_id = _concept_id_of(owner_id, right)
                parent_ids = tuple(sorted((left_id, right_id)))
                left.status = GroupStatus.MERGED
                right.status = GroupStatus.MERGED
                for parent_draft, parent_stance in (
                    (left, left.stance),
                    (right, right.stance),
                ):
                    parent_belief = _find_belief(
                        beliefs, parent_stance, parent_draft.members
                    )
                    if parent_belief is not None:
                        parent_belief.status = GroupStatus.MERGED
                support = max(left.support, right.support)
                child = _find_belief(beliefs, left.stance, union_members)
                if child is None or child.status is GroupStatus.MERGED:
                    child = _BeliefDraft(
                        stance=left.stance,
                        members=union_members,
                        support=support,
                        social_evidence=True,
                        status=GroupStatus.ACTIVE,
                        evidence=[],
                        parent_ids=parent_ids,
                        retire_reason=None,
                        touched=True,
                    )
                    beliefs.append(child)
                else:
                    child.support = support
                    child.social_evidence = True
                    child.status = GroupStatus.ACTIVE
                    child.parent_ids = parent_ids
                    child.touched = True
                    child.retire_reason = None
                _mint_concept(
                    concepts=concepts,
                    owner_id=owner_id,
                    tick=tick,
                    stance=left.stance,
                    members=union_members,
                    support=support,
                    social_evidence=True,
                    parent_ids=parent_ids,
                    policy=policy,
                    notices=notices,
                )
                _LOG.debug(
                    "group_concept_merged owner_id=%s tick=%s parent_count=%s "
                    "child_status=%s",
                    owner_id.value,
                    tick,
                    2,
                    GroupStatus.ACTIVE.value,
                )
                changed = True
                break
            if changed:
                break


def _decay(
    beliefs: list[_BeliefDraft],
    concepts: list[_ConceptDraft],
    owner_id: AgentId,
    tick: int,
    policy: GroupFormationPolicy,
) -> None:
    for belief in beliefs:
        if belief.touched:
            continue
        before = belief.support
        belief.support = _apply_delta(before, -policy.decay)
        _LOG.debug(
            "group_belief_applied owner_id=%s tick=%s channel=%s sign=%s",
            owner_id.value,
            tick,
            "decay",
            _sign(before, belief.support),
        )
        if (
            belief.status is GroupStatus.ACTIVE
            and belief.support < policy.retire_threshold
        ):
            belief.status = GroupStatus.RETIRED
            belief.retire_reason = "decay"
    for concept in concepts:
        if concept.status is not GroupStatus.ACTIVE:
            continue
        belief = _find_belief(beliefs, concept.stance, concept.members)
        if belief is None:
            continue
        concept.support = belief.support
        if (
            belief.status is GroupStatus.RETIRED
            or belief.support < policy.retire_threshold
        ):
            concept.status = GroupStatus.RETIRED
            _log_retired(owner_id, tick, concept.stance, concept.status)


def _load_beliefs(ledger: GroupLedger | None) -> list[_BeliefDraft]:
    if ledger is None:
        return []
    loaded: list[_BeliefDraft] = []
    for belief in ledger.beliefs:
        loaded.append(
            _BeliefDraft(
                stance=belief.stance,
                members=belief.member_ids,
                support=belief.support,
                social_evidence=belief.social_evidence,
                status=belief.status,
                evidence=[
                    _EvidenceDraft(
                        channel=item.channel,
                        lineage_ref=item.lineage_ref,
                        tick=item.tick,
                        actor_id=item.actor_id,
                        counterpart_id=item.counterpart_id,
                    )
                    for item in belief.evidence
                ],
                parent_ids=belief.parent_ids,
                retire_reason=belief.retire_reason,
                touched=False,
            )
        )
    return loaded


def _load_concepts(ledger: GroupLedger | None) -> list[_ConceptDraft]:
    if ledger is None:
        return []
    return [
        _ConceptDraft(
            stance=concept.stance,
            members=concept.member_ids,
            support=concept.support,
            social_evidence=concept.social_evidence,
            status=concept.status,
            parent_ids=concept.parent_ids,
        )
        for concept in ledger.concepts
    ]


def _freeze(
    owner_id: AgentId,
    beliefs: Sequence[_BeliefDraft],
    concepts: Sequence[_ConceptDraft],
    notices: Sequence[str],
) -> GroupLedger:
    frozen_beliefs: list[GroupMembershipBelief] = []
    for belief in beliefs:
        belief_id = group_belief_id(owner_id, belief.stance, belief.members)
        evidence: list[GroupEvidenceItem] = []
        for ordinal, item in enumerate(belief.evidence[:_MAX_EVIDENCE]):
            evidence.append(
                GroupEvidenceItem(
                    belief_id=belief_id,
                    channel=item.channel,
                    lineage_ref=item.lineage_ref,
                    ordinal=ordinal,
                    tick=item.tick,
                    actor_id=item.actor_id,
                    counterpart_id=item.counterpart_id,
                )
            )
        frozen_beliefs.append(
            GroupMembershipBelief(
                belief_id=belief_id,
                owner_id=owner_id,
                stance=belief.stance,
                member_ids=belief.members,
                support=belief.support,
                social_evidence=belief.social_evidence,
                status=belief.status,
                evidence=tuple(evidence),
                parent_ids=belief.parent_ids,
                retire_reason=belief.retire_reason,
            )
        )
    known = {item.belief_id for item in frozen_beliefs}
    by_concept: dict[str, GroupConcept] = {}
    for concept in concepts:
        belief_id = group_belief_id(owner_id, concept.stance, concept.members)
        if belief_id not in known or concept.social_evidence is not True:
            continue
        concept_id = group_concept_id(belief_id)
        record = GroupConcept(
            concept_id=concept_id,
            belief_id=belief_id,
            owner_id=owner_id,
            stance=concept.stance,
            member_ids=concept.members,
            support=concept.support,
            social_evidence=True,
            status=concept.status,
            parent_ids=concept.parent_ids,
        )
        current = by_concept.get(concept_id)
        if current is None or record.status is GroupStatus.ACTIVE:
            by_concept[concept_id] = record
    ordered = tuple(sorted(by_concept.values(), key=lambda item: item.concept_id))
    unique_notices = tuple(
        sorted(item for item in set(notices) if item in _NOTICE_REASONS)
    )
    return GroupLedger(
        owner_id=owner_id,
        beliefs=tuple(frozen_beliefs),
        concepts=ordered,
        notices=unique_notices,
    )


def _apply_participation(
    *,
    occurrence: ObservedOccurrence,
    identity: OwnerSafeSocialIdentity,
    beliefs: list[_BeliefDraft],
    channel: GroupChannel,
    delta: float,
    tick: int,
    ordinal: int,
    policy: GroupFormationPolicy,
    notices: list[str],
) -> None:
    owner_id = identity.owner_id
    if occurrence.success is False:
        return
    actor = _resolve_agent(identity, occurrence.actor_id)
    other = _resolve_agent(identity, occurrence.other_entity_id)
    if actor is None or other is None or actor == other:
        notices.append("unresolved_entity")
        _log_drop(owner_id, "unresolved_entity")
        return
    lineage = _lineage_for(tick, ordinal, occurrence.provenance.source_event_id)
    if owner_id in {actor, other}:
        members = _sorted_members((owner_id, other if actor == owner_id else actor))
        stance = GroupStance.WE
    else:
        members = _sorted_members((actor, other))
        stance = GroupStance.THOSE_AGENTS
    _add_evidence(
        beliefs=beliefs,
        owner_id=owner_id,
        members=members,
        stance=stance,
        channel=channel,
        lineage_ref=lineage,
        tick=tick,
        actor_id=actor,
        counterpart_id=other,
        delta=delta,
        policy=policy,
        notices=notices,
    )


def _collect_attacks(
    observation: Observation,
    identity: OwnerSafeSocialIdentity,
    notices: list[str],
) -> list[tuple[AgentId, AgentId, str]]:
    rows: list[tuple[AgentId, AgentId, str]] = []
    for ordinal, occurrence in enumerate(observation.occurrences):
        if type(occurrence) is not ObservedOccurrence or occurrence.kind != "attack":
            continue
        if occurrence.success is False:
            continue
        actor = _resolve_agent(identity, occurrence.actor_id)
        target = _resolve_agent(identity, occurrence.other_entity_id)
        if actor is None or target is None or actor == target:
            notices.append("unresolved_entity")
            _log_drop(identity.owner_id, "unresolved_entity")
            continue
        lineage = _lineage_for(
            observation.tick, ordinal, occurrence.provenance.source_event_id
        )
        rows.append((actor, target, lineage))
    return rows


def _shared_harm_pairs(
    rows: Sequence[tuple[AgentId, AgentId, str]],
) -> list[tuple[AgentId, AgentId, str]]:
    by_actor: dict[str, list[tuple[AgentId, str]]] = {}
    by_target: dict[str, list[tuple[AgentId, str]]] = {}
    actor_of: dict[str, AgentId] = {}
    target_of: dict[str, AgentId] = {}
    for actor, target, lineage in rows:
        by_actor.setdefault(actor.value, []).append((target, lineage))
        by_target.setdefault(target.value, []).append((actor, lineage))
        actor_of[actor.value] = actor
        target_of[target.value] = target
    pairs: list[tuple[AgentId, AgentId, str]] = []
    for patients in by_actor.values():
        ordered = sorted(patients, key=lambda item: (item[0].value, item[1]))
        for index, (left, left_line) in enumerate(ordered):
            for right, right_line in ordered[index + 1 :]:
                if left == right:
                    continue
                lineage = "~".join(sorted((left_line, right_line)))
                pairs.append((*_sorted_members((left, right)), lineage))
    for attackers in by_target.values():
        ordered = sorted(attackers, key=lambda item: (item[0].value, item[1]))
        for index, (left, left_line) in enumerate(ordered):
            for right, right_line in ordered[index + 1 :]:
                if left == right:
                    continue
                lineage = "~".join(sorted((left_line, right_line)))
                pairs.append((*_sorted_members((left, right)), lineage))
    return pairs


def apply_group_update(
    observation: Observation,
    identity: OwnerSafeSocialIdentity,
    trust: Mapping[str, float],
    ledger: GroupLedger | None = None,
    policy: GroupFormationPolicy | None = None,
) -> GroupLedger:
    """Return the owner's next ledger. Disabled callers must not use this."""
    for value in (observation, identity, trust, ledger, policy):
        _reject_forbidden(value)
    if type(observation) is not Observation:
        raise TypeError("observation must be Observation")
    if type(identity) is not OwnerSafeSocialIdentity:
        raise TypeError("identity must be OwnerSafeSocialIdentity")
    if not isinstance(trust, Mapping):
        raise TypeError("trust must be a mapping")
    if ledger is not None and type(ledger) is not GroupLedger:
        raise TypeError("ledger must be GroupLedger or None")
    if policy is None:
        chosen = default_group_formation_policy()
    elif type(policy) is not GroupFormationPolicy:
        raise TypeError("policy must be GroupFormationPolicy or None")
    else:
        chosen = policy
    if ledger is not None and ledger.owner_id != identity.owner_id:
        _LOG.error(
            "group_validation_failed field=%s reason_code=%s",
            "owner_id",
            "owner_mismatch",
        )
        raise ValueError("owner_id: owner_mismatch")
    owner_id = identity.owner_id
    tick = observation.tick
    beliefs = _load_beliefs(ledger)
    concepts = _load_concepts(ledger)
    notices: list[str] = []
    harm_pairs: list[frozenset[str]] = []

    for body in observation.visible_bodies:
        if type(body) is not VisibleBody:
            continue
        other = _resolve_agent(identity, body.entity_id)
        if other is None or other == owner_id:
            if other is None:
                notices.append("unresolved_entity")
                _log_drop(owner_id, "unresolved_entity")
            continue
        _add_evidence(
            beliefs=beliefs,
            owner_id=owner_id,
            members=_sorted_members((owner_id, other)),
            stance=GroupStance.WE,
            channel=GroupChannel.PROXIMITY,
            lineage_ref=f"{tick}:{other.value}",
            tick=tick,
            actor_id=owner_id,
            counterpart_id=other,
            delta=_PROXIMITY_DELTA,
            policy=chosen,
            notices=notices,
        )

    for key in sorted(trust):
        if not isinstance(key, str):
            raise _fail("trust", "invalid_type")
        try:
            other = AgentId(key)
        except ValueError as exc:
            raise _fail("trust", "invalid_type") from exc
        level = _unit("trust", trust[key])
        if other == owner_id or level < chosen.trust_floor:
            continue
        _add_evidence(
            beliefs=beliefs,
            owner_id=owner_id,
            members=_sorted_members((owner_id, other)),
            stance=GroupStance.WE,
            channel=GroupChannel.TRUST,
            lineage_ref=f"{tick}:{other.value}",
            tick=tick,
            actor_id=owner_id,
            counterpart_id=other,
            delta=_TRUST_DELTA,
            policy=chosen,
            notices=notices,
        )

    for ordinal, occurrence in enumerate(observation.occurrences):
        if type(occurrence) is not ObservedOccurrence:
            continue
        if occurrence.kind == "help":
            _apply_participation(
                occurrence=occurrence,
                identity=identity,
                beliefs=beliefs,
                channel=GroupChannel.ASSISTANCE,
                delta=_ASSISTANCE_DELTA,
                tick=tick,
                ordinal=ordinal,
                policy=chosen,
                notices=notices,
            )
        elif occurrence.kind == "give":
            _apply_participation(
                occurrence=occurrence,
                identity=identity,
                beliefs=beliefs,
                channel=GroupChannel.EXCHANGE,
                delta=_EXCHANGE_DELTA,
                tick=tick,
                ordinal=ordinal,
                policy=chosen,
                notices=notices,
            )
        elif occurrence.kind != "attack":
            notices.append("ignored_kind")
            _log_drop(owner_id, "ignored_kind")

    for left, right, lineage in _shared_harm_pairs(
        _collect_attacks(observation, identity, notices)
    ):
        harm_pairs.append(frozenset({left.value, right.value}))
        stance = (
            GroupStance.WE if owner_id in {left, right} else GroupStance.THOSE_AGENTS
        )
        members = (
            _sorted_members((owner_id, right if left == owner_id else left))
            if stance is GroupStance.WE
            else _sorted_members((left, right))
        )
        actor, counterpart = _sorted_members((left, right))
        _add_evidence(
            beliefs=beliefs,
            owner_id=owner_id,
            members=members,
            stance=stance,
            channel=GroupChannel.SHARED_HARM,
            lineage_ref=lineage,
            tick=tick,
            actor_id=actor,
            counterpart_id=counterpart,
            delta=_SHARED_HARM_DELTA,
            policy=chosen,
            notices=notices,
        )

    for ordinal, communication in enumerate(observation.communications):
        if type(communication) is not ObservedCommunication:
            continue
        hop = _hop_count(communication)
        if hop is None or hop > 1:
            notices.append("hop_dropped")
            _log_drop(owner_id, "hop_dropped")
            continue
        speaker = _resolve_agent(identity, communication.speaker_id)
        listener = _resolve_agent(identity, communication.listener_id)
        if speaker is None or listener is None or speaker == listener:
            notices.append("unresolved_entity")
            _log_drop(owner_id, "unresolved_entity")
            continue
        lineage = _lineage_for(tick, ordinal, communication.provenance.source_event_id)
        if owner_id in {speaker, listener}:
            counterpart = listener if speaker == owner_id else speaker
            members = _sorted_members((owner_id, counterpart))
            stance = GroupStance.WE
        else:
            members = _sorted_members((speaker, listener))
            stance = GroupStance.THOSE_AGENTS
        _add_evidence(
            beliefs=beliefs,
            owner_id=owner_id,
            members=members,
            stance=stance,
            channel=GroupChannel.COMMUNICATION,
            lineage_ref=lineage,
            tick=tick,
            actor_id=speaker,
            counterpart_id=listener,
            delta=_COMMUNICATION_DELTA,
            policy=chosen,
            notices=notices,
        )

    for belief in beliefs:
        _refresh_social(belief, owner_id)
    _promote(beliefs, concepts, owner_id, tick, chosen, notices)
    _withhold(beliefs, concepts, owner_id, chosen, notices)
    _split(beliefs, concepts, owner_id, tick, harm_pairs, chosen, notices)
    _merge(beliefs, concepts, owner_id, tick, chosen, notices)
    _decay(beliefs, concepts, owner_id, tick, chosen)
    _shrink_beliefs(beliefs, owner_id, chosen, notices)
    _shrink_concepts(concepts, owner_id, chosen, notices)
    result = _freeze(owner_id, beliefs, concepts, notices)
    _LOG.info(
        "group_belief_updated owner_id=%s belief_count=%s concept_count=%s",
        owner_id.value,
        len(result.beliefs),
        len(result.concepts),
    )
    return result
