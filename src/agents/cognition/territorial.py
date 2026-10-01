"""Owner-scoped claims about places and stores.

A head is one ``(owner, target kind, target entity)``. The ledger is a belief
held by that owner. It is not a world field, a semantic belief, or a
reputation profile. This module does not read world authority, another
agent's ledger, or an analysis aggregate.
"""

from __future__ import annotations

import hashlib
import logging
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from typing import Final

from agents.cognition.models import OwnerSafeSocialIdentity
from agents.models import AgentId
from memory.models import MemorySourceKind, MemoryTrace
from social.models import CommunicationEnvelope
from world.communications import StructuredUtterance
from world.identifiers import EntityId, require_exact_nonneg_int, require_stable_id
from world.observations import (
    Observation,
    ObservedCommunication,
    ObservedOccurrence,
    ObservedStructure,
)

_LOG: Final[logging.Logger] = logging.getLogger("agents.cognition.territorial")

TERRITORIAL_CLAIM_POLICY_VERSION: Final[str] = "territorial-claims.v1"
_QUANTUM: Final[Decimal] = Decimal("0.000001")
_DIRECT_ACTION_FLOOR: Final[float] = 0.50
_FREQUENT_AREA_STEP: Final[float] = 0.15
_FREQUENT_AREA_ACTIVATION: Final[float] = 0.40
_FREQUENT_AREA_CAP: Final[float] = 1.0
_TESTIMONY_TARGET_SCALE: Final[float] = 0.70
_TESTIMONY_RATE: Final[float] = 0.50
_MAX_TESTIMONY_HOP: Final[int] = 1
_VIOLATION_CONTRADICTION: Final[float] = 0.25
_RESPECT_STRENGTH: Final[float] = 0.40
_RESPECT_TRUST: Final[float] = 0.60
_RESPECT_PENALTY: Final[float] = 0.35
_IGNORE_TRUST_BELOW: Final[float] = 0.40
_MISSING_PROFILE_TRUST: Final[float] = 0.50
_MISSING_PROFILE_RESENTMENT: Final[float] = 0.0
_MISSING_PROFILE_FEAR: Final[float] = 0.0
_CRITICAL_NEED: Final[float] = 0.75
_DEFEND_RESENTMENT: Final[float] = 0.40
_DEFEND_FEAR_BELOW: Final[float] = 0.60
_ANNOUNCE_STRENGTH: Final[float] = 0.40
_MAX_HEADS: Final[int] = 32
_MAX_EVIDENCE: Final[int] = 64
_REPEATED_CONTROL_WINDOW: Final[int] = 2
_HEX: Final[frozenset[str]] = frozenset("0123456789abcdef")


class ClaimTargetKind(StrEnum):
    """Closed logical target. ``frequent_area`` still names a location id."""

    LOCATION = "location"
    SHELTER = "shelter"
    STORED_RESOURCE = "stored_resource"
    FREQUENT_AREA = "frequent_area"


class ClaimChannel(StrEnum):
    """Closed provenance channel for one contribution."""

    DIRECT_ACTION = "direct_action"
    REPEATED_PRESENCE = "repeated_presence"
    TESTIMONY = "testimony"
    VIOLATION = "violation"


def _fail(field_name: str, code: str) -> ValueError:
    _LOG.error(
        "territorial_validation_failed field=%s reason_code=%s",
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
    if quantized != expected:
        raise _fail(field_name, "unsupported_policy")
    return quantized


def _locked_int(field_name: str, value: object, expected: int) -> int:
    if isinstance(value, bool) or type(value) is not int:
        raise _fail(field_name, "invalid_type")
    if value != expected:
        raise _fail(field_name, "unsupported_policy")
    return value


def territorial_claim_id(
    owner_id: AgentId,
    target_kind: ClaimTargetKind,
    target_entity_id: EntityId,
) -> str:
    """sha256 of owner id, target kind, and target entity id."""
    if type(owner_id) is not AgentId:
        raise _fail("owner_id", "invalid_type")
    if type(target_kind) is not ClaimTargetKind:
        raise _fail("target_kind", "unknown_target_kind")
    if type(target_entity_id) is not EntityId:
        raise _fail("target_entity_id", "unresolved_entity")
    material = f"{owner_id.value}|{target_kind.value}|{target_entity_id.value}"
    return _sha256_hex(material)


def territorial_evidence_id(
    *,
    claim_id: str,
    ordinal: int,
    channel: ClaimChannel,
    lineage_ref: str,
) -> str:
    """sha256 of head id, ordinal, channel, and lineage ref."""
    head = _require_hex_id("claim_id", claim_id, "invalid_claim_id")
    if type(channel) is not ClaimChannel:
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


@dataclass(frozen=True, slots=True)
class TerritorialEvidenceItem:
    """One adopted contribution. The id is derived; it is not chosen by RNG."""

    owner_id: AgentId
    target_kind: ClaimTargetKind
    target_entity_id: EntityId
    channel: ClaimChannel
    lineage_ref: str
    source_id: AgentId
    pre_scale_delta: float
    tick: int
    policy_version: str
    claim_id: str
    ordinal: int
    evidence_id: str = field(init=False)

    def __post_init__(self) -> None:
        if type(self.owner_id) is not AgentId:
            raise _fail("owner_id", "invalid_type")
        if type(self.target_kind) is not ClaimTargetKind:
            raise _fail("target_kind", "unknown_target_kind")
        if type(self.target_entity_id) is not EntityId:
            raise _fail("target_entity_id", "unresolved_entity")
        if type(self.channel) is not ClaimChannel:
            raise _fail("channel", "unknown_channel")
        if type(self.source_id) is not AgentId:
            raise _fail("source_id", "invalid_type")
        if self.policy_version != TERRITORIAL_CLAIM_POLICY_VERSION:
            raise _fail("policy_version", "unsupported_policy")
        try:
            lineage = require_stable_id("lineage_ref", self.lineage_ref)
        except ValueError as exc:
            raise _fail("lineage_ref", "invalid_lineage") from exc
        head = _require_hex_id("claim_id", self.claim_id, "invalid_claim_id")
        expected_head = territorial_claim_id(
            self.owner_id, self.target_kind, self.target_entity_id
        )
        if head != expected_head:
            raise _fail("claim_id", "claim_id_mismatch")
        try:
            ordinal = require_exact_nonneg_int("ordinal", self.ordinal)
        except ValueError as exc:
            raise _fail("ordinal", "invalid_ordinal") from exc
        try:
            tick = require_exact_nonneg_int("tick", self.tick)
        except ValueError as exc:
            raise _fail("tick", "invalid_tick") from exc
        object.__setattr__(self, "lineage_ref", lineage)
        object.__setattr__(self, "claim_id", head)
        object.__setattr__(self, "ordinal", ordinal)
        object.__setattr__(self, "tick", tick)
        object.__setattr__(
            self, "pre_scale_delta", _unit("pre_scale_delta", self.pre_scale_delta)
        )
        object.__setattr__(
            self,
            "evidence_id",
            territorial_evidence_id(
                claim_id=head,
                ordinal=ordinal,
                channel=self.channel,
                lineage_ref=lineage,
            ),
        )


@dataclass(frozen=True, slots=True)
class TerritorialClaim:
    """One ``(owner, target kind, target entity)`` head."""

    claim_id: str
    owner_id: AgentId
    target_kind: ClaimTargetKind
    target_entity_id: EntityId
    strength: float
    support_mass: float
    contradiction_mass: float
    evidence: tuple[TerritorialEvidenceItem, ...] = ()

    def __post_init__(self) -> None:
        if type(self.owner_id) is not AgentId:
            raise _fail("owner_id", "invalid_type")
        if type(self.target_kind) is not ClaimTargetKind:
            raise _fail("target_kind", "unknown_target_kind")
        if type(self.target_entity_id) is not EntityId:
            raise _fail("target_entity_id", "unresolved_entity")
        head = _require_hex_id("claim_id", self.claim_id, "invalid_claim_id")
        expected = territorial_claim_id(
            self.owner_id, self.target_kind, self.target_entity_id
        )
        if head != expected:
            raise _fail("claim_id", "claim_id_mismatch")
        object.__setattr__(self, "claim_id", head)
        object.__setattr__(self, "strength", _unit("strength", self.strength))
        object.__setattr__(
            self, "support_mass", _unit("support_mass", self.support_mass)
        )
        object.__setattr__(
            self,
            "contradiction_mass",
            _unit("contradiction_mass", self.contradiction_mass),
        )
        evidence = _require_tuple("evidence", self.evidence)
        if len(evidence) > _MAX_EVIDENCE:
            raise _fail("evidence", "cap_exceeded")
        seen: set[tuple[ClaimChannel, str]] = set()
        checked: list[TerritorialEvidenceItem] = []
        for ordinal, item in enumerate(evidence):
            if type(item) is not TerritorialEvidenceItem:
                raise _fail("evidence", "invalid_type")
            if item.owner_id != self.owner_id:
                raise _fail("evidence.owner_id", "owner_mismatch")
            if (
                item.target_kind is not self.target_kind
                or item.target_entity_id != self.target_entity_id
            ):
                raise _fail("evidence.target_entity_id", "target_mismatch")
            if item.claim_id != self.claim_id or item.ordinal != ordinal:
                raise _fail("evidence.evidence_id", "evidence_id_mismatch")
            key = (item.channel, item.lineage_ref)
            if key in seen:
                raise _fail("evidence", "duplicate_evidence")
            seen.add(key)
            checked.append(item)
        object.__setattr__(self, "evidence", tuple(checked))


@dataclass(frozen=True, slots=True)
class TerritorialClaimLedger:
    """Private heads owned by one agent. There is no shared claim."""

    owner_id: AgentId
    claims: tuple[TerritorialClaim, ...] = ()

    def __post_init__(self) -> None:
        if type(self.owner_id) is not AgentId:
            raise _fail("owner_id", "invalid_type")
        claims = _require_tuple("claims", self.claims)
        if len(claims) > _MAX_HEADS:
            raise _fail("claims", "cap_exceeded")
        seen: set[tuple[ClaimTargetKind, EntityId]] = set()
        checked: list[TerritorialClaim] = []
        for item in claims:
            if type(item) is not TerritorialClaim:
                raise _fail("claims", "invalid_type")
            if item.owner_id != self.owner_id:
                raise _fail("claims.owner_id", "owner_mismatch")
            key = (item.target_kind, item.target_entity_id)
            if key in seen:
                raise _fail("claims", "duplicate_head")
            seen.add(key)
            checked.append(item)
        object.__setattr__(self, "claims", tuple(checked))
        _LOG.debug(
            "territorial_ledger_constructed owner_id=%s policy_version=%s "
            "head_count=%s",
            self.owner_id.value,
            TERRITORIAL_CLAIM_POLICY_VERSION,
            len(self.claims),
        )

    def claim_for(
        self, target_kind: ClaimTargetKind, target_entity_id: EntityId
    ) -> TerritorialClaim | None:
        """Return one head, or ``None`` when this owner has no such claim."""
        if type(target_kind) is not ClaimTargetKind:
            raise _fail("target_kind", "unknown_target_kind")
        if type(target_entity_id) is not EntityId:
            raise _fail("target_entity_id", "unresolved_entity")
        for item in self.claims:
            if (
                item.target_kind is target_kind
                and item.target_entity_id == target_entity_id
            ):
                return item
        return None


@dataclass(frozen=True, slots=True)
class TerritorialClaimPolicy:
    """Locked claim constants. Runner JSON does not carry these weights."""

    version: str = TERRITORIAL_CLAIM_POLICY_VERSION
    direct_action_floor: float = _DIRECT_ACTION_FLOOR
    frequent_area_step: float = _FREQUENT_AREA_STEP
    frequent_area_activation: float = _FREQUENT_AREA_ACTIVATION
    frequent_area_cap: float = _FREQUENT_AREA_CAP
    testimony_target_scale: float = _TESTIMONY_TARGET_SCALE
    testimony_rate: float = _TESTIMONY_RATE
    max_testimony_hop: int = _MAX_TESTIMONY_HOP
    violation_contradiction: float = _VIOLATION_CONTRADICTION
    respect_strength: float = _RESPECT_STRENGTH
    respect_trust: float = _RESPECT_TRUST
    respect_penalty: float = _RESPECT_PENALTY
    ignore_trust_below: float = _IGNORE_TRUST_BELOW
    missing_profile_trust: float = _MISSING_PROFILE_TRUST
    missing_profile_resentment: float = _MISSING_PROFILE_RESENTMENT
    missing_profile_fear: float = _MISSING_PROFILE_FEAR
    critical_need: float = _CRITICAL_NEED
    defend_resentment: float = _DEFEND_RESENTMENT
    defend_fear_below: float = _DEFEND_FEAR_BELOW
    announce_strength: float = _ANNOUNCE_STRENGTH
    max_heads: int = _MAX_HEADS
    max_evidence: int = _MAX_EVIDENCE
    repeated_control_window: int = _REPEATED_CONTROL_WINDOW

    def __post_init__(self) -> None:
        if self.version != TERRITORIAL_CLAIM_POLICY_VERSION:
            raise _fail("version", "unsupported_policy")
        units = (
            ("direct_action_floor", _DIRECT_ACTION_FLOOR),
            ("frequent_area_step", _FREQUENT_AREA_STEP),
            ("frequent_area_activation", _FREQUENT_AREA_ACTIVATION),
            ("frequent_area_cap", _FREQUENT_AREA_CAP),
            ("testimony_target_scale", _TESTIMONY_TARGET_SCALE),
            ("testimony_rate", _TESTIMONY_RATE),
            ("violation_contradiction", _VIOLATION_CONTRADICTION),
            ("respect_strength", _RESPECT_STRENGTH),
            ("respect_trust", _RESPECT_TRUST),
            ("respect_penalty", _RESPECT_PENALTY),
            ("ignore_trust_below", _IGNORE_TRUST_BELOW),
            ("missing_profile_trust", _MISSING_PROFILE_TRUST),
            ("missing_profile_resentment", _MISSING_PROFILE_RESENTMENT),
            ("missing_profile_fear", _MISSING_PROFILE_FEAR),
            ("critical_need", _CRITICAL_NEED),
            ("defend_resentment", _DEFEND_RESENTMENT),
            ("defend_fear_below", _DEFEND_FEAR_BELOW),
            ("announce_strength", _ANNOUNCE_STRENGTH),
        )
        for name, expected in units:
            object.__setattr__(
                self, name, _locked_unit(name, getattr(self, name), expected)
            )
        counts = (
            ("max_testimony_hop", _MAX_TESTIMONY_HOP),
            ("max_heads", _MAX_HEADS),
            ("max_evidence", _MAX_EVIDENCE),
            ("repeated_control_window", _REPEATED_CONTROL_WINDOW),
        )
        for name, expected in counts:
            object.__setattr__(
                self, name, _locked_int(name, getattr(self, name), expected)
            )
        _LOG.debug(
            "territorial_policy_constructed policy_version=%s",
            self.version,
        )


def default_territorial_claim_policy() -> TerritorialClaimPolicy:
    """Return the only accepted claim policy."""
    return TerritorialClaimPolicy()


def empty_territorial_ledger(owner_id: AgentId) -> TerritorialClaimLedger:
    """Ledger with no heads. Disabled mode does not call this."""
    return TerritorialClaimLedger(owner_id=owner_id)


def require_owner_territorial_claims(
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
    if type(ledger) is not TerritorialClaimLedger:
        raise TypeError(f"{field_name} must be TerritorialClaimLedger")
    if ledger.owner_id != owner_id:
        raise ValueError(f"{field_name} owner_id mismatch")


_FORBIDDEN_TYPES: Final[frozenset[str]] = frozenset(
    {"WorldState", "WorldEvent", "PhysicalRules", "AgentBody"}
)
_SELF_CHANNELS: Final[Mapping[str, ClaimTargetKind]] = {
    "sleep": ClaimTargetKind.LOCATION,
    "structure_built": ClaimTargetKind.SHELTER,
    "structure_repaired": ClaimTargetKind.SHELTER,
    "item_stored": ClaimTargetKind.STORED_RESOURCE,
    "resource_harvested": ClaimTargetKind.STORED_RESOURCE,
}
_TESTIMONY_PREDICATES: Final[frozenset[str]] = frozenset({"claims", "disputes"})
_VIOLATION_KINDS: Final[frozenset[str]] = frozenset(
    {"take", "resource_harvested", "eat", "drink", "item_stored", "sleep"}
)
_PLACE_KINDS: Final[frozenset[ClaimTargetKind]] = frozenset(
    {ClaimTargetKind.LOCATION, ClaimTargetKind.FREQUENT_AREA}
)
_MISSING: Final[object] = object()


def _reject_world(value: object) -> None:
    if type(value).__name__ in _FORBIDDEN_TYPES:
        raise TypeError(f"{type(value).__name__}: forbidden_input")


def _resolve_agent(
    identity: OwnerSafeSocialIdentity | None, entity_id: EntityId | None
) -> AgentId | None:
    if identity is None or type(entity_id) is not EntityId:
        return None
    if entity_id == identity.owner_entity_id:
        return identity.owner_id
    for binding in identity.counterparts:
        if binding.entity_id == entity_id:
            return binding.agent_id
    return None


def _warn(owner_id: AgentId, code: str, entity_id: str) -> None:
    _LOG.warning(
        "territorial_claim_skipped owner_id=%s reason_code=%s entity_id=%s",
        owner_id.value,
        code,
        entity_id,
    )


def relationship_projection(profile: object | None) -> tuple[float, float, float]:
    """Trust, resentment, and fear. A missing profile is ``(0.50, 0, 0)``."""
    if profile is None:
        return (
            _MISSING_PROFILE_TRUST,
            _MISSING_PROFILE_RESENTMENT,
            _MISSING_PROFILE_FEAR,
        )
    from social.relationships import (
        DirectedRelationshipProfile,
        RelationshipDimension,
    )

    if type(profile) is not DirectedRelationshipProfile:
        raise _fail("relationship", "invalid_type")
    from agents.cognition.communication import project_trust_inputs

    trust, _confidence = project_trust_inputs(profile)
    dims = profile.dimension_map()
    resentment_state = dims.get(RelationshipDimension.RESENTMENT)
    fear_state = dims.get(RelationshipDimension.FEAR)
    resentment = 0.0 if resentment_state is None else float(resentment_state.value)
    fear = 0.0 if fear_state is None else float(fear_state.value)
    return (_quantize(trust), _quantize(resentment), _quantize(fear))


def _lineage(occurrence: ObservedOccurrence, ordinal: int) -> str:
    event_id = occurrence.provenance.source_event_id
    if event_id is None:
        return f"tick-{occurrence.provenance.source_tick}-{ordinal}"
    return event_id.value


def _visible_structure(
    observation: Observation,
    entity_id: EntityId,
    kind_value: str,
) -> ObservedStructure | None:
    for structure in observation.structures:
        if type(structure) is not ObservedStructure:
            continue
        if structure.entity_id == entity_id and structure.kind.value == kind_value:
            return structure
    return None


def _replace_head(
    heads: list[TerritorialClaim],
    index: dict[tuple[ClaimTargetKind, str], int],
    claim: TerritorialClaim,
) -> None:
    key = (claim.target_kind, claim.target_entity_id.value)
    slot = index.get(key)
    if slot is None:
        index[key] = len(heads)
        heads.append(claim)
        return
    heads[slot] = claim


def _contribute(
    *,
    owner_id: AgentId,
    heads: list[TerritorialClaim],
    index: dict[tuple[ClaimTargetKind, str], int],
    kind: ClaimTargetKind,
    target: EntityId,
    channel: ClaimChannel,
    lineage: str,
    source_id: AgentId,
    tick: int,
    policy: TerritorialClaimPolicy,
    strength: float,
    added: dict[ClaimChannel, int],
    replace_strength: bool,
) -> None:
    key = (kind, target.value)
    slot = index.get(key)
    current = None if slot is None else heads[slot]
    if current is not None and any(
        item.channel is channel and item.lineage_ref == lineage
        for item in current.evidence
    ):
        if replace_strength:
            refreshed = TerritorialClaim(
                claim_id=current.claim_id,
                owner_id=owner_id,
                target_kind=kind,
                target_entity_id=target,
                strength=strength,
                support_mass=current.support_mass,
                contradiction_mass=current.contradiction_mass,
                evidence=current.evidence,
            )
            heads[slot] = refreshed
        return
    if current is None and len(heads) >= policy.max_heads:
        _warn(owner_id, "cap_exceeded", target.value)
        return
    if current is not None and len(current.evidence) >= policy.max_evidence:
        _warn(owner_id, "cap_exceeded", target.value)
        return
    prior = 0.0 if current is None else current.strength
    applied = strength if replace_strength else max(prior, strength)
    delta = _quantize(abs(applied - prior))
    if delta == 0.0 and current is not None and not replace_strength:
        delta = _quantize(strength)
    claim_id = territorial_claim_id(owner_id, kind, target)
    evidence = () if current is None else current.evidence
    item = TerritorialEvidenceItem(
        owner_id=owner_id,
        target_kind=kind,
        target_entity_id=target,
        channel=channel,
        lineage_ref=lineage,
        source_id=source_id,
        pre_scale_delta=delta if delta > 0.0 else _quantize(min(1.0, strength)),
        tick=tick,
        policy_version=policy.version,
        claim_id=claim_id,
        ordinal=len(evidence),
    )
    support = 0.0 if current is None else current.support_mass
    contradiction = 0.0 if current is None else current.contradiction_mass
    updated = TerritorialClaim(
        claim_id=claim_id,
        owner_id=owner_id,
        target_kind=kind,
        target_entity_id=target,
        strength=applied,
        support_mass=min(1.0, _quantize(support + delta)),
        contradiction_mass=contradiction,
        evidence=(*evidence, item),
    )
    _replace_head(heads, index, updated)
    added[channel] = added.get(channel, 0) + 1


def _apply_self_actions(
    *,
    owner_id: AgentId,
    tick: int,
    observation: Observation,
    identity: OwnerSafeSocialIdentity | None,
    policy: TerritorialClaimPolicy,
    heads: list[TerritorialClaim],
    index: dict[tuple[ClaimTargetKind, str], int],
    added: dict[ClaimChannel, int],
) -> None:
    if identity is None or observation.self_body is None:
        return
    for ordinal, occurrence in enumerate(observation.occurrences):
        if type(occurrence) is not ObservedOccurrence:
            raise _fail("occurrences", "invalid_type")
        if occurrence.provenance.source_tick >= tick:
            continue
        if occurrence.success is False:
            continue
        kind_name = occurrence.kind
        if kind_name == "take":
            continue
        if kind_name not in _SELF_CHANNELS:
            continue
        actor = _resolve_agent(identity, occurrence.actor_id)
        if actor != owner_id:
            if occurrence.actor_id is not None and actor is None:
                _warn(owner_id, "unresolved_entity", occurrence.actor_id.value)
            continue
        target_kind = _SELF_CHANNELS[kind_name]
        if kind_name == "sleep":
            target = observation.self_body.location_id
        elif kind_name == "resource_harvested":
            if type(occurrence.other_entity_id) is not EntityId:
                _warn(owner_id, "unresolved_entity", "resource")
                continue
            target = occurrence.other_entity_id
        else:
            if type(occurrence.other_entity_id) is not EntityId:
                _warn(owner_id, "unresolved_entity", kind_name)
                continue
            expected = "shelter" if target_kind is ClaimTargetKind.SHELTER else "store"
            seen = _visible_structure(observation, occurrence.other_entity_id, expected)
            if seen is None or seen.location_id != observation.self_body.location_id:
                code = "shelter_unseen" if expected == "shelter" else "store_unseen"
                _warn(owner_id, code, occurrence.other_entity_id.value)
                continue
            target = seen.entity_id
        _contribute(
            owner_id=owner_id,
            heads=heads,
            index=index,
            kind=target_kind,
            target=target,
            channel=ClaimChannel.DIRECT_ACTION,
            lineage=_lineage(occurrence, ordinal),
            source_id=owner_id,
            tick=tick,
            policy=policy,
            strength=policy.direct_action_floor,
            added=added,
            replace_strength=False,
        )


def _apply_frequent_areas(
    *,
    owner_id: AgentId,
    tick: int,
    memories: Sequence[MemoryTrace],
    policy: TerritorialClaimPolicy,
    heads: list[TerritorialClaim],
    index: dict[tuple[ClaimTargetKind, str], int],
    added: dict[ClaimChannel, int],
) -> None:
    if isinstance(memories, (str, bytes, set, frozenset)) or not isinstance(
        memories, Sequence
    ):
        raise _fail("memories", "invalid_type")
    ticks: dict[str, set[int]] = {}
    entities: dict[str, EntityId] = {}
    for trace in memories:
        _reject_world(trace)
        if type(trace) is not MemoryTrace:
            raise _fail("memories", "invalid_type")
        if trace.owner_id != owner_id:
            raise _fail("memories.owner_id", "owner_mismatch")
        if trace.provenance.kind is not MemorySourceKind.DIRECT_OBSERVATION:
            continue
        location = trace.context.location_id
        if location is None:
            continue
        entities[location.value] = location
        ticks.setdefault(location.value, set()).add(trace.provenance.source_tick)
    for location_value in sorted(ticks):
        count = len(ticks[location_value])
        strength = _quantize(
            min(policy.frequent_area_cap, policy.frequent_area_step * count)
        )
        if strength < policy.frequent_area_activation:
            continue
        _contribute(
            owner_id=owner_id,
            heads=heads,
            index=index,
            kind=ClaimTargetKind.FREQUENT_AREA,
            target=entities[location_value],
            channel=ClaimChannel.REPEATED_PRESENCE,
            lineage=f"frequent-area|{location_value}|{count}",
            source_id=owner_id,
            tick=tick,
            policy=policy,
            strength=strength,
            added=added,
            replace_strength=True,
        )


def _utterances(
    observation: Observation,
    inbox: Sequence[object] | None,
    identity: OwnerSafeSocialIdentity | None,
    owner_id: AgentId,
) -> list[tuple[StructuredUtterance, AgentId]]:
    speeches: list[tuple[StructuredUtterance, AgentId]] = []
    for communication in observation.communications:
        _reject_world(communication)
        if type(communication) is not ObservedCommunication:
            _warn(owner_id, "invalid_testimony", "communication")
            continue
        if identity is None:
            continue
        listener = _resolve_agent(identity, communication.listener_id)
        speaker = _resolve_agent(identity, communication.speaker_id)
        if listener != owner_id or speaker is None:
            if speaker is None:
                _warn(owner_id, "unresolved_entity", communication.speaker_id.value)
            continue
        speeches.append((communication.utterance, speaker))
    if inbox is None:
        return speeches
    if isinstance(inbox, (str, bytes, set, frozenset)) or not isinstance(
        inbox, Sequence
    ):
        raise _fail("inbox", "invalid_type")
    for envelope in inbox:
        _reject_world(envelope)
        if type(envelope) is not CommunicationEnvelope:
            _warn(owner_id, "invalid_testimony", "inbox")
            continue
        if envelope.recipient_id != owner_id:
            continue
        utterance = next(
            (
                value
                for value in envelope.payload.values()
                if type(value) is StructuredUtterance
            ),
            None,
        )
        if utterance is None:
            _warn(owner_id, "invalid_testimony", envelope.sender_id.value)
            continue
        speeches.append((utterance, envelope.sender_id))
    return speeches


def _apply_violations(
    *,
    owner_id: AgentId,
    tick: int,
    observation: Observation,
    identity: OwnerSafeSocialIdentity | None,
    policy: TerritorialClaimPolicy,
    heads: list[TerritorialClaim],
    index: dict[tuple[ClaimTargetKind, str], int],
    prior: set[tuple[ClaimTargetKind, str]],
    added: dict[ClaimChannel, int],
) -> None:
    """Append breach evidence on heads that already existed."""
    if identity is None or observation.self_body is None:
        return
    location = observation.self_body.location_id
    for ordinal, occurrence in enumerate(observation.occurrences):
        if type(occurrence) is not ObservedOccurrence:
            continue
        if occurrence.provenance.source_tick >= tick or occurrence.success is False:
            continue
        if occurrence.kind not in _VIOLATION_KINDS:
            continue
        actor = _resolve_agent(identity, occurrence.actor_id)
        if actor == owner_id:
            continue
        if actor is None:
            if occurrence.actor_id is not None:
                _warn(owner_id, "unresolved_entity", occurrence.actor_id.value)
            continue
        lineage = _lineage(occurrence, ordinal)
        for key in sorted(prior, key=lambda item: (item[0].value, item[1])):
            slot = index.get(key)
            if slot is None:
                continue
            current = heads[slot]
            if key not in prior:
                continue
            matched = False
            if current.target_kind in _PLACE_KINDS:
                matched = location == current.target_entity_id
            elif type(occurrence.other_entity_id) is EntityId:
                matched = occurrence.other_entity_id == current.target_entity_id
            if not matched:
                continue
            if any(
                item.channel is ClaimChannel.VIOLATION and item.lineage_ref == lineage
                for item in current.evidence
            ):
                continue
            if len(current.evidence) >= policy.max_evidence:
                _warn(owner_id, "cap_exceeded", current.target_entity_id.value)
                continue
            delta = policy.violation_contradiction
            item = TerritorialEvidenceItem(
                owner_id=owner_id,
                target_kind=current.target_kind,
                target_entity_id=current.target_entity_id,
                channel=ClaimChannel.VIOLATION,
                lineage_ref=lineage,
                source_id=actor,
                pre_scale_delta=delta,
                tick=tick,
                policy_version=policy.version,
                claim_id=current.claim_id,
                ordinal=len(current.evidence),
            )
            updated = TerritorialClaim(
                claim_id=current.claim_id,
                owner_id=owner_id,
                target_kind=current.target_kind,
                target_entity_id=current.target_entity_id,
                strength=current.strength,
                support_mass=current.support_mass,
                contradiction_mass=_quantize(
                    min(1.0, current.contradiction_mass + delta)
                ),
                evidence=(*current.evidence, item),
            )
            heads[slot] = updated
            added[ClaimChannel.VIOLATION] = added.get(ClaimChannel.VIOLATION, 0) + 1
            _LOG.debug(
                "territorial_violation owner_id=%s target_kind=%s tick=%s "
                "target_entity_id=%s reason=%s",
                owner_id.value,
                current.target_kind.value,
                tick,
                current.target_entity_id.value,
                "violated",
            )


def _apply_testimony(
    *,
    owner_id: AgentId,
    tick: int,
    observation: Observation,
    identity: OwnerSafeSocialIdentity | None,
    inbox: Sequence[object] | None,
    trust_by_speaker: Mapping[str, float] | None,
    policy: TerritorialClaimPolicy,
    heads: list[TerritorialClaim],
    index: dict[tuple[ClaimTargetKind, str], int],
    added: dict[ClaimChannel, int],
) -> None:
    if trust_by_speaker is not None and not isinstance(trust_by_speaker, Mapping):
        raise _fail("source_trust_by_speaker", "invalid_type")
    for utterance, speaker in _utterances(observation, inbox, identity, owner_id):
        hop = utterance.declared.hop_count
        if hop > policy.max_testimony_hop:
            _warn(owner_id, "hop_exceeded", speaker.value)
            continue
        trust = _MISSING_PROFILE_TRUST
        if trust_by_speaker is not None and speaker.value in trust_by_speaker:
            trust = _unit("source_trust", trust_by_speaker[speaker.value])
        for relation in utterance.content.relations:
            if relation.predicate not in _TESTIMONY_PREDICATES:
                continue
            if relation.object not in {item.value for item in ClaimTargetKind}:
                _LOG.error(
                    "territorial_validation_failed field=%s reason_code=%s",
                    "testimony.object",
                    "unknown_target_kind",
                )
                continue
            try:
                target_value = require_stable_id("subject", relation.subject)
            except ValueError:
                _warn(owner_id, "unresolved_entity", "testimony")
                continue
            target = EntityId(target_value)
            kind = ClaimTargetKind(relation.object)
            key = (kind, target.value)
            slot = index.get(key)
            current = 0.0 if slot is None else heads[slot].strength
            delta = _quantize(
                (policy.testimony_target_scale * trust - current)
                * policy.testimony_rate
            )
            _contribute(
                owner_id=owner_id,
                heads=heads,
                index=index,
                kind=kind,
                target=target,
                channel=ClaimChannel.TESTIMONY,
                lineage=(
                    f"{utterance.declared.communication_id.value}|"
                    f"{relation.predicate}|{relation.subject}|{relation.object}"
                ),
                source_id=speaker,
                tick=tick,
                policy=policy,
                strength=_quantize(min(1.0, max(0.0, current + delta))),
                added=added,
                replace_strength=True,
            )


def apply_territorial_update(
    *,
    owner_id: AgentId,
    tick: int,
    observation: Observation,
    social_identity: OwnerSafeSocialIdentity | None,
    ledger: TerritorialClaimLedger | None,
    policy: TerritorialClaimPolicy,
    memories: Sequence[MemoryTrace] = (),
    source_trust_by_speaker: Mapping[str, float] | None = None,
    inbox: Sequence[object] | None = None,
    world_state: object = _MISSING,
    world_event: object = _MISSING,
) -> TerritorialClaimLedger:
    """Return one owner's next ledger. Disabled mode does not call this."""
    if world_state is not _MISSING or world_event is not _MISSING:
        raise TypeError("forbidden_input")
    _reject_world(observation)
    if type(owner_id) is not AgentId:
        raise _fail("owner_id", "invalid_type")
    if type(observation) is not Observation:
        raise _fail("observation", "invalid_type")
    if type(policy) is not TerritorialClaimPolicy:
        raise _fail("policy", "invalid_type")
    try:
        require_exact_nonneg_int("tick", tick)
    except ValueError as exc:
        raise _fail("tick", "invalid_tick") from exc
    if (
        social_identity is not None
        and type(social_identity) is not OwnerSafeSocialIdentity
    ):
        raise _fail("social_identity", "invalid_type")
    if ledger is not None and (
        type(ledger) is not TerritorialClaimLedger or ledger.owner_id != owner_id
    ):
        raise _fail("ledger", "owner_mismatch")
    heads = [] if ledger is None else list(ledger.claims)
    index = {
        (item.target_kind, item.target_entity_id.value): slot
        for slot, item in enumerate(heads)
    }
    added: dict[ClaimChannel, int] = {}
    prior = set(index)
    _apply_self_actions(
        owner_id=owner_id,
        tick=tick,
        observation=observation,
        identity=social_identity,
        policy=policy,
        heads=heads,
        index=index,
        added=added,
    )
    _apply_frequent_areas(
        owner_id=owner_id,
        tick=tick,
        memories=memories,
        policy=policy,
        heads=heads,
        index=index,
        added=added,
    )
    _apply_testimony(
        owner_id=owner_id,
        tick=tick,
        observation=observation,
        identity=social_identity,
        inbox=inbox,
        trust_by_speaker=source_trust_by_speaker,
        policy=policy,
        heads=heads,
        index=index,
        added=added,
    )
    _apply_violations(
        owner_id=owner_id,
        tick=tick,
        observation=observation,
        identity=social_identity,
        policy=policy,
        heads=heads,
        index=index,
        prior=prior,
        added=added,
    )
    updated = TerritorialClaimLedger(owner_id=owner_id, claims=tuple(heads))
    counts = ",".join(
        f"{channel.value}={added.get(channel, 0)}" for channel in ClaimChannel
    )
    _LOG.debug(
        "territorial_update owner_id=%s tick=%s heads=%s channels=%s",
        owner_id.value,
        tick,
        len(updated.claims),
        counts,
    )
    return updated


@dataclass(frozen=True, slots=True)
class TerritorialClaimAudit:
    """One owner-scoped reason the planner kept or replaced Wait."""

    owner_id: AgentId
    tick: int
    reason_code: str
    target_kind: ClaimTargetKind
    target_entity_id: EntityId
    policy_version: str

    def __post_init__(self) -> None:
        if type(self.owner_id) is not AgentId:
            raise _fail("owner_id", "invalid_type")
        try:
            require_exact_nonneg_int("tick", self.tick)
        except ValueError as exc:
            raise _fail("tick", "invalid_tick") from exc
        if self.reason_code not in {
            "defend",
            "challenge",
            "communicate",
            "ignore_need",
            "ignore_relationship",
            "relationship_neutral",
            "source_relationship_missing",
            "respect",
        }:
            raise _fail("reason_code", "unknown_reason")
        if type(self.target_kind) is not ClaimTargetKind:
            raise _fail("target_kind", "unknown_target_kind")
        if type(self.target_entity_id) is not EntityId:
            raise _fail("target_entity_id", "unresolved_entity")
        if self.policy_version != TERRITORIAL_CLAIM_POLICY_VERSION:
            raise _fail("policy_version", "unsupported_policy")


def _other_sources(claim: TerritorialClaim, owner_id: AgentId) -> tuple[AgentId, ...]:
    sources = {
        item.source_id
        for item in claim.evidence
        if item.channel is ClaimChannel.TESTIMONY and item.source_id != owner_id
    }
    return tuple(sorted(sources, key=lambda item: item.value))


def _profile_for(
    relationships: Sequence[object] | None, target: AgentId
) -> object | None:
    if relationships is None:
        return None
    return next(
        (item for item in relationships if getattr(item, "target_id", None) == target),
        None,
    )


def territorial_respect_penalties(
    *,
    owner_id: AgentId,
    futures: Sequence[object],
    ledger: object | None,
    relationships: Sequence[object] | None,
    hunger: float,
    thirst: float,
    mode: object | None,
) -> dict[str, float]:
    """Subtract ``0.35`` from futures that respect another agent's claim."""
    from agents.cognition.configuration import CognitionTerritorialClaimMode
    from agents.cognition.models import ActionDirection

    penalties: dict[str, float] = {}
    if mode is not CognitionTerritorialClaimMode.DETERMINISTIC:
        return penalties
    if type(ledger) is not TerritorialClaimLedger:
        return penalties
    critical = hunger / 100.0 >= _CRITICAL_NEED or thirst / 100.0 >= _CRITICAL_NEED
    for future in futures:
        direction = getattr(future, "direction", None)
        future_id = getattr(future, "future_id", None)
        target = getattr(future, "target_entity_id", None)
        if not isinstance(future_id, str) or type(direction) is not ActionDirection:
            continue
        if direction not in {
            ActionDirection.MOVE,
            ActionDirection.SEARCH,
            ActionDirection.EAT,
            ActionDirection.DRINK,
        }:
            continue
        if not isinstance(target, str):
            continue
        matched = None
        for claim in ledger.claims:
            if claim.strength < _RESPECT_STRENGTH:
                continue
            if claim.target_entity_id.value != target:
                continue
            place = (
                claim.target_kind in _PLACE_KINDS and direction is ActionDirection.MOVE
            )
            stock = (
                claim.target_kind is ClaimTargetKind.STORED_RESOURCE
                and direction
                in {
                    ActionDirection.SEARCH,
                    ActionDirection.EAT,
                    ActionDirection.DRINK,
                }
            )
            if place or stock:
                matched = claim
                break
        if matched is None:
            continue
        sources = _other_sources(matched, owner_id)
        if not sources:
            continue
        claimant = sources[0]
        profile = _profile_for(relationships, claimant)
        trust, _resentment, _fear = relationship_projection(profile)
        if critical:
            reason = "ignore_need"
            delta = 0.0
        elif profile is None:
            reason = "source_relationship_missing"
            delta = 0.0
        elif trust < _IGNORE_TRUST_BELOW:
            reason = "ignore_relationship"
            delta = 0.0
        elif trust < _RESPECT_TRUST:
            reason = "relationship_neutral"
            delta = 0.0
        else:
            reason = "respect"
            delta = -_RESPECT_PENALTY
        penalties[future_id] = delta
        _LOG.debug(
            "territorial_bias owner_id=%s reason=%s direction=%s",
            owner_id.value,
            reason,
            direction.value,
        )
    return penalties


def territorial_wait_replacement(
    command: object,
    *,
    owner_id: AgentId,
    tick: int,
    observation: Observation,
    identity: OwnerSafeSocialIdentity | None,
    ledger: object | None,
    relationships: Sequence[object] | None,
    mode: object | None,
) -> tuple[object, tuple[TerritorialClaimAudit, ...] | None]:
    """Defend, challenge, or announce only while the command is still Wait."""
    from agents.cognition.configuration import CognitionTerritorialClaimMode
    from world.actions import Attack, Tell, Wait
    from world.communications import (
        CommunicationRelation,
        observation_allows_communication_target,
        origin_utterance,
    )
    from world.observations import CONTENT_VISIBILITY_THRESHOLD

    if mode is not CognitionTerritorialClaimMode.DETERMINISTIC:
        return command, None
    if type(ledger) is not TerritorialClaimLedger or identity is None:
        return command, ()
    breaches = [
        item
        for claim in ledger.claims
        for item in claim.evidence
        if item.channel is ClaimChannel.VIOLATION and item.tick == tick
    ]
    if type(command) is not Wait:
        if breaches:
            _LOG.warning(
                "territorial_response owner_id=%s reason=%s command=%s",
                owner_id.value,
                "command_already_selected",
                type(command).__name__,
            )
        return command, ()
    actor_by_event = {
        occurrence.provenance.source_event_id.value: occurrence.actor_id
        for occurrence in observation.occurrences
        if occurrence.provenance.source_event_id is not None
    }

    def recipient_for(excluded: EntityId | None) -> EntityId | None:
        visible = tuple(body.entity_id for body in observation.visible_bodies)
        choices = []
        for body in observation.visible_bodies:
            if body.entity_id == identity.owner_entity_id:
                continue
            if excluded is not None and body.entity_id == excluded:
                continue
            if observation_allows_communication_target(
                visibility=observation.visibility,
                visible_body_ids=visible,
                recipient_id=body.entity_id,
                visibility_threshold=CONTENT_VISIBILITY_THRESHOLD,
            ):
                choices.append(body.entity_id)
        if not choices:
            return None
        return min(choices, key=lambda item: item.value)

    def tell(predicate: str, claim: TerritorialClaim, recipient: EntityId) -> Tell:
        utterance = origin_utterance(
            text=predicate,
            speaker_id=identity.owner_entity_id,
            communication_id=f"territorial-{owner_id.value}-{tick}-{predicate}",
            relations=(
                CommunicationRelation(
                    subject=claim.target_entity_id.value,
                    predicate=predicate,
                    object=claim.target_kind.value,
                ),
            ),
        )
        _LOG.debug(
            "territorial_tell owner_id=%s predicate=%s target_kind=%s",
            owner_id.value,
            predicate,
            claim.target_kind.value,
        )
        return Tell(recipient_id=recipient, utterance=utterance)

    if breaches:
        evidence = breaches[0]
        claim = next(
            item
            for item in ledger.claims
            if any(piece is evidence for piece in item.evidence)
        )
        actor_entity = actor_by_event.get(evidence.lineage_ref)
        actor = (
            _resolve_agent(identity, actor_entity)
            if type(actor_entity) is EntityId
            else None
        )
        profile = None if actor is None else _profile_for(relationships, actor)
        _trust, resentment, fear = relationship_projection(profile)
        if (
            resentment >= _DEFEND_RESENTMENT
            and fear < _DEFEND_FEAR_BELOW
            and type(actor_entity) is EntityId
        ):
            _LOG.debug(
                "territorial_response owner_id=%s reason=%s command=%s",
                owner_id.value,
                "defend",
                "Attack",
            )
            return Attack(target_id=actor_entity), (
                TerritorialClaimAudit(
                    owner_id=owner_id,
                    tick=tick,
                    reason_code="defend",
                    target_kind=claim.target_kind,
                    target_entity_id=claim.target_entity_id,
                    policy_version=TERRITORIAL_CLAIM_POLICY_VERSION,
                ),
            )
        recipient = recipient_for(None)
        if recipient is not None:
            _LOG.debug(
                "territorial_response owner_id=%s reason=%s command=%s",
                owner_id.value,
                "challenge",
                "Tell",
            )
            return tell("disputes", claim, recipient), (
                TerritorialClaimAudit(
                    owner_id=owner_id,
                    tick=tick,
                    reason_code="challenge",
                    target_kind=claim.target_kind,
                    target_entity_id=claim.target_entity_id,
                    policy_version=TERRITORIAL_CLAIM_POLICY_VERSION,
                ),
            )
    own = [claim for claim in ledger.claims if claim.strength >= _ANNOUNCE_STRENGTH]
    if own:
        claim = sorted(
            own, key=lambda item: (item.target_kind.value, item.target_entity_id.value)
        )[0]
        recipient = recipient_for(claim.target_entity_id)
        if recipient is not None:
            return tell("claims", claim, recipient), (
                TerritorialClaimAudit(
                    owner_id=owner_id,
                    tick=tick,
                    reason_code="communicate",
                    target_kind=claim.target_kind,
                    target_entity_id=claim.target_entity_id,
                    policy_version=TERRITORIAL_CLAIM_POLICY_VERSION,
                ),
            )
    return command, ()
