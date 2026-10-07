"""Owner-scoped cultural feature beliefs and provenance contracts.

Owns the subjective half of ``cultural_historical_memory``: fallible,
owner-scoped cultural beliefs with closed feature kinds and transmission
channels. Never copies peer ledgers, society packs, or analysis traits.
There is no global Culture object — WorldEngine remains the only objective
authority; analytical traits live in ``analysis`` only.
"""

from __future__ import annotations

import hashlib
import logging
import math
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from agents.models import AgentId
from world.identifiers import require_exact_nonneg_int, require_stable_id

_LOG: Final[logging.Logger] = logging.getLogger("agents.cognition.cultural_features")

CULTURAL_FEATURE_POLICY_VERSION: Final[str] = "cultural-features-v1"

# Root uptake / independent rediscovery uses hop_index=0; children increment.
CULTURAL_FEATURE_FIRST_HOP_INDEX: Final[int] = 0

# Soft hop cap when mutation/recombination chains deepen (plan default).
CULTURAL_FEATURE_DEFAULT_HOP_CAP: Final[int] = 8

_CONFIDENCE_QUANTUM: Final[float] = 1e-6
_FINGERPRINT_TOKEN_WIDTH: Final[int] = 8
_REINFORCE_DELTA_DEFAULT: Final[float] = 0.05
_CONTENT_AFFINITY_BOOST: Final[float] = 0.05

_FORBIDDEN_FEATURE_KIND_ALIASES: Final[frozenset[str]] = frozenset(
    {
        "culture_pack",
        "encyclopedia",
        "society_memory",
        "global_culture",
        "tradition_law",
        "myth_object",
        "language_authority",
        "society_culture",
        "encyclopedia_download",
    }
)

_FORBIDDEN_CHANNEL_ALIASES: Final[frozenset[str]] = frozenset(
    {
        "culture_pack",
        "encyclopedia",
        "society_memory",
        "global_culture",
        "tradition_law",
        "myth_object",
        "language_authority",
    }
)

__all__ = [
    "CULTURAL_FEATURE_DEFAULT_HOP_CAP",
    "CULTURAL_FEATURE_FIRST_HOP_INDEX",
    "CULTURAL_FEATURE_POLICY_VERSION",
    "CulturalFeatureAudit",
    "CulturalFeatureKindId",
    "CulturalFeatureLedger",
    "CulturalFeatureUptakeCue",
    "CulturalTransmissionChannelId",
    "SubjectiveCulturalBelief",
    "apply_cultural_feature_channel_uptake",
    "apply_cultural_feature_compose_adapters",
    "apply_cultural_feature_from_teaching",
    "belief_to_audit",
    "collect_cultural_feature_compose_keys",
    "collect_cultural_feature_public_cues",
    "cultural_feature_bias_futures",
    "empty_cultural_feature_ledger",
    "form_or_reinforce_cultural_belief",
    "log_unsatisfiable_feature_kinds",
    "mutate_cultural_belief",
    "parse_cultural_feature_kind",
    "parse_cultural_transmission_channel",
    "recombine_cultural_beliefs",
    "require_owner_cultural_features",
    "upsert_cultural_belief",
]


class CulturalFeatureKindId(StrEnum):
    """Closed cultural feature kinds (never free-form society prose)."""

    PRACTICE = "practice"
    NARRATIVE_ELEMENT = "narrative_element"
    TERM = "term"
    PRODUCTION_TECHNIQUE = "production_technique"
    SOCIAL_EXPECTATION = "social_expectation"
    SYMBOLIC_ASSOCIATION = "symbolic_association"


class CulturalTransmissionChannelId(StrEnum):
    """Closed provenance channels for cultural feature uptake."""

    OBSERVATION = "observation"
    TEACHING = "teaching"
    COMMUNICATION = "communication"
    ARTIFACT = "artifact"
    IMITATION = "imitation"
    INDEPENDENT_REDISCOVERY = "independent_rediscovery"


def _fail(field_name: str, code: str) -> ValueError:
    _LOG.error(
        "cultural_feature_validation_failed field=%s reason_code=%s code=%s",
        field_name,
        code,
        code,
    )
    return ValueError(f"{field_name}: {code}")


def _finite(field_name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _fail(field_name, "not_finite")
    number = float(value)
    if not math.isfinite(number):
        raise _fail(field_name, "not_finite")
    return number


def _unit_interval(field_name: str, value: object) -> float:
    number = _finite(field_name, value)
    if number < 0.0 or number > 1.0:
        raise _fail(field_name, "out_of_range")
    return number


def _quantize_unit(value: float) -> float:
    steps = round(value / _CONFIDENCE_QUANTUM)
    quantized = steps * _CONFIDENCE_QUANTUM
    if quantized < 0.0:
        quantized = 0.0
    elif quantized > 1.0:
        quantized = 1.0
    return 0.0 if quantized == 0.0 else quantized


def _require_tuple(field_name: str, values: object) -> tuple[object, ...]:
    if isinstance(values, (str, bytes, set, frozenset)) or not isinstance(
        values, Sequence
    ):
        raise _fail(field_name, "invalid_type")
    return tuple(values)


def _reject_forbidden_feature_kind_alias(raw: str) -> None:
    if raw in _FORBIDDEN_FEATURE_KIND_ALIASES:
        raise _fail("feature_kind", "forbidden_feature_kind_alias")


def _reject_forbidden_channel_alias(raw: str) -> None:
    if raw in _FORBIDDEN_CHANNEL_ALIASES:
        raise _fail("channel", "forbidden_channel_alias")


def parse_cultural_feature_kind(value: object) -> CulturalFeatureKindId:
    """Parse a closed feature-kind id; reject society/encyclopedia aliases."""
    if type(value) is CulturalFeatureKindId:
        return value
    if not isinstance(value, str):
        raise _fail("feature_kind", "unknown_feature_kind")
    _reject_forbidden_feature_kind_alias(value)
    try:
        return CulturalFeatureKindId(value)
    except ValueError as exc:
        raise _fail("feature_kind", "unknown_feature_kind") from exc


def parse_cultural_transmission_channel(
    value: object,
) -> CulturalTransmissionChannelId:
    """Parse a closed provenance channel id."""
    if type(value) is CulturalTransmissionChannelId:
        return value
    if not isinstance(value, str):
        raise _fail("channel", "unknown_channel")
    _reject_forbidden_channel_alias(value)
    try:
        return CulturalTransmissionChannelId(value)
    except ValueError as exc:
        raise _fail("channel", "unknown_channel") from exc


def _confidence_band(confidence: float) -> str:
    value = _unit_interval("confidence", confidence)
    if value <= 0.0:
        return "none"
    if value < 0.34:
        return "low"
    if value < 0.67:
        return "mid"
    return "high"


def _digest_id_token(fingerprint: str, *, max_len: int = 24) -> str:
    """Opaque truncated digest token for audits (never free-form prose)."""
    token = require_stable_id("content_fingerprint", fingerprint)
    if len(token) <= max_len:
        return token
    return token[:max_len]


@dataclass(frozen=True, slots=True)
class SubjectiveCulturalBelief:
    """Owner-scoped cultural belief row (fallible; never an objective law)."""

    belief_id: str
    owner_agent_id: AgentId
    feature_kind: CulturalFeatureKindId
    content_key: str
    content_fingerprint: str
    channel: CulturalTransmissionChannelId
    confidence: float
    parent_belief_ids: tuple[str, ...]
    hop_index: int
    mutated: bool
    recombined: bool
    evidence_refs: tuple[str, ...]
    acquired_tick: int
    last_updated_tick: int
    policy_version: str = CULTURAL_FEATURE_POLICY_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "belief_id", require_stable_id("belief_id", self.belief_id)
        )
        if type(self.owner_agent_id) is not AgentId:
            raise _fail("owner_agent_id", "invalid_type")
        kind = parse_cultural_feature_kind(self.feature_kind)
        object.__setattr__(self, "feature_kind", kind)
        object.__setattr__(
            self, "content_key", require_stable_id("content_key", self.content_key)
        )
        object.__setattr__(
            self,
            "content_fingerprint",
            require_stable_id("content_fingerprint", self.content_fingerprint),
        )
        channel = parse_cultural_transmission_channel(self.channel)
        object.__setattr__(self, "channel", channel)
        confidence = _quantize_unit(_unit_interval("confidence", self.confidence))
        object.__setattr__(self, "confidence", confidence)

        raw_parents = _require_tuple("parent_belief_ids", self.parent_belief_ids)
        parents: list[str] = []
        seen_parents: set[str] = set()
        for item in raw_parents:
            parent_id = require_stable_id("parent_belief_ids", item)
            if parent_id in seen_parents:
                raise _fail("parent_belief_ids", "duplicate_parent")
            seen_parents.add(parent_id)
            parents.append(parent_id)
        object.__setattr__(self, "parent_belief_ids", tuple(parents))

        hop = require_exact_nonneg_int("hop_index", self.hop_index)
        if hop > CULTURAL_FEATURE_DEFAULT_HOP_CAP:
            raise _fail("hop_index", "cultural_feature_hop_cap")
        object.__setattr__(self, "hop_index", hop)

        if type(self.mutated) is not bool:
            raise _fail("mutated", "invalid_type")
        if type(self.recombined) is not bool:
            raise _fail("recombined", "invalid_type")

        raw_refs = _require_tuple("evidence_refs", self.evidence_refs)
        refs: list[str] = []
        seen_refs: set[str] = set()
        for item in raw_refs:
            ref = require_stable_id("evidence_refs", item)
            if ref in seen_refs:
                raise _fail("evidence_refs", "duplicate_evidence_ref")
            seen_refs.add(ref)
            refs.append(ref)
        object.__setattr__(self, "evidence_refs", tuple(refs))

        # Provenance required except independent rediscovery roots.
        if channel is CulturalTransmissionChannelId.INDEPENDENT_REDISCOVERY:
            if parents:
                raise _fail("parent_belief_ids", "independent_rediscovery_no_parents")
            if hop != CULTURAL_FEATURE_FIRST_HOP_INDEX:
                raise _fail("hop_index", "independent_rediscovery_hop_must_be_zero")
        elif not refs and not parents:
            raise _fail("evidence_refs", "provenance_required")

        if self.recombined and len(parents) < 2:
            raise _fail("parent_belief_ids", "recombination_requires_parents")

        acquired = require_exact_nonneg_int("acquired_tick", self.acquired_tick)
        updated = require_exact_nonneg_int("last_updated_tick", self.last_updated_tick)
        if updated < acquired:
            raise _fail("last_updated_tick", "before_acquired")
        object.__setattr__(self, "acquired_tick", acquired)
        object.__setattr__(self, "last_updated_tick", updated)

        if self.policy_version != CULTURAL_FEATURE_POLICY_VERSION:
            raise _fail("policy_version", "unsupported_policy")


@dataclass(frozen=True, slots=True)
class CulturalFeatureLedger:
    """Private cultural-feature belief ledger for one owner."""

    owner_id: AgentId
    beliefs: tuple[SubjectiveCulturalBelief, ...] = ()
    policy_version: str = CULTURAL_FEATURE_POLICY_VERSION
    max_beliefs: int = 128
    max_evidence_refs: int = 16

    def __post_init__(self) -> None:
        if type(self.owner_id) is not AgentId:
            raise _fail("owner_id", "invalid_type")
        if self.policy_version != CULTURAL_FEATURE_POLICY_VERSION:
            raise _fail("policy_version", "unsupported_policy")
        max_beliefs = require_exact_nonneg_int("max_beliefs", self.max_beliefs)
        if max_beliefs < 1:
            raise _fail("max_beliefs", "out_of_range")
        object.__setattr__(self, "max_beliefs", max_beliefs)
        max_refs = require_exact_nonneg_int("max_evidence_refs", self.max_evidence_refs)
        if max_refs < 1:
            raise _fail("max_evidence_refs", "out_of_range")
        object.__setattr__(self, "max_evidence_refs", max_refs)

        raw = _require_tuple("beliefs", self.beliefs)
        checked: list[SubjectiveCulturalBelief] = []
        seen_ids: set[str] = set()
        for item in raw:
            if type(item) is not SubjectiveCulturalBelief:
                raise _fail("beliefs", "invalid_type")
            if item.owner_agent_id != self.owner_id:
                raise _fail("beliefs", "owner_mismatch")
            if item.belief_id in seen_ids:
                raise _fail("beliefs", "duplicate_belief_id")
            seen_ids.add(item.belief_id)
            if len(item.evidence_refs) > max_refs:
                raise _fail("evidence_refs", "evidence_ref_cap")
            checked.append(item)
        if len(checked) > max_beliefs:
            raise _fail("beliefs", "max_beliefs_exceeded")
        object.__setattr__(self, "beliefs", tuple(checked))


@dataclass(frozen=True, slots=True)
class CulturalFeatureAudit:
    """Metadata-only cultural feature audit row (analysis harvest)."""

    owner_id: AgentId
    feature_kind: CulturalFeatureKindId
    channel: CulturalTransmissionChannelId
    hop_index: int
    mutated: bool
    recombined: bool
    parent_count: int
    confidence_band: str
    digest_id_token: str
    tick: int
    reason_code: str

    def __post_init__(self) -> None:
        if type(self.owner_id) is not AgentId:
            raise _fail("owner_id", "invalid_type")
        object.__setattr__(
            self, "feature_kind", parse_cultural_feature_kind(self.feature_kind)
        )
        object.__setattr__(
            self, "channel", parse_cultural_transmission_channel(self.channel)
        )
        object.__setattr__(
            self, "hop_index", require_exact_nonneg_int("hop_index", self.hop_index)
        )
        if type(self.mutated) is not bool:
            raise _fail("mutated", "invalid_type")
        if type(self.recombined) is not bool:
            raise _fail("recombined", "invalid_type")
        object.__setattr__(
            self,
            "parent_count",
            require_exact_nonneg_int("parent_count", self.parent_count),
        )
        band = require_stable_id("confidence_band", self.confidence_band)
        if band not in {"none", "low", "mid", "high"}:
            raise _fail("confidence_band", "unknown_band")
        object.__setattr__(self, "confidence_band", band)
        object.__setattr__(
            self,
            "digest_id_token",
            require_stable_id("digest_id_token", self.digest_id_token),
        )
        object.__setattr__(self, "tick", require_exact_nonneg_int("tick", self.tick))
        object.__setattr__(
            self, "reason_code", require_stable_id("reason_code", self.reason_code)
        )


def empty_cultural_feature_ledger(
    owner_id: AgentId,
    *,
    max_beliefs: int = 128,
    max_evidence_refs: int = 16,
) -> CulturalFeatureLedger:
    """Return an empty owner cultural-feature ledger (channel may be on)."""
    if type(owner_id) is not AgentId:
        raise _fail("owner_id", "invalid_type")
    ledger = CulturalFeatureLedger(
        owner_id=owner_id,
        max_beliefs=max_beliefs,
        max_evidence_refs=max_evidence_refs,
    )
    _LOG.debug(
        "cultural_feature_ledger_empty owner_id=%s belief_count=%s",
        owner_id.value,
        0,
    )
    return ledger


def require_owner_cultural_features(
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
    if type(ledger) is not CulturalFeatureLedger:
        _LOG.warning("cultural_feature_carry_rejected reason=%s", "invalid_type")
        raise TypeError(f"{field_name} must be CulturalFeatureLedger")
    if ledger.owner_id != owner_id:
        _LOG.error(
            "cultural_feature_validation_failed field=%s reason_code=%s",
            field_name,
            "owner_mismatch",
        )
        _LOG.warning("cultural_feature_carry_rejected reason=%s", "owner_mismatch")
        raise ValueError(f"{field_name} owner_id mismatch")


def belief_to_audit(
    belief: SubjectiveCulturalBelief,
    *,
    reason_code: str,
    tick: int | None = None,
) -> CulturalFeatureAudit:
    """Build a metadata-only audit from a belief (no content payloads)."""
    if type(belief) is not SubjectiveCulturalBelief:
        raise _fail("belief", "invalid_type")
    return CulturalFeatureAudit(
        owner_id=belief.owner_agent_id,
        feature_kind=belief.feature_kind,
        channel=belief.channel,
        hop_index=belief.hop_index,
        mutated=belief.mutated,
        recombined=belief.recombined,
        parent_count=len(belief.parent_belief_ids),
        confidence_band=_confidence_band(belief.confidence),
        digest_id_token=_digest_id_token(belief.content_fingerprint),
        tick=belief.last_updated_tick if tick is None else tick,
        reason_code=reason_code,
    )


def _fingerprint_tokens(fingerprint: str) -> list[str]:
    """Opaque fingerprint tokens: split on ``:`` or fixed-width chunks."""
    token = require_stable_id("content_fingerprint", fingerprint)
    if ":" in token:
        parts = [part for part in token.split(":") if part]
        return parts if parts else [token]
    width = _FINGERPRINT_TOKEN_WIDTH
    if len(token) <= width:
        return [token]
    return [token[i : i + width] for i in range(0, len(token), width)]


def _join_fingerprint_tokens(tokens: Sequence[str]) -> str:
    joined = ":".join(tokens)
    return require_stable_id("content_fingerprint", joined)


def _token_jaccard(left: str, right: str) -> float:
    left_set = set(_fingerprint_tokens(left))
    right_set = set(_fingerprint_tokens(right))
    if not left_set or not right_set:
        return 0.0
    union = left_set | right_set
    return len(left_set & right_set) / len(union)


def _cap_evidence_refs(
    refs: Sequence[str], *, max_refs: int
) -> tuple[str, ...]:
    checked: list[str] = []
    seen: set[str] = set()
    for item in refs:
        ref = require_stable_id("evidence_refs", item)
        if ref in seen:
            continue
        seen.add(ref)
        checked.append(ref)
        if len(checked) >= max_refs:
            break
    return tuple(checked)


def _belief_by_id(
    ledger: CulturalFeatureLedger, belief_id: str
) -> SubjectiveCulturalBelief | None:
    for belief in ledger.beliefs:
        if belief.belief_id == belief_id:
            return belief
    return None


def _resolve_hop_index(
    ledger: CulturalFeatureLedger,
    *,
    channel: CulturalTransmissionChannelId,
    parent_belief_ids: Sequence[str],
    parent_hop_index: int | None,
) -> int:
    if channel is CulturalTransmissionChannelId.INDEPENDENT_REDISCOVERY:
        return CULTURAL_FEATURE_FIRST_HOP_INDEX
    if not parent_belief_ids:
        return CULTURAL_FEATURE_FIRST_HOP_INDEX
    hops: list[int] = []
    for parent_id in parent_belief_ids:
        parent = _belief_by_id(ledger, parent_id)
        if parent is not None:
            hops.append(parent.hop_index)
        elif parent_hop_index is not None:
            hops.append(require_exact_nonneg_int("parent_hop_index", parent_hop_index))
        else:
            hops.append(CULTURAL_FEATURE_FIRST_HOP_INDEX)
    return max(hops) + 1


def _evict_oldest_beliefs(
    beliefs: Sequence[SubjectiveCulturalBelief],
    *,
    max_beliefs: int,
    owner_id: AgentId,
) -> list[SubjectiveCulturalBelief]:
    if len(beliefs) <= max_beliefs:
        return list(beliefs)
    ordered = sorted(
        beliefs,
        key=lambda row: (row.acquired_tick, row.belief_id),
    )
    kept = ordered[len(ordered) - max_beliefs :]
    _LOG.debug(
        "cultural_feature_evict owner_id=%s dropped=%s reason_code=%s",
        owner_id.value,
        len(ordered) - len(kept),
        "max_beliefs_evict",
    )
    return kept


def _replace_belief(
    ledger: CulturalFeatureLedger, belief: SubjectiveCulturalBelief
) -> CulturalFeatureLedger:
    rows = [
        belief if row.belief_id == belief.belief_id else row for row in ledger.beliefs
    ]
    if belief.belief_id not in {row.belief_id for row in ledger.beliefs}:
        rows.append(belief)
    rows = _evict_oldest_beliefs(
        rows, max_beliefs=ledger.max_beliefs, owner_id=ledger.owner_id
    )
    return CulturalFeatureLedger(
        owner_id=ledger.owner_id,
        beliefs=tuple(rows),
        policy_version=ledger.policy_version,
        max_beliefs=ledger.max_beliefs,
        max_evidence_refs=ledger.max_evidence_refs,
    )


def upsert_cultural_belief(
    ledger: CulturalFeatureLedger,
    belief: SubjectiveCulturalBelief,
) -> CulturalFeatureLedger:
    """Insert or replace a belief by ``belief_id`` with deterministic eviction."""
    if type(ledger) is not CulturalFeatureLedger:
        raise _fail("ledger", "invalid_type")
    if type(belief) is not SubjectiveCulturalBelief:
        raise _fail("belief", "invalid_type")
    if belief.owner_agent_id != ledger.owner_id:
        raise _fail("belief", "owner_mismatch")
    if len(belief.evidence_refs) > ledger.max_evidence_refs:
        raise _fail("evidence_refs", "evidence_ref_cap")
    if belief.hop_index > CULTURAL_FEATURE_DEFAULT_HOP_CAP:
        _LOG.error(
            "cultural_feature_validation_failed field=%s reason_code=%s code=%s",
            "hop_index",
            "cultural_feature_hop_cap",
            "cultural_feature_hop_cap",
        )
        raise _fail("hop_index", "cultural_feature_hop_cap")
    result = _replace_belief(ledger, belief)
    _LOG.debug(
        "cultural_feature_upsert owner_id=%s feature_kind=%s channel=%s "
        "hop_index=%s mutated=%s recombined=%s reason_code=%s",
        ledger.owner_id.value,
        belief.feature_kind.value,
        belief.channel.value,
        belief.hop_index,
        belief.mutated,
        belief.recombined,
        "upsert",
    )
    return result


def form_or_reinforce_cultural_belief(
    ledger: CulturalFeatureLedger,
    *,
    feature_kind: object,
    content_key: str,
    content_fingerprint: str,
    channel: object,
    confidence: float,
    tick: int,
    enabled_provenance_channels: Sequence[str],
    parent_belief_ids: Sequence[str] = (),
    evidence_refs: Sequence[str] = (),
    parent_hop_index: int | None = None,
    belief_id: str | None = None,
    reinforce_delta: float = _REINFORCE_DELTA_DEFAULT,
) -> CulturalFeatureLedger:
    """Form a new belief or reinforce an existing row sharing ``content_key``.

    Channel must be in ``enabled_provenance_channels``. Independent rediscovery
    forces ``hop_index=0`` and empty parents. Child hops increment from parents.
    """
    if type(ledger) is not CulturalFeatureLedger:
        raise _fail("ledger", "invalid_type")
    kind = parse_cultural_feature_kind(feature_kind)
    channel_id = parse_cultural_transmission_channel(channel)
    enabled = {
        parse_cultural_transmission_channel(item).value
        for item in enabled_provenance_channels
    }
    if channel_id.value not in enabled:
        _LOG.error(
            "cultural_feature_validation_failed field=%s reason_code=%s code=%s",
            "channel",
            "channel_not_enabled",
            "channel_not_enabled",
        )
        raise _fail("channel", "channel_not_enabled")

    key = require_stable_id("content_key", content_key)
    fingerprint = require_stable_id("content_fingerprint", content_fingerprint)
    tick_i = require_exact_nonneg_int("tick", tick)
    conf = _unit_interval("confidence", confidence)
    parents = tuple(
        require_stable_id("parent_belief_ids", item) for item in parent_belief_ids
    )
    if channel_id is CulturalTransmissionChannelId.INDEPENDENT_REDISCOVERY and parents:
        raise _fail("parent_belief_ids", "independent_rediscovery_no_parents")

    refs = _cap_evidence_refs(evidence_refs, max_refs=ledger.max_evidence_refs)
    if (
        channel_id is not CulturalTransmissionChannelId.INDEPENDENT_REDISCOVERY
        and not refs
        and not parents
    ):
        raise _fail("evidence_refs", "provenance_required")

    existing: SubjectiveCulturalBelief | None = None
    for row in ledger.beliefs:
        if row.content_key == key and row.feature_kind is kind:
            existing = row
            break

    if existing is not None:
        merged_refs = _cap_evidence_refs(
            [*existing.evidence_refs, *refs], max_refs=ledger.max_evidence_refs
        )
        reinforced = SubjectiveCulturalBelief(
            belief_id=existing.belief_id,
            owner_agent_id=ledger.owner_id,
            feature_kind=existing.feature_kind,
            content_key=existing.content_key,
            content_fingerprint=fingerprint,
            channel=existing.channel,
            confidence=_quantize_unit(
                min(
                    1.0,
                    existing.confidence
                    + _unit_interval("reinforce_delta", reinforce_delta),
                )
            ),
            parent_belief_ids=existing.parent_belief_ids,
            hop_index=existing.hop_index,
            mutated=existing.mutated,
            recombined=existing.recombined,
            evidence_refs=merged_refs,
            acquired_tick=existing.acquired_tick,
            last_updated_tick=tick_i,
            policy_version=existing.policy_version,
        )
        result = upsert_cultural_belief(ledger, reinforced)
        _LOG.debug(
            "cultural_feature_reinforce owner_id=%s feature_kind=%s channel=%s "
            "hop_index=%s mutated=%s recombined=%s reason_code=%s",
            ledger.owner_id.value,
            reinforced.feature_kind.value,
            reinforced.channel.value,
            reinforced.hop_index,
            reinforced.mutated,
            reinforced.recombined,
            "reinforce",
        )
        return result

    hop = _resolve_hop_index(
        ledger,
        channel=channel_id,
        parent_belief_ids=parents,
        parent_hop_index=parent_hop_index,
    )
    if hop > CULTURAL_FEATURE_DEFAULT_HOP_CAP:
        _LOG.error(
            "cultural_feature_validation_failed field=%s reason_code=%s code=%s",
            "hop_index",
            "cultural_feature_hop_cap",
            "cultural_feature_hop_cap",
        )
        raise _fail("hop_index", "cultural_feature_hop_cap")

    if belief_id is None:
        belief_id = f"cf:{ledger.owner_id.value}:{kind.value}:{key}:h{hop}"
    new_belief = SubjectiveCulturalBelief(
        belief_id=belief_id,
        owner_agent_id=ledger.owner_id,
        feature_kind=kind,
        content_key=key,
        content_fingerprint=fingerprint,
        channel=channel_id,
        confidence=conf,
        parent_belief_ids=parents,
        hop_index=hop,
        mutated=False,
        recombined=False,
        evidence_refs=refs,
        acquired_tick=tick_i,
        last_updated_tick=tick_i,
    )
    result = upsert_cultural_belief(ledger, new_belief)
    _LOG.debug(
        "cultural_feature_form owner_id=%s feature_kind=%s channel=%s "
        "hop_index=%s mutated=%s recombined=%s reason_code=%s",
        ledger.owner_id.value,
        new_belief.feature_kind.value,
        new_belief.channel.value,
        new_belief.hop_index,
        False,
        False,
        "formed",
    )
    return result


def mutate_cultural_belief(
    ledger: CulturalFeatureLedger,
    *,
    belief_id: str,
    tick: int,
    allow_mutation: bool,
    mutation_requires_evidence: bool,
    owner_evidence_present: bool,
    max_token_edits: int,
    rng_namespace: str,
    seed_material: str = "0",
) -> CulturalFeatureLedger:
    """Edit opaque fingerprint tokens when mutation policy allows."""
    if type(ledger) is not CulturalFeatureLedger:
        raise _fail("ledger", "invalid_type")
    if not allow_mutation:
        _LOG.debug(
            "cultural_feature_mutation_skip owner_id=%s reason_code=%s",
            ledger.owner_id.value,
            "mutation_disabled",
        )
        return ledger
    if mutation_requires_evidence and not owner_evidence_present:
        _LOG.debug(
            "cultural_feature_mutation_skip owner_id=%s reason_code=%s",
            ledger.owner_id.value,
            "mutation_requires_evidence",
        )
        return ledger
    token = require_stable_id("belief_id", belief_id)
    tick_i = require_exact_nonneg_int("tick", tick)
    edits = require_exact_nonneg_int("max_token_edits", max_token_edits)
    if edits > 8:
        raise _fail("max_token_edits", "out_of_range")
    if edits == 0:
        return ledger
    namespace = require_stable_id("rng_namespace", rng_namespace)
    seed = require_stable_id("seed_material", seed_material)
    current = _belief_by_id(ledger, token)
    if current is None:
        raise _fail("belief_id", "unknown_belief")

    tokens = _fingerprint_tokens(current.content_fingerprint)
    edit_count = min(edits, len(tokens))
    material = f"{namespace}:{seed}:{token}:{tick_i}"
    for index in range(edit_count):
        # Deterministic pick of which token to edit (cycle through).
        pick = int(hashlib.sha256(f"{material}:pick:{index}".encode()).hexdigest(), 16)
        target = pick % len(tokens)
        replacement = hashlib.sha256(
            f"{material}:edit:{index}:{tokens[target]}".encode()
        ).hexdigest()[:_FINGERPRINT_TOKEN_WIDTH]
        tokens[target] = replacement
    new_fingerprint = _join_fingerprint_tokens(tokens)
    mutated = SubjectiveCulturalBelief(
        belief_id=current.belief_id,
        owner_agent_id=current.owner_agent_id,
        feature_kind=current.feature_kind,
        content_key=current.content_key,
        content_fingerprint=new_fingerprint,
        channel=current.channel,
        confidence=current.confidence,
        parent_belief_ids=current.parent_belief_ids,
        hop_index=current.hop_index,
        mutated=True,
        recombined=current.recombined,
        evidence_refs=current.evidence_refs,
        acquired_tick=current.acquired_tick,
        last_updated_tick=tick_i,
        policy_version=current.policy_version,
    )
    result = upsert_cultural_belief(ledger, mutated)
    _LOG.debug(
        "cultural_feature_mutation owner_id=%s feature_kind=%s channel=%s "
        "hop_index=%s mutated=%s recombined=%s reason_code=%s",
        ledger.owner_id.value,
        mutated.feature_kind.value,
        mutated.channel.value,
        mutated.hop_index,
        True,
        mutated.recombined,
        "mutated",
    )
    return result


def recombine_cultural_beliefs(
    ledger: CulturalFeatureLedger,
    *,
    parent_belief_ids: Sequence[str],
    tick: int,
    allow_recombination: bool,
    max_parents: int,
    min_token_overlap: float,
    enabled_provenance_channels: Sequence[str],
    channel: object = CulturalTransmissionChannelId.INDEPENDENT_REDISCOVERY,
    content_key: str | None = None,
    confidence: float = 0.4,
) -> CulturalFeatureLedger:
    """Form a recombined belief from ≥2 same-kind parents meeting overlap."""
    if type(ledger) is not CulturalFeatureLedger:
        raise _fail("ledger", "invalid_type")
    if not allow_recombination:
        _LOG.debug(
            "cultural_feature_recombination_skip owner_id=%s reason_code=%s",
            ledger.owner_id.value,
            "recombination_disabled",
        )
        return ledger
    parent_cap = require_exact_nonneg_int("max_parents", max_parents)
    if parent_cap < 2 or parent_cap > 4:
        raise _fail("max_parents", "out_of_range")
    overlap_floor = _unit_interval("min_token_overlap", min_token_overlap)
    ordered_ids = tuple(
        require_stable_id("parent_belief_ids", item) for item in parent_belief_ids
    )
    if len(ordered_ids) < 2:
        raise _fail("parent_belief_ids", "recombination_requires_parents")
    if len(ordered_ids) > parent_cap:
        raise _fail("parent_belief_ids", "max_parents_exceeded")
    if len(set(ordered_ids)) != len(ordered_ids):
        raise _fail("parent_belief_ids", "duplicate_parent")

    parents: list[SubjectiveCulturalBelief] = []
    for parent_id in ordered_ids:
        parent = _belief_by_id(ledger, parent_id)
        if parent is None:
            raise _fail("parent_belief_ids", "unknown_parent")
        parents.append(parent)
    kind = parents[0].feature_kind
    if any(parent.feature_kind is not kind for parent in parents):
        raise _fail("parent_belief_ids", "kind_mismatch")
    for left_index, left in enumerate(parents):
        for right in parents[left_index + 1 :]:
            if _token_jaccard(left.content_fingerprint, right.content_fingerprint) < (
                overlap_floor
            ):
                raise _fail("parent_belief_ids", "min_token_overlap")

    hop = max(parent.hop_index for parent in parents) + 1
    if hop > CULTURAL_FEATURE_DEFAULT_HOP_CAP:
        _LOG.error(
            "cultural_feature_validation_failed field=%s reason_code=%s code=%s",
            "hop_index",
            "cultural_feature_hop_cap",
            "cultural_feature_hop_cap",
        )
        raise _fail("hop_index", "cultural_feature_hop_cap")

    # Deterministic opaque merge: sorted unique parent tokens.
    merged_tokens: list[str] = []
    seen_tokens: set[str] = set()
    for parent in parents:
        for part in _fingerprint_tokens(parent.content_fingerprint):
            if part not in seen_tokens:
                seen_tokens.add(part)
                merged_tokens.append(part)
    fingerprint = _join_fingerprint_tokens(merged_tokens)
    key = (
        require_stable_id("content_key", content_key)
        if content_key is not None
        else require_stable_id(
            "content_key",
            f"recomb:{kind.value}:{':'.join(ordered_ids)}",
        )
    )
    # Prefer teaching/observation if enabled; otherwise first enabled channel.
    channel_id = parse_cultural_transmission_channel(channel)
    enabled = {
        parse_cultural_transmission_channel(item).value
        for item in enabled_provenance_channels
    }
    if channel_id.value not in enabled:
        # Recombination records under first enabled channel when caller default off.
        if not enabled:
            raise _fail("channel", "channel_not_enabled")
        channel_id = parse_cultural_transmission_channel(sorted(enabled)[0])
    # Independent rediscovery forbids parents — switch channel if needed.
    if channel_id is CulturalTransmissionChannelId.INDEPENDENT_REDISCOVERY:
        for candidate in (
            CulturalTransmissionChannelId.OBSERVATION,
            CulturalTransmissionChannelId.COMMUNICATION,
            CulturalTransmissionChannelId.TEACHING,
            CulturalTransmissionChannelId.IMITATION,
            CulturalTransmissionChannelId.ARTIFACT,
        ):
            if candidate.value in enabled:
                channel_id = candidate
                break
        else:
            raise _fail("channel", "channel_not_enabled")

    tick_i = require_exact_nonneg_int("tick", tick)
    belief_id = f"cf:{ledger.owner_id.value}:{kind.value}:{key}:h{hop}:recomb"
    evidence = _cap_evidence_refs(
        [f"parent:{parent_id}" for parent_id in ordered_ids],
        max_refs=ledger.max_evidence_refs,
    )
    belief = SubjectiveCulturalBelief(
        belief_id=belief_id,
        owner_agent_id=ledger.owner_id,
        feature_kind=kind,
        content_key=key,
        content_fingerprint=fingerprint,
        channel=channel_id,
        confidence=confidence,
        parent_belief_ids=ordered_ids,
        hop_index=hop,
        mutated=False,
        recombined=True,
        evidence_refs=evidence,
        acquired_tick=tick_i,
        last_updated_tick=tick_i,
    )
    result = upsert_cultural_belief(ledger, belief)
    _LOG.debug(
        "cultural_feature_recombination owner_id=%s feature_kind=%s channel=%s "
        "hop_index=%s mutated=%s recombined=%s parent_count=%s reason_code=%s",
        ledger.owner_id.value,
        belief.feature_kind.value,
        belief.channel.value,
        belief.hop_index,
        False,
        True,
        len(ordered_ids),
        "recombined",
    )
    return result


def cultural_feature_bias_futures(
    *,
    ledger: CulturalFeatureLedger | None,
    bias_policy: object | None,
    futures: Sequence[object],
) -> dict[str, float]:
    """Float bias toward communicate/practice futures aligned with beliefs.

    Mode ``ignore`` (or absent bias/ledger) is passthrough. Never injects
    analytical traits — only owner-scoped subjective confidence bands.
    """
    if ledger is None or bias_policy is None or not futures:
        return {}
    mode = getattr(bias_policy, "mode", "ignore")
    if mode != "prefer_aligned_features":
        _LOG.debug(
            "cultural_feature_bias_skip reason_code=%s",
            "bias_ignore",
        )
        return {}
    weight = _unit_interval(
        "communicate_weight", getattr(bias_policy, "communicate_weight", 0.0)
    )
    if weight <= 0.0:
        return {}
    affinity = bool(getattr(bias_policy, "content_affinity", False))
    # High-confidence beliefs (confidence_band high) drive partner/token bias.
    high_keys: set[str] = set()
    high_kinds: set[str] = set()
    for belief in ledger.beliefs:
        if _confidence_band(belief.confidence) != "high":
            continue
        high_keys.add(belief.content_key)
        high_kinds.add(belief.feature_kind.value)
    if not high_keys and not high_kinds:
        return {}
    biases: dict[str, float] = {}
    for future in futures:
        future_id = getattr(future, "future_id", None)
        direction = getattr(getattr(future, "direction", None), "value", None)
        if future_id is None or direction not in {"communicate", "help", "search"}:
            continue
        applied = _quantize_unit(weight)
        content_token = getattr(future, "content_key", None)
        if affinity and isinstance(content_token, str) and content_token in high_keys:
            applied = _quantize_unit(min(1.0, applied + _CONTENT_AFFINITY_BOOST))
            reason = "content_affinity"
        else:
            # Prefer communicate toward any partner when owner holds high-confidence
            # cultural features (partner id optional metadata only).
            reason = "aligned_features"
        biases[str(future_id)] = applied
        _LOG.debug(
            "cultural_feature_bias_applied partner_or_token_band=%s weight_band=%s "
            "reason_code=%s",
            _confidence_band(applied),
            _confidence_band(applied),
            reason,
        )
    return biases


# ---------------------------------------------------------------------------
# Public uptake / compose (Tasks 9-11) — never copy peer ledgers
# ---------------------------------------------------------------------------

_FEATURE_KIND_PRIMARY_CHANNELS: Final[dict[CulturalFeatureKindId, frozenset[str]]] = {
    CulturalFeatureKindId.PRACTICE: frozenset(
        {"observation", "imitation", "teaching", "communication", "artifact"}
    ),
    CulturalFeatureKindId.NARRATIVE_ELEMENT: frozenset(
        {"communication", "teaching", "observation", "artifact"}
    ),
    CulturalFeatureKindId.TERM: frozenset({"communication", "teaching", "artifact"}),
    CulturalFeatureKindId.PRODUCTION_TECHNIQUE: frozenset(
        {"observation", "imitation", "teaching"}
    ),
    CulturalFeatureKindId.SOCIAL_EXPECTATION: frozenset(
        {"observation", "communication", "teaching", "artifact"}
    ),
    CulturalFeatureKindId.SYMBOLIC_ASSOCIATION: frozenset(
        {"artifact", "communication", "observation"}
    ),
}

# Durable-record genre → cultural feature kind (v3-11; never writes kinship/history).
_DURABLE_GENRE_FEATURE_KINDS: Final[dict[str, CulturalFeatureKindId]] = {
    "warning": CulturalFeatureKindId.SYMBOLIC_ASSOCIATION,
    "instruction": CulturalFeatureKindId.PRACTICE,
    "map": CulturalFeatureKindId.SYMBOLIC_ASSOCIATION,
    "story": CulturalFeatureKindId.NARRATIVE_ELEMENT,
    "agreement": CulturalFeatureKindId.SOCIAL_EXPECTATION,
    "inventory_record": CulturalFeatureKindId.PRACTICE,
    "genealogy": CulturalFeatureKindId.SYMBOLIC_ASSOCIATION,
    "chronicle": CulturalFeatureKindId.NARRATIVE_ELEMENT,
}

_TEACHING_DOMAIN_TO_FEATURE_KINDS: Final[
    dict[str, tuple[CulturalFeatureKindId, ...]]
] = {
    "foraging": (CulturalFeatureKindId.PRACTICE,),
    "navigation": (CulturalFeatureKindId.PRACTICE,),
    "resource_detection": (CulturalFeatureKindId.PRACTICE,),
    "crafting": (CulturalFeatureKindId.PRODUCTION_TECHNIQUE,),
    "building": (CulturalFeatureKindId.PRODUCTION_TECHNIQUE,),
    "healing": (CulturalFeatureKindId.PRACTICE,),
    "communication": (
        CulturalFeatureKindId.PRACTICE,
        CulturalFeatureKindId.SOCIAL_EXPECTATION,
    ),
    "teaching": (CulturalFeatureKindId.PRACTICE,),
    "stories": (CulturalFeatureKindId.NARRATIVE_ELEMENT,),
    "vocabulary": (CulturalFeatureKindId.TERM,),
    "social_practices": (
        CulturalFeatureKindId.PRACTICE,
        CulturalFeatureKindId.SOCIAL_EXPECTATION,
    ),
    "production_recipes": (CulturalFeatureKindId.PRODUCTION_TECHNIQUE,),
}

_MENTORSHIP_CONTENT_TO_FEATURE_KINDS: Final[
    dict[str, tuple[CulturalFeatureKindId, ...]]
] = {
    "stories": (CulturalFeatureKindId.NARRATIVE_ELEMENT,),
    "vocabulary": (CulturalFeatureKindId.TERM,),
    "social_practices": (
        CulturalFeatureKindId.PRACTICE,
        CulturalFeatureKindId.SOCIAL_EXPECTATION,
    ),
    "production_recipes": (CulturalFeatureKindId.PRODUCTION_TECHNIQUE,),
    "practical_skills": (CulturalFeatureKindId.PRACTICE,),
    "warnings": (CulturalFeatureKindId.SOCIAL_EXPECTATION,),
}


@dataclass(frozen=True, slots=True)
class CulturalFeatureUptakeCue:
    """Opaque public cue for cultural-feature uptake (never peer ledger rows)."""

    feature_kind: CulturalFeatureKindId
    channel: CulturalTransmissionChannelId
    content_key: str
    content_fingerprint: str
    evidence_refs: tuple[str, ...]
    confidence: float = 0.4


def collect_cultural_feature_public_cues(
    observation: object | None,
) -> tuple[CulturalFeatureUptakeCue, ...]:
    """Collect observation / imitation / communication cues from public evidence."""
    if observation is None:
        return ()
    tick = int(getattr(observation, "tick", 0))
    cues: list[CulturalFeatureUptakeCue] = []

    for communication in getattr(observation, "communications", ()) or ():
        speaker = getattr(communication, "speaker_id", None)
        speaker_token = getattr(speaker, "value", None)
        if not isinstance(speaker_token, str):
            continue
        action = getattr(communication, "action_kind", "talk")
        utterance = getattr(communication, "utterance", None)
        declared = getattr(utterance, "declared", None)
        claim = getattr(declared, "claim_id", None) or getattr(
            declared, "proposition_id", None
        )
        hop = getattr(declared, "hop_count", 0)
        if claim is None:
            claim = f"comm:{speaker_token}:{getattr(communication, 'event_id', hop)}"
        claim_token = getattr(claim, "value", claim)
        if not isinstance(claim_token, str):
            continue
        evidence = (f"comm:{tick}:{action}:{claim_token}",)
        for kind, key_prefix in (
            (CulturalFeatureKindId.TERM, "term"),
            (CulturalFeatureKindId.NARRATIVE_ELEMENT, "narrative"),
            (CulturalFeatureKindId.SOCIAL_EXPECTATION, "expect"),
        ):
            cues.append(
                CulturalFeatureUptakeCue(
                    feature_kind=kind,
                    channel=CulturalTransmissionChannelId.COMMUNICATION,
                    content_key=f"{key_prefix}:{claim_token}",
                    content_fingerprint=(
                        f"fp:{key_prefix}:{speaker_token}:{claim_token}:{hop}"
                    ),
                    evidence_refs=evidence,
                    confidence=0.4,
                )
            )

    for occurrence in getattr(observation, "occurrences", ()) or ():
        kind_raw = str(getattr(occurrence, "kind", "act")).lower()
        event_id = getattr(getattr(occurrence, "provenance", None), "event_id", None)
        evidence_token = (
            f"evt:{event_id.value}"
            if event_id is not None and hasattr(event_id, "value")
            else f"occ:{tick}:{kind_raw}"
        )
        other = getattr(occurrence, "other_entity_id", None)
        success = getattr(occurrence, "success", None)
        if success is not False:
            cues.append(
                CulturalFeatureUptakeCue(
                    feature_kind=CulturalFeatureKindId.PRACTICE,
                    channel=CulturalTransmissionChannelId.OBSERVATION,
                    content_key=f"practice:{kind_raw}",
                    content_fingerprint=f"fp:obs:practice:{kind_raw}",
                    evidence_refs=(evidence_token,),
                    confidence=0.35,
                )
            )
            if "craft" in kind_raw or "build" in kind_raw or "produce" in kind_raw:
                cues.append(
                    CulturalFeatureUptakeCue(
                        feature_kind=CulturalFeatureKindId.PRODUCTION_TECHNIQUE,
                        channel=CulturalTransmissionChannelId.OBSERVATION,
                        content_key=f"technique:{kind_raw}",
                        content_fingerprint=f"fp:obs:technique:{kind_raw}",
                        evidence_refs=(evidence_token,),
                        confidence=0.35,
                    )
                )
            cues.append(
                CulturalFeatureUptakeCue(
                    feature_kind=CulturalFeatureKindId.SOCIAL_EXPECTATION,
                    channel=CulturalTransmissionChannelId.OBSERVATION,
                    content_key=f"expect:{kind_raw}",
                    content_fingerprint=f"fp:obs:expect:{kind_raw}",
                    evidence_refs=(evidence_token,),
                    confidence=0.3,
                )
            )
        if other is not None and (
            success is True or "success" in kind_raw or "complete" in kind_raw
        ):
            other_token = other.value if hasattr(other, "value") else str(other)
            cues.append(
                CulturalFeatureUptakeCue(
                    feature_kind=CulturalFeatureKindId.PRACTICE,
                    channel=CulturalTransmissionChannelId.IMITATION,
                    content_key=f"imitate:{kind_raw}:{other_token}",
                    content_fingerprint=f"fp:imit:{other_token}:{kind_raw}",
                    evidence_refs=(evidence_token, f"actor:{other_token}"),
                    confidence=0.45,
                )
            )
            if "craft" in kind_raw or "build" in kind_raw or "produce" in kind_raw:
                cues.append(
                    CulturalFeatureUptakeCue(
                        feature_kind=CulturalFeatureKindId.PRODUCTION_TECHNIQUE,
                        channel=CulturalTransmissionChannelId.IMITATION,
                        content_key=f"imitate-tech:{kind_raw}:{other_token}",
                        content_fingerprint=f"fp:imit-tech:{other_token}:{kind_raw}",
                        evidence_refs=(evidence_token, f"actor:{other_token}"),
                        confidence=0.45,
                    )
                )

    for artifact in getattr(observation, "artifacts", ()) or ():
        entity = getattr(artifact, "entity_id", None)
        entity_token = getattr(entity, "value", None)
        if not isinstance(entity_token, str):
            continue
        author = getattr(artifact, "author_id", None)
        author_token = getattr(author, "value", "unknown")
        kind_token = getattr(getattr(artifact, "kind", None), "value", "mark")
        evidence = (f"artifact:{entity_token}",)
        genre = getattr(artifact, "record_genre", None)
        genre_token = getattr(genre, "value", None)
        feature_kind = _DURABLE_GENRE_FEATURE_KINDS.get(
            genre_token if isinstance(genre_token, str) else "",
            CulturalFeatureKindId.SYMBOLIC_ASSOCIATION,
        )
        content_prefix = (
            f"durable:{genre_token}"
            if isinstance(genre_token, str)
            else "symbol"
        )
        cues.append(
            CulturalFeatureUptakeCue(
                feature_kind=feature_kind,
                channel=CulturalTransmissionChannelId.ARTIFACT,
                content_key=f"{content_prefix}:{entity_token}",
                content_fingerprint=(
                    f"fp:{content_prefix}:{entity_token}:{kind_token}"
                ),
                evidence_refs=evidence,
                confidence=0.4,
            )
        )
        cues.append(
            CulturalFeatureUptakeCue(
                feature_kind=CulturalFeatureKindId.TERM,
                channel=CulturalTransmissionChannelId.ARTIFACT,
                content_key=f"term:artifact:{entity_token}",
                content_fingerprint=f"fp:term:{author_token}:{entity_token}",
                evidence_refs=evidence,
                confidence=0.35,
            )
        )

    for repository in getattr(observation, "repositories", ()) or ():
        repo_id = getattr(repository, "repository_id", None)
        repo_token = getattr(repo_id, "value", None)
        if not isinstance(repo_token, str):
            continue
        status = getattr(repository, "status", "intact")
        access = getattr(repository, "access_mode", None) or "container"
        # Subjective framing only — never library/archive/sacred labels.
        evidence = (f"repository:{repo_token}",)
        cues.append(
            CulturalFeatureUptakeCue(
                feature_kind=CulturalFeatureKindId.SYMBOLIC_ASSOCIATION,
                channel=CulturalTransmissionChannelId.OBSERVATION,
                content_key=f"container:{repo_token}",
                content_fingerprint=f"fp:container:{repo_token}:{status}",
                evidence_refs=evidence,
                confidence=0.4,
            )
        )
        cues.append(
            CulturalFeatureUptakeCue(
                feature_kind=CulturalFeatureKindId.PRACTICE,
                channel=CulturalTransmissionChannelId.OBSERVATION,
                content_key=f"custody-practice:{repo_token}:{access}",
                content_fingerprint=f"fp:custody:{repo_token}:{access}",
                evidence_refs=evidence,
                confidence=0.35,
            )
        )
    return tuple(cues)


def apply_cultural_feature_channel_uptake(
    ledger: CulturalFeatureLedger,
    *,
    enabled_feature_kinds: Sequence[str],
    enabled_provenance_channels: Sequence[str],
    cues: Sequence[CulturalFeatureUptakeCue],
    tick: int,
) -> tuple[CulturalFeatureLedger, tuple[CulturalFeatureAudit, ...]]:
    """Form beliefs from observation / imitation / communication public cues."""
    if type(ledger) is not CulturalFeatureLedger:
        raise _fail("ledger", "invalid_type")
    enabled_kinds = {
        parse_cultural_feature_kind(item).value for item in enabled_feature_kinds
    }
    enabled_channels = {
        parse_cultural_transmission_channel(item).value
        for item in enabled_provenance_channels
    }
    current = ledger
    audits: list[CulturalFeatureAudit] = []
    for cue in cues:
        if cue.feature_kind.value not in enabled_kinds:
            continue
        if cue.channel.value not in enabled_channels:
            continue
        primary = _FEATURE_KIND_PRIMARY_CHANNELS.get(cue.feature_kind, frozenset())
        if cue.channel.value not in primary:
            continue
        before_ids = {row.belief_id for row in current.beliefs}
        try:
            current = form_or_reinforce_cultural_belief(
                current,
                feature_kind=cue.feature_kind,
                content_key=cue.content_key,
                content_fingerprint=cue.content_fingerprint,
                channel=cue.channel,
                confidence=cue.confidence,
                tick=tick,
                enabled_provenance_channels=tuple(enabled_channels),
                evidence_refs=cue.evidence_refs,
            )
        except ValueError as exc:
            if "cultural_feature_hop_cap" in str(exc) or "channel_not_enabled" in str(
                exc
            ):
                continue
            raise
        belief = next(
            (
                row
                for row in current.beliefs
                if row.content_key == cue.content_key
                and row.feature_kind is cue.feature_kind
            ),
            None,
        )
        if belief is None:
            continue
        reason = "formed" if belief.belief_id not in before_ids else "reinforce"
        audits.append(belief_to_audit(belief, reason_code=f"channel_{reason}"))
        _LOG.debug(
            "cultural_feature_uptake channel=%s feature_kind=%s hop_index=%s "
            "reason_code=%s",
            cue.channel.value,
            cue.feature_kind.value,
            belief.hop_index,
            f"channel_{reason}",
        )
    return current, tuple(audits)


def apply_cultural_feature_from_teaching(
    ledger: CulturalFeatureLedger,
    *,
    enabled_feature_kinds: Sequence[str],
    enabled_provenance_channels: Sequence[str],
    advice_delta: Sequence[object],
    tick: int,
    teaching_compose_on: bool,
    teaching_mode_on: bool,
    mentorship_compose_on: bool = False,
    mentorship_channel_on: bool = False,
) -> tuple[CulturalFeatureLedger, tuple[CulturalFeatureAudit, ...]]:
    """Map teaching/mentorship public advice onto cultural kinds (no lineage clone)."""
    if type(ledger) is not CulturalFeatureLedger:
        raise _fail("ledger", "invalid_type")
    if not teaching_compose_on and not mentorship_compose_on:
        return ledger, ()
    if teaching_compose_on and not teaching_mode_on:
        _LOG.debug(
            "cultural_feature_compose_skip teaching_on=%s mentorship_on=%s "
            "mapped_kind=%s reason_code=%s",
            False,
            mentorship_compose_on,
            "teaching",
            "teaching_mode_off",
        )
    if mentorship_compose_on and not mentorship_channel_on:
        _LOG.debug(
            "cultural_feature_compose_skip teaching_on=%s mentorship_on=%s "
            "mapped_kind=%s reason_code=%s",
            teaching_compose_on,
            False,
            "mentorship",
            "mentorship_channel_off",
        )
    if "teaching" not in {
        parse_cultural_transmission_channel(item).value
        for item in enabled_provenance_channels
    }:
        _LOG.debug(
            "cultural_feature_compose_skip teaching_on=%s mentorship_on=%s "
            "mapped_kind=%s reason_code=%s",
            teaching_compose_on,
            mentorship_compose_on,
            "teaching",
            "teaching_channel_disabled",
        )
        return ledger, ()
    if not advice_delta:
        return ledger, ()
    enabled_kinds = {
        parse_cultural_feature_kind(item).value for item in enabled_feature_kinds
    }
    enabled_channels = tuple(
        parse_cultural_transmission_channel(item).value
        for item in enabled_provenance_channels
    )
    use_teaching = teaching_compose_on and teaching_mode_on
    use_mentorship_meta = mentorship_compose_on and mentorship_channel_on
    if not use_teaching and not use_mentorship_meta:
        return ledger, ()
    current = ledger
    audits: list[CulturalFeatureAudit] = []
    for row in advice_delta:
        teacher = getattr(row, "source_agent_id", None)
        teacher_token = getattr(teacher, "value", None)
        domain = getattr(getattr(row, "domain", None), "value", None)
        if not isinstance(domain, str):
            domain = getattr(getattr(row, "content_kind", None), "value", None)
        if not isinstance(domain, str):
            continue
        band = getattr(getattr(row, "band", None), "value", "unspecified")
        occurrence = getattr(row, "occurrence_id", None) or "teach"
        kinds = _TEACHING_DOMAIN_TO_FEATURE_KINDS.get(domain)
        if kinds is None:
            kinds = _MENTORSHIP_CONTENT_TO_FEATURE_KINDS.get(domain)
        if kinds is None:
            continue
        evidence: list[str] = [f"teach:{occurrence}"]
        if use_mentorship_meta and isinstance(teacher_token, str):
            evidence.append(f"mentor:{teacher_token}")
        for kind in kinds:
            if kind.value not in enabled_kinds:
                continue
            content_key = f"teach:{domain}:{kind.value}"
            fingerprint = f"fp:teach:{domain}:{band}"
            try:
                current = form_or_reinforce_cultural_belief(
                    current,
                    feature_kind=kind,
                    content_key=content_key,
                    content_fingerprint=fingerprint,
                    channel=CulturalTransmissionChannelId.TEACHING,
                    confidence=0.45,
                    tick=tick,
                    enabled_provenance_channels=enabled_channels,
                    evidence_refs=tuple(evidence),
                )
            except ValueError as exc:
                if "cultural_feature_hop_cap" in str(exc):
                    continue
                raise
            belief = next(
                (
                    item
                    for item in current.beliefs
                    if item.content_key == content_key and item.feature_kind is kind
                ),
                None,
            )
            if belief is None:
                continue
            audits.append(belief_to_audit(belief, reason_code="teaching_compose"))
            _LOG.debug(
                "cultural_feature_compose_write teaching_on=%s mentorship_on=%s "
                "mapped_kind=%s reason_code=%s",
                use_teaching,
                use_mentorship_meta,
                kind.value,
                "teaching_compose",
            )
    return current, tuple(audits)


def apply_cultural_feature_compose_adapters(
    ledger: CulturalFeatureLedger,
    *,
    enabled_feature_kinds: Sequence[str],
    enabled_provenance_channels: Sequence[str],
    tick: int,
    uptake_compose: object,
    naming_mode_on: bool = False,
    narrative_mode_on: bool = False,
    norms_mode_on: bool = False,
    conventions_mode_on: bool = False,
    artifacts_mode_on: bool = False,
    repositories_mode_on: bool = False,
    naming_keys: Sequence[tuple[str, str, str]] = (),
    narrative_keys: Sequence[tuple[str, str, str]] = (),
    norm_keys: Sequence[tuple[str, str, str]] = (),
    convention_keys: Sequence[tuple[str, str, str]] = (),
    artifact_keys: Sequence[tuple[str, str, str]] = (),
    repository_keys: Sequence[tuple[str, str, str]] = (),
) -> tuple[CulturalFeatureLedger, tuple[CulturalFeatureAudit, ...]]:
    """Optional V2 mode compose adapters (opaque keys only; no peer copy)."""
    if type(ledger) is not CulturalFeatureLedger:
        raise _fail("ledger", "invalid_type")
    compose = uptake_compose
    enabled_kinds = {
        parse_cultural_feature_kind(item).value for item in enabled_feature_kinds
    }
    enabled_channels = {
        parse_cultural_transmission_channel(item).value
        for item in enabled_provenance_channels
    }
    current = ledger
    audits: list[CulturalFeatureAudit] = []

    def _ingest(
        *,
        compose_bit: bool,
        mode_on: bool,
        skip_code: str,
        source_mode: str,
        feature_kind: CulturalFeatureKindId,
        channel: CulturalTransmissionChannelId,
        rows: Sequence[tuple[str, str, str]],
    ) -> None:
        nonlocal current
        if not compose_bit:
            return
        if feature_kind.value not in enabled_kinds:
            return
        if channel.value not in enabled_channels:
            _LOG.debug(
                "cultural_feature_compose_skip source_mode=%s feature_kind=%s "
                "reason_code=%s",
                source_mode,
                feature_kind.value,
                "channel_disabled",
            )
            return
        if not mode_on:
            _LOG.debug(
                "cultural_feature_compose_skip source_mode=%s feature_kind=%s "
                "reason_code=%s",
                source_mode,
                feature_kind.value,
                skip_code,
            )
            return
        for _source, content_key, fingerprint in rows:
            try:
                current = form_or_reinforce_cultural_belief(
                    current,
                    feature_kind=feature_kind,
                    content_key=content_key,
                    content_fingerprint=fingerprint,
                    channel=channel,
                    confidence=0.4,
                    tick=tick,
                    enabled_provenance_channels=tuple(enabled_channels),
                    evidence_refs=(f"compose:{source_mode}:{content_key}",),
                )
            except ValueError as exc:
                if "cultural_feature_hop_cap" in str(exc):
                    continue
                raise
            belief = next(
                (
                    item
                    for item in current.beliefs
                    if item.content_key == content_key
                    and item.feature_kind is feature_kind
                ),
                None,
            )
            if belief is None:
                continue
            audits.append(
                belief_to_audit(belief, reason_code=f"compose_{source_mode}")
            )
            _LOG.debug(
                "cultural_feature_compose_write source_mode=%s feature_kind=%s "
                "reason_code=%s",
                source_mode,
                feature_kind.value,
                f"compose_{source_mode}",
            )

    naming_on = bool(getattr(compose, "naming", False))
    narrative_on = bool(getattr(compose, "narrative", False))
    norms_on = bool(getattr(compose, "norms", False))
    conventions_on = bool(getattr(compose, "conventions", False))
    artifacts_on = bool(getattr(compose, "artifacts", False))

    _ingest(
        compose_bit=naming_on,
        mode_on=naming_mode_on,
        skip_code="naming_mode_off",
        source_mode="naming",
        feature_kind=CulturalFeatureKindId.TERM,
        channel=CulturalTransmissionChannelId.COMMUNICATION,
        rows=naming_keys,
    )
    _ingest(
        compose_bit=narrative_on,
        mode_on=narrative_mode_on,
        skip_code="narrative_mode_off",
        source_mode="narrative",
        feature_kind=CulturalFeatureKindId.NARRATIVE_ELEMENT,
        channel=CulturalTransmissionChannelId.COMMUNICATION,
        rows=narrative_keys,
    )
    _ingest(
        compose_bit=narrative_on,
        mode_on=narrative_mode_on,
        skip_code="narrative_mode_off",
        source_mode="narrative",
        feature_kind=CulturalFeatureKindId.SYMBOLIC_ASSOCIATION,
        channel=CulturalTransmissionChannelId.OBSERVATION,
        rows=tuple(
            (src, f"symbol-narr:{key}", fp) for src, key, fp in narrative_keys
        ),
    )
    _ingest(
        compose_bit=norms_on,
        mode_on=norms_mode_on,
        skip_code="norms_mode_off",
        source_mode="norms",
        feature_kind=CulturalFeatureKindId.SOCIAL_EXPECTATION,
        channel=CulturalTransmissionChannelId.OBSERVATION,
        rows=norm_keys,
    )
    _ingest(
        compose_bit=conventions_on,
        mode_on=conventions_mode_on,
        skip_code="conventions_mode_off",
        source_mode="conventions",
        feature_kind=CulturalFeatureKindId.PRACTICE,
        channel=CulturalTransmissionChannelId.OBSERVATION,
        rows=convention_keys,
    )
    _ingest(
        compose_bit=conventions_on,
        mode_on=conventions_mode_on,
        skip_code="conventions_mode_off",
        source_mode="conventions",
        feature_kind=CulturalFeatureKindId.SOCIAL_EXPECTATION,
        channel=CulturalTransmissionChannelId.OBSERVATION,
        rows=tuple(
            (src, f"expect-conv:{key}", fp) for src, key, fp in convention_keys
        ),
    )
    _ingest(
        compose_bit=artifacts_on,
        mode_on=artifacts_mode_on,
        skip_code="artifacts_mode_off",
        source_mode="artifacts",
        feature_kind=CulturalFeatureKindId.SYMBOLIC_ASSOCIATION,
        channel=CulturalTransmissionChannelId.ARTIFACT,
        rows=artifact_keys,
    )
    _ingest(
        compose_bit=artifacts_on,
        mode_on=artifacts_mode_on,
        skip_code="artifacts_mode_off",
        source_mode="artifacts",
        feature_kind=CulturalFeatureKindId.TERM,
        channel=CulturalTransmissionChannelId.ARTIFACT,
        rows=tuple((src, f"term-art:{key}", fp) for src, key, fp in artifact_keys),
    )
    repositories_on = bool(getattr(compose, "repositories", False))
    _ingest(
        compose_bit=repositories_on,
        mode_on=repositories_mode_on,
        skip_code="repositories_mode_off",
        source_mode="repositories",
        feature_kind=CulturalFeatureKindId.SYMBOLIC_ASSOCIATION,
        channel=CulturalTransmissionChannelId.OBSERVATION,
        rows=repository_keys,
    )
    _ingest(
        compose_bit=repositories_on,
        mode_on=repositories_mode_on,
        skip_code="repositories_mode_off",
        source_mode="repositories",
        feature_kind=CulturalFeatureKindId.PRACTICE,
        channel=CulturalTransmissionChannelId.OBSERVATION,
        rows=tuple(
            (src, f"practice-repo:{key}", fp) for src, key, fp in repository_keys
        ),
    )
    return current, tuple(audits)


def collect_cultural_feature_compose_keys(
    *,
    semantic_naming: object | None = None,
    cultural_narratives: object | None = None,
    social_norms: object | None = None,
    social_conventions: object | None = None,
    artifact_interpretations: object | None = None,
    observation: object | None = None,
) -> dict[str, tuple[tuple[str, str, str], ...]]:
    """Collect opaque (source, content_key, fingerprint) rows for compose adapters."""

    def _ledger_keys(
        ledger: object | None, *, prefix: str, id_attrs: tuple[str, ...]
    ) -> list[tuple[str, str, str]]:
        if ledger is None:
            return []
        out: list[tuple[str, str, str]] = []
        entries = (
            getattr(ledger, "entries", None)
            or getattr(ledger, "interpretations", None)
            or getattr(ledger, "beliefs", None)
            or ()
        )
        for entry in entries:
            source = (
                getattr(entry, "source_agent_id", None)
                or getattr(entry, "author_id", None)
                or getattr(entry, "teacher_agent_id", None)
            )
            source_token = getattr(source, "value", None)
            if not isinstance(source_token, str):
                source_token = "public"
            key = None
            for attr in id_attrs:
                key = getattr(entry, attr, None)
                if key is not None:
                    break
            key_token = getattr(key, "value", key)
            if not isinstance(key_token, str):
                continue
            fp = getattr(entry, "fingerprint", None) or f"fp:{prefix}:{key_token}"
            fp_token = getattr(fp, "value", fp)
            if not isinstance(fp_token, str):
                fp_token = f"fp:{prefix}:{key_token}"
            out.append((source_token, f"{prefix}:{key_token}", fp_token))
        return out

    return {
        "naming_keys": tuple(
            _ledger_keys(
                semantic_naming,
                prefix="vocab",
                id_attrs=("term_id", "name_id", "concept_key", "binding_id"),
            )
        ),
        "narrative_keys": tuple(
            _ledger_keys(
                cultural_narratives,
                prefix="story",
                id_attrs=("narrative_id", "variant_id", "concept_key"),
            )
        ),
        "norm_keys": tuple(
            _ledger_keys(
                social_norms,
                prefix="norm",
                id_attrs=("norm_id", "expectation_id", "concept_key"),
            )
        ),
        "convention_keys": tuple(
            _ledger_keys(
                social_conventions,
                prefix="practice",
                id_attrs=("convention_id", "habit_id", "concept_key"),
            )
        ),
        "artifact_keys": tuple(
            _ledger_keys(
                artifact_interpretations,
                prefix="artifact",
                id_attrs=("artifact_id", "mark_id", "entity_id"),
            )
        ),
        "repository_keys": tuple(
            _repository_compose_keys(observation)
        ),
    }


def _repository_compose_keys(
    observation: object | None,
) -> list[tuple[str, str, str]]:
    if observation is None:
        return []
    out: list[tuple[str, str, str]] = []
    for repository in getattr(observation, "repositories", ()) or ():
        repo_id = getattr(repository, "repository_id", None)
        repo_token = getattr(repo_id, "value", None)
        if not isinstance(repo_token, str):
            continue
        status = getattr(repository, "status", "intact")
        out.append(
            (
                "public",
                f"repository:{repo_token}",
                f"fp:repository:{repo_token}:{status}",
            )
        )
    return out


def log_unsatisfiable_feature_kinds(
    *,
    enabled_feature_kinds: Sequence[str],
    enabled_provenance_channels: Sequence[str],
    uptake_compose: object,
    naming_mode_on: bool = False,
    narrative_mode_on: bool = False,
    norms_mode_on: bool = False,
    conventions_mode_on: bool = False,
    artifacts_mode_on: bool = False,
    repositories_mode_on: bool = False,
    teaching_mode_on: bool = False,
    mentorship_channel_on: bool = False,
) -> tuple[str, ...]:
    """DEBUG skip when an enabled kind has no channel and no compose path."""
    enabled_channels = {
        parse_cultural_transmission_channel(item).value
        for item in enabled_provenance_channels
    }
    compose = uptake_compose
    unsat: list[str] = []
    for raw in enabled_feature_kinds:
        kind = parse_cultural_feature_kind(raw)
        primary = _FEATURE_KIND_PRIMARY_CHANNELS.get(kind, frozenset())
        channel_ok = bool(primary & enabled_channels)
        compose_ok = False
        if kind is CulturalFeatureKindId.TERM:
            compose_ok = (
                (bool(getattr(compose, "naming", False)) and naming_mode_on)
                or (bool(getattr(compose, "teaching", False)) and teaching_mode_on)
                or (
                    bool(getattr(compose, "mentorship", False))
                    and mentorship_channel_on
                )
                or (bool(getattr(compose, "artifacts", False)) and artifacts_mode_on)
            )
        elif kind is CulturalFeatureKindId.NARRATIVE_ELEMENT:
            compose_ok = (
                (bool(getattr(compose, "narrative", False)) and narrative_mode_on)
                or (bool(getattr(compose, "teaching", False)) and teaching_mode_on)
                or (
                    bool(getattr(compose, "mentorship", False))
                    and mentorship_channel_on
                )
            )
        elif kind is CulturalFeatureKindId.PRACTICE:
            compose_ok = (
                (
                    bool(getattr(compose, "conventions", False))
                    and conventions_mode_on
                )
                or (
                    bool(getattr(compose, "repositories", False))
                    and repositories_mode_on
                )
                or (bool(getattr(compose, "teaching", False)) and teaching_mode_on)
                or (
                    bool(getattr(compose, "mentorship", False))
                    and mentorship_channel_on
                )
            )
        elif kind is CulturalFeatureKindId.SOCIAL_EXPECTATION:
            compose_ok = (
                (bool(getattr(compose, "norms", False)) and norms_mode_on)
                or (
                    bool(getattr(compose, "conventions", False))
                    and conventions_mode_on
                )
                or (bool(getattr(compose, "teaching", False)) and teaching_mode_on)
                or (
                    bool(getattr(compose, "mentorship", False))
                    and mentorship_channel_on
                )
            )
        elif kind is CulturalFeatureKindId.PRODUCTION_TECHNIQUE:
            compose_ok = (
                (bool(getattr(compose, "teaching", False)) and teaching_mode_on)
                or (
                    bool(getattr(compose, "mentorship", False))
                    and mentorship_channel_on
                )
            )
        elif kind is CulturalFeatureKindId.SYMBOLIC_ASSOCIATION:
            compose_ok = (
                (bool(getattr(compose, "artifacts", False)) and artifacts_mode_on)
                or (bool(getattr(compose, "narrative", False)) and narrative_mode_on)
                or (
                    bool(getattr(compose, "repositories", False))
                    and repositories_mode_on
                )
            )
        if not channel_ok and not compose_ok:
            unsat.append(kind.value)
            _LOG.debug(
                "cultural_feature_kind_unsatisfiable feature_kind=%s reason_code=%s",
                kind.value,
                "cultural_feature_kind_unsatisfiable",
            )
    return tuple(unsat)
