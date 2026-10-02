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
from collections.abc import Sequence
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum
from typing import Final

from agents.models import AgentId
from world.identifiers import require_exact_nonneg_int, require_stable_id

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

