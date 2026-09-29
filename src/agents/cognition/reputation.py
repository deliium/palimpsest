"""Owner-scoped dimensional assessments of other agents.

Each owner holds a private ledger. A profile is one directed head. This
module does not read world authority, another agent's ledger, or an analysis
aggregate.
"""

from __future__ import annotations

import hashlib
import logging
import math
import re
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
from world.observations import Observation, ObservedCommunication, ObservedOccurrence

_LOG: Final[logging.Logger] = logging.getLogger("agents.cognition.reputation")

REPUTATION_POLICY_VERSION: Final[str] = "reputation-formation.v1"
_QUANTUM: Final[Decimal] = Decimal("0.000001")
_SPEECH_RATE: Final[float] = 0.5
_REMEMBERED_SCALE: Final[float] = 0.5
_READING_THRESHOLD: Final[float] = 0.4
_MAX_PROFILES: Final[int] = 32
_MAX_EVIDENCE: Final[int] = 64
_LOW_TRUST_BELOW: Final[float] = 0.35
_HIGH_TRUST_FROM: Final[float] = 0.65
_DIRECT_SCALE: Final[float] = 1.0
_CANONICAL_DECIMAL: Final[re.Pattern[str]] = re.compile(
    r"^-?(?:0|[1-9]\d*)(?:\.\d{1,6})?$"
)
_MAX_UTTERANCE_RELATIONS: Final[int] = 4
_FORBIDDEN_INPUTS: Final[frozenset[str]] = frozenset(
    {"WorldState", "WorldEvent", "PhysicalRules", "AgentBody"}
)


class ReputationDimension(StrEnum):
    """Independent signed axes. They are not combined into one score."""

    RELIABILITY = "reliability"
    HARM = "harm"
    GENEROSITY = "generosity"
    COMPETENCE = "competence"


class ReputationChannel(StrEnum):
    """Closed provenance channel for one contribution."""

    DIRECT_OBSERVATION = "direct_observation"
    REMEMBERED_INTERACTION = "remembered_interaction"
    COMMUNICATION = "communication"
    THIRD_PARTY_STORY = "third_party_story"


class ReputationSourceTrustBand(StrEnum):
    """Coarse band recorded at adoption. Own evidence is unmediated."""

    LOW = "low"
    MID = "mid"
    HIGH = "high"
    UNMEDIATED = "unmediated"


_OBSERVATION_DELTAS: Final[
    Mapping[str, tuple[tuple[ReputationDimension, float], ...]]
] = {
    "help": (
        (ReputationDimension.GENEROSITY, 0.25),
        (ReputationDimension.RELIABILITY, 0.10),
        (ReputationDimension.HARM, -0.05),
    ),
    "give": (
        (ReputationDimension.GENEROSITY, 0.30),
        (ReputationDimension.RELIABILITY, 0.05),
    ),
    "attack": (
        (ReputationDimension.HARM, 0.35),
        (ReputationDimension.RELIABILITY, -0.10),
        (ReputationDimension.GENEROSITY, -0.15),
    ),
}


def _fail(field_name: str, code: str) -> ValueError:
    _LOG.error(
        "reputation_validation_failed field=%s reason_code=%s",
        field_name,
        code,
    )
    return ValueError(f"{field_name}: {code}")


def _sha256_hex(material: str) -> str:
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def reputation_profile_id(owner_id: AgentId, target_id: AgentId) -> str:
    """sha256 of the owner id and the target id. No Python ``hash()``."""
    if type(owner_id) is not AgentId:
        raise _fail("owner_id", "invalid_type")
    if type(target_id) is not AgentId:
        raise _fail("target_id", "invalid_type")
    return _sha256_hex(f"{owner_id.value}|{target_id.value}")


def reputation_evidence_id(
    *,
    profile_id: str,
    ordinal: int,
    dimension: ReputationDimension,
    channel: ReputationChannel,
    lineage_ref: str,
) -> str:
    """sha256 of profile id, ordinal, dimension, channel, and lineage ref."""
    if type(dimension) is not ReputationDimension:
        raise _fail("dimension", "unknown_dimension")
    if type(channel) is not ReputationChannel:
        raise _fail("channel", "unknown_channel")
    if (
        not isinstance(profile_id, str)
        or len(profile_id) != 64
        or any(char not in "0123456789abcdef" for char in profile_id)
    ):
        raise _fail("profile_id", "invalid_profile_id")
    try:
        ordinal_value = require_exact_nonneg_int("ordinal", ordinal)
    except ValueError as exc:
        raise _fail("ordinal", "invalid_ordinal") from exc
    try:
        lineage = require_stable_id("lineage_ref", lineage_ref)
    except ValueError as exc:
        raise _fail("lineage_ref", "invalid_lineage") from exc
    material = (
        f"{profile_id}|{ordinal_value}|{dimension.value}|{channel.value}|{lineage}"
    )
    return _sha256_hex(material)


def _quantize(value: float) -> float:
    steps = round(value / 1e-6)
    quantized = float(Decimal(steps) * _QUANTUM)
    return 0.0 if quantized == 0.0 else quantized


def _signed_unit(field_name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _fail(field_name, "not_finite")
    number = float(value)
    if not math.isfinite(number):
        raise _fail(field_name, "not_finite")
    if number < -1.0 or number > 1.0:
        raise _fail(field_name, "out_of_range")
    quantized = _quantize(number)
    if quantized < -1.0 or quantized > 1.0:
        raise _fail(field_name, "out_of_range")
    return quantized


def _nonnegative_mass(field_name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _fail(field_name, "not_finite")
    number = float(value)
    if not math.isfinite(number):
        raise _fail(field_name, "not_finite")
    if number < 0.0:
        raise _fail(field_name, "out_of_range")
    return _quantize(number)


def _require_tuple(field_name: str, values: object) -> tuple[object, ...]:
    if isinstance(values, (str, bytes, set, frozenset)) or not isinstance(
        values, Sequence
    ):
        raise _fail(field_name, "invalid_type")
    return tuple(values)


def neutral_dimension_state() -> ReputationDimensionState:
    """Zero head for one dimension."""
    return ReputationDimensionState(
        value=0.0,
        support_mass=0.0,
        contradiction_mass=0.0,
    )


def source_trust_band_for(
    trust: float,
    *,
    unmediated: bool = False,
) -> ReputationSourceTrustBand:
    """Map a caller-projected trust float onto a closed band."""
    if unmediated:
        return ReputationSourceTrustBand.UNMEDIATED
    if isinstance(trust, bool) or not isinstance(trust, (int, float)):
        raise _fail("source_trust", "not_finite")
    number = float(trust)
    if not math.isfinite(number):
        raise _fail("source_trust", "not_finite")
    if number < 0.0 or number > 1.0:
        raise _fail("source_trust", "out_of_range")
    if number < _LOW_TRUST_BELOW:
        return ReputationSourceTrustBand.LOW
    if number < _HIGH_TRUST_FROM:
        return ReputationSourceTrustBand.MID
    return ReputationSourceTrustBand.HIGH


@dataclass(frozen=True, slots=True)
class ReputationDimensionState:
    """Clamped signed value plus independent support and contradiction mass."""

    value: float
    support_mass: float
    contradiction_mass: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _signed_unit("value", self.value))
        object.__setattr__(
            self,
            "support_mass",
            _nonnegative_mass("support_mass", self.support_mass),
        )
        object.__setattr__(
            self,
            "contradiction_mass",
            _nonnegative_mass("contradiction_mass", self.contradiction_mass),
        )


@dataclass(frozen=True, slots=True)
class ReputationEvidenceItem:
    """One adopted contribution. The id is derived; it is not chosen by RNG."""

    owner_id: AgentId
    target_id: AgentId
    dimension: ReputationDimension
    channel: ReputationChannel
    lineage_ref: str
    source_id: AgentId
    pre_scale_delta: float
    source_trust_band: ReputationSourceTrustBand
    tick: int
    policy_version: str
    profile_id: str
    ordinal: int
    evidence_id: str = field(init=False)

    def __post_init__(self) -> None:
        if type(self.owner_id) is not AgentId:
            raise _fail("owner_id", "invalid_type")
        if type(self.target_id) is not AgentId:
            raise _fail("target_id", "invalid_type")
        if self.owner_id == self.target_id:
            raise _fail("target_id", "owner_is_target")
        if type(self.dimension) is not ReputationDimension:
            raise _fail("dimension", "unknown_dimension")
        if type(self.channel) is not ReputationChannel:
            raise _fail("channel", "unknown_channel")
        if type(self.source_id) is not AgentId:
            raise _fail("source_id", "invalid_type")
        if type(self.source_trust_band) is not ReputationSourceTrustBand:
            raise _fail("source_trust_band", "unknown_band")
        if self.policy_version != REPUTATION_POLICY_VERSION:
            raise _fail("policy_version", "unsupported_policy")
        try:
            lineage = require_stable_id("lineage_ref", self.lineage_ref)
        except ValueError as exc:
            raise _fail("lineage_ref", "invalid_lineage") from exc
        try:
            profile = require_stable_id("profile_id", self.profile_id)
        except ValueError as exc:
            raise _fail("profile_id", "invalid_profile_id") from exc
        if len(profile) != 64 or any(
            char not in "0123456789abcdef" for char in profile
        ):
            raise _fail("profile_id", "invalid_profile_id")
        try:
            ordinal = require_exact_nonneg_int("ordinal", self.ordinal)
        except ValueError as exc:
            raise _fail("ordinal", "invalid_ordinal") from exc
        try:
            tick = require_exact_nonneg_int("tick", self.tick)
        except ValueError as exc:
            raise _fail("tick", "invalid_tick") from exc
        object.__setattr__(self, "lineage_ref", lineage)
        object.__setattr__(self, "profile_id", profile)
        object.__setattr__(self, "ordinal", ordinal)
        object.__setattr__(self, "tick", tick)
        object.__setattr__(
            self,
            "pre_scale_delta",
            _signed_unit("pre_scale_delta", self.pre_scale_delta),
        )
        object.__setattr__(
            self,
            "evidence_id",
            reputation_evidence_id(
                profile_id=profile,
                ordinal=ordinal,
                dimension=self.dimension,
                channel=self.channel,
                lineage_ref=lineage,
            ),
        )


@dataclass(frozen=True, slots=True)
class ReputationProfile:
    """One ``(owner, target)`` head and the evidence that formed it."""

    profile_id: str
    owner_id: AgentId
    target_id: AgentId
    reliability: ReputationDimensionState
    harm: ReputationDimensionState
    generosity: ReputationDimensionState
    competence: ReputationDimensionState
    evidence: tuple[ReputationEvidenceItem, ...] = ()

    def __post_init__(self) -> None:
        if type(self.owner_id) is not AgentId:
            raise _fail("owner_id", "invalid_type")
        if type(self.target_id) is not AgentId:
            raise _fail("target_id", "invalid_type")
        if self.owner_id == self.target_id:
            raise _fail("target_id", "owner_is_target")
        expected = reputation_profile_id(self.owner_id, self.target_id)
        if self.profile_id != expected:
            raise _fail("profile_id", "profile_id_mismatch")
        for name in ("reliability", "harm", "generosity", "competence"):
            state = getattr(self, name)
            if type(state) is not ReputationDimensionState:
                raise _fail(name, "invalid_type")
        evidence = _require_tuple("evidence", self.evidence)
        if len(evidence) > _MAX_EVIDENCE:
            raise _fail("evidence", "cap_exceeded")
        seen: set[tuple[ReputationChannel, str, ReputationDimension]] = set()
        checked: list[ReputationEvidenceItem] = []
        for ordinal, item in enumerate(evidence):
            if type(item) is not ReputationEvidenceItem:
                raise _fail("evidence", "invalid_type")
            if item.owner_id != self.owner_id:
                raise _fail("evidence.owner_id", "owner_mismatch")
            if item.target_id != self.target_id:
                raise _fail("evidence.target_id", "target_mismatch")
            if item.profile_id != self.profile_id or item.ordinal != ordinal:
                raise _fail("evidence.evidence_id", "evidence_id_mismatch")
            key = (item.channel, item.lineage_ref, item.dimension)
            if key in seen:
                raise _fail("evidence", "duplicate_evidence")
            seen.add(key)
            checked.append(item)
        object.__setattr__(self, "evidence", tuple(checked))

    def dimension_state(
        self, dimension: ReputationDimension
    ) -> ReputationDimensionState:
        """Return the head for one dimension. The four heads stay independent."""
        if type(dimension) is not ReputationDimension:
            raise _fail("dimension", "unknown_dimension")
        state = getattr(self, dimension.value)
        if type(state) is not ReputationDimensionState:
            raise _fail(dimension.value, "invalid_type")
        return state


@dataclass(frozen=True, slots=True)
class ReputationLedger:
    """Private profiles owned by one agent. There is no shared score."""

    owner_id: AgentId
    profiles: tuple[ReputationProfile, ...] = ()

    def __post_init__(self) -> None:
        if type(self.owner_id) is not AgentId:
            raise _fail("owner_id", "invalid_type")
        profiles = _require_tuple("profiles", self.profiles)
        if len(profiles) > _MAX_PROFILES:
            raise _fail("profiles", "cap_exceeded")
        seen: set[AgentId] = set()
        checked: list[ReputationProfile] = []
        for item in profiles:
            if type(item) is not ReputationProfile:
                raise _fail("profiles", "invalid_type")
            if item.owner_id != self.owner_id:
                raise _fail("profiles.owner_id", "owner_mismatch")
            if item.target_id in seen:
                raise _fail("profiles.target_id", "duplicate_target")
            seen.add(item.target_id)
            checked.append(item)
        object.__setattr__(self, "profiles", tuple(checked))
        _LOG.debug(
            "reputation_ledger_constructed owner_id=%s policy_version=%s "
            "profile_count=%s",
            self.owner_id.value,
            REPUTATION_POLICY_VERSION,
            len(self.profiles),
        )

    def profile_for(self, target_id: AgentId) -> ReputationProfile | None:
        """Return the head for one target, or ``None`` when absent."""
        if type(target_id) is not AgentId:
            raise _fail("target_id", "invalid_type")
        for profile in self.profiles:
            if profile.target_id == target_id:
                return profile
        return None


@dataclass(frozen=True, slots=True)
class ReputationFormationPolicy:
    """Locked formation constants. Runner JSON does not carry these weights."""

    version: str = REPUTATION_POLICY_VERSION
    speech_rate: float = _SPEECH_RATE
    remembered_scale: float = _REMEMBERED_SCALE
    reading_threshold: float = _READING_THRESHOLD
    max_profiles: int = _MAX_PROFILES
    max_evidence: int = _MAX_EVIDENCE

    def __post_init__(self) -> None:
        if self.version != REPUTATION_POLICY_VERSION:
            raise _fail("version", "unsupported_policy")
        if _signed_unit("speech_rate", self.speech_rate) != _SPEECH_RATE:
            raise _fail("speech_rate", "unsupported_policy")
        if _signed_unit("remembered_scale", self.remembered_scale) != (
            _REMEMBERED_SCALE
        ):
            raise _fail("remembered_scale", "unsupported_policy")
        if _signed_unit("reading_threshold", self.reading_threshold) != (
            _READING_THRESHOLD
        ):
            raise _fail("reading_threshold", "unsupported_policy")
        if self.max_profiles != _MAX_PROFILES:
            raise _fail("max_profiles", "unsupported_policy")
        if self.max_evidence != _MAX_EVIDENCE:
            raise _fail("max_evidence", "unsupported_policy")
        _LOG.debug(
            "reputation_policy_constructed policy_version=%s",
            self.version,
        )


def default_reputation_policy() -> ReputationFormationPolicy:
    """Return the only accepted formation policy."""
    return ReputationFormationPolicy()


def empty_reputation_ledger(owner_id: AgentId) -> ReputationLedger:
    """Ledger with no profiles. Disabled mode does not call this."""
    return ReputationLedger(owner_id=owner_id)


def require_owner_reputation(
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
    if type(ledger) is not ReputationLedger:
        raise TypeError(f"{field_name} must be ReputationLedger")
    if ledger.owner_id != owner_id:
        raise ValueError(f"{field_name} owner_id mismatch")


def _reject_forbidden(field_name: str, value: object) -> None:
    candidate = value if isinstance(value, type) else type(value)
    if candidate.__name__ in _FORBIDDEN_INPUTS:
        raise TypeError(f"{field_name}: forbidden_input")


def _sign_label(delta: float) -> str:
    if delta > 0.0:
        return "positive"
    if delta < 0.0:
        return "negative"
    return "zero"


def _clamp_signed(value: float) -> float:
    if not math.isfinite(value):
        raise _fail("value", "not_finite")
    if value > 1.0:
        value = 1.0
    elif value < -1.0:
        value = -1.0
    quantized = _quantize(value)
    if quantized > 1.0:
        return 1.0
    if quantized < -1.0:
        return -1.0
    return quantized


def _moved_state(
    state: ReputationDimensionState, applied: float
) -> ReputationDimensionState:
    support = state.support_mass
    contradiction = state.contradiction_mass
    if applied > 0.0:
        support = _quantize(support + applied)
    elif applied < 0.0:
        contradiction = _quantize(contradiction + abs(applied))
    return ReputationDimensionState(
        value=_clamp_signed(state.value + applied),
        support_mass=support,
        contradiction_mass=contradiction,
    )


def _with_dimension(
    profile: ReputationProfile,
    dimension: ReputationDimension,
    state: ReputationDimensionState,
    evidence: tuple[ReputationEvidenceItem, ...],
) -> ReputationProfile:
    return ReputationProfile(
        profile_id=profile.profile_id,
        owner_id=profile.owner_id,
        target_id=profile.target_id,
        reliability=(
            state
            if dimension is ReputationDimension.RELIABILITY
            else profile.reliability
        ),
        harm=state if dimension is ReputationDimension.HARM else profile.harm,
        generosity=(
            state
            if dimension is ReputationDimension.GENEROSITY
            else profile.generosity
        ),
        competence=(
            state
            if dimension is ReputationDimension.COMPETENCE
            else profile.competence
        ),
        evidence=evidence,
    )


def _counterpart_agent(
    identity: OwnerSafeSocialIdentity, entity_id: EntityId | None
) -> AgentId | None:
    if type(entity_id) is not EntityId:
        return None
    for binding in identity.counterparts:
        if binding.entity_id == entity_id:
            return binding.agent_id
    return None


def _drop(owner_id: AgentId, tick: int, reason: str) -> None:
    _LOG.warning(
        "reputation_evidence_dropped owner_id=%s tick=%s reason=%s",
        owner_id.value,
        tick,
        reason,
    )


def _skip_memory(owner_id: AgentId, tick: int, memory_id: str, reason: str) -> None:
    _LOG.warning(
        "reputation_memory_skipped owner_id=%s tick=%s memory_id=%s reason=%s",
        owner_id.value,
        tick,
        memory_id,
        reason,
    )


def _interaction_cue(trace: MemoryTrace) -> str | None:
    for concept in trace.concepts:
        if (
            concept.mention_id.value == "c-kind"
            and concept.concept in _OBSERVATION_DELTAS
        ):
            return concept.concept
    return None


def _mentioned_entity(trace: MemoryTrace, mention_id: str) -> EntityId | None:
    for entity in trace.entities:
        if entity.mention_id.value == mention_id:
            return entity.entity_id
    return None


def canonical_signed_decimal(value: float) -> str:
    """Quantized signed decimal without exponent, sign prefix, or trailing zeros."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _fail("value", "not_finite")
    number = float(value)
    if not math.isfinite(number):
        raise _fail("value", "not_finite")
    if number < -1.0 or number > 1.0:
        raise _fail("value", "out_of_range")
    steps = round(number / 1e-6)
    text = format(Decimal(steps) * _QUANTUM, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    if text in {"", "-0"}:
        return "0"
    return text


def _parse_canonical_signed(token: object) -> float | None:
    if not isinstance(token, str) or _CANONICAL_DECIMAL.fullmatch(token) is None:
        return None
    try:
        number = float(token)
    except ValueError:
        return None
    if not math.isfinite(number) or number < -1.0 or number > 1.0:
        return None
    if canonical_signed_decimal(number) != token:
        return None
    return _quantize(number)


def _resolve_social_agent(
    identity: OwnerSafeSocialIdentity, entity_id: EntityId | None
) -> AgentId | None:
    if type(entity_id) is not EntityId:
        return None
    if entity_id == identity.owner_entity_id:
        return identity.owner_id
    return _counterpart_agent(identity, entity_id)


def _reject_testimony(
    owner_id: AgentId, tick: int, reason: str
) -> None:
    _LOG.warning(
        "reputation_testimony_rejected owner_id=%s tick=%s reason=%s",
        owner_id.value,
        tick,
        reason,
    )


def _entity_from_token(token: str) -> EntityId | None:
    try:
        return EntityId(token)
    except ValueError:
        return None


def _direct_lineages(profiles: Sequence[ReputationProfile]) -> set[str]:
    return {
        item.lineage_ref
        for profile in profiles
        for item in profile.evidence
        if item.channel is ReputationChannel.DIRECT_OBSERVATION
    }


def _occurrence_applies(occurrence: ObservedOccurrence) -> bool:
    if occurrence.kind == "attack":
        return occurrence.success is True
    return occurrence.success is not False


def _known_agent(identity: OwnerSafeSocialIdentity, agent_id: AgentId) -> bool:
    if agent_id == identity.owner_id:
        return True
    return any(binding.agent_id == agent_id for binding in identity.counterparts)


def _adopt_testified_dimension(
    *,
    owner_id: AgentId,
    tick: int,
    target_id: AgentId,
    speaker_id: AgentId,
    dimension: ReputationDimension,
    channel: ReputationChannel,
    testified: float,
    lineage: str,
    trust: float,
    band: ReputationSourceTrustBand,
    policy: ReputationFormationPolicy,
    profiles: list[ReputationProfile],
    index_by_target: dict[AgentId, int],
) -> None:
    index = index_by_target.get(target_id)
    profile = None if index is None else profiles[index]
    if profile is not None and any(
        item.channel is channel
        and item.lineage_ref == lineage
        and item.dimension is dimension
        for item in profile.evidence
    ):
        return
    if profile is None and len(profiles) >= policy.max_profiles:
        _drop(owner_id, tick, "cap_exceeded")
        return
    if profile is not None and len(profile.evidence) >= policy.max_evidence:
        _drop(owner_id, tick, "cap_exceeded")
        return
    current = 0.0 if profile is None else profile.dimension_state(dimension).value
    pre_scale = _clamp_signed((testified - current) * policy.speech_rate)
    applied = _quantize(pre_scale * trust)
    if profile is None:
        profile = ReputationProfile(
            profile_id=reputation_profile_id(owner_id, target_id),
            owner_id=owner_id,
            target_id=target_id,
            reliability=neutral_dimension_state(),
            harm=neutral_dimension_state(),
            generosity=neutral_dimension_state(),
            competence=neutral_dimension_state(),
        )
    evidence = (
        *profile.evidence,
        ReputationEvidenceItem(
            owner_id=owner_id,
            target_id=target_id,
            dimension=dimension,
            channel=channel,
            lineage_ref=lineage,
            source_id=speaker_id,
            pre_scale_delta=pre_scale,
            source_trust_band=band,
            tick=tick,
            policy_version=policy.version,
            profile_id=profile.profile_id,
            ordinal=len(profile.evidence),
        ),
    )
    updated = _with_dimension(
        profile,
        dimension,
        _moved_state(profile.dimension_state(dimension), applied),
        evidence,
    )
    if index is None:
        index_by_target[target_id] = len(profiles)
        profiles.append(updated)
    else:
        profiles[index] = updated
    _LOG.debug(
        "reputation_testimony_applied owner_id=%s tick=%s speaker_id=%s "
        "target_id=%s channel=%s dimension=%s source_trust_band=%s",
        owner_id.value,
        tick,
        speaker_id.value,
        target_id.value,
        channel.value,
        dimension.value,
        band.value,
    )


def _bounded_trust(field_name: str, value: float | None) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _fail(field_name, "not_finite")
    number = float(value)
    if not math.isfinite(number) or number < 0.0 or number > 1.0:
        raise _fail(field_name, "out_of_range")
    return number


def _trust_for_speaker(
    speaker_id: AgentId,
    by_speaker: Mapping[str, float] | None,
    fallback: float | None,
) -> tuple[float, bool]:
    if by_speaker is not None and speaker_id.value in by_speaker:
        resolved = _bounded_trust(
            "source_trust", by_speaker[speaker_id.value]
        )
        if resolved is None:
            return 0.5, True
        return resolved, False
    if fallback is None:
        return 0.5, True
    return fallback, False


def _apply_testimony(
    *,
    owner_id: AgentId,
    tick: int,
    identity: OwnerSafeSocialIdentity,
    observation: Observation,
    inbox: Sequence[CommunicationEnvelope] | None,
    profiles: list[ReputationProfile],
    index_by_target: dict[AgentId, int],
    policy: ReputationFormationPolicy,
    source_trust: float | None,
    source_trust_by_speaker: Mapping[str, float] | None,
) -> None:
    speeches: list[tuple[StructuredUtterance, AgentId, AgentId]] = []
    for communication in observation.communications:
        _reject_forbidden("communication", communication)
        if type(communication) is not ObservedCommunication:
            _reject_testimony(owner_id, tick, "invalid_testimony")
            continue
        speaker = _resolve_social_agent(identity, communication.speaker_id)
        listener = _resolve_social_agent(identity, communication.listener_id)
        if speaker is None or listener is None:
            _reject_testimony(owner_id, tick, "unresolved_entity")
            continue
        speeches.append((communication.utterance, speaker, listener))
    if inbox is not None:
        if isinstance(inbox, (str, bytes, set, frozenset)) or not isinstance(
            inbox, Sequence
        ):
            raise _fail("inbox", "invalid_type")
        for envelope in inbox:
            _reject_forbidden("inbox", envelope)
            if type(envelope) is not CommunicationEnvelope:
                _reject_testimony(owner_id, tick, "invalid_testimony")
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
            if utterance is None or not _known_agent(identity, envelope.sender_id):
                _reject_testimony(owner_id, tick, "unresolved_entity")
                continue
            speeches.append((utterance, envelope.sender_id, envelope.recipient_id))
    fallback = _bounded_trust("source_trust", source_trust)
    logged_missing: set[str] = set()
    for utterance, speaker_id, listener_id in speeches:
        if utterance.declared.hop_count > 1:
            _reject_testimony(owner_id, tick, "hop_dropped")
            continue
        trust, missing_trust = _trust_for_speaker(
            speaker_id,
            source_trust_by_speaker,
            fallback,
        )
        band = source_trust_band_for(trust)
        chosen: AgentId | None = None
        adopted = 0
        for relation in utterance.content.relations:
            if adopted >= _MAX_UTTERANCE_RELATIONS:
                break
            try:
                dimension = ReputationDimension(relation.predicate)
            except ValueError:
                _reject_testimony(owner_id, tick, "invalid_testimony")
                continue
            testified = _parse_canonical_signed(relation.object)
            if testified is None:
                _reject_testimony(owner_id, tick, "invalid_testimony")
                continue
            subject = _resolve_social_agent(
                identity, _entity_from_token(relation.subject)
            )
            if subject is None:
                _reject_testimony(owner_id, tick, "unresolved_entity")
                continue
            if subject == listener_id:
                _reject_testimony(owner_id, tick, "self_subject")
                continue
            if chosen is None:
                chosen = subject
            elif subject != chosen:
                continue
            channel = (
                ReputationChannel.COMMUNICATION
                if subject == speaker_id
                else ReputationChannel.THIRD_PARTY_STORY
            )
            _adopt_testified_dimension(
                owner_id=owner_id,
                tick=tick,
                target_id=subject,
                speaker_id=speaker_id,
                dimension=dimension,
                channel=channel,
                testified=testified,
                lineage=utterance.declared.communication_id.value,
                trust=trust,
                band=band,
                policy=policy,
                profiles=profiles,
                index_by_target=index_by_target,
            )
            adopted += 1
            if missing_trust and speaker_id.value not in logged_missing:
                _LOG.debug(
                    "reputation_source_trust owner_id=%s tick=%s "
                    "reason=source_trust_missing",
                    owner_id.value,
                    tick,
                )
                logged_missing.add(speaker_id.value)


def apply_reputation_update(
    *,
    owner_id: AgentId,
    tick: int,
    observation: Observation,
    social_identity: OwnerSafeSocialIdentity,
    ledger: ReputationLedger | None = None,
    policy: ReputationFormationPolicy | None = None,
    memories: Sequence[MemoryTrace] | None = None,
    source_trust: float | None = None,
    source_trust_by_speaker: Mapping[str, float] | None = None,
    inbox: Sequence[CommunicationEnvelope] | None = None,
    **forbidden: object,
) -> ReputationLedger:
    """Adopt this tick's qualifying occurrences into the owner's ledger.

    Disabled callers do not call this function. The returned traces and
    relationship heads are not rewritten here.
    """
    for name, value in forbidden.items():
        _reject_forbidden(name, value)
        raise TypeError(f"{name}: unexpected")
    _reject_forbidden("observation", observation)
    if type(owner_id) is not AgentId:
        raise _fail("owner_id", "invalid_type")
    if type(observation) is not Observation:
        raise TypeError("observation must be Observation")
    if type(social_identity) is not OwnerSafeSocialIdentity:
        raise TypeError("social_identity must be OwnerSafeSocialIdentity")
    try:
        resolved_tick = require_exact_nonneg_int("tick", tick)
    except ValueError as exc:
        raise _fail("tick", "invalid_tick") from exc
    if observation.tick != resolved_tick:
        raise _fail("tick", "tick_mismatch")
    if social_identity.owner_id != owner_id:
        raise _fail("owner_id", "owner_mismatch")
    active = policy if policy is not None else default_reputation_policy()
    if type(active) is not ReputationFormationPolicy:
        raise _fail("policy", "invalid_type")
    current = ledger if ledger is not None else empty_reputation_ledger(owner_id)
    if type(current) is not ReputationLedger:
        raise _fail("ledger", "invalid_type")
    if current.owner_id != owner_id:
        raise _fail("owner_id", "owner_mismatch")
    profiles: list[ReputationProfile] = list(current.profiles)
    index_by_target: dict[AgentId, int] = {
        profile.target_id: index for index, profile in enumerate(profiles)
    }
    for occurrence in observation.occurrences:
        _reject_forbidden("occurrence", occurrence)
        if type(occurrence) is not ObservedOccurrence:
            _drop(owner_id, resolved_tick, "ignored_kind")
            continue
        deltas = _OBSERVATION_DELTAS.get(occurrence.kind)
        if deltas is None:
            _drop(owner_id, resolved_tick, "ignored_kind")
            continue
        if not _occurrence_applies(occurrence):
            continue
        target_id = _counterpart_agent(social_identity, occurrence.actor_id)
        if target_id is None:
            _drop(owner_id, resolved_tick, "unresolved_entity")
            continue
        event_id = occurrence.provenance.source_event_id
        if event_id is None:
            raise _fail("lineage_ref", "invalid_lineage")
        lineage = event_id.value
        for dimension, pre_scale in deltas:
            index = index_by_target.get(target_id)
            profile = None if index is None else profiles[index]
            if profile is not None and any(
                item.channel is ReputationChannel.DIRECT_OBSERVATION
                and item.lineage_ref == lineage
                and item.dimension is dimension
                for item in profile.evidence
            ):
                continue
            if profile is None and len(profiles) >= active.max_profiles:
                _drop(owner_id, resolved_tick, "cap_exceeded")
                continue
            if profile is not None and len(profile.evidence) >= active.max_evidence:
                _drop(owner_id, resolved_tick, "cap_exceeded")
                continue
            if profile is None:
                profile = ReputationProfile(
                    profile_id=reputation_profile_id(owner_id, target_id),
                    owner_id=owner_id,
                    target_id=target_id,
                    reliability=neutral_dimension_state(),
                    harm=neutral_dimension_state(),
                    generosity=neutral_dimension_state(),
                    competence=neutral_dimension_state(),
                )
            applied = _quantize(pre_scale * _DIRECT_SCALE)
            evidence = (
                *profile.evidence,
                ReputationEvidenceItem(
                    owner_id=owner_id,
                    target_id=target_id,
                    dimension=dimension,
                    channel=ReputationChannel.DIRECT_OBSERVATION,
                    lineage_ref=lineage,
                    source_id=owner_id,
                    pre_scale_delta=pre_scale,
                    source_trust_band=ReputationSourceTrustBand.UNMEDIATED,
                    tick=resolved_tick,
                    policy_version=active.version,
                    profile_id=profile.profile_id,
                    ordinal=len(profile.evidence),
                ),
            )
            updated = _with_dimension(
                profile,
                dimension,
                _moved_state(profile.dimension_state(dimension), applied),
                evidence,
            )
            if index is None:
                index_by_target[target_id] = len(profiles)
                profiles.append(updated)
            else:
                profiles[index] = updated
            _LOG.debug(
                "reputation_observation_applied owner_id=%s tick=%s target_id=%s "
                "dimension=%s channel=%s sign=%s",
                owner_id.value,
                resolved_tick,
                target_id.value,
                dimension.value,
                ReputationChannel.DIRECT_OBSERVATION.value,
                _sign_label(pre_scale),
            )
    if memories is not None:
        if isinstance(memories, (str, bytes, set, frozenset)) or not isinstance(
            memories, Sequence
        ):
            raise _fail("memories", "invalid_type")
        seen_memory_ids: set[str] = set()
        for trace in memories:
            _reject_forbidden("memory", trace)
            if type(trace) is not MemoryTrace:
                _skip_memory(owner_id, resolved_tick, "unknown", "no_cue")
                continue
            memory_id = trace.memory_id.value
            if trace.owner_id != owner_id:
                raise _fail("memories.owner_id", "owner_mismatch")
            if trace.provenance.kind is not MemorySourceKind.DIRECT_OBSERVATION:
                _skip_memory(owner_id, resolved_tick, memory_id, "no_cue")
                continue
            if trace.provenance.source_tick >= resolved_tick:
                _skip_memory(owner_id, resolved_tick, memory_id, "too_recent")
                continue
            cue = _interaction_cue(trace)
            if cue is None:
                _skip_memory(owner_id, resolved_tick, memory_id, "no_cue")
                continue
            actor_entity = _mentioned_entity(trace, "e-actor")
            other_entity = _mentioned_entity(trace, "e-other")
            owner_entity = social_identity.owner_entity_id
            target_entity: EntityId | None
            if actor_entity == owner_entity and other_entity not in (
                None,
                owner_entity,
            ):
                target_entity = other_entity
            elif other_entity == owner_entity and actor_entity not in (
                None,
                owner_entity,
            ):
                target_entity = actor_entity
            else:
                _skip_memory(owner_id, resolved_tick, memory_id, "not_participant")
                continue
            observed = trace.provenance.observed_source_id
            if observed is not None and observed.value in _direct_lineages(profiles):
                _skip_memory(owner_id, resolved_tick, memory_id, "already_observed")
                continue
            if memory_id in seen_memory_ids:
                continue
            target_id = _counterpart_agent(social_identity, target_entity)
            if target_id is None:
                _skip_memory(owner_id, resolved_tick, memory_id, "unresolved_entity")
                continue
            applied_any = False
            for dimension, pre_scale in _OBSERVATION_DELTAS[cue]:
                index = index_by_target.get(target_id)
                profile = None if index is None else profiles[index]
                if profile is not None and any(
                    item.channel is ReputationChannel.REMEMBERED_INTERACTION
                    and item.lineage_ref == memory_id
                    and item.dimension is dimension
                    for item in profile.evidence
                ):
                    continue
                if profile is None and len(profiles) >= active.max_profiles:
                    _drop(owner_id, resolved_tick, "cap_exceeded")
                    continue
                if (
                    profile is not None
                    and len(profile.evidence) >= active.max_evidence
                ):
                    _drop(owner_id, resolved_tick, "cap_exceeded")
                    continue
                if profile is None:
                    profile = ReputationProfile(
                        profile_id=reputation_profile_id(owner_id, target_id),
                        owner_id=owner_id,
                        target_id=target_id,
                        reliability=neutral_dimension_state(),
                        harm=neutral_dimension_state(),
                        generosity=neutral_dimension_state(),
                        competence=neutral_dimension_state(),
                    )
                applied = _quantize(pre_scale * active.remembered_scale)
                evidence = (
                    *profile.evidence,
                    ReputationEvidenceItem(
                        owner_id=owner_id,
                        target_id=target_id,
                        dimension=dimension,
                        channel=ReputationChannel.REMEMBERED_INTERACTION,
                        lineage_ref=memory_id,
                        source_id=owner_id,
                        pre_scale_delta=pre_scale,
                        source_trust_band=ReputationSourceTrustBand.UNMEDIATED,
                        tick=resolved_tick,
                        policy_version=active.version,
                        profile_id=profile.profile_id,
                        ordinal=len(profile.evidence),
                    ),
                )
                updated = _with_dimension(
                    profile,
                    dimension,
                    _moved_state(profile.dimension_state(dimension), applied),
                    evidence,
                )
                if index is None:
                    index_by_target[target_id] = len(profiles)
                    profiles.append(updated)
                else:
                    profiles[index] = updated
                applied_any = True
                _LOG.debug(
                    "reputation_memory_applied owner_id=%s tick=%s memory_id=%s "
                    "target_id=%s dimension=%s sign=%s",
                    owner_id.value,
                    resolved_tick,
                    memory_id,
                    target_id.value,
                    dimension.value,
                    _sign_label(pre_scale),
                )
            if applied_any:
                seen_memory_ids.add(memory_id)
    _apply_testimony(
        owner_id=owner_id,
        tick=resolved_tick,
        identity=social_identity,
        observation=observation,
        inbox=inbox,
        profiles=profiles,
        index_by_target=index_by_target,
        policy=active,
        source_trust=source_trust,
        source_trust_by_speaker=source_trust_by_speaker,
    )
    result = ReputationLedger(owner_id=owner_id, profiles=tuple(profiles))
    evidence_count = sum(len(profile.evidence) for profile in result.profiles)
    _LOG.info(
        "reputation_head_updated owner_id=%s target_count=%s evidence_count=%s",
        owner_id.value,
        len(result.profiles),
        evidence_count,
    )
    return result
